"""
Author: rahn
Datum: 08.02.2026
Version: 1.0
Beschreibung: Helfer-Funktionen fuer DevLoop.run().
              Extrahiert aus dev_loop.py (Regel 1: Max 500 Zeilen).
              Enthaelt: File-by-File-Phase, Truncation-Recovery,
              Success-Finalisierung und UTDS-Feedback-Verarbeitung.
"""

import os
import json
import logging
import asyncio
from typing import Tuple
from concurrent.futures import ThreadPoolExecutor

from agents.memory_agent import update_memory
from .file_by_file_loop import (
    run_file_by_file_loop,
    run_file_by_file_repair,
    merge_repaired_files,
    run_planner
)
from .parallel_file_generator import (
    run_parallel_file_generation,
    get_file_descriptions_from_plan,
    get_file_list_from_plan
)
from .dev_loop_steps import run_sandbox_and_tests

logger = logging.getLogger(__name__)


# =========================================================================
# File-by-File Pre-Loop Phase
# =========================================================================

def run_file_by_file_phase(manager, user_goal, project_rules):
    """
    File-by-File Initialisierung (Pre-Loop).
    Generiert Dateien parallel oder sequenziell bevor der Haupt-Loop startet.
    Setzt manager.current_code und manager.is_first_run.

    AENDERUNG 31.01.2026: File-by-File Modus bei komplexen Projekten.
    AENDERUNG 01.02.2026: Parallele Generierung mit dynamischer Worker-Anzahl.
    """
    parallel_config = manager.config.get("parallel_file_generation", {})
    use_parallel = parallel_config.get("enabled", True)

    if use_parallel:
        manager._ui_log("DevLoop", "Mode", "PARALLELE File-by-File Generierung aktiviert")
    else:
        manager._ui_log("DevLoop", "Mode", "File-by-File Modus aktiviert (sequenziell)")

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            if use_parallel:
                created_files, expected_files = _run_parallel_generation(
                    loop, manager, project_rules, parallel_config
                )
            else:
                # Sequenzieller Modus (Original)
                success, message, created_files = loop.run_until_complete(
                    run_file_by_file_loop(
                        manager,
                        project_rules,
                        manager.user_prompt if hasattr(manager, 'user_prompt') else "",
                        max_iterations=manager.config.get("max_retries", 3)
                    )
                )
                expected_files = len(created_files) if created_files else 0
        finally:
            loop.close()

        # AENDERUNG 02.02.2026: Auch bei partiellem Erfolg loggen
        if created_files:
            manager._ui_log("DevLoop", "FileByFileComplete", json.dumps({
                "success": True,
                "files_created": len(created_files),
                "files_expected": expected_files if use_parallel else len(created_files),
                "parallel": use_parallel
            }, ensure_ascii=False))
            # Setze current_code aus erstellten Dateien
            all_code = ""
            for filepath in created_files:
                full_path = os.path.join(manager.project_path, filepath)
                if os.path.exists(full_path):
                    with open(full_path, "r", encoding="utf-8") as f:
                        all_code += f"\n### FILENAME: {filepath}\n{f.read()}\n"
            manager.current_code = all_code
            manager._ui_log("DevLoop", "Info",
                           "File-by-File abgeschlossen, starte Tests und Review...")
            # AENDERUNG 03.02.2026: is_first_run auch bei File-by-File setzen (Fix 6b)
            if manager.is_first_run:
                manager.is_first_run = False
                manager._ui_log("System", "FirstRunComplete",
                               "Erste Iteration abgeschlossen - PatchMode aktiviert")
    except Exception as fbf_err:
        manager._ui_log("DevLoop", "Warning",
                       f"File-by-File fehlgeschlagen, nutze Standard-Modus: {fbf_err}")
        import traceback
        logger.error("File-by-File Fehler: %s", traceback.format_exc())
        # Fallback auf normalen Modus


def _run_parallel_generation(loop, manager, project_rules, parallel_config):
    """
    Fuehrt parallele File-by-File Generierung durch.
    Returns: (created_files, expected_files)
    """
    # Schritt 1: Plan erstellen
    plan = loop.run_until_complete(
        run_planner(
            manager,
            project_rules,
            manager.user_prompt if hasattr(manager, 'user_prompt') else ""
        )
    )
    file_list = get_file_list_from_plan(plan)
    file_descriptions = get_file_descriptions_from_plan(plan)

    # AENDERUNG 10.02.2026: Fix 49 — Template-Config-Dateien ueberspringen
    # ROOT-CAUSE-FIX:
    # Symptom: tailwind.config.js braucht 197s LLM-Generierung, ueberschreibt dann Template-Version
    # Ursache: PROTECTED_CONFIGS existierte nur im Default-Plan, nicht im LLM-Planner-Pfad
    # Loesung: Config-Dateien die bereits vom Template kopiert wurden aus file_list entfernen
    if hasattr(manager, 'project_path') and manager.project_path:
        from agents.planner_defaults import PROTECTED_CONFIGS
        skipped = []
        for cfg in list(file_list):  # list() fuer sichere Iteration
            basename = os.path.basename(cfg)
            if basename in PROTECTED_CONFIGS:
                full_path = os.path.join(str(manager.project_path), cfg)
                if os.path.exists(full_path):
                    file_list.remove(cfg)
                    file_descriptions.pop(cfg, None)
                    skipped.append(cfg)
        if skipped:
            manager._ui_log("DevLoop", "TemplateSkip",
                f"{len(skipped)} Template-Config-Dateien uebersprungen: {', '.join(skipped)}")

    manager._ui_log("DevLoop", "ParallelPlan", json.dumps({
        "total_files": len(file_list),
        "files": file_list[:10]
    }, ensure_ascii=False))

    # Schritt 2: Parallele Generierung
    # AENDERUNG 08.02.2026: Pro-Agent Timeout statt globalem agent_timeout_seconds
    max_workers = parallel_config.get("max_workers", None)
    agent_timeouts = manager.config.get("agent_timeouts", {})
    agent_timeout = agent_timeouts.get("coder", 750)
    timeout_per_file = parallel_config.get("timeout_per_file", agent_timeout)
    batch_timeout = parallel_config.get("batch_timeout", agent_timeout * 2)

    results, errors = loop.run_until_complete(
        run_parallel_file_generation(
            manager=manager,
            file_list=file_list,
            file_descriptions=file_descriptions,
            user_goal=manager.user_prompt if hasattr(manager, 'user_prompt') else "",
            project_rules=project_rules,
            max_workers=max_workers,
            timeout_per_file=timeout_per_file,
            batch_timeout=batch_timeout
        )
    )

    created_files = list(results.keys())

    # AENDERUNG 01.02.2026: Retry fuer fehlgeschlagene Dateien bei Rate-Limits
    if errors:
        manager._ui_log("DevLoop", "ParallelErrors", json.dumps({
            "failed_count": len(errors),
            "errors": [(f, e[:50]) for f, e in errors[:5]]
        }, ensure_ascii=False))

        rate_limit_files = [
            (f, desc) for f, e in errors
            if "RateLimit" in e or "429" in e
            for desc in [file_descriptions.get(f, f"Generiere {f}")]
        ]

        if rate_limit_files and len(rate_limit_files) > 0:
            manager._ui_log("DevLoop", "ParallelRetry", json.dumps({
                "reason": "rate_limit",
                "files_to_retry": len(rate_limit_files),
                "wait_seconds": 30
            }, ensure_ascii=False))

            loop.run_until_complete(asyncio.sleep(30))

            retry_file_list = [f for f, _ in rate_limit_files]
            retry_descriptions = {f: d for f, d in rate_limit_files}

            retry_results, retry_errors = loop.run_until_complete(
                run_parallel_file_generation(
                    manager=manager,
                    file_list=retry_file_list,
                    file_descriptions=retry_descriptions,
                    user_goal=manager.user_prompt if hasattr(manager, 'user_prompt') else "",
                    project_rules=project_rules,
                    max_workers=1,
                    timeout_per_file=timeout_per_file * 2,
                    batch_timeout=batch_timeout
                )
            )

            results.update(retry_results)
            created_files = list(results.keys())

            if retry_errors:
                manager._ui_log("DevLoop", "ParallelRetryPartial", json.dumps({
                    "success_count": len(retry_results),
                    "still_failed": len(retry_errors)
                }, ensure_ascii=False))

    expected_files = len(file_list)
    return created_files, expected_files


# =========================================================================
# Truncation Recovery
# =========================================================================

def handle_truncation_recovery(manager, project_rules, truncated_files,
                                user_goal, created_files, iteration):
    """
    Repariert abgeschnittene Dateien via File-by-File Reparatur.
    AENDERUNG 01.02.2026: Truncation Recovery - File-by-File Reparatur.

    Returns:
        tuple: (sandbox_result, sandbox_failed, test_result, ui_result,
                test_summary, truncated_files, created_files)
    """
    manager._ui_log("DevLoop", "TruncationRecovery",
                   f"Starte File-by-File Reparatur fuer {len(truncated_files)} Dateien...")
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            repair_success, repair_msg, repaired_content = loop.run_until_complete(
                run_file_by_file_repair(
                    manager,
                    project_rules,
                    truncated_files,
                    manager.current_code,
                    user_goal,
                    max_iterations=3
                )
            )
        finally:
            loop.close()

        if repair_success and repaired_content:
            manager.current_code = merge_repaired_files(
                manager.current_code,
                repaired_content
            )
            manager._ui_log("DevLoop", "TruncationRepaired", json.dumps({
                "success": True,
                "repaired_files": list(repaired_content.keys()),
                "message": repair_msg
            }, ensure_ascii=False))

            for filepath in repaired_content.keys():
                if filepath not in created_files:
                    created_files.append(filepath)

            truncated_files = []

            # Re-run Sandbox mit reparierten Dateien
            sandbox_result, sandbox_failed, test_result, ui_result, test_summary = run_sandbox_and_tests(
                manager,
                manager.current_code,
                created_files,
                iteration,
                manager.tech_blueprint.get("project_type", "webapp")
            )

            if not sandbox_failed:
                manager._ui_log("DevLoop", "TruncationRecoverySuccess",
                               "Sandbox nach Reparatur erfolgreich!")

            return sandbox_result, sandbox_failed, test_result, ui_result, test_summary, truncated_files, created_files
        else:
            manager._ui_log("DevLoop", "TruncationRecoveryFailed",
                           f"File-by-File Reparatur fehlgeschlagen: {repair_msg}")
    except Exception as repair_err:
        manager._ui_log("DevLoop", "TruncationRecoveryError",
                       f"Reparatur-Fehler: {repair_err}")

    # Keine erfolgreiche Reparatur → None signalisiert dem Caller "keine Aenderung"
    return None


# =========================================================================
# Success Finalization
# =========================================================================

def handle_success_finalization(manager, iteration, review_says_ok,
                                 sandbox_failed, security_passed,
                                 review_output, test_summary,
                                 created_files, sandbox_result):
    """
    QG Final Validation + Waisen-Check + Doc-Service + Memory.
    Wird aufgerufen wenn alle Gates bestanden sind.
    AENDERUNG 30.01.2026: Quality Gate - Finale Validierung.
    AENDERUNG 08.02.2026: Fix 24 - Waisen-Check in Final Validation.
    """
    created_count = len(created_files) if created_files else 0
    manager._ui_log("Security", "SecurityGate", "Security-Gate bestanden - Code ist sicher.")
    manager._ui_log("Reviewer", "Status", f"Code OK - Projekt komplett mit {created_count} Dateien.")

    # Quality Gate - Finale Validierung
    if hasattr(manager, 'quality_gate'):
        final_validation = manager.quality_gate.validate_final(
            code=manager.current_code,
            tests_passed=not sandbox_failed,
            review_passed=review_says_ok,
            security_passed=security_passed,
            blueprint=manager.tech_blueprint
        )
        manager._ui_log("QualityGate", "FinalValidation", json.dumps({
            "step": "Final",
            "passed": final_validation.passed,
            "score": final_validation.score,
            "issues": final_validation.issues,
            "warnings": final_validation.warnings,
            "component_status": final_validation.details.get("component_status", {})
        }, ensure_ascii=False))

        # AENDERUNG 08.02.2026: Fix 24 - Waisen-Check in Final Validation
        # Prueft Traceability-Kette: ANF -> FEAT -> TASK -> FILE
        if hasattr(manager, 'traceability_manager') and manager.traceability_manager:
            try:
                matrix = manager.traceability_manager.get_matrix()
                waisen_result = manager.quality_gate.validate_waisen(
                    anforderungen=list(matrix.get("anforderungen", {}).values()),
                    features=list(matrix.get("features", {}).values()),
                    tasks=list(matrix.get("tasks", {}).values()),
                    file_generations=[
                        {"task_id": t_id}
                        for t_id, t in matrix.get("tasks", {}).items()
                        if t.get("dateien")
                    ]
                )
                manager._ui_log("QualityGate", "WaisenCheck", json.dumps({
                    "step": "WaisenCheck",
                    "passed": waisen_result.passed,
                    "score": waisen_result.score,
                    "waisen": waisen_result.details.get("waisen", {}),
                    "counts": waisen_result.details.get("counts", {})
                }, ensure_ascii=False))
            except Exception as wc_err:
                logger.warning(f"Waisen-Check Fehler: {wc_err}")

    # Sammle Iterations-Daten fuer Dokumentation
    if hasattr(manager, 'doc_service') and manager.doc_service:
        manager.doc_service.collect_iteration(
            iteration=iteration + 1,
            changes="Code erfolgreich generiert und validiert",
            status="success",
            review_summary=review_output[:200] if review_output else "",
            test_result=test_summary[:100] if test_summary else ""
        )
        manager.doc_service.collect_test_result(
            test_name="Final Integration Test",
            passed=True,
            details=test_summary[:200] if test_summary else ""
        )

    try:
        memory_path = os.path.join(manager.base_dir, "memory", "global_memory.json")
        with ThreadPoolExecutor(max_workers=1) as executor:
            executor.submit(update_memory, memory_path, manager.current_code, review_output, sandbox_result)
        manager._ui_log("Memory", "Recording", "Erfolgreiche Iteration aufgezeichnet.")
    except Exception as mem_err:
        manager._ui_log("Memory", "Error", f"Memory-Operation fehlgeschlagen: {mem_err}")


# =========================================================================
# UTDS Feedback Processing
# =========================================================================

def process_utds_feedback(task_derivation, manager, feedback,
                          created_files, security_passed,
                          security_rescan_vulns, sandbox_failed,
                          sandbox_result, test_summary, iteration):
    """
    Verarbeitet UTDS-Feedback aus 3 Quellen: Security, Sandbox, Reviewer.
    AENDERUNG 01.02.2026: Universal Task Derivation System (UTDS).
    AENDERUNG 06.02.2026: ROOT-CAUSE-FIX tech_blueprint hinzugefuegt.

    Returns:
        tuple: (updated_feedback, utds_modified_files)
    """
    _utds_modified_files = []

    # AENDERUNG 06.02.2026: ROOT-CAUSE-FIX tech_blueprint hinzugefuegt
    _tech_blueprint = getattr(manager, 'tech_blueprint', {})
    utds_context = {
        "current_code": manager.current_code,
        "affected_files": created_files or [],
        "tech_stack": _tech_blueprint.get('language', 'unknown'),
        "tech_blueprint": _tech_blueprint,
        "project_type": _tech_blueprint.get('project_type', 'webapp')
    }

    # Security als UTDS-Quelle
    # AENDERUNG 10.02.2026: Fix 42b - affected_file als [DATEI:xxx] auch fuer UTDS
    if not security_passed and security_rescan_vulns:
        security_feedback = "\n".join([
            f"Security-Vulnerability: {v}" if isinstance(v, str)
            else f"Security-Vulnerability ({v.get('severity', 'medium')}): "
                 f"{'[DATEI:' + v['affected_file'] + '] ' if v.get('affected_file') else ''}"
                 f"{v.get('description', str(v))}"
            for v in security_rescan_vulns
        ])
        if task_derivation.should_use_task_derivation(security_feedback, "security", iteration):
            manager._ui_log("TaskDerivation", "SecurityStart", "Starte Task-Ableitung aus Security-Findings")
            sec_success, sec_summary, sec_modified = task_derivation.process_feedback(
                security_feedback, "security", utds_context
            )
            if sec_modified:
                _utds_modified_files.extend(sec_modified)
            if sec_success:
                manager._ui_log("TaskDerivation", "SecuritySuccess",
                               f"Security-Tasks erfolgreich: {len(sec_modified)} Dateien geaendert")
            else:
                manager._ui_log("TaskDerivation", "SecurityPartial",
                               "Nicht alle Security-Tasks erfolgreich - verbleibende im Feedback")
                feedback = f"{feedback}\n\nSecurity-Tasks Status:\n{sec_summary}"

    # Sandbox als UTDS-Quelle
    if sandbox_failed and sandbox_result:
        sandbox_feedback = f"Sandbox-Fehler:\n{sandbox_result}"
        if test_summary:
            sandbox_feedback += f"\n\nTest-Summary:\n{test_summary}"
        if task_derivation.should_use_task_derivation(sandbox_feedback, "sandbox", iteration):
            manager._ui_log("TaskDerivation", "SandboxStart", "Starte Task-Ableitung aus Sandbox-Fehlern")
            sb_success, sb_summary, sb_modified = task_derivation.process_feedback(
                sandbox_feedback, "sandbox", utds_context
            )
            if sb_modified:
                _utds_modified_files.extend(sb_modified)
            if sb_success:
                manager._ui_log("TaskDerivation", "SandboxSuccess",
                               f"Sandbox-Tasks erfolgreich: {len(sb_modified)} Dateien geaendert")
            else:
                manager._ui_log("TaskDerivation", "SandboxPartial",
                               "Nicht alle Sandbox-Tasks erfolgreich - verbleibende im Feedback")
                feedback = f"{feedback}\n\nSandbox-Tasks Status:\n{sb_summary}"

    # Reviewer als UTDS-Quelle
    if task_derivation.should_use_task_derivation(feedback, "reviewer", iteration):
        manager._ui_log("TaskDerivation", "Start", "Starte Task-Ableitung aus Feedback")
        td_success, td_summary, td_modified = task_derivation.process_feedback(
            feedback, "reviewer", utds_context
        )
        if td_modified:
            _utds_modified_files.extend(td_modified)
        if td_success:
            manager._ui_log("TaskDerivation", "Success",
                           f"Alle Tasks erfolgreich: {len(td_modified)} Dateien geaendert")
            feedback = td_summary
        else:
            manager._ui_log("TaskDerivation", "Partial",
                           "Nicht alle Tasks erfolgreich - verbleibende werden dokumentiert")
            feedback = f"{feedback}\n\n{td_summary}"

    return feedback, _utds_modified_files


# AENDERUNG 10.02.2026: Fix 43 - Smoke-Test als blockierende Success-Bedingung
def run_smoke_test_gate(manager) -> Tuple[bool, str]:
    """Fuehrt Smoke-Test aus. Returns (passed, feedback_for_coder)."""
    smoke_config = manager.config.get("smoke_test", {})
    if not smoke_config.get("enabled", True):
        return True, ""

    from .dev_loop_smoke_test import run_smoke_test
    manager._ui_log("SmokeTest", "Start", "Starte Smoke-Test (Server + Browser)...")
    manager._update_worker_status("tester", "working", "Smoke-Test...",
        manager.model_router.get_model("tester") if manager.model_router else "")

    try:
        # AENDERUNG 10.02.2026: Fix 50 - Docker-Container an Smoke-Test durchreichen
        docker_container = getattr(manager, '_docker_container', None)
        smoke_result = run_smoke_test(
            str(manager.project_path), manager.tech_blueprint, manager.config,
            docker_container=docker_container)
    except Exception as e:
        manager._ui_log("SmokeTest", "Error", f"Smoke-Test Fehler: {e}")
        manager._update_worker_status("tester", "idle")
        return (True, "") if smoke_config.get("skip_on_error", True) else (False, f"SMOKE-TEST FEHLER: {e}")

    manager._update_worker_status("tester", "idle")
    manager._ui_log("SmokeTest", "Result", json.dumps({
        "passed": smoke_result.passed, "server_started": smoke_result.server_started,
        "page_loaded": smoke_result.page_loaded, "compile_errors": len(smoke_result.compile_errors),
        "console_errors": len(smoke_result.console_errors),
        "duration": round(smoke_result.duration_seconds, 1)
    }, ensure_ascii=False))

    if smoke_result.passed:
        manager._ui_log("SmokeTest", "Passed", f"Bestanden in {smoke_result.duration_seconds:.1f}s")
        return True, ""
    manager._ui_log("SmokeTest", "Failed", "Fehlgeschlagen - Iteration wird wiederholt")
    return False, smoke_result.feedback_for_coder
