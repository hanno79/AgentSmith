"""
Author: rahn
Datum: 01.02.2026
Version: 1.0
Beschreibung: Task-Tracker für Traceability und Logging im UTDS.
              Dokumentiert alle abgeleiteten Tasks und deren Lebenszyklus.
"""

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.library_sanitizer import sanitize_structure, sanitize_text
from backend.task_models import (
    DerivedTask, TaskStatus, TaskBatch, BatchResult, TaskDerivationResult
)


class TaskTracker:
    """
    Dokumentiert und verfolgt alle abgeleiteten Tasks.

    Bietet:
    - Persistenz in task_log.json
    - Traceability: Issue -> Task -> Loesung -> Datei
    - Status-Tracking ueber den gesamten Lebenszyklus
    - Reporting-Funktionen
    """

    def __init__(self, log_dir: str = "library", dart_sync=None):
        """
        Initialisiert den TaskTracker.

        Args:
            log_dir: Verzeichnis fuer Log-Dateien
            dart_sync: Optional DartTaskSync fuer Dart-Integration
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.log_dir / "task_log.json"
        self.dart_sync = dart_sync

        # In-Memory Cache
        self._tasks: Dict[str, DerivedTask] = {}
        self._batches: Dict[str, TaskBatch] = {}
        self._derivation_sessions: List[Dict[str, Any]] = []

        # Lade existierende Daten
        self._load_from_file()

    def _load_from_file(self):
        """Laedt existierende Tasks aus Datei."""
        if self.log_file.exists():
            try:
                with open(self.log_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    # Tasks laden
                    for task_data in data.get("tasks", []):
                        task = DerivedTask.from_dict(task_data)
                        self._tasks[task.id] = task
                    # Sessions laden
                    self._derivation_sessions = data.get("sessions", [])
            except Exception as e:
                print(f"[TaskTracker] Fehler beim Laden: {e}")

    def _save_to_file(self):
        """Speichert alle Tasks in Datei."""
        try:
            data = {
                "last_updated": datetime.now().isoformat(),
                "total_tasks": len(self._tasks),
                "tasks": [t.to_dict() for t in self._tasks.values()],
                "sessions": self._derivation_sessions[-100:],  # Letzte 100 Sessions
                "summary": self._generate_summary()
            }
            data = sanitize_structure(data)
            with open(self.log_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[TaskTracker] Fehler beim Speichern: {e}")

    def _sanitize_modified_files(self, modified_files: List[str]) -> List[str]:
        """Filtert Artefakte und behaelt nur plausibel dateipfadartige Eintraege."""
        if not modified_files:
            return []

        path_re = re.compile(
            r"^[A-Za-z0-9_.\-\\/]+\.(py|js|jsx|ts|tsx|html|css|json|yaml|yml|md|sql|sh|bat|toml|ini|cfg|txt)$"
        )
        filtered: List[str] = []
        for entry in modified_files:
            if not isinstance(entry, str):
                continue
            normalized = entry.strip().replace("\\", "/")
            if not normalized:
                continue
            # request.json taucht als Artefakt aus await request.json() auf.
            if normalized.lower() == "request.json":
                continue
            if "(" in normalized or ")" in normalized or ":" in normalized:
                continue
            if path_re.match(normalized):
                filtered.append(normalized)

        return list(dict.fromkeys(filtered))[:20]

    def log_derivation_result(self, result: TaskDerivationResult) -> List[str]:
        """
        Loggt ein Task-Derivation-Ergebnis.

        Args:
            result: TaskDerivationResult vom TaskDeriver

        Returns:
            Liste der gespeicherten Task-IDs
        """
        task_ids = []

        # Session dokumentieren
        session = {
            "timestamp": datetime.now().isoformat(),
            "source": result.source,
            "total_tasks": result.total_tasks,
            "tasks_by_category": result.tasks_by_category,
            "tasks_by_priority": result.tasks_by_priority,
            "tasks_by_agent": result.tasks_by_agent,
            "derivation_time_seconds": result.derivation_time_seconds,
            "task_ids": []
        }

        # Tasks speichern
        for task in result.tasks:
            self._tasks[task.id] = task
            task_ids.append(task.id)
            session["task_ids"].append(task.id)

            # Dart-Sync wenn verfuegbar
            if self.dart_sync:
                try:
                    dart_id = self.dart_sync.sync_task(task)
                    task.dart_id = dart_id
                except Exception as e:
                    print(f"[TaskTracker] Dart-Sync fehlgeschlagen: {e}")

        self._derivation_sessions.append(session)
        self._save_to_file()

        return task_ids

    def log_task(self, task: DerivedTask) -> str:
        """
        Loggt einen einzelnen Task.

        Args:
            task: DerivedTask zum Speichern

        Returns:
            Task-ID
        """
        self._tasks[task.id] = task

        # Dart-Sync wenn verfuegbar
        if self.dart_sync and not task.dart_id:
            try:
                dart_id = self.dart_sync.sync_task(task)
                task.dart_id = dart_id
            except Exception as e:
                print(f"[TaskTracker] Dart-Sync fehlgeschlagen: {e}")

        self._save_to_file()
        return task.id

    def update_status(
        self,
        task_id: str,
        status: TaskStatus,
        result: str = None,
        error_message: str = None,
        modified_files: List[str] = None
    ):
        """
        Aktualisiert den Status eines Tasks.

        Args:
            task_id: Task-ID
            status: Neuer Status
            result: Ergebnis-Zusammenfassung (bei Completed)
            error_message: Fehlermeldung (bei Failed)
            modified_files: Liste geaenderter Dateien
        """
        if task_id not in self._tasks:
            print(f"[TaskTracker] Task {task_id} nicht gefunden")
            return

        task = self._tasks[task_id]
        task.status = status

        if status == TaskStatus.IN_PROGRESS:
            task.started_at = datetime.now()
        elif status in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
            task.completed_at = datetime.now()

        if result:
            task.result = result
        if error_message:
            task.error_message = sanitize_text(error_message)
        if modified_files:
            task.modified_files = self._sanitize_modified_files(modified_files)

        # Dart-Update wenn verfuegbar
        if self.dart_sync and task.dart_id:
            try:
                self.dart_sync.update_task_status(
                    task.dart_id,
                    status.value,
                    result or error_message or ""
                )
            except Exception as e:
                print(f"[TaskTracker] Dart-Update fehlgeschlagen: {e}")

        self._save_to_file()

    def increment_retry(self, task_id: str) -> bool:
        """
        Erhoeht den Retry-Counter eines Tasks.

        Args:
            task_id: Task-ID

        Returns:
            True wenn Retry moeglich, False wenn Maximum erreicht
        """
        if task_id not in self._tasks:
            return False

        task = self._tasks[task_id]
        task.retry_count += 1
        task.status = TaskStatus.PENDING
        self._save_to_file()

        return task.can_retry()

    def get_task(self, task_id: str) -> Optional[DerivedTask]:
        """Holt einen Task anhand der ID."""
        return self._tasks.get(task_id)

    def get_pending_tasks(self) -> List[DerivedTask]:
        """Liefert alle ausstehenden Tasks."""
        return [t for t in self._tasks.values() if t.status == TaskStatus.PENDING]

    def get_tasks_by_status(self, status: TaskStatus) -> List[DerivedTask]:
        """Liefert Tasks nach Status."""
        return [t for t in self._tasks.values() if t.status == status]

    def get_tasks_by_source(self, source: str) -> List[DerivedTask]:
        """Liefert Tasks nach Quelle."""
        return [t for t in self._tasks.values() if t.source_type == source]

    def get_traceability_report(self) -> Dict[str, Any]:
        """
        Erstellt einen Traceability-Report.

        Returns:
            Dict mit Issue -> Task -> Loesung Mapping
        """
        report = {
            "generated_at": datetime.now().isoformat(),
            "total_tasks": len(self._tasks),
            "by_status": {},
            "by_source": {},
            "traceability": []
        }

        # Nach Status gruppieren
        for status in TaskStatus:
            count = len([t for t in self._tasks.values() if t.status == status])
            if count > 0:
                report["by_status"][status.value] = count

        # Nach Quelle gruppieren
        sources = set(t.source_type for t in self._tasks.values())
        for source in sources:
            count = len([t for t in self._tasks.values() if t.source_type == source])
            report["by_source"][source] = count

        # Traceability-Eintraege
        for task in self._tasks.values():
            entry = {
                "task_id": task.id,
                "source": task.source_type,
                "source_issue": task.source_issue[:100] if task.source_issue else "",
                "title": task.title,
                "status": task.status.value,
                "result": task.result[:100] if task.result else None,
                "modified_files": task.modified_files,
                "dart_id": task.dart_id
            }
            report["traceability"].append(entry)

        return report

    def get_session_stats(self, last_n: int = 10) -> List[Dict[str, Any]]:
        """
        Liefert Statistiken der letzten Derivation-Sessions.

        Args:
            last_n: Anzahl der letzten Sessions

        Returns:
            Liste mit Session-Statistiken
        """
        return self._derivation_sessions[-last_n:]

    def _generate_summary(self) -> Dict[str, Any]:
        """Generiert eine Zusammenfassung aller Tasks."""
        if not self._tasks:
            return {"total": 0}

        completed = len([t for t in self._tasks.values() if t.status == TaskStatus.COMPLETED])
        failed = len([t for t in self._tasks.values() if t.status == TaskStatus.FAILED])
        pending = len([t for t in self._tasks.values() if t.status == TaskStatus.PENDING])

        return {
            "total": len(self._tasks),
            "completed": completed,
            "failed": failed,
            "pending": pending,
            "success_rate": completed / len(self._tasks) if self._tasks else 0,
            "sources": list(set(t.source_type for t in self._tasks.values())),
            "agents_used": list(set(t.target_agent.value for t in self._tasks.values()))
        }

    def clear_completed(self, older_than_hours: int = 24):
        """
        Entfernt abgeschlossene Tasks aelter als X Stunden.

        Args:
            older_than_hours: Schwellenwert in Stunden
        """
        cutoff = datetime.now()
        to_remove = []

        for task_id, task in self._tasks.items():
            if task.status == TaskStatus.COMPLETED and task.completed_at:
                age = (cutoff - task.completed_at).total_seconds() / 3600
                if age > older_than_hours:
                    to_remove.append(task_id)

        for task_id in to_remove:
            del self._tasks[task_id]

        if to_remove:
            self._save_to_file()
            print(f"[TaskTracker] {len(to_remove)} alte Tasks entfernt")

    def export_markdown_report(self, output_path: str = None) -> str:
        """
        Exportiert einen Markdown-Report.

        Args:
            output_path: Optionaler Ausgabepfad

        Returns:
            Markdown-String
        """
        report = self.get_traceability_report()
        summary = self._generate_summary()

        md = f"""# Task Derivation Report
Erstellt: {report['generated_at']}

## Zusammenfassung

| Metrik | Wert |
|--------|------|
| Gesamt | {summary.get('total', 0)} |
| Erledigt | {summary.get('completed', 0)} |
| Fehlgeschlagen | {summary.get('failed', 0)} |
| Ausstehend | {summary.get('pending', 0)} |
| Erfolgsrate | {summary.get('success_rate', 0):.1%} |

## Nach Status

"""
        for status, count in report.get("by_status", {}).items():
            md += f"- **{status}**: {count}\n"

        md += "\n## Nach Quelle\n\n"
        for source, count in report.get("by_source", {}).items():
            md += f"- **{source}**: {count}\n"

        md += "\n## Traceability\n\n"
        md += "| Task-ID | Quelle | Titel | Status | Geaenderte Dateien |\n"
        md += "|---------|--------|-------|--------|--------------------|\n"

        for entry in report.get("traceability", [])[:50]:  # Max 50 Eintraege
            files = ", ".join(entry.get("modified_files", [])[:3])
            md += f"| {entry['task_id']} | {entry['source']} | {entry['title'][:30]} | {entry['status']} | {files} |\n"

        if output_path:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(md)

        return md
