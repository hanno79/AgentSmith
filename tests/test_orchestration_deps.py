# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 07.02.2026
Version: 1.0
Beschreibung: Tests fuer backend/orchestration_deps.py
              Testet: Pflicht-Dependencies, Python-Sanitizing, Template-Anwendung
"""

import os
import sys
import json
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.orchestration_deps import (
    ensure_required_dependencies,
    sanitize_python_dependencies,
    apply_template_if_selected,
    INVALID_PYTHON_PACKAGES,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_log():
    """Mock fuer ui_log_callback — sammelt alle Aufrufe."""
    calls = []
    def _callback(agent, level, message):
        calls.append({"agent": agent, "level": level, "message": message})
    _callback.calls = calls
    return _callback


# ============================================================================
# Tests: ensure_required_dependencies
# ============================================================================

class TestEnsureRequiredDependencies:
    """Tests fuer automatische Pflicht-Dependencies."""

    def test_react_bekommt_react_dom(self, mock_log):
        """react allein bekommt react-dom hinzugefuegt."""
        deps = ["react", "tailwindcss"]
        result = ensure_required_dependencies(deps, "javascript", "webapp", mock_log)
        assert "react-dom" in result, "react-dom wurde nicht ergaenzt"

    def test_next_bekommt_react_und_react_dom(self, mock_log):
        """next allein bekommt react und react-dom hinzugefuegt."""
        deps = ["next"]
        result = ensure_required_dependencies(deps, "javascript", "nextjs", mock_log)
        assert "react" in result, "react wurde nicht ergaenzt"
        assert "react-dom" in result, "react-dom wurde nicht ergaenzt"

    def test_tailwind_bekommt_postcss_autoprefixer(self, mock_log):
        """tailwindcss bekommt postcss und autoprefixer hinzugefuegt."""
        deps = ["tailwindcss"]
        result = ensure_required_dependencies(deps, "javascript", "webapp", mock_log)
        assert "postcss" in result, "postcss wurde nicht ergaenzt"
        assert "autoprefixer" in result, "autoprefixer wurde nicht ergaenzt"

    def test_sqlite3_bekommt_sqlite(self, mock_log):
        """sqlite3 bekommt sqlite-Wrapper hinzugefuegt."""
        deps = ["sqlite3"]
        result = ensure_required_dependencies(deps, "javascript", "webapp", mock_log)
        assert "sqlite" in result, "sqlite wurde nicht ergaenzt"

    def test_shadcn_ui_entfernt(self, mock_log):
        """shadcn/ui und shadcn werden entfernt (existieren nicht auf npm)."""
        deps = ["react", "shadcn/ui", "shadcn"]
        result = ensure_required_dependencies(deps, "javascript", "webapp", mock_log)
        assert "shadcn/ui" not in result, "shadcn/ui wurde nicht entfernt"
        assert "shadcn" not in result, "shadcn wurde nicht entfernt"
        assert "react" in result, "react darf nicht entfernt werden"

    def test_next_jest_entfernt(self, mock_log):
        """@next/jest wird entfernt (existiert nicht auf npm)."""
        deps = ["next", "react", "@next/jest"]
        result = ensure_required_dependencies(deps, "javascript", "nextjs", mock_log)
        assert "@next/jest" not in result, "@next/jest wurde nicht entfernt"

    def test_radix_bekommt_ecosystem_deps(self, mock_log):
        """@radix-ui/* bekommt lucide-react, clsx, tailwind-merge."""
        deps = ["react", "@radix-ui/react-dialog"]
        result = ensure_required_dependencies(deps, "javascript", "webapp", mock_log)
        assert "lucide-react" in result, "lucide-react fehlt"
        assert "clsx" in result, "clsx fehlt"
        assert "tailwind-merge" in result, "tailwind-merge fehlt"

    def test_keine_duplikate(self, mock_log):
        """Bereits vorhandene Dependencies werden nicht doppelt eingefuegt."""
        deps = ["next", "react", "react-dom", "postcss", "autoprefixer", "tailwindcss"]
        result = ensure_required_dependencies(deps, "javascript", "nextjs", mock_log)
        assert result.count("react") == 1, "react doppelt"
        assert result.count("react-dom") == 1, "react-dom doppelt"
        assert result.count("postcss") == 1, "postcss doppelt"

    def test_python_unberuehrt(self, mock_log):
        """Python-Dependencies werden nicht veraendert."""
        deps = ["flask", "sqlalchemy"]
        result = ensure_required_dependencies(deps, "python", "webapp", mock_log)
        assert result == ["flask", "sqlalchemy"], "Python-Deps duerfen nicht veraendert werden"

    def test_leere_liste(self, mock_log):
        """Leere Liste bleibt leer."""
        result = ensure_required_dependencies([], "javascript", "webapp", mock_log)
        assert result == []

    def test_none_liste(self, mock_log):
        """None-Liste wird unveraendert zurueckgegeben."""
        result = ensure_required_dependencies(None, "javascript", "webapp", mock_log)
        assert result is None

    def test_vollstaendiges_nextjs_projekt(self, mock_log):
        """Vollstaendiges Next.js-Projekt benoetigt keine Ergaenzungen."""
        deps = ["next", "react", "react-dom", "tailwindcss", "postcss", "autoprefixer"]
        original_len = len(deps)
        result = ensure_required_dependencies(deps, "javascript", "nextjs", mock_log)
        assert len(result) == original_len, (
            f"Vollstaendiges Projekt sollte keine neuen Deps bekommen, "
            f"aber {len(result) - original_len} wurden hinzugefuegt")


# ============================================================================
# Tests: sanitize_python_dependencies
# ============================================================================

class TestSanitizePythonDependencies:
    """Tests fuer das Entfernen ungueltiger Python-Pakete."""

    def test_entfernt_frontend_pakete(self, mock_log):
        """Frontend-only Pakete werden aus Python-Deps entfernt."""
        deps = ["flask", "react", "bootstrap", "sqlalchemy"]
        result = sanitize_python_dependencies(deps, "python", mock_log)
        assert "flask" in result
        assert "sqlalchemy" in result
        assert "react" not in result, "react sollte entfernt werden"
        assert "bootstrap" not in result, "bootstrap sollte entfernt werden"

    def test_behaelt_gueltige_pakete(self, mock_log):
        """Gueltige Python-Pakete bleiben erhalten."""
        deps = ["flask", "sqlalchemy", "requests", "pandas"]
        result = sanitize_python_dependencies(deps, "python", mock_log)
        assert result == deps, "Gueltige Pakete duerfen nicht entfernt werden"

    def test_javascript_unberuehrt(self, mock_log):
        """JavaScript-Deps werden nicht gefiltert."""
        deps = ["react", "vue", "angular"]
        result = sanitize_python_dependencies(deps, "javascript", mock_log)
        assert result == deps, "JS-Deps duerfen nicht veraendert werden"

    def test_leere_liste(self, mock_log):
        """Leere Liste bleibt leer."""
        result = sanitize_python_dependencies([], "python", mock_log)
        assert result == []

    def test_alle_ungueltig(self, mock_log):
        """Wenn alle Pakete ungueltig sind, leere Liste."""
        deps = ["react", "bootstrap", "tailwindcss"]
        result = sanitize_python_dependencies(deps, "python", mock_log)
        assert result == [], f"Erwartet: leere Liste, Erhalten: {result}"

    def test_blacklist_vollstaendig(self):
        """Blacklist enthaelt die wichtigsten Frontend-Pakete."""
        pflicht_blacklist = ["react", "vue", "angular", "bootstrap", "tailwindcss", "jquery"]
        for pkg in pflicht_blacklist:
            assert pkg in INVALID_PYTHON_PACKAGES, f"'{pkg}' fehlt in INVALID_PYTHON_PACKAGES"


# ============================================================================
# Tests: apply_template_if_selected
# ============================================================================

class TestApplyTemplateIfSelected:
    """Tests fuer die Template-Anwendung bei TechStack-Output."""

    def test_kein_template_gewaehlt(self, mock_log):
        """Output ohne selected_template wird unveraendert zurueckgegeben."""
        parsed = {"project_type": "flask", "language": "python", "dependencies": ["flask"]}
        result = apply_template_if_selected(parsed, "/tmp/test", mock_log)
        assert result == parsed, "Output sollte unveraendert sein"

    def test_custom_blueprint_feld(self, mock_log):
        """Output mit 'blueprint' Feld (Custom-Format) wird extrahiert."""
        parsed = {
            "selected_template": None,
            "blueprint": {
                "project_type": "rust_cli",
                "language": "rust"
            }
        }
        result = apply_template_if_selected(parsed, "/tmp/test", mock_log)
        assert result["project_type"] == "rust_cli"

    def test_nicht_existierendes_template(self, mock_log):
        """Unbekanntes Template faellt auf Agent-Output zurueck."""
        parsed = {
            "selected_template": "non_existent_template_xyz",
            "blueprint": {"project_type": "test", "language": "test"}
        }
        result = apply_template_if_selected(parsed, "/tmp/test", mock_log)
        # Fallback: blueprint Feld oder parsed_output
        assert result is not None
        # Warning-Log muss existieren
        assert any("nicht gefunden" in c["message"] for c in mock_log.calls), (
            "Warning-Log fuer nicht gefundenes Template fehlt")

    def test_echtes_template_angewendet(self, mock_log):
        """Echtes Template wird korrekt angewendet."""
        import tempfile
        parsed = {
            "selected_template": "nextjs_tailwind",
            "additional_dependencies": {"openai": "4.0.0"},
            "customizations": {"database": "sqlite"},
            "reasoning": "Benutzer will Next.js"
        }
        with tempfile.TemporaryDirectory() as project_dir:
            result = apply_template_if_selected(parsed, project_dir, mock_log)
            # Blueprint muss Template-Felder haben
            assert result.get("_source_template") == "nextjs_tailwind"
            assert "next" in result.get("dependencies", [])
            assert "openai" in result.get("dependencies", [])
            # File-Templates muessen kopiert worden sein
            assert any("kopiert" in c["message"] for c in mock_log.calls), (
                "Log-Meldung ueber kopierte Dateien fehlt")

    def test_selected_template_null(self, mock_log):
        """selected_template=null (nicht None sondern JSON null) funktioniert."""
        parsed = {
            "selected_template": None,
            "project_type": "flask",
            "language": "python"
        }
        result = apply_template_if_selected(parsed, "/tmp/test", mock_log)
        assert result == parsed
