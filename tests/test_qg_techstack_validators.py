# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 06.02.2026
Version: 1.0
Beschreibung: Unit Tests fuer QualityGate TechStack-Validierungen.
              Tests validieren validate_techstack, validate_schema,
              validate_code und validate_design.
"""

import pytest
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.qg_techstack_validators import (
    validate_techstack, validate_schema, validate_code, validate_design
)
from backend.validation_result import ValidationResult


# =========================================================================
# Fixtures
# =========================================================================

@pytest.fixture
def standard_requirements():
    """Standard-Anforderungen fuer Tests."""
    return {
        "database": "sqlite", "language": "python",
        "framework": "flask", "ui_type": "webapp"
    }


@pytest.fixture
def standard_blueprint():
    """Standard TechStack-Blueprint fuer Tests."""
    return {
        "language": "python", "framework": "flask", "database": "sqlite",
        "app_type": "webapp", "project_type": "flask_webapp",
        "requires_server": True, "server_port": 5000
    }


@pytest.fixture
def python_code():
    """Beispiel Python-Code fuer Tests."""
    return (
        "import sqlite3\n"
        "from flask import Flask, render_template, request\n\n"
        "app = Flask(__name__)\n\n"
        "def get_db():\n"
        "    conn = sqlite3.connect('app.db')\n"
        "    return conn\n\n"
        "@app.route('/')\n"
        "def index():\n"
        "    return render_template('index.html')\n\n"
        "if __name__ == '__main__':\n"
        "    app.run(debug=True)\n"
    )


@pytest.fixture
def javascript_code():
    """Beispiel JavaScript-Code fuer Tests."""
    return (
        "const express = require('express');\n"
        "const app = express();\n"
        "let port = 3000;\n\n"
        "function startServer() {\n"
        "    app.listen(port, () => {\n"
        "        console.log('Server running');\n"
        "    });\n"
        "}\n\n"
        "app.get('/', (req, res) => { res.send('Hello'); });\n"
        "startServer();\n"
    )


@pytest.fixture
def sql_schema():
    """Beispiel SQL-Schema fuer Tests (> 50 Zeichen)."""
    return (
        "CREATE TABLE users (\n"
        "    id INTEGER PRIMARY KEY AUTOINCREMENT,\n"
        "    username TEXT NOT NULL UNIQUE,\n"
        "    email TEXT NOT NULL,\n"
        "    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP\n"
        ");\n\n"
        "CREATE TABLE tasks (\n"
        "    id INTEGER PRIMARY KEY AUTOINCREMENT,\n"
        "    title TEXT NOT NULL,\n"
        "    description TEXT,\n"
        "    user_id INTEGER,\n"
        "    FOREIGN KEY (user_id) REFERENCES users(id)\n"
        ");\n"
    )


# =========================================================================
# Tests: validate_techstack
# =========================================================================

class TestValidateTechstack:
    """Tests fuer die TechStack-Blueprint-Validierung."""

    def test_alles_ok(self, standard_requirements, standard_blueprint):
        """Alle Anforderungen passen zum Blueprint - passed=True, keine Issues."""
        result = validate_techstack(standard_requirements, standard_blueprint)
        assert result.passed is True, f"passed erwartet, Issues: {result.issues}"
        assert len(result.issues) == 0, f"Keine Issues erwartet: {result.issues}"

    def test_datenbank_mismatch(self):
        """Benutzer fordert sqlite, Blueprint hat postgres - Issue erwartet."""
        result = validate_techstack({"database": "sqlite"}, {"database": "postgres"})
        assert result.passed is False, "passed=False bei DB-Mismatch erwartet"
        assert len(result.issues) >= 1, "Mindestens 1 Issue erwartet"
        assert "sqlite" in result.issues[0].lower() or "postgres" in result.issues[0].lower()

    def test_datenbank_fehlt(self):
        """Benutzer fordert sqlite, Blueprint ohne Datenbank - Issue erwartet."""
        result = validate_techstack({"database": "sqlite"}, {"language": "python"})
        assert result.passed is False, "passed=False bei fehlender DB erwartet"
        assert len(result.issues) >= 1, "Mindestens 1 Issue erwartet"

    def test_sprache_mismatch(self):
        """Benutzer fordert python, Blueprint hat javascript - Issue erwartet."""
        result = validate_techstack({"language": "python"}, {"language": "javascript"})
        assert result.passed is False, "passed=False bei Sprach-Mismatch erwartet"
        assert any("python" in i.lower() for i in result.issues), f"'python' in Issues erwartet: {result.issues}"

    def test_framework_warning(self):
        """Framework-Mismatch erzeugt Warning, kein Issue - passed bleibt True."""
        result = validate_techstack({"framework": "flask"}, {"project_type": "python_script"})
        assert result.passed is True, f"passed=True erwartet (nur Warning). Issues: {result.issues}"
        assert len(result.warnings) >= 1, "Mindestens 1 Warning erwartet"
        assert any("flask" in w.lower() for w in result.warnings), f"'flask' in Warnings erwartet: {result.warnings}"

    def test_ui_typ_desktop_mismatch(self):
        """Benutzer fordert Desktop, Blueprint hat webapp - Issue erwartet."""
        result = validate_techstack({"ui_type": "desktop"}, {"app_type": "webapp"})
        assert result.passed is False, "passed=False bei UI-Mismatch erwartet"
        assert any("desktop" in i.lower() for i in result.issues), f"'desktop' in Issues erwartet: {result.issues}"

    def test_requires_server_ohne_port(self):
        """requires_server=True ohne server_port - Warning erwartet."""
        result = validate_techstack({}, {"requires_server": True})
        assert result.passed is True, "passed=True erwartet (nur Warning)"
        assert any("server_port" in w.lower() for w in result.warnings), f"server_port Warning erwartet: {result.warnings}"

    def test_score_berechnung(self):
        """Score sinkt korrekt mit Issues (-0.3) und Warnings (-0.1)."""
        # Keine Probleme: Score = 1.0
        result_ok = validate_techstack({}, {"requires_server": False})
        assert result_ok.score == 1.0, f"Score 1.0 erwartet, erhalten: {result_ok.score}"

        # 1 Issue: Score = 0.7
        result_issue = validate_techstack({"language": "python"}, {"language": "javascript"})
        assert result_issue.score == pytest.approx(0.7, abs=0.01), f"Score ~0.7 erwartet: {result_issue.score}"

        # 1 Warning: Score = 0.9
        result_warn = validate_techstack({"framework": "flask"}, {"project_type": "python_script"})
        assert result_warn.score == pytest.approx(0.9, abs=0.01), f"Score ~0.9 erwartet: {result_warn.score}"

    def test_generic_db_wird_ignoriert(self):
        """generic_db ist Platzhalter und erzeugt keinen Mismatch."""
        result = validate_techstack({"database": "generic_db"}, {"database": "postgres"})
        assert result.passed is True, f"passed=True bei generic_db erwartet. Issues: {result.issues}"


# =========================================================================
# Tests: validate_schema
# =========================================================================

class TestValidateSchema:
    """Tests fuer die DB-Schema-Validierung."""

    def test_schema_fehlt_bei_db_anforderung(self):
        """Datenbank gefordert aber kein Schema - Issue erwartet."""
        result = validate_schema({"database": "sqlite"}, "", {"database": "sqlite"})
        assert result.passed is False, "passed=False bei fehlendem Schema erwartet"
        assert len(result.issues) >= 1, "Mindestens 1 Issue erwartet"

    def test_valides_sql_schema(self, sql_schema):
        """Gueltiges SQL-Schema mit CREATE TABLE - keine Issues."""
        result = validate_schema({"database": "sqlite"}, sql_schema, {"database": "sqlite"})
        assert result.passed is True, f"passed=True erwartet. Issues: {result.issues}"

    def test_zu_kurzes_schema(self):
        """Schema < 50 Zeichen - Warning erwartet."""
        result = validate_schema({}, "CREATE TABLE t (id INT);", {})
        assert len(result.warnings) >= 1, "Mindestens 1 Warning erwartet"
        assert any("kurz" in w.lower() for w in result.warnings), f"'kurz' in Warning erwartet: {result.warnings}"

    def test_mongodb_schema_warnung(self):
        """MongoDB ohne Collection-Keyword - Warning erwartet."""
        mongo_schema = (
            "// MongoDB Datenbank-Konfiguration fuer die Applikation\n"
            "// Hier werden die Strukturen definiert fuer Benutzer und Aufgaben\n"
            "db.createIndex({field: 1});"
        )
        result = validate_schema({}, mongo_schema, {"database": "mongodb"})
        assert any("mongodb" in w.lower() or "collection" in w.lower() for w in result.warnings), \
            f"MongoDB/Collection-Warnung erwartet: {result.warnings}"

    def test_schema_ohne_db_anforderung(self):
        """Kein Schema und keine DB-Anforderung - kein Issue."""
        result = validate_schema({}, "", {})
        assert result.passed is True, "passed=True ohne DB-Anforderung erwartet"


# =========================================================================
# Tests: validate_code
# =========================================================================

class TestValidateCode:
    """Tests fuer die Code-Validierung gegen Blueprint."""

    def test_leerer_code(self):
        """Leerer/kurzer/None Code - passed=False und Issue erwartet."""
        bp = {"language": "python"}
        # Komplett leer
        assert validate_code({}, "", bp).passed is False, "passed=False bei leerem Code erwartet"
        # Zu kurz (< 10 Zeichen)
        assert validate_code({}, "x = 1", bp).passed is False, "passed=False bei kurzem Code erwartet"
        # None-Wert
        assert validate_code({}, None, bp).passed is False, "passed=False bei None-Code erwartet"

    def test_python_code_ok(self, python_code):
        """Python-Code mit def/import - keine Language-Warnings."""
        result = validate_code({}, python_code, {"language": "python"})
        assert result.passed is True, f"passed=True erwartet. Issues: {result.issues}"
        py_warns = [w for w in result.warnings if "python" in w.lower()]
        assert len(py_warns) == 0, f"Keine Python-Keyword-Warnung erwartet: {py_warns}"

    def test_javascript_code_ok(self, javascript_code):
        """JavaScript-Code mit function/const/let - keine Language-Warnings."""
        result = validate_code({}, javascript_code, {"language": "javascript"})
        assert result.passed is True, f"passed=True erwartet. Issues: {result.issues}"
        js_warns = [w for w in result.warnings if "javascript" in w.lower()]
        assert len(js_warns) == 0, f"Keine JS-Keyword-Warnung erwartet: {js_warns}"

    def test_db_usage_fehlt(self):
        """Datenbank gefordert, Code ohne DB-Indikatoren - Warning erwartet."""
        code_ohne_db = (
            "import os\n\n"
            "def process_data():\n"
            "    data = [1, 2, 3, 4, 5]\n"
            "    for item in data:\n"
            "        print(item)\n\n"
            "if __name__ == '__main__':\n"
            "    process_data()\n"
        )
        result = validate_code({"database": "sqlite"}, code_ohne_db, {"language": "python"})
        assert any("sqlite" in w.lower() or "datenbank" in w.lower() for w in result.warnings), \
            f"DB-Warnung erwartet: {result.warnings}"

    def test_framework_usage_ok(self, python_code):
        """Flask im project_type, Code hat Flask-Imports - keine Warning."""
        result = validate_code({}, python_code, {"language": "python", "project_type": "flask_webapp"})
        fw_warns = [w for w in result.warnings if "flask" in w.lower() and "import" in w.lower()]
        assert len(fw_warns) == 0, f"Keine Flask-Import-Warnung erwartet: {fw_warns}"

    def test_framework_usage_fehlt(self):
        """Flask im project_type, Code ohne Flask-Imports - Warning erwartet."""
        code_ohne_flask = (
            "import os\nimport json\n\n"
            "def main():\n"
            "    data = json.loads('{\"key\": \"value\"}')\n"
            "    print(data)\n\n"
            "if __name__ == '__main__':\n"
            "    main()\n"
        )
        result = validate_code({}, code_ohne_flask, {"language": "python", "project_type": "flask_webapp"})
        assert any("flask" in w.lower() for w in result.warnings), f"Flask-Warnung erwartet: {result.warnings}"

    def test_score_null_bei_leerem_code(self):
        """Score = 0.0 bei leerem Code."""
        result = validate_code({}, "", {"language": "python"})
        assert result.score == 0.0, f"Score 0.0 erwartet, erhalten: {result.score}"


# =========================================================================
# Tests: validate_design
# =========================================================================

class TestValidateDesign:
    """Tests fuer die Design-Konzept-Validierung."""

    def test_kurzes_design(self):
        """Design < 50 Zeichen - Warning erwartet."""
        result = validate_design("Ein kurzes Design.", {"app_type": "webapp"})
        assert any("kurz" in w.lower() for w in result.warnings), f"'kurz' Warning erwartet: {result.warnings}"

    def test_desktop_design_ohne_fenster(self):
        """Desktop-App ohne Fenster/Window/GUI Keywords - Warning erwartet."""
        design = (
            "Die Applikation bietet eine moderne Benutzeroberflaeche "
            "mit verschiedenen Funktionen fuer die Datenverwaltung und "
            "Verarbeitung von Benutzeranfragen im System."
        )
        result = validate_design(design, {"app_type": "desktop"})
        assert any("desktop" in w.lower() or "fenster" in w.lower() or "gui" in w.lower()
                    for w in result.warnings), f"Desktop/GUI-Warnung erwartet: {result.warnings}"

    def test_webapp_design_ok(self):
        """Webapp-Design mit 'Seite' Keyword - keine Warnung."""
        design = (
            "Die Webanwendung besteht aus mehreren Seiten: "
            "eine Startseite mit Uebersicht, eine Detailseite "
            "fuer einzelne Eintraege und eine Konfigurationsseite "
            "fuer die Benutzereinstellungen."
        )
        result = validate_design(design, {"app_type": "webapp"})
        webapp_warns = [w for w in result.warnings if "webapp" in w.lower() or "seite" in w.lower()]
        assert len(webapp_warns) == 0, f"Keine Webapp-Warnung erwartet: {webapp_warns}"

    def test_desktop_design_mit_fenster(self):
        """Desktop-Design mit 'Fenster' Keyword - keine Warnung."""
        design = (
            "Die Desktop-Anwendung oeffnet ein Hauptfenster "
            "mit einer Menueleiste und verschiedenen Fenster-Elementen "
            "fuer die Dateneingabe und Bearbeitung."
        )
        result = validate_design(design, {"app_type": "desktop"})
        desktop_warns = [w for w in result.warnings if "desktop" in w.lower() or "fenster" in w.lower()]
        assert len(desktop_warns) == 0, f"Keine Desktop-Warnung erwartet: {desktop_warns}"

    def test_leeres_design(self):
        """Leeres Design-Konzept - Warning erwartet."""
        result = validate_design("", {"app_type": "webapp"})
        assert any("kurz" in w.lower() for w in result.warnings), f"'kurz' Warning erwartet: {result.warnings}"

    def test_none_design(self):
        """None als Design-Konzept - Warning, kein Crash."""
        result = validate_design(None, {"app_type": "webapp"})
        assert result.passed is True, "passed=True erwartet (nur Warnungen)"
        assert len(result.warnings) >= 1, "Mindestens 1 Warning bei None erwartet"

    def test_design_ohne_app_type(self):
        """Blueprint ohne app_type - keine Typ-spezifische Warnung."""
        design = (
            "Die Applikation bietet verschiedene Funktionen "
            "fuer die Verarbeitung und Darstellung von Daten "
            "in einem modernen und benutzerfreundlichen Format."
        )
        result = validate_design(design, {})
        assert result.passed is True, "passed=True ohne app_type erwartet"


# =========================================================================
# Tests: ValidationResult Struktur
# =========================================================================

class TestValidationResultStruktur:
    """Tests fuer die korrekte Struktur des ValidationResult."""

    def test_result_hat_alle_felder(self, standard_requirements, standard_blueprint):
        """ValidationResult enthaelt alle erwarteten Felder."""
        result = validate_techstack(standard_requirements, standard_blueprint)
        for feld in ["passed", "issues", "warnings", "score", "details"]:
            assert hasattr(result, feld), f"ValidationResult fehlt '{feld}' Feld"

    def test_score_bereich(self, standard_requirements, standard_blueprint):
        """Score liegt zwischen 0.0 und 1.0."""
        result = validate_techstack(standard_requirements, standard_blueprint)
        assert 0.0 <= result.score <= 1.0, f"Score ausserhalb 0.0-1.0: {result.score}"

    def test_score_minimum_bei_vielen_issues(self):
        """Score faellt nicht unter 0.0 auch bei vielen Issues."""
        requirements = {"database": "sqlite", "language": "python", "ui_type": "desktop"}
        blueprint = {"database": "postgres", "language": "javascript", "app_type": "webapp"}
        result = validate_techstack(requirements, blueprint)
        assert result.score >= 0.0, f"Score >= 0.0 erwartet: {result.score}"
        assert result.passed is False, "passed=False bei mehreren Issues erwartet"
