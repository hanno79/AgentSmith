# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 28.01.2026
Version: 1.0
Beschreibung: Tests fuer Unit Test Runner.
              Prueft die korrekte Framework-Erkennung und Test-Ausfuehrung.
"""

import os
import sys
import pytest
import tempfile
import shutil
import json

# Projekt-Root zum Python-Path hinzufuegen
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unit_test_runner import (
    run_unit_tests,
    select_test_framework,
    _find_python_test_files,
    _extract_pytest_count,
    _extract_pytest_failures,
    _extract_npm_test_count
)


@pytest.fixture
def temp_project_dir():
    """Erstellt ein temporaeres Projektverzeichnis."""
    dir_path = tempfile.mkdtemp()
    yield dir_path
    shutil.rmtree(dir_path, ignore_errors=True)


# ===== Tests fuer select_test_framework =====

class TestSelectTestFramework:
    """Tests fuer die Framework-Auswahl."""

    def test_python_projekt(self):
        """Python-Projekte nutzen pytest."""
        blueprint = {"language": "python", "project_type": "flask_app"}
        assert select_test_framework(blueprint) == "pytest"

    def test_javascript_nodejs(self):
        """Node.js-Projekte nutzen jest."""
        blueprint = {"language": "javascript", "project_type": "nodejs_express"}
        assert select_test_framework(blueprint) == "jest"

    def test_javascript_react(self):
        """React-Projekte nutzen jest."""
        blueprint = {"language": "javascript", "project_type": "react_app"}
        assert select_test_framework(blueprint) == "jest"

    def test_javascript_vue(self):
        """Vue-Projekte nutzen vitest."""
        blueprint = {"language": "javascript", "project_type": "vue_app"}
        assert select_test_framework(blueprint) == "vitest"

    def test_static_html(self):
        """Statische HTML-Projekte haben keine Tests."""
        blueprint = {"language": "html", "project_type": "static_html"}
        assert select_test_framework(blueprint) == "none"

    def test_unbekanntes_projekt(self):
        """Unbekannte Projekte geben 'unknown' zurueck."""
        blueprint = {"language": "rust", "project_type": "cli"}
        assert select_test_framework(blueprint) == "unknown"


# ===== Tests fuer run_unit_tests =====

class TestRunUnitTests:
    """Tests fuer die Haupt-Funktion."""

    def test_python_ohne_tests_ordner(self, temp_project_dir):
        """Python-Projekt ohne tests/ wird uebersprungen."""
        blueprint = {"language": "python", "project_type": "flask_app"}
        result = run_unit_tests(temp_project_dir, blueprint)
        assert result["status"] == "SKIP"
        assert "tests" in result["summary"].lower() or "test" in result["summary"].lower()

    def test_static_html_wird_uebersprungen(self, temp_project_dir):
        """Statische HTML-Projekte werden uebersprungen."""
        blueprint = {"language": "html", "project_type": "static_html"}
        result = run_unit_tests(temp_project_dir, blueprint)
        assert result["status"] == "SKIP"
        assert "statisch" in result["summary"].lower() or "html" in result["summary"].lower()

    def test_javascript_ohne_package_json(self, temp_project_dir):
        """JavaScript-Projekt ohne package.json wird uebersprungen."""
        blueprint = {"language": "javascript", "project_type": "nodejs_app"}
        result = run_unit_tests(temp_project_dir, blueprint)
        assert result["status"] == "SKIP"
        assert "package.json" in result["summary"].lower()

    def test_javascript_ohne_test_script(self, temp_project_dir):
        """JavaScript-Projekt ohne test-Script wird uebersprungen."""
        # package.json ohne test-Script erstellen
        package = {"name": "test-project", "scripts": {"start": "node index.js"}}
        with open(os.path.join(temp_project_dir, "package.json"), "w") as f:
            json.dump(package, f)

        blueprint = {"language": "javascript", "project_type": "nodejs_app"}
        result = run_unit_tests(temp_project_dir, blueprint)
        assert result["status"] == "SKIP"
        assert "test" in result["summary"].lower()


# ===== Tests fuer _find_python_test_files =====

class TestFindPythonTestFiles:
    """Tests fuer die Test-Datei-Suche."""

    def test_keine_test_dateien(self, temp_project_dir):
        """Leeres Verzeichnis hat keine Test-Dateien."""
        result = _find_python_test_files(temp_project_dir)
        assert result == []

    def test_test_prefix(self, temp_project_dir):
        """test_*.py Dateien werden gefunden."""
        test_file = os.path.join(temp_project_dir, "test_example.py")
        with open(test_file, "w") as f:
            f.write("def test_something(): pass")

        result = _find_python_test_files(temp_project_dir)
        assert len(result) == 1
        assert "test_example.py" in result[0]

    def test_test_suffix(self, temp_project_dir):
        """*_test.py Dateien werden gefunden."""
        test_file = os.path.join(temp_project_dir, "example_test.py")
        with open(test_file, "w") as f:
            f.write("def test_something(): pass")

        result = _find_python_test_files(temp_project_dir)
        assert len(result) == 1
        assert "example_test.py" in result[0]

    def test_tests_ordner(self, temp_project_dir):
        """Tests in tests/ Unterordner werden gefunden."""
        tests_dir = os.path.join(temp_project_dir, "tests")
        os.makedirs(tests_dir)
        test_file = os.path.join(tests_dir, "test_app.py")
        with open(test_file, "w") as f:
            f.write("def test_app(): pass")

        result = _find_python_test_files(temp_project_dir)
        assert len(result) == 1
        assert "test_app.py" in result[0]

    def test_node_modules_ignoriert(self, temp_project_dir):
        """node_modules wird nicht durchsucht."""
        node_dir = os.path.join(temp_project_dir, "node_modules", "some_package")
        os.makedirs(node_dir)
        test_file = os.path.join(node_dir, "test_internal.py")
        with open(test_file, "w") as f:
            f.write("def test_internal(): pass")

        result = _find_python_test_files(temp_project_dir)
        assert result == []


# ===== Tests fuer Output-Extraktion =====

class TestOutputExtraction:
    """Tests fuer die Extraktion von Test-Ergebnissen."""

    def test_pytest_count_passed(self):
        """Extrahiert Anzahl bestandener Tests."""
        output = "============ 5 passed in 0.12s ============"
        assert _extract_pytest_count(output) == 5

    def test_pytest_count_mixed(self):
        """Extrahiert Anzahl bei gemischtem Ergebnis."""
        output = "============ 3 passed, 2 failed in 0.15s ============"
        assert _extract_pytest_count(output) == 5

    def test_pytest_failures(self):
        """Extrahiert Fehler-Info."""
        output = "FAILED test_app.py::test_login - AssertionError\n2 failed"
        result = _extract_pytest_failures(output)
        assert "failed" in result.lower() or "test" in result.lower()

    def test_npm_count(self):
        """Extrahiert npm/jest Test-Anzahl."""
        output = "Tests: 3 passed, 3 total"
        assert _extract_npm_test_count(output) == 3

    def test_npm_count_alternative(self):
        """Extrahiert alternative Test-Anzahl-Formate."""
        output = "5 tests passed"
        assert _extract_npm_test_count(output) == 5


# ===== Tests fuer Tech-Blueprint Erkennung =====

class TestTechBlueprintRecognition:
    """Tests fuer korrekte Tech-Stack-Erkennung."""

    def test_flask_erkannt(self, temp_project_dir):
        """Flask-Projekte werden als Python erkannt."""
        blueprint = {"project_type": "flask_app", "language": "python"}
        result = run_unit_tests(temp_project_dir, blueprint)
        # Sollte pytest versuchen (und SKIP weil keine Tests)
        assert result["status"] == "SKIP"

    def test_fastapi_erkannt(self, temp_project_dir):
        """FastAPI-Projekte werden als Python erkannt."""
        blueprint = {"project_type": "fastapi_app", "language": "python"}
        result = run_unit_tests(temp_project_dir, blueprint)
        assert result["status"] == "SKIP"

    def test_express_erkannt(self, temp_project_dir):
        """Express-Projekte werden als JavaScript erkannt."""
        blueprint = {"project_type": "nodejs_express", "language": "javascript"}
        result = run_unit_tests(temp_project_dir, blueprint)
        assert result["status"] == "SKIP"
        assert "package.json" in result["summary"].lower()

    def test_react_erkannt(self, temp_project_dir):
        """React-Projekte werden als JavaScript erkannt."""
        blueprint = {"project_type": "react_app", "language": "javascript"}
        result = run_unit_tests(temp_project_dir, blueprint)
        assert result["status"] == "SKIP"
