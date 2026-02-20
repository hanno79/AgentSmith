"""
Author: rahn
Datum: 14.02.2026
Version: 1.0
Beschreibung: Tests fuer DevLoopTaskDerivation Modul.
              Testet should_use_task_derivation, _summarize_results,
              _emit_event und integrate_task_derivation.
"""

import pytest
from unittest.mock import MagicMock, patch

from backend.dev_loop_task_derivation import DevLoopTaskDerivation, integrate_task_derivation
from backend.task_models import (
    DerivedTask, TaskCategory, TaskPriority, TaskStatus, TargetAgent
)


# --- Hilfsfunktionen fuer Mock-Objekte ---

def _make_manager(**kwargs):
    """Erstellt einen Mock-Manager mit optionalen Attributen."""
    manager = MagicMock()
    manager.config = kwargs.get("config", {})
    manager.base_dir = kwargs.get("base_dir", ".")
    manager.model_router = kwargs.get("model_router", None)
    manager._ui_log = MagicMock()
    return manager


def _make_batch_result(completed=None, failed=None, modified=None, errors=None):
    """Erstellt ein Mock-BatchResult Objekt."""
    br = MagicMock()
    br.completed_tasks = completed or []
    br.failed_tasks = failed or []
    br.modified_files = modified or []
    br.errors = errors or []
    return br


def _make_derivation_result(tasks=None):
    """Erstellt ein Mock-TaskDerivationResult Objekt."""
    dr = MagicMock()
    dr.tasks = tasks or []
    dr.total_tasks = len(dr.tasks)
    return dr


def _make_task(task_id, title="Test Task", source_issue="Test Issue"):
    """Erstellt ein einfaches DerivedTask Objekt."""
    return DerivedTask(
        id=task_id, title=title, description="Beschreibung",
        category=TaskCategory.CODE, priority=TaskPriority.MEDIUM,
        target_agent=TargetAgent.CODER, source_issue=source_issue
    )


_PATCH_DEPS = [
    "backend.dev_loop_task_derivation.DartTaskSync",
    "backend.dev_loop_task_derivation.TaskTracker",
    "backend.dev_loop_task_derivation.TaskDeriver",
]


@pytest.fixture
def td():
    """Erstellt eine DevLoopTaskDerivation Instanz mit gemockten Abhaengigkeiten."""
    manager = _make_manager()
    with patch(_PATCH_DEPS[0]), patch(_PATCH_DEPS[1]), patch(_PATCH_DEPS[2]), \
         patch.dict("os.environ", {}, clear=False):
        instance = DevLoopTaskDerivation(manager)
    return instance


class TestShouldUseTaskDerivation:
    """Tests fuer should_use_task_derivation() - reine Logik-Entscheidung."""

    # --- Source "initial" / "discovery" ---

    @pytest.mark.parametrize("source", ["initial", "discovery"])
    def test_initial_feedback_lang_genug(self, td, source):
        """Initial/Discovery mit Feedback >= 30 Zeichen -> True."""
        assert td.should_use_task_derivation("A" * 30, source, 0) is True

    @pytest.mark.parametrize("source", ["initial", "discovery"])
    def test_initial_feedback_zu_kurz(self, td, source):
        """Initial/Discovery mit Feedback < 30 Zeichen -> False."""
        assert td.should_use_task_derivation("A" * 29, source, 0) is False

    @pytest.mark.parametrize("source", ["initial", "discovery"])
    def test_initial_leerer_feedback(self, td, source):
        """Initial/Discovery mit leerem Feedback -> False."""
        assert td.should_use_task_derivation("", source, 0) is False

    @pytest.mark.parametrize("source", ["initial", "discovery"])
    def test_initial_nur_whitespace(self, td, source):
        """Initial/Discovery mit nur Leerzeichen -> False (strip() < 30)."""
        assert td.should_use_task_derivation("   ", source, 0) is False

    @pytest.mark.parametrize("source", ["initial", "discovery"])
    def test_initial_ignoriert_iteration(self, td, source):
        """Initial/Discovery prueft Iteration NICHT."""
        fb = "A" * 50
        assert td.should_use_task_derivation(fb, source, 5) is True
        assert td.should_use_task_derivation(fb, source, 0) is True

    # --- iteration < 1 (non-initial Quellen) ---

    @pytest.mark.parametrize("source", ["reviewer", "quality_gate", "security", "sandbox"])
    def test_iteration_null_blockiert(self, td, source):
        """Non-initial Quellen bei iteration=0 -> False."""
        fb = "A" * 200 + " Error: Fehler: BUG: FIXME:"
        assert td.should_use_task_derivation(fb, source, 0) is False

    # --- Minimale Feedback-Laenge (< 50 Zeichen) ---

    @pytest.mark.parametrize("source", ["reviewer", "quality_gate"])
    def test_kurzer_feedback_standard(self, td, source):
        """Standard-Quellen mit Feedback < 50 Zeichen -> False."""
        assert td.should_use_task_derivation("kurz", source, 1) is False

    def test_kurzer_feedback_security(self, td):
        """Security mit Feedback < 50 Zeichen -> False (50-Zeichen-Gate greift)."""
        assert td.should_use_task_derivation("SQL Injection", "security", 1) is False

    def test_kurzer_feedback_sandbox(self, td):
        """Sandbox mit Feedback < 50 Zeichen -> False (50-Zeichen-Gate greift)."""
        assert td.should_use_task_derivation("Error:", "sandbox", 1) is False

    # --- Security-Indikatoren ---

    def test_security_ein_indikator_reicht(self, td):
        """Security: Ein Indikator reicht fuer Aktivierung."""
        fb = "A" * 50 + " SQL Injection found in login endpoint"
        assert td.should_use_task_derivation(fb, "security", 1) is True

    def test_security_keine_indikatoren(self, td):
        """Security: Keine relevanten Begriffe -> False."""
        fb = "A" * 50 + " Alles sieht gut aus, keine Probleme gefunden"
        assert td.should_use_task_derivation(fb, "security", 1) is False

    def test_security_zwei_indikatoren(self, td):
        """Security: CVE + Vulnerability -> True (2 Indikatoren)."""
        fb = "A" * 50 + " CVE-2024-1234 Vulnerability entdeckt"
        assert td.should_use_task_derivation(fb, "security", 1) is True

    def test_security_case_insensitive(self, td):
        """Security: Indikatoren werden case-insensitive geprueft."""
        fb = "A" * 50 + " xss schwachstelle in der Suchfunktion"
        assert td.should_use_task_derivation(fb, "security", 1) is True

    def test_security_severity_indikatoren(self, td):
        """Security: severity/risk Begriffe zaehlen als Indikatoren."""
        fb = "A" * 50 + " severity: high risk detected"
        assert td.should_use_task_derivation(fb, "security", 1) is True

    # --- Sandbox-Indikatoren ---

    def test_sandbox_error_indikator(self, td):
        """Sandbox: 'Error:' als Indikator -> True."""
        fb = "A" * 50 + " Error: module not found in project"
        assert td.should_use_task_derivation(fb, "sandbox", 1) is True

    def test_sandbox_typeerror_indikator(self, td):
        """Sandbox: 'TypeError' als Indikator -> True."""
        fb = "A" * 50 + " TypeError: cannot read property of undefined"
        assert td.should_use_task_derivation(fb, "sandbox", 1) is True

    def test_sandbox_keine_indikatoren(self, td):
        """Sandbox: Keine Fehler-Indikatoren -> False."""
        fb = "A" * 50 + " alles ok keine fehler gefunden im Code"
        assert td.should_use_task_derivation(fb, "sandbox", 1) is False

    def test_sandbox_case_sensitive(self, td):
        """Sandbox: Indikatoren sind case-sensitive (anders als Security)."""
        fb = "A" * 50 + " error: etwas ist passiert im Sandbox-Lauf"
        assert td.should_use_task_derivation(fb, "sandbox", 1) is False

    def test_sandbox_syntaxerror(self, td):
        """Sandbox: SyntaxError als Indikator -> True."""
        fb = "A" * 50 + " SyntaxError: unexpected token in line 42"
        assert td.should_use_task_derivation(fb, "sandbox", 1) is True

    def test_sandbox_fail_prefix(self, td):
        """Sandbox: 'FAIL:' als Indikator -> True."""
        fb = "A" * 50 + " FAIL: test_login hat nicht funktioniert"
        assert td.should_use_task_derivation(fb, "sandbox", 1) is True

    # --- Standard (reviewer, quality_gate) - 2+ Indikatoren noetig ---

    def test_standard_zwei_verschiedene_indikatoren(self, td):
        """Standard: Listenelement + Fehler-Keyword -> True (2 Indikatoren)."""
        fb = "A" * 50 + "\n- Fehler: in Zeile 42"
        assert td.should_use_task_derivation(fb, "reviewer", 1) is True

    def test_standard_ein_indikator_reicht_nicht(self, td):
        """Standard: Nur 'Fehler:' allein -> False (nur 1 Indikator)."""
        fb = "A" * 50 + " Fehler: in Zeile 42"
        assert td.should_use_task_derivation(fb, "reviewer", 1) is False

    def test_standard_zwei_keyword_indikatoren(self, td):
        """Standard: Error: + Fehler: -> True (2 Indikatoren)."""
        fb = "A" * 50 + "\n1. Error:\nFehler: in der Validierung"
        assert td.should_use_task_derivation(fb, "reviewer", 1) is True

    def test_standard_fixme_ursache(self, td):
        """Standard: FIXME: + Ursache: -> True (2 Indikatoren)."""
        fb = "A" * 50 + " FIXME: Ursache: Falscher Rueckgabewert"
        assert td.should_use_task_derivation(fb, "reviewer", 1) is True

    def test_standard_keine_indikatoren(self, td):
        """Standard: 'Alles ist gut' -> False (0 Indikatoren)."""
        fb = "A" * 50 + " Alles ist gut und funktioniert einwandfrei"
        assert td.should_use_task_derivation(fb, "reviewer", 1) is False

    def test_standard_quality_gate_gleich(self, td):
        """Quality Gate nutzt dieselbe Logik wie Reviewer."""
        fb = "A" * 50 + "\n- Error: Problem gefunden"
        assert td.should_use_task_derivation(fb, "quality_gate", 1) is True

    def test_standard_warning_und_todo(self, td):
        """Standard: Warning: + TODO: -> True (2 Indikatoren)."""
        fb = "A" * 50 + " Warning: veraltet. TODO: erneuern"
        assert td.should_use_task_derivation(fb, "reviewer", 1) is True

    def test_standard_nummerierte_liste(self, td):
        """Standard: Nummerierte Liste mit zwei Eintraegen -> True."""
        fb = "A" * 50 + "\n1. Erster Fehler\n2. Zweiter Fehler"
        assert td.should_use_task_derivation(fb, "quality_gate", 2) is True


class TestSummarizeResults:
    """Tests fuer _summarize_results() - Zusammenfassung der Batch-Ergebnisse."""

    def test_alle_tasks_erfolgreich(self, td):
        """Alle Tasks completed -> success=True."""
        tasks = [_make_task("T-1"), _make_task("T-2")]
        dr = _make_derivation_result(tasks=tasks)
        br = _make_batch_result(completed=["T-1", "T-2"])
        success, summary, _ = td._summarize_results([br], dr)
        assert success is True
        assert "Erfolgreich: 2" in summary
        assert "Gesamt: 2" in summary

    def test_teilweise_fehlgeschlagen(self, td):
        """Teilweise failed -> success=False."""
        tasks = [_make_task("T-1"), _make_task("T-2")]
        dr = _make_derivation_result(tasks=tasks)
        br = _make_batch_result(completed=["T-1"], failed=["T-2"])
        success, summary, _ = td._summarize_results([br], dr)
        assert success is False
        assert "Fehlgeschlagen: 1" in summary

    def test_modified_files_in_summary(self, td):
        """Modifizierte Dateien erscheinen in der Zusammenfassung."""
        dr = _make_derivation_result(tasks=[_make_task("T-1")])
        br = _make_batch_result(completed=["T-1"], modified=["a.py", "b.py", "c.py"])
        success, summary, modified = td._summarize_results([br], dr)
        assert success is True
        assert "Geaenderte Dateien:" in summary
        assert len(modified) == 3

    def test_modified_files_dedupliziert(self, td):
        """Doppelte Dateien werden dedupliziert."""
        dr = _make_derivation_result(tasks=[_make_task("T-1")])
        br = _make_batch_result(completed=["T-1"], modified=["a.py", "a.py", "b.py"])
        _, _, modified = td._summarize_results([br], dr)
        assert len(modified) == 2

    def test_modified_files_max_5_in_summary(self, td):
        """Maximal 5 Dateien in der Summary-Zeile."""
        dr = _make_derivation_result(tasks=[_make_task("T-1")])
        dateien = [f"datei_{i}.py" for i in range(10)]
        br = _make_batch_result(completed=["T-1"], modified=dateien)
        _, summary, _ = td._summarize_results([br], dr)
        zeile = [z for z in summary.split("\n") if "Geaenderte Dateien:" in z]
        assert len(zeile) == 1
        assert zeile[0].count(",") <= 4  # Max 5 Dateien = max 4 Kommas

    def test_errors_in_summary(self, td):
        """Fehler erscheinen als 'Fehler:' Section (max 3)."""
        dr = _make_derivation_result(tasks=[_make_task("T-1")])
        br = _make_batch_result(
            completed=["T-1"],
            errors=["Fehler A", "Fehler B", "Fehler C", "Fehler D"]
        )
        _, summary, _ = td._summarize_results([br], dr)
        assert "Fehler:" in summary
        assert "Fehler A" in summary and "Fehler C" in summary
        assert "Fehler D" not in summary  # Max 3

    def test_kein_task(self, td):
        """Keine Tasks -> success=True (0 == 0)."""
        dr = _make_derivation_result(tasks=[])
        br = _make_batch_result()
        success, summary, modified = td._summarize_results([br], dr)
        assert success is True
        assert "Gesamt: 0" in summary
        assert modified == []

    def test_verbleibende_aufgaben_bei_fehlern(self, td):
        """Fehlgeschlagene Tasks unter 'AUTOMATISCH ERKANNTE PROBLEME' (Fix 58d)."""
        task = _make_task("T-1", title="Login Fix", source_issue="Login bricht ab")
        dr = _make_derivation_result(tasks=[task])
        br = _make_batch_result(failed=["T-1"])
        success, summary, _ = td._summarize_results([br], dr)
        assert success is False
        # Fix 58d: Bei komplettem Fehlschlag (0 completed) → Coder-Hints statt "Verbleibende Aufgaben"
        assert "AUTOMATISCH ERKANNTE PROBLEME" in summary
        assert "Login Fix" in summary

    def test_mehrere_batches_aggregiert(self, td):
        """Ergebnisse aus mehreren Batches korrekt aggregiert."""
        tasks = [_make_task("T-1"), _make_task("T-2"), _make_task("T-3")]
        dr = _make_derivation_result(tasks=tasks)
        br1 = _make_batch_result(completed=["T-1"], modified=["a.py"])
        br2 = _make_batch_result(completed=["T-2", "T-3"], modified=["b.py"])
        success, summary, modified = td._summarize_results([br1, br2], dr)
        assert success is True
        assert "Erfolgreich: 3" in summary
        assert len(modified) == 2

    def test_leere_batch_results(self, td):
        """Leere batch_results Liste -> success=True."""
        dr = _make_derivation_result(tasks=[])
        success, summary, _ = td._summarize_results([], dr)
        assert success is True
        assert "Gesamt: 0" in summary

    def test_error_truncation_100_zeichen(self, td):
        """Fehler werden auf 100 Zeichen abgeschnitten."""
        dr = _make_derivation_result(tasks=[_make_task("T-1")])
        br = _make_batch_result(completed=["T-1"], errors=["X" * 200])
        _, summary, _ = td._summarize_results([br], dr)
        zeilen = [z for z in summary.split("\n") if z.startswith("- X")]
        assert len(zeilen) == 1
        assert len(zeilen[0].lstrip("- ")) == 100

    def test_source_issue_truncation(self, td):
        """source_issue auf 200 Zeichen abgeschnitten (Fix 58d: ausfuehrlichere Hints)."""
        task = _make_task("T-1", title="Fix", source_issue="Y" * 300)
        dr = _make_derivation_result(tasks=[task])
        br = _make_batch_result(failed=["T-1"])
        _, summary, _ = td._summarize_results([br], dr)
        assert "Y" * 200 in summary
        assert "Y" * 201 not in summary

    def test_mehrere_batches_mit_fehlern(self, td):
        """Fehler aus verschiedenen Batches zusammengefuehrt."""
        dr = _make_derivation_result(tasks=[_make_task("T-1"), _make_task("T-2")])
        br1 = _make_batch_result(completed=["T-1"], errors=["Fehler aus Batch 1"])
        br2 = _make_batch_result(failed=["T-2"], errors=["Fehler aus Batch 2"])
        _, summary, _ = td._summarize_results([br1, br2], dr)
        assert "Fehler aus Batch 1" in summary
        assert "Fehler aus Batch 2" in summary


class TestEmitEvent:
    """Tests fuer _emit_event() - WebSocket Event-Versand."""

    def test_ui_log_aufgerufen(self, td):
        """_emit_event ruft manager._ui_log auf."""
        td._emit_event("TestEvent", {"key": "value"})
        td.manager._ui_log.assert_called_once()
        args = td.manager._ui_log.call_args[0]
        assert args[0] == "UTDS" and args[1] == "TestEvent"

    def test_broadcast_event_aufgerufen(self, td):
        """_emit_event ruft broadcast_event via get_session_manager auf."""
        mock_sm = MagicMock()
        with patch("backend.session_manager.get_session_manager", return_value=mock_sm), \
             patch("backend.dev_loop_task_derivation.os.path.exists", return_value=False):
            td._emit_event("TestEvent", {"key": "value"})
        mock_sm.broadcast_event.assert_called_once()

    def test_broadcast_exception_kein_crash(self, td):
        """Exception bei broadcast -> kein Absturz (graceful)."""
        with patch("backend.dev_loop_task_derivation.get_session_manager",
                    side_effect=Exception("Verbindungsfehler"), create=True), \
             patch("backend.dev_loop_task_derivation.os.path.exists", return_value=False):
            td._emit_event("TestEvent", {"test": True})
        assert td.manager._ui_log.called

    def test_event_data_als_json(self, td):
        """Event-Daten werden als JSON serialisiert."""
        import json
        with patch("backend.dev_loop_task_derivation.os.path.exists", return_value=False):
            td._emit_event("JsonTest", {"zahl": 42, "text": "test"})
        data_str = td.manager._ui_log.call_args[0][2]
        parsed = json.loads(data_str)
        assert parsed["zahl"] == 42 and parsed["text"] == "test"

    def test_manager_ohne_ui_log(self):
        """Manager ohne _ui_log -> print() Fallback (kein Crash)."""
        manager = MagicMock(spec=[])
        with patch(_PATCH_DEPS[0]), patch(_PATCH_DEPS[1]), patch(_PATCH_DEPS[2]), \
             patch.dict("os.environ", {}, clear=False):
            instance = DevLoopTaskDerivation(manager)
        with patch("builtins.print") as mock_print, \
             patch("backend.dev_loop_task_derivation.os.path.exists", return_value=False):
            instance._emit_event("FallbackTest", {"ok": True})
        mock_print.assert_called_once()


class TestIntegrateTaskDerivation:
    """Tests fuer integrate_task_derivation() Convenience-Funktion."""

    def test_erstellt_task_derivation_wenn_nicht_vorhanden(self):
        """Manager ohne _task_derivation -> wird neu erstellt."""
        manager = _make_manager()
        del manager._task_derivation
        with patch(_PATCH_DEPS[0]), patch(_PATCH_DEPS[1]), patch(_PATCH_DEPS[2]):
            result = integrate_task_derivation(
                manager, "kurzer feedback", "reviewer", iteration=0
            )
        assert hasattr(manager, '_task_derivation')
        assert result == (False, "kurzer feedback", [])

    def test_should_use_false_gibt_original_zurueck(self):
        """should_use=False -> (False, original_feedback, [])."""
        manager = _make_manager()
        del manager._task_derivation
        fb = "einfacher Text"
        with patch(_PATCH_DEPS[0]), patch(_PATCH_DEPS[1]), patch(_PATCH_DEPS[2]):
            used, returned, files = integrate_task_derivation(
                manager, fb, "reviewer", iteration=0
            )
        assert used is False and returned == fb and files == []

    def test_cached_task_derivation_wiederverwendet(self):
        """Vorhandene _task_derivation wird wiederverwendet."""
        manager = _make_manager()
        mock_td = MagicMock()
        mock_td.should_use_task_derivation.return_value = False
        manager._task_derivation = mock_td
        result = integrate_task_derivation(manager, "feedback text", "reviewer", iteration=0)
        mock_td.should_use_task_derivation.assert_called_once()
        assert result == (False, "feedback text", [])

    def test_process_feedback_aufgerufen_wenn_aktiviert(self):
        """should_use=True -> process_feedback wird aufgerufen."""
        manager = _make_manager()
        mock_td = MagicMock()
        mock_td.should_use_task_derivation.return_value = True
        mock_td.process_feedback.return_value = (True, "Zusammenfassung", ["a.py"])
        manager._task_derivation = mock_td
        used, summary, files = integrate_task_derivation(
            manager, "langer feedback text", "initial", context={"key": "val"}
        )
        mock_td.process_feedback.assert_called_once_with(
            "langer feedback text", "initial", {"key": "val"}
        )
        assert used is True and summary == "Zusammenfassung" and files == ["a.py"]

    def test_default_iteration_ist_null(self):
        """Ohne explizite iteration wird 0 verwendet."""
        manager = _make_manager()
        mock_td = MagicMock()
        mock_td.should_use_task_derivation.return_value = False
        manager._task_derivation = mock_td
        integrate_task_derivation(manager, "feedback", "reviewer")
        assert mock_td.should_use_task_derivation.call_args[0][2] == 0
