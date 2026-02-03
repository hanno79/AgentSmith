# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 31.01.2026
Version: 1.0
Beschreibung: Coder-Funktionen für DevLoop.
              Extrahiert aus dev_loop_steps.py (Regel 1: Max 500 Zeilen)
              Enthält: Coder-Prompt Builder, Task-Ausführung, Output-Speicherung
              ÄNDERUNG 29.01.2026: Modellwechsel erst nach 2 gleichen Fehlern
              ÄNDERUNG 31.01.2026: Truncation-Detection und Unicode-Sanitization
"""

import os
import json
import time
import traceback
from typing import Dict, Any, Tuple, List

from crewai import Task

from agents.memory_agent import get_lessons_for_prompt
from budget_tracker import get_budget_tracker
from main import save_multi_file_output
from .agent_factory import init_agents
from .orchestration_helpers import (
    is_rate_limit_error,
    is_server_error,
    is_litellm_internal_error,
    is_openrouter_error  # ÄNDERUNG 02.02.2026: OpenRouter-Fehler für sofortigen Modellwechsel
)
from .heartbeat_utils import run_with_heartbeat
from .dev_loop_helpers import _sanitize_unicode, _check_for_truncation, get_python_dependency_versions

import re


# ÄNDERUNG 03.02.2026: Patch-Modus Helper-Funktionen
# Verhindert dass Coder bei Fehlern kompletten Code überschreibt

def _is_targeted_fix_context(feedback: str) -> bool:
    """
    Prüft ob Feedback auf einen gezielten Fix hinweist.

    Args:
        feedback: Das Fehler-Feedback

    Returns:
        True wenn Patch-Modus sinnvoll, False sonst
    """
    if not feedback:
        return False

    # Spezifische Error-Indikatoren die auf gezielten Fix hinweisen
    # ÄNDERUNG 03.02.2026: Deutsche Fehlerbegriffe hinzugefügt für PatchMode-Aktivierung
    fix_indicators = [
        # Englische Error-Typen
        "TypeError:", "NameError:", "SyntaxError:", "ImportError:",
        "AttributeError:", "KeyError:", "ValueError:", "ModuleNotFoundError:",
        "expected", "got", "argument", "parameter", "takes",
        "missing", "undefined", "not defined", "cannot import",
        # Deutsche Fehlerbegriffe
        "Syntaxfehler", "Fehler:", "ungültig", "fehlgeschlagen",
        "nicht gefunden", "nicht definiert", "fehlerhaft", "Formatierung"
    ]

    feedback_lower = feedback.lower()
    return any(ind.lower() in feedback_lower for ind in fix_indicators)


def _get_affected_files_from_feedback(feedback: str) -> List[str]:
    """
    Extrahiert betroffene Dateinamen aus Feedback.

    Args:
        feedback: Das Fehler-Feedback

    Returns:
        Liste der betroffenen Dateinamen
    """
    if not feedback:
        return []

    # Regex-Patterns für Dateinamen in Fehlermeldungen
    file_patterns = [
        r'File "([^"]+\.py)"',           # Python Traceback
        r'in ([a-zA-Z_][a-zA-Z0-9_]*\.py)',  # "in filename.py"
        r'([a-zA-Z_][a-zA-Z0-9_]*\.py):',    # "filename.py:"
        r'tests/([^/\s]+\.py)',           # Tests
        r'([a-zA-Z_][a-zA-Z0-9_]*\.(?:js|jsx|ts|tsx))[\s:]',  # JS/TS
    ]

    found_files = []
    for pattern in file_patterns:
        matches = re.findall(pattern, feedback)
        for match in matches:
            # Nur Dateinamen, nicht volle Pfade aus System-Bibliotheken
            if not any(skip in match.lower() for skip in ['site-packages', 'python3', '/usr/', 'venv/']):
                basename = os.path.basename(match)
                if basename not in found_files:
                    found_files.append(basename)

    return found_files[:5]  # Max 5 Dateien


def _build_patch_prompt(current_code: dict, affected_files: List[str], feedback: str) -> str:
    """
    Baut einen Patch-fokussierten Prompt.

    Args:
        current_code: Dict mit aktuellem Code {filename: content}
        affected_files: Liste der betroffenen Dateien
        feedback: Das Fehler-Feedback

    Returns:
        Patch-Modus Prompt-String
    """
    prompt = "\n\n⚠️ PATCH-MODUS - NUR die folgenden Dateien anpassen:\n"
    prompt += "WICHTIG: Nur die betroffenen Zeilen ändern, Rest UNVERÄNDERT lassen!\n\n"

    files_found = 0
    for fname in affected_files:
        # Suche Datei im current_code (auch mit Pfad-Variationen)
        content = None
        for code_file, code_content in (current_code or {}).items():
            if code_file == fname or code_file.endswith(f"/{fname}") or code_file.endswith(f"\\{fname}"):
                content = code_content
                break

        if content:
            prompt += f"--- {fname} (AKTUELLER CODE) ---\n"
            prompt += f"```\n{content}\n```\n\n"
            files_found += 1

    prompt += f"🔧 FEHLER ZU BEHEBEN:\n{feedback}\n\n"
    prompt += "📋 ANWEISUNGEN:\n"
    prompt += "1. Analysiere den Fehler genau\n"
    prompt += "2. Ändere NUR die betroffene(n) Zeile(n)\n"
    prompt += "3. Behalte alle anderen Funktionen/Klassen unverändert bei\n"
    prompt += "4. Gib die komplette korrigierte Datei aus\n"

    return prompt


def build_coder_prompt(manager, user_goal: str, feedback: str, iteration: int) -> str:
    """
    Baut den Coder-Prompt basierend auf Kontext, Feedback und Security-Tasks.
    """
    c_prompt = f"Ziel: {user_goal}\nTech: {manager.tech_blueprint}\nDB: {manager.database_schema}\n"

    briefing_context = manager.get_briefing_context()
    if briefing_context:
        c_prompt += f"\n{briefing_context}\n"

    # ÄNDERUNG 03.02.2026: Patch-Modus bei gezielten Fehlern
    # Verhindert dass UTDS-Fixes überschrieben werden
    if not manager.is_first_run:
        if feedback and _is_targeted_fix_context(feedback):
            # PATCH-MODUS: Nur betroffene Dateien + Patch-Anweisungen
            affected_files = _get_affected_files_from_feedback(feedback)
            if affected_files and manager.current_code:
                manager._ui_log("Coder", "PatchMode",
                    f"Patch-Modus aktiv für: {', '.join(affected_files)}")
                c_prompt += _build_patch_prompt(manager.current_code, affected_files, feedback)
            else:
                # Fallback: Vollständiger Code wenn keine betroffenen Dateien erkannt
                # ÄNDERUNG 03.02.2026: Log warum PatchMode nicht aktiviert
                reason = "keine betroffenen Dateien" if not affected_files else "kein current_code"
                manager._ui_log("Coder", "FullMode",
                    f"PatchMode-Fallback: {reason}")
                c_prompt += f"\nAlt-Code:\n{manager.current_code}\n"
                c_prompt += f"\nKorrektur: {feedback}\n"
        else:
            # VOLLSTÄNDIGER MODUS: Kompletter Code für größere Änderungen
            # ÄNDERUNG 03.02.2026: Log wenn kein Error-Kontext erkannt
            manager._ui_log("Coder", "FullMode",
                "Kein gezielter Fehler-Kontext erkannt - vollständige Regenerierung")
            c_prompt += f"\nAlt-Code:\n{manager.current_code}\n"
            if feedback:
                c_prompt += f"\nKorrektur: {feedback}\n"
    elif feedback:
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

    # AENDERUNG 01.02.2026: Dependency-Versionen aus Inventar laden
    # Verhindert dass LLM veraltete/falsche Versionen generiert (z.B. greenlet==2.0.7)
    try:
        dep_versions = get_python_dependency_versions()
        if dep_versions:
            c_prompt += f"\n\n📦 {dep_versions}\n"
            c_prompt += "WICHTIG: Für requirements.txt NUR diese Versionen verwenden! Keine eigenen Versionen erfinden!\n"
    except Exception as dep_err:
        manager._ui_log("Coder", "Warning", f"Dependency-Versionen konnten nicht geladen werden: {dep_err}")

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
    Fuehrt den Coder-Task mit Retry-Logik und Heartbeat-Updates aus.
    ÄNDERUNG 29.01.2026: Modellwechsel erst nach 2 gleichen Fehlern mit demselben Modell.
    """
    task_coder = Task(description=c_prompt, expected_output="Code", agent=agent_coder)
    MAX_CODER_RETRIES = 6  # Erhöht: 2 Versuche pro Modell x 3 Modelle
    # ÄNDERUNG 30.01.2026: Timeout aus globaler Config
    CODER_TIMEOUT_SECONDS = manager.config.get("agent_timeout_seconds", 300)
    # ÄNDERUNG 29.01.2026: Modellwechsel erst nach X gleichen Fehlern
    ERRORS_BEFORE_MODEL_SWITCH = 2
    current_code = ""

    # Fehler-Tracker: (modell, fehlertyp) -> anzahl
    error_tracker = {}
    last_error_type = None

    for coder_attempt in range(MAX_CODER_RETRIES):
        current_model = manager.model_router.get_model("coder") if manager.model_router else "unknown"
        try:
            # ÄNDERUNG 29.01.2026: Heartbeat-Wrapper für stabile WebSocket-Verbindung
            current_code = run_with_heartbeat(
                func=lambda: str(task_coder.execute_sync()).strip(),
                ui_log_callback=manager._ui_log,
                agent_name="Coder",
                task_description=f"Code-Generierung (Versuch {coder_attempt + 1}/{MAX_CODER_RETRIES})",
                heartbeat_interval=15,
                timeout_seconds=CODER_TIMEOUT_SECONDS
            )
            break
        except TimeoutError as te:
            # ÄNDERUNG 02.02.2026: OpenRouter-Fehler = sofortiger Modellwechsel
            if is_openrouter_error(te):
                manager._ui_log("Coder", "OpenRouterError",
                                f"OpenRouter-Fehler erkannt bei {current_model} - sofortiger Modellwechsel")
                manager.model_router.mark_rate_limited_sync(current_model)
                agent_coder = init_agents(
                    manager.config,
                    project_rules,
                    router=manager.model_router,
                    include=["coder"]
                ).get("coder")
                task_coder = Task(description=c_prompt, expected_output="Code", agent=agent_coder)
                error_tracker = {}  # Tracker zurücksetzen nach Modellwechsel

                if coder_attempt == MAX_CODER_RETRIES - 1:
                    manager._ui_log("Coder", "Error", f"Alle {MAX_CODER_RETRIES} Versuche fehlgeschlagen (OpenRouter)")
                    raise te
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

            manager._ui_log("Coder", "Timeout",
                            f"Coder-Modell {current_model} timeout nach {CODER_TIMEOUT_SECONDS}s (Fehler {error_count}/{ERRORS_BEFORE_MODEL_SWITCH})")

            # Erst nach ERRORS_BEFORE_MODEL_SWITCH gleichen Fehlern Modell wechseln
            if error_count >= ERRORS_BEFORE_MODEL_SWITCH:
                manager._ui_log("Coder", "Status", f"🔄 Modellwechsel nach {error_count} Timeouts")
                manager.model_router.mark_rate_limited_sync(current_model)
                agent_coder = init_agents(
                    manager.config,
                    project_rules,
                    router=manager.model_router,
                    include=["coder"]
                ).get("coder")
                task_coder = Task(description=c_prompt, expected_output="Code", agent=agent_coder)
                error_tracker = {}  # Tracker zurücksetzen nach Modellwechsel

            if coder_attempt == MAX_CODER_RETRIES - 1:
                manager._ui_log("Coder", "Error", f"Alle {MAX_CODER_RETRIES} Versuche fehlgeschlagen (Timeout)")
                raise te
            continue

        except Exception as error:
            # ÄNDERUNG 29.01.2026: LiteLLM interne Bugs wie Rate-Limits behandeln
            if is_litellm_internal_error(error):
                error_type = "litellm_bug"
                error_key = (current_model, error_type)

                # Bei neuem Fehlertyp: Tracker zurücksetzen
                if last_error_type and last_error_type != error_type:
                    error_tracker = {}
                last_error_type = error_type

                error_tracker[error_key] = error_tracker.get(error_key, 0) + 1
                error_count = error_tracker[error_key]

                manager._ui_log("Coder", "Warning",
                                f"LiteLLM-Bug erkannt (Fehler {error_count}/{ERRORS_BEFORE_MODEL_SWITCH}): {str(error)[:100]}")

                # Erst nach ERRORS_BEFORE_MODEL_SWITCH gleichen Fehlern Modell wechseln
                if error_count >= ERRORS_BEFORE_MODEL_SWITCH:
                    manager._ui_log("Coder", "Status", f"🔄 Modellwechsel nach {error_count} LiteLLM-Bugs")
                    manager.model_router.mark_rate_limited_sync(current_model)
                    agent_coder = init_agents(
                        manager.config,
                        project_rules,
                        router=manager.model_router,
                        include=["coder"]
                    ).get("coder")
                    task_coder = Task(description=c_prompt, expected_output="Code", agent=agent_coder)
                    error_tracker = {}  # Tracker zurücksetzen nach Modellwechsel

                if coder_attempt == MAX_CODER_RETRIES - 1:
                    manager._ui_log("Coder", "Error", f"Alle {MAX_CODER_RETRIES} Versuche fehlgeschlagen (LiteLLM-Bug): {str(error)[:200]}")
                    raise error
                continue

            if is_rate_limit_error(error):
                # Rate-Limit: Sofort wechseln (keine Wartezeit sinnvoll)
                manager.model_router.mark_rate_limited_sync(current_model)
                manager._ui_log(
                    "ModelRouter",
                    "RateLimit",
                    f"Modell {current_model} pausiert, wechsle zu Fallback..."
                )
                agent_coder = init_agents(
                    manager.config,
                    project_rules,
                    router=manager.model_router,
                    include=["coder"]
                ).get("coder")
                task_coder = Task(description=c_prompt, expected_output="Code", agent=agent_coder)
                error_tracker = {}  # Tracker zurücksetzen

                if coder_attempt == MAX_CODER_RETRIES - 1:
                    manager._ui_log("Coder", "Error", f"Alle {MAX_CODER_RETRIES} Versuche fehlgeschlagen: {str(error)[:200]}")
                    raise error
                continue

            # ÄNDERUNG 29.01.2026: Server-Fehler-Delay im Caller statt im Helper
            if is_server_error(error):
                manager._ui_log("Coder", "Warning", "Server-Fehler erkannt - kurze Pause von 5s")
                time.sleep(5)
            manager._ui_log("Coder", "Error", f"Unerwarteter Fehler: {str(error)[:200]}")
            raise error

    return current_code, agent_coder


def save_coder_output(manager, current_code: str, output_path: str, iteration: int, max_retries: int) -> tuple:
    """
    Speichert Coder-Output und sendet UI-Events.
    ÄNDERUNG 31.01.2026: Truncation-Detection für abgeschnittene LLM-Outputs.
    ÄNDERUNG 31.01.2026: Unicode-Sanitization vor Datei-Speicherung.
    ÄNDERUNG 31.01.2026: Gibt jetzt (created_files, truncated_files) zurück für Modellwechsel-Logik.
    """
    # ÄNDERUNG 31.01.2026: Unicode-Sanitization vor Datei-Speicherung
    # Entfernt unsichtbare Zeichen (U+FE0F etc.) die Python-Syntax brechen
    sanitized_code = _sanitize_unicode(current_code)

    def_file = os.path.basename(output_path)
    created_files = save_multi_file_output(manager.project_path, sanitized_code, def_file)
    manager._ui_log("Coder", "Files", f"Created: {', '.join(created_files)}")

    # ÄNDERUNG 31.01.2026: Truncation-Detection
    # Prüfe ob Python-Dateien vollständig sind (nicht abgeschnitten)
    # ÄNDERUNG 31.01.2026: truncated_files außerhalb try-Block für Rückgabe
    truncated_files = []
    try:
        files_to_check = {}
        for filename in created_files:
            if filename.endswith('.py'):
                filepath = os.path.join(manager.project_path, filename)
                if os.path.exists(filepath):
                    with open(filepath, 'r', encoding='utf-8') as f:
                        files_to_check[filename] = f.read()

        truncated_files = _check_for_truncation(files_to_check)
        if truncated_files:
            truncated_names = [f[0] for f in truncated_files]
            truncation_details = "; ".join([f"{f[0]}: {f[1]}" for f in truncated_files])
            manager._ui_log("Coder", "TruncationWarning", json.dumps({
                "truncated_files": truncated_names,
                "details": truncation_details,
                "iteration": iteration + 1,
                "action": "model_switch_recommended"
            }, ensure_ascii=False))
            manager._ui_log("Coder", "Warning",
                f"⚠️ Abgeschnittene Dateien erkannt: {', '.join(truncated_names)}")
    except Exception as trunc_err:
        manager._ui_log("Coder", "Warning", f"Truncation-Check fehlgeschlagen: {trunc_err}")

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
    except Exception as budget_err:
        # ÄNDERUNG 29.01.2026: Budget-Tracker Fehler sichtbar loggen
        manager._ui_log(
            "Coder",
            "Warning",
            "Fehler bei get_budget_tracker/tracker.get_today_totals; Details siehe Stacktrace."
        )
        manager._ui_log("Coder", "Warning", traceback.format_exc())

    # ÄNDERUNG 31.01.2026: Gebe auch truncated_files zurück für Modellwechsel-Logik
    return created_files, truncated_files
