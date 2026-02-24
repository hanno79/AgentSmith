# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 14.02.2026
Version: 1.0
Beschreibung: Tests fuer agents/memory_features.py - Feature-Derivation und Session Recording.
              Testet record_feature_derivation, record_file_by_file_session,
              record_task_derivation und interne Hilfsfunktionen.
"""

import os
import sys
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime

# Fuege Projekt-Root zum Python-Path hinzu
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.memory_features import (
    record_feature_derivation,
    record_file_by_file_session,
    record_task_derivation,
    _create_traceability_sample,
    _learn_from_feature_patterns,
    _record_file_generation_failure,
    _learn_from_task_patterns,
    _add_or_update_lesson,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_memory_data():
    """Erstellt leere Memory-Daten fuer Tests."""
    return {"history": [], "lessons": []}


@pytest.fixture
def sample_anforderungen():
    """Beispiel-Anforderungen fuer Feature-Derivation."""
    return [
        {"id": "REQ-001", "title": "Login Seite"},
        {"id": "REQ-002", "title": "Dashboard"},
    ]


@pytest.fixture
def sample_features():
    """Beispiel-Features fuer Feature-Derivation."""
    return [
        {"id": "FEAT-001", "title": "Auth System", "anforderungen": ["REQ-001"], "technologie": "javascript"},
        {"id": "FEAT-002", "title": "Dashboard UI", "anforderungen": ["REQ-002"], "technologie": "javascript"},
        {"id": "FEAT-003", "title": "API Routes", "anforderungen": ["REQ-001", "REQ-002"], "technologie": "javascript"},
    ]


@pytest.fixture
def sample_tasks():
    """Beispiel-Tasks fuer Feature-Derivation."""
    return [
        {"id": "TASK-001", "title": "Login Formular", "features": ["FEAT-001"]},
        {"id": "TASK-002", "title": "Dashboard Layout", "features": ["FEAT-002"]},
        {"id": "TASK-003", "title": "Auth API", "features": ["FEAT-001"]},
        {"id": "TASK-004", "title": "Dashboard API", "features": ["FEAT-002", "FEAT-003"]},
    ]


# ============================================================================
# Tests fuer _create_traceability_sample
# ============================================================================


class TestCreateTraceabilitySample:
    """Tests fuer die _create_traceability_sample Funktion."""

    def test_basic_mapping(self, sample_anforderungen, sample_features, sample_tasks):
        """Test: Grundlegende REQ->FEAT und FEAT->TASK Zuordnung."""
        result = _create_traceability_sample(sample_anforderungen, sample_features, sample_tasks)

        assert "req_to_feat" in result
        assert "feat_to_task" in result

    def test_req_to_feat_mapping(self, sample_anforderungen, sample_features, sample_tasks):
        """Test: REQ-zu-FEAT Zuordnung ist korrekt."""
        result = _create_traceability_sample(sample_anforderungen, sample_features, sample_tasks)

        # REQ-001 soll zu FEAT-001 und FEAT-003 gehoeren
        assert "REQ-001" in result["req_to_feat"]
        assert "FEAT-001" in result["req_to_feat"]["REQ-001"]

    def test_feat_to_task_mapping(self, sample_anforderungen, sample_features, sample_tasks):
        """Test: FEAT-zu-TASK Zuordnung ist korrekt."""
        result = _create_traceability_sample(sample_anforderungen, sample_features, sample_tasks)

        # FEAT-001 soll zu TASK-001 und TASK-003 gehoeren
        assert "FEAT-001" in result["feat_to_task"]
        assert "TASK-001" in result["feat_to_task"]["FEAT-001"]

    def test_max_five_features_sampled(self):
        """Test: Nur die ersten 5 Features werden gesampelt."""
        features = [
            {"id": f"FEAT-{i:03d}", "anforderungen": ["REQ-001"]}
            for i in range(10)
        ]
        result = _create_traceability_sample([], features, [])

        # Maximal 5 Features werden verarbeitet
        total_feat_ids = []
        for feat_list in result["req_to_feat"].values():
            total_feat_ids.extend(feat_list)
        # Alle gesammelten FEAT-IDs sollten aus den ersten 5 stammen
        for fid in total_feat_ids:
            idx = int(fid.split("-")[1])
            assert idx < 5

    def test_max_five_tasks_sampled(self):
        """Test: Nur die ersten 5 Tasks werden gesampelt."""
        tasks = [
            {"id": f"TASK-{i:03d}", "features": ["FEAT-001"]}
            for i in range(10)
        ]
        result = _create_traceability_sample([], [], tasks)

        if "FEAT-001" in result["feat_to_task"]:
            task_ids = result["feat_to_task"]["FEAT-001"]
            for tid in task_ids:
                idx = int(tid.split("-")[1])
                assert idx < 5

    def test_empty_inputs(self):
        """Test: Leere Eingaben erzeugen leere Mappings."""
        result = _create_traceability_sample([], [], [])

        assert result["req_to_feat"] == {}
        assert result["feat_to_task"] == {}

    def test_feature_without_anforderungen(self):
        """Test: Features ohne anforderungen Key werden uebersprungen."""
        features = [{"id": "FEAT-001"}]  # Kein 'anforderungen' Key
        result = _create_traceability_sample([], features, [])

        assert result["req_to_feat"] == {}

    def test_task_without_features(self):
        """Test: Tasks ohne features Key werden uebersprungen."""
        tasks = [{"id": "TASK-001"}]  # Kein 'features' Key
        result = _create_traceability_sample([], [], tasks)

        assert result["feat_to_task"] == {}

    def test_missing_id_uses_fallback(self):
        """Test: Fehlende ID nutzt Fallback-Wert."""
        features = [{"anforderungen": ["REQ-001"]}]  # Kein 'id' Key
        result = _create_traceability_sample([], features, [])

        assert "REQ-001" in result["req_to_feat"]
        assert "FEAT-???" in result["req_to_feat"]["REQ-001"]


# ============================================================================
# Tests fuer _learn_from_feature_patterns
# ============================================================================


class TestLearnFromFeaturePatterns:
    """Tests fuer die _learn_from_feature_patterns Funktion."""

    def test_learns_dominant_technology(self, mock_memory_data):
        """Test: Dominante Technologie wird erkannt (>70%)."""
        features = [
            {"technologie": "javascript"},
            {"technologie": "javascript"},
            {"technologie": "javascript"},
            {"technologie": "python"},
        ]
        _learn_from_feature_patterns(mock_memory_data, features)

        # 75% JavaScript - sollte als Lesson gelernt werden
        assert len(mock_memory_data["lessons"]) == 1
        assert "javascript" in mock_memory_data["lessons"][0]["pattern"]

    def test_no_lesson_below_threshold(self, mock_memory_data):
        """Test: Keine Lesson wenn keine Technologie >70% hat."""
        features = [
            {"technologie": "javascript"},
            {"technologie": "python"},
            {"technologie": "java"},
        ]
        _learn_from_feature_patterns(mock_memory_data, features)

        # 33% pro Technologie - keine dominante
        assert len(mock_memory_data["lessons"]) == 0

    def test_does_not_duplicate_pattern(self, mock_memory_data):
        """Test: Gleiches Pattern wird nicht doppelt hinzugefuegt."""
        mock_memory_data["lessons"] = [
            {"pattern": "project_tech_javascript", "count": 1}
        ]

        features = [
            {"technologie": "javascript"},
            {"technologie": "javascript"},
            {"technologie": "javascript"},
        ]
        _learn_from_feature_patterns(mock_memory_data, features)

        # Sollte immer noch nur eine Lesson geben
        assert len(mock_memory_data["lessons"]) == 1

    def test_handles_missing_technologie(self, mock_memory_data):
        """Test: Features ohne 'technologie' Key werden als 'unknown' behandelt."""
        features = [
            {},
            {},
            {},
        ]
        _learn_from_feature_patterns(mock_memory_data, features)

        # 100% unknown - sollte als Lesson gelernt werden
        assert len(mock_memory_data["lessons"]) == 1
        assert "unknown" in mock_memory_data["lessons"][0]["pattern"]

    def test_creates_lessons_key_if_missing(self):
        """Test: 'lessons' Key wird erstellt wenn nicht vorhanden."""
        memory_data = {"history": []}
        features = [
            {"technologie": "python"},
            {"technologie": "python"},
            {"technologie": "python"},
        ]
        _learn_from_feature_patterns(memory_data, features)

        assert "lessons" in memory_data


# ============================================================================
# Tests fuer _record_file_generation_failure
# ============================================================================


class TestRecordFileGenerationFailure:
    """Tests fuer die _record_file_generation_failure Funktion."""

    def test_new_failure_creates_lesson(self, mock_memory_data):
        """Test: Neuer Fehler erstellt eine Lesson."""
        _record_file_generation_failure(mock_memory_data, "app/page.js")

        assert len(mock_memory_data["lessons"]) == 1
        assert mock_memory_data["lessons"][0]["pattern"] == "file_generation_failed_js"
        assert mock_memory_data["lessons"][0]["count"] == 1

    def test_existing_failure_increments_count(self, mock_memory_data):
        """Test: Bekannter Fehler erhoeht den Zaehler."""
        mock_memory_data["lessons"] = [
            {"pattern": "file_generation_failed_js", "count": 2,
             "last_seen": "2026-01-01 00:00:00"}
        ]
        _record_file_generation_failure(mock_memory_data, "components/Button.js")

        assert mock_memory_data["lessons"][0]["count"] == 3

    def test_different_extensions_create_separate_lessons(self, mock_memory_data):
        """Test: Verschiedene Dateiendungen erzeugen separate Lessons."""
        _record_file_generation_failure(mock_memory_data, "app.py")
        _record_file_generation_failure(mock_memory_data, "app.js")

        assert len(mock_memory_data["lessons"]) == 2
        patterns = {l["pattern"] for l in mock_memory_data["lessons"]}
        assert "file_generation_failed_py" in patterns
        assert "file_generation_failed_js" in patterns

    def test_file_without_extension(self, mock_memory_data):
        """Test: Datei ohne Extension verwendet '.noext'."""
        _record_file_generation_failure(mock_memory_data, "Dockerfile")

        assert mock_memory_data["lessons"][0]["pattern"] == "file_generation_failed_noext"

    def test_creates_lessons_key_if_missing(self):
        """Test: 'lessons' Key wird erstellt wenn nicht vorhanden."""
        memory_data = {"history": []}
        _record_file_generation_failure(memory_data, "test.py")

        assert "lessons" in memory_data
        assert len(memory_data["lessons"]) == 1

    def test_lesson_has_correct_structure(self, mock_memory_data):
        """Test: Lesson hat alle erwarteten Felder."""
        _record_file_generation_failure(mock_memory_data, "app.tsx")

        lesson = mock_memory_data["lessons"][0]
        assert "pattern" in lesson
        assert "category" in lesson
        assert "action" in lesson
        assert "tags" in lesson
        assert "count" in lesson
        assert "first_seen" in lesson
        assert "last_seen" in lesson
        assert lesson["category"] == "file_generation"

    def test_action_text_mentions_extension(self, mock_memory_data):
        """Test: Aktionstext erwaehnt die Dateiendung."""
        _record_file_generation_failure(mock_memory_data, "layout.css")

        assert ".css" in mock_memory_data["lessons"][0]["action"]


# ============================================================================
# Tests fuer record_feature_derivation
# ============================================================================


class TestRecordFeatureDerivation:
    """Tests fuer die record_feature_derivation Funktion."""

    @patch("agents.memory_features.save_memory")
    @patch("agents.memory_features.load_memory")
    def test_successful_derivation(self, mock_load, mock_save,
                                   sample_anforderungen, sample_features, sample_tasks):
        """Test: Erfolgreiche Feature-Derivation wird korrekt gespeichert."""
        mock_load.return_value = {"history": [], "lessons": []}

        result = record_feature_derivation(
            "test_memory.json",
            sample_anforderungen,
            sample_features,
            sample_tasks,
            success=True
        )

        assert "Feature-Derivation gespeichert" in result
        assert "2 REQs" in result
        assert "3 FEATs" in result
        assert "4 TASKs" in result

        # Sicherstellen dass save_memory aufgerufen wurde
        mock_save.assert_called_once()

    @patch("agents.memory_features.save_memory")
    @patch("agents.memory_features.load_memory")
    def test_failed_derivation(self, mock_load, mock_save,
                                sample_anforderungen, sample_features, sample_tasks):
        """Test: Fehlgeschlagene Derivation wird gespeichert ohne Lern-Patterns."""
        mock_load.return_value = {"history": [], "lessons": []}

        result = record_feature_derivation(
            "test_memory.json",
            sample_anforderungen,
            sample_features,
            sample_tasks,
            success=False
        )

        assert "Feature-Derivation gespeichert" in result

        # Bei Fehler sollten keine Patterns gelernt werden
        saved_data = mock_save.call_args[0][1]
        assert len(saved_data["lessons"]) == 0

    @patch("agents.memory_features.save_memory")
    @patch("agents.memory_features.load_memory")
    def test_statistics_calculation(self, mock_load, mock_save,
                                    sample_anforderungen, sample_features, sample_tasks):
        """Test: Statistiken werden korrekt berechnet."""
        mock_load.return_value = {"history": [], "lessons": []}

        record_feature_derivation(
            "test_memory.json",
            sample_anforderungen,
            sample_features,
            sample_tasks,
            success=True
        )

        saved_data = mock_save.call_args[0][1]
        entry = saved_data["history"][0]
        stats = entry["statistics"]

        assert stats["anforderungen_count"] == 2
        assert stats["features_count"] == 3
        assert stats["tasks_count"] == 4
        assert stats["avg_features_per_req"] == 1.5  # 3 Features / 2 REQs
        assert stats["avg_tasks_per_feature"] == pytest.approx(4 / 3)

    @patch("agents.memory_features.save_memory")
    @patch("agents.memory_features.load_memory")
    def test_empty_anforderungen_avoids_division_by_zero(self, mock_load, mock_save):
        """Test: Leere Anforderungen fuehren nicht zu Division durch Null."""
        mock_load.return_value = {"history": [], "lessons": []}

        result = record_feature_derivation(
            "test_memory.json", [], [], [], success=True
        )

        assert "Feature-Derivation gespeichert" in result

    @patch("agents.memory_features.load_memory", side_effect=Exception("Testfehler"))
    def test_error_handling(self, mock_load):
        """Test: Fehler werden abgefangen und als Nachricht zurueckgegeben."""
        result = record_feature_derivation(
            "test_memory.json", [], [], [], success=True
        )

        assert "Fehler" in result


# ============================================================================
# Tests fuer record_file_by_file_session
# ============================================================================


class TestRecordFileByFileSession:
    """Tests fuer die record_file_by_file_session Funktion."""

    @patch("agents.memory_features.save_memory")
    @patch("agents.memory_features.load_memory")
    def test_successful_session(self, mock_load, mock_save):
        """Test: Erfolgreiche Session wird korrekt gespeichert."""
        mock_load.return_value = {"history": [], "lessons": []}
        plan = {"files": [{"path": "a.js"}, {"path": "b.js"}, {"path": "c.js"}]}

        result = record_file_by_file_session(
            "test_memory.json",
            plan,
            created_files=["a.js", "b.js"],
            failed_files=["c.js"],
            success=False
        )

        assert "File-by-File Session gespeichert" in result
        assert "2/3 erfolgreich" in result

    @patch("agents.memory_features.save_memory")
    @patch("agents.memory_features.load_memory")
    def test_success_rate_calculation(self, mock_load, mock_save):
        """Test: Erfolgsrate wird korrekt berechnet."""
        mock_load.return_value = {"history": [], "lessons": []}
        plan = {"files": [{"path": f"file_{i}.py"} for i in range(10)]}

        record_file_by_file_session(
            "test_memory.json",
            plan,
            created_files=[f"file_{i}.py" for i in range(7)],
            failed_files=[f"file_{i}.py" for i in range(7, 10)],
            success=False
        )

        saved_data = mock_save.call_args[0][1]
        stats = saved_data["history"][0]["statistics"]
        assert stats["success_rate"] == 0.7

    @patch("agents.memory_features.save_memory")
    @patch("agents.memory_features.load_memory")
    def test_empty_plan_avoids_division_by_zero(self, mock_load, mock_save):
        """Test: Leerer Plan fuehrt nicht zu Division durch Null."""
        mock_load.return_value = {"history": [], "lessons": []}
        plan = {"files": []}

        result = record_file_by_file_session(
            "test_memory.json", plan, [], [], success=True
        )

        assert "File-by-File Session gespeichert" in result

    @patch("agents.memory_features.save_memory")
    @patch("agents.memory_features.load_memory")
    def test_failed_files_trigger_learning(self, mock_load, mock_save):
        """Test: Fehlgeschlagene Dateien loesen Lern-Prozess aus."""
        mock_load.return_value = {"history": [], "lessons": []}
        plan = {"files": [{"path": "a.py"}, {"path": "b.js"}]}

        record_file_by_file_session(
            "test_memory.json",
            plan,
            created_files=[],
            failed_files=["a.py", "b.js"],
            success=False
        )

        saved_data = mock_save.call_args[0][1]
        # Lessons fuer fehlgeschlagene Dateien sollten erstellt worden sein
        assert len(saved_data["lessons"]) >= 1

    @patch("agents.memory_features.save_memory")
    @patch("agents.memory_features.load_memory")
    def test_max_created_files_stored(self, mock_load, mock_save):
        """Test: Maximal 10 erstellte Dateien werden gespeichert."""
        mock_load.return_value = {"history": [], "lessons": []}
        plan = {"files": [{"path": f"f{i}.py"} for i in range(20)]}

        record_file_by_file_session(
            "test_memory.json",
            plan,
            created_files=[f"f{i}.py" for i in range(20)],
            failed_files=[],
            success=True
        )

        saved_data = mock_save.call_args[0][1]
        assert len(saved_data["history"][0]["created"]) == 10

    @patch("agents.memory_features.save_memory")
    @patch("agents.memory_features.load_memory")
    def test_max_failed_files_stored(self, mock_load, mock_save):
        """Test: Maximal 5 fehlgeschlagene Dateien werden gespeichert."""
        mock_load.return_value = {"history": [], "lessons": []}
        plan = {"files": [{"path": f"f{i}.py"} for i in range(10)]}

        record_file_by_file_session(
            "test_memory.json",
            plan,
            created_files=[],
            failed_files=[f"f{i}.py" for i in range(10)],
            success=False
        )

        saved_data = mock_save.call_args[0][1]
        assert len(saved_data["history"][0]["failed"]) == 5

    @patch("agents.memory_features.load_memory", side_effect=Exception("Testfehler"))
    def test_error_handling(self, mock_load):
        """Test: Fehler werden abgefangen und als Nachricht zurueckgegeben."""
        result = record_file_by_file_session(
            "test_memory.json", {"files": []}, [], [], success=True
        )

        assert "Fehler" in result


# ============================================================================
# Tests fuer record_task_derivation
# ============================================================================


class TestRecordTaskDerivation:
    """Tests fuer die record_task_derivation Funktion."""

    @patch("agents.memory_features.save_memory")
    @patch("agents.memory_features.load_memory")
    def test_successful_task_derivation(self, mock_load, mock_save):
        """Test: Erfolgreiche Task-Derivation wird korrekt gespeichert."""
        mock_load.return_value = {"history": [], "lessons": []}
        derivation_result = {
            "source": "planner",
            "total_tasks": 5,
            "tasks_by_category": {"code": 3, "test": 2},
            "tasks_by_priority": {"high": 2, "medium": 3},
            "tasks_by_agent": {"coder": 3, "tester": 2},
            "derivation_time_seconds": 12.5,
            "tasks": [
                {"id": "T-001", "title": "Implementiere Login", "category": "code", "priority": "high", "target_agent": "coder"},
                {"id": "T-002", "title": "Teste Login", "category": "test", "priority": "medium", "target_agent": "tester"},
            ]
        }

        result = record_task_derivation("test_memory.json", derivation_result, success=True)

        assert "Task-Derivation gespeichert" in result
        assert "5 Tasks" in result
        assert "planner" in result

    @patch("agents.memory_features.save_memory")
    @patch("agents.memory_features.load_memory")
    def test_sample_tasks_limited_to_three(self, mock_load, mock_save):
        """Test: Maximal 3 Sample-Tasks werden gespeichert."""
        mock_load.return_value = {"history": [], "lessons": []}
        tasks = [
            {"id": f"T-{i:03d}", "title": f"Task {i}", "category": "code",
             "priority": "medium", "target_agent": "coder"}
            for i in range(10)
        ]
        derivation_result = {
            "source": "utds", "total_tasks": 10, "tasks": tasks,
            "tasks_by_category": {}, "tasks_by_priority": {}, "tasks_by_agent": {},
        }

        record_task_derivation("test_memory.json", derivation_result)

        saved_data = mock_save.call_args[0][1]
        entry = saved_data["history"][0]
        assert len(entry["sample_tasks"]) == 3

    @patch("agents.memory_features.save_memory")
    @patch("agents.memory_features.load_memory")
    def test_task_title_truncated(self, mock_load, mock_save):
        """Test: Task-Titel werden auf 50 Zeichen gekuerzt."""
        mock_load.return_value = {"history": [], "lessons": []}
        derivation_result = {
            "source": "planner", "total_tasks": 1,
            "tasks": [{"id": "T-001", "title": "A" * 100, "category": "code",
                       "priority": "high", "target_agent": "coder"}],
            "tasks_by_category": {}, "tasks_by_priority": {}, "tasks_by_agent": {},
        }

        record_task_derivation("test_memory.json", derivation_result)

        saved_data = mock_save.call_args[0][1]
        sample = saved_data["history"][0]["sample_tasks"][0]
        assert len(sample["title"]) == 50

    @patch("agents.memory_features.load_memory", side_effect=Exception("Testfehler"))
    def test_error_handling(self, mock_load):
        """Test: Fehler werden abgefangen."""
        result = record_task_derivation("test.json", {"tasks": []})
        assert "Fehler" in result


# ============================================================================
# Tests fuer _learn_from_task_patterns
# ============================================================================


class TestLearnFromTaskPatterns:
    """Tests fuer die _learn_from_task_patterns Funktion."""

    def test_learns_dominant_category(self, mock_memory_data):
        """Test: Dominante Kategorie (>=70%) wird als Lesson gespeichert."""
        tasks = [
            {"category": "code", "priority": "medium", "target_agent": "coder"},
            {"category": "code", "priority": "medium", "target_agent": "coder"},
            {"category": "code", "priority": "medium", "target_agent": "coder"},
            {"category": "test", "priority": "medium", "target_agent": "tester"},
        ]
        _learn_from_task_patterns(mock_memory_data, tasks)

        # 75% code-Tasks - sollte Lesson erzeugen
        patterns = [l["pattern"] for l in mock_memory_data["lessons"]]
        assert any("dominant_code" in p for p in patterns)

    def test_learns_many_critical_tasks(self, mock_memory_data):
        """Test: Viele kritische Tasks werden erkannt."""
        tasks = [
            {"category": "code", "priority": "critical", "target_agent": "coder"},
            {"category": "code", "priority": "critical", "target_agent": "coder"},
            {"category": "code", "priority": "medium", "target_agent": "coder"},
        ]
        _learn_from_task_patterns(mock_memory_data, tasks)

        patterns = [l["pattern"] for l in mock_memory_data["lessons"]]
        assert any("many_critical" in p for p in patterns)

    def test_skips_with_less_than_two_tasks(self, mock_memory_data):
        """Test: Weniger als 2 Tasks erzeugt keine Lessons."""
        tasks = [
            {"category": "code", "priority": "critical", "target_agent": "coder"},
        ]
        _learn_from_task_patterns(mock_memory_data, tasks)

        assert len(mock_memory_data["lessons"]) == 0

    def test_skips_empty_tasks(self, mock_memory_data):
        """Test: Leere Task-Liste erzeugt keine Lessons."""
        _learn_from_task_patterns(mock_memory_data, [])

        assert len(mock_memory_data["lessons"]) == 0

    def test_handles_missing_keys(self, mock_memory_data):
        """Test: Tasks ohne category/priority/target_agent werden als 'unknown' behandelt."""
        tasks = [{}, {}, {}]
        _learn_from_task_patterns(mock_memory_data, tasks)

        # 100% unknown - sollte dominant sein
        patterns = [l["pattern"] for l in mock_memory_data["lessons"]]
        assert any("unknown" in p for p in patterns)


# ============================================================================
# Tests fuer _add_or_update_lesson
# ============================================================================


class TestAddOrUpdateLesson:
    """Tests fuer die _add_or_update_lesson Funktion."""

    def test_adds_new_lesson(self, mock_memory_data):
        """Test: Neue Lesson wird hinzugefuegt."""
        _add_or_update_lesson(
            mock_memory_data,
            pattern="test_pattern",
            category="test",
            action="Testaktionstext",
            tags=["global"]
        )

        assert len(mock_memory_data["lessons"]) == 1
        assert mock_memory_data["lessons"][0]["pattern"] == "test_pattern"
        assert mock_memory_data["lessons"][0]["count"] == 1

    def test_updates_existing_lesson(self, mock_memory_data):
        """Test: Existierende Lesson wird aktualisiert (count + last_seen)."""
        mock_memory_data["lessons"] = [
            {"pattern": "test_pattern", "count": 3,
             "last_seen": "2026-01-01 00:00:00"}
        ]

        _add_or_update_lesson(
            mock_memory_data,
            pattern="test_pattern",
            category="test",
            action="Neuer Text",
            tags=["global"]
        )

        assert len(mock_memory_data["lessons"]) == 1
        assert mock_memory_data["lessons"][0]["count"] == 4
        # last_seen sollte aktualisiert worden sein
        assert mock_memory_data["lessons"][0]["last_seen"] != "2026-01-01 00:00:00"

    def test_creates_lessons_key_if_missing(self):
        """Test: 'lessons' Key wird erstellt wenn nicht vorhanden."""
        memory_data = {"history": []}

        _add_or_update_lesson(
            memory_data,
            pattern="test_pattern",
            category="test",
            action="Test",
            tags=[]
        )

        assert "lessons" in memory_data
        assert len(memory_data["lessons"]) == 1
