# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 31.01.2026
Version: 1.2
Beschreibung: Test-Generierungs-Utilities für DevLoop.
              Extrahiert aus dev_loop_steps.py (Regel 1: Max 500 Zeilen)
              Enthält: Test-Generator Aufruf, Test-Existenz-Prüfung
              ÄNDERUNG 30.01.2026: Test-Generator für Free-Tier-Modelle die Unit-Tests ignorieren.
              ÄNDERUNG 03.02.2026: Dynamische Test-Erkennung via LANGUAGE_TEST_CONFIG
                                   Unterstützt: Python, JS/TS, C#/.NET, PHP, C++, Go, Rust, Java, etc.
"""

import fnmatch
import os
from typing import Dict, List

from crewai import Crew

from agents.test_generator_agent import (
    create_test_generator,
    create_test_generation_task,
    extract_test_files
)
from backend.test_templates import create_fallback_tests
from backend.qg_constants import get_test_config_for_project


def _matches_any_pattern(filename: str, patterns: List[str]) -> bool:
    """Prüft ob ein Dateiname einem der Patterns entspricht (fnmatch)."""
    for pattern in patterns:
        if fnmatch.fnmatch(filename, pattern):
            return True
    return False


def _is_test_file(filename: str, test_config: Dict) -> bool:
    """Prüft ob eine Datei eine Test-Datei ist basierend auf Config."""
    test_patterns = test_config.get("test_patterns", [])
    return _matches_any_pattern(filename, test_patterns)


def _is_code_file(filename: str, test_config: Dict) -> bool:
    """Prüft ob eine Datei eine Code-Datei ist (keine Test-Datei)."""
    code_extensions = test_config.get("code_extensions", [])
    skip_patterns = test_config.get("skip_patterns", [])

    # Muss eine der Code-Extensions haben
    has_code_ext = any(filename.endswith(ext) for ext in code_extensions)
    if not has_code_ext:
        return False

    # Darf kein Skip-Pattern enthalten
    for skip in skip_patterns:
        if skip in filename:
            return False

    return True


# =========================================================================
# ÄNDERUNG 30.01.2026: Test-Generierung für Free-Tier-Modelle
# =========================================================================

def run_test_generator(manager, code_files: Dict[str, str], iteration: int) -> bool:
    """
    Führt den Test-Generator Agent aus wenn keine Tests vorhanden sind.

    Args:
        manager: OrchestrationManager Instanz
        code_files: Dict mit Dateiname → Inhalt
        iteration: Aktuelle Iteration

    Returns:
        True wenn Tests erstellt wurden
    """
    manager._ui_log("TestGenerator", "Status", "Starte Test-Generierung...")

    try:
        # Erstelle Test-Generator Agent
        test_agent = create_test_generator(
            manager.config,
            manager.project_rules,
            router=manager.model_router
        )

        # Erstelle Task
        task = create_test_generation_task(
            test_agent,
            code_files,
            manager.tech_blueprint.get("project_type", "python_script"),
            manager.tech_blueprint
        )

        # Führe Task aus
        crew = Crew(agents=[test_agent], tasks=[task], verbose=True)
        result = crew.kickoff()

        # Parse Output und erstelle Dateien
        result_str = str(result)
        if result_str and "### FILENAME:" in result_str:
            test_files = extract_test_files(result_str)
            if test_files:
                # Speichere Test-Dateien
                for filename, content in test_files.items():
                    full_path = os.path.join(manager.project_path, filename)
                    dir_path = os.path.dirname(full_path)
                    if dir_path:  # Nur wenn Unterverzeichnis nötig
                        os.makedirs(dir_path, exist_ok=True)
                    with open(full_path, "w", encoding="utf-8") as f:
                        f.write(content)

                manager._ui_log("TestGenerator", "Result",
                    f"Tests erstellt: {', '.join(test_files.keys())}")
                return True

        # Agent hat keine Tests erstellt → Fallback
        manager._ui_log("TestGenerator", "Warning",
            "Agent hat keine Tests erstellt, verwende Templates...")
        return False

    except Exception as e:
        manager._ui_log("TestGenerator", "Error", f"Test-Generator fehlgeschlagen: {e}")
        return False


def ensure_tests_exist(manager, iteration: int) -> bool:
    """
    Stellt sicher dass Unit-Tests existieren.
    Ruft Test-Generator auf wenn nötig, dann Fallback zu Templates.

    Diese Funktion löst das Problem dass Free-Tier-Modelle (xiaomi, qwen, etc.)
    die Anweisung zum Erstellen von Unit-Tests ignorieren.

    ÄNDERUNG 03.02.2026: Dynamische Test-Erkennung via LANGUAGE_TEST_CONFIG
    Unterstützt alle Sprachen: Python, JS/TS, C#/.NET, PHP, C++, Go, Rust, Java, etc.

    Args:
        manager: OrchestrationManager Instanz
        iteration: Aktuelle Iteration

    Returns:
        True wenn Tests existieren (oder erstellt wurden)
    """
    tests_dir = os.path.join(manager.project_path, "tests")

    # ÄNDERUNG 03.02.2026: Dynamische Test-Config basierend auf Blueprint
    tech_blueprint = manager.tech_blueprint or {}
    test_config = get_test_config_for_project(tech_blueprint)
    test_patterns = test_config.get("test_patterns", [])
    test_command = test_config.get("test_command")
    language = tech_blueprint.get("language", "python")

    # Keine Unit-Tests für statische Projekte (HTML/CSS)
    if not test_patterns:
        manager._ui_log("Tester", "Info", "Statisches Projekt - nur UI-Tests moeglich")
        return True

    # Prüfe ob Tests im tests/ Verzeichnis existieren
    if os.path.exists(tests_dir) and os.path.isdir(tests_dir):
        test_files = [f for f in os.listdir(tests_dir) if _is_test_file(f, test_config)]
        if test_files:
            manager._ui_log("Tester", "Info", f"Tests vorhanden: {len(test_files)} Dateien")
            return True

    # Auch Root-Level Tests prüfen
    root_test_files = []
    if os.path.exists(manager.project_path) and os.path.isdir(manager.project_path):
        root_test_files = [f for f in os.listdir(manager.project_path) if _is_test_file(f, test_config)]
    if root_test_files:
        manager._ui_log("Tester", "Info", f"Tests im Root: {len(root_test_files)} Dateien")
        return True

    # Für nicht-Python Sprachen: Test-Ausführung dem nativen Tool überlassen
    if language.lower() != "python" and test_command:
        manager._ui_log("Tester", "Info",
            f"{language.capitalize()}-Projekt - Tests werden via '{test_command}' ausgefuehrt")
        return True

    manager._ui_log("Tester", "Warning", "Keine Unit-Tests gefunden, starte Test-Generierung...")

    # Sammle vorhandene Code-Dateien basierend auf Config
    code_files = {}
    for filename in os.listdir(manager.project_path):
        if _is_code_file(filename, test_config):
            filepath = os.path.join(manager.project_path, filename)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    code_files[filename] = f.read()
            except Exception as e:
                manager._ui_log("TestGenerator", "Warning", f"Konnte {filename} nicht lesen: {e}")

    if not code_files:
        manager._ui_log("TestGenerator", "Warning",
            f"Keine {language.capitalize()}-Dateien zum Testen gefunden")
        return False

    # Versuch 1: Test-Generator Agent (nur bei Iteration > 0 um nicht jeden Run zu verlangsamen)
    if iteration > 0:
        if run_test_generator(manager, code_files, iteration):
            return True

    # Versuch 2: Template-basierte Tests
    manager._ui_log("Tester", "Info", "Verwende Template-Tests als Fallback...")
    project_type = manager.tech_blueprint.get("project_type", "python_script")
    created = create_fallback_tests(manager.project_path, project_type)

    if created:
        manager._ui_log("Tester", "Result", f"Template-Tests erstellt: {', '.join(created)}")
        return True
    else:
        manager._ui_log("Tester", "Error", "Keine passenden Test-Templates gefunden")
        return False
