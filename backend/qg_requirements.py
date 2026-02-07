# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 01.02.2026
Version: 1.0
Beschreibung: Quality Gate Anforderungs-Extraktion.
              Extrahiert aus quality_gate.py (Regel 1: Max 500 Zeilen)
"""

from typing import Dict, Any

from backend.qg_constants import (
    DB_KEYWORDS,
    LANG_KEYWORDS,
    FRAMEWORK_KEYWORDS,
    UI_TYPE_KEYWORDS
)


def extract_requirements(user_goal: str) -> Dict[str, Any]:
    """
    Extrahiert prüfbare Anforderungen aus user_goal.

    NUR Benutzer-Vorgaben zählen als verbindlich!
    Researcher-Vorschläge werden hier NICHT berücksichtigt.

    Args:
        user_goal: Das ursprüngliche Benutzer-Ziel

    Returns:
        Dictionary mit erkannten Anforderungen
    """
    goal_lower = user_goal.lower()
    requirements: Dict[str, Any] = {}

    # Datenbank-Vorgaben
    for keyword, db_type in DB_KEYWORDS.items():
        if keyword in goal_lower:
            requirements["database"] = db_type
            break

    # Sprach-Vorgaben
    for keyword, lang in LANG_KEYWORDS.items():
        if keyword in goal_lower:
            requirements["language"] = lang
            break

    # Framework-Vorgaben
    for keyword, fw in FRAMEWORK_KEYWORDS.items():
        if keyword in goal_lower:
            requirements["framework"] = fw
            break

    # UI-Typ - Intelligentere Erkennung
    # Problem: "gui" ist zu generisch und kann webapp/desktop bedeuten
    # Loesung: Explizite Keywords (webapp, desktop) haben Prioritaet
    ui_matches: Dict[str, list] = {}
    for ui_type, keywords in UI_TYPE_KEYWORDS.items():
        matching_keywords = [kw for kw in keywords if kw in goal_lower]
        if matching_keywords:
            ui_matches[ui_type] = matching_keywords

    if ui_matches:
        # Priorisiere explizite Matches ueber generische wie "gui"
        # webapp/website explizit genannt = webapp
        webapp_explicit = ["webapp", "website", "webseite", "web app", "browser"]
        if "webapp" in ui_matches and any(kw in webapp_explicit for kw in ui_matches["webapp"]):
            requirements["ui_type"] = "webapp"
        # desktop/fenster/window explizit genannt = desktop
        elif "desktop" in ui_matches and any(kw in ["desktop", "fenster", "window"] for kw in ui_matches["desktop"]):
            # Aber NICHT wenn webapp auch explizit genannt wurde
            if "webapp" not in ui_matches:
                requirements["ui_type"] = "desktop"
            else:
                requirements["ui_type"] = "webapp"  # webapp hat Vorrang
        # api explizit genannt
        elif "api" in ui_matches:
            requirements["ui_type"] = "api"
        # cli explizit genannt
        elif "cli" in ui_matches:
            requirements["ui_type"] = "cli"
        # Fallback: Erstes Match (alte Logik)
        else:
            requirements["ui_type"] = list(ui_matches.keys())[0]

    return requirements


def get_requirements_summary(requirements: Dict[str, Any]) -> str:
    """
    Gibt eine lesbare Zusammenfassung der erkannten Anforderungen zurück.

    Args:
        requirements: Dictionary mit erkannten Anforderungen

    Returns:
        Formatierter String mit Anforderungen
    """
    if not requirements:
        return "Keine spezifischen Anforderungen erkannt."

    parts = []
    if requirements.get("database"):
        parts.append(f"Datenbank: {requirements['database']}")
    if requirements.get("language"):
        parts.append(f"Sprache: {requirements['language']}")
    if requirements.get("framework"):
        parts.append(f"Framework: {requirements['framework']}")
    if requirements.get("ui_type"):
        parts.append(f"UI-Typ: {requirements['ui_type']}")

    return ", ".join(parts) if parts else "Keine spezifischen Anforderungen erkannt."
