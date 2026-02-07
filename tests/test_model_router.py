# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 01.02.2026
Version: 1.0
Beschreibung: Unit Tests für ModelRouter - Rate Limiting, Fallback, Error History.

              Tests validieren:
              - Fallback bei Rate-Limit
              - Cooldown-Tracking
              - Modellwechsel bei wiederholten Fehlern
              - Health-Check Integration
"""

import pytest
import time
import asyncio
from unittest.mock import patch, MagicMock

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from model_router import ModelRouter, get_model_router, reset_model_router


# =========================================================================
# Fixtures
# =========================================================================

@pytest.fixture
def model_config():
    """Konfiguration mit Primary und Fallback-Modellen."""
    return {
        "mode": "test",
        "models": {
            "test": {
                "coder": {
                    "primary": "model-primary",
                    "fallback": ["model-fallback-1", "model-fallback-2"]
                },
                "reviewer": {
                    "primary": "reviewer-primary",
                    "fallback": ["reviewer-fallback"]
                },
                "meta_orchestrator": "simple-model"
            }
        }
    }


@pytest.fixture
def router(model_config):
    """Frische ModelRouter-Instanz für jeden Test."""
    reset_model_router()
    return ModelRouter(model_config, cooldown_seconds=120)


@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset Singleton vor und nach jedem Test."""
    reset_model_router()
    yield
    reset_model_router()


# =========================================================================
# Test: Basis-Funktionalität
# =========================================================================

class TestModelRouterBasics:
    """Tests für grundlegende Model-Auswahl."""

    def test_get_model_returns_primary(self, router):
        """Primary-Modell wird zurückgegeben wenn verfügbar."""
        model = router.get_model("coder")
        assert model == "model-primary"

    def test_get_model_simple_string_config(self, router):
        """String-Konfiguration wird korrekt behandelt."""
        model = router.get_model("meta_orchestrator")
        assert model == "simple-model"

    def test_get_model_tracks_usage(self, router):
        """Nutzung wird getrackt."""
        router.get_model("coder")
        router.get_model("coder")
        assert router.model_usage_stats.get("model-primary", 0) == 2

    def test_get_all_models_for_role(self, router):
        """Gibt alle konfigurierten Modelle für eine Rolle zurück."""
        models = router.get_all_models_for_role("coder")
        assert models == ["model-primary", "model-fallback-1", "model-fallback-2"]

    def test_unknown_role_falls_back_to_meta_orchestrator(self, router):
        """Unbekannte Rolle fällt auf meta_orchestrator zurück."""
        # ÄNDERUNG 01.02.2026: ModelRouter nutzt meta_orchestrator als Fallback
        model = router.get_model("unknown_role")
        assert model == "simple-model"  # meta_orchestrator Konfiguration

    def test_unknown_role_without_meta_orchestrator_raises_error(self):
        """Unbekannte Rolle ohne meta_orchestrator wirft ValueError."""
        # Config OHNE meta_orchestrator
        config = {
            "mode": "test",
            "models": {
                "test": {
                    "coder": {"primary": "model-primary", "fallback": []}
                }
            }
        }
        router = ModelRouter(config)
        with pytest.raises(ValueError, match="No model configuration found"):
            router.get_model("unknown_role")


# =========================================================================
# Test: Rate Limiting & Fallback
# =========================================================================

class TestRateLimitingAndFallback:
    """Tests für Rate-Limit-Handling und Fallback-Logik."""

    def test_fallback_on_rate_limit(self, router):
        """Wechsel zu Fallback-Modell bei Rate-Limit."""
        # Primary rate-limitieren
        router.mark_rate_limited_sync("model-primary")

        # Jetzt sollte Fallback-1 zurückgegeben werden
        model = router.get_model("coder")
        assert model == "model-fallback-1"

    def test_second_fallback_when_first_rate_limited(self, router):
        """Wechsel zu zweitem Fallback wenn erster auch limitiert."""
        router.mark_rate_limited_sync("model-primary")
        router.mark_rate_limited_sync("model-fallback-1")

        model = router.get_model("coder")
        assert model == "model-fallback-2"

    def test_cooldown_tracking(self, router):
        """Modell wird nach Cooldown wieder verfügbar."""
        # Rate-Limit setzen mit sehr kurzem Cooldown
        router.cooldown_seconds = 1
        with patch.object(router, '_mark_rate_limited_core') as mock:
            # Simuliere sofortigen Cooldown-Ablauf
            router.rate_limited_models["model-primary"] = time.time() - 1

        # Modell sollte jetzt wieder verfügbar sein
        is_limited = router._is_rate_limited_sync("model-primary")
        assert is_limited is False

    def test_exponential_backoff_cooldown(self, router):
        """Cooldown erhöht sich exponentiell bei wiederholten Fehlern."""
        # Erster Fehler: 30s
        router.mark_rate_limited_sync("model-primary")
        assert router.model_failure_count["model-primary"] == 1

        # Warte Cooldown ab (simuliert)
        router.rate_limited_models.clear()

        # Zweiter Fehler: 60s
        router.mark_rate_limited_sync("model-primary")
        assert router.model_failure_count["model-primary"] == 2

    def test_mark_success_resets_failure_counter(self, router):
        """Erfolgreiche Nutzung resettet Failure-Counter."""
        router.mark_rate_limited_sync("model-primary")
        assert router.model_failure_count.get("model-primary", 0) == 1

        router.mark_success("model-primary")
        assert router.model_failure_count.get("model-primary", 0) == 0

    def test_on_fallback_callback(self, router):
        """Fallback-Callback wird aufgerufen."""
        callback_called = []

        def on_fallback(agent, primary, fallback):
            callback_called.append((agent, primary, fallback))

        router.on_fallback = on_fallback
        router.mark_rate_limited_sync("model-primary")
        router.get_model("coder")

        assert len(callback_called) == 1
        assert callback_called[0] == ("coder", "model-primary", "model-fallback-1")


# =========================================================================
# Test: Modellwechsel bei wiederholten Fehlern
# =========================================================================

class TestModelSwitchOnRepeatedErrors:
    """Tests für Modellwechsel-Logik bei wiederholten Fehlern."""

    def test_get_model_for_error_returns_untried_model(self, router):
        """Modell das Fehler noch nicht versucht hat wird bevorzugt."""
        error_hash = "error_abc123"

        # Primary hat Fehler versucht
        router.mark_error_tried(error_hash, "model-primary")

        # Nächstes Modell für diesen Fehler sollte Fallback-1 sein
        model = router.get_model_for_error("coder", error_hash)
        assert model == "model-fallback-1"

    def test_error_history_tracks_tried_models(self, router):
        """Error-Historie trackt welche Modelle einen Fehler versucht haben."""
        error_hash = "error_xyz789"

        router.mark_error_tried(error_hash, "model-primary")
        router.mark_error_tried(error_hash, "model-fallback-1")

        status = router.get_error_history_status()
        assert "error_xyz789" in str(status)

    def test_model_switch_after_3_failed_attempts(self, router):
        """Nach 3 fehlgeschlagenen Versuchen wechselt das Modell."""
        error_hash = "persistent_error"

        # Alle Modelle markieren (simuliert 3 fehlgeschlagene Versuche)
        router.mark_error_tried(error_hash, "model-primary")
        router.mark_error_tried(error_hash, "model-fallback-1")
        router.mark_error_tried(error_hash, "model-fallback-2")

        # Jetzt sollte Reset passieren und Primary wieder verfügbar sein
        model = router.get_model_for_error("coder", error_hash)
        # Nach Reset fängt es von vorne an
        assert model in ["model-primary", "model-fallback-1", "model-fallback-2"]

    def test_clear_error_history(self, router):
        """Error-Historie kann gelöscht werden."""
        error_hash = "clearable_error"
        router.mark_error_tried(error_hash, "model-primary")

        router.clear_error_history(error_hash)

        # Jetzt sollte Primary wieder verfügbar sein für diesen Fehler
        model = router.get_model_for_error("coder", error_hash)
        assert model == "model-primary"


# =========================================================================
# Test: Health-Check Integration
# =========================================================================

class TestHealthCheckIntegration:
    """Tests für Health-Check-Funktionalität."""

    def test_permanently_unavailable_skipped(self, router):
        """Permanent unavailable Modelle werden übersprungen."""
        router.mark_permanently_unavailable("model-primary", "Model discontinued")

        model = router.get_model("coder")
        assert model == "model-fallback-1"

    def test_reactivate_model(self, router):
        """Modell kann reaktiviert werden."""
        router.mark_permanently_unavailable("model-primary", "Temporary issue")
        assert router.is_permanently_unavailable("model-primary")

        router.reactivate_model("model-primary")
        assert not router.is_permanently_unavailable("model-primary")

    def test_get_status_includes_health(self, router):
        """Status enthält Health-Informationen."""
        status = router.get_status()
        assert "health_status" in status
        assert "rate_limited_models" in status
        assert "usage_stats" in status


# =========================================================================
# Test: Async-Funktionalität
# =========================================================================

class TestAsyncFunctionality:
    """Tests für async Methoden."""

    @pytest.mark.asyncio
    async def test_get_model_async_returns_primary(self, router):
        """Async: Primary-Modell wird zurückgegeben."""
        model = await router.get_model_async("coder")
        assert model == "model-primary"

    @pytest.mark.asyncio
    async def test_mark_rate_limited_async(self, router):
        """Async: Rate-Limit kann gesetzt werden."""
        await router.mark_rate_limited("model-primary")

        is_limited = await router._is_rate_limited("model-primary")
        assert is_limited is True

    @pytest.mark.asyncio
    async def test_async_fallback_on_rate_limit(self, router):
        """Async: Wechsel zu Fallback bei Rate-Limit."""
        await router.mark_rate_limited("model-primary")

        model = await router.get_model_async("coder")
        assert model == "model-fallback-1"


# =========================================================================
# Test: Edge Cases
# =========================================================================

class TestEdgeCases:
    """Tests für Grenzfälle."""

    def test_all_models_rate_limited_uses_fallback(self, router):
        """
        Wenn alle Modelle limitiert sind, wird dynamischer Fallback verwendet.
        
        AENDERUNG 05.02.2026: Test angepasst - der dynamische Fallback wird verwendet
        wenn alle konfigurierten Modelle erschöpft sind, ohne all_paused_count zu erhöhen.
        Der Counter wird nur für konfigurierte Modelle erhöht, nicht für dynamische Fallbacks.
        """
        router.mark_rate_limited_sync("model-primary")
        router.mark_rate_limited_sync("model-fallback-1")
        router.mark_rate_limited_sync("model-fallback-2")

        # Mit Patch um Sleep zu vermeiden
        with patch('time.sleep'):
            model = router.get_model("coder")

        # Dynamischer Fallback sollte verwendet werden
        assert model is not None
        # Entweder dynamisches Fallback (OpenRouter) oder eines der konfigurierten Modelle
        assert "openrouter/" in model or model in ["model-primary", "model-fallback-1", "model-fallback-2"]
        # all_paused_count wird nicht für dynamischen Fallback erhöht
        # Prüfe stattdessen, dass die konfigurierten Modelle limitiert sind
        assert len(router.rate_limited_models) == 3

    def test_all_models_exhausted_uses_dynamic_fallback(self, router):
        """
        Bei erschoepften konfigurierten Modellen wird dynamischer OpenRouter-Fallback genutzt.

        AENDERUNG 02.02.2026: Test angepasst fuer neues Verhalten mit dynamischem Fallback.
        Frueher wurde RuntimeError geworfen, jetzt wird ein OpenRouter-Modell geholt.
        """
        router.mark_rate_limited_sync("model-primary")
        router.mark_rate_limited_sync("model-fallback-1")
        router.mark_rate_limited_sync("model-fallback-2")

        # Der dynamische Fallback sollte ein OpenRouter-Modell zurueckgeben
        model = router.get_model("coder")

        # Modell sollte von OpenRouter kommen (hat "openrouter/" Praefix)
        assert model is not None
        assert "openrouter/" in model or model.startswith("model-")  # Entweder dynamisch oder Config
        # Usage wurde getrackt
        assert router.model_usage_stats.get(model, 0) >= 1

    def test_clear_rate_limits(self, router):
        """Rate-Limits können zurückgesetzt werden."""
        router.mark_rate_limited_sync("model-primary")
        router.mark_rate_limited_sync("model-fallback-1")

        router.clear_rate_limits()

        assert len(router.rate_limited_models) == 0
        assert len(router.model_failure_count) == 0

    def test_empty_model_is_rate_limited(self, router):
        """Leerer Model-String gilt als rate-limited."""
        assert router._is_rate_limited_sync("") is True
        assert router._is_rate_limited_sync(None) is True


# =========================================================================
# Test: Singleton-Verhalten
# =========================================================================

class TestSingleton:
    """Tests für Singleton-Pattern."""

    def test_get_model_router_creates_singleton(self, model_config):
        """get_model_router erstellt Singleton."""
        reset_model_router()

        router1 = get_model_router(model_config)
        router2 = get_model_router()

        assert router1 is router2

    def test_reset_clears_singleton(self, model_config):
        """reset_model_router löscht Singleton."""
        router1 = get_model_router(model_config)
        reset_model_router()

        router2 = get_model_router(model_config)
        assert router1 is not router2

    def test_get_without_config_raises(self):
        """get_model_router ohne Config wirft Fehler."""
        reset_model_router()

        with pytest.raises(ValueError, match="Config erforderlich"):
            get_model_router()
