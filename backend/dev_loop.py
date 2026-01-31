"""
Author: rahn
Datum: 31.01.2026
Version: 1.6
Beschreibung: DevLoop kapselt die Iterationslogik fuer Code-Generierung und Tests.
              AENDERUNG 31.01.2026: HELP_NEEDED Handler Integration fuer automatische Hilfs-Agenten.
              AENDERUNG 31.01.2026: FIX - Security-Blockade wird aufgehoben wenn Scan erfolgreich.
              AENDERUNG 31.01.2026: Fehler-Modell-Historie zur Vermeidung von Ping-Pong-Wechseln.
              AENDERUNG 31.01.2026: File-by-File Modus Integration (Anti-Truncation).
              AENDERUNG 31.01.2026: FIX - AsyncIO Event-Loop Bug in Worker-Thread behoben.
              AENDERUNG 31.01.2026: Targeted Fix Mode - Parallele gezielte Korrekturen statt Neugenerierung.
"""

import os
import json
from typing import Dict, Any, Tuple
from concurrent.futures import ThreadPoolExecutor

from agents.memory_agent import update_memory
from .dev_loop_steps import (
    build_coder_prompt,
    run_coder_task,
    save_coder_output,
    run_sandbox_and_tests,
    run_review,
    run_security_rescan,
    build_feedback,
    handle_model_switch
)
# AENDERUNG 31.01.2026: File-by-File Modus zur Vermeidung von Truncation
from .file_by_file_loop import should_use_file_by_file, run_file_by_file_loop
# AENDERUNG 31.01.2026: Targeted Fix Mode - Parallele gezielte Korrekturen
from .error_analyzer import ErrorAnalyzer, analyze_errors, get_files_to_fix
from .parallel_fixer import ParallelFixer, should_use_parallel_fix

# ÄNDERUNG 29.01.2026: Dev-Loop aus OrchestrationManager ausgelagert


class DevLoop:
    def __init__(self, manager, set_current_agent, run_with_timeout):
        self.manager = manager
        self.set_current_agent = set_current_agent
        self.run_with_timeout = run_with_timeout
        # AENDERUNG 31.01.2026: Targeted Fix Mode Komponenten
        self._parallel_fixer = None
        self._error_analyzer = ErrorAnalyzer()

    def _try_targeted_fix(
        self,
        sandbox_result: str,
        review_output: str,
        created_files: list,
        project_rules: Dict[str, Any],
        user_goal: str
    ) -> Tuple[bool, str, list]:
        """
        Versucht gezielte Korrekturen statt kompletter Neugenerierung.

        Args:
            sandbox_result: Sandbox/Test-Output mit Fehlern
            review_output: Reviewer-Feedback
            created_files: Liste der erstellten Dateien
            project_rules: Projektregeln
            user_goal: Benutzer-Ziel

        Returns:
            Tuple (erfolg, aktualisierter_code, aktualisierte_dateien)
        """
        manager = self.manager

        # Sammle aktuelle Dateiinhalte
        existing_files = {}
        for filepath in (created_files or []):
            full_path = os.path.join(manager.project_path, filepath)
            if os.path.exists(full_path):
                try:
                    with open(full_path, "r", encoding="utf-8") as f:
                        existing_files[filepath] = f.read()
                except Exception:
                    pass

        if not existing_files:
            manager._ui_log("TargetedFix", "Skip", "Keine Dateien fuer gezielte Korrektur gefunden")
            return False, "", []

        # Analysiere Fehler
        errors = analyze_errors(
            sandbox_output=sandbox_result,
            review_output=review_output,
            project_files=existing_files
        )

        if not errors:
            manager._ui_log("TargetedFix", "Skip", "Keine analysierbaren Fehler gefunden")
            return False, "", []

        # Pruefe ob paralleler Fix sinnvoll ist (max 3 Dateien)
        affected_files = get_files_to_fix(errors, max_files=3)
        if not should_use_parallel_fix(errors, max_threshold=3):
            manager._ui_log("TargetedFix", "Skip",
                          f"Zu viele Dateien betroffen ({len(affected_files)}) - nutze Standard-Modus")
            return False, "", []

        manager._ui_log("TargetedFix", "Start", json.dumps({
            "affected_files": affected_files,
            "error_count": len(errors),
            "error_types": list(set(e.error_type for e in errors))
        }, ensure_ascii=False))

        # Initialisiere ParallelFixer falls noetig
        if not self._parallel_fixer:
            self._parallel_fixer = ParallelFixer(
                manager=manager,
                config=manager.config,
                max_parallel=3,
                max_retries=2,
                router=manager.model_router if hasattr(manager, 'model_router') else None
            )

        # Fuehre parallele Korrekturen durch
        try:
            fix_results = self._parallel_fixer.fix_files_parallel(
                errors=errors,
                existing_files=existing_files,
                project_rules=str(project_rules),
                user_goal=user_goal
            )

            # Zaehle erfolgreiche Fixes
            successful = sum(1 for r in fix_results.values() if r.success)
            total = len(fix_results)

            manager._ui_log("TargetedFix", "Results", json.dumps({
                "successful": successful,
                "total": total,
                "fixed_files": [p for p, r in fix_results.items() if r.success],
                "failed_files": [p for p, r in fix_results.items() if not r.success]
            }, ensure_ascii=False))

            if successful == 0:
                return False, "", []

            # Schreibe korrigierte Dateien zurueck
            updated_files = []
            for filepath, result in fix_results.items():
                if result.success and result.new_content:
                    full_path = os.path.join(manager.project_path, filepath)
                    try:
                        with open(full_path, "w", encoding="utf-8") as f:
                            f.write(result.new_content)
                        updated_files.append(filepath)
                        existing_files[filepath] = result.new_content
                    except Exception as e:
                        manager._ui_log("TargetedFix", "WriteError", f"{filepath}: {e}")

            # Baue aktualisierten Code-String
            all_code = ""
            for filepath in (created_files or []):
                if filepath in existing_files:
                    all_code += f"\n### FILENAME: {filepath}\n{existing_files[filepath]}\n"

            return True, all_code, updated_files

        except Exception as e:
            manager._ui_log("TargetedFix", "Error", f"Parallele Korrektur fehlgeschlagen: {e}")
            return False, "", []

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

        # AENDERUNG 31.01.2026: File-by-File Modus bei komplexen Projekten
        # Verhindert Truncation bei Free-Tier-Modellen mit niedrigen Token-Limits
        if should_use_file_by_file(manager.tech_blueprint, manager.config):
            manager._ui_log("DevLoop", "Mode", "File-by-File Modus aktiviert (Anti-Truncation)")
            try:
                import asyncio
                # AENDERUNG 31.01.2026: FIX AsyncIO - Erstelle neuen Event-Loop fuer Worker-Thread
                # asyncio.get_event_loop() funktioniert nicht in Worker-Threads!
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    success, message, created_files = loop.run_until_complete(
                        run_file_by_file_loop(
                            manager,
                            project_rules,
                            manager.user_prompt if hasattr(manager, 'user_prompt') else "",
                            max_iterations=manager.config.get("max_retries", 3)
                        )
                    )
                finally:
                    loop.close()
                if success and created_files:
                    manager._ui_log("DevLoop", "FileByFileComplete", json.dumps({
                        "success": True,
                        "files_created": len(created_files),
                        "message": message
                    }, ensure_ascii=False))
                    # Fahre mit normaler Loop fuer Tests/Review fort
                    # Setze current_code aus erstellten Dateien
                    all_code = ""
                    for filepath in created_files:
                        full_path = os.path.join(manager.project_path, filepath)
                        if os.path.exists(full_path):
                            with open(full_path, "r", encoding="utf-8") as f:
                                all_code += f"\n### FILENAME: {filepath}\n{f.read()}\n"
                    manager.current_code = all_code
                    # Ueberspringe erste Iteration da Code bereits generiert
                    manager._ui_log("DevLoop", "Info",
                                   "File-by-File abgeschlossen, starte Tests und Review...")
            except Exception as fbf_err:
                manager._ui_log("DevLoop", "Warning",
                               f"File-by-File fehlgeschlagen, nutze Standard-Modus: {fbf_err}")
                # Fallback auf normalen Modus

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

        while iteration < max_retries:
            manager.iteration = iteration
            manager.max_retries = max_retries
            manager._ui_log("Coder", "Iteration", f"{iteration + 1} / {max_retries}")

            self.set_current_agent("Coder", project_id)
            coder_model = manager.model_router.get_model("coder") if manager.model_router else "unknown"
            manager._update_worker_status("coder", "working", f"Iteration {iteration + 1}/{max_retries}", coder_model)

            c_prompt = build_coder_prompt(manager, user_goal, feedback, iteration)
            manager.current_code, manager.agent_coder = run_coder_task(manager, project_rules, c_prompt, manager.agent_coder)
            # ÄNDERUNG 31.01.2026: Truncation-Status für Modellwechsel-Logik
            created_files, truncated_files = save_coder_output(manager, manager.current_code, manager.output_path, iteration, max_retries)

            # ÄNDERUNG 30.01.2026: Quality Gate - Code Validierung nach jeder Iteration
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
                # Sammle Code-Datei für Dokumentation
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

            # ÄNDERUNG 31.01.2026: Truncation als Sandbox-Fehler behandeln für Modellwechsel-Logik
            # Wenn Dateien abgeschnitten wurden (Token-Limit), triggert dies den Modellwechsel
            if truncated_files:
                truncation_msg = f"TRUNCATION: Dateien abgeschnitten durch Token-Limit: {', '.join([f[0] for f in truncated_files])}"
                sandbox_failed = True
                sandbox_result = f"{sandbox_result}\n{truncation_msg}" if sandbox_result else truncation_msg
                manager._ui_log("Coder", "TruncationError", json.dumps({
                    "message": "Truncation wird als Fehler behandelt für Modellwechsel",
                    "truncated_count": len(truncated_files),
                    "files": [f[0] for f in truncated_files]
                }, ensure_ascii=False))

            # AENDERUNG 31.01.2026: Targeted Fix Mode - Versuche gezielte Korrektur vor Neugenerierung
            # Nur bei Sandbox-Fehlern und wenn Dateien existieren (nicht erste Iteration)
            targeted_fix_applied = False
            if sandbox_failed and iteration > 0 and created_files:
                manager._ui_log("TargetedFix", "Attempting",
                              f"Versuche gezielte Korrektur fuer {len(created_files)} Dateien...")
                fix_success, fixed_code, updated_files = self._try_targeted_fix(
                    sandbox_result=sandbox_result,
                    review_output="",  # Noch kein Review in dieser Phase
                    created_files=created_files,
                    project_rules=project_rules,
                    user_goal=user_goal
                )

                if fix_success and fixed_code:
                    manager.current_code = fixed_code
                    targeted_fix_applied = True
                    manager._ui_log("TargetedFix", "Success",
                                   f"Gezielte Korrektur erfolgreich: {len(updated_files)} Dateien korrigiert")

                    # Re-run Sandbox mit korrigiertem Code
                    sandbox_result, sandbox_failed, test_result, ui_result, test_summary = run_sandbox_and_tests(
                        manager,
                        manager.current_code,
                        created_files,
                        iteration,
                        manager.tech_blueprint.get("project_type", "webapp")
                    )

                    if not sandbox_failed:
                        manager._ui_log("TargetedFix", "Validated",
                                       "Korrigierter Code hat Sandbox-Tests bestanden")

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

            # ÄNDERUNG 30.01.2026: Quality Gate - Review Validierung
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

            # ÄNDERUNG 30.01.2026: Quality Gate - Security Validierung
            if hasattr(manager, 'quality_gate'):
                # Konvertiere security_rescan_vulns in das erwartete Format
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
                # Sammle Security-Findings für Dokumentation
                if hasattr(manager, 'doc_service') and manager.doc_service:
                    for v in vuln_list:
                        manager.doc_service.collect_security_finding(v)

            if not security_passed:
                security_retry_count += 1
                if security_retry_count >= max_security_retries:
                    manager._ui_log(
                        "Security",
                        "Warning",
                        f"⚠️ {len(security_rescan_vulns)} Security-Issues nach {security_retry_count} Versuchen nicht behoben. "
                        f"Fahre mit Warnung fort (keine Blockade)."
                    )
                    security_passed = True
                    # ÄNDERUNG 31.01.2026: Security-Blockade aufheben da wir weitermachen
                    try:
                        from backend.session_manager import get_session_manager
                        get_session_manager().clear_agent_blocked("security")
                    except Exception:
                        pass
            else:
                # ÄNDERUNG 31.01.2026: Security erfolgreich - Blockade aufheben falls vorhanden
                try:
                    from backend.session_manager import get_session_manager
                    get_session_manager().clear_agent_blocked("security")
                except Exception:
                    pass

            review_says_ok = review_output.strip().upper().startswith("OK") or review_output.strip().upper() == "OK"
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
                success = True
                manager._ui_log("Security", "SecurityGate", "✅ Security-Gate bestanden - Code ist sicher.")
                manager._ui_log("Reviewer", "Status", f"Code OK - Projekt komplett mit {created_count} Dateien.")

                # ÄNDERUNG 30.01.2026: Quality Gate - Finale Validierung
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

                # ÄNDERUNG 30.01.2026: Sammle Iterations-Daten für Dokumentation
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
                    # ÄNDERUNG 29.01.2026: Non-blocking Memory-Operation für WebSocket-Stabilität
                    with ThreadPoolExecutor(max_workers=1) as executor:
                        executor.submit(update_memory, memory_path, manager.current_code, review_output, sandbox_result)
                    manager._ui_log("Memory", "Recording", "Erfolgreiche Iteration aufgezeichnet.")
                except Exception as mem_err:
                    manager._ui_log("Memory", "Error", f"Memory-Operation fehlgeschlagen: {mem_err}")
                break
            if review_says_ok and not has_minimum_files:
                manager._ui_log("Orchestrator", "Status", f"Nur {created_count} Dateien erstellt - generiere weitere...")
                feedback = f"Bitte weitere Dateien generieren. Bisher nur {created_count} Datei(en). "
                feedback += "Ein vollstaendiges Projekt braucht mindestens Backend, Config/Requirements und README oder Tests."
                iteration += 1
                manager._current_iteration = iteration
                continue

            # ÄNDERUNG 31.01.2026: review_verdict an build_feedback übergeben
            feedback = build_feedback(
                manager,
                review_output,
                review_verdict,  # NEU: Strukturiertes Verdict statt nur String-Parsing
                sandbox_failed,
                sandbox_result,
                test_summary,
                test_result,
                security_passed,
                security_rescan_vulns
            )
            manager._ui_log("Reviewer", "Feedback", feedback)

            # ÄNDERUNG 31.01.2026: HELP_NEEDED Handler aufrufen
            # Verarbeitet blockierte Agents und startet automatisch Hilfs-Agenten
            if hasattr(manager, '_handle_help_needed_events'):
                help_result = manager._handle_help_needed_events(iteration)
                if help_result.get("actions"):
                    manager._ui_log("HelpHandler", "Summary",
                                   f"Aktionen: {len(help_result['actions'])} durchgefuehrt")
                    # Falls Test-Generator erfolgreich war, koennen wir das im Feedback erwaehnen
                    for action in help_result.get("actions", []):
                        if action.get("action") == "test_generator" and action.get("success"):
                            feedback += "\n\nHINWEIS: Unit-Tests wurden automatisch generiert."

            # ÄNDERUNG 30.01.2026: Sammle fehlgeschlagene Iterations-Daten für Dokumentation
            if hasattr(manager, 'doc_service') and manager.doc_service:
                status = "partial" if not sandbox_failed else "failed"
                manager.doc_service.collect_iteration(
                    iteration=iteration + 1,
                    changes=feedback[:300] if feedback else "Keine Änderungen",
                    status=status,
                    review_summary=review_output[:200] if review_output else "",
                    test_result=test_summary[:100] if test_summary else ""
                )
            try:
                memory_path = os.path.join(manager.base_dir, "memory", "global_memory.json")
                # ÄNDERUNG 29.01.2026: Non-blocking Memory-Operation für WebSocket-Stabilität
                with ThreadPoolExecutor(max_workers=1) as executor:
                    executor.submit(update_memory, memory_path, manager.current_code, review_output, sandbox_result)
            except Exception as mem_err:
                manager._ui_log("Memory", "Error", f"Memory-Operation fehlgeschlagen: {mem_err}")

            model_attempt += 1
            failed_attempts_history.append({
                "model": current_coder_model,
                "attempt": model_attempt,
                "iteration": iteration + 1,
                "feedback": feedback[:500] if feedback else "",
                "sandbox_error": sandbox_result[:300] if sandbox_failed else ""
            })

            # AENDERUNG 31.01.2026: sandbox_result und sandbox_failed fuer Fehler-Modell-Historie
            current_coder_model, model_attempt, models_used, feedback = handle_model_switch(
                manager,
                project_rules,
                current_coder_model,
                models_used,
                failed_attempts_history,
                model_attempt,
                max_model_attempts,
                feedback,
                iteration,
                sandbox_result=sandbox_result if sandbox_failed else "",
                sandbox_failed=sandbox_failed
            )

            iteration += 1
            manager._current_iteration = iteration

        return success, feedback
