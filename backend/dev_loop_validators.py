# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 02.02.2026
Version: 1.5
Beschreibung: Validierungs-Funktionen für DevLoop.
              Extrahiert aus dev_loop_steps.py (Regel 1: Max 500 Zeilen)
              Enthält: Sandbox+Tests, Review, Security-Rescan
              ÄNDERUNG 29.01.2026: Modellwechsel erst nach 2 gleichen Fehlern
              AENDERUNG 31.01.2026: Docker-Isolation, Projekt-Typ-aware Sandbox
              ÄNDERUNG 02.02.2026: Fix #11 - Reviewer analysiert Docker-Fehler spezifisch
              AENDERUNG 02.02.2026 v1.2: Pre-Docker Validierung integriert
              AENDERUNG 02.02.2026 v1.3: Fix #13 - Harmlose pip-Warnungen nicht als Fehler
              AENDERUNG 02.02.2026 v1.4: Fix #14 - Docker stdout+stderr kombiniert fuer Reviewer
              AENDERUNG 02.02.2026 v1.5: Fix #15 - pytest-Ergebnisse separat extrahieren
"""

import os
import json
import base64
import logging
from datetime import datetime
from typing import Dict, Any, List, Tuple
from concurrent.futures import ThreadPoolExecutor

from crewai import Task

from agents.memory_agent import (
    extract_error_pattern,
    generate_tags_from_context,
    learn_from_error
)
from backend.docker_executor import create_docker_executor
from unit_test_runner import run_unit_tests
from agents.tester_agent import test_project, summarize_ui_result
from content_validator import validate_run_bat, validate_nextjs_structure
from .agent_factory import init_agents
from .orchestration_helpers import (
    is_rate_limit_error,
    is_empty_or_invalid_response,
    is_model_unavailable_error,
    is_empty_response_error,
    is_openrouter_error,  # ÄNDERUNG 02.02.2026: OpenRouter-Fehler für sofortigen Modellwechsel
    create_human_readable_verdict,
    extract_vulnerabilities,
    truncate_review_output
)
from .heartbeat_utils import run_with_heartbeat
from .dev_loop_helpers import run_sandbox_for_project
from .dev_loop_test_utils import ensure_tests_exist
from .pre_docker_validator import validate_before_docker  # AENDERUNG 02.02.2026: Pre-Docker Validierung

logger = logging.getLogger(__name__)


# AENDERUNG 02.02.2026: Hilfsfunktion zur Unterscheidung von Warnungen vs Fehler
def _is_harmless_warning_only(stderr: str, stdout: str = "") -> bool:
    """
    Prueft ob Docker-Output nur harmlose Warnungen enthaelt, keine echten Fehler.

    Bekannte harmlose Warnungen:
    - pip "Running as root" Warnung
    - pip "new release available" Notice
    - npm audit Warnungen

    Returns:
        True wenn nur Warnungen (kein Handlungsbedarf), False wenn echte Fehler
    """
    # Bekannte harmlose Warnungs-Patterns
    harmless_patterns = [
        "WARNING: Running pip as the 'root' user",
        "[notice] A new release of pip is available",
        "[notice] To update, run: pip install --upgrade pip",
        "npm WARN",
        "npm notice",
    ]

    # Echte Fehler-Keywords die NICHT ignoriert werden duerfen
    error_keywords = [
        "Error:", "ERROR:", "error:",
        "Failed:", "FAILED:", "failed:",
        "Exception:", "exception:",
        "Traceback (most recent call last)",
        "ModuleNotFoundError",
        "ImportError",
        "SyntaxError",
        "NameError",
        "TypeError",
        "ValueError",
        "AttributeError",
        "FileNotFoundError",
        "ResolutionImpossible",
        "Could not find a version",
        "No matching distribution",
        "pytest: error",
        "ERRORS",
        "= FAILURES =",
    ]

    combined_output = (stderr or "") + (stdout or "")

    # Pruefe auf echte Fehler
    for keyword in error_keywords:
        if keyword in combined_output:
            return False  # Echter Fehler gefunden

    # AENDERUNG 02.02.2026 (Fix): Zeilenbasierte Pruefung statt Pattern-Ersetzung
    # Problem: replace() entfernt nur Pattern-Anfang, Rest der Zeile bleibt uebrig
    # Loesung: Pruefe jede Zeile ob sie mit einem bekannten Pattern BEGINNT oder es enthaelt
    lines = combined_output.split('\n')
    non_warning_lines = []

    for line in lines:
        line_stripped = line.strip()
        if not line_stripped:
            continue  # Leere Zeilen ignorieren

        # Pruefe ob diese Zeile eine bekannte harmlose Warnung ist
        is_harmless = False

        # Pattern-basierte Pruefung (Zeile ENTHAELT Pattern)
        for pattern in harmless_patterns:
            if pattern in line:
                is_harmless = True
                break

        # Allgemeine Warnungs-Pruefung (Zeile BEGINNT mit warning/notice/etc.)
        if not is_harmless:
            lower_line = line_stripped.lower()
            if lower_line.startswith(('warning', 'notice', 'warn', '[notice]', '[warning]', 'npm warn')):
                is_harmless = True

        if not is_harmless:
            non_warning_lines.append(line_stripped)

    # Wenn keine nicht-harmlosen Zeilen uebrig bleiben, waren es nur Warnungen
    return len(non_warning_lines) == 0


def run_sandbox_and_tests(
    manager,
    current_code: str,
    created_files: List[str],
    iteration: int,
    project_type: str
) -> Tuple[str, bool, Dict[str, Any], Dict[str, Any], str]:
    """
    Fuehrt Sandbox, Unit-Tests und UI-Tests aus.
    ÄNDERUNG 31.01.2026: Projekt-Typ-aware Sandbox-Check - keine JS-Checks bei Python-Projekten.
    AENDERUNG 31.01.2026: Docker-Isolation wenn aktiviert (config.yaml: docker.enabled=true).
    AENDERUNG 02.02.2026: Pre-Docker Validierung - erkennt Fehler VOR Docker-Lauf.
    """
    # AENDERUNG 02.02.2026: Pre-Docker Validierung - Fehler frueh erkennen
    # Spart Docker-Zeit wenn Code offensichtliche Fehler hat (Truncation, zirkulaere Imports)
    if created_files and manager.project_path:
        project_files = {}
        for filepath in created_files:
            full_path = os.path.join(manager.project_path, filepath)
            if os.path.exists(full_path):
                try:
                    with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                        project_files[filepath] = f.read()
                except Exception as read_err:
                    logger.debug(f"Pre-Docker: Konnte {filepath} nicht lesen: {read_err}")

        if project_files:
            pre_validation = validate_before_docker(project_files)
            if not pre_validation.is_valid:
                manager._ui_log("PreDocker", "Warning",
                    f"Pre-Docker Validierung: {len(pre_validation.issues)} Fehler gefunden")
                for issue in pre_validation.issues[:3]:  # Max 3 Issues loggen
                    manager._ui_log("PreDocker", "Issue",
                        f"{issue.file_path}: {issue.issue_type} - {issue.message}")

                # Feedback fuer Coder zurueckgeben statt Docker laufen zu lassen
                pre_fail_result = {
                    "unit_tests": {
                        "status": "FAIL",
                        "summary": pre_validation.feedback_for_coder,
                        "passed": 0,
                        "failed_count": len(pre_validation.issues),
                        "details": "Pre-Docker Validierung fehlgeschlagen"
                    },
                    "ui_tests": {"status": "SKIP", "issues": [], "screenshot": None, "has_visible_content": True},
                    "overall_status": "FAIL"
                }
                return (
                    pre_validation.feedback_for_coder,
                    True,  # sandbox_failed
                    pre_fail_result,
                    {"status": "SKIP", "issues": ["Pre-Docker Validierung fehlgeschlagen"], "screenshot": None},
                    "Pre-Docker Validierung: " + ", ".join(i.issue_type for i in pre_validation.issues[:3])
                )
            else:
                manager._ui_log("PreDocker", "OK", "Code-Validierung bestanden")

    # AENDERUNG 31.01.2026: Docker-Isolation fuer Tests wenn aktiviert
    docker_config = manager.config.get("docker", {})
    use_docker = docker_config.get("enabled", False)

    # AENDERUNG 31.01.2026: Docker-Testergebnis nutzen, Host-Tests ueberspringen wenn Docker OK
    docker_ran_and_succeeded = False
    executor = None

    if use_docker:
        try:
            executor = create_docker_executor(
                project_path=manager.project_path,
                tech_blueprint=manager.tech_blueprint,
                docker_config=docker_config
            )

            if executor.is_docker_available():
                manager._ui_log("Docker", "Status", "Docker-Isolation aktiviert")

                # AENDERUNG 01.02.2026: Install + Test in EINEM Container
                # Vorher: getrennte Aufrufe fuehrten zu "No module named pytest"
                manager._ui_log("Docker", "Info", "Installiere Dependencies und fuehre Tests aus...")
                combined_result = executor.install_and_test()

                if combined_result.success:
                    manager._ui_log("Docker", "Result",
                        f"Docker Install+Test erfolgreich in {combined_result.duration_seconds:.1f}s")
                    docker_ran_and_succeeded = True
                # AENDERUNG 02.02.2026: Harmlose Warnungen (pip root, npm warn) nicht als Fehler behandeln
                # Problem: pip gibt immer "Running as root" Warnung in Docker aus -> endloser Loop
                # Loesung: Pruefe ob Output NUR Warnungen enthaelt, keine echten Fehler
                elif _is_harmless_warning_only(combined_result.stderr, combined_result.stdout):
                    manager._ui_log("Docker", "Info",
                        f"Docker Install+Test OK (mit Warnungen) in {combined_result.duration_seconds:.1f}s")
                    manager._ui_log("Docker", "Warning",
                        f"Harmlose Warnung ignoriert:\n{combined_result.stderr[:200]}...")
                    docker_ran_and_succeeded = True
                else:
                    # AENDERUNG 02.02.2026 v1.4: stdout + stderr kombinieren fuer vollstaendige Fehleranalyse
                    # Problem: pytest-Fehler sind in stdout, pip-Warnungen in stderr
                    # Reviewer sah nur stderr und konnte echte Fehler nicht diagnostizieren
                    # AENDERUNG 02.02.2026 v1.5: pytest-Fehler separat extrahieren - sie werden oft
                    # durch pip-Download-Logs abgeschnitten und der Reviewer sieht nur pip-Warnungen
                    combined_error = ""
                    stdout_content = combined_result.stdout.strip()
                    stderr_content = combined_result.stderr.strip()

                    # v1.5: Extrahiere pytest-Ergebnisse separat (am Ende des Outputs)
                    pytest_section = ""
                    if stdout_content:
                        # Suche nach pytest-Output Markern
                        pytest_markers = ["= FAILURES =", "= ERRORS =", "= short test summary",
                                          "FAILED", "ERROR", "passed", "failed"]
                        stdout_lines = stdout_content.split('\n')
                        pytest_start_idx = -1
                        for idx, line in enumerate(stdout_lines):
                            if any(marker in line for marker in pytest_markers):
                                pytest_start_idx = idx
                                break

                        if pytest_start_idx >= 0:
                            pytest_section = "\n".join(stdout_lines[pytest_start_idx:])[:1000]
                            combined_error += f"=== PYTEST-ERGEBNISSE (WICHTIG!) ===\n{pytest_section}\n\n"

                        # Zeige auch den pip-Teil (gekuerzt)
                        pip_part = "\n".join(stdout_lines[:min(15, pytest_start_idx if pytest_start_idx >= 0 else len(stdout_lines))])
                        combined_error += f"=== STDOUT (pip install) ===\n{pip_part[:500]}\n"

                    if stderr_content:
                        combined_error += f"=== STDERR (Warnungen) ===\n{stderr_content[:500]}"

                    if not combined_error:
                        combined_error = "Keine Output-Details verfuegbar"

                    manager._ui_log("Docker", "Warning",
                        f"Docker Install+Test fehlgeschlagen:\n{combined_error[:1500]}")
                    docker_fail_result = {
                        "unit_tests": {"status": "FAIL", "summary": combined_error[:800], "passed": 0, "failed_count": 0, "details": combined_result.stdout},
                        "ui_tests": {"status": "SKIP", "issues": [], "screenshot": None, "has_visible_content": True},
                        "overall_status": "FAIL"
                    }
                    try:
                        executor.cleanup()
                    except Exception as cleanup_err:
                        logger.warning("Docker-Cleanup nach Test-Fehler fehlgeschlagen: %s", cleanup_err)
                    # AENDERUNG 02.02.2026 v1.4: stderr UND stdout kombiniert zurueckgeben
                    return (combined_error[:1500], True, docker_fail_result, {"status": "FAIL", "issues": [combined_error[:500]], "screenshot": None}, "Docker-Tests fehlgeschlagen")
            else:
                if docker_config.get("fallback_to_host", True):
                    manager._ui_log("Docker", "Warning",
                        "Docker nicht verfuegbar - Fallback auf Host-Ausfuehrung")
                else:
                    manager._ui_log("Docker", "Error",
                        "Docker nicht verfuegbar und Fallback deaktiviert")
                    return ("Docker nicht verfuegbar", True,
                            {"unit_tests": {"status": "ERROR"}, "ui_tests": {"status": "ERROR"}},
                            {"status": "ERROR"}, "Docker nicht verfuegbar")
        except Exception as docker_err:
            manager._ui_log("Docker", "Error", f"Docker-Fehler: {docker_err}")
            if not docker_config.get("fallback_to_host", True):
                raise
        finally:
            if executor is not None:
                try:
                    executor.cleanup()
                except Exception as cleanup_err:
                    logger.warning("Docker-Cleanup fehlgeschlagen: %s", cleanup_err)

    # ÄNDERUNG 31.01.2026: Nutze Projekt-Typ-aware Sandbox statt generischem run_sandbox()
    sandbox_result = run_sandbox_for_project(current_code, manager.tech_blueprint)
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

    # AENDERUNG 07.02.2026: Next.js Pflichtdateien pruefen (pages/_app.js, react-dom etc.)
    try:
        nextjs_result = validate_nextjs_structure(manager.project_path, manager.tech_blueprint)
        if nextjs_result.issues:
            for issue in nextjs_result.issues:
                manager._ui_log("Sandbox", "NextJsStruktur", issue)
                sandbox_result += f"\nNext.js-Strukturfehler: {issue}"
                sandbox_failed = True
        if nextjs_result.warnings:
            for warning in nextjs_result.warnings:
                manager._ui_log("Sandbox", "NextJsInfo", warning)
    except Exception as njs_err:
        manager._ui_log("Sandbox", "Warning", f"Next.js-Validierung fehlgeschlagen: {njs_err}")

    if sandbox_failed:
        try:
            memory_path = os.path.join(manager.base_dir, "memory", "global_memory.json")
            error_msg = extract_error_pattern(sandbox_result)
            tags = generate_tags_from_context(manager.tech_blueprint, sandbox_result)
            # ÄNDERUNG 29.01.2026: Non-blocking Memory-Operation für WebSocket-Stabilität
            with ThreadPoolExecutor(max_workers=1) as mem_executor:
                future = mem_executor.submit(learn_from_error, memory_path, error_msg, tags)
                learn_result = future.result(timeout=5)  # Max 5s warten
            manager._ui_log("Memory", "Learning", f"Sandbox: {learn_result}")
        except Exception as mem_err:
            manager._ui_log("Memory", "Error", f"Memory-Operation fehlgeschlagen: {mem_err}")

    unit_test_result = {"status": "SKIP", "summary": "Keine Unit-Tests", "test_count": 0}
    if docker_ran_and_succeeded:
        unit_test_result = {"status": "OK", "summary": "Docker-Tests erfolgreich (Host-Tests uebersprungen)", "test_count": 0}
        manager._ui_log("UnitTest", "Result", "Docker-Tests erfolgreich - Host Unit-Tests uebersprungen")
    try:
        if not docker_ran_and_succeeded:
            manager._ui_log("UnitTest", "Status", "Führe Unit-Tests durch...")
            manager._update_worker_status("tester", "working", "Unit-Tests...", "pytest/jest")

            # ÄNDERUNG 30.01.2026: Stelle sicher dass Tests existieren bevor wir sie ausführen
            ensure_tests_exist(manager, iteration)

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
    if docker_ran_and_succeeded:
        ui_result = {"status": "OK", "issues": [], "screenshot": None}
        test_summary = "Docker-Tests erfolgreich - Host UI-Tests uebersprungen."

    try:
        if not docker_ran_and_succeeded:
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
                # ÄNDERUNG 29.01.2026: Non-blocking Memory-Operation für WebSocket-Stabilität
                with ThreadPoolExecutor(max_workers=1) as mem_executor:
                    future = mem_executor.submit(learn_from_error, memory_path, error_msg, tags)
                    learn_result = future.result(timeout=5)  # Max 5s warten
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
    run_with_timeout_func
) -> Tuple[str, str, str]:
    """
    Fuehrt den Review-Task mit Retry-Logik aus.
    ÄNDERUNG 29.01.2026: Modellwechsel erst nach 2 gleichen Fehlern mit demselben Modell.
    ÄNDERUNG 02.02.2026: Erweiterter Prompt fuer spezifische Docker-Fehler-Analyse (Fix #11).
    """
    # ÄNDERUNG 02.02.2026: Erweiterter Reviewer-Prompt mit Docker-Fehler-Analyse
    # Problem: Reviewer gab generisches Feedback statt spezifische Fehleranalyse

    # ÄNDERUNG 02.02.2026 v2: Extrahiere spezifische Fehler aus Docker-Output
    docker_error_highlight = ""
    if sandbox_result and sandbox_failed:
        # Extrahiere relevante Fehlerzeilen
        error_keywords = ["Error", "ImportError", "ModuleNotFoundError", "SyntaxError",
                         "ResolutionImpossible", "conflicting", "in <module>", ".py:"]
        error_lines = []
        for line in sandbox_result.split('\n'):
            if any(kw in line for kw in error_keywords):
                error_lines.append(line.strip())
        if error_lines:
            docker_error_highlight = "\n>>> KRITISCHE FEHLER GEFUNDEN <<<\n" + "\n".join(error_lines[:10])

    r_prompt = f"""=== CODE ZUM PRUEFEN ===
{current_code}

=== SANDBOX/DOCKER-ERGEBNIS (WICHTIG!) ===
{sandbox_result if sandbox_result else "Kein Sandbox-Ergebnis vorhanden."}
{docker_error_highlight}

=== TEST-ZUSAMMENFASSUNG ===
{test_summary if test_summary else "Keine Test-Zusammenfassung vorhanden."}

=== ANALYSE-ANWEISUNGEN ===
ANALYSIERE den EXAKTEN Fehler oben im SANDBOX/DOCKER-ERGEBNIS!

Bei Fehlern MUSST du folgendes liefern:
1. URSACHE: Die KONKRETE Ursache (NICHT generisch "Docker fehlgeschlagen")
2. DATEI: Die EXAKTE Datei die geaendert werden muss
3. LOESUNG: Konkreter Fix mit Code-Beispiel

BEISPIELE fuer korrektes Feedback:
- "ModuleNotFoundError: No module named 'flask'"
  -> URSACHE: flask fehlt in requirements.txt
  -> DATEI: requirements.txt
  -> LOESUNG: Fuege 'flask' zu requirements.txt hinzu

- "SyntaxError: unexpected indent in line 15"
  -> URSACHE: Einrueckungsfehler in Zeile 15
  -> DATEI: app.py
  -> LOESUNG: Korrigiere die Einrueckung in Zeile 15

- "ImportError: cannot import name 'Config' from 'config'"
  -> URSACHE: Klasse Config existiert nicht in config.py
  -> DATEI: config.py
  -> LOESUNG: Erstelle die Config-Klasse in config.py

VERBOTEN - Niemals solches Feedback geben:
- "Die Docker-Tests sind fehlgeschlagen, was darauf hindeutet..."
- "Es gibt Probleme mit der Konfiguration"
- Unspezifische Aussagen ohne konkrete Dateinennung
- OK sagen wenn Fehler im SANDBOX/DOCKER-ERGEBNIS vorhanden sind

Wenn der Code FEHLERFREI ist und alle Tests bestanden: Antworte mit "OK"
"""
    manager._update_worker_status("reviewer", "working", "Prüfe Code...", manager.model_router.get_model("reviewer") if manager.model_router else "")

    MAX_REVIEW_RETRIES = 6  # Erhöht: 2 Versuche pro Modell x 3 Modelle
    # ÄNDERUNG 30.01.2026: Timeout aus globaler Config
    REVIEWER_TIMEOUT_SECONDS = manager.config.get("agent_timeout_seconds", 300)
    # ÄNDERUNG 29.01.2026: Modellwechsel erst nach X gleichen Fehlern
    ERRORS_BEFORE_MODEL_SWITCH = 2
    review_output = None
    agent_reviewer = manager.agent_reviewer

    # Fehler-Tracker: (modell, fehlertyp) -> anzahl
    error_tracker = {}
    last_error_type = None

    for review_attempt in range(MAX_REVIEW_RETRIES):
        task_review = Task(description=r_prompt, expected_output="OK/Feedback", agent=agent_reviewer)
        current_model = manager.model_router.get_model("reviewer")
        try:
            # ÄNDERUNG 29.01.2026: Heartbeat-Wrapper für stabile WebSocket-Verbindung
            review_output = run_with_heartbeat(
                func=lambda: str(task_review.execute_sync()),
                ui_log_callback=manager._ui_log,
                agent_name="Reviewer",
                task_description=f"Code-Review (Versuch {review_attempt + 1}/{MAX_REVIEW_RETRIES})",
                heartbeat_interval=15,
                timeout_seconds=REVIEWER_TIMEOUT_SECONDS
            )
            if is_empty_or_invalid_response(review_output):
                error_type = "no_response"
                error_key = (current_model, error_type)

                # Bei neuem Fehlertyp: Tracker zurücksetzen
                if last_error_type and last_error_type != error_type:
                    error_tracker = {}
                last_error_type = error_type

                error_tracker[error_key] = error_tracker.get(error_key, 0) + 1
                error_count = error_tracker[error_key]

                manager._ui_log("Reviewer", "NoResponse",
                                f"Modell {current_model} lieferte keine Antwort (Fehler {error_count}/{ERRORS_BEFORE_MODEL_SWITCH})")

                # Erst nach ERRORS_BEFORE_MODEL_SWITCH gleichen Fehlern Modell wechseln
                if error_count >= ERRORS_BEFORE_MODEL_SWITCH:
                    manager._ui_log("Reviewer", "Status", f"🔄 Modellwechsel nach {error_count} gleichen Fehlern")
                    manager.model_router.mark_rate_limited_sync(current_model)
                    # AENDERUNG 06.02.2026: tech_blueprint fuer Tech-Stack-Kontext
                    agent_reviewer = init_agents(
                        manager.config,
                        project_rules,
                        router=manager.model_router,
                        include=["reviewer"],
                        tech_blueprint=getattr(manager, 'tech_blueprint', None)
                    ).get("reviewer")
                    manager.agent_reviewer = agent_reviewer
                    error_tracker = {}  # Tracker zurücksetzen nach Modellwechsel
                continue
            break
        except TimeoutError as te:
            # ÄNDERUNG 02.02.2026: OpenRouter-Fehler = sofortiger Modellwechsel
            if is_openrouter_error(te):
                manager._ui_log("Reviewer", "OpenRouterError",
                                f"OpenRouter-Fehler erkannt bei {current_model} - sofortiger Modellwechsel")
                manager.model_router.mark_rate_limited_sync(current_model)
                # AENDERUNG 06.02.2026: tech_blueprint fuer Tech-Stack-Kontext
                agent_reviewer = init_agents(
                    manager.config,
                    project_rules,
                    router=manager.model_router,
                    include=["reviewer"],
                    tech_blueprint=getattr(manager, 'tech_blueprint', None)
                ).get("reviewer")
                manager.agent_reviewer = agent_reviewer
                error_tracker = {}  # Tracker zurücksetzen nach Modellwechsel
                continue

            # Normaler Timeout (kein OpenRouter-spezifischer Fehler)
            error_type = "timeout"
            error_key = (current_model, error_type)

            # Bei neuem Fehlertyp: Tracker zurücksetzen
            if last_error_type and last_error_type != error_type:
                error_tracker = {}
            last_error_type = error_type

            error_tracker[error_key] = error_tracker.get(error_key, 0) + 1
            error_count = error_tracker[error_key]

            manager._ui_log("Reviewer", "Timeout",
                            f"Reviewer-Modell {current_model} timeout nach {REVIEWER_TIMEOUT_SECONDS}s (Fehler {error_count}/{ERRORS_BEFORE_MODEL_SWITCH})")

            # Erst nach ERRORS_BEFORE_MODEL_SWITCH gleichen Fehlern Modell wechseln
            if error_count >= ERRORS_BEFORE_MODEL_SWITCH:
                manager._ui_log("Reviewer", "Status", f"🔄 Modellwechsel nach {error_count} Timeouts")
                manager.model_router.mark_rate_limited_sync(current_model)
                # AENDERUNG 06.02.2026: tech_blueprint fuer Tech-Stack-Kontext
                agent_reviewer = init_agents(
                    manager.config,
                    project_rules,
                    router=manager.model_router,
                    include=["reviewer"],
                    tech_blueprint=getattr(manager, 'tech_blueprint', None)
                ).get("reviewer")
                manager.agent_reviewer = agent_reviewer
                error_tracker = {}  # Tracker zurücksetzen nach Modellwechsel
            continue
        except Exception as error:
            if is_rate_limit_error(error):
                # Rate-Limit: Sofort wechseln (keine Wartezeit sinnvoll)
                manager.model_router.mark_rate_limited_sync(current_model)
                manager._ui_log("ModelRouter", "RateLimit", f"Reviewer-Modell {current_model} pausiert, wechsle zu Fallback...")
                # AENDERUNG 06.02.2026: tech_blueprint fuer Tech-Stack-Kontext
                agent_reviewer = init_agents(
                    manager.config,
                    project_rules,
                    router=manager.model_router,
                    include=["reviewer"],
                    tech_blueprint=getattr(manager, 'tech_blueprint', None)
                ).get("reviewer")
                manager.agent_reviewer = agent_reviewer
                error_tracker = {}  # Tracker zurücksetzen
                continue
            # ÄNDERUNG 03.02.2026: ROOT-CAUSE-FIX - idle vor raise
            # Problem: raise ohne idle ließ Reviewer auf "working" stecken
            manager._update_worker_status("reviewer", "idle")
            raise

    if is_empty_or_invalid_response(review_output):
        review_output = "FEHLER: Alle Review-Modelle haben versagt. Bitte prüfe die API-Verbindung und Modell-Verfügbarkeit."
        manager._ui_log("Reviewer", "AllModelsFailed", "Kein Modell konnte eine gültige Antwort liefern.")

    # ÄNDERUNG 31.01.2026: Review-Output Truncation gegen Wiederholungsschleifen
    review_output = truncate_review_output(review_output, max_length=3000)

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
    ÄNDERUNG 30.01.2026: Retry/Fallback bei 404/Rate-Limit Fehlern hinzugefügt.
    """
    security_passed = True
    security_rescan_vulns = []
    MAX_SECURITY_RETRIES = 3
    # ÄNDERUNG 30.01.2026: Timeout aus globaler Config
    SECURITY_TIMEOUT = manager.config.get("agent_timeout_seconds", 300)

    if manager.agent_security and current_code:
        manager._ui_log("Security", "RescanStart", f"Prüfe generierten Code (Iteration {iteration + 1})...")

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

        # ÄNDERUNG 30.01.2026: Retry-Schleife mit Fallback bei 404/Rate-Limit
        for security_attempt in range(MAX_SECURITY_RETRIES):
            current_security_model = manager.model_router.get_model("security") if manager.model_router else "unknown"
            manager._update_worker_status("security", "working",
                f"Security-Scan (Versuch {security_attempt + 1}/{MAX_SECURITY_RETRIES})",
                current_security_model)

            # Neuen Agent mit aktuellem Modell erstellen
            # AENDERUNG 06.02.2026: tech_blueprint fuer Tech-Stack-Kontext
            agent_security = init_agents(
                manager.config,
                project_rules,
                router=manager.model_router,
                include=["security"],
                tech_blueprint=getattr(manager, 'tech_blueprint', None)
            ).get("security")

            task_security_rescan = Task(
                description=security_rescan_prompt,
                expected_output="SECURE oder VULNERABILITY-Liste",
                agent=agent_security
            )

            try:
                security_rescan_result = run_with_heartbeat(
                    func=lambda: str(task_security_rescan.execute_sync()),
                    ui_log_callback=manager._ui_log,
                    agent_name="Security",
                    task_description=f"Security-Scan (Versuch {security_attempt + 1}/{MAX_SECURITY_RETRIES})",
                    heartbeat_interval=15,
                    timeout_seconds=SECURITY_TIMEOUT
                )
                security_rescan_vulns = extract_vulnerabilities(security_rescan_result)
                manager.security_vulnerabilities = security_rescan_vulns

                security_passed = not security_rescan_vulns or all(
                    v.get('severity') == 'low' for v in security_rescan_vulns
                )

                rescan_status = "SECURE" if security_passed else "VULNERABLE"

                manager._ui_log("Security", "SecurityRescanOutput", json.dumps({
                    "vulnerabilities": security_rescan_vulns,
                    "overall_status": rescan_status,
                    "scan_type": "code_scan",
                    "iteration": iteration + 1,
                    "blocking": not security_passed,
                    "model": current_security_model,
                    "timestamp": datetime.now().isoformat()
                }, ensure_ascii=False))

                manager._ui_log("Security", "RescanResult", f"Code-Scan: {rescan_status} ({len(security_rescan_vulns)} Findings)")
                manager._update_worker_status("security", "idle")
                break  # Erfolg - Schleife verlassen

            except Exception as sec_err:
                # ÄNDERUNG 30.01.2026: Retry bei 404/Rate-Limit/Leere Antwort mit Fallback-Modell
                should_retry = (
                    is_rate_limit_error(sec_err) or
                    is_model_unavailable_error(sec_err) or
                    is_empty_response_error(sec_err)
                )
                if should_retry:
                    error_type = "Rate-Limit" if is_rate_limit_error(sec_err) else \
                                 "404/Nicht verfügbar" if is_model_unavailable_error(sec_err) else \
                                 "Leere Antwort"
                    manager._ui_log("Security", "Warning",
                        f"Security-Modell {current_security_model} {error_type} (Versuch {security_attempt + 1}/{MAX_SECURITY_RETRIES})")
                    manager.model_router.mark_rate_limited_sync(current_security_model)
                    if security_attempt < MAX_SECURITY_RETRIES - 1:
                        manager._ui_log("Security", "Info", "Wechsle zu Fallback-Modell...")
                        continue  # Nächster Versuch mit Fallback

                manager._ui_log("Security", "Error", f"Security-Rescan fehlgeschlagen: {sec_err}")
                manager._update_worker_status("security", "idle")
                # Fail-Closed bei Security-Fehlern
                security_passed = False
                break

    return security_passed, security_rescan_vulns
