# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 31.01.2026
Version: 1.0
Beschreibung: Worker-Status Management für Orchestration Manager.
              Extrahiert aus orchestration_manager.py (Regel 1: Max 500 Zeilen)
# ÄNDERUNG [25.01.2026]: Worker-Status-Callback für WebSocket-Events
              Nachricht: Ergänzt Worker-Status-Callback für WebSocket-Events
"""

import json
from typing import Dict, Any, Callable, Optional

from .worker_pool import WorkerStatus


# Agent-Namen Mapping (Office-Key -> Agent-Name für Frontend)
# AENDERUNG 02.02.2026: Planner Office hinzugefuegt
AGENT_NAMES_MAPPING = {
    "coder": "Coder",
    "tester": "Tester",
    "designer": "Designer",
    "db_designer": "DBDesigner",
    "security": "Security",
    "researcher": "Researcher",
    "reviewer": "Reviewer",
    "techstack_architect": "TechArchitect",
    "documentation_manager": "DocumentationManager",
    "planner": "Planner",
    # AENDERUNG 07.02.2026: Fix-Agent Office (Fix 14)
    "fix": "Fix"
}


async def handle_worker_status_change(
    data: Dict[str, Any],
    on_log: Optional[Callable[[str, str, str], None]]
):
    """
    Callback für Worker-Pool Status-Änderungen.
    Sendet WorkerStatus Event an Frontend via WebSocket.

    Args:
        data: Status-Daten vom Worker-Pool
        on_log: UI-Log Callback
    """
    if on_log:
        agent_name = AGENT_NAMES_MAPPING.get(data.get("office"), "System")
        on_log(agent_name, "WorkerStatus", json.dumps(data, ensure_ascii=False))


def update_worker_status(
    office_manager,
    office: str,
    worker_status: str,
    on_log: Callable[[str, str, str], None],
    task_description: str = None,
    model: str = None
):
    """
    Synchrone Helper-Methode zum Aktualisieren des Worker-Status.
    Sendet WorkerStatus Event an Frontend.

    Args:
        office_manager: OfficeManager Instanz
        office: Name des Office (coder, tester, etc.)
        worker_status: "working" oder "idle"
        on_log: UI-Log Callback
        task_description: Beschreibung der aktuellen Aufgabe
        model: Verwendetes Modell
    """
    try:
        pool = office_manager.get_pool(office)
        if not pool:
            return

        # Finde ersten verfügbaren Worker
        workers = pool.get_idle_workers() if worker_status == "idle" else pool.get_active_workers()
        if workers or worker_status == "working":
            # Bei "working" den ersten idle Worker nehmen
            if worker_status == "working":
                idle_workers = pool.get_idle_workers()
                if idle_workers:
                    worker = idle_workers[0]
                    worker.status = WorkerStatus.WORKING
                    worker.current_task_description = task_description
                    worker.model = model
                else:
                    return  # Kein Worker verfügbar
            else:
                # Bei "idle" den ersten arbeitenden Worker auf idle setzen
                active_workers = pool.get_active_workers()
                if active_workers:
                    worker = active_workers[0]
                    worker.status = WorkerStatus.IDLE
                    worker.current_task_description = None
                    worker.current_task = None
                    worker.tasks_completed += 1
                else:
                    return  # Kein aktiver Worker zum Idle-Setzen

        agent_name = AGENT_NAMES_MAPPING.get(office, "System")
        on_log(agent_name, "WorkerStatus", json.dumps({
            "office": office,
            "pool_status": pool.get_status(),
            "event": "task_assigned" if worker_status == "working" else "task_completed"
        }, ensure_ascii=False))
    except Exception as e:
        import logging
        ts = __import__("datetime").datetime.utcnow().isoformat() + "Z"
        msg = f"[{ts}] [ERROR] [update_worker_status] - Fehler: {e}"
        on_log("System", "Error", msg)
        logging.getLogger(__name__).error(msg, exc_info=True)
