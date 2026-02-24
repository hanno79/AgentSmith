# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 14.02.2026
Version: 1.0
Beschreibung: Tests fuer agents/agent_utils.py - Zentrale Hilfsfunktionen fuer alle Agenten.
              Testet get_model_from_config, combine_project_rules, get_model_for_agent.
"""

import os
import sys
import pytest
from unittest.mock import MagicMock

# Fuege Projekt-Root zum Python-Path hinzu
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.agent_utils import (
    get_model_from_config,
    combine_project_rules,
    get_model_for_agent,
)


# ============================================================================
# Tests fuer get_model_from_config
# ============================================================================


class TestGetModelFromConfig:
    """Tests fuer die get_model_from_config Funktion."""

    def test_string_model_config(self, sample_config):
        """Test: Modell als einfacher String wird korrekt zurueckgegeben."""
        result = get_model_from_config(sample_config, "coder")
        assert result == "test-model"

    def test_dict_model_config_with_primary(self):
        """Test: Modell als Dict mit 'primary' Key wird korrekt extrahiert."""
        config = {
            "mode": "production",
            "models": {
                "production": {
                    "coder": {
                        "primary": "gpt-4",
                        "fallback": "gpt-3.5"
                    }
                }
            }
        }
        result = get_model_from_config(config, "coder")
        assert result == "gpt-4"

    def test_fallback_role_when_primary_missing(self):
        """Test: Fallback-Rolle wird genutzt wenn primaere Rolle fehlt."""
        config = {
            "mode": "test",
            "models": {
                "test": {
                    "reviewer": "gpt-4"
                }
            }
        }
        result = get_model_from_config(config, "tester", fallback_role="reviewer")
        assert result == "gpt-4"

    def test_missing_mode_raises_valueerror(self):
        """Test: Fehlender 'mode' Key loest ValueError aus."""
        config = {"models": {"test": {"coder": "gpt-4"}}}
        with pytest.raises(ValueError, match="mode"):
            get_model_from_config(config, "coder")

    def test_missing_models_key_raises_valueerror(self):
        """Test: Fehlender 'models.<mode>' Key loest ValueError aus."""
        config = {"mode": "production", "models": {}}
        with pytest.raises(ValueError, match="models.production"):
            get_model_from_config(config, "coder")

    def test_invalid_models_type_raises_typeerror(self):
        """Test: 'models' als nicht-Dict loest TypeError aus."""
        config = {"mode": "test", "models": "nicht_ein_dict"}
        with pytest.raises(TypeError, match="Dictionary"):
            get_model_from_config(config, "coder")

    def test_role_not_found_raises_valueerror(self):
        """Test: Nicht existierende Rolle ohne Fallback loest ValueError aus."""
        config = {
            "mode": "test",
            "models": {
                "test": {
                    "coder": "gpt-4"
                }
            }
        }
        with pytest.raises(ValueError, match="Kein Modell gefunden"):
            get_model_from_config(config, "nonexistent_role")

    def test_role_not_found_with_fallback_raises_valueerror(self):
        """Test: Weder Rolle noch Fallback gefunden loest ValueError aus."""
        config = {
            "mode": "test",
            "models": {
                "test": {
                    "coder": "gpt-4"
                }
            }
        }
        with pytest.raises(ValueError, match="Fallback-Rolle"):
            get_model_from_config(config, "nonexistent", fallback_role="also_nonexistent")

    def test_dict_model_without_primary_raises_valueerror(self):
        """Test: Dict-Modell ohne 'primary' Key loest ValueError aus."""
        config = {
            "mode": "test",
            "models": {
                "test": {
                    "coder": {"fallback": "gpt-3.5"}
                }
            }
        }
        with pytest.raises(ValueError, match="primary"):
            get_model_from_config(config, "coder")

    def test_dict_model_with_non_string_primary_raises_valueerror(self):
        """Test: Dict-Modell mit nicht-String 'primary' loest ValueError aus."""
        config = {
            "mode": "test",
            "models": {
                "test": {
                    "coder": {"primary": 12345}
                }
            }
        }
        with pytest.raises(ValueError, match="primary"):
            get_model_from_config(config, "coder")

    def test_models_mode_not_dict_raises_valueerror(self):
        """Test: Mode-Eintrag in models als nicht-Dict loest ValueError aus."""
        config = {
            "mode": "test",
            "models": {
                "test": "nicht_ein_dict"
            }
        }
        with pytest.raises(ValueError, match="kein Dictionary"):
            get_model_from_config(config, "coder")

    def test_multiple_roles_in_config(self, sample_config):
        """Test: Verschiedene Rollen werden korrekt zurueckgegeben."""
        assert get_model_from_config(sample_config, "coder") == "test-model"
        assert get_model_from_config(sample_config, "reviewer") == "test-model"
        assert get_model_from_config(sample_config, "designer") == "test-model"
        assert get_model_from_config(sample_config, "security") == "test-model"


# ============================================================================
# Tests fuer combine_project_rules
# ============================================================================


class TestCombineProjectRules:
    """Tests fuer die combine_project_rules Funktion."""

    def test_basic_combination(self):
        """Test: Globale und rollenspezifische Regeln werden kombiniert."""
        rules = {
            "global": ["Regel 1", "Regel 2"],
            "coder": ["Coder Regel A", "Coder Regel B"]
        }
        result = combine_project_rules(rules, "coder")

        assert "Globale Regeln:" in result
        assert "Regel 1" in result
        assert "Regel 2" in result
        assert "Coder-spezifische Regeln:" in result
        assert "Coder Regel A" in result
        assert "Coder Regel B" in result

    def test_empty_global_rules(self):
        """Test: Leere globale Regeln erzeugen leeren globalen Abschnitt."""
        rules = {
            "coder": ["Coder Regel"]
        }
        result = combine_project_rules(rules, "coder")

        assert "Globale Regeln:" in result
        assert "Coder Regel" in result

    def test_empty_role_rules(self):
        """Test: Fehlende rollenspezifische Regeln erzeugen leeren Abschnitt."""
        rules = {
            "global": ["Globale Regel"]
        }
        result = combine_project_rules(rules, "reviewer")

        assert "Globale Regel" in result
        assert "Reviewer-spezifische Regeln:" in result

    def test_empty_dict(self):
        """Test: Leeres Dictionary erzeugt Grundstruktur."""
        result = combine_project_rules({}, "coder")

        assert "Globale Regeln:" in result
        assert "Coder-spezifische Regeln:" in result

    def test_role_name_capitalization(self):
        """Test: Rollenname wird korrekt kapitalisiert."""
        rules = {"global": [], "reviewer": []}
        result = combine_project_rules(rules, "reviewer")

        assert "Reviewer-spezifische Regeln:" in result

    def test_multiline_rules(self):
        """Test: Mehrzeilige Regeln werden korrekt verbunden."""
        rules = {
            "global": ["Zeile 1", "Zeile 2", "Zeile 3"],
            "coder": []
        }
        result = combine_project_rules(rules, "coder")

        # Alle globalen Regeln durch Newline verbunden
        assert "Zeile 1\nZeile 2\nZeile 3" in result

    def test_different_roles(self):
        """Test: Verschiedene Rollen liefern unterschiedliche Ergebnisse."""
        rules = {
            "global": ["Allgemein"],
            "coder": ["Coder-spezifisch"],
            "reviewer": ["Reviewer-spezifisch"]
        }

        coder_result = combine_project_rules(rules, "coder")
        reviewer_result = combine_project_rules(rules, "reviewer")

        assert "Coder-spezifisch" in coder_result
        assert "Coder-spezifisch" not in reviewer_result
        assert "Reviewer-spezifisch" in reviewer_result
        assert "Reviewer-spezifisch" not in coder_result

    def test_rules_from_sample_config(self, sample_config):
        """Test: Regeln aus Beispiel-Konfiguration werden korrekt kombiniert."""
        templates = sample_config["templates"]["webapp"]
        result = combine_project_rules(templates, "coder")

        assert "PEP8 einhalten" in result
        assert "Erstelle requirements.txt" in result


# ============================================================================
# Tests fuer get_model_for_agent
# ============================================================================


class TestGetModelForAgent:
    """Tests fuer die get_model_for_agent Funktion."""

    def test_with_router_uses_router(self):
        """Test: Wenn Router vorhanden, wird router.get_model() aufgerufen."""
        config = {"mode": "test", "models": {"test": {"coder": "config-model"}}}
        mock_router = MagicMock()
        mock_router.get_model.return_value = "router-model"

        result = get_model_for_agent(config, mock_router, "coder")

        assert result == "router-model"
        mock_router.get_model.assert_called_once_with("coder")

    def test_without_router_uses_config(self, sample_config):
        """Test: Wenn kein Router (None), wird get_model_from_config() genutzt."""
        result = get_model_for_agent(sample_config, None, "coder")

        assert result == "test-model"

    def test_without_router_with_fallback(self):
        """Test: Fallback-Rolle wird an get_model_from_config weitergegeben."""
        config = {
            "mode": "test",
            "models": {
                "test": {
                    "reviewer": "fallback-model"
                }
            }
        }

        result = get_model_for_agent(config, None, "tester", fallback_role="reviewer")
        assert result == "fallback-model"

    def test_router_receives_correct_role(self):
        """Test: Router erhaelt die korrekte Rolle als Argument."""
        mock_router = MagicMock()
        mock_router.get_model.return_value = "some-model"
        config = {"mode": "test", "models": {"test": {}}}

        get_model_for_agent(config, mock_router, "security")
        mock_router.get_model.assert_called_once_with("security")

    def test_router_none_is_falsy(self):
        """Test: None-Router fuehrt zum Config-Pfad."""
        config = {
            "mode": "test",
            "models": {
                "test": {
                    "coder": "config-model"
                }
            }
        }

        result = get_model_for_agent(config, None, "coder")
        assert result == "config-model"

    def test_router_takes_precedence_over_config(self):
        """Test: Router hat Vorrang vor Config-Modell."""
        config = {
            "mode": "test",
            "models": {
                "test": {
                    "coder": "config-model"
                }
            }
        }
        mock_router = MagicMock()
        mock_router.get_model.return_value = "router-model"

        result = get_model_for_agent(config, mock_router, "coder")
        # Router soll priorisiert werden
        assert result == "router-model"
