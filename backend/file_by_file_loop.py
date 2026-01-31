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

    try:
        planner = create_planner(
            manager.config,
            project_rules,
            router=manager.model_router
        )

        task = create_planning_task(
            planner,
            manager.tech_blueprint,
            user_goal
        )

        # Fuehre Planner mit Heartbeat aus
        timeout = manager.config.get("agent_timeout_seconds", 120)
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
            manager._ui_log("Planner", "Result", json.dumps({
                "status": "success",
                "file_count": file_count,
                "files": [f["path"] for f in plan["files"]]
            }, ensure_ascii=False))
            return plan

        # Planner hat keinen gueltigen Plan geliefert
        manager._ui_log("Planner", "Warning", "Planner-Output ungueltig, verwende Default-Plan")

    except Exception as e:
        manager._ui_log("Planner", "Error", f"Planner fehlgeschlagen: {e}")

    # Fallback: Default-Plan
    plan = create_default_plan(manager.tech_blueprint, user_goal)
    manager._ui_log("Planner", "Info", f"Default-Plan mit {len(plan['files'])} Dateien erstellt")
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

    try:
        # Erstelle Single-File Coder
        coder = create_single_file_coder(
            manager.config,
            project_rules,
            router=manager.model_router,
            target_file=filepath,
            file_description=description
        )

        # Baue Prompt mit Kontext
        prompt = build_single_file_prompt(
            filepath,
            description,
            manager.tech_blueprint,
            existing_files,
            user_goal
        )

        task = Task(
            description=prompt,
            expected_output=f"Code fuer {filepath}",
            agent=coder
        )

        # Fuehre mit Heartbeat aus
        timeout = manager.config.get("agent_timeout_seconds", 120)
        result = run_with_heartbeat(
            func=lambda: str(task.execute_sync()),
            ui_log_callback=manager._ui_log,
            agent_name="Coder",
            task_description=f"Generiere {filepath}",
            heartbeat_interval=10,
            timeout_seconds=timeout
        )

        # Extrahiere Code aus Result
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

    for file_task in sorted_files:
        filepath = file_task["path"]

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
                # Speichere Datei
                full_path = os.path.join(manager.project_path, filepath)
                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                with open(full_path, "w", encoding="utf-8") as f:
                    f.write(result)

                completed_files.append(filepath)
                existing_content[filepath] = result
                success = True
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

    # 3. Integration: Traceability, Documentation, Memory
    await _integrate_file_by_file_results(
        manager, plan, completed_files, failed_files, existing_content
    )

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
