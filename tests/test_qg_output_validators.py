# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 14.02.2026
Version: 1.0
Beschreibung: Tests fuer backend/qg_output_validators.py —
              Review, Security, Final und AgentMessage Validierung.
"""

import os
import sys
import pytest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.qg_output_validators import (
    validate_review,
    validate_security,
    validate_final,
    validate_agent_message,
)
from backend.validation_result import ValidationResult


# =========================================================================
# TestValidateReview
# =========================================================================

class TestValidateReview:
    """Tests fuer validate_review()."""

    def test_leerer_review_output_failed(self):
        """Leerer Review-Output ist ungueltig."""
        result = validate_review("", "code", {})
        assert result.passed is False
        assert any("leer" in i.lower() or "kurz" in i.lower() for i in result.issues)

    def test_zu_kurzer_review_output(self):
        """Review unter 20 Zeichen ist ungueltig."""
        result = validate_review("OK gut", "code", {})
        assert result.passed is False

    def test_none_review_output(self):
        """None als Review ist ungueltig."""
        result = validate_review(None, "code", {})
        assert result.passed is False

    def test_gueltiger_review_mit_code_bezug(self):
        """Review mit Code-Bezug und Verdict besteht."""
        review = "Der Code implementiert die Funktion korrekt. Approved."
        result = validate_review(review, "def foo(): pass", {})
        assert result.passed is True
        assert result.score > 0.5

    def test_review_ohne_code_bezug_warnung(self):
        """Review ohne Code-bezogene Keywords erhaelt Warnung."""
        review = "Alles sieht gut aus, die Aufgabe ist erledigt. Genehmigt und fertig."
        result = validate_review(review, "def foo(): pass", {})
        assert any("Bezug" in w for w in result.warnings)

    def test_review_ohne_verdict_warnung(self):
        """Review ohne Verdict erhaelt Warnung."""
        review = "Der Code hat eine Funktion die Berechnungen durchfuehrt."
        result = validate_review(review, "def foo(): pass", {})
        assert any("Verdict" in w for w in result.warnings)

    def test_ablehnungs_review_ohne_gruende_warnung(self):
        """Abgelehnt ohne Gruende erhaelt Warnung."""
        review = "Der Code wird abgelehnt. Die Implementierung ist nicht ausreichend."
        result = validate_review(review, "def foo(): pass", {})
        assert any("Gründe" in w for w in result.warnings)

    def test_ablehnungs_review_mit_gruenden_ok(self):
        """Abgelehnt mit Gruenden hat keine Ablehnungs-Warnung."""
        review = "Der Code wird abgelehnt. Problem: Die Funktion hat einen Fehler bei der Berechnung."
        result = validate_review(review, "def foo(): pass", {})
        # Keine "nennt keine konkreten Gruende" Warnung
        assert not any("Gründe" in w for w in result.warnings)

    def test_score_bereich(self):
        """Score ist immer zwischen 0 und 1."""
        result = validate_review("x", "code", {})
        assert 0.0 <= result.score <= 1.0

    def test_details_enthalten_checked(self):
        """Details enthalten die durchgefuehrten Pruefungen."""
        review = "Gut Code Funktion OK approved bestanden."
        result = validate_review(review, "def foo(): pass", {})
        assert "review_completeness" in result.details.get("checked", [])
        assert "verdict_present" in result.details.get("checked", [])


# =========================================================================
# TestValidateSecurity
# =========================================================================

class TestValidateSecurity:
    """Tests fuer validate_security()."""

    def test_keine_vulnerabilities_ok(self):
        """Keine Vulnerabilities = bestanden."""
        result = validate_security([])
        assert result.passed is True
        assert result.score == 1.0

    def test_critical_vulnerability_blockiert(self):
        """CRITICAL Vulnerability blockiert."""
        vulns = [{"severity": "critical", "description": "SQL Injection"}]
        result = validate_security(vulns)
        assert result.passed is False
        assert any("CRITICAL" in i for i in result.issues)

    def test_high_vulnerability_blockiert(self):
        """HIGH Vulnerability blockiert."""
        vulns = [{"severity": "high", "description": "XSS"}]
        result = validate_security(vulns, severity_threshold="high")
        assert result.passed is False

    def test_low_vulnerability_nur_warnung(self):
        """LOW Vulnerability unter default-Threshold ist nur Warnung."""
        vulns = [{"severity": "low", "description": "Info Leak"}]
        result = validate_security(vulns, severity_threshold="high")
        assert result.passed is True
        assert len(result.warnings) > 0

    def test_info_vulnerability_nur_warnung(self):
        """INFO Vulnerability ist nur Warnung."""
        vulns = [{"severity": "info", "description": "Version sichtbar"}]
        result = validate_security(vulns)
        assert result.passed is True

    def test_medium_bei_high_threshold(self):
        """MEDIUM bei threshold='high' ist Warnung, nicht Issue."""
        vulns = [{"severity": "medium", "description": "CSRF"}]
        result = validate_security(vulns, severity_threshold="high")
        assert result.passed is True

    def test_mehrere_severities(self):
        """Mehrere Severities werden korrekt gruppiert."""
        vulns = [
            {"severity": "critical", "description": "SQLi"},
            {"severity": "high", "description": "XSS"},
            {"severity": "low", "description": "Info"},
        ]
        result = validate_security(vulns)
        assert result.passed is False
        details = result.details.get("vulnerabilities_by_severity", {})
        assert details.get("critical") == 1
        assert details.get("high") == 1
        assert details.get("low") == 1

    def test_score_sinkt_bei_critical(self):
        """Score sinkt stark bei CRITICAL."""
        vulns = [{"severity": "critical", "description": "Fehler"}]
        result = validate_security(vulns)
        assert result.score < 0.7

    def test_score_sinkt_weniger_bei_low(self):
        """Score sinkt wenig bei LOW."""
        vulns = [{"severity": "low", "description": "Minor"}]
        result = validate_security(vulns)
        assert result.score > 0.9

    def test_unbekannte_severity_wird_ignoriert(self):
        """Unbekannte Severity wird nicht in by_severity aufgenommen."""
        vulns = [{"severity": "unknown", "description": "Test"}]
        result = validate_security(vulns)
        assert result.passed is True


# =========================================================================
# TestValidateFinal
# =========================================================================

class TestValidateFinal:
    """Tests fuer validate_final()."""

    def test_alles_ok_besteht(self):
        """Alle Pruefungen bestanden = passed."""
        result = validate_final(
            code="x" * 100,
            tests_passed=True,
            review_passed=True,
            security_passed=True,
            blueprint={},
            code_validator_func=None
        )
        assert result.passed is True

    def test_leerer_code_failed(self):
        """Kein Code = nicht bestanden."""
        result = validate_final(
            code="",
            tests_passed=True,
            review_passed=True,
            security_passed=True,
            blueprint={},
            code_validator_func=None
        )
        assert result.passed is False
        assert any("unvollständig" in i.lower() or "kein" in i.lower() for i in result.issues)

    def test_tests_fehlgeschlagen(self):
        """Fehlgeschlagene Tests = nicht bestanden."""
        result = validate_final(
            code="x" * 100,
            tests_passed=False,
            review_passed=True,
            security_passed=True,
            blueprint={},
            code_validator_func=None
        )
        assert result.passed is False
        assert any("Tests" in i for i in result.issues)

    def test_review_fehlgeschlagen_warnung(self):
        """Fehlgeschlagenes Review ist nur Warnung, kein Issue."""
        result = validate_final(
            code="x" * 100,
            tests_passed=True,
            review_passed=False,
            security_passed=True,
            blueprint={},
            code_validator_func=None
        )
        assert result.passed is True
        assert any("Review" in w for w in result.warnings)

    def test_security_fehlgeschlagen(self):
        """Fehlgeschlagene Security = nicht bestanden."""
        result = validate_final(
            code="x" * 100,
            tests_passed=True,
            review_passed=True,
            security_passed=False,
            blueprint={},
            code_validator_func=None
        )
        assert result.passed is False
        assert any("Security" in i for i in result.issues)

    def test_code_validator_func_wird_aufgerufen(self):
        """code_validator_func wird aufgerufen und Ergebnis integriert."""
        mock_validator = MagicMock(return_value=ValidationResult(
            passed=False,
            issues=["Code-Fehler"],
            warnings=["Code-Warnung"],
            score=0.5
        ))
        result = validate_final(
            code="x" * 100,
            tests_passed=True,
            review_passed=True,
            security_passed=True,
            blueprint={"key": "val"},
            code_validator_func=mock_validator
        )
        mock_validator.assert_called_once()
        assert "Code-Fehler" in result.issues
        assert "Code-Warnung" in result.warnings

    def test_code_validator_none_kein_fehler(self):
        """None als code_validator_func verursacht keinen Fehler."""
        result = validate_final(
            code="x" * 100,
            tests_passed=True,
            review_passed=True,
            security_passed=True,
            blueprint={},
            code_validator_func=None
        )
        assert result.passed is True

    def test_details_component_status(self):
        """Details enthalten component_status Dict."""
        result = validate_final(
            code="x" * 100,
            tests_passed=True,
            review_passed=False,
            security_passed=True,
            blueprint={},
            code_validator_func=None
        )
        status = result.details.get("component_status", {})
        assert status.get("tests") is True
        assert status.get("review") is False
        assert status.get("security") is True

    def test_score_bereich(self):
        """Score ist immer zwischen 0 und 1."""
        result = validate_final("", False, False, False, {}, None)
        assert 0.0 <= result.score <= 1.0


# =========================================================================
# TestValidateAgentMessage
# =========================================================================

class TestValidateAgentMessage:
    """Tests fuer validate_agent_message()."""

    def test_gueltige_task_nachricht(self):
        """Gueltige TASK-Nachricht besteht."""
        msg = {
            "type": "TASK",
            "agent": "Coder",
            "timestamp": "2026-02-14T10:00:00",
            "content": "Erstelle Login"
        }
        result = validate_agent_message(msg, "TASK")
        assert result.passed is True

    def test_fehlende_pflichtfelder(self):
        """Fehlende Pflichtfelder werden als Issues gemeldet."""
        msg = {"content": "Test"}
        result = validate_agent_message(msg, "TASK")
        assert result.passed is False
        assert any("type" in i for i in result.issues)
        assert any("agent" in i for i in result.issues)
        assert any("timestamp" in i for i in result.issues)

    def test_falscher_typ(self):
        """Falscher Typ wird als Issue gemeldet."""
        msg = {"type": "RESULT", "agent": "A", "timestamp": "T"}
        result = validate_agent_message(msg, "TASK")
        assert result.passed is False
        assert any("Typ" in i for i in result.issues)

    def test_task_ohne_content(self):
        """TASK ohne content ist Issue."""
        msg = {"type": "TASK", "agent": "A", "timestamp": "T"}
        result = validate_agent_message(msg, "TASK")
        assert result.passed is False

    def test_result_ohne_result_feld(self):
        """RESULT ohne result-Feld ist Issue."""
        msg = {"type": "RESULT", "agent": "A", "timestamp": "T"}
        result = validate_agent_message(msg, "RESULT")
        assert result.passed is False

    def test_result_ohne_status_warnung(self):
        """RESULT ohne status ist Warnung."""
        msg = {"type": "RESULT", "agent": "A", "timestamp": "T", "result": "OK"}
        result = validate_agent_message(msg, "RESULT")
        assert result.passed is True
        assert any("status" in w.lower() for w in result.warnings)

    def test_question_ohne_question_feld(self):
        """QUESTION ohne question-Feld ist Issue."""
        msg = {"type": "QUESTION", "agent": "A", "timestamp": "T"}
        result = validate_agent_message(msg, "QUESTION")
        assert result.passed is False

    def test_question_ohne_target_warnung(self):
        """QUESTION ohne target ist Warnung."""
        msg = {"type": "QUESTION", "agent": "A", "timestamp": "T", "question": "Wie?"}
        result = validate_agent_message(msg, "QUESTION")
        assert result.passed is True
        assert any("target" in w.lower() for w in result.warnings)

    def test_status_nachricht_gueltig(self):
        """Gueltige STATUS-Nachricht besteht."""
        msg = {"type": "STATUS", "agent": "A", "timestamp": "T", "status": "working"}
        result = validate_agent_message(msg, "STATUS")
        assert result.passed is True

    def test_status_unbekannter_wert_warnung(self):
        """Unbekannter Status-Wert erhaelt Warnung."""
        msg = {"type": "STATUS", "agent": "A", "timestamp": "T", "status": "confused"}
        result = validate_agent_message(msg, "STATUS")
        assert any("Unbekannter Status" in w for w in result.warnings)

    def test_error_nachricht_gueltig(self):
        """Gueltige ERROR-Nachricht besteht."""
        msg = {"type": "ERROR", "agent": "A", "timestamp": "T",
               "error": "Timeout", "severity": "high"}
        result = validate_agent_message(msg, "ERROR")
        assert result.passed is True

    def test_error_ohne_error_feld(self):
        """ERROR ohne error-Feld ist Issue."""
        msg = {"type": "ERROR", "agent": "A", "timestamp": "T"}
        result = validate_agent_message(msg, "ERROR")
        assert result.passed is False

    def test_error_ohne_severity_warnung(self):
        """ERROR ohne severity ist Warnung."""
        msg = {"type": "ERROR", "agent": "A", "timestamp": "T", "error": "Fehler"}
        result = validate_agent_message(msg, "ERROR")
        assert result.passed is True
        assert any("severity" in w.lower() for w in result.warnings)

    @pytest.mark.parametrize("status", ["working", "waiting", "completed", "failed", "blocked"])
    def test_alle_gueltigen_status_werte(self, status):
        """Alle VALID_AGENT_STATUSES werden akzeptiert."""
        msg = {"type": "STATUS", "agent": "A", "timestamp": "T", "status": status}
        result = validate_agent_message(msg, "STATUS")
        assert not any("Unbekannter Status" in w for w in result.warnings)

    def test_score_bereich(self):
        """Score ist immer zwischen 0 und 1."""
        msg = {}
        result = validate_agent_message(msg, "TASK")
        assert 0.0 <= result.score <= 1.0
