# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 25.01.2026
Version: 1.0
Beschreibung: Worker-Pool für parallele Agent-Ausführung.
              Jedes Office hat einen Pool von Workern die Tasks parallel bearbeiten.
"""

import asyncio
from typing import Dict, List, Any, Optional, Callable, Awaitable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import json
import uuid


class WorkerStatus(Enum):
    """Status eines Workers."""
    IDLE = "idle"
    WORKING = "working"
    ERROR = "error"
    OFFLINE = "offline"


@dataclass
class Worker:
    """Einzelner Worker in einem Office."""
    id: str
    name: str
    office: str
    status: WorkerStatus = WorkerStatus.IDLE
    current_task: Optional[str] = None
    current_task_description: Optional[str] = None
    model: Optional[str] = None
    tasks_completed: int = 0
    last_activity: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Konvertiert Worker zu Dictionary für WebSocket."""
        return {
            "id": self.id,
            "name": self.name,
            "office": self.office,
            "status": self.status.value,
            "current_task": self.current_task,
            "current_task_description": self.current_task_description,
            "model": self.model,
            "tasks_completed": self.tasks_completed,
            "last_activity": self.last_activity.isoformat() if self.last_activity else None,
        }


class WorkerPool:
    """
    Pool von Workern für ein bestimmtes Office.

    Verwaltet mehrere Worker die parallel Tasks bearbeiten können.
    """

    # Standard Worker-Namen pro Office
    WORKER_NAMES = {
        "coder": ["Alex", "Jordan", "Casey", "Morgan", "Riley"],
        "tester": ["Sam", "Taylor", "Quinn"],
        "designer": ["Avery", "Blake"],
        "db_designer": ["Dana"],
        "security": ["Phoenix"],
        "researcher": ["Sage"],
        "reviewer": ["Parker"],
    }

    def __init__(self, office: str, max_workers: int = 3, on_status_change: Callable = None):
        """
        Initialisiert einen Worker-Pool.

        Args:
            office: Name des Offices (coder, tester, etc.)
            max_workers: Maximale Anzahl paralleler Worker
            on_status_change: Callback bei Status-Änderungen (für WebSocket)
        """
        self.office = office
        self.max_workers = max_workers
        self.on_status_change = on_status_change
        self.workers: Dict[str, Worker] = {}
        self._task_queue: asyncio.Queue = asyncio.Queue()
        self._running = False
        self._worker_tasks: List[asyncio.Task] = []

        # Erstelle initiale Worker
        names = self.WORKER_NAMES.get(office, ["Worker"])
        for i in range(min(max_workers, len(names))):
            worker_id = f"{office}_{i+1}"
            self.workers[worker_id] = Worker(
                id=worker_id,
                name=names[i],
                office=office
            )

    def get_worker(self, worker_id: str) -> Optional[Worker]:
        """Gibt einen Worker anhand seiner ID zurück."""
        return self.workers.get(worker_id)

    def get_idle_workers(self) -> List[Worker]:
        """Gibt alle verfügbaren (idle) Worker zurück."""
        return [w for w in self.workers.values() if w.status == WorkerStatus.IDLE]

    def get_active_workers(self) -> List[Worker]:
        """Gibt alle arbeitenden Worker zurück."""
        return [w for w in self.workers.values() if w.status == WorkerStatus.WORKING]

    def get_status(self) -> Dict[str, Any]:
        """
        Gibt den Status des gesamten Pools zurück.

        Returns:
            Dictionary mit Pool-Status
        """
        active = len(self.get_active_workers())
        total = len(self.workers)

        return {
            "office": self.office,
            "total_workers": total,
            "active_workers": active,
            "idle_workers": total - active,
            "workers": [w.to_dict() for w in self.workers.values()],
            "queue_size": self._task_queue.qsize() if self._running else 0,
        }

    async def assign_task(
        self,
        task_id: str,
        task_description: str,
        execute_fn: Callable[..., Awaitable[Any]],
        model: str = None,
        **kwargs
    ) -> Optional[str]:
        """
        Weist einem verfügbaren Worker einen Task zu.

        Args:
            task_id: ID des Tasks
            task_description: Beschreibung für UI
            execute_fn: Async-Funktion die den Task ausführt
            model: Optional - Modell das verwendet wird
            **kwargs: Zusätzliche Parameter für execute_fn

        Returns:
            Worker-ID wenn zugewiesen, None wenn kein Worker verfügbar
        """
        idle_workers = self.get_idle_workers()

        if not idle_workers:
            # Kein Worker verfügbar - in Queue einreihen
            await self._task_queue.put({
                "task_id": task_id,
                "description": task_description,
                "execute_fn": execute_fn,
                "model": model,
                "kwargs": kwargs
            })
            return None

        # Ersten verfügbaren Worker nehmen
        worker = idle_workers[0]
        worker.status = WorkerStatus.WORKING
        worker.current_task = task_id
        worker.current_task_description = task_description
        worker.model = model
        worker.last_activity = datetime.now()

        # Status-Update senden
        if self.on_status_change:
            await self._notify_status_change(worker, "task_assigned")

        # Task asynchron ausführen
        asyncio.create_task(self._execute_task(worker, execute_fn, **kwargs))

        return worker.id

    async def _execute_task(
        self,
        worker: Worker,
        execute_fn: Callable[..., Awaitable[Any]],
        **kwargs
    ):
        """Führt einen Task auf einem Worker aus."""
        try:
            result = await execute_fn(**kwargs)

            worker.tasks_completed += 1
            worker.status = WorkerStatus.IDLE
            worker.current_task = None
            worker.current_task_description = None
            worker.last_activity = datetime.now()

            if self.on_status_change:
                await self._notify_status_change(worker, "task_completed", result=result)

            # Prüfe ob Tasks in der Queue warten
            await self._process_queue()

            return result

        except Exception as e:
            worker.status = WorkerStatus.ERROR
            worker.last_activity = datetime.now()

            if self.on_status_change:
                await self._notify_status_change(worker, "task_failed", error=str(e))

            # Worker nach kurzer Pause wieder verfügbar machen
            await asyncio.sleep(1)
            worker.status = WorkerStatus.IDLE
            worker.current_task = None
            worker.current_task_description = None

            raise e

    async def _process_queue(self):
        """Verarbeitet wartende Tasks aus der Queue."""
        while not self._task_queue.empty():
            idle_workers = self.get_idle_workers()
            if not idle_workers:
                break

            try:
                task_data = self._task_queue.get_nowait()
                await self.assign_task(
                    task_id=task_data["task_id"],
                    task_description=task_data["description"],
                    execute_fn=task_data["execute_fn"],
                    model=task_data.get("model"),
                    **task_data.get("kwargs", {})
                )
            except asyncio.QueueEmpty:
                break

    async def _notify_status_change(self, worker: Worker, event: str, **kwargs):
        """Sendet Status-Update über Callback."""
        if self.on_status_change:
            await self.on_status_change({
                "office": self.office,
                "worker": worker.to_dict(),
                "event": event,
                "pool_status": self.get_status(),
                **kwargs
            })

    def to_dict(self) -> Dict[str, Any]:
        """Konvertiert den Pool zu einem Dictionary."""
        return self.get_status()

    def reset(self):
        """
        ÄNDERUNG 25.01.2026: Setzt alle Worker auf Idle zurück.
        Wird beim Projekt-Reset aufgerufen.
        """
        # ÄNDERUNG 25.01.2026: Bug-Fix - iteriere über .values() statt über Dict-Keys
        for worker in self.workers.values():
            worker.status = WorkerStatus.IDLE
            worker.current_task = None
            worker.current_task_description = None
            worker.model = None
        # Queue leeren
        while not self._task_queue.empty():
            try:
                self._task_queue.get_nowait()
            except asyncio.QueueEmpty:
                break


class OfficeManager:
    """
    Verwaltet alle Worker-Pools für alle Offices.

    Zentrale Koordination für parallele Verarbeitung.
    """

    # Standard-Konfiguration für Worker pro Office
    DEFAULT_CONFIG = {
        "coder": {"max_workers": 3},
        "tester": {"max_workers": 2},
        "designer": {"max_workers": 1},
        "db_designer": {"max_workers": 1},
        "security": {"max_workers": 1},
        "researcher": {"max_workers": 1},
        "reviewer": {"max_workers": 1},
        "techstack_architect": {"max_workers": 1},
    }

    def __init__(self, on_status_change: Callable = None, config: Dict = None):
        """
        Initialisiert den Office Manager.

        Args:
            on_status_change: Callback für WebSocket-Updates
            config: Optional - Überschreibt DEFAULT_CONFIG
        """
        self.on_status_change = on_status_change
        self.config = {**self.DEFAULT_CONFIG, **(config or {})}
        self.pools: Dict[str, WorkerPool] = {}

        # Erstelle Pools für alle konfigurierten Offices
        for office, office_config in self.config.items():
            self.pools[office] = WorkerPool(
                office=office,
                max_workers=office_config.get("max_workers", 1),
                on_status_change=self._handle_pool_status_change
            )

    async def _handle_pool_status_change(self, data: Dict):
        """Leitet Pool-Status-Änderungen weiter."""
        if self.on_status_change:
            await self.on_status_change(data)

    def get_pool(self, office: str) -> Optional[WorkerPool]:
        """Gibt den Worker-Pool für ein Office zurück."""
        return self.pools.get(office)

    def get_all_status(self) -> Dict[str, Any]:
        """
        Gibt den Status aller Offices zurück.

        Returns:
            Dictionary mit Status pro Office
        """
        total_active = 0
        total_workers = 0

        offices_status = {}
        for office, pool in self.pools.items():
            status = pool.get_status()
            offices_status[office] = status
            total_active += status["active_workers"]
            total_workers += status["total_workers"]

        return {
            "total_workers": total_workers,
            "total_active": total_active,
            "offices": offices_status
        }

    def get_active_offices(self) -> List[str]:
        """Gibt Liste der Offices mit aktiven Workern zurück."""
        return [
            office for office, pool in self.pools.items()
            if pool.get_active_workers()
        ]

    async def assign_task_to_office(
        self,
        office: str,
        task_id: str,
        task_description: str,
        execute_fn: Callable[..., Awaitable[Any]],
        model: str = None,
        **kwargs
    ) -> Optional[str]:
        """
        Weist einem Office einen Task zu.

        Args:
            office: Name des Offices
            task_id: ID des Tasks
            task_description: Beschreibung
            execute_fn: Auszuführende Funktion
            model: Optional - Modell
            **kwargs: Zusätzliche Parameter

        Returns:
            Worker-ID wenn zugewiesen
        """
        pool = self.get_pool(office)
        if not pool:
            return None

        return await pool.assign_task(
            task_id=task_id,
            task_description=task_description,
            execute_fn=execute_fn,
            model=model,
            **kwargs
        )

    def to_dict(self) -> Dict[str, Any]:
        """Konvertiert den Manager zu einem Dictionary."""
        return self.get_all_status()

    def reset_all_workers(self):
        """
        ÄNDERUNG 25.01.2026: Setzt alle Worker in allen Pools zurück.
        Wird beim Projekt-Reset aufgerufen.
        """
        for office, pool in self.pools.items():
            pool.reset()
