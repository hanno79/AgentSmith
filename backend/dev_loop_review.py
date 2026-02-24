# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 08.02.2026
Version: 1.1
Beschreibung: Review-Funktion fuer DevLoop mit Retry- und Modellwechsel-Logik.
              Extrahiert aus dev_loop_validators.py (Regel 1: Max 500 Zeilen)
              Enthaelt: run_review
              AENDERUNG 08.02.2026: Modul-Extraktion aus dev_loop_validators.py
              AENDERUNG 10.02.2026: Fix 42 - Reviewer Context-Kompression
"""

import json
import logging
from typing import Dict, Any, Tuple

from crewai import Task

from .agent_factory import init_agents
from .context_compressor import compress_context
from .dev_loop_coder_utils import _get_current_code_dict
from .orchestration_helpers import (
    is_rate_limit_error,
    is_empty_or_invalid_response,
    is_openrouter_error,
    create_human_readable_verdict,
    truncate_review_output
)
from .heartbeat_utils import run_with_heartbeat

logger = logging.getLogger(__name__)


def _compress_review_code(manager, sandbox_result: str, test_summary: str) -> str:
    """
    Komprimiert current_code fuer den Reviewer mit Context-Kompression.

    AENDERUNG 10.02.2026: Fix 42 - Reviewer Context-Overflow Guard
    ROOT-CAUSE-FIX:
    Symptom: deepseek-chat-v3.1 context overflow (196,577 > 163,840 tokens)
    Ursache: Reviewer bekam current_code verbatim ohne Kompression
    Loesung: compress_context() anwenden (gleiche Logik wie Coder)
    """
    code_dict = _get_current_code_dict(manager)
    if not code_dict:
        return getattr(manager, 'current_code', '') or ''

    # Feedback = sandbox_result + test_summary (enthaelt Dateinamen der Fehler)
    review_feedback = ""
    if sandbox_result:
        review_feedback += sandbox_result
    if test_summary:
        review_feedback += "\n" + test_summary

    cache = getattr(manager, '_reviewer_summary_cache', {})

    compressed = compress_context(
        code_dict=code_dict,
        feedback=review_feedback,
        config=manager.config,
        cache=cache
    )

    # Cache persistieren fuer naechste Iteration
    new_cache = compressed.pop('_cache', {})
    manager._reviewer_summary_cache = new_cache

    # Dict zurueck in ### FILENAME: Format
    parts = []
    for filepath in sorted(compressed.keys()):
        content = compressed[filepath]
        # Summary-Marker: Erkenne komprimierte Dateien
        is_summary = (
            content.startswith("IMPORTS:") or content.startswith("VORSCHAU:")
            or content.startswith("SELEKTOREN:") or content.startswith("TOP-KEYS:")
            or content.startswith("NAME:") or content.startswith("KLASSEN:")
            or content.startswith("FUNKTIONEN:") or content.startswith("[")
        )
        label = " (ZUSAMMENFASSUNG)" if is_summary else ""
        parts.append(f"### FILENAME: {filepath}{label}\n{content}")

    compressed_code = "\n\n".join(parts)
    original_len = len(getattr(manager, 'current_code', '') or '')

    # Sicherheits-Limit: Max Zeichen fuer Reviewer-Prompt (Ratio 1:3 Token:Char)
    max_chars = manager.config.get("max_reviewer_prompt_chars", 400000)
    if len(compressed_code) > max_chars:
        logger.warning(
            "Reviewer-Code ueberschreitet %d Zeichen (%d) - kuerze auf Limit",
            max_chars, len(compressed_code)
        )
        compressed_code = compressed_code[:max_chars] + "\n\n[... GEKUERZT wegen Token-Limit ...]"

    logger.info(
        "Reviewer-Code komprimiert: %d -> %d Zeichen (%d Dateien)",
        original_len, len(compressed_code), len(compressed)
    )
    return compressed_code


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
    AENDERUNG 29.01.2026: Modellwechsel erst nach 2 gleichen Fehlern mit demselben Modell.
    AENDERUNG 02.02.2026: Erweiterter Prompt fuer spezifische Docker-Fehler-Analyse (Fix #11).
    AENDERUNG 10.02.2026: Fix 42 - Context-Kompression fuer Reviewer-Input.
    """
    # AENDERUNG 10.02.2026: Fix 42 - Komprimiere Code VOR dem Reviewer-Prompt
    # ROOT-CAUSE-FIX:
    # Symptom: deepseek-chat-v3.1 context overflow (196,577 > 163,840 tokens)
    # Ursache: Reviewer bekam manager.current_code verbatim (31 Dateien = ~590k Zeichen)
    # Loesung: compress_context() reduziert Nicht-Fehler-Dateien auf Summaries
    compressed_code = _compress_review_code(manager, sandbox_result or "", test_summary or "")

    # AENDERUNG 02.02.2026 v2: Extrahiere spezifische Fehler aus Docker-Output
    docker_error_highlight = ""
    if sandbox_result and sandbox_failed:
        error_keywords = ["Error", "ImportError", "ModuleNotFoundError", "SyntaxError",
                         "ResolutionImpossible", "conflicting", "in <module>", ".py:"]
        error_lines = []
        for line in sandbox_result.split('\n'):
            if any(kw in line for kw in error_keywords):
                error_lines.append(line.strip())
        if error_lines:
            docker_error_highlight = "\n>>> KRITISCHE FEHLER GEFUNDEN <<<\n" + "\n".join(error_lines[:10])

    r_prompt = f"""=== CODE ZUM PRUEFEN ===
{compressed_code}

=== SANDBOX/DOCKER-ERGEBNIS (WICHTIG!) ===
{sandbox_result if sandbox_result else "Kein Sandbox-Ergebnis vorhanden."}
{docker_error_highlight}

=== TEST-ZUSAMMENFASSUNG ===
{test_summary if test_summary else "Keine Test-Zusammenfassung vorhanden."}

=== ANALYSE-ANWEISUNGEN ===
ANALYSIERE den EXAKTEN Fehler oben im SANDBOX/DOCKER-ERGEBNIS!

Bei Fehlern MUSST du folgendes liefern:
1. URSACHE: Die KONKRETE Ursache (NICHT generisch "Docker fehlgeschlagen")
2. BETROFFENE DATEIEN: [DATEI:dateiname.ext] fuer JEDE betroffene Datei
3. LOESUNG: Konkreter Fix mit Code-Beispiel

WICHTIG: Nenne JEDE betroffene Datei im Format [DATEI:dateiname.ext]!

BEISPIELE fuer korrektes Feedback:
- "ModuleNotFoundError: No module named 'flask'"
  -> URSACHE: flask fehlt in requirements.txt
  -> BETROFFENE DATEIEN: [DATEI:requirements.txt]
  -> LOESUNG: Fuege 'flask' zu requirements.txt hinzu

- "SyntaxError: unexpected indent in line 15"
  -> URSACHE: Einrueckungsfehler in Zeile 15
  -> BETROFFENE DATEIEN: [DATEI:app.py]
  -> LOESUNG: Korrigiere die Einrueckung in Zeile 15

- "ImportError: cannot import name 'Config' from 'config'"
  -> URSACHE: Klasse Config existiert nicht in config.py
  -> BETROFFENE DATEIEN: [DATEI:config.py]
  -> LOESUNG: Erstelle die Config-Klasse in config.py

VERBOTEN - Niemals solches Feedback geben:
- "Die Docker-Tests sind fehlgeschlagen, was darauf hindeutet..."
- "Es gibt Probleme mit der Konfiguration"
- Unspezifische Aussagen ohne konkrete Dateinennung
- OK sagen wenn Fehler im SANDBOX/DOCKER-ERGEBNIS vorhanden sind

Wenn der Code FEHLERFREI ist und alle Tests bestanden: Antworte mit "OK"
"""
    manager._update_worker_status("reviewer", "working", "Pruefe Code...", manager.model_router.get_model("reviewer") if manager.model_router else "")

    # AENDERUNG 08.02.2026: Nur noch agent_timeouts Dict (globales agent_timeout_seconds entfernt)
    agent_timeouts = manager.config.get("agent_timeouts", {})
    REVIEWER_TIMEOUT_SECONDS = agent_timeouts.get("reviewer", 1200)

    # AENDERUNG 21.02.2026: Multi-Tier Claude SDK (zentrale Helper-Funktion)
    from .claude_sdk import run_sdk_with_retry
    sdk_result = None
    try:
        sdk_result = run_sdk_with_retry(
            manager, role="reviewer", prompt=r_prompt,
            timeout_seconds=REVIEWER_TIMEOUT_SECONDS,
            agent_display_name="Reviewer"
        )
    except Exception as sdk_error:
        manager._ui_log("Reviewer", "Error", f"Reviewer SDK error: {sdk_error}")
        manager._update_worker_status("reviewer", "idle")
    if sdk_result and not is_empty_or_invalid_response(sdk_result):
        # Claude SDK Review erfolgreich — Ergebnis-Parsing
        sdk_result = truncate_review_output(sdk_result, max_length=3000)
        sdk_config = manager.config.get("claude_sdk", {})
        claude_model = sdk_config.get("agent_models", {}).get("reviewer", sdk_config.get("default_model", "sonnet"))
        reviewer_model = f"claude-sdk/{claude_model}"
        review_verdict = "OK" if "OK" in sdk_result.upper() and not sandbox_failed else "FEEDBACK"
        is_approved = review_verdict == "OK" and not sandbox_failed
        human_summary = create_human_readable_verdict(review_verdict, sandbox_failed, sdk_result)

        manager._ui_log("Reviewer", "ReviewOutput", json.dumps({
            "verdict": review_verdict,
            "isApproved": is_approved,
            "humanSummary": human_summary,
            "feedback": sdk_result if review_verdict == "FEEDBACK" else "",
            "model": reviewer_model,
            "iteration": manager.iteration + 1,
            "maxIterations": manager.max_retries,
            "sandboxStatus": "PASS" if not sandbox_failed else "FAIL",
            "sandboxResult": sandbox_result[:500] if sandbox_result else "",
            "testSummary": test_summary[:500] if test_summary else "",
            "reviewOutput": sdk_result if sdk_result else ""
        }, ensure_ascii=False))
        manager._update_worker_status("reviewer", "idle")
        return sdk_result, review_verdict, human_summary

    # Bestehender OpenRouter/CrewAI Pfad (Fallback oder primaerer Pfad wenn Claude SDK deaktiviert)
    MAX_REVIEW_RETRIES = 6  # Erhoeht: 2 Versuche pro Modell x 3 Modelle
    # AENDERUNG 29.01.2026: Modellwechsel erst nach X gleichen Fehlern
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
            # AENDERUNG 29.01.2026: Heartbeat-Wrapper fuer stabile WebSocket-Verbindung
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

                # Bei neuem Fehlertyp: Tracker zuruecksetzen
                if last_error_type and last_error_type != error_type:
                    error_tracker = {}
                last_error_type = error_type

                error_tracker[error_key] = error_tracker.get(error_key, 0) + 1
                error_count = error_tracker[error_key]

                manager._ui_log("Reviewer", "NoResponse",
                                f"Modell {current_model} lieferte keine Antwort (Fehler {error_count}/{ERRORS_BEFORE_MODEL_SWITCH})")

                # Erst nach ERRORS_BEFORE_MODEL_SWITCH gleichen Fehlern Modell wechseln
                if error_count >= ERRORS_BEFORE_MODEL_SWITCH:
                    manager._ui_log("Reviewer", "Status", f"Modellwechsel nach {error_count} gleichen Fehlern")
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
                    error_tracker = {}  # Tracker zuruecksetzen nach Modellwechsel
                continue
            break
        except TimeoutError as te:
            # AENDERUNG 02.02.2026: OpenRouter-Fehler = sofortiger Modellwechsel
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
                error_tracker = {}  # Tracker zuruecksetzen nach Modellwechsel
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

            manager._ui_log("Reviewer", "Timeout",
                            f"Reviewer-Modell {current_model} timeout nach {REVIEWER_TIMEOUT_SECONDS}s (Fehler {error_count}/{ERRORS_BEFORE_MODEL_SWITCH})")

            # Erst nach ERRORS_BEFORE_MODEL_SWITCH gleichen Fehlern Modell wechseln
            if error_count >= ERRORS_BEFORE_MODEL_SWITCH:
                manager._ui_log("Reviewer", "Status", f"Modellwechsel nach {error_count} Timeouts")
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
                error_tracker = {}  # Tracker zuruecksetzen nach Modellwechsel
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
                error_tracker = {}  # Tracker zuruecksetzen
                continue
            # AENDERUNG 07.02.2026: litellm-interne Fehler abfangen statt DevLoop crashen
            # ROOT-CAUSE-FIX:
            # Symptom: AttributeError: 'Exception' object has no attribute 'request' (litellm Bug)
            # Ursache: litellm exception_mapping_utils.py erwartet HTTPStatusError, bekommt generische Exception
            # Loesung: Behandle als Model-Fehler -> Modellwechsel + Retry statt DevLoop-Crash
            error_type = "model_error"
            error_key = (current_model, error_type)
            if last_error_type and last_error_type != error_type:
                error_tracker = {}
            last_error_type = error_type
            error_tracker[error_key] = error_tracker.get(error_key, 0) + 1
            error_count = error_tracker[error_key]
            manager._ui_log("Reviewer", "ModelError",
                            f"Unerwarteter Fehler bei {current_model}: {type(error).__name__}: {str(error)[:200]} "
                            f"(Fehler {error_count}/{ERRORS_BEFORE_MODEL_SWITCH})")
            if error_count >= ERRORS_BEFORE_MODEL_SWITCH:
                manager._ui_log("Reviewer", "Status", f"Modellwechsel nach {error_count} Fehlern")
                manager.model_router.mark_rate_limited_sync(current_model)
                # AENDERUNG 06.02.2026: tech_blueprint fuer Tech-Stack-Kontext
                agent_reviewer = init_agents(
                    manager.config, project_rules, router=manager.model_router,
                    include=["reviewer"],
                    tech_blueprint=getattr(manager, 'tech_blueprint', None)
                ).get("reviewer")
                manager.agent_reviewer = agent_reviewer
                error_tracker = {}
            continue

    if is_empty_or_invalid_response(review_output):
        review_output = "FEHLER: Alle Review-Modelle haben versagt. Bitte pruefe die API-Verbindung und Modell-Verfuegbarkeit."
        manager._ui_log("Reviewer", "AllModelsFailed", "Kein Modell konnte eine gueltige Antwort liefern.")

    # AENDERUNG 31.01.2026: Review-Output Truncation gegen Wiederholungsschleifen
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

