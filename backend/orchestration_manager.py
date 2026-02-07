# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 01.02.2026
Version: 2.6
Beschreibung: Orchestration Manager - Backend-Koordination mit LiteLLM Callbacks und Agent-Steuerung.
              AENDERUNG 01.02.2026: on_fallback Callback - WorkerStatus wird bei Modell-Fallback aktualisiert
              ÄNDERUNG 31.01.2026: Refaktoriert - Module ausgelagert für Regel 1 (Max 500 Zeilen)
              - orchestration_budget.py: Budget-Tracking, LiteLLM Callbacks
              - orchestration_utils.py: JSON-Reparatur, Requirements-Extraktion
              - orchestration_help_handler.py: HELP_NEEDED Events, Test-Generator
              - orchestration_discovery.py: Discovery Briefing Logik
              - orchestration_worker_status.py: Worker-Status Management
              - orchestration_readme.py: README-Generierung
"""

import os
import json
import yaml
import re
import traceback
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
    "Coder": "coder", "Reviewer": "reviewer", "Tester": "tester",
    "Designer": "designer", "Security": "security", "Researcher": "researcher",
    "TechArchitect": "techstack", "DBDesigner": "dbdesigner"
}

# ÄNDERUNG 31.01.2026: Robuste .env-Ladung
def _load_env_robust():
    """Lädt .env aus mehreren möglichen Pfaden."""
    possible_paths = [
        os.path.join(os.getcwd(), ".env"),
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

# Agenten-Struktur
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
    is_model_unavailable_error, is_rate_limit_error, is_empty_response_error
)
from .dev_loop import DevLoop
from .library_manager import get_library_manager
from .session_manager import get_session_manager
from .quality_gate import QualityGate
from .agent_message import AgentMessage, create_help_needed
from .documentation_service import DocumentationService
from .heartbeat_utils import run_with_heartbeat
from file_utils import find_html_file, find_python_entry
from crewai import Task

# ÄNDERUNG 31.01.2026: Imports aus ausgelagerten Modulen
from .orchestration_budget import set_current_agent
from .orchestration_utils import run_with_timeout
from .orchestration_discovery import format_briefing_context
from .orchestration_worker_status import (
    update_worker_status, handle_worker_status_change, AGENT_NAMES_MAPPING
)
from .orchestration_readme import generate_simple_readme, generate_readme_with_agent
from .orchestration_help_handler import handle_help_needed_events
from .orchestration_phases import run_techstack_phase, run_db_designer_phase, run_designer_phase

# AENDERUNG 01.02.2026: External Bureau Integration fuer Augment Context
try:
    from agents.external_bureau_manager import ExternalBureauManager
    EXTERNAL_BUREAU_AVAILABLE = True
except ImportError:
    EXTERNAL_BUREAU_AVAILABLE = False
    logger.debug("ExternalBureauManager nicht verfuegbar")

# AENDERUNG 01.02.2026: Universal Task Derivation System (UTDS)
from .dev_loop_task_derivation import DevLoopTaskDerivation


class OrchestrationManager:
    def __init__(self, config_path: str = None):
        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        os.makedirs(os.path.join(self.base_dir, "projects"), exist_ok=True)
        os.makedirs(os.path.join(self.base_dir, "memory"), exist_ok=True)

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
        self.security_vulnerabilities = []
        self.force_security_fix = False
        self.discovery_briefing: Optional[Dict[str, Any]] = None
        self.model_router = get_model_router(self.config)
        # AENDERUNG 01.02.2026: Fallback-Callback um WorkerStatus zu aktualisieren
        self.model_router.on_fallback = self._handle_model_fallback
        self.project_rules = {}

        # AENDERUNG 02.02.2026: Planner Office hinzugefuegt
        self.office_manager = OfficeManager(
            on_status_change=self._handle_worker_status_change,
            config={
                "coder": {"max_workers": 3}, "tester": {"max_workers": 2},
                "designer": {"max_workers": 1}, "db_designer": {"max_workers": 1},
                "security": {"max_workers": 1}, "researcher": {"max_workers": 1},
                "reviewer": {"max_workers": 1}, "techstack_architect": {"max_workers": 1},
                "planner": {"max_workers": 1},
            }
        )
        self.on_log: Optional[Callable[[str, str, str], None]] = None

        # AENDERUNG 01.02.2026: External Bureau fuer Augment Context
        self.external_bureau = None
        if EXTERNAL_BUREAU_AVAILABLE:
            try:
                self.external_bureau = ExternalBureauManager(self.config)
                augment_cfg = self.config.get("external_specialists", {}).get("augment_context", {})
                if augment_cfg.get("auto_activate", False):
                    self.external_bureau.activate_specialist("augment")
                    logger.info("Augment Context auto-aktiviert fuer DevLoop")
            except Exception as e:
                logger.warning(f"External Bureau nicht verfuegbar: {e}")
                self.external_bureau = None

    def _load_config(self):
        with open(self.config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    def _ui_log(self, agent: str, event: str, message: str):
        if self.on_log:
            self.on_log(agent, event, message)
        log_event(agent, event, message)
        try:
            library = get_library_manager()
            if library.current_project:
                library.log_entry(from_agent=agent, to_agent="System", entry_type=event,
                                  content=message, iteration=getattr(self, '_current_iteration', 0))
        except Exception:
            pass
        try:
            session_mgr = get_session_manager()
            session_mgr.add_log(agent, event, message)
            if event in ("Status", "Working", "Result", "Complete", "Error", "HELP_NEEDED"):
                agent_lower = agent.lower().replace("-", "").replace(" ", "")
                session_key = AGENT_TO_SESSION_KEY.get(agent, agent_lower)
                session_mgr.set_agent_active(session_key, event in ("Status", "Working"))
                if event == "HELP_NEEDED":
                    session_mgr.set_agent_blocked(session_key, True, message)
        except Exception:
            pass

    def _log_help_needed(self, agent: str, reason: str, context: dict = None, action_required: str = "manual_review"):
        project_id = os.path.basename(self.project_path) if self.project_path else None
        help_msg = create_help_needed(agent=agent, reason=reason, context=context,
                                      action_required=action_required, project_id=project_id)
        self._ui_log(*help_msg.to_legacy())

    def _handle_help_needed_events(self, iteration: int) -> Dict[str, Any]:
        """Wrapper für ausgelagerte HELP_NEEDED Handler Funktion."""
        return handle_help_needed_events(
            session_mgr=get_session_manager(),
            project_path=self.project_path,
            tech_blueprint=self.tech_blueprint,
            project_rules=self.project_rules,
            model_router=self.model_router,
            config=self.config,
            ui_log_callback=self._ui_log,
            iteration=iteration
        )

    def set_discovery_briefing(self, briefing: Dict[str, Any]) -> None:
        self.discovery_briefing = briefing
        self._ui_log("System", "DiscoveryBriefing",
                     f"Briefing aktiviert: {briefing.get('projectName', 'unbenannt')}")

    def get_briefing_context(self) -> str:
        return format_briefing_context(self.discovery_briefing)

    def _format_briefing_for_utds(self, briefing: Dict[str, Any]) -> str:
        """Formatiert Discovery-Briefing fuer UTDS Task-Ableitung."""
        parts = []
        if briefing.get("projectName"):
            parts.append(f"Projekt: {briefing['projectName']}")
        if briefing.get("projectDescription"):
            parts.append(f"Beschreibung: {briefing['projectDescription']}")
        if briefing.get("targetUsers"):
            parts.append(f"Zielgruppe: {briefing['targetUsers']}")
        if briefing.get("mainFeatures"):
            features = briefing["mainFeatures"]
            if isinstance(features, list):
                parts.append("Hauptfeatures:\n" + "\n".join(f"- {f}" for f in features))
            else:
                parts.append(f"Hauptfeatures: {features}")
        if briefing.get("technicalRequirements"):
            parts.append(f"Technische Anforderungen: {briefing['technicalRequirements']}")
        if briefing.get("agentResponses"):
            for resp in briefing["agentResponses"][:5]:  # Max 5 Antworten
                agent = resp.get("agent", "Agent")
                answer = resp.get("answer", "")[:300]
                parts.append(f"\n{agent}: {answer}")
        return "\n\n".join(parts) if parts else str(briefing)

    async def _handle_worker_status_change(self, data: Dict[str, Any]):
        await handle_worker_status_change(data, self.on_log)

    def _handle_model_fallback(self, agent_role: str, primary: str, fallback: str):
        """
        AENDERUNG 01.02.2026: Callback wenn ModelRouter zu Fallback wechselt.
        Aktualisiert den aktiven Worker mit dem neuen Modell.
        """
        # Mapping von agent_role zu office
        role_to_office = {
            "coder": "coder", "tester": "tester", "designer": "designer",
            "database_designer": "db_designer", "db_designer": "db_designer",
            "security": "security", "researcher": "researcher",
            "reviewer": "reviewer", "techstack_architect": "techstack_architect",
            "meta_orchestrator": None, "orchestrator": None  # Keine Worker-Pools
        }
        office = role_to_office.get(agent_role)
        if not office:
            return

        # Aktiven Worker finden und Modell aktualisieren
        pool = self.office_manager.get_pool(office)
        if pool:
            active_workers = pool.get_active_workers()
            for worker in active_workers:
                worker.model = fallback
                # WorkerStatus Event senden mit neuem Modell
                if self.on_log:
                    import json
                    from .orchestration_worker_status import AGENT_NAMES_MAPPING
                    agent_name = AGENT_NAMES_MAPPING.get(office, "System")
                    self.on_log(agent_name, "ModelFallback", json.dumps({
                        "office": office,
                        "worker_id": worker.id,
                        "old_model": primary,
                        "new_model": fallback,
                        "reason": "rate_limited"
                    }, ensure_ascii=False))

    def _generate_simple_readme(self, context: str) -> str:
        return generate_simple_readme(self.project_path, self.tech_blueprint,
                                      self.discovery_briefing, getattr(self, 'doc_service', None))

    def _generate_readme_with_agent(self, context: str) -> str:
        return generate_readme_with_agent(
            context=context, config=self.config, project_rules=self.project_rules,
            model_router=self.model_router, project_path=self.project_path,
            tech_blueprint=self.tech_blueprint, discovery_briefing=self.discovery_briefing,
            doc_service=getattr(self, 'doc_service', None), ui_log_callback=self._ui_log,
            update_worker_status_callback=self._update_worker_status
        )

    def _update_worker_status(self, office: str, worker_status: str, task_description: str = None, model: str = None):
        update_worker_status(self.office_manager, office, worker_status, self._ui_log, task_description, model)

    def run_task(self, user_goal: str):
        try:
            self._ui_log("System", "Task Start", f"Goal: {user_goal}")
            project_id = None
            try:
                library = get_library_manager()
                project_name = user_goal[:50] if len(user_goal) > 50 else user_goal
                library.start_project(name=project_name, goal=user_goal, briefing=self.discovery_briefing)
                project_id = library.current_project.get('project_id')
                self._ui_log("Library", "ProjectStart", f"Protokollierung gestartet: {project_id}")
            except Exception as lib_err:
                self._ui_log("Library", "Warning", f"Library-Start fehlgeschlagen: {lib_err}")

            try:
                session_mgr = get_session_manager()
                session_mgr.start_session(goal=user_goal, project_id=project_id)
                session_mgr.update_status("Working")
            except Exception as sess_err:
                self._ui_log("System", "Warning", f"Session-Start fehlgeschlagen: {sess_err}")

            if self.project_path:
                project_id = os.path.basename(self.project_path)

            AGENT_TIMEOUT = self.config.get("agent_timeout_seconds", 300)
            MAX_RESEARCHER_RETRIES = 3
            start_context = ""
            research_query = ""
            research_result = ""

            # AENDERUNG 01.02.2026: UTDS - Initial Task Derivation
            # Zerlegt die Aufgabenstellung in strukturierte Tasks
            initial_tasks = []
            try:
                if not hasattr(self, '_task_derivation'):
                    self._task_derivation = DevLoopTaskDerivation(self, self.config)

                # Kontext zusammenstellen
                utds_context = {
                    "is_initial": True,
                    "has_discovery": bool(self.discovery_briefing),
                    "tech_stack": "unknown"  # Wird spaeter durch TechStack-Phase gesetzt
                }

                # User Goal oder Discovery Briefing als Basis
                derivation_input = user_goal
                derivation_source = "initial"

                if self.discovery_briefing:
                    # Falls Discovery-Briefing vorhanden, dieses als Basis nutzen
                    derivation_source = "discovery"
                    briefing_text = self._format_briefing_for_utds(self.discovery_briefing)
                    derivation_input = briefing_text

                # Task-Ableitung durchfuehren
                result = self._task_derivation.deriver.derive_tasks(
                    derivation_input, derivation_source, utds_context
                )

                if result.tasks:
                    initial_tasks = result.tasks
                    self._task_derivation.tracker.log_derivation_result(result)
                    self._ui_log("UTDS", "InitialDerivation", json.dumps({
                        "source": derivation_source,
                        "total_tasks": result.total_tasks,
                        "by_category": result.tasks_by_category,
                        "by_priority": result.tasks_by_priority
                    }, ensure_ascii=False))
                    logger.info(f"[UTDS] {result.total_tasks} Initial-Tasks abgeleitet aus {derivation_source}")
                else:
                    self._ui_log("UTDS", "InitialDerivation", "Keine Tasks abgeleitet - nutze Standard-Flow")

            except Exception as utds_err:
                logger.warning(f"[UTDS] Initial-Derivation fehlgeschlagen: {utds_err}")
                self._ui_log("UTDS", "Warning", f"Initial-Derivation uebersprungen: {utds_err}")

            # 🔎 RESEARCH PHASE
            if self.is_first_run:
                timeout_minutes = self.config.get("research_timeout_minutes", 5)
                RESEARCH_TIMEOUT_SECONDS = timeout_minutes * 60
                research_query = f"Suche technische Details für: {user_goal}"

                for researcher_attempt in range(MAX_RESEARCHER_RETRIES):
                    research_model = self.model_router.get_model("researcher") if self.model_router else "unknown"
                    self._ui_log("Researcher", "ResearchOutput", json.dumps({
                        "query": research_query, "result": "", "status": "searching",
                        "model": research_model, "timeout_seconds": RESEARCH_TIMEOUT_SECONDS,
                        "attempt": researcher_attempt + 1, "max_attempts": MAX_RESEARCHER_RETRIES
                    }, ensure_ascii=False))

                    try:
                        self._ui_log("Researcher", "Status", f"Sucht Kontext... (max. {RESEARCH_TIMEOUT_SECONDS}s, Versuch {researcher_attempt + 1}/{MAX_RESEARCHER_RETRIES})")
                        set_current_agent("Researcher", project_id)
                        self._update_worker_status("researcher", "working", f"Recherche: {research_query[:50]}...", research_model)
                        res_agent = create_researcher(self.config, self.config.get("templates", {}).get("webapp", {}), router=self.model_router)
                        res_task = Task(description=research_query, expected_output="Zusammenfassung.", agent=res_agent)
                        research_result = run_with_heartbeat(
                            func=lambda: str(res_task.execute_sync()), ui_log_callback=self._ui_log,
                            agent_name="Researcher", task_description="Recherche-Phase",
                            heartbeat_interval=15, timeout_seconds=RESEARCH_TIMEOUT_SECONDS
                        )
                        start_context = f"\n\nRecherche-Ergebnisse:\n{research_result}"
                        self._ui_log("Researcher", "Result", "Recherche abgeschlossen.")
                        self._update_worker_status("researcher", "idle")
                        self._ui_log("Researcher", "ResearchOutput", json.dumps({
                            "query": research_query, "result": research_result[:2000],
                            "status": "completed", "model": research_model, "timeout_seconds": RESEARCH_TIMEOUT_SECONDS
                        }, ensure_ascii=False))
                        break
                    except TimeoutError as te:
                        self._ui_log("Researcher", "Timeout", f"Recherche abgebrochen: {te}")
                        self._update_worker_status("researcher", "idle")
                        start_context = ""
                        self._ui_log("Researcher", "ResearchOutput", json.dumps({
                            "query": research_query, "result": "", "status": "timeout",
                            "model": research_model, "error": str(te)
                        }, ensure_ascii=False))
                        break
                    except Exception as e:
                        if is_model_unavailable_error(e) or is_rate_limit_error(e) or is_empty_response_error(e):
                            self._ui_log("Researcher", "Warning", f"Modell {research_model} nicht verfügbar (Versuch {researcher_attempt + 1}/{MAX_RESEARCHER_RETRIES}): {str(e)[:80]}")
                            self.model_router.mark_rate_limited_sync(research_model)
                            self._update_worker_status("researcher", "idle")
                            if researcher_attempt < MAX_RESEARCHER_RETRIES - 1:
                                self._ui_log("Researcher", "Info", "Wechsle zu Fallback-Modell...")
                                continue
                            else:
                                self._ui_log("Researcher", "Error", f"Recherche nach {MAX_RESEARCHER_RETRIES} Versuchen fehlgeschlagen")
                        else:
                            self._ui_log("Researcher", "Error", f"Recherche fehlgeschlagen: {e}")
                        self._update_worker_status("researcher", "idle")
                        start_context = ""
                        self._ui_log("Researcher", "ResearchOutput", json.dumps({
                            "query": research_query, "result": "", "status": "error",
                            "model": research_model, "error": str(e), "attempt": researcher_attempt + 1
                        }, ensure_ascii=False))
                        break

            # 🧠 META-ORCHESTRATOR
            MAX_META_RETRIES = 3
            plan_data = None
            for meta_attempt in range(MAX_META_RETRIES):
                current_meta_model = self.model_router.get_model("meta_orchestrator") if self.model_router else "unknown"
                try:
                    self._ui_log("Orchestrator", "Status", f"Analysiere Intent (Versuch {meta_attempt + 1}/{MAX_META_RETRIES})...")
                    set_current_agent("Meta-Orchestrator", project_id)
                    meta_orchestrator = MetaOrchestratorV2()
                    plan_data = meta_orchestrator.orchestrate(user_goal + start_context)
                    self._ui_log("Orchestrator", "Analysis", json.dumps(plan_data["analysis"], ensure_ascii=False))
                    break
                except Exception as meta_err:
                    if is_model_unavailable_error(meta_err) or is_rate_limit_error(meta_err) or is_empty_response_error(meta_err):
                        self._ui_log("Orchestrator", "Warning", f"Meta-Modell {current_meta_model} nicht verfügbar (Versuch {meta_attempt + 1}/{MAX_META_RETRIES})")
                        self.model_router.mark_rate_limited_sync(current_meta_model)
                        if meta_attempt < MAX_META_RETRIES - 1:
                            continue
                    self._ui_log("Orchestrator", "Error", f"Meta-Orchestrator Fehler: {str(meta_err)[:200]}")
                    raise meta_err

            if not plan_data:
                self._log_help_needed(agent="Orchestrator", reason="no_orchestration_plan",
                    context={"user_goal": user_goal[:200], "attempts": MAX_META_RETRIES, "research_available": bool(start_context)},
                    action_required="clarify_requirements")
                raise RuntimeError("Meta-Orchestrator konnte keinen Plan erstellen nach allen Versuchen")

            # 📦 PROJEKTSTRUKTUR
            if self.is_first_run:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                project_name = f"project_{timestamp}"
                self.project_path = os.path.join(self.base_dir, "projects", project_name)
                os.makedirs(self.project_path, exist_ok=True)
                STANDARD_PROJECT_DIRS = ["tests", "docs", "src", "assets"]
                for dir_name in STANDARD_PROJECT_DIRS:
                    os.makedirs(os.path.join(self.project_path, dir_name), exist_ok=True)
                self._ui_log("System", "ProjectStructure", f"Standard-Ordner erstellt: {', '.join(STANDARD_PROJECT_DIRS)}")
                project_id = project_name
                set_current_agent("System", project_id)

                # 🛠️ TECHSTACK
                base_project_rules = self.config.get("templates", {}).get("webapp", {})
                if "techstack_architect" in plan_data["plan"]:
                    self._run_techstack_phase(user_goal, base_project_rules, project_id, AGENT_TIMEOUT)

                self.doc_service = DocumentationService(self.project_path)
                self.doc_service.collect_goal(user_goal)
                self.doc_service.collect_briefing(self.discovery_briefing or {})
                self.doc_service.collect_techstack(self.tech_blueprint)

                # Output-Pfad
                run_cmd = self.tech_blueprint.get("run_command", "")
                if "python" in run_cmd:
                    self.output_path = os.path.join(self.project_path, "app.py")
                elif "node" in run_cmd:
                    self.output_path = os.path.join(self.project_path, "index.js")
                else:
                    self.output_path = os.path.join(self.project_path, "index.html")

                self._create_run_bat()
                self._run_dependency_phase()

            # 🧩 AGENTEN INITIALISIERUNG
            project_type = self.tech_blueprint.get("project_type", "webapp")
            self.project_rules = self.config.get("templates", {}).get(project_type, {})
            agents = init_agents(self.config, self.project_rules, router=self.model_router,
                                 include=["coder", "reviewer", "tester", "security"])
            agent_coder = agents.get("coder")
            agent_reviewer = agents.get("reviewer")
            agent_tester = agents.get("tester")
            agent_security = agents.get("security")

            # Design & DB
            if self.is_first_run:
                if "database_designer" in plan_data["plan"]:
                    self._run_db_designer_phase(user_goal, self.project_rules, project_id, AGENT_TIMEOUT)
                if "designer" in plan_data["plan"]:
                    self._run_designer_phase(user_goal, self.project_rules, project_id, AGENT_TIMEOUT)
                self._ui_log("Security", "Status", "Security-Scan wird nach Code-Generierung durchgeführt...")

            # 🔄 DEV LOOP
            dev_loop = DevLoop(self, set_current_agent, run_with_timeout)
            success, feedback = dev_loop.run(
                user_goal=user_goal, project_rules=self.project_rules,
                agent_coder=agent_coder, agent_reviewer=agent_reviewer,
                agent_tester=agent_tester, agent_security=agent_security, project_id=project_id
            )

            # ÄNDERUNG 03.02.2026: Entfernt - wird jetzt in dev_loop.py nach erster Iteration gesetzt (Fix 6)
            # self.is_first_run = False
            if success:
                self._ui_log("System", "Success", "Projekt erfolgreich erstellt/geändert.")
                self._finalize_success(project_id)
            else:
                self._ui_log("System", "Failure", "Maximale Retries erreicht.")
                self._finalize_failure(feedback)

        except Exception as e:
            err = f"Fehler: {e}\n{traceback.format_exc()}"
            self._ui_log("System", "Error", err)
            self._finalize_error()
            raise e

    def _run_techstack_phase(self, user_goal: str, base_project_rules: dict, project_id: str, agent_timeout: int):
        """TechStack-Analyse Phase (Wrapper für ausgelagerte Funktion)."""
        self.tech_blueprint, self.quality_gate = run_techstack_phase(
            user_goal=user_goal, base_project_rules=base_project_rules, project_id=project_id,
            agent_timeout=agent_timeout, config=self.config, model_router=self.model_router,
            project_path=self.project_path, discovery_briefing=self.discovery_briefing,
            ui_log_callback=self._ui_log, update_worker_status_callback=self._update_worker_status
        )

    def _run_db_designer_phase(self, user_goal: str, project_rules: dict, project_id: str, agent_timeout: int):
        """DB-Designer Phase (Wrapper für ausgelagerte Funktion)."""
        self.database_schema = run_db_designer_phase(
            user_goal=user_goal, project_rules=project_rules, project_id=project_id,
            agent_timeout=agent_timeout, config=self.config, model_router=self.model_router,
            tech_blueprint=self.tech_blueprint, quality_gate=getattr(self, 'quality_gate', None),
            doc_service=getattr(self, 'doc_service', None),
            ui_log_callback=self._ui_log, update_worker_status_callback=self._update_worker_status
        )

    def _run_designer_phase(self, user_goal: str, project_rules: dict, project_id: str, agent_timeout: int):
        """Designer Phase (Wrapper für ausgelagerte Funktion)."""
        self.design_concept = run_designer_phase(
            user_goal=user_goal, project_rules=project_rules, project_id=project_id,
            project_path=self.project_path, agent_timeout=agent_timeout, config=self.config,
            model_router=self.model_router, tech_blueprint=self.tech_blueprint,
            quality_gate=getattr(self, 'quality_gate', None),
            doc_service=getattr(self, 'doc_service', None),
            ui_log_callback=self._ui_log, update_worker_status_callback=self._update_worker_status
        )

    def _create_run_bat(self):
        """Erstellt eine intelligente run.bat."""
        _pt = self.tech_blueprint.get("project_type", "webapp")
        run_bat_path = os.path.join(self.project_path, "run.bat")
        run_bat_content = "@echo off\necho Launching Multi-Agent Project...\n"

        if self.tech_blueprint.get("language") == "python":
            run_bat_content += "if not exist venv ( python -m venv venv )\ncall venv\\Scripts\\activate\n"
            if self.tech_blueprint.get("install_command"):
                run_bat_content += f"call {self.tech_blueprint['install_command']}\n"
        elif self.tech_blueprint.get("language") == "javascript":
            if self.tech_blueprint.get("install_command"):
                run_bat_content += f"call {self.tech_blueprint['install_command']}\n"

        if _pt == "webapp" or self.output_path.endswith(".html"):
            url = "index.html"
            if "flask" in str(self.tech_blueprint).lower(): url = "http://localhost:5000"
            elif "fastapi" in str(self.tech_blueprint).lower(): url = "http://localhost:8000"
            elif "uvicorn" in str(self.tech_blueprint).lower(): url = "http://localhost:8000"
            if url.startswith("http"):
                run_bat_content += f"start {url}\n"
            else:
                run_bat_content += f"start {os.path.basename(self.output_path)}\n"

        run_cmd = self.tech_blueprint.get("run_command", "")
        if run_cmd:
            run_bat_content += f"{run_cmd}\n"
        run_bat_content += "pause\n"

        with open(run_bat_path, "w", encoding="utf-8") as f:
            f.write(run_bat_content)
        self._ui_log("System", "Config", "run.bat created.")

    def _run_dependency_phase(self):
        """Dependency-Agent Phase."""
        try:
            from agents.dependency_agent import get_dependency_agent
            dep_agent = get_dependency_agent(self.config.get("dependency_agent", {}))
            dep_agent.on_log = self._ui_log
            self._ui_log("DependencyAgent", "Status", "Pruefe und installiere Dependencies...")
            dep_result = dep_agent.prepare_for_task(self.tech_blueprint, self.project_path)
            if dep_result.get("status") == "OK":
                self._ui_log("DependencyAgent", "DependencyStatus", json.dumps({
                    "status": "ready", "health_score": dep_result.get("inventory", {}).get("health_score", 0)
                }, ensure_ascii=False))
            elif dep_result.get("warnings"):
                self._ui_log("DependencyAgent", "DependencyStatus", json.dumps({
                    "status": "warning", "warnings": dep_result.get("warnings", [])
                }, ensure_ascii=False))
                for warning in dep_result.get("warnings", []):
                    self._ui_log("DependencyAgent", "Warning", warning)
        except Exception as dep_error:
            self._ui_log("DependencyAgent", "Error", f"Dependency-Pruefung fehlgeschlagen: {dep_error}")

    def _finalize_success(self, project_id: str):
        """Finalisierung bei Erfolg."""
        try:
            if hasattr(self, 'doc_service') and self.doc_service:
                self._ui_log("DocumentationManager", "Status", "Generiere Projekt-Dokumentation...")
                readme_context = self.doc_service.generate_readme_context()
                readme_content = self._generate_readme_with_agent(readme_context)
                readme_path = self.doc_service.save_readme(readme_content)
                if readme_path:
                    self._ui_log("DocumentationManager", "Result", f"README.md erstellt: {readme_path}")
                changelog_path = self.doc_service.save_changelog()
                if changelog_path:
                    self._ui_log("DocumentationManager", "Result", f"CHANGELOG.md erstellt: {changelog_path}")
                self._ui_log("DocumentationManager", "DocumentationComplete", json.dumps({
                    "readme": readme_path or "", "changelog": changelog_path or "",
                    "summary": self.doc_service.get_summary()
                }, ensure_ascii=False))
        except Exception as doc_err:
            self._ui_log("DocumentationManager", "Warning", f"Dokumentations-Generierung fehlgeschlagen: {doc_err}")
        try:
            library = get_library_manager()
            library.complete_project(status="success")
            self._ui_log("Library", "ProjectComplete", "Protokoll archiviert (success)")
        except Exception:
            pass
        try:
            session_mgr = get_session_manager()
            session_mgr.end_session(status="Success")
        except Exception:
            pass

    def _finalize_failure(self, feedback: str):
        """Finalisierung bei Fehlschlag."""
        try:
            library = get_library_manager()
            library.complete_project(status="failed")
            self._ui_log("Library", "ProjectComplete", "Protokoll archiviert (failed)")
        except Exception:
            pass
        try:
            session_mgr = get_session_manager()
            session_mgr.end_session(status="Error")
        except Exception:
            pass
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

    def _finalize_error(self):
        """Finalisierung bei Fehler."""
        try:
            library = get_library_manager()
            library.complete_project(status="error")
            self._ui_log("Library", "ProjectComplete", "Protokoll archiviert (error)")
        except Exception:
            pass
        try:
            session_mgr = get_session_manager()
            session_mgr.end_session(status="Error")
        except Exception:
            pass
