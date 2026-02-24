# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 14.02.2026
Version: 1.0
Beschreibung: Unit-Tests fuer backend/routers/model_health.py.
              Testet die Health-Check-Endpoints fuer Modell-Verfuegbarkeit
              (POST /models/health-check, POST /models/health-check/{model_id},
              GET /models/health-status, POST /models/recheck-unavailable,
              POST /models/reactivate/{model_id}).
"""
# ÄNDERUNG 22.02.2026: Fehlerbehandlung und DUMMY-WERT-Kennzeichnung ergänzt.

import os
import sys
import logging
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

# Projekt-Root zum Python-Path hinzufuegen
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.routers.model_health import router

# Test-App mit eingebundenem Router erstellen
app = FastAPI()
app.include_router(router)
client = TestClient(app)


# =========================================================================
# TestRunHealthCheck — POST /models/health-check
# =========================================================================

class TestRunHealthCheck:
    """Tests fuer den POST /models/health-check Endpoint."""

    @patch("backend.routers.model_health.manager")
    @patch("backend.routers.model_health.get_model_router")
    def test_health_check_erfolgreich(self, mock_get_router, mock_manager):
        """Fuehrt Health-Check durch und gibt Ergebnisse zurueck."""
        try:
            mock_router_instance = MagicMock()
            # DUMMY-WERT: Nur für Tests - NICHT produktiv verwenden!
            mock_router_instance.health_check_all_primary_models = AsyncMock(
                return_value={"gpt-4": True, "claude-3": True}
            )
            # DUMMY-WERT: Nur für Tests - NICHT produktiv verwenden!
            mock_router_instance.permanently_unavailable = {}
            mock_get_router.return_value = mock_router_instance
            mock_manager.config = {"mode": "test"}

            response = client.post("/models/health-check")
            assert response.status_code == 200
            daten = response.json()
            assert daten["status"] == "ok", (
                f"Erwartet: status='ok', Erhalten: '{daten['status']}'"
            )
            assert daten["unavailable_count"] == 0
        except Exception as e:
            logging.error("Fehler in test_health_check_erfolgreich: %s", e)
            raise

    @patch("backend.routers.model_health.manager")
    @patch("backend.routers.model_health.get_model_router")
    def test_health_check_mit_unavailable(self, mock_get_router, mock_manager):
        """Zaehlt unavailable Modelle korrekt."""
        mock_router_instance = MagicMock()
        mock_router_instance.health_check_all_primary_models = AsyncMock(
            return_value={"gpt-4": True, "broken-model": False}
        )
        mock_router_instance.permanently_unavailable = {"broken-model": "404"}
        mock_get_router.return_value = mock_router_instance
        mock_manager.config = {}

        response = client.post("/models/health-check")
        assert response.status_code == 200
        daten = response.json()
        assert daten["unavailable_count"] == 1

    @patch("backend.routers.model_health.manager")
    @patch("backend.routers.model_health.get_model_router")
    def test_health_check_exception_gibt_500(self, mock_get_router, mock_manager):
        """Bei Exception wird 500 zurueckgegeben."""
        mock_get_router.side_effect = Exception("Config ungueltig")
        mock_manager.config = {}

        response = client.post("/models/health-check")
        assert response.status_code == 500, (
            f"Erwartet: 500, Erhalten: {response.status_code}"
        )


# =========================================================================
# TestCheckSingleModel — POST /models/health-check/{model_id}
# =========================================================================

class TestCheckSingleModel:
    """Tests fuer den POST /models/health-check/{model_id} Endpoint."""

    @patch("backend.routers.model_health.manager")
    @patch("backend.routers.model_health.get_model_router")
    def test_modell_verfuegbar(self, mock_get_router, mock_manager):
        """Gibt available=True zurueck fuer verfuegbares Modell."""
        mock_router_instance = MagicMock()
        mock_router_instance.check_model_health = AsyncMock(
            return_value=(True, "OK")
        )
        mock_router_instance.permanently_unavailable = {}
        mock_get_router.return_value = mock_router_instance
        mock_manager.config = {}

        response = client.post("/models/health-check/gpt-4")
        assert response.status_code == 200
        daten = response.json()
        assert daten["available"] is True
        assert daten["model"] == "gpt-4"
        assert daten["is_permanent"] is False

    @patch("backend.routers.model_health.manager")
    @patch("backend.routers.model_health.get_model_router")
    def test_modell_temporaer_nicht_verfuegbar(self, mock_get_router, mock_manager):
        """Gibt available=False mit is_permanent=False bei temporaerem Fehler."""
        mock_router_instance = MagicMock()
        mock_router_instance.check_model_health = AsyncMock(
            return_value=(False, "Service temporarily overloaded")
        )
        mock_router_instance.permanently_unavailable = {}
        mock_get_router.return_value = mock_router_instance
        mock_manager.config = {}

        response = client.post("/models/health-check/gpt-4")
        assert response.status_code == 200
        daten = response.json()
        assert daten["available"] is False
        assert daten["is_permanent"] is False
        # mark_permanently_unavailable sollte NICHT aufgerufen werden
        mock_router_instance.mark_permanently_unavailable.assert_not_called()

    @patch("backend.routers.model_health.manager")
    @patch("backend.routers.model_health.get_model_router")
    def test_modell_permanent_nicht_verfuegbar_404(self, mock_get_router, mock_manager):
        """Markiert Modell als permanent unavailable bei '404 not found' Antwort."""
        mock_router_instance = MagicMock()
        mock_router_instance.check_model_health = AsyncMock(
            return_value=(False, "404 Not Found")
        )
        mock_router_instance.permanently_unavailable = {"test-model": "404 Not Found"}
        mock_get_router.return_value = mock_router_instance
        mock_manager.config = {}

        response = client.post("/models/health-check/test-model")
        assert response.status_code == 200
        daten = response.json()
        assert daten["available"] is False
        assert daten["is_permanent"] is True
        assert daten["marked_unavailable"] is True
        mock_router_instance.mark_permanently_unavailable.assert_called_once()

    @patch("backend.routers.model_health.manager")
    @patch("backend.routers.model_health.get_model_router")
    def test_modell_permanent_free_period_ended(self, mock_get_router, mock_manager):
        """Erkennt 'free period ended' als permanent unavailable."""
        mock_router_instance = MagicMock()
        mock_router_instance.check_model_health = AsyncMock(
            return_value=(False, "Free period ended for this model")
        )
        mock_router_instance.permanently_unavailable = {}
        mock_get_router.return_value = mock_router_instance
        mock_manager.config = {}

        response = client.post("/models/health-check/free-model")
        assert response.status_code == 200
        daten = response.json()
        assert daten["is_permanent"] is True

    @patch("backend.routers.model_health.manager")
    @patch("backend.routers.model_health.get_model_router")
    def test_modell_permanent_model_deprecated(self, mock_get_router, mock_manager):
        """Erkennt 'model deprecated' als permanent unavailable."""
        mock_router_instance = MagicMock()
        mock_router_instance.check_model_health = AsyncMock(
            return_value=(False, "Model deprecated, please migrate to v2")
        )
        mock_router_instance.permanently_unavailable = {}
        mock_get_router.return_value = mock_router_instance
        mock_manager.config = {}

        response = client.post("/models/health-check/old-model")
        assert response.status_code == 200
        daten = response.json()
        assert daten["is_permanent"] is True

    @patch("backend.routers.model_health.manager")
    @patch("backend.routers.model_health.get_model_router")
    def test_modell_mit_pfad_in_id(self, mock_get_router, mock_manager):
        """Unterstuetzt model_id mit Pfad-Zeichen (z.B. openrouter/vendor/model)."""
        mock_router_instance = MagicMock()
        mock_router_instance.check_model_health = AsyncMock(
            return_value=(True, "OK")
        )
        mock_router_instance.permanently_unavailable = {}
        mock_get_router.return_value = mock_router_instance
        mock_manager.config = {}

        response = client.post("/models/health-check/openrouter/xiaomi/mimo-v2-flash:free")
        assert response.status_code == 200
        daten = response.json()
        assert daten["model"] == "openrouter/xiaomi/mimo-v2-flash:free"

    @patch("backend.routers.model_health.manager")
    @patch("backend.routers.model_health.get_model_router")
    def test_check_single_exception_gibt_500(self, mock_get_router, mock_manager):
        """Bei Exception wird 500 zurueckgegeben."""
        mock_get_router.side_effect = Exception("Router nicht initialisiert")
        mock_manager.config = {}

        response = client.post("/models/health-check/gpt-4")
        assert response.status_code == 500


# =========================================================================
# TestGetHealthStatus — GET /models/health-status
# =========================================================================

class TestGetHealthStatus:
    """Tests fuer den GET /models/health-status Endpoint."""

    @patch("backend.routers.model_health.manager")
    @patch("backend.routers.model_health.get_model_router")
    def test_health_status_ok(self, mock_get_router, mock_manager):
        """Gibt vollstaendigen Health-Status zurueck."""
        erwarteter_status = {
            "models": {"gpt-4": "available", "claude-3": "available"},
            "permanently_unavailable": {},
            "last_check": "2026-02-14T10:00:00"
        }
        mock_router_instance = MagicMock()
        mock_router_instance.get_health_status.return_value = erwarteter_status
        mock_get_router.return_value = mock_router_instance
        mock_manager.config = {}

        response = client.get("/models/health-status")
        assert response.status_code == 200
        daten = response.json()
        assert "models" in daten
        assert daten["permanently_unavailable"] == {}

    @patch("backend.routers.model_health.manager")
    @patch("backend.routers.model_health.get_model_router")
    def test_health_status_exception_gibt_error_dict(self, mock_get_router, mock_manager):
        """Bei Exception wird error-dict zurueckgegeben (kein 500)."""
        mock_get_router.side_effect = Exception("Config fehlt")
        mock_manager.config = {}

        response = client.get("/models/health-status")
        assert response.status_code == 200, (
            "health-status faengt Exception und gibt error-dict zurueck"
        )
        daten = response.json()
        assert "error" in daten
        assert "Config fehlt" in daten["error"]
        assert daten["permanently_unavailable"] == {}


# =========================================================================
# TestRecheckUnavailable — POST /models/recheck-unavailable
# =========================================================================

class TestRecheckUnavailable:
    """Tests fuer den POST /models/recheck-unavailable Endpoint."""

    @patch("backend.routers.model_health.manager")
    @patch("backend.routers.model_health.get_model_router")
    def test_recheck_erfolgreich(self, mock_get_router, mock_manager):
        """Gibt Recheck-Ergebnisse und verbleibende unavailable zurueck."""
        mock_router_instance = MagicMock()
        mock_router_instance.recheck_unavailable_models = AsyncMock(
            return_value={"old-model": False, "fixed-model": True}
        )
        mock_router_instance.permanently_unavailable = {"old-model": "deprecated"}
        mock_get_router.return_value = mock_router_instance
        mock_manager.config = {}

        response = client.post("/models/recheck-unavailable")
        assert response.status_code == 200
        daten = response.json()
        assert daten["status"] == "ok"
        assert "old-model" in daten["still_unavailable"]

    @patch("backend.routers.model_health.manager")
    @patch("backend.routers.model_health.get_model_router")
    def test_recheck_alle_wieder_verfuegbar(self, mock_get_router, mock_manager):
        """Leere still_unavailable wenn alle Modelle wieder verfuegbar."""
        mock_router_instance = MagicMock()
        mock_router_instance.recheck_unavailable_models = AsyncMock(return_value={})
        mock_router_instance.permanently_unavailable = {}
        mock_get_router.return_value = mock_router_instance
        mock_manager.config = {}

        response = client.post("/models/recheck-unavailable")
        assert response.status_code == 200
        daten = response.json()
        assert daten["still_unavailable"] == []

    @patch("backend.routers.model_health.manager")
    @patch("backend.routers.model_health.get_model_router")
    def test_recheck_exception_gibt_500(self, mock_get_router, mock_manager):
        """Bei Exception wird 500 zurueckgegeben."""
        mock_get_router.side_effect = Exception("Netzwerkfehler")
        mock_manager.config = {}

        response = client.post("/models/recheck-unavailable")
        assert response.status_code == 500


# =========================================================================
# TestReactivateModel — POST /models/reactivate/{model_id}
# =========================================================================

class TestReactivateModel:
    """Tests fuer den POST /models/reactivate/{model_id} Endpoint."""

    @patch("backend.routers.model_health.manager")
    @patch("backend.routers.model_health.get_model_router")
    def test_reactivate_erfolgreich(self, mock_get_router, mock_manager):
        """Reaktiviert Modell erfolgreich."""
        mock_router_instance = MagicMock()
        mock_router_instance.reactivate_model.return_value = True
        mock_get_router.return_value = mock_router_instance
        mock_manager.config = {}

        response = client.post("/models/reactivate/gpt-4")
        assert response.status_code == 200
        daten = response.json()
        assert daten["status"] == "ok"
        assert daten["reactivated"] is True
        assert daten["model"] == "gpt-4"

    @patch("backend.routers.model_health.manager")
    @patch("backend.routers.model_health.get_model_router")
    def test_reactivate_nicht_gefunden(self, mock_get_router, mock_manager):
        """Gibt not_found zurueck wenn Modell nicht in unavailable Liste."""
        mock_router_instance = MagicMock()
        mock_router_instance.reactivate_model.return_value = False
        mock_get_router.return_value = mock_router_instance
        mock_manager.config = {}

        response = client.post("/models/reactivate/unbekannt")
        assert response.status_code == 200
        daten = response.json()
        assert daten["status"] == "not_found"
        assert daten["reactivated"] is False

    @patch("backend.routers.model_health.manager")
    @patch("backend.routers.model_health.get_model_router")
    def test_reactivate_mit_pfad_id(self, mock_get_router, mock_manager):
        """Unterstuetzt model_id mit Pfad-Separatoren."""
        mock_router_instance = MagicMock()
        mock_router_instance.reactivate_model.return_value = True
        mock_get_router.return_value = mock_router_instance
        mock_manager.config = {}

        response = client.post("/models/reactivate/openrouter/vendor/model-name")
        assert response.status_code == 200
        daten = response.json()
        assert daten["model"] == "openrouter/vendor/model-name"

    @patch("backend.routers.model_health.manager")
    @patch("backend.routers.model_health.get_model_router")
    def test_reactivate_exception_gibt_500(self, mock_get_router, mock_manager):
        """Bei Exception wird 500 zurueckgegeben."""
        mock_get_router.side_effect = Exception("Interner Fehler")
        mock_manager.config = {}

        response = client.post("/models/reactivate/gpt-4")
        assert response.status_code == 500
