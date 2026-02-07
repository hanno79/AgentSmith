# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 02.02.2026
Version: 1.0
Beschreibung: Model Router Error-Historie (get_model_for_error, mark_error_tried, clear, status).
              Extrahiert aus model_router.py (Regel 1: Max 500 Zeilen).

# ÄNDERUNG [02.02.2026]: Extraktion aus model_router.py – Error-Historie in eigenes Modul
"""

from typing import Any, Dict, Set

from logger_utils import log_event


def get_model_for_error(router, agent_role: str, error_hash: str) -> str:
    """Gibt ein Modell zurück, das diesen Fehler noch nicht versucht hat."""
    tried_models = router.error_model_history.get(error_hash, set())
    all_models = router.get_all_models_for_role(agent_role)

    available_untried = []
    rate_limited_untried = []

    for model in all_models:
        if model not in tried_models:
            if not router._is_rate_limited_sync(model):
                available_untried.append(model)
            else:
                rate_limited_untried.append(model)

    if available_untried:
        model = available_untried[0]
        log_event("ModelRouter", "ErrorHistory",
                  f"Modell {model} für Fehler {error_hash[:8]} ausgewählt")
        router._track_usage(model)
        return model

    if rate_limited_untried:
        log_event("ModelRouter", "Warning",
                  f"{len(rate_limited_untried)} Modelle rate-limited für {error_hash[:8]}")
        model = rate_limited_untried[0]
        router._track_usage(model)
        return model

    log_event("ModelRouter", "Warning",
              f"Alle Modelle haben Fehler {error_hash[:8]} versucht. Reset.")
    clear_error_history(router, error_hash)

    for model in all_models:
        if not router._is_rate_limited_sync(model):
            router._track_usage(model)
            return model

    return all_models[0] if all_models else ""


def mark_error_tried(router, error_hash: str, model: str) -> None:
    """Markiert dass ein Modell einen bestimmten Fehler versucht hat."""
    if not error_hash or not model:
        return

    if error_hash not in router.error_model_history:
        router.error_model_history[error_hash] = set()

    router.error_model_history[error_hash].add(model)
    log_event("ModelRouter", "ErrorHistory",
              f"Modell {model} für Fehler {error_hash[:8]} markiert")


def clear_error_history(router, error_hash: str = None) -> None:
    """Löscht Fehler-Historie."""
    if error_hash:
        if error_hash in router.error_model_history:
            del router.error_model_history[error_hash]
    else:
        router.error_model_history.clear()


def get_error_history_status(router) -> Dict[str, Any]:
    """Gibt den Status der Fehler-Historie zurück."""
    return {
        "total_errors_tracked": len(router.error_model_history),
        "errors": {
            eh[:12]: list(models)
            for eh, models in router.error_model_history.items()
        }
    }
