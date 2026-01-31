"""
Author: rahn
Datum: 31.01.2026
Version: 1.4
Beschreibung: SessionManager - Verwaltet aktive Sessions und deren Status.
              Ermoeglicht State-Recovery nach Browser-Refresh und Navigation.
              Haelt den aktuellen Projekt-Status fuer Frontend-Synchronisation.
              ÄNDERUNG 29.01.2026: Discovery Briefing Speicherung fuer Agent-Kontext.
              ÄNDERUNG 30.01.2026: HELP_NEEDED Support (set_agent_blocked) gemäß Protokoll.
              ÄNDERUNG 31.01.2026: get_blocked_agents(), clear_agent_blocked() fuer HELP_NEEDED Handler.
              ÄNDERUNG 31.01.2026: Parallel-Fix Status Tracking (fix, parallel_fixer Agenten).
"""

import logging
from copy import deepcopy
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
    _lock = threading.RLock()

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
        # ÄNDERUNG 29.01.2026: RLock fuer reentrante Status- und Log-Updates
        self._lock = threading.RLock()

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
        # AENDERUNG 31.01.2026: Dart AI Agenten hinzugefuegt (planner, analyst, konzepter)
        # AENDERUNG 31.01.2026: Parallel-Fix Agenten hinzugefuegt (fix, parallel_fixer)
        self.agent_snapshots: Dict[str, Dict[str, Any]] = {
            "coder": {},
            "reviewer": {},
            "tester": {},
            "designer": {},
            "security": {},
            "researcher": {},
            "techstack": {},
            "dbdesigner": {},
            # Dart AI Feature-Ableitung Agenten
            "planner": {},
            "analyst": {},
            "konzepter": {},
            # Parallel-Fix Agenten
            "fix": {},
            "parallel_fixer": {}
        }

        # Log-Puffer (Ring-Buffer fuer letzte N Logs)
        self._max_logs = 500
        self.logs: deque = deque(maxlen=self._max_logs)

        # ÄNDERUNG 29.01.2026: Discovery Briefing fuer Agent-Kontext
        self.discovery_briefing: Optional[Dict[str, Any]] = None

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
        with self._lock:
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
        with self._lock:
            self.current_session["status"] = status
            self.current_session["last_update"] = datetime.now().isoformat()
            self.current_session["ended_at"] = datetime.now().isoformat()

            self._add_log("System", "SessionEnd", f"Session beendet mit Status: {status}")

            logger.info(f"Session beendet: {self.current_session['project_id']} - {status}")
            return self.current_session

    def update_status(self, status: str) -> None:
        """Aktualisiert den Session-Status."""
        with self._lock:
            self.current_session["status"] = status
            self.current_session["last_update"] = datetime.now().isoformat()

    def update_iteration(self, iteration: int) -> None:
        """Aktualisiert die aktuelle Iteration."""
        with self._lock:
            self.current_session["iteration"] = iteration
            self.current_session["last_update"] = datetime.now().isoformat()

    def set_agent_active(self, agent_name: str, is_active: bool = True) -> None:
        """
        Markiert einen Agent als aktiv oder inaktiv.

        Args:
            agent_name: Name des Agents (z.B. 'coder', 'reviewer')
            is_active: True wenn aktiv
        """
        with self._lock:
            self.current_session["active_agents"][agent_name] = is_active
            self.current_session["last_update"] = datetime.now().isoformat()

    # ÄNDERUNG 30.01.2026: HELP_NEEDED Support gemäß Kommunikationsprotokoll
    def set_agent_blocked(self, agent_name: str, is_blocked: bool, reason: str = "") -> None:
        """
        Markiert einen Agent als blockiert (HELP_NEEDED Status).

        Args:
            agent_name: Name des Agents
            is_blocked: True wenn blockiert
            reason: Grund der Blockierung (JSON-String mit Details)
        """
        with self._lock:
            # ÄNDERUNG [31.01.2026]: Snapshot bei fehlenden Agents initialisieren
            if agent_name not in self.agent_snapshots:
                self.agent_snapshots[agent_name] = {}
            self.agent_snapshots[agent_name]["blocked"] = is_blocked
            self.agent_snapshots[agent_name]["blocked_reason"] = reason if is_blocked else ""
            self.agent_snapshots[agent_name]["blocked_at"] = datetime.now().isoformat() if is_blocked else None
            self.current_session["last_update"] = datetime.now().isoformat()

            if is_blocked:
                self._add_log(agent_name, "HELP_NEEDED", reason)

    # ÄNDERUNG 31.01.2026: Methoden fuer HELP_NEEDED Handler
    def get_blocked_agents(self) -> Dict[str, Dict[str, Any]]:
        """
        Gibt alle blockierten Agents zurueck.

        Returns:
            Dict mit Agent-Namen als Keys und Block-Details als Values
            z.B. {"security": {"reason": "...", "blocked_at": "...", "priority": "high"}}
        """
        with self._lock:
            return {
                agent: {
                    "reason": data.get("blocked_reason", ""),
                    "blocked_at": data.get("blocked_at"),
                    "priority": self._extract_priority(data.get("blocked_reason", ""))
                }
                for agent, data in self.agent_snapshots.items()
                if data.get("blocked", False)
            }

    def _extract_priority(self, reason_json: str) -> str:
        """
        Extrahiert Priority aus HELP_NEEDED Reason-JSON.

        Args:
            reason_json: JSON-String mit HELP_NEEDED Details

        Returns:
            Priority-String (critical, high, normal, low)
        """
        try:
            import json
            data = json.loads(reason_json)
            # Priority kann direkt im JSON sein oder muss aus action_required abgeleitet werden
            if "priority" in data:
                return data["priority"]
            # Ableitung aus action_required
            action = data.get("action_required", "")
            if "security" in action.lower() or "critical" in action.lower():
                return "high"
            return "normal"
        except (json.JSONDecodeError, TypeError):
            return "normal"

    def clear_agent_blocked(self, agent_name: str) -> None:
        """
        Setzt Agent-Blockade zurueck nach erfolgreicher Hilfe.

        Args:
            agent_name: Name des Agents dessen Blockade aufgehoben wird
        """
        with self._lock:
            if agent_name in self.agent_snapshots:
                self.agent_snapshots[agent_name]["blocked"] = False
                self.agent_snapshots[agent_name]["blocked_reason"] = ""
                self.agent_snapshots[agent_name]["blocked_at"] = None
                self._add_log(agent_name, "HELP_RESOLVED", "Blockade aufgehoben")
            self.current_session["last_update"] = datetime.now().isoformat()

    def update_agent_snapshot(self, agent_name: str, data: Dict[str, Any]) -> None:
        """
        Aktualisiert den Snapshot eines Agents.

        Args:
            agent_name: Name des Agents
            data: Aktuelle Agent-Daten
        """
        with self._lock:
            if agent_name in self.agent_snapshots:
                self.agent_snapshots[agent_name].update(data)
                self.agent_snapshots[agent_name]["last_update"] = datetime.now().isoformat()

    # AENDERUNG 31.01.2026: Status-Update fuer Parallel-Fix Tracking
    def update_agent_status(self, agent_name: str, status_data: Dict[str, Any]) -> None:
        """
        Aktualisiert den Status eines Agents (speziell fuer Parallel-Fix).

        Diese Methode wird vom ParallelFixer verwendet um Fortschritt zu tracken.

        Args:
            agent_name: Name des Agents (z.B. "parallel_fixer", "fix")
            status_data: Status-Daten mit:
                - status: "idle", "running", "completed", "error"
                - current_file: Aktuell bearbeitete Datei
                - progress: Fortschritt in Prozent (0-100)
                - message: Status-Nachricht
                - files_fixed: Liste korrigierter Dateien
                - files_failed: Liste fehlgeschlagener Dateien
        """
        with self._lock:
            # Initialisiere Snapshot falls noetig
            if agent_name not in self.agent_snapshots:
                self.agent_snapshots[agent_name] = {}

            self.agent_snapshots[agent_name].update(status_data)
            self.agent_snapshots[agent_name]["last_update"] = datetime.now().isoformat()

            # Aktiv-Status basierend auf "status" setzen
            is_active = status_data.get("status") == "running"
            self.current_session["active_agents"][agent_name] = is_active
            self.current_session["last_update"] = datetime.now().isoformat()

            # Log bei wichtigen Status-Aenderungen
            status = status_data.get("status", "unknown")
            if status in ["running", "completed", "error"]:
                message = status_data.get("message", "")
                self._add_log(agent_name, f"Status_{status}", message)

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
        # ÄNDERUNG 29.01.2026: Log-Zugriff reentrant absichern
        with self._lock:
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

    def get_logs(self, limit: int = 100, offset: int = 0) -> tuple:
        """
        Gibt die letzten N Logs zurueck.

        Args:
            limit: Maximale Anzahl Logs
            offset: Start-Offset

        Returns:
            Liste von Log-Eintraegen
        """
        # ÄNDERUNG 29.01.2026: Atomare Rückgabe von Logs + Total
        with self._lock:
            logs_list = list(self.logs)
            total = len(logs_list)
            start = max(0, total - limit - offset)
            end = total - offset if offset > 0 else total
            return logs_list[start:end], total

    def restore_from_library(self, project_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Stellt eine Session aus Library-Daten wieder her.

        Args:
            project_data: Projektdaten aus der Library

        Returns:
            Wiederhergestellte Session-Info
        """
        with self._lock:
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

    # =========================================================================
    # DISCOVERY BRIEFING - ÄNDERUNG 29.01.2026
    # =========================================================================

    def set_discovery_briefing(self, briefing: Dict[str, Any]) -> None:
        """
        Speichert das Discovery-Briefing fuer Agent-Kontext.

        Args:
            briefing: Das Briefing-Objekt aus der Discovery Session
        """
        with self._lock:
            self.discovery_briefing = briefing
            self._add_log("System", "DiscoveryBriefing",
                          f"Briefing gespeichert: {briefing.get('projectName', 'unbenannt')}")
            logger.info(f"Discovery Briefing gespeichert: {briefing.get('projectName')}")

    def get_discovery_briefing(self) -> Optional[Dict[str, Any]]:
        """
        Gibt das aktuelle Discovery-Briefing zurueck.

        Returns:
            Das gespeicherte Briefing oder None
        """
        with self._lock:
            if self.discovery_briefing is None:
                return None
            return deepcopy(self.discovery_briefing)

    def get_briefing_context_for_agent(self) -> str:
        """
        Generiert einen Kontext-String aus dem Briefing fuer Agent-System-Prompts.

        Returns:
            Formatierter Briefing-Kontext oder leerer String
        """
        with self._lock:
            if not self.discovery_briefing:
                return ""
            b = deepcopy(self.discovery_briefing)
        tech = b.get("techRequirements", {})
        agents = b.get("agents", [])
        answers = b.get("answers", [])

        context = f"""
## PROJEKTBRIEFING (aus Discovery Session)

**Projektziel:** {b.get('goal', 'Nicht definiert')}

**Technische Anforderungen:**
- Sprache: {tech.get('language', 'auto')}
- Deployment: {tech.get('deployment', 'local')}

**Beteiligte Agenten:** {', '.join(agents)}

**Wichtige Entscheidungen:**
"""

        for answer in answers:
            if not answer.get('skipped', False):
                agent = answer.get('agent', 'Unbekannt')
                values = answer.get('selectedValues', [])
                custom = answer.get('customText', '')
                if values or custom:
                    context += f"- {agent}: {', '.join(values) if values else custom}\n"

        open_points = b.get('openPoints', [])
        if open_points:
            context += "\n**Offene Punkte:**\n"
            for point in open_points:
                context += f"- {point}\n"

        return context

    def reset(self) -> None:
        """Setzt die Session komplett zurueck."""
        with self._lock:
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
            # ÄNDERUNG 29.01.2026: Auch Briefing zuruecksetzen
            self.discovery_briefing = None
            logger.info("Session zurueckgesetzt")


def get_session_manager() -> SessionManager:
    """
    Gibt die Singleton-Instanz des SessionManagers zurueck.

    Returns:
        SessionManager Instanz
    """
    # ÄNDERUNG 29.01.2026: Singleton bleibt aktiv durch __new__-Implementierung
    # Rueckgabe liefert weiterhin die geteilte Instanz
    return SessionManager()
