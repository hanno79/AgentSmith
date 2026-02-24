# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 14.02.2026
Version: 1.0
Beschreibung: Tests fuer backend/dev_loop_dep_helpers.py
              Testet Dependency-Hilfsfunktionen: Python-Paket-Versionen und Test-Dependencies.
"""

import json
import os
import sys
import pytest

# Projekt-Root zum Python-Path hinzufuegen
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.dev_loop_dep_helpers import (
    get_python_dependency_versions,
    COMMON_PYTHON_PACKAGES,
)


class TestGetPythonDependencyVersions:
    """Tests fuer get_python_dependency_versions()."""

    def test_datei_nicht_vorhanden_gibt_leer_zurueck(self, temp_dir):
        """Wenn dependencies.json nicht existiert, leerer String."""
        from pathlib import Path
        result = get_python_dependency_versions(Path(os.path.join(temp_dir, "nix.json")))
        assert result == ""

    def test_leere_pakete_gibt_leer_zurueck(self, temp_dir):
        """Wenn packages-Array leer ist, leerer String."""
        from pathlib import Path
        deps_path = Path(os.path.join(temp_dir, "dependencies.json"))
        data = {"python": {"packages": []}}
        deps_path.write_text(json.dumps(data), encoding="utf-8")
        result = get_python_dependency_versions(deps_path)
        assert result == ""

    def test_bekannte_pakete_werden_extrahiert(self, temp_dir):
        """Haeufig verwendete Pakete (flask, pytest) erscheinen im Output."""
        from pathlib import Path
        deps_path = Path(os.path.join(temp_dir, "dependencies.json"))
        data = {
            "python": {
                "packages": [
                    {"name": "flask", "version": "3.0.0"},
                    {"name": "pytest", "version": "8.1.0"},
                    {"name": "obscure-package", "version": "1.0.0"},
                ]
            }
        }
        deps_path.write_text(json.dumps(data), encoding="utf-8")
        result = get_python_dependency_versions(deps_path, filter_common=True)
        assert "flask==3.0.0" in result
        assert "pytest==8.1.0" in result
        # Unbekannte Pakete werden gefiltert
        assert "obscure-package" not in result

    def test_ohne_filter_alle_pakete(self, temp_dir):
        """Ohne filter_common werden alle Pakete ausgegeben."""
        from pathlib import Path
        deps_path = Path(os.path.join(temp_dir, "dependencies.json"))
        data = {
            "python": {
                "packages": [
                    {"name": "obscure-package", "version": "1.0.0"},
                ]
            }
        }
        deps_path.write_text(json.dumps(data), encoding="utf-8")
        result = get_python_dependency_versions(deps_path, filter_common=False)
        assert "obscure-package==1.0.0" in result

    def test_sortierte_ausgabe(self, temp_dir):
        """Pakete werden alphabetisch sortiert."""
        from pathlib import Path
        deps_path = Path(os.path.join(temp_dir, "dependencies.json"))
        data = {
            "python": {
                "packages": [
                    {"name": "requests", "version": "2.31.0"},
                    {"name": "flask", "version": "3.0.0"},
                    {"name": "django", "version": "5.0.0"},
                ]
            }
        }
        deps_path.write_text(json.dumps(data), encoding="utf-8")
        result = get_python_dependency_versions(deps_path, filter_common=True)
        lines = result.strip().split("\n")
        # Header + sortierte Pakete
        assert "django==5.0.0" in result
        assert "flask==3.0.0" in result
        assert "requests==2.31.0" in result
        # Sortierung pruefen: django vor flask vor requests
        paket_zeilen = [l for l in lines if "==" in l]
        assert paket_zeilen == sorted(paket_zeilen)

    def test_header_enthalten(self, temp_dir):
        """Ausgabe beginnt mit Header-Zeile."""
        from pathlib import Path
        deps_path = Path(os.path.join(temp_dir, "dependencies.json"))
        data = {"python": {"packages": [{"name": "flask", "version": "3.0.0"}]}}
        deps_path.write_text(json.dumps(data), encoding="utf-8")
        result = get_python_dependency_versions(deps_path)
        assert result.startswith("AKTUELLE PAKET-VERSIONEN")

    def test_ungueltige_json_gibt_leer_zurueck(self, temp_dir):
        """Bei JSON-Fehler leerer String statt Crash."""
        from pathlib import Path
        deps_path = Path(os.path.join(temp_dir, "dependencies.json"))
        deps_path.write_text("{invalid json", encoding="utf-8")
        result = get_python_dependency_versions(deps_path)
        assert result == ""

    def test_fehlende_python_sektion(self, temp_dir):
        """Ohne python-Sektion leerer String."""
        from pathlib import Path
        deps_path = Path(os.path.join(temp_dir, "dependencies.json"))
        data = {"node": {"packages": []}}
        deps_path.write_text(json.dumps(data), encoding="utf-8")
        result = get_python_dependency_versions(deps_path)
        assert result == ""

    def test_pakete_ohne_name_oder_version_uebersprungen(self, temp_dir):
        """Pakete ohne name oder version werden ignoriert."""
        from pathlib import Path
        deps_path = Path(os.path.join(temp_dir, "dependencies.json"))
        data = {
            "python": {
                "packages": [
                    {"name": "flask", "version": ""},
                    {"name": "", "version": "1.0"},
                    {"version": "2.0"},
                    {"name": "pytest", "version": "8.0.0"},
                ]
            }
        }
        deps_path.write_text(json.dumps(data), encoding="utf-8")
        result = get_python_dependency_versions(deps_path)
        assert "pytest==8.0.0" in result
        assert "flask==" not in result


class TestCommonPythonPackages:
    """Tests fuer COMMON_PYTHON_PACKAGES Konstante."""

    def test_web_frameworks_enthalten(self):
        """Alle wichtigen Web-Frameworks sind in der Liste."""
        assert "flask" in COMMON_PYTHON_PACKAGES
        assert "django" in COMMON_PYTHON_PACKAGES
        assert "fastapi" in COMMON_PYTHON_PACKAGES

    def test_testing_tools_enthalten(self):
        """Test-Tools sind in der Liste."""
        assert "pytest" in COMMON_PYTHON_PACKAGES
        assert "pytest-cov" in COMMON_PYTHON_PACKAGES

    def test_security_pakete_enthalten(self):
        """Security-Pakete sind in der Liste."""
        assert "bcrypt" in COMMON_PYTHON_PACKAGES
        assert "cryptography" in COMMON_PYTHON_PACKAGES
