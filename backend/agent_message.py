"""
Author: rahn
Datum: 30.01.2026
Version: 1.0
Beschreibung: Formale Message-Klasse gemäß Kommunikationsprotokoll v1.0.
              Definiert einheitliche Struktur für Agent-Kommunikation.
"""

import uuid
import json
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Literal

# Typ-Definitionen gemäß Kommunikationsprotokoll
MessageType = Literal["TASK", "RESULT", "QUESTION", "STATUS", "ERROR", "HELP_NEEDED"]
Priority = Literal["low", "normal", "high", "critical"]


@dataclass
class AgentMessage:
    """
    Standardisierte Agent-Nachricht gemäß Kommunikationsprotokoll v1.0.

    Pflichtfelder (Rückwärtskompatibel mit bestehendem System):
        - agent: Absender-Agent Name
        - event: Event-Typ (z.B. "CodeOutput", "Status")
        - message: Payload (String oder JSON)

    Protokoll-Felder (optional, für erweiterte Funktionalität):
        - message_id: Eindeutige Nachricht-ID
        - timestamp: ISO-Zeitstempel
        - message_type: TASK/RESULT/QUESTION/STATUS/ERROR/HELP_NEEDED
        - priority: low/normal/high/critical
        - receiver: Ziel-Agent oder "broadcast"
        - parent_message_id: Referenz auf vorherige Nachricht
        - project_id: Projekt-Referenz
        - context: Zusätzliche Kontext-Daten
        - blocking: Blockiert Agent auf Antwort?
        - action_required: Erforderliche Aktion bei HELP_NEEDED
    """
    # Pflichtfelder (Rückwärtskompatibel)
    agent: str
    event: str
    message: str

    # Protokoll-Felder (optional)
    message_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    message_type: MessageType = "STATUS"
    priority: Priority = "normal"

    # Kontext-Felder
    receiver: Optional[str] = None
    parent_message_id: Optional[str] = None
    project_id: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)

    # HELP_NEEDED spezifisch
    blocking: bool = False
    action_required: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Konvertiert zu Dictionary für WebSocket/JSON-Übertragung."""
        return {
            "agent": self.agent,
            "event": self.event,
            "message": self.message,
            "message_id": self.message_id,
            "timestamp": self.timestamp,
            "message_type": self.message_type,
            "priority": self.priority,
            "receiver": self.receiver,
            "parent_message_id": self.parent_message_id,
            "project_id": self.project_id,
            "context": self.context,
            "blocking": self.blocking,
            "action_required": self.action_required
        }

    def to_legacy(self) -> tuple:
        """
        Rückwärtskompatibel: Gibt (agent, event, message) Tuple zurück.
        Für bestehende _ui_log() Aufrufe.
        """
        return (self.agent, self.event, self.message)

    def to_json(self) -> str:
        """Konvertiert zu JSON-String."""
        return json.dumps(self.to_dict(), ensure_ascii=False)


def create_help_needed(
    agent: str,
    reason: str,
    context: Dict[str, Any] = None,
    action_required: str = "manual_review",
    priority: Priority = "high",
    project_id: str = None
) -> AgentMessage:
    """
    Factory-Funktion für HELP_NEEDED Events.

    Erstellt eine standardisierte HELP_NEEDED Nachricht wenn ein Agent
    auf ein Problem stößt und Unterstützung benötigt.

    Args:
        agent: Der blockierte Agent (z.B. "Security", "Tester")
        reason: Grund der Blockierung (z.B. "critical_vulnerabilities", "no_unit_tests")
        context: Zusätzliche Informationen zum Problem
        action_required: Erforderliche Aktion (z.B. "security_review_required")
        priority: Priorität (default: high)
        project_id: Projekt-ID für Zuordnung

    Returns:
        AgentMessage mit event="HELP_NEEDED" und blocking=True

    Example:
        >>> msg = create_help_needed(
        ...     agent="Security",
        ...     reason="critical_vulnerabilities",
        ...     context={"count": 3, "severity": "critical"},
        ...     action_required="security_review_required"
        ... )
        >>> msg.to_legacy()
        ('Security', 'HELP_NEEDED', '{"reason": "critical_vulnerabilities", ...}')
    """
    message_content = {
        "reason": reason,
        "action_required": action_required,
        "context": context or {}
    }

    return AgentMessage(
        agent=agent,
        event="HELP_NEEDED",
        message=json.dumps(message_content, ensure_ascii=False),
        message_type="HELP_NEEDED",
        priority=priority,
        blocking=True,
        action_required=action_required,
        context=context or {},
        project_id=project_id
    )


def create_task_message(
    sender: str,
    receiver: str,
    task_description: str,
    context: Dict[str, Any] = None,
    priority: Priority = "normal",
    project_id: str = None
) -> AgentMessage:
    """
    Factory-Funktion für TASK Messages.

    Args:
        sender: Absender-Agent (meist "Orchestrator")
        receiver: Ziel-Agent
        task_description: Aufgabenbeschreibung
        context: Zusätzlicher Kontext
        priority: Priorität
        project_id: Projekt-ID

    Returns:
        AgentMessage mit message_type="TASK"
    """
    return AgentMessage(
        agent=sender,
        event="TASK",
        message=task_description,
        message_type="TASK",
        priority=priority,
        receiver=receiver,
        context=context or {},
        project_id=project_id
    )


def create_result_message(
    agent: str,
    result: str,
    success: bool = True,
    context: Dict[str, Any] = None,
    parent_message_id: str = None,
    project_id: str = None
) -> AgentMessage:
    """
    Factory-Funktion für RESULT Messages.

    Args:
        agent: Agent der das Ergebnis liefert
        result: Ergebnis-Inhalt
        success: War die Aufgabe erfolgreich?
        context: Zusätzliche Ergebnis-Daten
        parent_message_id: Referenz auf ursprüngliche TASK Message
        project_id: Projekt-ID

    Returns:
        AgentMessage mit message_type="RESULT"
    """
    ctx = context or {}
    ctx["success"] = success

    return AgentMessage(
        agent=agent,
        event="RESULT",
        message=result,
        message_type="RESULT",
        priority="normal",
        context=ctx,
        parent_message_id=parent_message_id,
        project_id=project_id
    )


def create_error_message(
    agent: str,
    error: str,
    severity: Literal["warning", "error", "critical"] = "error",
    context: Dict[str, Any] = None,
    project_id: str = None
) -> AgentMessage:
    """
    Factory-Funktion für ERROR Messages.

    Args:
        agent: Agent der den Fehler meldet
        error: Fehlerbeschreibung
        severity: warning/error/critical
        context: Zusätzliche Fehler-Details
        project_id: Projekt-ID

    Returns:
        AgentMessage mit message_type="ERROR"
    """
    # Severity zu Priority mappen
    priority_map = {"warning": "normal", "error": "high", "critical": "critical"}

    ctx = context or {}
    ctx["severity"] = severity

    return AgentMessage(
        agent=agent,
        event="ERROR",
        message=error,
        message_type="ERROR",
        priority=priority_map.get(severity, "high"),
        context=ctx,
        project_id=project_id
    )


# ÄNDERUNG 31.01.2026: QUESTION Factory-Funktion gemaess Kommunikationsprotokoll
def create_question_message(
    agent: str,
    question: str,
    options: List[Dict[str, str]],
    blocking: bool = True,
    escalate_to_human: bool = False,
    timeout_action: str = "use_recommended",
    context: Dict[str, Any] = None,
    project_id: str = None
) -> AgentMessage:
    """
    Erstellt eine QUESTION Nachricht fuer Rueckfragen an Orchestrator oder Mensch.

    Gemaess Kommunikationsprotokoll v1.0 fuer strukturierte Rueckfragen
    wenn ein Agent eine Entscheidung benoetigt.

    Args:
        agent: Der fragende Agent
        question: Die Frage als String
        options: Liste von Antwortoptionen [{"id": "A", "text": "...", "recommended": True/False}]
        blocking: Ob die Frage den Workflow blockiert (Default: True)
        escalate_to_human: Ob die Frage direkt an den Menschen eskaliert werden soll
        timeout_action: Aktion bei Timeout ("use_recommended", "skip", "error")
        context: Zusaetzlicher Kontext
        project_id: Projekt-Referenz

    Returns:
        AgentMessage mit QUESTION Typ
    """
    ctx = context or {}
    ctx.update({
        "options": options,
        "escalate_to_human": escalate_to_human,
        "timeout_action": timeout_action
    })

    return AgentMessage(
        agent=agent,
        event="QUESTION",
        message=question,
        message_type="QUESTION",
        priority="high" if blocking else "normal",
        blocking=blocking,
        action_required="answer_required" if blocking else None,
        context=ctx,
        project_id=project_id
    )
