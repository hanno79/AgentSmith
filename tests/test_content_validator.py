# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 28.01.2026
Version: 1.1
Beschreibung: Tests fuer Content Validator und Referenz-Validierung.
              Prueft Erkennung leerer Seiten, fehlender Dateien und run.bat-Probleme.

              AENDERUNG 06.02.2026 v1.1: Neue Tests fuer _run_command_present,
              _should_check_javascript und validate_page_content mit Mock-Pages.
"""

import os
import sys
import pytest
from unittest.mock import MagicMock

# Projekt-Root zum Python-Path hinzufuegen
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from content_validator import (
    validate_run_bat,
    ContentValidationResult,
    _run_command_present,
    _should_check_javascript,
    validate_page_content,
)
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


# ===== Hilfsfunktionen fuer Mock-Pages =====

def _create_mock_page(evaluate_return):
    """Erstellt ein Mock-Page-Objekt mit vorkonfiguriertem evaluate-Rueckgabewert."""
    page = MagicMock()
    page.evaluate.return_value = evaluate_return
    return page


def _basic_page_info(text_len=200, children=5, height=800, scroll=1200,
                     title="Test App", visible=10, has_error=False,
                     error="", preview="Test-Inhalt"):
    """Erzeugt ein Standard-Dict fuer basic_content page.evaluate Ergebnis."""
    return {
        "noBody": False, "bodyInnerTextLength": text_len,
        "bodyChildrenCount": children, "bodyOffsetHeight": height,
        "bodyScrollHeight": scroll, "title": title,
        "visibleElements": visible, "hasErrorPattern": has_error,
        "errorPattern": error, "pageTextPreview": preview
    }


# ===== Tests fuer _run_command_present =====

class TestRunCommandPresent:
    """Tests fuer die flexible run_command Erkennung in run.bat-Inhalten."""

    def test_exakter_match(self):
        """Exakter String-Match wird erkannt."""
        assert _run_command_present("npm start", "npm start") is True

    def test_python_src_variante(self):
        """python main.py wird auch als python src/main.py akzeptiert."""
        assert _run_command_present("python main.py", "python src/main.py") is True

    def test_nur_dateiname(self):
        """Nur der Dateiname (ohne Interpreter) wird ebenfalls erkannt."""
        assert _run_command_present("python app.py", "@echo off\napp.py\npause") is True

    def test_node_src_variante(self):
        """node server.js wird auch als node src/server.js akzeptiert."""
        assert _run_command_present("node server.js", "node src/server.js") is True

    def test_kein_match(self):
        """Komplett anderer Befehl wird nicht erkannt."""
        assert _run_command_present("python app.py", "npm start") is False

    def test_dateiendung_match(self):
        """Dateiendungs-basierter Match fuer .py Dateien."""
        assert _run_command_present("python run_server.py", "cd src && run_server.py") is True

    def test_case_insensitive(self):
        """Gross-/Kleinschreibung wird ignoriert."""
        assert _run_command_present("Python App.py", "python app.py") is True

    def test_leerer_run_cmd(self):
        """Leerer run_command matcht immer (leerer String in jedem String enthalten)."""
        assert _run_command_present("", "npm start") is True

    def test_node_nur_dateiname(self):
        """Node-Script: Nur Dateiname ohne 'node' wird erkannt."""
        assert _run_command_present("node index.js", "index.js") is True

    def test_ts_dateiendung(self):
        """TypeScript .ts Dateiendung wird erkannt."""
        assert _run_command_present("npx ts-node server.ts", "server.ts") is True


# ===== Tests fuer _should_check_javascript =====

class TestShouldCheckJavascript:
    """Tests fuer die Guard-Funktion die entscheidet ob JS-Checks sinnvoll sind."""

    def test_python_sprache(self):
        """Bei language=python werden keine JS-Checks durchgefuehrt."""
        result = _should_check_javascript("/tmp/test", {"language": "python"})
        assert result is False

    def test_go_sprache(self):
        """Bei language=go werden keine JS-Checks durchgefuehrt."""
        result = _should_check_javascript("/tmp/test", {"language": "go"})
        assert result is False

    def test_rust_sprache(self):
        """Bei language=rust werden keine JS-Checks durchgefuehrt."""
        result = _should_check_javascript("/tmp/test", {"language": "rust"})
        assert result is False

    def test_java_sprache(self):
        """Bei language=java werden keine JS-Checks durchgefuehrt."""
        result = _should_check_javascript("/tmp/test", {"language": "java"})
        assert result is False

    def test_flask_projekt_typ(self):
        """Bei project_type mit flask werden keine JS-Checks durchgefuehrt."""
        result = _should_check_javascript("/tmp/test", {"project_type": "flask_app"})
        assert result is False

    def test_fastapi_projekt_typ(self):
        """Bei project_type mit fastapi werden keine JS-Checks durchgefuehrt."""
        result = _should_check_javascript("/tmp/test", {"project_type": "fastapi_server"})
        assert result is False

    def test_django_projekt_typ(self):
        """Bei project_type mit django werden keine JS-Checks durchgefuehrt."""
        result = _should_check_javascript("/tmp/test", {"project_type": "django_webapp"})
        assert result is False

    def test_desktop_projekt_typ(self):
        """Bei project_type mit desktop werden keine JS-Checks durchgefuehrt."""
        result = _should_check_javascript("/tmp/test", {"project_type": "desktop_app"})
        assert result is False

    def test_javascript_sprache_mit_js_dateien(self, temp_dir):
        """Bei language=javascript mit vorhandenen .js Dateien wird True zurueckgegeben."""
        # JS-Datei im Verzeichnis erstellen
        with open(os.path.join(temp_dir, "app.js"), "w") as f:
            f.write("console.log('test');")
        result = _should_check_javascript(temp_dir, {"language": "javascript"})
        assert result is True

    def test_react_projekt_mit_jsx_dateien(self, temp_dir):
        """Bei leerem Blueprint mit .jsx Dateien wird True zurueckgegeben."""
        with open(os.path.join(temp_dir, "App.jsx"), "w") as f:
            f.write("export default function App() {}")
        result = _should_check_javascript(temp_dir, {"language": "", "project_type": ""})
        assert result is True

    def test_keine_js_dateien(self, temp_dir):
        """Ohne JS/TS-Dateien im Verzeichnis wird False zurueckgegeben."""
        with open(os.path.join(temp_dir, "main.py"), "w") as f:
            f.write("print('hello')")
        result = _should_check_javascript(temp_dir, {"language": "", "project_type": ""})
        assert result is False

    def test_ungueltigeger_pfad(self):
        """Bei nicht existierendem Pfad wird False zurueckgegeben."""
        result = _should_check_javascript("/pfad/existiert/nicht", {"language": ""})
        assert result is False


# ===== Tests fuer validate_page_content mit Mock-Pages =====

class TestValidatePageContent:
    """Tests fuer die Seiten-Validierung mit Mock-Page-Objekten."""

    def test_mit_mock_page_leere_seite(self):
        """Leere Seite (kein Text, keine Elemente) wird als kritisch erkannt."""
        page = _create_mock_page(_basic_page_info(
            text_len=0, children=0, height=0, scroll=0,
            title="", visible=0, preview=""
        ))
        result = validate_page_content(page, None)
        assert result.is_critical_failure
        assert any("leere Seite" in i.lower() or "leer" in i.lower() for i in result.issues)

    def test_mit_mock_page_inhalt(self):
        """Seite mit sichtbarem Inhalt wird als gueltig erkannt."""
        page = _create_mock_page(_basic_page_info(title="Test-Anwendung"))
        result = validate_page_content(page, None)
        assert result.has_visible_content is True
        assert len(result.issues) == 0

    def test_react_blueprint(self):
        """Bei React-Blueprint wird React-spezifischer Check aufgerufen."""
        page = MagicMock()
        page.evaluate.side_effect = [
            _basic_page_info(text_len=100, children=3, height=600, scroll=600,
                             title="React App", visible=5, preview="Hello React"),
            {"hasRoot": True, "rootId": "root", "rootChildren": 3,
             "rootTextLength": 100, "rootHeight": 500, "hasReactError": False,
             "rawReactVisible": False, "rawJsxVisible": False}
        ]
        blueprint = {"project_type": "react_app", "language": "javascript"}
        result = validate_page_content(page, blueprint)
        assert "react_content" in result.checks_performed
        assert result.has_visible_content is True

    def test_flask_blueprint(self):
        """Bei Flask-Blueprint wird Server-Framework-Check aufgerufen."""
        page = MagicMock()
        page.evaluate.side_effect = [
            _basic_page_info(text_len=150, children=4, height=700, scroll=700,
                             title="Flask App", visible=8, preview="Flask Startseite"),
            {"hasInternalServerError": False, "hasTraceback": False,
             "hasDebugger": False, "hasJinjaError": False,
             "hasModuleError": False, "hasImportError": False, "pageTitle": "flask app"}
        ]
        blueprint = {"project_type": "flask_app", "language": "python"}
        result = validate_page_content(page, blueprint)
        assert "server_framework_content" in result.checks_performed

    def test_exception_handling(self):
        """Bei Exception in page.evaluate wird Warnung erzeugt, kein Absturz."""
        page = MagicMock()
        page.evaluate.side_effect = Exception("Browser-Verbindung getrennt")
        result = validate_page_content(page, None)
        assert len(result.warnings) > 0
        # Warnung kommt aus _check_basic_content: "Basis-Inhalts-Check konnte nicht..."
        assert any("konnte nicht" in w.lower() or "fehlgeschlagen" in w.lower()
                    for w in result.warnings)

    def test_fehler_pattern_auf_seite(self):
        """Fehler-Pattern (z.B. 404) auf der Seite wird als kritisch erkannt."""
        page = _create_mock_page(_basic_page_info(
            text_len=20, children=2, height=400, scroll=400, title="Error",
            visible=1, has_error=True, error="404 not found", preview="404 Not Found"
        ))
        result = validate_page_content(page, None)
        assert result.is_critical_failure
        assert any("404" in i or "fehler-pattern" in i.lower() for i in result.issues)

    def test_kein_body_element(self):
        """Fehlendes body-Element wird als kritisch erkannt."""
        page = _create_mock_page({"noBody": True})
        result = validate_page_content(page, None)
        assert result.is_critical_failure
        assert any("body" in i.lower() for i in result.issues)

    def test_react_leerer_root_container(self):
        """React-App mit leerem #root Container wird als kritisch erkannt."""
        page = MagicMock()
        page.evaluate.side_effect = [
            _basic_page_info(text_len=0, children=1, height=100, scroll=100,
                             title="React App", visible=0, preview=""),
            {"hasRoot": True, "rootId": "root", "rootChildren": 0,
             "rootTextLength": 0, "rootHeight": 0, "hasReactError": False,
             "rawReactVisible": False, "rawJsxVisible": False}
        ]
        blueprint = {"project_type": "react_app", "language": "javascript"}
        result = validate_page_content(page, blueprint)
        assert result.is_critical_failure
        assert any("leer" in i.lower() or "nicht gerendert" in i.lower() for i in result.issues)

    def test_flask_internal_server_error(self):
        """Flask-App mit Internal Server Error wird als kritisch erkannt."""
        page = MagicMock()
        page.evaluate.side_effect = [
            _basic_page_info(text_len=30, children=2, height=300, scroll=300,
                             title="Error", visible=1, has_error=True,
                             error="internal server error",
                             preview="Internal Server Error"),
            {"hasInternalServerError": True, "hasTraceback": False,
             "hasDebugger": False, "hasJinjaError": False,
             "hasModuleError": False, "hasImportError": False, "pageTitle": "error"}
        ]
        blueprint = {"project_type": "flask_app", "language": "python"}
        result = validate_page_content(page, blueprint)
        assert result.is_critical_failure
        assert any("500" in i or "server error" in i.lower() for i in result.issues)
