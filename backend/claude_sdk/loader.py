# -*- coding: utf-8 -*-
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
    "opus": "claude-opus-4-6",
    "sonnet": "claude-sonnet-4-6",
    "haiku": "claude-haiku-4-5",
}

# AENDERUNG 24.02.2026: Fix 76b — Neue Rollen hinzugefuegt
_SDK_TIER_ORDER = {
    "fix": 0,
    "tester": 0,
    "task_deriver": 0,       # Einfache strukturierte JSON-Ausgabe
    "coder": 1,
    "reviewer": 1,
    "planner": 1,
    "designer": 1,
    "db_designer": 1,
    "security": 1,
    "documentation_manager": 1,
    "analyst": 1,            # Anforderungsanalyse
    "konzepter": 1,          # Feature-Konzeption
    "researcher": 2,
    "techstack_architect": 2,
}
