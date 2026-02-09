# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 08.02.2026
Version: 1.0
Beschreibung: External Bureau Review (CodeRabbit) fuer DevLoop.
              Synchroner Wrapper fuer den async ExternalBureauManager.
              Wird nach positivem Primary-Review + Vier-Augen aufgerufen.
              AENDERUNG 08.02.2026: Fix 33 - CodeRabbit Integration in DevLoop
"""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Tuple, List, Dict, Any

logger = logging.getLogger(__name__)


def run_external_review(
    manager,
    created_files: list
) -> Tuple[bool, str, List[Dict[str, Any]]]:
    """
    Fuehrt externes CodeRabbit-Review aus.

    AENDERUNG 08.02.2026: Fix 33 - CodeRabbit External Review
    Symptom: Code wird nur von internen LLM-Reviewern geprueft
    Ursache: External Bureau Infrastruktur gebaut aber nie aus DevLoop aufgerufen
    Loesung: Synchroner Wrapper der run_review_specialists() nach Vier-Augen aufruft

    Args:
        manager: OrchestrationManager mit external_bureau
        created_files: Liste der generierten Dateipfade

    Returns:
        Tuple[passed, feedback_text, findings_list]:
        - passed: True wenn keine CRITICAL/HIGH Findings
        - feedback_text: Formatiertes Feedback fuer den Coder
        - findings_list: Rohe Findings als Dict-Liste fuer Logging
    """
    # 1. Pruefe ob External Bureau verfuegbar und konfiguriert
    if not hasattr(manager, 'external_bureau') or not manager.external_bureau:
        logger.debug("External Review: Kein External Bureau verfuegbar")
        return True, "", []

    ext_cfg = manager.config.get("external_specialists", {})
    if not ext_cfg.get("enabled", False):
        logger.debug("External Review: External Bureau deaktiviert")
        return True, "", []

    # 2. Pruefe ob CodeRabbit konfiguriert und aktiv
    coderabbit_cfg = ext_cfg.get("coderabbit", {})
    if not coderabbit_cfg.get("enabled", False):
        logger.debug("External Review: CodeRabbit deaktiviert")
        return True, "", []

    skip_on_error = coderabbit_cfg.get("skip_on_error", True)
    mode = coderabbit_cfg.get("mode", "advisory")

    manager._ui_log("CodeRabbit", "Start", "External Bureau Review gestartet...")
    manager._update_worker_status("external_bureau", "working", "CodeRabbit Review", "coderabbit-cli")

    try:
        # 3. Context-Dict fuer den Specialist bauen
        context = {
            "project_path": str(manager.project_path) if manager.project_path else "",
            "files": [f for f in (created_files or []) if f],
            "code": manager.current_code[:10000] if manager.current_code else "",
            "tech_blueprint": getattr(manager, 'tech_blueprint', {})
        }

        # 4. Async-zu-Sync Bridge via ThreadPoolExecutor
        # Gleicher Ansatz wie run_with_heartbeat() - vermeidet Event-Loop-Konflikte
        results = _run_async_review(manager.external_bureau, context)

        # 5. Findings aus allen Results sammeln
        all_findings = []
        for result in results:
            if not result.success:
                logger.warning(f"External Review: Specialist-Fehler: {result.error}")
                continue
            for finding in result.findings:
                all_findings.append({
                    "severity": finding.severity.lower(),
                    "description": finding.description,
                    "file": finding.file,
                    "line": finding.line,
                    "fix": finding.fix,
                    "category": finding.category
                })

        # 6. Feedback-Text fuer den Coder formatieren
        feedback_lines = []
        blocking_findings = []
        for f in all_findings:
            severity = f["severity"].upper()
            file_ref = f"[DATEI:{f['file']}] " if f.get("file") else ""
            fix_hint = f" | FIX: {f['fix']}" if f.get("fix") else ""
            line = f"[CodeRabbit] {file_ref}{f['description']}{fix_hint} | SEVERITY: {severity}"
            feedback_lines.append(line)
            if severity in ("CRITICAL", "HIGH"):
                blocking_findings.append(f)

        feedback_text = "\n".join(feedback_lines) if feedback_lines else ""

        # 7. Pass/Fail Entscheidung: Nur blocking mode blockiert bei CRITICAL/HIGH
        if mode == "blocking":
            passed = len(blocking_findings) == 0
        else:
            # Advisory Mode: Feedback wird angezeigt aber blockiert nicht
            passed = True

        manager._ui_log("CodeRabbit", "ReviewResult", f"Findings: {len(all_findings)} gesamt, "
                        f"{len(blocking_findings)} blockierend, Mode: {mode}, Passed: {passed}")
        manager._update_worker_status("external_bureau", "idle")

        return passed, feedback_text, all_findings

    except Exception as e:
        logger.warning(f"External Review Fehler: {e}")
        manager._ui_log("CodeRabbit", "Error", f"External Review fehlgeschlagen: {e}")
        manager._update_worker_status("external_bureau", "idle")

        if skip_on_error:
            manager._ui_log("CodeRabbit", "Skip", "Fehler uebersprungen - Primary-Verdict gilt")
            return True, "", []
        else:
            return False, f"[CodeRabbit] Review-Fehler: {e}", []


def _run_async_review(external_bureau, context: Dict[str, Any]) -> list:
    """
    Fuehrt die async run_review_specialists() synchron aus.

    Verwendet ThreadPoolExecutor mit asyncio.run() im Thread
    um Event-Loop-Konflikte mit dem Haupt-Thread zu vermeiden.

    Args:
        external_bureau: ExternalBureauManager Instanz
        context: Context-Dict fuer den Specialist

    Returns:
        Liste von SpecialistResult Objekten
    """
    def _async_runner():
        return asyncio.run(external_bureau.run_review_specialists(context))

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_async_runner)
        # Timeout aus Config oder 120s Default
        timeout = external_bureau.config.get("coderabbit", {}).get("timeout_seconds", 120)
        return future.result(timeout=timeout)
