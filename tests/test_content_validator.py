# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 28.01.2026
Version: 1.0
Beschreibung: Tests fuer Content Validator und Referenz-Validierung.
              Prueft Erkennung leerer Seiten, fehlender Dateien und run.bat-Probleme.
"""

import os
import sys
import pytest

# Projekt-Root zum Python-Path hinzufuegen
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from content_validator import validate_run_bat, ContentValidationResult
from sandbox_runner import validate_project_references


# ===== Tests fuer validate_run_bat =====

class TestValidateRunBat:
    """Tests fuer run.bat Validierung."""

    def test_fehlende_run_bat_mit_server(self, temp_dir):
        """Fehlende run.bat wird bei Server-Projekt als kritisch erkannt."""
        result = validate_run_bat(temp_dir, {"requires_server": True})
        assert len(result.issues) > 0
        assert any("run.bat fehlt" in i for i in result.issues)
        assert result.is_critical_failure

    def test_fehlende_run_bat_ohne_server(self, temp_dir):
        """Fehlende run.bat ist bei statischem Projekt nur Warnung."""
        result = validate_run_bat(temp_dir, {"requires_server": False})
        assert len(result.issues) == 0
        assert len(result.warnings) > 0

    def test_leere_run_bat(self, temp_dir):
        """Leere run.bat wird als kritisch erkannt."""
        with open(os.path.join(temp_dir, "run.bat"), "w") as f:
            f.write("@echo off\npause\n")

        result = validate_run_bat(temp_dir, {"requires_server": True})
        assert result.is_critical_failure
        assert any("leer" in i.lower() for i in result.issues)

    def test_korrekte_run_bat(self, temp_dir):
        """Korrekte run.bat mit allen Befehlen wird akzeptiert."""
        with open(os.path.join(temp_dir, "run.bat"), "w") as f:
            f.write("@echo off\nnpm install\nnpm start\npause\n")

        result = validate_run_bat(temp_dir, {
            "install_command": "npm install",
            "run_command": "npm start"
        })
        assert not result.is_critical_failure
        assert result.has_visible_content

    def test_fehlender_install_command(self, temp_dir):
        """Fehlender install_command erzeugt Warnung."""
        with open(os.path.join(temp_dir, "run.bat"), "w") as f:
            f.write("@echo off\nnpm start\npause\n")

        result = validate_run_bat(temp_dir, {
            "install_command": "pip install -r requirements.txt",
            "run_command": "npm start"
        })
        assert any("install" in w.lower() for w in result.warnings)

    def test_fehlender_run_command(self, temp_dir):
        """Fehlender run_command erzeugt Warnung."""
        with open(os.path.join(temp_dir, "run.bat"), "w") as f:
            f.write("@echo off\nnpm install\npause\n")

        result = validate_run_bat(temp_dir, {
            "install_command": "npm install",
            "run_command": "python app.py"
        })
        assert any("start-befehl" in w.lower() for w in result.warnings)


# ===== Tests fuer validate_project_references =====

class TestValidateProjectReferences:
    """Tests fuer Datei-Referenz-Validierung."""

    def test_fehlende_script_referenz(self, temp_dir):
        """Fehlende Script-Referenz wird erkannt."""
        html = '<html><head><script src="app.js"></script></head><body></body></html>'
        with open(os.path.join(temp_dir, "index.html"), "w") as f:
            f.write(html)

        result = validate_project_references(temp_dir)
        assert "❌" in result
        assert "app.js" in result

    def test_fehlende_css_referenz(self, temp_dir):
        """Fehlende CSS-Referenz wird erkannt."""
        html = '<html><head><link rel="stylesheet" href="styles.css"></head><body></body></html>'
        with open(os.path.join(temp_dir, "index.html"), "w") as f:
            f.write(html)

        result = validate_project_references(temp_dir)
        assert "❌" in result
        assert "styles.css" in result

    def test_vorhandene_referenzen(self, temp_dir):
        """Vorhandene Referenzen bestehen den Check."""
        html = '<html><head><script src="app.js"></script><link href="styles.css"></head><body></body></html>'
        with open(os.path.join(temp_dir, "index.html"), "w") as f:
            f.write(html)
        with open(os.path.join(temp_dir, "app.js"), "w") as f:
            f.write("console.log('test');")
        with open(os.path.join(temp_dir, "styles.css"), "w") as f:
            f.write("body { color: black; }")

        result = validate_project_references(temp_dir)
        assert "✅" in result

    def test_externe_urls_werden_ignoriert(self, temp_dir):
        """Externe URLs (http/https) werden nicht geprueft."""
        html = '''<html>
        <head>
            <script src="https://cdn.example.com/lib.js"></script>
            <link href="//cdn.example.com/styles.css">
            <script src="http://example.com/script.js"></script>
        </head>
        <body></body>
        </html>'''
        with open(os.path.join(temp_dir, "index.html"), "w") as f:
            f.write(html)

        result = validate_project_references(temp_dir)
        assert "✅" in result

    def test_gemischte_referenzen(self, temp_dir):
        """Externe URLs OK, lokale fehlende werden erkannt."""
        html = '''<html>
        <head>
            <script src="https://cdn.example.com/lib.js"></script>
            <script src="local_missing.js"></script>
        </head>
        <body></body>
        </html>'''
        with open(os.path.join(temp_dir, "index.html"), "w") as f:
            f.write(html)

        result = validate_project_references(temp_dir)
        assert "❌" in result
        assert "local_missing.js" in result

    def test_leeres_verzeichnis(self, temp_dir):
        """Leeres Verzeichnis ohne HTML-Dateien besteht."""
        result = validate_project_references(temp_dir)
        assert "✅" in result

    def test_mehrere_html_dateien(self, temp_dir):
        """Mehrere HTML-Dateien werden alle geprueft."""
        html1 = '<html><head><script src="app.js"></script></head><body></body></html>'
        html2 = '<html><head><script src="other.js"></script></head><body></body></html>'

        with open(os.path.join(temp_dir, "index.html"), "w") as f:
            f.write(html1)
        with open(os.path.join(temp_dir, "about.html"), "w") as f:
            f.write(html2)

        # Nur app.js erstellen, other.js fehlt
        with open(os.path.join(temp_dir, "app.js"), "w") as f:
            f.write("console.log('test');")

        result = validate_project_references(temp_dir)
        assert "❌" in result
        assert "other.js" in result

    def test_unterverzeichnisse(self, temp_dir):
        """Referenzen in Unterverzeichnissen werden korrekt aufgeloest."""
        subdir = os.path.join(temp_dir, "src")
        os.makedirs(subdir)

        html = '<html><head><script src="script.js"></script></head><body></body></html>'
        with open(os.path.join(subdir, "index.html"), "w") as f:
            f.write(html)
        # script.js in src/ erstellen
        with open(os.path.join(subdir, "script.js"), "w") as f:
            f.write("console.log('test');")

        result = validate_project_references(temp_dir)
        assert "✅" in result


# ===== Tests fuer ContentValidationResult =====

class TestContentValidationResult:
    """Tests fuer die Datenstruktur."""

    def test_default_values(self):
        """Standard-Werte sind korrekt."""
        result = ContentValidationResult()
        assert result.has_visible_content is False
        assert result.issues == []
        assert result.warnings == []
        assert result.checks_performed == []
        assert result.is_critical_failure is False

    def test_issues_hinzufuegen(self):
        """Issues koennen hinzugefuegt werden."""
        result = ContentValidationResult()
        result.issues.append("Testproblem")
        assert len(result.issues) == 1
        assert result.issues[0] == "Testproblem"
