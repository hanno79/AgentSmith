# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 01.02.2026
Version: 1.3
Beschreibung: Reviewer Agent - Validiert Code-Qualität, Funktionalität und Regelkonformität.
              ÄNDERUNG 01.02.2026: Root Cause Format - Bei Fehlern MUSS Ursachenanalyse erfolgen.
              ÄNDERUNG 28.01.2026: Verschärfte Vollständigkeitsprüfung - kein OK bei fehlenden Dateien.
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

    # ÄNDERUNG 28.01.2026: Verschärfte Vollständigkeitsprüfung
    return Agent(
        role="Reviewer",
        goal=(
            "Analysiere Code, Testergebnisse und Sandbox-Ausgaben kritisch. "
            "Finde alle Fehler, Regelverstöße oder Schwachstellen. "
            "Bewerte auch Laufzeitfehler aus der Sandbox (z. B. SyntaxError, Traceback, ModuleNotFoundError) "
            "als kritische Fehler, die eine Überarbeitung erfordern. "
            "Achte darauf, ob der Code tatsächlich fehlerfrei ausgeführt wurde.\n\n"
            "KRITISCHE PRÜFUNGEN vor OK:\n"
            "1. Sind ALLE referenzierten Dateien vorhanden? (script src, link href, import, require)\n"
            "2. Ist der Code VOLLSTÄNDIG ohne Platzhalter? (keine TODO-Kommentare, keine '...')\n"
            "3. Gibt es KEINE Widersprüche in deiner Analyse?\n\n"
            "VERBOTEN - Sage NIEMALS OK wenn:\n"
            "- Die Sandbox/Tester ein '❌' zeigt\n"
            "- Du selbst schreibst 'muss noch erstellt werden', 'fehlt noch', 'wird benötigt'\n"
            "- Dateien referenziert werden die nicht im Code enthalten sind\n"
            "- Der Code unvollständig ist\n\n"
            "Antworte NUR mit OK wenn der Code KOMPLETT, LAUFFÄHIG und FEHLERFREI ist.\n\n"
            "ROOT CAUSE FORMAT - Bei Fehlern MUSS dein Feedback dieses Format enthalten:\n"
            "URSACHE: [Warum ist der Fehler aufgetreten - die eigentliche Root Cause]\n"
            "BETROFFENE DATEIEN: [Welche Dateien müssen geändert werden]\n"
            "LÖSUNG: [Konkrete Schritte zur Behebung]\n\n"
            "WICHTIG: Analysiere nicht nur WAS falsch ist, sondern WARUM es falsch ist!"
        ),
        backstory=(
            "Du bist ein strenger, erfahrener Software-Tester und Code-Reviewer. "
            "Deine Aufgabe ist es, Code gründlich zu prüfen: Funktion, Stil, Robustheit, "
            "und Regelkonformität.\n\n"
            "SELBSTKONSISTENZ-REGEL:\n"
            "Wenn du in deiner Analyse schreibst dass etwas fehlt oder erstellt werden muss, "
            "dann darfst du NIEMALS mit OK antworten. Das wäre ein Widerspruch.\n"
            "Beispiel VERBOTEN: 'Die index.js muss noch erstellt werden. OK'\n"
            "Beispiel KORREKT: 'Die index.js fehlt. Der Coder muss diese erstellen.'\n\n"
            "Wenn du im Ausführungsergebnis Fehlermeldungen siehst, "
            "erkläre die Ursache, gib konkrete Verbesserungsvorschläge "
            "und antworte keinesfalls mit 'OK', bis ALLE Fehler behoben sind.\n\n"
            f"{combined_rules}"
        ),
        llm=model,
        verbose=True,
        allow_delegation=False
    )
