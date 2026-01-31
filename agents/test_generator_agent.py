"""
Author: rahn
Datum: 30.01.2026
Version: 1.0
Beschreibung: Test Generator Agent - Erstellt Unit-Tests für generierten Code.
              Wird nach dem Coder aufgerufen wenn keine Tests vorhanden sind.
              Teil der zweistufigen Lösung für Free-Tier-Modelle die Unit-Test-
              Anweisungen ignorieren.
"""

from typing import Any, Dict, List
from crewai import Agent, Task
from agents.agent_utils import get_model_from_config, combine_project_rules


def create_test_generator(
    config: Dict[str, Any],
    project_rules: Dict[str, List[str]],
    router=None
) -> Agent:
    """
    Erstellt den Test Generator Agent.

    Args:
        config: Konfigurationsdaten
        project_rules: Projektregeln für den Agent
        router: Optional ModelRouter für dynamische Modellauswahl

    Returns:
        Konfigurierter CrewAI Agent
    """
    if router:
        model = router.get_model("test_generator")
    else:
        model = get_model_from_config(config, "test_generator", fallback_role="tester")

    combined_rules = combine_project_rules(project_rules, "test_generator")

    return Agent(
        role="Test Generator",
        goal=(
            "Erstelle pytest-kompatible Unit-Tests für den generierten Code. "
            "WICHTIG: Du MUSST einen tests/ Ordner mit test_*.py Dateien erstellen. "
            "Teste alle wichtigen Funktionen und Klassen. "
            "Verwende fixtures und parametrize wo sinnvoll."
        ),
        backstory=(
            "Du bist ein Test-Spezialist der NUR Unit-Tests schreibt. "
            "Du erhältst Code und erstellst passende Tests dafür. "
            "Du gibst IMMER Dateien im Format '### FILENAME: tests/test_*.py' aus. "
            "NIEMALS vergisst du den tests/ Ordner zu erstellen.\n\n"
            f"{combined_rules}"
        ),
        llm=model,
        verbose=True,
        allow_delegation=False
    )


def create_test_generation_task(
    agent: Agent,
    code_files: Dict[str, str],
    project_type: str,
    tech_blueprint: Dict[str, Any]
) -> Task:
    """
    Erstellt einen Task für Test-Generierung.

    Args:
        agent: Der Test-Generator Agent
        code_files: Dict mit Dateiname → Inhalt der zu testenden Dateien
        project_type: Typ des Projekts (z.B. "pyqt_desktop")
        tech_blueprint: Technischer Blueprint mit Projektdetails

    Returns:
        CrewAI Task für Test-Generierung
    """
    # Formatiere Code-Dateien für Prompt
    code_listing = "\n\n".join([
        f"### DATEI: {filename}\n```python\n{content}\n```"
        for filename, content in code_files.items()
        if filename.endswith('.py') and not filename.startswith('test_')
    ])

    # Begrenze Code-Listing auf maximal 15000 Zeichen für Kontext-Limit
    if len(code_listing) > 15000:
        code_listing = code_listing[:15000] + "\n\n... (weitere Dateien gekürzt)"

    return Task(
        description=f'''
Du erhältst folgenden Python-Code für ein {project_type} Projekt.
Erstelle pytest-kompatible Unit-Tests.

WICHTIG - DEIN OUTPUT MUSS ENTHALTEN:
1. ### FILENAME: tests/__init__.py  (leere Datei)
2. ### FILENAME: tests/test_<modul>.py für JEDE .py Datei

CODE ZUM TESTEN:
{code_listing}

PROJEKT-INFO:
- Typ: {project_type}
- Datenbank: {tech_blueprint.get("database", "keine")}
- Framework: {tech_blueprint.get("framework", "none")}

ANFORDERUNGEN:
- Verwende pytest
- Mindestens 3 Test-Funktionen pro Modul
- Teste Haupt-Funktionalität und Edge-Cases
- Verwende Mocks für Datenbank-Zugriffe und UI-Komponenten
- Verwende unittest.mock für externe Abhängigkeiten
- Gib ALLE Dateien im Format ### FILENAME: aus

WICHTIG:
- Bei PyQt/Tkinter Apps: Mocke GUI-Komponenten, teste nur Logik
- Bei Datenbank-Apps: Verwende :memory: SQLite oder Mocks
- Jeder Test muss einen aussagekräftigen deutschen Docstring haben
''',
        expected_output="Unit-Test-Dateien im tests/ Ordner mit ### FILENAME: Präfix",
        agent=agent
    )


def extract_test_files(result_text: str) -> Dict[str, str]:
    """
    Extrahiert Test-Dateien aus dem Agent-Output.

    Args:
        result_text: Raw Output vom Agent

    Returns:
        Dict mit Dateiname → Inhalt
    """
    import re

    files = {}

    # Pattern: ### FILENAME: path/to/file.py gefolgt von Inhalt
    pattern = r'### FILENAME:\s*([^\n]+)\n(.*?)(?=### FILENAME:|$)'
    matches = re.findall(pattern, result_text, re.DOTALL)

    for filename, content in matches:
        filename = filename.strip()
        # Entferne mögliche Code-Block-Markierungen
        content = re.sub(r'^```\w*\n?', '', content.strip())
        content = re.sub(r'\n?```$', '', content.strip())

        # Nur Test-Dateien speichern
        if 'test' in filename.lower() or filename.endswith('__init__.py'):
            files[filename] = content

    return files
