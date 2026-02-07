# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 06.02.2026
Version: 1.0
Beschreibung: Unit Tests fuer dev_loop_feedback.py - Feedback-Builder und Modellwechsel-Logik.

              Tests validieren:
              - build_feedback(): Security-Blockade, Unit-Test-Skip, Sandbox-Fehlertypen,
                Leere-Seite-Diagnose, Reviewer-Analyse, normaler Review-Output
              - handle_model_switch(): Kein Wechsel unter Max-Attempts, Error-Hash-Wechsel,
                Rate-Limit-Wechsel, Feedback-Prepend bei Modellwechsel
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from unittest.mock import MagicMock, patch


# =========================================================================
# Hilfsfunktionen
# =========================================================================

def _create_mock_manager(tech_blueprint=None):
    """Erstellt einen Mock-Manager mit Standard-Konfiguration."""
    manager = MagicMock()
    manager.tech_blueprint = tech_blueprint or {
        "project_type": "flask_app",
        "language": "python"
    }
    manager._current_iteration = 1
    manager.config = {"mode": "test"}
    manager.model_router = MagicMock()
    manager.model_router.error_model_history = {}
    return manager


def _default_test_result(unit_status="OK", ui_status="OK"):
    """Erstellt ein Standard-Test-Result Dict."""
    return {
        "unit_tests": {"status": unit_status, "details": ""},
        "ui_tests": {"status": ui_status, "details": ""}
    }


def _create_help_needed_mock():
    """Erstellt ein Mock-Objekt das create_help_needed zurueckgibt."""
    help_obj = MagicMock()
    help_obj.to_legacy.return_value = ("Agent", "HelpNeeded", "Nachricht")
    return help_obj


# =========================================================================
# Tests fuer build_feedback()
# =========================================================================

# AENDERUNG 06.02.2026: Patch-Pfade zeigen auf backend.dev_loop_feedback
PATCH_PREFIX = "backend.dev_loop_feedback"


class TestBuildFeedback:
    """Tests fuer die build_feedback Funktion."""

    @patch(f"{PATCH_PREFIX}.format_test_feedback", return_value="")
    @patch(f"{PATCH_PREFIX}.create_help_needed")
    def test_security_vulns_blockieren(self, mock_help, mock_fmt):
        """Security-Vulnerabilities muessen das Feedback blockieren und SECURITY enthalten."""
        mock_help.return_value = _create_help_needed_mock()
        manager = _create_mock_manager()

        vulns = [
            {"severity": "critical", "description": "SQL Injection", "fix": "Prepared Statements"},
            {"severity": "high", "description": "XSS", "fix": "Input Sanitization"}
        ]
        result = self._call_build_feedback(
            manager,
            security_passed=False,
            security_rescan_vulns=vulns,
            test_result=_default_test_result()
        )

        assert "SECURITY" in result, (
            f"Erwartet: 'SECURITY' im Feedback, Erhalten: {result[:200]}"
        )
        assert "SQL Injection" in result, (
            "Erwartet: Vulnerability-Beschreibung im Feedback"
        )
        # create_help_needed muss fuer kritische Vulns aufgerufen werden
        assert mock_help.call_count >= 1, (
            "Erwartet: create_help_needed mindestens einmal aufgerufen"
        )

    @patch(f"{PATCH_PREFIX}.format_test_feedback", return_value="")
    @patch(f"{PATCH_PREFIX}.create_help_needed")
    def test_unit_test_skip_feedback(self, mock_help, mock_fmt):
        """Fehlende Unit-Tests muessen UNIT-TESTS FEHLEN Feedback erzeugen."""
        mock_help.return_value = _create_help_needed_mock()
        manager = _create_mock_manager()

        result = self._call_build_feedback(
            manager,
            sandbox_failed=False,
            test_result=_default_test_result(unit_status="SKIP")
        )

        assert "UNIT-TESTS FEHLEN" in result, (
            f"Erwartet: 'UNIT-TESTS FEHLEN' im Feedback, Erhalten: {result[:200]}"
        )

    @patch(f"{PATCH_PREFIX}.format_test_feedback", return_value="")
    @patch(f"{PATCH_PREFIX}.create_help_needed")
    def test_sandbox_syntax_fehler(self, mock_help, mock_fmt):
        """SyntaxError in Sandbox-Ausgabe muss als SYNTAX-FEHLER kategorisiert werden."""
        mock_help.return_value = _create_help_needed_mock()
        manager = _create_mock_manager()

        result = self._call_build_feedback(
            manager,
            sandbox_failed=True,
            sandbox_result="File app.py, line 10\n    SyntaxError: invalid syntax",
            test_result=_default_test_result()
        )

        assert "SYNTAX-FEHLER" in result, (
            f"Erwartet: 'SYNTAX-FEHLER' im Feedback, Erhalten: {result[:200]}"
        )

    @patch(f"{PATCH_PREFIX}.format_test_feedback", return_value="")
    @patch(f"{PATCH_PREFIX}.create_help_needed")
    def test_sandbox_runtime_fehler(self, mock_help, mock_fmt):
        """NameError in Sandbox-Ausgabe muss als LAUFZEIT-FEHLER kategorisiert werden."""
        mock_help.return_value = _create_help_needed_mock()
        manager = _create_mock_manager()

        result = self._call_build_feedback(
            manager,
            sandbox_failed=True,
            sandbox_result="NameError: name 'foo' is not defined",
            test_result=_default_test_result()
        )

        assert "LAUFZEIT-FEHLER" in result, (
            f"Erwartet: 'LAUFZEIT-FEHLER' im Feedback, Erhalten: {result[:200]}"
        )

    @patch(f"{PATCH_PREFIX}.format_test_feedback", return_value="")
    @patch(f"{PATCH_PREFIX}.create_help_needed")
    def test_sandbox_leere_seite(self, mock_help, mock_fmt):
        """'leere seite' in test_summary muss LEERE SEITE Diagnose ausloesen."""
        mock_help.return_value = _create_help_needed_mock()
        manager = _create_mock_manager()

        result = self._call_build_feedback(
            manager,
            sandbox_failed=True,
            sandbox_result="Tests fehlgeschlagen",
            test_summary="Die Seite ist eine leere Seite ohne Inhalt",
            test_result=_default_test_result()
        )

        assert "LEERE SEITE" in result, (
            f"Erwartet: 'LEERE SEITE' im Feedback, Erhalten: {result[:200]}"
        )

    @patch(f"{PATCH_PREFIX}.format_test_feedback", return_value="")
    @patch(f"{PATCH_PREFIX}.create_help_needed")
    def test_kein_fehler_gibt_review(self, mock_help, mock_fmt):
        """Ohne Fehler muss der review_output direkt zurueckgegeben werden."""
        mock_help.return_value = _create_help_needed_mock()
        manager = _create_mock_manager()
        review_text = "Code sieht gut aus, keine Probleme gefunden."

        result = self._call_build_feedback(
            manager,
            review_output=review_text,
            sandbox_failed=False,
            test_result=_default_test_result()
        )

        assert result == review_text, (
            f"Erwartet: review_output unveraendert, Erhalten: {result[:200]}"
        )

    @patch(f"{PATCH_PREFIX}.format_test_feedback", return_value="")
    @patch(f"{PATCH_PREFIX}.create_help_needed")
    def test_reviewer_analyse_bei_sandbox_fehler(self, mock_help, mock_fmt):
        """Bei Sandbox-Fehler und langem Review-Output muss REVIEWER-ANALYSE enthalten sein."""
        mock_help.return_value = _create_help_needed_mock()
        manager = _create_mock_manager()
        # Review-Output muss > 50 Zeichen sein, damit er eingebaut wird
        long_review = "A" * 60

        result = self._call_build_feedback(
            manager,
            review_output=long_review,
            sandbox_failed=True,
            sandbox_result="ImportError: No module named 'flask'",
            test_result=_default_test_result()
        )

        assert "REVIEWER-ANALYSE" in result, (
            f"Erwartet: 'REVIEWER-ANALYSE' im Feedback, Erhalten: {result[:300]}"
        )

    # Hilfsmethode um build_feedback mit Standardwerten aufzurufen
    def _call_build_feedback(
        self,
        manager,
        review_output="",
        review_verdict="FEEDBACK",
        sandbox_failed=False,
        sandbox_result="",
        test_summary="",
        test_result=None,
        security_passed=True,
        security_rescan_vulns=None
    ):
        """Wrapper fuer build_feedback mit Standardwerten."""
        from backend.dev_loop_feedback import build_feedback
        return build_feedback(
            manager=manager,
            review_output=review_output,
            review_verdict=review_verdict,
            sandbox_failed=sandbox_failed,
            sandbox_result=sandbox_result,
            test_summary=test_summary,
            test_result=test_result or _default_test_result(),
            security_passed=security_passed,
            security_rescan_vulns=security_rescan_vulns or []
        )


# =========================================================================
# Tests fuer handle_model_switch()
# =========================================================================

class TestHandleModelSwitch:
    """Tests fuer die handle_model_switch Funktion."""

    @patch(f"{PATCH_PREFIX}.init_agents")
    @patch(f"{PATCH_PREFIX}.hash_error")
    def test_kein_switch_unter_max(self, mock_hash, mock_init):
        """Unter max_model_attempts darf kein Modellwechsel stattfinden."""
        manager = _create_mock_manager()
        current_model = "gpt-4"

        model, attempt, used, fb = self._call_handle_model_switch(
            manager,
            current_coder_model=current_model,
            model_attempt=1,
            max_model_attempts=3
        )

        assert model == current_model, (
            f"Erwartet: Modell unveraendert '{current_model}', Erhalten: '{model}'"
        )
        assert attempt == 1, (
            f"Erwartet: Attempt unveraendert 1, Erhalten: {attempt}"
        )
        # hash_error und init_agents duerfen nicht aufgerufen werden
        mock_hash.assert_not_called()
        mock_init.assert_not_called()

    @patch(f"{PATCH_PREFIX}.init_agents")
    @patch(f"{PATCH_PREFIX}.hash_error", return_value="abc123")
    def test_switch_mit_error_hash(self, mock_hash, mock_init):
        """Bei Sandbox-Fehler und max Attempts muss Error-Hash-basierter Wechsel stattfinden."""
        manager = _create_mock_manager()
        new_model = "claude-3-opus"
        manager.model_router.get_model_for_error.return_value = new_model
        mock_init.return_value = {"coder": MagicMock()}

        model, attempt, used, fb = self._call_handle_model_switch(
            manager,
            current_coder_model="gpt-4",
            model_attempt=3,
            max_model_attempts=3,
            sandbox_result="NameError: name 'x' is not defined",
            sandbox_failed=True
        )

        assert model == new_model, (
            f"Erwartet: Neues Modell '{new_model}', Erhalten: '{model}'"
        )
        assert attempt == 0, (
            f"Erwartet: Attempt zurueckgesetzt auf 0, Erhalten: {attempt}"
        )
        # mark_error_tried muss aufgerufen werden
        manager.model_router.mark_error_tried.assert_called_once()
        # get_model_for_error muss mit "coder" und error_hash aufgerufen werden
        manager.model_router.get_model_for_error.assert_called_once_with("coder", "abc123")

    @patch(f"{PATCH_PREFIX}.init_agents")
    @patch(f"{PATCH_PREFIX}.hash_error", return_value="")
    def test_switch_ohne_error_hash(self, mock_hash, mock_init):
        """Ohne Sandbox-Fehler muss Rate-Limit-basierter Wechsel stattfinden."""
        manager = _create_mock_manager()
        new_model = "claude-3-sonnet"
        manager.model_router.get_model.return_value = new_model
        mock_init.return_value = {"coder": MagicMock()}

        model, attempt, used, fb = self._call_handle_model_switch(
            manager,
            current_coder_model="gpt-4",
            model_attempt=3,
            max_model_attempts=3,
            sandbox_failed=False
        )

        assert model == new_model, (
            f"Erwartet: Neues Modell '{new_model}', Erhalten: '{model}'"
        )
        # mark_rate_limited_sync muss aufgerufen werden (kein Error-Hash)
        manager.model_router.mark_rate_limited_sync.assert_called_once_with("gpt-4")
        manager.model_router.get_model.assert_called_once_with("coder")

    @patch(f"{PATCH_PREFIX}.init_agents")
    @patch(f"{PATCH_PREFIX}.hash_error", return_value="abc123")
    def test_feedback_prepend(self, mock_hash, mock_init):
        """Nach Modellwechsel muss MODELLWECHSEL-Info dem Feedback vorangestellt werden."""
        manager = _create_mock_manager()
        new_model = "claude-3-opus"
        manager.model_router.get_model_for_error.return_value = new_model
        mock_init.return_value = {"coder": MagicMock()}
        original_feedback = "LAUFZEIT-FEHLER: NameError in Zeile 5"

        _, _, _, fb = self._call_handle_model_switch(
            manager,
            current_coder_model="gpt-4",
            model_attempt=3,
            max_model_attempts=3,
            feedback=original_feedback,
            sandbox_result="NameError: name 'x' is not defined",
            sandbox_failed=True
        )

        assert "MODELLWECHSEL" in fb, (
            f"Erwartet: 'MODELLWECHSEL' im Feedback, Erhalten: {fb[:300]}"
        )
        # Original-Feedback muss am Ende erhalten bleiben (Prepend-Logik)
        assert fb.endswith(original_feedback), (
            f"Erwartet: Original-Feedback am Ende erhalten, Erhalten: {fb[-200:]}"
        )

    # Hilfsmethode um handle_model_switch mit Standardwerten aufzurufen
    def _call_handle_model_switch(
        self,
        manager,
        current_coder_model="gpt-4",
        models_used=None,
        failed_attempts_history=None,
        model_attempt=1,
        max_model_attempts=3,
        feedback="Test-Feedback",
        iteration=1,
        sandbox_result="",
        sandbox_failed=False
    ):
        """Wrapper fuer handle_model_switch mit Standardwerten."""
        from backend.dev_loop_feedback import handle_model_switch
        return handle_model_switch(
            manager=manager,
            project_rules={"rule": "test"},
            current_coder_model=current_coder_model,
            models_used=models_used if models_used is not None else [current_coder_model],
            failed_attempts_history=failed_attempts_history or [
                {"model": "gpt-4", "iteration": 1, "feedback": "Fehler aufgetreten"}
            ],
            model_attempt=model_attempt,
            max_model_attempts=max_model_attempts,
            feedback=feedback,
            iteration=iteration,
            sandbox_result=sandbox_result,
            sandbox_failed=sandbox_failed
        )
