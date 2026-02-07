# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 01.02.2026
Version: 1.0
Beschreibung: Model Router Health-Check Funktionen.
              Extrahiert aus model_router.py (Regel 1: Max 500 Zeilen)

              Enthält:
              - check_model_health (async und sync)
              - mark_permanently_unavailable
              - reactivate_model
              - recheck_unavailable_models
              - health_check_all_primary_models
              - get_health_status
"""

import time
import asyncio
from typing import Dict, Any, Tuple

from logger_utils import log_event

# LiteLLM Import für Health-Check
try:
    import litellm
    LITELLM_AVAILABLE = True
except ImportError:
    LITELLM_AVAILABLE = False


def parse_health_check_error(model: str, exception: Exception) -> Tuple[bool, str]:
    """
    Kernlogik für Health-Check Error-Parsing.

    Args:
        model: Modell-ID das geprüft wurde
        exception: Die aufgetretene Exception

    Returns:
        Tuple (available, reason)
    """
    error_str = str(exception).lower()
    error_type = type(exception).__name__.lower()

    # 404 / Not Found = Permanent unavailable (z.B. "free period ended")
    if "404" in error_str or "not found" in error_str or "notfounderror" in error_type:
        reason = str(exception)[:200]
        log_event("ModelRouter", "HealthCheck",
                  f"Modell {model} ist PERMANENT nicht verfuegbar: {reason[:100]}")
        return (False, reason)

    # 402 / Spend Limit = Temporaer (API-Key Problem, nicht Modell-Problem)
    if "402" in error_str or "spend limit" in error_str or "payment required" in error_str:
        log_event("ModelRouter", "HealthCheck",
                  f"Modell {model}: API-Key Spend-Limit erreicht (402)")
        return (True, "spend_limit_exceeded")

    # 429 / Rate Limit = Temporär, Modell existiert aber ist gerade limitiert
    if "429" in error_str or "rate" in error_str or "ratelimiterror" in error_type:
        log_event("ModelRouter", "HealthCheck",
                  f"Modell {model} hat Rate-Limit (aber existiert)")
        return (True, "rate_limited")

    # Andere Fehler: Als temporär behandeln (vorsichtshalber)
    log_event("ModelRouter", "HealthCheck",
              f"Modell {model} unbekannter Fehler: {str(exception)[:100]}")
    return (True, f"unknown_error: {str(exception)[:100]}")


async def check_model_health_async(model: str) -> Tuple[bool, str]:
    """
    Prueft ob ein Modell verfuegbar ist durch minimalen API-Call (async).

    Args:
        model: Modell-ID

    Returns:
        Tuple (available, reason)
    """
    if not LITELLM_AVAILABLE:
        log_event("ModelRouter", "Warning", "LiteLLM nicht verfuegbar fuer Health-Check")
        return (True, "litellm_not_available")
    if not model:
        return (False, "empty_model_id")

    try:
        await litellm.acompletion(
            model=model,
            messages=[{"role": "user", "content": "Hi"}],
            max_tokens=1,
            timeout=15
        )
        log_event("ModelRouter", "HealthCheck", f"Modell {model} ist verfuegbar")
        return (True, "OK")
    except Exception as e:
        return parse_health_check_error(model, e)


def check_model_health_sync(model: str) -> Tuple[bool, str]:
    """
    Synchrone Version des Health-Checks (fuer Startup).

    Args:
        model: Modell-ID

    Returns:
        Tuple (available, reason)
    """
    if not LITELLM_AVAILABLE:
        return (True, "litellm_not_available")
    if not model:
        return (False, "empty_model_id")

    try:
        litellm.completion(
            model=model,
            messages=[{"role": "user", "content": "Hi"}],
            max_tokens=1,
            timeout=15
        )
        log_event("ModelRouter", "HealthCheck", f"Modell {model} ist verfuegbar")
        return (True, "OK")
    except Exception as e:
        return parse_health_check_error(model, e)


class HealthCheckManager:
    """
    Verwaltet Health-Checks für Modelle.

    Separate Klasse für bessere Testbarkeit und Modularität.
    """

    def __init__(self):
        """Initialisiert den HealthCheckManager."""
        self.permanently_unavailable: Dict[str, str] = {}  # model -> reason
        self.last_health_check: float = 0
        self.health_check_interval: int = 600  # Re-Check alle 10 Minuten
        import threading
        self._lock = threading.Lock()

    def mark_permanently_unavailable(self, model: str, reason: str) -> None:
        """
        Markiert ein Modell als dauerhaft nicht verfuegbar.

        Args:
            model: Modell-ID
            reason: Grund fuer Nicht-Verfuegbarkeit
        """
        if not model:
            return
        with self._lock:
            self.permanently_unavailable[model] = reason
        log_event("ModelRouter", "Unavailable",
                  f"Modell {model} als dauerhaft nicht verfuegbar markiert: {reason[:100]}")

    def is_permanently_unavailable(self, model: str) -> bool:
        """Prueft ob ein Modell als permanent unavailable markiert ist."""
        with self._lock:
            return model in self.permanently_unavailable

    def get_unavailable_reason(self, model: str) -> str:
        """Gibt den Grund für die Nichtverfügbarkeit zurück."""
        with self._lock:
            return self.permanently_unavailable.get(model, "")

    def reactivate_model(self, model: str) -> bool:
        """
        Reaktiviert ein zuvor als unavailable markiertes Modell.

        Args:
            model: Modell-ID

        Returns:
            True wenn Modell reaktiviert wurde, False wenn es nicht unavailable war
        """
        with self._lock:
            if model in self.permanently_unavailable:
                del self.permanently_unavailable[model]
                log_event("ModelRouter", "Reactivated", f"Modell {model} wurde reaktiviert")
                return True
        return False

    async def recheck_unavailable_models(self) -> Dict[str, bool]:
        """
        Prueft ob zuvor als unavailable markierte Modelle wieder verfuegbar sind.

        Returns:
            Dictionary {model: reactivated}
        """
        results = {}
        with self._lock:
            models_to_check = list(self.permanently_unavailable.keys())

        for model in models_to_check:
            available, reason = await check_model_health_async(model)

            if available and reason != "rate_limited":
                self.reactivate_model(model)
                results[model] = True
            else:
                results[model] = False

        self.last_health_check = time.time()
        return results

    async def health_check_all_primary_models(
        self,
        models_config: Dict[str, Any],
        delay_between_checks: float = 2.0
    ) -> Dict[str, Dict[str, Any]]:
        """
        Fuehrt Health-Check fuer alle Primary-Modelle aller Rollen durch.

        Args:
            models_config: Model-Konfiguration für einen Mode
            delay_between_checks: Sekunden zwischen Checks

        Returns:
            Dictionary {role: {model, available, reason}}
        """
        results = {}
        checked_models: Dict[str, Tuple[bool, str]] = {}

        for role, model_config in models_config.items():
            if isinstance(model_config, dict):
                primary = model_config.get("primary", "")
                if primary:
                    # Pruefe ob Modell bereits gecheckt wurde
                    if primary in checked_models:
                        available, reason = checked_models[primary]
                        log_event("ModelRouter", "HealthCheck",
                                  f"Modell {primary} bereits geprueft (uebersprungen)")
                    else:
                        # Delay zwischen Checks
                        if checked_models:
                            await asyncio.sleep(delay_between_checks)
                        available, reason = await check_model_health_async(primary)
                        checked_models[primary] = (available, reason)

                    results[role] = {
                        "model": primary,
                        "available": available,
                        "reason": reason
                    }

                    # Bei permanent unavailable automatisch markieren
                    if not available and "not found" in reason.lower():
                        self.mark_permanently_unavailable(primary, reason)

        self.last_health_check = time.time()
        return results

    def get_health_status(self) -> Dict[str, Any]:
        """
        Gibt den aktuellen Health-Status aller Modelle zurueck.

        Returns:
            Dictionary mit verfuegbaren und unavailable Modellen
        """
        with self._lock:
            perm_unav = dict(self.permanently_unavailable)
            unav_count = len(self.permanently_unavailable)

        return {
            "permanently_unavailable": perm_unav,
            "unavailable_count": unav_count,
            "last_health_check": self.last_health_check,
            "health_check_interval": self.health_check_interval,
            "next_recheck_in": max(0, (self.last_health_check + self.health_check_interval) - time.time())
        }

    def clear_unavailable(self) -> None:
        """Loescht alle permanently_unavailable Markierungen."""
        with self._lock:
            self.permanently_unavailable.clear()
        log_event("ModelRouter", "Info", "Alle Unavailable-Status zurückgesetzt.")


# =========================================================================
# Router Status & Clear (aus model_router.py ausgelagert)
# =========================================================================

def get_router_status(router) -> Dict[str, Any]:
    """Gibt den aktuellen Status des ModelRouters zurück."""
    from model_router_error_history import get_error_history_status
    current_time = time.time()
    rate_limited_info = {}
    for model, cooldown_until in router.rate_limited_models.items():
        remaining = max(0, int(cooldown_until - current_time))
        rate_limited_info[model] = {
            "remaining_seconds": remaining,
            "cooldown_until": cooldown_until
        }
    return {
        "rate_limited_models": rate_limited_info,
        "usage_stats": router.model_usage_stats,
        "cooldown_seconds": router.cooldown_seconds,
        "error_history": get_error_history_status(router),
        "health_status": router._health_manager.get_health_status()
    }


def clear_router_rate_limits(router, include_permanently_unavailable: bool = False) -> None:
    """Löscht alle Rate-Limit-Markierungen."""
    router.rate_limited_models.clear()
    router.model_failure_count.clear()
    router.all_paused_count = 0
    router.error_model_history.clear()
    if include_permanently_unavailable:
        router._health_manager.clear_unavailable()
        log_event("ModelRouter", "Info", "Alle Limits und Unavailable-Status zurückgesetzt.")
    else:
        log_event("ModelRouter", "Info", "Alle Rate-Limits und Fehler-Historie zurückgesetzt.")
