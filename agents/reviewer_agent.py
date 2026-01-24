# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 24.01.2026
Version: 1.1
Beschreibung: Reviewer Agent - Validiert Code-Qualität, Funktionalität und Regelkonformität.
"""

from typing import Any, Dict, List, Optional
from crewai import Agent

# ÄNDERUNG 24.01.2026: Zentrale Hilfsfunktion verwenden (Single Source of Truth)
from agents.agent_utils import get_model_from_config, combine_project_rules


def create_reviewer(config: Dict[str, Any], project_rules: Dict[str, List[str]], router=None) -> Agent:
    """
    Erstellt den Reviewer-Agenten, der Codequalität, Funktionalität
    und Regelkonformität überprüft.

    Args:
        config: Anwendungskonfiguration mit mode und models
        project_rules: Dictionary mit globalen und rollenspezifischen Regeln
        router: Optional ModelRouter für Fallback bei Rate Limits

    Returns:
        Konfigurierte CrewAI Agent-Instanz
    """
    if router:
        model = router.get_model("reviewer")
    else:
        model = get_model_from_config(config, "reviewer")

    combined_rules = combine_project_rules(project_rules, "reviewer")

    return Agent(
        role="Reviewer",
        goal=(
            "Analysiere Code, Testergebnisse und Sandbox-Ausgaben kritisch. "
            "Finde alle Fehler, Regelverstöße oder Schwachstellen. "
            "Bewerte auch Laufzeitfehler aus der Sandbox (z. B. SyntaxError, Traceback, ModuleNotFoundError) "
            "als kritische Fehler, die eine Überarbeitung erfordern. "
            "Achte darauf, ob der Code tatsächlich fehlerfrei ausgeführt wurde. "
            "WICHTIG: Wenn die Sandbox oder der Tester ein Ergebnis mit '❌' liefern, "
            "darfst du UNTER KEINEN UMSTÄNDEN mit 'OK' antworten. Der Fehler muss erst behoben werden. "
            "Nur wenn die Ausführung erfolgreich war und alle Projektregeln eingehalten wurden, "
            "antworte am Ende klar mit 'OK'."
        ),
        backstory=(
            "Du bist ein erfahrener Software-Tester und Code-Reviewer. "
            "Deine Aufgabe ist es, Code gründlich zu prüfen: Funktion, Stil, Robustheit, "
            "und Regelkonformität. "
            "Wenn du im Ausführungsergebnis Fehlermeldungen siehst, "
            "erkläre die Ursache, gib konkrete Verbesserungsvorschläge "
            "und antworte keinesfalls mit 'OK', bis der Fehler behoben ist.\n\n"
            f"{combined_rules}"
        ),
        llm=model,
        verbose=True,
        allow_delegation=False
    )
