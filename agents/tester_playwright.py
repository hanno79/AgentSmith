# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 01.02.2026
Version: 1.0
Beschreibung: Playwright Web-Test-Modul für Tester Agent.
              Extrahiert aus tester_agent.py (Regel 1: Max 500 Zeilen)
              ÄNDERUNG 24.01.2026: Robustere Playwright-Implementierung.
              ÄNDERUNG 28.01.2026: Content-Validierung gegen leere Seiten.
"""

import time
import shutil
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from PIL import Image, ImageChops
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout, Error as PlaywrightError

from .tester_types import (
    UITestResult,
    DEFAULT_GLOBAL_TIMEOUT,
    DEFAULT_NETWORKIDLE_TIMEOUT,
    MAX_RETRIES,
    RETRY_DELAY
)

logger = logging.getLogger(__name__)

# Server-Runner Import für automatisches Server-Management
try:
    from server_runner import managed_server, get_test_target
    SERVER_RUNNER_AVAILABLE = True
except ImportError:
    SERVER_RUNNER_AVAILABLE = False
    logging.warning("server_runner nicht verfügbar - Server-Tests deaktiviert")


def compare_images(baseline_path: Path, new_path: Path) -> Optional[Image.Image]:
    """
    Vergleicht zwei Screenshots Pixel-für-Pixel und gibt eine Differenz-Map zurück.

    Args:
        baseline_path: Pfad zum Baseline-Screenshot
        new_path: Pfad zum neuen Screenshot

    Returns:
        Differenz-Bild falls Unterschiede existieren, sonst None
    """
    try:
        with Image.open(baseline_path) as base_file, Image.open(new_path) as new_file:
            base_img = base_file.convert("RGB")
            new_img = new_file.convert("RGB")

            # Normalisiere Bildgrößen falls unterschiedlich
            if base_img.size != new_img.size:
                target_size = (max(base_img.width, new_img.width), max(base_img.height, new_img.height))
                normalized_base = Image.new("RGB", target_size, (0, 0, 0))
                normalized_new = Image.new("RGB", target_size, (0, 0, 0))
                normalized_base.paste(base_img, (0, 0))
                normalized_new.paste(new_img, (0, 0))
                base_img = normalized_base
                new_img = normalized_new

            diff = ImageChops.difference(base_img, new_img)
            return diff.copy() if diff.getbbox() else None

    except Exception as e:
        logger.error(f"Fehler beim Bildvergleich: {e}")
        return None


def test_web_ui(file_path: str, config: Optional[Dict[str, Any]] = None) -> UITestResult:
    """
    Führt UI-Tests mit Playwright durch, erstellt Screenshots und erkennt visuelle Unterschiede.

    Args:
        file_path: Pfad zur HTML-Datei oder URL
        config: Optionale Konfiguration mit playwright-spezifischen Timeouts

    Returns:
        UITestResult Dictionary mit status, issues und screenshot
    """
    playwright_config = config.get("playwright", {}) if config else {}
    global_timeout = playwright_config.get("global_timeout", DEFAULT_GLOBAL_TIMEOUT)
    networkidle_timeout = playwright_config.get("networkidle_timeout", DEFAULT_NETWORKIDLE_TIMEOUT)

    # Datei-Existenz prüfen BEVOR Playwright startet
    if not Path(file_path).exists():
        logger.error(f"Testdatei nicht gefunden: {file_path}")
        return {
            "status": "ERROR",
            "issues": [f"Testdatei nicht gefunden: {file_path}"],
            "screenshot": None
        }

    file_url = Path(file_path).absolute().as_uri()
    project_dir = Path(file_path).parent
    screenshots_dir = project_dir / "screenshots"
    screenshots_dir.mkdir(exist_ok=True)

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    screenshot_path = screenshots_dir / f"ui_test_{timestamp}.png"
    baseline_path = screenshots_dir / "baseline.png"

    result: UITestResult = {
        "status": "OK",
        "issues": [],
        "screenshot": str(screenshot_path)
    }

    last_error = None

    # Retry-Logik mit Exponential Backoff
    for attempt in range(MAX_RETRIES):
        browser = None
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.set_default_timeout(global_timeout)

                console_errors: List[str] = []
                page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

                page.goto(file_url, timeout=global_timeout, wait_until="domcontentloaded")

                try:
                    page.wait_for_load_state("networkidle", timeout=networkidle_timeout)
                except PlaywrightTimeout:
                    logger.debug("NetworkIdle Timeout - fahre fort")

                page.screenshot(path=str(screenshot_path), full_page=True)

            browser = None

            if not Path(screenshot_path).exists():
                result["issues"].append("Kein Screenshot erstellt.")

            if console_errors:
                result["issues"].append(f"JavaScript-Fehler: {len(console_errors)} Fehler")

            # Baseline-Vergleich
            if baseline_path.exists():
                diff_img = compare_images(baseline_path, screenshot_path)
                if diff_img:
                    diff_path = screenshots_dir / f"diff_{timestamp}.png"
                    diff_img.save(str(diff_path))
                    result["issues"].append("Visuelle Änderung erkannt")
                    result["status"] = "REVIEW"
            else:
                Path(baseline_path).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(screenshot_path, baseline_path)
                result["issues"].append("Neue Baseline gespeichert.")
                result["status"] = "BASELINE"

            _FAIL_KEYWORDS = ["Kein Screenshot", "JavaScript-Fehler"]
            if any(any(kw in i for kw in _FAIL_KEYWORDS) for i in result["issues"]):
                result["status"] = "FAIL"

            return result

        except PlaywrightTimeout as e:
            last_error = e
            logger.warning(f"Timeout bei Versuch {attempt + 1}/{MAX_RETRIES}: {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY * (attempt + 1))

        except PlaywrightError as e:
            last_error = e
            logger.warning(f"Browser-Fehler bei Versuch {attempt + 1}/{MAX_RETRIES}: {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY * (attempt + 1))

        except Exception as e:
            last_error = e
            logger.error(f"Fehler bei Versuch {attempt + 1}/{MAX_RETRIES}: {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)

        finally:
            if browser:
                try:
                    browser.close()
                except Exception:
                    pass

    error_type = type(last_error).__name__ if last_error else "Unbekannt"
    return {
        "status": "ERROR",
        "issues": [f"Playwright-Fehler nach {MAX_RETRIES} Versuchen ({error_type}): {last_error}"],
        "screenshot": None
    }


def _test_with_server(project_path: str, tech_blueprint: Dict[str, Any],
                      test_url: str, config: Optional[Dict[str, Any]] = None) -> UITestResult:
    """
    Interne Funktion: Testet gegen einen laufenden Server.

    Startet Server via run.bat, wartet auf Port, führt Tests durch,
    und beendet Server sauber.
    """
    if not SERVER_RUNNER_AVAILABLE:
        return {
            "status": "ERROR",
            "issues": ["server_runner nicht verfügbar"],
            "screenshot": None
        }

    startup_timeout_ms = tech_blueprint.get("server_startup_time_ms")
    startup_timeout = (startup_timeout_ms if startup_timeout_ms is not None else 30000) / 1000

    with managed_server(project_path, tech_blueprint, timeout=int(startup_timeout)) as server:
        if server is None:
            return {
                "status": "ERROR",
                "issues": ["Server konnte nicht gestartet werden"],
                "screenshot": None
            }

        logger.info(f"Server läuft auf {server.url} - starte Playwright-Tests")
        return _test_url(server.url, project_path, config, tech_blueprint)


def _test_url(url: str, project_path: str,
              config: Optional[Dict[str, Any]] = None,
              tech_blueprint: Optional[Dict[str, Any]] = None) -> UITestResult:
    """
    Interne Funktion: Testet eine URL mit Playwright.

    Ähnlich wie test_web_ui, aber für URLs statt Datei-Pfade.
    ÄNDERUNG 28.01.2026: tech_blueprint Parameter für Tech-Stack-spezifische Checks.
    """
    playwright_config = config.get("playwright", {}) if config else {}
    global_timeout = playwright_config.get("global_timeout", DEFAULT_GLOBAL_TIMEOUT)
    networkidle_timeout = playwright_config.get("networkidle_timeout", DEFAULT_NETWORKIDLE_TIMEOUT)

    screenshots_dir = Path(project_path) / "screenshots"
    screenshots_dir.mkdir(exist_ok=True)

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    screenshot_path = screenshots_dir / f"ui_test_{timestamp}.png"
    baseline_path = screenshots_dir / "baseline.png"

    result: UITestResult = {
        "status": "OK",
        "issues": [],
        "screenshot": str(screenshot_path)
    }

    last_error = None

    for attempt in range(MAX_RETRIES):
        browser = None
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.set_default_timeout(global_timeout)

                console_errors: List[str] = []
                page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

                page.goto(url, timeout=global_timeout, wait_until="domcontentloaded")

                try:
                    page.wait_for_load_state("networkidle", timeout=networkidle_timeout)
                except PlaywrightTimeout:
                    logger.debug(f"NetworkIdle Timeout - fahre fort")

                page.screenshot(path=str(screenshot_path), full_page=True)

                # Content-Validierung
                try:
                    from content_validator import validate_page_content
                    content_result = validate_page_content(page, tech_blueprint)
                    if content_result.issues:
                        result["issues"].extend(content_result.issues)
                    if not content_result.has_visible_content:
                        result["issues"].append("Leere Seite erkannt - kein sichtbarer Inhalt gerendert")
                except Exception as cv_err:
                    logger.warning(f"Content-Validierung fehlgeschlagen: {cv_err}")

            browser = None

            if not Path(screenshot_path).exists():
                result["issues"].append("Kein Screenshot erstellt.")

            if console_errors:
                result["issues"].append(f"JavaScript-Fehler: {len(console_errors)} Fehler")

            # Baseline-Vergleich
            if baseline_path.exists():
                diff_img = compare_images(baseline_path, screenshot_path)
                if diff_img:
                    diff_path = screenshots_dir / f"diff_{timestamp}.png"
                    diff_img.save(str(diff_path))
                    result["issues"].append(f"Visuelle Änderung erkannt")
                    result["status"] = "REVIEW"
            else:
                Path(screenshot_path).replace(baseline_path)
                result["issues"].append("Neue Baseline gespeichert.")
                result["status"] = "BASELINE"

            _FAIL_KEYWORDS = ["Kein Screenshot", "JavaScript-Fehler", "Leere Seite",
                              "komplett leer", "nicht gerendert", "Fehler-Pattern"]
            if any(any(kw.lower() in i.lower() for kw in _FAIL_KEYWORDS) for i in result["issues"]):
                result["status"] = "FAIL"

            return result

        except PlaywrightTimeout as e:
            last_error = e
            logger.warning(f"Timeout bei Versuch {attempt + 1}/{MAX_RETRIES}: {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY * (attempt + 1))

        except PlaywrightError as e:
            last_error = e
            logger.warning(f"Browser-Fehler bei Versuch {attempt + 1}/{MAX_RETRIES}: {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY * (attempt + 1))

        except Exception as e:
            last_error = e
            logger.error(f"Fehler bei Versuch {attempt + 1}/{MAX_RETRIES}: {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)

        finally:
            if browser:
                try:
                    browser.close()
                except Exception:
                    pass

    return {
        "status": "ERROR",
        "issues": [f"Test fehlgeschlagen nach {MAX_RETRIES} Versuchen: {last_error}"],
        "screenshot": None
    }
