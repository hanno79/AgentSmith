# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 31.01.2026
Version: 1.0
Beschreibung: Budget-Tracking Modul mit LiteLLM Callbacks.
              Extrahiert aus orchestration_manager.py (Regel 1: Max 500 Zeilen)
              ÄNDERUNG 30.01.2026: Thread-Safe globals statt ContextVar für korrektes Tracking
"""

import logging
import threading

logger = logging.getLogger(__name__)

# =====================================================================
# LiteLLM Callback für Budget-Tracking
# ÄNDERUNG 30.01.2026: Thread-Safe globals statt ContextVar für korrektes Tracking
# =====================================================================

# Thread-Safe globale Variablen für Budget-Tracking
_budget_tracking_lock = threading.Lock()
_current_agent_name = "Unknown"
_current_project_id = None


def _get_current_tracking_context():
    """
    Thread-Safe Getter für aktuelle Tracking-Kontextwerte.

    Returns:
        Tuple (agent_name, project_id)
    """
    global _current_agent_name, _current_project_id
    with _budget_tracking_lock:
        return (_current_agent_name, _current_project_id)


def set_current_agent(agent_name: str, project_id: str = None):
    """
    Setzt den aktuellen Agenten für Budget-Tracking (Thread-Safe).
    ÄNDERUNG 30.01.2026: Nutzt globale Variablen mit Lock statt ContextVar.

    Args:
        agent_name: Name des aktuellen Agenten
        project_id: Optionale Projekt-ID
    """
    global _current_agent_name, _current_project_id
    with _budget_tracking_lock:
        _current_agent_name = agent_name
        if project_id is not None:
            _current_project_id = project_id


# LiteLLM Callback-Registrierung
try:
    import litellm
    from budget_tracker import get_budget_tracker

    def _budget_tracking_callback(kwargs, completion_response, start_time, end_time):
        """
        LiteLLM success callback - erfasst Token-Nutzung nach jedem API-Call.
        ÄNDERUNG 30.01.2026: Thread-Safe Zugriff auf globale Variablen.
        """
        try:
            tracker = get_budget_tracker()

            # Thread-Safe Lesen der aktuellen Werte
            current_agent_name, current_project_id = _get_current_tracking_context()

            # Extrahiere Token-Usage aus der Response
            usage = getattr(completion_response, 'usage', None)
            if usage:
                prompt_tokens = getattr(usage, 'prompt_tokens', 0)
                completion_tokens = getattr(usage, 'completion_tokens', 0)
                model = kwargs.get('model', 'unknown')

                # Erfasse die Nutzung
                tracker.record_usage(
                    agent=current_agent_name,
                    model=model,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    project_id=current_project_id
                )
                logger.debug(
                    "_budget_tracking_callback: %s - %s+%s Tokens (Modell: %s, Projekt: %s)",
                    current_agent_name,
                    prompt_tokens,
                    completion_tokens,
                    model,
                    current_project_id
                )
        except Exception as e:
            logger.exception("_budget_tracking_callback: Fehler beim Budget-Tracking: %s", e)

    # Registriere den Callback
    litellm.success_callback = [_budget_tracking_callback]
    logger.info("litellm.success_callback: Budget-Tracking Callback erfolgreich registriert (Thread-Safe)")

except ImportError:
    logger.warning("litellm.success_callback: LiteLLM nicht verfuegbar - Budget-Tracking deaktiviert")
