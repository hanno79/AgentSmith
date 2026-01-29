"""
Author: rahn
Datum: 29.01.2026
Version: 1.0
Beschreibung: Schritt-Funktionen fuer den DevLoop.
"""

import os
import json
import base64
from datetime import datetime
from typing import Dict, Any, List, Tuple

from crewai import Task

from agents.memory_agent import (
    get_lessons_for_prompt, learn_from_error,
    extract_error_pattern, generate_tags_from_context
)
from budget_tracker import get_budget_tracker
from sandbox_runner import run_sandbox
from unit_test_runner import run_unit_tests
from main import save_multi_file_output
from content_validator import validate_run_bat
from agents.tester_agent import test_project, summarize_ui_result
from .agent_factory import init_agents
from .orchestration_helpers import (
    format_test_feedback,
    is_rate_limit_error,
    is_empty_or_invalid_response,
    create_human_readable_verdict,
    extract_vulnerabilities
)

# ÄNDERUNG 29.01.2026: Dev-Loop Schritte aus OrchestrationManager ausgelagert


def build_coder_prompt(manager, user_goal: str, feedback: str, iteration: int) -> str:
    """
    Baut den Coder-Prompt basierend auf Kontext, Feedback und Security-Tasks.
    """
    c_prompt = f"Ziel: {user_goal}\nTech: {manager.tech_blueprint}\nDB: {manager.database_schema}\n"

    briefing_context = manager.get_briefing_context()
    if briefing_context:
        c_prompt += f"\n{briefing_context}\n"

    if not manager.is_first_run:
        c_prompt += f"\nAlt-Code:\n{manager.current_code}\n"
    if feedback:
        c_prompt += f"\nKorrektur: {feedback}\n"

    if iteration == 0 and not feedback:
        c_prompt += "\n\n🛡️ SECURITY BASICS (von Anfang an beachten!):\n"
        c_prompt += "- Kein innerHTML/document.write mit User-Input (XSS-Risiko)\n"
        c_prompt += "- Keine String-Konkatenation in SQL/DB-Queries (Injection-Risiko)\n"
        c_prompt += "- Keine hardcoded API-Keys, Passwörter oder Secrets im Code\n"
        c_prompt += "- Bei eval(): Nur mit Button-Input, NIEMALS mit User-Text-Input\n"
        c_prompt += "- Nutze textContent statt innerHTML wenn möglich\n\n"

    try:
        memory_path = os.path.join(manager.base_dir, "memory", "global_memory.json")
        tech_stack = manager.tech_blueprint.get("project_type", "") if manager.tech_blueprint else ""
        lessons = get_lessons_for_prompt(memory_path, tech_stack=tech_stack)
        if lessons and lessons.strip():
            c_prompt += f"\n\n📚 LESSONS LEARNED (aus früheren Projekten - UNBEDINGT BEACHTEN!):\n{lessons}\n"
            manager._ui_log("Memory", "LessonsApplied", f"Coder erhält {len(lessons.splitlines())} Lektionen")
    except Exception as les_err:
        manager._ui_log("Memory", "Warning", f"Lektionen konnten nicht geladen werden: {les_err}")

    if hasattr(manager, 'security_vulnerabilities') and manager.security_vulnerabilities:
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        sorted_vulns = sorted(
            manager.security_vulnerabilities,
            key=lambda v: severity_order.get(v.get("severity", "medium"), 2)
        )

        coder_tasks = []
        task_prompt_lines = []

        for i, vuln in enumerate(sorted_vulns, 1):
            task_id = f"SEC-{i:03d}"
            severity = vuln.get("severity", "medium").upper()
            description = vuln.get("description", "Unbekannte Schwachstelle")
            fix = vuln.get("fix", "Bitte beheben")
            affected_file = vuln.get("affected_file", None)

            coder_tasks.append({
                "id": task_id,
                "type": "security",
                "severity": vuln.get("severity", "medium"),
                "description": description,
                "fix": fix,
                "affected_file": affected_file,
                "status": "pending"
            })

            file_hint = f"\n   -> DATEI: {affected_file}" if affected_file else ""
            task_prompt_lines.append(
                f"TASK {task_id} [{severity}]: {description}{file_hint}\n"
                f"   -> LÖSUNG: {fix}"
            )

        manager._ui_log("Coder", "CoderTasksOutput", json.dumps({
            "tasks": coder_tasks,
            "count": len(coder_tasks),
            "iteration": iteration + 1
        }, ensure_ascii=False))

        c_prompt += "\n\n⚠️ SECURITY TASKS (priorisiert nach Severity - CRITICAL zuerst):\n"
        c_prompt += "\n".join(task_prompt_lines)
        c_prompt += "\n\nWICHTIG: Bearbeite die Tasks in der angegebenen Reihenfolge! Implementiere die LÖSUNG für jeden Task!\n"

    c_prompt += "\n\n🧪 UNIT-TEST REQUIREMENT:\n"
    c_prompt += "- Erstelle IMMER Unit-Tests für alle neuen Funktionen/Klassen\n"
    c_prompt += "- Test-Dateien: tests/test_<modulname>.py oder tests/<modulname>.test.js\n"
    c_prompt += "- Mindestens 3 Test-Cases pro Funktion (normal, edge-case, error-case)\n"
    c_prompt += "- Format: ### FILENAME: tests/test_<modulname>.py\n"
    c_prompt += "- Tests müssen AUSFÜHRBAR sein (pytest bzw. npm test)\n"

    if manager.tech_blueprint and manager.tech_blueprint.get("requires_server"):
        c_prompt += "\n🔌 API-TESTS:\n"
        c_prompt += "- Teste JEDEN API-Endpoint mit mindestens 2 Test-Cases\n"
        c_prompt += "- Prüfe Erfolgs-Response UND Fehler-Response\n"
        c_prompt += "- Python: pytest + Flask test_client oder requests\n"
        c_prompt += "- JavaScript: jest + supertest\n"

    c_prompt += "\nFormat: ### FILENAME: path/to/file.ext"
    return c_prompt


def run_coder_task(manager, project_rules: Dict[str, Any], c_prompt: str, agent_coder) -> Tuple[str, Any]:
    """
    Fuehrt den Coder-Task mit Retry-Logik aus.
    """
    task_coder = Task(description=c_prompt, expected_output="Code", agent=agent_coder)
    MAX_CODER_RETRIES = 3
    coder_success = False
    current_code = ""

    for coder_attempt in range(MAX_CODER_RETRIES):
        try:
            current_code = str(task_coder.execute_sync()).strip()
            coder_success = True
            break
        except Exception as error:
            current_model = manager.model_router.get_model("coder") if manager.model_router else "unknown"
            if is_rate_limit_error(error):
                manager.model_router.mark_rate_limited_sync(current_model)
                manager._ui_log(
                    "ModelRouter",
                    "RateLimit",
                    f"Modell {current_model} pausiert (Versuch {coder_attempt + 1}/{MAX_CODER_RETRIES}), wechsle zu Fallback..."
                )
                agent_coder = init_agents(
                    manager.config,
                    project_rules,
                    router=manager.model_router,
                    include=["coder"]
                ).get("coder")
                task_coder = Task(description=c_prompt, expected_output="Code", agent=agent_coder)
                if coder_attempt == MAX_CODER_RETRIES - 1:
                    manager._ui_log("Coder", "Error", f"Alle {MAX_CODER_RETRIES} Versuche fehlgeschlagen: {str(error)[:200]}")
                    raise error
            else:
                manager._ui_log("Coder", "Error", f"Unerwarteter Fehler: {str(error)[:200]}")
                raise error

    if not coder_success:
        raise Exception(f"Coder konnte nach {MAX_CODER_RETRIES} Versuchen keine Ausgabe generieren")

    return current_code, agent_coder


def save_coder_output(manager, current_code: str, output_path: str, iteration: int, max_retries: int) -> List[str]:
    """
    Speichert Coder-Output und sendet UI-Events.
    """
    def_file = os.path.basename(output_path)
    created_files = save_multi_file_output(manager.project_path, current_code, def_file)
    manager._ui_log("Coder", "Files", f"Created: {', '.join(created_files)}")

    current_model = manager.model_router.get_model("coder") if manager.model_router else "unknown"
    manager._ui_log("Coder", "CodeOutput", json.dumps({
        "code": current_code,
        "files": created_files,
        "iteration": iteration + 1,
        "max_iterations": max_retries,
        "model": current_model
    }, ensure_ascii=False))
    manager._update_worker_status("coder", "idle")

    try:
        tracker = get_budget_tracker()
        today_totals = tracker.get_today_totals()
        manager._ui_log("Coder", "TokenMetrics", json.dumps({
            "total_tokens": today_totals.get("total_tokens", 0),
            "total_cost": today_totals.get("total_cost", 0.0)
        }, ensure_ascii=False))
    except Exception:
        pass

    return created_files


def run_sandbox_and_tests(
    manager,
    current_code: str,
    created_files: List[str],
    iteration: int,
    project_type: str
) -> Tuple[str, bool, Dict[str, Any], Dict[str, Any], str]:
    """
    Fuehrt Sandbox, Unit-Tests und UI-Tests aus.
    """
    sandbox_result = run_sandbox(current_code)
    manager._ui_log("Sandbox", "Result", sandbox_result)
    sandbox_failed = sandbox_result.startswith("❌")

    try:
        from sandbox_runner import validate_project_references
        ref_result = validate_project_references(manager.project_path)
        if ref_result.startswith("❌"):
            sandbox_result += f"\n{ref_result}"
            sandbox_failed = True
            manager._ui_log("Sandbox", "Referenzen", ref_result)
        else:
            manager._ui_log("Sandbox", "Referenzen", ref_result)
    except Exception as ref_err:
        manager._ui_log("Sandbox", "Warning", f"Referenz-Validierung fehlgeschlagen: {ref_err}")

    try:
        bat_result = validate_run_bat(manager.project_path, manager.tech_blueprint)
        if bat_result.issues:
            for issue in bat_result.issues:
                manager._ui_log("Tester", "RunBatWarning", issue)
        if bat_result.warnings:
            for warning in bat_result.warnings:
                manager._ui_log("Tester", "RunBatInfo", warning)
    except Exception as bat_err:
        manager._ui_log("Tester", "Warning", f"run.bat-Validierung fehlgeschlagen: {bat_err}")

    if sandbox_failed:
        try:
            memory_path = os.path.join(manager.base_dir, "memory", "global_memory.json")
            error_msg = extract_error_pattern(sandbox_result)
            tags = generate_tags_from_context(manager.tech_blueprint, sandbox_result)
            learn_result = learn_from_error(memory_path, error_msg, tags)
            manager._ui_log("Memory", "Learning", f"Sandbox: {learn_result}")
        except Exception as mem_err:
            manager._ui_log("Memory", "Error", f"Memory-Operation fehlgeschlagen: {mem_err}")

    unit_test_result = {"status": "SKIP", "summary": "Keine Unit-Tests", "test_count": 0}
    try:
        manager._ui_log("UnitTest", "Status", "Führe Unit-Tests durch...")
        manager._update_worker_status("tester", "working", "Unit-Tests...", "pytest/jest")
        unit_test_result = run_unit_tests(manager.project_path, manager.tech_blueprint)
        manager._ui_log("UnitTest", "Result", json.dumps({
            "status": unit_test_result.get("status"),
            "summary": unit_test_result.get("summary"),
            "test_count": unit_test_result.get("test_count", 0),
            "iteration": iteration + 1
        }, ensure_ascii=False))
        if unit_test_result.get("status") == "FAIL":
            sandbox_failed = True
            sandbox_result += f"\n\n❌ UNIT-TESTS FEHLGESCHLAGEN:\n{unit_test_result.get('summary', '')}"
            if unit_test_result.get("details"):
                sandbox_result += f"\n{unit_test_result.get('details', '')[:1000]}"
    except ImportError:
        manager._ui_log("UnitTest", "Warning", "unit_test_runner.py nicht gefunden - übersprungen")
    except Exception as ut_err:
        manager._ui_log("UnitTest", "Error", f"Unit-Test Fehler: {ut_err}")

    test_summary = "Keine UI-Tests durchgeführt."
    manager._ui_log("Tester", "Status", f"Starte Tests für Projekt-Typ '{project_type}'...")
    manager._update_worker_status("tester", "working", f"Teste {project_type}...", manager.model_router.get_model("tester") if manager.model_router else "")
    ui_result = {"status": "SKIP", "issues": [], "screenshot": None}

    try:
        ui_result = test_project(manager.project_path, manager.tech_blueprint, manager.config)
        test_summary = summarize_ui_result(ui_result)
        manager._ui_log("Tester", "Result", test_summary)

        screenshot_base64 = None
        if ui_result.get("screenshot") and os.path.exists(ui_result["screenshot"]):
            try:
                with open(ui_result["screenshot"], "rb") as img_file:
                    screenshot_base64 = f"data:image/png;base64,{base64.b64encode(img_file.read()).decode('utf-8')}"
            except Exception as img_err:
                manager._ui_log("Tester", "Warning", f"Screenshot konnte nicht geladen werden: {img_err}")

        manager._ui_log("Tester", "UITestResult", json.dumps({
            "status": ui_result["status"],
            "issues": ui_result.get("issues", []),
            "screenshot": screenshot_base64,
            "model": manager.model_router.get_model("tester") if hasattr(manager, 'model_router') else ""
        }, ensure_ascii=False))
        manager._update_worker_status("tester", "idle")

        if ui_result["status"] in ["FAIL", "ERROR"]:
            sandbox_failed = True
            try:
                memory_path = os.path.join(manager.base_dir, "memory", "global_memory.json")
                error_msg = extract_error_pattern(test_summary)
                tags = generate_tags_from_context(manager.tech_blueprint, test_summary)
                tags.append("ui-test")
                learn_result = learn_from_error(memory_path, error_msg, tags)
                manager._ui_log("Memory", "Learning", f"Test: {learn_result}")
            except Exception as mem_err:
                manager._ui_log("Memory", "Error", f"Memory-Operation fehlgeschlagen: {mem_err}")
    except Exception as te:
        test_summary = f"❌ Test-Runner Fehler: {te}"
        manager._ui_log("Tester", "Error", test_summary)
        manager._update_worker_status("tester", "idle")
        sandbox_failed = True
        ui_result = {"status": "ERROR", "issues": [str(te)], "screenshot": None}

    unit_ok = unit_test_result.get("status") in ["OK", "SKIP"]
    ui_ok = ui_result.get("status", "SKIP") not in ["FAIL", "ERROR"]
    test_result = {
        "unit_tests": {
            "status": unit_test_result.get("status", "SKIP"),
            "passed": unit_test_result.get("test_count", 0),
            "failed_count": unit_test_result.get("failed_count", 0),
            "summary": unit_test_result.get("summary", ""),
            "details": unit_test_result.get("details", "")
        },
        "ui_tests": {
            "status": ui_result.get("status", "SKIP"),
            "issues": ui_result.get("issues", []),
            "screenshot": ui_result.get("screenshot"),
            "has_visible_content": True
        },
        "overall_status": "PASS" if (unit_ok and ui_ok) else "FAIL"
    }

    manager._ui_log("Tester", "TestSummary", json.dumps({
        "overall_status": test_result.get("overall_status"),
        "unit_status": test_result["unit_tests"]["status"],
        "unit_passed": test_result["unit_tests"]["passed"],
        "ui_status": test_result["ui_tests"]["status"],
        "ui_issues_count": len(test_result["ui_tests"]["issues"]),
        "iteration": iteration + 1
    }, ensure_ascii=False))

    return sandbox_result, sandbox_failed, test_result, ui_result, test_summary


def run_review(
    manager,
    project_rules: Dict[str, Any],
    current_code: str,
    sandbox_result: str,
    test_summary: str,
    sandbox_failed: bool,
    run_with_timeout
) -> Tuple[str, str, str]:
    """
    Fuehrt den Review-Task mit Retry-Logik aus.
    """
    r_prompt = f"Review Code:\n{current_code}\nSandbox: {sandbox_result}\nTester: {test_summary}"
    manager._update_worker_status("reviewer", "working", "Prüfe Code...", manager.model_router.get_model("reviewer") if manager.model_router else "")

    MAX_REVIEW_RETRIES = 3
    REVIEWER_TIMEOUT_SECONDS = 120
    review_output = None
    agent_reviewer = manager.agent_reviewer

    for review_attempt in range(MAX_REVIEW_RETRIES):
        task_review = Task(description=r_prompt, expected_output="OK/Feedback", agent=agent_reviewer)
        current_model = manager.model_router.get_model("reviewer")
        try:
            review_output = run_with_timeout(
                lambda: str(task_review.execute_sync()),
                timeout_seconds=REVIEWER_TIMEOUT_SECONDS
            )
            if is_empty_or_invalid_response(review_output):
                manager._ui_log("Reviewer", "NoResponse",
                                f"Modell {current_model} lieferte keine Antwort (Versuch {review_attempt + 1}/{MAX_REVIEW_RETRIES})")
                manager.model_router.mark_rate_limited_sync(current_model)
                agent_reviewer = init_agents(
                    manager.config,
                    project_rules,
                    router=manager.model_router,
                    include=["reviewer"]
                ).get("reviewer")
                manager.agent_reviewer = agent_reviewer
                continue
            break
        except TimeoutError as te:
            manager._ui_log("Reviewer", "Timeout",
                            f"Reviewer-Modell {current_model} timeout nach {REVIEWER_TIMEOUT_SECONDS}s (Versuch {review_attempt + 1}/{MAX_REVIEW_RETRIES}), wechsle zu Fallback...")
            manager.model_router.mark_rate_limited_sync(current_model)
            agent_reviewer = init_agents(
                manager.config,
                project_rules,
                router=manager.model_router,
                include=["reviewer"]
            ).get("reviewer")
            manager.agent_reviewer = agent_reviewer
            continue
        except Exception as error:
            if is_rate_limit_error(error):
                manager.model_router.mark_rate_limited_sync(current_model)
                manager._ui_log("ModelRouter", "RateLimit", f"Reviewer-Modell {current_model} pausiert, wechsle zu Fallback...")
                agent_reviewer = init_agents(
                    manager.config,
                    project_rules,
                    router=manager.model_router,
                    include=["reviewer"]
                ).get("reviewer")
                manager.agent_reviewer = agent_reviewer
                continue
            raise error

    if is_empty_or_invalid_response(review_output):
        review_output = "FEHLER: Alle Review-Modelle haben versagt. Bitte prüfe die API-Verbindung und Modell-Verfügbarkeit."
        manager._ui_log("Reviewer", "AllModelsFailed", "Kein Modell konnte eine gültige Antwort liefern.")

    reviewer_model = manager.model_router.get_model("reviewer") if manager.model_router else "unknown"
    review_verdict = "OK" if "OK" in review_output.upper() and not sandbox_failed else "FEEDBACK"
    is_approved = review_verdict == "OK" and not sandbox_failed
    human_summary = create_human_readable_verdict(review_verdict, sandbox_failed, review_output)

    manager._ui_log("Reviewer", "ReviewOutput", json.dumps({
        "verdict": review_verdict,
        "isApproved": is_approved,
        "humanSummary": human_summary,
        "feedback": review_output if review_verdict == "FEEDBACK" else "",
        "model": reviewer_model,
        "iteration": manager.iteration + 1,
        "maxIterations": manager.max_retries,
        "sandboxStatus": "PASS" if not sandbox_failed else "FAIL",
        "sandboxResult": sandbox_result[:500] if sandbox_result else "",
        "testSummary": test_summary[:500] if test_summary else "",
        "reviewOutput": review_output if review_output else ""
    }, ensure_ascii=False))
    manager._update_worker_status("reviewer", "idle")

    return review_output, review_verdict, human_summary


def run_security_rescan(manager, project_rules: Dict[str, Any], current_code: str, iteration: int) -> Tuple[bool, List[Dict[str, Any]]]:
    """
    Fuehrt Security-Rescan fuer den generierten Code aus.
    """
    security_passed = True
    security_rescan_vulns = []

    if manager.agent_security and current_code:
        manager._ui_log("Security", "RescanStart", f"Prüfe generierten Code (Iteration {iteration + 1})...")
        manager._update_worker_status("security", "working", f"Security-Scan Iteration {iteration + 1}", manager.model_router.get_model("security") if manager.model_router else "")

        security_rescan_prompt = f"""Prüfe diesen Code auf Sicherheitsprobleme:

{current_code}

ANTWORT-FORMAT (eine Zeile pro Problem):
VULNERABILITY: [Problem-Beschreibung] | FIX: [Konkrete Lösung mit Code-Beispiel] | SEVERITY: [CRITICAL/HIGH/MEDIUM/LOW]

BEISPIEL:
VULNERABILITY: innerHTML in Zeile 15 ermöglicht XSS-Angriffe | FIX: Ersetze element.innerHTML = userInput mit element.textContent = userInput oder nutze DOMPurify.sanitize(userInput) | SEVERITY: HIGH

PRÜFE NUR auf die 3 wichtigsten Kategorien:
1. XSS (innerHTML, document.write, eval mit User-Input)
2. SQL/NoSQL Injection (String-Konkatenation in Queries)
3. Hardcoded Secrets (API-Keys, Passwörter im Code)

WICHTIG:
- Bei Taschenrechner-Apps: eval() mit Button-Input ist LOW severity (kein User-Text-Input)
- Bei statischen Webseiten: innerHTML ohne User-Input ist kein Problem
- Gib für JEDEN Fix KONKRETEN Code der das Problem löst

Wenn KEINE kritischen Probleme gefunden: Antworte nur mit "SECURE"
"""

        task_security_rescan = Task(
            description=security_rescan_prompt,
            expected_output="SECURE oder VULNERABILITY-Liste",
            agent=manager.agent_security
        )

        try:
            security_rescan_result = str(task_security_rescan.execute_sync())
            security_rescan_vulns = extract_vulnerabilities(security_rescan_result)
            manager.security_vulnerabilities = security_rescan_vulns

            security_passed = not security_rescan_vulns or all(
                v.get('severity') == 'low' for v in security_rescan_vulns
            )

            security_rescan_model = manager.model_router.get_model("security") if manager.model_router else "unknown"
            rescan_status = "SECURE" if security_passed else "VULNERABLE"

            manager._ui_log("Security", "SecurityRescanOutput", json.dumps({
                "vulnerabilities": security_rescan_vulns,
                "overall_status": rescan_status,
                "scan_type": "code_scan",
                "iteration": iteration + 1,
                "blocking": not security_passed,
                "model": security_rescan_model,
                "timestamp": datetime.now().isoformat()
            }, ensure_ascii=False))

            manager._ui_log("Security", "RescanResult", f"Code-Scan: {rescan_status} ({len(security_rescan_vulns)} Findings)")
            manager._update_worker_status("security", "idle")
        except Exception as sec_err:
            manager._ui_log("Security", "Error", f"Security-Rescan fehlgeschlagen: {sec_err}")
            manager._update_worker_status("security", "idle")
            security_passed = True

    return security_passed, security_rescan_vulns


def build_feedback(
    manager,
    review_output: str,
    sandbox_failed: bool,
    sandbox_result: str,
    test_summary: str,
    test_result: Dict[str, Any],
    security_passed: bool,
    security_rescan_vulns: List[Dict[str, Any]]
) -> str:
    """
    Erstellt Feedback fuer den naechsten Coder-Iterationen.
    """
    feedback = ""
    if not security_passed and security_rescan_vulns:
        security_feedback = "\n".join([
            f"- [{v.get('severity', 'unknown').upper()}] {v.get('description', '')}\n"
            f"  → LÖSUNG: {v.get('fix', 'Bitte beheben')}"
            for v in security_rescan_vulns
        ])
        feedback = f"⚠️ SECURITY VULNERABILITIES - MÜSSEN ZUERST BEHOBEN WERDEN:\n{security_feedback}\n\n"
        feedback += "WICHTIG: Implementiere die Lösungsvorschläge (→ LÖSUNG) für JEDE Vulnerability!\n"
        feedback += "Der Code wird erst akzeptiert wenn alle Security-Issues behoben sind.\n"
        manager._ui_log("Security", "BlockingIssues", f"❌ {len(security_rescan_vulns)} Vulnerabilities blockieren Abschluss")
        return feedback

    if sandbox_failed:
        feedback = "KRITISCHER FEHLER: Die Sandbox oder der Tester hat Fehler gemeldet.\n"
        feedback += "Bitte analysiere die Fehlermeldungen und behebe sie:\n\n"
        feedback += f"SANDBOX:\n{sandbox_result}\n\n"

        structured_test_feedback = format_test_feedback(test_result)
        if structured_test_feedback and "✅" not in structured_test_feedback:
            feedback += f"\n{structured_test_feedback}\n"
        else:
            feedback += f"TESTER:\n{test_summary}\n"

        test_lower = test_summary.lower()
        if "leere seite" in test_lower or "leer" in test_lower or "kein sichtbar" in test_lower:
            feedback += "\nDIAGNOSE - LEERE SEITE ERKANNT:\n"
            pt = str(manager.tech_blueprint.get("project_type", "")).lower()
            lang = str(manager.tech_blueprint.get("language", "")).lower()
            if any(kw in pt for kw in ["react", "next", "vue"]) or lang == "javascript":
                feedback += "- Pruefe ob ReactDOM.createRoot() oder ReactDOM.render() korrekt aufgerufen wird\n"
                feedback += "- Pruefe ob die App-Komponente exportiert und importiert wird\n"
                feedback += "- Pruefe ob index.html ein <div id='root'></div> enthaelt\n"
                feedback += "- Pruefe ob <script> Tags korrekte Pfade haben\n"
            elif any(kw in pt for kw in ["flask", "fastapi", "django"]):
                feedback += "- Pruefe ob die Route '/' definiert ist und HTML zurueckgibt\n"
                feedback += "- Pruefe ob Templates im Ordner 'templates/' liegen\n"
                feedback += "- Pruefe ob render_template() den korrekten Dateinamen verwendet\n"
            else:
                feedback += "- Pruefe ob index.html sichtbare HTML-Elemente im <body> hat\n"
                feedback += "- Pruefe ob alle <script src> und <link href> Pfade korrekt sind\n"
                feedback += "- Pruefe ob JavaScript-Code korrekt referenzierte Dateien hat\n"

        if "referenz" in test_lower or "nicht gefunden" in sandbox_result.lower():
            feedback += "\nDATEI-REFERENZEN:\n"
            feedback += "Es fehlen referenzierte Dateien. Stelle sicher, dass alle\n"
            feedback += "in HTML eingebundenen Scripts und Stylesheets auch erstellt werden.\n"
        return feedback

    return review_output


def handle_model_switch(
    manager,
    project_rules: Dict[str, Any],
    current_coder_model: str,
    models_used: List[str],
    failed_attempts_history: List[Dict[str, Any]],
    model_attempt: int,
    max_model_attempts: int,
    feedback: str,
    iteration: int
) -> Tuple[str, int, List[str], str]:
    """
    Fuehrt Modellwechsel-Logik aus und passt Feedback an.
    """
    if model_attempt < max_model_attempts:
        return current_coder_model, model_attempt, models_used, feedback

    old_model = current_coder_model
    manager.model_router.mark_rate_limited_sync(current_coder_model)
    current_coder_model = manager.model_router.get_model("coder")

    if current_coder_model != old_model:
        models_used.append(current_coder_model)
        model_attempt = 0
        manager.agent_coder = init_agents(
            manager.config,
            project_rules,
            router=manager.model_router,
            include=["coder"]
        ).get("coder")

        manager._ui_log("Coder", "ModelSwitch", json.dumps({
            "old_model": old_model,
            "new_model": current_coder_model,
            "reason": "max_attempts_reached",
            "attempt": max_model_attempts,
            "models_used": models_used,
            "failed_attempts": len(failed_attempts_history)
        }, ensure_ascii=False))

        history_summary = "\n".join([
            f"- Modell '{a['model']}' (Iteration {a['iteration']}): {a['feedback'][:200]}"
            for a in failed_attempts_history[-3:]
        ])
        feedback += f"\n\n🔄 MODELLWECHSEL: Das vorherige Modell ({old_model}) konnte dieses Problem nicht lösen.\n"
        feedback += f"BISHERIGE VERSUCHE (diese Ansätze haben NICHT funktioniert):\n{history_summary}\n"
        feedback += "\nWICHTIG: Versuche einen VÖLLIG ANDEREN Ansatz! Was bisher versucht wurde, funktioniert nicht!\n"

        manager._ui_log("Coder", "Status", f"🔄 Modellwechsel: {old_model} → {current_coder_model} (Versuch {len(models_used)})")
    else:
        manager._ui_log("Coder", "Warning", f"⚠️ Kein weiteres Modell verfügbar - fahre mit {current_coder_model} fort")

    return current_coder_model, model_attempt, models_used, feedback
