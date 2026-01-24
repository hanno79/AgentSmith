# -*- coding: utf-8 -*-
"""
Designer Agent: Erstellt UI/UX-Konzepte mit technischen Design-Specs.
"""

from typing import Any, Dict, List, Optional
from crewai import Agent


def _get_model_from_config(config: Dict[str, Any], role: str) -> str:
    """Hilfsfunktion: Extrahiert Modell aus Config (unterstützt String und Dict-Format)."""
    mode = config["mode"]
    model_config = config["models"][mode].get(role)
    if isinstance(model_config, str):
        return model_config
    elif isinstance(model_config, dict):
        return model_config.get("primary", "")
    return ""


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
        model = _get_model_from_config(config, "designer")

    global_rules = "\n".join(project_rules.get("global", []))
    role_rules = "\n".join(project_rules.get("designer", []))
    combined_rules = f"Globale Regeln:\n{global_rules}\n\nDesigner-spezifische Regeln:\n{role_rules}"

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
