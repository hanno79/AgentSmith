# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 14.02.2026
Version: 1.0
Beschreibung: Tests fuer dev_loop_external_review.py — External Bureau Review (CodeRabbit).
              Prueft run_external_review() Skip-Bedingungen, Finding-Verarbeitung,
              Feedback-Formatierung und Exception-Handling.
              _run_async_review wird vollstaendig gemockt (kein echtes async).
"""

import os
import sys
import pytest
from unittest.mock import MagicMock, patch

# Projekt-Root zum Python-Path hinzufuegen
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.dev_loop_external_review import run_external_review


# ===== Hilfsfunktionen fuer Mocks =====

def _make_manager(ext_enabled=True, cr_enabled=True, mode="advisory", skip_on_error=True):
    """Erstellt einen Mock-Manager mit konfigurierbaren External-Bureau-Einstellungen."""
    m = MagicMock()
    m.config = {
        "external_specialists": {
            "enabled": ext_enabled,
            "coderabbit": {
                "enabled": cr_enabled,
                "mode": mode,
                "skip_on_error": skip_on_error,
            }
        }
    }
    m.project_path = "/tmp/test"
    m.current_code = "const x = 1;"
    m.tech_blueprint = {}
    return m


def _make_finding(severity="low", description="Test Finding", file="app.js",
                  line=1, fix="", category="style"):
    """Erstellt ein Mock-Finding-Objekt (simuliert SpecialistResult.finding)."""
    f = MagicMock()
    f.severity = severity
    f.description = description
    f.file = file
    f.line = line
    f.fix = fix
    f.category = category
    return f


def _make_result(success=True, findings=None, error=""):
    """Erstellt ein Mock-SpecialistResult mit konfigurierbarem Erfolg und Findings."""
    r = MagicMock()
    r.success = success
    r.findings = findings or []
    r.error = error
    return r


# ===========================================================================
# 1. Tests fuer Skip-Bedingungen (kein Review wird ausgefuehrt)
# ===========================================================================

class TestRunExternalReviewSkips:
    """Tests fuer Faelle in denen das External Review uebersprungen wird."""

    def test_kein_external_bureau_attribut(self):
        """Ohne external_bureau Attribut wird (True, '', []) zurueckgegeben."""
        # spec=[] erzeugt einen Mock OHNE dynamische Attribute
        # hasattr(manager, 'external_bureau') gibt dann False zurueck
        manager = MagicMock(spec=[])

        passed, feedback, findings = run_external_review(manager, ["app.js"])
        assert passed is True, "Erwartet: passed=True bei fehlendem external_bureau"
        assert feedback == "", "Erwartet: leerer Feedback-Text"
        assert findings == [], "Erwartet: leere Findings-Liste"

    def test_external_bureau_none(self):
        """Bei external_bureau=None wird (True, '', []) zurueckgegeben."""
        manager = _make_manager()
        manager.external_bureau = None

        passed, feedback, findings = run_external_review(manager, ["app.js"])
        assert passed is True, "Erwartet: passed=True bei external_bureau=None"
        assert feedback == "", "Erwartet: leerer Feedback-Text"
        assert findings == [], "Erwartet: leere Findings-Liste"

    def test_external_specialists_disabled(self):
        """Bei external_specialists.enabled=False wird uebersprungen."""
        manager = _make_manager(ext_enabled=False)

        passed, feedback, findings = run_external_review(manager, ["app.js"])
        assert passed is True, "Erwartet: passed=True bei deaktiviertem External Bureau"
        assert feedback == "", "Erwartet: leerer Feedback-Text"
        assert findings == [], "Erwartet: leere Findings-Liste"

    def test_coderabbit_disabled(self):
        """Bei coderabbit.enabled=False wird uebersprungen."""
        manager = _make_manager(cr_enabled=False)

        passed, feedback, findings = run_external_review(manager, ["app.js"])
        assert passed is True, "Erwartet: passed=True bei deaktiviertem CodeRabbit"
        assert feedback == "", "Erwartet: leerer Feedback-Text"
        assert findings == [], "Erwartet: leere Findings-Liste"

    def test_external_specialists_fehlt_in_config(self):
        """Ohne external_specialists Key in config wird uebersprungen."""
        manager = _make_manager()
        manager.config = {}  # Kein external_specialists Key

        passed, feedback, findings = run_external_review(manager, ["app.js"])
        assert passed is True, "Erwartet: passed=True bei fehlendem config-Key"
        assert feedback == "", "Erwartet: leerer Feedback-Text"
        assert findings == [], "Erwartet: leere Findings-Liste"


# ===========================================================================
# 2. Tests fuer Finding-Verarbeitung und Pass/Fail Logik
# ===========================================================================

class TestRunExternalReviewFindings:
    """Tests fuer die Verarbeitung von Findings und Pass/Fail Entscheidung."""

    @patch("backend.dev_loop_external_review._run_async_review")
    def test_advisory_mode_mit_findings_passed_true(self, mock_async):
        """Im Advisory-Mode: passed=True auch bei Findings vorhanden."""
        manager = _make_manager(mode="advisory")
        finding = _make_finding(severity="high", description="Problem gefunden")
        mock_async.return_value = [_make_result(success=True, findings=[finding])]

        passed, feedback, findings = run_external_review(manager, ["app.js"])

        assert passed is True, "Erwartet: passed=True im Advisory-Mode trotz HIGH Finding"
        assert len(findings) == 1, "Erwartet: 1 Finding in der Liste"
        assert feedback != "", "Erwartet: Feedback-Text nicht leer bei vorhandenen Findings"

    @patch("backend.dev_loop_external_review._run_async_review")
    def test_blocking_mode_mit_high_finding_failed(self, mock_async):
        """Im Blocking-Mode: passed=False bei HIGH Finding."""
        manager = _make_manager(mode="blocking")
        finding = _make_finding(severity="high", description="Schwerwiegender Fehler")
        mock_async.return_value = [_make_result(success=True, findings=[finding])]

        passed, feedback, findings = run_external_review(manager, ["app.js"])

        assert passed is False, "Erwartet: passed=False im Blocking-Mode mit HIGH Finding"
        assert len(findings) == 1, "Erwartet: 1 Finding"

    @patch("backend.dev_loop_external_review._run_async_review")
    def test_blocking_mode_mit_critical_finding_failed(self, mock_async):
        """Im Blocking-Mode: passed=False bei CRITICAL Finding."""
        manager = _make_manager(mode="blocking")
        finding = _make_finding(severity="critical", description="Kritischer Fehler")
        mock_async.return_value = [_make_result(success=True, findings=[finding])]

        passed, feedback, findings = run_external_review(manager, ["app.js"])

        assert passed is False, "Erwartet: passed=False im Blocking-Mode mit CRITICAL Finding"

    @patch("backend.dev_loop_external_review._run_async_review")
    def test_blocking_mode_ohne_high_critical_passed(self, mock_async):
        """Im Blocking-Mode: passed=True wenn nur LOW/MEDIUM Findings."""
        manager = _make_manager(mode="blocking")
        low_finding = _make_finding(severity="low", description="Kleiner Hinweis")
        medium_finding = _make_finding(severity="medium", description="Mittlerer Hinweis")
        mock_async.return_value = [_make_result(
            success=True, findings=[low_finding, medium_finding]
        )]

        passed, feedback, findings = run_external_review(manager, ["app.js"])

        assert passed is True, "Erwartet: passed=True im Blocking-Mode ohne HIGH/CRITICAL"
        assert len(findings) == 2, "Erwartet: 2 Findings in der Liste"

    @patch("backend.dev_loop_external_review._run_async_review")
    def test_keine_findings_leerer_feedback(self, mock_async):
        """Ohne Findings ist der Feedback-Text leer und passed=True."""
        manager = _make_manager(mode="blocking")
        mock_async.return_value = [_make_result(success=True, findings=[])]

        passed, feedback, findings = run_external_review(manager, ["app.js"])

        assert passed is True, "Erwartet: passed=True ohne Findings"
        assert feedback == "", "Erwartet: leerer Feedback-Text ohne Findings"
        assert findings == [], "Erwartet: leere Findings-Liste"

    @patch("backend.dev_loop_external_review._run_async_review")
    def test_result_success_false_ignoriert_findings(self, mock_async):
        """Bei result.success=False werden Findings des Results uebersprungen."""
        manager = _make_manager(mode="blocking")
        finding = _make_finding(severity="critical", description="Wird ignoriert")
        # success=False → Findings werden nicht verarbeitet
        mock_async.return_value = [_make_result(success=False, findings=[finding],
                                                error="Specialist Fehler")]

        passed, feedback, findings = run_external_review(manager, ["app.js"])

        assert passed is True, "Erwartet: passed=True da fehlgeschlagener Specialist uebersprungen"
        assert findings == [], "Erwartet: leere Findings-Liste bei success=False"
        assert feedback == "", "Erwartet: leerer Feedback-Text bei success=False"

    @patch("backend.dev_loop_external_review._run_async_review")
    def test_gemischte_results_nur_erfolgreiche_verarbeitet(self, mock_async):
        """Nur Findings aus erfolgreichen Results werden verarbeitet."""
        manager = _make_manager(mode="advisory")
        good_finding = _make_finding(severity="low", description="Valides Finding")
        bad_finding = _make_finding(severity="critical", description="Ignoriert")

        mock_async.return_value = [
            _make_result(success=True, findings=[good_finding]),
            _make_result(success=False, findings=[bad_finding], error="Fehler"),
        ]

        passed, feedback, findings = run_external_review(manager, ["app.js"])

        assert len(findings) == 1, "Erwartet: nur 1 Finding aus dem erfolgreichen Result"
        assert findings[0]["description"] == "Valides Finding", (
            "Erwartet: Finding aus dem erfolgreichen Result"
        )

    @patch("backend.dev_loop_external_review._run_async_review")
    def test_mehrere_findings_alle_gesammelt(self, mock_async):
        """Mehrere Findings aus einem Result werden alle gesammelt."""
        manager = _make_manager(mode="advisory")
        findings_in = [
            _make_finding(severity="low", description="Finding 1", file="a.js"),
            _make_finding(severity="medium", description="Finding 2", file="b.js"),
            _make_finding(severity="high", description="Finding 3", file="c.js"),
        ]
        mock_async.return_value = [_make_result(success=True, findings=findings_in)]

        passed, feedback, findings = run_external_review(manager, ["a.js"])

        assert len(findings) == 3, "Erwartet: 3 Findings gesammelt"


# ===========================================================================
# 3. Tests fuer Exception-Handling
# ===========================================================================

class TestRunExternalReviewExceptions:
    """Tests fuer das Exception-Handling in run_external_review."""

    @patch("backend.dev_loop_external_review._run_async_review")
    def test_exception_mit_skip_on_error_true(self, mock_async):
        """Bei Exception und skip_on_error=True wird (True, '', []) zurueckgegeben."""
        manager = _make_manager(skip_on_error=True)
        mock_async.side_effect = RuntimeError("Verbindungsfehler")

        passed, feedback, findings = run_external_review(manager, ["app.js"])

        assert passed is True, "Erwartet: passed=True bei skip_on_error=True"
        assert feedback == "", "Erwartet: leerer Feedback-Text bei skip_on_error=True"
        assert findings == [], "Erwartet: leere Findings-Liste bei skip_on_error=True"

    @patch("backend.dev_loop_external_review._run_async_review")
    def test_exception_mit_skip_on_error_false(self, mock_async):
        """Bei Exception und skip_on_error=False wird (False, error_msg, []) zurueckgegeben."""
        manager = _make_manager(skip_on_error=False)
        mock_async.side_effect = RuntimeError("Verbindungsfehler")

        passed, feedback, findings = run_external_review(manager, ["app.js"])

        assert passed is False, "Erwartet: passed=False bei skip_on_error=False"
        assert "Verbindungsfehler" in feedback, (
            "Erwartet: Fehlermeldung im Feedback-Text enthalten"
        )
        assert "[CodeRabbit]" in feedback, (
            "Erwartet: [CodeRabbit] Prefix im Fehler-Feedback"
        )
        assert findings == [], "Erwartet: leere Findings-Liste bei Exception"

    @patch("backend.dev_loop_external_review._run_async_review")
    def test_exception_timeout_skip(self, mock_async):
        """TimeoutError mit skip_on_error=True wird uebersprungen."""
        manager = _make_manager(skip_on_error=True)
        mock_async.side_effect = TimeoutError("Timeout nach 120s")

        passed, feedback, findings = run_external_review(manager, ["app.js"])

        assert passed is True, "Erwartet: passed=True bei TimeoutError mit skip"
        assert feedback == "", "Erwartet: leerer Feedback-Text"


# ===========================================================================
# 4. Tests fuer Feedback-Formatierung
# ===========================================================================

class TestFeedbackFormat:
    """Tests fuer das korrekte Format der Feedback-Zeilen."""

    @patch("backend.dev_loop_external_review._run_async_review")
    def test_feedback_format_mit_datei_und_fix(self, mock_async):
        """Feedback-Zeile enthaelt [CodeRabbit], [DATEI:xxx], description, FIX und SEVERITY."""
        manager = _make_manager(mode="advisory")
        finding = _make_finding(
            severity="medium",
            description="Variable nicht verwendet",
            file="utils.js",
            line=42,
            fix="Variable entfernen oder verwenden",
            category="lint"
        )
        mock_async.return_value = [_make_result(success=True, findings=[finding])]

        passed, feedback, findings = run_external_review(manager, ["utils.js"])

        # Feedback-Format pruefen
        assert "[CodeRabbit]" in feedback, "Erwartet: [CodeRabbit] Prefix"
        assert "[DATEI:utils.js]" in feedback, "Erwartet: [DATEI:utils.js] Marker"
        assert "Variable nicht verwendet" in feedback, "Erwartet: Description im Feedback"
        assert "FIX: Variable entfernen oder verwenden" in feedback, "Erwartet: FIX-Hinweis"
        assert "SEVERITY: MEDIUM" in feedback, "Erwartet: SEVERITY in Grossbuchstaben"

    @patch("backend.dev_loop_external_review._run_async_review")
    def test_feedback_format_ohne_fix(self, mock_async):
        """Ohne Fix-Hinweis fehlt der FIX-Teil in der Feedback-Zeile."""
        manager = _make_manager(mode="advisory")
        finding = _make_finding(
            severity="low",
            description="Typo in Kommentar",
            file="main.js",
            fix="",  # Kein Fix-Hinweis
        )
        mock_async.return_value = [_make_result(success=True, findings=[finding])]

        passed, feedback, findings = run_external_review(manager, ["main.js"])

        assert "FIX:" not in feedback, "Erwartet: Kein FIX-Abschnitt bei leerem fix"
        assert "SEVERITY: LOW" in feedback, "Erwartet: SEVERITY trotzdem vorhanden"

    @patch("backend.dev_loop_external_review._run_async_review")
    def test_feedback_format_ohne_datei(self, mock_async):
        """Ohne Datei-Angabe fehlt der [DATEI:xxx] Marker."""
        manager = _make_manager(mode="advisory")
        finding = _make_finding(
            severity="low",
            description="Allgemeiner Hinweis",
            file="",  # Keine Datei
        )
        mock_async.return_value = [_make_result(success=True, findings=[finding])]

        passed, feedback, findings = run_external_review(manager, ["app.js"])

        assert "[DATEI:" not in feedback, "Erwartet: Kein [DATEI:] Marker bei leerer Datei"
        assert "[CodeRabbit]" in feedback, "Erwartet: [CodeRabbit] Prefix ist immer vorhanden"

    @patch("backend.dev_loop_external_review._run_async_review")
    def test_mehrere_findings_mehrzeiliger_feedback(self, mock_async):
        """Mehrere Findings erzeugen mehrzeiligen Feedback-Text mit Zeilenumbruch."""
        manager = _make_manager(mode="advisory")
        f1 = _make_finding(severity="low", description="Finding eins", file="a.js")
        f2 = _make_finding(severity="high", description="Finding zwei", file="b.js")
        mock_async.return_value = [_make_result(success=True, findings=[f1, f2])]

        passed, feedback, findings = run_external_review(manager, ["a.js", "b.js"])

        lines = feedback.strip().split("\n")
        assert len(lines) == 2, f"Erwartet: 2 Zeilen im Feedback, erhalten: {len(lines)}"
        assert "[DATEI:a.js]" in lines[0], "Erwartet: Erste Zeile referenziert a.js"
        assert "[DATEI:b.js]" in lines[1], "Erwartet: Zweite Zeile referenziert b.js"

    @patch("backend.dev_loop_external_review._run_async_review")
    def test_severity_wird_uppercase_gespeichert(self, mock_async):
        """Severity wird im Finding-Dict lowercase und im Feedback uppercase angezeigt."""
        manager = _make_manager(mode="advisory")
        finding = _make_finding(severity="Medium", description="Gemischte Schreibweise")
        mock_async.return_value = [_make_result(success=True, findings=[finding])]

        passed, feedback, findings = run_external_review(manager, ["app.js"])

        # Im findings-Dict wird severity lowercase gespeichert
        assert findings[0]["severity"] == "medium", (
            "Erwartet: severity lowercase im Dict"
        )
        # Im Feedback wird SEVERITY uppercase angezeigt
        assert "SEVERITY: MEDIUM" in feedback, "Erwartet: SEVERITY uppercase im Feedback"


# ===========================================================================
# 5. Tests fuer Context-Aufbau und _run_async_review Aufruf
# ===========================================================================

class TestContextAufbau:
    """Tests fuer den korrekten Aufbau des Context-Dicts."""

    @patch("backend.dev_loop_external_review._run_async_review")
    def test_context_enthaelt_project_path(self, mock_async):
        """Das Context-Dict enthaelt den project_path des Managers."""
        manager = _make_manager()
        mock_async.return_value = []

        run_external_review(manager, ["app.js"])

        # Pruefe den context-Parameter des Aufrufs
        call_args = mock_async.call_args
        context = call_args[0][1]  # Zweites positionales Argument
        assert context["project_path"] == "/tmp/test", (
            "Erwartet: project_path aus Manager"
        )

    @patch("backend.dev_loop_external_review._run_async_review")
    def test_context_files_filtert_none_werte(self, mock_async):
        """None-Werte in created_files werden herausgefiltert."""
        manager = _make_manager()
        mock_async.return_value = []

        run_external_review(manager, ["app.js", None, "", "lib.js"])

        context = mock_async.call_args[0][1]
        assert None not in context["files"], "Erwartet: Keine None-Werte in files"
        assert "" not in context["files"], "Erwartet: Keine leeren Strings in files"
        assert context["files"] == ["app.js", "lib.js"], (
            "Erwartet: Nur gueltige Dateinamen"
        )

    @patch("backend.dev_loop_external_review._run_async_review")
    def test_context_code_truncation(self, mock_async):
        """current_code wird auf 10000 Zeichen begrenzt."""
        manager = _make_manager()
        manager.current_code = "x" * 20000
        mock_async.return_value = []

        run_external_review(manager, ["app.js"])

        context = mock_async.call_args[0][1]
        assert len(context["code"]) == 10000, (
            "Erwartet: Code auf 10000 Zeichen begrenzt"
        )

    @patch("backend.dev_loop_external_review._run_async_review")
    def test_context_bei_none_created_files(self, mock_async):
        """Bei created_files=None wird eine leere Liste uebergeben."""
        manager = _make_manager()
        mock_async.return_value = []

        run_external_review(manager, None)

        context = mock_async.call_args[0][1]
        assert context["files"] == [], "Erwartet: Leere files-Liste bei None-Input"

    @patch("backend.dev_loop_external_review._run_async_review")
    def test_ui_log_und_worker_status_aufgerufen(self, mock_async):
        """_ui_log und _update_worker_status werden korrekt aufgerufen."""
        manager = _make_manager()
        mock_async.return_value = [_make_result(success=True, findings=[])]

        run_external_review(manager, ["app.js"])

        # Start-Aufrufe pruefen
        manager._ui_log.assert_any_call(
            "CodeRabbit", "Start", "External Bureau Review gestartet..."
        )
        manager._update_worker_status.assert_any_call(
            "external_bureau", "working", "CodeRabbit Review", "coderabbit-cli"
        )
        # Ende: Worker auf idle
        manager._update_worker_status.assert_any_call("external_bureau", "idle")
