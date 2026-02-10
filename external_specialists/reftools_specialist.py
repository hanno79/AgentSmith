# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 10.02.2026
Version: 1.0
Beschreibung: Ref.tools MCP Specialist fuer Library-Dokumentation im External Bureau.
              Duenner Wrapper um doc_enrichment.py fuer UI-Sichtbarkeit.

AENDERUNG 10.02.2026: Fix 47b - Neue Datei
ROOT-CAUSE-FIX:
  Symptom: Ref.tools Docs nicht im External Bureau UI sichtbar
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


class ReftoolsSpecialist(BaseSpecialist):
    """
    Ref.tools MCP Integration fuer Library-Dokumentation.

    Holt Bibliotheks-Dokumentation via Ref.tools MCP Server.
    Benoetigt: npx (Node.js) + REF_TOOLS_API_KEY.

    Konfiguration in config.yaml:
        reftools_docs:
            enabled: true
            api_key: ${REF_TOOLS_API_KEY}
            timeout_seconds: 30
            cooldown_seconds: 30
    """

    @property
    def name(self) -> str:
        return "Ref.tools Docs"

    @property
    def category(self) -> SpecialistCategory:
        return SpecialistCategory.INTELLIGENCE

    @property
    def stats(self) -> Dict[str, int]:
        return {
            "STR": 35,  # Keine Code-Analyse, nur Docs
            "INT": 85,  # Gute Dokumentations-Qualitaet
            "AGI": 70   # MCP-Start + API-Call braucht Zeit
        }

    @property
    def description(self) -> str:
        return "Holt Library-Dokumentation via Ref.tools MCP (benoetigt API-Key)"

    @property
    def icon(self) -> str:
        return "library_books"

    def _get_api_key(self) -> Optional[str]:
        """Holt API Key aus Config oder Umgebungsvariable."""
        api_key = self.config.get("api_key", "")

        # Ersetze ${VAR} Platzhalter
        if isinstance(api_key, str) and api_key.startswith("${") and api_key.endswith("}"):
            env_var = api_key[2:-1]
            api_key = os.getenv(env_var, "")

        # Fallback auf direkte Umgebungsvariable
        if not api_key:
            api_key = os.getenv("REF_TOOLS_API_KEY", "")

        return api_key if api_key else None

    def check_available(self) -> bool:
        """Prueft ob npx und API-Key verfuegbar sind."""
        npx_path = shutil.which("npx")
        if not npx_path:
            logger.debug("Ref.tools: npx nicht gefunden")
            return False

        api_key = self._get_api_key()
        if not api_key:
            logger.debug("Ref.tools: API Key nicht konfiguriert")
            return False

        logger.debug("Ref.tools: npx + API Key gefunden")
        return True

    async def execute(self, context: Dict[str, Any]) -> SpecialistResult:
        """
        Holt Library-Dokumentation via Ref.tools MCP.

        Args:
            context: Dict mit:
                - library: Library-Name (z.B. "prisma")
                - query: Such-Query (z.B. "schema setup")

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

            api_key = self._get_api_key()
            if not api_key:
                self.status = SpecialistStatus.ERROR
                return SpecialistResult(
                    success=False,
                    summary="API Key nicht konfiguriert",
                    error="REF_TOOLS_API_KEY nicht gefunden"
                )

            timeout = self.config.get("timeout_seconds", 30)

            logger.info("Ref.tools: Hole Docs fuer '%s' (Query: %s)", library, query[:50])

            # Delegiere an DocEnrichmentPipeline
            doc_text = await self._fetch_reftools_docs(library, query, timeout, api_key)

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
                logger.info("Ref.tools: %d Zeichen Docs in %dms", len(doc_text), duration_ms)
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
                summary="Ref.tools Ausfuehrungsfehler",
                error=str(e),
                duration_ms=duration_ms
            )
            logger.error("Ref.tools Exception: %s", e)
            return self.last_result

    async def _fetch_reftools_docs(
        self, library: str, query: str, timeout: int, api_key: str
    ) -> Optional[str]:
        """
        Delegiert an DocEnrichmentPipeline._fetch_via_ref_tools().

        Returns:
            Dokumentations-Text oder None
        """
        try:
            from backend.doc_enrichment import DocEnrichmentPipeline

            # Minimale Config fuer Pipeline
            pipeline_config = {
                "doc_enrichment": {
                    "enabled": True,
                    "ref_tools": {
                        "enabled": True,
                        "api_key": api_key,
                        "timeout_seconds": timeout
                    },
                    "max_docs_chars": 3000
                }
            }
            pipeline = DocEnrichmentPipeline(pipeline_config)
            return await pipeline._fetch_via_ref_tools(library, query)

        except ImportError:
            logger.warning("Ref.tools: doc_enrichment Modul nicht gefunden")
            return None
        except Exception as e:
            logger.warning("Ref.tools: Fetch fehlgeschlagen: %s", e)
            return None
