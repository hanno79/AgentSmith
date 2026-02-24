# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 22.02.2026
Version: 1.0
Beschreibung: Modell-/Prioritaets-/Rate-Limit-Tests fuer backend/routers/config.py.
"""

import os
import sys
import pytest
from unittest.mock import MagicMock, patch, AsyncMock, mock_open
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from fastapi import FastAPI

_mock_model_router_module = MagicMock()
sys.modules["model_router"] = _mock_model_router_module

from backend.routers.config import (
    router,
    _is_valid_model,
    _save_config,
    KNOWN_AGENT_ROLES,
    _models_cache,
    MODELS_CACHE_DURATION,
    fetch_openrouter_models,
)


@pytest.fixture
def test_config():
    return {
        "mode": "test",
        "project_type": "webapp",
        "max_retries": 5,
        "include_designer": True,
        "models": {
            "test": {
                "coder": "openrouter/test-model",
                "reviewer": "openrouter/review-model",
                "designer": "openrouter/design-model",
            },
            "production": {
                "coder": "openrouter/prod-model",
            }
        },
        "token_limits": {"default": 4096, "coder": 8192},
        "agent_timeouts": {"default": 750, "coder": 600},
        "docker": {"enabled": False},
    }


@pytest.fixture
def mock_manager(test_config):
    mgr = MagicMock()
    mgr.config = test_config
    mgr.base_dir = "/tmp/test_project"
    return mgr


@pytest.fixture
def app(mock_manager):
    test_app = FastAPI()
    test_app.include_router(router)
    with patch("backend.routers.config.manager", mock_manager):
        yield test_app


@pytest.fixture
def client(app, mock_manager):
    with patch("backend.routers.config.manager", mock_manager), \
         patch("backend.routers.config._save_config"):
        yield TestClient(app)


# ÄNDERUNG 22.02.2026: Modell-/Prioritaets-/Rate-Limit-Tests ausgelagert.

class TestSetMaxModelAttempts:
    """Tests fuer den PUT /config/max-model-attempts Endpoint."""

    def test_max_model_attempts_gueltig(self, client, mock_manager):
        """Gueltiger max_model_attempts Wert wird akzeptiert."""
        # max_retries ist 5, also max_model_attempts muss 1-4 sein
        response = client.put(
            "/config/max-model-attempts",
            json={"max_model_attempts": 3}
        )
        assert response.status_code == 200
        assert response.json()["max_model_attempts"] == 3

    def test_max_model_attempts_minimum(self, client, mock_manager):
        """Minimaler max_model_attempts Wert (1) wird akzeptiert."""
        response = client.put(
            "/config/max-model-attempts",
            json={"max_model_attempts": 1}
        )
        assert response.status_code == 200

    def test_max_model_attempts_zu_hoch(self, client, mock_manager):
        """max_model_attempts >= max_retries gibt HTTP 400 zurueck."""
        # max_retries ist 5, also 5 oder hoeher ist ungueltig
        response = client.put(
            "/config/max-model-attempts",
            json={"max_model_attempts": 5}
        )
        assert response.status_code == 400

    def test_max_model_attempts_null(self, client, mock_manager):
        """max_model_attempts von 0 gibt HTTP 400 zurueck."""
        response = client.put(
            "/config/max-model-attempts",
            json={"max_model_attempts": 0}
        )
        assert response.status_code == 400



class TestGetModelPriority:
    """Tests fuer den GET /config/model-priority/{agent_role} Endpoint."""

    def test_priority_string_format(self, client, mock_manager):
        """Altes String-Format gibt eine Einzel-Modell-Liste zurueck."""
        # coder ist als String konfiguriert
        response = client.get("/config/model-priority/coder")
        assert response.status_code == 200
        data = response.json()
        assert data["agent"] == "coder"
        assert data["models"] == ["openrouter/test-model"]

    def test_priority_dict_format(self, client, mock_manager):
        """Neues Dict-Format (primary + fallback) wird korrekt zurueckgegeben."""
        # Konfiguriere dict-Format fuer reviewer
        mock_manager.config["models"]["test"]["reviewer"] = {
            "primary": "openrouter/primary-model",
            "fallback": ["openrouter/fallback-1", "openrouter/fallback-2"]
        }
        response = client.get("/config/model-priority/reviewer")
        assert response.status_code == 200
        data = response.json()
        assert len(data["models"]) == 3
        assert data["models"][0] == "openrouter/primary-model"
        assert data["models"][1] == "openrouter/fallback-1"

    def test_priority_unbekannte_rolle_gibt_404(self, client, mock_manager):
        """Priority-Abfrage fuer nicht-existierende Rolle gibt HTTP 404 zurueck."""
        response = client.get("/config/model-priority/nicht_vorhanden")
        assert response.status_code == 404

    def test_priority_dict_fallback_als_string(self, client, mock_manager):
        """Dict-Format mit einzelnem Fallback-String wird korrekt behandelt."""
        mock_manager.config["models"]["test"]["coder"] = {
            "primary": "openrouter/primary",
            "fallback": "openrouter/single-fallback"
        }
        response = client.get("/config/model-priority/coder")
        assert response.status_code == 200
        data = response.json()
        assert len(data["models"]) == 2
        assert data["models"][1] == "openrouter/single-fallback"



class TestSetModelPriority:
    """Tests fuer den PUT /config/model-priority/{agent_role} Endpoint."""

    def test_priority_setzen_erfolgreich(self, client, mock_manager):
        """Prioritaetsliste fuer bekannte Rolle setzen ist erfolgreich."""
        response = client.put(
            "/config/model-priority/coder",
            json={"models": ["openrouter/model-a", "openrouter/model-b"]}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["agent"] == "coder"
        assert len(data["models"]) == 2

    def test_priority_leere_liste_gibt_400(self, client, mock_manager):
        """Leere Modell-Liste gibt HTTP 400 zurueck."""
        response = client.put(
            "/config/model-priority/coder",
            json={"models": []}
        )
        assert response.status_code == 400

    def test_priority_unbekannte_rolle_gibt_400(self, client, mock_manager):
        """Unbekannte Agent-Rolle gibt HTTP 400 zurueck."""
        response = client.put(
            "/config/model-priority/unbekannte_rolle_xyz",
            json={"models": ["openrouter/test"]}
        )
        assert response.status_code == 400

    def test_priority_ungueltiges_modell_gibt_400(self, client, mock_manager):
        """Ungueltiges Modell in der Liste gibt HTTP 400 zurueck."""
        mock_manager.config["available_models"] = []
        mock_manager.config["allow_unlisted_models"] = False
        response = client.put(
            "/config/model-priority/coder",
            json={"models": ["ungueltig-modell"]}
        )
        assert response.status_code == 400

    def test_priority_max_5_modelle(self, client, mock_manager):
        """Mehr als 5 Modelle werden auf 5 begrenzt (4 Fallbacks + 1 Primary)."""
        modelle = [f"openrouter/model-{i}" for i in range(7)]
        response = client.put(
            "/config/model-priority/coder",
            json={"models": modelle}
        )
        assert response.status_code == 200
        data = response.json()
        # Maximal 5 Modelle zurueck
        assert len(data["models"]) == 5

    def test_priority_speichert_primary_fallback_format(self, client, mock_manager):
        """Modelle werden als primary + fallback Format gespeichert."""
        response = client.put(
            "/config/model-priority/coder",
            json={"models": ["openrouter/primary", "openrouter/fb1", "openrouter/fb2"]}
        )
        assert response.status_code == 200
        stored = mock_manager.config["models"]["test"]["coder"]
        assert stored["primary"] == "openrouter/primary"
        assert stored["fallback"] == ["openrouter/fb1", "openrouter/fb2"]



class TestKnownAgentRoles:
    """Tests fuer die KNOWN_AGENT_ROLES Konstante."""

    def test_known_roles_ist_frozenset(self):
        """KNOWN_AGENT_ROLES muss ein frozenset sein."""
        assert isinstance(KNOWN_AGENT_ROLES, frozenset), (
            f"Erwartet: frozenset, Erhalten: {type(KNOWN_AGENT_ROLES).__name__}"
        )

    def test_known_roles_enthaelt_kern_rollen(self):
        """KNOWN_AGENT_ROLES enthaelt alle Kern-Rollen."""
        kern_rollen = {"coder", "reviewer", "tester", "designer", "researcher", "security"}
        for rolle in kern_rollen:
            assert rolle in KNOWN_AGENT_ROLES, (
                f"Erwartete Rolle '{rolle}' fehlt in KNOWN_AGENT_ROLES"
            )

    def test_known_roles_enthaelt_orchestrator(self):
        """KNOWN_AGENT_ROLES enthaelt orchestrator und meta_orchestrator."""
        assert "orchestrator" in KNOWN_AGENT_ROLES
        assert "meta_orchestrator" in KNOWN_AGENT_ROLES

    def test_known_roles_enthaelt_fix_und_task_deriver(self):
        """KNOWN_AGENT_ROLES enthaelt fix und task_deriver (Fix 14)."""
        assert "fix" in KNOWN_AGENT_ROLES
        assert "task_deriver" in KNOWN_AGENT_ROLES



class TestFetchOpenrouterModels:
    """Tests fuer die async fetch_openrouter_models() Funktion."""

    @pytest.mark.asyncio
    async def test_cache_wird_verwendet(self):
        """Cached Daten werden zurueckgegeben wenn Cache gueltig ist."""
        cached_data = {"free_models": [{"id": "cached"}], "paid_models": []}
        _models_cache["data"] = cached_data
        _models_cache["timestamp"] = datetime.now()
        try:
            result = await fetch_openrouter_models()
            assert result == cached_data, "Erwartet: gecachte Daten"
        finally:
            _models_cache["data"] = None
            _models_cache["timestamp"] = None

    @pytest.mark.asyncio
    async def test_cache_abgelaufen_holt_neu(self):
        """Abgelaufener Cache fuehrt zu neuem API-Aufruf."""
        _models_cache["data"] = {"free_models": [], "paid_models": []}
        _models_cache["timestamp"] = datetime.now() - timedelta(hours=2)

        mock_response_data = {
            "data": [
                {
                    "id": "meta/llama-test",
                    "name": "Llama Test",
                    "context_length": 4096,
                    "pricing": {"prompt": "0", "completion": "0"}
                }
            ]
        }

        mock_response = AsyncMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = AsyncMock(return_value=mock_response_data)
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        try:
            with patch("backend.routers.config.aiohttp.ClientSession", return_value=mock_session), \
                 patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}):
                result = await fetch_openrouter_models()
                assert len(result["free_models"]) == 1
                assert result["free_models"][0]["id"] == "openrouter/meta/llama-test"
        finally:
            _models_cache["data"] = None
            _models_cache["timestamp"] = None

    @pytest.mark.asyncio
    async def test_api_fehler_gibt_fallback(self):
        """Bei API-Fehler werden Fallback-Modelle zurueckgegeben."""
        _models_cache["data"] = None
        _models_cache["timestamp"] = None

        with patch("backend.routers.config.aiohttp.ClientSession", side_effect=Exception("Netzwerk-Fehler")), \
             patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}):
            result = await fetch_openrouter_models()
            # Fallback-Modelle muessen vorhanden sein
            assert "free_models" in result
            assert "paid_models" in result
            assert len(result["free_models"]) > 0
            assert len(result["paid_models"]) > 0

    @pytest.mark.asyncio
    async def test_kein_api_key_gibt_fallback(self):
        """Ohne API-Key werden Fallback-Modelle zurueckgegeben."""
        _models_cache["data"] = None
        _models_cache["timestamp"] = None

        with patch.dict(os.environ, {}, clear=True), \
             patch.object(os, "getenv", return_value=None):
            result = await fetch_openrouter_models()
            assert "free_models" in result
            assert "paid_models" in result



class TestGetAvailableModels:
    """Tests fuer den GET /models/available Endpoint."""

    def test_available_models_gibt_ergebnis(self, client, mock_manager):
        """GET /models/available gibt ein Ergebnis zurueck (cached oder Fallback)."""
        # Cache leeren und Fallback erzwingen
        _models_cache["data"] = None
        _models_cache["timestamp"] = None

        with patch("backend.routers.config.fetch_openrouter_models", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = {"free_models": [], "paid_models": []}
            response = client.get("/models/available")
            assert response.status_code == 200
            data = response.json()
            assert "free_models" in data
            assert "paid_models" in data



class TestGetRouterStatus:
    """Tests fuer den GET /models/router-status Endpoint."""

    def test_router_status_erfolgreich(self, client, mock_manager):
        """GET /models/router-status gibt Status zurueck."""
        mock_router_instance = MagicMock()
        mock_router_instance.get_status.return_value = {
            "rate_limited_models": {},
            "usage_stats": {"total_calls": 42}
        }
        with patch("backend.routers.config.get_model_router", return_value=mock_router_instance):
            response = client.get("/models/router-status")
            assert response.status_code == 200
            data = response.json()
            assert "usage_stats" in data

    def test_router_status_bei_fehler(self, client, mock_manager):
        """GET /models/router-status gibt Error-Dict bei Fehler zurueck."""
        with patch("backend.routers.config.get_model_router", side_effect=Exception("Router-Fehler")):
            response = client.get("/models/router-status")
            assert response.status_code == 200
            data = response.json()
            assert "error" in data



class TestClearRateLimits:
    """Tests fuer den POST /models/clear-rate-limits Endpoint."""

    def test_clear_rate_limits_erfolgreich(self, client, mock_manager):
        """POST /models/clear-rate-limits setzt Rate-Limits zurueck."""
        mock_router_instance = MagicMock()
        with patch("backend.routers.config.get_model_router", return_value=mock_router_instance):
            response = client.post("/models/clear-rate-limits")
            assert response.status_code == 200
            assert response.json()["status"] == "ok"
            mock_router_instance.clear_rate_limits.assert_called_once()

    def test_clear_rate_limits_bei_fehler(self, client, mock_manager):
        """POST /models/clear-rate-limits gibt 500 bei Fehler zurueck."""
        with patch("backend.routers.config.get_model_router", side_effect=Exception("Fehler")):
            response = client.post("/models/clear-rate-limits")
            assert response.status_code == 500




