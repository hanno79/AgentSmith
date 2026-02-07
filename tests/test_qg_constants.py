# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 06.02.2026
Version: 1.0
Beschreibung: Unit Tests fuer backend/qg_constants.py - Quality Gate Konstanten.
              Testet: LANGUAGE_TEST_CONFIG, LANGUAGE_MAPPING, get_test_config_for_project.
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.qg_constants import (
    LANGUAGE_TEST_CONFIG,
    LANGUAGE_MAPPING,
    get_test_config_for_project,
    DB_KEYWORDS,
    LANG_KEYWORDS,
    FRAMEWORK_KEYWORDS,
    SEVERITY_ORDER,
)


# =========================================================================
# Tests fuer LANGUAGE_TEST_CONFIG
# =========================================================================
class TestLanguageTestConfig:
    """Tests fuer die zentrale Test-Konfiguration."""

    def test_alle_sprachen_haben_test_patterns(self):
        """Jede Sprache hat ein test_patterns Feld."""
        for lang, config in LANGUAGE_TEST_CONFIG.items():
            assert "test_patterns" in config, f"{lang} fehlt test_patterns"
            assert isinstance(config["test_patterns"], list), f"{lang} test_patterns kein List"

    def test_alle_sprachen_haben_code_extensions(self):
        """Jede Sprache hat ein code_extensions Feld."""
        for lang, config in LANGUAGE_TEST_CONFIG.items():
            assert "code_extensions" in config, f"{lang} fehlt code_extensions"
            assert isinstance(config["code_extensions"], list), f"{lang} code_extensions kein List"

    def test_alle_sprachen_haben_test_command(self):
        """Jede Sprache hat ein test_command Feld (kann None sein fuer static)."""
        for lang, config in LANGUAGE_TEST_CONFIG.items():
            assert "test_command" in config, f"{lang} fehlt test_command"

    def test_alle_sprachen_haben_skip_patterns(self):
        """Jede Sprache hat ein skip_patterns Feld."""
        for lang, config in LANGUAGE_TEST_CONFIG.items():
            assert "skip_patterns" in config, f"{lang} fehlt skip_patterns"

    def test_python_config(self):
        """Python-Config ist korrekt."""
        cfg = LANGUAGE_TEST_CONFIG["python"]
        assert "test_*.py" in cfg["test_patterns"]
        assert ".py" in cfg["code_extensions"]
        assert cfg["test_command"] == "pytest"

    def test_javascript_config(self):
        """JavaScript-Config deckt alle Varianten ab."""
        cfg = LANGUAGE_TEST_CONFIG["javascript"]
        assert "*.test.js" in cfg["test_patterns"]
        assert "*.spec.js" in cfg["test_patterns"]
        assert "*.test.ts" in cfg["test_patterns"]
        assert ".js" in cfg["code_extensions"]
        assert ".ts" in cfg["code_extensions"]
        assert ".tsx" in cfg["code_extensions"]
        assert cfg["test_command"] == "npm test"

    def test_csharp_config(self):
        """C#-Config ist korrekt."""
        cfg = LANGUAGE_TEST_CONFIG["csharp"]
        assert "*Tests.cs" in cfg["test_patterns"]
        assert ".cs" in cfg["code_extensions"]
        assert cfg["test_command"] == "dotnet test"

    def test_static_config(self):
        """Static-Config hat keine Unit-Tests."""
        cfg = LANGUAGE_TEST_CONFIG["static"]
        assert cfg["test_patterns"] == []
        assert cfg["test_command"] is None
        assert ".html" in cfg["code_extensions"]

    def test_mindestens_10_sprachen(self):
        """Mindestens 10 Sprachen konfiguriert."""
        assert len(LANGUAGE_TEST_CONFIG) >= 10

    def test_go_config(self):
        """Go-Config ist korrekt."""
        cfg = LANGUAGE_TEST_CONFIG["go"]
        assert "*_test.go" in cfg["test_patterns"]
        assert cfg["test_command"] == "go test ./..."

    def test_rust_config(self):
        """Rust-Config ist korrekt."""
        cfg = LANGUAGE_TEST_CONFIG["rust"]
        assert "*_test.rs" in cfg["test_patterns"]
        assert cfg["test_command"] == "cargo test"

    def test_java_config(self):
        """Java-Config ist korrekt."""
        cfg = LANGUAGE_TEST_CONFIG["java"]
        assert "*Test.java" in cfg["test_patterns"]
        assert cfg["test_command"] == "mvn test"


# =========================================================================
# Tests fuer LANGUAGE_MAPPING
# =========================================================================
class TestLanguageMapping:
    """Tests fuer das Sprach-Mapping."""

    def test_alle_mappings_zeigen_auf_existierende_configs(self):
        """Jedes Mapping verweist auf einen existierenden Config-Key."""
        for mapping_key, config_key in LANGUAGE_MAPPING.items():
            assert config_key in LANGUAGE_TEST_CONFIG, (
                f"Mapping '{mapping_key}' -> '{config_key}' existiert nicht in LANGUAGE_TEST_CONFIG"
            )

    def test_python_varianten(self):
        """Alle Python-Varianten mappen auf 'python'."""
        python_keys = ["python", "flask", "fastapi", "django", "tkinter", "pyqt", "streamlit"]
        for key in python_keys:
            assert LANGUAGE_MAPPING.get(key) == "python", f"{key} sollte auf python mappen"

    def test_javascript_varianten(self):
        """Alle JS-Varianten mappen auf 'javascript'."""
        js_keys = ["javascript", "typescript", "nodejs", "react", "vue", "angular", "nextjs"]
        for key in js_keys:
            assert LANGUAGE_MAPPING.get(key) == "javascript", f"{key} sollte auf javascript mappen"

    def test_csharp_varianten(self):
        """Alle C#-Varianten mappen auf 'csharp'."""
        cs_keys = ["csharp", "dotnet", "aspnet", "excel_addin", "wpf"]
        for key in cs_keys:
            assert LANGUAGE_MAPPING.get(key) == "csharp", f"{key} sollte auf csharp mappen"

    def test_static_varianten(self):
        """Statische Varianten mappen auf 'static'."""
        static_keys = ["static_html", "html", "css", "static"]
        for key in static_keys:
            assert LANGUAGE_MAPPING.get(key) == "static", f"{key} sollte auf static mappen"

    def test_mindestens_50_mappings(self):
        """Mindestens 50 Mappings definiert."""
        assert len(LANGUAGE_MAPPING) >= 50


# =========================================================================
# Tests fuer get_test_config_for_project
# =========================================================================
class TestGetTestConfigForProject:
    """Tests fuer die Blueprint-basierte Config-Ermittlung."""

    def test_python_blueprint(self):
        """Python-Blueprint liefert Python-Config."""
        bp = {"language": "python", "framework": "flask", "project_type": "flask_app"}
        config = get_test_config_for_project(bp)
        assert config["test_command"] == "pytest"

    def test_javascript_blueprint(self):
        """JS-Blueprint liefert JavaScript-Config."""
        bp = {"language": "javascript", "framework": "react", "project_type": "react_app"}
        config = get_test_config_for_project(bp)
        assert config["test_command"] == "npm test"

    def test_nextjs_blueprint(self):
        """Next.js-Blueprint liefert JavaScript-Config."""
        bp = {"language": "javascript", "framework": "nextjs", "project_type": "nodejs_app"}
        config = get_test_config_for_project(bp)
        assert "*.test.js" in config["test_patterns"]

    def test_csharp_blueprint(self):
        """C#-Blueprint liefert C#-Config."""
        bp = {"language": "csharp", "framework": "aspnet", "project_type": "aspnet_app"}
        config = get_test_config_for_project(bp)
        assert config["test_command"] == "dotnet test"

    def test_static_blueprint(self):
        """Statisches Blueprint liefert leere Patterns."""
        bp = {"language": "", "framework": "", "project_type": "static_html"}
        config = get_test_config_for_project(bp)
        assert config["test_patterns"] == []
        assert config["test_command"] is None

    def test_leeres_blueprint(self):
        """Leeres Blueprint liefert Python-Fallback."""
        config = get_test_config_for_project({})
        assert config["test_command"] == "pytest"

    def test_none_blueprint(self):
        """None-Blueprint liefert Python-Fallback."""
        config = get_test_config_for_project(None)
        assert config["test_command"] == "pytest"

    def test_language_hat_vorrang(self):
        """language hat Vorrang vor framework und project_type."""
        bp = {"language": "python", "framework": "nextjs", "project_type": "nodejs_app"}
        config = get_test_config_for_project(bp)
        assert config["test_command"] == "pytest"

    def test_framework_fallback(self):
        """Framework wird genutzt wenn language nicht matcht."""
        bp = {"language": "unbekannt", "framework": "flask", "project_type": ""}
        config = get_test_config_for_project(bp)
        assert config["test_command"] == "pytest"

    def test_project_type_fallback(self):
        """project_type wird genutzt wenn language und framework nicht matchen."""
        bp = {"language": "unbekannt", "framework": "unbekannt", "project_type": "nodejs"}
        config = get_test_config_for_project(bp)
        assert config["test_command"] == "npm test"

    def test_go_blueprint(self):
        """Go-Blueprint liefert Go-Config."""
        bp = {"language": "go", "framework": "", "project_type": "go_app"}
        config = get_test_config_for_project(bp)
        assert config["test_command"] == "go test ./..."
        assert "*_test.go" in config["test_patterns"]


# =========================================================================
# Tests fuer bestehende Konstanten (Regression)
# =========================================================================
class TestBestehendeKonstanten:
    """Regressionstests fuer bestehende Konstanten."""

    def test_db_keywords_nicht_leer(self):
        """DB_KEYWORDS enthaelt Eintraege."""
        assert len(DB_KEYWORDS) > 0
        assert "sqlite" in DB_KEYWORDS

    def test_lang_keywords_nicht_leer(self):
        """LANG_KEYWORDS enthaelt Eintraege."""
        assert len(LANG_KEYWORDS) > 0
        assert "python" in LANG_KEYWORDS

    def test_framework_keywords_nicht_leer(self):
        """FRAMEWORK_KEYWORDS enthaelt Eintraege."""
        assert len(FRAMEWORK_KEYWORDS) > 0
        assert "flask" in FRAMEWORK_KEYWORDS

    def test_severity_order_korrekt(self):
        """SEVERITY_ORDER hat korrekte Reihenfolge."""
        assert SEVERITY_ORDER[0] == "critical"
        assert SEVERITY_ORDER[-1] == "info"
        assert len(SEVERITY_ORDER) == 5
