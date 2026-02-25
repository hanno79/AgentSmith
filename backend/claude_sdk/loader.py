# -*- coding: utf-8 -*-
# Author: rahn
# Datum: 24.02.2026
# Version: 1.0
# Beschreibung: Loader fuer Claude SDK Zustand, Model-Mapping und Tier-Konfiguration.
"""Claude SDK Loader-Zustand (thread-safe lazy init)."""

import logging
import threading

logger = logging.getLogger(__name__)

_sdk_loaded = False
_sdk_load_lock = threading.RLock()
_sdk_query = None
_sdk_options_class = None
_sdk_assistant_message = None
_sdk_text_block = None
# ÄNDERUNG 22.02.2026: StreamEvent + ResultMessage für korrekte isinstance-Prüfungen.
_sdk_stream_event = None
_sdk_result_message = None


def _ensure_sdk_loaded():
    global _sdk_loaded
    global _sdk_query
    global _sdk_options_class
    global _sdk_assistant_message
    global _sdk_text_block
    global _sdk_stream_event
    global _sdk_result_message

    if _sdk_loaded:
        return

    with _sdk_load_lock:
        if _sdk_loaded:
            return
        try:
            from claude_agent_sdk import (
                query,
                ClaudeAgentOptions,
                AssistantMessage,
                TextBlock,
                ResultMessage,
            )
            try:
                from claude_agent_sdk.types import StreamEvent
            except Exception:
                StreamEvent = type("StreamEvent", (), {})

            _sdk_query = query
            _sdk_options_class = ClaudeAgentOptions
            _sdk_assistant_message = AssistantMessage
            _sdk_text_block = TextBlock
            _sdk_stream_event = StreamEvent
            _sdk_result_message = ResultMessage
            _sdk_loaded = True
            logger.info("claude-agent-sdk geladen (thread-safe lazy init)")
        except ImportError as e:
            logger.error("claude-agent-sdk nicht installiert: %s", e)
            raise ImportError(
                "claude-agent-sdk nicht verfuegbar. Installation: pip install claude-agent-sdk"
            ) from e


CLAUDE_MODEL_MAP = {
    "opus": "claude-opus-4-1-20250805",
    "sonnet": "claude-sonnet-4-20250514",
    # ÄNDERUNG 24.02.2026: Fix 77 — Haiku Model-ID aktualisiert
    # ROOT-CAUSE-FIX:
    # Symptom: "There's an issue with the selected model" bei allen role="fix" Aufrufen
    # Ursache: claude-3-5-haiku-20241022 von Claude CLI 2.1.39 nicht mehr akzeptiert
    # Loesung: Auf aktuelle Haiku 4.5 ID aktualisiert (verifiziert via test_model_ids.py)
    "haiku": "claude-haiku-4-5-20251001",
}

# AENDERUNG 24.02.2026: Fix 76b — Neue Rollen hinzugefuegt
_SDK_TIER_ORDER = {
    # AENDERUNG 25.02.2026: Fix 80 — Fix auf Tier 1 (Sonnet statt Haiku)
    "fix": 1,
    "tester": 0,
    # AENDERUNG 24.02.2026: Fix 76d — TaskDeriver auf Tier 2 (Opus, wie researcher/techstack)
    "task_deriver": 2,       # Opus: Komplexe Ziel-Dekomposition
    "coder": 1,
    # AENDERUNG 24.02.2026: Fix 78 — Reviewer/Planner auf Tier 2 (Opus)
    # ROOT-CAUSE-FIX:
    # Symptom: Reviewer/Planner treffen IMMER auf rate_limit_event im async SDK
    # Ursache: Als Tier-1 hatten sie max_retries_tier1_non_coder=2, zu wenig mit Cooldown
    # Loesung: Tier 2 mit max_retries_tier2=2, passend zu Opus-Modell und Pre-Call Cooldown
    "reviewer": 2,
    "planner": 2,
    "designer": 1,
    "db_designer": 1,
    "security": 1,
    "documentation_manager": 1,
    "analyst": 1,            # Anforderungsanalyse
    "konzepter": 1,          # Feature-Konzeption
    "researcher": 2,
    "techstack_architect": 2,
}
