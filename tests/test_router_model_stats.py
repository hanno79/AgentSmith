# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 14.02.2026
Version: 1.0
Beschreibung: Unit-Tests fuer backend/routers/model_stats.py.
              Testet die Modell-Statistik-Endpoints (GET /stats/models,
              GET /stats/runs, GET /stats/best-models).
              Alle Endpoints nutzen lazy-import von model_stats_db.
"""

import os
import sys
import pytest
from unittest.mock import MagicMock, patch

# Projekt-Root zum Python-Path hinzufuegen
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.routers.model_stats import router

# Test-App mit eingebundenem Router erstellen
app = FastAPI()
app.include_router(router)
client = TestClient(app)


# =========================================================================
# TestGetModelStats — GET /stats/models
# =========================================================================

class TestGetModelStats:
    """Tests fuer den GET /stats/models Endpoint."""

    @patch("model_stats_db.get_model_stats_db")
    def test_stats_ohne_filter(self, mock_get_db):
        """Gibt alle Modell-Statistiken ohne Filter zurueck."""
        mock_db = MagicMock()
        stats_daten = [
            {"model": "gpt-4", "calls": 100, "avg_tokens": 500},
            {"model": "claude-3", "calls": 50, "avg_tokens": 800}
        ]
        mock_db.get_model_stats.return_value = stats_daten
        mock_get_db.return_value = mock_db

        response = client.get("/stats/models")
        assert response.status_code == 200
        daten = response.json()
        assert daten["status"] == "ok", (
            f"Erwartet: status='ok', Erhalten: '{daten['status']}'"
        )
        assert daten["count"] == 2
        assert len(daten["stats"]) == 2

    @patch("model_stats_db.get_model_stats_db")
    def test_stats_mit_agent_filter(self, mock_get_db):
        """Gibt gefilterte Statistiken nach Agent-Rolle zurueck."""
        mock_db = MagicMock()
        mock_db.get_model_stats.return_value = [{"model": "gpt-4", "agent": "coder"}]
        mock_get_db.return_value = mock_db

        response = client.get("/stats/models?agent=coder&days=7")
        assert response.status_code == 200
        daten = response.json()
        assert daten["count"] == 1
        mock_db.get_model_stats.assert_called_once_with(agent="coder", days=7)

    @patch("model_stats_db.get_model_stats_db")
    def test_stats_leere_ergebnisse(self, mock_get_db):
        """Gibt leere Liste zurueck wenn keine Statistiken vorhanden."""
        mock_db = MagicMock()
        mock_db.get_model_stats.return_value = []
        mock_get_db.return_value = mock_db

        response = client.get("/stats/models")
        assert response.status_code == 200
        daten = response.json()
        assert daten["count"] == 0
        assert daten["stats"] == []

    @patch("model_stats_db.get_model_stats_db", side_effect=Exception("DB nicht erreichbar"))
    def test_stats_fehler_gibt_error_status(self, mock_get_db):
        """Bei Exception wird error-Status zurueckgegeben (kein 500)."""
        response = client.get("/stats/models")
        assert response.status_code == 200, (
            "Endpoint faengt Exceptions ab und gibt 200 mit error-Status zurueck"
        )
        daten = response.json()
        assert daten["status"] == "error", (
            f"Erwartet: status='error', Erhalten: '{daten['status']}'"
        )
        assert "DB nicht erreichbar" in daten["message"]
        assert daten["stats"] == []

    @patch("model_stats_db.get_model_stats_db")
    def test_stats_default_days_30(self, mock_get_db):
        """Standard-days-Wert ist 30 wenn nicht angegeben."""
        mock_db = MagicMock()
        mock_db.get_model_stats.return_value = []
        mock_get_db.return_value = mock_db

        response = client.get("/stats/models")
        assert response.status_code == 200
        mock_db.get_model_stats.assert_called_once_with(agent=None, days=30)


# =========================================================================
# TestGetRuns — GET /stats/runs
# =========================================================================

class TestGetRuns:
    """Tests fuer den GET /stats/runs Endpoint."""

    @patch("model_stats_db.get_model_stats_db")
    def test_runs_alle(self, mock_get_db):
        """Gibt alle Run-Zusammenfassungen zurueck."""
        mock_db = MagicMock()
        runs_daten = [
            {"run_id": "run-1", "status": "success"},
            {"run_id": "run-2", "status": "failed"}
        ]
        mock_db.get_run_summary.return_value = runs_daten
        mock_get_db.return_value = mock_db

        response = client.get("/stats/runs")
        assert response.status_code == 200
        daten = response.json()
        assert daten["status"] == "ok"
        assert daten["count"] == 2
        assert len(daten["runs"]) == 2

    @patch("model_stats_db.get_model_stats_db")
    def test_runs_einzelner_run(self, mock_get_db):
        """Gibt einzelnen Run zurueck wenn run_id angegeben."""
        mock_db = MagicMock()
        mock_db.get_run_summary.return_value = [{"run_id": "run-42", "status": "success"}]
        mock_get_db.return_value = mock_db

        response = client.get("/stats/runs?run_id=run-42&limit=1")
        assert response.status_code == 200
        daten = response.json()
        assert daten["count"] == 1
        mock_db.get_run_summary.assert_called_once_with(run_id="run-42", limit=1)

    @patch("model_stats_db.get_model_stats_db")
    def test_runs_default_limit_20(self, mock_get_db):
        """Standard-limit-Wert ist 20 wenn nicht angegeben."""
        mock_db = MagicMock()
        mock_db.get_run_summary.return_value = []
        mock_get_db.return_value = mock_db

        response = client.get("/stats/runs")
        assert response.status_code == 200
        mock_db.get_run_summary.assert_called_once_with(run_id=None, limit=20)

    @patch("model_stats_db.get_model_stats_db", side_effect=Exception("Lesefehler"))
    def test_runs_fehler_gibt_error_status(self, mock_get_db):
        """Bei Exception wird error-Status mit leerer runs-Liste zurueckgegeben."""
        response = client.get("/stats/runs")
        assert response.status_code == 200
        daten = response.json()
        assert daten["status"] == "error"
        assert daten["runs"] == []
        assert "Lesefehler" in daten["message"]


# =========================================================================
# TestGetBestModels — GET /stats/best-models
# =========================================================================

class TestGetBestModels:
    """Tests fuer den GET /stats/best-models Endpoint."""

    @patch("model_stats_db.get_model_stats_db")
    def test_best_models_vorhanden(self, mock_get_db):
        """Gibt Empfehlungen pro Rolle zurueck."""
        mock_db = MagicMock()
        empfehlungen = {
            "coder": {"model": "gpt-4", "score": 0.95},
            "reviewer": {"model": "claude-3", "score": 0.88}
        }
        mock_db.get_best_models_per_role.return_value = empfehlungen
        mock_get_db.return_value = mock_db

        response = client.get("/stats/best-models")
        assert response.status_code == 200
        daten = response.json()
        assert daten["status"] == "ok"
        assert "coder" in daten["recommendations"]
        assert "reviewer" in daten["recommendations"]

    @patch("model_stats_db.get_model_stats_db")
    def test_best_models_mit_days_parameter(self, mock_get_db):
        """days-Parameter wird korrekt weitergereicht."""
        mock_db = MagicMock()
        mock_db.get_best_models_per_role.return_value = {}
        mock_get_db.return_value = mock_db

        response = client.get("/stats/best-models?days=7")
        assert response.status_code == 200
        mock_db.get_best_models_per_role.assert_called_once_with(days=7)

    @patch("model_stats_db.get_model_stats_db")
    def test_best_models_leer(self, mock_get_db):
        """Gibt leere Empfehlungen zurueck wenn keine Daten."""
        mock_db = MagicMock()
        mock_db.get_best_models_per_role.return_value = {}
        mock_get_db.return_value = mock_db

        response = client.get("/stats/best-models")
        assert response.status_code == 200
        daten = response.json()
        assert daten["status"] == "ok"
        assert daten["recommendations"] == {}

    @patch("model_stats_db.get_model_stats_db", side_effect=Exception("Timeout"))
    def test_best_models_fehler_gibt_error_status(self, mock_get_db):
        """Bei Exception wird error-Status mit leerem dict zurueckgegeben."""
        response = client.get("/stats/best-models")
        assert response.status_code == 200
        daten = response.json()
        assert daten["status"] == "error"
        assert daten["recommendations"] == {}
        assert "Timeout" in daten["message"]

    @patch("model_stats_db.get_model_stats_db")
    def test_default_days_parameter(self, mock_get_db):
        """Standard-days-Wert ist 30 wenn nicht angegeben."""
        mock_db = MagicMock()
        mock_db.get_best_models_per_role.return_value = {}
        mock_get_db.return_value = mock_db

        response = client.get("/stats/best-models")
        assert response.status_code == 200
        mock_db.get_best_models_per_role.assert_called_once_with(days=30)
