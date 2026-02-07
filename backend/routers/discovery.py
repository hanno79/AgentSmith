# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 01.02.2026
Version: 2.0
Beschreibung: Discovery-Session Endpunkte (Orchestrator).
              REFAKTORIERT: Aus 818 Zeilen → 3 Module + Orchestrator

              Module:
              - discovery_briefing.py: Briefing speichern/laden, Markdown-Generierung
              - discovery_questions.py: Fragen-Generierung, Deduplizierung
              - discovery_team.py: Team-Empfehlung, erweiterte Optionen

              ÄNDERUNG 01.02.2026: Aufsplitten in 3 Module (Regel 1: Max 500 Zeilen).
              ÄNDERUNG 29.01.2026: Discovery-Endpunkte in eigenes Router-Modul verschoben.
              ÄNDERUNG 29.01.2026 v1.1: Quellen-System Endpunkt für erweiterte Optionen.
              ÄNDERUNG 29.01.2026 v1.2: Memory-Integration für Quellen-System.
"""

import logging
from fastapi import APIRouter

# =========================================================================
# Logger Setup
# =========================================================================
logger = logging.getLogger(__name__)

if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(funcName)s] - %(message)s"
    ))
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)

# =========================================================================
# Haupt-Router
# =========================================================================
router = APIRouter()

# =========================================================================
# Sub-Router importieren und inkludieren
# =========================================================================
from .discovery_briefing import router as briefing_router
from .discovery_questions import router as questions_router
from .discovery_team import router as team_router

# Inkludiere alle Sub-Router (ohne Prefix, da bereits in den Modulen definiert)
router.include_router(briefing_router)
router.include_router(questions_router)
router.include_router(team_router)

# =========================================================================
# Re-exports für Rückwärtskompatibilität
# =========================================================================
from .discovery_briefing import (
    MEMORY_PATH,
    load_memory_safe,
    find_relevant_lessons,
    sanitize_project_name,
    generate_briefing_markdown,
    save_discovery_briefing,
    get_discovery_briefing
)

from .discovery_questions import (
    SKIP_QUESTION_AGENTS,
    MAX_QUESTIONS_PER_AGENT,
    AGENT_QUESTION_PRIORITY,
    STOP_WORDS,
    DiscoveryQuestionsRequest,
    generate_agent_questions,
    questions_are_similar,
    merge_options,
    deduplicate_questions,
    generate_discovery_questions
)

from .discovery_team import (
    SuggestTeamRequest,
    EnhancedOptionsRequest,
    suggest_team,
    get_enhanced_options
)

# =========================================================================
# Expliziter __all__ Export
# =========================================================================
__all__ = [
    # Router
    'router',
    # Briefing
    'MEMORY_PATH',
    'load_memory_safe',
    'find_relevant_lessons',
    'sanitize_project_name',
    'generate_briefing_markdown',
    'save_discovery_briefing',
    'get_discovery_briefing',
    # Questions
    'SKIP_QUESTION_AGENTS',
    'MAX_QUESTIONS_PER_AGENT',
    'AGENT_QUESTION_PRIORITY',
    'STOP_WORDS',
    'DiscoveryQuestionsRequest',
    'generate_agent_questions',
    'questions_are_similar',
    'merge_options',
    'deduplicate_questions',
    'generate_discovery_questions',
    # Team
    'SuggestTeamRequest',
    'EnhancedOptionsRequest',
    'suggest_team',
    'get_enhanced_options'
]

# =========================================================================
# Deprecated Aliases für Rückwärtskompatibilität
# =========================================================================
# Diese Funktionen wurden umbenannt, Aliases für bestehenden Code
_load_memory_safe = load_memory_safe
_find_relevant_lessons = find_relevant_lessons
_sanitize_project_name = sanitize_project_name
_generate_briefing_markdown = generate_briefing_markdown
_generate_agent_questions = generate_agent_questions
_questions_are_similar = questions_are_similar
_merge_options = merge_options
_deduplicate_questions = deduplicate_questions
