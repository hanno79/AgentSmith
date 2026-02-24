# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 14.02.2026
Version: 1.0
Beschreibung: Tests fuer backend/error_models.py
              Testet FileError Dataclass, Regex-Patterns und ERROR_PRIORITY_MAP.
"""

import os
import sys
import re
import pytest

# Projekt-Root zum Python-Path hinzufuegen
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.error_models import (
    FileError,
    PYTHON_TRACEBACK_PATTERN,
    PYTHON_SYNTAX_ERROR_PATTERN,
    GERMAN_SYNTAX_ERROR_PATTERN,
    UNKNOWN_FILE_SYNTAX_PATTERN,
    PYTHON_IMPORT_ERROR_PATTERN,
    JAVASCRIPT_ERROR_PATTERN,
    TRUNCATION_PATTERN,
    TEST_FAILURE_PATTERN,
    PIP_ERROR_PATTERNS,
    CONFIG_ERROR_PATTERNS,
    IMPORT_ERROR_PATTERNS,
    ERROR_PRIORITY_MAP,
)


class TestFileError:
    """Tests fuer FileError Dataclass."""

    def test_erstellung_mit_defaults(self):
        """FileError mit Pflichtfeldern hat korrekte Defaults."""
        fe = FileError(file_path="test.py", error_type="syntax")
        assert fe.file_path == "test.py"
        assert fe.error_type == "syntax"
        assert fe.line_numbers == []
        assert fe.error_message == ""
        assert fe.suggested_fix == ""
        assert fe.dependencies == []
        assert fe.severity == "error"

    def test_erstellung_vollstaendig(self):
        """FileError mit allen Feldern."""
        fe = FileError(
            file_path="src/main.py",
            error_type="import",
            line_numbers=[10, 20],
            error_message="ImportError: flask",
            suggested_fix="pip install flask",
            dependencies=["src/config.py"],
            severity="warning"
        )
        assert fe.line_numbers == [10, 20]
        assert "flask" in fe.error_message
        assert fe.severity == "warning"

    def test_hash_basiert_auf_pfad_typ_zeilen(self):
        """Hash basiert auf file_path, error_type und line_numbers."""
        fe1 = FileError("test.py", "syntax", [1, 2])
        fe2 = FileError("test.py", "syntax", [1, 2])
        assert hash(fe1) == hash(fe2)

    def test_hash_unterschiedliche_pfade(self):
        """Unterschiedliche Pfade geben verschiedene Hashes."""
        fe1 = FileError("a.py", "syntax")
        fe2 = FileError("b.py", "syntax")
        assert hash(fe1) != hash(fe2)

    def test_hash_unterschiedliche_typen(self):
        """Unterschiedliche error_types geben verschiedene Hashes."""
        fe1 = FileError("a.py", "syntax")
        fe2 = FileError("a.py", "import")
        assert hash(fe1) != hash(fe2)

    def test_keine_geteilte_default_liste(self):
        """Zwei Instanzen teilen nicht dieselbe Default-Liste."""
        fe1 = FileError("a.py", "syntax")
        fe2 = FileError("b.py", "import")
        fe1.line_numbers.append(42)
        assert len(fe2.line_numbers) == 0


class TestPythonTracebackPattern:
    """Tests fuer PYTHON_TRACEBACK_PATTERN."""

    def test_standard_traceback(self):
        """Erkennt Standard Python-Traceback."""
        text = 'File "src/main.py", line 42'
        match = PYTHON_TRACEBACK_PATTERN.search(text)
        assert match is not None
        assert match.group(1) == "src/main.py"
        assert match.group(2) == "42"

    def test_windows_pfad(self):
        """Erkennt Windows-Pfade im Traceback."""
        text = 'File "C:\\Users\\rahn\\project\\app.py", line 10'
        match = PYTHON_TRACEBACK_PATTERN.search(text)
        assert match is not None
        assert "app.py" in match.group(1)

    def test_multiline_traceback(self):
        """Findet alle Dateien in mehrzeiligem Traceback."""
        text = '''Traceback (most recent call last):
  File "src/main.py", line 10, in main
    result = process()
  File "src/utils.py", line 5, in process
    return None'''
        matches = PYTHON_TRACEBACK_PATTERN.findall(text)
        assert len(matches) == 2


class TestGermanSyntaxErrorPattern:
    """Tests fuer GERMAN_SYNTAX_ERROR_PATTERN."""

    def test_deutsches_fehlerformat(self):
        """Erkennt deutsches Sandbox-Fehlerformat."""
        text = "Python-Syntaxfehler in Zeile 42: invalid syntax"
        match = GERMAN_SYNTAX_ERROR_PATTERN.search(text)
        assert match is not None
        assert match.group(1) == "42"

    def test_ohne_nachricht(self):
        """Erkennt deutsches Format ohne Fehlernachricht."""
        text = "Python-Syntaxfehler in Zeile 10"
        match = GERMAN_SYNTAX_ERROR_PATTERN.search(text)
        assert match is not None

    def test_case_insensitive(self):
        """Case-insensitives Matching."""
        text = "python-syntaxfehler in zeile 5: error"
        match = GERMAN_SYNTAX_ERROR_PATTERN.search(text)
        assert match is not None


class TestImportErrorPattern:
    """Tests fuer PYTHON_IMPORT_ERROR_PATTERN."""

    def test_import_error(self):
        """Erkennt ImportError."""
        text = "ImportError: cannot import name 'Flask'"
        match = PYTHON_IMPORT_ERROR_PATTERN.search(text)
        assert match is not None
        assert match.group(1) == "ImportError"

    def test_module_not_found(self):
        """Erkennt ModuleNotFoundError."""
        text = "ModuleNotFoundError: No module named 'requests'"
        match = PYTHON_IMPORT_ERROR_PATTERN.search(text)
        assert match is not None
        assert "requests" in match.group(2)


class TestJavaScriptErrorPattern:
    """Tests fuer JAVASCRIPT_ERROR_PATTERN."""

    def test_js_error(self):
        """Erkennt JavaScript-Fehler mit Datei und Zeile."""
        text = "src/app.js:15:3 error: Unexpected token"
        match = JAVASCRIPT_ERROR_PATTERN.search(text)
        assert match is not None
        assert match.group(1) == "src/app.js"
        assert match.group(2) == "15"

    def test_tsx_error(self):
        """Erkennt TypeScript JSX-Fehler."""
        text = "components/Button.tsx:42:10 Error: Type mismatch"
        match = JAVASCRIPT_ERROR_PATTERN.search(text)
        assert match is not None
        assert match.group(1) == "components/Button.tsx"


class TestTruncationPattern:
    """Tests fuer TRUNCATION_PATTERN."""

    def test_erkennt_truncation(self):
        """Erkennt verschiedene Truncation-Marker."""
        for marker in ["truncated", "abgeschnitten", "unvollstaendig", "incomplete", "cut off"]:
            match = TRUNCATION_PATTERN.search(f"Code wurde {marker}")
            assert match is not None, f"Marker '{marker}' nicht erkannt"


class TestTestFailurePattern:
    """Tests fuer TEST_FAILURE_PATTERN."""

    def test_failed_test(self):
        """Erkennt FAILED Testausgabe."""
        text = "FAILED tests/test_main.py::test_login: assert False"
        match = TEST_FAILURE_PATTERN.search(text)
        assert match is not None
        assert match.group(1) == "FAILED"

    def test_error_test(self):
        """Erkennt ERROR Testausgabe."""
        text = "ERROR tests/test_db.py::test_connect: RuntimeError"
        match = TEST_FAILURE_PATTERN.search(text)
        assert match is not None


class TestPipErrorPatterns:
    """Tests fuer PIP_ERROR_PATTERNS."""

    def test_no_module_named(self):
        """Erkennt 'No module named' Fehler."""
        text = "No module named 'flask'"
        for pattern, error_type in PIP_ERROR_PATTERNS:
            match = pattern.search(text)
            if match and error_type == "missing_module":
                assert match.group(1) == "flask"
                return
        pytest.fail("Pattern 'no module named' nicht gefunden")

    def test_no_matching_distribution(self):
        """Erkennt 'No matching distribution' Fehler."""
        text = "ERROR: No matching distribution found for nonexistent-pkg"
        for pattern, error_type in PIP_ERROR_PATTERNS:
            match = pattern.search(text)
            if match and error_type == "invalid_package":
                assert "nonexistent-pkg" in match.group(1)
                return
        pytest.fail("Pattern 'no matching distribution' nicht gefunden")

    def test_resolution_impossible(self):
        """Erkennt ResolutionImpossible Fehler."""
        text = "pip failed: ResolutionImpossible"
        found = False
        for pattern, error_type in PIP_ERROR_PATTERNS:
            if pattern.search(text) and error_type == "dependency_conflict":
                found = True
                break
        assert found, "ResolutionImpossible nicht erkannt"


class TestConfigErrorPatterns:
    """Tests fuer CONFIG_ERROR_PATTERNS."""

    def test_pytest_ini_fehler(self):
        """Erkennt pytest.ini Konfigurationsfehler."""
        text = "ERROR: C:\\project\\pytest.ini:1: unexpected line: 'ini'"
        for pattern, error_type in CONFIG_ERROR_PATTERNS:
            if pattern.search(text) and error_type == "config_error":
                return
        pytest.fail("pytest.ini Fehler nicht erkannt")


class TestImportErrorPatterns:
    """Tests fuer IMPORT_ERROR_PATTERNS."""

    def test_conftest_import_error(self):
        """Erkennt conftest ImportError."""
        text = "ImportError while loading conftest '/app/tests/conftest.py'"
        for pattern, error_type in IMPORT_ERROR_PATTERNS:
            match = pattern.search(text)
            if match and error_type == "conftest_import":
                assert "conftest.py" in match.group(1)
                return
        pytest.fail("conftest Import-Fehler nicht erkannt")

    def test_circular_import(self):
        """Erkennt zirkulaeren Import."""
        text = "src/__init__.py:3: in <module>"
        for pattern, error_type in IMPORT_ERROR_PATTERNS:
            if pattern.search(text) and error_type == "circular_import":
                return
        pytest.fail("Zirkulaerer Import nicht erkannt")


class TestErrorPriorityMap:
    """Tests fuer ERROR_PRIORITY_MAP."""

    def test_syntax_hoechste_prioritaet(self):
        """Syntax-Fehler haben hoechste Prioritaet (0)."""
        assert ERROR_PRIORITY_MAP["syntax"] == 0

    def test_config_hoechste_prioritaet(self):
        """Config-Fehler haben hoechste Prioritaet (0)."""
        assert ERROR_PRIORITY_MAP["config"] == 0

    def test_unknown_niedrigste_prioritaet(self):
        """Unknown hat niedrigste Prioritaet."""
        assert ERROR_PRIORITY_MAP["unknown"] == max(ERROR_PRIORITY_MAP.values())

    def test_prioritaet_reihenfolge(self):
        """Prioritaeten sind korrekt geordnet: syntax < import < runtime < test."""
        assert ERROR_PRIORITY_MAP["syntax"] < ERROR_PRIORITY_MAP["import"]
        assert ERROR_PRIORITY_MAP["import"] < ERROR_PRIORITY_MAP["runtime"]
        assert ERROR_PRIORITY_MAP["runtime"] < ERROR_PRIORITY_MAP["test"]

    def test_alle_erwarteten_typen_vorhanden(self):
        """Alle erwarteten Fehlertypen sind im Mapping."""
        erwartete = ["syntax", "config", "truncation", "pip_dependency",
                     "import", "runtime", "test", "review", "unknown"]
        for typ in erwartete:
            assert typ in ERROR_PRIORITY_MAP, f"'{typ}' fehlt in ERROR_PRIORITY_MAP"
