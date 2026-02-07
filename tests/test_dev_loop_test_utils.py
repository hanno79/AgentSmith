# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 06.02.2026
Version: 1.0
Beschreibung: Tests fuer die pure Hilfsfunktionen aus dev_loop_test_utils.py.
              Testet _matches_any_pattern, _is_test_file, _is_code_file.
              Keine externen Abhaengigkeiten, kein Mocking noetig.
"""

import pytest
from backend.dev_loop_test_utils import _matches_any_pattern, _is_test_file, _is_code_file


# =========================================================================
# Wiederverwendbare Test-Konfigurationen
# =========================================================================

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


# =========================================================================
# Tests fuer _matches_any_pattern
# =========================================================================

class TestMatchesAnyPattern:
    """Tests fuer _matches_any_pattern - fnmatch Wrapper."""

    def test_match_python_test_prefix(self):
        """Python test_*.py Pattern wird erkannt."""
        assert _matches_any_pattern("test_app.py", ["test_*.py"]) is True

    def test_match_python_test_suffix(self):
        """Python *_test.py Pattern wird erkannt."""
        assert _matches_any_pattern("app_test.py", ["*_test.py"]) is True

    def test_no_match(self):
        """Normale Code-Datei matcht keins der Test-Patterns."""
        assert _matches_any_pattern("app.py", ["test_*.py", "*_test.py"]) is False

    def test_match_js_test(self):
        """JavaScript *.test.js Pattern wird erkannt."""
        assert _matches_any_pattern("App.test.js", ["*.test.js"]) is True

    def test_match_ts_spec(self):
        """TypeScript *.spec.ts Pattern wird erkannt."""
        assert _matches_any_pattern("utils.spec.ts", ["*.spec.ts"]) is True

    def test_leere_patterns(self):
        """Leere Pattern-Liste ergibt immer False."""
        assert _matches_any_pattern("test_app.py", []) is False

    def test_mehrere_patterns_zweites_matcht(self):
        """Bei mehreren Patterns reicht ein Treffer."""
        assert _matches_any_pattern("app_test.py", ["test_*.py", "*_test.py"]) is True

    def test_case_sensitivity(self):
        """Exakter Match funktioniert unabhaengig vom Betriebssystem."""
        assert _matches_any_pattern("test_app.py", ["test_*.py"]) is True

    def test_wildcard_star(self):
        """Wildcard * matcht beliebige Zeichen vor dem Suffix."""
        assert _matches_any_pattern("anything.test.js", ["*.test.js"]) is True

    def test_kein_match_falsche_extension(self):
        """Falsche Dateiendung wird nicht gematcht."""
        assert _matches_any_pattern("test_app.txt", ["test_*.py"]) is False


# =========================================================================
# Tests fuer _is_test_file
# =========================================================================

class TestIsTestFile:
    """Tests fuer _is_test_file mit verschiedenen Sprach-Configs."""

    # --- Python ---
    def test_python_test_prefix(self):
        """Python Test-Datei mit test_ Prefix wird erkannt."""
        assert _is_test_file("test_models.py", PYTHON_CONFIG) is True

    def test_python_test_suffix(self):
        """Python Test-Datei mit _test Suffix wird erkannt."""
        assert _is_test_file("models_test.py", PYTHON_CONFIG) is True

    def test_python_code_datei(self):
        """Normale Python-Datei ist keine Test-Datei."""
        assert _is_test_file("models.py", PYTHON_CONFIG) is False

    def test_python_init_nicht_test(self):
        """__init__.py ist keine Test-Datei."""
        assert _is_test_file("__init__.py", PYTHON_CONFIG) is False

    # --- JavaScript / TypeScript ---
    def test_js_test_datei(self):
        """JavaScript .test.js Datei wird erkannt."""
        assert _is_test_file("App.test.js", JS_CONFIG) is True

    def test_js_spec_datei(self):
        """JavaScript .spec.js Datei wird erkannt."""
        assert _is_test_file("utils.spec.js", JS_CONFIG) is True

    def test_jsx_test_datei(self):
        """JSX .test.jsx Datei wird erkannt."""
        assert _is_test_file("Component.test.jsx", JS_CONFIG) is True

    def test_ts_test_datei(self):
        """TypeScript .test.ts Datei wird erkannt."""
        assert _is_test_file("service.test.ts", JS_CONFIG) is True

    def test_tsx_test_datei(self):
        """TSX .test.tsx Datei wird erkannt."""
        assert _is_test_file("Page.test.tsx", JS_CONFIG) is True

    def test_js_code_datei(self):
        """Normale JS-Datei ist keine Test-Datei."""
        assert _is_test_file("App.js", JS_CONFIG) is False

    # --- C# ---
    def test_csharp_tests(self):
        """C# *Tests.cs Datei wird erkannt."""
        assert _is_test_file("UserTests.cs", CSHARP_CONFIG) is True

    def test_csharp_code(self):
        """Normale C#-Datei ist keine Test-Datei."""
        assert _is_test_file("User.cs", CSHARP_CONFIG) is False

    # --- Edge Cases ---
    def test_leere_config(self):
        """Leere Config ergibt immer False."""
        assert _is_test_file("test_app.py", EMPTY_CONFIG) is False

    def test_fehlende_test_patterns(self):
        """Config ohne test_patterns Key ergibt False."""
        assert _is_test_file("test_app.py", {}) is False


# =========================================================================
# Tests fuer _is_code_file
# =========================================================================

class TestIsCodeFile:
    """Tests fuer _is_code_file mit Extension- und Skip-Pattern-Pruefung."""

    # --- Python ---
    def test_python_code_datei(self):
        """Normale Python-Datei wird als Code erkannt."""
        assert _is_code_file("app.py", PYTHON_CONFIG) is True

    def test_python_test_ist_code(self):
        """Test-Dateien haben .py Extension und sind technisch Code-Dateien.
        _is_code_file prueft nur Extension und skip_patterns, nicht test_patterns."""
        assert _is_code_file("test_app.py", PYTHON_CONFIG) is True

    def test_python_pycache_skip(self):
        """Dateien in __pycache__ werden uebersprungen."""
        assert _is_code_file("__pycache__/module.py", PYTHON_CONFIG) is False

    def test_python_init_skip(self):
        """__init__.py wird uebersprungen (enthaelt __init__ Skip-Pattern)."""
        assert _is_code_file("__init__.py", PYTHON_CONFIG) is False

    def test_python_pyc_skip(self):
        """Kompilierte .pyc Dateien werden uebersprungen."""
        assert _is_code_file("module.pyc", PYTHON_CONFIG) is False

    # --- JavaScript / TypeScript ---
    def test_js_code_datei(self):
        """Normale JS-Datei wird als Code erkannt."""
        assert _is_code_file("App.js", JS_CONFIG) is True

    def test_jsx_code_datei(self):
        """JSX-Datei wird als Code erkannt."""
        assert _is_code_file("Component.jsx", JS_CONFIG) is True

    def test_ts_code_datei(self):
        """TypeScript-Datei wird als Code erkannt."""
        assert _is_code_file("service.ts", JS_CONFIG) is True

    def test_tsx_code_datei(self):
        """TSX-Datei wird als Code erkannt."""
        assert _is_code_file("Page.tsx", JS_CONFIG) is True

    def test_js_node_modules_skip(self):
        """Dateien in node_modules werden uebersprungen."""
        assert _is_code_file("node_modules/lib.js", JS_CONFIG) is False

    def test_js_minified_skip(self):
        """Minifizierte Dateien (.min.) werden uebersprungen."""
        assert _is_code_file("app.min.js", JS_CONFIG) is False

    def test_js_bundle_skip(self):
        """Bundle-Dateien werden uebersprungen."""
        assert _is_code_file("bundle.js", JS_CONFIG) is False

    def test_js_vendor_skip(self):
        """Vendor-Dateien werden uebersprungen."""
        assert _is_code_file("vendor/lib.js", JS_CONFIG) is False

    # --- Nicht-Code-Dateien ---
    def test_html_nicht_code(self):
        """HTML-Dateien sind kein Python-Code."""
        assert _is_code_file("index.html", PYTHON_CONFIG) is False

    def test_json_nicht_code(self):
        """JSON-Dateien sind kein JS-Code."""
        assert _is_code_file("package.json", JS_CONFIG) is False

    def test_markdown_nicht_code(self):
        """Markdown-Dateien sind kein Code."""
        assert _is_code_file("README.md", PYTHON_CONFIG) is False

    # --- Edge Cases ---
    def test_leere_config(self):
        """Leere Config ergibt immer False."""
        assert _is_code_file("app.py", EMPTY_CONFIG) is False

    def test_fehlende_keys(self):
        """Config ohne code_extensions Key ergibt False."""
        assert _is_code_file("app.py", {}) is False
