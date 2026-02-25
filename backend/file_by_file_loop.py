# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 31.01.2026
Version: 1.2
Beschreibung: File-by-File Code-Generierung zur Vermeidung von Truncation.
              Basiert auf Dart AI Feature-Ableitung Konzept.

              Jede Datei wird einzeln generiert statt alle auf einmal.
              Dies loest das Token-Limit-Problem bei Free-Tier-Modellen.

              AENDERUNG 31.01.2026: Integration von Traceability Manager,
              Documentation Service und Memory Agent.
              AENDERUNG 31.01.2026: Intelligente Retries mit Fehler-Kontext.
"""

import os
import json
import logging
from typing import Dict, Any, List, Tuple, Optional
from crewai import Task, Crew

# AENDERUNG 09.02.2026: Fix 36 — System-Level Blacklist
from backend.dev_loop_helpers import is_forbidden_file

from agents.planner_agent import (
    create_planner,
    create_planning_task,
    parse_planner_output,
    create_default_plan,
    sort_files_by_priority,
    get_ready_files
)
from agents.coder_agent import (
    create_single_file_coder,
    build_single_file_prompt
)
from backend.heartbeat_utils import run_with_heartbeat
from backend.orchestration_helpers import is_rate_limit_error
# AENDERUNG 31.01.2026: Fehleranalyse fuer intelligente Retries
from backend.error_analyzer import ErrorAnalyzer, FileError
# AENDERUNG 02.02.2026: Planner Worker-Status Logging
from backend.orchestration_worker_status import update_worker_status
# AENDERUNG 02.02.2026: Memory-Integration fuer Planner
from agents.memory_core import add_plan_entry

logger = logging.getLogger(__name__)


def _analyze_generation_failure(
    output: str,
    expected_path: str,
    error_message: str = ""
) -> Dict[str, Any]:
    """
    Analysiert WARUM eine Datei-Generierung fehlgeschlagen ist.

    Args:
        output: Der Output des Coders (falls vorhanden)
        expected_path: Der erwartete Dateipfad
        error_message: Die Fehlermeldung

    Returns:
        Dict mit Fehleranalyse fuer gezielten Retry
    """
    analysis = {
        "error_type": "unknown",
        "suggested_fix": "",
        "context_hint": ""
    }

    error_lower = error_message.lower() if error_message else ""
    output_lower = output.lower() if output else ""

    # Truncation erkennen
    if any(kw in error_lower or kw in output_lower for kw in [
        "truncat", "abgeschnitten", "incomplete", "cut off",
        "token limit", "max_tokens", "context length"
    ]):
        analysis["error_type"] = "truncation"
        analysis["suggested_fix"] = "Generiere eine kuerzere Version. Max. 150 Zeilen."
        analysis["context_hint"] = "WICHTIG: Halte den Code so kurz wie moeglich!"

    # Syntax-Fehler im generierten Code
    elif any(kw in error_lower for kw in ["syntax", "parse", "unexpected"]):
        analysis["error_type"] = "syntax"
        analysis["suggested_fix"] = "Pruefe Syntax genau. Achte auf Einrueckung und Klammern."
        analysis["context_hint"] = "Der vorherige Versuch hatte Syntax-Fehler."

    # Import-Probleme
    elif any(kw in error_lower for kw in ["import", "module", "not found"]):
        analysis["error_type"] = "import"
        analysis["suggested_fix"] = "Pruefe Import-Statements. Verwende nur Standardbibliotheken oder bereits definierte Module."
        analysis["context_hint"] = "Der vorherige Versuch hatte Import-Probleme."

    # Kein gueltiger Code extrahiert
    elif "kein gueltiger code" in error_lower or "extrahiert" in error_lower:
        analysis["error_type"] = "format"
        analysis["suggested_fix"] = "Gib den Code im korrekten Format aus: ### FILENAME: {path}"
        analysis["context_hint"] = f"Nutze GENAU dieses Format: ### FILENAME: {expected_path}"

    # Rate-Limit
    elif any(kw in error_lower for kw in ["rate limit", "429", "too many"]):
        analysis["error_type"] = "rate_limit"
        analysis["suggested_fix"] = "Warte kurz und versuche erneut."
        analysis["context_hint"] = ""

    # Timeout
    elif any(kw in error_lower for kw in ["timeout", "timed out"]):
        analysis["error_type"] = "timeout"
        analysis["suggested_fix"] = "Generiere eine einfachere, kuerzere Version."
        analysis["context_hint"] = "Der vorherige Versuch war zu komplex/lang."

    return analysis


def should_use_file_by_file(blueprint: Dict[str, Any], config: Dict[str, Any]) -> bool:
    """
    Entscheidet ob File-by-File Modus verwendet werden soll.

    Kriterien:
    - Komplexe Projekte (mehr als 3 erwartete Dateien)
    - Desktop-Anwendungen (PyQt, Tkinter)
    - Free-Tier Modelle im Einsatz

    Args:
        blueprint: TechStack-Blueprint
        config: Anwendungskonfiguration

    Returns:
        True wenn File-by-File Modus empfohlen
    """
    # Explizit deaktiviert?
    if not config.get("enable_file_by_file_mode", True):
        return False

    project_type = blueprint.get("project_type", "").lower()
    app_type = blueprint.get("app_type", "").lower()

    # Desktop-Apps: IMMER File-by-File (komplex, viele Module)
    if app_type == "desktop" or any(pt in project_type for pt in [
        "pyqt", "tkinter", "pyside", "wxpython", "desktop"
    ]):
        return True

    # Komplexe Web-Apps: File-by-File empfohlen
    if any(pt in project_type for pt in [
        "flask", "fastapi", "django", "express", "react", "vue", "angular"
    ]):
        return True

    # Einfache Projekte: Standard-Modus (alles auf einmal)
    if project_type in ["static_html", "python_script", "python_cli"]:
        return False

    # Default: File-by-File bei unbekannten Typen (sicherer)
    return True


async def run_planner(
    manager,
    project_rules: Dict[str, Any],
    user_goal: str
) -> Dict[str, Any]:
    """
    Fuehrt den Planner-Agenten aus um einen File-Plan zu erstellen.

    Args:
        manager: OrchestrationManager
        project_rules: Projekt-Regeln
        user_goal: Benutzer-Anforderung

    Returns:
        Plan mit files-Liste oder Default-Plan bei Fehler
    """
    manager._ui_log("Planner", "Status", "Erstelle File-by-File Plan...")

    # AENDERUNG 02.02.2026: Worker-Status fuer Planner-Buero senden
    planner_model = manager.model_router.get_model("planner") if manager.model_router else "unknown"
    update_worker_status(
        office_manager=manager.office_manager,
        office="planner",
        worker_status="working",
        task_description="Erstelle File-by-File Plan...",
        model=planner_model,
        on_log=manager._ui_log
    )

    try:
        planner = create_planner(
            manager.config,
            project_rules,
            router=manager.model_router
        )

        # AENDERUNG 20.02.2026: Fix 58a — Schema an Planner durchreichen
        # ROOT-CAUSE-FIX: Planner sah nur blueprint["database"]="sqlite" aber keine
        # Tabellennamen → generierte generischen "todos"-Plan statt echte Tabellen
        task = create_planning_task(
            planner,
            manager.tech_blueprint,
            user_goal,
            database_schema=getattr(manager, 'database_schema', '')
        )

        # AENDERUNG 08.02.2026: Pro-Agent Timeout statt globalem agent_timeout_seconds
        agent_timeouts = manager.config.get("agent_timeouts", {})
        timeout = agent_timeouts.get("planner", 300)

        # AENDERUNG 21.02.2026: Multi-Tier Claude SDK (Sonnet fuer Planner)
        result = None
        try:
            from backend.claude_sdk import run_sdk_with_retry
            sdk_result = run_sdk_with_retry(
                manager, role="planner", prompt=task.description,
                timeout_seconds=timeout,
                agent_display_name="Planner"
            )
            if sdk_result:
                result = sdk_result
        except Exception as sdk_err:
            logger.debug("Claude SDK Planner nicht verfuegbar: %s", sdk_err)

        # Fallback: CrewAI/OpenRouter
        if not result:
            result = run_with_heartbeat(
                func=lambda: str(task.execute_sync()),
                ui_log_callback=manager._ui_log,
                agent_name="Planner",
                task_description="File-Plan erstellen",
                heartbeat_interval=10,
                timeout_seconds=timeout
            )

        plan = parse_planner_output(result)
        if plan and plan.get("files"):
            file_count = len(plan["files"])

            # AENDERUNG 13.02.2026: Features in DB speichern fuer Kanban-Board
            try:
                from backend.feature_tracking_db import get_feature_tracking_db
                _fdb = get_feature_tracking_db()
                _run_id = getattr(manager, '_stats_run_id', None) or getattr(manager, 'run_id', 'unknown')
                _feature_ids = _fdb.create_features_from_plan(_run_id, plan["files"])
                if _feature_ids:
                    manager._ui_log("System", "FeaturesCreated", json.dumps(
                        _fdb.get_stats(_run_id), ensure_ascii=False))
                # Feature-ID-Mapping fuer spaetere Status-Updates (path → feature_id)
                manager._feature_id_map = {}
                for i, f in enumerate(plan["files"]):
                    if i < len(_feature_ids):
                        manager._feature_id_map[f.get("path", "")] = _feature_ids[i]
            except Exception as _fdb_err:
                logger.warning("Feature-Tracking DB: %s", _fdb_err)

            # AENDERUNG 03.02.2026: "Result" zu "PlannerOutput" geaendert
            # Grund: Frontend erwartet COMPLETION_EVENTS fuer Status-Reset auf "Idle"
            manager._ui_log("Planner", "PlannerOutput", json.dumps({
                "status": "success",
                "file_count": file_count,
                "files": [f["path"] for f in plan["files"]]
            }, ensure_ascii=False))

            # AENDERUNG 02.02.2026: Token-Metrics fuer Planner (geschaetzt)
            estimated_tokens = len(result) // 4 if result else 0
            manager._ui_log("Planner", "TokenMetrics", json.dumps({
                "total_tokens": estimated_tokens,
                "total_cost": 0.0,
                "model": planner_model,
                "estimated": True
            }, ensure_ascii=False))

            # AENDERUNG 02.02.2026: Plan in Memory speichern
            try:
                if hasattr(manager, 'memory_path') and manager.memory_path:
                    add_plan_entry(
                        memory_path=manager.memory_path,
                        plan=plan,
                        source="planner"
                    )
            except Exception as mem_err:
                manager._ui_log("Memory", "Warning", f"Plan nicht gespeichert: {mem_err}")

            # Worker-Status: Completed
            update_worker_status(
                office_manager=manager.office_manager,
                office="planner",
                worker_status="completed",
                on_log=manager._ui_log
            )
            return plan

        # Planner hat keinen gueltigen Plan geliefert
        manager._ui_log("Planner", "Warning", "Planner-Output ungueltig, verwende Default-Plan")

    except Exception as e:
        manager._ui_log("Planner", "Error", f"Planner fehlgeschlagen: {e}")

    # Worker-Status: Completed (auch bei Fehler/Fallback)
    update_worker_status(
        office_manager=manager.office_manager,
        office="planner",
        worker_status="completed",
        on_log=manager._ui_log
    )

    # Fallback: Default-Plan
    # AENDERUNG 20.02.2026: Fix 58b — database_schema an Default-Plan durchreichen
    plan = create_default_plan(manager.tech_blueprint, user_goal,
                               database_schema=getattr(manager, 'database_schema', ''))
    manager._ui_log("Planner", "Info", f"Default-Plan mit {len(plan['files'])} Dateien erstellt")

    # AENDERUNG 02.02.2026: Auch Default-Plan in Memory speichern
    try:
        if hasattr(manager, 'memory_path') and manager.memory_path:
            add_plan_entry(
                memory_path=manager.memory_path,
                plan=plan,
                source="default"
            )
    except Exception as mem_err:
        manager._ui_log("Memory", "Warning", f"Default-Plan nicht gespeichert: {mem_err}")

    return plan


def run_single_file_coder(
    manager,
    project_rules: Dict[str, Any],
    file_task: Dict[str, Any],
    existing_files: Dict[str, str],
    user_goal: str,
    iteration: int,
    error_context: Dict[str, Any] = None
) -> Tuple[Optional[str], str]:
    """
    Generiert eine einzelne Datei mit dem Coder-Agenten.

    Args:
        manager: OrchestrationManager
        project_rules: Projekt-Regeln
        file_task: Task aus dem Plan (path, description, etc.)
        existing_files: Bereits erstellte Dateien als Kontext
        user_goal: Benutzer-Anforderung
        iteration: Aktuelle Iteration
        error_context: Optional - Fehlerkontext vom vorherigen Versuch

    Returns:
        Tuple (filepath, content) oder (None, error_message)
    """
    filepath = file_task.get("path", "")
    description = file_task.get("description", "")

    # AENDERUNG 31.01.2026: Fehlerkontext in Beschreibung integrieren
    if error_context and error_context.get("context_hint"):
        description = f"{description}\n\nHINWEIS VOM VORHERIGEN VERSUCH:\n{error_context['context_hint']}"
        if error_context.get("suggested_fix"):
            description += f"\nEMPFEHLUNG: {error_context['suggested_fix']}"

    manager._ui_log("Coder", "SingleFile", json.dumps({
        "action": "start",
        "file": filepath,
        "description": description,
        "iteration": iteration
    }, ensure_ascii=False))

    # Baue Prompt mit Kontext
    # AENDERUNG 20.02.2026: Fix 58g — Schema an Einzeldatei-Coder durchreichen
    prompt = build_single_file_prompt(
        filepath,
        description,
        manager.tech_blueprint,
        existing_files,
        user_goal,
        database_schema=getattr(manager, 'database_schema', '')
    )

    # AENDERUNG 08.02.2026: Pro-Agent Timeout statt globalem agent_timeout_seconds
    agent_timeouts = manager.config.get("agent_timeouts", {})
    timeout = agent_timeouts.get("coder", 750)

    # AENDERUNG 25.02.2026: Fix 81b — role="coder" statt "fix" (Haiku fuer Erstgenerierung)
    # ROOT-CAUSE-FIX:
    # Symptom: File-by-File nutzt Sonnet statt Haiku → 197 "Leere Antwort" Rate-Limit Fehler
    # Ursache: role="fix" referenziert seit Fix 80 Sonnet statt Haiku
    # Loesung: role="coder" verweist korrekt auf Haiku (konfiguriert in config.yaml)
    try:
        from backend.claude_sdk import run_sdk_with_retry
        sdk_result = run_sdk_with_retry(
            manager, role="coder", prompt=prompt,
            timeout_seconds=timeout,
            agent_display_name="Coder"
        )
        if sdk_result:
            content = _extract_file_content(sdk_result, filepath)
            if content:
                manager._ui_log("Coder", "SingleFile", json.dumps({
                    "action": "complete",
                    "file": filepath,
                    "lines": len(content.split('\n')),
                    "provider": "claude-sdk"
                }, ensure_ascii=False))
                return filepath, content
    except Exception as sdk_err:
        logger.debug("Claude SDK fuer %s nicht verfuegbar: %s", filepath, sdk_err)

    # Fallback: Bestehender OpenRouter/CrewAI Pfad
    try:
        coder = create_single_file_coder(
            manager.config,
            project_rules,
            router=manager.model_router,
            target_file=filepath,
            file_description=description
        )

        task = Task(
            description=prompt,
            expected_output=f"Code fuer {filepath}",
            agent=coder
        )

        result = run_with_heartbeat(
            func=lambda: str(task.execute_sync()),
            ui_log_callback=manager._ui_log,
            agent_name="Coder",
            task_description=f"Generiere {filepath}",
            heartbeat_interval=10,
            timeout_seconds=timeout
        )

        content = _extract_file_content(result, filepath)
        if content:
            manager._ui_log("Coder", "SingleFile", json.dumps({
                "action": "complete",
                "file": filepath,
                "lines": len(content.split('\n'))
            }, ensure_ascii=False))
            return filepath, content

        return None, f"Kein gueltiger Code fuer {filepath} extrahiert"

    except Exception as e:
        error_msg = str(e)
        if is_rate_limit_error(e):
            manager.model_router.mark_rate_limited_sync(
                manager.model_router.get_model("coder")
            )
        manager._ui_log("Coder", "Error", f"Fehler bei {filepath}: {error_msg}")
        return None, error_msg


def _strip_markdown_wrapper(code: str) -> str:
    """
    Entfernt Markdown-Codeblock-Wrapper (```language ... ```) aus dem Code.

    Args:
        code: Code der moeglicherweise Markdown-Wrapper enthaelt

    Returns:
        Bereinigter Code ohne Markdown-Backticks
    """
    if not code:
        return code

    code = code.strip()

    # AENDERUNG 31.01.2026: Robustere Markdown-Bereinigung
    # Pattern: Code beginnt mit ```<optional_language> und endet mit ```
    if code.startswith('```'):
        lines = code.split('\n')
        # Erste Zeile entfernen (```javascript, ```python, etc.)
        if len(lines) > 1:
            lines = lines[1:]
        # Letzte Zeile entfernen wenn sie nur ``` ist
        if lines and lines[-1].strip() == '```':
            lines = lines[:-1]
        code = '\n'.join(lines)

    return code.strip()


def _extract_file_content(output: str, expected_path: str) -> Optional[str]:
    """
    Extrahiert den Dateiinhalt aus dem Coder-Output.

    Args:
        output: Raw-Output des Coders
        expected_path: Erwarteter Dateipfad

    Returns:
        Extrahierter Code oder None
    """
    import re

    if not output:
        return None

    # Pattern: ### FILENAME: path\ncode
    pattern = rf'###\s*FILENAME:\s*{re.escape(expected_path)}\s*\n(.*?)(?=###\s*FILENAME:|$)'
    matches = re.findall(pattern, output, re.DOTALL | re.IGNORECASE)
    if matches:
        # AENDERUNG 31.01.2026: Markdown-Wrapper IMMER entfernen
        return _strip_markdown_wrapper(matches[0])

    # Fallback: Suche nach dem Pfad-Fragment
    filename = os.path.basename(expected_path)
    pattern = rf'###\s*FILENAME:.*?{re.escape(filename)}\s*\n(.*?)(?=###\s*FILENAME:|$)'
    matches = re.findall(pattern, output, re.DOTALL | re.IGNORECASE)
    if matches:
        # AENDERUNG 31.01.2026: Markdown-Wrapper IMMER entfernen
        return _strip_markdown_wrapper(matches[0])

    # Letzter Fallback: Nimm den gesamten Output (abzueglich Markdown-Bloecke)
    code = _strip_markdown_wrapper(output)

    if len(code) > 10:  # Mindestlaenge
        return code

    return None


async def run_file_by_file_loop(
    manager,
    project_rules: Dict[str, Any],
    user_goal: str,
    max_iterations: int = 3
) -> Tuple[bool, str, List[str]]:
    """
    Hauptfunktion: Fuehrt File-by-File Code-Generierung durch.

    Args:
        manager: OrchestrationManager
        project_rules: Projekt-Regeln
        user_goal: Benutzer-Anforderung
        max_iterations: Max. Versuche pro Datei

    Returns:
        Tuple (success, message, created_files)
    """
    manager._ui_log("FileByFile", "Start", "File-by-File Modus aktiviert")

    # 1. Plan erstellen
    plan = await run_planner(manager, project_rules, user_goal)
    sorted_files = sort_files_by_priority(plan)

    manager._ui_log("FileByFile", "Plan", json.dumps({
        "total_files": len(sorted_files),
        "order": [f["path"] for f in sorted_files]
    }, ensure_ascii=False))

    # 2. Dateien erstellen
    completed_files: List[str] = []
    existing_content: Dict[str, str] = {}
    failed_files: List[str] = []

    # AENDERUNG 13.02.2026: Feature-DB Referenz fuer Status-Updates
    _fdb_ref = None
    _fdb_run_id = None
    try:
        from backend.feature_tracking_db import get_feature_tracking_db
        _fdb_ref = get_feature_tracking_db()
        _fdb_run_id = getattr(manager, '_stats_run_id', None) or getattr(manager, 'run_id', 'unknown')
    except Exception:
        pass
    _fid_map = getattr(manager, '_feature_id_map', {})

    for file_task in sorted_files:
        filepath = file_task["path"]

        # AENDERUNG 13.02.2026: Feature-Status auf "in_progress" setzen
        _fid = _fid_map.get(filepath)
        if _fid and _fdb_ref:
            try:
                _fdb_ref.update_status(_fid, "in_progress", agent="Coder")
                manager._ui_log("System", "FeatureUpdate", json.dumps({
                    "id": _fid, "status": "in_progress", "file_path": filepath
                }, ensure_ascii=False))
            except Exception:
                pass

        # Pruefe Abhaengigkeiten
        depends = file_task.get("depends_on", [])
        unmet = [d for d in depends if d not in completed_files]
        if unmet:
            manager._ui_log("FileByFile", "Warning",
                           f"Abhaengigkeiten fuer {filepath} nicht erfuellt: {unmet}")
            # Trotzdem versuchen, aber mit Warnung

        # Generiere Datei (mit intelligentem Retry)
        success = False
        error_context = None  # Fehlerkontext fuer naechsten Versuch
        last_output = ""
        last_error = ""

        for attempt in range(max_iterations):
            result_path, result = run_single_file_coder(
                manager,
                project_rules,
                file_task,
                existing_content,
                user_goal,
                attempt,
                error_context=error_context  # AENDERUNG 31.01.2026: Fehlerkontext mitgeben
            )

            if result_path:
                # AENDERUNG 09.02.2026: Fix 36 — System-Level Blacklist
                if is_forbidden_file(filepath):
                    manager._ui_log("FileByFile", "ForbiddenFileBlocked", filepath)
                    break  # Naechste Datei in der aeusseren Schleife
                # Speichere Datei
                full_path = os.path.join(manager.project_path, filepath)
                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                with open(full_path, "w", encoding="utf-8") as f:
                    f.write(result)

                completed_files.append(filepath)
                existing_content[filepath] = result
                success = True

                # AENDERUNG 13.02.2026: Feature-Status auf "done" setzen
                if _fid and _fdb_ref:
                    try:
                        _fdb_ref.mark_done(_fid, actual_lines=len(result.splitlines()))
                        manager._ui_log("System", "FeatureUpdate", json.dumps({
                            "id": _fid, "status": "done", "file_path": filepath
                        }, ensure_ascii=False))
                    except Exception:
                        pass
                break

            # AENDERUNG 31.01.2026: Analysiere Fehler fuer gezielten Retry
            last_output = result if isinstance(result, str) else ""
            last_error = result if not result_path else ""

            error_context = _analyze_generation_failure(
                output=last_output,
                expected_path=filepath,
                error_message=last_error
            )

            manager._ui_log("FileByFile", "Retry", json.dumps({
                "attempt": attempt + 1,
                "max": max_iterations,
                "file": filepath,
                "error_type": error_context.get("error_type", "unknown"),
                "hint": error_context.get("suggested_fix", "")
            }, ensure_ascii=False))

        if not success:
            failed_files.append(filepath)
            manager._ui_log("FileByFile", "Error",
                           f"Datei {filepath} konnte nicht erstellt werden")
            # AENDERUNG 13.02.2026: Feature-Status auf "failed" setzen
            if _fid and _fdb_ref:
                try:
                    _fdb_ref.mark_failed(_fid, f"Generierung fehlgeschlagen nach {max_iterations} Versuchen")
                except Exception:
                    pass

    # 3. Integration: Traceability, Documentation, Memory
    await _integrate_file_by_file_results(
        manager, plan, completed_files, failed_files, existing_content
    )

    # AENDERUNG 02.02.2026: Fix #9 - Automatisch pytest hinzufuegen wenn Tests existieren
    # Verhindert "No module named pytest" Fehler in Docker-Tests
    from backend.dev_loop_helpers import _ensure_test_dependencies

    req_path = os.path.join(manager.project_path, "requirements.txt")
    if os.path.exists(req_path):
        with open(req_path, "r", encoding="utf-8") as f:
            req_content = f.read()

        updated_req = _ensure_test_dependencies(req_content, completed_files)
        if updated_req != req_content:
            with open(req_path, "w", encoding="utf-8") as f:
                f.write(updated_req)
            manager._ui_log("FileByFile", "AutoFix", "pytest zu requirements.txt hinzugefuegt")

    # 4. Ergebnis
    total = len(sorted_files)
    created = len(completed_files)
    failed = len(failed_files)

    if failed == 0:
        return True, f"Alle {created} Dateien erfolgreich erstellt", completed_files
    elif created > 0:
        return True, f"{created}/{total} Dateien erstellt, {failed} fehlgeschlagen", completed_files
    else:
        return False, f"Keine Dateien erstellt ({failed} Fehler)", []


async def _integrate_file_by_file_results(
    manager,
    plan: Dict[str, Any],
    completed_files: List[str],
    failed_files: List[str],
    file_contents: Dict[str, str]
) -> None:
    """
    Integriert die File-by-File Ergebnisse in Traceability, Documentation und Memory.

    Args:
        manager: OrchestrationManager
        plan: Der File-by-File Plan
        completed_files: Erfolgreich erstellte Dateien
        failed_files: Fehlgeschlagene Dateien
        file_contents: Inhalt der erstellten Dateien
    """
    success = len(failed_files) == 0

    # 1. Documentation Service Integration
    try:
        if hasattr(manager, 'doc_service') and manager.doc_service:
            manager.doc_service.collect_file_by_file_plan(plan)

            for filepath in completed_files:
                content = file_contents.get(filepath, "")
                lines = len(content.split('\n')) if content else 0
                manager.doc_service.collect_file_generation_result(
                    filepath=filepath,
                    success=True,
                    lines=lines
                )

            for filepath in failed_files:
                manager.doc_service.collect_file_generation_result(
                    filepath=filepath,
                    success=False,
                    error="Generierung fehlgeschlagen"
                )

            manager._ui_log("Documentation", "Info",
                           f"File-by-File Ergebnisse dokumentiert")
    except Exception as e:
        logger.warning(f"Documentation Service Integration fehlgeschlagen: {e}")

    # 2. Traceability Manager Integration
    try:
        from backend.traceability_manager import TraceabilityManager

        traceability = TraceabilityManager(manager.project_path)

        # Tasks aus Plan hinzufuegen
        for i, file_info in enumerate(plan.get("files", []), 1):
            task_id = f"TASK-{i:03d}"
            traceability.add_task(
                id=task_id,
                titel=file_info.get("description", f"Erstelle {file_info.get('path', '?')}"),
                features=[],  # Features werden spaeter verknuepft
                datei=file_info.get("path"),
                status="pending"
            )

        # Dateien hinzufuegen und Status aktualisieren
        for i, filepath in enumerate(completed_files, 1):
            task_id = f"TASK-{i:03d}"
            content = file_contents.get(filepath, "")
            lines = len(content.split('\n')) if content else 0

            traceability.add_datei(
                pfad=filepath,
                tasks=[task_id],
                status="completed",
                lines=lines
            )
            traceability.update_task_status(task_id, "completed")

        for filepath in failed_files:
            # Finde passenden Task
            for i, file_info in enumerate(plan.get("files", []), 1):
                if file_info.get("path") == filepath:
                    traceability.update_task_status(f"TASK-{i:03d}", "failed")
                    break

        traceability.save()
        manager._ui_log("Traceability", "Info",
                       f"Matrix aktualisiert: {len(completed_files)} Dateien")

        # Traceability Report in Documentation Service
        if hasattr(manager, 'doc_service') and manager.doc_service:
            manager.doc_service.collect_traceability_matrix(traceability.get_matrix())

    except Exception as e:
        logger.warning(f"Traceability Manager Integration fehlgeschlagen: {e}")

    # 3. Memory Agent Integration
    try:
        from agents.memory_agent import record_file_by_file_session_async

        memory_path = os.path.join(manager.base_dir, "memory", "global_memory.json")
        result = await record_file_by_file_session_async(
            memory_path=memory_path,
            plan=plan,
            created_files=completed_files,
            failed_files=failed_files,
            success=success
        )
        manager._ui_log("Memory", "Info", result)
    except Exception as e:
        logger.warning(f"Memory Agent Integration fehlgeschlagen: {e}")


# AENDERUNG 01.02.2026: Truncation Recovery - File-by-File Reparatur
async def run_file_by_file_repair(
    manager,
    project_rules: Dict[str, Any],
    truncated_files: List[Tuple[str, str]],
    existing_code: str,
    user_goal: str,
    max_iterations: int = 3
) -> Tuple[bool, str, Dict[str, str]]:
    """
    Repariert abgeschnittene Dateien im File-by-File Modus.

    Diese Funktion wird aufgerufen wenn bei Fix-Iterationen Truncation erkannt wurde.
    Sie generiert nur die betroffenen Dateien einzeln neu.

    Args:
        manager: OrchestrationManager
        project_rules: Projekt-Regeln
        truncated_files: Liste von (filepath, error) Tuples
        existing_code: Der bisherige Code (alle Dateien)
        user_goal: Benutzer-Anforderung
        max_iterations: Max. Versuche pro Datei

    Returns:
        Tuple (success, message, repaired_content_dict)
    """
    manager._ui_log("FileByFile", "RepairStart", json.dumps({
        "mode": "truncation_recovery",
        "files_to_repair": [f[0] for f in truncated_files]
    }, ensure_ascii=False))

    # Extrahiere existierende Dateien aus existing_code
    existing_files: Dict[str, str] = {}
    import re
    pattern = r'###\s*FILENAME:\s*(.+?)\s*\n(.*?)(?=###\s*FILENAME:|$)'
    matches = re.findall(pattern, existing_code, re.DOTALL)
    for filepath, content in matches:
        filepath = filepath.strip()
        # Nur nicht-abgeschnittene Dateien behalten
        is_truncated = any(tf[0] == filepath for tf in truncated_files)
        if not is_truncated:
            existing_files[filepath] = content.strip()

    repaired_content: Dict[str, str] = {}
    failed_repairs: List[str] = []

    for filepath, error_msg in truncated_files:
        manager._ui_log("FileByFile", "RepairFile", json.dumps({
            "file": filepath,
            "reason": "truncation"
        }, ensure_ascii=False))

        # Erstelle Task fuer diese Datei
        file_task = {
            "path": filepath,
            "description": f"Repariere abgeschnittene Datei. Die vorherige Version war unvollstaendig. "
                          f"Generiere eine VOLLSTAENDIGE, syntaktisch korrekte Version. "
                          f"WICHTIG: Halte den Code kompakt (max. 100 Zeilen wenn moeglich).",
            "depends_on": []
        }

        # Fehlerkontext fuer intelligenten Retry
        error_context = {
            "error_type": "truncation",
            "suggested_fix": "Generiere eine kuerzere, kompaktere Version der Datei.",
            "context_hint": f"Die vorherige Version wurde abgeschnitten: {error_msg[:100]}..."
        }

        success = False
        for attempt in range(max_iterations):
            result_path, result = run_single_file_coder(
                manager,
                project_rules,
                file_task,
                existing_files,
                user_goal,
                attempt,
                error_context=error_context
            )

            if result_path and result:
                # Validiere: Keine offenen Klammern/Bloecke
                if _validate_file_complete(result, filepath):
                    repaired_content[filepath] = result
                    existing_files[filepath] = result  # Fuer naechste Dateien
                    success = True

                    # Speichere reparierte Datei
                    full_path = os.path.join(manager.project_path, filepath)
                    os.makedirs(os.path.dirname(full_path), exist_ok=True)
                    with open(full_path, "w", encoding="utf-8") as f:
                        f.write(result)

                    manager._ui_log("FileByFile", "RepairSuccess", json.dumps({
                        "file": filepath,
                        "lines": len(result.split('\n')),
                        "attempt": attempt + 1
                    }, ensure_ascii=False))
                    break
                else:
                    error_context["context_hint"] = "Die Datei hat noch offene Klammern/Bloecke. Stelle sicher dass alle geschlossen sind."
                    manager._ui_log("FileByFile", "RepairIncomplete",
                                   f"{filepath} noch unvollstaendig, Versuch {attempt + 2}")
            else:
                error_context["context_hint"] = f"Generierung fehlgeschlagen. {error_context.get('suggested_fix', '')}"

        if not success:
            failed_repairs.append(filepath)
            manager._ui_log("FileByFile", "RepairFailed",
                           f"Reparatur von {filepath} fehlgeschlagen nach {max_iterations} Versuchen")

    # Ergebnis
    total = len(truncated_files)
    repaired = len(repaired_content)
    failed = len(failed_repairs)

    if failed == 0:
        return True, f"Alle {repaired} Dateien erfolgreich repariert", repaired_content
    elif repaired > 0:
        return True, f"{repaired}/{total} Dateien repariert, {failed} fehlgeschlagen", repaired_content
    else:
        return False, f"Keine Dateien repariert ({failed} Fehler)", {}


def _validate_file_complete(content: str, filepath: str) -> bool:
    """
    Validiert ob eine Datei vollstaendig ist (keine offenen Klammern/Bloecke).

    Args:
        content: Dateiinhalt
        filepath: Dateipfad (fuer Typ-Erkennung)

    Returns:
        True wenn Datei vollstaendig erscheint
    """
    if not content or not content.strip():
        return False

    ext = os.path.splitext(filepath)[1].lower()

    # Python-Dateien: Keine offenen Klammern
    if ext == '.py':
        open_parens = content.count('(') - content.count(')')
        open_brackets = content.count('[') - content.count(']')
        open_braces = content.count('{') - content.count('}')
        if open_parens != 0 or open_brackets != 0 or open_braces != 0:
            return False

    # JavaScript/TypeScript: Klammern pruefen
    elif ext in ['.js', '.jsx', '.ts', '.tsx']:
        open_braces = content.count('{') - content.count('}')
        open_parens = content.count('(') - content.count(')')
        if open_braces != 0 or open_parens != 0:
            return False

    # HTML: Tags pruefen (einfach) – Fragmente ohne </html>/</body> werden akzeptiert
    elif ext in ['.html', '.htm']:
        pass

    # CSS: Geschweifte Klammern pruefen
    elif ext == '.css':
        open_braces = content.count('{') - content.count('}')
        if open_braces != 0:
            return False

    return True


def merge_repaired_files(existing_code: str, repaired_content: Dict[str, str]) -> str:
    """
    Merged reparierte Dateien in den existierenden Code.

    Ersetzt die abgeschnittenen Versionen durch die reparierten Versionen.

    Args:
        existing_code: Der bisherige Code (alle Dateien)
        repaired_content: Dict mit {filepath: repaired_content}

    Returns:
        Aktualisierter Code mit reparierten Dateien
    """
    import re

    result = existing_code

    for filepath, new_content in repaired_content.items():
        # Pattern: ### FILENAME: filepath\n...content...(bis zum naechsten ### FILENAME oder Ende)
        pattern = rf'(###\s*FILENAME:\s*{re.escape(filepath)}\s*\n).*?(?=###\s*FILENAME:|$)'

        # Ersetze mit neuer Version
        replacement = f"### FILENAME: {filepath}\n{new_content}\n"

        new_result = re.sub(pattern, replacement, result, flags=re.DOTALL)

        if new_result == result:
            # Datei war nicht im Code - anhaengen
            result = result.rstrip() + f"\n\n### FILENAME: {filepath}\n{new_content}\n"
        else:
            result = new_result

    return result

