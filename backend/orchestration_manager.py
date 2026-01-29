# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 28.01.2026
Version: 2.0
Beschreibung: Orchestration Manager - Backend-Koordination mit LiteLLM Callbacks und Agent-Steuerung.
              ÄNDERUNG 28.01.2026: Library-Manager Integration für Protokollierung aller Agent-Aktionen
              ÄNDERUNG 28.01.2026: Informationsfluss-Reparatur zwischen Agenten:
                                   - Fix 1: Regex-Pattern für VULNERABILITY|FIX|SEVERITY korrigiert
                                   - Fix 3: Feedback-Logik ohne widersprüchliche OK+Security-Signale
                                   - Fix 4: Basis-Security-Hints für Iteration 1 (proaktive Guidance)
              ÄNDERUNG 25.01.2026: TokenMetrics, OK-Erkennung, OfficeManager, Security-Workflow
"""

import os
import json
import yaml
import re
import traceback
import contextvars
import threading
import base64
import logging
from datetime import datetime
from typing import Callable, Optional, Dict, Any, List
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# ÄNDERUNG 28.01.2026: Mapping von Anzeige-Namen zu Session-Keys
AGENT_TO_SESSION_KEY = {
    "Coder": "coder",
    "Reviewer": "reviewer",
    "Tester": "tester",
    "Designer": "designer",
    "Security": "security",
    "Researcher": "researcher",
    "TechArchitect": "techstack",
    "DBDesigner": "dbdesigner"
}

# Lade .env aus dem Projektverzeichnis (nicht CWD!)
# Dies stellt sicher, dass die .env gefunden wird, auch wenn der Server
# aus einem anderen Verzeichnis gestartet wird
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(_project_root, ".env"), override=True)

# Agenten-Struktur (muss evtl. Pfade anpassen)
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.meta_orchestrator_agent import MetaOrchestratorV2
from agents.coder_agent import create_coder
from agents.designer_agent import create_designer
from agents.reviewer_agent import create_reviewer
from agents.orchestrator_agent import create_orchestrator
from agents.researcher_agent import create_researcher
from agents.database_designer_agent import create_database_designer
from agents.techstack_architect_agent import create_techstack_architect
from agents.security_agent import create_security_agent
# ÄNDERUNG 24.01.2026: test_project für intelligente Tests mit tech_blueprint
from agents.tester_agent import create_tester, test_web_ui, test_project, summarize_ui_result
from agents.memory_agent import (
    update_memory, get_lessons_for_prompt, learn_from_error,
    extract_error_pattern, generate_tags_from_context
)
from sandbox_runner import run_sandbox
from logger_utils import log_event
from budget_tracker import get_budget_tracker
from model_router import get_model_router
from .worker_pool import OfficeManager, WorkerStatus
from .library_manager import get_library_manager
from .session_manager import get_session_manager

from crewai import Task

# ÄNDERUNG 24.01.2026: Import aus zentraler file_utils (REGEL 13 - Single Source of Truth)
from file_utils import find_html_file, find_python_entry

# =====================================================================
# LiteLLM Callback für Budget-Tracking
# =====================================================================
try:
    import litellm

    # Context-local Variablen für Thread/Async-Sicherheit
    _current_agent_name_var: contextvars.ContextVar[str] = contextvars.ContextVar('current_agent_name', default="Unknown")
    _current_project_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar('current_project_id', default=None)

    def _budget_tracking_callback(kwargs, completion_response, start_time, end_time):
        """
        LiteLLM success callback - erfasst Token-Nutzung nach jedem API-Call.
        """
        try:
            tracker = get_budget_tracker()
            
            # Lese aus Context-Variablen
            current_agent_name = _current_agent_name_var.get("Unknown")
            current_project_id = _current_project_id_var.get(None)

            # Extrahiere Token-Usage aus der Response
            usage = getattr(completion_response, 'usage', None)
            if usage:
                prompt_tokens = getattr(usage, 'prompt_tokens', 0)
                completion_tokens = getattr(usage, 'completion_tokens', 0)
                model = kwargs.get('model', 'unknown')

                # Erfasse die Nutzung
                tracker.record_usage(
                    agent=current_agent_name,
                    model=model,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    project_id=current_project_id
                )
                print(f"📊 Budget tracked: {current_agent_name} - {prompt_tokens}+{completion_tokens} tokens")
        except Exception as e:
            print(f"⚠️ Budget tracking error: {e}")

    # Registriere den Callback
    litellm.success_callback = [_budget_tracking_callback]
    print("✅ Budget tracking callback registered with LiteLLM")

except ImportError:
    print("⚠️ LiteLLM nicht verfügbar - Budget tracking deaktiviert")
    _current_agent_name_var: contextvars.ContextVar[str] = contextvars.ContextVar('current_agent_name', default="Unknown")
    _current_project_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar('current_project_id', default=None)

def set_current_agent(agent_name: str, project_id: str = None):
    """Setzt den aktuellen Agenten für Budget-Tracking."""
    _current_agent_name_var.set(agent_name)
    if project_id is not None:
        _current_project_id_var.set(project_id)


def run_with_timeout(func, timeout_seconds: int = 60):
    """
    Führt eine Funktion mit Timeout aus.
    Verhindert endloses Blockieren bei langsamen API-Aufrufen oder Netzwerk-Problemen.

    Args:
        func: Die auszuführende Funktion (keine Argumente)
        timeout_seconds: Maximale Ausführungszeit in Sekunden

    Returns:
        Das Ergebnis der Funktion

    Raises:
        TimeoutError: Wenn die Funktion länger als timeout_seconds dauert
        Exception: Wenn die Funktion eine Exception wirft
    """
    result = [None]
    exception = [None]

    def target():
        try:
            result[0] = func()
        except Exception as e:
            exception[0] = e

    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    thread.join(timeout=timeout_seconds)

    if thread.is_alive():
        raise TimeoutError(f"Operation dauerte länger als {timeout_seconds}s und wurde abgebrochen")
    if exception[0]:
        raise exception[0]
    return result[0]


class OrchestrationManager:
    def __init__(self, config_path: str = None):
        # Sicherstellen, dass Basis-Verzeichnisse existieren
        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        os.makedirs(os.path.join(self.base_dir, "projects"), exist_ok=True)
        os.makedirs(os.path.join(self.base_dir, "memory"), exist_ok=True)

        # Verwende absoluten Pfad zur config.yaml wenn kein Pfad angegeben
        if config_path is None:
            config_path = os.path.join(self.base_dir, "config.yaml")
        self.config_path = config_path
        self.config = self._load_config()
        self.project_path = None
        self.output_path = None
        self.tech_blueprint = {}
        self.database_schema = "Kein Datenbank-Schema."
        self.design_concept = "Kein Design-Konzept."
        self.current_code = ""
        self.is_first_run = True
        # ÄNDERUNG 24.01.2026: Security Vulnerabilities für Coder-Feedback
        self.security_vulnerabilities = []
        self.force_security_fix = False  # Flag für manuellen Security-Fix via API

        # ModelRouter für automatisches Fallback bei Rate Limits
        self.model_router = get_model_router(self.config)

        # ÄNDERUNG 25.01.2026: OfficeManager für Worker-Pool-Tracking
        self.office_manager = OfficeManager(
            on_status_change=self._handle_worker_status_change,
            config={
                "coder": {"max_workers": 3},
                "tester": {"max_workers": 2},
                "designer": {"max_workers": 1},
                "db_designer": {"max_workers": 1},
                "security": {"max_workers": 1},
                "researcher": {"max_workers": 1},
                "reviewer": {"max_workers": 1},
                "techstack_architect": {"max_workers": 1},
            }
        )

        # Callback für UI-Updates
        self.on_log: Optional[Callable[[str, str, str], None]] = None

    def _load_config(self):
        with open(self.config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    def _ui_log(self, agent: str, event: str, message: str):
        if self.on_log:
            self.on_log(agent, event, message)
        log_event(agent, event, message)

        # ÄNDERUNG 28.01.2026: Protokollierung in Library Manager
        try:
            library = get_library_manager()
            if library.current_project:
                library.log_entry(
                    from_agent=agent,
                    to_agent="System",
                    entry_type=event,
                    content=message,
                    iteration=getattr(self, '_current_iteration', 0)
                )
        except Exception:
            pass  # Fehler beim Protokollieren sollten nicht den Workflow stoppen

        # ÄNDERUNG 28.01.2026: Session Manager fuer Frontend State-Sync
        try:
            session_mgr = get_session_manager()
            session_mgr.add_log(agent, event, message)

            # Agent-Status aktualisieren wenn relevant
            if event in ("Status", "Working", "Result", "Complete", "Error"):
                agent_lower = agent.lower().replace("-", "").replace(" ", "")
                # ÄNDERUNG 28.01.2026: Session-Key ueber Mapping aufloesen
                session_key = AGENT_TO_SESSION_KEY.get(agent, agent_lower)
                is_active = event in ("Status", "Working")
                session_mgr.set_agent_active(session_key, is_active)
        except Exception:
            pass  # Session-Updates sollten nicht den Workflow stoppen

    # ÄNDERUNG 25.01.2026: Worker-Status-Callback für WebSocket-Events
    async def _handle_worker_status_change(self, data: Dict[str, Any]):
        """
        Callback für Worker-Pool Status-Änderungen.
        Sendet WorkerStatus Event an Frontend via WebSocket.
        """
        if self.on_log:
            # Mapping von Office-Namen zu Agent-Namen für das Frontend
            agent_names = {
                "coder": "Coder",
                "tester": "Tester",
                "designer": "Designer",
                "db_designer": "DBDesigner",
                "security": "Security",
                "researcher": "Researcher",
                "reviewer": "Reviewer",
                "techstack_architect": "TechArchitect"
            }
            agent_name = agent_names.get(data.get("office"), "System")
            self.on_log(agent_name, "WorkerStatus", json.dumps(data, ensure_ascii=False))

    def _update_worker_status(self, office: str, worker_status: str, task_description: str = None, model: str = None):
        """
        Synchrone Helper-Methode zum Aktualisieren des Worker-Status.
        Sendet WorkerStatus Event an Frontend.

        Args:
            office: Name des Office (coder, tester, etc.)
            worker_status: "working" oder "idle"
            task_description: Beschreibung der aktuellen Aufgabe
            model: Verwendetes Modell
        """
        pool = self.office_manager.get_pool(office)
        if pool:
            # Finde ersten verfügbaren Worker
            workers = pool.get_idle_workers() if worker_status == "idle" else pool.get_active_workers()
            if workers or worker_status == "working":
                # Bei "working" den ersten idle Worker nehmen
                if worker_status == "working":
                    idle_workers = pool.get_idle_workers()
                    if idle_workers:
                        worker = idle_workers[0]
                        worker.status = WorkerStatus.WORKING
                        worker.current_task_description = task_description
                        worker.model = model
                    else:
                        return  # Kein Worker verfügbar
                else:
                    # Bei "idle" den ersten arbeitenden Worker auf idle setzen
                    active_workers = pool.get_active_workers()
                    if active_workers:
                        worker = active_workers[0]
                        worker.status = WorkerStatus.IDLE
                        worker.current_task_description = None
                        worker.current_task = None
                        worker.tasks_completed += 1
                    else:
                        return  # Kein aktiver Worker zum Idle-Setzen

            # Agent-Namen Mapping
            agent_names = {
                "coder": "Coder",
                "tester": "Tester",
                "designer": "Designer",
                "db_designer": "DBDesigner",
                "security": "Security",
                "researcher": "Researcher",
                "reviewer": "Reviewer",
                "techstack_architect": "TechArchitect"
            }
            agent_name = agent_names.get(office, "System")

            # WorkerStatus Event senden
            self._ui_log(agent_name, "WorkerStatus", json.dumps({
                "office": office,
                "pool_status": pool.get_status(),
                "event": "task_assigned" if worker_status == "working" else "task_completed"
            }, ensure_ascii=False))

    # ÄNDERUNG 28.01.2026: Strukturiertes Test-Feedback für Coder (Phase 0.12)
    def _format_test_feedback(self, test_result: Dict[str, Any]) -> str:
        """
        Formatiert Test-Ergebnisse als strukturiertes Feedback für den Coder.

        Args:
            test_result: Dictionary mit unit_tests und ui_tests Ergebnissen

        Returns:
            Formatierter Feedback-Text
        """
        lines = []

        # Unit-Tests
        ut = test_result.get("unit_tests", {})
        if ut.get("status") == "FAIL":
            lines.append("🧪 UNIT-TEST FEHLER:")
            failed_count = ut.get("failed_count", 0)
            if failed_count:
                lines.append(f"   {failed_count} Test(s) fehlgeschlagen")
            summary = ut.get("summary", "")
            if summary:
                lines.append(f"   Zusammenfassung: {summary}")
            details = ut.get("details", "")
            if details:
                # Details auf 1500 Zeichen begrenzen für Übersichtlichkeit
                lines.append(f"   Details:\n{details[:1500]}")
            lines.append("")

        # UI-Tests
        ui = test_result.get("ui_tests", {})
        if ui.get("status") in ["FAIL", "ERROR"]:
            lines.append("🖥️ UI-TEST FEHLER:")
            issues = ui.get("issues", [])
            for issue in issues[:5]:  # Max 5 Issues anzeigen
                lines.append(f"   - {issue}")
            if not ui.get("has_visible_content", True):
                lines.append("   ⚠️ LEERE SEITE ERKANNT - kein sichtbarer Inhalt!")
            if len(issues) > 5:
                lines.append(f"   ... und {len(issues) - 5} weitere Probleme")
            lines.append("")

        # Re-Test Hinweis wenn Fehler vorhanden
        if lines:
            lines.append("🔄 RE-TEST ERFORDERLICH:")
            lines.append("Nach deinen Fixes werden die Tests AUTOMATISCH erneut ausgeführt.")
            lines.append("Der Loop läuft bis alle Tests grün sind oder max_iterations erreicht.\n")

        return "\n".join(lines) if lines else "✅ Alle Tests bestanden"

    def _is_rate_limit_error(self, e: Exception) -> bool:
        """
        Prüft, ob eine Exception ein Rate-Limit-Fehler ist.
        ÄNDERUNG 28.01.2026: Server-Fehler (500, 503) sind KEINE Rate-Limits mehr!
        Diese führen nicht mehr zu Modell-Pausierung.

        Args:
            e: Die Exception, die geprüft werden soll

        Returns:
            True NUR wenn Status-Code 429/402 oder explizites Rate-Limit erkannt wird
        """
        # Prüfe auf Status-Code (429 oder 402)
        status_code = None
        if hasattr(e, 'response') and hasattr(e.response, 'status_code'):
            status_code = e.response.status_code
        elif hasattr(e, 'status_code'):
            status_code = e.status_code

        # Prüfe auf Rate-Limit im Fehlertext mit Regex
        error_str = str(e).lower()
        rate_limit_pattern = r'\brate[_\s-]?limit\b'

        # ÄNDERUNG 28.01.2026: Server-Fehler erkennen aber NICHT als Rate-Limit behandeln
        server_error_patterns = [
            'internal server error',
            'service unavailable',
            'bad gateway',
            'gateway timeout',
            '500',
            '502',
            '503',
            '504'
        ]

        is_server_error = any(pattern in error_str for pattern in server_error_patterns)

        if is_server_error:
            # Server-Fehler: Kurz warten, aber NICHT als Rate-Limit behandeln
            log_event("System", "Warning",
                      "Server-Fehler erkannt (kein Rate-Limit) - kurze Pause von 5s")
            time.sleep(5)  # Kurze Pause bei Server-Fehler
            return False  # KEIN Rate-Limit - Modell wird NICHT pausiert

        # Nur echte Rate-Limit Patterns (429, 402, "rate limit")
        is_rate_limit = (status_code in [429, 402]) or bool(re.search(rate_limit_pattern, error_str))

        # ÄNDERUNG 28.01.2026: Upstream-Fehler nur als Rate-Limit wenn sie wiederholt auftreten
        # Diese sind oft temporär und sollten nicht sofort Fallback auslösen
        upstream_patterns = [
            'upstream error',
            'openrouterexception'
        ]
        is_upstream = any(pattern in error_str for pattern in upstream_patterns)

        if is_upstream and not is_rate_limit:
            log_event("System", "Warning",
                      "Upstream-Fehler erkannt - wird als Rate-Limit behandelt für Fallback")

        return is_rate_limit or is_upstream

    # ÄNDERUNG 24.01.2026: Erkennung für leere/ungültige API-Antworten
    def _is_empty_or_invalid_response(self, response: str) -> bool:
        """
        Erkennt leere oder ungültige Antworten von LLM-Modellen.

        Args:
            response: Die Antwort des Modells

        Returns:
            True wenn die Antwort leer, ungültig oder ein bekanntes Fehlermuster ist
        """
        if not response or not response.strip():
            return True

        # Bekannte Fehler-Patterns bei fehlenden Antworten
        invalid_patterns = [
            "(no response",
            "no response -",
            "indicating failure",
            "malfunctioning",
            "[empty]",
            "[no output]",
            "failed to generate",
            "unable to process"
        ]
        response_lower = response.lower()
        return any(pattern in response_lower for pattern in invalid_patterns)

    # ÄNDERUNG 24.01.2026: Menschenlesbare Zusammenfassung für Reviews
    def _create_human_readable_verdict(self, verdict: str, sandbox_failed: bool, review_output: str) -> str:
        """
        Erstellt menschenlesbare Zusammenfassung des Reviews.

        Args:
            verdict: "OK" oder "FEEDBACK"
            sandbox_failed: True wenn Sandbox/Test Fehler hatte
            review_output: Vollständiger Review-Text

        Returns:
            Menschenlesbare Zusammenfassung mit Emoji
        """
        if verdict == "OK" and not sandbox_failed:
            return "✅ REVIEW BESTANDEN: Code erfüllt alle Anforderungen."
        elif sandbox_failed:
            return "❌ REVIEW FEHLGESCHLAGEN: Sandbox/Test hat Fehler gemeldet."
        else:
            # Extrahiere ersten Satz des Feedbacks als Zusammenfassung
            if review_output:
                first_sentence = review_output.split('.')[0][:100]
                return f"⚠️ ÄNDERUNGEN NÖTIG: {first_sentence}"
            return "⚠️ ÄNDERUNGEN NÖTIG: Bitte Feedback beachten."

    def _extract_tables_from_schema(self, schema: str) -> List[Dict[str, Any]]:
        """
        Extrahiert Tabellen-Informationen aus einem SQL-Schema-String.

        Args:
            schema: SQL-Schema als String

        Returns:
            Liste von Tabellen-Dictionaries mit name, columns, type
        """
        tables = []
        if not schema:
            return tables

        # Suche nach CREATE TABLE Statements
        table_pattern = r'CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[\"\`]?(\w+)[\"\`]?\s*\((.*?)\);'
        matches = re.findall(table_pattern, schema, re.IGNORECASE | re.DOTALL)

        for match in matches:
            table_name = match[0]
            columns_str = match[1]

            # Extrahiere Spalten-Namen
            columns = []
            for line in columns_str.split(','):
                line = line.strip()
                if line and not line.upper().startswith(('PRIMARY', 'FOREIGN', 'UNIQUE', 'CHECK', 'INDEX', 'CONSTRAINT')):
                    col_match = re.match(r'[\"\`]?(\w+)[\"\`]?\s+(\w+)', line)
                    if col_match:
                        col_name = col_match.group(1)
                        col_type = col_match.group(2)
                        is_primary = 'PRIMARY KEY' in line.upper()
                        is_foreign = 'REFERENCES' in line.upper() or 'FOREIGN' in line.upper()
                        columns.append({
                            "name": col_name,
                            "type": col_type,
                            "isPrimary": is_primary,
                            "isForeign": is_foreign
                        })

            tables.append({
                "name": table_name,
                "columns": columns,
                "type": "table"
            })

        return tables[:10]  # Limitiere auf 10 Tabellen für UI

    # ÄNDERUNG 24.01.2026: Hilfsfunktion für Security-Vulnerabilities Extraktion
    # ÄNDERUNG 24.01.2026: Erweitert um FIX-Extraktion für Lösungsvorschläge
    def _extract_vulnerabilities(self, security_result: str) -> List[Dict[str, Any]]:
        """
        Extrahiert Vulnerabilities UND Lösungsvorschläge aus dem Security-Agent Output.

        Args:
            security_result: Rohtext-Ergebnis der Sicherheitsanalyse

        Returns:
            Liste von Vulnerability-Dictionaries mit severity, description, fix, type
        """
        vulnerabilities = []
        if not security_result:
            return vulnerabilities

        # ÄNDERUNG 28.01.2026: Verbessertes Pattern für "VULNERABILITY: ... | FIX: ... | SEVERITY: ..."
        # Pattern 1: Vollständiges Format mit SEVERITY (bevorzugt)
        full_pattern = r'VULNERABILITY:\s*(.+?)\s*\|\s*FIX:\s*(.+?)\s*\|\s*SEVERITY:\s*(\w+)'
        full_matches = re.findall(full_pattern, security_result, re.IGNORECASE | re.DOTALL)

        for match in full_matches:
            vuln_text = match[0].strip()
            fix_text = match[1].strip()
            severity_text = match[2].strip().lower()

            # Severity aus explizitem Feld
            severity = severity_text if severity_text in ["critical", "high", "medium", "low"] else "medium"

            # Datei-Pfad extrahieren
            file_match = re.search(r'(?:in|file|datei|zeile\s+\d+\s+in)\s+["\']?([a-zA-Z0-9_./\\-]+\.[a-z]{2,4})["\']?', vuln_text, re.IGNORECASE)
            affected_file = file_match.group(1) if file_match else None

            # ÄNDERUNG 28.01.2026: Limits erhöht damit Coder vollständige Fix-Anweisungen erhält
            vulnerabilities.append({
                "severity": severity,
                "description": vuln_text[:2000],
                "fix": fix_text[:5000],
                "affected_file": affected_file,
                "type": "SECURITY_ISSUE"
            })

        # Pattern 2: Fallback für altes Format ohne SEVERITY (Abwärtskompatibilität)
        if not vulnerabilities:
            old_pattern = r'VULNERABILITY:\s*(.+?)(?:\s*\|\s*FIX:\s*(.+?))?(?=VULNERABILITY:|$)'
            old_matches = re.findall(old_pattern, security_result, re.IGNORECASE | re.DOTALL)

            for match in old_matches:
                vuln_text = match[0].strip() if match[0] else ""
                fix_text = match[1].strip() if len(match) > 1 and match[1] else ""

                # Falls kein FIX gefunden, versuche alternative Patterns
                if not fix_text and "|" in vuln_text:
                    parts = vuln_text.split("|", 1)
                    vuln_text = parts[0].strip()
                    if len(parts) > 1 and "fix" in parts[1].lower():
                        fix_text = parts[1].replace("FIX:", "").replace("fix:", "").strip()

                # Severity aus Keywords (wie bisher)
                severity = "medium"
                if any(word in vuln_text.lower() for word in ["critical", "kritisch", "sql injection", "rce", "remote code"]):
                    severity = "critical"
                elif any(word in vuln_text.lower() for word in ["high", "hoch", "xss", "csrf", "injection"]):
                    severity = "high"
                elif any(word in vuln_text.lower() for word in ["low", "niedrig", "info", "informational", "minimal"]):
                    severity = "low"

                # Datei-Pfad extrahieren
                file_match = re.search(r'(?:in|file|datei)\s+["\']?([a-zA-Z0-9_./\\-]+\.[a-z]{2,4})["\']?', vuln_text, re.IGNORECASE)
                affected_file = file_match.group(1) if file_match else None

                # ÄNDERUNG 28.01.2026: Limits erhöht damit Coder vollständige Fix-Anweisungen erhält
                vulnerabilities.append({
                    "severity": severity,
                    "description": vuln_text[:2000],
                    "fix": fix_text[:5000],
                    "affected_file": affected_file,
                    "type": "SECURITY_ISSUE"
                })

        return vulnerabilities[:10]  # Limitiere auf 10 für UI

    # ÄNDERUNG 24.01.2026: Hilfsfunktion für Design-Daten Extraktion
    def _extract_design_data(self, design_concept: str) -> Dict[str, Any]:
        """
        Extrahiert strukturierte Design-Daten aus Designer Agent Output.

        Args:
            design_concept: Rohtext-Design-Konzept vom Designer Agent

        Returns:
            Dictionary mit colorPalette, typography, atomicAssets, qualityScore
        """
        result = {
            "colorPalette": [],
            "typography": [],
            "atomicAssets": [],
            "qualityScore": {"overall": 0, "contrast": 0, "hierarchy": 0, "consistency": 0}
        }
        if not design_concept:
            return result

        # Extrahiere HEX-Farben aus dem Konzept
        hex_pattern = r'#([0-9A-Fa-f]{6})\b'
        hex_matches = re.findall(hex_pattern, design_concept)
        color_names = ["Primary", "Secondary", "Accent", "Neutral", "Background"]
        for i, hex_val in enumerate(hex_matches[:5]):
            result["colorPalette"].append({
                "name": color_names[i] if i < len(color_names) else f"Color{i+1}",
                "hex": f"#{hex_val.upper()}"
            })

        # Extrahiere Typography - suche nach bekannten Font-Namen
        font_pattern = r'\b(Inter|Roboto|Open Sans|Lato|Montserrat|Poppins|Raleway|Nunito|Source Sans|Fira Sans)\b'
        font_matches = list(set(re.findall(font_pattern, design_concept, re.IGNORECASE)))
        primary_font = font_matches[0] if font_matches else "Inter"
        for config in [("Display", "700", "48px"), ("Heading", "600", "24px"), ("Body", "400", "16px")]:
            result["typography"].append({
                "name": config[0],
                "font": primary_font,
                "weight": config[1],
                "size": config[2]
            })

        # Extrahiere Atomic Assets - suche nach UI-Komponenten-Namen
        component_pattern = r'\b(Button|Card|Input|Modal|Form|Header|Footer|Navbar|Sidebar|Table|List)\b'
        component_matches = list(set(re.findall(component_pattern, design_concept, re.IGNORECASE)))
        for comp in component_matches[:4]:
            result["atomicAssets"].append({
                "name": f"{comp.title()} Component",
                "status": "pending"
            })

        # Quality Score basierend auf Vollständigkeit des Konzepts
        score = min(100, len(result["colorPalette"]) * 20 + len(result["typography"]) * 15 + len(result["atomicAssets"]) * 10 + 25)
        result["qualityScore"] = {
            "overall": score,
            "contrast": min(100, 70 + len(result["colorPalette"]) * 5),
            "hierarchy": min(100, 65 + len(result["typography"]) * 10),
            "consistency": min(100, 75 + len(result["atomicAssets"]) * 5)
        }

        return result

    def run_task(self, user_goal: str):
        try:
            self._ui_log("System", "Task Start", f"Goal: {user_goal}")

            # ÄNDERUNG 28.01.2026: Projekt in Library starten für Protokollierung
            project_id = None
            try:
                library = get_library_manager()
                project_name = user_goal[:50] if len(user_goal) > 50 else user_goal
                library.start_project(name=project_name, goal=user_goal)
                project_id = library.current_project.get('project_id')
                self._ui_log("Library", "ProjectStart", f"Protokollierung gestartet: {project_id}")
            except Exception as lib_err:
                self._ui_log("Library", "Warning", f"Library-Start fehlgeschlagen: {lib_err}")

            # ÄNDERUNG 28.01.2026: Session für Frontend State-Sync starten
            try:
                session_mgr = get_session_manager()
                session_mgr.start_session(goal=user_goal, project_id=project_id)
                session_mgr.update_status("Working")
            except Exception as sess_err:
                self._ui_log("System", "Warning", f"Session-Start fehlgeschlagen: {sess_err}")

            # Extrahiere Projekt-ID für Budget-Tracking
            project_id = None
            if self.project_path:
                project_id = os.path.basename(self.project_path)

            # 🔎 RESEARCH PHASE (Nur beim ersten Mal) - Mit Timeout um Hängen zu verhindern
            start_context = ""
            research_query = ""
            research_result = ""
            if self.is_first_run:
                # Research-Timeout aus Config lesen (in Minuten), in Sekunden umrechnen
                timeout_minutes = self.config.get("research_timeout_minutes", 5)
                RESEARCH_TIMEOUT_SECONDS = timeout_minutes * 60
                research_query = f"Suche technische Details für: {user_goal}"
                research_model = self.model_router.get_model("researcher") if self.model_router else "unknown"

                # ResearchOutput Event: Status "searching"
                self._ui_log("Researcher", "ResearchOutput", json.dumps({
                    "query": research_query,
                    "result": "",
                    "status": "searching",
                    "model": research_model,
                    "timeout_seconds": RESEARCH_TIMEOUT_SECONDS
                }, ensure_ascii=False))

                try:
                    self._ui_log("Researcher", "Status", f"Sucht Kontext... (max. {RESEARCH_TIMEOUT_SECONDS}s)")
                    set_current_agent("Researcher", project_id)  # Budget-Tracking
                    # ÄNDERUNG 25.01.2026: Worker-Status auf "working" setzen
                    self._update_worker_status("researcher", "working", f"Recherche: {research_query[:50]}...", research_model)
                    res_agent = create_researcher(self.config, self.config.get("templates", {}).get("webapp", {}), router=self.model_router)
                    res_task = Task(
                        description=research_query,
                        expected_output="Zusammenfassung.",
                        agent=res_agent
                    )
                    # Mit Timeout wrappen um endloses Blockieren zu verhindern
                    research_result = run_with_timeout(
                        lambda: str(res_task.execute_sync()),
                        timeout_seconds=RESEARCH_TIMEOUT_SECONDS
                    )
                    start_context = f"\n\nRecherche-Ergebnisse:\n{research_result}"
                    self._ui_log("Researcher", "Result", "Recherche abgeschlossen.")
                    # ÄNDERUNG 25.01.2026: Worker-Status auf "idle" setzen
                    self._update_worker_status("researcher", "idle")

                    # ResearchOutput Event: Status "completed"
                    self._ui_log("Researcher", "ResearchOutput", json.dumps({
                        "query": research_query,
                        "result": research_result[:2000],  # Limit für UI
                        "status": "completed",
                        "model": research_model,
                        "timeout_seconds": RESEARCH_TIMEOUT_SECONDS
                    }, ensure_ascii=False))

                except TimeoutError as te:
                    self._ui_log("Researcher", "Timeout", f"Recherche abgebrochen: {te}")
                    # ÄNDERUNG 25.01.2026: Worker-Status auf "idle" setzen (auch bei Timeout)
                    self._update_worker_status("researcher", "idle")
                    start_context = ""  # Ohne Recherche-Kontext fortfahren

                    # ResearchOutput Event: Status "timeout"
                    self._ui_log("Researcher", "ResearchOutput", json.dumps({
                        "query": research_query,
                        "result": "",
                        "status": "timeout",
                        "model": research_model,
                        "error": str(te)
                    }, ensure_ascii=False))

                except Exception as e:
                    self._ui_log("Researcher", "Error", f"Recherche fehlgeschlagen: {e}")
                    # ÄNDERUNG 25.01.2026: Worker-Status auf "idle" setzen (auch bei Fehler)
                    self._update_worker_status("researcher", "idle")

                    # ResearchOutput Event: Status "error"
                    self._ui_log("Researcher", "ResearchOutput", json.dumps({
                        "query": research_query,
                        "result": "",
                        "status": "error",
                        "model": research_model,
                        "error": str(e)
                    }, ensure_ascii=False))

            # 🧠 META-ORCHESTRATOR
            self._ui_log("Orchestrator", "Status", "Analysiere Intent...")
            set_current_agent("Meta-Orchestrator", project_id)  # Budget-Tracking
            meta_orchestrator = MetaOrchestratorV2()
            plan_data = meta_orchestrator.orchestrate(user_goal + start_context)
            self._ui_log("Orchestrator", "Analysis", json.dumps(plan_data["analysis"], ensure_ascii=False))

            # 📦 PROJEKTSTRUKTUR (Nur beim ersten Mal)
            if self.is_first_run:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                project_name = f"project_{timestamp}"
                # Absoluten Pfad verwenden für konsistentes Verhalten
                self.project_path = os.path.join(self.base_dir, "projects", project_name)
                os.makedirs(self.project_path, exist_ok=True)
                
                # Aktualisiere project_id nach Projekt-Erstellung
                project_id = project_name

                # 🛠️ TECHSTACK
                if "techstack_architect" in plan_data["plan"]:
                    self._ui_log("TechArchitect", "Status", "Analysiere TechStack...")
                    set_current_agent("TechStack-Architect", project_id)  # Budget-Tracking
                    # ÄNDERUNG 25.01.2026: Worker-Status auf "working" setzen
                    self._update_worker_status("techstack_architect", "working", "Analysiere TechStack...", self.model_router.get_model("techstack_architect"))
                    agent_techstack = create_techstack_architect(self.config, self.config.get("templates", {}).get("webapp", {}), router=self.model_router)
                    techstack_task = Task(
                        description=f"Entscheide TechStack für: {user_goal}",
                        expected_output="JSON-Blueprint.",
                        agent=agent_techstack
                    )
                    techstack_result = str(techstack_task.execute_sync())
                    try:
                        json_match = re.search(r'\{[^{}]*"project_type"[^{}]*\}', techstack_result, re.DOTALL)
                        if json_match:
                            self.tech_blueprint = json.loads(json_match.group())
                    except (json.JSONDecodeError, KeyError, ValueError) as e:
                        # Spezifische Exception-Behandlung für JSON-Parsing-Fehler
                        self.tech_blueprint = {"project_type": "static_html"}
                        self._ui_log("TechArchitect", "Warning", f"Blueprint-Parsing fehlgeschlagen, verwende Fallback: {e}")
                    
                    self._ui_log("TechArchitect", "Blueprint", json.dumps(self.tech_blueprint, ensure_ascii=False))
                    # ÄNDERUNG 25.01.2026: Worker-Status auf "idle" setzen
                    self._update_worker_status("techstack_architect", "idle")

                    # ÄNDERUNG 24.01.2026: Strukturiertes TechStackOutput Event für Frontend Office
                    self._ui_log("TechArchitect", "TechStackOutput", json.dumps({
                        "blueprint": self.tech_blueprint,
                        "model": self.model_router.get_model("techstack_architect"),
                        "decisions": [
                            {"type": "Sprache", "value": self.tech_blueprint.get("language", "unknown")},
                            {"type": "Framework", "value": self.tech_blueprint.get("project_type", "unknown")},
                            {"type": "Datenbank", "value": self.tech_blueprint.get("database", "keine")},
                            {"type": "Server", "value": f"Port {self.tech_blueprint.get('server_port', '-')}" if self.tech_blueprint.get("requires_server") else "Nicht benötigt"}
                        ],
                        "dependencies": self.tech_blueprint.get("dependencies", []),
                        "reasoning": self.tech_blueprint.get("reasoning", "")
                    }, ensure_ascii=False))

                    with open(os.path.join(self.project_path, "tech_blueprint.json"), "w", encoding="utf-8") as f:
                        json.dump(self.tech_blueprint, f, indent=2, ensure_ascii=False)

                # Output-Pfad deduction
                run_cmd = self.tech_blueprint.get("run_command", "")
                if "python" in run_cmd:
                    self.output_path = os.path.join(self.project_path, "app.py")
                elif "node" in run_cmd:
                    self.output_path = os.path.join(self.project_path, "index.js")
                else:
                    self.output_path = os.path.join(self.project_path, "index.html")

                # REFINEMENT: Erstelle eine intelligente run.bat
                _pt = self.tech_blueprint.get("project_type", "webapp")
                run_bat_path = os.path.join(self.project_path, "run.bat")
                run_bat_content = "@echo off\n"
                run_bat_content += "echo Launching Multi-Agent Project...\n"
                
                # Check for dependencies
                if self.tech_blueprint.get("language") == "python":
                    run_bat_content += "if not exist venv ( python -m venv venv )\n"
                    run_bat_content += "call venv\\Scripts\\activate\n"
                    if self.tech_blueprint.get("install_command"):
                        run_bat_content += f"call {self.tech_blueprint['install_command']}\n"
                elif self.tech_blueprint.get("language") == "javascript":
                    if self.tech_blueprint.get("install_command"):
                        run_bat_content += f"call {self.tech_blueprint['install_command']}\n"

                # Browser opening
                if _pt == "webapp" or self.output_path.endswith(".html"):
                    # URL ermitteln (default localhost:5000 für Flask, :8000 für FastAPI/Uvicorn, oder file://)
                    url = "index.html"
                    if "flask" in str(self.tech_blueprint).lower(): url = "http://localhost:5000"
                    elif "fastapi" in str(self.tech_blueprint).lower(): url = "http://localhost:8000"
                    elif "uvicorn" in str(self.tech_blueprint).lower(): url = "http://localhost:8000"
                    
                    if url.startswith("http"):
                        run_bat_content += f"start {url}\n"
                    else:
                        run_bat_content += f"start {os.path.basename(self.output_path)}\n"

                # Execute main command
                if run_cmd:
                    run_bat_content += f"{run_cmd}\n"
                
                run_bat_content += "pause\n"
                
                with open(run_bat_path, "w", encoding="utf-8") as f:
                    f.write(run_bat_content)
                self._ui_log("System", "Config", "run.bat created.")

                # ÄNDERUNG 28.01.2026: Dependency-Agent (IT-Abteilung) aufrufen
                # Installiert Dependencies aus dem Blueprint bevor Coder startet
                try:
                    from agents.dependency_agent import get_dependency_agent
                    dep_agent = get_dependency_agent(self.config.get("dependency_agent", {}))
                    dep_agent.on_log = self._ui_log  # UI-Callback setzen

                    self._ui_log("DependencyAgent", "Status", "Pruefe und installiere Dependencies...")

                    # Dependencies aus Blueprint vorbereiten
                    dep_result = dep_agent.prepare_for_task(self.tech_blueprint, self.project_path)

                    if dep_result.get("status") == "OK":
                        self._ui_log("DependencyAgent", "DependencyStatus", json.dumps({
                            "status": "ready",
                            "health_score": dep_result.get("inventory", {}).get("health_score", 0)
                        }, ensure_ascii=False))
                    elif dep_result.get("warnings"):
                        self._ui_log("DependencyAgent", "DependencyStatus", json.dumps({
                            "status": "warning",
                            "warnings": dep_result.get("warnings", [])
                        }, ensure_ascii=False))
                        for warning in dep_result.get("warnings", []):
                            self._ui_log("DependencyAgent", "Warning", warning)
                except Exception as dep_error:
                    self._ui_log("DependencyAgent", "Error", f"Dependency-Pruefung fehlgeschlagen: {dep_error}")
                    # Nicht abbrechen - Coder kann trotzdem versuchen zu arbeiten

            # 🧩 AGENTEN INITIALISIERUNG
            project_type = self.tech_blueprint.get("project_type", "webapp")
            project_rules = self.config.get("templates", {}).get(project_type, {})
            
            agent_coder = create_coder(self.config, project_rules, router=self.model_router)
            agent_reviewer = create_reviewer(self.config, project_rules, router=self.model_router)
            # ÄNDERUNG 28.01.2026: Tester mit router für konsistente Modell-Konfiguration (Phase 0.12)
            agent_tester = create_tester(self.config, project_rules, router=self.model_router)
            # ÄNDERUNG 25.01.2026: Security-Agent immer erstellen (für Re-Scan im DEV LOOP)
            agent_security = create_security_agent(self.config, project_rules, router=self.model_router)
            
            # Design & DB (Nur beim ersten Mal)
            if self.is_first_run:
                if "database_designer" in plan_data["plan"]:
                    self._ui_log("DBDesigner", "Status", "Erstelle Schema...")
                    set_current_agent("Database-Designer", project_id)  # Budget-Tracking
                    dbdesigner_model = self.model_router.get_model("database_designer") if self.model_router else "unknown"
                    # ÄNDERUNG 25.01.2026: Worker-Status auf "working" setzen
                    self._update_worker_status("db_designer", "working", "Erstelle Schema...", dbdesigner_model)
                    agent_db = create_database_designer(self.config, project_rules, router=self.model_router)
                    if agent_db:
                        task_db = Task(description=f"Schema für {user_goal}", expected_output="Schema", agent=agent_db)
                        self.database_schema = str(task_db.execute_sync())
                        # ÄNDERUNG 25.01.2026: Worker-Status auf "idle" setzen
                        self._update_worker_status("db_designer", "idle")

                        # ÄNDERUNG 24.01.2026: DBDesignerOutput Event für Frontend Office
                        self._ui_log("DBDesigner", "DBDesignerOutput", json.dumps({
                            "schema": self.database_schema[:2000] if self.database_schema else "",
                            "model": dbdesigner_model,
                            "status": "completed",
                            "tables": self._extract_tables_from_schema(self.database_schema),
                            "timestamp": datetime.now().isoformat()
                        }, ensure_ascii=False))

                if "designer" in plan_data["plan"]:
                    self._ui_log("Designer", "Status", "Erstelle Design-Konzept...")
                    set_current_agent("Designer", project_id)  # Budget-Tracking
                    designer_model = self.model_router.get_model("designer") if self.model_router else "unknown"
                    # ÄNDERUNG 25.01.2026: Worker-Status auf "working" setzen
                    self._update_worker_status("designer", "working", "Erstelle Design-Konzept...", designer_model)
                    agent_des = create_designer(self.config, project_rules, router=self.model_router)
                    if agent_des:
                        # AENDERUNG 25.01.2026: Designer erhaelt TechStack-Blueprint
                        tech_info = f"Tech-Stack: {self.tech_blueprint.get('project_type', 'webapp')}"
                        if self.tech_blueprint.get('dependencies'):
                            tech_info += f", Frameworks: {', '.join(self.tech_blueprint.get('dependencies', []))}"
                        task_des = Task(description=f"Design für: {user_goal}\n{tech_info}", expected_output="Konzept", agent=agent_des)
                        self.design_concept = str(task_des.execute_sync())
                        # ÄNDERUNG 25.01.2026: Worker-Status auf "idle" setzen
                        self._update_worker_status("designer", "idle")

                        # ÄNDERUNG 24.01.2026: DesignerOutput Event für Frontend Office
                        design_data = self._extract_design_data(self.design_concept)

                        self._ui_log("Designer", "DesignerOutput", json.dumps({
                            "colorPalette": design_data["colorPalette"],
                            "typography": design_data["typography"],
                            "atomicAssets": design_data["atomicAssets"],
                            "qualityScore": design_data["qualityScore"],
                            "iterationInfo": {"current": 1, "progress": 100},
                            "viewport": {"width": 1440, "height": 900},
                            "previewUrl": f"file://{self.project_path}/index.html" if self.project_path else "",
                            "concept": self.design_concept[:2000] if self.design_concept else "",
                            "model": designer_model,
                            "timestamp": datetime.now().isoformat()
                        }, ensure_ascii=False))

                # ÄNDERUNG 25.01.2026: Initial-Security-Scan auf Anforderungen ENTFERNT
                # Security-Analyse erfolgt jetzt NUR im DEV LOOP nach Code-Generierung (Re-Scan)
                # Begründung: Es macht keinen Sinn, Vulnerabilities zu finden bevor Code existiert
                self._ui_log("Security", "Status", "Security-Scan wird nach Code-Generierung durchgeführt...")

            # 🔄 DEV LOOP
            max_retries = self.config.get("max_retries", 3)
            feedback = ""
            iteration = 0
            self._current_iteration = 0  # ÄNDERUNG 28.01.2026: Für Library-Protokollierung
            success = False
            # ÄNDERUNG 24.01.2026: Security-Retry-Counter für max_security_retries
            security_retry_count = 0
            max_security_retries = self.config.get("max_security_retries", 3)  # Nach 3 Versuchen: Warnung statt Blockade

            # ÄNDERUNG 25.01.2026: Modellwechsel-Tracking ("Kollegen fragen")
            model_attempt = 0
            max_model_attempts = self.config.get("max_model_attempts", 3)
            current_coder_model = self.model_router.get_model("coder")
            models_used = [current_coder_model]
            failed_attempts_history = []  # Speichert was jedes Modell versucht hat

            while iteration < max_retries:
                self._ui_log("Coder", "Iteration", f"{iteration+1} / {max_retries}")

                # Budget-Tracking für Coder
                set_current_agent("Coder", project_id)
                # ÄNDERUNG 25.01.2026: Worker-Status auf "working" setzen
                coder_model = self.model_router.get_model("coder") if self.model_router else "unknown"
                self._update_worker_status("coder", "working", f"Iteration {iteration+1}/{max_retries}", coder_model)

                # ÄNDERUNG 28.01.2026: Truncation entfernt - Coder braucht vollständiges DB-Schema
                c_prompt = f"Ziel: {user_goal}\nTech: {self.tech_blueprint}\nDB: {self.database_schema}\n"
                if not self.is_first_run: c_prompt += f"\nAlt-Code:\n{self.current_code}\n"
                if feedback: c_prompt += f"\nKorrektur: {feedback}\n"

                # ÄNDERUNG 28.01.2026: Basis-Security-Hints für erste Iteration (proaktive Guidance)
                if iteration == 0 and not feedback:
                    c_prompt += "\n\n🛡️ SECURITY BASICS (von Anfang an beachten!):\n"
                    c_prompt += "- Kein innerHTML/document.write mit User-Input (XSS-Risiko)\n"
                    c_prompt += "- Keine String-Konkatenation in SQL/DB-Queries (Injection-Risiko)\n"
                    c_prompt += "- Keine hardcoded API-Keys, Passwörter oder Secrets im Code\n"
                    c_prompt += "- Bei eval(): Nur mit Button-Input, NIEMALS mit User-Text-Input\n"
                    c_prompt += "- Nutze textContent statt innerHTML wenn möglich\n\n"

                # ÄNDERUNG 28.01.2026: Gelernte Lektionen aus Memory in Coder-Prompt einbinden
                try:
                    memory_path = os.path.join(self.base_dir, "memory", "global_memory.json")
                    tech_stack = self.tech_blueprint.get("project_type", "") if self.tech_blueprint else ""
                    lessons = get_lessons_for_prompt(memory_path, tech_stack=tech_stack)
                    if lessons and lessons.strip():
                        c_prompt += f"\n\n📚 LESSONS LEARNED (aus früheren Projekten - UNBEDINGT BEACHTEN!):\n{lessons}\n"
                        self._ui_log("Memory", "LessonsApplied", f"Coder erhält {len(lessons.splitlines())} Lektionen")
                except Exception as les_err:
                    logger.debug(f"Lektionen konnten nicht geladen werden: {les_err}")

                # ÄNDERUNG 25.01.2026: Granulare Security-Tasks mit Priorisierung
                if hasattr(self, 'security_vulnerabilities') and self.security_vulnerabilities:
                    # Sortiere nach Severity (CRITICAL zuerst)
                    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
                    sorted_vulns = sorted(
                        self.security_vulnerabilities,
                        key=lambda v: severity_order.get(v.get("severity", "medium"), 2)
                    )

                    # Generiere strukturierte Tasks für Frontend und Prompt
                    coder_tasks = []
                    task_prompt_lines = []

                    for i, vuln in enumerate(sorted_vulns, 1):
                        task_id = f"SEC-{i:03d}"
                        severity = vuln.get("severity", "medium").upper()
                        description = vuln.get("description", "Unbekannte Schwachstelle")
                        fix = vuln.get("fix", "Bitte beheben")
                        # ÄNDERUNG 25.01.2026: Datei-Pfad für bessere Lokalisierung
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

                        # ÄNDERUNG 25.01.2026: Datei-Pfad in Prompt für Free-Modelle
                        file_hint = f"\n   -> DATEI: {affected_file}" if affected_file else ""
                        task_prompt_lines.append(
                            f"TASK {task_id} [{severity}]: {description}{file_hint}\n"
                            f"   -> LÖSUNG: {fix}"
                        )

                    # WebSocket Event für Frontend (CoderOffice Task-Liste)
                    self._ui_log("Coder", "CoderTasksOutput", json.dumps({
                        "tasks": coder_tasks,
                        "count": len(coder_tasks),
                        "iteration": iteration + 1
                    }, ensure_ascii=False))

                    # Prompt mit nummerierten, priorisierten Tasks
                    c_prompt += "\n\n⚠️ SECURITY TASKS (priorisiert nach Severity - CRITICAL zuerst):\n"
                    c_prompt += "\n".join(task_prompt_lines)
                    c_prompt += "\n\nWICHTIG: Bearbeite die Tasks in der angegebenen Reihenfolge! Implementiere die LÖSUNG für jeden Task!\n"

                # ÄNDERUNG 28.01.2026: Unit-Test-Anforderung hinzufügen
                c_prompt += "\n\n🧪 UNIT-TEST REQUIREMENT:\n"
                c_prompt += "- Erstelle IMMER Unit-Tests für alle neuen Funktionen/Klassen\n"
                c_prompt += "- Test-Dateien: tests/test_<modulname>.py oder tests/<modulname>.test.js\n"
                c_prompt += "- Mindestens 3 Test-Cases pro Funktion (normal, edge-case, error-case)\n"
                c_prompt += "- Format: ### FILENAME: tests/test_<modulname>.py\n"
                c_prompt += "- Tests müssen AUSFÜHRBAR sein (pytest bzw. npm test)\n"

                # Für API-Projekte zusätzliche Anforderungen
                if self.tech_blueprint and self.tech_blueprint.get("requires_server"):
                    c_prompt += "\n🔌 API-TESTS:\n"
                    c_prompt += "- Teste JEDEN API-Endpoint mit mindestens 2 Test-Cases\n"
                    c_prompt += "- Prüfe Erfolgs-Response UND Fehler-Response\n"
                    c_prompt += "- Python: pytest + Flask test_client oder requests\n"
                    c_prompt += "- JavaScript: jest + supertest\n"

                c_prompt += "\nFormat: ### FILENAME: path/to/file.ext"

                task_coder = Task(description=c_prompt, expected_output="Code", agent=agent_coder)

                # ÄNDERUNG 25.01.2026: Erweiterte Retry-Logik mit 3 Versuchen (analog zum Reviewer)
                MAX_CODER_RETRIES = 3
                coder_success = False

                for coder_attempt in range(MAX_CODER_RETRIES):
                    try:
                        self.current_code = str(task_coder.execute_sync()).strip()
                        coder_success = True
                        break

                    except Exception as e:
                        current_model = self.model_router.get_model("coder") if self.model_router else "unknown"

                        if self._is_rate_limit_error(e):
                            # Markiere aktuelles Modell als rate-limited
                            self.model_router.mark_rate_limited_sync(current_model)
                            self._ui_log("ModelRouter", "RateLimit",
                                f"Modell {current_model} pausiert (Versuch {coder_attempt + 1}/{MAX_CODER_RETRIES}), wechsle zu Fallback...")

                            # Erstelle Agent mit Fallback-Modell und retry
                            agent_coder = create_coder(self.config, project_rules, router=self.model_router)
                            task_coder = Task(description=c_prompt, expected_output="Code", agent=agent_coder)

                            if coder_attempt == MAX_CODER_RETRIES - 1:
                                # Letzter Versuch fehlgeschlagen
                                self._ui_log("Coder", "Error", f"Alle {MAX_CODER_RETRIES} Versuche fehlgeschlagen: {str(e)[:200]}")
                                raise e
                        else:
                            # Unbekannter Fehler - sofort abbrechen
                            self._ui_log("Coder", "Error", f"Unerwarteter Fehler: {str(e)[:200]}")
                            raise e

                if not coder_success:
                    raise Exception(f"Coder konnte nach {MAX_CODER_RETRIES} Versuchen keine Ausgabe generieren")
                
                # Speichern
                from main import save_multi_file_output
                def_file = os.path.basename(self.output_path)
                created_files = save_multi_file_output(self.project_path, self.current_code, def_file)
                self._ui_log("Coder", "Files", f"Created: {', '.join(created_files)}")

                # CodeOutput Event für Live-Anzeige im Frontend
                current_model = self.model_router.get_model("coder") if self.model_router else "unknown"
                self._ui_log("Coder", "CodeOutput", json.dumps({
                    "code": self.current_code,
                    "files": created_files,
                    "iteration": iteration + 1,
                    "max_iterations": max_retries,
                    "model": current_model
                }, ensure_ascii=False))
                # ÄNDERUNG 25.01.2026: Worker-Status auf "idle" setzen nach Code-Generierung
                self._update_worker_status("coder", "idle")

                # ÄNDERUNG 25.01.2026: TokenMetrics Event für Live-Metriken im CoderOffice
                try:
                    tracker = get_budget_tracker()
                    today_totals = tracker.get_today_totals()
                    self._ui_log("Coder", "TokenMetrics", json.dumps({
                        "total_tokens": today_totals.get("total_tokens", 0),
                        "total_cost": today_totals.get("total_cost", 0.0)
                    }, ensure_ascii=False))
                except Exception as metric_err:
                    # Nicht blockieren bei Metrik-Fehlern
                    pass

                # Sandbox
                sandbox_result = run_sandbox(self.current_code)
                self._ui_log("Sandbox", "Result", sandbox_result)
                sandbox_failed = sandbox_result.startswith("❌")

                # ÄNDERUNG 28.01.2026: Multi-File Referenz-Validierung
                try:
                    from sandbox_runner import validate_project_references
                    ref_result = validate_project_references(self.project_path)
                    if ref_result.startswith("❌"):
                        sandbox_result += f"\n{ref_result}"
                        sandbox_failed = True
                        self._ui_log("Sandbox", "Referenzen", ref_result)
                    else:
                        self._ui_log("Sandbox", "Referenzen", ref_result)
                except Exception as ref_err:
                    self._ui_log("Sandbox", "Warning", f"Referenz-Validierung fehlgeschlagen: {ref_err}")

                # ÄNDERUNG 28.01.2026: run.bat Validierung vor Server-Start
                try:
                    from content_validator import validate_run_bat
                    bat_result = validate_run_bat(self.project_path, self.tech_blueprint)
                    if bat_result.issues:
                        for issue in bat_result.issues:
                            self._ui_log("Tester", "RunBatWarning", issue)
                    if bat_result.warnings:
                        for warning in bat_result.warnings:
                            self._ui_log("Tester", "RunBatInfo", warning)
                except Exception as bat_err:
                    self._ui_log("Tester", "Warning", f"run.bat-Validierung fehlgeschlagen: {bat_err}")

                # Memory: Lerne aus Sandbox-Fehlern (geschützt, damit Iteration weiterläuft)
                if sandbox_failed:
                    try:
                        memory_path = os.path.join(self.base_dir, "memory", "global_memory.json")
                        error_msg = extract_error_pattern(sandbox_result)
                        tags = generate_tags_from_context(self.tech_blueprint, sandbox_result)
                        learn_result = learn_from_error(memory_path, error_msg, tags)
                        self._ui_log("Memory", "Learning", f"Sandbox: {learn_result}")
                    except Exception as mem_err:
                        self._ui_log("Memory", "Error", f"Memory-Operation fehlgeschlagen: {mem_err}")

                # ÄNDERUNG 28.01.2026: Unit-Tests vor Playwright-Tests ausführen
                unit_test_result = {"status": "SKIP", "summary": "Keine Unit-Tests", "test_count": 0}
                try:
                    from unit_test_runner import run_unit_tests
                    self._ui_log("UnitTest", "Status", "Führe Unit-Tests durch...")
                    self._update_worker_status("tester", "working", "Unit-Tests...", "pytest/jest")

                    unit_test_result = run_unit_tests(self.project_path, self.tech_blueprint)

                    self._ui_log("UnitTest", "Result", json.dumps({
                        "status": unit_test_result.get("status"),
                        "summary": unit_test_result.get("summary"),
                        "test_count": unit_test_result.get("test_count", 0),
                        "iteration": iteration + 1
                    }, ensure_ascii=False))

                    # Unit-Test-Fehler blockieren wie Syntax-Fehler
                    if unit_test_result.get("status") == "FAIL":
                        sandbox_failed = True
                        sandbox_result += f"\n\n❌ UNIT-TESTS FEHLGESCHLAGEN:\n{unit_test_result.get('summary', '')}"
                        if unit_test_result.get("details"):
                            sandbox_result += f"\n{unit_test_result.get('details', '')[:1000]}"

                except ImportError:
                    self._ui_log("UnitTest", "Warning", "unit_test_runner.py nicht gefunden - übersprungen")
                except Exception as ut_err:
                    logger.warning(f"Unit-Test Runner Fehler: {ut_err}")
                    self._ui_log("UnitTest", "Error", f"Unit-Test Fehler: {ut_err}")

                # ÄNDERUNG 24.01.2026: Intelligente Test-Logik mit tech_blueprint und Server-Integration
                # test_project() nutzt tech_blueprint um:
                # - Server via run.bat zu starten (wenn requires_server=true)
                # - Auf Server-Verfügbarkeit zu warten (Port-Check)
                # - Playwright-Tests gegen URL oder Datei durchzuführen
                # - Sauberes Cleanup nach Tests
                test_summary = "Keine UI-Tests durchgeführt."
                set_current_agent("Tester", project_id)  # Budget-Tracking
                self._ui_log("Tester", "Status", f"Starte Tests für Projekt-Typ '{project_type}'...")
                # ÄNDERUNG 25.01.2026: Worker-Status auf "working" setzen
                self._update_worker_status("tester", "working", f"Teste {project_type}...", self.model_router.get_model("tester") if self.model_router else "")

                try:
                    ui_result = test_project(self.project_path, self.tech_blueprint, self.config)
                    test_summary = summarize_ui_result(ui_result)
                    self._ui_log("Tester", "Result", test_summary)

                    # ÄNDERUNG 24.01.2026: Screenshot als Base64 für Live-Vorschau senden
                    screenshot_base64 = None
                    if ui_result.get("screenshot") and os.path.exists(ui_result["screenshot"]):
                        try:
                            with open(ui_result["screenshot"], "rb") as img_file:
                                screenshot_base64 = f"data:image/png;base64,{base64.b64encode(img_file.read()).decode('utf-8')}"
                        except Exception as img_err:
                            self._ui_log("Tester", "Warning", f"Screenshot konnte nicht geladen werden: {img_err}")

                    # UITestResult Event für Frontend (Live Canvas + TesterOffice)
                    self._ui_log("Tester", "UITestResult", json.dumps({
                        "status": ui_result["status"],
                        "issues": ui_result.get("issues", []),
                        "screenshot": screenshot_base64,
                        "model": self.model_router.get_model("tester") if hasattr(self, 'model_router') else ""
                    }, ensure_ascii=False))
                    # ÄNDERUNG 25.01.2026: Worker-Status auf "idle" setzen
                    self._update_worker_status("tester", "idle")

                    if ui_result["status"] in ["FAIL", "ERROR"]:
                        sandbox_failed = True  # UI-Fehler blockieren auch
                        # Memory: Lerne aus Test-Fehlern (geschützt)
                        try:
                            memory_path = os.path.join(self.base_dir, "memory", "global_memory.json")
                            error_msg = extract_error_pattern(test_summary)
                            tags = generate_tags_from_context(self.tech_blueprint, test_summary)
                            tags.append("ui-test")
                            learn_result = learn_from_error(memory_path, error_msg, tags)
                            self._ui_log("Memory", "Learning", f"Test: {learn_result}")
                        except Exception as mem_err:
                            self._ui_log("Memory", "Error", f"Memory-Operation fehlgeschlagen: {mem_err}")
                except Exception as te:
                    test_summary = f"❌ Test-Runner Fehler: {te}"
                    self._ui_log("Tester", "Error", test_summary)
                    # ÄNDERUNG 25.01.2026: Worker-Status auf "idle" setzen (auch bei Fehler)
                    self._update_worker_status("tester", "idle")
                    sandbox_failed = True
                    ui_result = {"status": "ERROR", "issues": [str(te)], "screenshot": None}

                # ÄNDERUNG 28.01.2026: Strukturiertes Test-Ergebnis für Coder-Feedback (Phase 0.12)
                unit_ok = unit_test_result.get("status") in ["OK", "SKIP"]
                ui_ok = ui_result.get("status", "SKIP") not in ["FAIL", "ERROR"]
                test_result = {
                    "unit_tests": {
                        "status": unit_test_result.get("status", "SKIP"),
                        "passed": unit_test_result.get("test_count", 0),
                        "failed_count": unit_test_result.get("failed_count", 0),
                        "summary": unit_test_result.get("summary", ""),
                        "details": unit_test_result.get("details", "")
                    },
                    "ui_tests": {
                        "status": ui_result.get("status", "SKIP"),
                        "issues": ui_result.get("issues", []),
                        "screenshot": ui_result.get("screenshot"),
                        "has_visible_content": True  # Default, wird durch Content-Validator gesetzt
                    },
                    "overall_status": "PASS" if (unit_ok and ui_ok) else "FAIL"
                }

                # ÄNDERUNG 28.01.2026: Test-Zusammenfassung für Bibliothek protokollieren (Phase 0.12)
                self._ui_log("Tester", "TestSummary", json.dumps({
                    "overall_status": test_result.get("overall_status"),
                    "unit_status": test_result["unit_tests"]["status"],
                    "unit_passed": test_result["unit_tests"]["passed"],
                    "ui_status": test_result["ui_tests"]["status"],
                    "ui_issues_count": len(test_result["ui_tests"]["issues"]),
                    "iteration": iteration + 1
                }, ensure_ascii=False))

                # Review
                set_current_agent("Reviewer", project_id)  # Budget-Tracking
                # ÄNDERUNG 28.01.2026: Truncation entfernt - Reviewer muss vollständigen Code sehen
                r_prompt = f"Review Code:\n{self.current_code}\nSandbox: {sandbox_result}\nTester: {test_summary}"
                # ÄNDERUNG 25.01.2026: Worker-Status auf "working" setzen
                self._update_worker_status("reviewer", "working", "Prüfe Code...", self.model_router.get_model("reviewer") if self.model_router else "")

                # ÄNDERUNG 24.01.2026: Review mit "No Response" Handling und automatischem Modellwechsel
                # ÄNDERUNG 25.01.2026: Timeout hinzugefügt (wie beim Researcher) für robustere API-Aufrufe
                MAX_REVIEW_RETRIES = 3
                REVIEWER_TIMEOUT_SECONDS = 120  # 2 Minuten Timeout
                review_output = None

                for review_attempt in range(MAX_REVIEW_RETRIES):
                    task_review = Task(description=r_prompt, expected_output="OK/Feedback", agent=agent_reviewer)
                    current_model = self.model_router.get_model("reviewer")

                    try:
                        # ÄNDERUNG 25.01.2026: Mit Timeout wrappen um endloses Blockieren zu verhindern
                        review_output = run_with_timeout(
                            lambda: str(task_review.execute_sync()),
                            timeout_seconds=REVIEWER_TIMEOUT_SECONDS
                        )

                        # Prüfe auf leere/ungültige Antwort
                        if self._is_empty_or_invalid_response(review_output):
                            self._ui_log("Reviewer", "NoResponse",
                                f"Modell {current_model} lieferte keine Antwort (Versuch {review_attempt + 1}/{MAX_REVIEW_RETRIES})")

                            # Markiere als rate-limited und wechsle Modell
                            self.model_router.mark_rate_limited_sync(current_model)
                            agent_reviewer = create_reviewer(self.config, project_rules, router=self.model_router)
                            continue

                        break  # Gültige Antwort erhalten

                    except TimeoutError as te:
                        # ÄNDERUNG 25.01.2026: Timeout - Modellwechsel wie bei Rate-Limit
                        self._ui_log("Reviewer", "Timeout",
                            f"Reviewer-Modell {current_model} timeout nach {REVIEWER_TIMEOUT_SECONDS}s (Versuch {review_attempt + 1}/{MAX_REVIEW_RETRIES}), wechsle zu Fallback...")
                        self.model_router.mark_rate_limited_sync(current_model)
                        agent_reviewer = create_reviewer(self.config, project_rules, router=self.model_router)
                        continue

                    except Exception as e:
                        if self._is_rate_limit_error(e):
                            # Markiere aktuelles Modell als rate-limited
                            self.model_router.mark_rate_limited_sync(current_model)
                            self._ui_log("ModelRouter", "RateLimit", f"Reviewer-Modell {current_model} pausiert, wechsle zu Fallback...")

                            # Erstelle Agent mit Fallback-Modell
                            agent_reviewer = create_reviewer(self.config, project_rules, router=self.model_router)
                            continue
                        else:
                            raise e

                # Falls alle Retries fehlschlagen: Expliziter Fehler statt endlose Iteration
                if self._is_empty_or_invalid_response(review_output):
                    review_output = "FEHLER: Alle Review-Modelle haben versagt. Bitte prüfe die API-Verbindung und Modell-Verfügbarkeit."
                    self._ui_log("Reviewer", "AllModelsFailed", "Kein Modell konnte eine gültige Antwort liefern.")

                # ÄNDERUNG 24.01.2026: ReviewOutput Event für Frontend Office (erweitert mit humanSummary)
                reviewer_model = self.model_router.get_model("reviewer") if self.model_router else "unknown"
                review_verdict = "OK" if "OK" in review_output.upper() and not sandbox_failed else "FEEDBACK"
                is_approved = review_verdict == "OK" and not sandbox_failed
                human_summary = self._create_human_readable_verdict(review_verdict, sandbox_failed, review_output)

                self._ui_log("Reviewer", "ReviewOutput", json.dumps({
                    "verdict": review_verdict,
                    "isApproved": is_approved,
                    "humanSummary": human_summary,
                    "feedback": review_output if review_verdict == "FEEDBACK" else "",
                    "model": reviewer_model,
                    "iteration": iteration + 1,
                    "maxIterations": max_retries,
                    "sandboxStatus": "PASS" if not sandbox_failed else "FAIL",
                    "sandboxResult": sandbox_result[:500] if sandbox_result else "",
                    "testSummary": test_summary[:500] if test_summary else "",
                    "reviewOutput": review_output if review_output else ""
                }, ensure_ascii=False))
                # ÄNDERUNG 25.01.2026: Worker-Status auf "idle" setzen
                self._update_worker_status("reviewer", "idle")

                # ÄNDERUNG 24.01.2026: Security Re-Scan - Prüfe generierten Code auf Sicherheitslücken
                security_passed = True  # Default: Security-Gate bestanden
                security_rescan_vulns = []

                if agent_security and self.current_code:
                    self._ui_log("Security", "RescanStart", f"Prüfe generierten Code (Iteration {iteration+1})...")
                    set_current_agent("Security", project_id)
                    # ÄNDERUNG 25.01.2026: Worker-Status auf "working" setzen
                    self._update_worker_status("security", "working", f"Security-Scan Iteration {iteration+1}", self.model_router.get_model("security") if self.model_router else "")

                    # ÄNDERUNG 25.01.2026: Vereinfachter Security-Prompt für Free-Modelle
                    security_rescan_prompt = f"""Prüfe diesen Code auf Sicherheitsprobleme:

{self.current_code}

ANTWORT-FORMAT (eine Zeile pro Problem):
VULNERABILITY: [Problem-Beschreibung] | FIX: [Konkrete Lösung mit Code-Beispiel] | SEVERITY: [CRITICAL/HIGH/MEDIUM/LOW]

BEISPIEL:
VULNERABILITY: innerHTML in Zeile 15 ermöglicht XSS-Angriffe | FIX: Ersetze element.innerHTML = userInput mit element.textContent = userInput oder nutze DOMPurify.sanitize(userInput) | SEVERITY: HIGH

PRÜFE NUR auf die 3 wichtigsten Kategorien:
1. XSS (innerHTML, document.write, eval mit User-Input)
2. SQL/NoSQL Injection (String-Konkatenation in Queries)
3. Hardcoded Secrets (API-Keys, Passwörter im Code)

WICHTIG:
- Bei Taschenrechner-Apps: eval() mit Button-Input ist LOW severity (kein User-Text-Input)
- Bei statischen Webseiten: innerHTML ohne User-Input ist kein Problem
- Gib für JEDEN Fix KONKRETEN Code der das Problem löst

Wenn KEINE kritischen Probleme gefunden: Antworte nur mit "SECURE"
"""

                    task_security_rescan = Task(
                        description=security_rescan_prompt,
                        expected_output="SECURE oder VULNERABILITY-Liste",
                        agent=agent_security
                    )

                    try:
                        security_rescan_result = str(task_security_rescan.execute_sync())
                        security_rescan_vulns = self._extract_vulnerabilities(security_rescan_result)
                        self.security_vulnerabilities = security_rescan_vulns  # Aktualisieren

                        # Security-Gate: Nur low-Severity erlaubt
                        security_passed = not security_rescan_vulns or all(
                            v.get('severity') == 'low' for v in security_rescan_vulns
                        )

                        security_rescan_model = self.model_router.get_model("security") if self.model_router else "unknown"
                        rescan_status = "SECURE" if security_passed else "VULNERABLE"

                        # UI-Event für Frontend
                        self._ui_log("Security", "SecurityRescanOutput", json.dumps({
                            "vulnerabilities": security_rescan_vulns,
                            "overall_status": rescan_status,
                            "scan_type": "code_scan",
                            "iteration": iteration + 1,
                            "blocking": not security_passed,
                            "model": security_rescan_model,
                            "timestamp": datetime.now().isoformat()
                        }, ensure_ascii=False))

                        self._ui_log("Security", "RescanResult", f"Code-Scan: {rescan_status} ({len(security_rescan_vulns)} Findings)")
                        # ÄNDERUNG 25.01.2026: Worker-Status auf "idle" setzen
                        self._update_worker_status("security", "idle")
                    except Exception as sec_err:
                        self._ui_log("Security", "Error", f"Security-Rescan fehlgeschlagen: {sec_err}")
                        # ÄNDERUNG 25.01.2026: Worker-Status auf "idle" setzen (auch bei Fehler)
                        self._update_worker_status("security", "idle")
                        security_passed = True  # Bei Fehler nicht blockieren

                # ÄNDERUNG 24.01.2026: Nach max_security_retries nur noch warnen, nicht blockieren
                if not security_passed:
                    security_retry_count += 1
                    if security_retry_count >= max_security_retries:
                        self._ui_log("Security", "Warning",
                            f"⚠️ {len(security_rescan_vulns)} Security-Issues nach {security_retry_count} Versuchen nicht behoben. "
                            f"Fahre mit Warnung fort (keine Blockade).")
                        security_passed = True  # Erlaube Fortfahren mit Warnung

                # ÄNDERUNG 25.01.2026: Debug-Logging für Break-Entscheidung
                # ÄNDERUNG 28.01.2026: Erweitert um Datei-Zaehler
                review_says_ok = review_output.strip().upper().startswith("OK") or review_output.strip().upper() == "OK"
                file_count = len(created_files) if created_files else 0
                self._ui_log("Debug", "LoopDecision", json.dumps({
                    "iteration": iteration + 1,
                    "review_output_preview": review_output[:200] if review_output else "",
                    "review_says_ok": review_says_ok,
                    "sandbox_failed": sandbox_failed,
                    "security_passed": security_passed,
                    "security_retry_count": security_retry_count,
                    "created_files_count": file_count,
                    "has_minimum_files": file_count >= 3,
                    "will_break": review_says_ok and not sandbox_failed and security_passed and file_count >= 3
                }, ensure_ascii=False))

                # STRIKTER CHECK: Reviewer OK + Sandbox OK + Security SECURE + Mindestanzahl Dateien
                # ÄNDERUNG 25.01.2026: Verbesserte OK-Erkennung - nur wenn Review mit "OK" STARTET
                # ÄNDERUNG 28.01.2026: Validiere Datei-Vollstaendigkeit vor Break
                created_count = len(created_files) if created_files else 0
                has_minimum_files = created_count >= 3  # Mindestens 3 Dateien fuer ein Projekt

                if review_says_ok and not sandbox_failed and security_passed and has_minimum_files:
                    success = True
                    self._ui_log("Security", "SecurityGate", "✅ Security-Gate bestanden - Code ist sicher.")
                    self._ui_log("Reviewer", "Status", f"Code OK - Projekt komplett mit {created_count} Dateien.")
                    # Memory: Zeichne erfolgreiche Iteration auf (geschützt)
                    try:
                        memory_path = os.path.join(self.base_dir, "memory", "global_memory.json")
                        update_memory(memory_path, self.current_code, review_output, sandbox_result)
                        self._ui_log("Memory", "Recording", "Erfolgreiche Iteration aufgezeichnet.")
                    except Exception as mem_err:
                        self._ui_log("Memory", "Error", f"Memory-Operation fehlgeschlagen: {mem_err}")
                    break
                elif review_says_ok and not has_minimum_files:
                    # ÄNDERUNG 28.01.2026: Reviewer sagt OK aber zu wenig Dateien - weitermachen
                    self._ui_log("Orchestrator", "Status", f"Nur {created_count} Dateien erstellt - generiere weitere...")
                    feedback = f"Bitte weitere Dateien generieren. Bisher nur {created_count} Datei(en). "
                    feedback += "Ein vollstaendiges Projekt braucht mindestens Backend, Config/Requirements und README oder Tests."
                    iteration += 1
                    continue
                else:
                    # ÄNDERUNG 28.01.2026: Feedback-Logik ohne widersprüchliche Signale
                    # Security-Issues haben PRIORITÄT - nicht mit "OK" kombinieren
                    if not security_passed and security_rescan_vulns:
                        # Security-Issues MIT Lösungsvorschlägen als Feedback an Coder
                        # NICHT mit review_output kombinieren um Widersprüche zu vermeiden
                        security_feedback = "\n".join([
                            f"- [{v.get('severity', 'unknown').upper()}] {v.get('description', '')}\n"
                            f"  → LÖSUNG: {v.get('fix', 'Bitte beheben')}"
                            for v in security_rescan_vulns
                        ])
                        feedback = f"⚠️ SECURITY VULNERABILITIES - MÜSSEN ZUERST BEHOBEN WERDEN:\n{security_feedback}\n\n"
                        feedback += "WICHTIG: Implementiere die Lösungsvorschläge (→ LÖSUNG) für JEDE Vulnerability!\n"
                        feedback += "Der Code wird erst akzeptiert wenn alle Security-Issues behoben sind.\n"
                        self._ui_log("Security", "BlockingIssues", f"❌ {len(security_rescan_vulns)} Vulnerabilities blockieren Abschluss")
                    elif sandbox_failed:
                        # Sandbox/Tester-Fehler
                        feedback = f"KRITISCHER FEHLER: Die Sandbox oder der Tester hat Fehler gemeldet.\n"
                        feedback += f"Bitte analysiere die Fehlermeldungen und behebe sie:\n\n"
                        feedback += f"SANDBOX:\n{sandbox_result}\n\n"

                        # ÄNDERUNG 28.01.2026: Strukturiertes Test-Feedback nutzen (Phase 0.12)
                        structured_test_feedback = self._format_test_feedback(test_result)
                        if structured_test_feedback and "✅" not in structured_test_feedback:
                            feedback += f"\n{structured_test_feedback}\n"
                        else:
                            feedback += f"TESTER:\n{test_summary}\n"

                        # ÄNDERUNG 28.01.2026: Tech-Stack-spezifische Diagnose-Hinweise
                        test_lower = test_summary.lower()
                        if "leere seite" in test_lower or "leer" in test_lower or "kein sichtbar" in test_lower:
                            feedback += "\nDIAGNOSE - LEERE SEITE ERKANNT:\n"
                            pt = str(self.tech_blueprint.get("project_type", "")).lower()
                            lang = str(self.tech_blueprint.get("language", "")).lower()
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
                    else:
                        # Reviewer-Feedback (kein Security-Problem, keine Sandbox-Fehler)
                        feedback = review_output

                    self._ui_log("Reviewer", "Feedback", feedback)
                    # Memory: Zeichne fehlgeschlagene Iteration auf (geschützt, damit iteration++ nicht blockiert)
                    try:
                        memory_path = os.path.join(self.base_dir, "memory", "global_memory.json")
                        update_memory(memory_path, self.current_code, review_output, sandbox_result)
                    except Exception as mem_err:
                        self._ui_log("Memory", "Error", f"Memory-Operation fehlgeschlagen: {mem_err}")

                    # ÄNDERUNG 25.01.2026: Modellwechsel-Logik ("Kollegen fragen")
                    model_attempt += 1

                    # Speichere was dieses Modell versucht hat (für das nächste Modell)
                    failed_attempts_history.append({
                        "model": current_coder_model,
                        "attempt": model_attempt,
                        "iteration": iteration + 1,
                        "feedback": feedback[:500] if feedback else "",
                        "sandbox_error": sandbox_result[:300] if sandbox_failed else ""
                    })

                    # Prüfe ob Modellwechsel nötig
                    if model_attempt >= max_model_attempts:
                        old_model = current_coder_model

                        # Markiere aktuelles Modell als "erschöpft" für dieses Problem
                        self.model_router.mark_rate_limited_sync(current_coder_model)

                        # Hole neues Modell aus Fallback-Kette
                        current_coder_model = self.model_router.get_model("coder")

                        if current_coder_model != old_model:
                            models_used.append(current_coder_model)
                            model_attempt = 0  # Reset Zähler für neues Modell

                            # Neuen Agent mit neuem Modell erstellen
                            agent_coder = create_coder(self.config, project_rules, router=self.model_router)

                            # UI-Event für Modellwechsel
                            self._ui_log("Coder", "ModelSwitch", json.dumps({
                                "old_model": old_model,
                                "new_model": current_coder_model,
                                "reason": "max_attempts_reached",
                                "attempt": max_model_attempts,
                                "models_used": models_used,
                                "failed_attempts": len(failed_attempts_history)
                            }, ensure_ascii=False))

                            # KRITISCH: Gib dem neuen Modell die Historie der Fehlversuche
                            history_summary = "\n".join([
                                f"- Modell '{a['model']}' (Iteration {a['iteration']}): {a['feedback'][:200]}"
                                for a in failed_attempts_history[-3:]  # Letzte 3 Versuche
                            ])
                            feedback += f"\n\n🔄 MODELLWECHSEL: Das vorherige Modell ({old_model}) konnte dieses Problem nicht lösen.\n"
                            feedback += f"BISHERIGE VERSUCHE (diese Ansätze haben NICHT funktioniert):\n{history_summary}\n"
                            feedback += f"\nWICHTIG: Versuche einen VÖLLIG ANDEREN Ansatz! Was bisher versucht wurde, funktioniert nicht!\n"

                            self._ui_log("Coder", "Status", f"🔄 Modellwechsel: {old_model} → {current_coder_model} (Versuch {len(models_used)})")
                        else:
                            self._ui_log("Coder", "Warning", f"⚠️ Kein weiteres Modell verfügbar - fahre mit {current_coder_model} fort")

                    iteration += 1  # WICHTIG: Immer inkrementieren, auch bei Memory-Fehler!
                    self._current_iteration = iteration  # ÄNDERUNG 28.01.2026: Für Library-Protokollierung

            self.is_first_run = False
            if success:
                self._ui_log("System", "Success", "Projekt erfolgreich erstellt/geändert.")
                # ÄNDERUNG 28.01.2026: Projekt in Library als erfolgreich abschließen
                try:
                    library = get_library_manager()
                    library.complete_project(status="success")
                    self._ui_log("Library", "ProjectComplete", "Protokoll archiviert (success)")
                except Exception:
                    pass
                # ÄNDERUNG 28.01.2026: Session beenden
                try:
                    session_mgr = get_session_manager()
                    session_mgr.end_session(status="Success")
                except Exception:
                    pass
            else:
                self._ui_log("System", "Failure", "Maximale Retries erreicht.")
                # ÄNDERUNG 28.01.2026: Projekt in Library als fehlgeschlagen abschließen
                try:
                    library = get_library_manager()
                    library.complete_project(status="failed")
                    self._ui_log("Library", "ProjectComplete", "Protokoll archiviert (failed)")
                except Exception:
                    pass
                # ÄNDERUNG 28.01.2026: Session beenden
                try:
                    session_mgr = get_session_manager()
                    session_mgr.end_session(status="Error")
                except Exception:
                    pass
                # Memory: Lerne aus ungelösten Fehlern (geschützt)
                if feedback:
                    try:
                        memory_path = os.path.join(self.base_dir, "memory", "global_memory.json")
                        error_msg = extract_error_pattern(feedback)
                        tags = generate_tags_from_context(self.tech_blueprint, feedback)
                        tags.append("unresolved")
                        learn_result = learn_from_error(memory_path, error_msg, tags)
                        self._ui_log("Memory", "Learning", f"Ungelöst: {learn_result}")
                    except Exception as mem_err:
                        self._ui_log("Memory", "Error", f"Memory-Operation fehlgeschlagen: {mem_err}")

        except Exception as e:
            err = f"Fehler: {e}\n{traceback.format_exc()}"
            self._ui_log("System", "Error", err)
            # ÄNDERUNG 28.01.2026: Projekt in Library als Fehler abschließen
            try:
                library = get_library_manager()
                library.complete_project(status="error")
                self._ui_log("Library", "ProjectComplete", "Protokoll archiviert (error)")
            except Exception:
                pass
            # ÄNDERUNG 28.01.2026: Session beenden
            try:
                session_mgr = get_session_manager()
                session_mgr.end_session(status="Error")
            except Exception:
                pass
            raise e
