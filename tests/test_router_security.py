# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 14.02.2026
Version: 1.0
Beschreibung: Unit-Tests fuer backend/routers/security.py.
              Testet die Security-Endpoints (POST /security-feedback,
              GET /security-status) mit gemocktem manager und limiter.
"""
# ÄNDERUNG 22.02.2026: Fehlerbehandlung und DUMMY-WERT-Kommentare ergänzt.
# Hintergrund: Test robuster gegen unerwartete Exceptions gemacht.

import os
import sys
import logging
import pytest
from unittest.mock import MagicMock, patch, PropertyMock

# Projekt-Root zum Python-Path hinzufuegen
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI
from fastapi.testclient import TestClient
from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.middleware.trustedhost import TrustedHostMiddleware

from backend.routers.security import router

# Test-App mit eingebundenem Router erstellen
# Rate-Limiter muss fuer Tests konfiguriert werden
app = FastAPI()
# SlowAPI Limiter fuer Tests: kein echtes Rate-Limiting
test_limiter = Limiter(key_func=get_remote_address, enabled=False)
app.state.limiter = test_limiter
app.include_router(router)
client = TestClient(app)


# =========================================================================
# TestTriggerSecurityFix — POST /security-feedback
# =========================================================================

class TestTriggerSecurityFix:
    """Tests fuer den POST /security-feedback Endpoint."""

    @patch("backend.routers.security.limiter")
    @patch("backend.routers.security.manager")
    def test_security_fix_aktiviert(self, mock_manager, mock_limiter):
        """Setzt force_security_fix auf True."""
        try:
            # DUMMY-WERT: Nur für Tests - NICHT produktiv verwenden!
            mock_manager.force_security_fix = False
            # DUMMY-WERT: Nur für Tests - NICHT produktiv verwenden!
            mock_manager.security_vulnerabilities = [
                {"id": "vuln-1", "severity": "HIGH"},
                {"id": "vuln-2", "severity": "MEDIUM"}
            ]
            # Limiter deaktivieren fuer Tests
            mock_limiter.limit.return_value = lambda f: f

            response = client.post("/security-feedback")
            assert response.status_code == 200
            daten = response.json()
            assert daten["status"] == "ok", (
                f"Erwartet: status='ok', Erhalten: '{daten['status']}'"
            )
            assert daten["vulnerabilities_count"] == 2
        except Exception as e:
            logging.error("Fehler in test_security_fix_aktiviert: %s", e)
            raise

    @patch("backend.routers.security.limiter")
    @patch("backend.routers.security.manager")
    def test_security_fix_ohne_vulnerabilities_attribut(self, mock_manager, mock_limiter):
        """Gibt count=0 zurueck wenn security_vulnerabilities nicht existiert."""
        mock_manager.force_security_fix = False
        # hasattr soll False zurueckgeben
        del mock_manager.security_vulnerabilities
        mock_limiter.limit.return_value = lambda f: f

        response = client.post("/security-feedback")
        assert response.status_code == 200
        daten = response.json()
        assert daten["vulnerabilities_count"] == 0

    @patch("backend.routers.security.limiter")
    @patch("backend.routers.security.manager")
    def test_security_fix_leere_vulnerabilities(self, mock_manager, mock_limiter):
        """Gibt count=0 zurueck bei leerer Vulnerabilities-Liste."""
        mock_manager.force_security_fix = False
        mock_manager.security_vulnerabilities = []
        mock_limiter.limit.return_value = lambda f: f

        response = client.post("/security-feedback")
        assert response.status_code == 200
        daten = response.json()
        assert daten["vulnerabilities_count"] == 0

    @patch("backend.routers.security.limiter")
    @patch("backend.routers.security.manager")
    def test_security_fix_nachricht_enthaelt_count(self, mock_manager, mock_limiter):
        """Antwortnachricht enthaelt die Anzahl der Vulnerabilities."""
        mock_manager.force_security_fix = False
        mock_manager.security_vulnerabilities = [{"id": "v1"}, {"id": "v2"}, {"id": "v3"}]
        mock_limiter.limit.return_value = lambda f: f

        response = client.post("/security-feedback")
        assert response.status_code == 200
        daten = response.json()
        assert "3" in daten["message"], (
            f"Nachricht sollte '3' enthalten, ist aber: '{daten['message']}'"
        )


# =========================================================================
# TestGetSecurityStatus — GET /security-status
# =========================================================================

class TestGetSecurityStatus:
    """Tests fuer den GET /security-status Endpoint."""

    @patch("backend.routers.security.manager")
    def test_status_mit_vulnerabilities(self, mock_manager):
        """Gibt Vulnerabilities und force_security_fix zurueck."""
        mock_manager.security_vulnerabilities = [
            {"id": "vuln-1", "severity": "HIGH"}
        ]
        mock_manager.force_security_fix = True

        response = client.get("/security-status")
        assert response.status_code == 200
        daten = response.json()
        assert daten["force_security_fix"] is True
        assert daten["count"] == 1
        assert len(daten["vulnerabilities"]) == 1

    @patch("backend.routers.security.manager")
    def test_status_ohne_vulnerabilities_attribut(self, mock_manager):
        """Gibt Defaults zurueck wenn Attribute nicht existieren."""
        # Entferne Attribute damit hasattr() False liefert
        del mock_manager.security_vulnerabilities
        del mock_manager.force_security_fix

        response = client.get("/security-status")
        assert response.status_code == 200
        daten = response.json()
        assert daten["vulnerabilities"] == []
        assert daten["force_security_fix"] is False
        assert daten["count"] == 0

    @patch("backend.routers.security.manager")
    def test_status_force_fix_false(self, mock_manager):
        """Gibt force_security_fix=False zurueck wenn nicht aktiviert."""
        mock_manager.security_vulnerabilities = []
        mock_manager.force_security_fix = False

        response = client.get("/security-status")
        assert response.status_code == 200
        daten = response.json()
        assert daten["force_security_fix"] is False
        assert daten["count"] == 0

    @patch("backend.routers.security.manager")
    def test_status_mehrere_vulnerabilities(self, mock_manager):
        """Count stimmt mit Anzahl der Vulnerabilities ueberein."""
        vulns = [{"id": f"v{i}"} for i in range(5)]
        mock_manager.security_vulnerabilities = vulns
        mock_manager.force_security_fix = False

        response = client.get("/security-status")
        assert response.status_code == 200
        daten = response.json()
        assert daten["count"] == 5, (
            f"Erwartet: count=5, Erhalten: {daten['count']}"
        )
        assert len(daten["vulnerabilities"]) == 5

    @patch("backend.routers.security.manager")
    def test_status_exception_gibt_500(self, mock_manager):
        """Bei Exception im Manager wird 500 zurueckgegeben."""
        # Konfiguriere Mock so dass Zugriff auf security_vulnerabilities
        # eine Exception wirft
        type(mock_manager).security_vulnerabilities = PropertyMock(
            side_effect=Exception("Interner Fehler")
        )

        response = client.get("/security-status")
        assert response.status_code == 500, (
            f"Erwartet: 500, Erhalten: {response.status_code}"
        )
