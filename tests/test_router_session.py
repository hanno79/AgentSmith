# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 14.02.2026
Version: 1.0
Beschreibung: Unit-Tests fuer backend/routers/session.py.
              Testet die Session-Management-Endpoints (GET /session/current,
              GET /session/logs, POST /session/restore, POST /session/reset,
              GET /session/status).
"""

import os
import sys
import pytest
from unittest.mock import MagicMock, patch, AsyncMock

# Projekt-Root zum Python-Path hinzufuegen
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.routers.session import router

# Test-App mit eingebundenem Router erstellen
app = FastAPI()
app.include_router(router)
client = TestClient(app)


# =========================================================================
# TestGetCurrentSession — GET /session/current
# =========================================================================

class TestGetCurrentSession:
    """Tests fuer den GET /session/current Endpoint."""

    @patch("backend.routers.session.get_session_manager_instance")
    def test_session_vorhanden(self, mock_get_session):
        """Gibt Session-State zurueck wenn Session-Manager existiert."""
        mock_session = MagicMock()
        erwarteter_state = {
            "session": {"project_id": "proj-1", "goal": "Test", "status": "Running"},
            "agent_data": {"coder": {}},
            "recent_logs": [{"msg": "Start"}],
            "is_active": True
        }
        mock_session.get_current_state.return_value = erwarteter_state
        mock_get_session.return_value = mock_session

        response = client.get("/session/current")
        assert response.status_code == 200
        daten = response.json()
        assert daten["is_active"] is True
        assert daten["session"]["project_id"] == "proj-1"

    @patch("backend.routers.session.get_session_manager_instance")
    def test_session_nicht_vorhanden(self, mock_get_session):
        """Gibt leeren Default-State zurueck wenn kein Session-Manager."""
        mock_get_session.return_value = None

        response = client.get("/session/current")
        assert response.status_code == 200
        daten = response.json()
        assert daten["is_active"] is False
        assert daten["session"]["project_id"] is None
        assert daten["session"]["status"] == "Idle"
        assert daten["session"]["goal"] == ""
        assert daten["recent_logs"] == []

    @patch("backend.routers.session.get_session_manager_instance")
    def test_session_default_agent_data_leer(self, mock_get_session):
        """Default-State hat leeres agent_data dict."""
        mock_get_session.return_value = None

        response = client.get("/session/current")
        daten = response.json()
        assert daten["agent_data"] == {}


# =========================================================================
# TestGetSessionLogs — GET /session/logs
# =========================================================================

class TestGetSessionLogs:
    """Tests fuer den GET /session/logs Endpoint."""

    @patch("backend.routers.session.get_session_manager_instance")
    def test_logs_vorhanden(self, mock_get_session):
        """Gibt Logs und Total zurueck wenn Session-Manager existiert."""
        mock_session = MagicMock()
        log_eintraege = [{"msg": "Log 1"}, {"msg": "Log 2"}]
        mock_session.get_logs.return_value = (log_eintraege, 42)
        mock_get_session.return_value = mock_session

        response = client.get("/session/logs")
        assert response.status_code == 200
        daten = response.json()
        assert len(daten["logs"]) == 2
        assert daten["total"] == 42

    @patch("backend.routers.session.get_session_manager_instance")
    def test_logs_mit_limit_und_offset(self, mock_get_session):
        """Limit und Offset werden korrekt weitergereicht."""
        mock_session = MagicMock()
        mock_session.get_logs.return_value = ([], 0)
        mock_get_session.return_value = mock_session

        response = client.get("/session/logs?limit=50&offset=10")
        assert response.status_code == 200
        mock_session.get_logs.assert_called_once_with(limit=50, offset=10)

    @patch("backend.routers.session.get_session_manager_instance")
    def test_logs_kein_session_manager(self, mock_get_session):
        """Gibt leere Logs zurueck wenn kein Session-Manager."""
        mock_get_session.return_value = None

        response = client.get("/session/logs")
        assert response.status_code == 200
        daten = response.json()
        assert daten["logs"] == []
        assert daten["total"] == 0

    @patch("backend.routers.session.get_session_manager_instance")
    def test_logs_default_parameter(self, mock_get_session):
        """Standard-Parameter sind limit=100 und offset=0."""
        mock_session = MagicMock()
        mock_session.get_logs.return_value = ([], 0)
        mock_get_session.return_value = mock_session

        response = client.get("/session/logs")
        assert response.status_code == 200
        mock_session.get_logs.assert_called_once_with(limit=100, offset=0)


# =========================================================================
# TestRestoreSession — POST /session/restore
# =========================================================================

class TestRestoreSession:
    """Tests fuer den POST /session/restore Endpoint."""

    @patch("backend.routers.session.get_library_manager")
    @patch("backend.routers.session.get_session_manager_instance")
    def test_restore_erfolgreich(self, mock_get_session, mock_get_lib):
        """Stellt Session erfolgreich wieder her."""
        mock_session = MagicMock()
        mock_session.restore_from_library.return_value = {"project_id": "proj-99", "status": "Restored"}
        mock_get_session.return_value = mock_session

        mock_lib = MagicMock()
        mock_lib.get_project.return_value = {"id": "proj-99", "data": "test"}
        mock_get_lib.return_value = mock_lib

        response = client.post("/session/restore", json={"project_id": "proj-99"})
        assert response.status_code == 200
        daten = response.json()
        assert daten["status"] == "ok"
        assert daten["session"]["project_id"] == "proj-99"

    @patch("backend.routers.session.get_library_manager")
    @patch("backend.routers.session.get_session_manager_instance")
    def test_restore_projekt_nicht_gefunden_404(self, mock_get_session, mock_get_lib):
        """Gibt 404 zurueck wenn Projekt nicht in Library gefunden."""
        mock_session = MagicMock()
        mock_get_session.return_value = mock_session

        mock_lib = MagicMock()
        mock_lib.get_project.return_value = None
        mock_get_lib.return_value = mock_lib

        response = client.post("/session/restore", json={"project_id": "nicht-vorhanden"})
        assert response.status_code == 404, (
            f"Erwartet: 404, Erhalten: {response.status_code}"
        )

    @patch("backend.routers.session.get_session_manager_instance")
    def test_restore_kein_session_manager_503(self, mock_get_session):
        """Gibt 503 zurueck wenn Session-Manager nicht verfuegbar."""
        mock_get_session.return_value = None

        response = client.post("/session/restore", json={"project_id": "test"})
        assert response.status_code == 503, (
            f"Erwartet: 503, Erhalten: {response.status_code}"
        )

    def test_restore_ohne_project_id_422(self):
        """Gibt 422 zurueck wenn project_id fehlt."""
        response = client.post("/session/restore", json={})
        assert response.status_code == 422, (
            f"Erwartet: 422 (Validation Error), Erhalten: {response.status_code}"
        )


# =========================================================================
# TestResetSession — POST /session/reset
# =========================================================================

class TestResetSession:
    """Tests fuer den POST /session/reset Endpoint."""

    @patch("backend.routers.session.get_session_manager_instance")
    def test_reset_erfolgreich(self, mock_get_session):
        """Setzt Session zurueck und bestaetigt."""
        mock_session = MagicMock()
        mock_get_session.return_value = mock_session

        with patch("backend.app_state.ws_manager") as mock_ws_manager, \
             patch("backend.app_state.manager") as mock_orch_manager:
            mock_ws_manager.broadcast = AsyncMock()
            mock_orch_manager.stop = MagicMock()
            response = client.post("/session/reset")
        assert response.status_code == 200
        daten = response.json()
        assert daten["status"] == "ok"
        mock_session.reset.assert_called_once()

    @patch("backend.routers.session.get_session_manager_instance")
    def test_reset_kein_session_manager(self, mock_get_session):
        """Reset ohne Session-Manager gibt trotzdem ok zurueck."""
        mock_get_session.return_value = None

        with patch("backend.app_state.ws_manager") as mock_ws_manager, \
             patch("backend.app_state.manager") as mock_orch_manager:
            mock_ws_manager.broadcast = AsyncMock()
            mock_orch_manager.stop = MagicMock()
            response = client.post("/session/reset")
        assert response.status_code == 200
        daten = response.json()
        assert daten["status"] == "ok"


# =========================================================================
# TestGetSessionStatus — GET /session/status
# =========================================================================

class TestGetSessionStatus:
    """Tests fuer den GET /session/status Endpoint."""

    @patch("backend.routers.session.get_session_manager_instance")
    def test_status_aktive_session(self, mock_get_session):
        """Gibt vollstaendigen Status bei aktiver Session zurueck."""
        mock_session = MagicMock()
        mock_session.current_session = {
            "status": "Running",
            "goal": "App erstellen",
            "iteration": 3,
            "project_id": "proj-7"
        }
        mock_session.is_active.return_value = True
        mock_get_session.return_value = mock_session

        response = client.get("/session/status")
        assert response.status_code == 200
        daten = response.json()
        assert daten["status"] == "Running"
        assert daten["is_active"] is True
        assert daten["goal"] == "App erstellen"
        assert daten["iteration"] == 3
        assert daten["project_id"] == "proj-7"

    @patch("backend.routers.session.get_session_manager_instance")
    def test_status_kein_session_manager(self, mock_get_session):
        """Gibt Idle-Status zurueck wenn kein Session-Manager."""
        mock_get_session.return_value = None

        response = client.get("/session/status")
        assert response.status_code == 200
        daten = response.json()
        assert daten["status"] == "Idle"
        assert daten["is_active"] is False

    @patch("backend.routers.session.get_session_manager_instance")
    def test_status_inaktive_session(self, mock_get_session):
        """Gibt is_active=False zurueck bei inaktiver Session."""
        mock_session = MagicMock()
        mock_session.current_session = {
            "status": "Idle",
            "goal": "",
            "iteration": 0,
            "project_id": None
        }
        mock_session.is_active.return_value = False
        mock_get_session.return_value = mock_session

        response = client.get("/session/status")
        assert response.status_code == 200
        daten = response.json()
        assert daten["is_active"] is False
        assert daten["iteration"] == 0

    @patch("backend.routers.session.get_session_manager_instance")
    def test_status_fehlende_felder_defaults(self, mock_get_session):
        """Fehlende Felder in current_session nutzen Default-Werte."""
        mock_session = MagicMock()
        # Leeres dict — alle .get() Aufrufe geben Defaults
        mock_session.current_session = {}
        mock_session.is_active.return_value = False
        mock_get_session.return_value = mock_session

        response = client.get("/session/status")
        assert response.status_code == 200
        daten = response.json()
        assert daten["status"] == "Idle"
        assert daten["goal"] == ""
        assert daten["iteration"] == 0
        assert daten["project_id"] is None
