# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 31.01.2026
Version: 1.0
Beschreibung: README-Generierung für Orchestration Manager.
              Extrahiert aus orchestration_manager.py (Regel 1: Max 500 Zeilen)
              ÄNDERUNG 30.01.2026: Einfache README-Generierung ohne LLM
              ÄNDERUNG 31.01.2026: Echter Documentation Manager Agent für bessere Qualität
"""

import os
import logging
from datetime import datetime
from typing import Dict, Any, Optional, Callable

from crewai import Task
from .claude_sdk_provider import run_sdk_with_retry

logger = logging.getLogger(__name__)


def generate_simple_readme(
    project_path: str,
    tech_blueprint: dict,
    discovery_briefing: Optional[Dict[str, Any]] = None,
    doc_service = None
) -> str:
    """
    Generiert eine einfache README.md basierend auf dem Kontext.
    Verwendet kein LLM, sondern Template-basierte Generierung.

    Args:
        project_path: Pfad zum Projekt
        tech_blueprint: TechStack Blueprint
        discovery_briefing: Discovery Briefing (optional)
        doc_service: DocumentationService Instanz (optional)

    Returns:
        README-Inhalt als String
    """
    ts = tech_blueprint
    project_name = os.path.basename(project_path) if project_path else "Projekt"

    # Basis-Template
    readme_parts = [
        f"# {project_name}",
        "",
        f"**Generiert von AgentSmith Multi-Agent System**",
        f"*Erstellt am: {datetime.now().strftime('%d.%m.%Y %H:%M')}*",
        "",
        "## Beschreibung",
        "",
    ]

    # Briefing-Ziel wenn vorhanden
    if discovery_briefing and discovery_briefing.get("projectGoal"):
        readme_parts.append(discovery_briefing["projectGoal"])
    elif doc_service and doc_service.data.get("goal"):
        readme_parts.append(doc_service.data["goal"])
    else:
        readme_parts.append("*Keine Beschreibung verfügbar.*")

    readme_parts.extend(["", "## Technische Details", ""])

    # TechStack-Details
    readme_parts.append(f"- **Projekttyp:** {ts.get('project_type', 'unbekannt')}")
    readme_parts.append(f"- **Sprache:** {ts.get('language', 'unbekannt')}")
    if ts.get("database"):
        readme_parts.append(f"- **Datenbank:** {ts['database']}")
    if ts.get("requires_server"):
        readme_parts.append(f"- **Server-Port:** {ts.get('server_port', 'nicht definiert')}")

    # Installation
    if ts.get("install_command"):
        readme_parts.extend([
            "",
            "## Installation",
            "",
            "```bash",
            ts["install_command"],
            "```",
        ])

    # Start
    if ts.get("run_command"):
        readme_parts.extend([
            "",
            "## Starten",
            "",
            "```bash",
            ts["run_command"],
            "```",
        ])

    # Windows-Batch falls vorhanden
    if project_path and os.path.exists(os.path.join(project_path, "run.bat")):
        readme_parts.extend([
            "",
            "Oder unter Windows:",
            "",
            "```batch",
            "run.bat",
            "```",
        ])

    # Lizenz-Hinweis
    readme_parts.extend([
        "",
        "## Lizenz",
        "",
        "Erstellt mit AgentSmith - Multi-Agent Development System",
        "",
        "---",
        f"*Auto-generiert am {datetime.now().strftime('%d.%m.%Y')}*"
    ])

    return "\n".join(readme_parts)


def generate_readme_with_agent(
    context: str,
    config: dict,
    project_rules: dict,
    model_router,
    project_path: str,
    tech_blueprint: dict,
    discovery_briefing: Optional[Dict[str, Any]],
    doc_service,
    ui_log_callback: Callable[[str, str, str], None],
    update_worker_status_callback: Callable,
    manager=None
) -> str:
    """
    Generiert README.md mit dem echten Documentation Manager Agent.
    Nutzt LLM für intelligente, kontextbezogene Dokumentation.

    Args:
        context: Der vom DocumentationService generierte Kontext
        config: Konfiguration
        project_rules: Projekt-Regeln
        model_router: Model Router Instanz
        project_path: Projekt-Pfad
        tech_blueprint: TechStack Blueprint
        discovery_briefing: Discovery Briefing
        doc_service: DocumentationService Instanz
        ui_log_callback: UI-Log Callback
        update_worker_status_callback: Worker-Status Update Callback
        manager: OrchestrationManager (fuer Claude SDK Integration)

    Returns:
        README-Inhalt als String
    """
    from agents.documentation_manager_agent import (
        create_documentation_manager,
        get_readme_task_description
    )
    from backend.agent_factory import init_agents

    # AENDERUNG 21.02.2026: Fix 59g — Claude SDK Integration fuer DocManager (Sonnet)
    task_description = get_readme_task_description(context)
    agent_timeouts = config.get("agent_timeouts", {})
    doc_timeout = agent_timeouts.get("documentation_manager", 300)

    if manager:
        sdk_result = run_sdk_with_retry(
            manager, role="documentation_manager", prompt=task_description,
            timeout_seconds=doc_timeout, agent_display_name="DocManager"
        )
        if sdk_result:
            ui_log_callback("DocumentationManager", "Info",
                            "README via Claude SDK (Sonnet) erfolgreich")
            return sdk_result

    # Fallback: CrewAI/OpenRouter
    try:
        agents = init_agents(
            config,
            project_rules,
            router=model_router,
            include=["documentation_manager"]
        )
        doc_agent = agents.get("documentation_manager")

        if not doc_agent:
            ui_log_callback("DocumentationManager", "Warning",
                           "Agent konnte nicht erstellt werden, verwende Template")
            return generate_simple_readme(project_path, tech_blueprint, discovery_briefing, doc_service)

        doc_task = Task(
            description=task_description,
            expected_output="README.md Inhalt in Markdown",
            agent=doc_agent
        )

        ui_log_callback("DocumentationManager", "Status", "LLM generiert README.md...")
        update_worker_status_callback("documentation_manager", "working", "README-Generierung")

        readme_content = str(doc_task.execute_sync())

        update_worker_status_callback("documentation_manager", "idle")
        ui_log_callback("DocumentationManager", "Status", "README.md erfolgreich generiert")

        return readme_content

    except Exception as agent_err:
        update_worker_status_callback("documentation_manager", "idle")
        ui_log_callback("DocumentationManager", "Warning",
                       f"Agent-Generierung fehlgeschlagen: {agent_err}, verwende Template")
        return generate_simple_readme(project_path, tech_blueprint, discovery_briefing, doc_service)
