# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 31.01.2026
Version: 1.0
Beschreibung: Analyst Agent - Clustert Benutzeranforderungen aus Discovery-Briefing.
              Teil des Dart AI Feature-Ableitung Konzepts.

              Workflow: Discovery-Briefing -> Analyst -> Strukturierter Anforderungskatalog
"""

import json
import re
from typing import Any, Dict, List, Optional
from crewai import Agent, Task

from agents.agent_utils import get_model_from_config, combine_project_rules


def create_analyst(config: Dict[str, Any], project_rules: Dict[str, List[str]], router=None) -> Agent:
    """
    Erstellt den Analyst Agenten.
    Analysiert das Discovery-Briefing und extrahiert strukturierte Anforderungen.

    Args:
        config: Anwendungskonfiguration mit mode und models
        project_rules: Dictionary mit globalen und rollenspezifischen Regeln
        router: Optional ModelRouter fuer Fallback bei Rate Limits

    Returns:
        Konfigurierte CrewAI Agent-Instanz
    """
    if router:
        # Analyst nutzt das Meta-Orchestrator-Modell (analytische Aufgabe)
        model = router.get_model("meta_orchestrator")
    else:
        model = get_model_from_config(config, "meta_orchestrator")

    combined_rules = combine_project_rules(project_rules, "analyst")

    return Agent(
        role="Anforderungs-Analyst",
        goal=(
            "Analysiere das Discovery-Briefing und erstelle einen strukturierten "
            "Anforderungskatalog mit kategorisierten Anforderungen."
        ),
        backstory=(
            "Du bist ein erfahrener Business Analyst mit Expertise in Requirements Engineering.\n"
            "Du analysierst Benutzeranforderungen und strukturierst sie in klare Kategorien.\n\n"
            "DEINE AUFGABEN:\n"
            "1. Extrahiere alle expliziten und impliziten Anforderungen aus dem Briefing\n"
            "2. Kategorisiere jede Anforderung (Funktional, Technisch, UI/UX, Sicherheit, etc.)\n"
            "3. Weise jeder Anforderung eine Prioritaet zu (hoch, mittel, niedrig)\n"
            "4. Verknuepfe Anforderungen mit ihrer Quelle im Briefing\n\n"
            "AUSGABE-FORMAT (strikt JSON):\n"
            "```json\n"
            "{\n"
            '  "anforderungen": [\n'
            "    {\n"
            '      "id": "REQ-001",\n'
            '      "titel": "Benutzer-Authentifizierung",\n'
            '      "beschreibung": "Das System muss eine sichere Login-Funktion bieten",\n'
            '      "kategorie": "Sicherheit",\n'
            '      "prioritaet": "hoch",\n'
            '      "quelle": "Discovery-Frage 3: Sicherheitsanforderungen",\n'
            '      "akzeptanzkriterien": ["Login funktioniert", "Passwort wird verschluesselt"]\n'
            "    }\n"
            "  ],\n"
            '  "kategorien": ["Funktional", "Sicherheit", "UI/UX", "Daten", "Integration"],\n'
            '  "zusammenfassung": "Kurze Zusammenfassung der Hauptanforderungen"\n'
            "}\n"
            "```\n\n"
            "REGELN:\n"
            "- Jede Anforderung braucht eine eindeutige ID (REQ-001, REQ-002, ...)\n"
            "- Kategorien muessen konsistent sein (gleiche Schreibweise)\n"
            "- Akzeptanzkriterien muessen testbar formuliert sein\n"
            "- Priorisierung: 'hoch' = Kernfunktion, 'mittel' = wichtig, 'niedrig' = nice-to-have\n"
            f"\n{combined_rules}"
        ),
        llm=model,
        verbose=True
    )


def create_analysis_task(agent: Agent, briefing: Dict[str, Any]) -> Task:
    """
    Erstellt einen Analyse-Task fuer den Analyst-Agenten.

    Args:
        agent: Der Analyst-Agent
        briefing: Das Discovery-Briefing

    Returns:
        CrewAI Task-Instanz
    """
    # Briefing in lesbaren Text umwandeln
    briefing_text = _format_briefing(briefing)

    description = f"""Analysiere das folgende Discovery-Briefing und erstelle einen strukturierten Anforderungskatalog.

DISCOVERY-BRIEFING:
{briefing_text}

DEINE AUFGABE:
1. Identifiziere alle Anforderungen (explizit und implizit)
2. Kategorisiere jede Anforderung
3. Weise Prioritaeten zu
4. Formuliere Akzeptanzkriterien

Gib NUR den JSON-Block aus, keine zusaetzlichen Erklaerungen.
"""

    return Task(
        description=description,
        expected_output="JSON mit Anforderungskatalog",
        agent=agent
    )


def _format_briefing(briefing: Dict[str, Any]) -> str:
    """
    Formatiert das Briefing in lesbaren Text.

    Args:
        briefing: Das Discovery-Briefing Dict

    Returns:
        Formatierter Text
    """
    text = f"""
PROJEKT: {briefing.get('projectName', 'Unbenannt')}

ZIEL:
{briefing.get('goal', 'Nicht definiert')}

TECHNISCHE ANFORDERUNGEN:
- Sprache: {briefing.get('techRequirements', {}).get('language', 'auto')}
- Deployment: {briefing.get('techRequirements', {}).get('deployment', 'local')}

BETEILIGTE AGENTEN: {', '.join(briefing.get('agents', []))}

ENTSCHEIDUNGEN AUS DISCOVERY:
"""

    answers = briefing.get('answers', [])
    for i, answer in enumerate(answers, 1):
        if not answer.get('skipped', False):
            agent = answer.get('agent', 'Unbekannt')
            question = answer.get('question', '')
            values = answer.get('selectedValues', [])
            custom = answer.get('customText', '')
            response = ', '.join(values) if values else custom
            text += f"\nFrage {i} ({agent}): {question}\nAntwort: {response}\n"

    open_points = briefing.get('openPoints', [])
    if open_points:
        text += "\nOFFENE PUNKTE:\n"
        for point in open_points:
            text += f"- {point}\n"

    return text


def parse_analyst_output(output: str) -> Optional[Dict[str, Any]]:
    """
    Parst den Analyst-Output und extrahiert den Anforderungskatalog.

    Args:
        output: Raw-Output des Analyst-Agenten

    Returns:
        Dict mit anforderungen-Liste oder None bei Fehler
    """
    if not output:
        return None

    # Versuche JSON-Block zu extrahieren
    json_patterns = [
        r'```json\s*(.*?)\s*```',
        r'```\s*(.*?)\s*```',
        r'\{[\s\S]*"anforderungen"[\s\S]*\}'
    ]

    for pattern in json_patterns:
        matches = re.findall(pattern, output, re.DOTALL)
        if matches:
            json_str = matches[0] if isinstance(matches[0], str) else matches[0]
            try:
                result = json.loads(json_str)
                if "anforderungen" in result and isinstance(result["anforderungen"], list):
                    return result
            except json.JSONDecodeError:
                continue

    # Fallback: Versuche gesamten Output als JSON
    try:
        result = json.loads(output.strip())
        if "anforderungen" in result:
            return result
    except json.JSONDecodeError:
        pass

    return None


def create_default_requirements(briefing: Dict[str, Any]) -> Dict[str, Any]:
    """
    Erstellt Standard-Anforderungen wenn der Analyst-Agent fehlschlaegt.

    Args:
        briefing: Das Discovery-Briefing

    Returns:
        Standard-Anforderungskatalog
    """
    goal = briefing.get('goal', 'Projekt erstellen')
    project_name = briefing.get('projectName', 'Projekt')

    return {
        "anforderungen": [
            {
                "id": "REQ-001",
                "titel": "Hauptfunktionalitaet",
                "beschreibung": f"Das System muss die Kernfunktion erfuellen: {goal}",
                "kategorie": "Funktional",
                "prioritaet": "hoch",
                "quelle": "Projektziel",
                "akzeptanzkriterien": ["Kernfunktion ist implementiert", "System ist ausfuehrbar"]
            },
            {
                "id": "REQ-002",
                "titel": "Benutzeroberflaeche",
                "beschreibung": "Das System muss eine benutzerfreundliche Oberflaeche haben",
                "kategorie": "UI/UX",
                "prioritaet": "mittel",
                "quelle": "Implizit",
                "akzeptanzkriterien": ["UI ist vorhanden", "Bedienung ist intuitiv"]
            },
            {
                "id": "REQ-003",
                "titel": "Fehlerbehandlung",
                "beschreibung": "Das System muss Fehler angemessen behandeln",
                "kategorie": "Technisch",
                "prioritaet": "mittel",
                "quelle": "Best Practice",
                "akzeptanzkriterien": ["Keine unbehandelten Exceptions", "Fehlermeldungen sind verstaendlich"]
            }
        ],
        "kategorien": ["Funktional", "UI/UX", "Technisch"],
        "zusammenfassung": f"Grundanforderungen fuer {project_name}",
        "source": "default_fallback"
    }
