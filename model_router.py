# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 24.01.2026
Version: 1.1
Beschreibung: Model Router - Intelligentes Model-Routing mit Fallback bei Rate Limits.
              Automatisches Umschalten auf alternative Modelle bei temporärer Blockierung.
              AENDERUNG 31.01.2026: Fehler-Modell-Historie zur Vermeidung von Ping-Pong-Wechseln.
"""

import time
import asyncio
import threading
from typing import Dict, List, Optional, Any, Callable, Set
from logger_utils import log_event


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

        # Prüfe ob Primary verfügbar (synchrone Wrapper für async _is_rate_limited)
        is_limited = self._is_rate_limited_sync(primary)
        
        if not is_limited:
            self._track_usage(primary)
            return primary

        # Fallback suchen
        for fallback_model in fallbacks:
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

        # Prüfe ob Primary verfügbar (async Version)
        is_limited = await self._is_rate_limited(primary)
        
        if not is_limited:
            self._track_usage(primary)
            return primary

        # Fallback suchen
        for fallback_model in fallbacks:
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
            "error_history": self.get_error_history_status()
        }

    def clear_rate_limits(self):
        """Löscht alle Rate-Limit-Markierungen (für Tests oder manuelles Reset)."""
        self.rate_limited_models.clear()
        self.model_failure_count.clear()
        self.all_paused_count = 0
        # AENDERUNG 31.01.2026: Auch Fehler-Historie loeschen bei vollem Reset
        self.error_model_history.clear()
        log_event("ModelRouter", "Info", "Alle Rate-Limits, Failure-Counter und Fehler-Historie zurückgesetzt.")

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

        Args:
            agent_role: Name der Agent-Rolle (z.B. "coder")
            error_hash: Hash des Fehler-Inhalts

        Returns:
            Modell-ID die diesen Fehler noch nicht versucht hat
        """
        tried_models = self.error_model_history.get(error_hash, set())
        all_models = self.get_all_models_for_role(agent_role)

        # Finde erstes Modell das diesen Fehler noch nicht versucht hat
        for model in all_models:
            if model not in tried_models and not self._is_rate_limited_sync(model):
                log_event("ModelRouter", "ErrorHistory",
                          f"Modell {model} fuer Fehler {error_hash[:8]} ausgewaehlt "
                          f"(bereits versucht: {len(tried_models)}/{len(all_models)})")
                self._track_usage(model)
                return model

        # Alle Modelle haben diesen Fehler versucht
        log_event("ModelRouter", "Warning",
                  f"Alle {len(all_models)} Modelle haben Fehler {error_hash[:8]} bereits versucht. "
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
