# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 14.02.2026
Version: 1.0
Beschreibung: Tests fuer backend/task_tracker.py - Persistenz, Status-Updates,
              Traceability-Reports und Markdown-Export.
"""
# ÄNDERUNG 22.02.2026: Header ergänzt, Helper mit Logging/Fehlerbehandlung und DUMMY-WERT-Markierung erweitert.
import json
import os
import sys
from datetime import datetime, timedelta
from unittest.mock import MagicMock
import logging
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend.task_tracker import TaskTracker
from backend.task_models import (
    DerivedTask, TaskStatus, TaskDerivationResult,
    TaskCategory, TaskPriority, TargetAgent,
)


def _make_task(task_id="T-001", title="Test Task", source_type="reviewer",
               source_issue="Fix bug", category=TaskCategory.CODE,
               priority=TaskPriority.MEDIUM, target_agent=TargetAgent.CODER):
    """Erstellt einen DerivedTask mit sinnvollen Defaults."""
    try:
        # DUMMY-WERT: Nur für Tests - NICHT produktiv verwenden!
        return DerivedTask(
            id=task_id, title=title, description="Beschreibung",
            category=category, priority=priority, target_agent=target_agent,
            affected_files=["file.js"], source_issue=source_issue,
            source_type=source_type)
    except Exception as e:
        logging.error("Fehler in _make_task: %s", e)
        raise


def _make_result(tasks=None, source="reviewer"):
    """Erstellt ein TaskDerivationResult mit Defaults."""
    try:
        # DUMMY-WERT: Nur für Tests - NICHT produktiv verwenden!
        return TaskDerivationResult(
            source=source, source_feedback="Test-Feedback",
            tasks=tasks or [], derivation_time_seconds=0.5)
    except Exception as e:
        logging.error("Fehler in _make_result: %s", e)
        raise


class TestTaskTrackerInit:
    """Tests fuer die Initialisierung des TaskTrackers."""
    def test_erstellt_log_dir(self, tmp_path):
        """Erstellt log_dir wenn nicht vorhanden."""
        log_dir = tmp_path / "sub" / "logs"
        TaskTracker(log_dir=str(log_dir))
        assert log_dir.exists()
    def test_log_file_pfad(self, tmp_path):
        """log_file Pfad ist korrekt (task_log.json)."""
        assert TaskTracker(log_dir=str(tmp_path)).log_file == tmp_path / "task_log.json"
    def test_leerer_tracker_keine_tasks(self, tmp_path):
        """Neuer Tracker hat keine Tasks."""
        assert len(TaskTracker(log_dir=str(tmp_path))._tasks) == 0
    def test_dart_sync_none_kein_fehler(self, tmp_path):
        """dart_sync=None verursacht keinen Fehler."""
        assert TaskTracker(log_dir=str(tmp_path), dart_sync=None).dart_sync is None
    def test_laedt_existierende_daten(self, tmp_path):
        """Laedt existierende Tasks aus vorhandener Datei."""
        TaskTracker(log_dir=str(tmp_path)).log_task(_make_task(task_id="T-LOAD"))
        t2 = TaskTracker(log_dir=str(tmp_path))
        assert "T-LOAD" in t2._tasks and t2._tasks["T-LOAD"].title == "Test Task"


class TestLogDerivationResult:
    """Tests fuer log_derivation_result()."""
    def test_speichert_tasks_in_dict(self, tmp_path):
        """Tasks werden im _tasks Dict gespeichert."""
        tracker = TaskTracker(log_dir=str(tmp_path))
        tracker.log_derivation_result(_make_result(tasks=[_make_task(task_id="T-100")]))
        assert "T-100" in tracker._tasks
    def test_gibt_task_ids_zurueck(self, tmp_path):
        """Gibt korrekte Task-IDs zurueck."""
        tracker = TaskTracker(log_dir=str(tmp_path))
        assert tracker.log_derivation_result(_make_result(tasks=[_make_task(task_id="T-200")])) == ["T-200"]
    def test_session_gespeichert(self, tmp_path):
        """Session wird in _derivation_sessions gespeichert."""
        tracker = TaskTracker(log_dir=str(tmp_path))
        tracker.log_derivation_result(_make_result(tasks=[_make_task()]))
        assert len(tracker._derivation_sessions) == 1
        assert tracker._derivation_sessions[0]["source"] == "reviewer"
    def test_datei_wird_geschrieben(self, tmp_path):
        """Log-Datei wird geschrieben."""
        tracker = TaskTracker(log_dir=str(tmp_path))
        tracker.log_derivation_result(_make_result(tasks=[_make_task()]))
        assert tracker.log_file.exists()
    def test_mehrere_tasks_alle_gespeichert(self, tmp_path):
        """Mehrere Tasks werden alle gespeichert."""
        tracker = TaskTracker(log_dir=str(tmp_path))
        tasks = [_make_task(task_id=f"T-{c}") for c in "ABC"]
        ids = tracker.log_derivation_result(_make_result(tasks=tasks))
        assert len(ids) == 3 and all(tid in tracker._tasks for tid in ["T-A", "T-B", "T-C"])
    def test_mit_dart_sync_aufgerufen(self, tmp_path):
        """Mit dart_sync wird sync_task aufgerufen."""
        mock_sync = MagicMock()
        mock_sync.sync_task.return_value = "DART-42"
        tracker = TaskTracker(log_dir=str(tmp_path), dart_sync=mock_sync)
        tracker.log_derivation_result(_make_result(tasks=[_make_task(task_id="T-DART")]))
        mock_sync.sync_task.assert_called_once()
        assert tracker._tasks["T-DART"].dart_id == "DART-42"
    def test_dart_sync_exception_kein_crash(self, tmp_path):
        """dart_sync Exception fuehrt nicht zum Crash."""
        mock_sync = MagicMock()
        mock_sync.sync_task.side_effect = RuntimeError("Dart offline")
        tracker = TaskTracker(log_dir=str(tmp_path), dart_sync=mock_sync)
        assert tracker.log_derivation_result(_make_result(tasks=[_make_task(task_id="T-ERR")])) == ["T-ERR"]
    def test_session_enthaelt_task_ids(self, tmp_path):
        """Session-Eintrag enthaelt die Task-IDs."""
        tracker = TaskTracker(log_dir=str(tmp_path))
        tracker.log_derivation_result(_make_result(tasks=[_make_task(task_id="T-S1"), _make_task(task_id="T-S2")]))
        s = tracker._derivation_sessions[0]
        assert "T-S1" in s["task_ids"] and "T-S2" in s["task_ids"]


class TestLogTask:
    """Tests fuer log_task()."""
    def test_einzelnen_task_speichern(self, tmp_path):
        """Einzelner Task wird gespeichert."""
        tracker = TaskTracker(log_dir=str(tmp_path))
        tracker.log_task(_make_task(task_id="T-SINGLE"))
        assert "T-SINGLE" in tracker._tasks
    def test_gibt_task_id_zurueck(self, tmp_path):
        """Gibt die Task-ID zurueck."""
        assert TaskTracker(log_dir=str(tmp_path)).log_task(_make_task(task_id="T-RET")) == "T-RET"
    def test_datei_wird_geschrieben(self, tmp_path):
        """Log-Datei wird nach log_task geschrieben."""
        tracker = TaskTracker(log_dir=str(tmp_path))
        tracker.log_task(_make_task())
        assert tracker.log_file.exists()
    def test_dart_sync_bei_leerem_dart_id(self, tmp_path):
        """dart_sync wird aufgerufen wenn task.dart_id leer ist."""
        mock_sync = MagicMock()
        mock_sync.sync_task.return_value = "DART-99"
        tracker = TaskTracker(log_dir=str(tmp_path), dart_sync=mock_sync)
        tracker.log_task(_make_task(task_id="T-DS"))
        mock_sync.sync_task.assert_called_once()
        assert tracker._tasks["T-DS"].dart_id == "DART-99"
    def test_dart_sync_exception_kein_crash(self, tmp_path):
        """dart_sync Exception fuehrt nicht zum Crash."""
        mock_sync = MagicMock()
        mock_sync.sync_task.side_effect = ConnectionError("Netzwerk-Fehler")
        assert TaskTracker(log_dir=str(tmp_path), dart_sync=mock_sync).log_task(_make_task(task_id="T-EX")) == "T-EX"


class TestUpdateStatus:
    """Tests fuer update_status()."""
    def _tracker_mit_task(self, tmp_path, task_id="T-UPD"):
        tracker = TaskTracker(log_dir=str(tmp_path))
        tracker.log_task(_make_task(task_id=task_id))
        return tracker
    def test_in_progress_started_at(self, tmp_path):
        """IN_PROGRESS setzt started_at."""
        tracker = self._tracker_mit_task(tmp_path)
        tracker.update_status("T-UPD", TaskStatus.IN_PROGRESS)
        t = tracker.get_task("T-UPD")
        assert t.status == TaskStatus.IN_PROGRESS and t.started_at is not None
    def test_completed_completed_at(self, tmp_path):
        """COMPLETED setzt completed_at."""
        tracker = self._tracker_mit_task(tmp_path)
        tracker.update_status("T-UPD", TaskStatus.COMPLETED)
        t = tracker.get_task("T-UPD")
        assert t.status == TaskStatus.COMPLETED and t.completed_at is not None
    def test_failed_completed_at(self, tmp_path):
        """FAILED setzt completed_at."""
        tracker = self._tracker_mit_task(tmp_path)
        tracker.update_status("T-UPD", TaskStatus.FAILED)
        t = tracker.get_task("T-UPD")
        assert t.status == TaskStatus.FAILED and t.completed_at is not None
    def test_result_parameter(self, tmp_path):
        """result Parameter wird auf task.result gesetzt."""
        tracker = self._tracker_mit_task(tmp_path)
        tracker.update_status("T-UPD", TaskStatus.COMPLETED, result="Alles erledigt")
        assert tracker.get_task("T-UPD").result == "Alles erledigt"
    def test_error_message(self, tmp_path):
        """error_message wird auf task.error_message gesetzt."""
        tracker = self._tracker_mit_task(tmp_path)
        tracker.update_status("T-UPD", TaskStatus.FAILED, error_message="Timeout")
        assert tracker.get_task("T-UPD").error_message == "Timeout"
    def test_modified_files(self, tmp_path):
        """modified_files werden auf task.modified_files gesetzt."""
        tracker = self._tracker_mit_task(tmp_path)
        tracker.update_status("T-UPD", TaskStatus.COMPLETED, modified_files=["a.py", "b.py"])
        assert tracker.get_task("T-UPD").modified_files == ["a.py", "b.py"]
    def test_unbekannte_task_id_kein_crash(self, tmp_path):
        """Unbekannte task_id fuehrt nicht zum Crash."""
        TaskTracker(log_dir=str(tmp_path)).update_status("UNKNOWN", TaskStatus.COMPLETED)
    def test_dart_sync_update(self, tmp_path):
        """dart_sync.update_task_status wird bei vorhandener dart_id aufgerufen."""
        mock_sync = MagicMock()
        mock_sync.sync_task.return_value = "DART-55"
        tracker = TaskTracker(log_dir=str(tmp_path), dart_sync=mock_sync)
        tracker.log_task(_make_task(task_id="T-DU"))
        tracker.update_status("T-DU", TaskStatus.COMPLETED, result="Fertig")
        mock_sync.update_task_status.assert_called_once_with("DART-55", "completed", "Fertig")
    def test_dart_sync_update_exception(self, tmp_path):
        """dart_sync.update_task_status Exception fuehrt nicht zum Crash."""
        mock_sync = MagicMock()
        mock_sync.sync_task.return_value = "DART-66"
        mock_sync.update_task_status.side_effect = RuntimeError("Dart kaputt")
        tracker = TaskTracker(log_dir=str(tmp_path), dart_sync=mock_sync)
        tracker.log_task(_make_task(task_id="T-DUE"))
        tracker.update_status("T-DUE", TaskStatus.FAILED, error_message="Fehler")
    def test_datei_wird_aktualisiert(self, tmp_path):
        """Nach update_status wird die Datei aktualisiert."""
        tracker = self._tracker_mit_task(tmp_path)
        tracker.update_status("T-UPD", TaskStatus.COMPLETED)
        with open(tracker.log_file, "r", encoding="utf-8") as f:
            assert json.load(f)["tasks"][0]["status"] == "completed"


class TestIncrementRetry:
    """Tests fuer increment_retry()."""
    def test_retry_count_erhoeht(self, tmp_path):
        """retry_count wird um 1 erhoeht."""
        tracker = TaskTracker(log_dir=str(tmp_path))
        tracker.log_task(_make_task(task_id="T-R"))
        tracker.increment_retry("T-R")
        assert tracker.get_task("T-R").retry_count == 1
    def test_status_auf_pending(self, tmp_path):
        """Status wird auf PENDING zurueckgesetzt."""
        tracker = TaskTracker(log_dir=str(tmp_path))
        task = _make_task(task_id="T-RP")
        task.status = TaskStatus.FAILED
        tracker.log_task(task)
        tracker.increment_retry("T-RP")
        assert tracker.get_task("T-RP").status == TaskStatus.PENDING
    def test_gibt_can_retry_true(self, tmp_path):
        """Gibt True zurueck wenn Retry moeglich (retry_count < max_retries)."""
        tracker = TaskTracker(log_dir=str(tmp_path))
        tracker.log_task(_make_task(task_id="T-CR"))
        assert tracker.increment_retry("T-CR") is True  # 0+1=1 < max=2
    def test_max_retries_erreicht(self, tmp_path):
        """Gibt False zurueck wenn max_retries erreicht."""
        tracker = TaskTracker(log_dir=str(tmp_path))
        task = _make_task(task_id="T-MR")
        task.retry_count = 1  # nach increment: 2 >= max=2 → False
        tracker.log_task(task)
        assert tracker.increment_retry("T-MR") is False
    def test_unbekannte_task_id_false(self, tmp_path):
        """Unbekannte task_id gibt False zurueck."""
        assert TaskTracker(log_dir=str(tmp_path)).increment_retry("UNBEKANNT") is False


class TestGetTasks:
    """Tests fuer get_task, get_pending_tasks, get_tasks_by_status, get_tasks_by_source."""
    def _tracker_mit_tasks(self, tmp_path):
        tracker = TaskTracker(log_dir=str(tmp_path))
        tracker.log_task(_make_task(task_id="T-P1", source_type="reviewer"))
        tracker.log_task(_make_task(task_id="T-P2", source_type="quality_gate"))
        tracker.log_task(_make_task(task_id="T-C1", source_type="reviewer"))
        tracker.update_status("T-C1", TaskStatus.COMPLETED)
        tracker.log_task(_make_task(task_id="T-F1", source_type="security"))
        tracker.update_status("T-F1", TaskStatus.FAILED)
        return tracker
    def test_get_task_vorhanden(self, tmp_path):
        """get_task mit vorhandener ID gibt Task zurueck."""
        t = self._tracker_mit_tasks(tmp_path).get_task("T-P1")
        assert t is not None and t.id == "T-P1"
    def test_get_task_unbekannt(self, tmp_path):
        """get_task mit unbekannter ID gibt None zurueck."""
        assert self._tracker_mit_tasks(tmp_path).get_task("UNBEKANNT") is None
    def test_get_pending_tasks(self, tmp_path):
        """get_pending_tasks liefert nur PENDING Tasks."""
        pending = self._tracker_mit_tasks(tmp_path).get_pending_tasks()
        assert len(pending) == 2 and all(t.status == TaskStatus.PENDING for t in pending)
    def test_get_tasks_by_status_completed(self, tmp_path):
        """get_tasks_by_status(COMPLETED) liefert nur abgeschlossene."""
        c = self._tracker_mit_tasks(tmp_path).get_tasks_by_status(TaskStatus.COMPLETED)
        assert len(c) == 1 and c[0].id == "T-C1"
    def test_get_tasks_by_status_failed(self, tmp_path):
        """get_tasks_by_status(FAILED) liefert nur fehlgeschlagene."""
        f = self._tracker_mit_tasks(tmp_path).get_tasks_by_status(TaskStatus.FAILED)
        assert len(f) == 1 and f[0].id == "T-F1"
    def test_get_tasks_by_source_reviewer(self, tmp_path):
        """get_tasks_by_source('reviewer') liefert nur Reviewer-Tasks."""
        tasks = self._tracker_mit_tasks(tmp_path).get_tasks_by_source("reviewer")
        assert len(tasks) == 2 and all(t.source_type == "reviewer" for t in tasks)
    def test_get_tasks_by_source_security(self, tmp_path):
        """get_tasks_by_source('security') liefert nur Security-Tasks."""
        tasks = self._tracker_mit_tasks(tmp_path).get_tasks_by_source("security")
        assert len(tasks) == 1 and tasks[0].id == "T-F1"
    def test_leerer_tracker_leere_listen(self, tmp_path):
        """Leerer Tracker gibt leere Listen zurueck."""
        tracker = TaskTracker(log_dir=str(tmp_path))
        assert tracker.get_pending_tasks() == []
        assert tracker.get_tasks_by_status(TaskStatus.COMPLETED) == []
        assert tracker.get_tasks_by_source("reviewer") == []
    def test_get_task_nach_status_update(self, tmp_path):
        """get_task gibt aktualisierten Status zurueck."""
        tracker = TaskTracker(log_dir=str(tmp_path))
        tracker.log_task(_make_task(task_id="T-SU"))
        tracker.update_status("T-SU", TaskStatus.IN_PROGRESS)
        assert tracker.get_task("T-SU").status == TaskStatus.IN_PROGRESS
    def test_get_tasks_by_source_leer(self, tmp_path):
        """get_tasks_by_source mit unbekannter Quelle gibt leere Liste zurueck."""
        assert self._tracker_mit_tasks(tmp_path).get_tasks_by_source("unbekannt") == []


class TestTraceabilityReport:
    """Tests fuer get_traceability_report()."""
    def _tracker_mit_task(self, tmp_path):
        tracker = TaskTracker(log_dir=str(tmp_path))
        tracker.log_task(_make_task(task_id="T-TR", source_type="reviewer",
                                    source_issue="Bug in Login-Formular"))
        return tracker
    def test_enthaelt_by_status(self, tmp_path):
        """Report enthaelt by_status Sektion."""
        r = self._tracker_mit_task(tmp_path).get_traceability_report()
        assert "by_status" in r and "pending" in r["by_status"]
    def test_enthaelt_by_source(self, tmp_path):
        """Report enthaelt by_source Sektion."""
        r = self._tracker_mit_task(tmp_path).get_traceability_report()
        assert "by_source" in r and "reviewer" in r["by_source"]
    def test_enthaelt_traceability(self, tmp_path):
        """Report enthaelt traceability Eintraege mit korrekten Feldern."""
        r = self._tracker_mit_task(tmp_path).get_traceability_report()
        assert len(r["traceability"]) == 1
        e = r["traceability"][0]
        assert e["task_id"] == "T-TR" and e["source"] == "reviewer"
        assert e["title"] == "Test Task" and e["status"] == "pending"
    def test_source_issue_gekuerzt(self, tmp_path):
        """source_issue wird auf 100 Zeichen gekuerzt."""
        tracker = TaskTracker(log_dir=str(tmp_path))
        tracker.log_task(_make_task(task_id="T-LONG", source_issue="A" * 200))
        assert len(tracker.get_traceability_report()["traceability"][0]["source_issue"]) == 100
    def test_result_gekuerzt(self, tmp_path):
        """result wird auf 100 Zeichen gekuerzt."""
        tracker = TaskTracker(log_dir=str(tmp_path))
        task = _make_task(task_id="T-RES")
        task.result = "B" * 200
        tracker.log_task(task)
        assert len(tracker.get_traceability_report()["traceability"][0]["result"]) == 100


class TestGenerateSummary:
    """Tests fuer _generate_summary()."""
    def test_leerer_tracker(self, tmp_path):
        """Leerer Tracker gibt {'total': 0} zurueck."""
        assert TaskTracker(log_dir=str(tmp_path))._generate_summary() == {"total": 0}
    def test_total_korrekt(self, tmp_path):
        """total zaehlt alle Tasks."""
        tracker = TaskTracker(log_dir=str(tmp_path))
        tracker.log_task(_make_task(task_id="T-1"))
        tracker.log_task(_make_task(task_id="T-2"))
        assert tracker._generate_summary()["total"] == 2
    def test_completed_zaehlung(self, tmp_path):
        """completed zaehlt abgeschlossene Tasks."""
        tracker = TaskTracker(log_dir=str(tmp_path))
        tracker.log_task(_make_task(task_id="T-C"))
        tracker.update_status("T-C", TaskStatus.COMPLETED)
        assert tracker._generate_summary()["completed"] == 1
    def test_failed_und_pending(self, tmp_path):
        """failed und pending werden korrekt gezaehlt."""
        tracker = TaskTracker(log_dir=str(tmp_path))
        tracker.log_task(_make_task(task_id="T-P"))
        tracker.log_task(_make_task(task_id="T-F"))
        tracker.update_status("T-F", TaskStatus.FAILED)
        s = tracker._generate_summary()
        assert s["pending"] == 1 and s["failed"] == 1
    def test_success_rate(self, tmp_path):
        """success_rate wird korrekt berechnet."""
        tracker = TaskTracker(log_dir=str(tmp_path))
        tracker.log_task(_make_task(task_id="T-1"))
        tracker.log_task(_make_task(task_id="T-2"))
        tracker.update_status("T-1", TaskStatus.COMPLETED)
        assert tracker._generate_summary()["success_rate"] == 0.5
    def test_sources_und_agents(self, tmp_path):
        """sources und agents_used werden aufgelistet."""
        tracker = TaskTracker(log_dir=str(tmp_path))
        tracker.log_task(_make_task(task_id="T-1", source_type="reviewer", target_agent=TargetAgent.CODER))
        tracker.log_task(_make_task(task_id="T-2", source_type="security", target_agent=TargetAgent.SECURITY))
        s = tracker._generate_summary()
        assert set(s["sources"]) == {"reviewer", "security"}
        assert set(s["agents_used"]) == {"coder", "security"}


class TestClearCompleted:
    """Tests fuer clear_completed()."""
    def test_entfernt_alte_tasks(self, tmp_path):
        """Entfernt abgeschlossene Tasks aelter als X Stunden."""
        tracker = TaskTracker(log_dir=str(tmp_path))
        tracker.log_task(_make_task(task_id="T-OLD"))
        tracker.update_status("T-OLD", TaskStatus.COMPLETED)
        tracker._tasks["T-OLD"].completed_at = datetime.now() - timedelta(hours=48)
        tracker.clear_completed(older_than_hours=24)
        assert "T-OLD" not in tracker._tasks
    def test_behaelt_neuere_tasks(self, tmp_path):
        """Behaelt abgeschlossene Tasks neuer als der Schwellenwert."""
        tracker = TaskTracker(log_dir=str(tmp_path))
        tracker.log_task(_make_task(task_id="T-NEW"))
        tracker.update_status("T-NEW", TaskStatus.COMPLETED)
        tracker.clear_completed(older_than_hours=24)
        assert "T-NEW" in tracker._tasks
    def test_behaelt_nicht_abgeschlossene(self, tmp_path):
        """Behaelt Tasks die nicht abgeschlossen sind."""
        tracker = TaskTracker(log_dir=str(tmp_path))
        tracker.log_task(_make_task(task_id="T-PEND"))
        tracker.clear_completed(older_than_hours=0)
        assert "T-PEND" in tracker._tasks
    def test_datei_aktualisiert_nach_clear(self, tmp_path):
        """Datei wird nach Entfernung aktualisiert."""
        tracker = TaskTracker(log_dir=str(tmp_path))
        tracker.log_task(_make_task(task_id="T-CLR"))
        tracker.update_status("T-CLR", TaskStatus.COMPLETED)
        tracker._tasks["T-CLR"].completed_at = datetime.now() - timedelta(hours=48)
        tracker.clear_completed(older_than_hours=1)
        with open(tracker.log_file, "r", encoding="utf-8") as f:
            assert json.load(f)["total_tasks"] == 0
    def test_keine_entfernung_bei_leerem_tracker(self, tmp_path):
        """Kein Fehler bei leerem Tracker."""
        TaskTracker(log_dir=str(tmp_path)).clear_completed(older_than_hours=1)


class TestExportMarkdown:
    """Tests fuer export_markdown_report()."""
    def _tracker_mit_tasks(self, tmp_path):
        tracker = TaskTracker(log_dir=str(tmp_path))
        tracker.log_task(_make_task(task_id="T-MD1"))
        tracker.update_status("T-MD1", TaskStatus.COMPLETED, modified_files=["app.js"])
        tracker.log_task(_make_task(task_id="T-MD2"))
        return tracker
    def test_enthaelt_markdown_header(self, tmp_path):
        """Markdown enthaelt den Report-Header."""
        assert "# Task Derivation Report" in self._tracker_mit_tasks(tmp_path).export_markdown_report()
    def test_enthaelt_zusammenfassung_tabelle(self, tmp_path):
        """Markdown enthaelt die Zusammenfassungs-Tabelle."""
        md = self._tracker_mit_tasks(tmp_path).export_markdown_report()
        assert "| Metrik | Wert |" in md and "Gesamt" in md and "Erledigt" in md
    def test_output_path_datei_geschrieben(self, tmp_path):
        """Bei output_path wird die Datei geschrieben."""
        output = str(tmp_path / "report.md")
        self._tracker_mit_tasks(tmp_path).export_markdown_report(output_path=output)
        assert os.path.exists(output)
        with open(output, "r", encoding="utf-8") as f:
            assert "# Task Derivation Report" in f.read()
    def test_max_50_eintraege_traceability(self, tmp_path):
        """Traceability-Tabelle hat maximal 50 Eintraege."""
        tracker = TaskTracker(log_dir=str(tmp_path))
        for i in range(60):
            tracker.log_task(_make_task(task_id=f"T-{i:03d}"))
        md = tracker.export_markdown_report()
        lines = [l for l in md.split("## Traceability")[1].strip().split("\n") if l.startswith("| T-")]
        assert len(lines) == 50
    def test_enthaelt_traceability_section(self, tmp_path):
        """Markdown enthaelt Traceability-Sektion."""
        md = self._tracker_mit_tasks(tmp_path).export_markdown_report()
        assert "## Traceability" in md and "| Task-ID |" in md


class TestPersistence:
    """Tests fuer Persistenz (Speichern und Laden)."""
    def test_tasks_persistiert_und_geladen(self, tmp_path):
        """Tasks werden gespeichert und beim Laden wiederhergestellt."""
        t1 = TaskTracker(log_dir=str(tmp_path))
        t1.log_task(_make_task(task_id="T-P1"))
        t1.log_task(_make_task(task_id="T-P2", title="Zweiter Task"))
        t1.update_status("T-P1", TaskStatus.COMPLETED, result="Erledigt")
        t2 = TaskTracker(log_dir=str(tmp_path))
        assert len(t2._tasks) == 2
        assert t2.get_task("T-P1").status == TaskStatus.COMPLETED
        assert t2.get_task("T-P2").title == "Zweiter Task"
    def test_sessions_persistiert(self, tmp_path):
        """Sessions werden persistiert."""
        TaskTracker(log_dir=str(tmp_path)).log_derivation_result(_make_result(tasks=[_make_task(task_id="T-S1")]))
        assert len(TaskTracker(log_dir=str(tmp_path))._derivation_sessions) == 1
    def test_sessions_max_100(self, tmp_path):
        """Maximal 100 Sessions werden in der Datei gespeichert."""
        tracker = TaskTracker(log_dir=str(tmp_path))
        for i in range(110):
            tracker.log_derivation_result(_make_result(tasks=[_make_task(task_id=f"T-{i:04d}")], source=f"s{i}"))
        with open(tracker.log_file, "r", encoding="utf-8") as f:
            assert len(json.load(f)["sessions"]) <= 100
    def test_korrupte_json_kein_crash(self, tmp_path):
        """Korrupte JSON-Datei fuehrt nicht zum Crash."""
        (tmp_path / "task_log.json").write_text("{ korrupt: json }", encoding="utf-8")
        assert len(TaskTracker(log_dir=str(tmp_path))._tasks) == 0
    def test_leere_datei_kein_crash(self, tmp_path):
        """Leere JSON-Datei fuehrt nicht zum Crash."""
        (tmp_path / "task_log.json").write_text("", encoding="utf-8")
        assert len(TaskTracker(log_dir=str(tmp_path))._tasks) == 0
