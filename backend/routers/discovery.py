# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 29.01.2026
Version: 1.2
Beschreibung: Discovery-Session Endpunkte und Hilfsfunktionen.
"""
# ÄNDERUNG 29.01.2026: Discovery-Endpunkte in eigenes Router-Modul verschoben
# ÄNDERUNG 29.01.2026 v1.1: Quellen-System Endpunkt für erweiterte Optionen
# ÄNDERUNG 29.01.2026 v1.2: Memory-Integration für Quellen-System

import json
import os
import re
import requests
from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from ..app_state import manager
from ..session_utils import get_session_manager_instance
from ..api_logging import log_event

router = APIRouter()

# ÄNDERUNG 29.01.2026 v1.2: Memory-Pfad für Quellen-System
MEMORY_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "memory", "agent_memory.json")


def _load_memory_safe() -> dict:
    """Lädt Memory sicher, gibt leeres Dict bei Fehler zurück."""
    try:
        if os.path.exists(MEMORY_PATH):
            with open(MEMORY_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        log_event("Discovery", "MemoryLoadError", str(e))
    return {"history": [], "lessons": []}


def _find_relevant_lessons(lessons: List[dict], keywords: List[str]) -> List[dict]:
    """Findet Lessons die zu den Keywords passen."""
    relevant = []
    for lesson in lessons:
        tags = lesson.get("tags", [])
        pattern = lesson.get("pattern", "").lower()
        action = lesson.get("action", "").lower()

        for keyword in keywords:
            kw = keyword.lower()
            if (kw in tags or
                kw in pattern or
                kw in action):
                relevant.append(lesson)
                break

    # Sortiere nach Häufigkeit (count) absteigend
    relevant.sort(key=lambda x: x.get("count", 0), reverse=True)
    return relevant[:5]  # Maximal 5 relevante Lessons


def _sanitize_project_name(raw_name: str, max_length: int = 80) -> str:
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
    project_name = _sanitize_project_name(briefing.get("projectName", "unnamed_project"))

    if session_mgr:
        session_mgr.set_discovery_briefing(briefing)

    manager.set_discovery_briefing(briefing)

    briefing_path = None
    try:
        projects_dir = os.path.join(os.path.dirname(__file__), "..", "..", "projects")
        os.makedirs(projects_dir, exist_ok=True)
        briefing_path = os.path.join(projects_dir, f"{project_name}_briefing.md")

        markdown = _generate_briefing_markdown(briefing)
        with open(briefing_path, "w", encoding="utf-8") as f:
            f.write(markdown)
    except Exception as e:
        print(f"[WARN] Briefing-Datei konnte nicht gespeichert werden: {e}")

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


def _generate_briefing_markdown(briefing: dict) -> str:
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


class DiscoveryQuestionsRequest(BaseModel):
    """Request für dynamische Fragen-Generierung."""
    vision: str
    agents: list


SKIP_QUESTION_AGENTS = ["Security", "Tester", "Reviewer"]

MAX_QUESTIONS_PER_AGENT = {
    "Coder": 3,
    "DB-Designer": 3,
    "Designer": 2,
    "Researcher": 1,
    "TechStack": 1
}


async def _generate_agent_questions(agent: str, vision: str) -> dict:
    """
    Generiert kundenfreundliche Fragen für einen Agent via LLM.

    Args:
        agent: Agent-Name (z.B. "Coder", "DB-Designer")
        vision: Projektbeschreibung vom Benutzer

    Returns:
        Dict mit agent und questions Array
    """
    max_questions = MAX_QUESTIONS_PER_AGENT.get(agent, 2)

    agent_roles = {
        "Coder": "Entwickler, der die Features und Funktionalität implementiert",
        "DB-Designer": "Datenbankexperte, der die Datenstruktur plant",
        "Designer": "UI/UX Designer, der das Aussehen und die Bedienung gestaltet",
        "Researcher": "Recherche-Experte für technische Hintergründe",
        "TechStack": "Technologie-Berater für die Wahl der Werkzeuge"
    }

    role_desc = agent_roles.get(agent, f"{agent}-Experte")

    prompt = f'''Du bist der {role_desc} in einem Entwicklungsteam.
Analysiere diese Projektbeschreibung:

"{vision}"

Generiere {max_questions} Fragen um die genauen Anforderungen zu verstehen.

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

        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": model.replace("openrouter/", ""),
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.7,
                "max_tokens": 1500
            },
            timeout=30
        )
        response.raise_for_status()

        result = response.json()
        content = result.get("choices", [{}])[0].get("message", {}).get("content", "")

        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            parsed = json.loads(json_match.group())
            return parsed
        raise ValueError("Kein JSON in LLM-Antwort gefunden")

    except Exception as e:
        log_event("Discovery", "Warning", f"Fragen-Generierung für {agent} fehlgeschlagen: {e}")
        return {"agent": agent, "questions": []}


STOP_WORDS = {
    "der", "die", "das", "ein", "eine", "einer", "einem", "einen",
    "soll", "sollen", "werden", "wird", "ist", "sind", "wird",
    "welche", "welcher", "welches", "wie", "was", "wer",
    "bei", "mit", "für", "auf", "von", "zu", "zur", "zum",
    "und", "oder", "aber", "denn", "wenn", "ob", "als",
    "es", "sie", "er", "wir", "ihr", "du", "ich"
}


def _questions_are_similar(q1: str, q2: str, threshold: float = 0.6) -> bool:
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


def _merge_options(target_options: list, source_options: list) -> None:
    """Fügt einzigartige Optionen zur Zielliste hinzu."""
    existing_values = {opt.get("value") for opt in target_options}
    for opt in source_options:
        if opt.get("value") not in existing_values:
            target_options.append(opt)
            existing_values.add(opt.get("value"))


def _deduplicate_questions(all_agent_questions: list) -> list:
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

            if _questions_are_similar(q1.get("question", ""), q2.get("question", "")):
                if q2["source_agent"] not in group["agents"]:
                    group["agents"].append(q2["source_agent"])
                _merge_options(group["options"], q2.get("options", []))
                if not group["example"] and q2.get("example"):
                    group["example"] = q2["example"]
                used_indices.add(j)

        merged.append(group)

    log_event("Discovery", "Deduplicate",
              f"{len(all_questions)} Fragen → {len(merged)} dedupliziert "
              f"({len(all_questions) - len(merged)} zusammengeführt)")

    return merged


@router.post("/discovery/generate-questions")
async def generate_discovery_questions(request: DiscoveryQuestionsRequest):
    """
    LLM generiert projektspezifische Fragen pro Agent.
    """
    vision = request.vision
    agents = request.agents

    if not vision or not vision.strip():
        raise HTTPException(status_code=400, detail="Vision/Projektbeschreibung fehlt")

    if not agents:
        raise HTTPException(status_code=400, detail="Keine Agenten angegeben")

    all_questions = []

    for agent in agents:
        if agent in SKIP_QUESTION_AGENTS:
            continue

        try:
            agent_questions = await _generate_agent_questions(agent, vision)
            if agent_questions.get("questions"):
                all_questions.append(agent_questions)
        except Exception as e:
            log_event("Discovery", "Warning", f"Fragen für {agent} übersprungen: {e}")
            continue

    original_count = sum(len(aq.get("questions", [])) for aq in all_questions)
    deduplicated = _deduplicate_questions(all_questions)

    return {
        "status": "ok",
        "questions": deduplicated,
        "agents_processed": len(all_questions),
        "questions_original": original_count,
        "questions_deduplicated": len(deduplicated),
        "questions_merged": original_count - len(deduplicated)
    }


# ÄNDERUNG 29.01.2026 v1.1: Quellen-System für erweiterte Optionen
class EnhancedOptionsRequest(BaseModel):
    """Request für erweiterte Optionen aus verschiedenen Quellen."""
    question_id: str
    question_text: str
    agent: str
    vision: str = ""


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

    # ÄNDERUNG 29.01.2026 v1.2: Memory-Integration
    # Extrahiere Keywords aus Frage und Vision
    keywords = []
    keywords.extend(question_text.lower().split())
    keywords.extend(vision.lower().split() if vision else [])
    # Filtere kurze Wörter und Stoppwörter
    keywords = [k for k in keywords if len(k) > 3 and k not in ['eine', 'einen', 'wird', 'soll', 'werden']]

    # Lade Memory und suche relevante Lessons
    memory = _load_memory_safe()
    lessons = memory.get("lessons", [])

    if lessons:
        relevant_lessons = _find_relevant_lessons(lessons, keywords)
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
