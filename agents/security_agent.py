# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 24.01.2026
Version: 1.1
Beschreibung: Security Agent ("The Guardian") - Prüft Code auf Sicherheitslücken.
              Fokus: OWASP Top 10, SQL Injection, XSS, CSRF, Dependency-Audits.
"""

from typing import Any, Dict, List, Optional
from crewai import Agent

# ÄNDERUNG 24.01.2026: Zentrale Hilfsfunktion verwenden (Single Source of Truth)
from agents.agent_utils import get_model_from_config, combine_project_rules


def create_security_agent(config: Dict[str, Any], project_rules: Dict[str, List[str]], router=None) -> Agent:
    """
    Erstellt den Security-Agenten ("The Guardian"), der Code auf Sicherheitslücken prüft.
    Fokus: OWASP Top 10, Dependency-Audits (Simulation), Injection-Prevention.

    Args:
        config: Anwendungskonfiguration mit mode und models
        project_rules: Dictionary mit globalen und rollenspezifischen Regeln
        router: Optional ModelRouter für Fallback bei Rate Limits

    Returns:
        Konfigurierte CrewAI Agent-Instanz
    """
    if router:
        model = router.get_model("security")
    else:
        model = get_model_from_config(config, "security", fallback_role="reviewer")

    combined_rules = combine_project_rules(project_rules, "security")

    return Agent(
        role="Security Specialist (The Guardian)",
        goal=(
            "Analysiere den Code radikal auf Sicherheitslücken. "
            "Denke wie ein Hacker (White Hat). "
            "Prüfe auf SQL-Injection, XSS, CSRF, unsichere Dependencies und Hardcoded Secrets. "
            "Lasse NIEMALS Code durch, der offensichtliche Schwachstellen hat."
        ),
        backstory=(
            "Du bist 'The Guardian', ein spezialisierter Security-Expert. "
            "Du interessierst dich nicht für schöne UIs oder Performance, sondern NUR für Sicherheit. "
            "Du scannst Code auf typische Angriffsvektoren. "
            "Wenn du 'npm install' Befehle siehst, simuliere gedanklich ein 'npm audit' und warne vor bekannten unsicheren Paketen oder Patterns. "
            "Antworte mit 'SECURE', wenn alles sicher ist, oder einer Liste von 'VULNERABILITY: ...', wenn nicht.\n\n"
            f"{combined_rules}"
        ),
        llm=model,
        verbose=True,
        allow_delegation=False
    )
