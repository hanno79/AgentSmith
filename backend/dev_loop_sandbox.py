# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 08.02.2026
Version: 1.0
Beschreibung: Sandbox- und Test-Validierungen fuer DevLoop.
              Extrahiert aus dev_loop_validators.py (Regel 1: Max 500 Zeilen)
              Enthaelt: _is_harmless_warning_only, _run_content_validators, run_sandbox_and_tests
              AENDERUNG 08.02.2026: Modul-Extraktion aus dev_loop_validators.py
"""

import os
import json
import base64
import logging
from datetime import datetime
from typing import Dict, Any, List, Tuple
from concurrent.futures import ThreadPoolExecutor

from agents.memory_agent import (
    extract_error_pattern,
    generate_tags_from_context,
    learn_from_error
)
from backend.docker_executor import create_docker_executor
from unit_test_runner import run_unit_tests
from agents.tester_agent import test_project, summarize_ui_result
from content_validator import (
    validate_run_bat,
    validate_nextjs_structure,
    validate_import_dependencies,
    validate_template_structure,
    validate_no_inline_svg,
    validate_no_pages_router,
    validate_no_better_sqlite3
)
from .dev_loop_helpers import run_sandbox_for_project
from .dev_loop_test_utils import ensure_tests_exist
from .pre_docker_validator import validate_before_docker

logger = logging.getLogger(__name__)


# AENDERUNG 08.02.2026: Konsolidierte Content-Validierung (DRY, Regel 13)
# Tuples: (validator_fn, issue_label, issue_prefix, warn_label, warn_prefix, issues_set_failed)
_CONTENT_VALIDATORS = [
    (validate_template_structure, "TemplateStruktur", "Template-Strukturfehler", None, None, True),
    (validate_nextjs_structure, "NextJsStruktur", "Next.js-Strukturfehler", "NextJsInfo", None, True),
    (validate_import_dependencies, "FehlendeDeps", "Dependency-Fehler", None, None, True),
    (validate_no_inline_svg, None, None, "InlineSVG", "Inline-SVG WARNING", False),
    (validate_no_pages_router, None, None, "RouterConflict", "Router WARNING", False),
    (validate_no_better_sqlite3, None, None, "ForbiddenLibrary", "Library WARNING", False),
]


def _run_content_validators(manager, sandbox_result: str, sandbox_failed: bool) -> Tuple[str, bool]:
    """
    Fuehrt alle Content-Validierungen aus (Template, NextJS, Deps, SVG, Router, Libs).
    Gibt aktualisierte (sandbox_result, sandbox_failed) zurueck.
    AENDERUNG 08.02.2026: Konsolidiert 6 try-except-Bloecke (Regel 13: DRY).
    """
    for fn, issue_label, issue_prefix, warn_label, warn_prefix, issues_fail in _CONTENT_VALIDATORS:
        try:
            result = fn(manager.project_path, manager.tech_blueprint)
            if issue_label and hasattr(result, 'issues') and result.issues:
                for issue in result.issues:
                    manager._ui_log("Sandbox", issue_label, issue)
                    sandbox_result += f"\n{issue_prefix}: {issue}"
                    if issues_fail:
                        sandbox_failed = True
            if warn_label and hasattr(result, 'warnings') and result.warnings:
                for warning in result.warnings:
                    manager._ui_log("Sandbox", warn_label, warning)
                    if warn_prefix:
                        sandbox_result += f"\n{warn_prefix}: {warning}"
        except Exception as val_err:
            label = issue_label or warn_label
            manager._ui_log("Sandbox", "Warning", f"{label}-Validierung fehlgeschlagen: {val_err}")
    return sandbox_result, sandbox_failed


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
    AENDERUNG 31.01.2026: Projekt-Typ-aware Sandbox-Check - keine JS-Checks bei Python-Projekten.
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
            # AENDERUNG 10.02.2026: Fix 50 - Persistenten Container bevorzugen
            container = getattr(manager, '_docker_container', None)
            _using_persistent_container = False

            if container and container.is_healthy():
                manager._ui_log("Docker", "Status",
                    "Persistenter Docker-Container aktiv (Fix 50)")
                _using_persistent_container = True
                # Install + Test via exec im bestehenden Container
                manager._ui_log("Docker", "Info",
                    "Installiere Dependencies im persistenten Container...")
                install_result = container.install_deps()
                if install_result.success or _is_harmless_warning_only(
                        install_result.stderr, install_result.stdout):
                    manager._ui_log("Docker", "Info", "Fuehre Tests im Container aus...")
                    test_result = container.run_tests()
                    # Konvertiere zu DockerResult-kompatiblem Format
                    combined_result = type('DockerResult', (), {
                        'success': test_result.success or _is_harmless_warning_only(
                            test_result.stderr, test_result.stdout),
                        'stdout': install_result.stdout + "\n" + test_result.stdout,
                        'stderr': install_result.stderr + "\n" + test_result.stderr,
                        'duration_seconds': install_result.duration_seconds + test_result.duration_seconds
                    })()
                else:
                    combined_result = install_result
            else:
                # Fallback: Einmal-Container (bestehende Logik)
                executor = create_docker_executor(
                    project_path=manager.project_path,
                    tech_blueprint=manager.tech_blueprint,
                    docker_config=docker_config
                )

                if not executor.is_docker_available():
                    raise RuntimeError("Docker nicht verfuegbar")

                manager._ui_log("Docker", "Status", "Docker-Isolation aktiviert (Einmal-Container)")

                # AENDERUNG 01.02.2026: Install + Test in EINEM Container
                # Vorher: getrennte Aufrufe fuehrten zu "No module named pytest"
                manager._ui_log("Docker", "Info", "Installiere Dependencies und fuehre Tests aus...")
                combined_result = executor.install_and_test()

            # Ab hier: combined_result aus BEIDEN Pfaden (persistent ODER Einmal-Container)
            if combined_result.success:
                manager._ui_log("Docker", "Result",
                    f"Docker Install+Test erfolgreich in {combined_result.duration_seconds:.1f}s")
                docker_ran_and_succeeded = True
            # AENDERUNG 02.02.2026: Harmlose Warnungen (pip root, npm warn) nicht als Fehler behandeln
            elif _is_harmless_warning_only(combined_result.stderr, combined_result.stdout):
                manager._ui_log("Docker", "Info",
                    f"Docker Install+Test OK (mit Warnungen) in {combined_result.duration_seconds:.1f}s")
                docker_ran_and_succeeded = True
            else:
                # AENDERUNG 02.02.2026 v1.4: stdout + stderr kombinieren
                combined_error = ""
                stdout_content = combined_result.stdout.strip()
                stderr_content = combined_result.stderr.strip()

                pytest_section = ""
                if stdout_content:
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
                if executor:
                    try:
                        executor.cleanup()
                    except Exception as cleanup_err:
                        logger.warning("Docker-Cleanup nach Test-Fehler fehlgeschlagen: %s", cleanup_err)
                return (combined_error[:1500], True, docker_fail_result, {"status": "FAIL", "issues": [combined_error[:500]], "screenshot": None}, "Docker-Tests fehlgeschlagen")
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

    # AENDERUNG 31.01.2026: Nutze Projekt-Typ-aware Sandbox statt generischem run_sandbox()
    sandbox_result = run_sandbox_for_project(current_code, manager.tech_blueprint)
    manager._ui_log("Sandbox", "Result", sandbox_result)
    sandbox_failed = sandbox_result.startswith("\u274c")

    try:
        from sandbox_runner import validate_project_references
        ref_result = validate_project_references(manager.project_path)
        if ref_result.startswith("\u274c"):
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

    # AENDERUNG 08.02.2026: Konsolidierte Content-Validierungen (Regel 13: DRY)
    sandbox_result, sandbox_failed = _run_content_validators(manager, sandbox_result, sandbox_failed)

    if sandbox_failed:
        try:
            memory_path = os.path.join(manager.base_dir, "memory", "global_memory.json")
            error_msg = extract_error_pattern(sandbox_result)
            tags = generate_tags_from_context(manager.tech_blueprint, sandbox_result)
            # AENDERUNG 29.01.2026: Non-blocking Memory-Operation fuer WebSocket-Stabilitaet
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
            manager._ui_log("UnitTest", "Status", "Fuehre Unit-Tests durch...")
            manager._update_worker_status("tester", "working", "Unit-Tests...", "pytest/jest")

            # AENDERUNG 30.01.2026: Stelle sicher dass Tests existieren bevor wir sie ausfuehren
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
            sandbox_result += f"\n\n\u274c UNIT-TESTS FEHLGESCHLAGEN:\n{unit_test_result.get('summary', '')}"
            if unit_test_result.get("details"):
                sandbox_result += f"\n{unit_test_result.get('details', '')[:1000]}"
    except ImportError:
        manager._ui_log("UnitTest", "Warning", "unit_test_runner.py nicht gefunden - uebersprungen")
    except Exception as ut_err:
        manager._ui_log("UnitTest", "Error", f"Unit-Test Fehler: {ut_err}")

    test_summary = "Keine UI-Tests durchgefuehrt."
    manager._ui_log("Tester", "Status", f"Starte Tests fuer Projekt-Typ '{project_type}'...")
    manager._update_worker_status("tester", "working", f"Teste {project_type}...", manager.model_router.get_model("tester") if manager.model_router else "")
    ui_result = {"status": "SKIP", "issues": [], "screenshot": None}
    # AENDERUNG 10.02.2026: Fix 43 - Docker-Erfolg ueberspringt UI-Tests NICHT MEHR
    # bei Server-Projekten. Docker prueft nur npm install + npm test, NICHT ob
    # die App tatsaechlich im Browser startet und funktioniert.
    # ROOT-CAUSE-FIX:
    # Symptom: Projekte werden als "Success" deklariert obwohl sie nicht starten
    # Ursache: docker_ran_and_succeeded skippt test_project() komplett
    # Loesung: UI-Tests IMMER ausfuehren wenn Projekt einen Server braucht
    _needs_server_test = False
    if docker_ran_and_succeeded:
        try:
            from server_runner import requires_server
            _needs_server_test = requires_server(manager.tech_blueprint)
        except ImportError:
            pass
        if not _needs_server_test:
            ui_result = {"status": "OK", "issues": [], "screenshot": None}
            test_summary = "Docker-Tests erfolgreich - kein Server noetig."
        else:
            manager._ui_log("Tester", "Info",
                "Docker OK - fuehre trotzdem Server+Browser-Test durch")

    # UI-Test immer ausfuehren AUSSER bei Nicht-Server-Projekten mit Docker-Erfolg
    skip_ui_test = docker_ran_and_succeeded and not _needs_server_test
    try:
        if not skip_ui_test:
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
                # AENDERUNG 29.01.2026: Non-blocking Memory-Operation fuer WebSocket-Stabilitaet
                with ThreadPoolExecutor(max_workers=1) as mem_executor:
                    future = mem_executor.submit(learn_from_error, memory_path, error_msg, tags)
                    learn_result = future.result(timeout=5)  # Max 5s warten
                manager._ui_log("Memory", "Learning", f"Test: {learn_result}")
            except Exception as mem_err:
                manager._ui_log("Memory", "Error", f"Memory-Operation fehlgeschlagen: {mem_err}")
    except Exception as te:
        test_summary = f"\u274c Test-Runner Fehler: {te}"
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
