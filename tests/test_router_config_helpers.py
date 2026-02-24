# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 22.02.2026
Version: 1.0
Beschreibung: Helper-Tests fuer backend/routers/config.py.
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


# ÄNDERUNG 22.02.2026: Helper-Tests (_is_valid_model, _save_config) ausgelagert.

class TestIsValidModel:
    """Tests fuer die _is_valid_model() Hilfsfunktion."""

    def test_openrouter_prefix_gueltig(self, mock_manager):
        """Modellname mit 'openrouter/' Prefix ist gueltig."""
        with patch("backend.routers.config.manager", mock_manager):
            assert _is_valid_model("openrouter/anthropic/claude-4") is True

    def test_gpt_prefix_gueltig(self, mock_manager):
        """Modellname mit 'gpt-' Prefix ist gueltig."""
        with patch("backend.routers.config.manager", mock_manager):
            assert _is_valid_model("gpt-5-mini") is True

    def test_claude_prefix_gueltig(self, mock_manager):
        """Modellname mit 'claude-' Prefix ist gueltig."""
        with patch("backend.routers.config.manager", mock_manager):
            assert _is_valid_model("claude-haiku-4.5") is True

    def test_leerer_string_ungueltig(self, mock_manager):
        """Leerer String ist kein gueltiger Modellname."""
        with patch("backend.routers.config.manager", mock_manager):
            assert _is_valid_model("") is False

    def test_none_ungueltig(self, mock_manager):
        """None ist kein gueltiger Modellname."""
        with patch("backend.routers.config.manager", mock_manager):
            assert _is_valid_model(None) is False

    def test_nicht_string_ungueltig(self, mock_manager):
        """Nicht-String Typ ist kein gueltiger Modellname."""
        with patch("backend.routers.config.manager", mock_manager):
            assert _is_valid_model(12345) is False

    def test_unbekanntes_modell_ohne_prefix(self, mock_manager):
        """Unbekanntes Modell ohne gueltigen Prefix ist ungueltig."""
        mock_manager.config["available_models"] = []
        mock_manager.config["allow_unlisted_models"] = False
        with patch("backend.routers.config.manager", mock_manager):
            assert _is_valid_model("random-model-xyz") is False

    def test_modell_in_available_models(self, mock_manager):
        """Modell das in available_models steht ist gueltig."""
        mock_manager.config["available_models"] = ["custom-model-1", "custom-model-2"]
        with patch("backend.routers.config.manager", mock_manager):
            assert _is_valid_model("custom-model-1") is True

    def test_allow_unlisted_models_aktiviert(self, mock_manager):
        """Mit allow_unlisted_models=True ist jeder nicht-leere String gueltig."""
        mock_manager.config["available_models"] = []
        mock_manager.config["allow_unlisted_models"] = True
        with patch("backend.routers.config.manager", mock_manager):
            assert _is_valid_model("beliebiges-modell") is True

    def test_allow_unlisted_nur_whitespace_ungueltig(self, mock_manager):
        """Auch mit allow_unlisted_models ist ein nur-Whitespace-String ungueltig."""
        mock_manager.config["allow_unlisted_models"] = True
        with patch("backend.routers.config.manager", mock_manager):
            # strip() ergibt leeren String -> len == 0 -> False
            assert _is_valid_model("   ") is False



class TestSaveConfig:
    """Tests fuer die _save_config() Hilfsfunktion."""

    def test_save_config_ruamel_pfad(self, mock_manager):
        """_save_config nutzt ruamel.yaml wenn verfuegbar."""
        mock_yaml_instance = MagicMock()
        mock_yaml_instance.load.return_value = {"mode": "test"}
        mock_yaml_cls = MagicMock(return_value=mock_yaml_instance)

        with patch("backend.routers.config.manager", mock_manager), \
             patch("backend.routers.config.RUAMEL_AVAILABLE", True), \
             patch("builtins.open", mock_open(read_data="mode: test\n")) as mocked_file, \
             patch("backend.routers.config.YAML", mock_yaml_cls, create=True):

            _save_config()

            # Datei muss zum Lesen und Schreiben geoeffnet worden sein
            assert mocked_file.call_count >= 1
            mock_yaml_instance.dump.assert_called_once()

    def test_save_config_pyyaml_fallback(self, mock_manager):
        """_save_config nutzt PyYAML wenn ruamel.yaml nicht verfuegbar ist."""
        with patch("backend.routers.config.manager", mock_manager), \
             patch("backend.routers.config.RUAMEL_AVAILABLE", False), \
             patch("builtins.open", mock_open()) as mocked_file, \
             patch("backend.routers.config.yaml.dump") as mock_dump:

            _save_config()

            mock_dump.assert_called_once()
            # Pruefe dass sort_keys=False uebergeben wird
            call_kwargs = mock_dump.call_args[1]
            assert call_kwargs.get("sort_keys") is False

    def test_save_config_pfad_korrekt(self, mock_manager):
        """_save_config nutzt den korrekten Pfad basierend auf manager.base_dir."""
        expected_path = os.path.join(mock_manager.base_dir, "config.yaml")
        with patch("backend.routers.config.manager", mock_manager), \
             patch("backend.routers.config.RUAMEL_AVAILABLE", False), \
             patch("builtins.open", mock_open()) as mocked_file, \
             patch("backend.routers.config.yaml.dump"):

            _save_config()

            # Pruefe dass der korrekte Pfad verwendet wird
            mocked_file.assert_called_once_with(expected_path, "w", encoding="utf-8")


