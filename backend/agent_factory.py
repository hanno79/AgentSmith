"""
Author: rahn
Datum: 31.01.2026
Version: 1.2
Beschreibung: Zentrale Factory fuer Agent-Erstellung im Backend.
              AENDERUNG 31.01.2026: Dart AI Agenten hinzugefuegt (Planner, Analyst, Konzepter).
              AENDERUNG 31.01.2026: Fix-Agent fuer gezielte Code-Korrekturen hinzugefuegt.
"""

from typing import Dict, Any, List

from agents.coder_agent import create_coder
from agents.designer_agent import create_designer
from agents.reviewer_agent import create_reviewer
from agents.tester_agent import create_tester
from agents.database_designer_agent import create_database_designer
from agents.techstack_architect_agent import create_techstack_architect
from agents.security_agent import create_security_agent
# ÄNDERUNG 30.01.2026: Documentation Manager Agent (5. Core Agent)
from agents.documentation_manager_agent import create_documentation_manager
# AENDERUNG 31.01.2026: Dart AI Feature-Ableitung Agenten
from agents.planner_agent import create_planner
from agents.analyst_agent import create_analyst
from agents.konzepter_agent import create_konzepter
# AENDERUNG 31.01.2026: Fix-Agent fuer gezielte Code-Korrekturen
from agents.fix_agent import create_fix_agent

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
        "designer": lambda: create_designer(config, project_rules, router=router),
        # ÄNDERUNG 30.01.2026: Documentation Manager (5. Core Agent)
        "documentation_manager": lambda: create_documentation_manager(config, project_rules, router=router),
        # AENDERUNG 31.01.2026: Dart AI Feature-Ableitung Agenten
        "planner": lambda: create_planner(config, project_rules, router=router),
        "analyst": lambda: create_analyst(config, project_rules, router=router),
        "konzepter": lambda: create_konzepter(config, project_rules, router=router),
        # AENDERUNG 31.01.2026: Fix-Agent fuer gezielte Code-Korrekturen
        "fix": lambda: create_fix_agent(config, project_rules, router=router)
    }

    selected = include or list(available.keys())
    return {key: available[key]() for key in selected if key in available}
