"""
Author: rahn
Datum: 28.01.2026
Version: 1.0
Beschreibung: SessionManager - Verwaltet aktive Sessions und deren Status.
              Ermoeglicht State-Recovery nach Browser-Refresh und Navigation.
              Haelt den aktuellen Projekt-Status fuer Frontend-Synchronisation.
"""

import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
from collections import deque
import threading

logger = logging.getLogger(__name__)


class SessionManager:
    """
    Singleton-Klasse zur Verwaltung der aktuellen Session.
    Haelt den State zwischen Frontend-Refreshes persistent.
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._initialized = True

        # Aktuelle Session-Daten
        self.current_session: Dict[str, Any] = {
            "project_id": None,
            "goal": "",
            "status": "Idle",  # Idle, Working, Success, Error
            "active_agents": {},
            "started_at": None,
            "last_update": None,
            "iteration": 0,
            "max_iterations": 3
        }

        # Agent-Snapshots (letzter bekannter Status jedes Agents)
        self.agent_snapshots: Dict[str, Dict[str, Any]] = {
            "coder": {},
            "reviewer": {},
            "tester": {},
            "designer": {},
            "security": {},
            "researcher": {},
            "techstack": {},
            "dbdesigner": {}
        }

        # Log-Puffer (Ring-Buffer fuer letzte N Logs)
        self._max_logs = 500
        self.logs: deque = deque(maxlen=self._max_logs)

        logger.info("SessionManager initialisiert")

    def start_session(self, goal: str, project_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Startet eine neue Session mit dem gegebenen Ziel.

        Args:
            goal: Das Projektziel
            project_id: Optionale Projekt-ID (sonst auto-generiert)

        Returns:
            Session-Info Dictionary
        """
        self.current_session = {
            "project_id": project_id or f"proj_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "goal": goal,
            "status": "Working",
            "active_agents": {},
            "started_at": datetime.now().isoformat(),
            "last_update": datetime.now().isoformat(),
            "iteration": 0,
            "max_iterations": 3
        }

        # Agent-Snapshots zuruecksetzen
        for agent in self.agent_snapshots:
            self.agent_snapshots[agent] = {}

        # Logs leeren
        self.logs.clear()

        self._add_log("System", "SessionStart", f"Neue Session gestartet: {goal[:50]}...")

        logger.info(f"Session gestartet: {self.current_session['project_id']}")
        return self.current_session

    def end_session(self, status: str = "Success") -> Dict[str, Any]:
        """
        Beendet die aktuelle Session.

        Args:
            status: Endstatus (Success, Error)

        Returns:
            Finale Session-Info
        """
        self.current_session["status"] = status
        self.current_session["last_update"] = datetime.now().isoformat()
        self.current_session["ended_at"] = datetime.now().isoformat()

        self._add_log("System", "SessionEnd", f"Session beendet mit Status: {status}")

        logger.info(f"Session beendet: {self.current_session['project_id']} - {status}")
        return self.current_session

    def update_status(self, status: str) -> None:
        """Aktualisiert den Session-Status."""
        self.current_session["status"] = status
        self.current_session["last_update"] = datetime.now().isoformat()

    def update_iteration(self, iteration: int) -> None:
        """Aktualisiert die aktuelle Iteration."""
        self.current_session["iteration"] = iteration
        self.current_session["last_update"] = datetime.now().isoformat()

    def set_agent_active(self, agent_name: str, is_active: bool = True) -> None:
        """
        Markiert einen Agent als aktiv oder inaktiv.

        Args:
            agent_name: Name des Agents (z.B. 'coder', 'reviewer')
            is_active: True wenn aktiv
        """
        self.current_session["active_agents"][agent_name] = is_active
        self.current_session["last_update"] = datetime.now().isoformat()

    def update_agent_snapshot(self, agent_name: str, data: Dict[str, Any]) -> None:
        """
        Aktualisiert den Snapshot eines Agents.

        Args:
            agent_name: Name des Agents
            data: Aktuelle Agent-Daten
        """
        if agent_name in self.agent_snapshots:
            self.agent_snapshots[agent_name].update(data)
            self.agent_snapshots[agent_name]["last_update"] = datetime.now().isoformat()

    def add_log(self, agent: str, event: str, message: str) -> Dict[str, Any]:
        """
        Fuegt einen Log-Eintrag hinzu.

        Args:
            agent: Agent-Name
            event: Event-Typ
            message: Log-Nachricht

        Returns:
            Der erstellte Log-Eintrag
        """
        return self._add_log(agent, event, message)

    def _add_log(self, agent: str, event: str, message: str) -> Dict[str, Any]:
        """Interne Methode zum Hinzufuegen von Logs."""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "agent": agent,
            "event": event,
            "message": message
        }
        self.logs.append(log_entry)
        return log_entry

    def get_current_state(self) -> Dict[str, Any]:
        """
        Gibt den kompletten aktuellen State zurueck.
        Wird vom Frontend nach Refresh/Reconnect abgefragt.

        Returns:
            Kompletter Session-State
        """
        return {
            "session": self.current_session,
            "agent_data": self.agent_snapshots,
            "recent_logs": list(self.logs)[-100:],  # Letzte 100 Logs
            "is_active": self.current_session["status"] == "Working"
        }

    def get_logs(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """
        Gibt die letzten N Logs zurueck.

        Args:
            limit: Maximale Anzahl Logs
            offset: Start-Offset

        Returns:
            Liste von Log-Eintraegen
        """
        logs_list = list(self.logs)
        start = max(0, len(logs_list) - limit - offset)
        end = len(logs_list) - offset if offset > 0 else len(logs_list)
        return logs_list[start:end]

    def restore_from_library(self, project_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Stellt eine Session aus Library-Daten wieder her.

        Args:
            project_data: Projektdaten aus der Library

        Returns:
            Wiederhergestellte Session-Info
        """
        self.current_session = {
            "project_id": project_data.get("project_id"),
            "goal": project_data.get("goal", ""),
            "status": "Restored",
            "active_agents": {},
            "started_at": project_data.get("started_at"),
            "last_update": datetime.now().isoformat(),
            "iteration": project_data.get("iteration", 0),
            "max_iterations": project_data.get("max_iterations", 3),
            "restored_from": project_data.get("project_id")
        }

        # Logs aus Library laden falls vorhanden
        if "logs" in project_data:
            self.logs.clear()
            for log in project_data["logs"][-self._max_logs:]:
                self.logs.append(log)

        self._add_log("System", "SessionRestore", f"Session wiederhergestellt: {self.current_session['project_id']}")

        return self.current_session

    def is_active(self) -> bool:
        """Prueft ob eine aktive Session laeuft."""
        return self.current_session["status"] == "Working"

    def reset(self) -> None:
        """Setzt die Session komplett zurueck."""
        self.current_session = {
            "project_id": None,
            "goal": "",
            "status": "Idle",
            "active_agents": {},
            "started_at": None,
            "last_update": None,
            "iteration": 0,
            "max_iterations": 3
        }
        for agent in self.agent_snapshots:
            self.agent_snapshots[agent] = {}
        self.logs.clear()
        logger.info("Session zurueckgesetzt")


# Singleton-Instanz
_session_manager: Optional[SessionManager] = None


def get_session_manager() -> SessionManager:
    """
    Gibt die Singleton-Instanz des SessionManagers zurueck.

    Returns:
        SessionManager Instanz
    """
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager
