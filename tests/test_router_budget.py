# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 14.02.2026
Version: 1.0
Beschreibung: Unit-Tests fuer backend/routers/budget.py.
              Testet Budget-Endpoints (Stats, Costs, Heatmap, Caps,
              Recommendations, Prediction, History, Projects).
              Pydantic-Modelltests wurden nach test_router_budget_models.py ausgelagert.
"""

import os
import sys
import pytest
from unittest.mock import patch, MagicMock

# Projekt-Root zum Python-Path hinzufuegen
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI
from fastapi.testclient import TestClient
from backend.routers.budget import router

# Mini-App fuer Tests erstellen
app = FastAPI()
app.include_router(router)
client = TestClient(app)

# Einheitlicher Patch-Pfad fuer get_budget_tracker
TRACKER_PATCH = "backend.routers.budget.get_budget_tracker"


# =========================================================================
# TestBudgetStatsEndpoint — GET /budget/stats
# =========================================================================

class TestBudgetStatsEndpoint:
    """Tests fuer den Budget-Statistiken Endpoint."""

    @patch(TRACKER_PATCH)
    def test_stats_default_period(self, mock_get_tracker):
        """GET /budget/stats ohne Parameter nutzt Default period_days=30."""
        mock_tracker = MagicMock()
        mock_tracker.get_stats.return_value = {"total_spent": 42.5, "burn_rate_change": 5.0}
        mock_get_tracker.return_value = mock_tracker

        response = client.get("/budget/stats")
        assert response.status_code == 200
        mock_tracker.get_stats.assert_called_once_with(period_days=30)

    @patch(TRACKER_PATCH)
    def test_stats_custom_period(self, mock_get_tracker):
        """GET /budget/stats mit period_days=7 gibt 7-Tage-Statistiken zurueck."""
        mock_tracker = MagicMock()
        mock_tracker.get_stats.return_value = {"total_spent": 10.0}
        mock_get_tracker.return_value = mock_tracker

        response = client.get("/budget/stats?period_days=7")
        assert response.status_code == 200
        mock_tracker.get_stats.assert_called_once_with(period_days=7)

    def test_stats_period_zu_gross(self):
        """GET /budget/stats mit period_days=500 wird abgelehnt (max 365)."""
        response = client.get("/budget/stats?period_days=500")
        assert response.status_code == 422, (
            f"Erwartet: 422 (Validation Error), Erhalten: {response.status_code}"
        )

    def test_stats_period_negativ(self):
        """GET /budget/stats mit period_days=0 wird abgelehnt (min 1)."""
        response = client.get("/budget/stats?period_days=0")
        assert response.status_code == 422, (
            f"Erwartet: 422 (Validation Error), Erhalten: {response.status_code}"
        )


# =========================================================================
# TestAgentCostsEndpoint — GET /budget/costs/agents
# =========================================================================

class TestAgentCostsEndpoint:
    """Tests fuer den Kosten-pro-Agent Endpoint."""

    @patch(TRACKER_PATCH)
    def test_agent_costs_mit_daten(self, mock_get_tracker):
        """GET /budget/costs/agents gibt Agenten-Kosten mit data_source=real zurueck."""
        mock_tracker = MagicMock()
        agent_daten = [{"name": "Coder", "role": "coder", "cost": 5.0}]
        mock_tracker.get_costs_by_agent.return_value = agent_daten
        mock_get_tracker.return_value = mock_tracker

        response = client.get("/budget/costs/agents")
        assert response.status_code == 200
        data = response.json()
        assert data["data_source"] == "real"
        assert data["period"] == "7d"
        assert len(data["agents"]) == 1

    @patch(TRACKER_PATCH)
    def test_agent_costs_ohne_daten(self, mock_get_tracker):
        """GET /budget/costs/agents ohne Daten gibt data_source=no_data zurueck."""
        mock_tracker = MagicMock()
        mock_tracker.get_costs_by_agent.return_value = []
        mock_get_tracker.return_value = mock_tracker

        response = client.get("/budget/costs/agents")
        assert response.status_code == 200
        data = response.json()
        assert data["data_source"] == "no_data"
        assert data["agents"] == []

    def test_agent_costs_period_zu_gross(self):
        """GET /budget/costs/agents mit period_days=100 wird abgelehnt (max 90)."""
        response = client.get("/budget/costs/agents?period_days=100")
        assert response.status_code == 422


# =========================================================================
# TestHeatmapEndpoint — GET /budget/heatmap
# =========================================================================

class TestHeatmapEndpoint:
    """Tests fuer den Token-Heatmap Endpoint."""

    @patch(TRACKER_PATCH)
    def test_heatmap_mit_daten(self, mock_get_tracker):
        """GET /budget/heatmap gibt Heatmap mit data_source=real zurueck."""
        mock_tracker = MagicMock()
        mock_tracker.get_hourly_heatmap.return_value = {
            "agents": ["coder", "reviewer"],
            "hours": list(range(24))
        }
        mock_get_tracker.return_value = mock_tracker

        response = client.get("/budget/heatmap")
        assert response.status_code == 200
        data = response.json()
        assert data["data_source"] == "real"

    @patch(TRACKER_PATCH)
    def test_heatmap_ohne_daten(self, mock_get_tracker):
        """GET /budget/heatmap ohne Agenten gibt data_source=no_data zurueck."""
        mock_tracker = MagicMock()
        mock_tracker.get_hourly_heatmap.return_value = {"agents": [], "hours": []}
        mock_get_tracker.return_value = mock_tracker

        response = client.get("/budget/heatmap")
        assert response.status_code == 200
        data = response.json()
        assert data["data_source"] == "no_data"

    def test_heatmap_period_zu_gross(self):
        """GET /budget/heatmap mit period_days=10 wird abgelehnt (max 7)."""
        response = client.get("/budget/heatmap?period_days=10")
        assert response.status_code == 422


# =========================================================================
# TestBudgetCapsEndpoints — GET/PUT /budget/caps
# =========================================================================

class TestBudgetCapsEndpoints:
    """Tests fuer die Budget-Caps Endpoints (Lesen und Setzen)."""

    @patch(TRACKER_PATCH)
    def test_get_caps(self, mock_get_tracker):
        """GET /budget/caps gibt die aktuelle Konfiguration zurueck."""
        mock_tracker = MagicMock()
        mock_tracker.get_config.return_value = {
            "global_monthly_cap": 100.0,
            "global_daily_cap": 10.0,
            "auto_pause": True,
            "alert_thresholds": [50, 80, 95],
            "slack_webhook_url": "https://hooks.slack.com/test",
            "discord_webhook_url": None
        }
        mock_get_tracker.return_value = mock_tracker

        response = client.get("/budget/caps")
        assert response.status_code == 200
        data = response.json()
        assert data["monthly"] == 100.0
        assert data["daily"] == 10.0
        assert data["auto_pause"] is True
        assert data["slack_webhook_configured"] is True
        assert data["discord_webhook_configured"] is False

    @patch(TRACKER_PATCH)
    def test_put_caps_erfolgreich(self, mock_get_tracker):
        """PUT /budget/caps setzt neue Budget-Caps und gibt Status zurueck."""
        mock_tracker = MagicMock()
        mock_get_tracker.return_value = mock_tracker

        response = client.put("/budget/caps", json={
            "monthly": 200.0,
            "daily": 20.0,
            "auto_pause": False
        })
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["monthly"] == 200.0
        assert data["daily"] == 20.0
        assert data["auto_pause"] is False
        mock_tracker.update_config.assert_called_once()

    def test_put_caps_negative_monthly(self):
        """PUT /budget/caps mit negativem monthly wird abgelehnt."""
        response = client.put("/budget/caps", json={
            "monthly": -10.0,
            "daily": 5.0
        })
        assert response.status_code == 422, (
            f"Erwartet: 422 (Validation Error), Erhalten: {response.status_code}"
        )

    def test_put_caps_negative_daily(self):
        """PUT /budget/caps mit negativem daily wird abgelehnt."""
        response = client.put("/budget/caps", json={
            "monthly": 10.0,
            "daily": -5.0
        })
        assert response.status_code == 422


# =========================================================================
# TestRecommendationsEndpoint — GET /budget/recommendations
# =========================================================================

class TestRecommendationsEndpoint:
    """Tests fuer den Empfehlungs-Endpoint."""

    @patch(TRACKER_PATCH)
    def test_recommendations_mit_teuerem_agenten(self, mock_get_tracker):
        """Empfehlung wird generiert wenn ein Agent hohe Kosten hat."""
        mock_tracker = MagicMock()
        mock_tracker.get_stats.return_value = {
            "burn_rate_change": 5.0,
            "remaining": 80.0,
            "total_budget": 100.0,
            "days_remaining": 30
        }
        mock_tracker.get_costs_by_agent.return_value = [
            {"name": "Coder", "role": "coder", "cost": 25.0}
        ]
        mock_tracker.predict_costs.return_value = {"prediction_available": False}
        mock_get_tracker.return_value = mock_tracker

        response = client.get("/budget/recommendations")
        assert response.status_code == 200
        data = response.json()
        empfehlungen = data["recommendations"]
        assert len(empfehlungen) >= 1
        assert empfehlungen[0]["type"] == "recommendation"
        assert "Coder" in empfehlungen[0]["title"]

    @patch(TRACKER_PATCH)
    def test_recommendations_steigende_burn_rate(self, mock_get_tracker):
        """Warnung wird generiert wenn burn_rate_change > 20%."""
        mock_tracker = MagicMock()
        mock_tracker.get_stats.return_value = {
            "burn_rate_change": 25.0,
            "remaining": 80.0,
            "total_budget": 100.0,
            "days_remaining": 30
        }
        mock_tracker.get_costs_by_agent.return_value = []
        mock_tracker.predict_costs.return_value = {"prediction_available": False}
        mock_get_tracker.return_value = mock_tracker

        response = client.get("/budget/recommendations")
        data = response.json()
        typen = [r["type"] for r in data["recommendations"]]
        assert "warning" in typen, (
            f"Erwartet: 'warning' in Empfehlungstypen, Erhalten: {typen}"
        )

    @patch(TRACKER_PATCH)
    def test_recommendations_niedriges_budget(self, mock_get_tracker):
        """Kritische Warnung wenn remaining < 20% von total_budget."""
        mock_tracker = MagicMock()
        mock_tracker.get_stats.return_value = {
            "burn_rate_change": 0.0,
            "remaining": 10.0,
            "total_budget": 100.0,
            "days_remaining": 5
        }
        mock_tracker.get_costs_by_agent.return_value = []
        mock_tracker.predict_costs.return_value = {"prediction_available": False}
        mock_get_tracker.return_value = mock_tracker

        response = client.get("/budget/recommendations")
        data = response.json()
        typen = [r["type"] for r in data["recommendations"]]
        assert "critical" in typen, (
            f"Erwartet: 'critical' in Empfehlungstypen, Erhalten: {typen}"
        )

    @patch(TRACKER_PATCH)
    def test_recommendations_keine_daten(self, mock_get_tracker):
        """Ohne Daten kommt Info-Meldung 'Keine Daten'."""
        mock_tracker = MagicMock()
        mock_tracker.get_stats.return_value = {
            "burn_rate_change": 0.0,
            "remaining": 100.0,
            "total_budget": 100.0,
            "days_remaining": 365
        }
        mock_tracker.get_costs_by_agent.return_value = []
        mock_tracker.predict_costs.return_value = {"prediction_available": False}
        mock_get_tracker.return_value = mock_tracker

        response = client.get("/budget/recommendations")
        data = response.json()
        assert len(data["recommendations"]) == 1
        assert data["recommendations"][0]["type"] == "info"
        assert "Keine Daten" in data["recommendations"][0]["title"]

    @patch(TRACKER_PATCH)
    def test_recommendations_mit_prognose(self, mock_get_tracker):
        """Prognose-Info wird angezeigt wenn prediction_available=True."""
        mock_tracker = MagicMock()
        mock_tracker.get_stats.return_value = {
            "burn_rate_change": 0.0,
            "remaining": 100.0,
            "total_budget": 100.0,
            "days_remaining": 365
        }
        mock_tracker.get_costs_by_agent.return_value = []
        mock_tracker.predict_costs.return_value = {
            "prediction_available": True,
            "trend": "steigend",
            "total_predicted_30d": 45.50,
            "confidence": "hoch"
        }
        mock_get_tracker.return_value = mock_tracker

        response = client.get("/budget/recommendations")
        data = response.json()
        typen = [r["type"] for r in data["recommendations"]]
        assert "info" in typen


# =========================================================================
# TestPredictionEndpoint — GET /budget/prediction
# =========================================================================

class TestPredictionEndpoint:
    """Tests fuer den Kostenprognose-Endpoint."""

    @patch(TRACKER_PATCH)
    def test_prediction_default(self, mock_get_tracker):
        """GET /budget/prediction ohne Parameter nutzt days_ahead=30."""
        mock_tracker = MagicMock()
        mock_tracker.predict_costs.return_value = {"prediction_available": True}
        mock_get_tracker.return_value = mock_tracker

        response = client.get("/budget/prediction")
        assert response.status_code == 200
        mock_tracker.predict_costs.assert_called_once_with(days_ahead=30)

    def test_prediction_period_zu_gross(self):
        """GET /budget/prediction mit days_ahead=100 wird abgelehnt (max 90)."""
        response = client.get("/budget/prediction?days_ahead=100")
        assert response.status_code == 422


# =========================================================================
# TestHistoryEndpoint — GET /budget/history
# =========================================================================

class TestHistoryEndpoint:
    """Tests fuer den historische Daten Endpoint."""

    @patch(TRACKER_PATCH)
    def test_history_mit_daten(self, mock_get_tracker):
        """GET /budget/history gibt historische Daten mit data_source=real zurueck."""
        mock_tracker = MagicMock()
        mock_tracker.get_historical_data.return_value = [
            {"date": "2026-02-13", "cost": 5.0}
        ]
        mock_get_tracker.return_value = mock_tracker

        response = client.get("/budget/history")
        assert response.status_code == 200
        data = response.json()
        assert data["data_source"] == "real"
        assert data["period_days"] == 30
        assert len(data["history"]) == 1

    @patch(TRACKER_PATCH)
    def test_history_ohne_daten(self, mock_get_tracker):
        """GET /budget/history ohne Daten gibt data_source=no_data zurueck."""
        mock_tracker = MagicMock()
        mock_tracker.get_historical_data.return_value = []
        mock_get_tracker.return_value = mock_tracker

        response = client.get("/budget/history")
        assert response.status_code == 200
        data = response.json()
        assert data["data_source"] == "no_data"


# =========================================================================
# TestProjectsEndpoints — GET/POST/DELETE /budget/projects
# =========================================================================

class TestProjectsEndpoints:
    """Tests fuer die Projekt-Management Endpoints."""

    @patch(TRACKER_PATCH)
    def test_get_projects(self, mock_get_tracker):
        """GET /budget/projects gibt alle Projekte zurueck."""
        mock_tracker = MagicMock()
        mock_tracker.get_all_projects.return_value = [
            {"project_id": "p1", "name": "Projekt A"}
        ]
        mock_get_tracker.return_value = mock_tracker

        response = client.get("/budget/projects")
        assert response.status_code == 200
        data = response.json()
        assert len(data["projects"]) == 1

    @patch(TRACKER_PATCH)
    def test_create_project_erfolgreich(self, mock_get_tracker):
        """POST /budget/projects erstellt ein neues Projekt."""
        mock_tracker = MagicMock()
        # create_project gibt ein ProjectBudget-aehnliches Objekt zurueck
        mock_projekt = MagicMock()
        mock_projekt.project_id = "p1"
        mock_projekt.name = "Neues Projekt"
        mock_projekt.total_budget = 500.0
        mock_tracker.create_project.return_value = mock_projekt
        mock_get_tracker.return_value = mock_tracker

        response = client.post("/budget/projects", json={
            "project_id": "p1",
            "name": "Neues Projekt",
            "budget": 500.0
        })
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["project"]["project_id"] == "p1"
        assert data["project"]["name"] == "Neues Projekt"
        assert data["project"]["total_budget"] == 500.0

    @patch(TRACKER_PATCH)
    def test_delete_project_erfolgreich(self, mock_get_tracker):
        """DELETE /budget/projects/{id} loescht ein vorhandenes Projekt."""
        mock_tracker = MagicMock()
        mock_tracker.delete_project.return_value = True
        mock_get_tracker.return_value = mock_tracker

        response = client.delete("/budget/projects/p1")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

    @patch(TRACKER_PATCH)
    def test_delete_project_nicht_gefunden(self, mock_get_tracker):
        """DELETE /budget/projects/{id} gibt 404 bei unbekanntem Projekt."""
        mock_tracker = MagicMock()
        mock_tracker.delete_project.return_value = False
        mock_get_tracker.return_value = mock_tracker

        response = client.delete("/budget/projects/nicht_vorhanden")
        assert response.status_code == 404, (
            f"Erwartet: 404 (Not Found), Erhalten: {response.status_code}"
        )

    @patch(TRACKER_PATCH)
    def test_get_project_details(self, mock_get_tracker):
        """GET /budget/projects/{id} gibt Projekt-Details mit Kostenberechnung zurueck."""
        mock_tracker = MagicMock()
        mock_projekt = MagicMock()
        mock_projekt.project_id = "p1"
        mock_projekt.name = "Testprojekt"
        mock_projekt.total_budget = 100.0
        mock_tracker.get_project.return_value = mock_projekt
        # usage_history simulieren fuer Kostenberechnung
        mock_usage = MagicMock()
        mock_usage.cost_usd = 25.0
        mock_usage.project_id = "p1"
        mock_tracker.usage_history = [mock_usage]
        mock_get_tracker.return_value = mock_tracker

        response = client.get("/budget/projects/p1")
        assert response.status_code == 200
        data = response.json()
        assert data["project_id"] == "p1"
        assert data["spent"] == 25.0
        assert data["remaining"] == 75.0
        assert data["percentage_used"] == 25.0

    @patch(TRACKER_PATCH)
    def test_get_project_nicht_gefunden(self, mock_get_tracker):
        """GET /budget/projects/{id} gibt 404 bei unbekanntem Projekt."""
        mock_tracker = MagicMock()
        mock_tracker.get_project.return_value = None
        mock_get_tracker.return_value = mock_tracker

        response = client.get("/budget/projects/nicht_vorhanden")
        assert response.status_code == 404, (
            f"Erwartet: 404 (Not Found), Erhalten: {response.status_code}"
        )

    @patch(TRACKER_PATCH)
    def test_get_project_ohne_budget(self, mock_get_tracker):
        """GET /budget/projects/{id} mit total_budget=0 gibt percentage_used=0."""
        mock_tracker = MagicMock()
        mock_projekt = MagicMock()
        mock_projekt.project_id = "p_null"
        mock_projekt.name = "Null-Budget"
        mock_projekt.total_budget = 0.0
        mock_tracker.get_project.return_value = mock_projekt
        mock_tracker.usage_history = []
        mock_get_tracker.return_value = mock_tracker

        response = client.get("/budget/projects/p_null")
        assert response.status_code == 200
        data = response.json()
        assert data["percentage_used"] == 0, (
            f"Erwartet: 0 bei Budget=0, Erhalten: {data['percentage_used']}"
        )
