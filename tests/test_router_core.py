# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 14.02.2026
Version: 1.0
Beschreibung: Unit-Tests fuer backend/routers/core.py.
              Testet die Core-Endpoints (Run, Status, Reset, Agents).
              Manager und ws_manager werden gemockt.
"""

import os
import sys
import json
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

# Projekt-Root zum Python-Path hinzufuegen
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Manager und ws_manager MUESSEN vor dem Router-Import gemockt werden,
# damit die Modul-Level Importe in core.py die Mocks erhalten.
mock_manager = MagicMock()
mock_ws_manager = MagicMock()
mock_ws_manager.broadcast = AsyncMock()
mock_limiter = MagicMock()
# Limiter-Dekorator transparent machen (Funktion unveraendert durchleiten)
mock_limiter.limit.return_value = lambda func: func

with patch("backend.app_state.manager", mock_manager), \
     patch("backend.app_state.ws_manager", mock_ws_manager), \
     patch("backend.app_state.limiter", mock_limiter):
    from backend.routers.core import router, TaskRequest

from fastapi import FastAPI
from fastapi.testclient import TestClient
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler

# Mini-App fuer Tests erstellen
app = FastAPI()
# Echten Limiter fuer die Test-App setzen (damit app.state.limiter existiert)
_test_limiter = Limiter(key_func=get_remote_address)
app.state.limiter = _test_limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.include_router(router)
client = TestClient(app)

# Patch-Pfade fuer die im Router importierten Objekte
MANAGER_PATCH = "backend.routers.core.manager"
WS_MANAGER_PATCH = "backend.routers.core.ws_manager"
LOG_EVENT_PATCH = "backend.routers.core.log_event"


# =========================================================================
# TestTaskRequest — Pydantic-Modell Validierung
# =========================================================================

class TestTaskRequest:
    """Tests fuer das TaskRequest Pydantic-Modell."""

    def test_nur_goal_pflicht(self):
        """TaskRequest benoetigt nur das goal-Feld."""
        req = TaskRequest(goal="Erstelle eine Todo-App")
        assert req.goal == "Erstelle eine Todo-App"
        assert req.project_name is None

    def test_mit_project_name(self):
        """TaskRequest akzeptiert optionalen project_name."""
        req = TaskRequest(goal="Erstelle eine App", project_name="mein_projekt")
        assert req.project_name == "mein_projekt"

    def test_leerer_project_name_erlaubt(self):
        """Leerer String als project_name ist technisch erlaubt."""
        req = TaskRequest(goal="Test", project_name="")
        assert req.project_name == ""

    def test_goal_ist_string(self):
        """goal muss ein String sein."""
        req = TaskRequest(goal="Teste die API")
        assert isinstance(req.goal, str)


# =========================================================================
# TestRunEndpoint — POST /run
# =========================================================================

class TestRunEndpoint:
    """Tests fuer den /run Endpoint (Task starten)."""

    @patch(LOG_EVENT_PATCH)
    @patch(WS_MANAGER_PATCH)
    @patch(MANAGER_PATCH)
    def test_run_erfolgreich(self, mock_mgr, mock_ws, mock_log):
        """POST /run startet einen Task und gibt status=started zurueck."""
        # AENDERUNG 26.02.2026: Fix 89 — _is_running Mock fuer Fix 85 Kompatibilitaet
        # ROOT-CAUSE-FIX:
        # Symptom: Test gibt 409 statt 200 zurueck
        # Ursache: MagicMock._is_running ist truthy → getattr() liefert Mock statt False
        # Loesung: _is_running explizit auf False setzen
        mock_mgr._is_running = False
        response = client.post("/run", json={"goal": "Erstelle eine Todo-App"})
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "started"
        assert data["goal"] == "Erstelle eine Todo-App"

    @patch(LOG_EVENT_PATCH)
    @patch(WS_MANAGER_PATCH)
    @patch(MANAGER_PATCH)
    def test_run_mit_project_name(self, mock_mgr, mock_ws, mock_log):
        """POST /run mit project_name wird akzeptiert."""
        mock_mgr._is_running = False
        response = client.post("/run", json={
            "goal": "Erstelle eine App",
            "project_name": "mein_projekt"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "started"

    def test_run_ohne_goal_abgelehnt(self):
        """POST /run ohne goal-Feld gibt 422 zurueck."""
        response = client.post("/run", json={})
        assert response.status_code == 422, (
            f"Erwartet: 422 (Validation Error), Erhalten: {response.status_code}"
        )

    def test_run_leerer_body_abgelehnt(self):
        """POST /run mit leerem Body gibt 422 zurueck."""
        response = client.post("/run", content=b"")
        assert response.status_code == 422


# =========================================================================
# TestStatusEndpoint — GET /status
# =========================================================================

class TestStatusEndpoint:
    """Tests fuer den /status Endpoint."""

    @patch(MANAGER_PATCH)
    def test_status_gibt_projekt_info(self, mock_mgr):
        """GET /status gibt project_path, is_first_run und tech_blueprint zurueck."""
        mock_mgr.project_path = "/tmp/test_projekt"
        mock_mgr.is_first_run = True
        mock_mgr.tech_blueprint = {"framework": "Next.js"}

        response = client.get("/status")
        assert response.status_code == 200
        data = response.json()
        assert data["project_path"] == "/tmp/test_projekt"
        assert data["is_first_run"] is True
        assert data["tech_blueprint"] == {"framework": "Next.js"}

    @patch(MANAGER_PATCH)
    def test_status_nach_reset(self, mock_mgr):
        """GET /status nach Reset zeigt None/True/leeres Blueprint."""
        mock_mgr.project_path = None
        mock_mgr.is_first_run = True
        mock_mgr.tech_blueprint = {}

        response = client.get("/status")
        assert response.status_code == 200
        data = response.json()
        assert data["project_path"] is None
        assert data["is_first_run"] is True
        assert data["tech_blueprint"] == {}

    @patch(MANAGER_PATCH)
    def test_status_waehrend_lauf(self, mock_mgr):
        """GET /status waehrend eines laufenden Projekts zeigt aktive Daten."""
        mock_mgr.project_path = "C:/output/todo_app_20260214"
        mock_mgr.is_first_run = False
        mock_mgr.tech_blueprint = {
            "framework": "Next.js",
            "language": "javascript",
            "database": "sqlite"
        }

        response = client.get("/status")
        assert response.status_code == 200
        data = response.json()
        assert data["is_first_run"] is False
        assert "framework" in data["tech_blueprint"]


# =========================================================================
# TestResetEndpoint — POST /reset
# =========================================================================

class TestResetEndpoint:
    """Tests fuer den /reset Endpoint (Projekt zuruecksetzen)."""

    @patch(LOG_EVENT_PATCH)
    @patch(WS_MANAGER_PATCH)
    @patch(MANAGER_PATCH)
    def test_reset_erfolgreich(self, mock_mgr, mock_ws, mock_log):
        """POST /reset setzt den Manager zurueck und gibt success zurueck."""
        mock_ws.broadcast = AsyncMock()
        mock_mgr.office_manager = None

        response = client.post("/reset")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "zurueck" in data["message"].lower() or "zurück" in data["message"].lower()

    @patch(LOG_EVENT_PATCH)
    @patch(WS_MANAGER_PATCH)
    @patch(MANAGER_PATCH)
    def test_reset_setzt_project_path_zurueck(self, mock_mgr, mock_ws, mock_log):
        """POST /reset setzt project_path auf None."""
        mock_ws.broadcast = AsyncMock()
        mock_mgr.office_manager = None
        mock_mgr.project_path = "/tmp/altes_projekt"

        response = client.post("/reset")
        assert response.status_code == 200
        # Pruefen dass project_path zurueckgesetzt wurde
        assert mock_mgr.project_path is None

    @patch(LOG_EVENT_PATCH)
    @patch(WS_MANAGER_PATCH)
    @patch(MANAGER_PATCH)
    def test_reset_sendet_broadcast(self, mock_mgr, mock_ws, mock_log):
        """POST /reset sendet eine WebSocket-Broadcast-Nachricht."""
        mock_ws.broadcast = AsyncMock()
        mock_mgr.office_manager = None

        response = client.post("/reset")
        assert response.status_code == 200
        mock_ws.broadcast.assert_called_once()
        # Broadcast-Nachricht pruefen
        broadcast_arg = mock_ws.broadcast.call_args[0][0]
        broadcast_data = json.loads(broadcast_arg)
        assert broadcast_data["event"] == "Reset"
        assert broadcast_data["agent"] == "System"

    @patch(LOG_EVENT_PATCH)
    @patch(WS_MANAGER_PATCH)
    @patch(MANAGER_PATCH)
    def test_reset_mit_office_manager(self, mock_mgr, mock_ws, mock_log):
        """POST /reset ruft reset_all_workers() auf wenn office_manager existiert."""
        mock_ws.broadcast = AsyncMock()
        mock_office = MagicMock()
        mock_mgr.office_manager = mock_office

        response = client.post("/reset")
        assert response.status_code == 200
        mock_office.reset_all_workers.assert_called_once()

    @patch(LOG_EVENT_PATCH)
    @patch(WS_MANAGER_PATCH)
    @patch(MANAGER_PATCH)
    def test_reset_office_manager_fehler_kein_crash(self, mock_mgr, mock_ws, mock_log):
        """POST /reset stuerzt nicht ab wenn reset_all_workers() fehlschlaegt."""
        mock_ws.broadcast = AsyncMock()
        mock_office = MagicMock()
        mock_office.reset_all_workers.side_effect = RuntimeError("Worker-Fehler")
        mock_mgr.office_manager = mock_office

        response = client.post("/reset")
        # Trotz Worker-Fehler muss der Reset erfolgreich sein
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"


# =========================================================================
# TestAgentsEndpoint — GET /agents
# =========================================================================

class TestAgentsEndpoint:
    """Tests fuer den /agents Endpoint (Agenten-Liste)."""

    @patch(MANAGER_PATCH)
    def test_agents_liste_mit_string_modell(self, mock_mgr):
        """GET /agents gibt Agenten mit String-Modell korrekt zurueck."""
        mock_mgr.config = {
            "mode": "test",
            "models": {
                "test": {
                    "coder": "gpt-4",
                    "reviewer": "claude-3.5-sonnet"
                }
            }
        }

        response = client.get("/agents")
        assert response.status_code == 200
        data = response.json()
        assert data["mode"] == "test"
        assert len(data["agents"]) == 2
        # Pruefen ob bekannte Agenten korrekte Info haben
        rollen = [a["role"] for a in data["agents"]]
        assert "coder" in rollen
        assert "reviewer" in rollen

    @patch(MANAGER_PATCH)
    def test_agents_liste_mit_dict_modell(self, mock_mgr):
        """GET /agents verarbeitet Dict-Modellkonfig (primary/fallback) korrekt."""
        mock_mgr.config = {
            "mode": "test",
            "models": {
                "test": {
                    "coder": {
                        "primary": "gpt-4",
                        "fallback": "gpt-3.5-turbo"
                    }
                }
            }
        }

        response = client.get("/agents")
        assert response.status_code == 200
        data = response.json()
        agents = data["agents"]
        assert len(agents) == 1
        assert agents[0]["model"] == "gpt-4", (
            "Bei Dict-Modellkonfig sollte das 'primary' Modell zurueckgegeben werden"
        )

    @patch(MANAGER_PATCH)
    def test_agents_leere_modell_liste(self, mock_mgr):
        """GET /agents mit leerer Modell-Konfiguration gibt leere Liste zurueck."""
        mock_mgr.config = {
            "mode": "test",
            "models": {"test": {}}
        }

        response = client.get("/agents")
        assert response.status_code == 200
        data = response.json()
        assert data["agents"] == []

    @patch(MANAGER_PATCH)
    def test_agents_unbekannte_rolle(self, mock_mgr):
        """GET /agents mit unbekannter Rolle verwendet den Rollennamen als Fallback."""
        mock_mgr.config = {
            "mode": "test",
            "models": {
                "test": {
                    "unbekannter_agent": "test-model"
                }
            }
        }

        response = client.get("/agents")
        assert response.status_code == 200
        data = response.json()
        agent = data["agents"][0]
        assert agent["role"] == "unbekannter_agent"
        assert agent["name"] == "unbekannter_agent", (
            "Bei unbekannter Rolle sollte der Rollenname als Name verwendet werden"
        )

    @patch(MANAGER_PATCH)
    def test_agents_bekannte_agenten_info(self, mock_mgr):
        """GET /agents gibt fuer bekannte Rollen Name und Beschreibung zurueck."""
        mock_mgr.config = {
            "mode": "test",
            "models": {
                "test": {
                    "designer": "gpt-4"
                }
            }
        }

        response = client.get("/agents")
        assert response.status_code == 200
        data = response.json()
        agent = data["agents"][0]
        assert agent["name"] == "Designer"
        assert "UI/UX" in agent["description"] or "Design" in agent["description"]

    @patch(MANAGER_PATCH)
    def test_agents_mode_fallback(self, mock_mgr):
        """GET /agents nutzt 'test' als Fallback wenn mode nicht in config."""
        mock_mgr.config = {
            "models": {
                "test": {
                    "coder": "gpt-4"
                }
            }
        }

        response = client.get("/agents")
        assert response.status_code == 200
        data = response.json()
        assert data["mode"] == "test"
