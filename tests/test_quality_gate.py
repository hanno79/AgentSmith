# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 01.02.2026
Version: 1.0
Beschreibung: Unit Tests für QualityGate - Anforderungsextraktion, Validierung, Scoring.

              Tests validieren:
              - Anforderungs-Extraktion aus Benutzer-Zielen
              - TechStack-Validierung
              - Security-Validierung mit Severity-Schwellwerten
              - Review-Validierung
              - Agent-Message-Validierung
              - Finale Projekt-Validierung
"""

import pytest
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.quality_gate import QualityGate, ValidationResult
from backend.qg_requirements import extract_requirements, get_requirements_summary
from backend.qg_output_validators import (
    validate_security,
    validate_review,
    validate_agent_message
)


# =========================================================================
# Fixtures
# =========================================================================

@pytest.fixture
def sample_blueprint():
    """Standard TechStack Blueprint für Tests."""
    return {
        "language": "python",
        "framework": "flask",
        "database": "sqlite",
        "ui_type": "webapp",
        "project_type": "flask_webapp"
    }


@pytest.fixture
def sample_code():
    """Beispiel-Code für Tests."""
    return '''
from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///app.db"
db = SQLAlchemy(app)

@app.route("/")
def index():
    return render_template("index.html")
'''


# =========================================================================
# Test: Anforderungs-Extraktion
# =========================================================================

class TestRequirementsExtraction:
    """Tests für extract_requirements Funktion."""

    def test_extract_database_sqlite(self):
        """SQLite-Datenbank wird erkannt."""
        reqs = extract_requirements("Erstelle eine App mit SQLite Datenbank")
        assert reqs.get("database") == "sqlite"

    def test_extract_database_mysql(self):
        """MySQL-Datenbank wird erkannt."""
        reqs = extract_requirements("Webapp mit MySQL Backend")
        assert reqs.get("database") == "mysql"

    def test_extract_database_postgresql(self):
        """PostgreSQL-Datenbank wird erkannt."""
        reqs = extract_requirements("Erstelle einen Blog mit PostgreSQL")
        # Implementierung nutzt "postgres" als Kurzform
        assert reqs.get("database") == "postgres"

    def test_extract_language_python(self):
        """Python-Sprache wird erkannt."""
        reqs = extract_requirements("Python-Webapp entwickeln")
        assert reqs.get("language") == "python"

    def test_extract_language_javascript(self):
        """JavaScript-Sprache wird erkannt."""
        reqs = extract_requirements("Eine JavaScript-Anwendung erstellen")
        assert reqs.get("language") == "javascript"

    def test_extract_framework_flask(self):
        """Flask-Framework wird erkannt."""
        reqs = extract_requirements("Flask-Webanwendung erstellen")
        assert reqs.get("framework") == "flask"

    def test_extract_framework_react(self):
        """React-Framework wird erkannt."""
        reqs = extract_requirements("React-Frontend entwickeln")
        assert reqs.get("framework") == "react"

    def test_extract_ui_type_webapp(self):
        """UI-Typ Webapp wird erkannt."""
        reqs = extract_requirements("Erstelle eine Webapp für Benutzerverwaltung")
        assert reqs.get("ui_type") == "webapp"

    def test_extract_ui_type_cli(self):
        """UI-Typ CLI wird erkannt."""
        reqs = extract_requirements("Erstelle ein CLI-Tool für Dateiverarbeitung")
        assert reqs.get("ui_type") == "cli"

    def test_extract_ui_type_api(self):
        """UI-Typ API wird erkannt."""
        reqs = extract_requirements("Erstelle eine REST-API für Produktdaten")
        assert reqs.get("ui_type") == "api"

    def test_extract_no_requirements(self):
        """Keine spezifischen Anforderungen bei vagem Ziel."""
        reqs = extract_requirements("Erstelle etwas Nützliches")
        # Sollte nicht crashen, leeres Dict ist OK
        assert isinstance(reqs, dict)

    def test_webapp_priority_over_desktop(self):
        """Webapp hat Priorität über Desktop bei gemischten Keywords."""
        reqs = extract_requirements("Eine GUI-Webapp für Browser entwickeln")
        assert reqs.get("ui_type") == "webapp"

    def test_requirements_summary_format(self):
        """get_requirements_summary gibt formatierten String zurück."""
        reqs = {"database": "sqlite", "language": "python"}
        summary = get_requirements_summary(reqs)
        assert "Datenbank: sqlite" in summary
        assert "Sprache: python" in summary

    def test_requirements_summary_empty(self):
        """get_requirements_summary bei leerem Dict."""
        summary = get_requirements_summary({})
        assert "Keine spezifischen Anforderungen" in summary


# =========================================================================
# Test: Security-Validierung
# =========================================================================

class TestSecurityValidation:
    """Tests für validate_security Funktion."""

    def test_no_vulnerabilities_passes(self):
        """Keine Vulnerabilities = bestanden."""
        result = validate_security([], severity_threshold="high")
        assert result.passed is True
        assert result.score == 1.0

    def test_critical_vulnerability_fails(self):
        """CRITICAL-Vulnerability führt zu Fehlschlag."""
        vulns = [{"severity": "critical", "description": "SQL Injection"}]
        result = validate_security(vulns, severity_threshold="critical")
        assert result.passed is False
        assert "CRITICAL" in str(result.issues)

    def test_high_vulnerability_fails(self):
        """HIGH-Vulnerability führt zu Fehlschlag bei high threshold."""
        vulns = [{"severity": "high", "description": "XSS Vulnerability"}]
        result = validate_security(vulns, severity_threshold="high")
        assert result.passed is False
        assert "HIGH" in str(result.issues)

    def test_medium_vulnerability_warns(self):
        """MEDIUM-Vulnerability gibt Warnung bei high threshold."""
        vulns = [{"severity": "medium", "description": "Weak Password Policy"}]
        result = validate_security(vulns, severity_threshold="high")
        assert result.passed is True, "Medium-Vulnerability darf bei high-Threshold nicht durchfallen"
        assert len(result.warnings) > 0, "Es muss mindestens eine Warnung für Medium-Vulnerability geben"

    def test_low_vulnerability_info_only(self):
        """LOW-Vulnerability ist nur informativ."""
        vulns = [{"severity": "low", "description": "Missing Header"}]
        result = validate_security(vulns, severity_threshold="high")
        assert result.passed is True  # Low blockiert nicht bei high threshold

    def test_multiple_vulnerabilities_aggregated(self):
        """Mehrere Vulnerabilities werden aggregiert."""
        vulns = [
            {"severity": "high", "description": "Issue 1"},
            {"severity": "high", "description": "Issue 2"},
            {"severity": "medium", "description": "Issue 3"},
        ]
        result = validate_security(vulns, severity_threshold="high")
        assert result.passed is False
        assert result.details["vulnerabilities_by_severity"]["high"] == 2
        assert result.details["vulnerabilities_by_severity"]["medium"] == 1

    def test_score_decreases_with_severity(self):
        """Score sinkt bei schwereren Vulnerabilities."""
        low_vulns = [{"severity": "low", "description": "Minor"}]
        high_vulns = [{"severity": "high", "description": "Major"}]

        low_result = validate_security(low_vulns, severity_threshold="critical")
        high_result = validate_security(high_vulns, severity_threshold="critical")

        # High sollte niedrigeren Score haben als Low
        assert high_result.score < low_result.score


# =========================================================================
# Test: Review-Validierung
# =========================================================================

class TestReviewValidation:
    """Tests für validate_review Funktion."""

    def test_empty_review_fails(self):
        """Leeres Review führt zu Fehlschlag."""
        result = validate_review("", "code here", {})
        assert result.passed is False
        assert "leer" in str(result.issues).lower()

    def test_too_short_review_fails(self):
        """Zu kurzes Review führt zu Fehlschlag."""
        result = validate_review("OK", "code here", {})
        assert result.passed is False

    def test_valid_review_passes(self):
        """Gültiges Review mit Verdict besteht."""
        review = """
        Code-Review Ergebnis:

        Die Implementierung ist korrekt. Die Funktionen wurden ordnungsgemäß implementiert.
        Alle Klassen folgen dem Single Responsibility Principle.

        Verdict: APPROVED - Der Code entspricht den Anforderungen.
        """
        result = validate_review(review, "def foo(): pass", {})
        assert result.passed is True

    def test_review_without_verdict_warns(self):
        """Review ohne Verdict gibt Warnung."""
        review = """
        Code-Review:
        Die Implementierung sieht gut aus. Die Funktionen sind korrekt.
        Es gibt keine offensichtlichen Probleme im Code.
        """
        result = validate_review(review, "def foo(): pass", {})
        # Sollte bestehen (keine Issues) aber mit Warnung
        assert result.passed is True
        assert len(result.warnings) > 0

    def test_rejection_without_reason_warns(self):
        """Ablehnung ohne Gründe gibt Warnung."""
        review = """
        Code-Review:
        Der Code wurde überprüft.
        Verdict: REJECTED
        """
        result = validate_review(review, "def foo(): pass", {})
        # Ablehnung ohne konkreten Grund sollte warnen
        assert "warnung" in str(result.warnings).lower() or len(result.warnings) > 0


# =========================================================================
# Test: Agent-Message-Validierung
# =========================================================================

class TestAgentMessageValidation:
    """Tests für validate_agent_message Funktion."""

    def test_valid_task_message(self):
        """Gültige TASK-Nachricht besteht."""
        msg = {
            "type": "TASK",
            "agent": "Coder",
            "timestamp": "2026-02-01T12:00:00",
            "content": "Generate Flask app"
        }
        result = validate_agent_message(msg, "TASK")
        assert result.passed is True

    def test_missing_required_field(self):
        """Fehlendes Pflichtfeld führt zu Fehlschlag."""
        msg = {
            "type": "TASK",
            "content": "Do something"
            # Missing: agent, timestamp
        }
        result = validate_agent_message(msg, "TASK")
        assert result.passed is False
        assert "agent" in str(result.issues)

    def test_wrong_message_type(self):
        """Falscher Nachrichtentyp führt zu Fehlschlag."""
        msg = {
            "type": "STATUS",
            "agent": "Tester",
            "timestamp": "2026-02-01T12:00:00",
            "status": "working"
        }
        result = validate_agent_message(msg, "TASK")
        assert result.passed is False
        assert "Typ" in str(result.issues)

    def test_result_message_needs_result(self):
        """RESULT-Nachricht braucht 'result' Feld."""
        msg = {
            "type": "RESULT",
            "agent": "Coder",
            "timestamp": "2026-02-01T12:00:00",
            # Missing: result
        }
        result = validate_agent_message(msg, "RESULT")
        assert result.passed is False
        assert "result" in str(result.issues)

    def test_question_message_needs_question(self):
        """QUESTION-Nachricht braucht 'question' Feld."""
        msg = {
            "type": "QUESTION",
            "agent": "Researcher",
            "timestamp": "2026-02-01T12:00:00",
            "question": "What framework should I use?"
        }
        result = validate_agent_message(msg, "QUESTION")
        assert result.passed is True

    def test_error_message_needs_error(self):
        """ERROR-Nachricht braucht 'error' Feld."""
        msg = {
            "type": "ERROR",
            "agent": "Tester",
            "timestamp": "2026-02-01T12:00:00",
            "error": "Tests failed"
        }
        result = validate_agent_message(msg, "ERROR")
        assert result.passed is True

    def test_status_message_with_valid_status(self):
        """STATUS-Nachricht mit gültigem Status."""
        msg = {
            "type": "STATUS",
            "agent": "Coder",
            "timestamp": "2026-02-01T12:00:00",
            "status": "working"
        }
        result = validate_agent_message(msg, "STATUS")
        assert result.passed is True


# =========================================================================
# Test: QualityGate Klasse Integration
# =========================================================================

class TestQualityGateIntegration:
    """Integration-Tests für QualityGate Klasse."""

    def test_initialization(self):
        """QualityGate initialisiert korrekt."""
        qg = QualityGate("Erstelle eine Flask-Webapp mit SQLite")
        assert qg.user_goal == "Erstelle eine Flask-Webapp mit SQLite"
        assert "flask" in qg.requirements.get("framework", "").lower()

    def test_validate_security_delegation(self, sample_blueprint):
        """validate_security delegiert korrekt."""
        qg = QualityGate("Test-Projekt")
        vulns = [{"severity": "high", "description": "XSS"}]
        result = qg.validate_security(vulns, severity_threshold="high")
        assert isinstance(result, ValidationResult)
        assert result.passed is False

    def test_get_requirements_summary(self):
        """get_requirements_summary gibt formatierte Zusammenfassung."""
        qg = QualityGate("Python-Flask-Webapp mit SQLite")
        summary = qg.get_requirements_summary()
        assert isinstance(summary, str)
        # Sollte erkannte Anforderungen enthalten
        assert len(summary) > 0


# =========================================================================
# Test: ValidationResult Dataclass
# =========================================================================

class TestValidationResult:
    """Tests für ValidationResult Dataclass."""

    def test_default_values(self):
        """ValidationResult hat korrekte Defaults."""
        result = ValidationResult(passed=True)
        assert result.passed is True
        assert result.issues == []
        assert result.warnings == []
        assert result.score == 1.0
        assert result.details == {}

    def test_with_issues(self):
        """ValidationResult mit Issues."""
        result = ValidationResult(
            passed=False,
            issues=["Issue 1", "Issue 2"],
            score=0.4
        )
        assert result.passed is False
        assert len(result.issues) == 2
        assert result.score == 0.4

    def test_with_all_fields(self):
        """ValidationResult mit allen Feldern."""
        result = ValidationResult(
            passed=True,
            issues=[],
            warnings=["Minor warning"],
            score=0.9,
            details={"checked": ["test1", "test2"]}
        )
        assert result.passed is True
        assert len(result.warnings) == 1
        assert "checked" in result.details


# =========================================================================
# Test: Edge Cases
# =========================================================================

class TestEdgeCases:
    """Tests für Grenzfälle."""

    def test_empty_user_goal(self):
        """Leeres Benutzer-Ziel crasht nicht."""
        qg = QualityGate("")
        assert qg.requirements is not None

    def test_unicode_in_user_goal(self):
        """Unicode im Benutzer-Ziel wird behandelt."""
        qg = QualityGate("Erstelle eine Wetter-App 🌤️ für München")
        assert isinstance(qg.requirements, dict)

    def test_very_long_user_goal(self):
        """Sehr langes Benutzer-Ziel wird behandelt."""
        long_goal = "Erstelle eine Webapp " * 100
        qg = QualityGate(long_goal)
        assert isinstance(qg.requirements, dict)

    def test_mixed_case_keywords(self):
        """Keywords werden case-insensitive erkannt."""
        reqs = extract_requirements("PYTHON Flask SQLITE")
        assert reqs.get("language") == "python"
        assert reqs.get("framework") == "flask"
        assert reqs.get("database") == "sqlite"

    def test_security_unknown_severity(self):
        """Unbekannte Severity wird als 'info' behandelt."""
        vulns = [{"severity": "unknown", "description": "Something"}]
        result = validate_security(vulns, severity_threshold="high")
        assert result.passed is True  # Unknown sollte nicht blockieren
