# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 14.02.2026
Version: 1.0
Beschreibung: Unit Tests fuer agents/planner_defaults.py - PROTECTED_CONFIGS,
              PROTECTED_CONFIG_STEMS, create_default_plan, sort_files_by_priority,
              get_ready_files und Template-basierte Plan-Erstellung.
"""

import os
import sys
import pytest
from unittest.mock import patch, MagicMock

# Projekt-Root zum Python-Path hinzufuegen
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.planner_defaults import (
    PROTECTED_CONFIGS,
    PROTECTED_CONFIG_STEMS,
    _create_template_based_plan,
    create_default_plan,
    sort_files_by_priority,
    get_ready_files,
)


# =========================================================================
# Tests fuer PROTECTED_CONFIGS
# =========================================================================
class TestProtectedConfigs:
    """Tests fuer die PROTECTED_CONFIGS Konstantenmenge."""

    def test_ist_ein_set(self):
        """PROTECTED_CONFIGS ist ein Set."""
        assert isinstance(PROTECTED_CONFIGS, set)

    def test_enthaelt_tailwind_config(self):
        """tailwind.config.js ist geschuetzt."""
        assert "tailwind.config.js" in PROTECTED_CONFIGS

    def test_enthaelt_postcss_config(self):
        """postcss.config.js ist geschuetzt."""
        assert "postcss.config.js" in PROTECTED_CONFIGS

    def test_enthaelt_next_config(self):
        """next.config.js ist geschuetzt."""
        assert "next.config.js" in PROTECTED_CONFIGS

    def test_enthaelt_jsconfig(self):
        """jsconfig.json ist geschuetzt."""
        assert "jsconfig.json" in PROTECTED_CONFIGS

    def test_enthaelt_tsconfig(self):
        """tsconfig.json ist geschuetzt."""
        assert "tsconfig.json" in PROTECTED_CONFIGS

    def test_enthaelt_vite_config(self):
        """vite.config.js ist geschuetzt."""
        assert "vite.config.js" in PROTECTED_CONFIGS

    def test_enthaelt_mjs_varianten(self):
        """Fix 52: .mjs Varianten sind enthalten."""
        assert "postcss.config.mjs" in PROTECTED_CONFIGS
        assert "next.config.mjs" in PROTECTED_CONFIGS
        assert "vite.config.mjs" in PROTECTED_CONFIGS

    def test_enthaelt_ts_varianten(self):
        """Fix 52: .ts Varianten sind enthalten."""
        assert "tailwind.config.ts" in PROTECTED_CONFIGS
        assert "postcss.config.ts" in PROTECTED_CONFIGS
        assert "next.config.ts" in PROTECTED_CONFIGS
        assert "vite.config.ts" in PROTECTED_CONFIGS

    def test_enthaelt_globals_css(self):
        """Fix 57d: globals.css ist geschuetzt (Shadcn CSS-Variablen)."""
        assert "globals.css" in PROTECTED_CONFIGS

    def test_mindestgroesse(self):
        """Mindestens 10 geschuetzte Configs."""
        assert len(PROTECTED_CONFIGS) >= 10

    def test_keine_source_code_dateien(self):
        """Keine Source-Code-Dateien (page.js, layout.js etc.) enthalten."""
        for cfg in PROTECTED_CONFIGS:
            assert "page" not in cfg, f"{cfg} sollte nicht geschuetzt sein"
            assert "layout" not in cfg, f"{cfg} sollte nicht geschuetzt sein"
            assert "route" not in cfg, f"{cfg} sollte nicht geschuetzt sein"


# =========================================================================
# Tests fuer PROTECTED_CONFIG_STEMS
# =========================================================================
class TestProtectedConfigStems:
    """Tests fuer die PROTECTED_CONFIG_STEMS Stem-Varianten."""

    def test_ist_ein_set(self):
        """PROTECTED_CONFIG_STEMS ist ein Set."""
        assert isinstance(PROTECTED_CONFIG_STEMS, set)

    def test_enthaelt_tailwind_config_stem(self):
        """tailwind.config Stem ist enthalten."""
        assert "tailwind.config" in PROTECTED_CONFIG_STEMS

    def test_enthaelt_next_config_stem(self):
        """next.config Stem ist enthalten."""
        assert "next.config" in PROTECTED_CONFIG_STEMS

    def test_enthaelt_postcss_config_stem(self):
        """postcss.config Stem ist enthalten."""
        assert "postcss.config" in PROTECTED_CONFIG_STEMS

    def test_enthaelt_vite_config_stem(self):
        """vite.config Stem ist enthalten."""
        assert "vite.config" in PROTECTED_CONFIG_STEMS

    def test_keine_json_stems(self):
        """JSON-Dateien erzeugen keine Stems (nur .js/.mjs/.ts)."""
        # jsconfig und tsconfig enden auf .json und sind NICHT in
        # PROTECTED_CONFIG_STEMS (nur .js/.mjs/.ts werden gestemmt)
        for stem in PROTECTED_CONFIG_STEMS:
            assert not stem.endswith(".json"), f"{stem} sollte kein JSON-Stem sein"

    def test_stems_sind_ohne_extension(self):
        """Stems haben keine Dateiendung."""
        for stem in PROTECTED_CONFIG_STEMS:
            assert not stem.endswith(".js"), f"{stem} hat noch Extension"
            assert not stem.endswith(".ts"), f"{stem} hat noch Extension"
            assert not stem.endswith(".mjs"), f"{stem} hat noch Extension"

    def test_stem_match_logik(self):
        """Stem-Match: next.config.mjs matcht next.config Stem."""
        test_datei = "next.config.mjs"
        datei_stem = os.path.splitext(test_datei)[0]
        assert datei_stem in PROTECTED_CONFIG_STEMS


# =========================================================================
# Tests fuer _create_template_based_plan
# =========================================================================
class TestCreateTemplateBasedPlan:
    """Tests fuer die Template-basierte Plan-Erstellung."""

    def test_ohne_source_template_gibt_none(self):
        """Ohne _source_template wird None zurueckgegeben."""
        blueprint = {"project_type": "webapp"}
        result = _create_template_based_plan(blueprint)
        assert result is None

    def test_leeres_blueprint_gibt_none(self):
        """Leeres Blueprint gibt None zurueck."""
        result = _create_template_based_plan({})
        assert result is None

    @patch("techstack_templates.template_loader.load_all_templates")
    def test_unbekanntes_template_gibt_none(self, mock_load):
        """Unbekanntes Template gibt None zurueck."""
        mock_load.return_value = {"nextjs": {}}
        blueprint = {"_source_template": "unbekannt_template"}
        result = _create_template_based_plan(blueprint)
        assert result is None

    @patch("techstack_templates.template_loader.load_all_templates")
    def test_template_mit_required_files(self, mock_load):
        """Template mit required_files erzeugt einen Plan."""
        mock_load.return_value = {
            "nextjs": {
                "required_files": [
                    "app/globals.css",
                    "app/layout.js",
                    "app/page.js",
                    "package.json",
                ]
            }
        }
        blueprint = {
            "_source_template": "nextjs",
            "project_type": "next",
            "database": "none",
            "package_file": "package.json"
        }
        result = _create_template_based_plan(blueprint)
        assert result is not None
        assert len(result) >= 3  # Minimum 3 Dateien noetig
        pfade = [f["path"] for f in result]
        assert "package.json" in pfade

    @patch("techstack_templates.template_loader.load_all_templates")
    def test_template_mit_db(self, mock_load):
        """Template mit Datenbank fuegt DB-Datei hinzu."""
        mock_load.return_value = {
            "nextjs": {
                "required_files": [
                    "app/globals.css",
                    "app/layout.js",
                    "app/page.js",
                ]
            }
        }
        blueprint = {
            "_source_template": "nextjs",
            "project_type": "next",
            "database": "sqlite",
            "package_file": "package.json"
        }
        result = _create_template_based_plan(blueprint)
        assert result is not None
        pfade = [f["path"] for f in result]
        assert "lib/db.js" in pfade

    @patch("techstack_templates.template_loader.load_all_templates")
    def test_template_run_bat_wird_hinzugefuegt(self, mock_load):
        """run.bat wird automatisch hinzugefuegt wenn nicht vorhanden."""
        mock_load.return_value = {
            "nextjs": {
                "required_files": [
                    "app/globals.css",
                    "app/layout.js",
                    "app/page.js",
                ]
            }
        }
        blueprint = {
            "_source_template": "nextjs",
            "project_type": "next",
            "database": "none",
            "package_file": "package.json"
        }
        result = _create_template_based_plan(blueprint)
        assert result is not None
        pfade = [f["path"] for f in result]
        assert "run.bat" in pfade

    @patch("techstack_templates.template_loader.load_all_templates")
    def test_protected_configs_werden_uebersprungen(self, mock_load):
        """Config-Dateien aus PROTECTED_CONFIGS werden nicht in den Plan aufgenommen."""
        mock_load.return_value = {
            "nextjs": {
                "required_files": [
                    "tailwind.config.js",
                    "postcss.config.js",
                    "app/globals.css",
                    "app/layout.js",
                    "app/page.js",
                ]
            }
        }
        blueprint = {
            "_source_template": "nextjs",
            "project_type": "next",
            "database": "none",
            "package_file": "package.json"
        }
        result = _create_template_based_plan(blueprint)
        assert result is not None
        pfade = [f["path"] for f in result]
        # PROTECTED_CONFIGS sollten als Priority-4 Anwendungsdateien uebersprungen werden
        assert "tailwind.config.js" not in pfade
        assert "postcss.config.js" not in pfade

    @patch("techstack_templates.template_loader.load_all_templates")
    def test_weniger_als_3_dateien_gibt_none(self, mock_load):
        """Plan mit weniger als 3 Dateien gibt None zurueck."""
        mock_load.return_value = {
            "minimal": {
                "required_files": ["package.json"]
            }
        }
        blueprint = {
            "_source_template": "minimal",
            "project_type": "node",
            "database": "none",
            "package_file": "package.json"
        }
        result = _create_template_based_plan(blueprint)
        # package.json + run.bat = 2, weniger als 3 → None
        assert result is None

    @patch("techstack_templates.template_loader.load_all_templates")
    def test_import_fehler_gibt_none(self, mock_load):
        """ImportError bei Template-Laden gibt None zurueck."""
        mock_load.side_effect = ImportError("Kein Template-Modul")
        blueprint = {"_source_template": "test"}
        result = _create_template_based_plan(blueprint)
        assert result is None


# =========================================================================
# Tests fuer create_default_plan
# =========================================================================
class TestCreateDefaultPlan:
    """Tests fuer die create_default_plan Funktion."""

    def test_python_default_plan(self):
        """Python-Blueprint erzeugt Python-Standardplan."""
        blueprint = {"language": "python", "project_type": "python_script"}
        plan = create_default_plan(blueprint, "Erstelle eine App")
        assert plan["source"] == "default_fallback"
        assert plan["total_files"] > 0
        pfade = [f["path"] for f in plan["files"]]
        assert "src/main.py" in pfade
        assert "requirements.txt" in pfade
        assert "run.bat" in pfade

    def test_javascript_default_plan(self):
        """JavaScript-Blueprint erzeugt JS-Standardplan."""
        blueprint = {"language": "javascript", "project_type": "node_app"}
        plan = create_default_plan(blueprint, "Erstelle eine App")
        assert plan["source"] == "default_fallback"
        pfade = [f["path"] for f in plan["files"]]
        assert "src/index.js" in pfade
        assert "package.json" in pfade
        assert "run.bat" in pfade

    def test_javascript_mit_db(self):
        """JavaScript-Blueprint mit Datenbank fuegt DB-Datei hinzu."""
        blueprint = {"language": "javascript", "project_type": "node_app", "database": "sqlite"}
        plan = create_default_plan(blueprint, "App mit DB")
        pfade = [f["path"] for f in plan["files"]]
        assert "src/database.js" in pfade

    def test_nextjs_mit_db(self):
        """Next.js-Blueprint mit DB nutzt lib/db.js."""
        blueprint = {"language": "javascript", "project_type": "next_app", "database": "sqlite"}
        plan = create_default_plan(blueprint, "Next.js App")
        pfade = [f["path"] for f in plan["files"]]
        assert "lib/db.js" in pfade

    def test_unbekannte_sprache_fallback(self):
        """Unbekannte Sprache erzeugt generischen Fallback."""
        blueprint = {"language": "cobol", "project_type": "legacy"}
        plan = create_default_plan(blueprint, "Irgendwas")
        assert plan["source"] == "default_fallback"
        assert plan["total_files"] > 0
        pfade = [f["path"] for f in plan["files"]]
        assert "src/main.py" in pfade
        assert "run.bat" in pfade

    def test_leeres_blueprint(self):
        """Leeres Blueprint erzeugt Python-Fallback."""
        plan = create_default_plan({}, "Test")
        assert plan["source"] == "default_fallback"
        pfade = [f["path"] for f in plan["files"]]
        assert "src/main.py" in pfade or "src/config.py" in pfade

    def test_plan_hat_project_name(self):
        """Plan hat immer project_name."""
        plan = create_default_plan({"language": "python"}, "Test")
        assert plan["project_name"] == "project"

    def test_plan_hat_total_files(self):
        """total_files stimmt mit Anzahl der Dateien ueberein."""
        plan = create_default_plan({"language": "python"}, "Test")
        assert plan["total_files"] == len(plan["files"])

    def test_plan_hat_estimated_lines(self):
        """estimated_lines ist Summe der Einzel-Schaetzungen."""
        plan = create_default_plan({"language": "python"}, "Test")
        erwartete_summe = sum(f["estimated_lines"] for f in plan["files"])
        assert plan["estimated_lines"] == erwartete_summe

    def test_dateien_haben_pflichtfelder(self):
        """Jede Datei hat path, description, depends_on, estimated_lines, priority."""
        plan = create_default_plan({"language": "python"}, "Test")
        for f in plan["files"]:
            assert "path" in f, f"path fehlt in {f}"
            assert "description" in f, f"description fehlt in {f}"
            assert "depends_on" in f, f"depends_on fehlt in {f}"
            assert "estimated_lines" in f, f"estimated_lines fehlt in {f}"
            assert "priority" in f, f"priority fehlt in {f}"

    @patch("agents.planner_defaults._create_template_based_plan")
    def test_template_plan_hat_vorrang(self, mock_template):
        """Template-basierter Plan hat Vorrang vor generischem Fallback."""
        mock_template.return_value = [
            {"path": "a.js", "description": "A", "depends_on": [], "estimated_lines": 10, "priority": 1},
            {"path": "b.js", "description": "B", "depends_on": [], "estimated_lines": 20, "priority": 2},
            {"path": "c.js", "description": "C", "depends_on": [], "estimated_lines": 30, "priority": 3},
        ]
        plan = create_default_plan({"language": "javascript"}, "Test")
        assert plan["source"] == "template_fallback"
        assert plan["total_files"] == 3


# =========================================================================
# Tests fuer sort_files_by_priority
# =========================================================================
class TestSortFilesByPriority:
    """Tests fuer die Sortierung nach Prioritaet."""

    def test_sortierung_nach_priority(self):
        """Dateien werden primaer nach priority sortiert."""
        plan = {
            "files": [
                {"path": "c.js", "priority": 3, "depends_on": []},
                {"path": "a.js", "priority": 1, "depends_on": []},
                {"path": "b.js", "priority": 2, "depends_on": []},
            ]
        }
        result = sort_files_by_priority(plan)
        assert result[0]["path"] == "a.js"
        assert result[1]["path"] == "b.js"
        assert result[2]["path"] == "c.js"

    def test_sekundaere_sortierung_nach_abhaengigkeiten(self):
        """Bei gleicher Prioritaet wird nach Anzahl Abhaengigkeiten sortiert."""
        plan = {
            "files": [
                {"path": "b.js", "priority": 1, "depends_on": ["x.js", "y.js"]},
                {"path": "a.js", "priority": 1, "depends_on": []},
            ]
        }
        result = sort_files_by_priority(plan)
        assert result[0]["path"] == "a.js"
        assert result[1]["path"] == "b.js"

    def test_leerer_plan(self):
        """Leerer Plan gibt leere Liste zurueck."""
        result = sort_files_by_priority({"files": []})
        assert result == []

    def test_plan_ohne_files_key(self):
        """Plan ohne files-Key gibt leere Liste zurueck."""
        result = sort_files_by_priority({})
        assert result == []

    def test_fehlende_priority_wird_999(self):
        """Fehlende priority wird als 999 behandelt."""
        plan = {
            "files": [
                {"path": "a.js", "depends_on": []},
                {"path": "b.js", "priority": 1, "depends_on": []},
            ]
        }
        result = sort_files_by_priority(plan)
        assert result[0]["path"] == "b.js"
        assert result[1]["path"] == "a.js"


# =========================================================================
# Tests fuer get_ready_files
# =========================================================================
class TestGetReadyFiles:
    """Tests fuer die Abhaengigkeitspruefung."""

    def test_dateien_ohne_abhaengigkeiten_sofort_bereit(self):
        """Dateien ohne Abhaengigkeiten sind sofort bereit."""
        plan = {
            "files": [
                {"path": "a.js", "depends_on": []},
                {"path": "b.js", "depends_on": []},
            ]
        }
        ready = get_ready_files(plan, completed_files=[])
        assert len(ready) == 2

    def test_abhaengigkeiten_muessen_erfuellt_sein(self):
        """Dateien mit unerfuellten Abhaengigkeiten sind nicht bereit."""
        plan = {
            "files": [
                {"path": "a.js", "depends_on": []},
                {"path": "b.js", "depends_on": ["a.js"]},
            ]
        }
        ready = get_ready_files(plan, completed_files=[])
        assert len(ready) == 1
        assert ready[0]["path"] == "a.js"

    def test_erfuellte_abhaengigkeiten(self):
        """Nach Abschluss von a.js ist b.js bereit."""
        plan = {
            "files": [
                {"path": "a.js", "depends_on": []},
                {"path": "b.js", "depends_on": ["a.js"]},
            ]
        }
        ready = get_ready_files(plan, completed_files=["a.js"])
        assert len(ready) == 1
        assert ready[0]["path"] == "b.js"

    def test_bereits_erstellte_dateien_werden_uebersprungen(self):
        """Bereits erstellte Dateien tauchen nicht als bereit auf."""
        plan = {
            "files": [
                {"path": "a.js", "depends_on": []},
                {"path": "b.js", "depends_on": []},
            ]
        }
        ready = get_ready_files(plan, completed_files=["a.js"])
        assert len(ready) == 1
        assert ready[0]["path"] == "b.js"

    def test_alle_dateien_erledigt(self):
        """Wenn alle Dateien erledigt sind, ist die Liste leer."""
        plan = {
            "files": [
                {"path": "a.js", "depends_on": []},
                {"path": "b.js", "depends_on": ["a.js"]},
            ]
        }
        ready = get_ready_files(plan, completed_files=["a.js", "b.js"])
        assert ready == []

    def test_mehrstufige_abhaengigkeiten(self):
        """Mehrstufige Abhaengigkeitskette wird korrekt aufgeloest."""
        plan = {
            "files": [
                {"path": "config.py", "depends_on": []},
                {"path": "db.py", "depends_on": ["config.py"]},
                {"path": "main.py", "depends_on": ["config.py", "db.py"]},
            ]
        }
        # Stufe 1: Nur config.py bereit
        ready1 = get_ready_files(plan, completed_files=[])
        assert len(ready1) == 1
        assert ready1[0]["path"] == "config.py"

        # Stufe 2: Nach config.py -> db.py bereit
        ready2 = get_ready_files(plan, completed_files=["config.py"])
        assert len(ready2) == 1
        assert ready2[0]["path"] == "db.py"

        # Stufe 3: Nach config+db -> main.py bereit
        ready3 = get_ready_files(plan, completed_files=["config.py", "db.py"])
        assert len(ready3) == 1
        assert ready3[0]["path"] == "main.py"

    def test_leerer_plan(self):
        """Leerer Plan gibt leere Liste zurueck."""
        ready = get_ready_files({"files": []}, completed_files=[])
        assert ready == []

    def test_plan_ohne_files_key(self):
        """Plan ohne files-Key gibt leere Liste zurueck."""
        ready = get_ready_files({}, completed_files=[])
        assert ready == []

    def test_fehlende_depends_on_wird_als_leer_behandelt(self):
        """Fehlende depends_on wird als leere Liste behandelt."""
        plan = {
            "files": [
                {"path": "a.js"},
            ]
        }
        ready = get_ready_files(plan, completed_files=[])
        assert len(ready) == 1
