# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 24.01.2026
Version: 1.2
Beschreibung: Tester Agent - Führt UI-Tests mit Playwright durch und erkennt visuelle Unterschiede.

# ÄNDERUNG 24.01.2026: Robustere Playwright-Implementierung
# - Retry-Logik mit Exponential Backoff hinzugefügt
# - Garantiertes Browser-Cleanup mit try-finally
# - Konfigurierbare Timeouts
# - Memory-sichere Bildverarbeitung
# - Strukturiertes Error-Handling nach Fehlertyp

# ÄNDERUNG 24.01.2026: Server-Integration für stabile Tests
# - test_project() Funktion mit tech_blueprint Support
# - Automatischer Server-Start via run.bat
# - Port-Erkennung und Wartezeit-Management
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, TypedDict
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout, Error as PlaywrightError
from PIL import Image, ImageChops
import os
import time
import logging
from crewai import Agent

# Server-Runner Import für automatisches Server-Management
try:
    from server_runner import managed_server, requires_server, get_test_target
    SERVER_RUNNER_AVAILABLE = True
except ImportError:
    SERVER_RUNNER_AVAILABLE = False
    logging.warning("server_runner nicht verfügbar - Server-Tests deaktiviert")

# Logging konfigurieren
logger = logging.getLogger(__name__)

# Konfigurierbare Konstanten (Standardwerte)
DEFAULT_GLOBAL_TIMEOUT = 10000  # 10 Sekunden
DEFAULT_NETWORKIDLE_TIMEOUT = 3000  # 3 Sekunden
MAX_RETRIES = 3
RETRY_DELAY = 2  # Sekunden Basis-Wartezeit


class UITestResult(TypedDict):
    """Typdefinition für UI-Testergebnisse."""
    status: str  # "OK", "FAIL", "REVIEW", "BASELINE", "ERROR"
    issues: List[str]
    screenshot: Optional[str]


def create_tester(config: Dict[str, Any], project_rules: Dict[str, List[str]]) -> Agent:
    """
    Erstellt den Tester-Agenten, der UI-Tests durchführt.

    Args:
        config: Anwendungskonfiguration mit mode und models
        project_rules: Dictionary mit globalen und rollenspezifischen Regeln

    Returns:
        Konfigurierte CrewAI Agent-Instanz
    """
    mode = config["mode"]
    # Fallback to reviewer model if tester model not specified
    model = config["models"][mode].get("tester", config["models"][mode]["reviewer"])

    return Agent(
        role="Tester",
        goal="Überprüfe die Benutzeroberfläche auf visuelle Fehler und Funktionalität.",
        backstory=(
            "Du bist ein detailgenauer Tester. Du nutzt Tools wie Playwright, "
            "um Screenshots zu vergleichen und die Funktionalität von Webseiten zu prüfen."
        ),
        llm=model,
        verbose=True
    )

def test_web_ui(file_path: str, config: Optional[Dict[str, Any]] = None) -> UITestResult:
    """
    Führt UI-Tests mit Playwright durch, erstellt Screenshots und erkennt visuelle Unterschiede.

    Args:
        file_path: Pfad zur HTML-Datei oder URL
        config: Optionale Konfiguration mit playwright-spezifischen Timeouts

    Returns:
        UITestResult Dictionary mit status, issues und screenshot
    """
    # Konfigurierbare Timeouts aus config laden
    playwright_config = config.get("playwright", {}) if config else {}
    global_timeout = playwright_config.get("global_timeout", DEFAULT_GLOBAL_TIMEOUT)
    networkidle_timeout = playwright_config.get("networkidle_timeout", DEFAULT_NETWORKIDLE_TIMEOUT)

    # ÄNDERUNG 24.01.2026: Datei-Existenz prüfen BEVOR Playwright startet
    # Verhindert ERR_FILE_NOT_FOUND Fehler und gibt klare Fehlermeldung
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

                # Konfigurierbare Timeouts
                page.set_default_timeout(global_timeout)

                console_errors: List[str] = []
                page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

                # Goto mit konfiguriertem Timeout
                page.goto(file_url, timeout=global_timeout, wait_until="domcontentloaded")

                # Optionales networkidle mit konfiguriertem Timeout
                try:
                    page.wait_for_load_state("networkidle", timeout=networkidle_timeout)
                except PlaywrightTimeout:
                    logger.debug(f"NetworkIdle Timeout nach {networkidle_timeout}ms - fahre fort mit Screenshot")

                # Screenshot erstellen
                page.screenshot(path=str(screenshot_path), full_page=True)

            # Browser wird automatisch geschlossen durch Context Manager, aber sicherheitshalber:
            browser = None

            # Grundlegende Checks
            if not Path(screenshot_path).exists():
                result["issues"].append("Kein Screenshot erstellt.")

            # Console-Errors auswerten (nur echte Fehler, nicht alle Nachrichten)
            if console_errors:
                error_count = len(console_errors)
                result["issues"].append(f"JavaScript-Fehler erkannt ({error_count} Fehler im Log).")

            # Pixelvergleich (nur wenn Baseline vorhanden)
            if baseline_path.exists():
                diff_img = compare_images(baseline_path, screenshot_path)
                if diff_img:
                    diff_path = screenshots_dir / f"diff_{timestamp}.png"
                    diff_img.save(str(diff_path))
                    result["issues"].append(f"Visuelle Änderung erkannt – siehe {diff_path}")
                    result["status"] = "REVIEW"
            else:
                # Erste Version als Baseline speichern
                Path(screenshot_path).replace(baseline_path)
                result["issues"].append("Neue Baseline gespeichert.")
                result["status"] = "BASELINE"

            # Status basierend auf kritischen Issues setzen
            if any("Kein Screenshot" in issue or "JavaScript-Fehler" in issue for issue in result["issues"]):
                result["status"] = "FAIL"

            return result

        except PlaywrightTimeout as e:
            last_error = e
            logger.warning(f"Timeout bei Versuch {attempt + 1}/{MAX_RETRIES}: {e}")
            if attempt < MAX_RETRIES - 1:
                wait_time = RETRY_DELAY * (attempt + 1)
                logger.info(f"Warte {wait_time}s vor erneutem Versuch...")
                time.sleep(wait_time)

        except PlaywrightError as e:
            last_error = e
            logger.warning(f"Browser-Fehler bei Versuch {attempt + 1}/{MAX_RETRIES}: {e}")
            if attempt < MAX_RETRIES - 1:
                wait_time = RETRY_DELAY * (attempt + 1)
                time.sleep(wait_time)

        except Exception as e:
            last_error = e
            logger.error(f"Unerwarteter Fehler bei Versuch {attempt + 1}/{MAX_RETRIES}: {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)

        finally:
            # Garantiertes Browser-Cleanup
            if browser:
                try:
                    browser.close()
                except Exception:
                    pass

    # Alle Retries fehlgeschlagen
    error_type = type(last_error).__name__ if last_error else "Unbekannt"
    return {
        "status": "ERROR",
        "issues": [f"Playwright-Fehler nach {MAX_RETRIES} Versuchen ({error_type}): {last_error}"],
        "screenshot": None
    }


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
        # Context Manager für automatisches Schließen (Memory-Leak vermeiden)
        with Image.open(baseline_path) as base_file, Image.open(new_path) as new_file:
            base_img = base_file.convert("RGB")
            new_img = new_file.convert("RGB")

            # Normalisiere Bildgrößen falls unterschiedlich
            if base_img.size != new_img.size:
                target_size = (max(base_img.width, new_img.width), max(base_img.height, new_img.height))
                # Erstelle neue Leinwände mit schwarzem Hintergrund
                normalized_base = Image.new("RGB", target_size, (0, 0, 0))
                normalized_new = Image.new("RGB", target_size, (0, 0, 0))
                # Füge Bilder in die Leinwände ein (oben links)
                normalized_base.paste(base_img, (0, 0))
                normalized_new.paste(new_img, (0, 0))
                base_img = normalized_base
                new_img = normalized_new

            diff = ImageChops.difference(base_img, new_img)
            # Kopie erstellen, da wir außerhalb des Context Managers sind
            return diff.copy() if diff.getbbox() else None

    except Exception as e:
        logger.error(f"Fehler beim Bildvergleich: {e}")
        return None

def summarize_ui_result(ui_result: UITestResult) -> str:
    """
    Liefert eine kurze textuelle Zusammenfassung der Testergebnisse
    für den Designer-Agenten oder den Memory-Agenten.
    """
    summary = f"Testergebnis: {ui_result['status']}. "
    if ui_result["issues"]:
        summary += "Probleme: " + "; ".join(ui_result["issues"])
    else:
        summary += "Keine visuellen Probleme erkannt."
    return summary


def test_project(project_path: str, tech_blueprint: Dict[str, Any],
                 config: Optional[Dict[str, Any]] = None) -> UITestResult:
    """
    ÄNDERUNG 24.01.2026: Intelligente Test-Funktion basierend auf tech_blueprint.

    Entscheidet automatisch:
    - Ob ein Server gestartet werden muss (via run.bat)
    - Welche URL/Datei getestet werden soll
    - Wie lange auf Server-Start gewartet wird

    Args:
        project_path: Pfad zum Projektverzeichnis
        tech_blueprint: Blueprint vom TechStack-Architect mit:
                       - project_type
                       - requires_server
                       - server_port
                       - run_command
                       - server_startup_time_ms
        config: Optionale Konfiguration

    Returns:
        UITestResult Dictionary

    Example:
        >>> blueprint = {"project_type": "flask_app", "server_port": 5000, "requires_server": True}
        >>> result = test_project("/path/to/project", blueprint)
        # Startet Server, wartet auf Port 5000, testet http://localhost:5000
    """
    project_type = tech_blueprint.get("project_type", "unknown")
    logger.info(f"Starte Tests für Projekt-Typ: {project_type}")

    # Prüfe ob Server-Tests möglich sind
    if not SERVER_RUNNER_AVAILABLE:
        logger.warning("server_runner nicht verfügbar - Fallback auf statische Tests")
        # Fallback: Suche nach HTML-Datei
        from file_utils import find_html_file
        html_file = find_html_file(project_path)
        if html_file:
            return test_web_ui(html_file, config)
        return {
            "status": "ERROR",
            "issues": ["Keine HTML-Datei gefunden und server_runner nicht verfügbar"],
            "screenshot": None
        }

    # Ermittle Test-Ziel (URL oder Datei)
    test_target, needs_server = get_test_target(project_path, tech_blueprint)

    if not test_target:
        logger.warning("Kein Test-Ziel ermittelt")
        return {
            "status": "ERROR",
            "issues": ["Kein Test-Ziel (URL oder HTML-Datei) gefunden"],
            "screenshot": None
        }

    if needs_server:
        # Server-basierter Test
        logger.info(f"Server-Test: Starte Server und teste {test_target}")
        return _test_with_server(project_path, tech_blueprint, test_target, config)
    else:
        # Statischer Test (HTML-Datei)
        logger.info(f"Statischer Test: Teste Datei {test_target}")
        return test_web_ui(test_target, config)


def _test_with_server(project_path: str, tech_blueprint: Dict[str, Any],
                      test_url: str, config: Optional[Dict[str, Any]] = None) -> UITestResult:
    """
    Interne Funktion: Testet gegen einen laufenden Server.

    Startet Server via run.bat, wartet auf Port, führt Tests durch,
    und beendet Server sauber.
    """
    startup_timeout = tech_blueprint.get("server_startup_time_ms", 30000) / 1000

    with managed_server(project_path, tech_blueprint, timeout=int(startup_timeout)) as server:
        if server is None:
            # Server-Start fehlgeschlagen
            return {
                "status": "ERROR",
                "issues": ["Server konnte nicht gestartet werden"],
                "screenshot": None
            }

        logger.info(f"Server läuft auf {server.url} - starte Playwright-Tests")

        # Playwright-Test gegen URL
        return _test_url(server.url, project_path, config)


def _test_url(url: str, project_path: str,
              config: Optional[Dict[str, Any]] = None) -> UITestResult:
    """
    Interne Funktion: Testet eine URL mit Playwright.

    Ähnlich wie test_web_ui, aber für URLs statt Datei-Pfade.
    """
    playwright_config = config.get("playwright", {}) if config else {}
    global_timeout = playwright_config.get("global_timeout", DEFAULT_GLOBAL_TIMEOUT)
    networkidle_timeout = playwright_config.get("networkidle_timeout", DEFAULT_NETWORKIDLE_TIMEOUT)

    # Screenshots im Projekt-Ordner speichern
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

                # Goto URL (nicht file://)
                page.goto(url, timeout=global_timeout, wait_until="domcontentloaded")

                try:
                    page.wait_for_load_state("networkidle", timeout=networkidle_timeout)
                except PlaywrightTimeout:
                    logger.debug(f"NetworkIdle Timeout - fahre fort")

                # Screenshot
                page.screenshot(path=str(screenshot_path), full_page=True)

            browser = None

            # Checks
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

            if any("Kein Screenshot" in i or "JavaScript-Fehler" in i for i in result["issues"]):
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
