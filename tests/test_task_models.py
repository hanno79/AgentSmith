# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 14.02.2026
Version: 1.0
Beschreibung: Tests fuer backend/task_models.py
              Testet DerivedTask, TaskBatch, BatchResult, TaskDerivationResult,
              Enums, Serialisierung und Hilfsfunktionen.
"""

import os
import sys
import pytest
from datetime import datetime

# Projekt-Root zum Python-Path hinzufuegen
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.task_models import (
    TaskCategory, TaskPriority, TaskStatus, TargetAgent,
    DerivedTask, TaskBatch, BatchResult, TaskDerivationResult,
    priority_to_int, sort_tasks_by_priority, filter_ready_tasks,
)


# =========================================================================
# Enum-Tests
# =========================================================================

class TestTaskCategory:
    """Tests fuer TaskCategory Enum."""

    def test_alle_werte(self):
        """Alle erwarteten Kategorien existieren."""
        assert TaskCategory.CODE.value == "code"
        assert TaskCategory.TEST.value == "test"
        assert TaskCategory.SECURITY.value == "security"
        assert TaskCategory.DOCS.value == "docs"
        assert TaskCategory.CONFIG.value == "config"
        assert TaskCategory.REFACTOR.value == "refactor"


class TestTaskPriority:
    """Tests fuer TaskPriority Enum."""

    def test_alle_werte(self):
        """Alle erwarteten Prioritaeten existieren."""
        assert TaskPriority.CRITICAL.value == "critical"
        assert TaskPriority.HIGH.value == "high"
        assert TaskPriority.MEDIUM.value == "medium"
        assert TaskPriority.LOW.value == "low"


class TestTaskStatus:
    """Tests fuer TaskStatus Enum."""

    def test_alle_werte(self):
        """Alle erwarteten Status existieren."""
        assert TaskStatus.PENDING.value == "pending"
        assert TaskStatus.IN_PROGRESS.value == "in_progress"
        assert TaskStatus.COMPLETED.value == "completed"
        assert TaskStatus.FAILED.value == "failed"
        assert TaskStatus.BLOCKED.value == "blocked"
        assert TaskStatus.SKIPPED.value == "skipped"


class TestTargetAgent:
    """Tests fuer TargetAgent Enum."""

    def test_alle_werte(self):
        """Alle erwarteten Ziel-Agenten existieren."""
        assert TargetAgent.CODER.value == "coder"
        assert TargetAgent.TESTER.value == "tester"
        assert TargetAgent.SECURITY.value == "security"
        assert TargetAgent.FIX.value == "fix"


# =========================================================================
# DerivedTask Tests
# =========================================================================

class TestDerivedTask:
    """Tests fuer DerivedTask Dataclass."""

    def _create_task(self, **kwargs):
        """Hilfs-Methode: Erstellt DerivedTask mit Defaults."""
        defaults = {
            "id": "TASK-001",
            "title": "Test Task",
            "description": "Beschreibung",
            "category": TaskCategory.CODE,
            "priority": TaskPriority.MEDIUM,
            "target_agent": TargetAgent.CODER,
        }
        defaults.update(kwargs)
        return DerivedTask(**defaults)

    def test_erstellung_mit_defaults(self):
        """Task wird mit Default-Werten erstellt."""
        task = self._create_task()
        assert task.id == "TASK-001"
        assert task.status == TaskStatus.PENDING
        assert task.affected_files == []
        assert task.dependencies == []
        assert task.retry_count == 0
        assert task.max_retries == 2
        assert task.timeout_seconds == 120

    def test_to_dict(self):
        """to_dict() liefert korrektes Dictionary."""
        task = self._create_task(affected_files=["a.py"], dependencies=["TASK-000"])
        d = task.to_dict()
        assert d["id"] == "TASK-001"
        assert d["category"] == "code"
        assert d["priority"] == "medium"
        assert d["target_agent"] == "coder"
        assert d["status"] == "pending"
        assert d["affected_files"] == ["a.py"]
        assert d["dependencies"] == ["TASK-000"]
        assert d["created_at"] is not None

    def test_from_dict(self):
        """from_dict() rekonstruiert Task korrekt."""
        task = self._create_task()
        d = task.to_dict()
        restored = DerivedTask.from_dict(d)
        assert restored.id == task.id
        assert restored.title == task.title
        assert restored.category == task.category
        assert restored.priority == task.priority
        assert restored.target_agent == task.target_agent
        assert restored.status == task.status

    def test_roundtrip_serialization(self):
        """to_dict() → from_dict() Roundtrip erhaelt alle Felder."""
        task = self._create_task(
            affected_files=["a.py", "b.py"],
            dependencies=["TASK-000"],
            source_issue="Review sagt...",
            source_type="reviewer",
            result="Fertig",
            retry_count=1,
        )
        d = task.to_dict()
        restored = DerivedTask.from_dict(d)
        assert restored.affected_files == ["a.py", "b.py"]
        assert restored.dependencies == ["TASK-000"]
        assert restored.source_issue == "Review sagt..."
        assert restored.result == "Fertig"
        assert restored.retry_count == 1

    def test_is_ready_ohne_deps(self):
        """Task ohne Dependencies ist immer ready."""
        task = self._create_task(dependencies=[])
        assert task.is_ready([]) is True

    def test_is_ready_mit_erfuellten_deps(self):
        """Task mit erfuellten Dependencies ist ready."""
        task = self._create_task(dependencies=["TASK-000"])
        assert task.is_ready(["TASK-000"]) is True

    def test_is_ready_mit_unerfuellten_deps(self):
        """Task mit unerfuellten Dependencies ist nicht ready."""
        task = self._create_task(dependencies=["TASK-000"])
        assert task.is_ready([]) is False

    def test_can_retry_ja(self):
        """Retry moeglich wenn retry_count < max_retries."""
        task = self._create_task()
        task.retry_count = 0
        assert task.can_retry() is True

    def test_can_retry_nein(self):
        """Retry nicht moeglich wenn max_retries erreicht."""
        task = self._create_task()
        task.retry_count = 2
        assert task.can_retry() is False

    def test_datetime_serialization(self):
        """Datetime-Felder werden als ISO-String serialisiert."""
        task = self._create_task()
        task.started_at = datetime(2026, 2, 14, 10, 0, 0)
        d = task.to_dict()
        assert d["started_at"] == "2026-02-14T10:00:00"


# =========================================================================
# TaskBatch Tests
# =========================================================================

class TestTaskBatch:
    """Tests fuer TaskBatch Dataclass."""

    def _create_task(self, task_id):
        return DerivedTask(
            id=task_id, title=f"Task {task_id}", description="...",
            category=TaskCategory.CODE, priority=TaskPriority.MEDIUM,
            target_agent=TargetAgent.CODER
        )

    def test_erstellung(self):
        """Batch wird korrekt erstellt."""
        batch = TaskBatch(batch_id="BATCH-001")
        assert batch.batch_id == "BATCH-001"
        assert batch.tasks == []
        assert batch.status == TaskStatus.PENDING

    def test_task_count(self):
        """task_count Property zaehlt korrekt."""
        batch = TaskBatch(batch_id="B1", tasks=[self._create_task("T1"), self._create_task("T2")])
        assert batch.task_count == 2

    def test_all_completed_true(self):
        """all_completed ist True wenn alle Tasks fertig."""
        t1 = self._create_task("T1")
        t1.status = TaskStatus.COMPLETED
        t2 = self._create_task("T2")
        t2.status = TaskStatus.COMPLETED
        batch = TaskBatch(batch_id="B1", tasks=[t1, t2])
        assert batch.all_completed is True

    def test_all_completed_false(self):
        """all_completed ist False wenn Tasks offen."""
        t1 = self._create_task("T1")
        t1.status = TaskStatus.COMPLETED
        t2 = self._create_task("T2")
        t2.status = TaskStatus.PENDING
        batch = TaskBatch(batch_id="B1", tasks=[t1, t2])
        assert batch.all_completed is False

    def test_any_failed(self):
        """any_failed erkennt fehlgeschlagene Tasks."""
        t1 = self._create_task("T1")
        t1.status = TaskStatus.FAILED
        batch = TaskBatch(batch_id="B1", tasks=[t1])
        assert batch.any_failed is True

    def test_to_dict(self):
        """to_dict() liefert korrektes Dictionary."""
        batch = TaskBatch(batch_id="B1", tasks=[self._create_task("T1")])
        d = batch.to_dict()
        assert d["batch_id"] == "B1"
        assert len(d["tasks"]) == 1
        assert d["status"] == "pending"


# =========================================================================
# BatchResult Tests
# =========================================================================

class TestBatchResult:
    """Tests fuer BatchResult Dataclass."""

    def test_erstellung(self):
        """BatchResult wird korrekt erstellt."""
        br = BatchResult(batch_id="B1", success=True)
        assert br.success is True
        assert br.completed_tasks == []
        assert br.failed_tasks == []
        assert br.execution_time_seconds == 0.0

    def test_to_dict(self):
        """to_dict() liefert korrektes Dictionary."""
        br = BatchResult(
            batch_id="B1", success=True,
            completed_tasks=["T1", "T2"],
            failed_tasks=["T3"],
            execution_time_seconds=5.5
        )
        d = br.to_dict()
        assert d["success"] is True
        assert len(d["completed_tasks"]) == 2
        assert d["execution_time_seconds"] == 5.5


# =========================================================================
# TaskDerivationResult Tests
# =========================================================================

class TestTaskDerivationResult:
    """Tests fuer TaskDerivationResult Dataclass."""

    def test_erstellung(self):
        """TaskDerivationResult wird korrekt erstellt."""
        tdr = TaskDerivationResult(source="reviewer", source_feedback="Feedback-Text")
        assert tdr.source == "reviewer"
        assert tdr.tasks == []
        assert tdr.batches == []
        assert tdr.total_tasks == 0

    def test_to_dict_truncates_feedback(self):
        """to_dict() kuerzt source_feedback auf 500 Zeichen."""
        long_feedback = "x" * 1000
        tdr = TaskDerivationResult(source="test", source_feedback=long_feedback)
        d = tdr.to_dict()
        assert len(d["source_feedback"]) == 500


# =========================================================================
# Hilfsfunktionen Tests
# =========================================================================

class TestPriorityToInt:
    """Tests fuer priority_to_int()."""

    def test_critical_ist_0(self):
        """CRITICAL hat Wert 0."""
        assert priority_to_int(TaskPriority.CRITICAL) == 0

    def test_high_ist_1(self):
        """HIGH hat Wert 1."""
        assert priority_to_int(TaskPriority.HIGH) == 1

    def test_medium_ist_2(self):
        """MEDIUM hat Wert 2."""
        assert priority_to_int(TaskPriority.MEDIUM) == 2

    def test_low_ist_3(self):
        """LOW hat Wert 3."""
        assert priority_to_int(TaskPriority.LOW) == 3

    def test_reihenfolge_korrekt(self):
        """Prioritaeten sind korrekt geordnet."""
        assert priority_to_int(TaskPriority.CRITICAL) < priority_to_int(TaskPriority.HIGH)
        assert priority_to_int(TaskPriority.HIGH) < priority_to_int(TaskPriority.MEDIUM)
        assert priority_to_int(TaskPriority.MEDIUM) < priority_to_int(TaskPriority.LOW)


class TestSortTasksByPriority:
    """Tests fuer sort_tasks_by_priority()."""

    def _make_task(self, priority):
        return DerivedTask(
            id=f"T-{priority.value}", title="T", description="D",
            category=TaskCategory.CODE, priority=priority,
            target_agent=TargetAgent.CODER
        )

    def test_sortiert_korrekt(self):
        """Tasks werden nach Prioritaet sortiert (Critical zuerst)."""
        tasks = [
            self._make_task(TaskPriority.LOW),
            self._make_task(TaskPriority.CRITICAL),
            self._make_task(TaskPriority.MEDIUM),
        ]
        result = sort_tasks_by_priority(tasks)
        assert result[0].priority == TaskPriority.CRITICAL
        assert result[1].priority == TaskPriority.MEDIUM
        assert result[2].priority == TaskPriority.LOW

    def test_leere_liste(self):
        """Leere Liste gibt leere Liste zurueck."""
        assert sort_tasks_by_priority([]) == []


class TestFilterReadyTasks:
    """Tests fuer filter_ready_tasks()."""

    def _make_task(self, task_id, deps=None, status=TaskStatus.PENDING):
        t = DerivedTask(
            id=task_id, title="T", description="D",
            category=TaskCategory.CODE, priority=TaskPriority.MEDIUM,
            target_agent=TargetAgent.CODER, dependencies=deps or []
        )
        t.status = status
        return t

    def test_ohne_deps_sofort_bereit(self):
        """Tasks ohne Dependencies sind sofort bereit."""
        tasks = [self._make_task("T1"), self._make_task("T2")]
        result = filter_ready_tasks(tasks, [])
        assert len(result) == 2

    def test_mit_erfuellten_deps(self):
        """Tasks mit erfuellten Dependencies sind bereit."""
        tasks = [self._make_task("T2", deps=["T1"])]
        result = filter_ready_tasks(tasks, ["T1"])
        assert len(result) == 1

    def test_mit_unerfuellten_deps(self):
        """Tasks mit unerfuellten Dependencies sind nicht bereit."""
        tasks = [self._make_task("T2", deps=["T1"])]
        result = filter_ready_tasks(tasks, [])
        assert len(result) == 0

    def test_nur_pending_tasks(self):
        """Nur PENDING Tasks werden zurueckgegeben."""
        t1 = self._make_task("T1", status=TaskStatus.COMPLETED)
        t2 = self._make_task("T2", status=TaskStatus.PENDING)
        result = filter_ready_tasks([t1, t2], [])
        assert len(result) == 1
        assert result[0].id == "T2"

    def test_leere_liste(self):
        """Leere Liste gibt leere Liste zurueck."""
        assert filter_ready_tasks([], []) == []
