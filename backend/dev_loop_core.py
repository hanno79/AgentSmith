"""
Author: rahn
Datum: 08.02.2026
Version: 1.0
Beschreibung: DevLoop-Klasse mit Haupt-Iterationslogik.
              Extrahiert aus dev_loop.py (Regel 1: Max 500 Zeilen).
              AENDERUNG 02.02.2026: FIX - Augment CLI PATH-Problem mit shutil.which() behoben.
              AENDERUNG 01.02.2026: Documenter + Memory Agent Integration.
              AENDERUNG 01.02.2026: OrchestratorValidator Integration.
              AENDERUNG 03.02.2026: TargetedFix ENTFERNT zugunsten von UTDS.
              AENDERUNG 03.02.2026: Unified Fix Mode - UTDS fuer alle Fehlerkorrekturen.
              AENDERUNG 08.02.2026: Aufspaltung aus dev_loop.py in dev_loop_core/augment/run_helpers.
"""

import os
import json
import logging
from typing import Dict, Any, Tuple
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

from agents.memory_agent import update_memory
from .dev_loop_steps import (
    build_coder_prompt,
    run_coder_task,
    save_coder_output,
    rebuild_current_code_from_disk,
    run_sandbox_and_tests,
    run_review,
    run_security_rescan,
    build_feedback,
    handle_model_switch
)
from .file_by_file_loop import should_use_file_by_file
from .orchestration_validator import OrchestratorValidator
from .dev_loop_task_derivation import DevLoopTaskDerivation
from .file_status_detector import FileStatusDetector
from server_runner import _normalize_package_json_versions
# AENDERUNG 08.02.2026: Fix 24 - Vier-Augen-Prinzip (Second Opinion Review)
from .dev_loop_second_opinion import run_second_opinion_review
# AENDERUNG 08.02.2026: Extrahierte Helfer-Funktionen
from .dev_loop_augment import get_augment_context
from .dev_loop_run_helpers import (
    run_file_by_file_phase,
    handle_truncation_recovery,
    handle_success_finalization,
    process_utds_feedback,
    run_smoke_test_gate
)
# AENDERUNG 09.02.2026: Fix 35 — Dateinamen-Extraktion fuer Ping-Pong-Erkennung
from .dev_loop_helpers import extract_filenames_from_feedback


import re
import hashlib


def _compute_feedback_signature(feedback: str, sandbox_result: str) -> str:
    """
    AENDERUNG 20.02.2026: Fix 58c — Normalisierte Feedback-Signatur.
    ROOT-CAUSE-FIX: Error-Hash aenderte sich pro Iteration (Zeilennummern, Zeitstempel)
    obwohl der Kern-Fehler identisch blieb → keine Stagnation erkannt.

    Extrahiert Kern-Fehlermuster aus Feedback und Sandbox-Ergebnis:
    - Entfernt Zeilennummern, Zeitstempel, variablen Content
    - Normalisiert auf Kern-Patterns ("no such table", "Module not found", etc.)

    Returns:
        Normalisierte Signatur (MD5-Hash) oder leerer String wenn kein Feedback
    """
    combined = (feedback or "") + (sandbox_result or "")
    if not combined.strip():
        return ""

    # Zeilennummern entfernen (z.B. "line 42", "Zeile 42", ":42:", "(42)")
    normalized = re.sub(r'(?:line|zeile|:)\s*\d+', '', combined, flags=re.IGNORECASE)
    normalized = re.sub(r'\(\d+\)', '', normalized)
    # Zeitstempel entfernen
    normalized = re.sub(r'\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}', '', normalized)
    # Hex-Hashes entfernen (z.B. Error-IDs)
    normalized = re.sub(r'[0-9a-f]{8,}', '', normalized)
    # Whitespace normalisieren
    normalized = re.sub(r'\s+', ' ', normalized).strip().lower()

    # Kern-Pattern extrahieren (Top-20 wiederkehrende Fehlermuster)
    core_patterns = []
    _ERROR_PATTERNS = [
        "no such table", "module not found", "cannot read properties",
        "failed to compile", "syntaxerror", "referenceerror", "typeerror",
        "cannot find module", "unexpected token", "is not defined",
        "import error", "hydration", "missing required", "sqlite_error",
        "enoent", "permission denied", "timeout", "connection refused",
        "unhandled rejection", "cannot resolve"
    ]
    for pattern in _ERROR_PATTERNS:
        if pattern in normalized:
            core_patterns.append(pattern)

    # Signatur: Hash aus Kern-Patterns + normalisiertem Text (erste 500 Zeichen)
    signature_input = "|".join(sorted(core_patterns)) + "||" + normalized[:500]
    return hashlib.md5(signature_input.encode()).hexdigest()[:16]


class DevLoop:
    def __init__(self, manager, set_current_agent, run_with_timeout):
        self.manager = manager
        self.set_current_agent = set_current_agent
        self.run_with_timeout = run_with_timeout
        # AENDERUNG 01.02.2026: OrchestratorValidator fuer zentrale Prueflogik
        self._orchestrator_validator = OrchestratorValidator(
            manager=manager,
            model_router=manager.model_router,
            config=manager.config
        )
        # AENDERUNG 01.02.2026: Universal Task Derivation System (UTDS)
        self._task_derivation = DevLoopTaskDerivation(manager, manager.config)
        # AENDERUNG 05.02.2026: FileStatusDetector fuer gezielte Fixes
        self._file_detector = FileStatusDetector(str(manager.project_path))

    def run(
        self,
        user_goal: str,
        project_rules: Dict[str, Any],
        agent_coder,
        agent_reviewer,
        agent_tester,
        agent_security,
        project_id: str
    ) -> Tuple[bool, str]:
        manager = self.manager
        manager.agent_coder = agent_coder
        manager.agent_reviewer = agent_reviewer
        manager.agent_tester = agent_tester
        manager.agent_security = agent_security

        # AENDERUNG 09.02.2026: Fix 40b - Agent-Kontext VOR paralleler Generierung setzen
        # ROOT-CAUSE-FIX:
        # Symptom: Coder-LLM-Aufrufe in Iteration 0 werden als "Designer" getrackt
        # Ursache: set_current_agent("Designer") aus orchestration_phases.py war noch aktiv
        # Loesung: Explizit "Coder" setzen bevor der parallele File-Generator startet
        self.set_current_agent("Coder", project_id)

        # AENDERUNG 31.01.2026: File-by-File Modus bei komplexen Projekten
        # AENDERUNG 01.02.2026: Parallele Generierung mit dynamischer Worker-Anzahl
        if should_use_file_by_file(manager.tech_blueprint, manager.config):
            run_file_by_file_phase(manager, user_goal, project_rules)

        max_retries = manager.config.get("max_retries", 3)
        feedback = ""
        iteration = 0
        manager._current_iteration = 0
        success = False
        security_retry_count = 0
        max_security_retries = manager.config.get("max_security_retries", 3)

        model_attempt = 0
        max_model_attempts = manager.config.get("max_model_attempts", 3)
        current_coder_model = manager.model_router.get_model("coder")
        models_used = [current_coder_model]
        failed_attempts_history = []
        # AENDERUNG 06.02.2026: ROOT-CAUSE-FIX PatchModeFallback
        _utds_modified_files = []
        # AENDERUNG 09.02.2026: Fix 35 — Ping-Pong-Erkennung + Iteration Memory
        _iteration_history = []           # Feedback-Historie pro Iteration
        _utds_protected_files = []        # UTDS-gefixte Dateien (geschuetzt fuer naechste Iteration)
        _file_feedback_counter = {}       # Ping-Pong Counter pro Datei
        # AENDERUNG 10.02.2026: Fix 45 — Symptom-basierte Eskalation
        # ROOT-CAUSE-FIX: Leere Seite ueber 3+ Iterationen → Modellwechsel erzwingen
        # Unabhaengig vom Error-Hash (der sich jede Iteration aendert)
        _empty_page_counter = 0
        # AENDERUNG 20.02.2026: Fix 58c — Feedback-Stagnation-Erkennung
        # ROOT-CAUSE-FIX: Tabellen-Mismatch wiederholte sich 10x ohne Modellwechsel
        # weil Error-Hash sich minimal aenderte (Zeilennummer) obwohl Kern-Fehler gleich blieb
        _last_feedback_signature = ""
        _stagnation_counter = 0
        # AENDERUNG 21.02.2026: Fix 59h — SDK Tier-Eskalation bei PingPong
        # Wenn PingPong >= 3: Haiku→Sonnet, >= 6: Sonnet→Opus
        manager._sdk_tier_escalation = None

        while iteration < max_retries:
            manager.iteration = iteration
            manager.max_retries = max_retries
            manager._ui_log("Coder", "Iteration", f"{iteration + 1} / {max_retries}")

            self.set_current_agent("Coder", project_id)
            coder_model = manager.model_router.get_model("coder") if manager.model_router else "unknown"
            manager._update_worker_status("coder", "working", f"Iteration {iteration + 1}/{max_retries}", coder_model)

            # AENDERUNG 03.02.2026: ROOT-CAUSE-FIX - try-finally fuer sicheren idle-Reset
            try:
                # AENDERUNG 09.02.2026: Fix 35 — UTDS-Dateien als geschuetzt markieren statt an Coder leiten
                # ROOT-CAUSE-FIX:
                # Symptom: Coder regeneriert Dateien die UTDS gerade gefixt hat (Ping-Pong)
                # Ursache: _utds_modified_files wurde als files_to_patch an Coder gegeben
                # Folge: Coder ueberschrieb UTDS-Fixes mit fehlerhaftem Code
                # Loesung: UTDS-Dateien als "protected" markieren → Coder fasst sie nicht an
                _utds_protected_files = list(set(_utds_modified_files)) if _utds_modified_files else []
                _utds_modified_files = []

                # AENDERUNG 13.02.2026: Fix 55 — Skip FullMode nach File-by-File
                # ROOT-CAUSE-FIX:
                # Symptom: Iteration 0 regeneriert alle 15 Dateien in 30 Min FullMode
                # Ursache: feedback="" → ParallelPatch-Bedingung False → Standard-Coder
                # Loesung: Wenn File-by-File bereits Code generiert hat, Coder ueberspringen
                _fbf_files = getattr(manager, '_fbf_created_files', None)
                _skip_coder = iteration == 0 and _fbf_files and manager.current_code

                # AENDERUNG 10.02.2026: Fix 48 — Paralleler PatchMode
                _is_patch = not getattr(manager, 'is_first_run', True)
                _use_parallel = False

                if _skip_coder:
                    manager._ui_log("Coder", "SkipAfterFBF",
                        f"File-by-File hat {len(_fbf_files)} Dateien generiert "
                        "- ueberspringe Coder, starte Tests+Review direkt")
                    created_files = list(_fbf_files)
                    truncated_files = []
                elif _is_patch and feedback:
                    from .dev_loop_parallel_patch import should_use_parallel_patch, run_parallel_patch
                    from .dev_loop_coder_utils import _get_affected_files_from_feedback, _get_current_code_dict
                    _pp_affected = _get_affected_files_from_feedback(feedback)
                    _pp_code_dict = _get_current_code_dict(manager) if _pp_affected else {}
                    _pp_config = manager.config.get("parallel_patch", {})

                    if _pp_affected and should_use_parallel_patch(_pp_affected, _pp_code_dict, _pp_config):
                        _use_parallel = True
                        manager._ui_log("Coder", "ParallelPatchMode",
                            f"Paralleler Patch fuer {len(_pp_affected)} Dateien in "
                            f"{len(_pp_affected) // _pp_config.get('max_files_per_group', 3) + 1} Gruppen")
                        manager.current_code, created_files = run_parallel_patch(
                            manager, _pp_affected, _pp_code_dict, feedback, project_rules,
                            user_goal=user_goal, iteration=iteration,
                            utds_protected_files=_utds_protected_files,
                            iteration_history=_iteration_history
                        )
                        truncated_files = []  # Truncation wird IN run_parallel_patch behandelt

                if not _skip_coder and not _use_parallel:
                    # STANDARD: Einzelner Coder (wie bisher)
                    c_prompt = build_coder_prompt(
                        manager, user_goal, feedback, iteration,
                        utds_protected_files=_utds_protected_files,
                        iteration_history=_iteration_history
                    )
                    manager.current_code, manager.agent_coder = run_coder_task(manager, project_rules, c_prompt, manager.agent_coder)
                    created_files, truncated_files = save_coder_output(
                        manager, manager.current_code, manager.output_path,
                        iteration, max_retries, is_patch_mode=_is_patch
                    )

                # AENDERUNG 07.02.2026: Version-Normalisierung direkt nach Code-Speicherung
                if manager.output_path and os.path.exists(str(manager.output_path)):
                    _normalize_package_json_versions(str(manager.output_path))

                # ROOT-CAUSE-FIX 07.02.2026: PatchMode Merge
                if manager.project_path and os.path.exists(str(manager.project_path)):
                    manager.current_code = rebuild_current_code_from_disk(manager)
            finally:
                manager._update_worker_status("coder", "idle")

            # AENDERUNG 03.02.2026: is_first_run nach erster Iteration auf False setzen
            if manager.is_first_run and iteration == 0:
                manager.is_first_run = False
                manager._ui_log("System", "FirstRunComplete", "Erste Iteration abgeschlossen - PatchMode aktiviert")

            # AENDERUNG 30.01.2026: Quality Gate - Code Validierung nach jeder Iteration
            if hasattr(manager, 'quality_gate') and manager.current_code:
                code_validation = manager.quality_gate.validate_code(
                    manager.current_code, manager.tech_blueprint
                )
                manager._ui_log("QualityGate", "CodeValidation", json.dumps({
                    "step": "Code",
                    "iteration": iteration + 1,
                    "passed": code_validation.passed,
                    "score": code_validation.score,
                    "issues": code_validation.issues,
                    "warnings": code_validation.warnings
                }, ensure_ascii=False))
                if hasattr(manager, 'doc_service') and manager.doc_service:
                    for cf in (created_files or []):
                        manager.doc_service.collect_code_file(cf, manager.current_code, f"Iteration {iteration + 1}")

            sandbox_result, sandbox_failed, test_result, ui_result, test_summary = run_sandbox_and_tests(
                manager,
                manager.current_code,
                created_files,
                iteration,
                manager.tech_blueprint.get("project_type", "webapp")
            )

            # AENDERUNG 31.01.2026: Truncation als Sandbox-Fehler behandeln
            if truncated_files:
                truncation_msg = f"TRUNCATION: Dateien abgeschnitten durch Token-Limit: {', '.join([f[0] for f in truncated_files])}"
                sandbox_failed = True
                sandbox_result = f"{sandbox_result}\n{truncation_msg}" if sandbox_result else truncation_msg
                manager._ui_log("Coder", "TruncationError", json.dumps({
                    "message": "Truncation wird als Fehler behandelt fuer Modellwechsel",
                    "truncated_count": len(truncated_files),
                    "files": [f[0] for f in truncated_files]
                }, ensure_ascii=False))

                # AENDERUNG 01.02.2026: Truncation Recovery
                recovery = handle_truncation_recovery(
                    manager, project_rules, truncated_files,
                    user_goal, created_files, iteration
                )
                if recovery is not None:
                    sandbox_result, sandbox_failed, test_result, ui_result, test_summary, truncated_files, created_files = recovery

            self.set_current_agent("Reviewer", project_id)
            review_output, review_verdict, _ = run_review(
                manager,
                project_rules,
                manager.current_code,
                sandbox_result,
                test_summary,
                sandbox_failed,
                self.run_with_timeout
            )

            # AENDERUNG 01.02.2026: Augment Context bei wiederholten Fehlern
            augment_context = ""
            if sandbox_failed and iteration >= 2:
                augment_context = get_augment_context(
                    manager, sandbox_result, review_output, iteration
                )
                if augment_context:
                    review_output = f"{review_output}\n\n[AUGMENT ARCHITEKTUR-ANALYSE]\n{augment_context}"

            # AENDERUNG 30.01.2026: Quality Gate - Review Validierung
            if hasattr(manager, 'quality_gate') and review_output:
                review_validation = manager.quality_gate.validate_review(
                    review_output, manager.current_code, manager.tech_blueprint
                )
                manager._ui_log("QualityGate", "ReviewValidation", json.dumps({
                    "step": "Review",
                    "iteration": iteration + 1,
                    "passed": review_validation.passed,
                    "score": review_validation.score,
                    "issues": review_validation.issues,
                    "warnings": review_validation.warnings
                }, ensure_ascii=False))

            self.set_current_agent("Security", project_id)
            security_passed, security_rescan_vulns = run_security_rescan(
                manager,
                project_rules,
                manager.current_code,
                iteration
            )

            # AENDERUNG 30.01.2026: Quality Gate - Security Validierung
            if hasattr(manager, 'quality_gate'):
                vuln_list = []
                if security_rescan_vulns:
                    for v in security_rescan_vulns:
                        if isinstance(v, dict):
                            vuln_list.append(v)
                        elif isinstance(v, str):
                            vuln_list.append({"description": v, "severity": "medium"})
                security_validation = manager.quality_gate.validate_security(
                    vuln_list, severity_threshold="high"
                )
                manager._ui_log("QualityGate", "SecurityValidation", json.dumps({
                    "step": "Security",
                    "iteration": iteration + 1,
                    "passed": security_validation.passed,
                    "score": security_validation.score,
                    "issues": security_validation.issues,
                    "warnings": security_validation.warnings,
                    "vulnerabilities_by_severity": security_validation.details.get("vulnerabilities_by_severity", {})
                }, ensure_ascii=False))
                if hasattr(manager, 'doc_service') and manager.doc_service:
                    for v in vuln_list:
                        manager.doc_service.collect_security_finding(v)

            if not security_passed:
                security_retry_count += 1
                if security_retry_count >= max_security_retries:
                    manager._ui_log(
                        "Security",
                        "Warning",
                        f"{len(security_rescan_vulns)} Security-Issues nach {security_retry_count} Versuchen nicht behoben. "
                        f"Fahre mit Warnung fort (keine Blockade)."
                    )
                    security_passed = True
                    try:
                        from backend.session_manager import get_session_manager
                        get_session_manager().clear_agent_blocked("security")
                    except Exception:
                        pass
            else:
                try:
                    from backend.session_manager import get_session_manager
                    get_session_manager().clear_agent_blocked("security")
                except Exception:
                    pass

            # AENDERUNG 06.02.2026: ROOT-CAUSE-FIX Endlos-Iteration trotz Reviewer-OK
            review_says_ok = review_verdict == "OK"
            file_count = len(created_files) if created_files else 0
            manager._ui_log("Debug", "LoopDecision", json.dumps({
                "iteration": iteration + 1,
                "review_output_preview": review_output[:200] if review_output else "",
                "review_says_ok": review_says_ok,
                "sandbox_failed": sandbox_failed,
                "security_passed": security_passed,
                "security_retry_count": security_retry_count,
                "created_files_count": file_count,
                "has_minimum_files": file_count >= 3,
                "will_break": review_says_ok and not sandbox_failed and security_passed and file_count >= 3
            }, ensure_ascii=False))

            created_count = len(created_files) if created_files else 0
            has_minimum_files = created_count >= 3

            if review_says_ok and not sandbox_failed and security_passed and has_minimum_files:

                # AENDERUNG 13.02.2026: Features auf "review" setzen (vor Smoke-Test)
                try:
                    from backend.feature_tracking_db import get_feature_tracking_db
                    _fdb = get_feature_tracking_db()
                    _fdb_run_id = getattr(manager, '_stats_run_id', None) or project_id
                    for _feat in _fdb.get_features(_fdb_run_id, status="in_progress"):
                        _fdb.update_status(_feat["id"], "review")
                    manager._ui_log("System", "FeatureStats", json.dumps(
                        _fdb.get_stats(_fdb_run_id), ensure_ascii=False))
                except Exception:
                    pass

                # AENDERUNG 10.02.2026: Fix 43 - Smoke-Test als blockierende Success-Bedingung
                # ROOT-CAUSE-FIX:
                # Symptom: DevLoop deklariert Success obwohl Projekt nicht im Browser startet
                # Ursache: Kein echter Server-Start + Browser-Verify vor Success
                # Loesung: Smoke-Test BLOCKIERT Success wenn App nicht startet/rendert
                smoke_passed, smoke_feedback = run_smoke_test_gate(manager)
                if not smoke_passed:
                    feedback = smoke_feedback
                    sandbox_failed = True
                    sandbox_result = f"{sandbox_result}\n\n{smoke_feedback}" if sandbox_result else smoke_feedback
                    iteration += 1
                    manager._current_iteration = iteration
                    continue

                # AENDERUNG 08.02.2026: Fix 24 - Vier-Augen-Prinzip (Second Opinion Review)
                vier_augen_enabled = manager.config.get("vier_augen", {}).get("enabled", False)
                if vier_augen_enabled and review_verdict == "OK":
                    primary_model = manager.model_router.get_model("reviewer") if manager.model_router else None
                    if primary_model:
                        agrees, second_feedback, second_model = run_second_opinion_review(
                            manager, project_rules, manager.current_code,
                            sandbox_result, test_summary, sandbox_failed, primary_model
                        )
                        if not agrees:
                            review_says_ok = False
                            review_output = f"{review_output}\n\n[VIER-AUGEN FEEDBACK ({second_model})]\n{second_feedback}"
                            manager._ui_log("SecondOpinion", "Dissent",
                                f"Vier-Augen: Zweite Meinung widerspricht - Iteration wird wiederholt")
                            continue

                # AENDERUNG 08.02.2026: Fix 33 - External Bureau Review (CodeRabbit)
                # ROOT-CAUSE-FIX:
                # Symptom: Code wird nur von internen LLMs reviewed - blinde Flecken moeglich
                # Ursache: External Bureau Infrastruktur gebaut aber nie aus DevLoop aufgerufen
                # Loesung: CodeRabbit als zusaetzliche Qualitaetsschicht nach Vier-Augen
                ext_cfg = manager.config.get("external_specialists", {})
                if ext_cfg.get("enabled", False) and hasattr(manager, 'external_bureau') and manager.external_bureau:
                    from .dev_loop_external_review import run_external_review
                    ext_passed, ext_feedback, ext_findings = run_external_review(manager, created_files)
                    if not ext_passed:
                        review_says_ok = False
                        review_output = f"{review_output}\n\n[CODERABBIT REVIEW]\n{ext_feedback}"
                        manager._ui_log("CodeRabbit", "Findings",
                            f"External Review: {len(ext_findings)} Issue(s) - Iteration wird wiederholt")
                        continue
                    else:
                        info_count = len(ext_findings) if ext_findings else 0
                        manager._ui_log("CodeRabbit", "OK",
                            f"External Review bestanden ({info_count} Info-Findings)")

                success = True

                # AENDERUNG 13.02.2026: Alle Features auf "done" setzen bei Erfolg
                try:
                    from backend.feature_tracking_db import get_feature_tracking_db
                    _fdb = get_feature_tracking_db()
                    _fdb_run_id = getattr(manager, '_stats_run_id', None) or project_id
                    for _feat in _fdb.get_features(_fdb_run_id):
                        if _feat["status"] not in ("done", "failed"):
                            _fdb.mark_done(_feat["id"])
                    manager._ui_log("System", "FeatureStats", json.dumps(
                        _fdb.get_stats(_fdb_run_id), ensure_ascii=False))
                except Exception as _fdb_err:
                    logger.warning("Feature-Tracking Success-Update: %s", _fdb_err)

                handle_success_finalization(
                    manager, iteration, review_says_ok,
                    sandbox_failed, security_passed,
                    review_output, test_summary,
                    created_files, sandbox_result
                )
                break

            if review_says_ok and not has_minimum_files:
                manager._ui_log("Orchestrator", "Status", f"Nur {created_count} Dateien erstellt - generiere weitere...")
                feedback = f"Bitte weitere Dateien generieren. Bisher nur {created_count} Datei(en). "
                feedback += "Ein vollstaendiges Projekt braucht mindestens Backend, Config/Requirements und README oder Tests."
                iteration += 1
                manager._current_iteration = iteration
                continue

            # AENDERUNG 01.02.2026: OrchestratorValidator (Fix 30: None-Filter)
            current_files = {}
            for fp in filter(None, created_files or []):
                full_p = os.path.join(manager.project_path, fp)
                if os.path.exists(full_p):
                    try:
                        with open(full_p, "r", encoding="utf-8") as f:
                            current_files[fp] = f.read()
                    except Exception:
                        pass

            validator_decision = self._orchestrator_validator.validate_review_output(
                review_output=review_output, review_verdict=review_verdict,
                sandbox_result=sandbox_result, sandbox_failed=sandbox_failed,
                current_code=manager.current_code, current_files=current_files,
                current_model=current_coder_model)

            manager._ui_log("Orchestrator", "ValidationDecision", json.dumps({
                "action": validator_decision.action.value, "target": validator_decision.target_agent,
                "model_switch": validator_decision.model_switch_recommended,
                "root_cause": validator_decision.root_cause is not None,
                "error_hash": validator_decision.error_hash[:8] if validator_decision.error_hash else None}, ensure_ascii=False))

            if hasattr(manager, 'doc_service') and manager.doc_service:
                manager.doc_service.collect_orchestrator_decision(
                    iteration=iteration + 1, action=validator_decision.action.value,
                    target_agent=validator_decision.target_agent, root_cause=validator_decision.root_cause,
                    model_switch=validator_decision.model_switch_recommended, error_hash=validator_decision.error_hash)

            if validator_decision.root_cause:
                try:
                    mem_path = os.path.join(manager.base_dir, "memory", "global_memory.json")
                    ThreadPoolExecutor(max_workers=1).submit(update_memory, mem_path,
                        f"Root Cause (Iter {iteration+1}): {validator_decision.root_cause[:500]}",
                        f"Action: {validator_decision.action.value}", sandbox_result[:500] if sandbox_result else "")
                    manager._ui_log("Memory", "OrchestratorDecision", f"Root Cause aufgezeichnet (Iter {iteration+1})")
                except Exception as e:
                    manager._ui_log("Memory", "Warning", f"Memory-Aufzeichnung fehlgeschlagen: {e}")

            if validator_decision.root_cause:
                feedback = validator_decision.feedback
                manager._ui_log("Orchestrator", "RootCauseEnhanced", "Root Cause Analyse im Feedback")
            else:
                feedback = build_feedback(manager, review_output, review_verdict, sandbox_failed,
                    sandbox_result, test_summary, test_result, security_passed, security_rescan_vulns)
            manager._ui_log("Reviewer", "Feedback", feedback)

            if hasattr(manager, '_handle_help_needed_events'):
                help_result = manager._handle_help_needed_events(iteration)
                if help_result.get("actions"):
                    manager._ui_log("HelpHandler", "Summary", f"Aktionen: {len(help_result['actions'])}")
                    if any(a.get("action") == "test_generator" and a.get("success") for a in help_result["actions"]):
                        feedback += "\n\nHINWEIS: Unit-Tests wurden automatisch generiert."

            # AENDERUNG 01.02.2026: UTDS Feedback Processing
            feedback, new_utds_files = process_utds_feedback(
                self._task_derivation, manager, feedback,
                created_files, security_passed, security_rescan_vulns,
                sandbox_failed, sandbox_result, test_summary, iteration
            )
            _utds_modified_files.extend(new_utds_files)

            # AENDERUNG 21.02.2026: Fix 59e — Fehlende-Datei-Erkennung
            # ROOT-CAUSE-FIX:
            # Symptom: PatchMode kann keine neuen Dateien erstellen → Endlosschleife
            # Ursache: fetch('/api/ideas') in page.js aber app/api/ideas/route.js fehlt
            # Loesung: Referenzierte-aber-fehlende Dateien erkennen und ins Feedback einbauen
            from .dev_loop_coder_utils import detect_missing_files
            _missing_files = detect_missing_files(manager)
            if _missing_files:
                missing_info = "\n\nFEHLENDE DATEIEN (MUESSEN ERSTELLT WERDEN):\n"
                for mf in _missing_files:
                    missing_info += f"- {mf['file']}: {mf['reason']}\n"
                missing_info += "\nWICHTIG: Diese Dateien muessen im NAECHSTEN Output "
                missing_info += "als ### FILENAME: <pfad> enthalten sein!\n"
                feedback += missing_info
                manager._missing_files = _missing_files
                manager._ui_log("Orchestrator", "MissingFiles",
                    f"{len(_missing_files)} fehlende Dateien erkannt: "
                    f"{[mf['file'] for mf in _missing_files[:5]]}")
            else:
                manager._missing_files = []

            # AENDERUNG 09.02.2026: Fix 35 — Iteration-History und Ping-Pong-Counter
            _feedback_files = extract_filenames_from_feedback(feedback)
            _iteration_history.append({
                "iteration": iteration + 1,
                "feedback_files": _feedback_files,
                "utds_fixed": list(new_utds_files),
                "verdict": review_verdict
            })
            # Ping-Pong Counter: Dateien die wiederholt im Feedback auftauchen
            for _fname in _feedback_files:
                _file_feedback_counter[_fname] = _file_feedback_counter.get(_fname, 0) + 1
            for _fname in list(_file_feedback_counter.keys()):
                if _fname not in _feedback_files:
                    _file_feedback_counter[_fname] = 0
            _pp_files = [f for f, c in _file_feedback_counter.items() if c >= 3]
            if _pp_files:
                manager._ui_log("Orchestrator", "PingPongDetected", json.dumps(
                    {"files": _pp_files, "counts": {f: _file_feedback_counter[f] for f in _pp_files}}, ensure_ascii=False))

                # AENDERUNG 20.02.2026: Fix 57c — PingPong bricht Sandbox-Zyklus
                # ROOT-CAUSE-FIX: PingPong-Dateien mit >= 5 Iterationen die NUR
                # Sandbox-Fehler verursachen blockieren endlos. Override wenn ALLE
                # Sandbox-Fehler von PingPong-Dateien stammen (= false positives)
                _pp_severe = [f for f in _pp_files
                              if _file_feedback_counter.get(f, 0) >= 5]
                if _pp_severe and sandbox_failed and sandbox_result:
                    _sandbox_lines = [
                        line for line in sandbox_result.split("\n")
                        if line.strip().startswith("[") and "❌" not in line[:5]
                    ]
                    # Extrahiere Dateinamen aus Sandbox-Fehlerzeilen [filename]
                    _sandbox_error_lines = [
                        line for line in sandbox_result.split("\n")
                        if line.strip().startswith("[") and "]" in line
                    ]
                    _non_pp_errors = [
                        line for line in _sandbox_error_lines
                        if not any(pp in line for pp in _pp_severe)
                    ]
                    if not _non_pp_errors:
                        manager._ui_log("Orchestrator", "PingPongOverride",
                            f"Sandbox-Fehler fuer {len(_pp_severe)} PingPong-Dateien "
                            f"ignoriert (>= 5 Iterationen): {_pp_severe}")
                        sandbox_failed = False

                # AENDERUNG 21.02.2026: Fix 59h — SDK Tier-Eskalation bei PingPong
                # Wenn ein Problem trotz 3+ Iterationen nicht geloest wird, eskaliere:
                # Haiku(fix)→Sonnet(coder)→Opus(researcher)
                _max_pp_count = max(_file_feedback_counter[f] for f in _pp_files)
                if _max_pp_count >= 6 and manager._sdk_tier_escalation != "researcher":
                    manager._sdk_tier_escalation = "researcher"  # → Opus
                    manager._ui_log("Orchestrator", "TierEscalation",
                        f"PingPong >= 6 Iterationen ({_max_pp_count}x) — eskaliere SDK auf Opus")
                elif _max_pp_count >= 3 and not manager._sdk_tier_escalation:
                    manager._sdk_tier_escalation = "coder"  # → Sonnet
                    manager._ui_log("Orchestrator", "TierEscalation",
                        f"PingPong >= 3 Iterationen ({_max_pp_count}x) — eskaliere SDK auf Sonnet")
            else:
                # Kein PingPong mehr → Tier-Eskalation zuruecksetzen
                if getattr(manager, '_sdk_tier_escalation', None):
                    manager._ui_log("Orchestrator", "TierReset",
                        "PingPong aufgeloest — SDK Tier-Eskalation zurueckgesetzt")
                    manager._sdk_tier_escalation = None

            if hasattr(manager, 'doc_service') and manager.doc_service:
                manager.doc_service.collect_iteration(
                    iteration=iteration + 1, changes=feedback[:300] if feedback else "Keine",
                    status="partial" if not sandbox_failed else "failed",
                    review_summary=review_output[:200] if review_output else "",
                    test_result=test_summary[:100] if test_summary else "")
            try:
                ThreadPoolExecutor(max_workers=1).submit(update_memory, os.path.join(
                    manager.base_dir, "memory", "global_memory.json"),
                    manager.current_code, review_output, sandbox_result)
            except Exception as e:
                manager._ui_log("Memory", "Error", f"Memory fehlgeschlagen: {e}")

            # AENDERUNG 10.02.2026: Fix 45 — Symptom-basierte Eskalation
            # ROOT-CAUSE-FIX: Error-Hash aendert sich jede Iteration → kein automatischer Modellwechsel
            # obwohl Symptom "leere Seite" seit 3+ Iterationen identisch ist
            _combined_result = str(sandbox_result or "") + str(ui_result or "")
            _combined_lower = _combined_result.lower()
            if ("leere seite" in _combined_lower or "__next" in _combined_lower
                    or "kein sichtbarer inhalt" in _combined_lower
                    or "empty page" in _combined_lower):
                _empty_page_counter += 1
                if _empty_page_counter >= 3:
                    manager._ui_log("Orchestrator", "SymptomEscalation",
                        f"Leere Seite seit {_empty_page_counter} Iterationen - erzwinge Modellwechsel")
                    model_attempt = max_model_attempts  # Trigger Modellwechsel
                    _empty_page_counter = 0
            else:
                _empty_page_counter = 0

            # AENDERUNG 20.02.2026: Fix 58c — Feedback-Stagnation-Erkennung
            # ROOT-CAUSE-FIX: Tabellen-Mismatch ("no such table: todos") wiederholte sich
            # 10x ohne Modellwechsel weil Error-Hash sich minimal aenderte (Zeilennummer)
            # obwohl der Kern-Fehler identisch blieb. Neuer Check: Normalisiertes Feedback
            # ueber 4+ Iterationen gleich → erzwinge Modellwechsel
            _feedback_sig = _compute_feedback_signature(feedback, sandbox_result)
            if _feedback_sig and _feedback_sig == _last_feedback_signature:
                _stagnation_counter += 1
                if _stagnation_counter >= 4:
                    manager._ui_log("Orchestrator", "StagnationDetected",
                        f"Gleiches Feedback-Muster seit {_stagnation_counter + 1} Iterationen "
                        f"(Signatur: {_feedback_sig[:50]}...) — erzwinge Modellwechsel")
                    model_attempt = max_model_attempts
                    _stagnation_counter = 0
            else:
                _stagnation_counter = 0
                _last_feedback_signature = _feedback_sig

            model_attempt += 1
            failed_attempts_history.append({"model": current_coder_model, "attempt": model_attempt,
                "iteration": iteration + 1, "feedback": feedback[:500] if feedback else "",
                "sandbox_error": sandbox_result[:300] if sandbox_failed else ""})

            if validator_decision.model_switch_recommended and validator_decision.error_hash:
                manager.model_router.mark_error_tried(validator_decision.error_hash, current_coder_model)
                manager._ui_log("Orchestrator", "ForceModelSwitch",
                    f"Erzwingt Modellwechsel fuer Fehler {validator_decision.error_hash[:8]}")
                model_attempt = max_model_attempts

            current_coder_model, model_attempt, models_used, feedback = handle_model_switch(
                manager, project_rules, current_coder_model, models_used, failed_attempts_history,
                model_attempt, max_model_attempts, feedback, iteration,
                sandbox_result=sandbox_result if sandbox_failed else "", sandbox_failed=sandbox_failed)

            iteration += 1
            manager._current_iteration = iteration

        return success, feedback
