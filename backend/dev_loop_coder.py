# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 31.01.2026
Version: 2.0
Beschreibung: Coder-Kernfunktionen fuer DevLoop.
              Extrahiert aus dev_loop_steps.py (Regel 1: Max 500 Zeilen)
              Enthaelt: Coder-Task-Ausfuehrung, Output-Speicherung.
              AENDERUNG 08.02.2026: Refactoring — Prompt-Builder und Utilities
              in dev_loop_coder_prompt.py bzw. dev_loop_coder_utils.py ausgelagert.
              AENDERUNG 29.01.2026: Modellwechsel erst nach 2 gleichen Fehlern
              AENDERUNG 31.01.2026: Truncation-Detection und Unicode-Sanitization
"""

import logging
import os
import json
import time
import traceback
from typing import Dict, Any, Tuple

from crewai import Task

from budget_tracker import get_budget_tracker
from main import save_multi_file_output
from .agent_factory import init_agents
from .orchestration_helpers import (
    is_rate_limit_error,
    is_server_error,
    is_litellm_internal_error,
    is_openrouter_error  # AENDERUNG 02.02.2026: OpenRouter-Fehler fuer sofortigen Modellwechsel
)
from .heartbeat_utils import run_with_heartbeat
from .dev_loop_helpers import _sanitize_unicode, _check_for_truncation

# AENDERUNG 08.02.2026: Refactoring — Imports aus neuen Modulen
from .dev_loop_coder_utils import _clean_model_output, rebuild_current_code_from_disk
from .dev_loop_coder_prompt import build_coder_prompt

logger = logging.getLogger(__name__)


def run_coder_task(manager, project_rules: Dict[str, Any], c_prompt: str, agent_coder) -> Tuple[str, Any]:
    """
    Fuehrt den Coder-Task mit Retry-Logik und Heartbeat-Updates aus.
    AENDERUNG 29.01.2026: Modellwechsel erst nach 2 gleichen Fehlern mit demselben Modell.
    """
    task_coder = Task(description=c_prompt, expected_output="Code", agent=agent_coder)
    MAX_CODER_RETRIES = 6  # Erhoeht: 2 Versuche pro Modell x 3 Modelle
    # AENDERUNG 08.02.2026: Nur noch agent_timeouts Dict (globales agent_timeout_seconds entfernt)
    agent_timeouts = manager.config.get("agent_timeouts", {})
    CODER_TIMEOUT_SECONDS = agent_timeouts.get("coder", 750)
    # AENDERUNG 29.01.2026: Modellwechsel erst nach X gleichen Fehlern
    ERRORS_BEFORE_MODEL_SWITCH = 2
    current_code = ""

    # Fehler-Tracker: (modell, fehlertyp) -> anzahl
    error_tracker = {}
    last_error_type = None

    for coder_attempt in range(MAX_CODER_RETRIES):
        current_model = manager.model_router.get_model("coder") if manager.model_router else "unknown"
        try:
            # AENDERUNG 29.01.2026: Heartbeat-Wrapper fuer stabile WebSocket-Verbindung
            raw_output = run_with_heartbeat(
                func=lambda: str(task_coder.execute_sync()).strip(),
                ui_log_callback=manager._ui_log,
                agent_name="Coder",
                task_description=f"Code-Generierung (Versuch {coder_attempt + 1}/{MAX_CODER_RETRIES})",
                heartbeat_interval=15,
                timeout_seconds=CODER_TIMEOUT_SECONDS
            )
            # AENDERUNG 03.02.2026: Fix 8 - Think-Tag Filtering
            current_code = _clean_model_output(raw_output)
            if current_code != raw_output:
                manager._ui_log("Coder", "ThinkTagFilter", "Model-Output bereinigt (Think-Tags entfernt)")
            break
        except TimeoutError as te:
            # AENDERUNG 02.02.2026: OpenRouter-Fehler = sofortiger Modellwechsel
            if is_openrouter_error(te):
                manager._ui_log("Coder", "OpenRouterError",
                                f"OpenRouter-Fehler erkannt bei {current_model} - sofortiger Modellwechsel")
                manager.model_router.mark_rate_limited_sync(current_model)
                # AENDERUNG 06.02.2026: tech_blueprint fuer Tech-Stack-Kontext
                agent_coder = init_agents(
                    manager.config,
                    project_rules,
                    router=manager.model_router,
                    include=["coder"],
                    tech_blueprint=getattr(manager, 'tech_blueprint', None)
                ).get("coder")
                task_coder = Task(description=c_prompt, expected_output="Code", agent=agent_coder)
                error_tracker = {}  # Tracker zuruecksetzen nach Modellwechsel

                if coder_attempt == MAX_CODER_RETRIES - 1:
                    manager._ui_log("Coder", "Error", f"Alle {MAX_CODER_RETRIES} Versuche fehlgeschlagen (OpenRouter)")
                    raise te
                continue

            # Normaler Timeout (kein OpenRouter-spezifischer Fehler)
            error_type = "timeout"
            error_key = (current_model, error_type)

            # Bei neuem Fehlertyp: Tracker zuruecksetzen
            if last_error_type and last_error_type != error_type:
                error_tracker = {}
            last_error_type = error_type

            error_tracker[error_key] = error_tracker.get(error_key, 0) + 1
            error_count = error_tracker[error_key]

            manager._ui_log("Coder", "Timeout",
                            f"Coder-Modell {current_model} timeout nach {CODER_TIMEOUT_SECONDS}s (Fehler {error_count}/{ERRORS_BEFORE_MODEL_SWITCH})")

            # Erst nach ERRORS_BEFORE_MODEL_SWITCH gleichen Fehlern Modell wechseln
            if error_count >= ERRORS_BEFORE_MODEL_SWITCH:
                manager._ui_log("Coder", "Status", f"Modellwechsel nach {error_count} Timeouts")
                manager.model_router.mark_rate_limited_sync(current_model)
                # AENDERUNG 06.02.2026: tech_blueprint fuer Tech-Stack-Kontext
                agent_coder = init_agents(
                    manager.config,
                    project_rules,
                    router=manager.model_router,
                    include=["coder"],
                    tech_blueprint=getattr(manager, 'tech_blueprint', None)
                ).get("coder")
                task_coder = Task(description=c_prompt, expected_output="Code", agent=agent_coder)
                error_tracker = {}  # Tracker zuruecksetzen nach Modellwechsel

            if coder_attempt == MAX_CODER_RETRIES - 1:
                manager._ui_log("Coder", "Error", f"Alle {MAX_CODER_RETRIES} Versuche fehlgeschlagen (Timeout)")
                raise te
            continue

        except Exception as error:
            # AENDERUNG 29.01.2026: LiteLLM interne Bugs wie Rate-Limits behandeln
            if is_litellm_internal_error(error):
                error_type = "litellm_bug"
                error_key = (current_model, error_type)

                # Bei neuem Fehlertyp: Tracker zuruecksetzen
                if last_error_type and last_error_type != error_type:
                    error_tracker = {}
                last_error_type = error_type

                error_tracker[error_key] = error_tracker.get(error_key, 0) + 1
                error_count = error_tracker[error_key]

                manager._ui_log("Coder", "Warning",
                                f"LiteLLM-Bug erkannt (Fehler {error_count}/{ERRORS_BEFORE_MODEL_SWITCH}): {str(error)[:100]}")

                # Erst nach ERRORS_BEFORE_MODEL_SWITCH gleichen Fehlern Modell wechseln
                if error_count >= ERRORS_BEFORE_MODEL_SWITCH:
                    manager._ui_log("Coder", "Status", f"Modellwechsel nach {error_count} LiteLLM-Bugs")
                    manager.model_router.mark_rate_limited_sync(current_model)
                    # AENDERUNG 06.02.2026: tech_blueprint fuer Tech-Stack-Kontext
                    agent_coder = init_agents(
                        manager.config,
                        project_rules,
                        router=manager.model_router,
                        include=["coder"],
                        tech_blueprint=getattr(manager, 'tech_blueprint', None)
                    ).get("coder")
                    task_coder = Task(description=c_prompt, expected_output="Code", agent=agent_coder)
                    error_tracker = {}  # Tracker zuruecksetzen nach Modellwechsel

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
                # AENDERUNG 06.02.2026: tech_blueprint fuer Tech-Stack-Kontext
                agent_coder = init_agents(
                    manager.config,
                    project_rules,
                    router=manager.model_router,
                    include=["coder"],
                    tech_blueprint=getattr(manager, 'tech_blueprint', None)
                ).get("coder")
                task_coder = Task(description=c_prompt, expected_output="Code", agent=agent_coder)
                error_tracker = {}  # Tracker zuruecksetzen

                if coder_attempt == MAX_CODER_RETRIES - 1:
                    manager._ui_log("Coder", "Error", f"Alle {MAX_CODER_RETRIES} Versuche fehlgeschlagen: {str(error)[:200]}")
                    raise error
                continue

            # AENDERUNG 29.01.2026: Server-Fehler-Delay im Caller statt im Helper
            if is_server_error(error):
                manager._ui_log("Coder", "Warning", "Server-Fehler erkannt - kurze Pause von 5s")
                time.sleep(5)
            manager._ui_log("Coder", "Error", f"Unerwarteter Fehler: {str(error)[:200]}")
            raise error

    return current_code, agent_coder


def save_coder_output(manager, current_code: str, output_path: str, iteration: int,
                      max_retries: int, is_patch_mode: bool = False) -> tuple:
    """
    Speichert Coder-Output und sendet UI-Events.
    AENDERUNG 31.01.2026: Truncation-Detection fuer abgeschnittene LLM-Outputs.
    AENDERUNG 31.01.2026: Unicode-Sanitization vor Datei-Speicherung.
    AENDERUNG 31.01.2026: Gibt jetzt (created_files, truncated_files) zurueck fuer Modellwechsel-Logik.
    AENDERUNG 10.02.2026: Fix 44 — is_patch_mode fuer Phantom-Datei-Schutz.
    """
    # AENDERUNG 31.01.2026: Unicode-Sanitization vor Datei-Speicherung
    sanitized_code = _sanitize_unicode(current_code)

    def_file = os.path.basename(output_path)
    created_files = save_multi_file_output(manager.project_path, sanitized_code, def_file,
                                           is_patch_mode=is_patch_mode)
    manager._ui_log("Coder", "Files", f"Created: {', '.join(created_files)}")

    # AENDERUNG 31.01.2026: Truncation-Detection
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
                f"Abgeschnittene Dateien erkannt: {', '.join(truncated_names)}")
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
    # AENDERUNG 03.02.2026: idle-Reset entfernt - wird jetzt zentral in dev_loop.py via try-finally gehandelt

    try:
        tracker = get_budget_tracker()
        today_totals = tracker.get_today_totals()
        manager._ui_log("Coder", "TokenMetrics", json.dumps({
            "total_tokens": today_totals.get("total_tokens", 0),
            "total_cost": today_totals.get("total_cost", 0.0)
        }, ensure_ascii=False))
    except Exception as budget_err:
        # AENDERUNG 29.01.2026: Budget-Tracker Fehler sichtbar loggen
        manager._ui_log(
            "Coder",
            "Warning",
            "Fehler bei get_budget_tracker/tracker.get_today_totals; Details siehe Stacktrace."
        )
        manager._ui_log("Coder", "Warning", traceback.format_exc())

    # AENDERUNG 31.01.2026: Gebe auch truncated_files zurueck fuer Modellwechsel-Logik
    return created_files, truncated_files
