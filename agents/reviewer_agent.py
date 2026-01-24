# -*- coding: utf-8 -*-
"""
Reviewer Agent: Validiert Code-Qualität, Funktionalität und Regelkonformität.
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
        model = _get_model_from_config(config, "reviewer")

    global_rules = "\n".join(project_rules.get("global", []))
    role_rules = "\n".join(project_rules.get("reviewer", []))
    combined_rules = f"Globale Regeln:\n{global_rules}\n\nReviewer-spezifische Regeln:\n{role_rules}"

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
