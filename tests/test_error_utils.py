# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 14.02.2026
Version: 1.0
Beschreibung: Tests fuer backend/error_utils.py
              Testet normalize_path, find_file_from_traceback, classify_error_from_message,
              extract_error_message_from_traceback, analyze_dependencies und merge_errors.
"""

import os
import sys
import pytest

# Projekt-Root zum Python-Path hinzufuegen
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.error_utils import (
    normalize_path,
    find_file_from_traceback,
    find_file_with_syntax_error,
    extract_error_message_from_traceback,
    classify_error_from_message,
    analyze_dependencies,
    merge_errors,
)
from backend.error_models import FileError


class TestNormalizePath:
    """Tests fuer normalize_path()."""

    def test_direkter_match(self):
        """Pfad wird direkt gefunden."""
        files = {"src/main.py": "code"}
        assert normalize_path("src/main.py", files) == "src/main.py"

    def test_windows_backslash(self):
        """Windows-Backslash wird normalisiert."""
        files = {"src/main.py": "code"}
        assert normalize_path("src\\main.py", files) == "src/main.py"

    def test_basename_match(self):
        """Findet ueber Dateinamen."""
        files = {"src/utils/helpers.py": "code"}
        result = normalize_path("helpers.py", files)
        assert result == "src/utils/helpers.py"

    def test_suffix_match(self):
        """Findet ueber Pfad-Suffix."""
        files = {"project/src/main.py": "code"}
        result = normalize_path("src/main.py", files)
        assert result == "project/src/main.py"

    def test_nicht_gefunden(self):
        """Nicht existierende Datei gibt None zurueck."""
        files = {"src/main.py": "code"}
        assert normalize_path("nichtda.py", files) is None

    def test_leerer_pfad(self):
        """Leerer Pfad gibt None zurueck."""
        assert normalize_path("", {"a.py": "code"}) is None

    def test_none_pfad(self):
        """None-Pfad gibt None zurueck."""
        assert normalize_path(None, {"a.py": "code"}) is None

    def test_whitespace_wird_gestripped(self):
        """Fuehrende/nachfolgende Leerzeichen werden entfernt."""
        files = {"src/main.py": "code"}
        assert normalize_path("  src/main.py  ", files) == "src/main.py"


class TestFindFileFromTraceback:
    """Tests fuer find_file_from_traceback()."""

    def test_standard_traceback(self):
        """Findet Datei aus Standard-Traceback."""
        output = '''Traceback (most recent call last):
  File "src/main.py", line 10, in main
    result = process()
TypeError: unsupported operand'''
        files = {"src/main.py": "code"}
        assert find_file_from_traceback(output, files) == "src/main.py"

    def test_kein_match(self):
        """Kein Traceback gibt None zurueck."""
        output = "Alles OK, kein Fehler"
        files = {"src/main.py": "code"}
        assert find_file_from_traceback(output, files) is None

    def test_datei_nicht_im_projekt(self):
        """Traceback-Datei nicht im Projekt gibt None zurueck."""
        output = 'File "/usr/lib/python3/site-packages/flask/app.py", line 50'
        files = {"src/main.py": "code"}
        assert find_file_from_traceback(output, files) is None


class TestFindFileWithSyntaxError:
    """Tests fuer find_file_with_syntax_error()."""

    def test_findet_datei_mit_syntaxfehler(self):
        """Findet Datei mit tatsaechlichem Syntaxfehler."""
        files = {
            "good.py": "def hello():\n    return 42\n",
            "bad.py": "def broken(\n    return 42\n"
        }
        result = find_file_with_syntax_error(files, 1)
        assert result == "bad.py"

    def test_findet_markdown_fence(self):
        """Findet Datei mit Markdown-Code-Fence."""
        files = {
            "fenced.py": "```python\ndef hello():\n    pass\n```\n"
        }
        result = find_file_with_syntax_error(files, 1)
        assert result == "fenced.py"

    def test_keine_python_dateien(self):
        """Keine Python-Dateien gibt None zurueck."""
        files = {"app.js": "console.log('hello')"}
        result = find_file_with_syntax_error(files, 1)
        assert result is None

    def test_datei_zu_kurz(self):
        """Datei kuerzer als line_num wird uebersprungen."""
        files = {"short.py": "x = 1\n"}
        result = find_file_with_syntax_error(files, 100)
        assert result is None


class TestExtractErrorMessageFromTraceback:
    """Tests fuer extract_error_message_from_traceback()."""

    def test_standard_traceback(self):
        """Extrahiert Fehlermeldung aus Traceback."""
        output = '''Traceback (most recent call last):
  File "test.py", line 1
TypeError: cannot add int and str'''
        result = extract_error_message_from_traceback(output)
        assert "TypeError" in result

    def test_leerer_output(self):
        """Leerer Output gibt Fallback zurueck."""
        result = extract_error_message_from_traceback("")
        assert result == "Unbekannter Fehler"

    def test_nur_whitespace(self):
        """Nur Whitespace gibt Fallback zurueck."""
        result = extract_error_message_from_traceback("   \n  \n  ")
        assert result == "Unbekannter Fehler"


class TestClassifyErrorFromMessage:
    """Tests fuer classify_error_from_message()."""

    def test_syntax_error(self):
        """Syntax-Fehler wird korrekt klassifiziert."""
        assert classify_error_from_message("SyntaxError: invalid syntax") == "syntax"

    def test_parse_error(self):
        """Parse-Fehler wird als Syntax klassifiziert."""
        assert classify_error_from_message("parse error in line 5") == "syntax"

    def test_import_error(self):
        """Import-Fehler wird korrekt klassifiziert."""
        assert classify_error_from_message("ImportError: no module named flask") == "import"

    def test_module_not_found(self):
        """ModuleNotFound wird als Import klassifiziert."""
        assert classify_error_from_message("Module not found: requests") == "import"

    def test_test_failure(self):
        """Test-Fehler wird korrekt klassifiziert."""
        assert classify_error_from_message("test_login: AssertionError: expected True") == "test"

    def test_truncation(self):
        """Truncation wird korrekt klassifiziert."""
        assert classify_error_from_message("Code wurde abgeschnitten") == "truncation"
        assert classify_error_from_message("File is truncated") == "truncation"
        assert classify_error_from_message("incomplete output received") == "truncation"

    def test_runtime_fallback(self):
        """Unbekannter Fehler wird als Runtime klassifiziert."""
        assert classify_error_from_message("TypeError: cannot add") == "runtime"
        assert classify_error_from_message("Irgendein Fehler") == "runtime"


class TestAnalyzeDependencies:
    """Tests fuer analyze_dependencies()."""

    def test_import_fehler_haben_keine_deps(self):
        """Import-Fehler haben keine Abhaengigkeiten."""
        errors = [
            FileError("a.py", "import", error_message="ImportError"),
            FileError("b.py", "runtime", error_message="RuntimeError"),
        ]
        result = analyze_dependencies(errors)
        # a.py ist Import-Fehler: keine deps
        assert result[0].dependencies == []
        # b.py haengt von Import-Fehlern ab
        assert "a.py" in result[1].dependencies

    def test_nur_import_fehler(self):
        """Nur Import-Fehler → keine deps gesetzt."""
        errors = [
            FileError("a.py", "import"),
            FileError("b.py", "import"),
        ]
        result = analyze_dependencies(errors)
        assert all(e.dependencies == [] for e in result)

    def test_leere_liste(self):
        """Leere Liste bleibt leer."""
        assert analyze_dependencies([]) == []


class TestMergeErrors:
    """Tests fuer merge_errors()."""

    def test_dedupliziert_gleiche_datei(self):
        """Fehler fuer gleiche Datei werden zusammengefuehrt."""
        errors = [
            FileError("a.py", "syntax", [10], "SyntaxError"),
            FileError("a.py", "import", [20], "ImportError"),
        ]
        result = merge_errors(errors)
        assert len(result) == 1
        assert result[0].file_path == "a.py"

    def test_merged_zeilennummern(self):
        """Zeilennummern werden zusammengefuehrt und sortiert."""
        errors = [
            FileError("a.py", "syntax", [20, 30]),
            FileError("a.py", "syntax", [10, 20]),
        ]
        result = merge_errors(errors)
        assert result[0].line_numbers == [10, 20, 30]

    def test_behaelt_hoehere_prioritaet(self):
        """Schwerwiegenderer Fehlertyp wird behalten."""
        errors = [
            FileError("a.py", "runtime"),  # Prioritaet 3
            FileError("a.py", "syntax"),   # Prioritaet 0 (hoeher)
        ]
        result = merge_errors(errors)
        assert result[0].error_type == "syntax"

    def test_kombiniert_fehlermeldungen(self):
        """Fehlermeldungen werden kombiniert."""
        errors = [
            FileError("a.py", "syntax", error_message="Fehler 1"),
            FileError("a.py", "syntax", error_message="Fehler 2"),
        ]
        result = merge_errors(errors)
        assert "Fehler 1" in result[0].error_message
        assert "Fehler 2" in result[0].error_message

    def test_verschiedene_dateien_bleiben_getrennt(self):
        """Fehler in verschiedenen Dateien bleiben getrennt."""
        errors = [
            FileError("a.py", "syntax"),
            FileError("b.py", "import"),
        ]
        result = merge_errors(errors)
        assert len(result) == 2

    def test_leere_liste(self):
        """Leere Liste gibt leere Liste zurueck."""
        assert merge_errors([]) == []

    def test_merged_dependencies(self):
        """Abhaengigkeiten werden zusammengefuehrt."""
        errors = [
            FileError("a.py", "syntax", dependencies=["b.py"]),
            FileError("a.py", "syntax", dependencies=["c.py"]),
        ]
        result = merge_errors(errors)
        assert "b.py" in result[0].dependencies
        assert "c.py" in result[0].dependencies
