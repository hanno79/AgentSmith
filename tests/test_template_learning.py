# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 07.02.2026
Version: 1.0
Beschreibung: Tests fuer techstack_templates/template_learning.py
              Testet: Recipe-Extraktion, Aehnlichkeitssuche, Template-Vorschlag,
              Nutzungsstatistiken, Lernschleife
"""

import os
import sys
import json
import pytest
import tempfile
import shutil

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from techstack_templates.template_loader import invalidate_cache
from techstack_templates.template_learning import (
    extract_proven_recipe,
    find_similar_recipes,
    propose_new_template,
    save_learned_template,
    record_template_usage,
    try_learn_from_project,
    _extract_blueprint_from_archive,
    _load_usage_stats,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture(autouse=True)
def reset_cache():
    """Cache vor jedem Test zuruecksetzen."""
    invalidate_cache()
    yield
    invalidate_cache()


@pytest.fixture
def sample_project_archive():
    """Beispiel-Projektarchiv mit TechStack-Blueprint."""
    return {
        "project_id": "proj_2026-02-07_10-00-00_abc123",
        "name": "Test-Projekt",
        "goal": "Erstelle eine Todo-App mit Sprachsteuerung",
        "status": "success",
        "completed_at": "2026-02-07T12:00:00",
        "entries": [
            {
                "type": "TechStackOutput",
                "content": json.dumps({
                    "blueprint": {
                        "project_type": "nextjs",
                        "language": "javascript",
                        "_source_template": "nextjs_tailwind",
                        "dependencies": [
                            "next", "react", "react-dom", "tailwindcss",
                            "postcss", "autoprefixer",
                            "react-speech-recognition", "openai"
                        ]
                    }
                })
            }
        ]
    }


@pytest.fixture
def similar_project_archive():
    """Zweites aehnliches Projektarchiv fuer Lernschleife."""
    return {
        "project_id": "proj_2026-02-07_14-00-00_def456",
        "name": "Einkaufsliste Voice",
        "goal": "Einkaufsliste mit Spracheingabe",
        "status": "success",
        "completed_at": "2026-02-07T16:00:00",
        "entries": [
            {
                "type": "TechStackOutput",
                "content": json.dumps({
                    "blueprint": {
                        "project_type": "nextjs",
                        "language": "javascript",
                        "_source_template": "nextjs_tailwind",
                        "dependencies": [
                            "next", "react", "react-dom", "tailwindcss",
                            "postcss", "autoprefixer",
                            "react-speech-recognition", "annyang"
                        ]
                    }
                })
            }
        ]
    }


@pytest.fixture
def archive_dir(sample_project_archive, similar_project_archive):
    """Temporaeres Archiv-Verzeichnis mit 2 Projekten."""
    dir_path = tempfile.mkdtemp()
    for archive in [sample_project_archive, similar_project_archive]:
        filepath = os.path.join(dir_path, f"{archive['project_id']}.json")
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(archive, f)
    yield dir_path
    shutil.rmtree(dir_path, ignore_errors=True)


# ============================================================================
# Tests: _extract_blueprint_from_archive
# ============================================================================

class TestExtractBlueprintFromArchive:
    """Tests fuer die Blueprint-Extraktion aus Archiv-Eintraegen."""

    def test_techstack_output_typ(self, sample_project_archive):
        """Blueprint wird aus TechStackOutput-Eintrag extrahiert."""
        bp = _extract_blueprint_from_archive(sample_project_archive)
        assert bp is not None, "Blueprint nicht extrahiert"
        assert bp.get("project_type") == "nextjs"
        assert bp.get("language") == "javascript"

    def test_blueprint_typ(self):
        """Blueprint wird aus Blueprint-Eintrag extrahiert."""
        archive = {
            "entries": [
                {
                    "type": "Blueprint",
                    "content": json.dumps({
                        "project_type": "flask",
                        "language": "python"
                    })
                }
            ]
        }
        bp = _extract_blueprint_from_archive(archive)
        assert bp is not None
        assert bp["project_type"] == "flask"

    def test_kein_blueprint_vorhanden(self):
        """None wenn kein Blueprint-Eintrag existiert."""
        archive = {"entries": [{"type": "CodeOutput", "content": "print('hello')"}]}
        bp = _extract_blueprint_from_archive(archive)
        assert bp is None

    def test_leere_entries(self):
        """None bei leerer Entry-Liste."""
        assert _extract_blueprint_from_archive({"entries": []}) is None
        assert _extract_blueprint_from_archive({}) is None


# ============================================================================
# Tests: extract_proven_recipe
# ============================================================================

class TestExtractProvenRecipe:
    """Tests fuer die Recipe-Extraktion aus erfolgreichen Projekten."""

    def test_erfolgreiche_extraktion(self, sample_project_archive):
        """Recipe wird korrekt aus erfolgreichem Projekt extrahiert."""
        recipe = extract_proven_recipe(sample_project_archive)
        assert recipe is not None, "Recipe ist None"
        assert recipe["project_id"] == "proj_2026-02-07_10-00-00_abc123"
        assert recipe["base_template"] == "nextjs_tailwind"
        assert recipe["language"] == "javascript"

    def test_additional_dependencies_berechnet(self, sample_project_archive):
        """Additional Dependencies = Projekt-Deps minus Template-Deps."""
        recipe = extract_proven_recipe(sample_project_archive)
        assert recipe is not None
        additional = recipe["additional_dependencies"]
        # react-speech-recognition und openai sind zusaetzlich
        assert "react-speech-recognition" in additional, (
            f"react-speech-recognition fehlt in: {additional}")
        assert "openai" in additional, f"openai fehlt in: {additional}"
        # Template-Basis-Deps duerfen NICHT in additional sein
        assert "react" not in additional, "react ist Template-Basis, nicht additional"
        assert "next" not in additional, "next ist Template-Basis, nicht additional"

    def test_fehlgeschlagenes_projekt(self, sample_project_archive):
        """Fehlgeschlagenes Projekt gibt None zurueck."""
        sample_project_archive["status"] = "failed"
        recipe = extract_proven_recipe(sample_project_archive)
        assert recipe is None, "Fehlgeschlagenes Projekt sollte kein Recipe liefern"

    def test_leeres_archiv(self):
        """None bei leerem Archiv."""
        assert extract_proven_recipe(None) is None
        assert extract_proven_recipe({}) is None


# ============================================================================
# Tests: find_similar_recipes
# ============================================================================

class TestFindSimilarRecipes:
    """Tests fuer die Aehnlichkeitssuche in archivierten Projekten."""

    def test_findet_aehnliches_projekt(self, sample_project_archive, archive_dir):
        """Findet aehnliches Projekt mit gleicher Basis und aehnlichen Deps."""
        recipe = extract_proven_recipe(sample_project_archive)
        assert recipe is not None
        similar = find_similar_recipes(recipe, archive_dir, min_similarity=0.3)
        assert len(similar) > 0, "Kein aehnliches Projekt gefunden"
        # Aehnlichkeit muss gesetzt sein
        assert "similarity" in similar[0]
        assert similar[0]["similarity"] > 0

    def test_eigenes_projekt_ausgeschlossen(self, sample_project_archive, archive_dir):
        """Das eigene Projekt wird nicht als aehnlich zurueckgegeben."""
        recipe = extract_proven_recipe(sample_project_archive)
        similar = find_similar_recipes(recipe, archive_dir, min_similarity=0.0)
        own_ids = [r["project_id"] for r in similar]
        assert recipe["project_id"] not in own_ids, "Eigenes Projekt darf nicht in Ergebnissen sein"

    def test_leeres_archiv_verzeichnis(self, sample_project_archive):
        """Leeres Verzeichnis gibt leere Liste zurueck."""
        recipe = extract_proven_recipe(sample_project_archive)
        with tempfile.TemporaryDirectory() as empty_dir:
            similar = find_similar_recipes(recipe, empty_dir)
            assert similar == [], "Leeres Archiv sollte leere Liste geben"

    def test_nicht_existierendes_verzeichnis(self, sample_project_archive):
        """Nicht-existierendes Verzeichnis gibt leere Liste zurueck."""
        recipe = extract_proven_recipe(sample_project_archive)
        similar = find_similar_recipes(recipe, "/nonexistent/path/xyz")
        assert similar == []

    def test_ohne_additional_deps(self):
        """Recipe ohne additional_dependencies findet keine Aehnlichen."""
        recipe = {
            "project_id": "test",
            "base_template": "nextjs_tailwind",
            "additional_dependencies": []
        }
        with tempfile.TemporaryDirectory() as empty_dir:
            similar = find_similar_recipes(recipe, empty_dir)
            assert similar == []


# ============================================================================
# Tests: propose_new_template
# ============================================================================

class TestProposeNewTemplate:
    """Tests fuer die Template-Generierung aus aehnlichen Recipes."""

    def test_generiert_template_aus_2_recipes(self):
        """Generiert Template-Vorschlag aus 2 aehnlichen Recipes."""
        recipes = [
            {
                "project_id": "proj_1",
                "base_template": "nextjs_tailwind",
                "additional_dependencies": ["react-speech-recognition", "openai"]
            },
            {
                "project_id": "proj_2",
                "base_template": "nextjs_tailwind",
                "additional_dependencies": ["react-speech-recognition", "annyang"]
            }
        ]
        proposed = propose_new_template(recipes)
        assert proposed is not None, "Template-Vorschlag ist None"
        assert proposed["source"] == "learned"
        assert "nextjs_tailwind" in proposed["template_id"]
        # Gemeinsame Dependency: react-speech-recognition
        bp_deps = proposed["blueprint"].get("dependencies", {})
        if isinstance(bp_deps, dict):
            dep_keys = list(bp_deps.keys())
        else:
            dep_keys = bp_deps
        assert "react-speech-recognition" in dep_keys, (
            f"Gemeinsame Dep fehlt: {dep_keys}")

    def test_weniger_als_2_recipes(self):
        """Weniger als 2 Recipes gibt None zurueck."""
        assert propose_new_template([]) is None
        assert propose_new_template([{"base_template": "x"}]) is None

    def test_keine_gemeinsamen_deps(self):
        """Keine gemeinsamen additional_dependencies gibt None zurueck."""
        recipes = [
            {
                "project_id": "proj_1",
                "base_template": "nextjs_tailwind",
                "additional_dependencies": ["openai"]
            },
            {
                "project_id": "proj_2",
                "base_template": "nextjs_tailwind",
                "additional_dependencies": ["sharp"]
            }
        ]
        proposed = propose_new_template(recipes)
        assert proposed is None, "Ohne gemeinsame Deps darf kein Template vorgeschlagen werden"

    def test_ohne_base_template(self):
        """Recipes ohne base_template gibt None zurueck."""
        recipes = [
            {"project_id": "p1", "base_template": None, "additional_dependencies": ["a"]},
            {"project_id": "p2", "base_template": None, "additional_dependencies": ["a"]}
        ]
        proposed = propose_new_template(recipes)
        assert proposed is None

    def test_template_hat_pflichtfelder(self):
        """Generiertes Template hat alle Pflichtfelder."""
        recipes = [
            {
                "project_id": "p1", "base_template": "nextjs_tailwind",
                "additional_dependencies": ["axios"]
            },
            {
                "project_id": "p2", "base_template": "nextjs_tailwind",
                "additional_dependencies": ["axios", "lodash"]
            }
        ]
        proposed = propose_new_template(recipes)
        assert proposed is not None
        pflichtfelder = [
            "template_id", "template_version", "display_name",
            "source", "blueprint", "match_keywords"
        ]
        for feld in pflichtfelder:
            assert feld in proposed, f"Pflichtfeld '{feld}' fehlt im Template-Vorschlag"


# ============================================================================
# Tests: save_learned_template + record_template_usage
# ============================================================================

class TestSaveAndUsageTracking:
    """Tests fuer Template-Speicherung und Nutzungs-Tracking."""

    def test_save_learned_template(self):
        """Gelerntes Template wird als JSON gespeichert."""
        from techstack_templates.template_loader import get_template_by_id

        template = {
            "template_id": "ztest_learned_temp",
            "template_version": "1.0",
            "display_name": "Test Learned",
            "source": "learned",
            "blueprint": {"project_type": "test", "language": "python", "dependencies": {}},
            "match_keywords": ["test"],
        }
        try:
            tid = save_learned_template(template)
            assert tid == "ztest_learned_temp"
            # Cache invalidieren damit neues Template sichtbar wird
            invalidate_cache()
            loaded = get_template_by_id("ztest_learned_temp")
            assert loaded is not None, "Gespeichertes Template nicht ladbar"
            assert loaded["source"] == "learned"
        finally:
            # Aufraeumen
            stacks_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "techstack_templates", "stacks"
            )
            test_file = os.path.join(stacks_dir, "ztest_learned_temp.json")
            if os.path.exists(test_file):
                os.remove(test_file)
            invalidate_cache()

    def test_record_template_usage(self):
        """Template-Nutzung wird korrekt aufgezeichnet."""
        # Stats-Datei Pfad
        stacks_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "techstack_templates", "stacks"
        )
        stats_file = os.path.join(stacks_dir, "_usage_stats.json")

        # Vorherige Stats sichern
        old_stats = None
        if os.path.exists(stats_file):
            with open(stats_file, "r") as f:
                old_stats = json.load(f)

        try:
            record_template_usage("nextjs_tailwind", "test_proj_001", True)
            record_template_usage("nextjs_tailwind", "test_proj_002", False)

            stats = _load_usage_stats()
            assert "nextjs_tailwind" in stats, "Template nicht in Usage-Stats"
            entry = stats["nextjs_tailwind"]
            assert entry["total_uses"] >= 2, f"Erwartet: >= 2, Erhalten: {entry['total_uses']}"
            assert entry["successes"] >= 1
            assert entry["failures"] >= 1
        finally:
            # Stats wiederherstellen
            if old_stats is not None:
                with open(stats_file, "w") as f:
                    json.dump(old_stats, f, indent=2)
            elif os.path.exists(stats_file):
                os.remove(stats_file)


# ============================================================================
# Tests: try_learn_from_project (Integration)
# ============================================================================

class TestTryLearnFromProject:
    """Integrationstests fuer die gesamte Lernschleife."""

    def test_lernt_nicht_ohne_additional_deps(self, archive_dir):
        """Projekt ohne zusaetzliche Dependencies loest kein Lernen aus."""
        archive = {
            "project_id": "proj_no_extra",
            "status": "success",
            "entries": [{
                "type": "TechStackOutput",
                "content": json.dumps({
                    "blueprint": {
                        "project_type": "nextjs",
                        "language": "javascript",
                        "_source_template": "nextjs_tailwind",
                        "dependencies": ["next", "react", "react-dom",
                                         "tailwindcss", "postcss", "autoprefixer"]
                    }
                })
            }]
        }
        result = try_learn_from_project(archive, archive_dir)
        assert result is None, "Ohne additional_deps darf kein Template gelernt werden"

    def test_fehlgeschlagenes_projekt_kein_lernen(self, archive_dir):
        """Fehlgeschlagenes Projekt loest kein Lernen aus."""
        archive = {"project_id": "proj_fail", "status": "failed", "entries": []}
        result = try_learn_from_project(archive, archive_dir)
        assert result is None
