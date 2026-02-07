# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 07.02.2026
Version: 1.0
Beschreibung: Hilfsmodul fuer User Story Operationen.
              Extrahiert aus konzepter_agent.py (Regel 1: Max 500 Zeilen).
              Enthaelt: Parsing, Validierung, Fallback-Generierung, Formatierung.

              AENDERUNG 07.02.2026: Initiale Erstellung (Dart Task zE40HTp29XJn)
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Pflichtfelder fuer eine gueltige User Story
US_REQUIRED_FIELDS = {"id", "feature_id", "titel", "gegeben", "wenn", "dann"}


def parse_user_stories(konzepter_output: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Extrahiert User Stories aus dem Konzepter-Output.

    Args:
        konzepter_output: Geparstes JSON-Dict vom Konzepter-Agenten

    Returns:
        Liste der User Stories (kann leer sein)
    """
    if not konzepter_output or not isinstance(konzepter_output, dict):
        return []

    stories = konzepter_output.get("user_stories", [])
    if not isinstance(stories, list):
        logger.warning("user_stories ist keine Liste, ignoriere")
        return []

    # IDs zuweisen falls fehlend
    stories = assign_user_story_ids(stories)

    return stories


def assign_user_story_ids(user_stories: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Weist fortlaufende US-IDs zu falls fehlend.

    Args:
        user_stories: Liste der User Stories

    Returns:
        Liste mit garantierten IDs (US-001, US-002, ...)
    """
    for i, story in enumerate(user_stories, 1):
        if not story.get("id"):
            story["id"] = f"US-{i:03d}"
    return user_stories


def create_default_user_stories(features: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Fallback: Generiert 1 Standard-User-Story pro Feature.
    Wird verwendet wenn der Konzepter-Agent keine User Stories generiert.

    Args:
        features: Liste der Features aus dem Konzepter-Output

    Returns:
        Liste von Standard-User-Stories
    """
    stories = []
    for i, feat in enumerate(features, 1):
        feat_id = feat.get("id", f"FEAT-{i:03d}")
        titel = feat.get("titel", "Unbenanntes Feature")
        beschreibung = feat.get("beschreibung", titel)

        stories.append({
            "id": f"US-{i:03d}",
            "feature_id": feat_id,
            "titel": f"Benutzer nutzt {titel}",
            "gegeben": f"Das Feature '{titel}' ist implementiert",
            "wenn": f"Der Benutzer die Funktion '{titel}' aufruft",
            "dann": f"Wird die erwartete Funktionalitaet ausgefuehrt: {beschreibung[:100]}",
            "akzeptanzkriterien": [
                f"{titel} funktioniert wie beschrieben",
                "Keine Fehlermeldungen bei normaler Nutzung"
            ],
            "prioritaet": feat.get("prioritaet", "mittel"),
            "source": "default_fallback"
        })

    logger.info(f"{len(stories)} Standard-User-Stories generiert (Fallback)")
    return stories


def validate_user_stories(
    features: List[Dict[str, Any]],
    user_stories: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Validiert User Stories gegen Features.

    Prueft:
    - Pflichtfelder vorhanden (id, feature_id, titel, gegeben, wenn, dann)
    - Jede US referenziert ein existierendes Feature
    - Kein Feature ohne User Story (Warning)
    - Keine doppelten US-IDs

    Args:
        features: Liste der Features
        user_stories: Liste der User Stories

    Returns:
        Validierungsergebnis mit valid, coverage, warnings, errors
    """
    errors = []
    warnings = []

    feat_ids = {f.get("id") for f in features if f.get("id")}
    us_ids = set()
    covered_feats = set()

    for story in user_stories:
        us_id = story.get("id", "US-???")

        # Pflichtfelder pruefen
        missing = US_REQUIRED_FIELDS - set(story.keys())
        if missing:
            errors.append(f"{us_id}: Fehlende Pflichtfelder: {', '.join(sorted(missing))}")

        # Doppelte IDs pruefen
        if us_id in us_ids:
            errors.append(f"{us_id}: Doppelte User-Story-ID")
        us_ids.add(us_id)

        # Feature-Referenz pruefen
        feat_ref = story.get("feature_id", "")
        if feat_ref and feat_ref in feat_ids:
            covered_feats.add(feat_ref)
        elif feat_ref:
            warnings.append(f"{us_id}: Referenziert unbekanntes Feature '{feat_ref}'")

        # Akzeptanzkriterien pruefen
        ak = story.get("akzeptanzkriterien", [])
        if not ak or not isinstance(ak, list) or len(ak) == 0:
            warnings.append(f"{us_id}: Keine Akzeptanzkriterien definiert")

        # GEGEBEN/WENN/DANN Inhalte pruefen (nicht nur Key vorhanden)
        for feld in ("gegeben", "wenn", "dann"):
            wert = story.get(feld, "")
            if not wert or not isinstance(wert, str) or len(wert.strip()) < 5:
                warnings.append(f"{us_id}: '{feld}' ist zu kurz oder leer")

    # Features ohne User Stories
    uncovered_feats = feat_ids - covered_feats
    if uncovered_feats:
        for feat_id in sorted(uncovered_feats):
            warnings.append(f"Feature {feat_id} hat keine User Story")

    coverage = len(covered_feats) / len(feat_ids) if feat_ids else 0.0

    return {
        "valid": len(errors) == 0,
        "coverage": coverage,
        "total_user_stories": len(user_stories),
        "total_features": len(feat_ids),
        "covered_features": list(sorted(covered_feats)),
        "uncovered_features": list(sorted(uncovered_feats)),
        "errors": errors,
        "warnings": warnings
    }


def build_user_story_traceability(user_stories: List[Dict[str, Any]]) -> Dict[str, List[str]]:
    """
    Baut die FEAT-ID → [US-IDs] Traceability-Matrix.

    Args:
        user_stories: Liste der User Stories

    Returns:
        Dict mit Feature-IDs als Keys und US-ID-Listen als Values
    """
    traceability = {}
    for story in user_stories:
        feat_id = story.get("feature_id", "")
        us_id = story.get("id", "")
        if feat_id and us_id:
            if feat_id not in traceability:
                traceability[feat_id] = []
            if us_id not in traceability[feat_id]:
                traceability[feat_id].append(us_id)
    return traceability


def format_user_story_text(story: Dict[str, Any]) -> str:
    """
    Formatiert eine User Story als lesbaren GEGEBEN-WENN-DANN Text.

    Args:
        story: User Story Dict

    Returns:
        Formatierter Text
    """
    us_id = story.get("id", "US-???")
    titel = story.get("titel", "Unbenannt")
    gegeben = story.get("gegeben", "???")
    wenn = story.get("wenn", "???")
    dann = story.get("dann", "???")
    feat_id = story.get("feature_id", "???")

    text = f"[{us_id}] {titel} (Feature: {feat_id})\n"
    text += f"  GEGEBEN: {gegeben}\n"
    text += f"  WENN:    {wenn}\n"
    text += f"  DANN:    {dann}"

    ak = story.get("akzeptanzkriterien", [])
    if ak:
        text += "\n  AKZEPTANZKRITERIEN:"
        for kriterium in ak:
            text += f"\n    - {kriterium}"

    return text
