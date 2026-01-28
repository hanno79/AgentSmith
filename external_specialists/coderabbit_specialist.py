# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 28.01.2026
Version: 1.0
Beschreibung: CodeRabbit CLI Wrapper fuer externes Code-Review.
              Integriert CodeRabbit als externen Specialist im External Bureau.
"""

import subprocess
import asyncio
import logging
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


class CodeRabbitSpecialist(BaseSpecialist):
    """
    CodeRabbit CLI Integration fuer externes Code-Review.

    CodeRabbit ist ein KI-gestuetztes Code-Review-Tool.
    Installation: npm install -g coderabbit

    Konfiguration in config.yaml:
        coderabbit:
            enabled: true
            mode: advisory       # "advisory" oder "blocking"
            cli_path: coderabbit # Pfad zur CLI
            timeout_seconds: 120
            cooldown_seconds: 300
    """

    @property
    def name(self) -> str:
        return "CodeRabbit"

    @property
    def category(self) -> SpecialistCategory:
        return SpecialistCategory.COMBAT

    @property
    def stats(self) -> Dict[str, int]:
        return {
            "STR": 85,  # Starke Analyse-Faehigkeiten
            "INT": 90,  # Hohe Intelligenz fuer Code-Verstaendnis
            "AGI": 70   # Moderate Geschwindigkeit (API-abhaengig)
        }

    @property
    def description(self) -> str:
        return "KI-gestuetztes Code-Review mit automatischer Fehler-Erkennung"

    @property
    def icon(self) -> str:
        return "pest_control"  # Bug-Hunter Icon

    def check_available(self) -> bool:
        """Prueft ob CodeRabbit CLI installiert ist."""
        cli_path = self.config.get("cli_path", "coderabbit")

        try:
            result = subprocess.run(
                [cli_path, "--version"],
                capture_output=True,
                timeout=10,
                text=True
            )
            if result.returncode == 0:
                logger.debug(f"CodeRabbit verfuegbar: {result.stdout.strip()}")
                return True
            return False
        except FileNotFoundError:
            logger.debug("CodeRabbit CLI nicht gefunden")
            return False
        except subprocess.TimeoutExpired:
            logger.warning("CodeRabbit --version Timeout")
            return False
        except Exception as e:
            logger.debug(f"CodeRabbit Pruefung fehlgeschlagen: {e}")
            return False

    async def execute(self, context: Dict[str, Any]) -> SpecialistResult:
        """
        Fuehrt CodeRabbit Review aus.

        Args:
            context: Dict mit:
                - project_path: Pfad zum Projektverzeichnis
                - code: Optional - spezifischer Code zu reviewen
                - files: Optional - Liste von Dateien zu reviewen

        Returns:
            SpecialistResult mit gefundenen Issues
        """
        self.status = SpecialistStatus.COMPILING
        start_time = time.time()

        try:
            project_path = context.get("project_path", ".")
            files = context.get("files", [])
            timeout = self.config.get("timeout_seconds", 120)
            cli_path = self.config.get("cli_path", "coderabbit")

            # Command zusammenbauen
            cmd = [cli_path, "review", "--plain"]

            if files:
                # Spezifische Dateien reviewen
                cmd.extend(files)
            else:
                # Ganzes Projekt reviewen
                cmd.append(project_path)

            logger.info(f"CodeRabbit: Starte Review in {project_path}")

            # Asynchron ausfuehren
            result = await asyncio.to_thread(
                subprocess.run,
                cmd,
                capture_output=True,
                timeout=timeout,
                text=True,
                encoding='utf-8',
                errors='replace',
                cwd=project_path
            )

            duration_ms = int((time.time() - start_time) * 1000)
            self.last_run = datetime.now()
            self.run_count += 1

            if result.returncode == 0:
                findings = self._parse_output(result.stdout)
                self.status = SpecialistStatus.READY
                self.last_result = SpecialistResult(
                    success=True,
                    findings=findings,
                    summary=f"{len(findings)} Issue(s) gefunden",
                    raw_output=result.stdout,
                    duration_ms=duration_ms
                )
                logger.info(f"CodeRabbit: {len(findings)} Issues in {duration_ms}ms")
                return self.last_result

            else:
                # Pruefe auf Rate-Limit
                if "rate limit" in result.stderr.lower():
                    cooldown = self.config.get("cooldown_seconds", 300)
                    self.set_cooldown(cooldown)
                    self.last_result = SpecialistResult(
                        success=False,
                        findings=[],
                        summary=f"Rate-Limit erreicht - Cooldown {cooldown}s",
                        error=result.stderr,
                        duration_ms=duration_ms
                    )
                else:
                    self.status = SpecialistStatus.ERROR
                    self.error_count += 1
                    self.last_result = SpecialistResult(
                        success=False,
                        findings=[],
                        summary="CodeRabbit Fehler",
                        error=result.stderr[:500] if result.stderr else "Unbekannter Fehler",
                        duration_ms=duration_ms
                    )

                logger.warning(f"CodeRabbit Fehler: {result.stderr[:200]}")
                return self.last_result

        except subprocess.TimeoutExpired:
            duration_ms = int((time.time() - start_time) * 1000)
            self.status = SpecialistStatus.ERROR
            self.error_count += 1
            self.last_result = SpecialistResult(
                success=False,
                findings=[],
                summary=f"Timeout nach {timeout}s",
                error=f"CodeRabbit hat nach {timeout} Sekunden nicht geantwortet",
                duration_ms=duration_ms
            )
            logger.warning(f"CodeRabbit Timeout nach {timeout}s")
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
            logger.error(f"CodeRabbit Exception: {e}")
            return self.last_result

    def _parse_output(self, output: str) -> List[SpecialistFinding]:
        """
        Parst CodeRabbit Output in strukturierte Findings.

        Args:
            output: Raw Output von CodeRabbit CLI

        Returns:
            Liste von SpecialistFinding Objekten
        """
        findings = []

        if not output or not output.strip():
            return findings

        # CodeRabbit Output Patterns (anpassen basierend auf echtem Format)
        # Beispiel-Pattern: "severity: HIGH | file: app.py:42 | message: ..."
        finding_pattern = r'(?:severity|level):\s*(\w+)\s*\|\s*(?:file|location):\s*([^|]+)\s*\|\s*(?:message|description):\s*(.+?)(?=\n(?:severity|level):|$)'

        matches = re.findall(finding_pattern, output, re.IGNORECASE | re.DOTALL)

        for match in matches:
            severity = match[0].upper()
            location = match[1].strip()
            message = match[2].strip()

            # File und Line extrahieren
            file_name = "unknown"
            line_num = 0
            if ':' in location:
                parts = location.split(':')
                file_name = parts[0].strip()
                if len(parts) > 1 and parts[1].isdigit():
                    line_num = int(parts[1])
            else:
                file_name = location

            findings.append(SpecialistFinding(
                severity=severity,
                description=message[:500],  # Max 500 Zeichen
                file=file_name,
                line=line_num,
                category="code-review"
            ))

        # Fallback: Wenn keine strukturierten Findings gefunden, ganzen Output als INFO
        if not findings and output.strip():
            # Versuche einfachere Patterns
            lines = output.strip().split('\n')
            for line in lines[:10]:  # Max 10 Findings
                line = line.strip()
                if line and len(line) > 10:
                    # Versuche Severity zu erraten
                    severity = "INFO"
                    lower_line = line.lower()
                    if any(kw in lower_line for kw in ['error', 'critical', 'severe']):
                        severity = "HIGH"
                    elif any(kw in lower_line for kw in ['warning', 'warn']):
                        severity = "MEDIUM"
                    elif any(kw in lower_line for kw in ['info', 'note', 'suggestion']):
                        severity = "LOW"

                    findings.append(SpecialistFinding(
                        severity=severity,
                        description=line[:300],
                        category="code-review"
                    ))

        return findings
