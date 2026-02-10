# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 08.02.2026
Version: 1.0
Beschreibung: Security-Rescan-Funktion fuer DevLoop mit Retry-Logik.
              Extrahiert aus dev_loop_validators.py (Regel 1: Max 500 Zeilen)
              Enthaelt: run_security_rescan
              AENDERUNG 08.02.2026: Modul-Extraktion aus dev_loop_validators.py
"""

import json
import os
import logging
from datetime import datetime
from typing import Dict, Any, List, Tuple

from crewai import Task

from .agent_factory import init_agents
from .orchestration_helpers import (
    is_rate_limit_error,
    is_model_unavailable_error,
    is_empty_response_error,
    extract_vulnerabilities
)
from .heartbeat_utils import run_with_heartbeat

logger = logging.getLogger(__name__)


def run_security_rescan(manager, project_rules: Dict[str, Any], current_code: str, iteration: int) -> Tuple[bool, List[Dict[str, Any]]]:
    """
    Fuehrt Security-Rescan fuer den generierten Code aus.
    AENDERUNG 30.01.2026: Retry/Fallback bei 404/Rate-Limit Fehlern hinzugefuegt.
    """
    security_passed = True
    security_rescan_vulns = []
    MAX_SECURITY_RETRIES = 3
    # AENDERUNG 08.02.2026: Nur noch agent_timeouts Dict (globales agent_timeout_seconds entfernt)
    agent_timeouts = manager.config.get("agent_timeouts", {})
    SECURITY_TIMEOUT = agent_timeouts.get("security", 300)

    if manager.agent_security and current_code:
        manager._ui_log("Security", "RescanStart", f"Pruefe generierten Code (Iteration {iteration + 1})...")

        # AENDERUNG 07.02.2026: Security-Prompt mit [DATEI:...] Pflicht (Fix 20)
        # ROOT-CAUSE-FIX:
        # Symptom: SQL Injection wird erkannt aber nie gefixt (5+ Iterationen)
        # Ursache: Security-Output enthaelt keinen Dateinamen -> affected_file=None
        #          -> Coder bekommt "DATEI: None" -> PatchMode kann keine Dateien extrahieren
        #          -> Fallback auf FullMode -> komplett neuer Code -> selbes Pattern
        # Loesung: Prompt fordert explizit [DATEI:dateiname.js] im Output
        security_rescan_prompt = f"""Pruefe diesen Code auf Sicherheitsprobleme:

{current_code}

ANTWORT-FORMAT (eine Zeile pro Problem):
VULNERABILITY: [DATEI:dateiname.js] [Problem-Beschreibung] | FIX: [Konkrete Loesung mit Code-Beispiel] | SEVERITY: [CRITICAL/HIGH/MEDIUM/LOW]

BEISPIEL:
VULNERABILITY: [DATEI:components/UserForm.js] innerHTML in Zeile 15 ermoeglicht XSS-Angriffe | FIX: Ersetze element.innerHTML = userInput mit element.textContent = userInput oder nutze DOMPurify.sanitize(userInput) | SEVERITY: HIGH

BEISPIEL SQL INJECTION:
VULNERABILITY: [DATEI:pages/api/tasks.js] String-Konkatenation in SQL-Query ermoeglicht SQL Injection | FIX: Verwende parametrisierte Queries: db.prepare('SELECT * FROM tasks WHERE id = ?').get(id) statt db.prepare(`SELECT * FROM tasks WHERE id = ${{id}}`) | SEVERITY: CRITICAL

PRUEFE NUR auf die 3 wichtigsten Kategorien:
1. XSS (innerHTML, document.write, eval mit User-Input)
2. SQL/NoSQL Injection (String-Konkatenation in Queries)
3. Hardcoded Secrets (API-Keys, Passwoerter im Code)

WICHTIG:
- JEDE Vulnerability MUSS mit [DATEI:dateiname] beginnen!
- Bei Taschenrechner-Apps: eval() mit Button-Input ist LOW severity (kein User-Text-Input)
- Bei statischen Webseiten: innerHTML ohne User-Input ist kein Problem
- Gib fuer JEDEN Fix KONKRETEN Code der das Problem loest

Wenn KEINE kritischen Probleme gefunden: Antworte nur mit "SECURE"

WICHTIG - CVE-REGELN:
- Erfinde NIEMALS CVE-Nummern! Nenne nur CVEs die du SICHER kennst.
- Wenn du die CVE-Nummer nicht sicher weisst: Beschreibe das Problem OHNE CVE-Nummer.
- FALSCH: "next@15.1.0 hat CVE-2025-66478" (erfundene Nummer!)
- RICHTIG: "String-Konkatenation in SQL-Query ermoeglicht Injection"
- Fokussiere dich auf CODE-Probleme, nicht auf Versions-CVEs.
"""

        # AENDERUNG 30.01.2026: Retry-Schleife mit Fallback bei 404/Rate-Limit
        for security_attempt in range(MAX_SECURITY_RETRIES):
            current_security_model = manager.model_router.get_model("security") if manager.model_router else "unknown"
            manager._update_worker_status("security", "working",
                f"Security-Scan (Versuch {security_attempt + 1}/{MAX_SECURITY_RETRIES})",
                current_security_model)

            # Neuen Agent mit aktuellem Modell erstellen
            # AENDERUNG 06.02.2026: tech_blueprint fuer Tech-Stack-Kontext
            agent_security = init_agents(
                manager.config,
                project_rules,
                router=manager.model_router,
                include=["security"],
                tech_blueprint=getattr(manager, 'tech_blueprint', None)
            ).get("security")

            task_security_rescan = Task(
                description=security_rescan_prompt,
                expected_output="SECURE oder VULNERABILITY-Liste",
                agent=agent_security
            )

            try:
                security_rescan_result = run_with_heartbeat(
                    func=lambda: str(task_security_rescan.execute_sync()),
                    ui_log_callback=manager._ui_log,
                    agent_name="Security",
                    task_description=f"Security-Scan (Versuch {security_attempt + 1}/{MAX_SECURITY_RETRIES})",
                    heartbeat_interval=15,
                    timeout_seconds=SECURITY_TIMEOUT
                )
                # AENDERUNG 10.02.2026: Fix 44 — existing_files fuer Dateinamen-Validierung
                _existing = []
                if hasattr(manager, 'project_path') and manager.project_path:
                    _proj = str(manager.project_path)
                    if os.path.exists(_proj):
                        _skip = {'node_modules', '.next', '.git', '__pycache__', 'screenshots'}
                        for _r, _d, _f in os.walk(_proj):
                            _d[:] = [d for d in _d if d not in _skip]
                            for fn in _f:
                                _existing.append(
                                    os.path.relpath(os.path.join(_r, fn), _proj).replace("\\", "/")
                                )
                security_rescan_vulns = extract_vulnerabilities(
                    security_rescan_result, existing_files=_existing
                )
                manager.security_vulnerabilities = security_rescan_vulns

                security_passed = not security_rescan_vulns or all(
                    v.get('severity') == 'low' for v in security_rescan_vulns
                )

                rescan_status = "SECURE" if security_passed else "VULNERABLE"

                manager._ui_log("Security", "SecurityRescanOutput", json.dumps({
                    "vulnerabilities": security_rescan_vulns,
                    "overall_status": rescan_status,
                    "scan_type": "code_scan",
                    "iteration": iteration + 1,
                    "blocking": not security_passed,
                    "model": current_security_model,
                    "timestamp": datetime.now().isoformat()
                }, ensure_ascii=False))

                manager._ui_log("Security", "RescanResult", f"Code-Scan: {rescan_status} ({len(security_rescan_vulns)} Findings)")
                manager._update_worker_status("security", "idle")
                break  # Erfolg - Schleife verlassen

            except Exception as sec_err:
                # AENDERUNG 30.01.2026: Retry bei 404/Rate-Limit/Leere Antwort mit Fallback-Modell
                should_retry = (
                    is_rate_limit_error(sec_err) or
                    is_model_unavailable_error(sec_err) or
                    is_empty_response_error(sec_err)
                )
                if should_retry:
                    error_type = "Rate-Limit" if is_rate_limit_error(sec_err) else \
                                 "404/Nicht verfuegbar" if is_model_unavailable_error(sec_err) else \
                                 "Leere Antwort"
                    manager._ui_log("Security", "Warning",
                        f"Security-Modell {current_security_model} {error_type} (Versuch {security_attempt + 1}/{MAX_SECURITY_RETRIES})")
                    manager.model_router.mark_rate_limited_sync(current_security_model)
                    if security_attempt < MAX_SECURITY_RETRIES - 1:
                        manager._ui_log("Security", "Info", "Wechsle zu Fallback-Modell...")
                        continue  # Naechster Versuch mit Fallback

                manager._ui_log("Security", "Error", f"Security-Rescan fehlgeschlagen: {sec_err}")
                manager._update_worker_status("security", "idle")
                # Fail-Closed bei Security-Fehlern
                security_passed = False
                break

    return security_passed, security_rescan_vulns
