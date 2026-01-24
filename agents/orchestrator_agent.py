# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 24.01.2026
Version: 1.1
Beschreibung: Orchestrator Agent - Projektleiter für Regelkonformität und Dokumentation.
"""

from typing import Any, Dict, List, Optional
from crewai import Agent

# ÄNDERUNG 24.01.2026: Zentrale Hilfsfunktion verwenden (Single Source of Truth)
from agents.agent_utils import get_model_from_config, combine_project_rules


def create_orchestrator(config: Dict[str, Any], project_rules: Dict[str, List[str]], router=None) -> Agent:
    """
    Erstellt den Orchestrator-Agenten, der als Projektleiter fungiert.
    Er überwacht die Einhaltung von Regeln und erstellt die Abschlussdokumentation.

    Args:
        config: Anwendungskonfiguration mit mode und models
        project_rules: Dictionary mit globalen und rollenspezifischen Regeln
        router: Optional ModelRouter für Fallback bei Rate Limits

    Returns:
        Konfigurierte CrewAI Agent-Instanz
    """
    if router:
        model = router.get_model("orchestrator")
    else:
        model = get_model_from_config(config, "orchestrator")

    combined_rules = combine_project_rules(project_rules, "orchestrator")

    return Agent(
        role="Orchestrator",
        goal="Überwache den Entwicklungsprozess, prüfe Regelkonformität und erstelle Dokumentation.",
        backstory=(
            "Du bist ein erfahrener technischer Projektleiter (Technical Lead). "
            "Deine Aufgabe ist es, sicherzustellen, dass das Team (Coder, Reviewer) "
            "alle globalen und spezifischen Projektregeln einhält. "
            "Am Ende des Projekts erstellst du eine saubere Dokumentation.\n\n"
            "Du bist streng, aber konstruktiv.\n"
            f"{combined_rules}"
        ),
        llm=model,
        verbose=True
    )
