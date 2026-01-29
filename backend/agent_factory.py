"""
Author: rahn
Datum: 29.01.2026
Version: 1.0
Beschreibung: Zentrale Factory fuer Agent-Erstellung im Backend.
"""

from typing import Dict, Any, List

from agents.coder_agent import create_coder
from agents.designer_agent import create_designer
from agents.reviewer_agent import create_reviewer
from agents.tester_agent import create_tester
from agents.database_designer_agent import create_database_designer
from agents.techstack_architect_agent import create_techstack_architect
from agents.security_agent import create_security_agent

# ÄNDERUNG 29.01.2026: Agent-Erstellung in zentrale Factory ausgelagert


def init_agents(
    config: Dict[str, Any],
    project_rules: Dict[str, Any],
    router=None,
    include: List[str] = None
) -> Dict[str, Any]:
    """
    Erstellt alle benoetigten Agenten fuer den Orchestration-Flow.

    Args:
        config: Globale Konfiguration
        project_rules: Projekt-spezifische Regeln/Templates
        router: Optionaler ModelRouter fuer konsistente Modell-Auswahl

    Returns:
        Dict mit Agent-Instanzen (coder, reviewer, tester, security, db_designer, techstack_architect, designer)
    """
    # ÄNDERUNG 29.01.2026: Optional nur ausgewaehlte Agenten instanziieren
    available = {
        "coder": lambda: create_coder(config, project_rules, router=router),
        "reviewer": lambda: create_reviewer(config, project_rules, router=router),
        "tester": lambda: create_tester(config, project_rules, router=router),
        "security": lambda: create_security_agent(config, project_rules, router=router),
        "db_designer": lambda: create_database_designer(config, project_rules, router=router),
        "techstack_architect": lambda: create_techstack_architect(config, project_rules, router=router),
        "designer": lambda: create_designer(config, project_rules, router=router)
    }

    selected = include or list(available.keys())
    return {key: available[key]() for key in selected if key in available}
