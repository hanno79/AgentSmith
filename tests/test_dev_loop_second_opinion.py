# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 14.02.2026
Version: 1.1
Beschreibung: Tests fuer dev_loop_second_opinion.py — Vier-Augen-Prinzip Hilfsfunktionen.
              Prueft _build_second_opinion_prompt (Prompt-Aufbau, Truncation, Flags),
              _restore_primary_model (Model-Router Wiederherstellung, Error-Handling)
              und run_second_opinion_review (Integration mit gemocktem Manager).

AENDERUNG 14.02.2026 v1.1: TestRunSecondOpinionReview hinzugefuegt
- 7 Szenarien: kein Reviewer, gleiches Modell, leere Antwort, OK, FEEDBACK,
  Exception mit skip_on_error=True/False
"""

import os
import sys
import pytest
from unittest.mock import MagicMock, patch

# Projekt-Root zum Python-Path hinzufuegen
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.dev_loop_second_opinion import (
    _build_second_opinion_prompt,
    _restore_primary_model,
    run_second_opinion_review,
)


# ===== Tests fuer _build_second_opinion_prompt =====

class TestBuildSecondOpinionPrompt:
    """Tests fuer den Vier-Augen Review-Prompt Aufbau."""

    def test_vier_augen_prinzip_im_text(self):
        """Der Prompt enthaelt den Begriff 'Vier-Augen-Prinzip'."""
        result = _build_second_opinion_prompt("code", "sandbox ok", "tests ok", False)
        assert "Vier-Augen-Prinzip" in result

    def test_sandbox_failed_true_fehlgeschlagen(self):
        """Bei sandbox_failed=True steht 'FEHLGESCHLAGEN' im Prompt."""
        result = _build_second_opinion_prompt("code", "error", "tests", True)
        assert "FEHLGESCHLAGEN" in result
        assert "ERFOLGREICH" not in result

    def test_sandbox_failed_false_erfolgreich(self):
        """Bei sandbox_failed=False steht 'ERFOLGREICH' im Prompt."""
        result = _build_second_opinion_prompt("code", "ok", "tests", False)
        assert "ERFOLGREICH" in result
        assert "FEHLGESCHLAGEN" not in result

    def test_current_code_truncation_8000(self):
        """current_code wird auf maximal 8000 Zeichen gekuerzt."""
        # Verwende Zeichen das nicht im Template-Text vorkommt
        marker = "\u2588"
        langer_code = marker * 10000
        result = _build_second_opinion_prompt(langer_code, "sandbox", "tests", False)
        assert result.count(marker) == 8000

    def test_current_code_kurz_nicht_gekuerzt(self):
        """Kurzer current_code (unter 8000 Zeichen) wird nicht abgeschnitten."""
        marker = "\u2588"
        kurzer_code = marker * 500
        result = _build_second_opinion_prompt(kurzer_code, "sandbox", "tests", False)
        assert result.count(marker) == 500

    def test_sandbox_result_truncation_2000(self):
        """sandbox_result wird auf maximal 2000 Zeichen gekuerzt."""
        marker = "\u2589"
        langes_result = marker * 5000
        result = _build_second_opinion_prompt("code", langes_result, "tests", False)
        assert result.count(marker) == 2000

    def test_sandbox_result_kurz_nicht_gekuerzt(self):
        """Kurzes sandbox_result (unter 2000 Zeichen) wird nicht abgeschnitten."""
        marker = "\u2589"
        kurzes_result = marker * 500
        result = _build_second_opinion_prompt("code", kurzes_result, "tests", False)
        assert result.count(marker) == 500

    def test_test_summary_truncation_1000(self):
        """test_summary wird auf maximal 1000 Zeichen gekuerzt."""
        marker = "\u258a"
        lange_summary = marker * 3000
        result = _build_second_opinion_prompt("code", "sandbox", lange_summary, False)
        assert result.count(marker) == 1000

    def test_test_summary_kurz_nicht_gekuerzt(self):
        """Kurze test_summary (unter 1000 Zeichen) wird nicht abgeschnitten."""
        marker = "\u258a"
        kurze_summary = marker * 200
        result = _build_second_opinion_prompt("code", "sandbox", kurze_summary, False)
        assert result.count(marker) == 200

    def test_sandbox_result_none_kein_ergebnis(self):
        """sandbox_result=None ergibt 'Kein Ergebnis' im Prompt."""
        result = _build_second_opinion_prompt("code", None, "tests", False)
        assert "Kein Ergebnis" in result

    def test_sandbox_result_leer_kein_ergebnis(self):
        """sandbox_result='' (leerer String) ergibt 'Kein Ergebnis' im Prompt."""
        result = _build_second_opinion_prompt("code", "", "tests", False)
        assert "Kein Ergebnis" in result

    def test_test_summary_none_keine_tests(self):
        """test_summary=None ergibt 'Keine Tests' im Prompt."""
        result = _build_second_opinion_prompt("code", "sandbox", None, False)
        assert "Keine Tests" in result

    def test_test_summary_leer_keine_tests(self):
        """test_summary='' (leerer String) ergibt 'Keine Tests' im Prompt."""
        result = _build_second_opinion_prompt("code", "sandbox", "", False)
        assert "Keine Tests" in result

    def test_leere_strings_alle_parameter(self):
        """Alle Parameter als leere Strings fuehren zu keinem Crash."""
        result = _build_second_opinion_prompt("", "", "", False)
        assert isinstance(result, str)
        assert "Kein Ergebnis" in result
        assert "Keine Tests" in result
        assert "ERFOLGREICH" in result

    def test_sehr_lange_strings_alle_parameter(self):
        """Sehr lange Strings (10000+ Zeichen) werden korrekt gekuerzt."""
        # Verwende eindeutige Unicode-Zeichen die nicht im Template vorkommen
        code_marker = "\u2588"
        sandbox_marker = "\u2589"
        test_marker = "\u258a"
        langer_code = code_marker * 15000
        langes_sandbox = sandbox_marker * 10000
        lange_tests = test_marker * 8000
        result = _build_second_opinion_prompt(
            langer_code, langes_sandbox, lange_tests, True
        )
        assert result.count(code_marker) == 8000
        assert result.count(sandbox_marker) == 2000
        assert result.count(test_marker) == 1000

    def test_enthaelt_pruefpunkt_logik_fehler(self):
        """Der Prompt enthaelt Pruefpunkt 1: 'Logik-Fehler und Edge-Cases'."""
        result = _build_second_opinion_prompt("code", "sandbox", "tests", False)
        assert "Logik-Fehler und Edge-Cases" in result

    def test_enthaelt_pruefpunkt_sicherheit(self):
        """Der Prompt enthaelt Pruefpunkt 2: 'Sicherheitsprobleme'."""
        result = _build_second_opinion_prompt("code", "sandbox", "tests", False)
        assert "Sicherheitsprobleme" in result
        assert "SQL Injection" in result
        assert "XSS" in result

    def test_enthaelt_pruefpunkt_fehlerbehandlung(self):
        """Der Prompt enthaelt Pruefpunkt 3: 'Fehlende Fehlerbehandlung'."""
        result = _build_second_opinion_prompt("code", "sandbox", "tests", False)
        assert "Fehlende Fehlerbehandlung" in result

    def test_enthaelt_pruefpunkt_imports(self):
        """Der Prompt enthaelt Pruefpunkt 4: 'Import-Fehler'."""
        result = _build_second_opinion_prompt("code", "sandbox", "tests", False)
        assert "Import-Fehler" in result

    def test_enthaelt_pruefpunkt_inkonsistenzen(self):
        """Der Prompt enthaelt Pruefpunkt 5: 'Inkonsistenzen zwischen Dateien'."""
        result = _build_second_opinion_prompt("code", "sandbox", "tests", False)
        assert "Inkonsistenzen zwischen Dateien" in result

    def test_enthaelt_ok_antwort_hinweis(self):
        """Der Prompt enthaelt den Hinweis zur OK-Antwort."""
        result = _build_second_opinion_prompt("code", "sandbox", "tests", False)
        assert 'Antworte mit "OK"' in result

    def test_code_abschnitt_marker(self):
        """Der Prompt enthaelt die Abschnitts-Marker fuer Code, Sandbox und Tests."""
        result = _build_second_opinion_prompt("code", "sandbox", "tests", False)
        assert "=== CODE ===" in result
        assert "=== SANDBOX-ERGEBNIS ===" in result
        assert "=== TEST-ZUSAMMENFASSUNG ===" in result

    def test_sandbox_result_inhalt_sichtbar(self):
        """Der tatsaechliche sandbox_result-Inhalt erscheint im Prompt."""
        result = _build_second_opinion_prompt("code", "Sandbox hat 3 Fehler", "tests", False)
        assert "Sandbox hat 3 Fehler" in result

    def test_test_summary_inhalt_sichtbar(self):
        """Der tatsaechliche test_summary-Inhalt erscheint im Prompt."""
        result = _build_second_opinion_prompt("code", "sandbox", "5 von 5 Tests bestanden", False)
        assert "5 von 5 Tests bestanden" in result


# ===== Tests fuer _restore_primary_model =====

class TestRestorePrimaryModel:
    """Tests fuer die Wiederherstellung des Primary-Modells nach Second-Opinion."""

    def _make_mock_manager(self, rate_limited_models=None):
        """Hilfsfunktion: Erstellt einen Mock-Manager mit model_router."""
        manager = MagicMock()
        manager.model_router = MagicMock()
        if rate_limited_models is None:
            rate_limited_models = {}
        manager.model_router.rate_limited_models = rate_limited_models
        return manager

    def test_mark_success_aufgerufen(self):
        """mark_success() wird mit dem primary_model aufgerufen."""
        manager = self._make_mock_manager()
        _restore_primary_model(manager, "gpt-4o")
        manager.model_router.mark_success.assert_called_once_with("gpt-4o")

    def test_modell_aus_rate_limited_entfernt(self):
        """Das Modell wird aus rate_limited_models entfernt wenn vorhanden."""
        rate_limited = {"gpt-4o": True, "claude-3": True}
        manager = self._make_mock_manager(rate_limited_models=rate_limited)
        _restore_primary_model(manager, "gpt-4o")
        assert "gpt-4o" not in rate_limited
        # Anderes Modell bleibt erhalten
        assert "claude-3" in rate_limited

    def test_modell_nicht_in_rate_limited_kein_fehler(self):
        """Wenn das Modell NICHT in rate_limited_models ist, kein KeyError."""
        rate_limited = {"claude-3": True}
        manager = self._make_mock_manager(rate_limited_models=rate_limited)
        # Darf keinen Fehler werfen
        _restore_primary_model(manager, "gpt-4o")
        manager.model_router.mark_success.assert_called_once_with("gpt-4o")
        assert "claude-3" in rate_limited

    def test_leere_rate_limited_kein_fehler(self):
        """Leeres rate_limited_models dict verursacht keinen Fehler."""
        manager = self._make_mock_manager(rate_limited_models={})
        _restore_primary_model(manager, "gpt-4o")
        manager.model_router.mark_success.assert_called_once_with("gpt-4o")

    def test_mark_success_exception_kein_crash(self):
        """Exception in mark_success() fuehrt nicht zum Crash (graceful handling)."""
        manager = self._make_mock_manager()
        manager.model_router.mark_success.side_effect = RuntimeError("Router-Fehler")
        # Darf keinen Fehler werfen — wird intern gefangen
        _restore_primary_model(manager, "gpt-4o")

    def test_del_exception_kein_crash(self):
        """Exception beim Entfernen aus rate_limited_models fuehrt nicht zum Crash."""
        manager = MagicMock()
        manager.model_router = MagicMock()
        # rate_limited_models als Property-Mock mit __contains__ und __delitem__
        rl_mock = MagicMock()
        rl_mock.__contains__ = MagicMock(return_value=True)
        rl_mock.__delitem__ = MagicMock(side_effect=KeyError("schon weg"))
        manager.model_router.rate_limited_models = rl_mock
        # mark_success funktioniert, aber del wirft → Gesamtfunktion faengt ab
        _restore_primary_model(manager, "gpt-4o")
        # Kein Crash = Test bestanden

    def test_verschiedene_modellnamen(self):
        """Verschiedene Modellnamen werden korrekt an mark_success() uebergeben."""
        modelle = [
            "gpt-4o",
            "claude-opus-4-20250514",
            "gemini-2.5-pro-preview",
            "deepseek/deepseek-r1",
        ]
        for modell in modelle:
            manager = self._make_mock_manager()
            _restore_primary_model(manager, modell)
            manager.model_router.mark_success.assert_called_once_with(modell)


# ===== Tests fuer run_second_opinion_review =====

# AENDERUNG 14.02.2026: Neue Testklasse fuer die Hauptfunktion
# Alle externen Abhaengigkeiten (CrewAI, init_agents, heartbeat, etc.) werden gemockt

# Patch-Pfade fuer Mocks (Modul-Level fuer Wiederverwendbarkeit)
_PATCH_INIT_AGENTS = "backend.dev_loop_second_opinion.init_agents"
_PATCH_HEARTBEAT = "backend.dev_loop_second_opinion.run_with_heartbeat"
_PATCH_EMPTY_CHECK = "backend.dev_loop_second_opinion.is_empty_or_invalid_response"
_PATCH_TASK = "backend.dev_loop_second_opinion.Task"


def _make_manager(vier_augen_config=None, second_model="model-b"):
    """Hilfsfunktion: Erstellt einen gemockten Manager fuer run_second_opinion_review."""
    m = MagicMock()
    m.config = {
        "vier_augen": vier_augen_config or {"skip_on_error": True, "timeout_factor": 0.5},
        "agent_timeouts": {"reviewer": 1200},
    }
    m.model_router = MagicMock()
    m.model_router.get_model.return_value = second_model
    m.model_router.rate_limited_models = {}
    m.tech_blueprint = {"project_type": "react_app"}
    return m


class TestRunSecondOpinionReview:
    """Tests fuer run_second_opinion_review — Vier-Augen-Prinzip Integration."""

    # --- Standard-Parameter fuer alle Tests ---
    _PROJECT_RULES = {"global": ["PEP8 einhalten"]}
    _CURRENT_CODE = "def hello(): pass"
    _SANDBOX_RESULT = "Python-Syntax OK"
    _TEST_SUMMARY = "3 von 3 Tests bestanden"
    _PRIMARY_MODEL = "model-a"

    def _call_review(self, manager, sandbox_failed=False):
        """Hilfsfunktion: Ruft run_second_opinion_review mit Standard-Parametern auf."""
        return run_second_opinion_review(
            manager=manager,
            project_rules=self._PROJECT_RULES,
            current_code=self._CURRENT_CODE,
            sandbox_result=self._SANDBOX_RESULT,
            test_summary=self._TEST_SUMMARY,
            sandbox_failed=sandbox_failed,
            primary_model=self._PRIMARY_MODEL,
        )

    @patch(_PATCH_TASK)
    @patch(_PATCH_EMPTY_CHECK)
    @patch(_PATCH_HEARTBEAT)
    @patch(_PATCH_INIT_AGENTS)
    def test_kein_second_reviewer_verfuegbar(
        self, mock_init_agents, mock_heartbeat, mock_empty_check, mock_task
    ):
        """Wenn init_agents keinen Reviewer liefert, wird (True, 'OK', 'keiner') zurueckgegeben."""
        manager = _make_manager()
        # init_agents gibt kein "reviewer"-Key zurueck
        mock_init_agents.return_value = {}

        agrees, verdict, second_model = self._call_review(manager)

        assert agrees is True, "Erwartet: agrees=True, Erhalten: agrees=False"
        assert verdict == "OK", f"Erwartet: verdict='OK', Erhalten: verdict='{verdict}'"
        assert second_model == "keiner", (
            f"Erwartet: second_model='keiner', Erhalten: '{second_model}'"
        )
        # Primary-Modell muss wiederhergestellt werden
        manager.model_router.mark_success.assert_called_with(self._PRIMARY_MODEL)

    @patch(_PATCH_TASK)
    @patch(_PATCH_EMPTY_CHECK)
    @patch(_PATCH_HEARTBEAT)
    @patch(_PATCH_INIT_AGENTS)
    def test_gleiches_modell_wie_primary(
        self, mock_init_agents, mock_heartbeat, mock_empty_check, mock_task
    ):
        """Wenn das Second-Modell identisch zum Primary ist, wird uebersprungen."""
        # Second-Modell = Primary-Modell
        manager = _make_manager(second_model=self._PRIMARY_MODEL)
        mock_init_agents.return_value = {"reviewer": MagicMock()}

        agrees, verdict, second_model = self._call_review(manager)

        assert agrees is True, "Erwartet: agrees=True bei gleichem Modell"
        assert verdict == "OK", f"Erwartet: verdict='OK', Erhalten: '{verdict}'"
        assert second_model == self._PRIMARY_MODEL, (
            f"Erwartet: second_model='{self._PRIMARY_MODEL}', Erhalten: '{second_model}'"
        )
        # Heartbeat darf NICHT aufgerufen worden sein (uebersprungen)
        mock_heartbeat.assert_not_called()

    @patch(_PATCH_TASK)
    @patch(_PATCH_EMPTY_CHECK)
    @patch(_PATCH_HEARTBEAT)
    @patch(_PATCH_INIT_AGENTS)
    def test_leere_antwort_wird_als_ok_gewertet(
        self, mock_init_agents, mock_heartbeat, mock_empty_check, mock_task
    ):
        """Eine leere/ungueltige Antwort gilt als OK (Primary-Verdict bleibt)."""
        manager = _make_manager(second_model="model-b")
        mock_init_agents.return_value = {"reviewer": MagicMock()}
        mock_heartbeat.return_value = ""
        # is_empty_or_invalid_response erkennt leere Antwort
        mock_empty_check.return_value = True

        agrees, verdict, second_model = self._call_review(manager)

        assert agrees is True, "Erwartet: agrees=True bei leerer Antwort"
        assert verdict == "OK", f"Erwartet: verdict='OK', Erhalten: '{verdict}'"
        assert second_model == "model-b", (
            f"Erwartet: second_model='model-b', Erhalten: '{second_model}'"
        )

    @patch(_PATCH_TASK)
    @patch(_PATCH_EMPTY_CHECK)
    @patch(_PATCH_HEARTBEAT)
    @patch(_PATCH_INIT_AGENTS)
    def test_second_opinion_sagt_ok(
        self, mock_init_agents, mock_heartbeat, mock_empty_check, mock_task
    ):
        """Second Opinion bestaetigt OK → agrees=True, verdict=review_output."""
        manager = _make_manager(second_model="model-b")
        mock_init_agents.return_value = {"reviewer": MagicMock()}
        review_output = "Code sieht gut aus. OK - keine Probleme gefunden."
        mock_heartbeat.return_value = review_output
        mock_empty_check.return_value = False

        agrees, verdict, second_model = self._call_review(manager)

        assert agrees is True, "Erwartet: agrees=True bei OK-Antwort"
        # Bei agrees=True wird review_output zurueckgegeben (nicht der String "OK")
        assert verdict == review_output, (
            f"Erwartet: verdict=review_output, Erhalten: '{verdict}'"
        )
        assert second_model == "model-b"

    @patch(_PATCH_TASK)
    @patch(_PATCH_EMPTY_CHECK)
    @patch(_PATCH_HEARTBEAT)
    @patch(_PATCH_INIT_AGENTS)
    def test_second_opinion_sagt_feedback(
        self, mock_init_agents, mock_heartbeat, mock_empty_check, mock_task
    ):
        """Second Opinion gibt Feedback → agrees=False, verdict='FEEDBACK'."""
        manager = _make_manager(second_model="model-b")
        mock_init_agents.return_value = {"reviewer": MagicMock()}
        # Antwort ohne "OK" → wird als FEEDBACK gewertet
        review_output = "Fehler in Zeile 5: fehlende Fehlerbehandlung fuer None-Werte."
        mock_heartbeat.return_value = review_output
        mock_empty_check.return_value = False

        agrees, verdict, second_model = self._call_review(manager)

        assert agrees is False, "Erwartet: agrees=False bei Feedback-Antwort"
        assert verdict == "FEEDBACK", f"Erwartet: verdict='FEEDBACK', Erhalten: '{verdict}'"
        assert second_model == "model-b"

    @patch(_PATCH_TASK)
    @patch(_PATCH_EMPTY_CHECK)
    @patch(_PATCH_HEARTBEAT)
    @patch(_PATCH_INIT_AGENTS)
    def test_exception_mit_skip_on_error_true(
        self, mock_init_agents, mock_heartbeat, mock_empty_check, mock_task
    ):
        """Exception bei skip_on_error=True → (True, 'OK', 'fehler')."""
        manager = _make_manager(
            vier_augen_config={"skip_on_error": True, "timeout_factor": 0.5},
            second_model="model-b",
        )
        mock_init_agents.return_value = {"reviewer": MagicMock()}
        # Heartbeat wirft Exception
        mock_heartbeat.side_effect = RuntimeError("Timeout beim Review")
        mock_empty_check.return_value = False

        agrees, verdict, second_model = self._call_review(manager)

        assert agrees is True, "Erwartet: agrees=True bei skip_on_error=True"
        assert verdict == "OK", f"Erwartet: verdict='OK', Erhalten: '{verdict}'"
        assert second_model == "fehler", (
            f"Erwartet: second_model='fehler', Erhalten: '{second_model}'"
        )
        # Primary-Modell muss trotz Fehler wiederhergestellt werden
        manager.model_router.mark_success.assert_called()

    @patch(_PATCH_TASK)
    @patch(_PATCH_EMPTY_CHECK)
    @patch(_PATCH_HEARTBEAT)
    @patch(_PATCH_INIT_AGENTS)
    def test_exception_mit_skip_on_error_false(
        self, mock_init_agents, mock_heartbeat, mock_empty_check, mock_task
    ):
        """Exception bei skip_on_error=False → (False, 'FEEDBACK', 'fehler')."""
        manager = _make_manager(
            vier_augen_config={"skip_on_error": False, "timeout_factor": 0.5},
            second_model="model-b",
        )
        mock_init_agents.return_value = {"reviewer": MagicMock()}
        # Heartbeat wirft Exception
        mock_heartbeat.side_effect = ValueError("Unbekannter Fehler")
        mock_empty_check.return_value = False

        agrees, verdict, second_model = self._call_review(manager)

        assert agrees is False, "Erwartet: agrees=False bei skip_on_error=False"
        assert verdict == "FEEDBACK", f"Erwartet: verdict='FEEDBACK', Erhalten: '{verdict}'"
        assert second_model == "fehler", (
            f"Erwartet: second_model='fehler', Erhalten: '{second_model}'"
        )

    @patch(_PATCH_TASK)
    @patch(_PATCH_EMPTY_CHECK)
    @patch(_PATCH_HEARTBEAT)
    @patch(_PATCH_INIT_AGENTS)
    def test_primary_modell_wird_temporaer_gesperrt(
        self, mock_init_agents, mock_heartbeat, mock_empty_check, mock_task
    ):
        """Das Primary-Modell wird per mark_rate_limited_sync gesperrt."""
        manager = _make_manager(second_model="model-b")
        mock_init_agents.return_value = {"reviewer": MagicMock()}
        mock_heartbeat.return_value = "OK"
        mock_empty_check.return_value = False

        self._call_review(manager)

        manager.model_router.mark_rate_limited_sync.assert_called_once_with(
            self._PRIMARY_MODEL
        )

    @patch(_PATCH_TASK)
    @patch(_PATCH_EMPTY_CHECK)
    @patch(_PATCH_HEARTBEAT)
    @patch(_PATCH_INIT_AGENTS)
    def test_init_agents_parameter(
        self, mock_init_agents, mock_heartbeat, mock_empty_check, mock_task
    ):
        """init_agents wird mit korrekten Parametern aufgerufen."""
        manager = _make_manager(second_model="model-b")
        mock_init_agents.return_value = {"reviewer": MagicMock()}
        mock_heartbeat.return_value = "OK"
        mock_empty_check.return_value = False

        self._call_review(manager)

        mock_init_agents.assert_called_once_with(
            manager.config,
            self._PROJECT_RULES,
            router=manager.model_router,
            include=["reviewer"],
            tech_blueprint=manager.tech_blueprint,
        )

    @patch(_PATCH_TASK)
    @patch(_PATCH_EMPTY_CHECK)
    @patch(_PATCH_HEARTBEAT)
    @patch(_PATCH_INIT_AGENTS)
    def test_timeout_berechnung(
        self, mock_init_agents, mock_heartbeat, mock_empty_check, mock_task
    ):
        """Timeout wird korrekt als base_timeout * timeout_factor berechnet (min 120)."""
        manager = _make_manager(
            vier_augen_config={"skip_on_error": True, "timeout_factor": 0.5},
            second_model="model-b",
        )
        mock_init_agents.return_value = {"reviewer": MagicMock()}
        mock_heartbeat.return_value = "OK"
        mock_empty_check.return_value = False

        self._call_review(manager)

        # base_timeout=1200, timeout_factor=0.5 → 600
        call_kwargs = mock_heartbeat.call_args[1]
        assert call_kwargs["timeout_seconds"] == 600, (
            f"Erwartet: timeout=600, Erhalten: {call_kwargs['timeout_seconds']}"
        )

    @patch(_PATCH_TASK)
    @patch(_PATCH_EMPTY_CHECK)
    @patch(_PATCH_HEARTBEAT)
    @patch(_PATCH_INIT_AGENTS)
    def test_timeout_minimum_120(
        self, mock_init_agents, mock_heartbeat, mock_empty_check, mock_task
    ):
        """Timeout hat ein Minimum von 120 Sekunden."""
        manager = _make_manager(
            # Sehr kleiner Timeout-Faktor: 100 * 0.1 = 10 → max(120, 10) = 120
            vier_augen_config={"skip_on_error": True, "timeout_factor": 0.1},
            second_model="model-b",
        )
        manager.config["agent_timeouts"] = {"reviewer": 100}
        mock_init_agents.return_value = {"reviewer": MagicMock()}
        mock_heartbeat.return_value = "OK"
        mock_empty_check.return_value = False

        self._call_review(manager)

        call_kwargs = mock_heartbeat.call_args[1]
        assert call_kwargs["timeout_seconds"] == 120, (
            f"Erwartet: timeout=120 (Minimum), Erhalten: {call_kwargs['timeout_seconds']}"
        )

    @patch(_PATCH_TASK)
    @patch(_PATCH_EMPTY_CHECK)
    @patch(_PATCH_HEARTBEAT)
    @patch(_PATCH_INIT_AGENTS)
    def test_sandbox_failed_erzwingt_feedback(
        self, mock_init_agents, mock_heartbeat, mock_empty_check, mock_task
    ):
        """Bei sandbox_failed=True wird IMMER 'FEEDBACK' zurueckgegeben, auch bei 'OK' im Output."""
        manager = _make_manager(second_model="model-b")
        mock_init_agents.return_value = {"reviewer": MagicMock()}
        # Antwort enthaelt "OK", aber Sandbox ist fehlgeschlagen
        mock_heartbeat.return_value = "Code sieht OK aus"
        mock_empty_check.return_value = False

        agrees, verdict, second_model = self._call_review(manager, sandbox_failed=True)

        assert agrees is False, "Erwartet: agrees=False bei sandbox_failed=True"
        assert verdict == "FEEDBACK", (
            f"Erwartet: verdict='FEEDBACK' trotz OK im Output, Erhalten: '{verdict}'"
        )

    @patch(_PATCH_TASK)
    @patch(_PATCH_EMPTY_CHECK)
    @patch(_PATCH_HEARTBEAT)
    @patch(_PATCH_INIT_AGENTS)
    def test_ui_log_wird_aufgerufen(
        self, mock_init_agents, mock_heartbeat, mock_empty_check, mock_task
    ):
        """_ui_log wird mindestens fuer Start und Result aufgerufen."""
        manager = _make_manager(second_model="model-b")
        mock_init_agents.return_value = {"reviewer": MagicMock()}
        mock_heartbeat.return_value = "OK - alles gut"
        mock_empty_check.return_value = False

        self._call_review(manager)

        # Mindestens 3 Aufrufe: Start, Model, Result
        assert manager._ui_log.call_count >= 3, (
            f"Erwartet: mindestens 3 _ui_log Aufrufe, Erhalten: {manager._ui_log.call_count}"
        )

    @patch(_PATCH_TASK)
    @patch(_PATCH_EMPTY_CHECK)
    @patch(_PATCH_HEARTBEAT)
    @patch(_PATCH_INIT_AGENTS)
    def test_dissent_log_bei_feedback(
        self, mock_init_agents, mock_heartbeat, mock_empty_check, mock_task
    ):
        """Bei Dissent (agrees=False) wird ein Dissent-Log geschrieben."""
        manager = _make_manager(second_model="model-b")
        mock_init_agents.return_value = {"reviewer": MagicMock()}
        mock_heartbeat.return_value = "Fehler: fehlende Validierung"
        mock_empty_check.return_value = False

        self._call_review(manager)

        # Suche nach dem Dissent-Aufruf in den _ui_log Aufrufen
        dissent_calls = [
            call for call in manager._ui_log.call_args_list
            if len(call.args) >= 2 and call.args[1] == "Dissent"
        ]
        assert len(dissent_calls) == 1, (
            f"Erwartet: genau 1 Dissent-Log, Erhalten: {len(dissent_calls)}"
        )

    @patch(_PATCH_TASK)
    @patch(_PATCH_EMPTY_CHECK)
    @patch(_PATCH_HEARTBEAT)
    @patch(_PATCH_INIT_AGENTS)
    def test_kein_dissent_log_bei_ok(
        self, mock_init_agents, mock_heartbeat, mock_empty_check, mock_task
    ):
        """Bei agrees=True wird KEIN Dissent-Log geschrieben."""
        manager = _make_manager(second_model="model-b")
        mock_init_agents.return_value = {"reviewer": MagicMock()}
        mock_heartbeat.return_value = "Alles OK, Code ist sauber"
        mock_empty_check.return_value = False

        self._call_review(manager)

        dissent_calls = [
            call for call in manager._ui_log.call_args_list
            if len(call.args) >= 2 and call.args[1] == "Dissent"
        ]
        assert len(dissent_calls) == 0, (
            f"Erwartet: kein Dissent-Log bei OK, Erhalten: {len(dissent_calls)}"
        )
