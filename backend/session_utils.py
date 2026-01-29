# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 29.01.2026
Version: 1.0
Beschreibung: Hilfsfunktionen für Session Manager.
"""
# ÄNDERUNG 29.01.2026: Lazy-Loader für Session Manager ausgelagert

from .api_logging import log_event

# Lazy-load Session Manager
_session_manager = None


def get_session_manager_instance():
    """Lazy-load des Session Managers."""
    global _session_manager
    if _session_manager is None:
        try:
            from .session_manager import get_session_manager
            _session_manager = get_session_manager()
        except Exception as e:
            log_event("API", "Error", f"Session Manager konnte nicht geladen werden: {e}")
            return None
    return _session_manager
