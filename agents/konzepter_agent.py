# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 31.01.2026
Version: 1.0
Beschreibung: Konzepter Agent - Extrahiert Features aus dem Anforderungskatalog.
              Teil des Dart AI Feature-Ableitung Konzepts.

              Workflow: Anforderungskatalog (Analyst) -> Konzepter -> Feature-Katalog mit Traceability
"""

import json
import re
from typing import Any, Dict, List, Optional
from crewai import Agent, Task

from agents.agent_utils import get_model_from_config, combine_project_rules


def create_konzepter(config: Dict[str, Any], project_rules: Dict[str, List[str]], router=None) -> Agent:
    """
    Erstellt den Konzepter Agenten.
    Extrahiert Features aus dem Anforderungskatalog und erstellt Traceability-Links.

    Args:
        config: Anwendungskonfiguration mit mode und models
        project_rules: Dictionary mit globalen und rollenspezifischen Regeln
        router: Optional ModelRouter fuer Fallback bei Rate Limits

    Returns:
        Konfigurierte CrewAI Agent-Instanz
    """
    if router:
        # Konzepter nutzt das Meta-Orchestrator-Modell (konzeptionelle Aufgabe)
        model = router.get_model("meta_orchestrator")
    else:
        model = get_model_from_config(config, "meta_orchestrator")

    combined_rules = combine_project_rules(project_rules, "konzepter")

    return Agent(
        role="Feature-Konzepter",
        goal=(
            "Analysiere den Anforderungskatalog und extrahiere konkrete, "
            "implementierbare Features mit vollstaendiger Traceability."
        ),
        backstory=(
            "Du bist ein erfahrener Solution Architect mit Expertise in Feature-Design.\n"
            "Du uebersetzt abstrakte Anforderungen in konkrete, technische Features.\n\n"
            "DEINE AUFGABEN:\n"
            "1. Analysiere jede Anforderung und leite passende Features ab\n"
            "2. Eine Anforderung kann 1-N Features ergeben\n"
            "3. Jedes Feature muss mindestens einer Anforderung zugeordnet sein\n"
            "4. Features sollten unabhaengig implementierbar sein\n"
            "5. Schaetze die Anzahl der benoetigten Dateien pro Feature\n\n"
            "AUSGABE-FORMAT (strikt JSON):\n"
            "```json\n"
            "{\n"
            '  "features": [\n'
            "    {\n"
            '      "id": "FEAT-001",\n'
            '      "titel": "Login-Formular",\n'
            '      "beschreibung": "Benutzer-Authentifizierung mit Email/Passwort",\n'
            '      "anforderungen": ["REQ-001"],\n'
            '      "technologie": "Python/Flask",\n'
            '      "geschaetzte_dateien": 2,\n'
            '      "prioritaet": "hoch",\n'
            '      "abhaengigkeiten": []\n'
            "    }\n"
            "  ],\n"
            '  "traceability": {\n'
            '    "REQ-001": ["FEAT-001", "FEAT-002"],\n'
            '    "REQ-002": ["FEAT-003"]\n'
            "  },\n"
            '  "zusammenfassung": "Kurze Zusammenfassung der Feature-Landschaft"\n'
            "}\n"
            "```\n\n"
            "REGELN:\n"
            "- Jedes Feature braucht eine eindeutige ID (FEAT-001, FEAT-002, ...)\n"
            "- Die Traceability-Matrix muss vollstaendig sein\n"
            "- Features muessen klein genug sein (max. 3 Dateien pro Feature)\n"
            "- Abhaengigkeiten zwischen Features explizit angeben\n"
            "- Prioritaeten: 'hoch' = Kernfunktion, 'mittel' = wichtig, 'niedrig' = optional\n"
            f"\n{combined_rules}"
        ),
        llm=model,
        verbose=True
    )


def create_feature_extraction_task(agent: Agent, anforderungen: Dict[str, Any], blueprint: Dict[str, Any] = None) -> Task:
    """
    Erstellt einen Feature-Extraktions-Task fuer den Konzepter-Agenten.

    Args:
        agent: Der Konzepter-Agent
        anforderungen: Der Anforderungskatalog vom Analyst
        blueprint: Optional TechStack-Blueprint fuer technischen Kontext

    Returns:
        CrewAI Task-Instanz
    """
    # Anforderungen formatieren
    anforderungen_text = _format_anforderungen(anforderungen)

    # Technischen Kontext hinzufuegen falls vorhanden
    tech_context = ""
    if blueprint:
        tech_context = f"""
TECHNISCHER KONTEXT:
- Projekt-Typ: {blueprint.get('project_type', 'unknown')}
- Sprache: {blueprint.get('language', 'unknown')}
- App-Typ: {blueprint.get('app_type', 'webapp')}
- Frameworks: {', '.join(blueprint.get('frameworks', []))}
"""

    description = f"""Analysiere den folgenden Anforderungskatalog und extrahiere konkrete Features.

ANFORDERUNGSKATALOG:
{anforderungen_text}
{tech_context}

DEINE AUFGABE:
1. Leite fuer jede Anforderung passende Features ab
2. Erstelle die Traceability-Matrix (REQ -> FEAT)
3. Definiere Abhaengigkeiten zwischen Features
4. Schaetze die Anzahl der Dateien pro Feature

WICHTIG:
- Jedes Feature sollte klein und fokussiert sein (max. 3 Dateien)
- Features muessen unabhaengig testbar sein
- Die Traceability muss vollstaendig sein (jede REQ mindestens ein FEAT)

Gib NUR den JSON-Block aus, keine zusaetzlichen Erklaerungen.
"""

    return Task(
        description=description,
        expected_output="JSON mit Feature-Katalog und Traceability-Matrix",
        agent=agent
    )


def _format_anforderungen(anforderungen: Dict[str, Any]) -> str:
    """
    Formatiert den Anforderungskatalog in lesbaren Text.

    Args:
        anforderungen: Der Anforderungskatalog Dict

    Returns:
        Formatierter Text
    """
    text = f"""
ZUSAMMENFASSUNG: {anforderungen.get('zusammenfassung', 'Keine Zusammenfassung')}

KATEGORIEN: {', '.join(anforderungen.get('kategorien', []))}

ANFORDERUNGEN:
"""

    for req in anforderungen.get('anforderungen', []):
        text += f"""
[{req.get('id', 'REQ-???')}] {req.get('titel', 'Unbenannt')}
  Kategorie: {req.get('kategorie', 'Unbekannt')}
  Prioritaet: {req.get('prioritaet', 'mittel')}
  Beschreibung: {req.get('beschreibung', '')}
  Akzeptanzkriterien: {', '.join(req.get('akzeptanzkriterien', []))}
  Quelle: {req.get('quelle', 'Unbekannt')}
"""

    return text


def parse_konzepter_output(output: str) -> Optional[Dict[str, Any]]:
    """
    Parst den Konzepter-Output und extrahiert den Feature-Katalog.

    Args:
        output: Raw-Output des Konzepter-Agenten

    Returns:
        Dict mit features-Liste und traceability oder None bei Fehler
    """
    if not output:
        return None

    # Versuche JSON-Block zu extrahieren
    json_patterns = [
        r'```json\s*(.*?)\s*```',
        r'```\s*(.*?)\s*```',
        r'\{[\s\S]*"features"[\s\S]*\}'
    ]

    for pattern in json_patterns:
        matches = re.findall(pattern, output, re.DOTALL)
        if matches:
            json_str = matches[0] if isinstance(matches[0], str) else matches[0]
            try:
                result = json.loads(json_str)
                if "features" in result and isinstance(result["features"], list):
                    # Validiere Traceability
                    if "traceability" not in result:
                        result["traceability"] = _build_traceability(result["features"])
                    return result
            except json.JSONDecodeError:
                continue

    # Fallback: Versuche gesamten Output als JSON
    try:
        result = json.loads(output.strip())
        if "features" in result:
            if "traceability" not in result:
                result["traceability"] = _build_traceability(result["features"])
            return result
    except json.JSONDecodeError:
        pass

    return None


def _build_traceability(features: List[Dict[str, Any]]) -> Dict[str, List[str]]:
    """
    Baut die Traceability-Matrix aus den Features auf.

    Args:
        features: Liste der Features

    Returns:
        Dict mit REQ-IDs als Keys und FEAT-ID-Listen als Values
    """
    traceability = {}
    for feat in features:
        feat_id = feat.get("id", "")
        for req_id in feat.get("anforderungen", []):
            if req_id not in traceability:
                traceability[req_id] = []
            if feat_id not in traceability[req_id]:
                traceability[req_id].append(feat_id)
    return traceability


def create_default_features(anforderungen: Dict[str, Any]) -> Dict[str, Any]:
    """
    Erstellt Standard-Features wenn der Konzepter-Agent fehlschlaegt.

    Args:
        anforderungen: Der Anforderungskatalog

    Returns:
        Standard-Feature-Katalog
    """
    features = []
    traceability = {}

    for i, req in enumerate(anforderungen.get("anforderungen", []), 1):
        req_id = req.get("id", f"REQ-{i:03d}")
        feat_id = f"FEAT-{i:03d}"

        features.append({
            "id": feat_id,
            "titel": f"Feature fuer {req.get('titel', 'Anforderung')}",
            "beschreibung": req.get("beschreibung", ""),
            "anforderungen": [req_id],
            "technologie": "Python",
            "geschaetzte_dateien": 1,
            "prioritaet": req.get("prioritaet", "mittel"),
            "abhaengigkeiten": []
        })

        traceability[req_id] = [feat_id]

    return {
        "features": features,
        "traceability": traceability,
        "zusammenfassung": "Automatisch generierte Features (1:1 Mapping)",
        "source": "default_fallback"
    }


def validate_traceability(anforderungen: Dict[str, Any], features: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validiert die Traceability zwischen Anforderungen und Features.

    Args:
        anforderungen: Der Anforderungskatalog
        features: Der Feature-Katalog

    Returns:
        Validierungsergebnis mit coverage und gaps
    """
    req_ids = {req.get("id") for req in anforderungen.get("anforderungen", [])}
    feat_ids = {feat.get("id") for feat in features.get("features", [])}

    traceability = features.get("traceability", {})

    # Finde Anforderungen ohne Features
    covered_reqs = set(traceability.keys())
    uncovered_reqs = req_ids - covered_reqs

    # Finde Features ohne Anforderungs-Zuordnung
    mapped_feats = set()
    for feat_list in traceability.values():
        mapped_feats.update(feat_list)
    orphan_feats = feat_ids - mapped_feats

    coverage = len(covered_reqs) / len(req_ids) if req_ids else 0.0

    return {
        "valid": len(uncovered_reqs) == 0 and len(orphan_feats) == 0,
        "coverage": coverage,
        "covered_requirements": list(covered_reqs),
        "uncovered_requirements": list(uncovered_reqs),
        "orphan_features": list(orphan_feats),
        "total_requirements": len(req_ids),
        "total_features": len(feat_ids)
    }
