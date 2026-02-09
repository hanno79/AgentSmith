# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 02.02.2026
Version: 1.1
Beschreibung: Planner Agent - Zerlegt Projekte in einzelne Datei-Tasks.
              AENDERUNG 02.02.2026: Eigenes Planner-Modell statt Coder-Modell.
              Loest das Truncation-Problem bei Free-Tier-Modellen durch
              File-by-File Code-Generierung statt "alles auf einmal".

              Basiert auf Dart AI Feature-Ableitung Konzept v1.0:
              - Max. 4h pro Task
              - EIN konkretes Ergebnis pro Task
              - Abhaengigkeiten zwischen Tasks beruecksichtigen
"""

import json
import re
from typing import Any, Dict, List, Optional
from crewai import Agent, Task

from agents.agent_utils import get_model_from_config, combine_project_rules


def create_planner(config: Dict[str, Any], project_rules: Dict[str, List[str]], router=None) -> Agent:
    """
    Erstellt den Planner Agenten.
    Analysiert den Blueprint und erstellt einen File-by-File Implementierungsplan.

    Args:
        config: Anwendungskonfiguration mit mode und models
        project_rules: Dictionary mit globalen und rollenspezifischen Regeln
        router: Optional ModelRouter fuer Fallback bei Rate Limits

    Returns:
        Konfigurierte CrewAI Agent-Instanz
    """
    if router:
        # AENDERUNG 02.02.2026: Planner nutzt eigenes Modell fuer bessere Kontrolle
        model = router.get_model("planner")
    else:
        model = get_model_from_config(config, "planner")

    combined_rules = combine_project_rules(project_rules, "planner")

    return Agent(
        role="Planner",
        goal=(
            "Analysiere den Projekt-Blueprint und erstelle einen strukturierten "
            "Implementierungsplan mit einzelnen Datei-Tasks. "
            "Jeder Task = Eine Datei = Ein Coder-Aufruf."
        ),
        backstory=(
            "Du bist ein erfahrener Projektplaner und Software-Architekt.\n"
            "Du zerlegst Projekte in kleine, ueberschaubare Einheiten.\n\n"
            "GRUNDREGELN (Dart AI Feature-Ableitung):\n"
            "- Jeder Task erstellt genau EINE Datei\n"
            "- Maximale Dateigroesse: 200 Zeilen Code\n"
            "- Groessere Dateien in Module aufteilen\n"
            "- Abhaengigkeiten klar definieren (welche Datei braucht welche andere)\n\n"
            "STANDARD-DATEISTRUKTUR fuer Python-Projekte:\n"
            "1. src/config.py - Konfiguration, Konstanten (keine Abhaengigkeiten)\n"
            "2. src/database.py - Datenbanklogik (abhaengig von config)\n"
            "3. src/models.py - Datenmodelle (abhaengig von config)\n"
            "4. src/utils.py - Hilfsfunktionen (abhaengig von config)\n"
            "5. src/main.py - Hauptlogik, UI (abhaengig von allen anderen)\n"
            "6. requirements.txt - Dependencies (keine Abhaengigkeiten)\n"
            "7. run.bat - Startskript (abhaengig von requirements.txt)\n"
            "8. tests/test_database.py - DB-Tests (abhaengig von database)\n"
            "9. tests/test_main.py - Haupttests (abhaengig von main)\n\n"
            "AUSGABE-FORMAT (strikt JSON):\n"
            "```json\n"
            "{\n"
            '  "project_name": "todo_app",\n'
            '  "total_files": 5,\n'
            '  "estimated_lines": 450,\n'
            '  "files": [\n'
            "    {\n"
            '      "path": "src/config.py",\n'
            '      "description": "Konfiguration und Konstanten",\n'
            '      "depends_on": [],\n'
            '      "estimated_lines": 30,\n'
            '      "priority": 1\n'
            "    },\n"
            "    {\n"
            '      "path": "src/database.py",\n'
            '      "description": "SQLite TodoDatabase Klasse mit CRUD-Operationen",\n'
            '      "depends_on": ["src/config.py"],\n'
            '      "estimated_lines": 80,\n'
            '      "priority": 2\n'
            "    }\n"
            "  ]\n"
            "}\n"
            "```\n\n"
            "WICHTIG:\n"
            "- priority: Niedrigere Zahlen = frueher erstellen\n"
            "- depends_on: Liste der Dateien die vorher existieren muessen\n"
            "- Unabhaengige Dateien koennen parallel erstellt werden\n"
            "- Tests IMMER als letzte Tasks (hoechste Priority-Nummer)\n"
            f"\n{combined_rules}"
        ),
        llm=model,
        verbose=True
    )


def create_planning_task(agent: Agent, blueprint: Dict[str, Any], user_prompt: str) -> Task:
    """
    Erstellt einen Planning-Task fuer den Planner-Agenten.

    Args:
        agent: Der Planner-Agent
        blueprint: TechStack-Blueprint mit project_type, language, etc.
        user_prompt: Original-Anforderung des Benutzers

    Returns:
        CrewAI Task-Instanz
    """
    description = f"""Erstelle einen File-by-File Implementierungsplan fuer dieses Projekt.

BENUTZER-ANFORDERUNG:
{user_prompt}

TECHNISCHER BLUEPRINT:
{json.dumps(blueprint, indent=2, ensure_ascii=False)}

DEINE AUFGABE:
1. Analysiere die Anforderungen und den Blueprint
2. Identifiziere alle benoetigten Dateien
3. Definiere Abhaengigkeiten zwischen den Dateien
4. Erstelle einen strukturierten Plan im JSON-Format

REGELN:
- Jede Datei max. 200 Zeilen
- Grosse Dateien aufteilen (z.B. main.py in main.py + ui.py + handlers.py)
- Tests MUESSEN enthalten sein (tests/test_*.py)
- Startskript (run.bat) MUSS enthalten sein
- requirements.txt/package.json MUSS enthalten sein

Gib NUR den JSON-Block aus, keine zusaetzlichen Erklaerungen.
"""

    # AENDERUNG 08.02.2026: DB-Pflichtdateien an Planner durchreichen (Fix 22.5)
    # ROOT-CAUSE-FIX: Planner plant keine DB-Dateien wenn Blueprint database != "none"
    # Generisch fuer alle Sprachen und Frameworks
    db_type = blueprint.get("database", "none")
    language = blueprint.get("language", "").lower()
    project_type = blueprint.get("project_type", "").lower()

    if db_type and db_type != "none":
        if language in ("javascript", "typescript"):
            if "next" in project_type:
                db_files = (
                    "- lib/db.js: Datenbank-Initialisierung und Verbindung\n"
                    "- app/api/[resource]/route.js: CRUD API-Route Handler (GET/POST/PUT/DELETE)"
                )
            elif "express" in project_type:
                db_files = (
                    "- src/database.js: Datenbank-Initialisierung und Verbindung\n"
                    "- src/routes/: API-Routen mit DB-Zugriff"
                )
            else:
                db_files = "- src/database.js: Datenbank-Initialisierung und Verbindung"
        elif language == "python":
            if "flask" in project_type or "fastapi" in project_type:
                db_files = (
                    "- src/database.py: Datenbank-Initialisierung und Verbindung\n"
                    "- src/models.py: Datenmodelle\n"
                    "- src/routes.py: API-Routen mit DB-Zugriff"
                )
            else:
                db_files = "- src/database.py: Datenbank-Initialisierung und Abfragen"
        else:
            db_files = "- Datenbank-Initialisierungsdatei"

        description += f"""
DATENBANK-PFLICHTDATEIEN (database: {db_type}):
{db_files}
Diese Dateien MUESSEN im Plan enthalten sein!
"""

    return Task(
        description=description,
        expected_output="JSON mit Datei-Liste und Abhaengigkeiten",
        agent=agent
    )


def parse_planner_output(output: str) -> Optional[Dict[str, Any]]:
    """
    Parst den Planner-Output und extrahiert den JSON-Plan.

    Args:
        output: Raw-Output des Planner-Agenten

    Returns:
        Dict mit files-Liste oder None bei Fehler
    """
    if not output:
        return None

    # Versuche JSON-Block zu extrahieren
    json_patterns = [
        r'```json\s*(.*?)\s*```',  # Markdown JSON-Block
        r'```\s*(.*?)\s*```',       # Generischer Code-Block
        r'\{[\s\S]*"files"[\s\S]*\}' # Rohes JSON mit files
    ]

    for pattern in json_patterns:
        matches = re.findall(pattern, output, re.DOTALL)
        if matches:
            json_str = matches[0] if isinstance(matches[0], str) else matches[0]
            try:
                plan = json.loads(json_str)
                if "files" in plan and isinstance(plan["files"], list):
                    return plan
            except json.JSONDecodeError:
                continue

    # Fallback: Versuche gesamten Output als JSON
    try:
        plan = json.loads(output.strip())
        if "files" in plan:
            return plan
    except json.JSONDecodeError:
        pass

    return None


# AENDERUNG 08.02.2026: Re-Exports aus planner_defaults.py (Regel-1 Refactoring)
# Importeure (file_by_file_loop.py, test_planner_agent.py) brauchen keine Aenderung
from agents.planner_defaults import (  # noqa: F401
    create_default_plan,
    sort_files_by_priority,
    get_ready_files
)
