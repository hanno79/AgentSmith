# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 31.01.2026
Version: 1.0
Beschreibung: Feedback-Funktionen für DevLoop.
              Extrahiert aus dev_loop_steps.py (Regel 1: Max 500 Zeilen)
              Enthält: Feedback-Builder, Modellwechsel-Logik
              ÄNDERUNG 30.01.2026: HELP_NEEDED Events bei kritischen Security-Issues
              AENDERUNG 31.01.2026: Fehler-Modell-Historie zur Vermeidung von Ping-Pong
"""

import json
from typing import Dict, Any, List, Tuple

from .orchestration_helpers import format_test_feedback
from .agent_message import create_help_needed
from .agent_factory import init_agents
from .dev_loop_helpers import hash_error


def build_feedback(
    manager,
    review_output: str,
    review_verdict: str,  # ÄNDERUNG 31.01.2026: review_verdict hinzugefügt
    sandbox_failed: bool,
    sandbox_result: str,
    test_summary: str,
    test_result: Dict[str, Any],
    security_passed: bool,
    security_rescan_vulns: List[Dict[str, Any]]
) -> str:
    """
    Erstellt Feedback fuer den naechsten Coder-Iterationen.

    Args:
        review_verdict: "OK" oder "FEEDBACK" - das Urteil des Reviewers
    """
    feedback = ""
    if not security_passed and security_rescan_vulns:
        security_feedback = "\n".join([
            f"- [{v.get('severity', 'unknown').upper()}] {v.get('description', '')}\n"
            f"  → LÖSUNG: {v.get('fix', 'Bitte beheben')}"
            for v in security_rescan_vulns
        ])
        feedback = f"⚠️ SECURITY VULNERABILITIES - MÜSSEN ZUERST BEHOBEN WERDEN:\n{security_feedback}\n\n"
        feedback += "WICHTIG: Implementiere die Lösungsvorschläge (→ LÖSUNG) für JEDE Vulnerability!\n"
        feedback += "Der Code wird erst akzeptiert wenn alle Security-Issues behoben sind.\n"
        manager._ui_log("Security", "BlockingIssues", f"❌ {len(security_rescan_vulns)} Vulnerabilities blockieren Abschluss")

        # ÄNDERUNG 30.01.2026: HELP_NEEDED bei kritischen Security-Vulnerabilities
        critical_vulns = [v for v in security_rescan_vulns if v.get('severity', '').lower() in ('critical', 'high')]
        if critical_vulns:
            help_msg = create_help_needed(
                agent="Security",
                reason="critical_vulnerabilities",
                context={
                    "count": len(critical_vulns),
                    "total_vulns": len(security_rescan_vulns),
                    "vulnerabilities": critical_vulns[:5],  # Max 5 für UI
                    "iteration": getattr(manager, '_current_iteration', 0)
                },
                action_required="security_review_required",
                priority="critical" if any(v.get('severity', '').lower() == 'critical' for v in critical_vulns) else "high"
            )
            manager._ui_log(*help_msg.to_legacy())

        # ÄNDERUNG 30.01.2026: NICHT sofort returnen! Unit-Test-HELP_NEEDED muss IMMER geprüft werden
        # Prüfe Unit-Tests auch bei Security-Issues (für HELP_NEEDED Event)
        unit_tests = test_result.get("unit_tests", {})
        if unit_tests.get("status") == "SKIP":
            # HELP_NEEDED Event senden (auch wenn Security-Issues vorliegen)
            help_msg = create_help_needed(
                agent="Tester",
                reason="no_unit_tests",
                context={
                    "expected_files": ["tests/test_*.py"],
                    "project_type": manager.tech_blueprint.get("project_type", "unknown"),
                    "iteration": getattr(manager, '_current_iteration', 0)
                },
                action_required="create_test_files",
                priority="normal"
            )
            manager._ui_log(*help_msg.to_legacy())

        return feedback

    # ÄNDERUNG 29.01.2026: Unit-Test-Skip ins Feedback aufnehmen (wenn KEINE Security-Issues)
    unit_tests = test_result.get("unit_tests", {})
    if unit_tests.get("status") == "SKIP":
        skip_feedback = "\n🧪 UNIT-TESTS FEHLEN:\n"
        skip_feedback += "Es wurden keine Unit-Tests gefunden (tests/ Verzeichnis oder *_test.py Dateien).\n"
        skip_feedback += "PFLICHT: Erstelle Unit-Tests für alle Funktionen:\n"
        skip_feedback += "- Datei: tests/test_<modulname>.py (für pytest)\n"
        skip_feedback += "- Mindestens 3 Test-Cases pro Funktion (normal, edge-case, error-case)\n"
        skip_feedback += "- Format: ### FILENAME: tests/test_<modulname>.py\n\n"

        # ÄNDERUNG 30.01.2026: HELP_NEEDED bei fehlenden Unit-Tests (nicht blockierend)
        help_msg = create_help_needed(
            agent="Tester",
            reason="no_unit_tests",
            context={
                "expected_files": ["tests/test_*.py"],
                "project_type": manager.tech_blueprint.get("project_type", "unknown"),
                "iteration": getattr(manager, '_current_iteration', 0)
            },
            action_required="create_test_files",
            priority="normal"  # Nicht blockierend, nur Warnung
        )
        manager._ui_log(*help_msg.to_legacy())

        if not sandbox_failed:
            return skip_feedback

    if sandbox_failed:
        # ÄNDERUNG 31.01.2026: Test-Fehler nach Typ differenzieren
        # Gibt dem Coder spezifischere Anleitung je nach Fehlerart
        unit_tests = test_result.get("unit_tests", {})
        ui_tests = test_result.get("ui_tests", {})
        sandbox_lower = sandbox_result.lower()

        # Fehlertyp erkennen und spezifische Meldung generieren
        if any(err in sandbox_lower for err in ["syntaxerror", "indentationerror", "invalid syntax", "unexpected indent"]):
            feedback = "SYNTAX-FEHLER: Der Code enthaelt Syntaxfehler.\n"
            feedback += "Bitte pruefe die Einrueckung und Syntax sorgfaeltig:\n\n"
        elif any(err in sandbox_lower for err in ["nameerror", "attributeerror", "typeerror", "importerror", "modulenotfounderror"]):
            feedback = "LAUFZEIT-FEHLER: Der Code hat Referenz- oder Typfehler.\n"
            feedback += "Bitte pruefe Variablennamen, Importe und Typen:\n\n"
        elif unit_tests.get("status") == "FAIL":
            feedback = "UNIT-TEST-FEHLER: Die Unit-Tests sind fehlgeschlagen.\n"
            feedback += "Bitte analysiere die Testausgabe und behebe die Fehler:\n\n"
        elif ui_tests.get("status") in ["FAIL", "ERROR"]:
            feedback = "UI-TEST-FEHLER: Die UI-Tests haben Probleme erkannt.\n"
            feedback += "Bitte pruefe die Benutzeroberflaeche und Rendering:\n\n"
        else:
            feedback = "FEHLER: Die Sandbox oder der Tester hat Probleme gemeldet.\n"
            feedback += "Bitte analysiere die Fehlermeldungen und behebe sie:\n\n"

        feedback += f"SANDBOX:\n{sandbox_result}\n\n"

        # ÄNDERUNG 31.01.2026: Reviewer-Analyse immer einbauen wenn vorhanden
        # Der Reviewer identifiziert oft die Lösung (z.B. Unicode-Ersetzung),
        # diese muss dem Coder auch bei Sandbox-Fehlern mitgeteilt werden
        if review_output and len(review_output.strip()) > 50:
            # Kürzen um Tokenverbrauch zu begrenzen, aber Essenz behalten
            reviewer_analysis = review_output[:2000]
            feedback += f"REVIEWER-ANALYSE:\n{reviewer_analysis}\n\n"

        # Unit-Test-Skip auch bei Sandbox-Fehler erwähnen
        if unit_tests.get("status") == "SKIP":
            feedback += "\n🧪 ZUSÄTZLICH: Unit-Tests fehlen! Erstelle tests/test_*.py mit pytest-Tests.\n"

        structured_test_feedback = format_test_feedback(test_result)
        if structured_test_feedback and "✅" not in structured_test_feedback:
            feedback += f"\n{structured_test_feedback}\n"
        else:
            feedback += f"TESTER:\n{test_summary}\n"

        test_lower = test_summary.lower()
        if "leere seite" in test_lower or "leer" in test_lower or "kein sichtbar" in test_lower:
            feedback += "\nDIAGNOSE - LEERE SEITE ERKANNT:\n"
            pt = str(manager.tech_blueprint.get("project_type", "")).lower()
            lang = str(manager.tech_blueprint.get("language", "")).lower()
            if any(kw in pt for kw in ["react", "next", "vue"]) or lang == "javascript":
                feedback += "- Pruefe ob ReactDOM.createRoot() oder ReactDOM.render() korrekt aufgerufen wird\n"
                feedback += "- Pruefe ob die App-Komponente exportiert und importiert wird\n"
                feedback += "- Pruefe ob index.html ein <div id='root'></div> enthaelt\n"
                feedback += "- Pruefe ob <script> Tags korrekte Pfade haben\n"
            elif any(kw in pt for kw in ["flask", "fastapi", "django"]):
                feedback += "- Pruefe ob die Route '/' definiert ist und HTML zurueckgibt\n"
                feedback += "- Pruefe ob Templates im Ordner 'templates/' liegen\n"
                feedback += "- Pruefe ob render_template() den korrekten Dateinamen verwendet\n"
            else:
                feedback += "- Pruefe ob index.html sichtbare HTML-Elemente im <body> hat\n"
                feedback += "- Pruefe ob alle <script src> und <link href> Pfade korrekt sind\n"
                feedback += "- Pruefe ob JavaScript-Code korrekt referenzierte Dateien hat\n"

        if "referenz" in test_lower or "nicht gefunden" in sandbox_result.lower():
            feedback += "\nDATEI-REFERENZEN:\n"
            feedback += "Es fehlen referenzierte Dateien. Stelle sicher, dass alle\n"
            feedback += "in HTML eingebundenen Scripts und Stylesheets auch erstellt werden.\n"
        return feedback

    return review_output


def handle_model_switch(
    manager,
    project_rules: Dict[str, Any],
    current_coder_model: str,
    models_used: List[str],
    failed_attempts_history: List[Dict[str, Any]],
    model_attempt: int,
    max_model_attempts: int,
    feedback: str,
    iteration: int,
    sandbox_result: str = "",
    sandbox_failed: bool = False
) -> Tuple[str, int, List[str], str]:
    """
    Fuehrt Modellwechsel-Logik aus und passt Feedback an.

    AENDERUNG 31.01.2026: Nutzt Fehler-Modell-Historie um Ping-Pong zu vermeiden.
    Wenn ein Modell denselben Fehler nicht beheben kann, wird das naechste
    unversuchte Modell gewaehlt statt zurueck zum ersten zu wechseln.

    Args:
        manager: OrchestrationManager
        project_rules: Projekt-Regeln
        current_coder_model: Aktuelles Coder-Modell
        models_used: Liste der bisher verwendeten Modelle
        failed_attempts_history: Historie fehlgeschlagener Versuche
        model_attempt: Aktueller Versuch mit diesem Modell
        max_model_attempts: Max Versuche pro Modell
        feedback: Bisheriges Feedback
        iteration: Aktuelle Iteration
        sandbox_result: Sandbox-Ausgabe (fuer Error-Hash)
        sandbox_failed: Ob Sandbox fehlgeschlagen ist

    Returns:
        Tuple: (neues_modell, reset_attempt, models_used, angepasstes_feedback)
    """
    if model_attempt < max_model_attempts:
        return current_coder_model, model_attempt, models_used, feedback

    old_model = current_coder_model

    # AENDERUNG 31.01.2026: Berechne Error-Hash fuer Fehler-Modell-Historie
    error_hash = ""
    if sandbox_failed and sandbox_result:
        error_hash = hash_error(feedback + sandbox_result)

    if error_hash:
        # Markiere dass dieses Modell diesen Fehler versucht hat
        manager.model_router.mark_error_tried(error_hash, old_model)
        # Hole naechstes Modell das diesen Fehler NICHT versucht hat
        current_coder_model = manager.model_router.get_model_for_error("coder", error_hash)

        manager._ui_log("Coder", "ErrorHistory", json.dumps({
            "error_hash": error_hash,
            "old_model": old_model,
            "new_model": current_coder_model,
            "tried_models": list(manager.model_router.error_model_history.get(error_hash, set()))
        }, ensure_ascii=False))
    else:
        # Fallback auf Rate-Limit-basiertes Switching (kein spezifischer Fehler)
        manager.model_router.mark_rate_limited_sync(current_coder_model)
        current_coder_model = manager.model_router.get_model("coder")

    if current_coder_model != old_model:
        models_used.append(current_coder_model)
        model_attempt = 0
        # AENDERUNG 06.02.2026: tech_blueprint fuer Tech-Stack-Kontext
        manager.agent_coder = init_agents(
            manager.config,
            project_rules,
            router=manager.model_router,
            include=["coder"],
            tech_blueprint=getattr(manager, 'tech_blueprint', None)
        ).get("coder")

        manager._ui_log("Coder", "ModelSwitch", json.dumps({
            "old_model": old_model,
            "new_model": current_coder_model,
            "reason": "max_attempts_reached",
            "attempt": max_model_attempts,
            "models_used": models_used,
            "failed_attempts": len(failed_attempts_history),
            "error_hash": error_hash if error_hash else "none"
        }, ensure_ascii=False))

        # ÄNDERUNG 03.02.2026: ROOT-CAUSE-FIX für FullMode nach Modellwechsel
        # Symptom: Nach Modellwechsel wurde FullMode aktiviert obwohl PatchMode aktiv war
        # Ursache: Das Modellwechsel-Feedback überschrieb das Original-Feedback mit den
        #          Error-Indikatoren (TypeError, NameError, etc.), wodurch _is_targeted_fix_context()
        #          False zurückgab und FullMode verwendet wurde
        # Lösung: Modellwechsel-Info PREPENDEN statt appenden - Original-Feedback bleibt erhalten
        history_summary = "\n".join([
            f"- Modell '{a['model']}' (Iteration {a['iteration']}): {a['feedback'][:200]}"
            for a in failed_attempts_history[-3:]
        ])
        model_switch_info = f"🔄 MODELLWECHSEL: {old_model} -> {current_coder_model}\n"
        model_switch_info += "HINWEIS: Bisherige Ansaetze haben nicht funktioniert. "
        model_switch_info += "Versuche einen anderen Ansatz fuer die folgenden Fehler.\n"
        model_switch_info += f"BISHERIGE VERSUCHE:\n{history_summary}\n\n"
        # Prepend statt append - Original-Feedback mit Error-Indikatoren bleibt erhalten!
        feedback = model_switch_info + feedback

        manager._ui_log("Coder", "Status", f"🔄 Modellwechsel: {old_model} -> {current_coder_model} (Versuch {len(models_used)})")
    else:
        manager._ui_log("Coder", "Warning", f"Kein weiteres Modell verfuegbar - fahre mit {current_coder_model} fort")

    return current_coder_model, model_attempt, models_used, feedback
