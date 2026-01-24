# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 24.01.2026
Version: 1.1
Beschreibung: Coder Agent - Generiert Production-Ready Code basierend auf Projektanforderungen.
"""

from typing import Any, Dict, List, Optional
from crewai import Agent

# ÄNDERUNG 24.01.2026: Zentrale Hilfsfunktion verwenden (Single Source of Truth)
from agents.agent_utils import get_model_from_config, combine_project_rules


def create_coder(config: Dict[str, Any], project_rules: Dict[str, List[str]], router=None) -> Agent:
    """
    Erstellt den Coder-Agenten, der auf Basis des Plans und Feedbacks
    funktionierenden, sauberen Code schreibt.

    Args:
        config: Anwendungskonfiguration mit mode und models
        project_rules: Dictionary mit globalen und rollenspezifischen Regeln
        router: Optional ModelRouter für Fallback bei Rate Limits

    Returns:
        Konfigurierte CrewAI Agent-Instanz
    """
    if router:
        model = router.get_model("coder")
    else:
        model = get_model_from_config(config, "coder")

    combined_rules = combine_project_rules(project_rules, "coder")

    return Agent(
        role="Senior Full-Stack Developer",
        goal=(
            "Schreibe sauberen, effizienten und vor allem SOFORT AUSFÜHRBAREN Code. "
            "Stelle sicher, dass alle notwendigen Dateien (Backend, Frontend, Config, Setup-Scripte) vorhanden sind. "
            "Erstelle immer eine `run.bat` (für Windows), die alle Dienste startet und ggf. den Browser öffnet."
        ),
        backstory=(
            "Du bist ein pragmatischer Senior Developer. Dein Ziel ist 'Production-Ready Code'. "
            "Du denkst nicht nur an die Logik, sondern auch an die Deployment-Fähigkeit. "
            "Wenn du ein Web-Projekt baust, sorge dafür, dass Backend und Frontend harmonieren. "
            "Nutze das Format ### FILENAME: Pfad/Datei.ext für JEDE Datei.\n\n"
            f"{combined_rules}"
        ),
        llm=model,
        verbose=True
    )
