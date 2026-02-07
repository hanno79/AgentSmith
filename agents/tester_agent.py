# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 01.02.2026
Version: 2.0
Beschreibung: Tester Agent - Orchestrator für UI-Tests.
              REFAKTORIERT: Aus 996 Zeilen → 4 Module + Orchestrator
              Enthält nur noch Routing und Agent-Erstellung.

              Module:
              - tester_types.py: UITestResult TypedDict, Konstanten
              - tester_playwright.py: Playwright Web-Tests
              - tester_desktop.py: PyAutoGUI Desktop-Tests
              - tester_cli.py: CLI-App Tests

              ÄNDERUNG 01.02.2026: Aufsplitten in 4 Module (Regel 1: Max 500 Zeilen).
              ÄNDERUNG 31.01.2026: pytest-qt Routing für PyQt/PySide Apps.
              ÄNDERUNG 29.01.2026: Desktop-App Testing mit PyAutoGUI.
              ÄNDERUNG 28.01.2026: Content-Validierung gegen leere Seiten.
"""

import logging
from typing import Any, Dict, List, Optional

from crewai import Agent
# AENDERUNG 02.02.2026: get_model_from_config fuer konsistente Modellwahl
from agents.agent_utils import combine_project_rules, get_model_from_config

# =========================================================================
# Re-exports aus tester_types.py
# =========================================================================
from .tester_types import (
    UITestResult,
    DEFAULT_GLOBAL_TIMEOUT,
    DEFAULT_NETWORKIDLE_TIMEOUT,
    MAX_RETRIES,
    RETRY_DELAY
)

# =========================================================================
# Re-exports aus tester_playwright.py
# =========================================================================
from .tester_playwright import (
    test_web_ui,
    compare_images,
    _test_with_server,
    _test_url
)

# =========================================================================
# Re-exports aus tester_desktop.py
# =========================================================================
from .tester_desktop import (
    test_desktop_app,
    _detect_qt_framework_in_project,
    _check_display_available,
    PYAUTOGUI_AVAILABLE,
    PYAUTOGUI_ERROR
)

# =========================================================================
# Re-exports aus tester_cli.py
# =========================================================================
from .tester_cli import test_cli_app

# =========================================================================
# Weitere Imports
# =========================================================================
logger = logging.getLogger(__name__)

# pytest-qt Import
try:
    from agents.pytest_qt_tester import run_pytest_qt_tests, detect_qt_framework
    PYTEST_QT_TESTER_AVAILABLE = True
except ImportError:
    PYTEST_QT_TESTER_AVAILABLE = False
    logging.debug("pytest_qt_tester nicht verfügbar")

# Server-Runner Import
try:
    from server_runner import managed_server, requires_server, get_test_target
    SERVER_RUNNER_AVAILABLE = True
except ImportError:
    SERVER_RUNNER_AVAILABLE = False
    logging.warning("server_runner nicht verfügbar - Server-Tests deaktiviert")


# =========================================================================
# Agent-Erstellung
# =========================================================================
def create_tester(config: Dict[str, Any], project_rules: Dict[str, List[str]], router=None) -> Agent:
    """
    Erstellt den Tester-Agenten, der UI-Tests durchführt.

    Args:
        config: Anwendungskonfiguration mit mode und models
        project_rules: Dictionary mit globalen und rollenspezifischen Regeln
        router: Optionaler ModelRouter für automatisches Fallback bei Rate-Limits

    Returns:
        Konfigurierte CrewAI Agent-Instanz
    """
    # AENDERUNG 02.02.2026: Konsistente Modellwahl mit get_model_from_config (Single Source of Truth)
    if router:
        model = router.get_model("tester")
    else:
        model = get_model_from_config(config, "tester", fallback_role="reviewer")

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


# =========================================================================
# Hilfs-Funktionen
# =========================================================================
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


def _get_ui_test_strategy(project_type: str, tech_blueprint: Dict[str, Any]) -> str:
    """
    Bestimmt die UI-Test-Strategie basierend auf Projekt-Typ und Blueprint.

    Framework-Erkennung hat VORRANG vor expliziter Strategy,
    weil pytest-qt objektiv besser für PyQt/PySide ist (headless, objektbasiert).

    Args:
        project_type: Typ des Projekts (z.B. "pyqt_desktop", "tkinter_desktop")
        tech_blueprint: Vollständiger Blueprint mit Framework-Info

    Returns:
        "pytest_qt" | "pyautogui" | "playwright" | "cli_test" | "none"
    """
    # Framework-Erkennung ZUERST (hat Vorrang!)
    framework = tech_blueprint.get("framework", "").lower()
    dependencies = tech_blueprint.get("dependencies", [])
    deps_lower = [d.lower() for d in dependencies] if dependencies else []

    # Prüfe auf Qt
    is_qt_app = (
        any(fw in framework for fw in ["pyqt", "pyside", "qt"]) or
        any(fw in project_type.lower() for fw in ["pyqt", "pyside"]) or
        any(dep in deps_lower for dep in ["pyqt5", "pyqt6", "pyside2", "pyside6"])
    )

    if is_qt_app:
        logger.info("Qt-Framework erkannt - verwende pytest-qt (Vorrang vor Blueprint-Strategy)")
        return "pytest_qt"

    # Tkinter → PyAutoGUI
    if "tkinter" in project_type.lower() or "tkinter" in framework:
        return "pyautogui"

    # Explizite test_strategy aus Blueprint
    explicit_strategy = tech_blueprint.get("test_strategy", "").lower()
    if explicit_strategy in ["pytest_qt", "pyautogui", "playwright", "cli_test", "pytest_only"]:
        return explicit_strategy

    # app_type basiertes Routing
    app_type = tech_blueprint.get("app_type", "").lower()
    if app_type == "desktop":
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


# =========================================================================
# Haupt-Test-Dispatcher
# =========================================================================
def test_project(project_path: str, tech_blueprint: Dict[str, Any],
                 config: Optional[Dict[str, Any]] = None) -> UITestResult:
    """
    Intelligente Test-Funktion mit Framework-basiertem Routing.

    Entscheidet automatisch basierend auf Framework-Erkennung:
    - PyQt/PySide: pytest-qt (headless, objektbasiert)
    - Tkinter: PyAutoGUI (screenshot-basiert)
    - Webapp: Playwright Browser-Tests
    - CLI: Kommandozeilen-Output Tests
    - API: Nur Unit-Tests (kein UI-Test)

    Args:
        project_path: Pfad zum Projektverzeichnis
        tech_blueprint: Blueprint vom TechStack-Architect
        config: Optionale Konfiguration

    Returns:
        UITestResult Dictionary
    """
    project_type = tech_blueprint.get("project_type", "unknown")
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

    # pytest-qt für PyQt/PySide Apps
    if strategy == "pytest_qt":
        if PYTEST_QT_TESTER_AVAILABLE:
            logger.info("Verwende pytest-qt Tests (headless)")
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

    # Desktop-Apps mit PyAutoGUI
    if strategy == "pyautogui":
        logger.info("Verwende Desktop-Test (PyAutoGUI)")
        return test_desktop_app(project_path, tech_blueprint, config)

    # CLI-Apps testen
    if strategy == "cli_test":
        logger.info("Verwende CLI-Test")
        return test_cli_app(project_path, tech_blueprint, config)

    # API-only oder pytest_only: Keine UI-Tests
    if strategy == "none" or strategy == "pytest_only":
        logger.info("Keine UI-Tests (API oder pytest_only)")
        return {
            "status": "OK",
            "issues": ["UI-Tests übersprungen (app_type: api oder test_strategy: pytest_only)"],
            "screenshot": None
        }

    # Standard: Webapp-Tests mit Playwright
    logger.info("Verwende Webapp-Test (Playwright)")

    if not SERVER_RUNNER_AVAILABLE:
        logger.warning("server_runner nicht verfügbar - Fallback auf statische Tests")
        from file_utils import find_html_file
        html_file = find_html_file(project_path)
        if html_file:
            return test_web_ui(html_file, config)
        return {
            "status": "ERROR",
            "issues": ["Keine HTML-Datei gefunden und server_runner nicht verfügbar"],
            "screenshot": None
        }

    # Ermittle Test-Ziel
    test_target, needs_server = get_test_target(project_path, tech_blueprint)

    if not test_target:
        logger.warning("Kein Test-Ziel ermittelt")
        return {
            "status": "ERROR",
            "issues": ["Kein Test-Ziel (URL oder HTML-Datei) gefunden"],
            "screenshot": None
        }

    if needs_server:
        logger.info(f"Server-Test: Starte Server und teste {test_target}")
        return _test_with_server(project_path, tech_blueprint, test_target, config)
    else:
        logger.info(f"Statischer Test: Teste Datei {test_target}")
        return test_web_ui(test_target, config)


# =========================================================================
# Expliziter __all__ Export für IDE-Unterstützung und Dokumentation
# =========================================================================
__all__ = [
    # Types
    'UITestResult',
    'DEFAULT_GLOBAL_TIMEOUT',
    'DEFAULT_NETWORKIDLE_TIMEOUT',
    'MAX_RETRIES',
    'RETRY_DELAY',
    # Agent
    'create_tester',
    # Test-Funktionen
    'test_project',
    'test_web_ui',
    'test_desktop_app',
    'test_cli_app',
    # Hilfs-Funktionen
    'summarize_ui_result',
    'compare_images',
    '_get_ui_test_strategy',
    '_detect_qt_framework_in_project',
    '_check_display_available',
    '_test_with_server',
    '_test_url',
    # Status-Variablen
    'PYAUTOGUI_AVAILABLE',
    'PYAUTOGUI_ERROR',
    'PYTEST_QT_TESTER_AVAILABLE',
    'SERVER_RUNNER_AVAILABLE'
]
