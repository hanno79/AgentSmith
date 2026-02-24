# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 14.02.2026
Version: 1.0
Beschreibung: Tests fuer backend/task_graph.py
              Testet TaskGraph, TaskStatus, Task-Dataclass und Graph-Templates.
"""

import json
import os
import sys
import pytest

# Projekt-Root zum Python-Path hinzufuegen
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.task_graph import (
    TaskGraph, TaskStatus, Task,
    create_webapp_task_graph, create_cli_task_graph,
)


class TestTaskStatus:
    """Tests fuer TaskStatus Enum."""

    def test_alle_status_werte(self):
        """Alle erwarteten Status-Werte existieren."""
        assert TaskStatus.PENDING.value == "pending"
        assert TaskStatus.READY.value == "ready"
        assert TaskStatus.RUNNING.value == "running"
        assert TaskStatus.COMPLETED.value == "completed"
        assert TaskStatus.FAILED.value == "failed"
        assert TaskStatus.SKIPPED.value == "skipped"


class TestTaskDataclass:
    """Tests fuer Task Dataclass."""

    def test_task_erstellung_mit_defaults(self):
        """Task wird mit Default-Werten erstellt."""
        task = Task(id="t1", office="coder", description="Test")
        assert task.id == "t1"
        assert task.office == "coder"
        assert task.status == TaskStatus.PENDING
        assert task.depends_on == []
        assert task.result is None
        assert task.error is None
        assert task.worker_id is None

    def test_task_to_dict(self):
        """Task.to_dict() liefert korrektes Dictionary."""
        task = Task(id="t1", office="coder", description="Code erstellen", depends_on=["t0"])
        d = task.to_dict()
        assert d["id"] == "t1"
        assert d["office"] == "coder"
        assert d["description"] == "Code erstellen"
        assert d["depends_on"] == ["t0"]
        assert d["status"] == "pending"
        assert d["started_at"] is None

    def test_task_to_dict_mit_zeitstempel(self):
        """to_dict() konvertiert datetime korrekt zu ISO-String."""
        from datetime import datetime
        task = Task(id="t1", office="coder", description="Test")
        task.started_at = datetime(2026, 2, 14, 10, 30, 0)
        d = task.to_dict()
        assert d["started_at"] == "2026-02-14T10:30:00"


class TestTaskGraph:
    """Tests fuer TaskGraph Klasse."""

    def test_leerer_graph(self):
        """Neuer Graph hat keine Tasks."""
        g = TaskGraph()
        assert len(g.tasks) == 0
        assert g.all_completed() is True  # Leerer Graph = alles fertig

    def test_task_hinzufuegen(self):
        """add_task() erstellt und speichert Task."""
        g = TaskGraph()
        task = g.add_task("t1", "coder", "Code schreiben")
        assert "t1" in g.tasks
        assert task.id == "t1"
        assert task.office == "coder"
        assert task.status == TaskStatus.PENDING

    def test_task_mit_abhaengigkeiten(self):
        """Task mit depends_on wird korrekt erstellt."""
        g = TaskGraph()
        g.add_task("t1", "researcher", "Recherche")
        g.add_task("t2", "coder", "Code", depends_on=["t1"])
        assert g.tasks["t2"].depends_on == ["t1"]

    def test_get_ready_tasks_ohne_abhaengigkeiten(self):
        """Tasks ohne Abhaengigkeiten sind sofort ready."""
        g = TaskGraph()
        g.add_task("t1", "researcher", "Recherche")
        g.add_task("t2", "designer", "Design")
        ready = g.get_ready_tasks()
        assert len(ready) == 2

    def test_get_ready_tasks_mit_abhaengigkeiten(self):
        """Tasks mit unerfuellten Dependencies sind nicht ready."""
        g = TaskGraph()
        g.add_task("t1", "researcher", "Recherche")
        g.add_task("t2", "coder", "Code", depends_on=["t1"])
        ready = g.get_ready_tasks()
        assert len(ready) == 1
        assert ready[0].id == "t1"

    def test_get_ready_tasks_nach_completion(self):
        """Nach Completion der Dependency wird abhaengiger Task ready."""
        g = TaskGraph()
        g.add_task("t1", "researcher", "Recherche")
        g.add_task("t2", "coder", "Code", depends_on=["t1"])
        g.mark_completed("t1")
        ready = g.get_ready_tasks()
        assert len(ready) == 1
        assert ready[0].id == "t2"

    def test_get_ready_tasks_by_office(self):
        """Tasks werden korrekt nach Office gruppiert."""
        g = TaskGraph()
        g.add_task("t1", "coder", "Code 1")
        g.add_task("t2", "coder", "Code 2")
        g.add_task("t3", "designer", "Design")
        by_office = g.get_ready_tasks_by_office()
        assert len(by_office["coder"]) == 2
        assert len(by_office["designer"]) == 1

    def test_mark_running(self):
        """mark_running() setzt Status und Worker."""
        g = TaskGraph()
        g.add_task("t1", "coder", "Code")
        result = g.mark_running("t1", worker_id="w1")
        assert result is True
        assert g.tasks["t1"].status == TaskStatus.RUNNING
        assert g.tasks["t1"].worker_id == "w1"
        assert g.tasks["t1"].started_at is not None

    def test_mark_running_unbekannter_task(self):
        """mark_running() mit unbekannter ID gibt False zurueck."""
        g = TaskGraph()
        result = g.mark_running("nichtexistent")
        assert result is False

    def test_mark_completed(self):
        """mark_completed() setzt Status und Ergebnis."""
        g = TaskGraph()
        g.add_task("t1", "coder", "Code")
        result = g.mark_completed("t1", result="Erfolg")
        assert result is True
        assert g.tasks["t1"].status == TaskStatus.COMPLETED
        assert g.tasks["t1"].result == "Erfolg"
        assert g.tasks["t1"].completed_at is not None

    def test_mark_completed_unbekannter_task(self):
        """mark_completed() mit unbekannter ID gibt False zurueck."""
        g = TaskGraph()
        assert g.mark_completed("nichtexistent") is False

    def test_mark_failed(self):
        """mark_failed() setzt Status und Fehlermeldung."""
        g = TaskGraph()
        g.add_task("t1", "coder", "Code")
        result = g.mark_failed("t1", error="Timeout")
        assert result is True
        assert g.tasks["t1"].status == TaskStatus.FAILED
        assert g.tasks["t1"].error == "Timeout"

    def test_mark_failed_unbekannter_task(self):
        """mark_failed() mit unbekannter ID gibt False zurueck."""
        g = TaskGraph()
        assert g.mark_failed("nichtexistent", "Fehler") is False

    def test_all_completed_false(self):
        """all_completed() ist False wenn Tasks ausstehen."""
        g = TaskGraph()
        g.add_task("t1", "coder", "Code")
        assert g.all_completed() is False

    def test_all_completed_true(self):
        """all_completed() ist True wenn alle fertig/fehlgeschlagen/uebersprungen."""
        g = TaskGraph()
        g.add_task("t1", "coder", "Code")
        g.add_task("t2", "reviewer", "Review")
        g.add_task("t3", "tester", "Test")
        g.mark_completed("t1")
        g.mark_failed("t2", "Fehler")
        g.tasks["t3"].status = TaskStatus.SKIPPED
        assert g.all_completed() is True

    def test_get_status_summary(self):
        """get_status_summary() zaehlt Tasks pro Status."""
        g = TaskGraph()
        g.add_task("t1", "coder", "Code")
        g.add_task("t2", "reviewer", "Review")
        g.add_task("t3", "tester", "Test")
        g.mark_completed("t1")
        g.mark_running("t2")
        summary = g.get_status_summary()
        assert summary["completed"] == 1
        assert summary["running"] == 1
        assert summary["pending"] == 1

    def test_get_parallel_groups(self):
        """get_parallel_groups() findet korrekte Parallelisierungsebenen."""
        g = TaskGraph()
        g.add_task("research", "researcher", "Recherche")
        g.add_task("design", "designer", "Design", depends_on=["research"])
        g.add_task("db", "db_designer", "DB-Schema", depends_on=["research"])
        g.add_task("code", "coder", "Code", depends_on=["design", "db"])
        groups = g.get_parallel_groups()
        # Ebene 0: research (keine Deps)
        assert "research" in groups[0]
        # Ebene 1: design + db (parallel, haengen nur von research ab)
        assert set(groups[1]) == {"design", "db"}
        # Ebene 2: code (haengt von design + db ab)
        assert "code" in groups[2]

    def test_get_parallel_groups_alle_unabhaengig(self):
        """Alle Tasks ohne Abhaengigkeiten = eine Gruppe."""
        g = TaskGraph()
        g.add_task("t1", "a", "Task 1")
        g.add_task("t2", "b", "Task 2")
        g.add_task("t3", "c", "Task 3")
        groups = g.get_parallel_groups()
        assert len(groups) == 1
        assert len(groups[0]) == 3

    def test_to_dict(self):
        """to_dict() liefert vollstaendiges Dictionary."""
        g = TaskGraph()
        g.add_task("t1", "coder", "Code")
        d = g.to_dict()
        assert "tasks" in d
        assert "status_summary" in d
        assert "parallel_groups" in d
        assert "all_completed" in d
        assert "t1" in d["tasks"]

    def test_to_json(self):
        """to_json() liefert gueltigen JSON-String."""
        g = TaskGraph()
        g.add_task("t1", "coder", "Code erstellen")
        json_str = g.to_json()
        parsed = json.loads(json_str)
        assert parsed["tasks"]["t1"]["office"] == "coder"


class TestCreateWebappTaskGraph:
    """Tests fuer create_webapp_task_graph()."""

    def test_webapp_graph_hat_9_tasks(self):
        """Webapp-Graph hat genau 9 Tasks (research, techstack, db, ui, code, sandbox, test, security, review)."""
        g = create_webapp_task_graph("Todo-App erstellen")
        assert len(g.tasks) == 9

    def test_webapp_graph_research_ohne_deps(self):
        """Research-Task hat keine Abhaengigkeiten."""
        g = create_webapp_task_graph("Test")
        assert g.tasks["research"].depends_on == []

    def test_webapp_graph_parallele_designer(self):
        """DB-Designer und UI-Designer koennen parallel laufen."""
        g = create_webapp_task_graph("Test")
        assert g.tasks["db_design"].depends_on == ["techstack"]
        assert g.tasks["ui_design"].depends_on == ["techstack"]

    def test_webapp_graph_coder_wartet_auf_designer(self):
        """Coder wartet auf beide Designer."""
        g = create_webapp_task_graph("Test")
        assert "db_design" in g.tasks["coding"].depends_on
        assert "ui_design" in g.tasks["coding"].depends_on

    def test_webapp_graph_parallele_validierung(self):
        """Sandbox, Testing, Security koennen parallel laufen."""
        g = create_webapp_task_graph("Test")
        assert g.tasks["sandbox"].depends_on == ["coding"]
        assert g.tasks["testing"].depends_on == ["coding"]
        assert g.tasks["security"].depends_on == ["coding"]

    def test_webapp_graph_review_wartet_auf_validierung(self):
        """Review wartet auf alle Validierungsschritte."""
        g = create_webapp_task_graph("Test")
        review_deps = g.tasks["review"].depends_on
        assert "sandbox" in review_deps
        assert "testing" in review_deps
        assert "security" in review_deps

    def test_webapp_graph_user_goal_in_research(self):
        """User-Goal wird in Research-Beschreibung aufgenommen."""
        g = create_webapp_task_graph("Budget-Tracker App")
        assert "Budget-Tracker App" in g.tasks["research"].description

    def test_webapp_graph_parallelgruppen(self):
        """Webapp hat mindestens 4 Parallelisierungsebenen."""
        g = create_webapp_task_graph("Test")
        groups = g.get_parallel_groups()
        # research → techstack → {db,ui} → coding → {sandbox,testing,security} → review
        assert len(groups) >= 4


class TestCreateCliTaskGraph:
    """Tests fuer create_cli_task_graph()."""

    def test_cli_graph_hat_5_tasks(self):
        """CLI-Graph hat genau 5 Tasks (einfacher als Webapp)."""
        g = create_cli_task_graph("CLI Tool bauen")
        assert len(g.tasks) == 5

    def test_cli_graph_sequentiell(self):
        """CLI-Graph ist weitgehend sequentiell."""
        g = create_cli_task_graph("Test")
        groups = g.get_parallel_groups()
        # Alle Tasks sind sequentiell = 5 Ebenen mit je 1 Task
        for group in groups:
            assert len(group) == 1

    def test_cli_graph_kein_designer(self):
        """CLI-Graph hat keinen UI-Designer."""
        g = create_cli_task_graph("Test")
        assert "ui_design" not in g.tasks
        assert "db_design" not in g.tasks
