# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 01.02.2026
Version: 1.0
Beschreibung: Validator-Agent für Quality Gate und Waisen-Check.
              Prüft Traceability: ANF → FEAT → TASK → FILE
"""

from typing import Dict, List, Any, Optional
from crewai import Agent
from agents.agent_utils import get_model_from_config, combine_project_rules


def create_validator(
    config: Dict[str, Any],
    project_rules: Dict[str, List[str]],
    router=None
) -> Agent:
    """
    Erstellt Validator-Agent für Quality Gate Prüfungen.

    Args:
        config: Konfiguration mit Modell-Einstellungen
        project_rules: Projektspezifische Regeln
        router: Optional ModelRouter für dynamische Modellauswahl

    Returns:
        CrewAI Agent für Validierung
    """
    # Modell-Auswahl mit Fallback auf Reviewer
    if router:
        model = router.get_model("validator")
    else:
        model = get_model_from_config(config, "validator", fallback_role="reviewer")

    combined_rules = combine_project_rules(project_rules, "validator")

    return Agent(
        role="Quality Gate Validator",
        goal=(
            "Validiere alle Projekt-Artefakte gegen Quality Gate Kriterien. "
            "Erkenne Waisen-Anforderungen (ANF ohne Feature), "
            "unvollständige Features (ohne Tasks), "
            "und fehlende Dateien. "
            "Stelle Traceability sicher: ANF → FEAT → TASK → FILE"
        ),
        backstory=(
            "Du bist ein erfahrener Qualitäts-Manager mit Expertise in "
            "Requirements Traceability und Vollständigkeitsprüfung.\n\n"
            "DEINE AUFGABEN:\n"
            "1. Prüfe ob JEDE Anforderung mindestens ein Feature hat\n"
            "2. Prüfe ob JEDES Feature mindestens einen Task hat\n"
            "3. Prüfe ob JEDER Task mindestens eine Datei erzeugt\n"
            "4. Identifiziere Waisen (nicht verknüpfte Elemente)\n"
            "5. Berechne Coverage-Metriken\n\n"
            "OUTPUT-FORMAT:\n"
            "```json\n"
            "{\n"
            '  "passed": true/false,\n'
            '  "coverage": 0.0-1.0,\n'
            '  "waisen": {\n'
            '    "anforderungen_ohne_features": [],\n'
            '    "features_ohne_tasks": [],\n'
            '    "tasks_ohne_dateien": []\n'
            "  },\n"
            '  "empfehlungen": []\n'
            "}\n"
            "```\n\n"
            f"REGELN:\n{combined_rules}"
        ),
        llm=model,
        verbose=True,
        allow_delegation=False
    )


def get_validation_task_description(
    anforderungen: List[Dict],
    features: List[Dict],
    tasks: List[Dict],
    file_generations: List[Dict]
) -> str:
    """
    Erstellt Task-Beschreibung für Validator-Agent.

    Args:
        anforderungen: Liste der Anforderungen
        features: Liste der Features
        tasks: Liste der Tasks
        file_generations: Liste der generierten Dateien

    Returns:
        Formatierte Task-Beschreibung
    """
    return f"""
Führe eine vollständige Traceability-Prüfung durch:

ANFORDERUNGEN ({len(anforderungen)}):
{_format_items(anforderungen, "id", "titel")}

FEATURES ({len(features)}):
{_format_items(features, "id", "name")}

TASKS ({len(tasks)}):
{_format_items(tasks, "id", "titel")}

GENERIERTE DATEIEN ({len(file_generations)}):
{_format_files(file_generations)}

PRÜFE:
1. Hat jede Anforderung mindestens ein Feature? (anforderungen → features.anforderungen)
2. Hat jedes Feature mindestens einen Task? (features → tasks.feature_id)
3. Hat jeder Task mindestens eine Datei? (tasks → file_generations)

Gib das Ergebnis als JSON zurück.
"""


def _format_items(items: List[Dict], id_key: str, name_key: str) -> str:
    """
    Formatiert Items für Task-Beschreibung.

    Args:
        items: Liste der Items
        id_key: Schlüssel für die ID
        name_key: Schlüssel für den Namen

    Returns:
        Formatierter String
    """
    if not items:
        return "  (keine)"
    lines = []
    for item in items[:20]:  # Max 20 für Übersichtlichkeit
        item_id = item.get(id_key, "?")
        item_name = item.get(name_key, "?")
        lines.append(f"  - {item_id}: {item_name}")
    if len(items) > 20:
        lines.append(f"  ... und {len(items) - 20} weitere")
    return "\n".join(lines)


def _format_files(file_generations: List[Dict]) -> str:
    """
    Formatiert Datei-Liste für Task-Beschreibung.

    Args:
        file_generations: Liste der Datei-Generierungen

    Returns:
        Formatierter String
    """
    if not file_generations:
        return "  (keine)"
    lines = []
    for fg in file_generations[:20]:
        path = fg.get("filepath", "?")
        success = "OK" if fg.get("success") else "FEHLER"
        lines.append(f"  [{success}] {path}")
    if len(file_generations) > 20:
        lines.append(f"  ... und {len(file_generations) - 20} weitere")
    return "\n".join(lines)
