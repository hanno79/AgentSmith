# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 01.02.2026
Version: 1.0
Beschreibung: Discovery Briefing-Funktionen.
              Extrahiert aus discovery.py (Regel 1: Max 500 Zeilen)
              Enthält: save/get Briefing, Markdown-Generierung, Hilfs-Funktionen
"""

import os
import re
import json
import logging
from typing import List
from fastapi import APIRouter

from ..app_state import manager
from ..session_utils import get_session_manager_instance
from ..api_logging import log_event

router = APIRouter()
logger = logging.getLogger(__name__)

# Memory-Pfad für Quellen-System
MEMORY_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "memory", "agent_memory.json")


# =========================================================================
# Hilfs-Funktionen
# =========================================================================

def load_memory_safe() -> dict:
    """Lädt Memory sicher, gibt leeres Dict bei Fehler zurück."""
    try:
        if os.path.exists(MEMORY_PATH):
            with open(MEMORY_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        log_event("Discovery", "MemoryLoadError", str(e))
    return {"history": [], "lessons": []}


def find_relevant_lessons(lessons: List[dict], keywords: List[str]) -> List[dict]:
    """Findet Lessons die zu den Keywords passen. Tags werden kleingeschrieben verglichen."""
    relevant = []
    for lesson in lessons:
        raw_tags = lesson.get("tags", [])
        tags_lower = [str(t).lower() for t in raw_tags] if isinstance(raw_tags, (list, tuple)) else []
        pattern = lesson.get("pattern", "").lower()
        action = lesson.get("action", "").lower()

        for keyword in keywords:
            kw = keyword.lower()
            if (kw in tags_lower or kw in pattern or kw in action):
                relevant.append(lesson)
                break

    # Sortiere nach Häufigkeit (count) absteigend
    relevant.sort(key=lambda x: x.get("count", 0), reverse=True)
    return relevant[:5]  # Maximal 5 relevante Lessons


def sanitize_project_name(raw_name: str, max_length: int = 80) -> str:
    """Sanitiziert Projektname für sichere Dateinamen."""
    if raw_name is None:
        raw_name = ""
    if not isinstance(raw_name, str):
        raw_name = str(raw_name)

    cleaned = raw_name.strip()

    for sep in filter(None, [os.path.sep, os.path.altsep]):
        cleaned = cleaned.replace(sep, "")

    while cleaned.startswith("."):
        cleaned = cleaned[1:]
    cleaned = cleaned.replace("..", "")

    cleaned = re.sub(r"[^A-Za-z0-9_-]", "", cleaned)
    cleaned = cleaned[:max_length]

    return cleaned or "unnamed_project"


def generate_briefing_markdown(briefing: dict) -> str:
    """Generiert Markdown aus dem Briefing-Objekt."""
    tech = briefing.get("techRequirements", {})
    agents = briefing.get("agents", [])
    answers = briefing.get("answers", [])
    open_points = briefing.get("openPoints", [])

    md = f"""# PROJEKTBRIEFING

**Projekt:** {briefing.get("projectName", "Unbenannt")}
**Datum:** {briefing.get("date", "Unbekannt")}
**Teilnehmende Agenten:** {", ".join(agents)}

---

## PROJEKTZIEL

{briefing.get("goal", "Kein Ziel definiert")}

---

## TECHNISCHE ANFORDERUNGEN

- **Sprache:** {tech.get("language", "auto")}
- **Deployment:** {tech.get("deployment", "local")}

---

## ENTSCHEIDUNGEN AUS DISCOVERY

"""

    for answer in answers:
        if not answer.get("skipped", False):
            agent = answer.get("agent", "Unbekannt")
            question = answer.get("questionText", "")
            values = answer.get("selectedValues", [])
            custom = answer.get("customText", "")
            answer_text = ', '.join(values) if values else custom
            if answer_text:
                if question:
                    md += f"### {agent}\n**Frage:** {question}\n**Antwort:** {answer_text}\n\n"
                else:
                    md += f"- **{agent}:** {answer_text}\n"

    if open_points:
        md += "\n---\n\n## OFFENE PUNKTE\n\n"
        for point in open_points:
            md += f"- {point}\n"

    md += "\n---\n\n*Generiert von AgentSmith Discovery Session*\n"
    return md


# =========================================================================
# API Endpunkte
# =========================================================================

@router.post("/discovery/save-briefing")
async def save_discovery_briefing(briefing: dict):
    """
    Speichert das Discovery-Briefing fuer die aktuelle Session.
    Das Briefing wird den Agenten als Kontext bereitgestellt.

    Args:
        briefing: Das Briefing-Objekt aus der Discovery Session

    Returns:
        Status und Pfad zur gespeicherten Datei
    """
    session_mgr = get_session_manager_instance()
    project_name = sanitize_project_name(briefing.get("projectName", "unnamed_project"))

    if session_mgr:
        session_mgr.set_discovery_briefing(briefing)

    manager.set_discovery_briefing(briefing)

    briefing_path = None
    try:
        projects_dir = os.path.join(os.path.dirname(__file__), "..", "..", "projects")
        os.makedirs(projects_dir, exist_ok=True)
        briefing_path = os.path.join(projects_dir, f"{project_name}_briefing.md")
        logger.debug("save_discovery_briefing: Speichere Briefing nach %s", briefing_path)

        markdown = generate_briefing_markdown(briefing)
        with open(briefing_path, "w", encoding="utf-8") as f:
            f.write(markdown)
        logger.info("Briefing erfolgreich gespeichert: %s", briefing_path)
    except Exception as e:
        logger.warning(
            "[save_discovery_briefing] Briefing-Datei konnte nicht gespeichert werden (briefing_path=%s): %s",
            briefing_path, e, exc_info=True,
        )

    return {
        "status": "ok",
        "project_name": project_name,
        "path": briefing_path
    }


@router.get("/discovery/briefing")
def get_discovery_briefing():
    """
    Gibt das aktuelle Discovery-Briefing zurueck.

    Returns:
        Das gespeicherte Briefing oder None
    """
    session_mgr = get_session_manager_instance()
    if session_mgr:
        return {"briefing": session_mgr.get_discovery_briefing()}
    return {"briefing": None}
