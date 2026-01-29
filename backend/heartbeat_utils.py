# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 29.01.2026
Version: 1.0
Beschreibung: Heartbeat-Utilities für stabile WebSocket-Verbindung während langer Operationen.
"""
# ÄNDERUNG 29.01.2026: Ausgelagert aus orchestration_manager.py um zirkuläre Imports zu vermeiden

import threading
import time
import json


def run_with_heartbeat(
    func,
    ui_log_callback,
    agent_name: str,
    task_description: str,
    heartbeat_interval: int = 15,
    timeout_seconds: int = 300
):
    """
    Führt eine Funktion aus und sendet regelmäßige Heartbeat-Updates.
    Verhindert WebSocket-Disconnects während langer CrewAI-Operationen.

    Args:
        func: Die auszuführende Funktion (keine Argumente)
        ui_log_callback: Callback für UI-Updates (agent, event, message)
        agent_name: Name des Agents (für Heartbeat-Logs)
        task_description: Beschreibung der aktuellen Aufgabe
        heartbeat_interval: Sekunden zwischen Heartbeats (default 15)
        timeout_seconds: Maximale Ausführungszeit in Sekunden

    Returns:
        Das Ergebnis der Funktion

    Raises:
        TimeoutError: Wenn die Funktion länger als timeout_seconds dauert
        Exception: Wenn die Funktion eine Exception wirft
    """
    result = [None]
    exception = [None]
    completed = threading.Event()
    start_time = time.time()

    def target():
        try:
            result[0] = func()
        except Exception as e:
            exception[0] = e
        finally:
            completed.set()

    def heartbeat_sender():
        """Sendet regelmäßige Heartbeat-Updates bis der Task fertig ist."""
        heartbeat_count = 0
        while not completed.is_set():
            completed.wait(timeout=heartbeat_interval)
            if not completed.is_set():
                heartbeat_count += 1
                elapsed = int(time.time() - start_time)
                if ui_log_callback:
                    try:
                        ui_log_callback(
                            agent_name,
                            "Heartbeat",
                            json.dumps({
                                "status": "working",
                                "task": task_description,
                                "elapsed_seconds": elapsed,
                                "heartbeat_count": heartbeat_count
                            }, ensure_ascii=False)
                        )
                    except Exception:
                        pass  # Heartbeat-Fehler ignorieren

    work_thread = threading.Thread(target=target, daemon=True)
    heartbeat_thread = threading.Thread(target=heartbeat_sender, daemon=True)

    work_thread.start()
    heartbeat_thread.start()
    work_thread.join(timeout=timeout_seconds)

    if work_thread.is_alive():
        completed.set()  # Signal an Heartbeat-Thread zum Stoppen
        raise TimeoutError(f"Operation dauerte länger als {timeout_seconds}s")

    if exception[0]:
        raise exception[0]
    return result[0]
