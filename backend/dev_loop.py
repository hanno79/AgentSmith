"""
Author: rahn
Datum: 29.01.2026
Version: 1.0
Beschreibung: DevLoop kapselt die Iterationslogik fuer Code-Generierung und Tests.
"""

import os
import json
from typing import Dict, Any, Tuple

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

# ÄNDERUNG 29.01.2026: Dev-Loop aus OrchestrationManager ausgelagert


class DevLoop:
    def __init__(self, manager, set_current_agent, run_with_timeout):
        self.manager = manager
        self.set_current_agent = set_current_agent
        self.run_with_timeout = run_with_timeout

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
            created_files = save_coder_output(manager, manager.current_code, manager.output_path, iteration, max_retries)

            sandbox_result, sandbox_failed, test_result, ui_result, test_summary = run_sandbox_and_tests(
                manager,
                manager.current_code,
                created_files,
                iteration,
                manager.tech_blueprint.get("project_type", "webapp")
            )

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

            self.set_current_agent("Security", project_id)
            security_passed, security_rescan_vulns = run_security_rescan(
                manager,
                project_rules,
                manager.current_code,
                iteration
            )

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
                try:
                    memory_path = os.path.join(manager.base_dir, "memory", "global_memory.json")
                    update_memory(memory_path, manager.current_code, review_output, sandbox_result)
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

            feedback = build_feedback(
                manager,
                review_output,
                sandbox_failed,
                sandbox_result,
                test_summary,
                test_result,
                security_passed,
                security_rescan_vulns
            )
            manager._ui_log("Reviewer", "Feedback", feedback)
            try:
                memory_path = os.path.join(manager.base_dir, "memory", "global_memory.json")
                update_memory(memory_path, manager.current_code, review_output, sandbox_result)
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

            current_coder_model, model_attempt, models_used, feedback = handle_model_switch(
                manager,
                project_rules,
                current_coder_model,
                models_used,
                failed_attempts_history,
                model_attempt,
                max_model_attempts,
                feedback,
                iteration
            )

            iteration += 1
            manager._current_iteration = iteration

        return success, feedback
