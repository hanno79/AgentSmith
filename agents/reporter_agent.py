# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 01.02.2026
Version: 1.0
Beschreibung: Reporter-Agent für Projektfortschritts-Berichte.
              Erstellt umfassende Projekt-Reports mit Metriken, Problemen und Empfehlungen.
"""

from typing import Dict, List, Any, Optional
from crewai import Agent
from agents.agent_utils import get_model_from_config, combine_project_rules


def create_reporter(
    config: Dict[str, Any],
    project_rules: Dict[str, List[str]],
    router=None
) -> Agent:
    """
    Erstellt Reporter-Agent für Projektberichte.

    Args:
        config: Konfiguration mit Modell-Einstellungen
        project_rules: Projektspezifische Regeln
        router: Optional ModelRouter für dynamische Modellauswahl

    Returns:
        CrewAI Agent für Reporting
    """
    # Modell-Auswahl mit Fallback auf Documentation Manager
    if router:
        model = router.get_model("reporter")
    else:
        model = get_model_from_config(
            config, "reporter",
            fallback_role="documentation_manager"
        )

    combined_rules = combine_project_rules(project_rules, "reporter")

    return Agent(
        role="Project Reporter",
        goal=(
            "Erstelle umfassende, gut strukturierte Projektberichte. "
            "Fasse Fortschritt zusammen, identifiziere Probleme, "
            "und gib klare Empfehlungen für nächste Schritte."
        ),
        backstory=(
            "Du bist ein erfahrener Projektmanager und technischer Redakteur.\n\n"
            "DEINE BERICHTE ENTHALTEN:\n"
            "1. ZUSAMMENFASSUNG - Kurzer Überblick (3-5 Sätze)\n"
            "2. FORTSCHRITT - Was wurde erreicht? (mit Metriken)\n"
            "3. PROBLEME - Was hat nicht funktioniert? (mit Root Cause)\n"
            "4. NÄCHSTE SCHRITTE - Priorisierte TODO-Liste\n"
            "5. EMPFEHLUNGEN - Verbesserungsvorschläge\n\n"
            "FORMAT:\n"
            "- Markdown mit klarer Struktur\n"
            "- Tabellen für Metriken\n"
            "- Bullet Points für Listen\n"
            "- Keine unnötigen Füllwörter\n\n"
            f"REGELN:\n{combined_rules}"
        ),
        llm=model,
        verbose=True,
        allow_delegation=False
    )


def get_report_task_description(report_data: Dict[str, Any]) -> str:
    """
    Erstellt Task-Beschreibung für Reporter-Agent.

    Args:
        report_data: Gesammelte Projektdaten

    Returns:
        Formatierte Task-Beschreibung
    """
    coverage = report_data.get('coverage', 0)
    coverage_str = f"{coverage:.1%}" if isinstance(coverage, float) else str(coverage)

    return f"""
Erstelle einen Projektbericht basierend auf folgenden Daten:

PROJEKT: {report_data.get('project_name', 'Unbekannt')}
ZEITRAUM: {report_data.get('start_date', '?')} - {report_data.get('end_date', '?')}

METRIKEN:
- Anforderungen: {report_data.get('anforderungen_count', 0)}
- Features: {report_data.get('features_count', 0)}
- Tasks: {report_data.get('tasks_count', 0)}
- Dateien generiert: {report_data.get('files_count', 0)}
- Tests bestanden: {report_data.get('tests_passed', 0)}/{report_data.get('tests_total', 0)}
- Coverage: {coverage_str}

ITERATIONEN: {report_data.get('iterations_count', 0)}

FEHLER:
{_format_errors(report_data.get('errors', []))}

AGENT-NUTZUNG:
{_format_agent_usage(report_data.get('agent_usage', {}))}

KOSTEN:
- Gesamt: ${report_data.get('total_cost', 0):.4f}
- Pro Iteration: ${report_data.get('cost_per_iteration', 0):.4f}

MEILENSTEINE:
{_format_milestones(report_data.get('milestones', []))}

Erstelle den Bericht im Markdown-Format mit den Abschnitten:
1. Zusammenfassung
2. Fortschritt
3. Probleme
4. Nächste Schritte
5. Empfehlungen
"""


def _format_errors(errors: List[Dict]) -> str:
    """
    Formatiert Fehler für Report.

    Args:
        errors: Liste der Fehler

    Returns:
        Formatierter String
    """
    if not errors:
        return "  Keine Fehler aufgetreten."
    lines = []
    for err in errors[:10]:
        err_type = err.get('type', '?')
        err_msg = str(err.get('message', '?'))[:100]
        agent = err.get('agent', '')
        agent_str = f" ({agent})" if agent else ""
        lines.append(f"  - {err_type}{agent_str}: {err_msg}")
    if len(errors) > 10:
        lines.append(f"  ... und {len(errors) - 10} weitere")
    return "\n".join(lines)


def _format_agent_usage(usage: Dict[str, Any]) -> str:
    """
    Formatiert Agent-Nutzung für Report.

    Args:
        usage: Dict mit Agent-Nutzungsdaten

    Returns:
        Formatierter String
    """
    if not usage:
        return "  Keine Daten verfügbar."
    lines = []
    for agent, data in usage.items():
        calls = data.get('calls', 0)
        tokens = data.get('tokens', 0)
        cost = data.get('cost', 0)
        lines.append(f"  - {agent}: {calls} Aufrufe, {tokens:,} Tokens, ${cost:.4f}")
    return "\n".join(lines)


def _format_milestones(milestones: List[Dict]) -> str:
    """
    Formatiert Meilensteine für Report.

    Args:
        milestones: Liste der Meilensteine

    Returns:
        Formatierter String
    """
    if not milestones:
        return "  Keine Meilensteine definiert."
    lines = []
    for ms in milestones:
        name = ms.get('name', '?')
        status = ms.get('status', '?')
        status_icon = "OK" if status == "completed" else "OFFEN"
        lines.append(f"  [{status_icon}] {name}")
    return "\n".join(lines)
