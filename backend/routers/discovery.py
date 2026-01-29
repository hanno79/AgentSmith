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
import aiohttp
import logging
import uuid
import random
from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from ..app_state import manager
from ..session_utils import get_session_manager_instance
from ..api_logging import log_event

router = APIRouter()
logger = logging.getLogger(__name__)

# ÄNDERUNG 29.01.2026: Logger-Format sicherstellen
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(funcName)s] - %(message)s"
    ))
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)

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
        # ÄNDERUNG 29.01.2026: Standard-Logger statt print
        logger.warning("Briefing-Datei konnte nicht gespeichert werden: %s", e, exc_info=True)

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

# ÄNDERUNG 29.01.2026: Priorisierte Reihenfolge für Fragen-Generierung
# Wichtigste Agenten zuerst (haben mehr Freiheit bei Fragen)
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


async def _generate_agent_questions(agent: str, vision: str, already_asked: List[str] = None) -> dict:
    """
    Generiert kundenfreundliche Fragen für einen Agent via LLM.

    ÄNDERUNG 29.01.2026: Sequentielle Generation mit Kontext
    Jeder Agent bekommt die bereits gestellten Fragen und muss ANDERE stellen.

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

    # ÄNDERUNG 29.01.2026: Dynamische Variation für unterschiedliche Fragen
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

    # ÄNDERUNG 29.01.2026: Kontext für bereits gestellte Fragen
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

        # ÄNDERUNG 29.01.2026: Async HTTP für non-blocking WebSocket-Stabilität
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
                    "temperature": 0.95,  # ÄNDERUNG 29.01.2026: Höhere Temperature für mehr Variation
                    "max_tokens": 1500
                },
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                response.raise_for_status()
                result = await response.json()
        content = result.get("choices", [{}])[0].get("message", {}).get("content", "")

        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            parsed = json.loads(json_match.group())
            # ÄNDERUNG 29.01.2026: Logging für Debugging der Fragen-Variation
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

    ÄNDERUNG 29.01.2026: Sequentielle Generation mit Kontext
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

    # ÄNDERUNG 29.01.2026: Sortiere Agenten nach Priorität
    # Wichtigste Agenten stellen zuerst Fragen (haben mehr Freiheit)
    def get_priority(agent_name: str) -> int:
        try:
            return AGENT_QUESTION_PRIORITY.index(agent_name)
        except ValueError:
            return 99  # Unbekannte Agenten am Ende

    agents_sorted = sorted(agents, key=get_priority)
    log_event("Discovery", "AgentOrder", f"Fragen-Reihenfolge: {agents_sorted}")

    all_questions = []
    already_asked_questions = []  # Sammelt alle bisherigen Fragen

    # ÄNDERUNG 29.01.2026: Sequentielle Generation mit Kontext
    for agent in agents_sorted:
        if agent in SKIP_QUESTION_AGENTS:
            continue

        try:
            # Generiere mit Kenntnis der bisherigen Fragen
            agent_questions = await _generate_agent_questions(
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

    # Deduplizierung bleibt als Sicherheitsnetz (sollte jetzt weniger zu tun haben)
    deduplicated = _deduplicate_questions(all_questions)

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


# ÄNDERUNG 29.01.2026: Intelligente LLM-basierte Agenten-Auswahl
class SuggestTeamRequest(BaseModel):
    """Request für LLM-basierte Team-Empfehlung."""
    vision: str


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
                    "max_tokens": 1000
                },
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                response.raise_for_status()
                result = await response.json()

        content = result.get("choices", [{}])[0].get("message", {}).get("content", "")

        # JSON aus Antwort extrahieren
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            parsed = json.loads(json_match.group())
            log_event("Discovery", "SuggestTeam",
                      f"Empfohlen: {parsed.get('recommended_agents', [])}")
            return {
                "status": "ok",
                "recommended_agents": parsed.get("recommended_agents", ["Coder", "Tester"]),
                "reasoning": parsed.get("reasoning", {}),
                "not_needed": parsed.get("not_needed", {})
            }
        else:
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
