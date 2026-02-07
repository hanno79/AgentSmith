# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 01.02.2026
Version: 1.0
Beschreibung: Discovery Fragen-Generierung.
              Extrahiert aus discovery.py (Regel 1: Max 500 Zeilen)
              Enthält: generate_discovery_questions, Deduplizierung, LLM-Integration
"""

import os
import re
import json
import uuid
import random
import logging
import aiohttp
from typing import List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..app_state import manager
from ..api_logging import log_event

router = APIRouter()
logger = logging.getLogger(__name__)


# =========================================================================
# Konstanten
# =========================================================================

SKIP_QUESTION_AGENTS = ["Security", "Tester", "Reviewer"]

MAX_QUESTIONS_PER_AGENT = {
    "Coder": 3,
    "DB-Designer": 3,
    "Designer": 2,
    "Researcher": 1,
    "TechStack": 1
}

# Priorisierte Reihenfolge für Fragen-Generierung
AGENT_QUESTION_PRIORITY = [
    "Analyst",          # Geschäftliche Grundfragen zuerst
    "Data Researcher",  # Datenquellen
    "Researcher",       # Recherche
    "Coder",            # Technische Fragen
    "TechStack",        # Technologie-Wahl
    "DB-Designer",      # Datenbank
    "Designer",         # UI/UX Fragen
    "Planner",          # Timeline/Meilensteine
    "Tester",           # Test-Anforderungen zuletzt
]

STOP_WORDS = {
    "der", "die", "das", "ein", "eine", "einer", "einem", "einen",
    "soll", "sollen", "werden", "wird", "ist", "sind", "wird",
    "welche", "welcher", "welches", "wie", "was", "wer",
    "bei", "mit", "für", "auf", "von", "zu", "zur", "zum",
    "und", "oder", "aber", "denn", "wenn", "ob", "als",
    "es", "sie", "er", "wir", "ihr", "du", "ich"
}


# =========================================================================
# Pydantic Models
# =========================================================================

class DiscoveryQuestionsRequest(BaseModel):
    """Request für dynamische Fragen-Generierung."""
    vision: str
    agents: list


# =========================================================================
# Hilfs-Funktionen
# =========================================================================

async def generate_agent_questions(agent: str, vision: str, already_asked: List[str] = None) -> dict:
    """
    Generiert kundenfreundliche Fragen für einen Agent via LLM.

    Sequentielle Generation mit Kontext - jeder Agent bekommt die bereits
    gestellten Fragen und muss ANDERE stellen.

    Args:
        agent: Agent-Name (z.B. "Coder", "DB-Designer")
        vision: Projektbeschreibung vom Benutzer
        already_asked: Liste bereits gestellter Fragen (von anderen Agenten)

    Returns:
        Dict mit agent und questions Array
    """
    max_questions = MAX_QUESTIONS_PER_AGENT.get(agent, 2)

    agent_roles = {
        "Coder": "Entwickler, der die Features und Funktionalität implementiert",
        "DB-Designer": "Datenbankexperte, der die Datenstruktur plant",
        "Designer": "UI/UX Designer, der das Aussehen und die Bedienung gestaltet",
        "Researcher": "Recherche-Experte für technische Hintergründe",
        "TechStack": "Technologie-Berater für die Wahl der Werkzeuge",
        "Analyst": "Business Analyst, der Geschäftsanforderungen analysiert",
        "Data Researcher": "Daten-Experte für Quellen und Qualität",
        "Planner": "Projektplaner für Timeline und Meilensteine"
    }

    role_desc = agent_roles.get(agent, f"{agent}-Experte")

    # Dynamische Variation für unterschiedliche Fragen
    session_hint = str(uuid.uuid4())[:6]
    focus_areas = [
        "Benutzerfreundlichkeit und UX",
        "technische Umsetzbarkeit",
        "Skalierbarkeit und Performance",
        "schnelle Implementierung (MVP)",
        "langfristige Wartbarkeit",
        "Sicherheit und Datenschutz",
        "Integration mit bestehenden Systemen"
    ]
    random_focus = random.choice(focus_areas)

    # Kontext für bereits gestellte Fragen
    exclusion_prompt = ""
    if already_asked and len(already_asked) > 0:
        questions_list = "\n".join([f"  - {q}" for q in already_asked])
        exclusion_prompt = f"""
⚠️ WICHTIG - DIESE FRAGEN WURDEN BEREITS GESTELLT:
{questions_list}

Du MUSST ANDERE Fragen stellen! Vermeide:
- Wiederholungen der obigen Fragen
- Leicht umformulierte Versionen derselben Themen
- Fragen zu bereits abgedeckten Bereichen (Geräte, Offline, Benutzeranzahl etc.)

Stelle stattdessen Fragen aus DEINER einzigartigen Fachperspektive als {role_desc}.
"""

    prompt = f'''Du bist der {role_desc} in einem Entwicklungsteam.
[Session: {session_hint}]
{exclusion_prompt}
Analysiere diese Projektbeschreibung mit besonderem Fokus auf {random_focus}:

"{vision}"

Generiere {max_questions} EINZIGARTIGE Fragen aus DEINER Fachperspektive.

WICHTIG - Formulierung:
- Verständlich für Nicht-Techniker (KEINE Fachbegriffe!)
- Nutze konkrete Beispiele zur Verdeutlichung
- Jede Frage braucht 3-4 Antwortoptionen

BEISPIELE für gute vs. schlechte Fragen:
SCHLECHT: "Benötigen Sie eine n:m Beziehung?"
GUT: "Kann ein Benutzer mehrere Listen anlegen, und können Listen mit anderen geteilt werden?"

SCHLECHT: "Soll das Frontend responsiv sein?"
GUT: "Auf welchen Geräten soll die App funktionieren - nur Computer, auch Handy?"

SCHLECHT: "Welche API-Architektur bevorzugen Sie?"
GUT: "Soll die App auch offline funktionieren oder nur mit Internetverbindung?"

Antworte NUR mit validem JSON in diesem Format:
{{
  "agent": "{agent}",
  "questions": [
    {{
      "id": "eindeutige_id",
      "question": "Verständliche Frage?",
      "example": "Konkretes Beispiel zur Verdeutlichung",
      "options": [
        {{"text": "Option 1", "value": "opt1"}},
        {{"text": "Option 2", "value": "opt2"}},
        {{"text": "Option 3", "value": "opt3"}}
      ],
      "allowCustom": true
    }}
  ]
}}'''

    try:
        mode = manager.config.get("mode", "test")
        models = manager.config.get("models", {}).get(mode, {})
        model = models.get("orchestrator", models.get("coder", "openrouter/meta-llama/llama-3.3-70b-instruct:free"))

        if isinstance(model, dict):
            model = model.get("primary", str(model))

        api_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("Kein API-Key gefunden")

        # Async HTTP für non-blocking WebSocket-Stabilität
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
                    "temperature": 0.95,
                    # ÄNDERUNG 03.02.2026: Feature 10a - Token-Limit aus Config
                    "max_tokens": manager.config.get("token_limits", {}).get("discovery", 1500)
                },
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                response.raise_for_status()
                result = await response.json()
        content = result.get("choices", [{}])[0].get("message", {}).get("content", "")

        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            parsed = json.loads(json_match.group())
            questions_count = len(parsed.get("questions", []))
            log_event("Discovery", "LLMQuestions", json.dumps({
                "agent": agent,
                "model": model,
                "session_hint": session_hint,
                "focus": random_focus,
                "questions_count": questions_count,
                "temperature": 0.95
            }, ensure_ascii=False))
            return parsed
        raise ValueError("Kein JSON in LLM-Antwort gefunden")

    except Exception as e:
        log_event("Discovery", "Warning", f"Fragen-Generierung für {agent} fehlgeschlagen: {e}")
        return {"agent": agent, "questions": []}


def questions_are_similar(q1: str, q2: str, threshold: float = 0.6) -> bool:
    """
    Prüft ob zwei Fragen ähnlich genug sind um zusammengeführt zu werden.
    Nutzt Jaccard-Ähnlichkeit (Wort-Überlappung).
    """
    def normalize(text: str) -> set:
        cleaned = re.sub(r'[^\w\s]', '', text.lower())
        words = set(cleaned.split())
        return words - STOP_WORDS

    words1 = normalize(q1)
    words2 = normalize(q2)

    if not words1 or not words2:
        return False

    intersection = len(words1 & words2)
    union = len(words1 | words2)
    similarity = intersection / union if union > 0 else 0

    return similarity >= threshold


def merge_options(target_options: list, source_options: list) -> None:
    """Fügt einzigartige Optionen zur Zielliste hinzu."""
    existing_values = {opt.get("value") for opt in target_options}
    for opt in source_options:
        if opt.get("value") not in existing_values:
            target_options.append(opt)
            existing_values.add(opt.get("value"))


def deduplicate_questions(all_agent_questions: list) -> list:
    """
    Gruppiert ähnliche Fragen von verschiedenen Agenten.
    Jede Frage wird nur einmal gestellt, aber alle relevanten Agenten zugeordnet.
    """
    all_questions = []
    for agent_data in all_agent_questions:
        agent = agent_data.get("agent", "Unknown")
        for q in agent_data.get("questions", []):
            q_copy = q.copy()
            q_copy["source_agent"] = agent
            all_questions.append(q_copy)

    if not all_questions:
        return []

    merged = []
    used_indices = set()

    for i, q1 in enumerate(all_questions):
        if i in used_indices:
            continue

        group = {
            "id": q1.get("id", f"q_{i}"),
            "question": q1.get("question", ""),
            "example": q1.get("example"),
            "options": list(q1.get("options", [])),
            "allowCustom": q1.get("allowCustom", True),
            "agents": [q1["source_agent"]]
        }
        used_indices.add(i)

        for j, q2 in enumerate(all_questions):
            if j in used_indices:
                continue

            if questions_are_similar(q1.get("question", ""), q2.get("question", "")):
                if q2["source_agent"] not in group["agents"]:
                    group["agents"].append(q2["source_agent"])
                merge_options(group["options"], q2.get("options", []))
                if not group["example"] and q2.get("example"):
                    group["example"] = q2["example"]
                used_indices.add(j)

        merged.append(group)

    log_event("Discovery", "Deduplicate",
              f"{len(all_questions)} Fragen → {len(merged)} dedupliziert "
              f"({len(all_questions) - len(merged)} zusammengeführt)")

    return merged


# =========================================================================
# API Endpunkt
# =========================================================================

@router.post("/discovery/generate-questions")
async def generate_discovery_questions(request: DiscoveryQuestionsRequest):
    """
    LLM generiert projektspezifische Fragen pro Agent.

    Sequentielle Generation mit Kontext:
    - Agenten werden nach Priorität sortiert
    - Jeder Agent kennt die bisherigen Fragen und muss ANDERE stellen
    - Verhindert redundante Fragen wie "Soll die App offline funktionieren?"
    """
    vision = request.vision
    agents = request.agents

    if not vision or not vision.strip():
        raise HTTPException(status_code=400, detail="Vision/Projektbeschreibung fehlt")

    if not agents:
        raise HTTPException(status_code=400, detail="Keine Agenten angegeben")

    # Sortiere Agenten nach Priorität
    def get_priority(agent_name: str) -> int:
        try:
            return AGENT_QUESTION_PRIORITY.index(agent_name)
        except ValueError:
            return 99  # Unbekannte Agenten am Ende

    agents_sorted = sorted(agents, key=get_priority)
    log_event("Discovery", "AgentOrder", f"Fragen-Reihenfolge: {agents_sorted}")

    all_questions = []
    already_asked_questions = []  # Sammelt alle bisherigen Fragen

    # Sequentielle Generation mit Kontext
    for agent in agents_sorted:
        if agent in SKIP_QUESTION_AGENTS:
            continue

        try:
            # Generiere mit Kenntnis der bisherigen Fragen
            agent_questions = await generate_agent_questions(
                agent=agent,
                vision=vision,
                already_asked=already_asked_questions
            )

            if agent_questions.get("questions"):
                all_questions.append(agent_questions)

                # Füge die neuen Fragen zur Liste hinzu für nächsten Agent
                for q in agent_questions.get("questions", []):
                    question_text = q.get("question", "")
                    if question_text:
                        already_asked_questions.append(question_text)

                log_event("Discovery", "AgentQuestions",
                          f"{agent}: {len(agent_questions.get('questions', []))} Fragen, "
                          f"Kontext: {len(already_asked_questions)} bisherige")

        except Exception as e:
            log_event("Discovery", "Warning", f"Fragen für {agent} übersprungen: {e}")
            continue

    original_count = sum(len(aq.get("questions", [])) for aq in all_questions)

    # Deduplizierung als Sicherheitsnetz
    deduplicated = deduplicate_questions(all_questions)

    log_event("Discovery", "Summary",
              f"Sequentielle Generation: {original_count} → {len(deduplicated)} "
              f"({original_count - len(deduplicated)} zusammengeführt)")

    return {
        "status": "ok",
        "questions": deduplicated,
        "agents_processed": len(all_questions),
        "questions_original": original_count,
        "questions_deduplicated": len(deduplicated),
        "questions_merged": original_count - len(deduplicated),
        "generation_mode": "sequential_with_context"
    }
