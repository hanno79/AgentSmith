# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 25.01.2026
Version: 1.0
Beschreibung: Task-Dependency-Graph für parallele Verarbeitung.
              Verwaltet Abhängigkeiten zwischen Tasks und ermöglicht
              die Identifikation von parallel ausführbaren Tasks.
"""

import asyncio
from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import json


class TaskStatus(Enum):
    """Status eines Tasks im Graph."""
    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class Task:
    """Einzelner Task im Dependency-Graph."""
    id: str
    office: str  # z.B. "coder", "designer", "db_designer"
    description: str
    depends_on: List[str] = field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    result: Any = None
    error: Optional[str] = None
    worker_id: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Konvertiert Task zu Dictionary für WebSocket."""
        return {
            "id": self.id,
            "office": self.office,
            "description": self.description,
            "depends_on": self.depends_on,
            "status": self.status.value,
            "worker_id": self.worker_id,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class TaskGraph:
    """
    Task-Dependency-Graph für parallele Verarbeitung.

    Verwaltet Tasks mit Abhängigkeiten und ermöglicht die Identifikation
    von Tasks, die parallel ausgeführt werden können.
    """

    def __init__(self):
        self.tasks: Dict[str, Task] = {}
        self._lock = asyncio.Lock()

    def add_task(
        self,
        task_id: str,
        office: str,
        description: str,
        depends_on: List[str] = None
    ) -> Task:
        """
        Fügt einen neuen Task zum Graph hinzu.

        Args:
            task_id: Eindeutige ID des Tasks
            office: Zuständiges Office (coder, designer, etc.)
            description: Beschreibung des Tasks
            depends_on: Liste von Task-IDs von denen dieser abhängt

        Returns:
            Der erstellte Task
        """
        if depends_on is None:
            depends_on = []

        task = Task(
            id=task_id,
            office=office,
            description=description,
            depends_on=depends_on
        )
        self.tasks[task_id] = task
        return task

    def get_ready_tasks(self) -> List[Task]:
        """
        Gibt alle Tasks zurück, deren Dependencies erfüllt sind.

        Ein Task ist "ready" wenn:
        - Status ist PENDING
        - Alle Tasks in depends_on sind COMPLETED

        Returns:
            Liste von ausführbaren Tasks
        """
        ready = []
        for task in self.tasks.values():
            if task.status == TaskStatus.PENDING:
                deps_satisfied = all(
                    self.tasks[dep_id].status == TaskStatus.COMPLETED
                    for dep_id in task.depends_on
                    if dep_id in self.tasks
                )
                if deps_satisfied:
                    ready.append(task)
        return ready

    def get_ready_tasks_by_office(self) -> Dict[str, List[Task]]:
        """
        Gruppiert ausführbare Tasks nach Office.

        Returns:
            Dictionary: office -> Liste von ready Tasks
        """
        ready_tasks = self.get_ready_tasks()
        by_office: Dict[str, List[Task]] = {}

        for task in ready_tasks:
            if task.office not in by_office:
                by_office[task.office] = []
            by_office[task.office].append(task)

        return by_office

    def mark_running(self, task_id: str, worker_id: str = None) -> bool:
        """
        Markiert einen Task als laufend.

        Args:
            task_id: ID des Tasks
            worker_id: Optional - ID des Workers der den Task ausführt

        Returns:
            True wenn erfolgreich, False wenn Task nicht existiert
        """
        if task_id not in self.tasks:
            return False

        task = self.tasks[task_id]
        task.status = TaskStatus.RUNNING
        task.worker_id = worker_id
        task.started_at = datetime.now()
        return True

    def mark_completed(self, task_id: str, result: Any = None) -> bool:
        """
        Markiert einen Task als abgeschlossen.

        Args:
            task_id: ID des Tasks
            result: Optional - Ergebnis des Tasks

        Returns:
            True wenn erfolgreich
        """
        if task_id not in self.tasks:
            return False

        task = self.tasks[task_id]
        task.status = TaskStatus.COMPLETED
        task.result = result
        task.completed_at = datetime.now()
        return True

    def mark_failed(self, task_id: str, error: str) -> bool:
        """
        Markiert einen Task als fehlgeschlagen.

        Args:
            task_id: ID des Tasks
            error: Fehlermeldung

        Returns:
            True wenn erfolgreich
        """
        if task_id not in self.tasks:
            return False

        task = self.tasks[task_id]
        task.status = TaskStatus.FAILED
        task.error = error
        task.completed_at = datetime.now()
        return True

    def all_completed(self) -> bool:
        """Prüft ob alle Tasks abgeschlossen sind."""
        return all(
            task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.SKIPPED]
            for task in self.tasks.values()
        )

    def get_status_summary(self) -> Dict[str, int]:
        """
        Gibt eine Zusammenfassung der Task-Status zurück.

        Returns:
            Dictionary mit Anzahl Tasks pro Status
        """
        summary = {status.value: 0 for status in TaskStatus}
        for task in self.tasks.values():
            summary[task.status.value] += 1
        return summary

    def get_parallel_groups(self) -> List[List[str]]:
        """
        Berechnet Gruppen von Tasks die parallel ausgeführt werden können.

        Verwendet topologische Sortierung um Parallelisierungs-Ebenen zu finden.

        Returns:
            Liste von Listen - jede innere Liste enthält parallel ausführbare Task-IDs
        """
        # Berechne in-degree für jeden Task
        in_degree: Dict[str, int] = {task_id: 0 for task_id in self.tasks}
        for task in self.tasks.values():
            for dep_id in task.depends_on:
                if dep_id in in_degree:
                    in_degree[task.id] += 1

        # Finde Ebenen (Tasks mit gleicher Tiefe können parallel laufen)
        levels: List[List[str]] = []
        remaining = set(self.tasks.keys())

        while remaining:
            # Finde alle Tasks ohne unerfüllte Dependencies
            current_level = [
                task_id for task_id in remaining
                if all(
                    dep_id not in remaining
                    for dep_id in self.tasks[task_id].depends_on
                )
            ]

            if not current_level:
                # Zyklus erkannt - sollte nicht passieren
                break

            levels.append(current_level)
            remaining -= set(current_level)

        return levels

    def to_dict(self) -> Dict[str, Any]:
        """Konvertiert den gesamten Graph zu einem Dictionary."""
        return {
            "tasks": {task_id: task.to_dict() for task_id, task in self.tasks.items()},
            "status_summary": self.get_status_summary(),
            "parallel_groups": self.get_parallel_groups(),
            "all_completed": self.all_completed()
        }

    def to_json(self) -> str:
        """Konvertiert den Graph zu JSON."""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


# Standard Task-Templates für verschiedene Projekt-Typen
def create_webapp_task_graph(user_goal: str) -> TaskGraph:
    """
    Erstellt einen Task-Graph für Web-Applikationen.

    Standard-Ablauf:
    1. Research (keine Dependencies)
    2. TechStack (depends: Research)
    3. DB-Designer + Designer PARALLEL (depends: TechStack)
    4. Coder (depends: DB-Designer, Designer)
    5. Sandbox + Tester + Security PARALLEL (depends: Coder)
    6. Reviewer (depends: Sandbox, Tester, Security)

    Args:
        user_goal: Das Benutzerziel

    Returns:
        Konfigurierter TaskGraph
    """
    graph = TaskGraph()

    # Phase 1: Research
    graph.add_task("research", "researcher", f"Recherche für: {user_goal}")

    # Phase 2: TechStack
    graph.add_task("techstack", "techstack_architect", "TechStack-Analyse", ["research"])

    # Phase 3: Design PARALLEL
    graph.add_task("db_design", "db_designer", "Datenbank-Schema erstellen", ["techstack"])
    graph.add_task("ui_design", "designer", "UI-Design erstellen", ["techstack"])

    # Phase 4: Coding (wartet auf beide Designer)
    graph.add_task("coding", "coder", "Code generieren", ["db_design", "ui_design"])

    # Phase 5: Validation PARALLEL
    graph.add_task("sandbox", "sandbox", "Sandbox-Test", ["coding"])
    graph.add_task("testing", "tester", "UI-Tests", ["coding"])
    graph.add_task("security", "security", "Security-Scan", ["coding"])

    # Phase 6: Review (wartet auf alle Validierung)
    graph.add_task("review", "reviewer", "Code-Review", ["sandbox", "testing", "security"])

    return graph


def create_cli_task_graph(user_goal: str) -> TaskGraph:
    """
    Erstellt einen Task-Graph für CLI-Tools (einfacher, weniger parallel).

    Args:
        user_goal: Das Benutzerziel

    Returns:
        Konfigurierter TaskGraph
    """
    graph = TaskGraph()

    graph.add_task("research", "researcher", f"Recherche für: {user_goal}")
    graph.add_task("techstack", "techstack_architect", "TechStack-Analyse", ["research"])
    graph.add_task("coding", "coder", "Code generieren", ["techstack"])
    graph.add_task("sandbox", "sandbox", "Sandbox-Test", ["coding"])
    graph.add_task("review", "reviewer", "Code-Review", ["sandbox"])

    return graph
