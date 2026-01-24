# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 24.01.2026
Version: 1.0
Beschreibung: Model Router - Intelligentes Model-Routing mit Fallback bei Rate Limits.
              Automatisches Umschalten auf alternative Modelle bei temporärer Blockierung.
"""

import time
import asyncio
import threading
from typing import Dict, List, Optional, Any, Callable
from logger_utils import log_event


class ModelRouter:
    """
    Intelligentes Model-Routing mit Fallback bei Rate Limits.

    Unterstützt sowohl die alte Config-Struktur (String) als auch
    die neue Struktur mit primary + fallback Modellen.
    """

    def __init__(self, config: Dict[str, Any], cooldown_seconds: int = 60):
        """
        Initialisiert den ModelRouter.

        Args:
            config: Anwendungskonfiguration mit mode und models
            cooldown_seconds: Sekunden, die ein rate-limited Modell pausiert wird
        """
        self.config = config
        self.cooldown_seconds = cooldown_seconds
        self.rate_limited_models: Dict[str, float] = {}  # model -> cooldown_until timestamp
        self.model_usage_stats: Dict[str, int] = {}  # model -> usage count
        self.on_fallback: Optional[Callable[[str, str, str], None]] = None  # Callback für Fallback-Events
        self._rate_limit_lock = asyncio.Lock()  # Lock für Async-Sicherheit
        self._rate_limit_thread_lock = threading.Lock()  # Lock für Thread-Sicherheit bei sync-Methoden

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

        # Alle rate-limited? Gib Primary zurück (wird beim nächsten Aufruf erneut versucht)
        log_event("ModelRouter", "Warning", f"Alle Modelle für {agent_role} sind rate-limited. Verwende Primary.")
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

        # Alle rate-limited? Gib Primary zurück (wird beim nächsten Aufruf erneut versucht)
        log_event("ModelRouter", "Warning", f"Alle Modelle für {agent_role} sind rate-limited. Verwende Primary.")
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

        Args:
            model: Modell-ID die rate-limited wurde
        """
        async with self._rate_limit_lock:
            self.rate_limited_models[model] = time.time() + self.cooldown_seconds
            log_event("ModelRouter", "RateLimit", f"Modell {model} für {self.cooldown_seconds}s pausiert.")
    
    def mark_rate_limited_sync(self, model: str):
        """Synchrone Version für Fallback."""
        with self._rate_limit_thread_lock:
            self.rate_limited_models[model] = time.time() + self.cooldown_seconds
            log_event("ModelRouter", "RateLimit", f"Modell {model} für {self.cooldown_seconds}s pausiert.")

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
            "cooldown_seconds": self.cooldown_seconds
        }

    def clear_rate_limits(self):
        """Löscht alle Rate-Limit-Markierungen (für Tests oder manuelles Reset)."""
        self.rate_limited_models.clear()
        log_event("ModelRouter", "Info", "Alle Rate-Limits zurückgesetzt.")

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
