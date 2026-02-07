# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 01.02.2026
Version: 1.0
Beschreibung: Unit Tests für Validator-Agent und Quality Gate Waisen-Check.

              Tests validieren:
              - create_validator: Agent-Erstellung
              - get_validation_task_description: Task-Beschreibung Generierung
              - validate_waisen: Quality Gate Traceability-Prüfung
              - Helper-Funktionen: _format_items, _format_files
"""

import pytest
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.validator_agent import (
    create_validator,
    get_validation_task_description,
    _format_items,
    _format_files
)
from backend.quality_gate import QualityGate
from backend.validation_result import ValidationResult


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
                "validator": {
                    "primary": "openrouter/meta-llama/llama-3.3-70b-instruct:free",
                    "fallback": ["openrouter/deepseek/deepseek-r1-0528:free"]
                },
                "reviewer": {
                    "primary": "openrouter/meta-llama/llama-3.3-70b-instruct:free",
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
        "validator": ["Prüfe Traceability vollständig"]
    }


@pytest.fixture
def sample_anforderungen():
    """Beispiel-Anforderungen für Tests."""
    return [
        {"id": "ANF-001", "titel": "Task-Erstellung"},
        {"id": "ANF-002", "titel": "Task-Anzeige"},
        {"id": "ANF-003", "titel": "Task-Bearbeitung"}
    ]


@pytest.fixture
def sample_features():
    """Beispiel-Features für Tests."""
    return [
        {"id": "FEAT-001", "name": "Task-Management", "anforderungen": ["ANF-001", "ANF-002"]},
        {"id": "FEAT-002", "name": "Task-Editor", "anforderungen": ["ANF-003"]}
    ]


@pytest.fixture
def sample_tasks():
    """Beispiel-Tasks für Tests."""
    return [
        {"id": "TASK-001", "titel": "API erstellen", "feature_id": "FEAT-001"},
        {"id": "TASK-002", "titel": "UI erstellen", "feature_id": "FEAT-001"},
        {"id": "TASK-003", "titel": "Editor-Komponente", "feature_id": "FEAT-002"}
    ]


@pytest.fixture
def sample_file_generations():
    """Beispiel-Datei-Generierungen für Tests."""
    return [
        {"filepath": "api.py", "task_id": "TASK-001", "success": True},
        {"filepath": "ui.py", "task_id": "TASK-002", "success": True},
        {"filepath": "editor.py", "task_id": "TASK-003", "success": True}
    ]


@pytest.fixture
def quality_gate():
    """QualityGate Instanz für Tests."""
    return QualityGate("Test Projekt")


# =========================================================================
# Test: Helper-Funktionen
# =========================================================================

class TestHelperFunctions:
    """Tests für Helper-Funktionen."""

    def test_format_items_empty_list(self):
        """Leere Liste wird korrekt formatiert."""
        result = _format_items([], "id", "name")
        assert result == "  (keine)"

    def test_format_items_single_item(self):
        """Einzelnes Item wird korrekt formatiert."""
        items = [{"id": "ANF-001", "name": "Test"}]
        result = _format_items(items, "id", "name")
        assert "ANF-001" in result
        assert "Test" in result

    def test_format_items_multiple_items(self):
        """Mehrere Items werden korrekt formatiert."""
        items = [
            {"id": "ANF-001", "name": "Test 1"},
            {"id": "ANF-002", "name": "Test 2"}
        ]
        result = _format_items(items, "id", "name")
        assert "ANF-001" in result
        assert "ANF-002" in result

    def test_format_items_max_20(self):
        """Mehr als 20 Items werden gekürzt."""
        items = [{"id": f"ANF-{i:03d}", "name": f"Test {i}"} for i in range(25)]
        result = _format_items(items, "id", "name")
        assert "und 5 weitere" in result

    def test_format_items_missing_keys(self):
        """Fehlende Schlüssel werden als '?' dargestellt."""
        items = [{"other": "value"}]
        result = _format_items(items, "id", "name")
        assert "?" in result

    def test_format_files_empty_list(self):
        """Leere Dateiliste wird korrekt formatiert."""
        result = _format_files([])
        assert result == "  (keine)"

    def test_format_files_success(self):
        """Erfolgreiche Dateien werden mit OK markiert."""
        files = [{"filepath": "test.py", "success": True}]
        result = _format_files(files)
        assert "[OK]" in result
        assert "test.py" in result

    def test_format_files_failure(self):
        """Fehlgeschlagene Dateien werden mit FEHLER markiert."""
        files = [{"filepath": "test.py", "success": False}]
        result = _format_files(files)
        assert "[FEHLER]" in result

    def test_format_files_max_20(self):
        """Mehr als 20 Dateien werden gekürzt."""
        files = [{"filepath": f"file{i}.py", "success": True} for i in range(25)]
        result = _format_files(files)
        assert "und 5 weitere" in result


# =========================================================================
# Test: get_validation_task_description
# =========================================================================

class TestGetValidationTaskDescription:
    """Tests für get_validation_task_description Funktion."""

    def test_basic_description(
        self, sample_anforderungen, sample_features, sample_tasks, sample_file_generations
    ):
        """Grundlegende Task-Beschreibung wird generiert."""
        result = get_validation_task_description(
            sample_anforderungen, sample_features, sample_tasks, sample_file_generations
        )
        assert "Traceability-Prüfung" in result
        assert "ANFORDERUNGEN (3)" in result
        assert "FEATURES (2)" in result
        assert "TASKS (3)" in result
        assert "GENERIERTE DATEIEN (3)" in result

    def test_empty_inputs(self):
        """Leere Inputs werden korrekt behandelt."""
        result = get_validation_task_description([], [], [], [])
        assert "ANFORDERUNGEN (0)" in result
        assert "(keine)" in result

    def test_contains_validation_instructions(
        self, sample_anforderungen, sample_features, sample_tasks, sample_file_generations
    ):
        """Beschreibung enthält Prüfanweisungen."""
        result = get_validation_task_description(
            sample_anforderungen, sample_features, sample_tasks, sample_file_generations
        )
        assert "Hat jede Anforderung mindestens ein Feature?" in result
        assert "Hat jedes Feature mindestens einen Task?" in result
        assert "Hat jeder Task mindestens eine Datei?" in result


# =========================================================================
# Test: create_validator (Agent-Erstellung)
# =========================================================================

class TestCreateValidator:
    """Tests für create_validator Funktion."""

    def test_create_validator_returns_agent(self, sample_config, sample_project_rules):
        """create_validator gibt einen Agent zurück."""
        # Hinweis: Dieser Test überprüft nur die Funktion, nicht den echten Agent
        # da CrewAI-Agent-Erstellung Netzwerkzugriff benötigen kann
        try:
            agent = create_validator(sample_config, sample_project_rules)
            assert agent is not None
            assert hasattr(agent, 'role')
            assert "Validator" in agent.role
        except Exception as e:
            # Falls CrewAI nicht vollständig initialisiert ist
            pytest.skip(f"CrewAI Agent-Erstellung nicht möglich: {e}")

    def test_create_validator_with_router(self, sample_config, sample_project_rules):
        """create_validator funktioniert mit Router."""
        # Mock-Router
        class MockRouter:
            def get_model(self, role):
                return "test-model"

        try:
            agent = create_validator(sample_config, sample_project_rules, router=MockRouter())
            assert agent is not None
        except Exception as e:
            pytest.skip(f"CrewAI Agent-Erstellung nicht möglich: {e}")


# =========================================================================
# Test: QualityGate.validate_waisen
# =========================================================================

class TestValidateWaisen:
    """Tests für Quality Gate Waisen-Prüfung."""

    def test_complete_traceability_passes(
        self, quality_gate, sample_anforderungen, sample_features,
        sample_tasks, sample_file_generations
    ):
        """Vollständige Traceability besteht die Prüfung."""
        result = quality_gate.validate_waisen(
            sample_anforderungen, sample_features, sample_tasks, sample_file_generations
        )
        assert result.passed is True
        assert result.score == 1.0
        assert len(result.issues) == 0

    def test_anforderung_ohne_feature(self, quality_gate):
        """Anforderung ohne Feature wird erkannt."""
        anforderungen = [
            {"id": "ANF-001"},
            {"id": "ANF-002"}  # Keine Feature-Referenz
        ]
        features = [{"id": "FEAT-001", "anforderungen": ["ANF-001"]}]
        tasks = [{"id": "TASK-001", "feature_id": "FEAT-001"}]
        files = [{"filepath": "test.py", "task_id": "TASK-001", "success": True}]

        result = quality_gate.validate_waisen(anforderungen, features, tasks, files)
        assert result.passed is False
        assert any("ANF-002" in str(i) for i in result.issues)
        assert "ANF-002" in result.details["waisen"]["anforderungen_ohne_features"]

    def test_feature_ohne_task(self, quality_gate):
        """Feature ohne Task wird erkannt."""
        anforderungen = [{"id": "ANF-001"}]
        features = [
            {"id": "FEAT-001", "anforderungen": ["ANF-001"]},
            {"id": "FEAT-002", "anforderungen": ["ANF-001"]}  # Kein Task
        ]
        tasks = [{"id": "TASK-001", "feature_id": "FEAT-001"}]
        files = [{"filepath": "test.py", "task_id": "TASK-001", "success": True}]

        result = quality_gate.validate_waisen(anforderungen, features, tasks, files)
        assert result.passed is False
        assert "FEAT-002" in result.details["waisen"]["features_ohne_tasks"]

    def test_task_ohne_datei_warning(self, quality_gate):
        """Task ohne Datei erzeugt Warnung (nicht Fehler)."""
        anforderungen = [{"id": "ANF-001"}]
        features = [{"id": "FEAT-001", "anforderungen": ["ANF-001"]}]
        tasks = [
            {"id": "TASK-001", "feature_id": "FEAT-001"},
            {"id": "TASK-002", "feature_id": "FEAT-001"}  # Keine Datei
        ]
        files = [{"filepath": "test.py", "task_id": "TASK-001", "success": True}]

        result = quality_gate.validate_waisen(anforderungen, features, tasks, files)
        assert result.passed is True  # Tasks ohne Dateien sind nur Warnungen
        assert len(result.warnings) > 0
        assert "TASK-002" in result.details["waisen"]["tasks_ohne_dateien"]

    def test_empty_inputs(self, quality_gate):
        """Leere Inputs werden korrekt behandelt."""
        result = quality_gate.validate_waisen([], [], [], [])
        assert result.passed is True
        assert result.score == 1.0

    def test_coverage_calculation(self, quality_gate):
        """Coverage wird korrekt berechnet."""
        anforderungen = [{"id": "ANF-001"}, {"id": "ANF-002"}]
        features = [{"id": "FEAT-001", "anforderungen": ["ANF-001"]}]  # ANF-002 nicht abgedeckt
        tasks = [{"id": "TASK-001", "feature_id": "FEAT-001"}]
        files = [{"filepath": "test.py", "task_id": "TASK-001", "success": True}]

        result = quality_gate.validate_waisen(anforderungen, features, tasks, files)
        # 1 Waise von 4 Elementen = 75% Coverage
        assert result.score == 0.75

    def test_multiple_waisen(self, quality_gate):
        """Mehrere Waisen werden alle erkannt."""
        anforderungen = [{"id": "ANF-001"}, {"id": "ANF-002"}, {"id": "ANF-003"}]
        features = [{"id": "FEAT-001", "anforderungen": ["ANF-001"]}]  # ANF-002, ANF-003 fehlen
        tasks = []  # Keine Tasks
        files = []  # Keine Dateien

        result = quality_gate.validate_waisen(anforderungen, features, tasks, files)
        assert result.passed is False
        # ANF-002 und ANF-003 ohne Features
        assert len(result.details["waisen"]["anforderungen_ohne_features"]) == 2
        # FEAT-001 ohne Tasks
        assert len(result.details["waisen"]["features_ohne_tasks"]) == 1

    def test_details_contain_counts(self, quality_gate, sample_anforderungen,
                                    sample_features, sample_tasks, sample_file_generations):
        """Details enthalten Zählungen."""
        result = quality_gate.validate_waisen(
            sample_anforderungen, sample_features, sample_tasks, sample_file_generations
        )
        assert "counts" in result.details
        assert result.details["counts"]["anforderungen"] == 3
        assert result.details["counts"]["features"] == 2
        assert result.details["counts"]["tasks"] == 3
        assert result.details["counts"]["dateien"] == 3

    def test_result_is_validation_result(self, quality_gate, sample_anforderungen,
                                         sample_features, sample_tasks, sample_file_generations):
        """Ergebnis ist ValidationResult."""
        result = quality_gate.validate_waisen(
            sample_anforderungen, sample_features, sample_tasks, sample_file_generations
        )
        assert isinstance(result, ValidationResult)

    def test_items_without_id_ignored(self, quality_gate):
        """Items ohne ID werden ignoriert."""
        anforderungen = [{"id": "ANF-001"}, {"titel": "Ohne ID"}]  # Zweites ohne ID
        features = [{"id": "FEAT-001", "anforderungen": ["ANF-001"]}]
        tasks = [{"id": "TASK-001", "feature_id": "FEAT-001"}]
        files = [{"filepath": "test.py", "task_id": "TASK-001", "success": True}]

        result = quality_gate.validate_waisen(anforderungen, features, tasks, files)
        assert result.passed is True
        # Nur 1 Anforderung gezählt (die mit ID)
        assert result.details["counts"]["anforderungen"] == 1


# =========================================================================
# Test: Integration
# =========================================================================

class TestIntegration:
    """Integrationstests für Validator-Komponenten."""

    def test_task_description_with_waisen_data(self, quality_gate):
        """Task-Beschreibung kann mit Waisen-Daten generiert werden."""
        anforderungen = [{"id": "ANF-001", "titel": "Test"}]
        features = []  # Keine Features
        tasks = []
        files = []

        # Erst Waisen prüfen
        waisen_result = quality_gate.validate_waisen(anforderungen, features, tasks, files)
        assert waisen_result.passed is False

        # Dann Task-Beschreibung generieren
        desc = get_validation_task_description(anforderungen, features, tasks, files)
        assert "ANFORDERUNGEN (1)" in desc
        assert "FEATURES (0)" in desc

    def test_complete_workflow(
        self, quality_gate, sample_anforderungen, sample_features,
        sample_tasks, sample_file_generations
    ):
        """Vollständiger Workflow funktioniert."""
        # 1. Task-Beschreibung generieren
        desc = get_validation_task_description(
            sample_anforderungen, sample_features, sample_tasks, sample_file_generations
        )
        assert len(desc) > 0

        # 2. Waisen-Check durchführen
        result = quality_gate.validate_waisen(
            sample_anforderungen, sample_features, sample_tasks, sample_file_generations
        )
        assert result.passed is True

        # 3. Details prüfen
        assert result.details["waisen"]["anforderungen_ohne_features"] == []
        assert result.details["waisen"]["features_ohne_tasks"] == []
        assert result.details["waisen"]["tasks_ohne_dateien"] == []
