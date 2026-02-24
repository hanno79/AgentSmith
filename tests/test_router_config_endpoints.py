# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 22.02.2026
Version: 1.0
Beschreibung: Endpoint-Tests fuer backend/routers/config.py.
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


# ÄNDERUNG 22.02.2026: Endpoint-Tests aus test_router_config.py ausgelagert.

class TestGetConfig:
    """Tests fuer den GET /config Endpoint."""

    def test_get_config_standard_felder(self, client, mock_manager):
        """GET /config gibt alle erwarteten Standard-Felder zurueck."""
        response = client.get("/config")
        assert response.status_code == 200
        data = response.json()
        assert "mode" in data, "Erwartet: 'mode' im Response"
        assert "project_type" in data, "Erwartet: 'project_type' im Response"
        assert "max_retries" in data, "Erwartet: 'max_retries' im Response"
        assert "include_designer" in data, "Erwartet: 'include_designer' im Response"
        assert "models" in data, "Erwartet: 'models' im Response"
        assert "available_modes" in data, "Erwartet: 'available_modes' im Response"
        assert "token_limits" in data, "Erwartet: 'token_limits' im Response"
        assert "agent_timeouts" in data, "Erwartet: 'agent_timeouts' im Response"
        assert "docker_enabled" in data, "Erwartet: 'docker_enabled' im Response"

    def test_get_config_korrekte_werte(self, client, mock_manager):
        """GET /config gibt die korrekten Werte aus der Konfiguration zurueck."""
        response = client.get("/config")
        data = response.json()
        assert data["mode"] == "test", f"Erwartet: 'test', Erhalten: {data['mode']}"
        assert data["max_retries"] == 5, f"Erwartet: 5, Erhalten: {data['max_retries']}"
        assert data["docker_enabled"] is False, f"Erwartet: False, Erhalten: {data['docker_enabled']}"

    def test_get_config_available_modes(self, client, mock_manager):
        """GET /config liefert genau drei verfuegbare Modi."""
        response = client.get("/config")
        data = response.json()
        assert data["available_modes"] == ["test", "production", "premium"], (
            f"Erwartet: ['test', 'production', 'premium'], Erhalten: {data['available_modes']}"
        )

    def test_get_config_defaults_bei_leerer_config(self, mock_manager):
        """GET /config verwendet Defaults wenn Konfigurationswerte fehlen."""
        mock_manager.config = {}
        app = FastAPI()
        app.include_router(router)
        with patch("backend.routers.config.manager", mock_manager), \
             patch("backend.routers.config._save_config"):
            client = TestClient(app)
            response = client.get("/config")
            data = response.json()
            assert data["mode"] == "test", "Default-Mode sollte 'test' sein"
            assert data["docker_enabled"] is False, "Default docker_enabled sollte False sein"



class TestSetMode:
    """Tests fuer den PUT /config/mode Endpoint."""

    def test_mode_test_erfolgreich(self, client, mock_manager):
        """Mode auf 'test' setzen ist erfolgreich."""
        response = client.put("/config/mode", json={"mode": "test"})
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
        assert response.json()["mode"] == "test"

    def test_mode_production_erfolgreich(self, client, mock_manager):
        """Mode auf 'production' setzen ist erfolgreich."""
        response = client.put("/config/mode", json={"mode": "production"})
        assert response.status_code == 200
        assert response.json()["mode"] == "production"

    def test_mode_premium_erfolgreich(self, client, mock_manager):
        """Mode auf 'premium' setzen ist erfolgreich."""
        response = client.put("/config/mode", json={"mode": "premium"})
        assert response.status_code == 200
        assert response.json()["mode"] == "premium"

    def test_mode_ungueltig_gibt_400(self, client, mock_manager):
        """Ungueltiger Mode gibt HTTP 400 zurueck."""
        response = client.put("/config/mode", json={"mode": "invalid_mode"})
        assert response.status_code == 400, (
            f"Erwartet: 400, Erhalten: {response.status_code}"
        )

    def test_mode_aendert_config(self, client, mock_manager):
        """Mode-Aenderung wird in manager.config gespeichert."""
        client.put("/config/mode", json={"mode": "production"})
        assert mock_manager.config["mode"] == "production", (
            f"Erwartet: 'production', Erhalten: {mock_manager.config['mode']}"
        )



class TestSetMaxRetries:
    """Tests fuer den PUT /config/max-retries Endpoint."""

    def test_max_retries_gueltig(self, client, mock_manager):
        """Gueltiger max_retries Wert (10) wird akzeptiert."""
        response = client.put("/config/max-retries", json={"max_retries": 10})
        assert response.status_code == 200
        assert response.json()["max_retries"] == 10

    def test_max_retries_minimum(self, client, mock_manager):
        """Minimaler max_retries Wert (1) wird akzeptiert."""
        response = client.put("/config/max-retries", json={"max_retries": 1})
        assert response.status_code == 200

    def test_max_retries_maximum(self, client, mock_manager):
        """Maximaler max_retries Wert (100) wird akzeptiert."""
        response = client.put("/config/max-retries", json={"max_retries": 100})
        assert response.status_code == 200

    def test_max_retries_zu_niedrig(self, client, mock_manager):
        """max_retries unter 1 gibt HTTP 400 zurueck."""
        response = client.put("/config/max-retries", json={"max_retries": 0})
        assert response.status_code == 400

    def test_max_retries_zu_hoch(self, client, mock_manager):
        """max_retries ueber 100 gibt HTTP 400 zurueck."""
        response = client.put("/config/max-retries", json={"max_retries": 101})
        assert response.status_code == 400

    def test_max_retries_negativ(self, client, mock_manager):
        """Negativer max_retries Wert gibt HTTP 400 zurueck."""
        response = client.put("/config/max-retries", json={"max_retries": -5})
        assert response.status_code == 400



class TestSetAgentTimeout:
    """Tests fuer den PUT /config/agent-timeout/{agent_role} Endpoint."""

    def test_timeout_gueltig(self, client, mock_manager):
        """Gueltiger Timeout-Wert (300) wird akzeptiert."""
        response = client.put(
            "/config/agent-timeout/coder",
            json={"agent_timeout_seconds": 300}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["agent"] == "coder"
        assert data["timeout_seconds"] == 300

    def test_timeout_minimum(self, client, mock_manager):
        """Minimaler Timeout-Wert (60) wird akzeptiert."""
        response = client.put(
            "/config/agent-timeout/reviewer",
            json={"agent_timeout_seconds": 60}
        )
        assert response.status_code == 200

    def test_timeout_maximum(self, client, mock_manager):
        """Maximaler Timeout-Wert (1800) wird akzeptiert."""
        response = client.put(
            "/config/agent-timeout/tester",
            json={"agent_timeout_seconds": 1800}
        )
        assert response.status_code == 200

    def test_timeout_zu_niedrig(self, client, mock_manager):
        """Timeout unter 60 gibt HTTP 400 zurueck."""
        response = client.put(
            "/config/agent-timeout/coder",
            json={"agent_timeout_seconds": 30}
        )
        assert response.status_code == 400

    def test_timeout_zu_hoch(self, client, mock_manager):
        """Timeout ueber 1800 gibt HTTP 400 zurueck."""
        response = client.put(
            "/config/agent-timeout/coder",
            json={"agent_timeout_seconds": 2000}
        )
        assert response.status_code == 400

    def test_timeout_initialisiert_agent_timeouts(self, mock_manager):
        """Timeout-Endpoint initialisiert agent_timeouts wenn nicht vorhanden."""
        # Entferne agent_timeouts aus der Config
        del mock_manager.config["agent_timeouts"]
        app = FastAPI()
        app.include_router(router)
        with patch("backend.routers.config.manager", mock_manager), \
             patch("backend.routers.config._save_config"):
            test_client = TestClient(app)
            response = test_client.put(
                "/config/agent-timeout/coder",
                json={"agent_timeout_seconds": 500}
            )
            assert response.status_code == 200
            assert "agent_timeouts" in mock_manager.config
            assert mock_manager.config["agent_timeouts"]["coder"] == 500
            assert mock_manager.config["agent_timeouts"]["default"] == 750



class TestSetDockerEnabled:
    """Tests fuer den PUT /config/docker Endpoint."""

    def test_docker_aktivieren(self, client, mock_manager):
        """Docker aktivieren gibt status ok zurueck."""
        response = client.put("/config/docker", json={"enabled": True})
        assert response.status_code == 200
        assert response.json()["docker_enabled"] is True

    def test_docker_deaktivieren(self, client, mock_manager):
        """Docker deaktivieren gibt status ok zurueck."""
        response = client.put("/config/docker", json={"enabled": False})
        assert response.status_code == 200
        assert response.json()["docker_enabled"] is False

    def test_docker_initialisiert_dict(self, mock_manager):
        """Docker-Endpoint initialisiert docker-Dict wenn nicht vorhanden."""
        del mock_manager.config["docker"]
        app = FastAPI()
        app.include_router(router)
        with patch("backend.routers.config.manager", mock_manager), \
             patch("backend.routers.config._save_config"):
            test_client = TestClient(app)
            response = test_client.put("/config/docker", json={"enabled": True})
            assert response.status_code == 200
            assert mock_manager.config["docker"]["enabled"] is True



class TestGetTokenLimits:
    """Tests fuer den GET /config/token-limits Endpoint."""

    def test_token_limits_vorhanden(self, client, mock_manager):
        """GET /config/token-limits gibt vorhandene Limits zurueck."""
        response = client.get("/config/token-limits")
        assert response.status_code == 200
        data = response.json()
        assert data["default"] == 4096
        assert data["coder"] == 8192

    def test_token_limits_defaults_bei_fehlendem_key(self, mock_manager):
        """GET /config/token-limits gibt Defaults zurueck wenn key fehlt."""
        del mock_manager.config["token_limits"]
        app = FastAPI()
        app.include_router(router)
        with patch("backend.routers.config.manager", mock_manager), \
             patch("backend.routers.config._save_config"):
            test_client = TestClient(app)
            response = test_client.get("/config/token-limits")
            data = response.json()
            # Defaults muessen alle bekannten Rollen enthalten
            assert "default" in data
            assert "coder" in data
            assert "reviewer" in data
            assert "planner" in data
            assert "discovery" in data



class TestSetTokenLimit:
    """Tests fuer den PUT /config/token-limit/{agent_role} Endpoint."""

    def test_token_limit_gueltig(self, client, mock_manager):
        """Gueltiger Token-Limit Wert wird akzeptiert."""
        response = client.put(
            "/config/token-limit/coder",
            json={"max_tokens": 16384}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["agent"] == "coder"
        assert data["max_tokens"] == 16384

    def test_token_limit_minimum(self, client, mock_manager):
        """Minimaler Token-Limit Wert (100) wird akzeptiert."""
        response = client.put(
            "/config/token-limit/reviewer",
            json={"max_tokens": 100}
        )
        assert response.status_code == 200

    def test_token_limit_maximum(self, client, mock_manager):
        """Maximaler Token-Limit Wert (131072) wird akzeptiert."""
        response = client.put(
            "/config/token-limit/coder",
            json={"max_tokens": 131072}
        )
        assert response.status_code == 200

    def test_token_limit_zu_niedrig(self, client, mock_manager):
        """Token-Limit unter 100 gibt HTTP 400 zurueck."""
        response = client.put(
            "/config/token-limit/coder",
            json={"max_tokens": 50}
        )
        assert response.status_code == 400

    def test_token_limit_zu_hoch(self, client, mock_manager):
        """Token-Limit ueber 131072 gibt HTTP 400 zurueck."""
        response = client.put(
            "/config/token-limit/coder",
            json={"max_tokens": 200000}
        )
        assert response.status_code == 400

    def test_token_limit_initialisiert_dict(self, mock_manager):
        """Token-Limit-Endpoint initialisiert token_limits wenn nicht vorhanden."""
        del mock_manager.config["token_limits"]
        app = FastAPI()
        app.include_router(router)
        with patch("backend.routers.config.manager", mock_manager), \
             patch("backend.routers.config._save_config"):
            test_client = TestClient(app)
            response = test_client.put(
                "/config/token-limit/security",
                json={"max_tokens": 4096}
            )
            assert response.status_code == 200
            assert "token_limits" in mock_manager.config
            assert mock_manager.config["token_limits"]["security"] == 4096



class TestSetAgentModel:
    """Tests fuer den PUT /config/model/{agent_role} Endpoint."""

    def test_modell_setzen_erfolgreich(self, client, mock_manager):
        """Modell fuer existierende Rolle setzen ist erfolgreich."""
        response = client.put(
            "/config/model/coder",
            json={"model": "openrouter/new-model"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["agent"] == "coder"
        assert data["model"] == "openrouter/new-model"

    def test_modell_unbekannte_rolle_gibt_404(self, client, mock_manager):
        """Modell fuer nicht-existierende Rolle gibt HTTP 404 zurueck."""
        response = client.put(
            "/config/model/nicht_vorhanden",
            json={"model": "openrouter/test"}
        )
        assert response.status_code == 404

    def test_modell_ungueltig_gibt_400(self, client, mock_manager):
        """Ungueltiger Modellname gibt HTTP 400 zurueck."""
        mock_manager.config["available_models"] = []
        mock_manager.config["allow_unlisted_models"] = False
        response = client.put(
            "/config/model/coder",
            json={"model": "ungueltig"}
        )
        assert response.status_code == 400



class TestGetAgentModel:
    """Tests fuer den GET /config/model/{agent_role} Endpoint."""

    def test_modell_abfragen_erfolgreich(self, client, mock_manager):
        """Modell fuer existierende Rolle abfragen ist erfolgreich."""
        response = client.get("/config/model/coder")
        assert response.status_code == 200
        data = response.json()
        assert data["agent"] == "coder"
        assert data["model"] == "openrouter/test-model"
        assert data["mode"] == "test"

    def test_modell_unbekannte_rolle_gibt_404(self, client, mock_manager):
        """Modell-Abfrage fuer nicht-existierende Rolle gibt HTTP 404 zurueck."""
        response = client.get("/config/model/nicht_vorhanden")
        assert response.status_code == 404




