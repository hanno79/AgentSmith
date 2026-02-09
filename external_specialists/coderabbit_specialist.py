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

    # AENDERUNG 08.02.2026: Fix 33b - WSL-Support fuer Windows
    def _to_wsl_path(self, win_path: str) -> str:
        """Konvertiert Windows-Pfad zu WSL-Pfad. C:\\Temp\\x → /mnt/c/Temp/x"""
        if not win_path:
            return win_path
        path = win_path.replace('\\', '/')
        # C:/Temp/x → /mnt/c/Temp/x
        if len(path) >= 2 and path[1] == ':':
            drive = path[0].lower()
            path = f"/mnt/{drive}{path[2:]}"
        return path

    def _build_cmd(self, args: list) -> list:
        """Baut Command mit optionalem WSL-Prefix."""
        cli_path = self.config.get("cli_path", "coderabbit")
        use_wsl = self.config.get("use_wsl", False)
        if use_wsl:
            return ["wsl", cli_path] + args
        return [cli_path] + args

    def check_available(self) -> bool:
        """Prueft ob CodeRabbit CLI installiert ist (auch via WSL)."""
        try:
            # AENDERUNG 08.02.2026: Fix 33b - _build_cmd() fuer WSL-Support
            cmd = self._build_cmd(["--version"])
            # Timeout 15s statt 10s wegen moeglichem WSL Cold Start
            result = subprocess.run(cmd, capture_output=True, timeout=15, text=True)
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

        AENDERUNG 08.02.2026: Fix 33c - Korrekte CLI-Argumente
        Symptom: review schlug fehl mit "Unknown error" bei grossem Diff
        Ursache: CLI akzeptiert keine Dateipfade als Argumente, braucht --cwd + --type
        Loesung: --cwd fuer Projektverzeichnis, --type uncommitted fuer DevLoop-Aenderungen

        Args:
            context: Dict mit:
                - project_path: Pfad zum Projektverzeichnis (git repo)
                - files: Optional - Liste von Dateien (fuer Logging)
                - code: Optional - Code-Kontext

        Returns:
            SpecialistResult mit gefundenen Issues
        """
        self.status = SpecialistStatus.COMPILING
        start_time = time.time()

        try:
            project_path = context.get("project_path", ".")
            timeout = self.config.get("timeout_seconds", 120)
            use_wsl = self.config.get("use_wsl", False)

            # AENDERUNG 08.02.2026: Fix 33c - --cwd + --type statt Dateipfade
            # CodeRabbit CLI: coderabbit review --plain --type uncommitted --cwd <path>
            cwd_path = self._to_wsl_path(project_path) if use_wsl else project_path
            cmd = self._build_cmd([
                "review", "--plain",
                "--type", "uncommitted",
                "--cwd", cwd_path
            ])

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

            # CodeRabbit gibt RC=0 auch bei erfolgreichen Reviews zurueck
            # Fehler stehen im stderr mit "REVIEW ERROR" oder "[error]"
            stderr_lower = (result.stderr or "").lower()
            has_review_error = "review error" in stderr_lower or "[error]" in stderr_lower

            if not has_review_error:
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
                if "rate limit" in stderr_lower:
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
                    error_msg = result.stderr[:500] if result.stderr else "Unbekannter Fehler"
                    self.last_result = SpecialistResult(
                        success=False,
                        findings=[],
                        summary="CodeRabbit Fehler",
                        error=error_msg,
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

    # AENDERUNG 08.02.2026: Fix 33c - Parser fuer echtes CodeRabbit Output-Format
    def _parse_output(self, output: str) -> List[SpecialistFinding]:
        """
        Parst CodeRabbit --plain Output in strukturierte Findings.

        Echtes Format:
            ============================================================================
            File: app.js
            Line: 10 to 13
            Type: potential_issue

            Comment:
            Beschreibung des Problems...
            ============================================================================

        Args:
            output: Raw Output von CodeRabbit CLI (--plain Modus)

        Returns:
            Liste von SpecialistFinding Objekten
        """
        findings = []

        if not output or not output.strip():
            return findings

        # Splitte Output an den Trennlinien (====...====)
        sections = re.split(r'={10,}', output)

        for section in sections:
            section = section.strip()
            if not section:
                continue

            # Extrahiere Felder aus der Section
            file_match = re.search(r'^File:\s*(.+)$', section, re.MULTILINE)
            line_match = re.search(r'^Line:\s*(\d+)', section, re.MULTILINE)
            type_match = re.search(r'^Type:\s*(.+)$', section, re.MULTILINE)
            comment_match = re.search(r'^Comment:\s*\n(.+?)(?=\n\n|\Z)', section, re.MULTILINE | re.DOTALL)

            if not comment_match:
                continue

            file_name = file_match.group(1).strip() if file_match else "unknown"
            line_num = int(line_match.group(1)) if line_match else 0
            finding_type = type_match.group(1).strip().lower() if type_match else "info"
            comment = comment_match.group(1).strip()

            # Type zu Severity mappen
            severity = self._type_to_severity(finding_type, comment)

            findings.append(SpecialistFinding(
                severity=severity,
                description=comment[:500],
                file=file_name,
                line=line_num,
                category="code-review"
            ))

        return findings

    def _type_to_severity(self, finding_type: str, comment: str) -> str:
        """Mappt CodeRabbit Finding-Type auf Severity."""
        comment_lower = comment.lower()

        # Kritische Security-Findings
        if any(kw in comment_lower for kw in [
            'sql injection', 'xss', 'command injection', 'path traversal',
            'remote code execution', 'rce', 'authentication bypass'
        ]):
            return "CRITICAL"

        # Type-basiertes Mapping
        type_map = {
            "potential_issue": "HIGH",
            "bug": "HIGH",
            "security": "CRITICAL",
            "error": "HIGH",
            "refactor_suggestion": "MEDIUM",
            "improvement": "MEDIUM",
            "nitpick": "LOW",
            "style": "LOW",
            "info": "INFO",
        }
        return type_map.get(finding_type, "MEDIUM")
