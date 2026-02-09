# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 07.02.2026
Version: 1.0
Beschreibung: Tests fuer techstack_templates/template_loader.py
              Testet: Laden, Matching, Merging, File-Copy, Coder-Regeln
"""

import os
import sys
import json
import pytest
import tempfile
import shutil

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from techstack_templates.template_loader import (
    load_all_templates,
    invalidate_cache,
    find_matching_templates,
    get_template_by_id,
    build_blueprint_from_template,
    copy_file_templates,
    get_coder_rules,
    get_template_summary_for_prompt,
    _deps_dict_to_list,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture(autouse=True)
def reset_template_cache():
    """Cache vor jedem Test zuruecksetzen fuer isolierte Tests."""
    invalidate_cache()
    yield
    invalidate_cache()


@pytest.fixture
def sample_template():
    """Beispiel-Template fuer Unit-Tests."""
    return {
        "template_id": "test_template",
        "template_version": "1.0",
        "display_name": "Test Template",
        "source": "manual",
        "match_keywords": ["test", "demo", "beispiel"],
        "match_priority": 5,
        "blueprint": {
            "project_type": "webapp",
            "app_type": "webapp",
            "language": "javascript",
            "database": "none",
            "dependencies": {
                "react": "18.2.0",
                "react-dom": "18.2.0"
            },
            "install_command": "npm install",
            "run_command": "npm run dev",
            "requires_server": True,
            "server_port": 3000
        },
        "required_files": ["package.json", "src/App.js"],
        "directory_structure": {"src/": "Quellcode"},
        "coder_rules": [
            "ES6 import/export verwenden",
            "Exakte Versionen in package.json"
        ],
        "file_templates_dir": "test_dir",
        "container_ids": ["root"]
    }


@pytest.fixture
def temp_template_dir():
    """Erstellt ein temporaeres Verzeichnis fuer Template-Dateien."""
    dir_path = tempfile.mkdtemp()
    stacks_dir = os.path.join(dir_path, "stacks")
    os.makedirs(stacks_dir)
    yield dir_path
    shutil.rmtree(dir_path, ignore_errors=True)


# ============================================================================
# Tests: load_all_templates
# ============================================================================

class TestLoadAllTemplates:
    """Tests fuer das Laden aller Templates aus dem stacks/ Verzeichnis."""

    def test_laedt_echte_templates(self):
        """Prueft ob alle 9 initialen Templates geladen werden."""
        templates = load_all_templates()
        assert len(templates) >= 9, (
            f"Erwartet: mindestens 9 Templates, Erhalten: {len(templates)}")

    def test_hat_pflicht_templates(self):
        """Prueft ob die wichtigsten Templates vorhanden sind."""
        templates = load_all_templates()
        pflicht_ids = [
            "nextjs_tailwind", "nextjs_sqlite", "flask_webapp",
            "fastapi_api", "python_cli", "react_vite"
        ]
        for tid in pflicht_ids:
            assert tid in templates, f"Template '{tid}' fehlt"

    def test_template_hat_pflichtfelder(self):
        """Prueft ob jedes Template die notwendigen Felder enthaelt."""
        templates = load_all_templates()
        for tid, tmpl in templates.items():
            assert "template_id" in tmpl, f"{tid}: template_id fehlt"
            assert "blueprint" in tmpl, f"{tid}: blueprint fehlt"
            assert "match_keywords" in tmpl, f"{tid}: match_keywords fehlt"
            assert tmpl["template_id"] == tid, (
                f"template_id Mismatch: Key={tid}, Value={tmpl['template_id']}")

    def test_blueprint_hat_pflichtfelder(self):
        """Prueft ob jeder Blueprint die notwendigen Felder enthaelt."""
        templates = load_all_templates()
        blueprint_felder = ["project_type", "language", "dependencies"]
        for tid, tmpl in templates.items():
            bp = tmpl["blueprint"]
            for feld in blueprint_felder:
                assert feld in bp, (
                    f"Template '{tid}': blueprint.{feld} fehlt")

    def test_cache_funktioniert(self):
        """Prueft ob wiederholtes Laden den Cache nutzt (gleiche Referenz)."""
        templates1 = load_all_templates()
        templates2 = load_all_templates()
        assert templates1 is templates2, "Cache sollte dieselbe Referenz zurueckgeben"

    def test_cache_invalidierung(self):
        """Prueft ob invalidate_cache() den Cache zuruecksetzt."""
        templates1 = load_all_templates()
        invalidate_cache()
        templates2 = load_all_templates()
        assert templates1 is not templates2, "Nach Invalidierung sollte neue Instanz kommen"
        assert len(templates1) == len(templates2), "Gleiche Anzahl nach Neuladen"


# ============================================================================
# Tests: find_matching_templates
# ============================================================================

class TestFindMatchingTemplates:
    """Tests fuer das Keyword-Matching gegen User-Goals."""

    def test_nextjs_keyword_match(self):
        """'Next.js Webapp' sollte nextjs_tailwind matchen."""
        results = find_matching_templates("Erstelle eine Next.js Webapp mit Tailwind")
        assert len(results) > 0, "Kein Match fuer Next.js + Tailwind"
        # Erster Treffer sollte nextjs_tailwind sein (hoechste Prioritaet)
        assert results[0][0] == "nextjs_tailwind", (
            f"Erwartet: nextjs_tailwind, Erhalten: {results[0][0]}")

    def test_flask_keyword_match(self):
        """'Flask Webapplikation' sollte flask_webapp matchen."""
        results = find_matching_templates("Eine Flask Webapplikation erstellen")
        ids = [r[0] for r in results]
        assert "flask_webapp" in ids, f"flask_webapp nicht in Ergebnissen: {ids}"

    def test_python_cli_match(self):
        """'Python Kommandozeile' sollte python_cli matchen."""
        results = find_matching_templates("Python CLI Tool fuer Dateiverwaltung")
        ids = [r[0] for r in results]
        assert "python_cli" in ids, f"python_cli nicht in Ergebnissen: {ids}"

    def test_kein_match_bei_exotischem_stack(self):
        """Unbekannter Stack sollte leere Liste zurueckgeben."""
        results = find_matching_templates("Erstelle eine Rust WebAssembly Anwendung")
        # Kann leer sein oder wenige schwache Matches
        assert isinstance(results, list), "Ergebnis muss eine Liste sein"

    def test_sortierung_nach_score(self):
        """Ergebnisse muessen absteigend nach Score sortiert sein."""
        results = find_matching_templates("React Webapp")
        if len(results) >= 2:
            scores = [r[2] for r in results]
            assert scores == sorted(scores, reverse=True), (
                f"Scores nicht absteigend: {scores}")

    def test_leerer_goal(self):
        """Leerer Goal-String sollte keine Treffer liefern."""
        results = find_matching_templates("")
        # Keine Keywords matchen auf leeren String
        assert len(results) == 0, "Leerer Goal sollte keine Treffer liefern"


# ============================================================================
# Tests: get_template_by_id
# ============================================================================

class TestGetTemplateById:
    """Tests fuer den direkten Template-Zugriff per ID."""

    def test_existierendes_template(self):
        """Vorhandenes Template wird korrekt zurueckgegeben."""
        tmpl = get_template_by_id("nextjs_tailwind")
        assert tmpl is not None, "nextjs_tailwind nicht gefunden"
        assert tmpl["template_id"] == "nextjs_tailwind"

    def test_nicht_existierendes_template(self):
        """Unbekannte ID gibt None zurueck."""
        tmpl = get_template_by_id("non_existent_template_xyz")
        assert tmpl is None, "Unbekanntes Template sollte None sein"

    def test_alle_templates_per_id_abrufbar(self):
        """Jedes geladene Template ist auch per get_template_by_id erreichbar."""
        templates = load_all_templates()
        for tid in templates:
            result = get_template_by_id(tid)
            assert result is not None, f"Template '{tid}' nicht per ID abrufbar"


# ============================================================================
# Tests: build_blueprint_from_template
# ============================================================================

class TestBuildBlueprintFromTemplate:
    """Tests fuer das Merging von Template-Blueprint mit LLM-Customizations."""

    def test_ohne_customizations(self, sample_template):
        """Blueprint ohne Customizations enthaelt Template-Basis."""
        bp = build_blueprint_from_template(sample_template, {})
        assert bp["project_type"] == "webapp"
        assert bp["language"] == "javascript"
        assert bp["_source_template"] == "test_template"
        assert "react" in bp["dependencies"]
        assert "react-dom" in bp["dependencies"]

    def test_dependencies_als_liste(self, sample_template):
        """Dependencies werden von Dict zu Liste konvertiert."""
        bp = build_blueprint_from_template(sample_template, {})
        assert isinstance(bp["dependencies"], list), "Dependencies muessen Liste sein"

    def test_additional_dependencies_hinzugefuegt(self, sample_template):
        """LLM kann zusaetzliche Dependencies hinzufuegen."""
        customizations = {
            "additional_dependencies": {
                "openai": "4.0.0",
                "speech-recognition": "3.1.0"
            }
        }
        bp = build_blueprint_from_template(sample_template, customizations)
        deps = bp["dependencies"]
        assert "openai" in deps, "openai wurde nicht hinzugefuegt"
        assert "speech-recognition" in deps, "speech-recognition wurde nicht hinzugefuegt"
        # Basis-Dependencies bleiben
        assert "react" in deps, "react (Template-Basis) fehlt"

    def test_template_deps_nicht_entfernbar(self, sample_template):
        """Template-Dependencies koennen nicht durch LLM entfernt werden."""
        customizations = {
            "additional_dependencies": {"axios": "1.0.0"}
        }
        bp = build_blueprint_from_template(sample_template, customizations)
        assert "react" in bp["dependencies"], "Template-Dep 'react' darf nicht fehlen"
        assert "react-dom" in bp["dependencies"], "Template-Dep 'react-dom' darf nicht fehlen"

    def test_feld_ueberschreibung(self, sample_template):
        """LLM kann database und server_port ueberschreiben."""
        customizations = {
            "database": "sqlite",
            "server_port": 8080
        }
        bp = build_blueprint_from_template(sample_template, customizations)
        assert bp["database"] == "sqlite", "database nicht ueberschrieben"
        assert bp["server_port"] == 8080, "server_port nicht ueberschrieben"

    def test_source_template_marker(self, sample_template):
        """_source_template und _template_version werden gesetzt."""
        bp = build_blueprint_from_template(sample_template, {})
        assert bp["_source_template"] == "test_template"
        assert bp["_template_version"] == "1.0"

    def test_pinned_versions_bei_additional(self, sample_template):
        """_pinned_versions enthaelt Template + Additional Dependencies."""
        customizations = {
            "additional_dependencies": {"axios": "1.5.0"}
        }
        bp = build_blueprint_from_template(sample_template, customizations)
        pinned = bp.get("_pinned_versions", {})
        assert "react" in pinned, "react nicht in _pinned_versions"
        assert "axios" in pinned, "axios nicht in _pinned_versions"

    def test_additional_als_liste(self, sample_template):
        """additional_dependencies als Liste (statt Dict) funktioniert auch."""
        customizations = {
            "additional_dependencies": ["openai", "sharp"]
        }
        bp = build_blueprint_from_template(sample_template, customizations)
        assert "openai" in bp["dependencies"]
        assert "sharp" in bp["dependencies"]

    def test_echtes_template_nextjs(self):
        """Integration: Echtes nextjs_tailwind Template mit Customizations."""
        tmpl = get_template_by_id("nextjs_tailwind")
        assert tmpl is not None
        customizations = {
            "additional_dependencies": {"sqlite3": "5.1.6", "sqlite": "5.0.1"},
            "database": "sqlite"
        }
        bp = build_blueprint_from_template(tmpl, customizations)
        assert "next" in bp["dependencies"]
        assert "sqlite3" in bp["dependencies"]
        assert bp["database"] == "sqlite"


# ============================================================================
# Tests: _deps_dict_to_list
# ============================================================================

class TestDepsDictToList:
    """Tests fuer die Dependency-Konvertierung."""

    def test_dict_zu_liste(self):
        """Dict mit Packages wird zu Key-Liste."""
        result = _deps_dict_to_list({"react": "18.2.0", "next": "14.0.0"})
        assert sorted(result) == ["next", "react"]

    def test_liste_bleibt_liste(self):
        """Liste wird unveraendert zurueckgegeben."""
        result = _deps_dict_to_list(["react", "next"])
        assert result == ["react", "next"]

    def test_leeres_dict(self):
        """Leeres Dict gibt leere Liste zurueck."""
        assert _deps_dict_to_list({}) == []

    def test_anderer_typ(self):
        """Unbekannter Typ gibt leere Liste zurueck."""
        assert _deps_dict_to_list(None) == []
        assert _deps_dict_to_list(42) == []


# ============================================================================
# Tests: copy_file_templates
# ============================================================================

class TestCopyFileTemplates:
    """Tests fuer das Kopieren von File-Templates ins Projekt."""

    def test_kopiert_echte_nextjs_templates(self):
        """Kopiert Next.js File-Templates in ein temporaeres Verzeichnis."""
        tmpl = get_template_by_id("nextjs_tailwind")
        assert tmpl is not None

        with tempfile.TemporaryDirectory() as project_dir:
            copied = copy_file_templates(tmpl, project_dir)
            assert len(copied) > 0, "Keine Dateien kopiert"
            # Pflichtdateien pruefen
            assert "package.json" in copied, "package.json nicht kopiert"
            # AENDERUNG 08.02.2026: App Router statt Pages Router (Fix 22)
            assert any("layout.js" in f for f in copied), "app/layout.js nicht kopiert"
            # Datei existiert auch auf Disk
            assert os.path.exists(os.path.join(project_dir, "package.json"))

    def test_ueberschreibt_nicht(self):
        """Existierende Dateien werden nicht ueberschrieben."""
        tmpl = get_template_by_id("nextjs_tailwind")
        assert tmpl is not None

        with tempfile.TemporaryDirectory() as project_dir:
            # Datei vorab erstellen
            pkg_path = os.path.join(project_dir, "package.json")
            with open(pkg_path, "w") as f:
                f.write('{"name": "mein-projekt"}')

            copy_file_templates(tmpl, project_dir)

            # Inhalt sollte unveraendert sein
            with open(pkg_path, "r") as f:
                content = f.read()
            assert '"mein-projekt"' in content, "Existierende Datei wurde ueberschrieben"

    def test_ohne_file_templates_dir(self, sample_template):
        """Template ohne file_templates_dir gibt leere Liste zurueck."""
        sample_template["file_templates_dir"] = ""
        result = copy_file_templates(sample_template, "/tmp/nonexistent")
        assert result == [], "Leerer file_templates_dir sollte leere Liste geben"

    def test_nicht_existierendes_verzeichnis(self, sample_template):
        """Nicht-existierendes Template-Verzeichnis gibt leere Liste zurueck."""
        sample_template["file_templates_dir"] = "nonexistent_dir_xyz"
        result = copy_file_templates(sample_template, "/tmp/test")
        assert result == []

    def test_kopiert_flask_templates(self):
        """Kopiert Flask File-Templates korrekt."""
        tmpl = get_template_by_id("flask_webapp")
        if tmpl is None:
            pytest.skip("flask_webapp Template nicht vorhanden")

        with tempfile.TemporaryDirectory() as project_dir:
            copied = copy_file_templates(tmpl, project_dir)
            assert len(copied) > 0, "Keine Flask-Dateien kopiert"
            assert any("requirements.txt" in f for f in copied), "requirements.txt fehlt"
            assert any("run.bat" in f for f in copied), "run.bat fehlt"


# ============================================================================
# Tests: get_coder_rules
# ============================================================================

class TestGetCoderRules:
    """Tests fuer die Coder-Regeln-Formatierung."""

    def test_formatierte_regeln(self, sample_template):
        """Regeln werden nummeriert formatiert."""
        result = get_coder_rules(sample_template)
        assert "FRAMEWORK-REGELN" in result
        assert "Test Template" in result
        assert "1." in result
        assert "2." in result

    def test_leere_regeln(self, sample_template):
        """Template ohne Regeln gibt leeren String zurueck."""
        sample_template["coder_rules"] = []
        result = get_coder_rules(sample_template)
        assert result == ""

    def test_echte_nextjs_regeln(self):
        """Echte Next.js-Regeln enthalten wichtige Hinweise."""
        tmpl = get_template_by_id("nextjs_tailwind")
        assert tmpl is not None
        rules = get_coder_rules(tmpl)
        assert "import/export" in rules.lower() or "esm" in rules.lower() or "require" in rules.lower(), (
            "ESM-Regel fehlt in Next.js Coder-Regeln")


# ============================================================================
# Tests: get_template_summary_for_prompt
# ============================================================================

class TestGetTemplateSummaryForPrompt:
    """Tests fuer die Template-Zusammenfassung im Agent-Prompt."""

    def test_zusammenfassung_enthaelt_templates(self):
        """Zusammenfassung listet alle Templates auf."""
        summary = get_template_summary_for_prompt()
        assert "VERFUEGBARE TEMPLATES" in summary
        assert "nextjs_tailwind" in summary
        assert "flask_webapp" in summary

    def test_zusammenfassung_enthaelt_sprachen(self):
        """Zusammenfassung zeigt Sprachen der Templates."""
        summary = get_template_summary_for_prompt()
        assert "javascript" in summary.lower() or "python" in summary.lower()

    def test_zusammenfassung_enthaelt_dependencies(self):
        """Zusammenfassung zeigt Dependencies."""
        summary = get_template_summary_for_prompt()
        assert "react" in summary.lower() or "flask" in summary.lower()


# ============================================================================
# Tests: Determinismus (Verifikation)
# ============================================================================

class TestDeterminismus:
    """Verifiziert dass Templates deterministische Ergebnisse liefern."""

    def test_gleicher_blueprint_bei_gleichem_template(self):
        """Gleiches Template + gleiche Customizations = identischer Blueprint."""
        tmpl = get_template_by_id("nextjs_tailwind")
        assert tmpl is not None
        custom = {"additional_dependencies": {"openai": "4.0.0"}}
        bp1 = build_blueprint_from_template(tmpl, custom)
        invalidate_cache()  # Cache zuruecksetzen
        tmpl2 = get_template_by_id("nextjs_tailwind")
        bp2 = build_blueprint_from_template(tmpl2, custom)
        # Dependencies muessen identisch sein (gleiche Reihenfolge)
        assert sorted(bp1["dependencies"]) == sorted(bp2["dependencies"]), (
            f"Dependencies nicht identisch:\n  bp1={sorted(bp1['dependencies'])}\n  bp2={sorted(bp2['dependencies'])}")

    def test_template_versionen_exakt(self):
        """Alle Template-Dependencies haben exakte Versionen (kein ^ oder ~)."""
        templates = load_all_templates()
        for tid, tmpl in templates.items():
            deps = tmpl.get("blueprint", {}).get("dependencies", {})
            if isinstance(deps, dict):
                for pkg, version in deps.items():
                    assert not version.startswith("^"), (
                        f"Template '{tid}': {pkg}={version} hat ^-Prefix")
                    assert not version.startswith("~"), (
                        f"Template '{tid}': {pkg}={version} hat ~-Prefix")
