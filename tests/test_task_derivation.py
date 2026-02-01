"""
Author: rahn
Datum: 01.02.2026
Version: 1.1
Beschreibung: Tests fuer das Universal Task Derivation System (UTDS).
              AENDERUNG 01.02.2026 v1.1: Tests fuer Security/Sandbox Quellen und WebSocket Events
"""

import pytest
import json
import os
from datetime import datetime
from unittest.mock import Mock, MagicMock, patch

from backend.task_models import (
    DerivedTask, TaskBatch, BatchResult, TaskDerivationResult,
    TaskCategory, TaskPriority, TaskStatus, TargetAgent,
    sort_tasks_by_priority, filter_ready_tasks, priority_to_int
)
from backend.task_deriver import TaskDeriver
from backend.task_tracker import TaskTracker
from backend.task_dispatcher import TaskDispatcher
from backend.dart_task_sync import DartTaskSync, MockDartTaskSync


# ============================================================================
# Task Models Tests
# ============================================================================

class TestDerivedTask:
    """Tests fuer DerivedTask Datenmodell."""

    def test_task_creation(self):
        """Testet die Erstellung eines Tasks."""
        task = DerivedTask(
            id="TASK-001",
            title="Test Task",
            description="Test Beschreibung",
            category=TaskCategory.CODE,
            priority=TaskPriority.HIGH,
            target_agent=TargetAgent.CODER,
            affected_files=["app.py"],
            source_issue="Original Issue"
        )
        assert task.id == "TASK-001"
        assert task.title == "Test Task"
        assert task.category == TaskCategory.CODE
        assert task.priority == TaskPriority.HIGH
        assert task.status == TaskStatus.PENDING

    def test_task_to_dict(self):
        """Testet die Serialisierung zu Dictionary."""
        task = DerivedTask(
            id="TASK-002",
            title="Serialisierung Test",
            description="Test",
            category=TaskCategory.TEST,
            priority=TaskPriority.MEDIUM,
            target_agent=TargetAgent.TESTER
        )
        d = task.to_dict()
        assert d["id"] == "TASK-002"
        assert d["category"] == "test"
        assert d["priority"] == "medium"
        assert d["target_agent"] == "tester"

    def test_task_from_dict(self):
        """Testet die Deserialisierung aus Dictionary."""
        data = {
            "id": "TASK-003",
            "title": "From Dict Test",
            "description": "Test",
            "category": "security",
            "priority": "critical",
            "target_agent": "security",
            "affected_files": ["db.py"],
            "dependencies": [],
            "source_issue": "SQL Injection",
            "source_type": "security",
            "status": "pending"
        }
        task = DerivedTask.from_dict(data)
        assert task.id == "TASK-003"
        assert task.category == TaskCategory.SECURITY
        assert task.priority == TaskPriority.CRITICAL

    def test_task_is_ready(self):
        """Testet die Abhaengigkeits-Pruefung."""
        task = DerivedTask(
            id="TASK-004",
            title="Ready Test",
            description="Test",
            category=TaskCategory.CODE,
            priority=TaskPriority.MEDIUM,
            target_agent=TargetAgent.CODER,
            dependencies=["TASK-001", "TASK-002"]
        )
        assert not task.is_ready([])
        assert not task.is_ready(["TASK-001"])
        assert task.is_ready(["TASK-001", "TASK-002"])
        assert task.is_ready(["TASK-001", "TASK-002", "TASK-003"])

    def test_task_can_retry(self):
        """Testet die Retry-Pruefung."""
        task = DerivedTask(
            id="TASK-005",
            title="Retry Test",
            description="Test",
            category=TaskCategory.CODE,
            priority=TaskPriority.MEDIUM,
            target_agent=TargetAgent.CODER,
            max_retries=2
        )
        assert task.can_retry()
        task.retry_count = 1
        assert task.can_retry()
        task.retry_count = 2
        assert not task.can_retry()


class TestTaskSorting:
    """Tests fuer Task-Sortierung."""

    def test_priority_to_int(self):
        """Testet Priority-Konvertierung."""
        assert priority_to_int(TaskPriority.CRITICAL) == 0
        assert priority_to_int(TaskPriority.HIGH) == 1
        assert priority_to_int(TaskPriority.MEDIUM) == 2
        assert priority_to_int(TaskPriority.LOW) == 3

    def test_sort_tasks_by_priority(self):
        """Testet Sortierung nach Prioritaet."""
        tasks = [
            DerivedTask("T1", "Low", "", TaskCategory.CODE, TaskPriority.LOW, TargetAgent.CODER),
            DerivedTask("T2", "Critical", "", TaskCategory.CODE, TaskPriority.CRITICAL, TargetAgent.CODER),
            DerivedTask("T3", "Medium", "", TaskCategory.CODE, TaskPriority.MEDIUM, TargetAgent.CODER),
            DerivedTask("T4", "High", "", TaskCategory.CODE, TaskPriority.HIGH, TargetAgent.CODER),
        ]
        sorted_tasks = sort_tasks_by_priority(tasks)
        assert sorted_tasks[0].priority == TaskPriority.CRITICAL
        assert sorted_tasks[1].priority == TaskPriority.HIGH
        assert sorted_tasks[2].priority == TaskPriority.MEDIUM
        assert sorted_tasks[3].priority == TaskPriority.LOW

    def test_filter_ready_tasks(self):
        """Testet Filterung nach Bereitschaft."""
        tasks = [
            DerivedTask("T1", "No Deps", "", TaskCategory.CODE, TaskPriority.HIGH, TargetAgent.CODER, dependencies=[]),
            DerivedTask("T2", "Dep on T1", "", TaskCategory.CODE, TaskPriority.MEDIUM, TargetAgent.CODER, dependencies=["T1"]),
            DerivedTask("T3", "Dep on T1,T2", "", TaskCategory.CODE, TaskPriority.LOW, TargetAgent.CODER, dependencies=["T1", "T2"]),
        ]
        ready = filter_ready_tasks(tasks, [])
        assert len(ready) == 1
        assert ready[0].id == "T1"

        ready = filter_ready_tasks(tasks, ["T1"])
        # T1 ist schon completed, also nicht mehr pending
        tasks[0].status = TaskStatus.COMPLETED
        ready = filter_ready_tasks(tasks, ["T1"])
        assert len(ready) == 1
        assert ready[0].id == "T2"


# ============================================================================
# Task Deriver Tests
# ============================================================================

class TestTaskDeriver:
    """Tests fuer den Task-Ableiter."""

    def test_derive_with_rules_syntax_error(self):
        """Testet regelbasierte Ableitung bei Syntax-Fehlern."""
        deriver = TaskDeriver()
        feedback = "SyntaxError: invalid syntax in app.py line 42"
        result = deriver.derive_tasks(feedback, "sandbox", {})

        assert result.total_tasks >= 1
        task = result.tasks[0]
        assert task.priority == TaskPriority.CRITICAL
        assert task.category == TaskCategory.CODE

    def test_derive_with_rules_import_error(self):
        """Testet regelbasierte Ableitung bei Import-Fehlern."""
        deriver = TaskDeriver()
        feedback = "ModuleNotFoundError: No module named 'flask'"
        result = deriver.derive_tasks(feedback, "sandbox", {})

        assert result.total_tasks >= 1
        task = result.tasks[0]
        assert task.priority == TaskPriority.CRITICAL

    def test_derive_with_rules_missing_tests(self):
        """Testet regelbasierte Ableitung bei fehlenden Tests."""
        deriver = TaskDeriver()
        feedback = "Keine Unit-Tests vorhanden. Tests fehlen fuer die Hauptfunktionen."
        result = deriver.derive_tasks(feedback, "tester", {})

        assert result.total_tasks >= 1
        task = result.tasks[0]
        assert task.category == TaskCategory.TEST
        assert task.target_agent == TargetAgent.TESTER

    def test_derive_with_rules_security(self):
        """Testet regelbasierte Ableitung bei Security-Issues."""
        deriver = TaskDeriver()
        feedback = "SQL-Injection vulnerability in database.py: unsichere SQL Query"
        result = deriver.derive_tasks(feedback, "security", {})

        assert result.total_tasks >= 1
        task = result.tasks[0]
        assert task.priority == TaskPriority.CRITICAL
        assert task.category == TaskCategory.SECURITY

    def test_derive_multiple_issues(self):
        """Testet Ableitung mehrerer Issues."""
        deriver = TaskDeriver()
        feedback = """
        1. SyntaxError: invalid syntax in app.py
        2. ModuleNotFoundError: No module named 'requests'
        3. TypeError: expected str, got int in utils.py
        """
        result = deriver.derive_tasks(feedback, "sandbox", {})

        assert result.total_tasks >= 3

    def test_derive_fallback_generic(self):
        """Testet Fallback auf generischen Task."""
        deriver = TaskDeriver()
        feedback = "Dies ist generisches Feedback ohne spezifische Patterns aber lang genug."
        result = deriver.derive_tasks(feedback, "reviewer", {})

        assert result.total_tasks == 1
        assert result.tasks[0].source_type == "reviewer"

    def test_statistics_calculation(self):
        """Testet die Statistik-Berechnung."""
        deriver = TaskDeriver()
        feedback = """
        - SyntaxError in app.py
        - Keine Tests vorhanden
        - SQL-Injection in db.py
        """
        result = deriver.derive_tasks(feedback, "sandbox", {})

        assert result.tasks_by_category.get("code", 0) >= 1
        assert result.derivation_time_seconds >= 0


# ============================================================================
# Task Tracker Tests
# ============================================================================

class TestTaskTracker:
    """Tests fuer den Task-Tracker."""

    @pytest.fixture
    def tracker(self, tmp_path):
        """Erstellt Tracker mit temporaerem Verzeichnis."""
        return TaskTracker(log_dir=str(tmp_path))

    def test_log_task(self, tracker):
        """Testet das Loggen eines Tasks."""
        task = DerivedTask(
            id="TASK-001",
            title="Test Task",
            description="Test",
            category=TaskCategory.CODE,
            priority=TaskPriority.HIGH,
            target_agent=TargetAgent.CODER
        )
        task_id = tracker.log_task(task)
        assert task_id == "TASK-001"
        assert tracker.get_task("TASK-001") is not None

    def test_update_status(self, tracker):
        """Testet Status-Updates."""
        task = DerivedTask(
            id="TASK-002",
            title="Status Test",
            description="Test",
            category=TaskCategory.CODE,
            priority=TaskPriority.MEDIUM,
            target_agent=TargetAgent.CODER
        )
        tracker.log_task(task)
        tracker.update_status("TASK-002", TaskStatus.IN_PROGRESS)

        updated = tracker.get_task("TASK-002")
        assert updated.status == TaskStatus.IN_PROGRESS
        assert updated.started_at is not None

    def test_update_status_completed(self, tracker):
        """Testet Abschluss-Status."""
        task = DerivedTask(
            id="TASK-003",
            title="Complete Test",
            description="Test",
            category=TaskCategory.CODE,
            priority=TaskPriority.HIGH,
            target_agent=TargetAgent.CODER
        )
        tracker.log_task(task)
        tracker.update_status(
            "TASK-003",
            TaskStatus.COMPLETED,
            result="Erfolgreich behoben",
            modified_files=["app.py"]
        )

        updated = tracker.get_task("TASK-003")
        assert updated.status == TaskStatus.COMPLETED
        assert updated.result == "Erfolgreich behoben"
        assert "app.py" in updated.modified_files

    def test_get_pending_tasks(self, tracker):
        """Testet Filterung nach Status."""
        for i in range(5):
            task = DerivedTask(
                id=f"TASK-{i:03d}",
                title=f"Task {i}",
                description="Test",
                category=TaskCategory.CODE,
                priority=TaskPriority.MEDIUM,
                target_agent=TargetAgent.CODER
            )
            tracker.log_task(task)

        # 2 Tasks abschliessen
        tracker.update_status("TASK-000", TaskStatus.COMPLETED)
        tracker.update_status("TASK-001", TaskStatus.COMPLETED)

        pending = tracker.get_pending_tasks()
        assert len(pending) == 3

    def test_traceability_report(self, tracker):
        """Testet Traceability-Report."""
        task = DerivedTask(
            id="TASK-001",
            title="Report Test",
            description="Test",
            category=TaskCategory.CODE,
            priority=TaskPriority.HIGH,
            target_agent=TargetAgent.CODER,
            source_type="reviewer",
            source_issue="Original Issue"
        )
        tracker.log_task(task)
        tracker.update_status("TASK-001", TaskStatus.COMPLETED, result="Behoben")

        report = tracker.get_traceability_report()
        assert report["total_tasks"] == 1
        assert "completed" in report["by_status"]
        assert len(report["traceability"]) == 1


# ============================================================================
# Dart Task Sync Tests
# ============================================================================

class TestMockDartTaskSync:
    """Tests fuer die Mock-Dart-Synchronisation."""

    def test_sync_task(self):
        """Testet Task-Synchronisation."""
        sync = MockDartTaskSync()
        task = DerivedTask(
            id="TASK-001",
            title="Sync Test",
            description="Test",
            category=TaskCategory.CODE,
            priority=TaskPriority.HIGH,
            target_agent=TargetAgent.CODER
        )
        dart_id = sync.sync_task(task)
        assert dart_id.startswith("DART-MOCK-")
        assert len(sync.get_synced_tasks()) == 1

    def test_update_status(self):
        """Testet Status-Update."""
        sync = MockDartTaskSync()
        task = DerivedTask(
            id="TASK-001",
            title="Update Test",
            description="Test",
            category=TaskCategory.CODE,
            priority=TaskPriority.HIGH,
            target_agent=TargetAgent.CODER
        )
        dart_id = sync.sync_task(task)
        success = sync.update_task_status(dart_id, "completed", "Erledigt")
        assert success

    def test_add_comment(self):
        """Testet Kommentar-Hinzufuegen."""
        sync = MockDartTaskSync()
        task = DerivedTask(
            id="TASK-001",
            title="Comment Test",
            description="Test",
            category=TaskCategory.CODE,
            priority=TaskPriority.HIGH,
            target_agent=TargetAgent.CODER
        )
        dart_id = sync.sync_task(task)
        sync.add_comment(dart_id, "Erster Kommentar")
        sync.add_comment(dart_id, "Zweiter Kommentar")

        comments = sync.get_comments(dart_id)
        assert len(comments) == 2


# ============================================================================
# Task Dispatcher Tests
# ============================================================================

class TestTaskDispatcher:
    """Tests fuer den Task-Dispatcher."""

    @pytest.fixture
    def mock_manager(self):
        """Erstellt Mock-Manager."""
        manager = Mock()
        manager.config = {}
        manager.model_router = None
        manager._ui_log = Mock()
        return manager

    def test_dispatch_no_dependencies(self, mock_manager, tmp_path):
        """Testet Dispatching ohne Abhaengigkeiten."""
        tracker = TaskTracker(log_dir=str(tmp_path))
        dispatcher = TaskDispatcher(mock_manager, {}, tracker=tracker, max_parallel=2)

        tasks = [
            DerivedTask("T1", "Task 1", "", TaskCategory.CODE, TaskPriority.HIGH, TargetAgent.CODER),
            DerivedTask("T2", "Task 2", "", TaskCategory.CODE, TaskPriority.MEDIUM, TargetAgent.CODER),
            DerivedTask("T3", "Task 3", "", TaskCategory.CODE, TaskPriority.LOW, TargetAgent.CODER),
        ]

        batches = dispatcher.dispatch(tasks)
        # Alle Tasks sollten in einem Batch sein (keine Abhaengigkeiten)
        assert len(batches) == 1
        assert batches[0].task_count == 3

    def test_dispatch_with_dependencies(self, mock_manager, tmp_path):
        """Testet Dispatching mit Abhaengigkeiten."""
        tracker = TaskTracker(log_dir=str(tmp_path))
        dispatcher = TaskDispatcher(mock_manager, {}, tracker=tracker)

        tasks = [
            DerivedTask("T1", "Base", "", TaskCategory.CODE, TaskPriority.HIGH, TargetAgent.CODER, dependencies=[]),
            DerivedTask("T2", "Depends on T1", "", TaskCategory.CODE, TaskPriority.MEDIUM, TargetAgent.CODER, dependencies=["T1"]),
            DerivedTask("T3", "Depends on T2", "", TaskCategory.CODE, TaskPriority.LOW, TargetAgent.CODER, dependencies=["T2"]),
        ]

        batches = dispatcher.dispatch(tasks)
        # Sollte 3 Batches geben (sequenzielle Abhaengigkeiten)
        assert len(batches) == 3
        assert batches[0].tasks[0].id == "T1"
        assert batches[1].tasks[0].id == "T2"
        assert batches[2].tasks[0].id == "T3"

    def test_dispatch_mixed_dependencies(self, mock_manager, tmp_path):
        """Testet Dispatching mit gemischten Abhaengigkeiten."""
        tracker = TaskTracker(log_dir=str(tmp_path))
        dispatcher = TaskDispatcher(mock_manager, {}, tracker=tracker)

        tasks = [
            DerivedTask("T1", "Base 1", "", TaskCategory.CODE, TaskPriority.CRITICAL, TargetAgent.CODER, dependencies=[]),
            DerivedTask("T2", "Base 2", "", TaskCategory.CODE, TaskPriority.HIGH, TargetAgent.CODER, dependencies=[]),
            DerivedTask("T3", "Depends on both", "", TaskCategory.CODE, TaskPriority.MEDIUM, TargetAgent.CODER, dependencies=["T1", "T2"]),
        ]

        batches = dispatcher.dispatch(tasks)
        # Batch 1: T1, T2 (parallel)
        # Batch 2: T3 (nach beiden)
        assert len(batches) == 2
        assert batches[0].task_count == 2
        assert batches[1].task_count == 1


# ============================================================================
# Integration Tests
# ============================================================================

class TestIntegration:
    """Integration Tests fuer das gesamte UTDS."""

    @pytest.fixture
    def setup(self, tmp_path):
        """Setup fuer Integration Tests."""
        mock_manager = Mock()
        mock_manager.config = {}
        mock_manager.model_router = None
        mock_manager._ui_log = Mock()
        mock_manager.base_dir = str(tmp_path)

        tracker = TaskTracker(log_dir=str(tmp_path))
        deriver = TaskDeriver()

        return mock_manager, tracker, deriver

    def test_full_flow(self, setup):
        """Testet den kompletten Flow."""
        manager, tracker, deriver = setup

        # 1. Feedback ableiten
        feedback = """
        FEHLER:
        1. SyntaxError in app.py Zeile 42
        2. TypeError in utils.py: expected int got str
        3. Keine Unit-Tests vorhanden
        """
        result = deriver.derive_tasks(feedback, "sandbox", {})

        assert result.total_tasks >= 3

        # 2. Tasks im Tracker registrieren
        task_ids = tracker.log_derivation_result(result)
        assert len(task_ids) == result.total_tasks

        # 3. Status-Updates simulieren
        for task_id in task_ids[:2]:
            tracker.update_status(task_id, TaskStatus.IN_PROGRESS)
            tracker.update_status(task_id, TaskStatus.COMPLETED, result="Behoben")

        # 4. Report pruefen
        report = tracker.get_traceability_report()
        assert report["by_status"]["completed"] == 2
        assert report["by_status"]["pending"] == result.total_tasks - 2


# ============================================================================
# AENDERUNG 01.02.2026: Tests fuer Phase 9 - Security/Sandbox UTDS-Quellen
# ============================================================================

class TestDevLoopTaskDerivation:
    """Tests fuer die DevLoopTaskDerivation Klasse."""

    @pytest.fixture
    def mock_manager(self, tmp_path):
        """Erstellt Mock-Manager fuer Tests."""
        manager = Mock()
        manager.config = {}
        manager.model_router = None
        manager._ui_log = Mock()
        manager.base_dir = str(tmp_path)
        manager.doc_service = None
        return manager

    def test_should_use_security_source(self, mock_manager, tmp_path):
        """Testet Erkennung von Security-Feedback."""
        from backend.dev_loop_task_derivation import DevLoopTaskDerivation

        td = DevLoopTaskDerivation(mock_manager)

        # Security-Feedback sollte erkannt werden (min 50 Zeichen)
        security_feedback = "Security Vulnerability: SQL Injection in database.py line 42 - user input not sanitized"
        assert td.should_use_task_derivation(security_feedback, "security", 1)

        # Auch mit CVE
        cve_feedback = "CVE-2024-1234: XSS vulnerability detected in template rendering with severity high"
        assert td.should_use_task_derivation(cve_feedback, "security", 1)

    def test_should_use_sandbox_source(self, mock_manager, tmp_path):
        """Testet Erkennung von Sandbox-Feedback."""
        from backend.dev_loop_task_derivation import DevLoopTaskDerivation

        td = DevLoopTaskDerivation(mock_manager)

        # Sandbox-Fehler sollten erkannt werden (min 50 Zeichen)
        sandbox_feedback = "Error: ImportError: No module named 'flask' - please install dependencies"
        assert td.should_use_task_derivation(sandbox_feedback, "sandbox", 1)

        # Auch mit Traceback
        traceback_feedback = "Traceback (most recent call last):\n  File 'app.py', line 42, in main\n    import flask"
        assert td.should_use_task_derivation(traceback_feedback, "sandbox", 1)

    def test_should_use_initial_source(self, mock_manager, tmp_path):
        """Testet Erkennung von Initial-Anforderungen."""
        from backend.dev_loop_task_derivation import DevLoopTaskDerivation

        td = DevLoopTaskDerivation(mock_manager)

        # Initial-Auftraege sollten immer erkannt werden
        initial_task = "Erstelle eine Web-Anwendung mit User-Login und Datenbankanbindung"
        assert td.should_use_task_derivation(initial_task, "initial", 0)

        # Discovery-Briefings ebenfalls
        discovery_task = "Projektziel: Entwicklung eines E-Commerce Systems"
        assert td.should_use_task_derivation(discovery_task, "discovery", 0)

    def test_should_not_use_short_feedback(self, mock_manager, tmp_path):
        """Testet Ablehnung von zu kurzem Feedback."""
        from backend.dev_loop_task_derivation import DevLoopTaskDerivation

        td = DevLoopTaskDerivation(mock_manager)

        # Zu kurzes Feedback sollte abgelehnt werden
        short_feedback = "OK"
        assert not td.should_use_task_derivation(short_feedback, "reviewer", 1)

    def test_should_not_use_first_iteration(self, mock_manager, tmp_path):
        """Testet Ablehnung in erster Iteration (fuer non-initial)."""
        from backend.dev_loop_task_derivation import DevLoopTaskDerivation

        td = DevLoopTaskDerivation(mock_manager)

        # In erster Iteration sollte reviewer abgelehnt werden
        feedback = "Fehler: TypeError in app.py\n- Fix needed\n- Another fix"
        assert not td.should_use_task_derivation(feedback, "reviewer", 0)

        # Aber initial sollte funktionieren
        assert td.should_use_task_derivation(feedback, "initial", 0)


class TestWebSocketEvents:
    """Tests fuer WebSocket Event Integration."""

    @pytest.fixture
    def mock_manager(self, tmp_path):
        """Erstellt Mock-Manager mit ui_log."""
        manager = Mock()
        manager.config = {}
        manager.model_router = None
        manager._ui_log = Mock()
        manager.base_dir = str(tmp_path)
        manager.doc_service = None
        return manager

    def test_emit_derivation_start_event(self, mock_manager, tmp_path):
        """Testet DerivationStart Event."""
        from backend.dev_loop_task_derivation import DevLoopTaskDerivation

        td = DevLoopTaskDerivation(mock_manager)
        td._emit_event("DerivationStart", {
            "source": "security",
            "feedback_length": 100
        })

        # Pruefen ob _ui_log aufgerufen wurde
        mock_manager._ui_log.assert_called()
        call_args = mock_manager._ui_log.call_args
        assert call_args[0][0] == "UTDS"
        assert call_args[0][1] == "DerivationStart"

    def test_emit_tasks_derived_event(self, mock_manager, tmp_path):
        """Testet TasksDerived Event."""
        from backend.dev_loop_task_derivation import DevLoopTaskDerivation

        td = DevLoopTaskDerivation(mock_manager)
        td._emit_event("TasksDerived", {
            "total": 5,
            "by_category": {"code": 3, "test": 2},
            "by_priority": {"high": 2, "medium": 3}
        })

        mock_manager._ui_log.assert_called()
        call_args = mock_manager._ui_log.call_args
        assert call_args[0][1] == "TasksDerived"
        assert "total" in call_args[0][2]


class TestDiscoveryUTDSIntegration:
    """Tests fuer Discovery Session UTDS Integration."""

    def test_format_briefing_for_utds(self, tmp_path):
        """Testet Formatierung des Briefings fuer UTDS."""
        from discovery_session import DiscoverySession
        from discovery_models import ProjectBriefing

        session = DiscoverySession()

        briefing = ProjectBriefing(
            project_name="test_projekt",
            auftraggeber="Test AG",
            datum="2026-02-01",
            teilnehmende_agenten=["Coder", "Tester"],
            projektziel="Eine Test-Anwendung",
            scope_enthalten=["Feature A", "Feature B"],
            scope_ausgeschlossen=[],
            datengrundlage=["Datenbank"],
            technische_anforderungen={"sprache": "python"},
            erfolgskriterien=["Tests bestanden"],
            timeline={"deadline": "2026-03"},
            offene_punkte=[]
        )

        formatted = session._format_briefing_for_utds(briefing)

        assert "test_projekt" in formatted
        assert "Test-Anwendung" in formatted
        assert "Feature A" in formatted
        assert "python" in formatted


class TestSecurityTaskDerivation:
    """Tests fuer Security-spezifische Task-Ableitung."""

    def test_derive_sql_injection(self):
        """Testet Ableitung von SQL-Injection Tasks."""
        deriver = TaskDeriver()
        feedback = """
        Security Scan Results:
        - SQL Injection vulnerability (high severity) in db.py line 45
        - User input not sanitized before query execution
        """
        result = deriver.derive_tasks(feedback, "security", {})

        assert result.total_tasks >= 1
        # Mindestens ein Task sollte Security-Kategorie haben
        security_tasks = [t for t in result.tasks if t.category == TaskCategory.SECURITY]
        assert len(security_tasks) >= 1

    def test_derive_xss_vulnerability(self):
        """Testet Ableitung von XSS Tasks."""
        deriver = TaskDeriver()
        feedback = """
        Security-Vulnerability (critical): XSS in template.html
        User input rendered without escaping
        """
        result = deriver.derive_tasks(feedback, "security", {})

        assert result.total_tasks >= 1
        # Kritische Prioritaet erwartet
        critical_tasks = [t for t in result.tasks if t.priority == TaskPriority.CRITICAL]
        assert len(critical_tasks) >= 1


class TestSandboxTaskDerivation:
    """Tests fuer Sandbox-spezifische Task-Ableitung."""

    def test_derive_from_assertion_error(self):
        """Testet Ableitung aus AssertionError."""
        deriver = TaskDeriver()
        feedback = """
        Sandbox-Fehler:
        AssertionError: expected 5, got 3
        at test_calculator.py:12
        """
        result = deriver.derive_tasks(feedback, "sandbox", {})

        assert result.total_tasks >= 1

    def test_derive_from_test_summary(self):
        """Testet Ableitung aus Test-Summary."""
        deriver = TaskDeriver()
        feedback = """
        Test-Summary:
        FAIL: test_login - timeout after 5s
        FAIL: test_register - assertion failed
        PASS: test_logout
        """
        result = deriver.derive_tasks(feedback, "sandbox", {})

        assert result.total_tasks >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
