# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 01.02.2026
Version: 1.0
Beschreibung: Augment Code Context Engine Integration fuer semantische Codebase-Analyse.
              Integriert Auggie CLI als externen INTELLIGENCE-Specialist im External Bureau.
"""

import shlex
import subprocess
import asyncio
import logging
import shutil
import time
import re
from typing import Dict, Any, List
from datetime import datetime

from .base_specialist import (
    BaseSpecialist,
    SpecialistResult,
    SpecialistFinding,
    SpecialistStatus,
    SpecialistCategory
)

logger = logging.getLogger(__name__)


class AugmentSpecialist(BaseSpecialist):
    """
    Augment Code Context Engine Integration fuer semantische Codebase-Analyse.

    Die Auggie CLI bietet KI-gestuetztes Codebase-Verstaendnis mit:
    - Semantischer Analyse statt nur Syntax-Suche
    - Architektur-Erkennung und Dependency-Mapping
    - "Infinite Context Window" durch intelligente Komprimierung

    Installation: npm install -g @augmentcode/auggie
    Login: auggie login

    Konfiguration in config.yaml:
        augment_context:
            enabled: true
            cli_command: "npx @augmentcode/auggie"
            timeout_seconds: 180
            cooldown_seconds: 60
            default_prompt: "Analysiere die Projektstruktur"
    """

    @property
    def name(self) -> str:
        return "Augment Context"

    @property
    def category(self) -> SpecialistCategory:
        return SpecialistCategory.INTELLIGENCE

    @property
    def stats(self) -> Dict[str, int]:
        return {
            "STR": 60,   # Keine direkte Code-Aenderung
            "INT": 98,   # Sehr hohe Analyse-Intelligenz
            "AGI": 75    # Moderate Geschwindigkeit (Indexierung)
        }

    @property
    def description(self) -> str:
        return "Semantische Codebase-Analyse mit KI-gestuetztem Kontext-Verstaendnis"

    @property
    def icon(self) -> str:
        return "hub"  # Netzwerk/Verbindungs-Icon

    def check_available(self) -> bool:
        """Prueft ob Auggie CLI installiert und verfuegbar ist (ohne shell=True)."""
        npx_path = shutil.which("npx")
        if not npx_path:
            logger.debug("Auggie CLI nicht gefunden: npx nicht im PATH - npm install -g @augmentcode/auggie")
            return False
        try:
            result = subprocess.run(
                [npx_path, "@augmentcode/auggie", "--version"],
                capture_output=True,
                timeout=30,
                text=True,
                shell=False,
            )
            if result.returncode == 0:
                version = (result.stdout or "").strip() or (result.stderr or "").strip()
                logger.debug("Augment verfuegbar: %s", (version or "")[:50])
                return True
            logger.debug("Auggie --version Exit-Code %s: %s", result.returncode, (result.stderr or result.stdout or "")[:200])
            return False
        except subprocess.TimeoutExpired:
            logger.warning("Auggie --version Timeout")
            return False
        except (subprocess.CalledProcessError, subprocess.SubprocessError) as e:
            logger.debug("Augment Pruefung fehlgeschlagen: %s", e)
            return False
        except Exception as e:
            logger.debug("Augment Pruefung fehlgeschlagen: %s", e)
            return False

    async def execute(self, context: Dict[str, Any]) -> SpecialistResult:
        """
        Fuehrt Augment Context-Analyse aus.

        Args:
            context: Dict mit:
                - query: Die Analysefrage (z.B. "Wie ist das Projekt strukturiert?")
                - project_path: Pfad zum Projektverzeichnis

        Returns:
            SpecialistResult mit Analyse-Findings
        """
        self.status = SpecialistStatus.COMPILING
        start_time = time.time()

        try:
            query = context.get("query", self.config.get(
                "default_prompt", "Analysiere die Projektstruktur und Architektur"
            ))
            project_path = context.get("project_path", ".")
            timeout = self.config.get("timeout_seconds", 180)
            cli_command = self.config.get("cli_command", "npx @augmentcode/auggie")

            # AENDERUNG 06.02.2026: ROOT-CAUSE-FIX Windows-Pfad-Bug
            # Symptom: shlex.split() zerlegt Windows-Pfade mit Leerzeichen falsch
            # Ursache: shutil.which("npx") → "C:\Program Files\..." → shlex splittet am Leerzeichen
            # Loesung: Array direkt bauen, npx-Pfad korrekt aufloesen
            if isinstance(cli_command, str):
                parts = cli_command.split()
                if parts and parts[0] == "npx":
                    npx_resolved = shutil.which("npx") or "npx"
                    base_args = [npx_resolved] + parts[1:]
                else:
                    base_args = parts
            else:
                base_args = list(cli_command)
            if not base_args:
                base_args = ["npx", "@augmentcode/auggie"]
            args = base_args + [query, "--print"]

            logger.info("Augment: Starte Analyse in %s", project_path)
            logger.debug("Augment args: %s", args)

            result = await asyncio.to_thread(
                subprocess.run,
                args,
                capture_output=True,
                timeout=timeout,
                text=True,
                encoding="utf-8",
                errors="replace",
                cwd=project_path,
                shell=False,
            )

            duration_ms = int((time.time() - start_time) * 1000)
            self.last_run = datetime.now()
            self.run_count += 1

            if result.returncode == 0 and result.stdout.strip():
                findings = self._parse_output(result.stdout, query)
                self.status = SpecialistStatus.READY
                self.last_result = SpecialistResult(
                    success=True,
                    findings=findings,
                    summary=f"Analyse abgeschlossen - {len(findings)} Insight(s)",
                    raw_output=result.stdout,
                    duration_ms=duration_ms
                )
                logger.info(f"Augment: {len(findings)} Insights in {duration_ms}ms")
                return self.last_result

            else:
                # Fehlerbehandlung
                error_output = result.stderr or result.stdout or "Keine Ausgabe"

                # Pruefe auf bekannte Fehler
                if "not logged in" in error_output.lower() or "login" in error_output.lower():
                    self.status = SpecialistStatus.ERROR
                    self.error_count += 1
                    self.last_result = SpecialistResult(
                        success=False,
                        findings=[],
                        summary="Nicht eingeloggt - 'auggie login' ausfuehren",
                        error="Authentication erforderlich: auggie login",
                        duration_ms=duration_ms
                    )
                elif "rate limit" in error_output.lower():
                    cooldown = self.config.get("cooldown_seconds", 60)
                    self.set_cooldown(cooldown)
                    self.last_result = SpecialistResult(
                        success=False,
                        findings=[],
                        summary=f"Rate-Limit erreicht - Cooldown {cooldown}s",
                        error=error_output[:500],
                        duration_ms=duration_ms
                    )
                else:
                    self.status = SpecialistStatus.ERROR
                    self.error_count += 1
                    self.last_result = SpecialistResult(
                        success=False,
                        findings=[],
                        summary="Augment Analyse fehlgeschlagen",
                        error=error_output[:500],
                        duration_ms=duration_ms
                    )

                logger.warning(f"Augment Fehler: {error_output[:200]}")
                return self.last_result

        except subprocess.TimeoutExpired:
            duration_ms = int((time.time() - start_time) * 1000)
            self.status = SpecialistStatus.ERROR
            self.error_count += 1
            self.last_result = SpecialistResult(
                success=False,
                findings=[],
                summary=f"Timeout nach {timeout}s",
                error=f"Augment hat nach {timeout} Sekunden nicht geantwortet",
                duration_ms=duration_ms
            )
            logger.warning(f"Augment Timeout nach {timeout}s")
            return self.last_result

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            self.status = SpecialistStatus.ERROR
            self.error_count += 1
            self.last_result = SpecialistResult(
                success=False,
                findings=[],
                summary="Ausfuehrungsfehler",
                error=str(e),
                duration_ms=duration_ms
            )
            logger.error(f"Augment Exception: {e}")
            return self.last_result

    def _parse_output(self, output: str, query: str) -> List[SpecialistFinding]:
        """
        Parst Augment Output in strukturierte Findings.

        Die Auggie CLI gibt typischerweise strukturierten Text zurueck.
        Wir extrahieren:
        - Haupterkenntnisse als INFO-Findings
        - Dateiverweise
        - Warnungen/Empfehlungen

        Args:
            output: Raw Output von Auggie CLI
            query: Die urspruengliche Anfrage

        Returns:
            Liste von SpecialistFinding Objekten
        """
        findings = []

        if not output or not output.strip():
            return findings

        # Output bereinigen
        output = output.strip()

        # Haupt-Analyse als primaeres Finding
        # Kuerzen auf max 1000 Zeichen fuer Uebersichtlichkeit
        main_content = output[:1000]
        if len(output) > 1000:
            main_content += "... [gekuerzt]"

        findings.append(SpecialistFinding(
            severity="INFO",
            description=main_content,
            category="context-analysis"
        ))

        # Versuche Dateiverweise zu extrahieren
        # Pattern: file.py, src/file.ts, ./path/file.jsx etc.
        file_pattern = r'(?:^|\s)([a-zA-Z0-9_\-./\\]+\.[a-zA-Z]{1,5})(?:[:|\s]|$)'
        file_matches = re.findall(file_pattern, output)

        seen_files = set()
        for file_ref in file_matches[:5]:  # Max 5 Datei-Findings
            if file_ref not in seen_files and not file_ref.startswith('.'):
                seen_files.add(file_ref)
                findings.append(SpecialistFinding(
                    severity="LOW",
                    description=f"Relevante Datei: {file_ref}",
                    file=file_ref,
                    category="file-reference"
                ))

        # Versuche Warnungen/Empfehlungen zu extrahieren
        warning_patterns = [
            (r'(?:warning|warnung|achtung)[:\s]+(.{20,200})', "MEDIUM"),
            (r'(?:recommend|empfehlung|empfohlen)[:\s]+(.{20,200})', "LOW"),
            (r'(?:wichtig|important|note)[:\s]+(.{20,200})', "LOW"),
        ]

        for pattern, severity in warning_patterns:
            matches = re.findall(pattern, output, re.IGNORECASE)
            for match in matches[:2]:  # Max 2 pro Pattern
                findings.append(SpecialistFinding(
                    severity=severity,
                    description=match.strip()[:300],
                    category="recommendation"
                ))

        return findings
