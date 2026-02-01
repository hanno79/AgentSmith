"""
Author: rahn
Datum: 01.02.2026
Version: 1.0
Beschreibung: Datenmodelle für das Universal Task Derivation System (UTDS).
              Definiert Task-Strukturen für Feedback-Zerlegung und Parallelisierung.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum
from datetime import datetime


class TaskCategory(Enum):
    """Kategorien für abgeleitete Tasks."""
    CODE = "code"
    TEST = "test"
    SECURITY = "security"
    DOCS = "docs"
    CONFIG = "config"
    REFACTOR = "refactor"


class TaskPriority(Enum):
    """Prioritätsstufen für Tasks."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class TaskStatus(Enum):
    """Status eines Tasks im Lebenszyklus."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"
    SKIPPED = "skipped"


class TargetAgent(Enum):
    """Ziel-Agenten für Task-Zuweisung."""
    CODER = "coder"
    TESTER = "tester"
    SECURITY = "security"
    DOCS = "docs"
    REVIEWER = "reviewer"
    FIX = "fix"


@dataclass
class DerivedTask:
    """
    Repräsentiert einen aus Feedback abgeleiteten Task.

    Jeder Task ist eine einzelne, ausführbare Arbeitseinheit,
    die einem spezifischen Agenten zugewiesen werden kann.
    """
    id: str                                    # TASK-001, TASK-002, ...
    title: str                                 # Kurze Beschreibung
    description: str                           # Detaillierte Anweisung
    category: TaskCategory                     # code, test, security, docs
    priority: TaskPriority                     # critical, high, medium, low
    target_agent: TargetAgent                  # coder, tester, security, docs
    affected_files: List[str] = field(default_factory=list)  # Betroffene Dateien
    dependencies: List[str] = field(default_factory=list)    # Abhängige Task-IDs
    source_issue: str = ""                     # Original-Issue aus Feedback
    source_type: str = ""                      # reviewer, quality_gate, security, tester
    status: TaskStatus = TaskStatus.PENDING

    # Traceability
    dart_id: Optional[str] = None              # ID in Dart nach Sync
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # Ergebnis
    result: Optional[str] = None               # Zusammenfassung der Lösung
    error_message: Optional[str] = None        # Fehlermeldung bei Failed
    modified_files: List[str] = field(default_factory=list)  # Tatsächlich geänderte Dateien

    # Metadaten
    retry_count: int = 0
    max_retries: int = 2
    timeout_seconds: int = 120

    def to_dict(self) -> Dict[str, Any]:
        """Konvertiert Task zu Dictionary für JSON-Serialisierung."""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "category": self.category.value,
            "priority": self.priority.value,
            "target_agent": self.target_agent.value,
            "affected_files": self.affected_files,
            "dependencies": self.dependencies,
            "source_issue": self.source_issue,
            "source_type": self.source_type,
            "status": self.status.value,
            "dart_id": self.dart_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "result": self.result,
            "error_message": self.error_message,
            "modified_files": self.modified_files,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "timeout_seconds": self.timeout_seconds,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DerivedTask":
        """Erstellt Task aus Dictionary."""
        return cls(
            id=data["id"],
            title=data["title"],
            description=data["description"],
            category=TaskCategory(data["category"]),
            priority=TaskPriority(data["priority"]),
            target_agent=TargetAgent(data["target_agent"]),
            affected_files=data.get("affected_files", []),
            dependencies=data.get("dependencies", []),
            source_issue=data.get("source_issue", ""),
            source_type=data.get("source_type", ""),
            status=TaskStatus(data.get("status", "pending")),
            dart_id=data.get("dart_id"),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.now(),
            started_at=datetime.fromisoformat(data["started_at"]) if data.get("started_at") else None,
            completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None,
            result=data.get("result"),
            error_message=data.get("error_message"),
            modified_files=data.get("modified_files", []),
            retry_count=data.get("retry_count", 0),
            max_retries=data.get("max_retries", 2),
            timeout_seconds=data.get("timeout_seconds", 120),
        )

    def is_ready(self, completed_tasks: List[str]) -> bool:
        """Prüft ob alle Abhängigkeiten erfüllt sind."""
        return all(dep in completed_tasks for dep in self.dependencies)

    def can_retry(self) -> bool:
        """Prüft ob ein Retry möglich ist."""
        return self.retry_count < self.max_retries


@dataclass
class TaskBatch:
    """
    Gruppe von Tasks die parallel ausgeführt werden können.

    Alle Tasks in einem Batch haben keine gegenseitigen Abhängigkeiten.
    """
    batch_id: str                              # BATCH-001, BATCH-002, ...
    tasks: List[DerivedTask] = field(default_factory=list)
    priority_order: int = 0                    # Reihenfolge der Batches

    # Status-Tracking
    status: TaskStatus = TaskStatus.PENDING
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Konvertiert Batch zu Dictionary."""
        return {
            "batch_id": self.batch_id,
            "tasks": [t.to_dict() for t in self.tasks],
            "priority_order": self.priority_order,
            "status": self.status.value,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }

    @property
    def task_count(self) -> int:
        """Anzahl der Tasks im Batch."""
        return len(self.tasks)

    @property
    def all_completed(self) -> bool:
        """Prüft ob alle Tasks abgeschlossen sind."""
        return all(t.status == TaskStatus.COMPLETED for t in self.tasks)

    @property
    def any_failed(self) -> bool:
        """Prüft ob ein Task fehlgeschlagen ist."""
        return any(t.status == TaskStatus.FAILED for t in self.tasks)


@dataclass
class BatchResult:
    """Ergebnis der Ausführung eines Task-Batches."""
    batch_id: str
    success: bool
    completed_tasks: List[str] = field(default_factory=list)   # Task-IDs
    failed_tasks: List[str] = field(default_factory=list)      # Task-IDs
    skipped_tasks: List[str] = field(default_factory=list)     # Task-IDs
    execution_time_seconds: float = 0.0

    # Aggregierte Ergebnisse
    modified_files: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Konvertiert Result zu Dictionary."""
        return {
            "batch_id": self.batch_id,
            "success": self.success,
            "completed_tasks": self.completed_tasks,
            "failed_tasks": self.failed_tasks,
            "skipped_tasks": self.skipped_tasks,
            "execution_time_seconds": self.execution_time_seconds,
            "modified_files": self.modified_files,
            "errors": self.errors,
        }


@dataclass
class TaskDerivationResult:
    """Ergebnis der Task-Ableitung aus Feedback."""
    source: str                                # reviewer, quality_gate, etc.
    source_feedback: str                       # Original-Feedback
    tasks: List[DerivedTask] = field(default_factory=list)
    batches: List[TaskBatch] = field(default_factory=list)

    # Statistiken
    total_tasks: int = 0
    tasks_by_category: Dict[str, int] = field(default_factory=dict)
    tasks_by_priority: Dict[str, int] = field(default_factory=dict)
    tasks_by_agent: Dict[str, int] = field(default_factory=dict)

    # Timing
    derivation_time_seconds: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Konvertiert Result zu Dictionary."""
        return {
            "source": self.source,
            "source_feedback": self.source_feedback[:500],  # Truncate für Logging
            "tasks": [t.to_dict() for t in self.tasks],
            "batches": [b.to_dict() for b in self.batches],
            "total_tasks": self.total_tasks,
            "tasks_by_category": self.tasks_by_category,
            "tasks_by_priority": self.tasks_by_priority,
            "tasks_by_agent": self.tasks_by_agent,
            "derivation_time_seconds": self.derivation_time_seconds,
        }


# Hilfsfunktionen für Prioritäts-Sortierung
def priority_to_int(priority: TaskPriority) -> int:
    """Konvertiert Priorität zu Integer für Sortierung (niedrig = wichtiger)."""
    mapping = {
        TaskPriority.CRITICAL: 0,
        TaskPriority.HIGH: 1,
        TaskPriority.MEDIUM: 2,
        TaskPriority.LOW: 3,
    }
    return mapping.get(priority, 99)


def sort_tasks_by_priority(tasks: List[DerivedTask]) -> List[DerivedTask]:
    """Sortiert Tasks nach Priorität (Critical zuerst)."""
    return sorted(tasks, key=lambda t: priority_to_int(t.priority))


def filter_ready_tasks(tasks: List[DerivedTask], completed_ids: List[str]) -> List[DerivedTask]:
    """Filtert Tasks deren Abhängigkeiten erfüllt sind."""
    return [t for t in tasks if t.is_ready(completed_ids) and t.status == TaskStatus.PENDING]
