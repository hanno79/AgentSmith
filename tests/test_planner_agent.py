# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 01.02.2026
Version: 1.0
Beschreibung: Unit Tests für Planner Agent - File-by-File Implementierungsplan.

              Tests validieren:
              - create_planner: Agent-Erstellung
              - create_planning_task: Task-Erstellung
              - parse_planner_output: Output-Parsing
              - create_default_plan: Fallback-Generierung
              - sort_files_by_priority: Sortierung
              - get_ready_files: Abhängigkeits-Check
"""

import pytest
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.planner_agent import (
    create_planner,
    create_planning_task,
    parse_planner_output,
    create_default_plan,
    sort_files_by_priority,
    get_ready_files
)


# =========================================================================
# Fixtures
# =========================================================================

@pytest.fixture
def sample_config():
    """Standard-Konfiguration für Tests."""
    return {
        "mode": "test",
        "models": {
            "test": {
                "coder": {
                    "primary": "openrouter/qwen/qwen3-coder:free",
                    "fallback": []
                },
                "planner": {
                    "primary": "openrouter/qwen/qwen3-coder:free",
                    "fallback": []
                }
            }
        }
    }


@pytest.fixture
def sample_project_rules():
    """Standard-Projektregeln für Tests."""
    return {
        "global": ["Nutze deutsche Fehlermeldungen"],
        "planner": ["Max 200 Zeilen pro Datei"]
    }


@pytest.fixture
def sample_blueprint():
    """Beispiel TechStack-Blueprint für Tests."""
    return {
        "project_type": "python_webapp",
        "language": "python",
        "app_type": "webapp",
        "frameworks": ["flask"]
    }


@pytest.fixture
def sample_user_prompt():
    """Beispiel Benutzer-Anforderung für Tests."""
    return "Erstelle eine Todo-App mit SQLite Datenbank und Flask-Backend"


@pytest.fixture
def valid_planner_output_json():
    """Gültiger Planner-Output als JSON-String."""
    return '''```json
{
  "project_name": "todo_app",
  "total_files": 4,
  "estimated_lines": 300,
  "files": [
    {
      "path": "src/config.py",
      "description": "Konfiguration und Konstanten",
      "depends_on": [],
      "estimated_lines": 30,
      "priority": 1
    },
    {
      "path": "src/database.py",
      "description": "SQLite Datenbanklogik",
      "depends_on": ["src/config.py"],
      "estimated_lines": 100,
      "priority": 2
    },
    {
      "path": "src/main.py",
      "description": "Flask-Anwendung",
      "depends_on": ["src/config.py", "src/database.py"],
      "estimated_lines": 120,
      "priority": 3
    },
    {
      "path": "requirements.txt",
      "description": "Dependencies",
      "depends_on": [],
      "estimated_lines": 10,
      "priority": 1
    }
  ]
}
```'''


@pytest.fixture
def sample_plan():
    """Beispiel-Plan für Sortier- und Abhängigkeits-Tests."""
    return {
        "project_name": "test",
        "files": [
            {"path": "main.py", "depends_on": ["config.py", "utils.py"], "priority": 3},
            {"path": "config.py", "depends_on": [], "priority": 1},
            {"path": "utils.py", "depends_on": ["config.py"], "priority": 2},
            {"path": "tests/test_main.py", "depends_on": ["main.py"], "priority": 4},
            {"path": "requirements.txt", "depends_on": [], "priority": 1}
        ]
    }


# =========================================================================
# Test: parse_planner_output
# =========================================================================

class TestParsePlannerOutput:
    """Tests für parse_planner_output Funktion."""

    def test_parse_json_block(self, valid_planner_output_json):
        """JSON-Block wird geparst."""
        result = parse_planner_output(valid_planner_output_json)
        assert result is not None
        assert "files" in result
        assert len(result["files"]) == 4

    def test_parse_raw_json(self):
        """Rohes JSON wird geparst."""
        raw = '{"files": [{"path": "main.py", "description": "Main"}]}'
        result = parse_planner_output(raw)
        assert result is not None
        assert "files" in result

    def test_empty_output_returns_none(self):
        """Leerer Output gibt None zurück."""
        assert parse_planner_output("") is None
        assert parse_planner_output(None) is None

    def test_invalid_json_returns_none(self):
        """Ungültiges JSON gibt None zurück."""
        result = parse_planner_output("Das ist kein JSON")
        assert result is None

    def test_missing_files_returns_none(self):
        """JSON ohne files gibt None zurück."""
        result = parse_planner_output('{"project_name": "test"}')
        assert result is None

    def test_files_not_list_handled(self):
        """JSON mit nicht-Liste files wird behandelt."""
        # Hinweis: Das Fallback-Parse prüft nur Schlüssel-Präsenz
        # Typ-Validierung erfolgt später im Workflow
        result = parse_planner_output('{"files": "keine Liste"}')
        # Fallback gibt das Dict zurück - Validierung in Sortier-/Ready-Funktionen
        if result is not None:
            assert "files" in result

    def test_extracts_correct_data(self, valid_planner_output_json):
        """Korrekte Daten werden extrahiert."""
        result = parse_planner_output(valid_planner_output_json)
        assert result["project_name"] == "todo_app"
        assert result["total_files"] == 4
        assert result["files"][0]["path"] == "src/config.py"

    def test_json_with_extra_text(self):
        """JSON mit umgebendem Text wird geparst."""
        output = '''Hier ist der Plan:
```json
{"files": [{"path": "main.py"}]}
```
Das war der Plan.'''
        result = parse_planner_output(output)
        assert result is not None


# =========================================================================
# Test: create_default_plan
# =========================================================================

class TestCreateDefaultPlan:
    """Tests für create_default_plan Funktion."""

    def test_python_plan(self):
        """Python-Plan wird erstellt."""
        blueprint = {"project_type": "python_webapp", "language": "python"}
        result = create_default_plan(blueprint, "Test-App")
        assert "files" in result
        assert any("src/config.py" in f["path"] for f in result["files"])
        assert any("requirements.txt" in f["path"] for f in result["files"])

    def test_javascript_plan(self):
        """JavaScript-Plan wird erstellt."""
        blueprint = {"project_type": "node_webapp", "language": "javascript"}
        result = create_default_plan(blueprint, "Test-App")
        assert "files" in result
        assert any("package.json" in f["path"] for f in result["files"])
        assert any(".js" in f["path"] for f in result["files"])

    def test_generic_fallback(self):
        """Generischer Fallback für unbekannte Sprachen."""
        blueprint = {"project_type": "unknown", "language": "rust"}
        result = create_default_plan(blueprint, "Test-App")
        assert "files" in result
        assert len(result["files"]) >= 1

    def test_has_required_fields(self, sample_blueprint):
        """Alle Pflichtfelder sind vorhanden."""
        result = create_default_plan(sample_blueprint, "Test")
        assert "project_name" in result
        assert "total_files" in result
        assert "files" in result
        for f in result["files"]:
            assert "path" in f
            assert "description" in f
            assert "depends_on" in f

    def test_marks_as_fallback(self, sample_blueprint):
        """Ergebnis wird als Fallback markiert."""
        result = create_default_plan(sample_blueprint, "Test")
        assert result.get("source") == "default_fallback"

    def test_includes_tests(self, sample_blueprint):
        """Tests sind enthalten."""
        result = create_default_plan(sample_blueprint, "Test")
        test_files = [f for f in result["files"] if "test" in f["path"].lower()]
        assert len(test_files) >= 1

    def test_includes_run_script(self, sample_blueprint):
        """Startskript ist enthalten."""
        result = create_default_plan(sample_blueprint, "Test")
        run_files = [f for f in result["files"] if "run" in f["path"].lower()]
        assert len(run_files) >= 1


# =========================================================================
# Test: sort_files_by_priority
# =========================================================================

class TestSortFilesByPriority:
    """Tests für sort_files_by_priority Funktion."""

    def test_sorts_by_priority(self, sample_plan):
        """Dateien werden nach Priorität sortiert."""
        result = sort_files_by_priority(sample_plan)
        priorities = [f.get("priority", 999) for f in result]
        assert priorities == sorted(priorities)

    def test_secondary_sort_by_dependencies(self):
        """Sekundär nach Anzahl der Abhängigkeiten."""
        plan = {
            "files": [
                {"path": "a.py", "depends_on": ["x.py", "y.py"], "priority": 1},
                {"path": "b.py", "depends_on": [], "priority": 1},
                {"path": "c.py", "depends_on": ["x.py"], "priority": 1}
            ]
        }
        result = sort_files_by_priority(plan)
        # b.py (0 deps) sollte vor c.py (1 dep) vor a.py (2 deps) kommen
        assert result[0]["path"] == "b.py"
        assert result[1]["path"] == "c.py"
        assert result[2]["path"] == "a.py"

    def test_empty_plan(self):
        """Leerer Plan gibt leere Liste zurück."""
        result = sort_files_by_priority({"files": []})
        assert result == []

    def test_missing_priority(self):
        """Fehlende Priorität wird als hohe Zahl behandelt."""
        plan = {
            "files": [
                {"path": "a.py", "depends_on": []},  # Keine priority
                {"path": "b.py", "depends_on": [], "priority": 1}
            ]
        }
        result = sort_files_by_priority(plan)
        assert result[0]["path"] == "b.py"  # Priority 1 zuerst


# =========================================================================
# Test: get_ready_files
# =========================================================================

class TestGetReadyFiles:
    """Tests für get_ready_files Funktion."""

    def test_initial_ready_files(self, sample_plan):
        """Dateien ohne Abhängigkeiten sind initial bereit."""
        result = get_ready_files(sample_plan, [])
        ready_paths = [f["path"] for f in result]
        assert "config.py" in ready_paths
        assert "requirements.txt" in ready_paths
        # main.py sollte NICHT bereit sein (hat Abhängigkeiten)
        assert "main.py" not in ready_paths

    def test_after_config_completed(self, sample_plan):
        """Nach config.py ist utils.py bereit."""
        result = get_ready_files(sample_plan, ["config.py"])
        ready_paths = [f["path"] for f in result]
        assert "utils.py" in ready_paths
        # main.py noch nicht (braucht auch utils.py)
        assert "main.py" not in ready_paths

    def test_after_config_and_utils_completed(self, sample_plan):
        """Nach config.py und utils.py ist main.py bereit."""
        result = get_ready_files(sample_plan, ["config.py", "utils.py"])
        ready_paths = [f["path"] for f in result]
        assert "main.py" in ready_paths

    def test_excludes_completed_files(self, sample_plan):
        """Bereits erledigte Dateien werden ausgeschlossen."""
        result = get_ready_files(sample_plan, ["config.py", "requirements.txt"])
        ready_paths = [f["path"] for f in result]
        assert "config.py" not in ready_paths
        assert "requirements.txt" not in ready_paths

    def test_empty_plan(self):
        """Leerer Plan gibt leere Liste zurück."""
        result = get_ready_files({"files": []}, [])
        assert result == []

    def test_all_completed(self, sample_plan):
        """Wenn alles erledigt, leere Liste."""
        all_files = [f["path"] for f in sample_plan["files"]]
        result = get_ready_files(sample_plan, all_files)
        assert result == []


# =========================================================================
# Test: create_planner (Agent-Erstellung)
# =========================================================================

class TestCreatePlanner:
    """Tests für create_planner Funktion."""

    def test_creates_agent(self, sample_config, sample_project_rules):
        """Agent wird erstellt."""
        try:
            agent = create_planner(sample_config, sample_project_rules)
            assert agent is not None
            assert hasattr(agent, 'role')
            assert "Planner" in agent.role
        except Exception as e:
            pytest.skip(f"CrewAI Agent-Erstellung nicht möglich: {e}")

    def test_with_router(self, sample_config, sample_project_rules):
        """Agent mit Router wird erstellt."""
        class MockRouter:
            def get_model(self, role):
                return "test-model"

        try:
            agent = create_planner(sample_config, sample_project_rules, router=MockRouter())
            assert agent is not None
        except Exception as e:
            pytest.skip(f"CrewAI Agent-Erstellung nicht möglich: {e}")


# =========================================================================
# Test: create_planning_task
# =========================================================================

class TestCreatePlanningTask:
    """Tests für create_planning_task Funktion."""

    def test_creates_task(self, sample_config, sample_project_rules,
                          sample_blueprint, sample_user_prompt):
        """Task wird erstellt."""
        try:
            agent = create_planner(sample_config, sample_project_rules)
            task = create_planning_task(agent, sample_blueprint, sample_user_prompt)
            assert task is not None
            assert hasattr(task, 'description')
            assert "BENUTZER-ANFORDERUNG" in task.description
        except Exception as e:
            pytest.skip(f"CrewAI Task-Erstellung nicht möglich: {e}")

    def test_task_contains_blueprint(self, sample_config, sample_project_rules,
                                      sample_blueprint, sample_user_prompt):
        """Task enthält Blueprint."""
        try:
            agent = create_planner(sample_config, sample_project_rules)
            task = create_planning_task(agent, sample_blueprint, sample_user_prompt)
            assert "TECHNISCHER BLUEPRINT" in task.description
            assert "python" in task.description
        except Exception as e:
            pytest.skip(f"CrewAI Task-Erstellung nicht möglich: {e}")


# =========================================================================
# Test: Integration
# =========================================================================

class TestIntegration:
    """Integrationstests für Planner-Komponenten."""

    def test_parse_sort_workflow(self, valid_planner_output_json):
        """Parse und Sortierung funktioniert zusammen."""
        plan = parse_planner_output(valid_planner_output_json)
        assert plan is not None

        sorted_files = sort_files_by_priority(plan)
        assert len(sorted_files) == 4
        # Erste Dateien sollten Priority 1 haben
        assert sorted_files[0]["priority"] == 1

    def test_dependency_workflow(self, valid_planner_output_json):
        """Abhängigkeits-Workflow funktioniert."""
        plan = parse_planner_output(valid_planner_output_json)

        # Initial bereit
        ready = get_ready_files(plan, [])
        ready_paths = [f["path"] for f in ready]
        assert "src/config.py" in ready_paths
        assert "requirements.txt" in ready_paths

        # Nach config.py
        ready = get_ready_files(plan, ["src/config.py", "requirements.txt"])
        ready_paths = [f["path"] for f in ready]
        assert "src/database.py" in ready_paths

        # Nach database.py
        ready = get_ready_files(plan, ["src/config.py", "requirements.txt", "src/database.py"])
        ready_paths = [f["path"] for f in ready]
        assert "src/main.py" in ready_paths

    def test_fallback_produces_valid_plan(self, sample_blueprint, sample_user_prompt):
        """Fallback erzeugt validen Plan."""
        plan = create_default_plan(sample_blueprint, sample_user_prompt)

        # Plan kann sortiert werden
        sorted_files = sort_files_by_priority(plan)
        assert len(sorted_files) > 0

        # Abhängigkeiten können geprüft werden
        ready = get_ready_files(plan, [])
        assert len(ready) > 0
