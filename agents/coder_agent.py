# -*- coding: utf-8 -*-
"""
Coder Agent: Generiert Production-Ready Code basierend auf Projektanforderungen.
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
        model = _get_model_from_config(config, "coder")

    global_rules = "\n".join(project_rules.get("global", []))
    role_rules = "\n".join(project_rules.get("coder", []))
    combined_rules = f"Globale Regeln:\n{global_rules}\n\nCoder-spezifische Regeln:\n{role_rules}"

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
