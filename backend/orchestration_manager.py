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
# AENDERUNG 08.02.2026: Fix 24 - Waisen-Check Phase
from .orchestration_phases import run_waisen_check_phase
from .dev_loop import DevLoop
from .library_manager import get_library_manager
from .session_manager import get_session_manager
from .quality_gate import QualityGate
from .agent_message import AgentMessage, create_help_needed
from .documentation_service import DocumentationService
from .heartbeat_utils import run_with_heartbeat
from file_utils import find_html_file, find_python_entry
from crewai import Task

# AENDERUNG 09.02.2026: ModelStatsDB fuer Run-Tracking (Fix 40)
from model_stats_db import get_model_stats_db

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

        # AENDERUNG 13.02.2026: Feature-Tracking DB initialisieren
        self._feature_id_map = {}  # Mapping file_path → feature_id (gesetzt nach Planner)
        self._feature_tracking_db = None  # Lazy-Init bei erstem Zugriff

        # AENDERUNG 21.02.2026: Claude SDK Provider (zusaetzliches LLM-Backend neben OpenRouter)
        self.claude_provider = None
        if self.config.get("claude_sdk", {}).get("enabled", False):
            try:
                from .claude_sdk_provider import get_claude_sdk_provider
                self.claude_provider = get_claude_sdk_provider()
                logger.info("Claude SDK Provider aktiviert (Max Plan Backend)")
            except ImportError as e:
                logger.warning("Claude SDK Provider nicht verfuegbar: %s", e)

        # AENDERUNG 01.02.2026: External Bureau fuer Augment Context
        self.external_bureau = None
        if EXTERNAL_BUREAU_AVAILABLE:
            try:
                self.external_bureau = ExternalBureauManager(self.config)
                augment_cfg = self.config.get("external_specialists", {}).get("augment_context", {})
                if augment_cfg.get("auto_activate", False):
                    self.external_bureau.activate_specialist("augment")
                    logger.info("Augment Context auto-aktiviert fuer DevLoop")
                # AENDERUNG 08.02.2026: Fix 33 - CodeRabbit auto-aktivieren
                coderabbit_cfg = self.config.get("external_specialists", {}).get("coderabbit", {})
                if coderabbit_cfg.get("enabled", False):
                    activate_result = self.external_bureau.activate_specialist("coderabbit")
                    if activate_result.get("success"):
                        logger.info("CodeRabbit auto-aktiviert fuer DevLoop")
                    else:
                        logger.info(f"CodeRabbit nicht verfuegbar: {activate_result.get('message')}")
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

    def get_provider(self, role: str) -> str:
        """
        Gibt den konfigurierten Provider fuer eine Agent-Rolle zurueck.
        AENDERUNG 21.02.2026: Claude SDK als zusaetzliches Backend.

        Args:
            role: Agent-Rolle (z.B. "coder", "reviewer")

        Returns:
            "claude-sdk" wenn aktiviert und Rolle konfiguriert, sonst "openrouter"
        """
        if self.claude_provider and role in self.config.get("claude_sdk", {}).get("agent_models", {}):
            return "claude-sdk"
        return "openrouter"

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
        # AENDERUNG 21.02.2026: Fix 59g — manager durchreichen fuer Claude SDK Integration
        return generate_readme_with_agent(
            context=context, config=self.config, project_rules=self.project_rules,
            model_router=self.model_router, project_path=self.project_path,
            tech_blueprint=self.tech_blueprint, discovery_briefing=self.discovery_briefing,
            doc_service=getattr(self, 'doc_service', None), ui_log_callback=self._ui_log,
            update_worker_status_callback=self._update_worker_status,
            manager=self
        )

    def _update_worker_status(self, office: str, worker_status: str, task_description: str = None, model: str = None):
        update_worker_status(self.office_manager, office, worker_status, self._ui_log, task_description, model)

    def _sanitize_project_name(self, name: str) -> str:
        """
        Bereinigt benutzerdefinierten Projektnamen.
        Entfernt Sonderzeichen, ersetzt Leerzeichen durch Unterstrich, max 50 Zeichen.
        AENDERUNG 09.02.2026: Neue Methode fuer benutzerdefinierte Projektnamen.
        """
        if not name or not name.strip():
            return None
        sanitized = re.sub(r'[^\w\s-]', '', name.strip())
        sanitized = re.sub(r'[\s]+', '_', sanitized)
        return sanitized[:50] if sanitized else None

    # AENDERUNG 09.02.2026: project_name Parameter fuer benutzerdefinierte Projektnamen
    def run_task(self, user_goal: str, project_name: str = None):
        try:
            self._ui_log("System", "Task Start", f"Goal: {user_goal}")
            # AENDERUNG 10.02.2026: Fix 47 — User-Goal fuer Doc-Enrichment Keyword-Erkennung
            self._current_user_goal = user_goal
            project_id = None

            # AENDERUNG 09.02.2026: Benutzerdefinierter Projektname sanitisieren
            sanitized_name = self._sanitize_project_name(project_name) if project_name else None
            self._custom_project_name = sanitized_name

            try:
                library = get_library_manager()
                display_name = sanitized_name or (user_goal[:50] if len(user_goal) > 50 else user_goal)
                library.start_project(name=display_name, goal=user_goal, briefing=self.discovery_briefing)
                project_id = library.current_project.get('project_id')
                self._ui_log("Library", "ProjectStart", f"Protokollierung gestartet: {project_id}")

                # AENDERUNG 09.02.2026: ModelStatsDB Run starten (Fix 40)
                # AENDERUNG 09.02.2026: Fix 40c - _stats_run_id HIER speichern (Library-ID, BEVOR Overwrites)
                self._stats_run_id = project_id
                try:
                    stats_db = get_model_stats_db()
                    stats_db.start_run(project_id, goal=user_goal)
                except Exception as stats_err:
                    logger.warning("ModelStatsDB.start_run: %s", stats_err)

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

            # AENDERUNG 09.02.2026: Fix 40c - Konsistente Stats-ID (Library-ID statt ueberschriebener project_id)
            self._stats_project_id = getattr(self, '_stats_run_id', project_id)

            # AENDERUNG 08.02.2026: Globales agent_timeout_seconds entfernt, Pro-Agent-Timeouts aus agent_timeouts Dict
            agent_timeouts = self.config.get("agent_timeouts", {})
            # AENDERUNG 21.02.2026: 3→7 damit alle konfigurierten Modelle + dynamischer Fallback probiert werden
            MAX_RESEARCHER_RETRIES = 7
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
                # AENDERUNG 08.02.2026: research_timeout_minutes entfernt → agent_timeouts["researcher"]
                RESEARCH_TIMEOUT_SECONDS = agent_timeouts.get("researcher", 600)
                research_query = f"Suche technische Details für: {user_goal}"

                # AENDERUNG 21.02.2026: Multi-Tier Claude SDK (Opus fuer Researcher)
                sdk_research_done = False
                try:
                    from .claude_sdk_provider import run_sdk_with_retry
                    set_current_agent("Researcher", getattr(self, '_stats_run_id', project_id))
                    self._update_worker_status("researcher", "working", f"Recherche: {research_query[:50]}...", "claude-sdk/opus")
                    sdk_result = run_sdk_with_retry(
                        self, role="researcher", prompt=research_query,
                        timeout_seconds=RESEARCH_TIMEOUT_SECONDS,
                        agent_display_name="Researcher"
                    )
                    if sdk_result:
                        start_context = f"\n\nRecherche-Ergebnisse:\n{sdk_result}"
                        self._ui_log("Researcher", "Result", "Recherche abgeschlossen (Claude SDK).")
                        self._update_worker_status("researcher", "idle")
                        self._ui_log("Researcher", "ResearchOutput", json.dumps({
                            "query": research_query, "result": sdk_result[:2000],
                            "status": "completed", "model": "claude-sdk/opus",
                            "timeout_seconds": RESEARCH_TIMEOUT_SECONDS
                        }, ensure_ascii=False))
                        sdk_research_done = True
                except Exception as sdk_err:
                    logger.debug("Claude SDK Researcher nicht verfuegbar: %s", sdk_err)

                # Fallback: Bestehender OpenRouter/CrewAI Loop
                if not sdk_research_done:
                    for researcher_attempt in range(MAX_RESEARCHER_RETRIES):
                        research_model = self.model_router.get_model("researcher") if self.model_router else "unknown"
                        self._ui_log("Researcher", "ResearchOutput", json.dumps({
                            "query": research_query, "result": "", "status": "searching",
                            "model": research_model, "timeout_seconds": RESEARCH_TIMEOUT_SECONDS,
                            "attempt": researcher_attempt + 1, "max_attempts": MAX_RESEARCHER_RETRIES
                        }, ensure_ascii=False))

                        try:
                            self._ui_log("Researcher", "Status", f"Sucht Kontext... (max. {RESEARCH_TIMEOUT_SECONDS}s, Versuch {researcher_attempt + 1}/{MAX_RESEARCHER_RETRIES})")
                            set_current_agent("Researcher", getattr(self, '_stats_run_id', project_id))
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
            # AENDERUNG 21.02.2026: 3→7 damit alle konfigurierten Modelle + dynamischer Fallback probiert werden
            MAX_META_RETRIES = 7
            plan_data = None
            for meta_attempt in range(MAX_META_RETRIES):
                current_meta_model = self.model_router.get_model("meta_orchestrator") if self.model_router else "unknown"
                try:
                    self._ui_log("Orchestrator", "Status", f"Analysiere Intent (Versuch {meta_attempt + 1}/{MAX_META_RETRIES})...")
                    set_current_agent("Meta-Orchestrator", getattr(self, '_stats_run_id', project_id))
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

            # PROJEKTSTRUKTUR
            if self.is_first_run:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                # AENDERUNG 09.02.2026: Benutzerdefinierter Ordnername wenn Projektname gesetzt
                if sanitized_name:
                    folder_name = f"{sanitized_name}_{timestamp}"
                else:
                    folder_name = f"project_{timestamp}"
                self.project_path = os.path.join(self.base_dir, "projects", folder_name)
                os.makedirs(self.project_path, exist_ok=True)
                STANDARD_PROJECT_DIRS = ["tests", "docs", "src", "assets"]
                for dir_name in STANDARD_PROJECT_DIRS:
                    os.makedirs(os.path.join(self.project_path, dir_name), exist_ok=True)
                self._ui_log("System", "ProjectStructure", f"Standard-Ordner erstellt: {', '.join(STANDARD_PROJECT_DIRS)}")
                project_id = folder_name
                set_current_agent("System", getattr(self, '_stats_run_id', project_id))

                # 🛠️ TECHSTACK
                base_project_rules = self.config.get("templates", {}).get("webapp", {})
                if "techstack_architect" in plan_data["plan"]:
                    self._run_techstack_phase(user_goal, base_project_rules, getattr(self, '_stats_run_id', project_id), agent_timeouts.get("techstack_architect", 750))

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

                # AENDERUNG 10.02.2026: Fix 50 - Docker Project Container erstellen
                # Persistenter Container fuer Server + Dependencies im gesamten DevLoop
                self._docker_container = None
                pc_config = self.config.get("docker", {}).get("project_container", {})
                if pc_config.get("enabled", False):
                    try:
                        from .docker_project_container import ProjectContainerManager
                        self._docker_container = ProjectContainerManager(
                            self.project_path, self.tech_blueprint, self.config
                        )
                        if self._docker_container.is_docker_available():
                            if self._docker_container.create():
                                self._ui_log("Docker", "Container",
                                    f"Persistenter Container erstellt: {self._docker_container.container_name}")
                            else:
                                self._ui_log("Docker", "Warning",
                                    "Container-Erstellung fehlgeschlagen - Host-Fallback")
                                self._docker_container = None
                        else:
                            self._ui_log("Docker", "Warning",
                                "Docker nicht verfuegbar - Host-Fallback aktiv")
                            self._docker_container = None
                    except Exception as dc_err:
                        self._ui_log("Docker", "Warning",
                            f"Docker-Container-Setup fehlgeschlagen: {dc_err}")
                        self._docker_container = None

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
                    self._run_db_designer_phase(user_goal, self.project_rules, getattr(self, '_stats_run_id', project_id), agent_timeouts.get("database_designer", 750))
                if "designer" in plan_data["plan"]:
                    # AENDERUNG 09.02.2026: Projektnamen in Designer-Kontext einbauen
                    designer_goal = user_goal
                    if self._custom_project_name:
                        designer_goal = f"Projektname: {self._custom_project_name}\n\n{user_goal}"
                    self._run_designer_phase(designer_goal, self.project_rules, getattr(self, '_stats_run_id', project_id), agent_timeouts.get("designer", 300))
                self._ui_log("Security", "Status", "Security-Scan wird nach Code-Generierung durchgeführt...")

            # 🔄 DEV LOOP
            dev_loop = DevLoop(self, set_current_agent, run_with_timeout)
            success, feedback = dev_loop.run(
                user_goal=user_goal, project_rules=self.project_rules,
                agent_coder=agent_coder, agent_reviewer=agent_reviewer,
                agent_tester=agent_tester, agent_security=agent_security, project_id=getattr(self, '_stats_run_id', project_id)
            )

            # ÄNDERUNG 03.02.2026: Entfernt - wird jetzt in dev_loop.py nach erster Iteration gesetzt (Fix 6)
            # self.is_first_run = False
            if success:
                # AENDERUNG 08.02.2026: Fix 24 - Waisen-Check nach erfolgreichem DevLoop
                if hasattr(self, 'quality_gate') and self.quality_gate:
                    try:
                        from .traceability_manager import TraceabilityManager
                        trace_path = self.project_path / "traceability_matrix.json"
                        if trace_path.exists():
                            tm = TraceabilityManager(str(self.project_path))
                            tm.load()
                            matrix = tm.get_matrix()
                            run_waisen_check_phase(
                                anforderungen=list(matrix.get("anforderungen", {}).values()),
                                features=list(matrix.get("features", {}).values()),
                                tasks=list(matrix.get("tasks", {}).values()),
                                file_generations=[
                                    {"task_id": t_id}
                                    for t_id, t in matrix.get("tasks", {}).items()
                                    if t.get("dateien")
                                ],
                                quality_gate=self.quality_gate,
                                ui_log_callback=self._ui_log
                            )
                    except Exception as wc_err:
                        logger.warning(f"Waisen-Check nach DevLoop: {wc_err}")

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
        finally:
            # AENDERUNG 10.02.2026: Fix 50 - Docker-Container aufräumen
            if getattr(self, '_docker_container', None):
                try:
                    self._docker_container.cleanup()
                    self._ui_log("Docker", "Cleanup",
                        f"Container {self._docker_container.container_name} entfernt")
                except Exception as dc_cleanup_err:
                    logger.warning("Docker-Container-Cleanup: %s", dc_cleanup_err)
                self._docker_container = None

    def _run_techstack_phase(self, user_goal: str, base_project_rules: dict, project_id: str, agent_timeout: int):
        """TechStack-Analyse Phase (Wrapper für ausgelagerte Funktion)."""
        # AENDERUNG 21.02.2026: Fix 59g — manager durchreichen fuer Claude SDK Integration
        self.tech_blueprint, self.quality_gate = run_techstack_phase(
            user_goal=user_goal, base_project_rules=base_project_rules, project_id=project_id,
            agent_timeout=agent_timeout, config=self.config, model_router=self.model_router,
            project_path=self.project_path, discovery_briefing=self.discovery_briefing,
            ui_log_callback=self._ui_log, update_worker_status_callback=self._update_worker_status,
            manager=self
        )

    def _run_db_designer_phase(self, user_goal: str, project_rules: dict, project_id: str, agent_timeout: int):
        """DB-Designer Phase (Wrapper für ausgelagerte Funktion)."""
        # AENDERUNG 21.02.2026: Fix 59g — manager durchreichen fuer Claude SDK Integration
        self.database_schema = run_db_designer_phase(
            user_goal=user_goal, project_rules=project_rules, project_id=project_id,
            agent_timeout=agent_timeout, config=self.config, model_router=self.model_router,
            tech_blueprint=self.tech_blueprint, quality_gate=getattr(self, 'quality_gate', None),
            doc_service=getattr(self, 'doc_service', None),
            ui_log_callback=self._ui_log, update_worker_status_callback=self._update_worker_status,
            manager=self
        )

    def _run_designer_phase(self, user_goal: str, project_rules: dict, project_id: str, agent_timeout: int):
        """Designer Phase (Wrapper für ausgelagerte Funktion)."""
        # AENDERUNG 21.02.2026: Fix 59g — manager durchreichen fuer Claude SDK Integration
        self.design_concept = run_designer_phase(
            user_goal=user_goal, project_rules=project_rules, project_id=project_id,
            project_path=self.project_path, agent_timeout=agent_timeout, config=self.config,
            model_router=self.model_router, tech_blueprint=self.tech_blueprint,
            quality_gate=getattr(self, 'quality_gate', None),
            doc_service=getattr(self, 'doc_service', None),
            ui_log_callback=self._ui_log, update_worker_status_callback=self._update_worker_status,
            manager=self
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
            dep_config = self.config.get("dependency_agent", {})
            dep_agent = get_dependency_agent(dep_config)
            dep_agent.on_log = self._ui_log
            self._ui_log("DependencyAgent", "Status", "Pruefe und installiere Dependencies...")
            # AENDERUNG 09.02.2026: max_duration aus config.yaml lesen (Default: 300s = 5 Min)
            dep_max_duration = dep_config.get("max_duration", 300)
            dep_result = dep_agent.prepare_for_task(self.tech_blueprint, self.project_path, max_duration=dep_max_duration)
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
        # AENDERUNG 09.02.2026: ModelStatsDB Run abschliessen (Fix 40)
        try:
            stats_db = get_model_stats_db()
            iterations = getattr(self, '_current_iteration', 0)
            stats_db.finish_run(
                run_id=project_id or getattr(self, '_stats_project_id', 'unknown'),
                iterations=iterations,
                status="success"
            )
        except Exception as stats_err:
            logger.warning("ModelStatsDB.finish_run (success): %s", stats_err)

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
        # AENDERUNG 09.02.2026: ModelStatsDB Run als failed markieren (Fix 40)
        try:
            stats_db = get_model_stats_db()
            stats_project_id = getattr(self, '_stats_project_id', None)
            if stats_project_id:
                iterations = getattr(self, '_current_iteration', 0)
                stats_db.finish_run(run_id=stats_project_id, iterations=iterations, status="failed")
        except Exception as stats_err:
            logger.warning("ModelStatsDB.finish_run (failed): %s", stats_err)

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
        # AENDERUNG 09.02.2026: Fix 40c - iterations Parameter hinzugefuegt (war immer 0)
        try:
            stats_db = get_model_stats_db()
            stats_project_id = getattr(self, '_stats_project_id', None)
            if stats_project_id:
                iterations = getattr(self, '_current_iteration', 0)
                stats_db.finish_run(run_id=stats_project_id, iterations=iterations, status="error")
        except Exception as stats_err:
            logger.warning("ModelStatsDB.finish_run (error): %s", stats_err)

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
