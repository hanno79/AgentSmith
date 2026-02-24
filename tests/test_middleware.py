# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 14.02.2026
Version: 1.0
Beschreibung: Tests fuer backend/middleware.py — SecurityHeadersMiddleware.
              Nutzt Starlette TestClient fuer HTTP-Header-Verifikation.
"""

import pytest
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.testclient import TestClient

from backend.middleware import SecurityHeadersMiddleware


# =========================================================================
# TestSecurityHeadersMiddleware
# =========================================================================

class TestSecurityHeadersMiddleware:
    """Tests fuer SecurityHeadersMiddleware."""

    @pytest.fixture
    def client(self):
        """Erstellt einen TestClient mit Middleware."""
        app = Starlette()
        app.add_middleware(SecurityHeadersMiddleware)

        @app.route("/test")
        async def test_route(request):
            return PlainTextResponse("OK")

        return TestClient(app)

    def test_x_content_type_options(self, client):
        """X-Content-Type-Options Header ist gesetzt."""
        response = client.get("/test")
        assert response.headers["X-Content-Type-Options"] == "nosniff"

    def test_x_frame_options(self, client):
        """X-Frame-Options Header ist gesetzt."""
        response = client.get("/test")
        assert response.headers["X-Frame-Options"] == "DENY"

    def test_x_xss_protection(self, client):
        """X-XSS-Protection Header ist gesetzt."""
        response = client.get("/test")
        assert response.headers["X-XSS-Protection"] == "1; mode=block"

    def test_referrer_policy(self, client):
        """Referrer-Policy Header ist gesetzt."""
        response = client.get("/test")
        assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"

    def test_permissions_policy(self, client):
        """Permissions-Policy Header ist gesetzt."""
        response = client.get("/test")
        assert response.headers["Permissions-Policy"] == "geolocation=(), microphone=(), camera=()"

    def test_response_body_unveraendert(self, client):
        """Response-Body wird nicht veraendert."""
        response = client.get("/test")
        assert response.text == "OK"
        assert response.status_code == 200

    def test_alle_security_headers_vorhanden(self, client):
        """Alle 5 Security-Header sind vorhanden."""
        response = client.get("/test")
        expected_headers = [
            "X-Content-Type-Options",
            "X-Frame-Options",
            "X-XSS-Protection",
            "Referrer-Policy",
            "Permissions-Policy",
        ]
        for header in expected_headers:
            assert header in response.headers, f"Header '{header}' fehlt"
