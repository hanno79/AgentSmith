# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 08.02.2026
Version: 1.0
Beschreibung: Vier-Augen-Prinzip - Second Opinion Review mit alternativem LLM-Modell.
              Wird nach positivem Primary-Review aufgerufen.
              Nur wenn BEIDE Modelle "OK" sagen, gilt der Code als akzeptiert.
"""

import json
import logging
from typing import Tuple, Dict, Any

from crewai import Task

from .agent_factory import init_agents
from .heartbeat_utils import run_with_heartbeat
# AENDERUNG 08.02.2026: Korrekter Import-Pfad (war dev_loop_helpers, ist orchestration_helpers)
from .orchestration_helpers import is_empty_or_invalid_response

logger = logging.getLogger(__name__)


def run_second_opinion_review(
    manager,
    project_rules: Dict[str, Any],
    current_code: str,
    sandbox_result: str,
    test_summary: str,
    sandbox_failed: bool,
    primary_model: str
) -> Tuple[bool, str, str]:
    """
    Vier-Augen-Prinzip: Zweite Meinung mit anderem LLM-Modell.

    AENDERUNG 08.02.2026: Fix 24 - Vier-Augen-Prinzip
    Symptom: Code wird nur von EINEM Modell reviewed → blinde Flecken moeglich
    Ursache: Kein Second-Opinion-Mechanismus
    Loesung: Nach Primary-OK automatisch Fallback-Modell als Gegencheck

    Args:
        manager: DevLoop Manager mit model_router, config, etc.
        project_rules: Projekt-Regeln fuer den Reviewer
        current_code: Aktueller Code-Stand
        sandbox_result: Sandbox-Ergebnis
        test_summary: Test-Zusammenfassung
        sandbox_failed: Ob Sandbox fehlgeschlagen ist
        primary_model: Das Modell das den Primary-Review gemacht hat

    Returns:
        Tuple[agrees, second_verdict, second_model]:
        - agrees: True wenn Second Opinion mit Primary uebereinstimmt
        - second_verdict: "OK" oder "FEEDBACK"
        - second_model: Name des Second-Opinion-Modells
    """
    vier_augen_config = manager.config.get("vier_augen", {})
    skip_on_error = vier_augen_config.get("skip_on_error", True)
    timeout_factor = vier_augen_config.get("timeout_factor", 0.5)

    manager._ui_log("SecondOpinion", "Start",
                    f"Vier-Augen-Prinzip: Hole zweite Meinung (Primary: {primary_model})")

    # Timeout: Faktor des Primary-Reviewer-Timeouts
    agent_timeouts = manager.config.get("agent_timeouts", {})
    # AENDERUNG 08.02.2026: Nur noch agent_timeouts Dict (globales agent_timeout_seconds entfernt)
    base_timeout = agent_timeouts.get("reviewer", 1200)
    second_timeout = max(120, int(base_timeout * timeout_factor))

    try:
        # 1. Primary-Modell temporaer sperren → Fallback wird gewaehlt
        manager.model_router.mark_rate_limited_sync(primary_model)

        # 2. Neuen Reviewer-Agent mit Fallback-Modell erstellen
        second_reviewer = init_agents(
            manager.config,
            project_rules,
            router=manager.model_router,
            include=["reviewer"],
            tech_blueprint=getattr(manager, 'tech_blueprint', None)
        ).get("reviewer")

        if not second_reviewer:
            logger.warning("Vier-Augen: Kein Second-Opinion Reviewer verfuegbar")
            _restore_primary_model(manager, primary_model)
            return True, "OK", "keiner"

        # 3. Second-Opinion-Modell ermitteln
        second_model = manager.model_router.get_model("reviewer")

        # Pruefe: Ist es tatsaechlich ein ANDERES Modell?
        if second_model == primary_model:
            logger.info("Vier-Augen: Kein alternatives Modell verfuegbar, ueberspringe")
            manager._ui_log("SecondOpinion", "Skip",
                            "Kein alternatives Modell verfuegbar - Primary-Verdict gilt")
            _restore_primary_model(manager, primary_model)
            return True, "OK", primary_model

        manager._ui_log("SecondOpinion", "Model",
                        f"Second Opinion durch: {second_model}")

        # 4. Review-Prompt (identisch zum Primary, aber mit Vier-Augen-Hinweis)
        review_prompt = _build_second_opinion_prompt(
            current_code, sandbox_result, test_summary, sandbox_failed
        )

        task_review = Task(
            description=review_prompt,
            expected_output="OK/Feedback",
            agent=second_reviewer
        )

        # 5. Review ausfuehren
        review_output = run_with_heartbeat(
            func=lambda: str(task_review.execute_sync()),
            ui_log_callback=manager._ui_log,
            agent_name="SecondOpinion",
            task_description=f"Vier-Augen Review ({second_model})",
            heartbeat_interval=15,
            timeout_seconds=second_timeout
        )

        # 6. Primary-Modell wieder freigeben
        _restore_primary_model(manager, primary_model)

        # 7. Verdict auswerten
        if is_empty_or_invalid_response(review_output):
            logger.warning("Vier-Augen: Second Opinion lieferte keine Antwort")
            manager._ui_log("SecondOpinion", "NoResponse",
                            f"Modell {second_model} lieferte keine Antwort - Primary-Verdict gilt")
            return True, "OK", second_model

        second_verdict = "OK" if "OK" in review_output.upper() and not sandbox_failed else "FEEDBACK"

        # 8. Ergebnis loggen
        agrees = second_verdict == "OK"
        manager._ui_log("SecondOpinion", "Result", json.dumps({
            "primaryModel": primary_model,
            "secondModel": second_model,
            "secondVerdict": second_verdict,
            "agrees": agrees,
            "feedback": review_output[:300] if not agrees else ""
        }, ensure_ascii=False))

        if not agrees:
            manager._ui_log("SecondOpinion", "Dissent",
                            f"Zweite Meinung ({second_model}) widerspricht: {review_output[:200]}")

        return agrees, second_verdict if not agrees else review_output, second_model

    except Exception as e:
        logger.warning(f"Vier-Augen: Fehler bei Second Opinion: {e}")
        _restore_primary_model(manager, primary_model)

        if skip_on_error:
            manager._ui_log("SecondOpinion", "Error",
                            f"Second Opinion fehlgeschlagen ({e}) - Primary-Verdict gilt")
            return True, "OK", "fehler"
        else:
            manager._ui_log("SecondOpinion", "Error",
                            f"Second Opinion fehlgeschlagen ({e}) - Iteration wird wiederholt")
            return False, "FEEDBACK", "fehler"


def _restore_primary_model(manager, primary_model: str):
    """Stellt das Primary-Modell nach dem Second-Opinion-Review wieder her."""
    try:
        manager.model_router.mark_success(primary_model)
        # Direkt aus rate_limited_models entfernen falls noch vorhanden
        if primary_model in manager.model_router.rate_limited_models:
            del manager.model_router.rate_limited_models[primary_model]
    except Exception as e:
        logger.warning(f"Vier-Augen: Fehler beim Wiederherstellen des Primary-Modells: {e}")


def _build_second_opinion_prompt(
    current_code: str, sandbox_result: str,
    test_summary: str, sandbox_failed: bool
) -> str:
    """Baut den Prompt fuer die zweite Meinung."""
    # AENDERUNG 08.02.2026: Vier-Augen Review-Prompt
    prompt = f"""Du bist ein unabhaengiger Code-Reviewer (Vier-Augen-Prinzip).
Ein anderer Reviewer hat diesen Code bereits als "OK" bewertet.
Deine Aufgabe: Pruefe den Code UNABHAENGIG und kritisch.

WICHTIG: Antworte NUR mit "OK" wenn der Code WIRKLICH fehlerfrei ist.
Bei JEDEM Problem antworte mit konkretem Feedback.

=== CODE ===
{current_code[:8000]}

=== SANDBOX-ERGEBNIS ===
{"FEHLGESCHLAGEN" if sandbox_failed else "ERFOLGREICH"}
{sandbox_result[:2000] if sandbox_result else "Kein Ergebnis"}

=== TEST-ZUSAMMENFASSUNG ===
{test_summary[:1000] if test_summary else "Keine Tests"}

Pruefe besonders:
1. Logik-Fehler und Edge-Cases
2. Sicherheitsprobleme (SQL Injection, XSS, etc.)
3. Fehlende Fehlerbehandlung
4. Import-Fehler und fehlende Abhaengigkeiten
5. Inkonsistenzen zwischen Dateien

Antworte mit "OK" wenn alles korrekt ist, oder mit detailliertem Feedback."""

    return prompt
