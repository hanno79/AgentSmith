# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 14.02.2026
Version: 1.0
Beschreibung: Unit Tests fuer backend/dev_loop_run_helpers.py.

              Getestete Funktionen:
              - run_file_by_file_phase(): Paralleler und sequenzieller Modus
              - _run_parallel_generation(): Plan, Template-Config-Skip, Rate-Limit-Retry
              - handle_truncation_recovery(): Erfolgreiche und fehlgeschlagene Reparatur
              - handle_success_finalization(): QualityGate, WaisenCheck, DocService, Memory
              - process_utds_feedback(): 3 Quellen (Security, Sandbox, Reviewer), Fix 53d append
              - run_smoke_test_gate(): Disabled, Passed, Failed, Error mit skip_on_error

              Mock-Strategie: Alle externen Abhaengigkeiten (LLM, asyncio, CrewAI) werden gemockt.
"""

import sys
import os
import json
import asyncio

# Fuege Projekt-Root zum Python-Path hinzu
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from unittest.mock import MagicMock, patch, AsyncMock, call
from dataclasses import dataclass, field
from typing import List, Optional


# =========================================================================
# Hilfs-Fixtures und Datenklassen
# =========================================================================

@dataclass
class MockSmokeTestResult:
    """Mock-Ergebnis fuer Smoke-Tests (analog zu SmokeTestResult)."""
    passed: bool
    server_started: bool = False
    page_loaded: bool = False
    compile_errors: List[str] = field(default_factory=list)
    console_errors: List[str] = field(default_factory=list)
    issues: List[str] = field(default_factory=list)
    screenshot: Optional[str] = None
    server_output: str = ""
    duration_seconds: float = 0.0
    feedback_for_coder: str = ""


@pytest.fixture
def mock_manager(tmp_path):
    """Erstellt einen Mock-Manager mit allen relevanten DevLoop-Attributen."""
    manager = MagicMock()
    manager.project_path = str(tmp_path)
    manager.base_dir = str(tmp_path)
    manager.current_code = ""
    manager.is_first_run = True
    manager.user_prompt = "Erstelle eine Todo-App"
    manager.tech_blueprint = {
        "project_type": "webapp",
        "framework": "Next.js",
        "language": "javascript",
    }
    manager.config = {
        "mode": "test",
        "max_retries": 3,
        "parallel_file_generation": {"enabled": True, "max_workers": 2},
        "agent_timeouts": {"coder": 750},
        "smoke_test": {"enabled": True, "skip_on_error": True},
    }
    manager._ui_log = MagicMock()
    manager._update_worker_status = MagicMock()
    manager._fbf_created_files = []
    manager.model_router = MagicMock()
    manager.model_router.get_model.return_value = "test-model"
    manager._docker_container = None
    return manager


@pytest.fixture
def mock_task_derivation():
    """Erstellt einen Mock fuer das TaskDerivation-System."""
    td = MagicMock()
    td.should_use_task_derivation = MagicMock(return_value=False)
    td.process_feedback = MagicMock(return_value=(True, "Alle Tasks erledigt", ["app/page.js"]))
    return td


# =========================================================================
# Tests fuer run_file_by_file_phase()
# =========================================================================

class TestRunFileByFilePhase:
    """Tests fuer run_file_by_file_phase() - Pre-Loop Datei-Generierung."""

    @patch("backend.dev_loop_run_helpers._run_parallel_generation")
    def test_paralleler_modus_aktiviert(self, mock_parallel_gen, mock_manager, tmp_path):
        """Parallele Generierung wird aufgerufen wenn enabled=True."""
        # Erstelle echte Dateien damit current_code gesetzt werden kann
        app_dir = tmp_path / "app"
        app_dir.mkdir()
        page_file = app_dir / "page.js"
        page_file.write_text("export default function Home() { return <div>Test</div> }")

        mock_parallel_gen.return_value = (["app/page.js"], 1)

        from backend.dev_loop_run_helpers import run_file_by_file_phase
        run_file_by_file_phase(mock_manager, "Erstelle Todo-App", "Keine Regeln")

        mock_parallel_gen.assert_called_once()
        assert "### FILENAME: app/page.js" in mock_manager.current_code
        assert mock_manager.is_first_run is False

    @patch("backend.dev_loop_run_helpers.run_file_by_file_loop", new_callable=AsyncMock)
    def test_sequenzieller_modus(self, mock_fbf_loop, mock_manager, tmp_path):
        """Sequenzieller Modus wird genutzt wenn parallel disabled."""
        mock_manager.config["parallel_file_generation"]["enabled"] = False

        lib_dir = tmp_path / "lib"
        lib_dir.mkdir()
        db_file = lib_dir / "db.js"
        db_file.write_text("export const db = {}")

        mock_fbf_loop.return_value = (True, "Alles ok", ["lib/db.js"])

        from backend.dev_loop_run_helpers import run_file_by_file_phase
        run_file_by_file_phase(mock_manager, "Erstelle App", "Regeln")

        mock_fbf_loop.assert_called_once()
        assert "### FILENAME: lib/db.js" in mock_manager.current_code

    @patch("backend.dev_loop_run_helpers._run_parallel_generation")
    def test_fehler_loest_fallback_aus(self, mock_parallel_gen, mock_manager):
        """Bei Fehler wird Warning geloggt und kein Crash."""
        mock_parallel_gen.side_effect = RuntimeError("LLM nicht erreichbar")

        from backend.dev_loop_run_helpers import run_file_by_file_phase
        # Sollte NICHT crashen
        run_file_by_file_phase(mock_manager, "Erstelle App", "Regeln")

        # Warning muss geloggt worden sein
        log_calls = [c for c in mock_manager._ui_log.call_args_list
                     if c[0][1] == "Warning"]
        assert len(log_calls) >= 1, "Erwartet: Warning-Log bei File-by-File Fehler"

    @patch("backend.dev_loop_run_helpers._run_parallel_generation")
    def test_keine_dateien_erstellt(self, mock_parallel_gen, mock_manager):
        """Wenn keine Dateien erstellt werden, bleibt current_code leer."""
        mock_parallel_gen.return_value = ([], 0)

        from backend.dev_loop_run_helpers import run_file_by_file_phase
        run_file_by_file_phase(mock_manager, "Erstelle App", "Regeln")

        # current_code wird nicht ueberschrieben, _fbf_created_files nicht gesetzt
        assert mock_manager.current_code == ""

    @patch("backend.dev_loop_run_helpers._run_parallel_generation")
    def test_first_run_flag_wird_gesetzt(self, mock_parallel_gen, mock_manager, tmp_path):
        """is_first_run wird nach File-by-File auf False gesetzt."""
        app_dir = tmp_path / "app"
        app_dir.mkdir()
        (app_dir / "page.js").write_text("export default function() {}")
        mock_parallel_gen.return_value = (["app/page.js"], 1)
        mock_manager.is_first_run = True

        from backend.dev_loop_run_helpers import run_file_by_file_phase
        run_file_by_file_phase(mock_manager, "Ziel", "Regeln")

        assert mock_manager.is_first_run is False

    @patch("backend.dev_loop_run_helpers._run_parallel_generation")
    def test_fbf_created_files_gespeichert(self, mock_parallel_gen, mock_manager, tmp_path):
        """Fix 55: _fbf_created_files wird fuer Iteration-0-Skip gespeichert."""
        app_dir = tmp_path / "app"
        app_dir.mkdir()
        (app_dir / "page.js").write_text("code")
        (app_dir / "layout.js").write_text("layout")
        mock_parallel_gen.return_value = (["app/page.js", "app/layout.js"], 2)

        from backend.dev_loop_run_helpers import run_file_by_file_phase
        run_file_by_file_phase(mock_manager, "Ziel", "Regeln")

        assert mock_manager._fbf_created_files == ["app/page.js", "app/layout.js"]


# =========================================================================
# Tests fuer _run_parallel_generation()
# =========================================================================

class TestRunParallelGeneration:
    """Tests fuer _run_parallel_generation() - Plan + parallele Generierung."""

    @patch("backend.dev_loop_run_helpers.run_parallel_file_generation", new_callable=AsyncMock)
    @patch("backend.dev_loop_run_helpers.get_file_list_from_plan")
    @patch("backend.dev_loop_run_helpers.get_file_descriptions_from_plan")
    @patch("backend.dev_loop_run_helpers.run_planner", new_callable=AsyncMock)
    def test_plan_wird_erstellt_und_ausgefuehrt(self, mock_planner, mock_descriptions,
                                                  mock_file_list, mock_parallel_gen, mock_manager):
        """Planner wird aufgerufen, Dateien parallel generiert."""
        mock_planner.return_value = [{"path": "app/page.js"}]
        mock_file_list.return_value = ["app/page.js", "lib/db.js"]
        mock_descriptions.return_value = {"app/page.js": "Hauptseite", "lib/db.js": "Datenbank"}
        mock_parallel_gen.return_value = (
            {"app/page.js": "code1", "lib/db.js": "code2"}, []
        )

        from backend.dev_loop_run_helpers import _run_parallel_generation

        loop = asyncio.new_event_loop()
        try:
            created, expected = _run_parallel_generation(
                loop, mock_manager, "Regeln", {"max_workers": 2}
            )
        finally:
            loop.close()

        assert set(created) == {"app/page.js", "lib/db.js"}
        assert expected == 2

    @patch("backend.dev_loop_run_helpers.run_parallel_file_generation", new_callable=AsyncMock)
    @patch("backend.dev_loop_run_helpers.get_file_list_from_plan")
    @patch("backend.dev_loop_run_helpers.get_file_descriptions_from_plan")
    @patch("backend.dev_loop_run_helpers.run_planner", new_callable=AsyncMock)
    def test_template_config_skip(self, mock_planner, mock_descriptions,
                                   mock_file_list, mock_parallel_gen, mock_manager, tmp_path):
        """Fix 49: Template-Config-Dateien werden uebersprungen wenn auf Disk."""
        # Erstelle tailwind.config.js auf Disk
        (tmp_path / "tailwind.config.js").write_text("module.exports = {}")

        mock_planner.return_value = []
        mock_file_list.return_value = ["tailwind.config.js", "app/page.js"]
        mock_descriptions.return_value = {
            "tailwind.config.js": "Tailwind Config",
            "app/page.js": "Hauptseite"
        }
        mock_parallel_gen.return_value = ({"app/page.js": "code"}, [])

        from backend.dev_loop_run_helpers import _run_parallel_generation

        loop = asyncio.new_event_loop()
        try:
            created, expected = _run_parallel_generation(
                loop, mock_manager, "Regeln", {"max_workers": 2}
            )
        finally:
            loop.close()

        # tailwind.config.js muss uebersprungen sein
        assert expected == 1, "Erwartet: 1 Datei (tailwind.config.js uebersprungen)"
        # TemplateSkip muss geloggt worden sein
        skip_logs = [c for c in mock_manager._ui_log.call_args_list
                     if c[0][1] == "TemplateSkip"]
        assert len(skip_logs) == 1

    @patch("backend.dev_loop_run_helpers.run_parallel_file_generation", new_callable=AsyncMock)
    @patch("backend.dev_loop_run_helpers.get_file_list_from_plan")
    @patch("backend.dev_loop_run_helpers.get_file_descriptions_from_plan")
    @patch("backend.dev_loop_run_helpers.run_planner", new_callable=AsyncMock)
    def test_stem_variante_wird_erkannt(self, mock_planner, mock_descriptions,
                                         mock_file_list, mock_parallel_gen, mock_manager, tmp_path):
        """Fix 52: next.config.mjs wird uebersprungen wenn next.config.js existiert."""
        (tmp_path / "next.config.js").write_text("module.exports = {}")

        mock_planner.return_value = []
        mock_file_list.return_value = ["next.config.mjs", "app/page.js"]
        mock_descriptions.return_value = {
            "next.config.mjs": "Next Config ESM",
            "app/page.js": "Hauptseite"
        }
        mock_parallel_gen.return_value = ({"app/page.js": "code"}, [])

        from backend.dev_loop_run_helpers import _run_parallel_generation

        loop = asyncio.new_event_loop()
        try:
            created, expected = _run_parallel_generation(
                loop, mock_manager, "Regeln", {"max_workers": 2}
            )
        finally:
            loop.close()

        assert expected == 1, "Erwartet: 1 Datei (next.config.mjs uebersprungen wegen .js Variante)"

    @patch("backend.dev_loop_run_helpers.run_parallel_file_generation", new_callable=AsyncMock)
    @patch("backend.dev_loop_run_helpers.get_file_list_from_plan")
    @patch("backend.dev_loop_run_helpers.get_file_descriptions_from_plan")
    @patch("backend.dev_loop_run_helpers.run_planner", new_callable=AsyncMock)
    def test_rate_limit_retry(self, mock_planner, mock_descriptions,
                               mock_file_list, mock_parallel_gen, mock_manager):
        """Rate-Limit-Fehler fuehren zu einem Retry nach 30s Wartezeit."""
        mock_planner.return_value = []
        mock_file_list.return_value = ["app/page.js", "lib/db.js"]
        mock_descriptions.return_value = {
            "app/page.js": "Hauptseite",
            "lib/db.js": "Datenbank"
        }
        # Erster Aufruf: page.js OK, db.js RateLimit-Fehler
        # Zweiter Aufruf (Retry): db.js OK
        mock_parallel_gen.side_effect = [
            ({"app/page.js": "code1"}, [("lib/db.js", "RateLimit 429")]),
            ({"lib/db.js": "code2"}, [])
        ]

        from backend.dev_loop_run_helpers import _run_parallel_generation

        loop = asyncio.new_event_loop()
        try:
            # asyncio.sleep mocken damit der Test nicht 30s wartet
            with patch.object(asyncio, "sleep", new_callable=AsyncMock):
                created, expected = _run_parallel_generation(
                    loop, mock_manager, "Regeln", {"max_workers": 2}
                )
        finally:
            loop.close()

        assert set(created) == {"app/page.js", "lib/db.js"}
        # Retry-Log muss vorhanden sein
        retry_logs = [c for c in mock_manager._ui_log.call_args_list
                      if c[0][1] == "ParallelRetry"]
        assert len(retry_logs) == 1

    @patch("backend.dev_loop_run_helpers.run_parallel_file_generation", new_callable=AsyncMock)
    @patch("backend.dev_loop_run_helpers.get_file_list_from_plan")
    @patch("backend.dev_loop_run_helpers.get_file_descriptions_from_plan")
    @patch("backend.dev_loop_run_helpers.run_planner", new_callable=AsyncMock)
    def test_fehler_ohne_rate_limit(self, mock_planner, mock_descriptions,
                                     mock_file_list, mock_parallel_gen, mock_manager):
        """Nicht-RateLimit-Fehler loesen keinen Retry aus."""
        mock_planner.return_value = []
        mock_file_list.return_value = ["app/page.js"]
        mock_descriptions.return_value = {"app/page.js": "Hauptseite"}
        mock_parallel_gen.return_value = (
            {}, [("app/page.js", "Timeout nach 750s")]
        )

        from backend.dev_loop_run_helpers import _run_parallel_generation

        loop = asyncio.new_event_loop()
        try:
            created, expected = _run_parallel_generation(
                loop, mock_manager, "Regeln", {"max_workers": 2}
            )
        finally:
            loop.close()

        assert created == []
        # Kein Retry-Log
        retry_logs = [c for c in mock_manager._ui_log.call_args_list
                      if c[0][1] == "ParallelRetry"]
        assert len(retry_logs) == 0

    @patch("backend.dev_loop_run_helpers.run_parallel_file_generation", new_callable=AsyncMock)
    @patch("backend.dev_loop_run_helpers.get_file_list_from_plan")
    @patch("backend.dev_loop_run_helpers.get_file_descriptions_from_plan")
    @patch("backend.dev_loop_run_helpers.run_planner", new_callable=AsyncMock)
    def test_coder_timeout_aus_config(self, mock_planner, mock_descriptions,
                                       mock_file_list, mock_parallel_gen, mock_manager):
        """Fix 53c: Timeout wird aus agent_timeouts.coder gelesen (Single Source)."""
        mock_manager.config["agent_timeouts"] = {"coder": 1800}

        mock_planner.return_value = []
        mock_file_list.return_value = ["app/page.js"]
        mock_descriptions.return_value = {"app/page.js": "Hauptseite"}
        mock_parallel_gen.return_value = ({"app/page.js": "code"}, [])

        from backend.dev_loop_run_helpers import _run_parallel_generation

        loop = asyncio.new_event_loop()
        try:
            _run_parallel_generation(loop, mock_manager, "Regeln", {})
        finally:
            loop.close()

        # Timeout muss 1800 sein (aus agent_timeouts.coder)
        gen_call = mock_parallel_gen.call_args
        assert gen_call.kwargs["timeout_per_file"] == 1800
        assert gen_call.kwargs["batch_timeout"] == 3600


# =========================================================================
# Tests fuer handle_truncation_recovery()
# =========================================================================

class TestHandleTruncationRecovery:
    """Tests fuer handle_truncation_recovery() - Reparatur abgeschnittener Dateien."""

    @patch("backend.dev_loop_run_helpers.run_sandbox_and_tests")
    @patch("backend.dev_loop_run_helpers.merge_repaired_files")
    @patch("backend.dev_loop_run_helpers.run_file_by_file_repair", new_callable=AsyncMock)
    def test_erfolgreiche_reparatur(self, mock_repair, mock_merge, mock_sandbox, mock_manager):
        """Erfolgreiche Reparatur aktualisiert current_code und fuehrt Sandbox-Tests durch."""
        mock_repair.return_value = (True, "Repariert", {"app/page.js": "reparierter Code"})
        mock_merge.return_value = "Zusammengefuehrter Code"
        mock_sandbox.return_value = ("OK", False, "Tests bestanden", None, "Zusammenfassung")

        from backend.dev_loop_run_helpers import handle_truncation_recovery

        result = handle_truncation_recovery(
            mock_manager, "Regeln", ["app/page.js"],
            "Erstelle App", ["lib/db.js"], iteration=0
        )

        assert result is not None
        sandbox_result, sandbox_failed, test_result, ui_result, test_summary, truncated, created = result
        assert sandbox_result == "OK"
        assert sandbox_failed is False
        assert truncated == []
        assert "app/page.js" in created

    @patch("backend.dev_loop_run_helpers.run_file_by_file_repair", new_callable=AsyncMock)
    def test_fehlgeschlagene_reparatur(self, mock_repair, mock_manager):
        """Fehlgeschlagene Reparatur gibt None zurueck."""
        mock_repair.return_value = (False, "Konnte nicht reparieren", None)

        from backend.dev_loop_run_helpers import handle_truncation_recovery

        result = handle_truncation_recovery(
            mock_manager, "Regeln", ["app/page.js"],
            "Erstelle App", [], iteration=0
        )

        assert result is None, "Erwartet: None bei fehlgeschlagener Reparatur"

    @patch("backend.dev_loop_run_helpers.run_file_by_file_repair", new_callable=AsyncMock)
    def test_exception_bei_reparatur(self, mock_repair, mock_manager):
        """Exception waehrend Reparatur gibt None zurueck und loggt Fehler."""
        mock_repair.side_effect = RuntimeError("Netzwerk-Fehler")

        from backend.dev_loop_run_helpers import handle_truncation_recovery

        result = handle_truncation_recovery(
            mock_manager, "Regeln", ["app/page.js"],
            "Erstelle App", [], iteration=0
        )

        assert result is None
        error_logs = [c for c in mock_manager._ui_log.call_args_list
                      if c[0][1] == "TruncationRecoveryError"]
        assert len(error_logs) == 1

    @patch("backend.dev_loop_run_helpers.run_sandbox_and_tests")
    @patch("backend.dev_loop_run_helpers.merge_repaired_files")
    @patch("backend.dev_loop_run_helpers.run_file_by_file_repair", new_callable=AsyncMock)
    def test_reparierte_datei_in_created_files(self, mock_repair, mock_merge,
                                                mock_sandbox, mock_manager):
        """Reparierte Dateien werden zu created_files hinzugefuegt (ohne Duplikate)."""
        mock_repair.return_value = (True, "OK", {"app/page.js": "code", "lib/utils.js": "code2"})
        mock_merge.return_value = "merged"
        mock_sandbox.return_value = ("OK", False, "OK", None, "OK")

        from backend.dev_loop_run_helpers import handle_truncation_recovery

        created_files = ["app/page.js"]  # page.js existiert schon
        result = handle_truncation_recovery(
            mock_manager, "Regeln", ["app/page.js", "lib/utils.js"],
            "Ziel", created_files, iteration=1
        )

        _, _, _, _, _, _, result_created = result
        # page.js war schon drin, utils.js muss hinzugefuegt sein
        assert result_created.count("app/page.js") == 1, "Erwartet: Kein Duplikat"
        assert "lib/utils.js" in result_created

    @patch("backend.dev_loop_run_helpers.run_sandbox_and_tests")
    @patch("backend.dev_loop_run_helpers.merge_repaired_files")
    @patch("backend.dev_loop_run_helpers.run_file_by_file_repair", new_callable=AsyncMock)
    def test_sandbox_nach_reparatur_fehlgeschlagen(self, mock_repair, mock_merge,
                                                    mock_sandbox, mock_manager):
        """Sandbox-Fehler nach Reparatur werden korrekt zurueckgegeben."""
        mock_repair.return_value = (True, "OK", {"app/page.js": "code"})
        mock_merge.return_value = "merged"
        mock_sandbox.return_value = ("Syntax-Fehler Zeile 5", True, "FAILED", None, "Fehler")

        from backend.dev_loop_run_helpers import handle_truncation_recovery

        result = handle_truncation_recovery(
            mock_manager, "Regeln", ["app/page.js"],
            "Ziel", [], iteration=0
        )

        sandbox_result, sandbox_failed, _, _, _, _, _ = result
        assert sandbox_failed is True
        assert "Syntax-Fehler" in sandbox_result


# =========================================================================
# Tests fuer handle_success_finalization()
# =========================================================================

class TestHandleSuccessFinalization:
    """Tests fuer handle_success_finalization() - QG + Waisen + Doc + Memory."""

    @patch("backend.dev_loop_run_helpers.update_memory")
    def test_basis_finalisierung(self, mock_memory, mock_manager):
        """Basis-Finalisierung loggt Security und Reviewer Status."""
        mock_manager.quality_gate = None
        delattr(mock_manager, "quality_gate")  # hasattr wird False
        mock_manager.doc_service = None
        delattr(mock_manager, "doc_service")

        from backend.dev_loop_run_helpers import handle_success_finalization

        handle_success_finalization(
            mock_manager, iteration=0, review_says_ok=True,
            sandbox_failed=False, security_passed=True,
            review_output="Alles ok", test_summary="Tests bestanden",
            created_files=["app/page.js"], sandbox_result="OK"
        )

        # Security und Reviewer Logs muessen vorhanden sein
        security_logs = [c for c in mock_manager._ui_log.call_args_list
                         if c[0][0] == "Security"]
        reviewer_logs = [c for c in mock_manager._ui_log.call_args_list
                         if c[0][0] == "Reviewer"]
        assert len(security_logs) >= 1
        assert len(reviewer_logs) >= 1

    @patch("backend.dev_loop_run_helpers.update_memory")
    def test_quality_gate_wird_aufgerufen(self, mock_memory, mock_manager):
        """QualityGate.validate_final() wird aufgerufen wenn vorhanden."""
        mock_qg = MagicMock()
        mock_qg.validate_final.return_value = MagicMock(
            passed=True, score=95, issues=[], warnings=[], details={"component_status": {}}
        )
        mock_manager.quality_gate = mock_qg
        mock_manager.traceability_manager = None
        delattr(mock_manager, "traceability_manager")
        mock_manager.doc_service = None
        delattr(mock_manager, "doc_service")

        from backend.dev_loop_run_helpers import handle_success_finalization

        handle_success_finalization(
            mock_manager, iteration=2, review_says_ok=True,
            sandbox_failed=False, security_passed=True,
            review_output="OK", test_summary="OK",
            created_files=["app/page.js"], sandbox_result="OK"
        )

        mock_qg.validate_final.assert_called_once()
        qg_logs = [c for c in mock_manager._ui_log.call_args_list
                   if c[0][0] == "QualityGate"]
        assert len(qg_logs) >= 1

    @patch("backend.dev_loop_run_helpers.update_memory")
    def test_waisen_check_wird_ausgefuehrt(self, mock_memory, mock_manager):
        """Fix 24: WaisenCheck prueft Traceability-Kette wenn vorhanden."""
        mock_qg = MagicMock()
        mock_qg.validate_final.return_value = MagicMock(
            passed=True, score=90, issues=[], warnings=[], details={"component_status": {}}
        )
        mock_qg.validate_waisen.return_value = MagicMock(
            passed=True, score=100, details={"waisen": {}, "counts": {}}
        )
        mock_manager.quality_gate = mock_qg

        mock_tm = MagicMock()
        mock_tm.get_matrix.return_value = {
            "anforderungen": {"A1": {"id": "A1"}},
            "features": {"F1": {"id": "F1"}},
            "tasks": {"T1": {"id": "T1", "dateien": ["app/page.js"]}}
        }
        mock_manager.traceability_manager = mock_tm
        mock_manager.doc_service = None
        delattr(mock_manager, "doc_service")

        from backend.dev_loop_run_helpers import handle_success_finalization

        handle_success_finalization(
            mock_manager, iteration=0, review_says_ok=True,
            sandbox_failed=False, security_passed=True,
            review_output="OK", test_summary="OK",
            created_files=["app/page.js"], sandbox_result="OK"
        )

        mock_qg.validate_waisen.assert_called_once()

    @patch("backend.dev_loop_run_helpers.update_memory")
    def test_doc_service_sammelt_daten(self, mock_memory, mock_manager):
        """DocService sammelt Iterations- und Test-Daten."""
        mock_ds = MagicMock()
        mock_manager.doc_service = mock_ds
        mock_manager.quality_gate = None
        delattr(mock_manager, "quality_gate")

        from backend.dev_loop_run_helpers import handle_success_finalization

        handle_success_finalization(
            mock_manager, iteration=3, review_says_ok=True,
            sandbox_failed=False, security_passed=True,
            review_output="Sehr gut", test_summary="Alle Tests ok",
            created_files=["app/page.js", "lib/db.js"], sandbox_result="OK"
        )

        mock_ds.collect_iteration.assert_called_once_with(
            iteration=4,  # iteration + 1
            changes="Code erfolgreich generiert und validiert",
            status="success",
            review_summary="Sehr gut"[:200],
            test_result="Alle Tests ok"[:100]
        )
        mock_ds.collect_test_result.assert_called_once()

    @patch("backend.dev_loop_run_helpers.update_memory")
    def test_memory_update_wird_ausgefuehrt(self, mock_memory, mock_manager):
        """Memory-Update wird via ThreadPoolExecutor aufgerufen."""
        mock_manager.quality_gate = None
        delattr(mock_manager, "quality_gate")
        mock_manager.doc_service = None
        delattr(mock_manager, "doc_service")

        from backend.dev_loop_run_helpers import handle_success_finalization

        handle_success_finalization(
            mock_manager, iteration=0, review_says_ok=True,
            sandbox_failed=False, security_passed=True,
            review_output="OK", test_summary="OK",
            created_files=[], sandbox_result="OK"
        )

        mock_memory.assert_called_once()
        memory_logs = [c for c in mock_manager._ui_log.call_args_list
                       if c[0][0] == "Memory" and c[0][1] == "Recording"]
        assert len(memory_logs) == 1

    @patch("backend.dev_loop_run_helpers.ThreadPoolExecutor")
    def test_memory_fehler_crasht_nicht(self, mock_executor_cls, mock_manager):
        """Memory-Fehler wird abgefangen und als Error geloggt."""
        mock_manager.quality_gate = None
        delattr(mock_manager, "quality_gate")
        mock_manager.doc_service = None
        delattr(mock_manager, "doc_service")

        # ThreadPoolExecutor.__enter__ wirft Exception
        mock_executor_cls.return_value.__enter__ = MagicMock(
            side_effect=Exception("DB Fehler")
        )

        from backend.dev_loop_run_helpers import handle_success_finalization

        # Sollte NICHT crashen
        handle_success_finalization(
            mock_manager, iteration=0, review_says_ok=True,
            sandbox_failed=False, security_passed=True,
            review_output="OK", test_summary="OK",
            created_files=[], sandbox_result="OK"
        )

        error_logs = [c for c in mock_manager._ui_log.call_args_list
                      if c[0][0] == "Memory" and c[0][1] == "Error"]
        assert len(error_logs) == 1

    @patch("backend.dev_loop_run_helpers.update_memory")
    def test_created_files_none_sicher(self, mock_memory, mock_manager):
        """created_files=None crasht nicht (None-Guard)."""
        mock_manager.quality_gate = None
        delattr(mock_manager, "quality_gate")
        mock_manager.doc_service = None
        delattr(mock_manager, "doc_service")

        from backend.dev_loop_run_helpers import handle_success_finalization

        # Sollte NICHT crashen
        handle_success_finalization(
            mock_manager, iteration=0, review_says_ok=True,
            sandbox_failed=False, security_passed=True,
            review_output="OK", test_summary="OK",
            created_files=None, sandbox_result="OK"
        )


# =========================================================================
# Tests fuer process_utds_feedback()
# =========================================================================

class TestProcessUtdsFeedback:
    """Tests fuer process_utds_feedback() - UTDS aus 3 Quellen."""

    def test_keine_quellen_aktiv(self, mock_manager, mock_task_derivation):
        """Ohne aktive Quellen bleibt Feedback unveraendert."""
        from backend.dev_loop_run_helpers import process_utds_feedback

        feedback, modified = process_utds_feedback(
            mock_task_derivation, mock_manager,
            feedback="Original-Feedback",
            created_files=["app/page.js"],
            security_passed=True,
            security_rescan_vulns=None,
            sandbox_failed=False,
            sandbox_result=None,
            test_summary=None,
            iteration=0
        )

        assert feedback == "Original-Feedback"
        assert modified == []

    def test_security_quelle(self, mock_manager, mock_task_derivation):
        """Security-Vulnerabilities werden als UTDS-Quelle verarbeitet."""
        mock_task_derivation.should_use_task_derivation.return_value = True
        mock_task_derivation.process_feedback.return_value = (True, "Security gefixt", ["app/api.js"])

        from backend.dev_loop_run_helpers import process_utds_feedback

        feedback, modified = process_utds_feedback(
            mock_task_derivation, mock_manager,
            feedback="Review sagt Fehler",
            created_files=["app/api.js"],
            security_passed=False,
            security_rescan_vulns=[{"severity": "high", "description": "XSS", "affected_file": "app/api.js"}],
            sandbox_failed=False,
            sandbox_result=None,
            test_summary=None,
            iteration=0
        )

        assert "app/api.js" in modified
        # process_feedback muss mit "security" aufgerufen worden sein
        sec_calls = [c for c in mock_task_derivation.process_feedback.call_args_list
                     if c[0][1] == "security"]
        assert len(sec_calls) >= 1

    def test_sandbox_quelle(self, mock_manager, mock_task_derivation):
        """Sandbox-Fehler werden als UTDS-Quelle verarbeitet."""
        mock_task_derivation.should_use_task_derivation.return_value = True
        mock_task_derivation.process_feedback.return_value = (True, "Sandbox gefixt", ["app/page.js"])

        from backend.dev_loop_run_helpers import process_utds_feedback

        feedback, modified = process_utds_feedback(
            mock_task_derivation, mock_manager,
            feedback="Review",
            created_files=["app/page.js"],
            security_passed=True,
            security_rescan_vulns=None,
            sandbox_failed=True,
            sandbox_result="SyntaxError in app/page.js",
            test_summary="1 Test fehlgeschlagen",
            iteration=1
        )

        assert "app/page.js" in modified

    def test_reviewer_quelle_fix53d_append(self, mock_manager, mock_task_derivation):
        """Fix 53d: UTDS-Feedback wird an Original-Feedback ANGEHAENGT statt es zu ersetzen."""
        mock_task_derivation.should_use_task_derivation.return_value = True
        mock_task_derivation.process_feedback.return_value = (
            True, "Task T1 erledigt", ["lib/db.js"]
        )

        from backend.dev_loop_run_helpers import process_utds_feedback

        original_feedback = "[DATEI:lib/db.js] SQL-Injection in addItem()"
        feedback, modified = process_utds_feedback(
            mock_task_derivation, mock_manager,
            feedback=original_feedback,
            created_files=["lib/db.js"],
            security_passed=True,
            security_rescan_vulns=None,
            sandbox_failed=False,
            sandbox_result=None,
            test_summary=None,
            iteration=2
        )

        # KRITISCH: Original-Feedback muss ENTHALTEN sein (Fix 53d)
        assert "[DATEI:lib/db.js]" in feedback, \
            "Erwartet: Original [DATEI:xxx] Pattern bleibt erhalten (Fix 53d)"
        assert "UTDS-STATUS" in feedback
        assert "lib/db.js" in modified

    def test_teilweise_fehlgeschlagen_security(self, mock_manager, mock_task_derivation):
        """Bei teilweisem Fehlschlag wird Status ans Feedback angehaengt."""
        # should_use = True fuer security, False fuer rest
        mock_task_derivation.should_use_task_derivation.side_effect = [True, False]
        mock_task_derivation.process_feedback.return_value = (
            False, "2 von 3 Tasks fehlgeschlagen", []
        )

        from backend.dev_loop_run_helpers import process_utds_feedback

        feedback, _ = process_utds_feedback(
            mock_task_derivation, mock_manager,
            feedback="Basis",
            created_files=[],
            security_passed=False,
            security_rescan_vulns=[{"severity": "medium", "description": "CSRF"}],
            sandbox_failed=False,
            sandbox_result=None,
            test_summary=None,
            iteration=0
        )

        assert "Security-Tasks Status" in feedback

    def test_drei_quellen_gleichzeitig(self, mock_manager, mock_task_derivation):
        """Alle 3 Quellen (Security, Sandbox, Reviewer) koennen gleichzeitig aktiv sein."""
        mock_task_derivation.should_use_task_derivation.return_value = True
        # Drei process_feedback Aufrufe: security, sandbox, reviewer
        mock_task_derivation.process_feedback.side_effect = [
            (True, "Security OK", ["sec.js"]),
            (True, "Sandbox OK", ["sb.js"]),
            (True, "Review OK", ["rev.js"]),
        ]

        from backend.dev_loop_run_helpers import process_utds_feedback

        feedback, modified = process_utds_feedback(
            mock_task_derivation, mock_manager,
            feedback="Review-Feedback",
            created_files=["sec.js", "sb.js", "rev.js"],
            security_passed=False,
            security_rescan_vulns=[{"severity": "high", "description": "XSS"}],
            sandbox_failed=True,
            sandbox_result="Fehler",
            test_summary="FAIL",
            iteration=0
        )

        assert "sec.js" in modified
        assert "sb.js" in modified
        assert "rev.js" in modified
        assert len(modified) == 3

    def test_security_vulns_string_format(self, mock_manager, mock_task_derivation):
        """Security-Vulnerabilities als einfache Strings werden korrekt formatiert."""
        mock_task_derivation.should_use_task_derivation.return_value = True
        mock_task_derivation.process_feedback.return_value = (True, "OK", [])

        from backend.dev_loop_run_helpers import process_utds_feedback

        process_utds_feedback(
            mock_task_derivation, mock_manager,
            feedback="FB",
            created_files=[],
            security_passed=False,
            security_rescan_vulns=["Einfache Vulnerability als String"],
            sandbox_failed=False,
            sandbox_result=None,
            test_summary=None,
            iteration=0
        )

        # security process_feedback muss aufgerufen worden sein
        sec_calls = [c for c in mock_task_derivation.process_feedback.call_args_list
                     if c[0][1] == "security"]
        assert len(sec_calls) == 1
        # Der Feedback-String muss "Security-Vulnerability:" enthalten
        assert "Security-Vulnerability:" in sec_calls[0][0][0]


# =========================================================================
# Tests fuer run_smoke_test_gate()
# =========================================================================

class TestRunSmokeTestGate:
    """Tests fuer run_smoke_test_gate() - Smoke-Test als Success-Bedingung."""

    def test_disabled_gibt_true_zurueck(self, mock_manager):
        """Deaktivierter Smoke-Test gibt (True, '') zurueck."""
        mock_manager.config["smoke_test"]["enabled"] = False

        from backend.dev_loop_run_helpers import run_smoke_test_gate
        passed, feedback = run_smoke_test_gate(mock_manager)

        assert passed is True
        assert feedback == ""

    @patch("backend.dev_loop_smoke_test.run_smoke_test")
    def test_bestanden(self, mock_smoke, mock_manager):
        """Bestandener Smoke-Test gibt (True, '') zurueck."""
        mock_smoke.return_value = MockSmokeTestResult(
            passed=True, server_started=True, page_loaded=True,
            duration_seconds=5.2
        )

        from backend.dev_loop_run_helpers import run_smoke_test_gate
        passed, feedback = run_smoke_test_gate(mock_manager)

        assert passed is True
        assert feedback == ""

    @patch("backend.dev_loop_smoke_test.run_smoke_test")
    def test_fehlgeschlagen(self, mock_smoke, mock_manager):
        """Fehlgeschlagener Smoke-Test gibt (False, feedback) zurueck."""
        mock_smoke.return_value = MockSmokeTestResult(
            passed=False, server_started=True, page_loaded=False,
            compile_errors=["Module not found: @/lib/utils"],
            duration_seconds=12.0,
            feedback_for_coder="SMOKE-TEST FEHLGESCHLAGEN: Module not found"
        )

        from backend.dev_loop_run_helpers import run_smoke_test_gate
        passed, feedback = run_smoke_test_gate(mock_manager)

        assert passed is False
        assert "SMOKE-TEST FEHLGESCHLAGEN" in feedback

    @patch("backend.dev_loop_smoke_test.run_smoke_test")
    def test_error_mit_skip_on_error(self, mock_smoke, mock_manager):
        """Exception mit skip_on_error=True gibt (True, '') zurueck."""
        mock_smoke.side_effect = RuntimeError("Playwright nicht installiert")
        mock_manager.config["smoke_test"]["skip_on_error"] = True

        from backend.dev_loop_run_helpers import run_smoke_test_gate
        passed, feedback = run_smoke_test_gate(mock_manager)

        assert passed is True, "Erwartet: True bei skip_on_error=True"
        assert feedback == ""

    @patch("backend.dev_loop_smoke_test.run_smoke_test")
    def test_error_ohne_skip_on_error(self, mock_smoke, mock_manager):
        """Exception mit skip_on_error=False gibt (False, feedback) zurueck."""
        mock_smoke.side_effect = RuntimeError("Server konnte nicht starten")
        mock_manager.config["smoke_test"]["skip_on_error"] = False

        from backend.dev_loop_run_helpers import run_smoke_test_gate
        passed, feedback = run_smoke_test_gate(mock_manager)

        assert passed is False
        assert "SMOKE-TEST FEHLER" in feedback

    @patch("backend.dev_loop_smoke_test.run_smoke_test")
    def test_worker_status_wird_aktualisiert(self, mock_smoke, mock_manager):
        """Worker-Status wird auf 'working' gesetzt und nach Test auf 'idle'."""
        mock_smoke.return_value = MockSmokeTestResult(
            passed=True, server_started=True, page_loaded=True,
            duration_seconds=3.0
        )

        from backend.dev_loop_run_helpers import run_smoke_test_gate
        run_smoke_test_gate(mock_manager)

        # Erster Aufruf: working, letzter: idle
        status_calls = mock_manager._update_worker_status.call_args_list
        assert status_calls[0][0][1] == "working"
        assert status_calls[-1][0][1] == "idle"

    @patch("backend.dev_loop_smoke_test.run_smoke_test")
    def test_docker_container_durchgereicht(self, mock_smoke, mock_manager):
        """Fix 50: Docker-Container wird an run_smoke_test durchgereicht."""
        mock_container = MagicMock()
        mock_manager._docker_container = mock_container
        mock_smoke.return_value = MockSmokeTestResult(
            passed=True, server_started=True, page_loaded=True,
            duration_seconds=2.0
        )

        from backend.dev_loop_run_helpers import run_smoke_test_gate
        run_smoke_test_gate(mock_manager)

        # docker_container muss als Parameter uebergeben worden sein
        smoke_call = mock_smoke.call_args
        assert smoke_call.kwargs.get("docker_container") == mock_container or \
               (len(smoke_call.args) > 3 and smoke_call.args[3] == mock_container) or \
               smoke_call[1].get("docker_container") == mock_container

    @patch("backend.dev_loop_smoke_test.run_smoke_test")
    def test_result_json_geloggt(self, mock_smoke, mock_manager):
        """Smoke-Test Ergebnis wird als JSON geloggt."""
        mock_smoke.return_value = MockSmokeTestResult(
            passed=True, server_started=True, page_loaded=True,
            compile_errors=[], console_errors=["Warning: React key"],
            duration_seconds=4.5
        )

        from backend.dev_loop_run_helpers import run_smoke_test_gate
        run_smoke_test_gate(mock_manager)

        result_logs = [c for c in mock_manager._ui_log.call_args_list
                       if c[0][0] == "SmokeTest" and c[0][1] == "Result"]
        assert len(result_logs) == 1
        # JSON parsen und pruefen
        logged_json = json.loads(result_logs[0][0][2])
        assert logged_json["passed"] is True
        assert logged_json["console_errors"] == 1
