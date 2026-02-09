# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 02.02.2026
Version: 1.1
Beschreibung: Parallele Datei-Generierung fuer den DevLoop.
              Generiert Dateien parallel basierend auf Dependency-Graph.
              Nutzt asyncio.gather() fuer echte Parallelitaet.
              AENDERUNG 02.02.2026: pytest-Integration (Fix #9) hinzugefuegt
"""

import os
import json
import asyncio
import logging
import threading
from typing import Dict, List, Tuple, Optional, Any, Callable
from concurrent.futures import ThreadPoolExecutor

from .file_dependency_graph import (
    build_dependency_graph,
    get_parallel_batches,
    analyze_parallelization_potential
)
from .dev_loop_helpers import _ensure_test_dependencies, is_forbidden_file

logger = logging.getLogger(__name__)

# Globaler Thread-Pool fuer LLM-Aufrufe (die sind synchron/blockierend)
_executor: Optional[ThreadPoolExecutor] = None
_executor_lock = threading.Lock()


def _get_executor(max_workers: Optional[int] = None) -> ThreadPoolExecutor:
    """
    Gibt den globalen Thread-Pool zurueck oder erstellt einen neuen (thread-sicher).

    Args:
        max_workers: Maximale Anzahl paralleler Threads (None = unbegrenzt)

    Returns:
        ThreadPoolExecutor Instanz
    """
    global _executor
    if _executor is None or _executor._shutdown:
        with _executor_lock:
            if _executor is None or _executor._shutdown:
                workers = max_workers or min(32, max(4, os.cpu_count() or 4))
                _executor = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="parallel_gen_")
                logger.info(f"Thread-Pool erstellt mit {workers} Workern")
    return _executor


async def generate_single_file_async(
    manager,
    filename: str,
    file_description: str,
    existing_files: Dict[str, str],
    user_goal: str,
    project_rules: Dict[str, Any],
    timeout_seconds: int = 300  # AENDERUNG 02.02.2026: Default von 120 auf 300 erhoeht
) -> Tuple[str, Optional[str], Optional[str]]:
    """
    Generiert eine einzelne Datei asynchron.

    Fuehrt den LLM-Aufruf in einem Thread aus (da LLM-Aufrufe blockierend sind).

    Args:
        manager: OrchestrationManager
        filename: Zu generierende Datei
        file_description: Beschreibung der Datei
        existing_files: Bereits generierte Dateien als Kontext
        user_goal: Benutzer-Anforderung
        project_rules: Projekt-Regeln
        timeout_seconds: Timeout pro Datei

    Returns:
        Tuple (filename, content, error) - error ist None bei Erfolg
    """
    from .file_by_file_loop import run_single_file_coder

    # Erstelle Task-Dict fuer run_single_file_coder
    file_task = {
        "path": filename,
        "description": file_description,
        "depends_on": []
    }

    # Fuehre in Thread aus (LLM-Aufruf ist blockierend)
    loop = asyncio.get_event_loop()
    executor = _get_executor()

    try:
        result_path, result_content = await asyncio.wait_for(
            loop.run_in_executor(
                executor,
                lambda: run_single_file_coder(
                    manager,
                    project_rules,
                    file_task,
                    existing_files,
                    user_goal,
                    iteration=0,
                    error_context=None
                )
            ),
            timeout=timeout_seconds
        )

        if result_path and result_content:
            return filename, result_content, None
        else:
            return filename, None, result_content or "Generierung fehlgeschlagen"

    except asyncio.TimeoutError:
        return filename, None, f"Timeout nach {timeout_seconds}s"
    except Exception as e:
        return filename, None, str(e)


async def run_parallel_file_generation(
    manager,
    file_list: List[str],
    file_descriptions: Dict[str, str],
    user_goal: str,
    project_rules: Dict[str, Any],
    max_workers: Optional[int] = None,
    timeout_per_file: int = 300,  # AENDERUNG 02.02.2026: Default von 120 auf 300 erhoeht
    batch_timeout: int = 600  # AENDERUNG 02.02.2026: Default von 300 auf 600 erhoeht
) -> Tuple[Dict[str, str], List[Tuple[str, str]]]:
    """
    Generiert Dateien parallel basierend auf Dependency-Graph.

    Args:
        manager: OrchestrationManager
        file_list: Liste der zu generierenden Dateien
        file_descriptions: Dict mit {filename: description}
        user_goal: Benutzer-Anforderung
        project_rules: Projekt-Regeln
        max_workers: Max. parallele Worker (None = unbegrenzt)
        timeout_per_file: Timeout pro Datei in Sekunden
        batch_timeout: Timeout pro Batch in Sekunden

    Returns:
        Tuple (results_dict, errors_list)
        - results_dict: {filename: content} fuer erfolgreiche Dateien
        - errors_list: [(filename, error)] fuer fehlgeschlagene Dateien
    """
    # Analysiere Parallelisierungs-Potenzial
    tech_stack = manager.tech_blueprint.get("project_type", "python") if manager.tech_blueprint else "python"
    analysis = analyze_parallelization_potential(file_list, tech_stack)

    manager._ui_log("ParallelGen", "Analysis", json.dumps({
        "total_files": analysis["total_files"],
        "total_batches": analysis["total_batches"],
        "max_parallel": analysis["max_parallel_per_batch"],
        "theoretical_speedup": analysis["theoretical_speedup"]
    }, ensure_ascii=False))

    # Baue Dependency-Graph und Batches
    graph = build_dependency_graph(file_list, tech_stack)
    batches = get_parallel_batches(graph)

    results: Dict[str, str] = {}
    errors: List[Tuple[str, str]] = []

    # Verarbeite Batches sequenziell, Dateien im Batch parallel
    for batch_idx, batch in enumerate(batches):
        batch_num = batch_idx + 1
        batch_size = len(batch)

        manager._ui_log("ParallelGen", "BatchStart", json.dumps({
            "batch": batch_num,
            "total_batches": len(batches),
            "files": batch,
            "parallel_count": batch_size
        }, ensure_ascii=False))

        # Erstelle Tasks fuer alle Dateien im Batch
        tasks = []
        for filename in batch:
            description = file_descriptions.get(filename, f"Generiere {filename}")

            task = generate_single_file_async(
                manager=manager,
                filename=filename,
                file_description=description,
                existing_files=results.copy(),  # Kontext aus vorherigen Batches
                user_goal=user_goal,
                project_rules=project_rules,
                timeout_seconds=timeout_per_file
            )
            tasks.append(task)

        # Fuehre alle Tasks im Batch parallel aus
        try:
            batch_results = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=batch_timeout
            )
        except asyncio.TimeoutError:
            manager._ui_log("ParallelGen", "BatchTimeout",
                          f"Batch {batch_num} Timeout nach {batch_timeout}s")
            # Markiere alle Dateien im Batch als fehlgeschlagen
            for filename in batch:
                errors.append((filename, f"Batch-Timeout"))
            continue

        # Verarbeite Batch-Ergebnisse
        for result in batch_results:
            if isinstance(result, Exception):
                # Task hat Exception geworfen
                errors.append(("unknown", str(result)))
                continue

            filename, content, error = result

            if content:
                # AENDERUNG 09.02.2026: Fix 36 — System-Level Blacklist
                if is_forbidden_file(filename):
                    manager._ui_log("ParallelGen", "ForbiddenFileBlocked", filename)
                    continue

                # AENDERUNG 02.02.2026: pytest-Integration fuer Test-Dateien
                # Fix #9: Fuegt pytest zu requirements.txt hinzu wenn Test-Dateien existieren
                if filename.endswith("requirements.txt"):
                    content = _ensure_test_dependencies(content, file_list)

                results[filename] = content

                # Speichere Datei
                full_path = os.path.join(manager.project_path, filename)
                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                with open(full_path, "w", encoding="utf-8") as f:
                    f.write(content)

                manager._ui_log("ParallelGen", "FileComplete", json.dumps({
                    "file": filename,
                    "lines": len(content.split('\n')),
                    "batch": batch_num
                }, ensure_ascii=False))
            else:
                errors.append((filename, error or "Unbekannter Fehler"))
                manager._ui_log("ParallelGen", "FileFailed", json.dumps({
                    "file": filename,
                    "error": error[:100] if error else "Unbekannt",
                    "batch": batch_num
                }, ensure_ascii=False))

        manager._ui_log("ParallelGen", "BatchComplete", json.dumps({
            "batch": batch_num,
            "success_count": sum(1 for r in batch_results if not isinstance(r, Exception) and r[1]),
            "failed_count": sum(1 for r in batch_results if isinstance(r, Exception) or not r[1])
        }, ensure_ascii=False))

    return results, errors


async def run_parallel_fixes(
    manager,
    files_to_fix: List[str],
    fix_instructions: Dict[str, str],
    existing_code: str,
    user_goal: str,
    project_rules: Dict[str, Any],
    max_workers: Optional[int] = None,
    timeout_per_file: int = 300  # AENDERUNG 02.02.2026: Default von 120 auf 300 erhoeht
) -> Tuple[Dict[str, str], List[Tuple[str, str]]]:
    """
    Fuehrt parallele Fixes fuer mehrere Dateien durch.

    Args:
        manager: OrchestrationManager
        files_to_fix: Liste der zu fixenden Dateien
        fix_instructions: Dict mit {filename: fix_instruction}
        existing_code: Der bisherige Code (alle Dateien)
        user_goal: Benutzer-Anforderung
        project_rules: Projekt-Regeln
        max_workers: Max. parallele Worker (None = unbegrenzt)
        timeout_per_file: Timeout pro Datei in Sekunden

    Returns:
        Tuple (results_dict, errors_list)
    """
    import re

    # Extrahiere existierende Dateien aus existing_code
    existing_files: Dict[str, str] = {}
    pattern = r'###\s*FILENAME:\s*(.+?)\s*\n(.*?)(?=###\s*FILENAME:|$)'
    matches = re.findall(pattern, existing_code, re.DOTALL)
    for filepath, content in matches:
        filepath = filepath.strip()
        # ROOT-CAUSE-FIX 06.02.2026: Markdown-Codeblock-Wrapper entfernen
        # Ohne dies bleibt der Sprach-Marker (js, python, etc.) im Content
        clean_content = content.strip()
        clean_content = re.sub(r'^```[a-zA-Z0-9]*\s*\n', '', clean_content)
        clean_content = re.sub(r'\n```\s*$', '', clean_content)
        clean_content = re.sub(r'^```\s*$', '', clean_content, flags=re.MULTILINE)
        existing_files[filepath] = clean_content.strip()

    manager._ui_log("ParallelFix", "Start", json.dumps({
        "files_to_fix": files_to_fix,
        "total": len(files_to_fix)
    }, ensure_ascii=False))

    # Fix-Beschreibungen erstellen
    descriptions = {}
    for filename in files_to_fix:
        fix_instr = fix_instructions.get(filename, "")
        existing_content = existing_files.get(filename, "")

        descriptions[filename] = (
            f"KORRIGIERE diese Datei:\n\n"
            f"BISHERIGER INHALT:\n{existing_content[:1000]}...\n\n"
            f"KORREKTUR-ANWEISUNG:\n{fix_instr}\n\n"
            f"Generiere die VOLLSTAENDIG korrigierte Version."
        )

    # Nutze parallele Generierung
    return await run_parallel_file_generation(
        manager=manager,
        file_list=files_to_fix,
        file_descriptions=descriptions,
        user_goal=user_goal,
        project_rules=project_rules,
        max_workers=max_workers,
        timeout_per_file=timeout_per_file
    )


def get_file_descriptions_from_plan(
    plan: Dict[str, Any]
) -> Dict[str, str]:
    """
    Extrahiert Datei-Beschreibungen aus einem Planner-Plan.

    Args:
        plan: Plan-Dict vom Planner-Agenten

    Returns:
        Dict mit {filepath: description}
    """
    descriptions = {}
    for file_info in plan.get("files", []):
        path = file_info.get("path", "")
        desc = file_info.get("description", f"Generiere {path}")
        if path:
            descriptions[path] = desc
    return descriptions


def get_file_list_from_plan(plan: Dict[str, Any]) -> List[str]:
    """
    Extrahiert Dateiliste aus einem Planner-Plan.

    Args:
        plan: Plan-Dict vom Planner-Agenten

    Returns:
        Liste der Dateipfade
    """
    return [f.get("path", "") for f in plan.get("files", []) if f.get("path")]


# Cleanup beim Modul-Entladen
import atexit

def _cleanup_executor():
    """Beendet den Thread-Pool ordnungsgemaess."""
    global _executor
    if _executor:
        _executor.shutdown(wait=False)
        _executor = None

atexit.register(_cleanup_executor)


# Exportiere Hauptfunktionen
__all__ = [
    "run_parallel_file_generation",
    "run_parallel_fixes",
    "generate_single_file_async",
    "get_file_descriptions_from_plan",
    "get_file_list_from_plan"
]
