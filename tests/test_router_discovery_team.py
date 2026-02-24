# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 14.02.2026
Version: 1.0
Beschreibung: Unit-Tests fuer backend/routers/discovery_team.py.
              Testet die Endpoints POST /discovery/suggest-team und
              POST /discovery/get-enhanced-options mit verschiedenen
              Szenarien (fehlender API-Key, Exceptions, Memory-Integration,
              Keyword-Filterung, Agent-Kombinationen).
"""

import os
import sys
import json
import pytest
from unittest.mock import MagicMock, patch, AsyncMock

# Projekt-Root zum Python-Path hinzufuegen
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from fastapi import FastAPI

from backend.routers.discovery_team import (
    router,
    SuggestTeamRequest,
    EnhancedOptionsRequest,
)


# =========================================================================
# Gemeinsame Test-Fixtures
# =========================================================================

@pytest.fixture
def app():
    """Erstellt eine FastAPI Test-App mit Discovery-Team-Router."""
    test_app = FastAPI()
    test_app.include_router(router)
    return test_app


@pytest.fixture
def client(app):
    """Erstellt einen TestClient fuer Discovery-Team-Tests."""
    with patch("backend.routers.discovery_team.load_memory_safe", return_value={"history": [], "lessons": []}), \
         patch("backend.routers.discovery_team.find_relevant_lessons", return_value=[]), \
         patch("backend.routers.discovery_team.log_event"):
        yield TestClient(app)


@pytest.fixture
def sample_memory():
    """Beispiel-Memory-Daten mit Lessons."""
    return {
        "history": [],
        "lessons": [
            {
                "pattern": "Flask SQLAlchemy Probleme",
                "action": "ORM korrekt konfigurieren",
                "tags": ["flask", "database"],
                "count": 5,
                "category": "error"
            },
            {
                "pattern": "React State Management",
                "action": "useReducer statt komplexem useState",
                "tags": ["react", "frontend"],
                "count": 3,
                "category": "best_practice"
            }
        ]
    }


@pytest.fixture
def sample_relevant_lessons():
    """Beispiel relevante Lessons fuer Mock-Responses."""
    return [
        {
            "pattern": "Flask SQLAlchemy Probleme",
            "action": "ORM korrekt konfigurieren",
            "count": 5,
            "category": "error"
        }
    ]


# =========================================================================
# TestSuggestTeamRequest — Tests fuer das Pydantic-Model
# =========================================================================

class TestSuggestTeamRequest:
    """Tests fuer das SuggestTeamRequest Pydantic-Model."""

    def test_gueltiger_request(self):
        """Gueltiger Request mit Vision wird akzeptiert."""
        req = SuggestTeamRequest(vision="Eine Todo-App bauen")
        assert req.vision == "Eine Todo-App bauen"

    def test_leerer_vision_string(self):
        """Leerer Vision-String wird vom Model akzeptiert (Validierung im Endpoint)."""
        req = SuggestTeamRequest(vision="")
        assert req.vision == ""


# =========================================================================
# TestEnhancedOptionsRequest — Tests fuer das Pydantic-Model
# =========================================================================

class TestEnhancedOptionsRequest:
    """Tests fuer das EnhancedOptionsRequest Pydantic-Model."""

    def test_gueltiger_request(self):
        """Gueltiger Request mit allen Feldern wird akzeptiert."""
        req = EnhancedOptionsRequest(
            question_id="coder_language",
            question_text="Welche Sprache?",
            agent="Coder",
            vision="Eine App bauen"
        )
        assert req.question_id == "coder_language"
        assert req.agent == "Coder"
        assert req.vision == "Eine App bauen"

    def test_request_ohne_vision_default(self):
        """Request ohne Vision verwendet Default-Leerstring."""
        req = EnhancedOptionsRequest(
            question_id="test",
            question_text="Testfrage",
            agent="Tester"
        )
        assert req.vision == "", f"Erwartet: Leerer Default-String, Erhalten: '{req.vision}'"


# =========================================================================
# TestSuggestTeamEndpoint — Tests fuer POST /discovery/suggest-team
# =========================================================================

class TestSuggestTeamEndpoint:
    """Tests fuer den POST /discovery/suggest-team Endpoint."""

    def test_leere_vision_gibt_400(self, app):
        """Leere Vision gibt HTTP 400 zurueck."""
        with patch("backend.routers.discovery_team.log_event"):
            client = TestClient(app)
            response = client.post(
                "/discovery/suggest-team",
                json={"vision": ""}
            )
            assert response.status_code == 400, (
                f"Erwartet: 400 bei leerer Vision, Erhalten: {response.status_code}"
            )

    def test_nur_whitespace_vision_gibt_400(self, app):
        """Vision mit nur Whitespace gibt HTTP 400 zurueck."""
        with patch("backend.routers.discovery_team.log_event"):
            client = TestClient(app)
            response = client.post(
                "/discovery/suggest-team",
                json={"vision": "   "}
            )
            assert response.status_code == 400, (
                f"Erwartet: 400 bei Whitespace-Vision, Erhalten: {response.status_code}"
            )

    def test_fehlender_api_key_gibt_fallback(self, app):
        """Fehlender API-Key gibt Fallback-Antwort mit Standard-Agenten zurueck."""
        with patch("backend.routers.discovery_team.log_event"), \
             patch.dict(os.environ, {}, clear=False), \
             patch("backend.routers.discovery_team.os.environ.get", return_value=None):
            client = TestClient(app)
            response = client.post(
                "/discovery/suggest-team",
                json={"vision": "Eine Todo-App erstellen"}
            )
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "fallback", (
                f"Erwartet: 'fallback', Erhalten: {data['status']}"
            )
            assert "Coder" in data["recommended_agents"], "Erwartet: 'Coder' in Fallback-Agenten"
            assert "Designer" in data["recommended_agents"], "Erwartet: 'Designer' in Fallback-Agenten"
            assert "Tester" in data["recommended_agents"], "Erwartet: 'Tester' in Fallback-Agenten"

    def test_exception_gibt_error_status(self, app):
        """Exception bei API-Aufruf gibt error-Status mit Standard-Agenten zurueck."""
        def mock_env_get(key, default=None):
            if key == "OPENROUTER_API_KEY":
                return "test-key-123"
            if key == "DEFAULT_MODEL":
                return "openrouter/test-model"
            return default

        with patch("backend.routers.discovery_team.log_event"), \
             patch("backend.routers.discovery_team.os.environ.get", side_effect=mock_env_get), \
             patch("backend.routers.discovery_team.aiohttp.ClientSession", side_effect=Exception("Netzwerk-Fehler")):
            client = TestClient(app)
            response = client.post(
                "/discovery/suggest-team",
                json={"vision": "Eine Todo-App erstellen"}
            )
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "error", (
                f"Erwartet: 'error', Erhalten: {data['status']}"
            )
            assert "Coder" in data["recommended_agents"]
            assert "error" in data["reasoning"]

    def test_error_response_enthaelt_standard_agenten(self, app):
        """Error-Response enthaelt immer die drei Standard-Agenten."""
        def mock_env_get(key, default=None):
            if key == "OPENROUTER_API_KEY":
                return "test-key"
            return default

        with patch("backend.routers.discovery_team.log_event"), \
             patch("backend.routers.discovery_team.os.environ.get", side_effect=mock_env_get), \
             patch("backend.routers.discovery_team.aiohttp.ClientSession", side_effect=RuntimeError("Test")):
            client = TestClient(app)
            response = client.post(
                "/discovery/suggest-team",
                json={"vision": "Projekt XYZ"}
            )
            data = response.json()
            assert set(data["recommended_agents"]) == {"Coder", "Designer", "Tester"}, (
                f"Erwartet: Standard-Agenten, Erhalten: {data['recommended_agents']}"
            )
            assert isinstance(data["not_needed"], dict)

    def test_fallback_bei_fehlendem_key_enthaelt_reasoning(self, app):
        """Fallback-Antwort enthaelt Reasoning mit Hinweis auf fehlenden Key."""
        with patch("backend.routers.discovery_team.log_event"), \
             patch("backend.routers.discovery_team.os.environ.get", return_value=None):
            client = TestClient(app)
            response = client.post(
                "/discovery/suggest-team",
                json={"vision": "Ein Chat-Bot"}
            )
            data = response.json()
            assert "fallback" in data["reasoning"], (
                f"Erwartet: 'fallback' Key im Reasoning, Erhalten: {data['reasoning']}"
            )


# =========================================================================
# TestGetEnhancedOptionsEndpoint — Tests fuer POST /discovery/get-enhanced-options
# =========================================================================

class TestGetEnhancedOptionsEndpoint:
    """Tests fuer den POST /discovery/get-enhanced-options Endpoint."""

    def test_coder_language_optionen(self, app):
        """Coder-Agent mit coder_language gibt Sprach-Empfehlungen zurueck."""
        with patch("backend.routers.discovery_team.load_memory_safe", return_value={"history": [], "lessons": []}), \
             patch("backend.routers.discovery_team.find_relevant_lessons", return_value=[]), \
             patch("backend.routers.discovery_team.log_event"):
            client = TestClient(app)
            response = client.post(
                "/discovery/get-enhanced-options",
                json={
                    "question_id": "coder_language",
                    "question_text": "Welche Programmiersprache?",
                    "agent": "Coder",
                    "vision": ""
                }
            )
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "ok"
            assert data["question_id"] == "coder_language"
            assert len(data["enhanced_options"]) >= 1, "Erwartet: mindestens 1 Sprach-Option"
            # Python sollte empfohlen sein
            values = [opt["value"] for opt in data["enhanced_options"]]
            assert "python" in values, "Erwartet: 'python' als Option"

    def test_coder_deployment_optionen(self, app):
        """Coder-Agent mit coder_deployment gibt Deployment-Optionen zurueck."""
        with patch("backend.routers.discovery_team.load_memory_safe", return_value={"history": [], "lessons": []}), \
             patch("backend.routers.discovery_team.find_relevant_lessons", return_value=[]), \
             patch("backend.routers.discovery_team.log_event"):
            client = TestClient(app)
            response = client.post(
                "/discovery/get-enhanced-options",
                json={
                    "question_id": "coder_deployment",
                    "question_text": "Deployment-Methode?",
                    "agent": "Coder"
                }
            )
            data = response.json()
            assert len(data["enhanced_options"]) >= 1
            values = [opt["value"] for opt in data["enhanced_options"]]
            assert "docker" in values, "Erwartet: 'docker' als Deployment-Option"

    def test_analyst_purpose_optionen(self, app):
        """Analyst-Agent mit analyst_purpose gibt Zweck-Optionen zurueck."""
        with patch("backend.routers.discovery_team.load_memory_safe", return_value={"history": [], "lessons": []}), \
             patch("backend.routers.discovery_team.find_relevant_lessons", return_value=[]), \
             patch("backend.routers.discovery_team.log_event"):
            client = TestClient(app)
            response = client.post(
                "/discovery/get-enhanced-options",
                json={
                    "question_id": "analyst_purpose",
                    "question_text": "Projektzweck?",
                    "agent": "Analyst"
                }
            )
            data = response.json()
            assert len(data["enhanced_options"]) >= 1
            values = [opt["value"] for opt in data["enhanced_options"]]
            assert "customer" in values, "Erwartet: 'customer' als Zweck-Option"

    def test_tester_coverage_optionen(self, app):
        """Tester-Agent mit tester_coverage gibt Coverage-Optionen zurueck."""
        with patch("backend.routers.discovery_team.load_memory_safe", return_value={"history": [], "lessons": []}), \
             patch("backend.routers.discovery_team.find_relevant_lessons", return_value=[]), \
             patch("backend.routers.discovery_team.log_event"):
            client = TestClient(app)
            response = client.post(
                "/discovery/get-enhanced-options",
                json={
                    "question_id": "tester_coverage",
                    "question_text": "Test-Coverage?",
                    "agent": "Tester"
                }
            )
            data = response.json()
            assert len(data["enhanced_options"]) >= 1

    def test_unbekannter_agent_gibt_leere_optionen(self, app):
        """Unbekannter Agent gibt leere enhanced_options zurueck."""
        with patch("backend.routers.discovery_team.load_memory_safe", return_value={"history": [], "lessons": []}), \
             patch("backend.routers.discovery_team.find_relevant_lessons", return_value=[]), \
             patch("backend.routers.discovery_team.log_event"):
            client = TestClient(app)
            response = client.post(
                "/discovery/get-enhanced-options",
                json={
                    "question_id": "unknown_question",
                    "question_text": "Unbekannte Frage",
                    "agent": "UnbekannterAgent"
                }
            )
            data = response.json()
            assert data["enhanced_options"] == [], (
                f"Erwartet: leere enhanced_options, Erhalten: {data['enhanced_options']}"
            )

    def test_unbekannte_question_id_gibt_leere_optionen(self, app):
        """Unbekannte question_id bei bekanntem Agent gibt leere Optionen zurueck."""
        with patch("backend.routers.discovery_team.load_memory_safe", return_value={"history": [], "lessons": []}), \
             patch("backend.routers.discovery_team.find_relevant_lessons", return_value=[]), \
             patch("backend.routers.discovery_team.log_event"):
            client = TestClient(app)
            response = client.post(
                "/discovery/get-enhanced-options",
                json={
                    "question_id": "nicht_existierend",
                    "question_text": "Unbekannte Frage",
                    "agent": "Coder"
                }
            )
            data = response.json()
            assert data["enhanced_options"] == []

    def test_memory_integration_aendert_source(self, app, sample_relevant_lessons):
        """Vorhandene Memory-Lessons aendern source auf 'memory'."""
        with patch("backend.routers.discovery_team.load_memory_safe", return_value={
            "history": [], "lessons": [{"pattern": "test", "tags": ["flask"]}]
        }), \
             patch("backend.routers.discovery_team.find_relevant_lessons", return_value=sample_relevant_lessons), \
             patch("backend.routers.discovery_team.log_event"):
            client = TestClient(app)
            response = client.post(
                "/discovery/get-enhanced-options",
                json={
                    "question_id": "coder_language",
                    "question_text": "Welche Sprache fuer Flask?",
                    "agent": "Coder",
                    "vision": "Flask Webanwendung"
                }
            )
            data = response.json()
            assert data["source"] == "memory", (
                f"Erwartet: 'memory' als Quelle, Erhalten: {data['source']}"
            )
            assert len(data["memory_insights"]) > 0, "Erwartet: mindestens 1 Memory-Insight"

    def test_memory_insights_enthalten_korrekte_felder(self, app, sample_relevant_lessons):
        """Memory-Insights enthalten pattern, action, count und category."""
        with patch("backend.routers.discovery_team.load_memory_safe", return_value={
            "history": [], "lessons": [{"pattern": "test", "tags": ["x"]}]
        }), \
             patch("backend.routers.discovery_team.find_relevant_lessons", return_value=sample_relevant_lessons), \
             patch("backend.routers.discovery_team.log_event"):
            client = TestClient(app)
            response = client.post(
                "/discovery/get-enhanced-options",
                json={
                    "question_id": "test",
                    "question_text": "test frage",
                    "agent": "Coder",
                    "vision": "test projekt"
                }
            )
            data = response.json()
            insight = data["memory_insights"][0]
            assert "pattern" in insight, "Erwartet: 'pattern' in Memory-Insight"
            assert "action" in insight, "Erwartet: 'action' in Memory-Insight"
            assert "count" in insight, "Erwartet: 'count' in Memory-Insight"
            assert "category" in insight, "Erwartet: 'category' in Memory-Insight"

    def test_keywords_filter_kurze_woerter(self, app):
        """Kurze Woerter (<=3 Zeichen) werden aus Keywords gefiltert."""
        mock_find = MagicMock(return_value=[])
        with patch("backend.routers.discovery_team.load_memory_safe", return_value={"history": [], "lessons": [{"x": 1}]}), \
             patch("backend.routers.discovery_team.find_relevant_lessons", mock_find), \
             patch("backend.routers.discovery_team.log_event"):
            client = TestClient(app)
            client.post(
                "/discovery/get-enhanced-options",
                json={
                    "question_id": "test",
                    "question_text": "Die App hat ein Problem",
                    "agent": "Coder",
                    "vision": "ein web tool"
                }
            )
            # Pruefen welche Keywords an find_relevant_lessons uebergeben wurden
            mock_find.assert_called_once()
            keywords = mock_find.call_args[0][1]
            for kw in keywords:
                assert len(kw) > 3, (
                    f"Erwartet: nur Woerter >3 Zeichen, Gefunden: '{kw}'"
                )

    def test_keywords_filter_stoppwoerter(self, app):
        """Deutsche Stoppwoerter werden aus Keywords gefiltert."""
        mock_find = MagicMock(return_value=[])
        with patch("backend.routers.discovery_team.load_memory_safe", return_value={"history": [], "lessons": [{"x": 1}]}), \
             patch("backend.routers.discovery_team.find_relevant_lessons", mock_find), \
             patch("backend.routers.discovery_team.log_event"):
            client = TestClient(app)
            client.post(
                "/discovery/get-enhanced-options",
                json={
                    "question_id": "test",
                    "question_text": "Eine Aufgabe soll werden",
                    "agent": "Coder",
                    "vision": "wird einen erstellen"
                }
            )
            assert mock_find.called
            keywords = mock_find.call_args[0][1]
            stoppwoerter = {"eine", "einen", "wird", "soll", "werden"}
            for kw in keywords:
                assert kw not in stoppwoerter, (
                    f"Erwartet: Stoppwort '{kw}' gefiltert"
                )

    def test_source_bleibt_standards_ohne_memory(self, app):
        """Source bleibt 'standards' wenn keine Memory-Lessons gefunden werden."""
        with patch("backend.routers.discovery_team.load_memory_safe", return_value={"history": [], "lessons": []}), \
             patch("backend.routers.discovery_team.find_relevant_lessons", return_value=[]), \
             patch("backend.routers.discovery_team.log_event"):
            client = TestClient(app)
            response = client.post(
                "/discovery/get-enhanced-options",
                json={
                    "question_id": "coder_language",
                    "question_text": "Welche Sprache?",
                    "agent": "Coder"
                }
            )
            data = response.json()
            assert data["source"] == "standards", (
                f"Erwartet: 'standards', Erhalten: {data['source']}"
            )

    def test_designer_style_optionen(self, app):
        """Designer-Agent mit designer_style gibt Stil-Optionen zurueck."""
        with patch("backend.routers.discovery_team.load_memory_safe", return_value={"history": [], "lessons": []}), \
             patch("backend.routers.discovery_team.find_relevant_lessons", return_value=[]), \
             patch("backend.routers.discovery_team.log_event"):
            client = TestClient(app)
            response = client.post(
                "/discovery/get-enhanced-options",
                json={
                    "question_id": "designer_style",
                    "question_text": "Design-Stil?",
                    "agent": "Designer"
                }
            )
            data = response.json()
            assert len(data["enhanced_options"]) >= 1
            values = [opt["value"] for opt in data["enhanced_options"]]
            assert "modern" in values, "Erwartet: 'modern' als Stil-Option"

    def test_security_auth_optionen(self, app):
        """Security-Agent mit security_auth gibt Auth-Optionen zurueck."""
        with patch("backend.routers.discovery_team.load_memory_safe", return_value={"history": [], "lessons": []}), \
             patch("backend.routers.discovery_team.find_relevant_lessons", return_value=[]), \
             patch("backend.routers.discovery_team.log_event"):
            client = TestClient(app)
            response = client.post(
                "/discovery/get-enhanced-options",
                json={
                    "question_id": "security_auth",
                    "question_text": "Authentifizierung?",
                    "agent": "Security"
                }
            )
            data = response.json()
            assert len(data["enhanced_options"]) >= 1
            values = [opt["value"] for opt in data["enhanced_options"]]
            assert "oauth" in values, "Erwartet: 'oauth' als Auth-Option"

    def test_planner_timeline_optionen(self, app):
        """Planner-Agent mit planner_timeline gibt Zeitleisten-Optionen zurueck."""
        with patch("backend.routers.discovery_team.load_memory_safe", return_value={"history": [], "lessons": []}), \
             patch("backend.routers.discovery_team.find_relevant_lessons", return_value=[]), \
             patch("backend.routers.discovery_team.log_event"):
            client = TestClient(app)
            response = client.post(
                "/discovery/get-enhanced-options",
                json={
                    "question_id": "planner_timeline",
                    "question_text": "Zeitrahmen?",
                    "agent": "Planner"
                }
            )
            data = response.json()
            assert len(data["enhanced_options"]) >= 1
            values = [opt["value"] for opt in data["enhanced_options"]]
            assert "short" in values, "Erwartet: 'short' als Zeitleisten-Option"

    def test_enhanced_options_recommended_feld(self, app):
        """Empfohlene Optionen haben recommended=True."""
        with patch("backend.routers.discovery_team.load_memory_safe", return_value={"history": [], "lessons": []}), \
             patch("backend.routers.discovery_team.find_relevant_lessons", return_value=[]), \
             patch("backend.routers.discovery_team.log_event"):
            client = TestClient(app)
            response = client.post(
                "/discovery/get-enhanced-options",
                json={
                    "question_id": "coder_language",
                    "question_text": "Sprache?",
                    "agent": "Coder"
                }
            )
            data = response.json()
            # Python sollte recommended=True haben
            python_opt = next((o for o in data["enhanced_options"] if o["value"] == "python"), None)
            assert python_opt is not None, "Erwartet: Python-Option vorhanden"
            assert python_opt["recommended"] is True, "Erwartet: Python als empfohlen markiert"
            assert "reason" in python_opt, "Erwartet: 'reason' Feld in Option"

    def test_response_struktur_vollstaendig(self, app):
        """Response enthaelt alle erwarteten Felder."""
        with patch("backend.routers.discovery_team.load_memory_safe", return_value={"history": [], "lessons": []}), \
             patch("backend.routers.discovery_team.find_relevant_lessons", return_value=[]), \
             patch("backend.routers.discovery_team.log_event"):
            client = TestClient(app)
            response = client.post(
                "/discovery/get-enhanced-options",
                json={
                    "question_id": "test_id",
                    "question_text": "Testfrage",
                    "agent": "Coder"
                }
            )
            data = response.json()
            assert "status" in data, "Erwartet: 'status' im Response"
            assert "question_id" in data, "Erwartet: 'question_id' im Response"
            assert "enhanced_options" in data, "Erwartet: 'enhanced_options' im Response"
            assert "memory_insights" in data, "Erwartet: 'memory_insights' im Response"
            assert "source" in data, "Erwartet: 'source' im Response"
