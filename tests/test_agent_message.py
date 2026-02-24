# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 14.02.2026
Version: 1.0
Beschreibung: Unit Tests fuer backend/agent_message.py - AgentMessage Dataclass,
              Serialisierung, Validierung und Factory-Funktionen.
"""

import os
import sys
import json
import pytest

# Projekt-Root zum Python-Path hinzufuegen
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.agent_message import (
    AgentMessage,
    create_help_needed,
    create_task_message,
    create_result_message,
    create_error_message,
    create_question_message,
)


# =========================================================================
# Tests fuer AgentMessage Dataclass
# =========================================================================
class TestAgentMessage:
    """Tests fuer die AgentMessage Dataclass."""

    def test_pflichtfelder_werden_gesetzt(self):
        """Pflichtfelder agent, event und message werden korrekt gesetzt."""
        msg = AgentMessage(agent="Coder", event="CodeOutput", message="Test-Code")
        assert msg.agent == "Coder"
        assert msg.event == "CodeOutput"
        assert msg.message == "Test-Code"

    def test_standardwerte_fuer_optionale_felder(self):
        """Optionale Felder haben korrekte Standardwerte."""
        msg = AgentMessage(agent="A", event="E", message="M")
        assert msg.message_type == "STATUS"
        assert msg.priority == "normal"
        assert msg.receiver is None
        assert msg.parent_message_id is None
        assert msg.project_id is None
        assert msg.context == {}
        assert msg.blocking is False
        assert msg.action_required is None

    def test_message_id_wird_automatisch_generiert(self):
        """Jede Nachricht bekommt eine eindeutige message_id."""
        msg1 = AgentMessage(agent="A", event="E", message="M")
        msg2 = AgentMessage(agent="A", event="E", message="M")
        assert msg1.message_id != msg2.message_id
        assert len(msg1.message_id) == 12

    def test_timestamp_wird_automatisch_gesetzt(self):
        """Timestamp wird automatisch als ISO-Format gesetzt."""
        msg = AgentMessage(agent="A", event="E", message="M")
        assert msg.timestamp is not None
        assert "T" in msg.timestamp  # ISO-Format enthaelt T

    def test_alle_felder_explizit_setzbar(self):
        """Alle Felder koennen explizit gesetzt werden."""
        msg = AgentMessage(
            agent="Security",
            event="ALERT",
            message="Sicherheitsproblem",
            message_id="custom-id-12",
            timestamp="2026-02-14T10:00:00",
            message_type="ERROR",
            priority="critical",
            receiver="Orchestrator",
            parent_message_id="parent-123",
            project_id="proj-456",
            context={"severity": "high"},
            blocking=True,
            action_required="security_review"
        )
        assert msg.agent == "Security"
        assert msg.message_id == "custom-id-12"
        assert msg.message_type == "ERROR"
        assert msg.priority == "critical"
        assert msg.receiver == "Orchestrator"
        assert msg.parent_message_id == "parent-123"
        assert msg.project_id == "proj-456"
        assert msg.context == {"severity": "high"}
        assert msg.blocking is True
        assert msg.action_required == "security_review"

    def test_context_default_ist_eigene_instanz(self):
        """Jede Nachricht bekommt eine eigene context-Dict-Instanz."""
        msg1 = AgentMessage(agent="A", event="E", message="M")
        msg2 = AgentMessage(agent="A", event="E", message="M")
        msg1.context["key"] = "val"
        assert "key" not in msg2.context


# =========================================================================
# Tests fuer Serialisierung (to_dict, to_json, to_legacy)
# =========================================================================
class TestAgentMessageSerialisierung:
    """Tests fuer Serialisierungsmethoden."""

    def test_to_dict_enthaelt_alle_felder(self):
        """to_dict() gibt ein Dictionary mit allen Feldern zurueck."""
        msg = AgentMessage(agent="Coder", event="Status", message="OK")
        d = msg.to_dict()
        erwartete_keys = {
            "agent", "event", "message", "message_id", "timestamp",
            "message_type", "priority", "receiver", "parent_message_id",
            "project_id", "context", "blocking", "action_required"
        }
        assert set(d.keys()) == erwartete_keys

    def test_to_dict_werte_stimmen(self):
        """to_dict() gibt die korrekten Werte zurueck."""
        msg = AgentMessage(
            agent="Tester",
            event="TestResult",
            message="Alle Tests bestanden",
            priority="high",
            project_id="test-proj"
        )
        d = msg.to_dict()
        assert d["agent"] == "Tester"
        assert d["event"] == "TestResult"
        assert d["message"] == "Alle Tests bestanden"
        assert d["priority"] == "high"
        assert d["project_id"] == "test-proj"

    def test_to_json_ist_valides_json(self):
        """to_json() liefert einen gueltigen JSON-String."""
        msg = AgentMessage(agent="A", event="E", message="M")
        json_str = msg.to_json()
        parsed = json.loads(json_str)
        assert parsed["agent"] == "A"
        assert parsed["event"] == "E"
        assert parsed["message"] == "M"

    def test_to_json_unicode_sonderzeichen(self):
        """to_json() behandelt Unicode/Umlaute korrekt (ensure_ascii=False)."""
        msg = AgentMessage(agent="A", event="E", message="Aenderung mit Umlauten: aeu")
        json_str = msg.to_json()
        # ensure_ascii=False bedeutet Umlaute bleiben erhalten
        assert "Umlauten" in json_str

    def test_to_legacy_gibt_tuple_zurueck(self):
        """to_legacy() gibt (agent, event, message) als Tuple zurueck."""
        msg = AgentMessage(agent="Reviewer", event="Review", message="Feedback")
        legacy = msg.to_legacy()
        assert isinstance(legacy, tuple)
        assert len(legacy) == 3
        assert legacy == ("Reviewer", "Review", "Feedback")

    def test_to_dict_roundtrip(self):
        """to_dict() und zurueck ergibt konsistente Daten."""
        original = AgentMessage(
            agent="Coder", event="Output", message="Code",
            priority="high", blocking=True, context={"key": "val"}
        )
        d = original.to_dict()
        # Erstelle neue Nachricht aus dict (nur Pflichtfelder + bekannte)
        recreated = AgentMessage(
            agent=d["agent"], event=d["event"], message=d["message"],
            message_id=d["message_id"], timestamp=d["timestamp"],
            message_type=d["message_type"], priority=d["priority"],
            receiver=d["receiver"], parent_message_id=d["parent_message_id"],
            project_id=d["project_id"], context=d["context"],
            blocking=d["blocking"], action_required=d["action_required"]
        )
        assert recreated.to_dict() == original.to_dict()


# =========================================================================
# Tests fuer create_help_needed Factory
# =========================================================================
class TestCreateHelpNeeded:
    """Tests fuer die create_help_needed Factory-Funktion."""

    def test_grundstruktur(self):
        """create_help_needed erzeugt korrekte HELP_NEEDED Nachricht."""
        msg = create_help_needed(agent="Security", reason="critical_vuln")
        assert msg.agent == "Security"
        assert msg.event == "HELP_NEEDED"
        assert msg.message_type == "HELP_NEEDED"
        assert msg.blocking is True
        assert msg.priority == "high"

    def test_reason_in_message_json(self):
        """reason wird als JSON in message kodiert."""
        msg = create_help_needed(agent="A", reason="test_reason")
        payload = json.loads(msg.message)
        assert payload["reason"] == "test_reason"

    def test_action_required_default(self):
        """Standard action_required ist manual_review."""
        msg = create_help_needed(agent="A", reason="r")
        assert msg.action_required == "manual_review"
        payload = json.loads(msg.message)
        assert payload["action_required"] == "manual_review"

    def test_custom_action_required(self):
        """Benutzerdefinierte action_required wird uebernommen."""
        msg = create_help_needed(agent="A", reason="r", action_required="security_review")
        assert msg.action_required == "security_review"

    def test_context_wird_uebernommen(self):
        """Kontext-Daten werden in context und message gespeichert."""
        ctx = {"count": 5, "severity": "critical"}
        msg = create_help_needed(agent="A", reason="r", context=ctx)
        assert msg.context == ctx
        payload = json.loads(msg.message)
        assert payload["context"]["count"] == 5

    def test_none_context_wird_zu_leerem_dict(self):
        """None als context wird zu leerem Dict."""
        msg = create_help_needed(agent="A", reason="r", context=None)
        assert msg.context == {}

    def test_project_id_wird_gesetzt(self):
        """project_id wird korrekt durchgereicht."""
        msg = create_help_needed(agent="A", reason="r", project_id="proj-123")
        assert msg.project_id == "proj-123"

    def test_custom_priority(self):
        """Benutzerdefinierte Prioritaet wird uebernommen."""
        msg = create_help_needed(agent="A", reason="r", priority="critical")
        assert msg.priority == "critical"

    def test_legacy_tuple_format(self):
        """to_legacy() liefert korrektes Tuple fuer HELP_NEEDED."""
        msg = create_help_needed(agent="Security", reason="vuln")
        agent, event, message = msg.to_legacy()
        assert agent == "Security"
        assert event == "HELP_NEEDED"
        # message ist JSON-String
        assert json.loads(message)["reason"] == "vuln"


# =========================================================================
# Tests fuer create_task_message Factory
# =========================================================================
class TestCreateTaskMessage:
    """Tests fuer die create_task_message Factory-Funktion."""

    def test_grundstruktur(self):
        """create_task_message erzeugt TASK Nachricht."""
        msg = create_task_message(
            sender="Orchestrator",
            receiver="Coder",
            task_description="Erstelle app/page.js"
        )
        assert msg.agent == "Orchestrator"
        assert msg.event == "TASK"
        assert msg.message == "Erstelle app/page.js"
        assert msg.message_type == "TASK"
        assert msg.receiver == "Coder"

    def test_default_priority_normal(self):
        """Standard-Prioritaet ist normal."""
        msg = create_task_message(sender="O", receiver="C", task_description="T")
        assert msg.priority == "normal"

    def test_custom_priority(self):
        """Benutzerdefinierte Prioritaet wird uebernommen."""
        msg = create_task_message(sender="O", receiver="C", task_description="T", priority="high")
        assert msg.priority == "high"

    def test_context_und_project_id(self):
        """Kontext und project_id werden durchgereicht."""
        ctx = {"file": "app/page.js"}
        msg = create_task_message(
            sender="O", receiver="C", task_description="T",
            context=ctx, project_id="p-1"
        )
        assert msg.context == ctx
        assert msg.project_id == "p-1"

    def test_none_context_wird_zu_leerem_dict(self):
        """None als context wird zu leerem Dict."""
        msg = create_task_message(sender="O", receiver="C", task_description="T", context=None)
        assert msg.context == {}


# =========================================================================
# Tests fuer create_result_message Factory
# =========================================================================
class TestCreateResultMessage:
    """Tests fuer die create_result_message Factory-Funktion."""

    def test_grundstruktur(self):
        """create_result_message erzeugt RESULT Nachricht."""
        msg = create_result_message(agent="Coder", result="Code generiert")
        assert msg.agent == "Coder"
        assert msg.event == "RESULT"
        assert msg.message == "Code generiert"
        assert msg.message_type == "RESULT"

    def test_success_flag_default_true(self):
        """Standard-Success ist True und wird im context gespeichert."""
        msg = create_result_message(agent="A", result="R")
        assert msg.context["success"] is True

    def test_success_flag_false(self):
        """success=False wird korrekt gespeichert."""
        msg = create_result_message(agent="A", result="R", success=False)
        assert msg.context["success"] is False

    def test_context_merge_mit_success(self):
        """Bestehender context wird mit success-Flag gemergt."""
        ctx = {"lines": 42}
        msg = create_result_message(agent="A", result="R", context=ctx)
        assert msg.context["lines"] == 42
        assert msg.context["success"] is True

    def test_parent_message_id(self):
        """parent_message_id wird korrekt gesetzt."""
        msg = create_result_message(
            agent="A", result="R", parent_message_id="parent-1"
        )
        assert msg.parent_message_id == "parent-1"

    def test_priority_ist_normal(self):
        """Prioritaet ist immer normal."""
        msg = create_result_message(agent="A", result="R")
        assert msg.priority == "normal"


# =========================================================================
# Tests fuer create_error_message Factory
# =========================================================================
class TestCreateErrorMessage:
    """Tests fuer die create_error_message Factory-Funktion."""

    def test_grundstruktur(self):
        """create_error_message erzeugt ERROR Nachricht."""
        msg = create_error_message(agent="Coder", error="Syntax-Fehler")
        assert msg.agent == "Coder"
        assert msg.event == "ERROR"
        assert msg.message == "Syntax-Fehler"
        assert msg.message_type == "ERROR"

    def test_default_severity_error(self):
        """Standard-Severity ist error mit Prioritaet high."""
        msg = create_error_message(agent="A", error="E")
        assert msg.context["severity"] == "error"
        assert msg.priority == "high"

    def test_severity_warning_mapping(self):
        """warning-Severity wird auf normal-Prioritaet gemappt."""
        msg = create_error_message(agent="A", error="E", severity="warning")
        assert msg.context["severity"] == "warning"
        assert msg.priority == "normal"

    def test_severity_critical_mapping(self):
        """critical-Severity wird auf critical-Prioritaet gemappt."""
        msg = create_error_message(agent="A", error="E", severity="critical")
        assert msg.context["severity"] == "critical"
        assert msg.priority == "critical"

    def test_context_merge(self):
        """Bestehender context wird mit severity gemergt."""
        ctx = {"stack_trace": "line 42"}
        msg = create_error_message(agent="A", error="E", context=ctx)
        assert msg.context["stack_trace"] == "line 42"
        assert msg.context["severity"] == "error"

    def test_project_id(self):
        """project_id wird durchgereicht."""
        msg = create_error_message(agent="A", error="E", project_id="p-1")
        assert msg.project_id == "p-1"


# =========================================================================
# Tests fuer create_question_message Factory
# =========================================================================
class TestCreateQuestionMessage:
    """Tests fuer die create_question_message Factory-Funktion."""

    def test_grundstruktur(self):
        """create_question_message erzeugt QUESTION Nachricht."""
        options = [{"id": "A", "text": "Option A", "recommended": True}]
        msg = create_question_message(agent="Planner", question="Welches Framework?", options=options)
        assert msg.agent == "Planner"
        assert msg.event == "QUESTION"
        assert msg.message == "Welches Framework?"
        assert msg.message_type == "QUESTION"

    def test_blocking_default_true(self):
        """Standard-blocking ist True."""
        options = [{"id": "A", "text": "A"}]
        msg = create_question_message(agent="A", question="Q", options=options)
        assert msg.blocking is True
        assert msg.priority == "high"
        assert msg.action_required == "answer_required"

    def test_blocking_false(self):
        """blocking=False setzt Prioritaet auf normal."""
        options = [{"id": "A", "text": "A"}]
        msg = create_question_message(agent="A", question="Q", options=options, blocking=False)
        assert msg.blocking is False
        assert msg.priority == "normal"
        assert msg.action_required is None

    def test_options_im_context(self):
        """Optionen werden im context gespeichert."""
        options = [
            {"id": "A", "text": "React", "recommended": True},
            {"id": "B", "text": "Vue", "recommended": False}
        ]
        msg = create_question_message(agent="A", question="Q", options=options)
        assert msg.context["options"] == options
        assert len(msg.context["options"]) == 2

    def test_escalate_to_human(self):
        """escalate_to_human wird im context gespeichert."""
        options = [{"id": "A", "text": "A"}]
        msg = create_question_message(agent="A", question="Q", options=options, escalate_to_human=True)
        assert msg.context["escalate_to_human"] is True

    def test_timeout_action_default(self):
        """Standard timeout_action ist use_recommended."""
        options = [{"id": "A", "text": "A"}]
        msg = create_question_message(agent="A", question="Q", options=options)
        assert msg.context["timeout_action"] == "use_recommended"

    def test_custom_timeout_action(self):
        """Benutzerdefinierte timeout_action wird uebernommen."""
        options = [{"id": "A", "text": "A"}]
        msg = create_question_message(agent="A", question="Q", options=options, timeout_action="skip")
        assert msg.context["timeout_action"] == "skip"

    def test_project_id_wird_gesetzt(self):
        """project_id wird durchgereicht."""
        options = [{"id": "A", "text": "A"}]
        msg = create_question_message(agent="A", question="Q", options=options, project_id="p-1")
        assert msg.project_id == "p-1"

    def test_context_merge_mit_optionen(self):
        """Bestehender context wird mit options/escalation gemergt."""
        options = [{"id": "A", "text": "A"}]
        ctx = {"extra": "data"}
        msg = create_question_message(agent="A", question="Q", options=options, context=ctx)
        assert msg.context["extra"] == "data"
        assert "options" in msg.context
