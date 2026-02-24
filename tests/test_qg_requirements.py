# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 14.02.2026
Version: 1.0
Beschreibung: Tests fuer backend/qg_requirements.py —
              Anforderungs-Extraktion aus User-Goals.
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.qg_requirements import extract_requirements, get_requirements_summary


# =========================================================================
# TestExtractRequirements
# =========================================================================

class TestExtractRequirements:
    """Tests fuer extract_requirements()."""

    # --- Datenbank-Erkennung ---

    def test_sqlite_erkennung(self):
        """SQLite wird als Datenbank erkannt."""
        r = extract_requirements("Erstelle eine App mit SQLite Datenbank")
        assert r.get("database") == "sqlite"

    def test_postgres_erkennung(self):
        """PostgreSQL wird erkannt (auch als 'postgresql')."""
        r = extract_requirements("Backend mit PostgreSQL")
        assert r.get("database") == "postgres"

    def test_mongodb_erkennung(self):
        """MongoDB wird erkannt (auch als 'mongo')."""
        r = extract_requirements("Speichere Daten in Mongo")
        assert r.get("database") == "mongodb"

    def test_redis_erkennung(self):
        """Redis wird erkannt."""
        r = extract_requirements("Cache mit Redis")
        assert r.get("database") == "redis"

    def test_generische_datenbank(self):
        """'Datenbank' ohne spezifisches System wird als generic_db erkannt."""
        r = extract_requirements("App mit einer Datenbank")
        assert r.get("database") == "generic_db"

    def test_keine_datenbank(self):
        """Ohne DB-Keywords fehlt 'database' im Ergebnis."""
        r = extract_requirements("Erstelle einen Taschenrechner")
        assert "database" not in r

    # --- Sprach-Erkennung ---

    def test_python_erkennung(self):
        """Python wird als Sprache erkannt."""
        r = extract_requirements("Schreibe in Python")
        assert r.get("language") == "python"

    def test_javascript_erkennung(self):
        """JavaScript wird erkannt."""
        r = extract_requirements("Mit JavaScript erstellen")
        assert r.get("language") == "javascript"

    def test_typescript_wird_javascript(self):
        """TypeScript wird zu 'javascript' gemappt."""
        r = extract_requirements("In TypeScript programmieren")
        assert r.get("language") == "javascript"

    def test_go_erkennung(self):
        """Go (auch 'golang') wird erkannt."""
        r = extract_requirements("Erstelle einen Server in Golang")
        assert r.get("language") == "go"

    def test_rust_erkennung(self):
        """Rust wird erkannt."""
        r = extract_requirements("CLI in Rust")
        assert r.get("language") == "rust"

    def test_keine_sprache(self):
        """Ohne Sprach-Keywords fehlt 'language' im Ergebnis."""
        r = extract_requirements("Erstelle eine schöne App")
        assert "language" not in r

    # --- Framework-Erkennung ---

    def test_flask_erkennung(self):
        """Flask wird als Framework erkannt."""
        r = extract_requirements("Web-App mit Flask")
        assert r.get("framework") == "flask"

    def test_react_erkennung(self):
        """React wird erkannt."""
        r = extract_requirements("Frontend in React")
        assert r.get("framework") == "react"

    def test_fastapi_erkennung(self):
        """FastAPI wird erkannt."""
        r = extract_requirements("REST-API mit FastAPI")
        assert r.get("framework") == "fastapi"

    def test_django_erkennung(self):
        """Django wird erkannt."""
        r = extract_requirements("Webseite mit Django")
        assert r.get("framework") == "django"

    def test_streamlit_erkennung(self):
        """Streamlit wird erkannt."""
        r = extract_requirements("Dashboard mit Streamlit")
        assert r.get("framework") == "streamlit"

    def test_kein_framework(self):
        """Ohne Framework-Keywords fehlt 'framework' im Ergebnis."""
        r = extract_requirements("Einfaches Script")
        assert "framework" not in r

    # --- UI-Typ-Erkennung ---

    def test_webapp_explizit(self):
        """'webapp' wird als UI-Typ erkannt."""
        r = extract_requirements("Erstelle eine Webapp")
        assert r.get("ui_type") == "webapp"

    def test_website_erkennung(self):
        """'website' wird als webapp erkannt."""
        r = extract_requirements("Baue eine Website")
        assert r.get("ui_type") == "webapp"

    def test_desktop_erkennung(self):
        """'desktop' wird erkannt."""
        r = extract_requirements("Desktop App erstellen")
        assert r.get("ui_type") == "desktop"

    def test_api_erkennung(self):
        """'api' wird als UI-Typ erkannt."""
        r = extract_requirements("REST API bauen")
        assert r.get("ui_type") == "api"

    def test_cli_erkennung(self):
        """'cli' wird als UI-Typ erkannt."""
        r = extract_requirements("CLI Tool erstellen")
        assert r.get("ui_type") == "cli"

    def test_webapp_vorrang_vor_desktop_bei_beiden(self):
        """Wenn webapp UND desktop erwaehnt werden, gewinnt webapp."""
        r = extract_requirements("Desktop und Web App im Browser")
        assert r.get("ui_type") == "webapp"

    def test_gui_ohne_kontext_wird_erkannt(self):
        """'gui' wird als UI-Typ erkannt (Desktop-Fallback)."""
        r = extract_requirements("Erstelle eine GUI Anwendung")
        assert "ui_type" in r

    def test_kein_ui_typ(self):
        """Ohne UI-Keywords fehlt 'ui_type' im Ergebnis."""
        r = extract_requirements("Berechne Fibonacci Zahlen")
        assert "ui_type" not in r

    # --- Kombinierte Erkennung ---

    def test_kombination_sprache_framework_db(self):
        """Mehrere Anforderungen werden gleichzeitig erkannt."""
        r = extract_requirements("Python Flask Webapp mit SQLite")
        assert r.get("language") == "python"
        assert r.get("framework") == "flask"
        assert r.get("database") == "sqlite"
        assert r.get("ui_type") == "webapp"

    def test_leerer_goal(self):
        """Leerer Goal ergibt leeres Dict."""
        r = extract_requirements("")
        assert r == {}

    def test_case_insensitive(self):
        """Erkennung ist case-insensitive."""
        r = extract_requirements("PYTHON FLASK SQLITE")
        assert r.get("language") == "python"
        assert r.get("framework") == "flask"
        assert r.get("database") == "sqlite"


# =========================================================================
# TestGetRequirementsSummary
# =========================================================================

class TestGetRequirementsSummary:
    """Tests fuer get_requirements_summary()."""

    def test_leere_anforderungen(self):
        """Leeres Dict ergibt Standard-Nachricht."""
        result = get_requirements_summary({})
        assert "Keine spezifischen Anforderungen" in result

    def test_nur_datenbank(self):
        """Nur Datenbank wird angezeigt."""
        result = get_requirements_summary({"database": "sqlite"})
        assert "Datenbank: sqlite" in result

    def test_nur_sprache(self):
        """Nur Sprache wird angezeigt."""
        result = get_requirements_summary({"language": "python"})
        assert "Sprache: python" in result

    def test_nur_framework(self):
        """Nur Framework wird angezeigt."""
        result = get_requirements_summary({"framework": "flask"})
        assert "Framework: flask" in result

    def test_nur_ui_typ(self):
        """Nur UI-Typ wird angezeigt."""
        result = get_requirements_summary({"ui_type": "webapp"})
        assert "UI-Typ: webapp" in result

    def test_alle_felder(self):
        """Alle Felder werden komma-getrennt angezeigt."""
        result = get_requirements_summary({
            "database": "postgres",
            "language": "python",
            "framework": "fastapi",
            "ui_type": "api"
        })
        assert "Datenbank: postgres" in result
        assert "Sprache: python" in result
        assert "Framework: fastapi" in result
        assert "UI-Typ: api" in result
        assert ", " in result

    def test_unbekannte_felder_ignoriert(self):
        """Unbekannte Felder werden nicht angezeigt."""
        result = get_requirements_summary({"unknown_key": "value"})
        assert "Keine spezifischen Anforderungen" in result
