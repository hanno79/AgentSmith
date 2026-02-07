# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 02.02.2026
Version: 2.2
Beschreibung: Model Router - Intelligentes Model-Routing mit Fallback bei Rate Limits.
              REFAKTORIERT: Health-Check-Logik nach model_router_health.py ausgelagert.

              AENDERUNG 02.02.2026 v2.2: Dynamischer OpenRouter-Fallback - Wenn alle konfigurierten
                                         Modelle erschoepft, automatisch beliebige verfuegbare
                                         Modelle von OpenRouter API holen.
              AENDERUNG 01.02.2026 v2.1: Extended-Fallbacks - Wenn alle Top-Modelle erschoepft,
                                         automatisch weitere Modelle aus extended_fallback nutzen.
              AENDERUNG 01.02.2026: Aufsplitten in 2 Module (Regel 1: Max 500 Zeilen).
              AENDERUNG 31.01.2026: Fehler-Modell-Historie zur Vermeidung von Ping-Pong-Wechseln.
              AENDERUNG 31.01.2026: Fix fuer Model-Rotation-Bug.
              AENDERUNG 31.01.2026: Proaktiver Health-Check - permanent unavailable Modelle ueberspringen.
              AENDERUNG 31.01.2026: Refactoring - Gemeinsame Kernlogik fuer Sync/Async.
              AENDERUNG 31.01.2026: 402 Spend-Limit Erkennung.
"""

import time
import asyncio
import threading
from typing import Dict, List, Optional, Any, Callable, Set, Tuple
from logger_utils import log_event

# Health-Check Modul importieren
from model_router_health import (
    HealthCheckManager,
    check_model_health_async,
    check_model_health_sync,
    parse_health_check_error,
    get_router_status,
    clear_router_rate_limits,
    LITELLM_AVAILABLE
)
from model_router_error_history import (
    get_model_for_error as _get_model_for_error,
    mark_error_tried as _mark_error_tried,
    clear_error_history as _clear_error_history,
    get_error_history_status as _get_error_history_status,
)


class ModelRouter:
    """
    Intelligentes Model-Routing mit Fallback bei Rate Limits.

    Unterstützt sowohl die alte Config-Struktur (String) als auch
    die neue Struktur mit primary + fallback Modellen.
    """

    def __init__(self, config: Dict[str, Any], cooldown_seconds: int = 120):
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
        self.on_fallback: Optional[Callable[[str, str, str], None]] = None
        self._rate_limit_lock = asyncio.Lock()
        self._rate_limit_thread_lock = threading.Lock()
        self.model_failure_count: Dict[str, int] = {}
        self.all_paused_count: int = 0
        self.error_model_history: Dict[str, Set[str]] = {}

        # Health-Check Manager (delegiert an separates Modul)
        self._health_manager = HealthCheckManager()

    # =========================================================================
    # Properties für Rückwärtskompatibilität mit Health-Manager
    # =========================================================================

    @property
    def permanently_unavailable(self) -> Dict[str, str]:
        """Rückwärtskompatibilität: Zugriff auf permanently_unavailable."""
        return self._health_manager.permanently_unavailable

    @property
    def last_health_check(self) -> float:
        """Rückwärtskompatibilität: Zugriff auf last_health_check."""
        return self._health_manager.last_health_check

    @property
    def health_check_interval(self) -> int:
        """Rückwärtskompatibilität: Zugriff auf health_check_interval."""
        return self._health_manager.health_check_interval

    # =========================================================================
    # AENDERUNG 02.02.2026: Free-Tier Budget-Schutz
    # =========================================================================

    def _is_free_tier_mode(self) -> bool:
        """Prüft ob der aktuelle Mode ein Free-Tier ist (mode=test)."""
        return self.config.get("mode", "test") == "test"

    def _validate_model_for_mode(self, model: str) -> bool:
        """
        BUDGET-SCHUTZ: Stellt sicher dass im Free-Tier nur :free Modelle verwendet werden.

        AENDERUNG 02.02.2026: Sicherheitsmassnahme gegen unbeabsichtigte Kosten.

        Args:
            model: Die Modell-ID die validiert werden soll

        Returns:
            True wenn das Modell im aktuellen Mode erlaubt ist
        """
        if not self._is_free_tier_mode():
            return True  # In production/premium sind alle Modelle erlaubt

        # Im Test-Modus NUR :free Modelle erlauben
        if not model.endswith(":free"):
            log_event("ModelRouter", "BUDGET_PROTECTION",
                      f"BLOCKIERT: {model} ist kein Free-Modell im Test-Modus!")
            return False
        return True

    # =========================================================================
    # Kernlogik: Model-Auswahl
    # =========================================================================

    def _get_model_core(self, agent_role: str) -> Tuple[Any, str, List[str], List[str], str]:
        """
        Kernlogik für Modell-Konfiguration auslesen.

        Returns:
            Tuple (model_config, primary, fallbacks, extended_fallbacks, mode)

        AENDERUNG 01.02.2026: Extended-Fallbacks hinzugefuegt
        """
        mode = self.config.get("mode", "test")
        model_config = self.config.get("models", {}).get(mode, {}).get(agent_role)

        if model_config is None:
            model_config = self.config.get("models", {}).get(mode, {}).get("meta_orchestrator")
            if model_config is None:
                log_event("ModelRouter", "Error",
                          f"No model config found for role '{agent_role}' in mode '{mode}'")
                raise ValueError(f"No model configuration found for role '{agent_role}'")

        if isinstance(model_config, str):
            return (model_config, model_config, [], [], mode)

        primary = model_config.get("primary", "")
        fallbacks = model_config.get("fallback", [])
        # AENDERUNG 01.02.2026: Extended-Fallbacks wenn alle Top-Modelle erschoepft
        extended_fallbacks = model_config.get("extended_fallback", [])
        return (model_config, primary, fallbacks, extended_fallbacks, mode)

    def get_model(self, agent_role: str) -> str:
        """
        Gibt das beste verfügbare Modell für eine Rolle zurück (sync).

        Args:
            agent_role: Name der Agent-Rolle

        Returns:
            Modell-ID für LiteLLM
        """
        model_config, primary, fallbacks, extended_fallbacks, mode = self._get_model_core(agent_role)

        if isinstance(model_config, str):
            self._track_usage(model_config)
            return model_config

        # Prüfe ob Primary permanent unavailable ist
        if self._health_manager.is_permanently_unavailable(primary):
            reason = self._health_manager.get_unavailable_reason(primary)
            log_event("ModelRouter", "Skip",
                      f"Primary {primary} übersprungen (unavailable: {reason[:50]})")
        else:
            if not self._is_rate_limited_sync(primary):
                self._track_usage(primary)
                return primary

        # Fallback suchen
        for fallback_model in fallbacks:
            if self._health_manager.is_permanently_unavailable(fallback_model):
                continue

            if not self._is_rate_limited_sync(fallback_model):
                self._track_usage(fallback_model)
                self._notify_fallback(agent_role, primary, fallback_model)
                return fallback_model

        # AENDERUNG 01.02.2026: Extended-Fallbacks versuchen wenn alle Top-Modelle erschoepft
        for ext_model in extended_fallbacks:
            if self._health_manager.is_permanently_unavailable(ext_model):
                continue

            if not self._is_rate_limited_sync(ext_model):
                self._track_usage(ext_model)
                log_event("ModelRouter", "ExtendedFallback",
                          f"Nutze Extended-Fallback fuer {agent_role}: {ext_model}")
                self._notify_fallback(agent_role, primary, ext_model)
                return ext_model

        # AENDERUNG 02.02.2026: Dynamischer OpenRouter-Fallback als letzte Option
        dynamic_model = self._get_dynamic_openrouter_fallback_sync(agent_role)
        if dynamic_model:
            self._notify_fallback(agent_role, primary, dynamic_model)
            return dynamic_model

        return self._handle_all_paused(agent_role, primary)

    def get_token_limit(self, agent_role: str, default: int = 4096) -> int:
        """
        Gibt das Token-Limit für eine Agent-Rolle zurück.

        ÄNDERUNG 03.02.2026: Feature 10a - Konfigurierbare Token-Limits.
        Liest aus config.yaml -> token_limits -> {agent_role}

        Args:
            agent_role: Name der Agent-Rolle (z.B. 'coder', 'tester')
            default: Default-Wert wenn nicht konfiguriert

        Returns:
            max_output_tokens für LLM-Aufrufe
        """
        token_limits = self.config.get("token_limits", {})

        # Erst spezifisches Limit für Rolle suchen
        if agent_role in token_limits:
            return token_limits[agent_role]

        # Dann Default aus Config
        if "default" in token_limits:
            return token_limits["default"]

        # Zuletzt Parameter-Default
        return default

    async def get_model_async(self, agent_role: str) -> str:
        """
        Async-Version: Gibt das beste verfügbare Modell zurück.

        Args:
            agent_role: Name der Agent-Rolle

        Returns:
            Modell-ID für LiteLLM
        """
        model_config, primary, fallbacks, extended_fallbacks, mode = self._get_model_core(agent_role)

        if isinstance(model_config, str):
            self._track_usage(model_config)
            return model_config

        # Prüfe ob Primary permanent unavailable ist
        if self._health_manager.is_permanently_unavailable(primary):
            reason = self._health_manager.get_unavailable_reason(primary)
            log_event("ModelRouter", "Skip",
                      f"Primary {primary} übersprungen (unavailable: {reason[:50]})")
        else:
            if not await self._is_rate_limited(primary):
                self._track_usage(primary)
                return primary

        # Fallback suchen
        for fallback_model in fallbacks:
            if self._health_manager.is_permanently_unavailable(fallback_model):
                continue

            if not await self._is_rate_limited(fallback_model):
                self._track_usage(fallback_model)
                self._notify_fallback(agent_role, primary, fallback_model)
                return fallback_model

        # AENDERUNG 01.02.2026: Extended-Fallbacks versuchen wenn alle Top-Modelle erschoepft
        for ext_model in extended_fallbacks:
            if self._health_manager.is_permanently_unavailable(ext_model):
                continue

            if not await self._is_rate_limited(ext_model):
                self._track_usage(ext_model)
                log_event("ModelRouter", "ExtendedFallback",
                          f"Nutze Extended-Fallback fuer {agent_role}: {ext_model}")
                self._notify_fallback(agent_role, primary, ext_model)
                return ext_model

        # AENDERUNG 02.02.2026: Dynamischer OpenRouter-Fallback als letzte Option
        dynamic_model = await self._get_dynamic_openrouter_fallback(agent_role)
        if dynamic_model:
            self._notify_fallback(agent_role, primary, dynamic_model)
            return dynamic_model

        return await self._handle_all_paused_async(agent_role, primary)

    def _handle_all_paused(self, agent_role: str, primary: str) -> str:
        """Behandelt den Fall wenn alle Modelle pausiert sind (sync)."""
        self.all_paused_count += 1

        if self.all_paused_count >= 5:
            log_event("ModelRouter", "Error",
                      f"KRITISCH: Alle Modelle für {agent_role} sind erschöpft")
            self.all_paused_count = 0
            raise RuntimeError(f"Alle Modelle für {agent_role} sind erschöpft.")

        log_event("ModelRouter", "Warning",
                  f"Alle Modelle für {agent_role} pausiert ({self.all_paused_count}/5). Warte 30s...")
        time.sleep(30)
        return primary

    async def _handle_all_paused_async(self, agent_role: str, primary: str) -> str:
        """Behandelt den Fall wenn alle Modelle pausiert sind (async)."""
        self.all_paused_count += 1

        if self.all_paused_count >= 5:
            log_event("ModelRouter", "Error",
                      f"KRITISCH: Alle Modelle für {agent_role} sind erschöpft")
            self.all_paused_count = 0
            raise RuntimeError(f"Alle Modelle für {agent_role} sind erschöpft.")

        log_event("ModelRouter", "Warning",
                  f"Alle Modelle für {agent_role} pausiert ({self.all_paused_count}/5). Warte 30s...")
        await asyncio.sleep(30)
        return primary

    # =========================================================================
    # Dynamischer OpenRouter-Fallback (AENDERUNG 02.02.2026)
    # =========================================================================

    async def _get_dynamic_openrouter_fallback(self, agent_role: str) -> Optional[str]:
        """
        Holt dynamisch ein verfuegbares Modell von OpenRouter wenn alle
        vordefinierten Modelle erschoepft sind.

        AENDERUNG 02.02.2026: Neues Feature fuer automatischen Fallback
        auf beliebige OpenRouter-Modelle.

        Priorisiert nach:
        1. Kostenlose Modelle zuerst
        2. Nach Context-Length sortiert
        3. Modelle die nicht rate-limited sind

        Args:
            agent_role: Name der Agent-Rolle (fuer Logging)

        Returns:
            Modell-ID oder None wenn keins verfuegbar
        """
        try:
            # Import hier um zirkulaere Imports zu vermeiden
            from backend.routers.config import fetch_openrouter_models

            models_data = await fetch_openrouter_models()
            free_models = models_data.get("free_models", [])
            paid_models = models_data.get("paid_models", [])

            # AENDERUNG 02.02.2026: Budget-Schutz - Im Test-Modus NUR free_models!
            if self._is_free_tier_mode():
                all_models = sorted(
                    free_models,
                    key=lambda x: x.get("context_length", 0),
                    reverse=True
                )
                log_event("ModelRouter", "BudgetProtection",
                          f"Free-Tier Modus: Nur {len(free_models)} kostenlose Modelle verfuegbar")
            else:
                # Kostenlose Modelle zuerst, dann kostenpflichtige
                # Sortiert nach Context-Length (groessere zuerst)
                all_models = sorted(
                    free_models + paid_models,
                    key=lambda x: x.get("context_length", 0),
                    reverse=True
                )

            for model_data in all_models:
                model_id = model_data.get("id", "")
                if not model_id:
                    continue

                # Pruefen ob verfuegbar
                if self._health_manager.is_permanently_unavailable(model_id):
                    continue

                if not self._is_rate_limited_sync(model_id):
                    self._track_usage(model_id)
                    log_event("ModelRouter", "DynamicFallback",
                              f"Dynamischer Fallback fuer {agent_role}: {model_id}")
                    return model_id

            log_event("ModelRouter", "Warning",
                      f"Kein dynamischer Fallback verfuegbar fuer {agent_role}")
            return None

        except Exception as e:
            log_event("ModelRouter", "Error",
                      f"Dynamischer Fallback fehlgeschlagen: {e}")
            return None

    def _get_dynamic_openrouter_fallback_sync(self, agent_role: str) -> Optional[str]:
        """
        Synchrone Version des dynamischen OpenRouter-Fallbacks.

        AENDERUNG 02.02.2026: Sync-Wrapper fuer async Methode.

        Args:
            agent_role: Name der Agent-Rolle

        Returns:
            Modell-ID oder None wenn keins verfuegbar
        """
        try:
            import concurrent.futures

            # Neuen Event Loop in separatem Thread ausfuehren
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(
                    asyncio.run,
                    self._get_dynamic_openrouter_fallback(agent_role)
                )
                return future.result(timeout=15)

        except concurrent.futures.TimeoutError:
            log_event("ModelRouter", "Warning",
                      f"Dynamischer Fallback Timeout fuer {agent_role}")
            return None
        except Exception as e:
            log_event("ModelRouter", "Error",
                      f"Sync dynamischer Fallback fehlgeschlagen: {e}")
            return None

    # =========================================================================
    # Rate-Limiting
    # =========================================================================

    def _is_rate_limited_sync(self, model: str) -> bool:
        """Synchrone Version für Rate-Limit Check."""
        if not model:
            return True
        with self._rate_limit_thread_lock:
            if model not in self.rate_limited_models:
                return False

            cooldown_until = self.rate_limited_models[model]
            if time.time() >= cooldown_until:
                del self.rate_limited_models[model]
                log_event("ModelRouter", "Info", f"Modell {model} wieder verfügbar.")
                return False

            return True

    async def _is_rate_limited(self, model: str) -> bool:
        """Async Version für Rate-Limit Check."""
        if not model:
            return True
        async with self._rate_limit_lock:
            if model not in self.rate_limited_models:
                return False

            cooldown_until = self.rate_limited_models[model]
            if time.time() >= cooldown_until:
                del self.rate_limited_models[model]
                log_event("ModelRouter", "Info", f"Modell {model} wieder verfügbar.")
                return False

            return True

    def _mark_rate_limited_core(self, model: str) -> int:
        """Kernlogik für Rate-Limit Markierung (ohne Lock)."""
        failure_count = self.model_failure_count.get(model, 0) + 1
        self.model_failure_count[model] = failure_count
        cooldown = min(30 * (2 ** (failure_count - 1)), 300)
        self.rate_limited_models[model] = time.time() + cooldown
        log_event("ModelRouter", "RateLimit",
                  f"Modell {model} pausiert für {cooldown}s (Fehler #{failure_count})")
        return cooldown

    async def mark_rate_limited(self, model: str):
        """Markiert ein Modell als temporär nicht verfügbar (async)."""
        async with self._rate_limit_lock:
            self._mark_rate_limited_core(model)

    def mark_rate_limited_sync(self, model: str):
        """Markiert ein Modell als temporär nicht verfügbar (sync)."""
        with self._rate_limit_thread_lock:
            self._mark_rate_limited_core(model)

    # =========================================================================
    # Utilities
    # =========================================================================

    def _track_usage(self, model: str):
        """Trackt die Nutzung eines Modells."""
        self.model_usage_stats[model] = self.model_usage_stats.get(model, 0) + 1

    def _notify_fallback(self, agent_role: str, primary: str, fallback: str):
        """Benachrichtigt über einen Fallback-Wechsel."""
        message = f"Agent '{agent_role}': Wechsel von {primary} auf {fallback}"
        log_event("ModelRouter", "Fallback", message)

        if self.on_fallback:
            self.on_fallback(agent_role, primary, fallback)

    def mark_success(self, model: str):
        """Markiert ein Modell als erfolgreich - resettet Failure-Counter."""
        with self._rate_limit_thread_lock:
            if model in self.model_failure_count:
                del self.model_failure_count[model]
                log_event("ModelRouter", "Info", f"Modell {model} erfolgreich - Counter zurückgesetzt.")
            self.all_paused_count = 0

    def get_all_models_for_role(self, agent_role: str) -> List[str]:
        """Gibt alle konfigurierten Modelle für eine Rolle zurück."""
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

    # =========================================================================
    # Error History (delegiert an model_router_error_history)
    # =========================================================================

    def get_model_for_error(self, agent_role: str, error_hash: str) -> str:
        """Gibt ein Modell zurück, das diesen Fehler noch nicht versucht hat."""
        return _get_model_for_error(self, agent_role, error_hash)

    def mark_error_tried(self, error_hash: str, model: str) -> None:
        """Markiert dass ein Modell einen bestimmten Fehler versucht hat."""
        _mark_error_tried(self, error_hash, model)

    def clear_error_history(self, error_hash: str = None) -> None:
        """Löscht Fehler-Historie."""
        _clear_error_history(self, error_hash)

    def get_error_history_status(self) -> Dict[str, Any]:
        """Gibt den Status der Fehler-Historie zurück."""
        return _get_error_history_status(self)

    # =========================================================================
    # Status & Clear (delegiert an model_router_health)
    # =========================================================================

    def get_status(self) -> Dict[str, Any]:
        """Gibt den aktuellen Status des ModelRouters zurück."""
        return get_router_status(self)

    def clear_rate_limits(self, include_permanently_unavailable: bool = False):
        """Löscht alle Rate-Limit-Markierungen."""
        clear_router_rate_limits(self, include_permanently_unavailable)

    # =========================================================================
    # Health-Check (delegiert an Health-Manager)
    # =========================================================================

    async def check_model_health(self, model: str) -> Tuple[bool, str]:
        """Prueft ob ein Modell verfuegbar ist (async)."""
        return await check_model_health_async(model)

    def check_model_health_sync(self, model: str) -> Tuple[bool, str]:
        """Synchrone Version des Health-Checks."""
        return check_model_health_sync(model)

    def _parse_health_check_error(self, model: str, exception: Exception) -> Tuple[bool, str]:
        """Rückwärtskompatibilität: Error-Parsing."""
        return parse_health_check_error(model, exception)

    def mark_permanently_unavailable(self, model: str, reason: str) -> None:
        """Markiert ein Modell als dauerhaft nicht verfuegbar."""
        self._health_manager.mark_permanently_unavailable(model, reason)

    def is_permanently_unavailable(self, model: str) -> bool:
        """Prueft ob ein Modell als permanent unavailable markiert ist."""
        return self._health_manager.is_permanently_unavailable(model)

    def reactivate_model(self, model: str) -> bool:
        """Reaktiviert ein zuvor als unavailable markiertes Modell."""
        return self._health_manager.reactivate_model(model)

    async def recheck_unavailable_models(self) -> Dict[str, bool]:
        """Prueft ob unavailable Modelle wieder verfuegbar sind."""
        return await self._health_manager.recheck_unavailable_models()

    async def health_check_all_primary_models(
        self,
        delay_between_checks: float = 2.0
    ) -> Dict[str, Dict[str, Any]]:
        """Fuehrt Health-Check fuer alle Primary-Modelle durch."""
        mode = self.config.get("mode", "test")
        models_config = self.config.get("models", {}).get(mode, {})
        return await self._health_manager.health_check_all_primary_models(
            models_config, delay_between_checks
        )

    def get_health_status(self) -> Dict[str, Any]:
        """Gibt den aktuellen Health-Status zurück."""
        return self._health_manager.get_health_status()


# =========================================================================
# Singleton-Instanz
# =========================================================================
_router_instance: Optional[ModelRouter] = None


def get_model_router(config: Dict[str, Any] = None) -> ModelRouter:
    """Gibt die globale ModelRouter-Instanz zurück oder erstellt eine neue."""
    global _router_instance

    if _router_instance is None:
        if config is None:
            raise ValueError("Config erforderlich bei erster Initialisierung")
        _router_instance = ModelRouter(config)
    elif config is not None:
        _router_instance.config = config

    return _router_instance


def reset_model_router():
    """Setzt die globale ModelRouter-Instanz zurück (für Tests)."""
    global _router_instance
    _router_instance = None


# =========================================================================
# Expliziter __all__ Export
# =========================================================================
__all__ = [
    'ModelRouter',
    'get_model_router',
    'reset_model_router',
    # Re-exports aus Health-Modul
    'check_model_health_async',
    'check_model_health_sync',
    'HealthCheckManager',
    'LITELLM_AVAILABLE'
]
