# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 10.02.2026
Version: 1.1
Beschreibung: Paralleler PatchMode - verteilt Datei-Fixes auf mehrere Coder-Worker.
              Loest das Problem dass EIN Coder-Call fuer ALLE betroffenen Dateien
              den max_tokens Output-Limit ueberschreitet und abgeschnittene Dateien produziert.

AENDERUNG 10.02.2026: Fix 48 - Neue Datei
AENDERUNG 13.02.2026: Fix 53 - Eigener Gruppen-Timeout, Modell-Rotation,
  gestaffelte Ausfuehrung (max_concurrent_groups), dynamische Gruppengroesse
ROOT-CAUSE-FIX:
  Symptom: Dateien werden abgeschnitten (`import { cl;` statt vollstaendiger Import)
  Ursache: EIN LLM-Call muss ALLE betroffenen Dateien ausgeben → Output > max_tokens
  Loesung: Aufteilen in Gruppen (max 3 Dateien) → parallele Coder-Calls → Merge
"""

import os
import re
import logging
from typing import Dict, Any, List, Tuple, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

# AENDERUNG 13.02.2026: Fix 53 — run_coder_task nicht mehr direkt verwendet
# _run_group_coder() nutzt jetzt _run_coder_with_timeout() mit eigenem Timeout
from .dev_loop_coder import save_coder_output
from .dev_loop_coder_prompt import build_coder_prompt, filter_feedback_for_files
from .dev_loop_coder_utils import _get_affected_files_from_feedback, rebuild_current_code_from_disk
from .dev_loop_helpers import _parse_code_to_files, _check_for_truncation, validate_before_write
from .context_compressor import compress_context

logger = logging.getLogger(__name__)


def should_use_parallel_patch(
    affected_files: List[str],
    code_dict: Dict[str, str],
    config: Optional[Dict] = None
) -> bool:
    """Entscheidet ob paralleler PatchMode aktiviert wird (>=min_files ODER >=min_chars)."""
    config = config or {}
    if not config.get("enabled", True):
        return False

    max_per_group = config.get("max_files_per_group", 3)
    min_files = config.get("min_files_for_parallel", 2)
    min_chars = config.get("min_chars_for_parallel", 8000)

    if len(affected_files) >= min_files:
        return True

    # Pruefe Gesamtlaenge der betroffenen Dateien
    total_chars = 0
    for fname in affected_files:
        for key, content in code_dict.items():
            if os.path.basename(key) == fname or key.endswith(fname):
                total_chars += len(content)
                break

    if total_chars >= min_chars:
        return True

    return False


def _extract_imports(content: str) -> List[str]:
    """Extrahiert importierte Dateinamen (Basenames) aus JS/TS/Python Code."""
    imports = []
    # JS/TS: import ... from './xxx' oder import ... from '../xxx'
    js_patterns = [
        r"import\s+.*?from\s+['\"]\.{1,2}/([^'\"]+)['\"]",
        r"require\s*\(\s*['\"]\.{1,2}/([^'\"]+)['\"]\s*\)",
    ]
    for pat in js_patterns:
        matches = re.findall(pat, content)
        for m in matches:
            basename = os.path.basename(m)
            # Fuege Extension hinzu wenn fehlend
            if '.' not in basename:
                for ext in ['.js', '.jsx', '.ts', '.tsx']:
                    imports.append(basename + ext)
            else:
                imports.append(basename)

    # Python: from .xxx import / import xxx
    py_patterns = [
        r"from\s+\.(\w+)\s+import",
        r"from\s+(\w+)\s+import",
    ]
    for pat in py_patterns:
        matches = re.findall(pat, content)
        for m in matches:
            imports.append(m + '.py')

    return imports


def _get_file_chars(fname: str, code_dict: Dict[str, str]) -> int:
    """Gibt die Zeichenanzahl einer Datei zurueck (Basename-Matching)."""
    for key, content in code_dict.items():
        if os.path.basename(key) == fname or key.endswith(fname):
            return len(content)
    return 0


def group_files_by_dependency(
    affected_files: List[str],
    code_dict: Dict[str, str],
    max_per_group: int = 3,
    max_chars_per_group: int = 15000
) -> List[List[str]]:
    """
    Gruppiert betroffene Dateien fuer parallele Verarbeitung.
    Union-Find fuer Import-Dependencies + dynamischer Split nach chars (Fix 53).
    """
    if len(affected_files) <= max_per_group:
        # Selbst bei wenig Dateien: Pruefe ob einzelne Datei zu gross ist
        total_chars = sum(_get_file_chars(f, code_dict) for f in affected_files)
        if total_chars <= max_chars_per_group:
            return [affected_files]

    # Mappe Basenames auf volle Pfade
    basename_to_full = {}
    for key in code_dict:
        bn = os.path.basename(key)
        basename_to_full[bn] = key

    # Baue Abhaengigkeitsgraph (nur unter affected_files)
    deps = {}  # fname -> set of affected files it imports
    for fname in affected_files:
        full_path = basename_to_full.get(fname, fname)
        content = code_dict.get(full_path, "")
        if not content:
            # Suche mit Basename-Matching
            for key, val in code_dict.items():
                if os.path.basename(key) == fname:
                    content = val
                    break

        imported = _extract_imports(content)
        deps[fname] = set()
        for imp_name in imported:
            if imp_name in affected_files and imp_name != fname:
                deps[fname].add(imp_name)

    # Union-Find: Verbinde abhaengige Dateien
    parent = {f: f for f in affected_files}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for fname, dep_set in deps.items():
        for dep in dep_set:
            union(fname, dep)

    # Sammle Gruppen
    groups_map = {}
    for fname in affected_files:
        root = find(fname)
        if root not in groups_map:
            groups_map[root] = []
        groups_map[root].append(fname)

    # AENDERUNG 13.02.2026: Fix 53 — Dynamischer Split nach Dateien UND Zeichenanzahl
    # ROOT-CAUSE-FIX: 3 grosse Dateien (je 8000 Zeichen) = 24000 Zeichen pro Gruppe
    # → Output > max_tokens → Truncation. Dynamisches Splitting nach chars verhindert das.
    final_groups = []
    for group in groups_map.values():
        if len(group) <= max_per_group:
            # Pruefe Zeichenanzahl auch bei kleinen Gruppen
            group_chars = sum(_get_file_chars(f, code_dict) for f in group)
            if group_chars <= max_chars_per_group:
                final_groups.append(group)
                continue

        # Zeichenbasierter Split
        current_group = []
        current_chars = 0
        for fname in group:
            fchars = _get_file_chars(fname, code_dict)
            # Einzelne Datei groesser als Limit → eigene Gruppe
            if fchars > max_chars_per_group:
                if current_group:
                    final_groups.append(current_group)
                    current_group = []
                    current_chars = 0
                final_groups.append([fname])
                continue
            # Wuerde Gruppenlimit sprengen → neue Gruppe starten
            if (len(current_group) >= max_per_group or
                    current_chars + fchars > max_chars_per_group):
                if current_group:
                    final_groups.append(current_group)
                current_group = [fname]
                current_chars = fchars
            else:
                current_group.append(fname)
                current_chars += fchars
        if current_group:
            final_groups.append(current_group)

    return final_groups


def _build_group_prompt(
    group_files: List[str],
    all_code_dict: Dict[str, str],
    feedback: str,
    manager,
    user_goal: str,
    iteration: int,
    utds_protected_files: List[str] = None,
    iteration_history: List = None
) -> str:
    """Baut Prompt fuer eine Datei-Gruppe (VOLL fuer Gruppe, SUMMARY fuer Rest)."""
    # Filtere Feedback auf relevante Abschnitte
    filtered_feedback = filter_feedback_for_files(feedback, group_files)

    # Baue komprimierten Code-Kontext:
    # Gruppe-Dateien = VOLL, Rest = SUMMARY
    compressed = compress_context(
        all_code_dict,
        filtered_feedback,
        model_router=getattr(manager, 'model_router', None),
        config=manager.config,
        cache=getattr(manager, '_file_summaries_cache', None)
    )
    # Aktualisiere Cache
    if '_cache' in compressed:
        manager._file_summaries_cache = compressed.pop('_cache')

    # Stelle sicher dass Gruppe-Dateien VOLL enthalten sind (nicht komprimiert)
    for gfile in group_files:
        for key, content in all_code_dict.items():
            if os.path.basename(key) == gfile or key.endswith(gfile):
                compressed[key] = content  # Original-Inhalt statt Summary
                break

    # Baue Prompt mit dem komprimierten Code-Dict
    c_prompt = build_coder_prompt(
        manager, user_goal, filtered_feedback, iteration,
        utds_protected_files=utds_protected_files or [],
        iteration_history=iteration_history or [],
        override_code_dict=compressed
    )

    # Fuege Gruppen-Hinweis hinzu
    group_hint = (
        f"\n\n--- PARALLEL PATCH MODUS ---\n"
        f"Du bist fuer diese {len(group_files)} Datei(en) verantwortlich: "
        f"{', '.join(group_files)}\n"
        f"Gib NUR diese Dateien im ### FILENAME: Format aus.\n"
        f"Die anderen Dateien sind als Kontext-Zusammenfassung enthalten.\n"
        f"--- ENDE PARALLEL PATCH ---\n"
    )

    return c_prompt + group_hint


# AENDERUNG 13.02.2026: Fix 53 — Eigener Coder-Call mit konfigurierbarem Timeout
# AENDERUNG 21.02.2026: Multi-Tier Claude SDK (Haiku fuer Gruppen-Patches)
def _run_coder_with_timeout(manager, project_rules, prompt, timeout_seconds):
    """Fuehrt einen Coder-Call mit eigenem Timeout aus. Claude SDK zuerst, CrewAI als Fallback."""
    # Claude SDK Versuch (Haiku fuer einfache Patch-Aufgaben)
    try:
        from .claude_sdk_provider import run_sdk_with_retry
        sdk_result = run_sdk_with_retry(
            manager, role="fix", prompt=prompt,
            timeout_seconds=timeout_seconds,
            agent_display_name="ParallelPatch"
        )
        if sdk_result:
            return sdk_result
    except Exception as sdk_err:
        logger.debug("Claude SDK ParallelPatch nicht verfuegbar: %s", sdk_err)

    # Fallback: Bestehender CrewAI/OpenRouter Pfad
    from .agent_factory import init_agents
    from .heartbeat_utils import run_with_heartbeat
    from crewai import Task

    agent = init_agents(
        manager.config, project_rules,
        router=manager.model_router,
        include=["coder"],
        tech_blueprint=getattr(manager, 'tech_blueprint', None)
    ).get("coder")

    if not agent:
        logger.warning("Gruppen-Coder: Kein Agent erstellt")
        return None

    task = Task(description=prompt, expected_output="Code", agent=agent)
    try:
        raw = run_with_heartbeat(
            func=lambda: str(task.execute_sync()).strip(),
            ui_log_callback=manager._ui_log,
            agent_name="ParallelPatch",
            task_description=f"Gruppen-Coder (max {timeout_seconds}s)",
            heartbeat_interval=10,
            timeout_seconds=timeout_seconds
        )
        from .dev_loop_coder_utils import _clean_model_output
        return _clean_model_output(raw) if raw else None
    except TimeoutError as te:
        logger.warning("Gruppen-Coder Timeout nach %ds: %s", timeout_seconds, str(te)[:100])
        return None
    except Exception as e:
        logger.warning("Gruppen-Coder Fehler: %s", str(e)[:100])
        return None


def _find_old_content(fname: str, old_code_dict: Dict[str, str]) -> str:
    """Findet den bisherigen Inhalt einer Datei im code_dict (Basename-Matching)."""
    for key, val in old_code_dict.items():
        if os.path.basename(key) == fname or key.endswith(fname):
            return val
    return ""


# AENDERUNG 13.02.2026: Fix 53 — Eigener Timeout + Modell-Rotation pro Gruppe
def _run_group_coder(group_files, prompt, manager, project_rules, group_index, old_code_dict):
    """Worker mit eigenem Timeout + Modell-Rotation. Returns: {filename: content}."""
    group_label = f"Gruppe {group_index + 1} ({', '.join(group_files)})"
    # AENDERUNG 13.02.2026: Fix 53b — Single Source of Truth: agent_timeouts.coder
    # Parallele Gruppen-Coder SIND Coder-Agenten → selber Timeout wie run_coder_task()
    agent_timeouts = manager.config.get("agent_timeouts", {})
    group_timeout = agent_timeouts.get("coder", 750)

    try:
        manager._ui_log("ParallelPatch", "GroupStart",
            f"Starte {group_label} (Timeout: {group_timeout}s)")

        # Erster Versuch mit aktuellem Modell
        code_output = _run_coder_with_timeout(manager, project_rules, prompt, group_timeout)

        if not code_output:
            # AENDERUNG 13.02.2026: Fix 53 — Modell-Rotation bei Timeout/Fehler
            manager._ui_log("ParallelPatch", "GroupRetry",
                f"{group_label}: Erster Versuch fehlgeschlagen - versuche alternatives Modell")

            if manager.model_router:
                current = manager.model_router.get_model("coder")
                manager.model_router.mark_rate_limited_sync(current)
                code_output = _run_coder_with_timeout(
                    manager, project_rules, prompt, group_timeout)

        if not code_output:
            manager._ui_log("ParallelPatch", "GroupEmpty",
                f"{group_label}: Kein Output nach 2 Versuchen")
            return {}

        # Parse Output zu Dateien
        files_dict = _parse_code_to_files(code_output)

        if not files_dict:
            manager._ui_log("ParallelPatch", "GroupEmpty",
                f"{group_label}: Keine Dateien im Output")
            return {}

        # Truncation-Guard: Pruefe JEDE Datei VOR dem Akzeptieren
        valid_files = {}
        for fname, content in files_dict.items():
            old_content = _find_old_content(fname, old_code_dict)

            is_valid, reason = validate_before_write(fname, content, old_content)
            if is_valid:
                valid_files[fname] = content
            else:
                manager._ui_log("ParallelPatch", "TruncationBlocked",
                    f"{group_label}: {fname} nicht akzeptiert - {reason}")

        manager._ui_log("ParallelPatch", "GroupDone",
            f"{group_label}: {len(valid_files)}/{len(files_dict)} Dateien akzeptiert")

        return valid_files

    except Exception as e:
        manager._ui_log("ParallelPatch", "GroupError",
            f"{group_label} fehlgeschlagen: {str(e)[:200]}")
        logger.error("ParallelPatch %s Fehler: %s", group_label, e)
        return {}


def run_parallel_patch(
    manager,
    affected_files: List[str],
    code_dict: Dict[str, str],
    feedback: str,
    project_rules: Dict[str, Any],
    user_goal: str = "",
    iteration: int = 0,
    utds_protected_files: List[str] = None,
    iteration_history: List = None
) -> Tuple[str, List[str]]:
    """Fuehrt parallelen PatchMode aus: Gruppierung → Prompts → ThreadPool → Merge → Disk."""
    pp_config = manager.config.get("parallel_patch", {})
    max_per_group = pp_config.get("max_files_per_group", 3)
    # AENDERUNG 13.02.2026: Fix 53b — Dynamisch: Default = alle Gruppen parallel
    max_concurrent = pp_config.get("max_concurrent_groups", 8)
    max_chars_per_group = pp_config.get("max_chars_per_group", 15000)

    # Schritt 1: Gruppierung (mit dynamischer Groesse)
    groups = group_files_by_dependency(
        affected_files, code_dict, max_per_group,
        max_chars_per_group=max_chars_per_group
    )
    manager._ui_log("ParallelPatch", "Grouping",
        f"{len(affected_files)} Dateien → {len(groups)} Gruppe(n): "
        f"{[g for g in groups]}")

    # Schritt 2: Prompts bauen
    prompts = []
    for group in groups:
        prompt = _build_group_prompt(
            group, code_dict, feedback, manager,
            user_goal, iteration,
            utds_protected_files, iteration_history
        )
        prompts.append(prompt)

    # Schritt 3: Parallele Ausfuehrung
    all_results = {}  # filename -> content

    # AENDERUNG 13.02.2026: Fix 53b — Single Source of Truth: agent_timeouts.coder
    agent_timeouts = manager.config.get("agent_timeouts", {})
    coder_timeout = agent_timeouts.get("coder", 750)
    # Future-Timeout: 2× Coder-Timeout (Modell-Rotation) + Buffer
    future_timeout = coder_timeout * 2 + 60

    with ThreadPoolExecutor(max_workers=min(len(groups), max_concurrent)) as executor:
        futures = {}
        for i, (group, prompt) in enumerate(zip(groups, prompts)):
            future = executor.submit(
                _run_group_coder,
                group, prompt, manager, project_rules, i, code_dict
            )
            futures[future] = group

        for future in as_completed(futures):
            group = futures[future]
            try:
                result = future.result(timeout=future_timeout)
                all_results.update(result)
            except Exception as e:
                manager._ui_log("ParallelPatch", "Error",
                    f"Gruppe {group} Timeout/Fehler: {str(e)[:200]}")

    # Schritt 4: Merge — Aktualisiere code_dict mit neuen Ergebnissen
    merged_code_dict = dict(code_dict)  # Kopie des aktuellen Stands
    created_files = []

    for fname, content in all_results.items():
        # Finde den vollen Pfad im code_dict
        matched_key = None
        for key in merged_code_dict:
            if os.path.basename(key) == fname or key.endswith(fname):
                matched_key = key
                break
        if matched_key:
            merged_code_dict[matched_key] = content
        else:
            merged_code_dict[fname] = content
        created_files.append(fname)

    # Schritt 5: Dateien auf Disk schreiben
    if manager.project_path and created_files:
        from main import save_multi_file_output
        # Baue Code-String im ### FILENAME: Format
        code_parts = []
        for fname, content in all_results.items():
            code_parts.append(f"### FILENAME: {fname}")
            code_parts.append(content)
        code_string = "\n".join(code_parts)

        written_files = save_multi_file_output(
            str(manager.project_path), code_string,
            "parallel_patch_output.js",
            is_patch_mode=True  # Truncation-Guard aktiv
        )
        created_files = written_files

    # Schritt 6: current_code von Disk rekonstruieren
    merged_current_code = rebuild_current_code_from_disk(manager)

    manager._ui_log("ParallelPatch", "Complete",
        f"Parallel PatchMode abgeschlossen: "
        f"{len(created_files)} Dateien geschrieben, "
        f"{len(affected_files) - len(all_results)} noch offen")

    return merged_current_code, created_files
