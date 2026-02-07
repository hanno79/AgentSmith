# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 31.01.2026
Version: 1.0
Beschreibung: Discovery Briefing Modul für Orchestration Manager.
              Extrahiert aus orchestration_manager.py (Regel 1: Max 500 Zeilen)
# ÄNDERUNG [29.01.2026]: Discovery Briefing Integration für Agent-Kontext
"""

import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


def format_briefing_context(discovery_briefing: Optional[Dict[str, Any]]) -> str:
    """
    Generiert einen Kontext-String aus dem Briefing fuer Agent-System-Prompts.

    Args:
        discovery_briefing: Das Briefing-Objekt aus der Discovery Session

    Returns:
        Formatierter Briefing-Kontext oder leerer String
    """
    try:
        if not discovery_briefing:
            return ""
        return _format_briefing_context_impl(discovery_briefing)
    except Exception as e:
        logger.critical(
            "[format_briefing_context] Unerwarteter Fehler: %s",
            e, exc_info=True,
        )
        return ""


def _format_briefing_context_impl(discovery_briefing: Dict[str, Any]) -> str:
    """Interne Implementierung von format_briefing_context."""
    b = discovery_briefing
    if not isinstance(b, dict):
        return ""

    tech = b.get("techRequirements") if isinstance(b.get("techRequirements"), dict) else {}
    agents = b.get("agents") if isinstance(b.get("agents"), list) else []
    answers = b.get("answers") if isinstance(b.get("answers"), list) else []

    context = f"""
## PROJEKTBRIEFING (aus Discovery Session)

**Projektziel:** {b.get('goal', 'Nicht definiert')}

**Technische Anforderungen:**
- Programmiersprache: {tech.get('language', 'auto')}
- Deployment: {tech.get('deployment', 'local')}

**Beteiligte Agenten:** {', '.join(agents) if agents and all(isinstance(a, str) for a in agents) else 'Nicht definiert'}

**Wichtige Entscheidungen aus Discovery:**
"""

    for answer in answers:
        if not isinstance(answer, dict):
            continue
        if not answer.get('skipped', False):
            agent = answer.get('agent', 'Unbekannt')
            agent_text = str(agent) if agent is not None else "Unbekannt"
            values = answer.get('selectedValues', [])
            if not isinstance(values, list):
                values = []
            custom = answer.get('customText', '')
            custom_text = str(custom) if custom is not None else ""
            values_text = ', '.join([str(v) for v in values]) if values else ""
            if values_text or custom_text:
                context += f"- {agent_text}: {values_text if values_text else custom_text}\n"

    open_points = b.get('openPoints') if isinstance(b.get('openPoints'), list) else []
    if open_points:
        context += "\n**Offene Punkte (bitte beruecksichtigen):**\n"
        for point in open_points:
            context += f"- {point}\n"

    return context


def extract_project_name_from_briefing(discovery_briefing: Optional[Dict[str, Any]]) -> str:
    """
    Extrahiert den Projektnamen aus dem Discovery Briefing.

    Args:
        discovery_briefing: Das Briefing-Objekt

    Returns:
        Projektname oder 'unbenannt'
    """
    try:
        if not discovery_briefing or not isinstance(discovery_briefing, dict):
            return "unbenannt"
        return discovery_briefing.get("projectName", "unbenannt")
    except Exception as e:
        logger.critical("[extract_project_name_from_briefing] Fehler: %s", e, exc_info=True)
        return "unbenannt"


def extract_project_goal_from_briefing(discovery_briefing: Optional[Dict[str, Any]]) -> str:
    """
    Extrahiert das Projektziel aus dem Discovery Briefing.

    Args:
        discovery_briefing: Das Briefing-Objekt

    Returns:
        Projektziel oder leerer String
    """
    try:
        if not discovery_briefing or not isinstance(discovery_briefing, dict):
            return ""
        return discovery_briefing.get("goal", "") or discovery_briefing.get("projectGoal", "")
    except Exception as e:
        logger.critical("[extract_project_goal_from_briefing] Fehler: %s", e, exc_info=True)
        return ""
