# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 24.02.2026
Version: 1.0
Beschreibung: Aufgesplittete Tests fuer _matches_any_pattern aus dev_loop_test_utils.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.dev_loop_test_utils import _matches_any_pattern

PYTHON_CONFIG = {
    "test_patterns": ["test_*.py", "*_test.py"],
    "code_extensions": [".py"],
    "skip_patterns": ["__pycache__", ".pyc", "__init__"],
    "test_command": "pytest",
}

JS_CONFIG = {
    "test_patterns": [
        "*.test.js", "*.test.jsx", "*.spec.js",
        "*.test.ts", "*.test.tsx", "*.spec.ts",
    ],
    "code_extensions": [".js", ".jsx", ".ts", ".tsx"],
    "skip_patterns": ["node_modules", ".min.", "bundle.", "vendor"],
    "test_command": "npm test",
}

CSHARP_CONFIG = {
    "test_patterns": ["*Tests.cs", "*Test.cs", "*_test.cs"],
    "code_extensions": [".cs"],
    "skip_patterns": ["bin/", "obj/", ".Designer."],
}

EMPTY_CONFIG = {
    "test_patterns": [],
    "code_extensions": [],
    "skip_patterns": [],
}


# Tests fuer _matches_any_pattern
# =========================================================================

class TestMatchesAnyPattern:
    """Tests fuer _matches_any_pattern - fnmatch Wrapper."""

    def test_match_python_test_prefix(self):
        """Python test_*.py Pattern wird erkannt."""
        assert _matches_any_pattern("test_app.py", ["test_*.py"]) is True, "Erwartet: True, Erhalten: {} bei Funktion _matches_any_pattern".format(_matches_any_pattern("test_app.py", ["test_*.py"]))

    def test_match_python_test_suffix(self):
        """Python *_test.py Pattern wird erkannt."""
        assert _matches_any_pattern("app_test.py", ["*_test.py"]) is True, "Erwartet: True, Erhalten: {} bei Funktion _matches_any_pattern".format(_matches_any_pattern("app_test.py", ["*_test.py"]))

    def test_no_match(self):
        """Normale Code-Datei matcht keins der Test-Patterns."""
        assert _matches_any_pattern("app.py", ["test_*.py", "*_test.py"]) is False, "Erwartet: False, Erhalten: {} bei Funktion _matches_any_pattern".format(_matches_any_pattern("app.py", ["test_*.py", "*_test.py"]))

    def test_match_js_test(self):
        """JavaScript *.test.js Pattern wird erkannt."""
        assert _matches_any_pattern("App.test.js", ["*.test.js"]) is True, "Erwartet: True, Erhalten: {} bei Funktion _matches_any_pattern".format(_matches_any_pattern("App.test.js", ["*.test.js"]))

    def test_match_ts_spec(self):
        """TypeScript *.spec.ts Pattern wird erkannt."""
        assert _matches_any_pattern("utils.spec.ts", ["*.spec.ts"]) is True, "Erwartet: True, Erhalten: {} bei Funktion _matches_any_pattern".format(_matches_any_pattern("utils.spec.ts", ["*.spec.ts"]))

    def test_leere_patterns(self):
        """Leere Pattern-Liste ergibt immer False."""
        assert _matches_any_pattern("test_app.py", []) is False, "Erwartet: False, Erhalten: {} bei Funktion _matches_any_pattern".format(_matches_any_pattern("test_app.py", []))

    def test_mehrere_patterns_zweites_matcht(self):
        """Bei mehreren Patterns reicht ein Treffer."""
        assert _matches_any_pattern("app_test.py", ["test_*.py", "*_test.py"]) is True, "Erwartet: True, Erhalten: {} bei Funktion _matches_any_pattern".format(_matches_any_pattern("app_test.py", ["test_*.py", "*_test.py"]))

    def test_case_sensitivity(self):
        """Exakter Match funktioniert unabhaengig vom Betriebssystem."""
        assert _matches_any_pattern("test_app.py", ["test_*.py"]) is True, "Erwartet: True, Erhalten: {} bei Funktion _matches_any_pattern".format(_matches_any_pattern("test_app.py", ["test_*.py"]))

    def test_wildcard_star(self):
        """Wildcard * matcht beliebige Zeichen vor dem Suffix."""
        assert _matches_any_pattern("anything.test.js", ["*.test.js"]) is True, "Erwartet: True, Erhalten: {} bei Funktion _matches_any_pattern".format(_matches_any_pattern("anything.test.js", ["*.test.js"]))

    def test_kein_match_falsche_extension(self):
        """Falsche Dateiendung wird nicht gematcht."""
        assert _matches_any_pattern("test_app.txt", ["test_*.py"]) is False, "Erwartet: False, Erhalten: {} bei Funktion _matches_any_pattern".format(_matches_any_pattern("test_app.txt", ["test_*.py"]))


# =========================================================================

