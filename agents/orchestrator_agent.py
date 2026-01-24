# -*- coding: utf-8 -*-
"""
Orchestrator Agent: Projektleiter für Regelkonformität und Dokumentation.
"""

from typing import Any, Dict, List, Optional
from crewai import Agent


def _get_model_from_config(config: Dict[str, Any], role: str) -> str:
    """Hilfsfunktion: Extrahiert Modell aus Config (unterstützt String und Dict-Format)."""
    mode = config.get("mode", "test")
    model_config = config.get("models", {}).get(mode, {}).get(role)
    if isinstance(model_config, str):
        return model_config
    elif isinstance(model_config, dict):
        return model_config.get("primary", "gpt-4")
    return "gpt-4"


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
        model = _get_model_from_config(config, "orchestrator")

    global_rules = "\n".join(project_rules.get("global", []))
    role_rules = "\n".join(project_rules.get("orchestrator", []))
    combined_rules = f"Globale Regeln:\n{global_rules}\n\nOrchestrator-spezifische Regeln:\n{role_rules}"

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
