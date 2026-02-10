# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 10.02.2026
Version: 1.0
Beschreibung: Context7 MCP Specialist fuer Library-Dokumentation im External Bureau.
              Duenner Wrapper um doc_enrichment.py fuer UI-Sichtbarkeit.

AENDERUNG 10.02.2026: Fix 47b - Neue Datei
ROOT-CAUSE-FIX:
  Symptom: Context7 Docs nicht im External Bureau UI sichtbar
  Ursache: doc_enrichment.py war standalone, nicht als Specialist registriert
  Loesung: BaseSpecialist-Wrapper mit Delegation an DocEnrichmentPipeline
"""

import os
import sys
import shutil
import time
import logging
from typing import Dict, Any, Optional
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from external_specialists.base_specialist import (
    BaseSpecialist,
    SpecialistResult,
    SpecialistFinding,
    SpecialistStatus,
    SpecialistCategory
)

logger = logging.getLogger(__name__)


class Context7Specialist(BaseSpecialist):
    """
    Context7 MCP Integration fuer Library-Dokumentation.

    Holt aktuelle Bibliotheks-Dokumentation via Context7 MCP Server (kostenlos).
    Benoetigt: npx (Node.js) muss installiert sein.

    Konfiguration in config.yaml:
        context7_docs:
            enabled: true
            timeout_seconds: 30
            cooldown_seconds: 30
    """

    @property
    def name(self) -> str:
        return "Context7 Docs"

    @property
    def category(self) -> SpecialistCategory:
        return SpecialistCategory.INTELLIGENCE

    @property
    def stats(self) -> Dict[str, int]:
        return {
            "STR": 30,  # Keine Code-Analyse, nur Docs
            "INT": 90,  # Sehr gute Dokumentations-Qualitaet
            "AGI": 75   # MCP-Start braucht etwas Zeit
        }

    @property
    def description(self) -> str:
        return "Holt aktuelle Library-Dokumentation via Context7 MCP (kostenlos)"

    @property
    def icon(self) -> str:
        return "menu_book"

    def check_available(self) -> bool:
        """Prueft ob npx verfuegbar ist (Voraussetzung fuer Context7 MCP)."""
        npx_path = shutil.which("npx")
        if npx_path:
            logger.debug("Context7: npx gefunden bei %s", npx_path)
            return True
        logger.debug("Context7: npx nicht gefunden")
        return False

    async def execute(self, context: Dict[str, Any]) -> SpecialistResult:
        """
        Holt Library-Dokumentation via Context7 MCP.

        Args:
            context: Dict mit:
                - library: Library-Name (z.B. "shadcn/ui")
                - query: Such-Query (z.B. "CSS setup")

        Returns:
            SpecialistResult mit Dokumentations-Findings
        """
        self.status = SpecialistStatus.COMPILING
        start_time = time.time()

        try:
            library = context.get("library", "")
            query = context.get("query", "setup configuration")

            if not library:
                self.status = SpecialistStatus.ERROR
                return SpecialistResult(
                    success=False,
                    summary="Kein Library-Name angegeben",
                    error="Parameter 'library' ist erforderlich"
                )

            timeout = self.config.get("timeout_seconds", 30)

            logger.info("Context7: Hole Docs fuer '%s' (Query: %s)", library, query[:50])

            # Delegiere an DocEnrichmentPipeline
            doc_text = await self._fetch_context7_docs(library, query, timeout)

            duration_ms = int((time.time() - start_time) * 1000)
            self.last_run = datetime.now()
            self.run_count += 1

            if doc_text:
                findings = [SpecialistFinding(
                    severity="INFO",
                    description=doc_text[:500],
                    category="documentation",
                    fix=f"Library-Docs fuer {library} verfuegbar"
                )]
                self.status = SpecialistStatus.READY
                self.last_result = SpecialistResult(
                    success=True,
                    findings=findings,
                    summary=f"Docs fuer {library}: {len(doc_text)} Zeichen",
                    raw_output=doc_text,
                    duration_ms=duration_ms
                )
                logger.info("Context7: %d Zeichen Docs in %dms", len(doc_text), duration_ms)
                return self.last_result
            else:
                self.status = SpecialistStatus.READY
                self.last_result = SpecialistResult(
                    success=False,
                    summary=f"Keine Docs fuer {library} gefunden",
                    duration_ms=duration_ms
                )
                return self.last_result

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            self.status = SpecialistStatus.ERROR
            self.error_count += 1
            self.last_result = SpecialistResult(
                success=False,
                summary="Context7 Ausfuehrungsfehler",
                error=str(e),
                duration_ms=duration_ms
            )
            logger.error("Context7 Exception: %s", e)
            return self.last_result

    async def _fetch_context7_docs(
        self, library: str, query: str, timeout: int
    ) -> Optional[str]:
        """
        Delegiert an DocEnrichmentPipeline._fetch_via_context7().

        Returns:
            Dokumentations-Text oder None
        """
        try:
            from backend.doc_enrichment import DocEnrichmentPipeline

            # Minimale Config fuer Pipeline
            pipeline_config = {
                "doc_enrichment": {
                    "enabled": True,
                    "context7": {
                        "enabled": True,
                        "timeout_seconds": timeout
                    },
                    "max_docs_chars": 3000
                }
            }
            pipeline = DocEnrichmentPipeline(pipeline_config)
            return await pipeline._fetch_via_context7(library, query)

        except ImportError:
            logger.warning("Context7: doc_enrichment Modul nicht gefunden")
            return None
        except Exception as e:
            logger.warning("Context7: Fetch fehlgeschlagen: %s", e)
            return None
