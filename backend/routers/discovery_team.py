# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 01.02.2026
Version: 1.0
Beschreibung: Discovery Team-Empfehlung und erweiterte Optionen.
              Extrahiert aus discovery.py (Regel 1: Max 500 Zeilen)
              Enthält: suggest_team, get_enhanced_options
"""

import os
import re
import json
import logging
import aiohttp
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..api_logging import log_event
from .discovery_briefing import load_memory_safe, find_relevant_lessons

router = APIRouter()
logger = logging.getLogger(__name__)


# =========================================================================
# Pydantic Models
# =========================================================================

class SuggestTeamRequest(BaseModel):
    """Request für LLM-basierte Team-Empfehlung."""
    vision: str


class EnhancedOptionsRequest(BaseModel):
    """Request für erweiterte Optionen aus verschiedenen Quellen."""
    question_id: str
    question_text: str
    agent: str
    vision: str = ""


# =========================================================================
# API Endpunkte
# =========================================================================

@router.post("/discovery/suggest-team")
async def suggest_team(request: SuggestTeamRequest):
    """
    LLM analysiert die Vision und empfiehlt die passenden Agenten.

    Ersetzt die bisherige Regex-basierte Auswahl durch echte LLM-Analyse.
    Für eine Todo-Liste App wird z.B. kein Data Researcher empfohlen.
    """
    vision = request.vision

    if not vision or not vision.strip():
        raise HTTPException(status_code=400, detail="Vision/Projektbeschreibung fehlt")

    prompt = f'''Analysiere diese Projektbeschreibung und entscheide,
welche Agenten wirklich benötigt werden:

PROJEKT: "{vision}"

VERFÜGBARE AGENTEN:
- Analyst: Business-Anforderungsanalyse (nur bei komplexen Geschäftsprozessen)
- Coder: Code-Implementierung (IMMER nötig bei Software-Projekten)
- Designer: UI/UX Design (nur wenn visuelle Oberfläche/GUI nötig)
- DB-Designer: Datenbank-Schema (nur bei Datenpersistenz in DB)
- Tester: Qualitätsprüfung (IMMER empfohlen)
- Data Researcher: Datenquellen recherchieren (NUR bei EXTERNEN Daten/APIs)
- TechStack: Technologie-Beratung (nur bei unklarer Tech-Wahl)
- Planner: Projektplanung (nur bei komplexen Projekten)
- Security: Sicherheitsprüfung (bei sensiblen Daten/Login)

WICHTIGE REGELN:
- Wähle NUR die wirklich notwendigen Agenten
- Für einfache Apps: Coder + Designer + Tester reicht oft
- Data Researcher NUR wenn EXTERNE Datenquellen recherchiert werden müssen
  (NICHT bei lokalen Datenbanken wie SQLite!)
- Analyst nur bei komplexen Geschäftsanforderungen
- DB-Designer wenn Datenbank-Schema geplant werden muss

Antworte NUR mit validem JSON:
{{
  "recommended_agents": ["Coder", "Designer", ...],
  "reasoning": {{
    "Coder": "Kurze Begründung warum dieser Agent nötig ist",
    "Designer": "Kurze Begründung..."
  }},
  "not_needed": {{
    "Data Researcher": "Kurze Begründung warum nicht nötig",
    "Analyst": "Kurze Begründung..."
  }}
}}'''

    try:
        api_key = os.environ.get("OPENROUTER_API_KEY")
        model = os.environ.get("DEFAULT_MODEL", "openrouter/google/gemini-2.0-flash-001")

        if not api_key:
            log_event("Discovery", "Error", "OPENROUTER_API_KEY nicht gesetzt")
            # Fallback: Standard-Agenten
            return {
                "status": "fallback",
                "recommended_agents": ["Coder", "Designer", "Tester"],
                "reasoning": {"fallback": "API-Key fehlt, Standard-Team verwendet"},
                "not_needed": {}
            }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": model.replace("openrouter/", ""),
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3,  # Niedrig für konsistente Entscheidungen
                    # ÄNDERUNG 03.02.2026: Feature 10a - Token-Limit aus Config
                    "max_tokens": manager.config.get("token_limits", {}).get("discovery", 1500)
                },
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                response.raise_for_status()
                result = await response.json()

        content = result.get("choices", [{}])[0].get("message", {}).get("content", "")

        # JSON aus Antwort extrahieren
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            try:
                parsed = json.loads(json_match.group())
            except (json.JSONDecodeError, ValueError) as e:
                log_event("Discovery", "SuggestTeam", f"JSON-Parse-Fehler: {e}")
                parsed = {}
            if parsed:
                log_event("Discovery", "SuggestTeam",
                          f"Empfohlen: {parsed.get('recommended_agents', [])}")
                return {
                    "status": "ok",
                    "recommended_agents": parsed.get("recommended_agents", ["Coder", "Tester"]),
                    "reasoning": parsed.get("reasoning", {}),
                    "not_needed": parsed.get("not_needed", {})
                }
        log_event("Discovery", "Warning", "Konnte JSON nicht parsen, Fallback")
        return {
            "status": "fallback",
            "recommended_agents": ["Coder", "Designer", "Tester"],
            "reasoning": {"fallback": "LLM-Antwort nicht parsebar"},
            "not_needed": {}
        }

    except Exception as e:
        log_event("Discovery", "Error", f"suggest-team Fehler: {e}")
        return {
            "status": "error",
            "recommended_agents": ["Coder", "Designer", "Tester"],
            "reasoning": {"error": str(e)},
            "not_needed": {}
        }


@router.post("/discovery/get-enhanced-options")
async def get_enhanced_options(request: EnhancedOptionsRequest):
    """
    Liefert erweiterte Optionen für eine Frage aus verschiedenen Quellen.

    Quellen-Hierarchie:
    1. Memory Agent (frühere Projekte / gelernte Lessons)
    2. Standards (Fallback-Defaults)

    Args:
        request: Frage-Kontext für Option-Generierung

    Returns:
        Erweiterte Optionen mit Quellen-Angabe
    """
    question_id = request.question_id
    question_text = request.question_text
    agent = request.agent
    vision = request.vision

    # Basis-Response
    response = {
        "status": "ok",
        "question_id": question_id,
        "enhanced_options": [],
        "memory_insights": [],
        "source": "standards"
    }

    # Memory-Integration
    # Extrahiere Keywords aus Frage und Vision
    keywords = []
    keywords.extend(question_text.lower().split())
    keywords.extend(vision.lower().split() if vision else [])
    # Filtere kurze Wörter und Stoppwörter
    keywords = [k for k in keywords if len(k) > 3 and k not in ['eine', 'einen', 'wird', 'soll', 'werden']]

    # Lade Memory und suche relevante Lessons
    memory = load_memory_safe()
    lessons = memory.get("lessons", [])

    if lessons:
        relevant_lessons = find_relevant_lessons(lessons, keywords)
        if relevant_lessons:
            response["source"] = "memory"
            response["memory_insights"] = [
                {
                    "pattern": lesson.get("pattern", ""),
                    "action": lesson.get("action", ""),
                    "count": lesson.get("count", 1),
                    "category": lesson.get("category", "general")
                }
                for lesson in relevant_lessons
            ]
            log_event("Discovery", "MemoryInsights",
                      f"{len(relevant_lessons)} relevante Lessons für '{question_id}' gefunden")

    # Standard-Empfehlungen basierend auf Agent und Frage
    standard_recommendations = {
        "Coder": {
            "coder_language": [
                {"text": "Python", "value": "python", "recommended": True, "reason": "Vielseitig, große Community"},
                {"text": "TypeScript", "value": "typescript", "recommended": False, "reason": "Typsicher für Frontend"}
            ],
            "coder_deployment": [
                {"text": "Docker Container", "value": "docker", "recommended": True, "reason": "Konsistente Umgebung"},
                {"text": "Lokale Ausführung", "value": "local", "recommended": False, "reason": "Einfachster Start"}
            ]
        },
        "Analyst": {
            "analyst_purpose": [
                {"text": "Kundenprodukt", "value": "customer", "recommended": True, "reason": "Höchste Qualitätsstandards"}
            ],
            "analyst_scope_in": [
                {"text": "Kernfunktionalität", "value": "core", "recommended": True, "reason": "Fokus auf MVP"}
            ]
        },
        "Tester": {
            "tester_coverage": [
                {"text": "Standard (Unit + Integration)", "value": "standard", "recommended": True, "reason": "Gute Balance"}
            ]
        },
        "Planner": {
            "planner_timeline": [
                {"text": "1-2 Wochen", "value": "short", "recommended": True, "reason": "Schnelles Feedback"}
            ],
            "planner_milestones": [
                {"text": "MVP / Proof of Concept", "value": "mvp", "recommended": True, "reason": "Frühe Validierung"}
            ]
        },
        "Data Researcher": {
            "researcher_sources": [
                {"text": "Interne Datenbanken", "value": "internal_db", "recommended": True, "reason": "Direkter Zugriff"}
            ]
        },
        "Designer": {
            "designer_style": [
                {"text": "Modern / Minimalistisch", "value": "modern", "recommended": True, "reason": "Zeitgemäß"}
            ]
        },
        "Security": {
            "security_auth": [
                {"text": "OAuth / Social Login", "value": "oauth", "recommended": True, "reason": "Sichere Standards"}
            ]
        }
    }

    agent_recommendations = standard_recommendations.get(agent, {})
    question_recommendations = agent_recommendations.get(question_id, [])

    if question_recommendations:
        response["enhanced_options"] = question_recommendations
        if response["source"] != "memory":
            response["source"] = "standards"

    log_event("Discovery", "EnhancedOptions",
              f"Optionen für {question_id} von {agent}: "
              f"{len(response['enhanced_options'])} Optionen, "
              f"{len(response['memory_insights'])} Memory-Insights ({response['source']})")

    return response
