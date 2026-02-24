# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 14.02.2026
Version: 1.0
Beschreibung: Tests fuer backend/routers/features.py —
              Feature-Tracking und Kanban-Board Endpoints.
"""

import pytest
from unittest.mock import MagicMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.routers.features import router


# =========================================================================
# Fixtures
# =========================================================================

@pytest.fixture
def client():
    """TestClient mit Features-Router."""
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


@pytest.fixture
def mock_db():
    """Gemocktes Feature-Tracking-DB Objekt."""
    db = MagicMock()
    db.get_features.return_value = [
        {"id": 1, "name": "Login", "status": "done", "priority": 1},
        {"id": 2, "name": "Dashboard", "status": "in_progress", "priority": 2},
        {"id": 3, "name": "Settings", "status": "pending", "priority": 3},
    ]
    db.get_stats.return_value = {"pending": 1, "in_progress": 1, "done": 1}
    db.get_dependency_graph.return_value = {
        "nodes": [{"id": 1}, {"id": 2}],
        "edges": [{"from": 1, "to": 2}]
    }
    return db


# =========================================================================
# TestGetFeatures
# =========================================================================

class TestGetFeatures:
    """Tests fuer GET /features/{run_id}."""

    def test_features_abrufen(self, client, mock_db):
        """Features werden korrekt nach Status gruppiert."""
        with patch("backend.feature_tracking_db.get_feature_tracking_db", return_value=mock_db):
            resp = client.get("/features/run-123")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["count"] == 3
        assert len(data["grouped"]["done"]) == 1
        assert len(data["grouped"]["in_progress"]) == 1

    def test_features_mit_status_filter(self, client, mock_db):
        """Status-Filter wird an DB weitergegeben."""
        with patch("backend.feature_tracking_db.get_feature_tracking_db", return_value=mock_db):
            resp = client.get("/features/run-123?status=done")
        assert resp.status_code == 200
        mock_db.get_features.assert_called_once_with("run-123", status="done")

    def test_features_db_fehler(self, client):
        """DB-Fehler gibt error-Status statt Exception."""
        mock_db_err = MagicMock()
        mock_db_err.get_features.side_effect = Exception("DB kaputt")
        with patch("backend.feature_tracking_db.get_feature_tracking_db", return_value=mock_db_err):
            resp = client.get("/features/run-x")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "error"
        assert data["features"] == []

    def test_features_leere_liste(self, client):
        """Leere Feature-Liste wird korrekt gruppiert."""
        mock_db_empty = MagicMock()
        mock_db_empty.get_features.return_value = []
        with patch("backend.feature_tracking_db.get_feature_tracking_db", return_value=mock_db_empty):
            resp = client.get("/features/run-empty")
        data = resp.json()
        assert data["count"] == 0
        assert all(len(v) == 0 for v in data["grouped"].values())


# =========================================================================
# TestGetStats
# =========================================================================

class TestGetStats:
    """Tests fuer GET /features/{run_id}/stats."""

    def test_stats_abrufen(self, client, mock_db):
        """Stats werden korrekt zurueckgegeben."""
        with patch("backend.feature_tracking_db.get_feature_tracking_db", return_value=mock_db):
            resp = client.get("/features/run-123/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["stats"]["done"] == 1

    def test_stats_db_fehler(self, client):
        """DB-Fehler bei Stats gibt error-Status."""
        mock_db_err = MagicMock()
        mock_db_err.get_stats.side_effect = RuntimeError("Connection lost")
        with patch("backend.feature_tracking_db.get_feature_tracking_db", return_value=mock_db_err):
            resp = client.get("/features/run-x/stats")
        data = resp.json()
        assert data["status"] == "error"


# =========================================================================
# TestGetGraph
# =========================================================================

class TestGetGraph:
    """Tests fuer GET /features/{run_id}/graph."""

    def test_graph_abrufen(self, client, mock_db):
        """Dependency-Graph wird zurueckgegeben."""
        with patch("backend.feature_tracking_db.get_feature_tracking_db", return_value=mock_db):
            resp = client.get("/features/run-123/graph")
        data = resp.json()
        assert data["status"] == "ok"
        assert len(data["graph"]["nodes"]) == 2
        assert len(data["graph"]["edges"]) == 1

    def test_graph_db_fehler(self, client):
        """DB-Fehler bei Graph gibt leere Struktur."""
        mock_db_err = MagicMock()
        mock_db_err.get_dependency_graph.side_effect = Exception("err")
        with patch("backend.feature_tracking_db.get_feature_tracking_db", return_value=mock_db_err):
            resp = client.get("/features/run-x/graph")
        data = resp.json()
        assert data["status"] == "error"
        assert data["graph"]["nodes"] == []


# =========================================================================
# TestUpdatePriority
# =========================================================================

class TestUpdatePriority:
    """Tests fuer PUT /features/{feature_id}/priority."""

    def test_priority_aendern(self, client, mock_db):
        """Prioritaet wird korrekt gesetzt."""
        mock_conn = MagicMock()
        mock_db._get_conn.return_value = mock_conn
        with patch("backend.feature_tracking_db.get_feature_tracking_db", return_value=mock_db):
            resp = client.put("/features/42/priority", json={"priority": 5})
        assert resp.status_code == 200
        data = resp.json()
        assert data["feature_id"] == 42
        assert data["priority"] == 5
        mock_conn.execute.assert_called_once()
        mock_conn.commit.assert_called_once()

    def test_priority_db_fehler(self, client):
        """DB-Fehler bei Priority gibt 500."""
        mock_db_err = MagicMock()
        mock_db_err._get_conn.side_effect = Exception("err")
        with patch("backend.feature_tracking_db.get_feature_tracking_db", return_value=mock_db_err):
            resp = client.put("/features/1/priority", json={"priority": 1})
        assert resp.status_code == 500


# =========================================================================
# TestUpdateStatus
# =========================================================================

class TestUpdateStatus:
    """Tests fuer PUT /features/{feature_id}/status."""

    def test_status_aendern_gueltig(self, client, mock_db):
        """Gueltiger Status wird gesetzt."""
        with patch("backend.feature_tracking_db.get_feature_tracking_db", return_value=mock_db):
            resp = client.put("/features/10/status", json={"status": "done"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["new_status"] == "done"
        mock_db.update_status.assert_called_once_with(10, "done")

    def test_status_ungueltig(self, client):
        """Ungueltiger Status gibt 400."""
        with patch("backend.feature_tracking_db.get_feature_tracking_db", return_value=MagicMock()):
            resp = client.put("/features/10/status", json={"status": "cancelled"})
        assert resp.status_code == 400
        assert "Ungueltiger Status" in resp.json()["detail"]

    @pytest.mark.parametrize("status", ["pending", "in_progress", "review", "done", "failed"])
    def test_alle_gueltigen_status(self, client, mock_db, status):
        """Alle 5 gueltigen Status werden akzeptiert."""
        with patch("backend.feature_tracking_db.get_feature_tracking_db", return_value=mock_db):
            resp = client.put("/features/1/status", json={"status": status})
        assert resp.status_code == 200

    def test_status_db_fehler(self, client):
        """DB-Fehler bei Status gibt 500."""
        mock_db_err = MagicMock()
        mock_db_err.update_status.side_effect = Exception("err")
        with patch("backend.feature_tracking_db.get_feature_tracking_db", return_value=mock_db_err):
            resp = client.put("/features/1/status", json={"status": "done"})
        assert resp.status_code == 500
