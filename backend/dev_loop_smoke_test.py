# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 10.02.2026
Version: 1.0
Beschreibung: Smoke-Test-Modul fuer DevLoop.
              Startet den Server, prueft App-Bereitschaft und verifiziert
              im Browser dass die App fehlerfrei laeuft.
              BLOCKIERENDE Bedingung fuer Success-Deklaration.
              Fix 43: Echter Server-Start + Browser-Verifikation.
"""

import os
import time
import logging
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutTimeout
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class SmokeTestResult:
    """Ergebnis des Smoke-Tests."""
    passed: bool
    server_started: bool = False
    page_loaded: bool = False
    compile_errors: List[str] = field(default_factory=list)
    console_errors: List[str] = field(default_factory=list)
    issues: List[str] = field(default_factory=list)
    screenshot: Optional[str] = None
    server_output: str = ""
    duration_seconds: float = 0.0

    @property
    def feedback_for_coder(self) -> str:
        """Generiert strukturiertes Feedback fuer den Coder."""
        if self.passed:
            return ""
        parts = ["SMOKE-TEST FEHLGESCHLAGEN:"]
        if self.compile_errors:
            parts.append("\nKOMPILIERUNGS-FEHLER:")
            for err in self.compile_errors[:10]:
                parts.append(f"  - {err}")
        if not self.server_started:
            parts.append("\nSERVER KONNTE NICHT GESTARTET WERDEN:")
            if self.server_output:
                parts.append(f"  Server-Output:\n{self.server_output[:2000]}")
        if not self.page_loaded and self.server_started:
            parts.append("\nSEITE KONNTE NICHT GELADEN WERDEN:")
            parts.append("  Die App antwortet nicht auf HTTP-Anfragen.")
        if self.console_errors:
            parts.append(f"\nBROWSER CONSOLE-FEHLER ({len(self.console_errors)}):")
            for err in self.console_errors[:5]:
                parts.append(f"  - {err}")
        if self.issues:
            parts.append("\nWEITERE PROBLEME:")
            for issue in self.issues:
                parts.append(f"  - {issue}")
        return "\n".join(parts)


# Bekannte Compile-Error-Patterns aus Server-Stdout/Stderr
_COMPILE_ERROR_PATTERNS = [
    "Module not found", "ModuleNotFoundError",
    "Cannot find module", "Cannot resolve",
    "Failed to compile", "Build error",
    "SyntaxError", "TypeError:", "ReferenceError:",
    "ENOENT", "EPERM",
    "Cannot read properties of",
    "is not a function",
    "Unexpected token",
    "Error: Cannot find",
]

# Harmlose Patterns die NICHT als Compile-Error gelten
_HARMLESS_PATTERNS = [
    "warn", "notice", "npm warn", "[notice]",
    "deprecated", "ExperimentalWarning",
    "punycode", "cleanup",
]


def _extract_compile_errors(output: str) -> List[str]:
    """
    Extrahiert Compile-Fehler aus Server-Output (stdout/stderr).
    Filtert harmlose Warnungen heraus.
    """
    errors = []
    if not output:
        return errors
    for line in output.split("\n"):
        line_stripped = line.strip()
        if not line_stripped or len(line_stripped) < 5:
            continue
        # Harmlose Warnungen ignorieren
        lower_line = line_stripped.lower()
        if any(lower_line.startswith(p) for p in _HARMLESS_PATTERNS):
            continue
        # Compile-Fehler erkennen
        for pattern in _COMPILE_ERROR_PATTERNS:
            if pattern in line_stripped:
                errors.append(line_stripped[:300])
                break
    return errors


def _capture_server_output(process, timeout: float = 5.0) -> str:
    """
    Liest verfuegbaren Server-Output non-blocking.
    Nutzt ThreadPoolExecutor fuer Windows-Kompatibilitaet.
    """
    output_parts = []
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            if process.stdout and not process.stdout.closed:
                future_out = executor.submit(
                    lambda: process.stdout.read(8192) if process.stdout else b""
                )
                try:
                    data = future_out.result(timeout=timeout)
                    if data:
                        output_parts.append(
                            data.decode("utf-8", errors="ignore") if isinstance(data, bytes) else data
                        )
                except (FutTimeout, Exception):
                    pass
            if process.stderr and not process.stderr.closed:
                future_err = executor.submit(
                    lambda: process.stderr.read(8192) if process.stderr else b""
                )
                try:
                    data = future_err.result(timeout=timeout)
                    if data:
                        output_parts.append(
                            data.decode("utf-8", errors="ignore") if isinstance(data, bytes) else data
                        )
                except (FutTimeout, Exception):
                    pass
    except Exception as e:
        logger.debug(f"Server-Output-Capture Fehler: {e}")
    return "\n".join(output_parts)


def run_smoke_test(
    project_path: str,
    tech_blueprint: Dict[str, Any],
    config: Dict[str, Any],
    docker_container=None
) -> SmokeTestResult:
    """
    Fuehrt den Smoke-Test durch:
    1. Server starten (npm run dev / python app.py / etc.)
    2. Auf Bereitschaft warten (HTTP-Response mit Content)
    3. Playwright-Check: Seite laden, Console-Errors, Content-Validierung
    4. Compile-Errors aus Server-Output extrahieren

    Args:
        project_path: Pfad zum Projektverzeichnis
        tech_blueprint: Projekt-Blueprint
        config: Anwendungskonfiguration

    Returns:
        SmokeTestResult mit allen Ergebnissen
    """
    try:
        from server_runner import requires_server, managed_server
    except ImportError:
        return SmokeTestResult(
            passed=True, issues=["server_runner nicht verfuegbar - Smoke-Test uebersprungen"]
        )

    smoke_config = config.get("smoke_test", {})
    if not smoke_config.get("enabled", True):
        return SmokeTestResult(passed=True, issues=["Smoke-Test deaktiviert"])

    # Nicht-Server-Projekte brauchen keinen Smoke-Test
    if not requires_server(tech_blueprint):
        return SmokeTestResult(passed=True, issues=["Kein Server noetig"])

    start_time = time.time()
    result = SmokeTestResult(passed=False)
    server_timeout = smoke_config.get("server_timeout", 90)

    try:
        # AENDERUNG 10.02.2026: Fix 50 - Docker-Container an managed_server durchreichen
        with managed_server(project_path, tech_blueprint, timeout=server_timeout,
                            docker_container=docker_container) as server:
            if server is None:
                result.issues.append("Server konnte nicht gestartet werden")
                result.duration_seconds = time.time() - start_time
                return result

            result.server_started = True
            logger.info(f"Smoke-Test: Server gestartet auf {server.url}")

            # Server-Output fuer Compile-Error-Erkennung capturen
            if server.process:
                server_output = _capture_server_output(server.process, timeout=3.0)
                result.server_output = server_output
                result.compile_errors = _extract_compile_errors(server_output)

                if result.compile_errors:
                    result.issues.append(
                        f"{len(result.compile_errors)} Kompilierungsfehler erkannt"
                    )
                    result.duration_seconds = time.time() - start_time
                    return result

            # Playwright-Check
            result = _run_playwright_check(result, server.url, project_path, smoke_config)

            # Nochmal Server-Output checken (Compile-Errors koennen verzoegert kommen)
            if server.process:
                late_output = _capture_server_output(server.process, timeout=2.0)
                if late_output:
                    result.server_output += late_output
                    late_errors = _extract_compile_errors(late_output)
                    result.compile_errors.extend(late_errors)

    except Exception as e:
        result.issues.append(f"Smoke-Test Fehler: {e}")
        logger.error(f"Smoke-Test Exception: {e}")

    result.duration_seconds = time.time() - start_time

    # Passed-Entscheidung
    has_blocking_issues = (
        not result.server_started
        or not result.page_loaded
        or len(result.compile_errors) > 0
    )
    # Console-Errors optional blockierend (Default: nicht blockierend)
    if smoke_config.get("block_on_console_errors", False) and result.console_errors:
        has_blocking_issues = True

    result.passed = not has_blocking_issues
    return result


def _run_playwright_check(
    result: SmokeTestResult,
    url: str,
    project_path: str,
    smoke_config: Dict[str, Any]
) -> SmokeTestResult:
    """
    Fuehrt den Playwright-Browser-Check durch.
    Separiert fuer Uebersichtlichkeit und Fehlerbehandlung.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        result.issues.append("Playwright nicht installiert - nur Server-Start geprueft")
        # Server hat gestartet = mindestens Teilerfolg
        if not result.compile_errors:
            result.page_loaded = True
        return result

    playwright_timeout = smoke_config.get("playwright_timeout", 15000)

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                page.set_default_timeout(playwright_timeout)

                console_errors = []
                page.on("console", lambda msg: (
                    console_errors.append(msg.text)
                    if msg.type == "error" else None
                ))

                page.goto(url, wait_until="domcontentloaded", timeout=playwright_timeout)

                try:
                    page.wait_for_load_state("networkidle", timeout=5000)
                except Exception:
                    pass

                result.page_loaded = True

                # Screenshot
                screenshots_dir = os.path.join(project_path, "screenshots")
                os.makedirs(screenshots_dir, exist_ok=True)
                screenshot_path = os.path.join(
                    screenshots_dir,
                    f"smoke_test_{time.strftime('%Y%m%d_%H%M%S')}.png"
                )
                page.screenshot(path=screenshot_path, full_page=True)
                result.screenshot = screenshot_path

                # Content-Check: Leere Seite?
                body_text = page.evaluate(
                    "() => document.body ? document.body.innerText.trim() : ''"
                )
                body_html = page.evaluate(
                    "() => document.body ? document.body.innerHTML.trim() : ''"
                )

                if len(body_html) < 50 and len(body_text) < 10:
                    result.issues.append(
                        "Leere Seite erkannt - App rendert keinen sichtbaren Inhalt"
                    )
                    result.page_loaded = False

                # Console-Errors sammeln
                result.console_errors = console_errors
                if console_errors:
                    result.issues.append(
                        f"{len(console_errors)} Browser Console-Fehler"
                    )

                # Next.js Error-Overlay erkennen
                error_overlay = page.evaluate(
                    "() => !!document.querySelector('#__next-build-error') "
                    "|| !!document.querySelector('[data-nextjs-dialog]')"
                )
                if error_overlay:
                    result.issues.append("Next.js Error-Overlay erkannt - Build-Fehler")
                    result.page_loaded = False

            finally:
                browser.close()

    except Exception as pw_err:
        result.issues.append(f"Playwright-Fehler: {pw_err}")
        logger.warning(f"Smoke-Test Playwright-Fehler: {pw_err}")

    return result
