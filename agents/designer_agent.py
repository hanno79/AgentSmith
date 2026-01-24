# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 24.01.2026
Version: 1.1
Beschreibung: Designer Agent - Erstellt UI/UX-Konzepte mit technischen Design-Specs.
"""

from typing import Any, Dict, List, Optional
from crewai import Agent

# ÄNDERUNG 24.01.2026: Zentrale Hilfsfunktion verwenden (Single Source of Truth)
from agents.agent_utils import get_model_from_config, combine_project_rules


def create_designer(config: Dict[str, Any], project_rules: Dict[str, List[str]], router=None) -> Agent:
    """
    Erstellt den Designer-Agenten, der UI/UX-Konzepte oder visuelle Entwürfe vorschlägt.
    Wird nur aktiviert, wenn include_designer in der config.yaml = true ist.

    Args:
        config: Anwendungskonfiguration mit mode und models
        project_rules: Dictionary mit globalen und rollenspezifischen Regeln
        router: Optional ModelRouter für Fallback bei Rate Limits

    Returns:
        Konfigurierte CrewAI Agent-Instanz
    """
    if router:
        model = router.get_model("designer")
    else:
        model = get_model_from_config(config, "designer")

    combined_rules = combine_project_rules(project_rules, "designer")

    return Agent(
        role="Designer",
        goal=(
            "Erstelle klare UI/UX-Konzepte inklusive technischer Design-Specs. "
            "Liefere konkrete CSS-Variablen (:root), Farbcodes (HEX/RGB) und Layout-Anweisungen, "
            "die ein Entwickler direkt in CSS umsetzen kann."
        ),
        backstory=(
            "Du bist ein erfahrener UI/UX-Designer, der einfache, elegante und funktionale "
            "Designkonzepte entwickelt. Du vermeidest generische 'AI-Farbverläufe' (wie Violett/Neon) "
            "und setzt auf sauberes 'Flat Design', gute Typografie (Inter/Roboto) und Whitespace.\n\n"
            f"{combined_rules}"
        ),
        llm=model,
        verbose=True
    )
