# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 01.02.2026
Version: 1.0
Beschreibung: Unit Tests für OrchestratorValidator - Root Cause Analyse und Modellwechsel.

              Tests validieren:
              - Coder-Output Validierung
              - Review-Output Validierung und Root Cause Erkennung
              - Security-Output Validierung
              - Modellwechsel-Entscheidung
              - Error Pattern Erkennung
"""

import pytest
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.orchestration_validator import (
    OrchestratorValidator,
    ValidationDecision,
    ValidatorAction
)


# =========================================================================
# Mock-Klassen für Tests
# =========================================================================

class MockUILogger:
    """Mock für _ui_log Methode."""
    def __init__(self):
        self.logs = []

    def _ui_log(self, agent: str, event: str, message: str):
        self.logs.append({"agent": agent, "event": event, "message": message})


class MockModelRouter:
    """Mock für ModelRouter."""
    def __init__(self):
        self.rate_limited = set()
        self.error_tried = {}

    def get_model(self, role: str) -> str:
        return f"mock-model-{role}"

    def mark_rate_limited_sync(self, model: str):
        self.rate_limited.add(model)

    def mark_error_tried(self, error_hash: str, model: str):
        key = f"{model}:{error_hash}"
        self.error_tried[key] = self.error_tried.get(key, 0) + 1


class MockManager:
    """Mock für OrchestrationManager."""
    def __init__(self):
        self._logger = MockUILogger()
        self.model_router = MockModelRouter()

    def _ui_log(self, agent: str, event: str, message: str):
        self._logger._ui_log(agent, event, message)


# =========================================================================
# Fixtures
# =========================================================================

@pytest.fixture
def validator():
    """Erstellt OrchestratorValidator mit Mocks."""
    manager = MockManager()
    config = {"max_same_error": 3}
    return OrchestratorValidator(manager, manager.model_router, config)


@pytest.fixture
def sample_code_files():
    """Beispiel Code-Dateien für Tests."""
    return {
        "app.py": '''from flask import Flask
app = Flask(__name__)

@app.route("/")
def index():
    return "Hello World"

if __name__ == "__main__":
    app.run()
''',
        "requirements.txt": "flask==3.0.0\n",
        "README.md": "# Test Project\n"
    }


@pytest.fixture
def truncated_code_files():
    """Abgeschnittene Code-Dateien."""
    return {
        "app.py": '''from flask import Flask
app = Flask(__name__)

@app.route("/")
def index():
    return render_template("'''  # Abgeschnitten!
    }


# =========================================================================
# Test: Coder-Output Validierung
# =========================================================================

class TestCoderOutputValidation:
    """Tests für validate_coder_output Methode."""

    def test_empty_code_returns_fix(self, validator):
        """Leerer Code führt zu FIX-Aktion."""
        result = validator.validate_coder_output("", {})
        assert result.action == ValidatorAction.FIX
        assert result.target_agent == "coder"
        assert len(result.issues) > 0

    def test_too_short_code_returns_fix(self, validator):
        """Zu kurzer Code führt zu FIX-Aktion."""
        result = validator.validate_coder_output("print('hi')", {})
        assert result.action == ValidatorAction.FIX
        assert "unvollständig" in result.feedback.lower() or "leer" in result.feedback.lower()

    def test_no_files_returns_fix(self, validator):
        """Keine Dateien führt zu FIX-Aktion."""
        code = "# Some long code comment that is more than 50 characters long..."
        result = validator.validate_coder_output(code, {})
        assert result.action == ValidatorAction.FIX
        assert "Dateien" in result.feedback

    def test_valid_code_proceeds(self, validator, sample_code_files):
        """Valider Code führt zu PROCEED-Aktion."""
        code = "### FILENAME: app.py\n" + sample_code_files["app.py"]
        result = validator.validate_coder_output(code, sample_code_files)
        assert result.action == ValidatorAction.PROCEED
        assert result.target_agent == "reviewer"

    def test_truncation_detected(self, validator, truncated_code_files):
        """Truncation wird erkannt und führt zu MODEL_SWITCH."""
        code = "### FILENAME: app.py\n" + truncated_code_files["app.py"]
        result = validator.validate_coder_output(code, truncated_code_files)
        assert result.action == ValidatorAction.MODEL_SWITCH
        assert result.model_switch_recommended is True
        assert "Truncation" in str(result.issues)

    def test_missing_expected_files_warns(self, validator, sample_code_files):
        """Fehlende erwartete Dateien generieren Warnung."""
        code = "### FILENAME: app.py\n" + sample_code_files["app.py"]
        result = validator.validate_coder_output(
            code, sample_code_files, expected_files=["app.py", "config.py"]
        )
        # Sollte PROCEED sein da Code OK, aber Warnung haben
        assert result.action == ValidatorAction.PROCEED
        assert any("config.py" in w for w in result.warnings)

    def test_too_few_files_warns(self, validator):
        """Weniger als 3 Dateien generiert Warnung."""
        files = {"app.py": "from flask import Flask\napp = Flask(__name__)\n# More code here..."}
        code = "### FILENAME: app.py\n" + files["app.py"]
        result = validator.validate_coder_output(code, files)
        # Warnung wegen weniger als 3 Dateien
        assert any("Nur" in w and "Dateien" in w for w in result.warnings)


# =========================================================================
# Test: Review-Output Validierung
# =========================================================================

class TestReviewOutputValidation:
    """Tests für validate_review_output Methode."""

    def test_ok_review_proceeds(self, validator, sample_code_files):
        """OK-Review führt zu PROCEED-Aktion."""
        result = validator.validate_review_output(
            review_output="Der Code sieht gut aus.",
            review_verdict="OK",
            sandbox_result="All tests passed",
            sandbox_failed=False,
            current_code="# Code",
            current_files=sample_code_files,
            current_model="mock-model"
        )
        assert result.action == ValidatorAction.PROCEED
        assert result.target_agent == "tester"

    def test_feedback_review_returns_fix(self, validator, sample_code_files):
        """FEEDBACK-Review führt zu FIX-Aktion."""
        result = validator.validate_review_output(
            review_output="Der Code hat Probleme.",
            review_verdict="FEEDBACK",
            sandbox_result="Error: SyntaxError",
            sandbox_failed=True,
            current_code="# Code",
            current_files=sample_code_files,
            current_model="mock-model"
        )
        assert result.action == ValidatorAction.FIX
        assert result.target_agent == "coder"

    def test_root_cause_detected_in_review(self, validator, sample_code_files):
        """Root Cause im Review wird erkannt."""
        review_with_root_cause = """
        Der Code funktioniert nicht.

        URSACHE: Der Import von 'flask' fehlt.
        BETROFFENE DATEIEN: app.py
        LÖSUNG: Flask muss importiert werden.
        """
        result = validator.validate_review_output(
            review_output=review_with_root_cause,
            review_verdict="FEEDBACK",
            sandbox_result="ModuleNotFoundError: No module named 'flask'",
            sandbox_failed=True,
            current_code="# Code",
            current_files=sample_code_files,
            current_model="mock-model"
        )
        # Root Cause sollte im Review erkannt werden
        assert result.root_cause is not None

    def test_missing_root_cause_orchestrator_analyzes(self, validator, sample_code_files):
        """Fehlende Root Cause wird vom Orchestrator analysiert."""
        review_without_root_cause = "Der Code geht nicht. Bitte reparieren."
        result = validator.validate_review_output(
            review_output=review_without_root_cause,
            review_verdict="FEEDBACK",
            sandbox_result="SyntaxError: invalid syntax in line 5",
            sandbox_failed=True,
            current_code="# Code",
            current_files=sample_code_files,
            current_model="mock-model"
        )
        # Orchestrator sollte selbst analysieren
        assert result.root_cause is not None
        assert "SYMPTOM" in result.root_cause or "SyntaxError" in result.root_cause

    def test_sandbox_failure_triggers_analysis(self, validator, sample_code_files):
        """Sandbox-Fehler triggert Root Cause Analyse."""
        result = validator.validate_review_output(
            review_output="OK",
            review_verdict="FEEDBACK",
            sandbox_result="ModuleNotFoundError: No module named 'nonexistent'",
            sandbox_failed=True,
            current_code="# Code",
            current_files=sample_code_files,
            current_model="mock-model"
        )
        assert result.action == ValidatorAction.FIX
        assert result.error_hash is not None


# =========================================================================
# Test: Security-Output Validierung
# =========================================================================

class TestSecurityOutputValidation:
    """Tests für validate_security_output Methode."""

    def test_no_vulnerabilities_proceeds(self, validator):
        """Keine Vulnerabilities führt zu PROCEED."""
        result = validator.validate_security_output([], "mock-model")
        assert result.action == ValidatorAction.PROCEED
        assert result.target_agent == "final"

    def test_low_severity_proceeds(self, validator):
        """Niedrige Severity führt zu PROCEED."""
        vulns = [{"severity": "low", "description": "Missing header"}]
        result = validator.validate_security_output(vulns, "mock-model")
        assert result.action == ValidatorAction.PROCEED

    def test_high_severity_returns_fix(self, validator):
        """HIGH Severity führt zu FIX."""
        vulns = [{"severity": "high", "description": "SQL Injection"}]
        result = validator.validate_security_output(vulns, "mock-model")
        assert result.action == ValidatorAction.FIX
        assert result.target_agent == "coder"
        assert len(result.issues) > 0

    def test_critical_severity_returns_fix(self, validator):
        """CRITICAL Severity führt zu FIX."""
        vulns = [{"severity": "critical", "description": "Remote Code Execution"}]
        result = validator.validate_security_output(vulns, "mock-model")
        assert result.action == ValidatorAction.FIX
        assert "kritische" in str(result.issues).lower()

    def test_multiple_vulnerabilities(self, validator):
        """Mehrere Vulnerabilities werden korrekt behandelt."""
        vulns = [
            {"severity": "high", "description": "XSS Vulnerability"},
            {"severity": "critical", "description": "SQL Injection"},
            {"severity": "medium", "description": "Weak Password"},
        ]
        result = validator.validate_security_output(vulns, "mock-model")
        assert result.action == ValidatorAction.FIX
        # Feedback sollte kritische Issues erwähnen
        assert "Security" in result.feedback or "Vulnerability" in result.feedback


# =========================================================================
# Test: Root Cause Analyse
# =========================================================================

class TestRootCauseAnalysis:
    """Tests für analyze_root_cause Methode."""

    def test_circular_import_detected(self, validator):
        """Zirkulärer Import wird erkannt."""
        error = "ImportError: cannot import name 'foo' from partially initialized module 'bar'"
        root_cause = validator.analyze_root_cause(error, {})
        assert "Zirkulär" in root_cause or "Import" in root_cause

    def test_module_not_found_detected(self, validator):
        """ModuleNotFoundError wird erkannt."""
        error = "ModuleNotFoundError: No module named 'flask'"
        root_cause = validator.analyze_root_cause(error, {})
        assert "Modul" in root_cause
        assert "LÖSUNG" in root_cause

    def test_syntax_error_detected(self, validator):
        """SyntaxError wird erkannt."""
        error = "SyntaxError: invalid syntax in line 5"
        root_cause = validator.analyze_root_cause(error, {})
        assert "Syntax" in root_cause

    def test_name_error_detected(self, validator):
        """NameError wird erkannt."""
        error = "NameError: name 'undefined_var' is not defined"
        root_cause = validator.analyze_root_cause(error, {})
        assert "Variable" in root_cause or "definiert" in root_cause

    def test_empty_error_returns_empty(self, validator):
        """Leerer Error gibt leeren String zurück."""
        root_cause = validator.analyze_root_cause("", {})
        assert root_cause == ""

    def test_affected_files_identified(self, validator, sample_code_files):
        """Betroffene Dateien werden identifiziert."""
        error = "Error in app.py: SyntaxError"
        root_cause = validator.analyze_root_cause(error, sample_code_files)
        assert "app.py" in root_cause


# =========================================================================
# Test: Modellwechsel-Entscheidung
# =========================================================================

class TestModelSwitchDecision:
    """Tests für _should_switch_model Methode."""

    def test_first_error_no_switch(self, validator):
        """Erster Fehler führt nicht zu Modellwechsel."""
        should_switch = validator._should_switch_model("coder", "error123", "model-a")
        assert should_switch is False

    def test_second_error_no_switch(self, validator):
        """Zweiter gleicher Fehler führt noch nicht zu Modellwechsel."""
        validator._should_switch_model("coder", "error123", "model-a")
        should_switch = validator._should_switch_model("coder", "error123", "model-a")
        assert should_switch is False

    def test_third_error_triggers_switch(self, validator):
        """
        Dritter gleicher Fehler triggert Modellwechsel.
        
        AENDERUNG 05.02.2026: _should_switch_model aendert nicht den State.
        _record_error_attempt muss aufgerufen werden um den Counter zu erhoehen.
        """
        # Fehler aufzeichnen (erhoeht Counter)
        validator._record_error_attempt("coder", "error123", "model-a")
        validator._record_error_attempt("coder", "error123", "model-a")
        validator._record_error_attempt("coder", "error123", "model-a")
        # Nach 3 Versuchen sollte Modellwechsel ausgeloest werden
        should_switch = validator._should_switch_model("coder", "error123", "model-a")
        assert should_switch is True

    def test_different_error_no_switch(self, validator):
        """Unterschiedliche Fehler führen nicht zu Modellwechsel."""
        # Fehler aufzeichnen
        validator._record_error_attempt("coder", "error123", "model-a")
        validator._record_error_attempt("coder", "error123", "model-a")
        # Unterschiedlicher Fehler sollte nicht zählen
        should_switch = validator._should_switch_model("coder", "error456", "model-a")
        assert should_switch is False

    def test_different_model_resets_count(self, validator):
        """Anderes Modell resettet den Zähler."""
        # Fehler mit model-a aufzeichnen
        validator._record_error_attempt("coder", "error123", "model-a")
        validator._record_error_attempt("coder", "error123", "model-a")
        # Wechsel zu model-b - sollte keinen Eintrag haben
        should_switch = validator._should_switch_model("coder", "error123", "model-b")
        assert should_switch is False  # Erster Versuch mit model-b

    def test_empty_error_hash_no_switch(self, validator):
        """Leerer Error-Hash führt nie zu Modellwechsel."""
        should_switch = validator._should_switch_model("coder", "", "model-a")
        assert should_switch is False
        should_switch = validator._should_switch_model("coder", None, "model-a")
        assert should_switch is False


# =========================================================================
# Test: Error-Tracking und Status
# =========================================================================

class TestErrorTracking:
    """Tests für Error-Tracking Funktionalität."""

    def test_get_status_empty(self, validator):
        """Status bei leerem Tracking."""
        status = validator.get_status()
        assert status["error_tracking"] == {}
        assert status["max_same_error"] == 3

    def test_get_status_with_errors(self, validator):
        """
        Status nach Error-Tracking.
        
        AENDERUNG 05.02.2026: _should_switch_model aendert nicht den State.
        _record_error_attempt muss aufgerufen werden um den Counter zu erhoehen.
        """
        validator._record_error_attempt("coder", "error123", "model-a")
        validator._record_error_attempt("reviewer", "error456", "model-b")
        status = validator.get_status()
        assert "coder" in status["error_tracking"]
        assert "reviewer" in status["error_tracking"]

    def test_mark_error_resolved(self, validator):
        """Error-Resolved löscht Tracking."""
        # Fehler aufzeichnen
        validator._record_error_attempt("coder", "error123", "model-a")
        validator._record_error_attempt("coder", "error123", "model-a")
        validator.mark_error_resolved("coder", "error123")
        status = validator.get_status()
        # Nach Resolve sollte der Eintrag weg sein
        coder_errors = status["error_tracking"].get("coder", {})
        assert not any("error123" in k for k in coder_errors.keys())


# =========================================================================
# Test: UI-Logging
# =========================================================================

class TestUILogging:
    """Tests für UI-Logging Integration."""

    def test_validate_coder_logs_analysis(self, validator, sample_code_files):
        """validate_coder_output loggt 'Analysis' Event."""
        code = "### FILENAME: app.py\n" + sample_code_files["app.py"]
        validator.validate_coder_output(code, sample_code_files)
        logs = validator.manager._logger.logs
        # Mindestens ein Analysis-Event sollte geloggt sein
        analysis_logs = [l for l in logs if l["event"] == "Analysis"]
        assert len(analysis_logs) > 0

    def test_validate_review_logs_events(self, validator, sample_code_files):
        """validate_review_output loggt Events."""
        validator.validate_review_output(
            review_output="OK",
            review_verdict="OK",
            sandbox_result="passed",
            sandbox_failed=False,
            current_code="# Code",
            current_files=sample_code_files,
            current_model="mock-model"
        )
        logs = validator.manager._logger.logs
        # Sollte mindestens Analysis und Status loggen
        events = [l["event"] for l in logs]
        assert "Analysis" in events
        assert "Status" in events

    def test_validate_security_logs_analysis(self, validator):
        """validate_security_output loggt 'Analysis' Event."""
        vulns = [{"severity": "low", "description": "Minor issue"}]
        validator.validate_security_output(vulns, "mock-model")
        logs = validator.manager._logger.logs
        analysis_logs = [l for l in logs if l["event"] == "Analysis"]
        assert len(analysis_logs) > 0


# =========================================================================
# Test: Edge Cases
# =========================================================================

class TestEdgeCases:
    """Tests für Grenzfälle."""

    def test_unicode_in_error(self, validator):
        """Unicode in Fehlermeldung wird behandelt."""
        error = "UnicodeDecodeError: 'utf-8' codec can't decode Ümläut 🔥"
        root_cause = validator.analyze_root_cause(error, {})
        assert isinstance(root_cause, str)

    def test_very_long_error(self, validator):
        """Sehr lange Fehlermeldung wird behandelt."""
        error = "Error: " + "x" * 10000
        root_cause = validator.analyze_root_cause(error, {})
        assert len(root_cause) < 2000  # Sollte gekürzt werden

    def test_none_values_handled(self, validator):
        """None-Werte werden behandelt."""
        result = validator.validate_review_output(
            review_output=None,
            review_verdict="FEEDBACK",
            sandbox_result=None,
            sandbox_failed=True,
            current_code=None,
            current_files={},
            current_model="mock-model"
        )
        # Sollte nicht crashen
        assert result is not None

    def test_empty_files_dict(self, validator):
        """Leeres Files-Dict wird behandelt."""
        result = validator.validate_coder_output(
            "Some long code content that is more than 50 chars...",
            {}
        )
        assert result.action == ValidatorAction.FIX

    def test_special_characters_in_filename(self, validator):
        """Sonderzeichen in Dateinamen werden behandelt."""
        files = {"test-file_v2.1.py": "# code\n" * 10}
        error = "Error in test-file_v2.1.py"
        affected = validator._find_affected_files(error, files)
        assert "test-file_v2.1.py" in affected

