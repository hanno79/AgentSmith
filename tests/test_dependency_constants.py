# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 14.02.2026
Version: 1.0
Beschreibung: Tests fuer agents/dependency_constants.py
              Testet NPM_PACKAGES, PYTHON_BUILTIN_MODULES, is_builtin_module(),
              filter_builtin_modules() und WINDOWS_NPM_PATHS.
"""

import os
import sys
import pytest

# Projekt-Root zum Python-Path hinzufuegen
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.dependency_constants import (
    NPM_PACKAGES,
    PYTHON_BUILTIN_MODULES,
    WINDOWS_NPM_PATHS,
    is_builtin_module,
    filter_builtin_modules,
)


class TestNpmPackages:
    """Tests fuer NPM_PACKAGES Set."""

    def test_ist_ein_set(self):
        """NPM_PACKAGES ist ein Set."""
        assert isinstance(NPM_PACKAGES, set)

    def test_react_ecosystem(self):
        """React-Pakete sind enthalten."""
        for pkg in ["react", "react-dom", "react-router", "next"]:
            assert pkg in NPM_PACKAGES, f"'{pkg}' fehlt in NPM_PACKAGES"

    def test_vue_ecosystem(self):
        """Vue-Pakete sind enthalten."""
        for pkg in ["vue", "vue-router", "nuxt"]:
            assert pkg in NPM_PACKAGES, f"'{pkg}' fehlt in NPM_PACKAGES"

    def test_build_tools(self):
        """Build-Tools sind enthalten."""
        for pkg in ["webpack", "vite", "esbuild"]:
            assert pkg in NPM_PACKAGES, f"'{pkg}' fehlt in NPM_PACKAGES"

    def test_css_tools(self):
        """CSS-Tools sind enthalten."""
        for pkg in ["tailwindcss", "postcss", "autoprefixer"]:
            assert pkg in NPM_PACKAGES, f"'{pkg}' fehlt in NPM_PACKAGES"

    def test_shadcn_pakete(self):
        """Shadcn-Pakete sind enthalten (Fix 07.02)."""
        assert "shadcn-ui" in NPM_PACKAGES or "shadcn" in NPM_PACKAGES

    def test_lucide_react(self):
        """lucide-react ist als npm-Paket erkannt."""
        assert "lucide-react" in NPM_PACKAGES

    def test_testing_tools(self):
        """Test-Tools sind enthalten."""
        for pkg in ["jest", "vitest", "mocha"]:
            assert pkg in NPM_PACKAGES, f"'{pkg}' fehlt in NPM_PACKAGES"

    def test_mindestgroesse(self):
        """Mindestens 40 npm-Pakete definiert."""
        assert len(NPM_PACKAGES) >= 40


class TestPythonBuiltinModules:
    """Tests fuer PYTHON_BUILTIN_MODULES Set."""

    def test_ist_ein_set(self):
        """PYTHON_BUILTIN_MODULES ist ein Set."""
        assert isinstance(PYTHON_BUILTIN_MODULES, set)

    def test_system_module(self):
        """System-Module sind enthalten."""
        for mod in ["os", "sys", "pathlib", "subprocess"]:
            assert mod in PYTHON_BUILTIN_MODULES, f"'{mod}' fehlt"

    def test_datentyp_module(self):
        """Datentyp-Module sind enthalten."""
        for mod in ["json", "csv", "collections", "dataclasses", "typing"]:
            assert mod in PYTHON_BUILTIN_MODULES, f"'{mod}' fehlt"

    def test_kryptographie_module(self):
        """Kryptographie-Module sind enthalten."""
        for mod in ["hashlib", "hmac", "secrets", "base64"]:
            assert mod in PYTHON_BUILTIN_MODULES, f"'{mod}' fehlt"

    def test_sqlite3_ist_builtin(self):
        """sqlite3 ist ein Built-in (kein pip install noetig)."""
        assert "sqlite3" in PYTHON_BUILTIN_MODULES

    def test_asyncio_ist_builtin(self):
        """asyncio ist ein Built-in."""
        assert "asyncio" in PYTHON_BUILTIN_MODULES

    def test_datetime_ist_builtin(self):
        """datetime ist ein Built-in."""
        assert "datetime" in PYTHON_BUILTIN_MODULES

    def test_flask_ist_kein_builtin(self):
        """flask ist KEIN Built-in."""
        assert "flask" not in PYTHON_BUILTIN_MODULES

    def test_requests_ist_kein_builtin(self):
        """requests ist KEIN Built-in."""
        assert "requests" not in PYTHON_BUILTIN_MODULES

    def test_mindestgroesse(self):
        """Mindestens 60 Built-in Module definiert."""
        assert len(PYTHON_BUILTIN_MODULES) >= 60


class TestIsBuiltinModule:
    """Tests fuer is_builtin_module() Funktion."""

    def test_bekanntes_builtin(self):
        """Bekanntes Built-in Modul wird erkannt."""
        assert is_builtin_module("os") is True
        assert is_builtin_module("json") is True
        assert is_builtin_module("datetime") is True

    def test_unbekanntes_paket(self):
        """Unbekanntes Paket ist kein Built-in."""
        assert is_builtin_module("flask") is False
        assert is_builtin_module("requests") is False
        assert is_builtin_module("django") is False

    def test_case_insensitive(self):
        """Matching ist case-insensitiv."""
        assert is_builtin_module("OS") is True
        assert is_builtin_module("Json") is True

    def test_leerer_name(self):
        """Leerer Name ist kein Built-in."""
        assert is_builtin_module("") is False


class TestFilterBuiltinModules:
    """Tests fuer filter_builtin_modules() Funktion."""

    def test_filtert_builtins(self):
        """Built-in Module werden herausgefiltert."""
        deps = ["flask", "os", "requests", "json", "django"]
        result = filter_builtin_modules(deps)
        assert "flask" in result
        assert "requests" in result
        assert "django" in result
        assert "os" not in result
        assert "json" not in result

    def test_leere_liste(self):
        """Leere Liste gibt leere Liste zurueck."""
        assert filter_builtin_modules([]) == []

    def test_nur_builtins(self):
        """Wenn alle Built-ins, leere Liste zurueck."""
        deps = ["os", "sys", "json"]
        assert filter_builtin_modules(deps) == []

    def test_keine_builtins(self):
        """Wenn keine Built-ins, alles zurueck."""
        deps = ["flask", "requests"]
        result = filter_builtin_modules(deps)
        assert result == deps

    def test_mit_versionen(self):
        """Versionsspezifikationen werden korrekt behandelt."""
        deps = ["flask==3.0.0", "os>=3.0", "requests<3.0", "json"]
        result = filter_builtin_modules(deps)
        assert "flask==3.0.0" in result
        assert "requests<3.0" in result
        assert len(result) == 2

    def test_mit_groesser_gleich(self):
        """>=Version wird korrekt geparst."""
        deps = ["flask>=2.0", "datetime>=1.0"]
        result = filter_builtin_modules(deps)
        assert "flask>=2.0" in result
        assert "datetime>=1.0" not in result


class TestWindowsNpmPaths:
    """Tests fuer WINDOWS_NPM_PATHS Liste."""

    def test_ist_liste(self):
        """WINDOWS_NPM_PATHS ist eine Liste."""
        assert isinstance(WINDOWS_NPM_PATHS, list)

    def test_mindestens_3_pfade(self):
        """Mindestens 3 Pfade definiert."""
        assert len(WINDOWS_NPM_PATHS) >= 3

    def test_enthaelt_program_files(self):
        """Program Files Pfad ist enthalten."""
        assert any("Program Files" in p for p in WINDOWS_NPM_PATHS)

    def test_alle_enden_auf_npm_cmd(self):
        """Alle Pfade enden auf npm.cmd."""
        for path in WINDOWS_NPM_PATHS:
            assert path.endswith("npm.cmd"), f"'{path}' endet nicht auf npm.cmd"
