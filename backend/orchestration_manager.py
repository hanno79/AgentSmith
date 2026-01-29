# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 29.01.2026
Version: 2.2
Beschreibung: Orchestration Manager - Backend-Koordination mit LiteLLM Callbacks und Agent-Steuerung.
              ÄNDERUNG 28.01.2026: Library-Manager Integration für Protokollierung aller Agent-Aktionen
              ÄNDERUNG 28.01.2026: Informationsfluss-Reparatur zwischen Agenten:
                                   - Fix 1: Regex-Pattern für VULNERABILITY|FIX|SEVERITY korrigiert
                                   - Fix 3: Feedback-Logik ohne widersprüchliche OK+Security-Signale
                                   - Fix 4: Basis-Security-Hints für Iteration 1 (proaktive Guidance)
              ÄNDERUNG 25.01.2026: TokenMetrics, OK-Erkennung, OfficeManager, Security-Workflow
              ÄNDERUNG 29.01.2026: Discovery Briefing Integration fuer Agent-Kontext
              ÄNDERUNG 29.01.2026: Briefing wird mit Projekt in Library gespeichert
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
if not logging.getLogger().handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] [%(levelname)s] [%(funcName)s] - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

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

# ÄNDERUNG 29.01.2026: Robuste .env-Ladung mit mehreren Fallback-Pfaden
# Löst das Problem wenn Module aus Worktree-Pfad importiert werden
def _load_env_robust():
    """Lädt .env aus mehreren möglichen Pfaden."""
    possible_paths = [
        # 1. Expliziter bekannter Pfad (höchste Priorität)
        r"C:\Temp\multi_agent_poc\.env",
        # 2. Relativ zum aktuellen Arbeitsverzeichnis
        os.path.join(os.getcwd(), ".env"),
        # 3. Relativ zu __file__ (funktioniert wenn nicht im Worktree)
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"),
    ]

    for env_path in possible_paths:
        if os.path.exists(env_path):
            load_dotenv(env_path, override=True)
            logger.info(f".env geladen von: {env_path}")
            return env_path

    logger.warning("Keine .env gefunden! Geprüfte Pfade: %s", possible_paths)
    return None

_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_env_loaded_from = _load_env_robust()

# Agenten-Struktur (muss evtl. Pfade anpassen)
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.meta_orchestrator_agent import MetaOrchestratorV2
from agents.researcher_agent import create_researcher
from .agent_factory import init_agents
from agents.memory_agent import (
    update_memory, update_memory_async, get_lessons_for_prompt, learn_from_error,
    extract_error_pattern, generate_tags_from_context
)
from logger_utils import log_event
from budget_tracker import get_budget_tracker
from model_router import get_model_router
from .worker_pool import OfficeManager, WorkerStatus
from .orchestration_helpers import (
    extract_tables_from_schema,
    extract_design_data,
    is_model_unavailable_error,
    is_rate_limit_error
)
from .dev_loop import DevLoop
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
                logger.debug(
                    "_budget_tracking_callback: %s - %s+%s Tokens (Modell: %s)",
                    current_agent_name,
                    prompt_tokens,
                    completion_tokens,
                    model
                )
        except Exception as e:
            logger.exception("_budget_tracking_callback: Fehler beim Budget-Tracking: %s", e)

    # Registriere den Callback
    litellm.success_callback = [_budget_tracking_callback]
    logger.info("litellm.success_callback: Budget-Tracking Callback erfolgreich registriert")

except ImportError:
    logger.warning("litellm.success_callback: LiteLLM nicht verfuegbar - Budget-Tracking deaktiviert")
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


# ÄNDERUNG 29.01.2026: Import aus separatem Modul um zirkuläre Imports zu vermeiden
from .heartbeat_utils import run_with_heartbeat


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

        # ÄNDERUNG 29.01.2026: Discovery Briefing für Agent-Kontext
        self.discovery_briefing: Optional[Dict[str, Any]] = None

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

    # =========================================================================
    # DISCOVERY BRIEFING - ÄNDERUNG 29.01.2026
    # =========================================================================

    def set_discovery_briefing(self, briefing: Dict[str, Any]) -> None:
        """
        Setzt das Discovery-Briefing fuer Agent-Kontext.
        Das Briefing wird den Agenten als Kontext bereitgestellt.

        Args:
            briefing: Das Briefing-Objekt aus der Discovery Session
        """
        self.discovery_briefing = briefing
        self._ui_log("System", "DiscoveryBriefing",
                     f"Briefing aktiviert: {briefing.get('projectName', 'unbenannt')}")

    def get_briefing_context(self) -> str:
        """
        Generiert einen Kontext-String aus dem Briefing fuer Agent-System-Prompts.

        Returns:
            Formatierter Briefing-Kontext oder leerer String
        """
        if not self.discovery_briefing:
            return ""

        b = self.discovery_briefing
        if not isinstance(b, dict):
            return ""

        tech = b.get("techRequirements") if isinstance(b.get("techRequirements"), dict) else {}
        agents = b.get("agents") if isinstance(b.get("agents"), list) else []
        answers = b.get("answers") if isinstance(b.get("answers"), list) else []

        context = f"""
## PROJEKTBRIEFING (aus Discovery Session)

**Projektziel:** {b.get('goal', 'Nicht definiert')}

**Technische Anforderungen:**
- Programmiersprache: {tech.get('language', 'auto')}
- Deployment: {tech.get('deployment', 'local')}

**Beteiligte Agenten:** {', '.join(agents) if agents and all(isinstance(a, str) for a in agents) else 'Nicht definiert'}

**Wichtige Entscheidungen aus Discovery:**
"""

        for answer in answers:
            if not isinstance(answer, dict):
                continue
            if not answer.get('skipped', False):
                agent = answer.get('agent', 'Unbekannt')
                agent_text = str(agent) if agent is not None else "Unbekannt"
                values = answer.get('selectedValues', [])
                if not isinstance(values, list):
                    values = []
                custom = answer.get('customText', '')
                custom_text = str(custom) if custom is not None else ""
                values_text = ', '.join([str(v) for v in values]) if values else ""
                if values_text or custom_text:
                    context += f"- {agent_text}: {values_text if values_text else custom_text}\n"

        open_points = b.get('openPoints') if isinstance(b.get('openPoints'), list) else []
        if open_points:
            context += "\n**Offene Punkte (bitte beruecksichtigen):**\n"
            for point in open_points:
                context += f"- {point}\n"

        return context

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

    def run_task(self, user_goal: str):
        try:
            self._ui_log("System", "Task Start", f"Goal: {user_goal}")

            # ÄNDERUNG 28.01.2026: Projekt in Library starten für Protokollierung
            # ÄNDERUNG 29.01.2026: Discovery Briefing mit übergeben
            project_id = None
            try:
                library = get_library_manager()
                project_name = user_goal[:50] if len(user_goal) > 50 else user_goal
                library.start_project(
                    name=project_name,
                    goal=user_goal,
                    briefing=self.discovery_briefing
                )
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
                    # ÄNDERUNG 29.01.2026: Heartbeat-Wrapper für stabile WebSocket-Verbindung
                    research_result = run_with_heartbeat(
                        func=lambda: str(res_task.execute_sync()),
                        ui_log_callback=self._ui_log,
                        agent_name="Researcher",
                        task_description="Recherche-Phase",
                        heartbeat_interval=15,
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
                    # ÄNDERUNG 29.01.2026: 404/Model-Unavailable behandeln
                    if is_model_unavailable_error(e) or is_rate_limit_error(e):
                        self._ui_log("Researcher", "Warning", f"Recherche-Modell nicht verfügbar: {str(e)[:100]}")
                        self.model_router.mark_rate_limited_sync(research_model)
                    else:
                        self._ui_log("Researcher", "Error", f"Recherche fehlgeschlagen: {e}")
                    # ÄNDERUNG 25.01.2026: Worker-Status auf "idle" setzen (auch bei Fehler)
                    self._update_worker_status("researcher", "idle")
                    start_context = ""  # Ohne Recherche-Kontext fortfahren

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
                base_project_rules = self.config.get("templates", {}).get("webapp", {})
                if "techstack_architect" in plan_data["plan"]:
                    self._ui_log("TechArchitect", "Status", "Analysiere TechStack...")
                    set_current_agent("TechStack-Architect", project_id)  # Budget-Tracking
                    # ÄNDERUNG 25.01.2026: Worker-Status auf "working" setzen
                    self._update_worker_status("techstack_architect", "working", "Analysiere TechStack...", self.model_router.get_model("techstack_architect"))

                    # ÄNDERUNG 29.01.2026: Retry-Logik mit Modellwechsel bei 404/Unavailable
                    MAX_TECHSTACK_RETRIES = 3
                    techstack_result = None
                    for techstack_attempt in range(MAX_TECHSTACK_RETRIES):
                        current_techstack_model = self.model_router.get_model("techstack_architect")
                        try:
                            agent_techstack = init_agents(
                                self.config,
                                base_project_rules,
                                router=self.model_router,
                                include=["techstack_architect"]
                            ).get("techstack_architect")
                            techstack_task = Task(
                                description=f"Entscheide TechStack für: {user_goal}",
                                expected_output="JSON-Blueprint.",
                                agent=agent_techstack
                            )
                            # ÄNDERUNG 29.01.2026: Heartbeat-Wrapper für stabile WebSocket-Verbindung
                            techstack_result = run_with_heartbeat(
                                func=lambda: str(techstack_task.execute_sync()),
                                ui_log_callback=self._ui_log,
                                agent_name="TechStack",
                                task_description="Tech-Stack Analyse",
                                heartbeat_interval=15,
                                timeout_seconds=180
                            )
                            break  # Erfolg - Schleife verlassen
                        except Exception as ts_error:
                            # Bei 404/Model-Unavailable oder Rate-Limit: Modell wechseln
                            if is_model_unavailable_error(ts_error) or is_rate_limit_error(ts_error):
                                self._ui_log("TechStack", "Warning",
                                    f"Modell {current_techstack_model} nicht verfügbar (Versuch {techstack_attempt + 1}/{MAX_TECHSTACK_RETRIES}), wechsle zu Fallback...")
                                self.model_router.mark_rate_limited_sync(current_techstack_model)
                                if techstack_attempt == MAX_TECHSTACK_RETRIES - 1:
                                    # Alle Versuche fehlgeschlagen - Fallback auf static_html
                                    self._ui_log("TechStack", "Error", "Alle TechStack-Modelle nicht verfügbar, verwende Fallback")
                                    techstack_result = '{"project_type": "static_html", "language": "html"}'
                                continue
                            else:
                                # Anderer Fehler - weiterleiten
                                raise ts_error
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

            agents = init_agents(
                self.config,
                project_rules,
                router=self.model_router,
                include=["coder", "reviewer", "tester", "security"]
            )
            agent_coder = agents.get("coder")
            agent_reviewer = agents.get("reviewer")
            # ÄNDERUNG 28.01.2026: Tester mit router für konsistente Modell-Konfiguration (Phase 0.12)
            agent_tester = agents.get("tester")
            # ÄNDERUNG 25.01.2026: Security-Agent immer erstellen (für Re-Scan im DEV LOOP)
            agent_security = agents.get("security")
            
            # Design & DB (Nur beim ersten Mal)
            if self.is_first_run:
                if "database_designer" in plan_data["plan"]:
                    self._ui_log("DBDesigner", "Status", "Erstelle Schema...")
                    set_current_agent("Database-Designer", project_id)  # Budget-Tracking
                    dbdesigner_model = self.model_router.get_model("database_designer") if self.model_router else "unknown"
                    # ÄNDERUNG 25.01.2026: Worker-Status auf "working" setzen
                    self._update_worker_status("db_designer", "working", "Erstelle Schema...", dbdesigner_model)

                    # ÄNDERUNG 29.01.2026: Retry-Logik mit Modellwechsel bei 404/Unavailable
                    MAX_DB_RETRIES = 3
                    for db_attempt in range(MAX_DB_RETRIES):
                        current_db_model = self.model_router.get_model("database_designer")
                        try:
                            agent_db = init_agents(
                                self.config,
                                project_rules,
                                router=self.model_router,
                                include=["db_designer"]
                            ).get("db_designer")
                            if agent_db:
                                task_db = Task(description=f"Schema für {user_goal}", expected_output="Schema", agent=agent_db)
                                # ÄNDERUNG 29.01.2026: Heartbeat-Wrapper für stabile WebSocket-Verbindung
                                self.database_schema = run_with_heartbeat(
                                    func=lambda: str(task_db.execute_sync()),
                                    ui_log_callback=self._ui_log,
                                    agent_name="DB-Designer",
                                    task_description="Datenbank-Schema Erstellung",
                                    heartbeat_interval=15,
                                    timeout_seconds=180
                                )
                                break  # Erfolg
                        except Exception as db_error:
                            if is_model_unavailable_error(db_error) or is_rate_limit_error(db_error):
                                self._ui_log("DBDesigner", "Warning",
                                    f"Modell {current_db_model} nicht verfügbar (Versuch {db_attempt + 1}/{MAX_DB_RETRIES}), wechsle...")
                                self.model_router.mark_rate_limited_sync(current_db_model)
                                if db_attempt == MAX_DB_RETRIES - 1:
                                    self._ui_log("DBDesigner", "Error", "Alle DB-Modelle nicht verfügbar, überspringe Schema")
                                    self.database_schema = ""
                            else:
                                self._ui_log("DBDesigner", "Error", f"Schema-Fehler: {str(db_error)[:200]}")
                                self.database_schema = ""
                                break

                    # ÄNDERUNG 25.01.2026: Worker-Status auf "idle" setzen
                    self._update_worker_status("db_designer", "idle")

                    # ÄNDERUNG 24.01.2026: DBDesignerOutput Event für Frontend Office
                    self._ui_log("DBDesigner", "DBDesignerOutput", json.dumps({
                        "schema": self.database_schema[:2000] if self.database_schema else "",
                        "model": dbdesigner_model,
                        "status": "completed" if self.database_schema else "error",
                        "tables": extract_tables_from_schema(self.database_schema) if self.database_schema else [],
                        "timestamp": datetime.now().isoformat()
                    }, ensure_ascii=False))

                if "designer" in plan_data["plan"]:
                    self._ui_log("Designer", "Status", "Erstelle Design-Konzept...")
                    set_current_agent("Designer", project_id)  # Budget-Tracking
                    designer_model = self.model_router.get_model("designer") if self.model_router else "unknown"
                    # ÄNDERUNG 25.01.2026: Worker-Status auf "working" setzen
                    self._update_worker_status("designer", "working", "Erstelle Design-Konzept...", designer_model)

                    # ÄNDERUNG 29.01.2026: Retry-Logik mit Modellwechsel bei 404/Unavailable
                    MAX_DESIGN_RETRIES = 3
                    for design_attempt in range(MAX_DESIGN_RETRIES):
                        current_design_model = self.model_router.get_model("designer")
                        try:
                            agent_des = init_agents(
                                self.config,
                                project_rules,
                                router=self.model_router,
                                include=["designer"]
                            ).get("designer")
                            if agent_des:
                                # AENDERUNG 25.01.2026: Designer erhaelt TechStack-Blueprint
                                tech_info = f"Tech-Stack: {self.tech_blueprint.get('project_type', 'webapp')}"
                                if self.tech_blueprint.get('dependencies'):
                                    tech_info += f", Frameworks: {', '.join(self.tech_blueprint.get('dependencies', []))}"
                                task_des = Task(description=f"Design für: {user_goal}\n{tech_info}", expected_output="Konzept", agent=agent_des)
                                # ÄNDERUNG 29.01.2026: Heartbeat-Wrapper für stabile WebSocket-Verbindung
                                self.design_concept = run_with_heartbeat(
                                    func=lambda: str(task_des.execute_sync()),
                                    ui_log_callback=self._ui_log,
                                    agent_name="Designer",
                                    task_description="UI/UX Design",
                                    heartbeat_interval=15,
                                    timeout_seconds=180
                                )
                                break  # Erfolg
                        except Exception as des_error:
                            if is_model_unavailable_error(des_error) or is_rate_limit_error(des_error):
                                self._ui_log("Designer", "Warning",
                                    f"Modell {current_design_model} nicht verfügbar (Versuch {design_attempt + 1}/{MAX_DESIGN_RETRIES}), wechsle...")
                                self.model_router.mark_rate_limited_sync(current_design_model)
                                if design_attempt == MAX_DESIGN_RETRIES - 1:
                                    self._ui_log("Designer", "Error", "Alle Design-Modelle nicht verfügbar, überspringe Design")
                                    self.design_concept = ""
                            else:
                                self._ui_log("Designer", "Error", f"Design-Fehler: {str(des_error)[:200]}")
                                self.design_concept = ""
                                break

                    # ÄNDERUNG 25.01.2026: Worker-Status auf "idle" setzen
                    self._update_worker_status("designer", "idle")

                    # ÄNDERUNG 24.01.2026: DesignerOutput Event für Frontend Office
                    if self.design_concept:
                        design_data = extract_design_data(self.design_concept)
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
            dev_loop = DevLoop(self, set_current_agent, run_with_timeout)
            success, feedback = dev_loop.run(
                user_goal=user_goal,
                project_rules=project_rules,
                agent_coder=agent_coder,
                agent_reviewer=agent_reviewer,
                agent_tester=agent_tester,
                agent_security=agent_security,
                project_id=project_id
            )

            # ÄNDERUNG 29.01.2026: Iterationsstatus wird im DevLoop verwaltet

















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
