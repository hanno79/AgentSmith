# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 31.01.2026
Version: 1.0
Beschreibung: HELP_NEEDED Event Handler für Orchestration Manager.
              Extrahiert aus orchestration_manager.py (Regel 1: Max 500 Zeilen)
              ÄNDERUNG 31.01.2026: HELP_NEEDED Handler mit automatischem Test-Generator und Priorisierung.
"""

import os
import json
import logging
from typing import Dict, Any, Callable, Optional

logger = logging.getLogger(__name__)


def handle_help_needed_events(
    session_mgr,
    project_path: str,
    tech_blueprint: dict,
    project_rules: dict,
    model_router,
    config: dict,
    ui_log_callback: Callable[[str, str, str], None],
    iteration: int
) -> Dict[str, Any]:
    """
    Zentraler HELP_NEEDED Handler - verarbeitet blockierte Agents.

    Stufe 1: Automatische Hilfs-Agenten starten
    Stufe 2: Priorisierung und Konsens-Mechanismus

    Args:
        session_mgr: Session Manager Instanz
        project_path: Pfad zum Projekt
        tech_blueprint: TechStack Blueprint
        project_rules: Projekt-Regeln
        model_router: Model Router Instanz
        config: Konfiguration
        ui_log_callback: Callback für UI-Logging
        iteration: Aktuelle DevLoop-Iteration

    Returns:
        Dict mit Status und durchgefuehrten Aktionen
    """
    blocked_agents = session_mgr.get_blocked_agents()

    if not blocked_agents:
        return {"status": "no_blocks", "actions": []}

    ui_log_callback("HelpHandler", "Status",
                    f"Verarbeite {len(blocked_agents)} blockierte Agents...")

    # STUFE 2: Priorisierung - Critical zuerst
    priority_order = {"critical": 0, "high": 1, "normal": 2, "low": 3}
    sorted_agents = sorted(
        blocked_agents.items(),
        key=lambda x: priority_order.get(x[1].get("priority", "normal"), 2)
    )

    actions_taken = []

    for agent_name, block_info in sorted_agents:
        reason_str = block_info.get("reason", "{}")

        try:
            reason_data = json.loads(reason_str)
            action_required = reason_data.get("action_required", "")
        except (json.JSONDecodeError, TypeError) as e:
            logger.error("[parse_blocked_reasons] reason_str=%s Fehler: %s", reason_str[:200], e, exc_info=True)
            action_required = ""

        # STUFE 1: Automatische Aktionen basierend auf action_required
        if action_required == "create_test_files":
            # Test-Generator automatisch starten
            ui_log_callback("HelpHandler", "Action",
                           "Starte Test-Generator fuer fehlende Unit-Tests...")
            success = _run_automatic_test_generator(
                project_path=project_path,
                tech_blueprint=tech_blueprint,
                project_rules=project_rules,
                model_router=model_router,
                config=config,
                ui_log_callback=ui_log_callback,
                iteration=iteration
            )
            actions_taken.append({
                "agent": agent_name,
                "action": "test_generator",
                "success": success
            })
            if success:
                session_mgr.clear_agent_blocked(agent_name)
                ui_log_callback("HelpHandler", "Success",
                               f"Test-Generator hat Tests erstellt - {agent_name} Blockade aufgehoben")

        elif action_required == "security_review_required":
            # Bei kritischen Security Issues: Warnung + Eskalation an Coder
            ui_log_callback("HelpHandler", "Warning",
                           "Kritische Security-Issues - Coder muss in naechster Iteration fixen")
            actions_taken.append({
                "agent": agent_name,
                "action": "escalate_to_coder",
                "success": True  # Eskalation ist erfolgreich
            })
            # NICHT clear_agent_blocked - bleibt blockiert bis gefixt

        else:
            # Unbekannte Aktion - nur loggen
            ui_log_callback("HelpHandler", "Info",
                           f"Unbekannte Aktion fuer {agent_name}: {action_required}")
            actions_taken.append({
                "agent": agent_name,
                "action": "unknown",
                "success": False
            })

    return {
        "status": "processed",
        "blocked_count": len(blocked_agents),
        "actions": actions_taken
    }


def _run_automatic_test_generator(
    project_path: str,
    tech_blueprint: dict,
    project_rules: dict,
    model_router,
    config: dict,
    ui_log_callback: Callable[[str, str, str], None],
    iteration: int
) -> bool:
    """
    Startet den Test-Generator Agent automatisch.

    Args:
        project_path: Pfad zum Projekt
        tech_blueprint: TechStack Blueprint
        project_rules: Projekt-Regeln
        model_router: Model Router Instanz
        config: Konfiguration
        ui_log_callback: Callback für UI-Logging
        iteration: Aktuelle Iteration (fuer Logging)

    Returns:
        True wenn Tests erfolgreich erstellt wurden
    """
    try:
        from agents.test_generator_agent import (
            create_test_generator,
            create_test_generation_task,
            extract_test_files
        )
        from backend.test_templates import create_fallback_tests

        # Sammle vorhandene Code-Dateien (rekursiv, alle .py außer test_*)
        code_files = {}
        if project_path and os.path.exists(project_path):
            for root, _dirs, files in os.walk(project_path):
                for filename in files:
                    if filename.endswith(".py") and not filename.startswith("test_"):
                        filepath = os.path.join(root, filename)
                        try:
                            with open(filepath, "r", encoding="utf-8") as f:
                                code_files[filepath] = f.read()
                        except Exception as e:
                            ui_log_callback("HelpHandler", "Warning", f"Datei nicht lesbar: {filepath} - {e}")

        project_type = tech_blueprint.get("project_type", "python_script") if tech_blueprint else "python_script"

        if not code_files:
            ui_log_callback("HelpHandler", "Warning", "Keine Python-Dateien zum Testen gefunden")
            # Fallback zu Templates trotzdem versuchen
            created = create_fallback_tests(project_path, project_type)
            return len(created) > 0

        # Erstelle Test-Generator Agent
        test_agent = create_test_generator(
            config,
            project_rules,
            router=model_router
        )

        task = create_test_generation_task(
            test_agent,
            code_files,
            project_type,
            tech_blueprint or {}
        )

        # Fuehre Task aus
        from crewai import Crew
        crew = Crew(agents=[test_agent], tasks=[task], verbose=True)
        result = crew.kickoff()

        # Parse und speichere Tests
        result_str = str(result) if result else ""
        if result_str and "### FILENAME:" in result_str:
            test_files = extract_test_files(result_str)

            for filepath, content in test_files.items():
                full_path = os.path.join(project_path, filepath)
                dirpath = os.path.dirname(full_path)
                if not dirpath:
                    dirpath = project_path
                try:
                    os.makedirs(dirpath, exist_ok=True)
                    with open(full_path, "w", encoding="utf-8") as f:
                        f.write(content)
                except (OSError, IOError) as e:
                    logger.warning("Test-Datei konnte nicht geschrieben werden: %s - %s", filepath, e)
                    continue

            ui_log_callback("HelpHandler", "Result",
                           f"Test-Generator hat {len(test_files)} Dateien erstellt")
            return len(test_files) > 0

        # Fallback: Template-Tests
        ui_log_callback("HelpHandler", "Info", "Verwende Template-Tests als Fallback")
        created = create_fallback_tests(project_path, project_type)
        return len(created) > 0

    except Exception as e:
        ui_log_callback("HelpHandler", "Error", f"Test-Generator fehlgeschlagen: {e}")
        # Letzter Fallback: Templates
        try:
            from backend.test_templates import create_fallback_tests
            project_type = tech_blueprint.get("project_type", "python_script") if tech_blueprint else "python_script"
            created = create_fallback_tests(project_path, project_type)
            if created:
                ui_log_callback("HelpHandler", "Info", f"Template-Fallback erstellt: {created}")
                return True
        except Exception as e:
            logger.exception("Template-Fallback fehlgeschlagen: %s", e)
        return False
