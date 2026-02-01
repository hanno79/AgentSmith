"""
Author: rahn
Datum: 01.02.2026
Version: 1.0
Beschreibung: Dart-Task-Synchronisation fuer externes Task-Tracking.
              Synchronisiert abgeleitete Tasks mit Dart Project Management.
"""

import os
import json
import requests
from typing import Any, Dict, List, Optional
from datetime import datetime

from backend.task_models import DerivedTask, TaskStatus, TaskPriority


class DartTaskSync:
    """
    Synchronisiert abgeleitete Tasks mit Dart fuer externes Tracking.

    Nutzt die Dart REST API fuer:
    - Task-Erstellung
    - Status-Updates
    - Kommentare hinzufuegen
    """

    # Dart API Base URL
    API_BASE = "https://api.itsdart.com/api/v0"

    # Mapping: Interne Priority -> Dart Priority
    PRIORITY_MAPPING = {
        TaskPriority.CRITICAL: "Critical",
        TaskPriority.HIGH: "High",
        TaskPriority.MEDIUM: "Medium",
        TaskPriority.LOW: "Low"
    }

    # Mapping: Interner Status -> Dart Status
    STATUS_MAPPING = {
        TaskStatus.PENDING: "To Do",
        TaskStatus.IN_PROGRESS: "In Progress",
        TaskStatus.COMPLETED: "Done",
        TaskStatus.FAILED: "Blocked",
        TaskStatus.BLOCKED: "Blocked",
        TaskStatus.SKIPPED: "Cancelled"
    }

    def __init__(self, token: str = None, dartboard: str = None):
        """
        Initialisiert den DartTaskSync.

        Args:
            token: Dart API Token (oder aus DART_TOKEN Umgebungsvariable)
            dartboard: Standard-Dartboard fuer neue Tasks
        """
        self.token = token or os.environ.get("DART_TOKEN")
        self.dartboard = dartboard or os.environ.get("DART_DARTBOARD", "AgentSmith Tasks")
        self._enabled = bool(self.token)

        if not self._enabled:
            print("[DartTaskSync] WARNUNG: Kein DART_TOKEN gefunden - Sync deaktiviert")

    @property
    def is_enabled(self) -> bool:
        """Prueft ob Dart-Sync aktiv ist."""
        return self._enabled

    def _get_headers(self) -> Dict[str, str]:
        """Erstellt HTTP-Header fuer Dart API."""
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }

    def sync_task(self, task: DerivedTask) -> Optional[str]:
        """
        Erstellt einen Task in Dart.

        Args:
            task: DerivedTask zum Synchronisieren

        Returns:
            Dart Task-ID oder None bei Fehler
        """
        if not self._enabled:
            return None

        # Task-Beschreibung zusammenbauen
        description = self._build_description(task)

        # Dart Task-Payload
        payload = {
            "title": f"[{task.id}] {task.title}",
            "description": description,
            "dartboard": self.dartboard,
            "priority": self.PRIORITY_MAPPING.get(task.priority, "Medium"),
            "status": self.STATUS_MAPPING.get(task.status, "To Do"),
            "tags": self._get_tags(task)
        }

        try:
            response = requests.post(
                f"{self.API_BASE}/tasks/create",
                headers=self._get_headers(),
                json=payload,
                timeout=10
            )

            if response.status_code in [200, 201]:
                data = response.json()
                dart_id = data.get("id") or data.get("duid")
                print(f"[DartTaskSync] Task {task.id} -> Dart {dart_id}")
                return dart_id
            else:
                print(f"[DartTaskSync] Fehler: {response.status_code} - {response.text[:200]}")
                return None

        except requests.exceptions.RequestException as e:
            print(f"[DartTaskSync] Netzwerk-Fehler: {e}")
            return None

    def update_task_status(self, dart_id: str, status: str, comment: str = None) -> bool:
        """
        Aktualisiert den Status eines Dart-Tasks.

        Args:
            dart_id: Dart Task-ID
            status: Neuer Status (interner Status-String)
            comment: Optionaler Kommentar

        Returns:
            True bei Erfolg
        """
        if not self._enabled or not dart_id:
            return False

        # Status konvertieren
        try:
            task_status = TaskStatus(status) if isinstance(status, str) else status
            dart_status = self.STATUS_MAPPING.get(task_status, "To Do")
        except ValueError:
            dart_status = status  # Bereits Dart-Status

        payload = {
            "id": dart_id,
            "status": dart_status
        }

        try:
            response = requests.patch(
                f"{self.API_BASE}/tasks/update",
                headers=self._get_headers(),
                json=payload,
                timeout=10
            )

            if response.status_code in [200, 204]:
                # Kommentar hinzufuegen wenn vorhanden
                if comment:
                    self.add_comment(dart_id, comment)
                return True
            else:
                print(f"[DartTaskSync] Update-Fehler: {response.status_code}")
                return False

        except requests.exceptions.RequestException as e:
            print(f"[DartTaskSync] Netzwerk-Fehler: {e}")
            return False

    def add_comment(self, dart_id: str, text: str) -> bool:
        """
        Fuegt einen Kommentar zum Dart-Task hinzu.

        Args:
            dart_id: Dart Task-ID
            text: Kommentar-Text

        Returns:
            True bei Erfolg
        """
        if not self._enabled or not dart_id:
            return False

        payload = {
            "taskId": dart_id,
            "text": text
        }

        try:
            response = requests.post(
                f"{self.API_BASE}/comments/create",
                headers=self._get_headers(),
                json=payload,
                timeout=10
            )

            return response.status_code in [200, 201]

        except requests.exceptions.RequestException as e:
            print(f"[DartTaskSync] Kommentar-Fehler: {e}")
            return False

    def add_resolution_comment(self, dart_id: str, resolution: str, modified_files: List[str] = None) -> bool:
        """
        Fuegt einen Loesungs-Kommentar zum Dart-Task hinzu.

        Args:
            dart_id: Dart Task-ID
            resolution: Loesungs-Beschreibung
            modified_files: Liste geaenderter Dateien

        Returns:
            True bei Erfolg
        """
        comment = f"**Loesung:**\n{resolution}"

        if modified_files:
            comment += f"\n\n**Geaenderte Dateien:**\n"
            for f in modified_files[:10]:
                comment += f"- `{f}`\n"

        comment += f"\n\n_Abgeschlossen: {datetime.now().strftime('%d.%m.%Y %H:%M')}_"

        return self.add_comment(dart_id, comment)

    def _build_description(self, task: DerivedTask) -> str:
        """Erstellt die Dart-Task-Beschreibung."""
        desc = f"""## Beschreibung
{task.description}

## Details
- **Kategorie:** {task.category.value}
- **Ziel-Agent:** {task.target_agent.value}
- **Quelle:** {task.source_type}
- **Erstellt:** {task.created_at.strftime('%d.%m.%Y %H:%M')}
"""

        if task.affected_files:
            desc += f"\n## Betroffene Dateien\n"
            for f in task.affected_files[:10]:
                desc += f"- `{f}`\n"

        if task.dependencies:
            desc += f"\n## Abhaengigkeiten\n"
            for dep in task.dependencies:
                desc += f"- {dep}\n"

        if task.source_issue:
            desc += f"\n## Original-Issue\n```\n{task.source_issue[:500]}\n```"

        return desc

    def _get_tags(self, task: DerivedTask) -> List[str]:
        """Erstellt Tags fuer den Dart-Task."""
        tags = [
            f"agent:{task.target_agent.value}",
            f"category:{task.category.value}",
            f"source:{task.source_type}",
            "auto-derived"
        ]
        return tags

    def sync_batch(self, tasks: List[DerivedTask], parent_task_id: str = None) -> Dict[str, str]:
        """
        Synchronisiert mehrere Tasks als Batch.

        Args:
            tasks: Liste von Tasks
            parent_task_id: Optionale Parent-Task-ID fuer Subtasks

        Returns:
            Dict mit Task-ID -> Dart-ID Mapping
        """
        result = {}

        for task in tasks:
            dart_id = self.sync_task(task)
            if dart_id:
                result[task.id] = dart_id
                task.dart_id = dart_id

        return result

    def get_task_status(self, dart_id: str) -> Optional[str]:
        """
        Holt den aktuellen Status eines Dart-Tasks.

        Args:
            dart_id: Dart Task-ID

        Returns:
            Status-String oder None
        """
        if not self._enabled or not dart_id:
            return None

        try:
            response = requests.get(
                f"{self.API_BASE}/tasks/{dart_id}",
                headers=self._get_headers(),
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                return data.get("status")
            return None

        except requests.exceptions.RequestException:
            return None


class MockDartTaskSync(DartTaskSync):
    """
    Mock-Implementierung fuer Tests ohne echte Dart-API.
    """

    def __init__(self, *args, **kwargs):
        self.token = "mock-token"
        self.dartboard = "Mock Dartboard"
        self._enabled = True
        self._synced_tasks: Dict[str, DerivedTask] = {}
        self._comments: Dict[str, List[str]] = {}
        self._counter = 0

    def sync_task(self, task: DerivedTask) -> Optional[str]:
        self._counter += 1
        dart_id = f"DART-MOCK-{self._counter:04d}"
        self._synced_tasks[dart_id] = task
        return dart_id

    def update_task_status(self, dart_id: str, status: str, comment: str = None) -> bool:
        if dart_id in self._synced_tasks:
            if comment:
                self.add_comment(dart_id, comment)
            return True
        return False

    def add_comment(self, dart_id: str, text: str) -> bool:
        if dart_id not in self._comments:
            self._comments[dart_id] = []
        self._comments[dart_id].append(text)
        return True

    def get_synced_tasks(self) -> Dict[str, DerivedTask]:
        """Liefert alle synchronisierten Tasks (fuer Tests)."""
        return self._synced_tasks

    def get_comments(self, dart_id: str) -> List[str]:
        """Liefert alle Kommentare eines Tasks (fuer Tests)."""
        return self._comments.get(dart_id, [])
