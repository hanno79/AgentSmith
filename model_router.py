# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 31.01.2026
Version: 1.3
Beschreibung: Model Router - Intelligentes Model-Routing mit Fallback bei Rate Limits.
              Automatisches Umschalten auf alternative Modelle bei temporärer Blockierung.
              AENDERUNG 31.01.2026: Fehler-Modell-Historie zur Vermeidung von Ping-Pong-Wechseln.
              AENDERUNG 31.01.2026: Fix für Model-Rotation-Bug - Trennung von rate-limited und versucht.
              AENDERUNG 31.01.2026: Proaktiver Health-Check - permanent unavailable Modelle überspringen.
"""

import time
import asyncio
import threading
from typing import Dict, List, Optional, Any, Callable, Set, Tuple
from logger_utils import log_event

# AENDERUNG 31.01.2026: LiteLLM Import für Health-Check
try:
    import litellm
    LITELLM_AVAILABLE = True
except ImportError:
    LITELLM_AVAILABLE = False


class ModelRouter:
    """
    Intelligentes Model-Routing mit Fallback bei Rate Limits.

    Unterstützt sowohl die alte Config-Struktur (String) als auch
    die neue Struktur mit primary + fallback Modellen.
    """

    # ÄNDERUNG 24.01.2026: Cooldown von 60 auf 120 Sekunden erhöht für stabilere API-Nutzung
    def __init__(self, config: Dict[str, Any], cooldown_seconds: int = 120):
        """
        Initialisiert den ModelRouter.

        Args:
            config: Anwendungskonfiguration mit mode und models
            cooldown_seconds: Sekunden, die ein rate-limited Modell pausiert wird (Standard: 120s)
        """
        self.config = config
        self.cooldown_seconds = cooldown_seconds
        self.rate_limited_models: Dict[str, float] = {}  # model -> cooldown_until timestamp
        self.model_usage_stats: Dict[str, int] = {}  # model -> usage count
        self.on_fallback: Optional[Callable[[str, str, str], None]] = None  # Callback für Fallback-Events
        self._rate_limit_lock = asyncio.Lock()  # Lock für Async-Sicherheit
        self._rate_limit_thread_lock = threading.Lock()  # Lock für Thread-Sicherheit bei sync-Methoden
        # ÄNDERUNG 28.01.2026: Exponentieller Backoff und Endlosschleifen-Schutz
        self.model_failure_count: Dict[str, int] = {}  # model -> failure count für exponentiellen Backoff
        self.all_paused_count: int = 0  # Zähler für "alle pausiert" Situationen
        # AENDERUNG 31.01.2026: Fehler-Modell-Historie zur Vermeidung von Ping-Pong-Wechseln
        self.error_model_history: Dict[str, Set[str]] = {}  # error_hash -> {tried_models}
        # AENDERUNG 31.01.2026: Proaktiver Health-Check - permanent unavailable Modelle
        self.permanently_unavailable: Dict[str, str] = {}  # model -> reason (z.B. "free period ended")
        self.last_health_check: float = 0  # Timestamp des letzten Health-Checks
        self.health_check_interval: int = 600  # Re-Check alle 10 Minuten

    def get_model(self, agent_role: str) -> str:
        """
        Gibt das beste verfügbare Modell für eine Rolle zurück.

        Args:
            agent_role: Name der Agent-Rolle (z.B. "coder", "reviewer")

        Returns:
            Modell-ID für LiteLLM
        """
        mode = self.config.get("mode", "test")
        model_config = self.config.get("models", {}).get(mode, {}).get(agent_role)

        if model_config is None:
            # Fallback auf meta_orchestrator wenn Rolle nicht gefunden
            model_config = self.config.get("models", {}).get(mode, {}).get("meta_orchestrator")
            if model_config is None:
                # Kein Modell gefunden - werfe Exception statt leerer String
                log_event("ModelRouter", "Error", f"No model config found for role '{agent_role}' or 'meta_orchestrator' in mode '{mode}'")
                raise ValueError(f"No model configuration found for role '{agent_role}' or fallback 'meta_orchestrator' in mode '{mode}'")

        # Alte Struktur (String) unterstützen
        if isinstance(model_config, str):
            self._track_usage(model_config)
            return model_config

        # Neue Struktur mit primary + fallback
        primary = model_config.get("primary", "")
        fallbacks = model_config.get("fallback", [])

        # AENDERUNG 31.01.2026: Prüfe ob Primary permanent unavailable ist
        if primary in self.permanently_unavailable:
            reason = self.permanently_unavailable[primary]
            log_event("ModelRouter", "Skip",
                      f"Primary {primary} übersprungen (unavailable: {reason[:50]})")
        else:
            # Prüfe ob Primary verfügbar (synchrone Wrapper für async _is_rate_limited)
            is_limited = self._is_rate_limited_sync(primary)

            if not is_limited:
                self._track_usage(primary)
                return primary

        # Fallback suchen
        for fallback_model in fallbacks:
            # AENDERUNG 31.01.2026: Auch Fallbacks auf permanent unavailable prüfen
            if fallback_model in self.permanently_unavailable:
                continue  # Überspringe unavailable Fallbacks

            is_limited = self._is_rate_limited_sync(fallback_model)

            if not is_limited:
                self._track_usage(fallback_model)
                self._notify_fallback(agent_role, primary, fallback_model)
                return fallback_model

        # ÄNDERUNG 28.01.2026: Endlosschleifen-Schutz wenn alle Modelle pausiert sind
        self.all_paused_count += 1

        if self.all_paused_count >= 5:
            log_event("ModelRouter", "Error",
                      f"KRITISCH: Alle Modelle für {agent_role} sind erschöpft nach {self.all_paused_count} Versuchen")
            # Reset für nächsten Versuch
            self.all_paused_count = 0
            raise RuntimeError(f"Alle Modelle für {agent_role} sind erschöpft. Bitte später erneut versuchen.")

        log_event("ModelRouter", "Warning",
                  f"Alle Modelle für {agent_role} pausiert ({self.all_paused_count}/5). Warte 30s...")
        time.sleep(30)  # Warte bevor Primary zurückgegeben wird
        return primary

    async def get_model_async(self, agent_role: str) -> str:
        """
        Async-Version: Gibt das beste verfügbare Modell für eine Rolle zurück.

        Args:
            agent_role: Name der Agent-Rolle (z.B. "coder", "reviewer")

        Returns:
            Modell-ID für LiteLLM
        """
        mode = self.config.get("mode", "test")
        model_config = self.config.get("models", {}).get(mode, {}).get(agent_role)

        if model_config is None:
            # Fallback auf meta_orchestrator wenn Rolle nicht gefunden
            model_config = self.config.get("models", {}).get(mode, {}).get("meta_orchestrator")
            if model_config is None:
                # Kein Modell gefunden - werfe Exception statt leerer String
                log_event("ModelRouter", "Error", f"No model config found for role '{agent_role}' or 'meta_orchestrator' in mode '{mode}'")
                raise ValueError(f"No model configuration found for role '{agent_role}' or fallback 'meta_orchestrator' in mode '{mode}'")

        # Alte Struktur (String) unterstützen
        if isinstance(model_config, str):
            self._track_usage(model_config)
            return model_config

        # Neue Struktur mit primary + fallback
        primary = model_config.get("primary", "")
        fallbacks = model_config.get("fallback", [])

        # AENDERUNG 31.01.2026: Prüfe ob Primary permanent unavailable ist (async)
        if primary in self.permanently_unavailable:
            reason = self.permanently_unavailable[primary]
            log_event("ModelRouter", "Skip",
                      f"Primary {primary} übersprungen (unavailable: {reason[:50]})")
        else:
            # Prüfe ob Primary verfügbar (async Version)
            is_limited = await self._is_rate_limited(primary)

            if not is_limited:
                self._track_usage(primary)
                return primary

        # Fallback suchen
        for fallback_model in fallbacks:
            # AENDERUNG 31.01.2026: Auch Fallbacks auf permanent unavailable prüfen
            if fallback_model in self.permanently_unavailable:
                continue  # Überspringe unavailable Fallbacks

            is_limited = await self._is_rate_limited(fallback_model)

            if not is_limited:
                self._track_usage(fallback_model)
                self._notify_fallback(agent_role, primary, fallback_model)
                return fallback_model

        # ÄNDERUNG 28.01.2026: Endlosschleifen-Schutz wenn alle Modelle pausiert sind (async)
        self.all_paused_count += 1

        if self.all_paused_count >= 5:
            log_event("ModelRouter", "Error",
                      f"KRITISCH: Alle Modelle für {agent_role} sind erschöpft nach {self.all_paused_count} Versuchen")
            # Reset für nächsten Versuch
            self.all_paused_count = 0
            raise RuntimeError(f"Alle Modelle für {agent_role} sind erschöpft. Bitte später erneut versuchen.")

        log_event("ModelRouter", "Warning",
                  f"Alle Modelle für {agent_role} pausiert ({self.all_paused_count}/5). Warte 30s...")
        await asyncio.sleep(30)  # Async-Warten bevor Primary zurückgegeben wird
        return primary

    def _is_rate_limited_sync(self, model: str) -> bool:
        """Synchrone Version für Fallback wenn kein Event Loop vorhanden."""
        if not model:
            return True
        with self._rate_limit_thread_lock:
            if model not in self.rate_limited_models:
                return False

            cooldown_until = self.rate_limited_models[model]
            if time.time() >= cooldown_until:
                del self.rate_limited_models[model]
                log_event("ModelRouter", "Info", f"Modell {model} wieder verfügbar nach Cooldown.")
                return False

            return True

    async def _is_rate_limited(self, model: str) -> bool:
        """Prüft ob ein Modell aktuell rate-limited ist (thread/async-safe)."""
        if not model:
            return True
        async with self._rate_limit_lock:
            if model not in self.rate_limited_models:
                return False

            cooldown_until = self.rate_limited_models[model]
            if time.time() >= cooldown_until:
                # Cooldown abgelaufen, Modell wieder freigeben
                del self.rate_limited_models[model]
                log_event("ModelRouter", "Info", f"Modell {model} wieder verfügbar nach Cooldown.")
                return False

            return True

    async def mark_rate_limited(self, model: str):
        """
        Markiert ein Modell als temporär nicht verfügbar (thread/async-safe).
        ÄNDERUNG 28.01.2026: Exponentieller Backoff - 30s, 60s, 120s, 240s, max 300s

        Args:
            model: Modell-ID die rate-limited wurde
        """
        async with self._rate_limit_lock:
            # Exponentieller Backoff basierend auf Fehleranzahl
            failure_count = self.model_failure_count.get(model, 0) + 1
            self.model_failure_count[model] = failure_count

            # Berechne Cooldown: 30 * 2^(failures-1), max 300s
            cooldown = min(30 * (2 ** (failure_count - 1)), 300)

            self.rate_limited_models[model] = time.time() + cooldown
            log_event("ModelRouter", "RateLimit",
                      f"Modell {model} pausiert für {cooldown}s (Fehler #{failure_count})")
    
    def mark_rate_limited_sync(self, model: str):
        """
        Synchrone Version für Fallback.
        ÄNDERUNG 28.01.2026: Exponentieller Backoff - 30s, 60s, 120s, 240s, max 300s
        """
        with self._rate_limit_thread_lock:
            # Exponentieller Backoff basierend auf Fehleranzahl
            failure_count = self.model_failure_count.get(model, 0) + 1
            self.model_failure_count[model] = failure_count

            # Berechne Cooldown: 30 * 2^(failures-1), max 300s
            cooldown = min(30 * (2 ** (failure_count - 1)), 300)

            self.rate_limited_models[model] = time.time() + cooldown
            log_event("ModelRouter", "RateLimit",
                      f"Modell {model} pausiert für {cooldown}s (Fehler #{failure_count})")

    def _track_usage(self, model: str):
        """Trackt die Nutzung eines Modells für Statistiken."""
        self.model_usage_stats[model] = self.model_usage_stats.get(model, 0) + 1

    def _notify_fallback(self, agent_role: str, primary: str, fallback: str):
        """Benachrichtigt über einen Fallback-Wechsel."""
        message = f"Agent '{agent_role}': Wechsel von {primary} auf Fallback {fallback}"
        log_event("ModelRouter", "Fallback", message)

        if self.on_fallback:
            self.on_fallback(agent_role, primary, fallback)

    def get_status(self) -> Dict[str, Any]:
        """
        Gibt den aktuellen Status des ModelRouters zurück.

        Returns:
            Dictionary mit rate-limited Modellen und Nutzungsstatistiken
        """
        current_time = time.time()
        rate_limited_info = {}

        for model, cooldown_until in self.rate_limited_models.items():
            remaining = max(0, int(cooldown_until - current_time))
            rate_limited_info[model] = {
                "remaining_seconds": remaining,
                "cooldown_until": cooldown_until
            }

        return {
            "rate_limited_models": rate_limited_info,
            "usage_stats": self.model_usage_stats,
            "cooldown_seconds": self.cooldown_seconds,
            # AENDERUNG 31.01.2026: Fehler-Historie im Status
            "error_history": self.get_error_history_status(),
            # AENDERUNG 31.01.2026: Health-Status im Status
            "health_status": self.get_health_status()
        }

    def clear_rate_limits(self, include_permanently_unavailable: bool = False):
        """
        Loescht alle Rate-Limit-Markierungen (fuer Tests oder manuelles Reset).

        Args:
            include_permanently_unavailable: Wenn True, werden auch permanent
                                            unavailable Modelle zurueckgesetzt
        """
        self.rate_limited_models.clear()
        self.model_failure_count.clear()
        self.all_paused_count = 0
        # AENDERUNG 31.01.2026: Auch Fehler-Historie loeschen bei vollem Reset
        self.error_model_history.clear()

        # AENDERUNG 31.01.2026: Optional auch permanently_unavailable zuruecksetzen
        if include_permanently_unavailable:
            self.permanently_unavailable.clear()
            log_event("ModelRouter", "Info",
                      "Alle Rate-Limits, Failure-Counter, Fehler-Historie und Unavailable-Status zurückgesetzt.")
        else:
            log_event("ModelRouter", "Info",
                      "Alle Rate-Limits, Failure-Counter und Fehler-Historie zurückgesetzt.")

    def mark_success(self, model: str):
        """
        ÄNDERUNG 28.01.2026: Markiert ein Modell als erfolgreich - resettet Failure-Counter.
        Sollte nach erfolgreichen API-Calls aufgerufen werden.

        Args:
            model: Modell-ID das erfolgreich war
        """
        with self._rate_limit_thread_lock:
            if model in self.model_failure_count:
                del self.model_failure_count[model]
                log_event("ModelRouter", "Info", f"Modell {model} erfolgreich - Failure-Counter zurückgesetzt.")
            # Reset auch den Paused-Counter wenn ein Modell erfolgreich ist
            self.all_paused_count = 0

    def get_all_models_for_role(self, agent_role: str) -> List[str]:
        """
        Gibt alle konfigurierten Modelle (primary + fallbacks) für eine Rolle zurück.

        Args:
            agent_role: Name der Agent-Rolle

        Returns:
            Liste aller Modell-IDs für diese Rolle
        """
        mode = self.config.get("mode", "test")
        model_config = self.config.get("models", {}).get(mode, {}).get(agent_role)

        if model_config is None:
            return []

        if isinstance(model_config, str):
            return [model_config]

        models = []
        if model_config.get("primary"):
            models.append(model_config["primary"])
        models.extend(model_config.get("fallback", []))

        return models

    # AENDERUNG 31.01.2026: Neue Methoden fuer Fehler-Modell-Historie

    def get_model_for_error(self, agent_role: str, error_hash: str) -> str:
        """
        Gibt ein Modell zurueck, das diesen Fehler noch nicht versucht hat.

        Verhindert Ping-Pong-Wechsel zwischen nur 2 Modellen bei persistenten Fehlern.
        Alle verfuegbaren Modelle werden der Reihe nach durchprobiert.

        AENDERUNG 31.01.2026: Trennung von "rate-limited" und "tatsaechlich versucht"
        um vorschnelles Zuruecksetzen der Historie zu verhindern.

        Args:
            agent_role: Name der Agent-Rolle (z.B. "coder")
            error_hash: Hash des Fehler-Inhalts

        Returns:
            Modell-ID die diesen Fehler noch nicht versucht hat
        """
        tried_models = self.error_model_history.get(error_hash, set())
        all_models = self.get_all_models_for_role(agent_role)

        # AENDERUNG 31.01.2026: Zaehle verfuegbare und unversuchte Modelle separat
        available_untried = []
        rate_limited_untried = []

        for model in all_models:
            if model not in tried_models:
                if not self._is_rate_limited_sync(model):
                    available_untried.append(model)
                else:
                    rate_limited_untried.append(model)

        # Fall 1: Es gibt ein verfuegbares, unversuchtes Modell
        if available_untried:
            model = available_untried[0]
            log_event("ModelRouter", "ErrorHistory",
                      f"Modell {model} fuer Fehler {error_hash[:8]} ausgewaehlt "
                      f"(bereits versucht: {len(tried_models)}/{len(all_models)})")
            self._track_usage(model)
            return model

        # Fall 2: Unversuchte Modelle existieren, aber alle sind rate-limited
        # WARTEN statt Historie loeschen!
        if rate_limited_untried:
            log_event("ModelRouter", "Warning",
                      f"{len(rate_limited_untried)} unversuchte Modelle fuer Fehler {error_hash[:8]} "
                      f"sind rate-limited. Warte auf Verfuegbarkeit...")
            # Gib das erste rate-limited Modell zurueck - es wird bald verfuegbar
            model = rate_limited_untried[0]
            self._track_usage(model)
            return model

        # Fall 3: ALLE Modelle haben diesen Fehler tatsaechlich versucht
        # NUR JETZT darf die Historie geloescht werden
        log_event("ModelRouter", "Warning",
                  f"Alle {len(all_models)} Modelle haben Fehler {error_hash[:8]} tatsaechlich versucht. "
                  f"Setze Historie zurueck und starte mit Primary.")
        self.clear_error_history(error_hash)

        # Gib Primary zurueck (oder erstes verfuegbares)
        for model in all_models:
            if not self._is_rate_limited_sync(model):
                self._track_usage(model)
                return model

        # Fallback: Primary auch wenn rate-limited
        return all_models[0] if all_models else ""

    def mark_error_tried(self, error_hash: str, model: str) -> None:
        """
        Markiert dass ein Modell einen bestimmten Fehler versucht hat.

        Args:
            error_hash: Hash des Fehler-Inhalts
            model: Modell-ID das den Fehler versucht hat
        """
        if not error_hash or not model:
            return

        if error_hash not in self.error_model_history:
            self.error_model_history[error_hash] = set()

        self.error_model_history[error_hash].add(model)
        log_event("ModelRouter", "ErrorHistory",
                  f"Modell {model} fuer Fehler {error_hash[:8]} markiert "
                  f"(insgesamt {len(self.error_model_history[error_hash])} Modelle versucht)")

    def clear_error_history(self, error_hash: str = None) -> None:
        """
        Loescht Fehler-Historie (einzeln oder komplett).

        Args:
            error_hash: Optional - nur diese Fehler-Historie loeschen.
                       Wenn None, wird die gesamte Historie geloescht.
        """
        if error_hash:
            if error_hash in self.error_model_history:
                del self.error_model_history[error_hash]
                log_event("ModelRouter", "Info", f"Fehler-Historie fuer {error_hash[:8]} geloescht.")
        else:
            self.error_model_history.clear()
            log_event("ModelRouter", "Info", "Gesamte Fehler-Historie geloescht.")

    def get_error_history_status(self) -> Dict[str, Any]:
        """
        Gibt den Status der Fehler-Historie zurueck.

        Returns:
            Dictionary mit Fehler-Hashes und versuchten Modellen
        """
        return {
            "total_errors_tracked": len(self.error_model_history),
            "errors": {
                error_hash[:12]: list(models)
                for error_hash, models in self.error_model_history.items()
            }
        }

    # =========================================================================
    # AENDERUNG 31.01.2026: Proaktiver Health-Check fuer Modelle
    # =========================================================================

    async def check_model_health(self, model: str) -> Tuple[bool, str]:
        """
        Prueft ob ein Modell verfuegbar ist durch minimalen API-Call.

        Args:
            model: Modell-ID zum Pruefen

        Returns:
            Tuple (available, reason):
            - (True, "OK") - Modell verfuegbar
            - (True, "rate_limited") - Modell verfuegbar aber gerade limitiert
            - (False, "reason") - Modell permanent nicht verfuegbar
        """
        if not LITELLM_AVAILABLE:
            log_event("ModelRouter", "Warning", "LiteLLM nicht verfuegbar fuer Health-Check")
            return (True, "litellm_not_available")

        if not model:
            return (False, "empty_model_id")

        try:
            # Minimaler Request: Nur 1 Token generieren
            response = await litellm.acompletion(
                model=model,
                messages=[{"role": "user", "content": "Hi"}],
                max_tokens=1,
                timeout=15
            )
            log_event("ModelRouter", "HealthCheck", f"Modell {model} ist verfuegbar")
            return (True, "OK")

        except Exception as e:
            error_str = str(e).lower()

            # 404 / Not Found = Permanent unavailable (z.B. "free period ended")
            if "404" in error_str or "not found" in error_str or "notfounderror" in type(e).__name__.lower():
                reason = str(e)[:200]
                log_event("ModelRouter", "HealthCheck",
                          f"Modell {model} ist PERMANENT nicht verfuegbar: {reason[:100]}")
                return (False, reason)

            # 429 / Rate Limit = Temporär, Modell existiert aber ist gerade limitiert
            if "429" in error_str or "rate" in error_str or "ratelimiterror" in type(e).__name__.lower():
                log_event("ModelRouter", "HealthCheck",
                          f"Modell {model} hat Rate-Limit (aber existiert)")
                return (True, "rate_limited")

            # Andere Fehler: Als temporär behandeln (vorsichtshalber)
            log_event("ModelRouter", "HealthCheck",
                      f"Modell {model} unbekannter Fehler: {str(e)[:100]}")
            return (True, f"unknown_error: {str(e)[:100]}")

    def check_model_health_sync(self, model: str) -> Tuple[bool, str]:
        """Synchrone Version des Health-Checks (fuer Startup)."""
        if not LITELLM_AVAILABLE:
            return (True, "litellm_not_available")

        if not model:
            return (False, "empty_model_id")

        try:
            # Synchroner Aufruf mit litellm.completion
            response = litellm.completion(
                model=model,
                messages=[{"role": "user", "content": "Hi"}],
                max_tokens=1,
                timeout=15
            )
            log_event("ModelRouter", "HealthCheck", f"Modell {model} ist verfuegbar")
            return (True, "OK")

        except Exception as e:
            error_str = str(e).lower()

            if "404" in error_str or "not found" in error_str or "notfounderror" in type(e).__name__.lower():
                reason = str(e)[:200]
                log_event("ModelRouter", "HealthCheck",
                          f"Modell {model} ist PERMANENT nicht verfuegbar: {reason[:100]}")
                return (False, reason)

            if "429" in error_str or "rate" in error_str or "ratelimiterror" in type(e).__name__.lower():
                log_event("ModelRouter", "HealthCheck",
                          f"Modell {model} hat Rate-Limit (aber existiert)")
                return (True, "rate_limited")

            log_event("ModelRouter", "HealthCheck",
                      f"Modell {model} unbekannter Fehler: {str(e)[:100]}")
            return (True, f"unknown_error: {str(e)[:100]}")

    def mark_permanently_unavailable(self, model: str, reason: str) -> None:
        """
        Markiert ein Modell als dauerhaft nicht verfuegbar.

        Args:
            model: Modell-ID
            reason: Grund fuer Nicht-Verfuegbarkeit
        """
        if not model:
            return

        self.permanently_unavailable[model] = reason
        log_event("ModelRouter", "Unavailable",
                  f"Modell {model} als dauerhaft nicht verfuegbar markiert: {reason[:100]}")

    def is_permanently_unavailable(self, model: str) -> bool:
        """Prueft ob ein Modell als permanent unavailable markiert ist."""
        return model in self.permanently_unavailable

    def reactivate_model(self, model: str) -> bool:
        """
        Reaktiviert ein zuvor als unavailable markiertes Modell.

        Args:
            model: Modell-ID

        Returns:
            True wenn Modell reaktiviert wurde, False wenn es nicht unavailable war
        """
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

        for model in list(self.permanently_unavailable.keys()):
            available, reason = await self.check_model_health(model)

            if available and reason != "rate_limited":
                self.reactivate_model(model)
                results[model] = True
            else:
                results[model] = False

        self.last_health_check = time.time()
        return results

    async def health_check_all_primary_models(self) -> Dict[str, Dict[str, Any]]:
        """
        Fuehrt Health-Check fuer alle Primary-Modelle aller Rollen durch.

        Returns:
            Dictionary {role: {model, available, reason}}
        """
        mode = self.config.get("mode", "test")
        models_config = self.config.get("models", {}).get(mode, {})
        results = {}

        for role, model_config in models_config.items():
            if isinstance(model_config, dict):
                primary = model_config.get("primary", "")
                if primary:
                    available, reason = await self.check_model_health(primary)
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
        return {
            "permanently_unavailable": dict(self.permanently_unavailable),
            "unavailable_count": len(self.permanently_unavailable),
            "last_health_check": self.last_health_check,
            "health_check_interval": self.health_check_interval,
            "next_recheck_in": max(0, (self.last_health_check + self.health_check_interval) - time.time())
        }


# Singleton-Instanz für globalen Zugriff
_router_instance: Optional[ModelRouter] = None


def get_model_router(config: Dict[str, Any] = None) -> ModelRouter:
    """
    Gibt die globale ModelRouter-Instanz zurück oder erstellt eine neue.

    Args:
        config: Konfiguration (nur bei erster Initialisierung benötigt)

    Returns:
        ModelRouter-Instanz
    """
    global _router_instance

    if _router_instance is None:
        if config is None:
            raise ValueError("Config erforderlich bei erster Initialisierung")
        _router_instance = ModelRouter(config)
    elif config is not None:
        # Update config wenn bereitgestellt
        _router_instance.config = config

    return _router_instance


def reset_model_router():
    """Setzt die globale ModelRouter-Instanz zurück (für Tests)."""
    global _router_instance
    _router_instance = None
