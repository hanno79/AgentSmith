# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 14.02.2026
Version: 1.0
Beschreibung: Tests fuer dev_loop_review.py — Review-Funktion mit Retry- und Modellwechsel-Logik.
              Prueft _compress_review_code (Context-Kompression fuer Reviewer) und
              run_review (Retry-Logik, Modellwechsel, Verdict-Bestimmung).
              Schwere externe Abhaengigkeiten (CrewAI, agent_factory, heartbeat_utils,
              context_compressor, orchestration_helpers) werden vollstaendig gemockt.
"""

import os
import sys
import json
import pytest
from unittest.mock import MagicMock, patch, call

# Projekt-Root zum Python-Path hinzufuegen
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ===========================================================================
# 1. Tests fuer _compress_review_code
# ===========================================================================

class TestCompressReviewCode:
    """Tests fuer _compress_review_code(manager, sandbox_result, test_summary)."""

    @patch("backend.dev_loop_review._get_current_code_dict")
    @patch("backend.dev_loop_review.compress_context")
    def test_leeres_code_dict_fallback_current_code(self, mock_compress, mock_get_code):
        """Bei leerem code_dict wird manager.current_code als Fallback zurueckgegeben."""
        from backend.dev_loop_review import _compress_review_code

        manager = MagicMock()
        manager.config = {}
        manager.current_code = "fallback code content"

        mock_get_code.return_value = {}

        result = _compress_review_code(manager, "sandbox ok", "tests ok")
        assert result == "fallback code content", (
            "Erwartet: Fallback auf manager.current_code bei leerem code_dict"
        )
        # compress_context sollte NICHT aufgerufen werden bei leerem code_dict
        mock_compress.assert_not_called()

    @patch("backend.dev_loop_review._get_current_code_dict")
    @patch("backend.dev_loop_review.compress_context")
    def test_none_code_dict_fallback_leerer_string(self, mock_compress, mock_get_code):
        """Bei None code_dict und fehlendem current_code wird leerer String zurueckgegeben."""
        from backend.dev_loop_review import _compress_review_code

        manager = MagicMock(spec=[])
        manager.config = {}

        mock_get_code.return_value = None

        result = _compress_review_code(manager, "", "")
        assert result == "", (
            "Erwartet: Leerer String wenn code_dict None und current_code fehlt"
        )

    @patch("backend.dev_loop_review._get_current_code_dict")
    @patch("backend.dev_loop_review.compress_context")
    def test_normaler_fall_filename_format(self, mock_compress, mock_get_code):
        """Normaler Fall: Komprimierte Dateien werden im ### FILENAME: Format ausgegeben."""
        from backend.dev_loop_review import _compress_review_code

        manager = MagicMock()
        manager.config = {}
        manager.current_code = "original code"

        mock_get_code.return_value = {"app.js": "code1", "lib/db.js": "code2"}
        mock_compress.return_value = {
            "app.js": "const app = express()",
            "lib/db.js": "const db = require('sqlite3')"
        }

        result = _compress_review_code(manager, "sandbox ok", "tests ok")
        assert "### FILENAME: app.js" in result, (
            "Erwartet: '### FILENAME: app.js' im Ergebnis"
        )
        assert "### FILENAME: lib/db.js" in result, (
            "Erwartet: '### FILENAME: lib/db.js' im Ergebnis"
        )
        assert "const app = express()" in result, (
            "Erwartet: Inhalt von app.js im Ergebnis"
        )
        assert "const db = require('sqlite3')" in result, (
            "Erwartet: Inhalt von lib/db.js im Ergebnis"
        )

    @patch("backend.dev_loop_review._get_current_code_dict")
    @patch("backend.dev_loop_review.compress_context")
    def test_summary_dateien_markiert(self, mock_compress, mock_get_code):
        """Dateien mit Summary-Marker (IMPORTS:, FUNKTIONEN:, etc.) werden als ZUSAMMENFASSUNG markiert."""
        from backend.dev_loop_review import _compress_review_code

        manager = MagicMock()
        manager.config = {}
        manager.current_code = "original"

        mock_get_code.return_value = {"app.js": "code", "utils.js": "code2"}
        mock_compress.return_value = {
            "app.js": "const app = 'full code'",
            "utils.js": "IMPORTS: express, path\nFUNKTIONEN: helper, init"
        }

        result = _compress_review_code(manager, "", "")
        # utils.js startet mit IMPORTS: → Zusammenfassung
        assert "(ZUSAMMENFASSUNG)" in result, (
            "Erwartet: Summary-Datei mit (ZUSAMMENFASSUNG) markiert"
        )
        # app.js startet NICHT mit Summary-Marker
        assert "### FILENAME: app.js\n" in result, (
            "Erwartet: Nicht-Summary-Datei OHNE (ZUSAMMENFASSUNG)"
        )
        # Pruefe dass die Markierung bei utils.js ist
        assert "### FILENAME: utils.js (ZUSAMMENFASSUNG)" in result, (
            "Erwartet: utils.js hat (ZUSAMMENFASSUNG) Label"
        )

    @patch("backend.dev_loop_review._get_current_code_dict")
    @patch("backend.dev_loop_review.compress_context")
    def test_verschiedene_summary_marker(self, mock_compress, mock_get_code):
        """Alle Summary-Marker werden erkannt: IMPORTS, VORSCHAU, SELEKTOREN, TOP-KEYS, NAME, KLASSEN, FUNKTIONEN, [."""
        from backend.dev_loop_review import _compress_review_code

        manager = MagicMock()
        manager.config = {}
        manager.current_code = "x"

        marker_dateien = {
            "a.js": "IMPORTS: foo",
            "b.css": "VORSCHAU: body {}",
            "c.css": "SELEKTOREN: .btn, .card",
            "d.json": "TOP-KEYS: name, version",
            "e.py": "NAME: MyClass",
            "f.py": "KLASSEN: Foo, Bar",
            "g.py": "FUNKTIONEN: init, run",
            "h.json": "[\"array\", \"start\"]",
        }

        mock_get_code.return_value = marker_dateien
        mock_compress.return_value = dict(marker_dateien)

        result = _compress_review_code(manager, "", "")
        # Alle 8 Dateien muessen als ZUSAMMENFASSUNG markiert sein
        zusammenfassung_count = result.count("(ZUSAMMENFASSUNG)")
        assert zusammenfassung_count == 8, (
            f"Erwartet: 8 Dateien mit (ZUSAMMENFASSUNG), erhalten: {zusammenfassung_count}"
        )

    @patch("backend.dev_loop_review._get_current_code_dict")
    @patch("backend.dev_loop_review.compress_context")
    def test_cache_wird_persistiert(self, mock_compress, mock_get_code):
        """Der Reviewer-Summary-Cache wird auf manager._reviewer_summary_cache persistiert."""
        from backend.dev_loop_review import _compress_review_code

        manager = MagicMock()
        manager.config = {}
        manager.current_code = "code"
        manager._reviewer_summary_cache = {}

        mock_get_code.return_value = {"app.js": "code"}
        # compress_context gibt _cache zurueck, das extrahiert und gespeichert wird
        mock_compress.return_value = {
            "app.js": "full code",
            "_cache": {"app.js": {"hash": "abc123", "summary": "cached"}}
        }

        _compress_review_code(manager, "", "")
        assert manager._reviewer_summary_cache == {"app.js": {"hash": "abc123", "summary": "cached"}}, (
            "Erwartet: Cache auf manager._reviewer_summary_cache gespeichert"
        )

    @patch("backend.dev_loop_review._get_current_code_dict")
    @patch("backend.dev_loop_review.compress_context")
    def test_bestehender_cache_wird_weitergegeben(self, mock_compress, mock_get_code):
        """Ein bestehender manager._reviewer_summary_cache wird an compress_context uebergeben."""
        from backend.dev_loop_review import _compress_review_code

        manager = MagicMock()
        manager.config = {"some": "config"}
        manager.current_code = "code"
        existing_cache = {"old.js": {"hash": "old_hash"}}
        manager._reviewer_summary_cache = existing_cache

        mock_get_code.return_value = {"app.js": "code"}
        mock_compress.return_value = {"app.js": "code"}

        _compress_review_code(manager, "sandbox", "tests")
        # compress_context muss mit dem bestehenden Cache aufgerufen worden sein
        mock_compress.assert_called_once()
        call_kwargs = mock_compress.call_args
        assert call_kwargs[1].get("cache") == existing_cache or call_kwargs[0][3] == existing_cache, (
            "Erwartet: Bestehender Cache an compress_context uebergeben"
        )

    @patch("backend.dev_loop_review._get_current_code_dict")
    @patch("backend.dev_loop_review.compress_context")
    def test_max_reviewer_prompt_chars_ueberschritten(self, mock_compress, mock_get_code):
        """Bei Ueberschreitung von max_reviewer_prompt_chars wird der Code gekuerzt."""
        from backend.dev_loop_review import _compress_review_code

        manager = MagicMock()
        # Setze niedriges Limit fuer den Test
        manager.config = {"max_reviewer_prompt_chars": 100}
        manager.current_code = "original"

        mock_get_code.return_value = {"app.js": "code"}
        # Gib sehr langen Code zurueck
        mock_compress.return_value = {"app.js": "x" * 200}

        result = _compress_review_code(manager, "", "")
        assert "[... GEKUERZT wegen Token-Limit ...]" in result, (
            "Erwartet: Kuerzungshinweis am Ende des gesamten Outputs"
        )

    @patch("backend.dev_loop_review._get_current_code_dict")
    @patch("backend.dev_loop_review.compress_context")
    def test_default_max_reviewer_prompt_chars_400000(self, mock_compress, mock_get_code):
        """Default-Wert fuer max_reviewer_prompt_chars ist 400000."""
        from backend.dev_loop_review import _compress_review_code

        manager = MagicMock()
        manager.config = {}  # Kein max_reviewer_prompt_chars gesetzt
        manager.current_code = "code"

        mock_get_code.return_value = {"app.js": "code"}
        # Unter 400000 Zeichen → kein Kuerzen
        mock_compress.return_value = {"app.js": "a" * 1000}

        result = _compress_review_code(manager, "", "")
        assert "[... GEKUERZT" not in result, (
            "Erwartet: Kein Kuerzen bei unter 400000 Zeichen"
        )

    @patch("backend.dev_loop_review._get_current_code_dict")
    @patch("backend.dev_loop_review.compress_context")
    def test_feedback_aus_sandbox_und_test_zusammengesetzt(self, mock_compress, mock_get_code):
        """Sandbox-Result und Test-Summary werden als zusammengesetztes Feedback uebergeben."""
        from backend.dev_loop_review import _compress_review_code

        manager = MagicMock()
        manager.config = {}
        manager.current_code = "code"

        mock_get_code.return_value = {"app.js": "code"}
        mock_compress.return_value = {"app.js": "code"}

        _compress_review_code(manager, "sandbox fehler xyz", "test fehlgeschlagen abc")
        # Pruefe, dass compress_context mit dem zusammengesetzten Feedback aufgerufen wurde
        mock_compress.assert_called_once()
        call_args = mock_compress.call_args
        feedback_arg = call_args[1].get("feedback") or call_args[0][1]
        assert "sandbox fehler xyz" in feedback_arg, (
            "Erwartet: sandbox_result im Feedback enthalten"
        )
        assert "test fehlgeschlagen abc" in feedback_arg, (
            "Erwartet: test_summary im Feedback enthalten"
        )

    @patch("backend.dev_loop_review._get_current_code_dict")
    @patch("backend.dev_loop_review.compress_context")
    def test_dateien_alphabetisch_sortiert(self, mock_compress, mock_get_code):
        """Dateien werden alphabetisch sortiert im Output."""
        from backend.dev_loop_review import _compress_review_code

        manager = MagicMock()
        manager.config = {}
        manager.current_code = "code"

        mock_get_code.return_value = {"z.js": "z", "a.js": "a", "m.js": "m"}
        mock_compress.return_value = {"z.js": "z_code", "a.js": "a_code", "m.js": "m_code"}

        result = _compress_review_code(manager, "", "")
        pos_a = result.index("### FILENAME: a.js")
        pos_m = result.index("### FILENAME: m.js")
        pos_z = result.index("### FILENAME: z.js")
        assert pos_a < pos_m < pos_z, (
            "Erwartet: Dateien alphabetisch sortiert (a < m < z)"
        )


# ===========================================================================
# 2. Tests fuer run_review
# ===========================================================================

class TestRunReview:
    """Tests fuer run_review(manager, project_rules, current_code, sandbox_result, test_summary, sandbox_failed, run_with_timeout_func)."""

    def _create_default_manager(self):
        """Erstellt einen Standard-Manager-Mock fuer run_review Tests."""
        manager = MagicMock()
        manager.config = {"agent_timeouts": {"reviewer": 600}}
        manager.model_router.get_model.return_value = "test-model"
        manager.iteration = 0
        manager.max_retries = 10
        manager.agent_reviewer = MagicMock()
        return manager

    @patch("backend.dev_loop_review._compress_review_code")
    @patch("backend.dev_loop_review.Task")
    @patch("backend.dev_loop_review.run_with_heartbeat")
    @patch("backend.dev_loop_review.init_agents")
    @patch("backend.dev_loop_review.is_empty_or_invalid_response", return_value=False)
    @patch("backend.dev_loop_review.is_rate_limit_error", return_value=False)
    @patch("backend.dev_loop_review.is_openrouter_error", return_value=False)
    @patch("backend.dev_loop_review.truncate_review_output", side_effect=lambda x, **kw: x)
    @patch("backend.dev_loop_review.create_human_readable_verdict", return_value="Zusammenfassung")
    def test_erfolg_ok_nicht_sandbox_failed(self, mock_verdict, mock_truncate,
                                            mock_openrouter, mock_rate, mock_empty,
                                            mock_init, mock_heartbeat, mock_task,
                                            mock_compress):
        """Erfolg mit 'OK' im Output und sandbox_failed=False ergibt verdict='OK'."""
        from backend.dev_loop_review import run_review

        manager = self._create_default_manager()
        mock_compress.return_value = "compressed code"
        mock_heartbeat.return_value = "OK - Alles ist in Ordnung"

        output, verdict, summary = run_review(
            manager, {}, "code", "sandbox ok", "tests ok", False, MagicMock()
        )
        assert verdict == "OK", (
            f"Erwartet: verdict='OK', erhalten: '{verdict}'"
        )
        assert "OK" in output, (
            "Erwartet: 'OK' im Review-Output"
        )

    @patch("backend.dev_loop_review._compress_review_code")
    @patch("backend.dev_loop_review.Task")
    @patch("backend.dev_loop_review.run_with_heartbeat")
    @patch("backend.dev_loop_review.init_agents")
    @patch("backend.dev_loop_review.is_empty_or_invalid_response", return_value=False)
    @patch("backend.dev_loop_review.is_rate_limit_error", return_value=False)
    @patch("backend.dev_loop_review.is_openrouter_error", return_value=False)
    @patch("backend.dev_loop_review.truncate_review_output", side_effect=lambda x, **kw: x)
    @patch("backend.dev_loop_review.create_human_readable_verdict", return_value="Sandbox fehlgeschlagen")
    def test_ok_aber_sandbox_failed_ergibt_feedback(self, mock_verdict, mock_truncate,
                                                     mock_openrouter, mock_rate, mock_empty,
                                                     mock_init, mock_heartbeat, mock_task,
                                                     mock_compress):
        """Erfolg mit 'OK' im Output aber sandbox_failed=True ergibt verdict='FEEDBACK'."""
        from backend.dev_loop_review import run_review

        manager = self._create_default_manager()
        mock_compress.return_value = "compressed code"
        mock_heartbeat.return_value = "OK - Code sieht gut aus"

        output, verdict, summary = run_review(
            manager, {}, "code", "sandbox failed", "tests", True, MagicMock()
        )
        assert verdict == "FEEDBACK", (
            f"Erwartet: verdict='FEEDBACK' bei sandbox_failed=True, erhalten: '{verdict}'"
        )

    @patch("backend.dev_loop_review._compress_review_code")
    @patch("backend.dev_loop_review.Task")
    @patch("backend.dev_loop_review.run_with_heartbeat")
    @patch("backend.dev_loop_review.init_agents")
    @patch("backend.dev_loop_review.is_empty_or_invalid_response")
    @patch("backend.dev_loop_review.is_rate_limit_error", return_value=False)
    @patch("backend.dev_loop_review.is_openrouter_error", return_value=False)
    @patch("backend.dev_loop_review.truncate_review_output", side_effect=lambda x, **kw: x)
    @patch("backend.dev_loop_review.create_human_readable_verdict", return_value="Fehler")
    def test_empty_response_retry_modellwechsel_nach_2(self, mock_verdict, mock_truncate,
                                                        mock_openrouter, mock_rate, mock_empty,
                                                        mock_init, mock_heartbeat, mock_task,
                                                        mock_compress):
        """Empty response fuehrt zu Retry, Modellwechsel erst nach 2 gleichen Fehlern."""
        from backend.dev_loop_review import run_review

        manager = self._create_default_manager()
        mock_compress.return_value = "compressed code"
        # Aufruf-Reihenfolge: Attempt 0 (True) → Attempt 1 (True, Modellwechsel) →
        # Attempt 2 im Loop (False, break) → Post-Loop-Check Zeile 330 (False)
        mock_empty.side_effect = [True, True, False, False]
        mock_heartbeat.return_value = "Feedback: Fehler in app.js"
        mock_init.return_value = {"reviewer": MagicMock()}

        output, verdict, summary = run_review(
            manager, {}, "code", "", "", False, MagicMock()
        )
        # Nach 2 leeren Antworten muss Modellwechsel stattgefunden haben
        manager.model_router.mark_rate_limited_sync.assert_called_once(), (
            "Erwartet: mark_rate_limited_sync nach 2 leeren Antworten aufgerufen"
        )
        mock_init.assert_called_once(), (
            "Erwartet: init_agents fuer Modellwechsel aufgerufen"
        )

    @patch("backend.dev_loop_review._compress_review_code")
    @patch("backend.dev_loop_review.Task")
    @patch("backend.dev_loop_review.run_with_heartbeat")
    @patch("backend.dev_loop_review.init_agents")
    @patch("backend.dev_loop_review.is_empty_or_invalid_response", return_value=False)
    @patch("backend.dev_loop_review.is_rate_limit_error", return_value=True)
    @patch("backend.dev_loop_review.is_openrouter_error", return_value=False)
    @patch("backend.dev_loop_review.truncate_review_output", side_effect=lambda x, **kw: x)
    @patch("backend.dev_loop_review.create_human_readable_verdict", return_value="OK")
    def test_rate_limit_sofortiger_modellwechsel(self, mock_verdict, mock_truncate,
                                                  mock_openrouter, mock_rate, mock_empty,
                                                  mock_init, mock_heartbeat, mock_task,
                                                  mock_compress):
        """Rate-Limit-Fehler fuehrt zu sofortigem Modellwechsel (nicht erst nach 2x)."""
        from backend.dev_loop_review import run_review

        manager = self._create_default_manager()
        mock_compress.return_value = "compressed code"
        # Erster Aufruf: Rate-Limit, zweiter Aufruf: Erfolg
        mock_heartbeat.side_effect = [Exception("rate limit"), "OK - Alles gut"]
        mock_init.return_value = {"reviewer": MagicMock()}

        output, verdict, summary = run_review(
            manager, {}, "code", "", "", False, MagicMock()
        )
        # Sofortiger Modellwechsel nach Rate-Limit
        manager.model_router.mark_rate_limited_sync.assert_called_once(), (
            "Erwartet: Sofortiger Modellwechsel nach Rate-Limit"
        )

    def test_model_unavailable_sofortiger_modellwechsel(self):
        """ModelUnavailable-Fehler (z.B. no endpoints found) wechseln sofort das Modell."""
        from backend.dev_loop_review import run_review

        manager = self._create_default_manager()

        with patch("backend.dev_loop_review._compress_review_code", return_value="compressed code"), \
             patch("backend.dev_loop_review.Task"), \
             patch("backend.dev_loop_review.run_with_heartbeat", side_effect=[
                 Exception("OpenrouterException - No endpoints found for deepseek/deepseek-r1-0528:free"),
                 "OK - Alles gut"
             ]), \
             patch("backend.dev_loop_review.init_agents", return_value={"reviewer": MagicMock()}), \
             patch("backend.dev_loop_review.is_empty_or_invalid_response", return_value=False), \
             patch("backend.dev_loop_review.is_rate_limit_error", return_value=False), \
             patch("backend.dev_loop_review.is_model_unavailable_error", return_value=True), \
             patch("backend.dev_loop_review.handle_model_error", return_value="permanent") as mock_handle, \
             patch("backend.dev_loop_review.is_openrouter_error", return_value=False), \
             patch("backend.dev_loop_review.truncate_review_output", side_effect=lambda x, **kw: x), \
             patch("backend.dev_loop_review.create_human_readable_verdict", return_value="Zusammenfassung"):
            output, verdict, summary = run_review(
                manager, {}, "code", "", "", False, MagicMock()
            )

        mock_handle.assert_called_once()
        assert verdict == "OK", "Nach Modellwechsel soll der zweite erfolgreiche Versuch akzeptiert werden"

    @patch("backend.dev_loop_review._compress_review_code")
    @patch("backend.dev_loop_review.Task")
    @patch("backend.dev_loop_review.run_with_heartbeat")
    @patch("backend.dev_loop_review.init_agents")
    @patch("backend.dev_loop_review.is_empty_or_invalid_response", return_value=False)
    @patch("backend.dev_loop_review.is_rate_limit_error", return_value=False)
    @patch("backend.dev_loop_review.is_openrouter_error", return_value=False)
    @patch("backend.dev_loop_review.truncate_review_output", side_effect=lambda x, **kw: x)
    @patch("backend.dev_loop_review.create_human_readable_verdict", return_value="Timeout")
    def test_timeout_modellwechsel_nach_2(self, mock_verdict, mock_truncate,
                                          mock_openrouter, mock_rate, mock_empty,
                                          mock_init, mock_heartbeat, mock_task,
                                          mock_compress):
        """Timeout fuehrt zu Retry, Modellwechsel erst nach 2 gleichen Timeouts."""
        from backend.dev_loop_review import run_review

        manager = self._create_default_manager()
        mock_compress.return_value = "compressed code"
        # 2 Timeouts, dann Erfolg
        mock_heartbeat.side_effect = [
            TimeoutError("timeout 1"),
            TimeoutError("timeout 2"),
            "FEEDBACK: Fehler in utils.js"
        ]
        mock_init.return_value = {"reviewer": MagicMock()}

        output, verdict, summary = run_review(
            manager, {}, "code", "", "", False, MagicMock()
        )
        # Nach 2 Timeouts muss Modellwechsel stattfinden
        manager.model_router.mark_rate_limited_sync.assert_called_once(), (
            "Erwartet: Modellwechsel nach 2 Timeouts"
        )

    @patch("backend.dev_loop_review._compress_review_code")
    @patch("backend.dev_loop_review.Task")
    @patch("backend.dev_loop_review.run_with_heartbeat")
    @patch("backend.dev_loop_review.init_agents")
    @patch("backend.dev_loop_review.is_empty_or_invalid_response", return_value=False)
    @patch("backend.dev_loop_review.is_rate_limit_error", return_value=False)
    @patch("backend.dev_loop_review.is_openrouter_error")
    @patch("backend.dev_loop_review.truncate_review_output", side_effect=lambda x, **kw: x)
    @patch("backend.dev_loop_review.create_human_readable_verdict", return_value="OK")
    def test_openrouter_error_sofortiger_modellwechsel(self, mock_verdict, mock_truncate,
                                                        mock_openrouter, mock_rate, mock_empty,
                                                        mock_init, mock_heartbeat, mock_task,
                                                        mock_compress):
        """OpenRouter-Error fuehrt zu sofortigem Modellwechsel (ueber TimeoutError-Pfad)."""
        from backend.dev_loop_review import run_review

        manager = self._create_default_manager()
        mock_compress.return_value = "compressed code"
        # OpenRouter-Fehler als TimeoutError getarnt
        mock_openrouter.return_value = True
        mock_heartbeat.side_effect = [TimeoutError("openrouter error"), "OK - gut"]
        mock_init.return_value = {"reviewer": MagicMock()}

        output, verdict, summary = run_review(
            manager, {}, "code", "", "", False, MagicMock()
        )
        # Sofortiger Modellwechsel bei OpenRouter-Error
        manager.model_router.mark_rate_limited_sync.assert_called_once(), (
            "Erwartet: Sofortiger Modellwechsel bei OpenRouter-Error"
        )

    @patch("backend.dev_loop_review._compress_review_code")
    @patch("backend.dev_loop_review.Task")
    @patch("backend.dev_loop_review.run_with_heartbeat")
    @patch("backend.dev_loop_review.init_agents")
    @patch("backend.dev_loop_review.is_empty_or_invalid_response")
    @patch("backend.dev_loop_review.is_rate_limit_error", return_value=False)
    @patch("backend.dev_loop_review.is_openrouter_error", return_value=False)
    @patch("backend.dev_loop_review.truncate_review_output", side_effect=lambda x, **kw: x)
    @patch("backend.dev_loop_review.create_human_readable_verdict", return_value="Alle Modelle versagt")
    def test_alle_retries_fehlgeschlagen(self, mock_verdict, mock_truncate,
                                         mock_openrouter, mock_rate, mock_empty,
                                         mock_init, mock_heartbeat, mock_task,
                                         mock_compress):
        """Wenn alle 6 Retries fehlschlagen, wird Fehlermeldung zurueckgegeben."""
        from backend.dev_loop_review import run_review

        manager = self._create_default_manager()
        mock_compress.return_value = "compressed code"
        # Alle Aufrufe liefern leere Antwort
        mock_empty.return_value = True
        mock_heartbeat.return_value = ""
        mock_init.return_value = {"reviewer": MagicMock()}

        output, verdict, summary = run_review(
            manager, {}, "code", "", "", False, MagicMock()
        )
        assert "FEHLER" in output or "Alle Review-Modelle" in output, (
            f"Erwartet: Fehlermeldung im Output, erhalten: '{output}'"
        )
        assert verdict == "FEEDBACK", (
            "Erwartet: verdict='FEEDBACK' wenn alle Modelle versagen"
        )

    @patch("backend.dev_loop_review._compress_review_code")
    @patch("backend.dev_loop_review.Task")
    @patch("backend.dev_loop_review.run_with_heartbeat")
    @patch("backend.dev_loop_review.init_agents")
    @patch("backend.dev_loop_review.is_empty_or_invalid_response", return_value=False)
    @patch("backend.dev_loop_review.is_rate_limit_error", return_value=False)
    @patch("backend.dev_loop_review.is_openrouter_error", return_value=False)
    @patch("backend.dev_loop_review.truncate_review_output")
    @patch("backend.dev_loop_review.create_human_readable_verdict", return_value="Zusammenfassung")
    def test_review_output_wird_truncated(self, mock_verdict, mock_truncate,
                                           mock_openrouter, mock_rate, mock_empty,
                                           mock_init, mock_heartbeat, mock_task,
                                           mock_compress):
        """Review-Output wird mit truncate_review_output(max_length=3000) gekuerzt."""
        from backend.dev_loop_review import run_review

        manager = self._create_default_manager()
        mock_compress.return_value = "compressed code"
        mock_heartbeat.return_value = "OK - Langer Review Output"
        mock_truncate.return_value = "getruncated"

        output, verdict, summary = run_review(
            manager, {}, "code", "", "", False, MagicMock()
        )
        mock_truncate.assert_called_once_with(
            "OK - Langer Review Output", max_length=3000
        ), (
            "Erwartet: truncate_review_output mit max_length=3000 aufgerufen"
        )

    @patch("backend.dev_loop_review._compress_review_code")
    @patch("backend.dev_loop_review.Task")
    @patch("backend.dev_loop_review.run_with_heartbeat")
    @patch("backend.dev_loop_review.init_agents")
    @patch("backend.dev_loop_review.is_empty_or_invalid_response", return_value=False)
    @patch("backend.dev_loop_review.is_rate_limit_error", return_value=False)
    @patch("backend.dev_loop_review.is_openrouter_error", return_value=False)
    @patch("backend.dev_loop_review.truncate_review_output", side_effect=lambda x, **kw: x)
    @patch("backend.dev_loop_review.create_human_readable_verdict", return_value="Zusammenfassung")
    def test_rueckgabe_ist_tuple(self, mock_verdict, mock_truncate,
                                  mock_openrouter, mock_rate, mock_empty,
                                  mock_init, mock_heartbeat, mock_task,
                                  mock_compress):
        """Rueckgabe ist ein Tuple aus (output, verdict, summary)."""
        from backend.dev_loop_review import run_review

        manager = self._create_default_manager()
        mock_compress.return_value = "compressed code"
        mock_heartbeat.return_value = "OK - Prima"

        result = run_review(
            manager, {}, "code", "", "", False, MagicMock()
        )
        assert isinstance(result, tuple), (
            f"Erwartet: Tuple, erhalten: {type(result)}"
        )
        assert len(result) == 3, (
            f"Erwartet: Tuple mit 3 Elementen, erhalten: {len(result)}"
        )

    @patch("backend.dev_loop_review._compress_review_code")
    @patch("backend.dev_loop_review.Task")
    @patch("backend.dev_loop_review.run_with_heartbeat")
    @patch("backend.dev_loop_review.init_agents")
    @patch("backend.dev_loop_review.is_empty_or_invalid_response", return_value=False)
    @patch("backend.dev_loop_review.is_rate_limit_error", return_value=False)
    @patch("backend.dev_loop_review.is_openrouter_error", return_value=False)
    @patch("backend.dev_loop_review.truncate_review_output", side_effect=lambda x, **kw: x)
    @patch("backend.dev_loop_review.create_human_readable_verdict", return_value="Zusammenfassung")
    def test_update_worker_status_wird_aufgerufen(self, mock_verdict, mock_truncate,
                                                    mock_openrouter, mock_rate, mock_empty,
                                                    mock_init, mock_heartbeat, mock_task,
                                                    mock_compress):
        """_update_worker_status wird am Anfang (working) und am Ende (idle) aufgerufen."""
        from backend.dev_loop_review import run_review

        manager = self._create_default_manager()
        mock_compress.return_value = "compressed code"
        mock_heartbeat.return_value = "OK - Alles gut"

        run_review(manager, {}, "code", "", "", False, MagicMock())

        # Pruefe dass _update_worker_status mindestens 2x aufgerufen wurde
        calls = manager._update_worker_status.call_args_list
        assert len(calls) >= 2, (
            f"Erwartet: Mindestens 2 Aufrufe von _update_worker_status, erhalten: {len(calls)}"
        )
        # Erster Aufruf: working
        assert calls[0][0][0] == "reviewer", (
            "Erwartet: Erster _update_worker_status Aufruf fuer 'reviewer'"
        )
        assert calls[0][0][1] == "working", (
            "Erwartet: Erster Aufruf mit Status 'working'"
        )
        # Letzter Aufruf: idle
        assert calls[-1][0][0] == "reviewer", (
            "Erwartet: Letzter _update_worker_status Aufruf fuer 'reviewer'"
        )
        assert calls[-1][0][1] == "idle", (
            "Erwartet: Letzter Aufruf mit Status 'idle'"
        )

    @patch("backend.dev_loop_review._compress_review_code")
    @patch("backend.dev_loop_review.Task")
    @patch("backend.dev_loop_review.run_with_heartbeat")
    @patch("backend.dev_loop_review.init_agents")
    @patch("backend.dev_loop_review.is_empty_or_invalid_response", return_value=False)
    @patch("backend.dev_loop_review.is_rate_limit_error", return_value=False)
    @patch("backend.dev_loop_review.is_openrouter_error", return_value=False)
    @patch("backend.dev_loop_review.truncate_review_output", side_effect=lambda x, **kw: x)
    @patch("backend.dev_loop_review.create_human_readable_verdict", return_value="Zusammenfassung")
    def test_feedback_verdict_ohne_ok(self, mock_verdict, mock_truncate,
                                       mock_openrouter, mock_rate, mock_empty,
                                       mock_init, mock_heartbeat, mock_task,
                                       mock_compress):
        """Output ohne 'OK' ergibt verdict='FEEDBACK'."""
        from backend.dev_loop_review import run_review

        manager = self._create_default_manager()
        mock_compress.return_value = "compressed code"
        mock_heartbeat.return_value = "FEHLER: Import fehlt in app.js"

        output, verdict, summary = run_review(
            manager, {}, "code", "", "", False, MagicMock()
        )
        assert verdict == "FEEDBACK", (
            f"Erwartet: verdict='FEEDBACK' ohne OK im Output, erhalten: '{verdict}'"
        )

    @patch("backend.dev_loop_review._compress_review_code")
    @patch("backend.dev_loop_review.Task")
    @patch("backend.dev_loop_review.run_with_heartbeat")
    @patch("backend.dev_loop_review.init_agents")
    @patch("backend.dev_loop_review.is_empty_or_invalid_response", return_value=False)
    @patch("backend.dev_loop_review.is_rate_limit_error", return_value=False)
    @patch("backend.dev_loop_review.is_openrouter_error", return_value=False)
    @patch("backend.dev_loop_review.truncate_review_output", side_effect=lambda x, **kw: x)
    @patch("backend.dev_loop_review.create_human_readable_verdict", return_value="Zusammenfassung")
    def test_ui_log_review_output_json(self, mock_verdict, mock_truncate,
                                        mock_openrouter, mock_rate, mock_empty,
                                        mock_init, mock_heartbeat, mock_task,
                                        mock_compress):
        """_ui_log wird mit ReviewOutput und JSON-Daten aufgerufen."""
        from backend.dev_loop_review import run_review

        manager = self._create_default_manager()
        mock_compress.return_value = "compressed code"
        mock_heartbeat.return_value = "OK - Alles korrekt"

        run_review(manager, {}, "code", "sandbox ok", "tests ok", False, MagicMock())

        # Suche den ReviewOutput-Aufruf in _ui_log
        review_output_calls = [
            c for c in manager._ui_log.call_args_list
            if len(c[0]) >= 2 and c[0][1] == "ReviewOutput"
        ]
        assert len(review_output_calls) >= 1, (
            "Erwartet: Mindestens ein _ui_log Aufruf mit 'ReviewOutput'"
        )
        # Parse JSON-Inhalt
        json_str = review_output_calls[0][0][2]
        data = json.loads(json_str)
        assert "verdict" in data, "Erwartet: 'verdict' im JSON-Output"
        assert "isApproved" in data, "Erwartet: 'isApproved' im JSON-Output"
        assert "humanSummary" in data, "Erwartet: 'humanSummary' im JSON-Output"
        assert "model" in data, "Erwartet: 'model' im JSON-Output"

    @patch("backend.dev_loop_review._compress_review_code")
    @patch("backend.dev_loop_review.Task")
    @patch("backend.dev_loop_review.run_with_heartbeat")
    @patch("backend.dev_loop_review.init_agents")
    @patch("backend.dev_loop_review.is_empty_or_invalid_response", return_value=False)
    @patch("backend.dev_loop_review.is_rate_limit_error", return_value=False)
    @patch("backend.dev_loop_review.is_openrouter_error", return_value=False)
    @patch("backend.dev_loop_review.truncate_review_output", side_effect=lambda x, **kw: x)
    @patch("backend.dev_loop_review.create_human_readable_verdict", return_value="Zusammenfassung")
    def test_compress_review_code_wird_aufgerufen(self, mock_verdict, mock_truncate,
                                                    mock_openrouter, mock_rate, mock_empty,
                                                    mock_init, mock_heartbeat, mock_task,
                                                    mock_compress):
        """_compress_review_code wird zu Beginn von run_review aufgerufen."""
        from backend.dev_loop_review import run_review

        manager = self._create_default_manager()
        mock_compress.return_value = "compressed code"
        mock_heartbeat.return_value = "OK"

        run_review(manager, {}, "code", "sandbox", "tests", False, MagicMock())

        mock_compress.assert_called_once_with(manager, "sandbox", "tests"), (
            "Erwartet: _compress_review_code mit manager, sandbox_result, test_summary aufgerufen"
        )

    @patch("backend.dev_loop_review._compress_review_code")
    @patch("backend.dev_loop_review.Task")
    @patch("backend.dev_loop_review.run_with_heartbeat")
    @patch("backend.dev_loop_review.init_agents")
    @patch("backend.dev_loop_review.is_empty_or_invalid_response", return_value=False)
    @patch("backend.dev_loop_review.is_rate_limit_error", return_value=False)
    @patch("backend.dev_loop_review.is_openrouter_error", return_value=False)
    @patch("backend.dev_loop_review.truncate_review_output", side_effect=lambda x, **kw: x)
    @patch("backend.dev_loop_review.create_human_readable_verdict", return_value="Zusammenfassung")
    def test_reviewer_timeout_aus_config(self, mock_verdict, mock_truncate,
                                          mock_openrouter, mock_rate, mock_empty,
                                          mock_init, mock_heartbeat, mock_task,
                                          mock_compress):
        """Reviewer-Timeout wird aus config.agent_timeouts.reviewer gelesen."""
        from backend.dev_loop_review import run_review

        manager = self._create_default_manager()
        manager.config = {"agent_timeouts": {"reviewer": 999}}
        mock_compress.return_value = "compressed code"
        mock_heartbeat.return_value = "OK"

        run_review(manager, {}, "code", "", "", False, MagicMock())

        # Pruefe ob run_with_heartbeat mit timeout_seconds=999 aufgerufen wurde
        heartbeat_call = mock_heartbeat.call_args
        assert heartbeat_call[1].get("timeout_seconds") == 999 or \
               (len(heartbeat_call[0]) > 4 and heartbeat_call[0][4] == 999), (
            "Erwartet: timeout_seconds=999 an run_with_heartbeat uebergeben"
        )

    @patch("backend.dev_loop_review._compress_review_code")
    @patch("backend.dev_loop_review.Task")
    @patch("backend.dev_loop_review.run_with_heartbeat")
    @patch("backend.dev_loop_review.init_agents")
    @patch("backend.dev_loop_review.is_empty_or_invalid_response", return_value=False)
    @patch("backend.dev_loop_review.is_rate_limit_error", return_value=False)
    @patch("backend.dev_loop_review.is_openrouter_error", return_value=False)
    @patch("backend.dev_loop_review.truncate_review_output", side_effect=lambda x, **kw: x)
    @patch("backend.dev_loop_review.create_human_readable_verdict", return_value="Zusammenfassung")
    def test_model_error_modellwechsel_nach_2(self, mock_verdict, mock_truncate,
                                               mock_openrouter, mock_rate, mock_empty,
                                               mock_init, mock_heartbeat, mock_task,
                                               mock_compress):
        """Generische Fehler (model_error) fuehren zu Modellwechsel nach 2 gleichen Fehlern."""
        from backend.dev_loop_review import run_review

        manager = self._create_default_manager()
        mock_compress.return_value = "compressed code"
        # 2x generischer Fehler, dann Erfolg
        mock_heartbeat.side_effect = [
            AttributeError("litellm bug 1"),
            AttributeError("litellm bug 2"),
            "OK"
        ]
        mock_init.return_value = {"reviewer": MagicMock()}

        output, verdict, summary = run_review(
            manager, {}, "code", "", "", False, MagicMock()
        )
        # Nach 2 gleichen Fehlern muss Modellwechsel stattfinden
        manager.model_router.mark_rate_limited_sync.assert_called_once(), (
            "Erwartet: Modellwechsel nach 2 generischen Fehlern"
        )

    @patch("backend.dev_loop_review._compress_review_code")
    @patch("backend.dev_loop_review.Task")
    @patch("backend.dev_loop_review.run_with_heartbeat")
    @patch("backend.dev_loop_review.init_agents")
    @patch("backend.dev_loop_review.is_empty_or_invalid_response", return_value=False)
    @patch("backend.dev_loop_review.is_rate_limit_error", return_value=False)
    @patch("backend.dev_loop_review.is_openrouter_error", return_value=False)
    @patch("backend.dev_loop_review.truncate_review_output", side_effect=lambda x, **kw: x)
    @patch("backend.dev_loop_review.create_human_readable_verdict", return_value="Zusammenfassung")
    def test_docker_error_highlight_bei_sandbox_failed(self, mock_verdict, mock_truncate,
                                                        mock_openrouter, mock_rate, mock_empty,
                                                        mock_init, mock_heartbeat, mock_task,
                                                        mock_compress):
        """Bei sandbox_failed=True werden Fehler-Zeilen aus sandbox_result hervorgehoben."""
        from backend.dev_loop_review import run_review

        manager = self._create_default_manager()
        mock_compress.return_value = "compressed code"
        sandbox = "Starting app...\nImportError: No module named 'flask'\nDone."
        mock_heartbeat.return_value = "FEEDBACK: flask fehlt"

        run_review(manager, {}, "code", sandbox, "", True, MagicMock())

        # Pruefe ob Task mit Docker-Error-Highlight erstellt wurde
        task_call = mock_task.call_args
        description = task_call[1].get("description") or task_call[0][0]
        assert "KRITISCHE FEHLER GEFUNDEN" in description, (
            "Erwartet: Docker-Error-Highlight im Task-Prompt"
        )
        assert "ImportError" in description, (
            "Erwartet: ImportError im hervorgehobenen Abschnitt"
        )

    @patch("backend.dev_loop_review._get_current_code_dict")
    @patch("backend.dev_loop_review.compress_context")
    def test_compress_kein_cache_attribut_am_manager(self, mock_compress, mock_get_code):
        """Wenn manager kein _reviewer_summary_cache hat, wird leerer Cache verwendet."""
        from backend.dev_loop_review import _compress_review_code

        manager = MagicMock(spec=["config", "current_code"])
        manager.config = {}
        manager.current_code = "code"

        mock_get_code.return_value = {"app.js": "code"}
        mock_compress.return_value = {"app.js": "code"}

        # Soll nicht crashen
        _compress_review_code(manager, "", "")
        mock_compress.assert_called_once()

    @patch("backend.dev_loop_review._compress_review_code")
    @patch("backend.dev_loop_review.Task")
    @patch("backend.dev_loop_review.run_with_heartbeat")
    @patch("backend.dev_loop_review.init_agents")
    @patch("backend.dev_loop_review.is_empty_or_invalid_response", return_value=False)
    @patch("backend.dev_loop_review.is_rate_limit_error", return_value=False)
    @patch("backend.dev_loop_review.is_openrouter_error", return_value=False)
    @patch("backend.dev_loop_review.truncate_review_output", side_effect=lambda x, **kw: x)
    @patch("backend.dev_loop_review.create_human_readable_verdict", return_value="OK Summary")
    def test_create_human_readable_verdict_aufgerufen(self, mock_verdict, mock_truncate,
                                                       mock_openrouter, mock_rate, mock_empty,
                                                       mock_init, mock_heartbeat, mock_task,
                                                       mock_compress):
        """create_human_readable_verdict wird mit korrekten Parametern aufgerufen."""
        from backend.dev_loop_review import run_review

        manager = self._create_default_manager()
        mock_compress.return_value = "compressed code"
        mock_heartbeat.return_value = "OK - Prima"

        output, verdict, summary = run_review(
            manager, {}, "code", "", "", False, MagicMock()
        )
        mock_verdict.assert_called_once()
        call_args = mock_verdict.call_args[0]
        assert call_args[0] == "OK", (
            f"Erwartet: verdict='OK' an create_human_readable_verdict, erhalten: '{call_args[0]}'"
        )
        assert call_args[1] is False, (
            "Erwartet: sandbox_failed=False an create_human_readable_verdict"
        )
        assert summary == "OK Summary", (
            "Erwartet: Rueckgabe von create_human_readable_verdict als summary"
        )

    @patch("backend.dev_loop_review._compress_review_code")
    @patch("backend.dev_loop_review.Task")
    @patch("backend.dev_loop_review.run_with_heartbeat")
    @patch("backend.dev_loop_review.init_agents")
    @patch("backend.dev_loop_review.is_empty_or_invalid_response", return_value=False)
    @patch("backend.dev_loop_review.is_rate_limit_error", return_value=False)
    @patch("backend.dev_loop_review.is_openrouter_error", return_value=False)
    @patch("backend.dev_loop_review.truncate_review_output", side_effect=lambda x, **kw: x)
    @patch("backend.dev_loop_review.create_human_readable_verdict", return_value="Zusammenfassung")
    def test_none_sandbox_und_test_summary(self, mock_verdict, mock_truncate,
                                            mock_openrouter, mock_rate, mock_empty,
                                            mock_init, mock_heartbeat, mock_task,
                                            mock_compress):
        """None-Werte fuer sandbox_result und test_summary werden korrekt behandelt."""
        from backend.dev_loop_review import run_review

        manager = self._create_default_manager()
        mock_compress.return_value = "compressed code"
        mock_heartbeat.return_value = "OK"

        # Soll nicht crashen
        output, verdict, summary = run_review(
            manager, {}, "code", None, None, False, MagicMock()
        )
        assert isinstance(output, str), (
            "Erwartet: String-Output auch bei None-Eingaben"
        )

    @patch("backend.dev_loop_review._compress_review_code")
    @patch("backend.dev_loop_review.Task")
    @patch("backend.dev_loop_review.run_with_heartbeat")
    @patch("backend.dev_loop_review.init_agents")
    @patch("backend.dev_loop_review.is_empty_or_invalid_response", return_value=False)
    @patch("backend.dev_loop_review.is_rate_limit_error", return_value=False)
    @patch("backend.dev_loop_review.is_openrouter_error", return_value=False)
    @patch("backend.dev_loop_review.truncate_review_output", side_effect=lambda x, **kw: x)
    @patch("backend.dev_loop_review.create_human_readable_verdict", return_value="Zusammenfassung")
    def test_erster_versuch_erfolgreich_kein_retry(self, mock_verdict, mock_truncate,
                                                     mock_openrouter, mock_rate, mock_empty,
                                                     mock_init, mock_heartbeat, mock_task,
                                                     mock_compress):
        """Bei erfolgreichem erstem Versuch wird kein Retry oder Modellwechsel gemacht."""
        from backend.dev_loop_review import run_review

        manager = self._create_default_manager()
        mock_compress.return_value = "compressed code"
        mock_heartbeat.return_value = "OK - Perfekt"

        run_review(manager, {}, "code", "", "", False, MagicMock())

        # Kein Modellwechsel
        manager.model_router.mark_rate_limited_sync.assert_not_called(), (
            "Erwartet: Kein Modellwechsel bei erstem erfolgreichen Versuch"
        )
        # Kein init_agents (kein Modellwechsel)
        mock_init.assert_not_called(), (
            "Erwartet: init_agents nicht aufgerufen"
        )
        # heartbeat nur 1x aufgerufen
        assert mock_heartbeat.call_count == 1, (
            f"Erwartet: run_with_heartbeat nur 1x aufgerufen, erhalten: {mock_heartbeat.call_count}"
        )

    @patch("backend.dev_loop_review._compress_review_code")
    @patch("backend.dev_loop_review.Task")
    @patch("backend.dev_loop_review.run_with_heartbeat")
    @patch("backend.dev_loop_review.init_agents")
    @patch("backend.dev_loop_review.is_empty_or_invalid_response", return_value=False)
    @patch("backend.dev_loop_review.is_rate_limit_error", return_value=False)
    @patch("backend.dev_loop_review.is_openrouter_error", return_value=False)
    @patch("backend.dev_loop_review.truncate_review_output", side_effect=lambda x, **kw: x)
    @patch("backend.dev_loop_review.create_human_readable_verdict", return_value="Zusammenfassung")
    def test_ok_case_insensitive_check(self, mock_verdict, mock_truncate,
                                        mock_openrouter, mock_rate, mock_empty,
                                        mock_init, mock_heartbeat, mock_task,
                                        mock_compress):
        """Die OK-Pruefung ist case-insensitive (review_output.upper())."""
        from backend.dev_loop_review import run_review

        manager = self._create_default_manager()
        mock_compress.return_value = "compressed code"
        # Kleingeschriebenes 'ok' im Output
        mock_heartbeat.return_value = "Alles ok, keine Fehler"

        output, verdict, summary = run_review(
            manager, {}, "code", "", "", False, MagicMock()
        )
        assert verdict == "OK", (
            f"Erwartet: verdict='OK' auch bei kleingeschriebenem 'ok', erhalten: '{verdict}'"
        )

    @patch("backend.dev_loop_review._compress_review_code")
    @patch("backend.dev_loop_review.Task")
    @patch("backend.dev_loop_review.run_with_heartbeat")
    @patch("backend.dev_loop_review.init_agents")
    @patch("backend.dev_loop_review.is_empty_or_invalid_response", return_value=False)
    @patch("backend.dev_loop_review.is_rate_limit_error", return_value=False)
    @patch("backend.dev_loop_review.is_openrouter_error", return_value=False)
    @patch("backend.dev_loop_review.truncate_review_output", side_effect=lambda x, **kw: x)
    @patch("backend.dev_loop_review.create_human_readable_verdict", return_value="Zusammenfassung")
    def test_sandbox_result_truncation_in_ui_log(self, mock_verdict, mock_truncate,
                                                   mock_openrouter, mock_rate, mock_empty,
                                                   mock_init, mock_heartbeat, mock_task,
                                                   mock_compress):
        """sandbox_result und test_summary werden auf 500 Zeichen gekuerzt im UI-Log."""
        from backend.dev_loop_review import run_review

        manager = self._create_default_manager()
        mock_compress.return_value = "compressed code"
        mock_heartbeat.return_value = "OK"
        langer_sandbox = "x" * 1000
        langer_test = "y" * 1000

        run_review(manager, {}, "code", langer_sandbox, langer_test, False, MagicMock())

        # Suche ReviewOutput-Aufruf
        review_calls = [
            c for c in manager._ui_log.call_args_list
            if len(c[0]) >= 2 and c[0][1] == "ReviewOutput"
        ]
        assert len(review_calls) >= 1
        data = json.loads(review_calls[0][0][2])
        assert len(data.get("sandboxResult", "")) <= 500, (
            "Erwartet: sandboxResult auf 500 Zeichen gekuerzt"
        )
        assert len(data.get("testSummary", "")) <= 500, (
            "Erwartet: testSummary auf 500 Zeichen gekuerzt"
        )
