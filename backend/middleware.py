# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 29.01.2026
Version: 1.0
Beschreibung: Middleware für Sicherheits-Header.
"""
# ÄNDERUNG 29.01.2026: SecurityHeadersMiddleware ausgelagert

from starlette.middleware.base import BaseHTTPMiddleware


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        # Note: HSTS sollte nur in Produktion mit HTTPS aktiviert werden
        # response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response
