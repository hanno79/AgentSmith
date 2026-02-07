# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 01.02.2026
Version: 1.0
Beschreibung: Desktop-Test-Modul für Tester Agent.
              Extrahiert aus tester_agent.py (Regel 1: Max 500 Zeilen)
              ÄNDERUNG 29.01.2026: Desktop-App Testing mit PyAutoGUI.
              ÄNDERUNG 31.01.2026: Display-Check vor PyAutoGUI-Import.
"""

import os
import shlex
import time
import shutil
import logging
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional
from PIL import Image

from .tester_types import UITestResult

logger = logging.getLogger(__name__)


# ÄNDERUNG 31.01.2026: Display-Check vor PyAutoGUI-Import
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
pyautogui = None  # Modul-Variable für späteren Import

try:
    if _check_display_available():
        import pyautogui as _pyautogui
        # Test-Aufruf um sicherzustellen dass es funktioniert
        _ = _pyautogui.size()
        PYAUTOGUI_AVAILABLE = True
        pyautogui = _pyautogui
    else:
        PYAUTOGUI_ERROR = "Kein Display verfügbar (DISPLAY nicht gesetzt)"
except ImportError as e:
    PYAUTOGUI_ERROR = f"PyAutoGUI nicht installiert: {e}"
except Exception as e:
    PYAUTOGUI_ERROR = f"PyAutoGUI nicht nutzbar: {e}"

if not PYAUTOGUI_AVAILABLE and PYAUTOGUI_ERROR:
    logging.warning(f"pyautogui nicht verfügbar - {PYAUTOGUI_ERROR}")


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


def test_desktop_app(project_path: str, tech_blueprint: Dict[str, Any],
                     config: Optional[Dict[str, Any]] = None,
                     compare_images_func=None) -> UITestResult:
    """
    Testet Desktop-Anwendungen (Tkinter, PyQt5, etc.) mit PyAutoGUI.

    Args:
        project_path: Pfad zum Projektverzeichnis
        tech_blueprint: Blueprint mit run_command und anderen Infos
        config: Optionale Konfiguration
        compare_images_func: Optionale Bildvergleichsfunktion

    Returns:
        UITestResult Dictionary mit status, issues und screenshot
    """
    # ÄNDERUNG 31.01.2026: SKIP statt ERROR wenn PyAutoGUI fehlt
    if not PYAUTOGUI_AVAILABLE:
        logger.warning("PyAutoGUI nicht verfügbar - Desktop-UI-Tests werden übersprungen")
        return {
            "status": "SKIP",
            "issues": ["PyAutoGUI nicht verfügbar - Desktop-UI-Tests übersprungen. Unit-Tests laufen weiterhin."],
            "screenshot": None
        }

    project_type = tech_blueprint.get("project_type", "desktop")
    run_command = tech_blueprint.get("run_command", "python app.py")
    # ÄNDERUNG 31.01.2026: None-Safe Default
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

    # Kommando als Argumentliste (ohne Shell) fuer sichere Ausfuehrung
    def _run_command_argv(cmd: str) -> List[str]:
        cmd = (cmd or "").strip()
        if not cmd:
            return ["python", "--version"]
        return shlex.split(cmd, posix=(os.name != "nt"))

    proc = None
    try:
        # 1. App starten
        logger.info(f"Starte Desktop-App: {run_command}")

        # Kommando vorbereiten (Windows vs Unix), ohne shell=True
        if os.name == 'nt':  # Windows
            run_bat = Path(project_path) / "run.bat"
            if run_bat.exists():
                proc = subprocess.Popen(
                    ["cmd", "/c", str(run_bat)],
                    cwd=project_path,
                    shell=False,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
                )
            else:
                argv = _run_command_argv(run_command)
                proc = subprocess.Popen(
                    argv,
                    cwd=project_path,
                    shell=False,
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
                argv = _run_command_argv(run_command)
                proc = subprocess.Popen(
                    argv,
                    cwd=project_path,
                    shell=False,
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
            try:
                with Image.open(screenshot_path) as img:
                    img_small = img.resize((100, 100))
                    pixels = list(img_small.getdata())
                    avg_color = tuple(sum(c[i] for c in pixels) // len(pixels) for i in range(3))

                    if all(c < 10 for c in avg_color):
                        result["issues"].append("Screenshot ist fast komplett schwarz - möglicherweise kein Fenster sichtbar")
                    elif all(c > 245 for c in avg_color):
                        result["issues"].append("Screenshot ist fast komplett weiß - möglicherweise leeres Fenster")
            except Exception as img_err:
                logger.warning(f"Screenshot-Analyse fehlgeschlagen: {img_err}")

        # 6. Baseline-Vergleich (falls vorhanden)
        baseline_path = screenshots_dir / "baseline_desktop.png"
        if baseline_path.exists() and screenshot_path.exists() and compare_images_func:
            diff_img = compare_images_func(baseline_path, screenshot_path)
            if diff_img:
                diff_path = screenshots_dir / f"diff_desktop_{timestamp}.png"
                diff_img.save(str(diff_path))
                result["issues"].append("Visuelle Änderung zur Baseline erkannt")
                if result["status"] == "OK":
                    result["status"] = "REVIEW"
        elif screenshot_path.exists() and not baseline_path.exists():
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
