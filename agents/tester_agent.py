# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 31.01.2026
Version: 1.6
Beschreibung: Tester Agent - Führt UI-Tests mit Playwright (Web) oder PyAutoGUI/pytest-qt (Desktop) durch.
              ÄNDERUNG 31.01.2026: pytest-qt Routing für PyQt/PySide Apps hinzugefügt.
              ÄNDERUNG 31.01.2026: Intelligentes Test-Routing basierend auf Framework-Erkennung.
              ÄNDERUNG 31.01.2026: Display-Check für PyAutoGUI.
              ÄNDERUNG 29.01.2026: Desktop-App Testing mit PyAutoGUI hinzugefügt.
              ÄNDERUNG 29.01.2026: Test-Routing basierend auf app_type und test_strategy.
              ÄNDERUNG 28.01.2026: Content-Validierung gegen leere Seiten und Tech-Stack-Checks.
              ÄNDERUNG 28.01.2026: Router-Parameter und project_rules Integration (Phase 0.12).

# ÄNDERUNG 29.01.2026: Desktop-App Testing mit PyAutoGUI
# - test_desktop_app() Funktion für Tkinter, PyQt5, etc.
# - Test-Routing basierend auf app_type (webapp/desktop/cli)
# - Screenshot-Capture für Desktop-GUIs

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
import subprocess
from crewai import Agent
from agents.agent_utils import combine_project_rules

# ÄNDERUNG 31.01.2026: pytest-qt für PyQt/PySide Tests
try:
    from agents.pytest_qt_tester import run_pytest_qt_tests, detect_qt_framework
    PYTEST_QT_TESTER_AVAILABLE = True
except ImportError:
    PYTEST_QT_TESTER_AVAILABLE = False
    logging.debug("pytest_qt_tester nicht verfügbar")


# ÄNDERUNG 31.01.2026: Display-Check vor PyAutoGUI-Import
# ÄNDERUNG [31.01.2026]: macOS als GUI-Plattform behandeln
def _check_display_available() -> bool:
    """
    Prüft ob ein Display für PyAutoGUI verfügbar ist.
    Windows: Immer True
    macOS: Immer True
    Linux: Prüft DISPLAY-Variable
    """
    import platform
    if platform.system() == "Windows":
        return True  # Windows hat immer ein Display
    if platform.system() == "Darwin":
        return True  # macOS hat ein Display
    # Linux/Mac: Prüfe DISPLAY
    return bool(os.environ.get("DISPLAY"))


# ÄNDERUNG 31.01.2026: PyAutoGUI mit Display-Check
PYAUTOGUI_AVAILABLE = False
PYAUTOGUI_ERROR = None

try:
    if _check_display_available():
        import pyautogui
        # Test-Aufruf um sicherzustellen dass es funktioniert
        _ = pyautogui.size()
        PYAUTOGUI_AVAILABLE = True
    else:
        PYAUTOGUI_ERROR = "Kein Display verfügbar (DISPLAY nicht gesetzt)"
except ImportError as e:
    PYAUTOGUI_ERROR = f"PyAutoGUI nicht installiert: {e}"
except Exception as e:
    PYAUTOGUI_ERROR = f"PyAutoGUI nicht nutzbar: {e}"

if not PYAUTOGUI_AVAILABLE and PYAUTOGUI_ERROR:
    logging.warning(f"pyautogui nicht verfügbar - {PYAUTOGUI_ERROR}")

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


def create_tester(config: Dict[str, Any], project_rules: Dict[str, List[str]], router=None) -> Agent:
    """
    Erstellt den Tester-Agenten, der UI-Tests durchführt.

    ÄNDERUNG 28.01.2026: Router-Parameter und project_rules Integration (Phase 0.12).

    Args:
        config: Anwendungskonfiguration mit mode und models
        project_rules: Dictionary mit globalen und rollenspezifischen Regeln
        router: Optionaler ModelRouter für automatisches Fallback bei Rate-Limits

    Returns:
        Konfigurierte CrewAI Agent-Instanz
    """
    # ÄNDERUNG 28.01.2026: Router-Parameter wie bei anderen Agenten
    if router:
        model = router.get_model("tester")
    else:
        mode = config["mode"]
        # Fallback to reviewer model if tester model not specified
        model = config["models"][mode].get("tester", config["models"][mode]["reviewer"])

    # ÄNDERUNG 28.01.2026: project_rules integrieren wie bei anderen Agenten
    combined_rules = combine_project_rules(project_rules, "tester") if project_rules else ""

    return Agent(
        role="Tester",
        goal="Überprüfe die Benutzeroberfläche auf visuelle Fehler und Funktionalität.",
        backstory=(
            "Du bist ein detailgenauer Tester. Du nutzt Tools wie Playwright, "
            "um Screenshots zu vergleichen und die Funktionalität von Webseiten zu prüfen. "
            "Du analysierst UI-Elemente, prüfst auf JavaScript-Fehler und erkennst leere Seiten. "
            "Bei fehlgeschlagenen Tests gibst du strukturiertes Feedback mit konkreten Hinweisen. "
            f"\n\n{combined_rules}"
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

                # ÄNDERUNG 28.01.2026: Content-Validierung gegen leere Seiten
                try:
                    from content_validator import validate_page_content
                    content_result = validate_page_content(page, None)
                    if content_result.issues:
                        result["issues"].extend(content_result.issues)
                    if not content_result.has_visible_content:
                        result["issues"].append("Leere Seite erkannt - kein sichtbarer Inhalt gerendert")
                except Exception as cv_err:
                    logger.warning(f"Content-Validierung fehlgeschlagen: {cv_err}")

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

            # ÄNDERUNG 28.01.2026: Erweiterte Fehler-Erkennung (auch leere Seiten)
            _FAIL_KEYWORDS = ["Kein Screenshot", "JavaScript-Fehler", "Leere Seite",
                              "komplett leer", "nicht gerendert", "Fehler-Pattern"]
            if any(any(kw.lower() in issue.lower() for kw in _FAIL_KEYWORDS) for issue in result["issues"]):
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


# ÄNDERUNG 31.01.2026: Intelligentes UI-Test-Routing
def _get_ui_test_strategy(project_type: str, tech_blueprint: Dict[str, Any]) -> str:
    """
    Bestimmt die UI-Test-Strategie basierend auf Projekt-Typ und Blueprint.

    ÄNDERUNG 31.01.2026: Framework-Erkennung hat VORRANG vor expliziter Strategy,
    weil pytest-qt objektiv besser für PyQt/PySide ist (headless, objektbasiert).

    Args:
        project_type: Typ des Projekts (z.B. "pyqt_desktop", "tkinter_desktop")
        tech_blueprint: Vollständiger Blueprint mit Framework-Info

    Returns:
        "pytest_qt" | "pyautogui" | "playwright" | "cli_test" | "none"
    """
    # ÄNDERUNG 31.01.2026: Framework-Erkennung ZUERST (hat Vorrang!)
    # PyQt/PySide → pytest-qt (besser als pyautogui für Qt-Apps)
    framework = tech_blueprint.get("framework", "").lower()
    dependencies = tech_blueprint.get("dependencies", [])
    deps_lower = [d.lower() for d in dependencies] if dependencies else []

    # Prüfe Framework, Dependencies und project_type auf Qt
    is_qt_app = (
        any(fw in framework for fw in ["pyqt", "pyside", "qt"]) or
        any(fw in project_type.lower() for fw in ["pyqt", "pyside"]) or
        any(dep in deps_lower for dep in ["pyqt5", "pyqt6", "pyside2", "pyside6"])
    )

    if is_qt_app:
        logger.info("Qt-Framework erkannt - verwende pytest-qt (Vorrang vor Blueprint-Strategy)")
        return "pytest_qt"

    # Tkinter → PyAutoGUI (kein besseres Alternative)
    if "tkinter" in project_type.lower() or "tkinter" in framework:
        return "pyautogui"

    # Explizite test_strategy aus Blueprint (nur wenn kein Qt erkannt)
    explicit_strategy = tech_blueprint.get("test_strategy", "").lower()
    if explicit_strategy in ["pytest_qt", "pyautogui", "playwright", "cli_test", "pytest_only"]:
        return explicit_strategy

    # app_type basiertes Routing
    app_type = tech_blueprint.get("app_type", "").lower()
    if app_type == "desktop":
        # Desktop ohne spezifisches Framework → Auto-Detection
        return "auto_detect"
    elif app_type == "cli":
        return "cli_test"
    elif app_type == "api":
        return "none"
    elif app_type == "webapp":
        return "playwright"

    # Fallback: project_type analysieren
    if any(dt in project_type.lower() for dt in ["desktop", "gui"]):
        return "auto_detect"
    elif any(ct in project_type.lower() for ct in ["cli", "script", "console"]):
        return "cli_test"

    # Default: webapp → playwright
    return "playwright"


def _detect_qt_framework_in_project(project_path: str) -> bool:
    """
    Erkennt ob das Projekt PyQt/PySide verwendet.

    Analysiert main.py und requirements.txt auf Qt-Imports.
    """
    indicators = ["PyQt5", "PyQt6", "PySide2", "PySide6", "from PyQt", "from PySide"]

    # Prüfe main.py
    main_file = os.path.join(project_path, "main.py")
    if os.path.exists(main_file):
        try:
            with open(main_file, "r", encoding="utf-8") as f:
                content = f.read()
                if any(ind in content for ind in indicators):
                    return True
        except Exception:
            pass

    # Prüfe requirements.txt
    req_file = os.path.join(project_path, "requirements.txt")
    if os.path.exists(req_file):
        try:
            with open(req_file, "r", encoding="utf-8") as f:
                content = f.read().lower()
                if any(ind.lower() in content for ind in ["pyqt5", "pyqt6", "pyside2", "pyside6"]):
                    return True
        except Exception:
            pass

    # Prüfe alle .py Dateien im Hauptverzeichnis
    try:
        for filename in os.listdir(project_path):
            if filename.endswith(".py"):
                filepath = os.path.join(project_path, filename)
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        content = f.read()
                        if any(ind in content for ind in indicators):
                            return True
                except Exception:
                    continue
    except Exception:
        pass

    return False


# ÄNDERUNG 29.01.2026: Desktop-App Testing mit PyAutoGUI
def test_desktop_app(project_path: str, tech_blueprint: Dict[str, Any],
                     config: Optional[Dict[str, Any]] = None) -> UITestResult:
    """
    Testet Desktop-Anwendungen (Tkinter, PyQt5, etc.) mit PyAutoGUI.

    Args:
        project_path: Pfad zum Projektverzeichnis
        tech_blueprint: Blueprint mit run_command und anderen Infos
        config: Optionale Konfiguration

    Returns:
        UITestResult Dictionary mit status, issues und screenshot
    """
    # ÄNDERUNG 31.01.2026: SKIP statt ERROR wenn PyAutoGUI fehlt
    # Damit blockiert fehlende Dependency nicht den gesamten Run
    if not PYAUTOGUI_AVAILABLE:
        logger.warning("PyAutoGUI nicht verfügbar - Desktop-UI-Tests werden übersprungen")
        return {
            "status": "SKIP",
            "issues": ["PyAutoGUI nicht verfügbar - Desktop-UI-Tests übersprungen. Unit-Tests laufen weiterhin."],
            "screenshot": None
        }

    project_type = tech_blueprint.get("project_type", "desktop")
    run_command = tech_blueprint.get("run_command", "python app.py")
    # ÄNDERUNG 31.01.2026: None-Safe Default (Blueprint kann null enthalten)
    startup_time_ms = tech_blueprint.get("server_startup_time_ms")
    if startup_time_ms is None:
        startup_time_ms = 3000

    logger.info(f"Starte Desktop-App Test für {project_type}")

    # Screenshots-Verzeichnis erstellen
    screenshots_dir = Path(project_path) / "screenshots"
    screenshots_dir.mkdir(exist_ok=True)

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    screenshot_path = screenshots_dir / f"desktop_test_{timestamp}.png"

    result: UITestResult = {
        "status": "OK",
        "issues": [],
        "screenshot": str(screenshot_path)
    }

    proc = None
    try:
        # 1. App starten
        logger.info(f"Starte Desktop-App: {run_command}")

        # Kommando vorbereiten (Windows vs Unix)
        if os.name == 'nt':  # Windows
            # Prüfe ob run.bat existiert
            run_bat = Path(project_path) / "run.bat"
            if run_bat.exists():
                proc = subprocess.Popen(
                    str(run_bat),
                    cwd=project_path,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
                )
            else:
                proc = subprocess.Popen(
                    run_command,
                    cwd=project_path,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
                )
        else:  # Linux/Mac
            run_sh = Path(project_path) / "run.sh"
            if run_sh.exists():
                proc = subprocess.Popen(
                    ["bash", str(run_sh)],
                    cwd=project_path,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    start_new_session=True
                )
            else:
                proc = subprocess.Popen(
                    run_command,
                    cwd=project_path,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    start_new_session=True
                )

        # 2. Warten bis GUI geladen ist
        wait_time = startup_time_ms / 1000
        logger.info(f"Warte {wait_time}s auf GUI-Start...")
        time.sleep(wait_time)

        # 3. Prüfen ob App noch läuft
        if proc.poll() is not None:
            # App ist abgestürzt
            stdout, stderr = proc.communicate(timeout=5)
            error_msg = stderr.decode('utf-8', errors='replace')[:500] if stderr else "Keine Fehlermeldung"
            result["issues"].append(f"Desktop-App ist abgestürzt: {error_msg}")
            result["status"] = "FAIL"
            logger.error(f"Desktop-App abgestürzt: {error_msg}")
            return result

        # 4. Screenshot mit PyAutoGUI machen
        logger.info("Erstelle Screenshot mit PyAutoGUI...")
        try:
            screenshot = pyautogui.screenshot()
            screenshot.save(str(screenshot_path))
            logger.info(f"Screenshot gespeichert: {screenshot_path}")
        except Exception as screenshot_err:
            result["issues"].append(f"Screenshot fehlgeschlagen: {screenshot_err}")
            result["status"] = "FAIL"
            logger.error(f"Screenshot-Fehler: {screenshot_err}")

        # 5. Basis-Validierung des Screenshots
        if screenshot_path.exists():
            # Prüfe ob Screenshot nicht komplett schwarz/weiß ist
            try:
                with Image.open(screenshot_path) as img:
                    # Berechne Durchschnittsfarbe
                    img_small = img.resize((100, 100))
                    pixels = list(img_small.getdata())
                    avg_color = tuple(sum(c[i] for c in pixels) // len(pixels) for i in range(3))

                    # Warnung wenn fast komplett schwarz oder weiß
                    if all(c < 10 for c in avg_color):
                        result["issues"].append("Screenshot ist fast komplett schwarz - möglicherweise kein Fenster sichtbar")
                    elif all(c > 245 for c in avg_color):
                        result["issues"].append("Screenshot ist fast komplett weiß - möglicherweise leeres Fenster")
            except Exception as img_err:
                logger.warning(f"Screenshot-Analyse fehlgeschlagen: {img_err}")

        # 6. Baseline-Vergleich (falls vorhanden)
        baseline_path = screenshots_dir / "baseline_desktop.png"
        if baseline_path.exists() and screenshot_path.exists():
            diff_img = compare_images(baseline_path, screenshot_path)
            if diff_img:
                diff_path = screenshots_dir / f"diff_desktop_{timestamp}.png"
                diff_img.save(str(diff_path))
                result["issues"].append("Visuelle Änderung zur Baseline erkannt")
                if result["status"] == "OK":
                    result["status"] = "REVIEW"
        elif screenshot_path.exists() and not baseline_path.exists():
            # Neue Baseline speichern
            import shutil
            shutil.copy(str(screenshot_path), str(baseline_path))
            result["issues"].append("Neue Desktop-Baseline gespeichert")
            if result["status"] == "OK":
                result["status"] = "BASELINE"

        # Finale Status-Bestimmung
        if not result["issues"]:
            result["issues"].append("Desktop-App startet und zeigt GUI")

        return result

    except Exception as e:
        logger.error(f"Desktop-Test Fehler: {e}")
        return {
            "status": "ERROR",
            "issues": [f"Desktop-Test fehlgeschlagen: {str(e)[:200]}"],
            "screenshot": str(screenshot_path) if screenshot_path.exists() else None
        }

    finally:
        # 7. App sauber beenden
        if proc and proc.poll() is None:
            logger.info("Beende Desktop-App...")
            try:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=2)
            except Exception as term_err:
                logger.warning(f"Fehler beim Beenden der App: {term_err}")


# ÄNDERUNG 29.01.2026: CLI-App Testing
def test_cli_app(project_path: str, tech_blueprint: Dict[str, Any],
                 config: Optional[Dict[str, Any]] = None) -> UITestResult:
    """
    Testet CLI-Anwendungen durch Ausführen und Prüfen des Outputs.

    Args:
        project_path: Pfad zum Projektverzeichnis
        tech_blueprint: Blueprint mit run_command
        config: Optionale Konfiguration

    Returns:
        UITestResult Dictionary
    """
    run_command = tech_blueprint.get("run_command", "python main.py --help")
    logger.info(f"Starte CLI-Test: {run_command}")

    result: UITestResult = {
        "status": "OK",
        "issues": [],
        "screenshot": None  # CLI hat keine Screenshots
    }

    try:
        # CLI ausführen mit Timeout
        proc = subprocess.run(
            run_command,
            cwd=project_path,
            shell=True,
            capture_output=True,
            timeout=30,
            text=True
        )

        # Prüfe Exit-Code
        if proc.returncode != 0:
            result["issues"].append(f"CLI beendet mit Exit-Code {proc.returncode}")
            if proc.stderr:
                result["issues"].append(f"Stderr: {proc.stderr[:300]}")
            result["status"] = "FAIL"
        else:
            result["issues"].append("CLI läuft erfolgreich")
            if proc.stdout:
                # Speichere Output als "Screenshot"-Ersatz
                output_file = Path(project_path) / "cli_output.txt"
                with open(output_file, "w", encoding="utf-8") as f:
                    f.write(proc.stdout)
                result["screenshot"] = str(output_file)

    except subprocess.TimeoutExpired:
        result["status"] = "FAIL"
        result["issues"].append("CLI-Timeout nach 30 Sekunden")
    except Exception as e:
        result["status"] = "ERROR"
        result["issues"].append(f"CLI-Test Fehler: {str(e)[:200]}")

    return result


def test_project(project_path: str, tech_blueprint: Dict[str, Any],
                 config: Optional[Dict[str, Any]] = None) -> UITestResult:
    """
    ÄNDERUNG 31.01.2026: Intelligente Test-Funktion mit Framework-basiertem Routing.

    Entscheidet automatisch basierend auf Framework-Erkennung:
    - PyQt/PySide: pytest-qt (headless, objektbasiert)
    - Tkinter: PyAutoGUI (screenshot-basiert)
    - Webapp: Playwright Browser-Tests
    - CLI: Kommandozeilen-Output Tests
    - API: Nur Unit-Tests (kein UI-Test)

    Args:
        project_path: Pfad zum Projektverzeichnis
        tech_blueprint: Blueprint vom TechStack-Architect mit:
                       - project_type
                       - app_type (webapp/desktop/cli/api)
                       - test_strategy (playwright/pyautogui/pytest_qt/cli_test/pytest_only)
                       - framework (pyqt5/tkinter/etc.)
                       - requires_server
                       - server_port
                       - run_command
                       - server_startup_time_ms
        config: Optionale Konfiguration

    Returns:
        UITestResult Dictionary

    Example:
        >>> blueprint = {"project_type": "pyqt_desktop", "app_type": "desktop", "framework": "pyqt5"}
        >>> result = test_project("/path/to/project", blueprint)
        # Verwendet pytest-qt für headless Qt-Tests
    """
    project_type = tech_blueprint.get("project_type", "unknown")

    # ÄNDERUNG 31.01.2026: Bestimme Test-Strategie über neues Routing
    strategy = _get_ui_test_strategy(project_type, tech_blueprint)

    # Auto-Detection wenn nötig
    if strategy == "auto_detect":
        if PYTEST_QT_TESTER_AVAILABLE and _detect_qt_framework_in_project(project_path):
            strategy = "pytest_qt"
            logger.info("Qt-Framework erkannt - verwende pytest-qt")
        else:
            strategy = "pyautogui"
            logger.info("Kein Qt-Framework erkannt - verwende PyAutoGUI")

    logger.info(f"UI-Test-Strategie: {strategy} für {project_type}")

    # ÄNDERUNG 31.01.2026: pytest-qt für PyQt/PySide Apps
    if strategy == "pytest_qt":
        if PYTEST_QT_TESTER_AVAILABLE:
            logger.info("Verwende pytest-qt Tests (headless)")
            # ÄNDERUNG [31.01.2026]: pytest-qt Ergebnis auf UITestResult normalisieren
            qt_result = run_pytest_qt_tests(project_path)
            issues = qt_result.get("issues", [])
            if not isinstance(issues, list):
                issues = [str(issues)]
            return {
                "status": qt_result.get("status") or "ERROR",
                "issues": issues,
                "screenshot": qt_result.get("screenshot")
            }
        else:
            logger.warning("pytest-qt nicht verfügbar, Fallback auf PyAutoGUI")
            strategy = "pyautogui"

    # Desktop-Apps mit PyAutoGUI testen
    if strategy == "pyautogui":
        logger.info("Verwende Desktop-Test (PyAutoGUI)")
        return test_desktop_app(project_path, tech_blueprint, config)

    # CLI-Apps durch Ausführen testen
    if strategy == "cli_test":
        logger.info("Verwende CLI-Test")
        return test_cli_app(project_path, tech_blueprint, config)

    # API-only oder pytest_only: Keine UI-Tests (nur Unit-Tests relevant)
    if strategy == "none" or strategy == "pytest_only":
        logger.info("Keine UI-Tests (API oder pytest_only)")
        return {
            "status": "OK",
            "issues": ["UI-Tests übersprungen (app_type: api oder test_strategy: pytest_only)"],
            "screenshot": None
        }

    # Standard: Webapp-Tests mit Playwright
    logger.info("Verwende Webapp-Test (Playwright)")

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
    # ÄNDERUNG 31.01.2026: None-Safe Default
    startup_timeout_ms = tech_blueprint.get("server_startup_time_ms")
    startup_timeout = (startup_timeout_ms if startup_timeout_ms is not None else 30000) / 1000

    with managed_server(project_path, tech_blueprint, timeout=int(startup_timeout)) as server:
        if server is None:
            # Server-Start fehlgeschlagen
            return {
                "status": "ERROR",
                "issues": ["Server konnte nicht gestartet werden"],
                "screenshot": None
            }

        logger.info(f"Server läuft auf {server.url} - starte Playwright-Tests")

        # ÄNDERUNG 28.01.2026: tech_blueprint an _test_url weiterreichen
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

                # ÄNDERUNG 28.01.2026: Content-Validierung mit Tech-Blueprint
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

            # ÄNDERUNG 28.01.2026: Erweiterte Fehler-Erkennung (auch leere Seiten)
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
