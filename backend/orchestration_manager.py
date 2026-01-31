# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 31.01.2026
Version: 2.4
Beschreibung: Orchestration Manager - Backend-Koordination mit LiteLLM Callbacks und Agent-Steuerung.
              ÄNDERUNG 31.01.2026: HELP_NEEDED Handler mit automatischem Test-Generator und Priorisierung.
              ÄNDERUNG 30.01.2026: AgentMessage + HELP_NEEDED Events gemäß Kommunikationsprotokoll.
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
# ÄNDERUNG 31.01.2026: Hardcodierten Windows-Pfad entfernt für Plattform-Unabhängigkeit
def _load_env_robust():
    """Lädt .env aus mehreren möglichen Pfaden."""
    possible_paths = [
        # 1. Relativ zum aktuellen Arbeitsverzeichnis
        os.path.join(os.getcwd(), ".env"),
        # 2. Relativ zu __file__ (funktioniert wenn nicht im Worktree)
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
    is_rate_limit_error,
    is_empty_response_error  # ÄNDERUNG 30.01.2026: Erkennt leere LLM-Antworten (deepseek-r1 Bug)
)
from .dev_loop import DevLoop
from .library_manager import get_library_manager
from .session_manager import get_session_manager
# ÄNDERUNG 30.01.2026: Quality Gate und Documentation Service für Qualitätskontrolle
from .quality_gate import QualityGate
# ÄNDERUNG 30.01.2026: AgentMessage für formale Kommunikation gemäß Protokoll
from .agent_message import AgentMessage, create_help_needed
from .documentation_service import DocumentationService

from crewai import Task

# ÄNDERUNG 24.01.2026: Import aus zentraler file_utils (REGEL 13 - Single Source of Truth)
from file_utils import find_html_file, find_python_entry

# =====================================================================
# LiteLLM Callback für Budget-Tracking
# ÄNDERUNG 30.01.2026: Thread-Safe globals statt ContextVar für korrektes Tracking
# =====================================================================
import threading

# Thread-Safe globale Variablen für Budget-Tracking
_budget_tracking_lock = threading.Lock()
_current_agent_name = "Unknown"
_current_project_id = None

try:
    import litellm

    def _budget_tracking_callback(kwargs, completion_response, start_time, end_time):
        """
        LiteLLM success callback - erfasst Token-Nutzung nach jedem API-Call.
        ÄNDERUNG 30.01.2026: Thread-Safe Zugriff auf globale Variablen.
        """
        global _current_agent_name, _current_project_id
        try:
            tracker = get_budget_tracker()

            # Thread-Safe Lesen der aktuellen Werte
            with _budget_tracking_lock:
                current_agent_name = _current_agent_name
                current_project_id = _current_project_id

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
                    "_budget_tracking_callback: %s - %s+%s Tokens (Modell: %s, Projekt: %s)",
                    current_agent_name,
                    prompt_tokens,
                    completion_tokens,
                    model,
                    current_project_id
                )
        except Exception as e:
            logger.exception("_budget_tracking_callback: Fehler beim Budget-Tracking: %s", e)

    # Registriere den Callback
    litellm.success_callback = [_budget_tracking_callback]
    logger.info("litellm.success_callback: Budget-Tracking Callback erfolgreich registriert (Thread-Safe)")

except ImportError:
    logger.warning("litellm.success_callback: LiteLLM nicht verfuegbar - Budget-Tracking deaktiviert")


def set_current_agent(agent_name: str, project_id: str = None):
    """
    Setzt den aktuellen Agenten für Budget-Tracking (Thread-Safe).
    ÄNDERUNG 30.01.2026: Nutzt globale Variablen mit Lock statt ContextVar.
    """
    global _current_agent_name, _current_project_id
    with _budget_tracking_lock:
        _current_agent_name = agent_name
        if project_id is not None:
            _current_project_id = project_id


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


# =====================================================================
# ÄNDERUNG 30.01.2026: Hilfsfunktionen für intelligenten TechStack-Fallback
# Respektiert Benutzer-Vorgaben und fällt nicht blind auf static_html zurück
# =====================================================================

def _repair_json(text: str) -> str:
    """
    Versucht ungültiges JSON zu reparieren.
    ÄNDERUNG 30.01.2026: Erweitert um mehr Fälle (Comments, Trailing Commas, etc.)

    Behandelt häufige LLM-Fehler:
    - Single quotes statt double quotes
    - Trailing commas
    - JavaScript-style comments
    """
    # 1. JavaScript-Comments entfernen (// und /* */)
    text = re.sub(r'//.*?$', '', text, flags=re.MULTILINE)
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.DOTALL)

    # 2. Single quotes durch double quotes ersetzen
    # Pattern für 'key': oder : 'value'
    text = re.sub(r"'([^']*)'(\s*:)", r'"\1"\2', text)
    text = re.sub(r":\s*'([^']*)'(\s*[,}\]])", r': "\1"\2', text)

    # 3. Trailing commas entfernen (vor } oder ])
    text = re.sub(r',(\s*[}\]])', r'\1', text)

    return text


def _extract_user_requirements(user_goal: str) -> dict:
    """
    Extrahiert ALLE erkennbaren Anforderungen aus dem Benutzer-Goal.
    ÄNDERUNG 30.01.2026: Erweitert um mehr Keywords (Datenbanken, Sprachen, Frameworks).

    Benutzer-Vorgaben dürfen NICHT ignoriert werden!
    """
    goal_lower = user_goal.lower()
    requirements = {}

    # Datenbank-Vorgaben (erweitert)
    db_keywords = {
        "sqlite": "sqlite", "postgres": "postgres", "postgresql": "postgres",
        "mysql": "mysql", "mariadb": "mysql", "mongodb": "mongodb", "mongo": "mongodb",
        "redis": "redis", "elasticsearch": "elasticsearch", "neo4j": "neo4j",
        "datenbank": "generic_db", "database": "generic_db"
    }
    for keyword, db_type in db_keywords.items():
        if keyword in goal_lower:
            requirements["database"] = db_type
            break

    # Sprach-Vorgaben (erweitert)
    lang_keywords = {
        "python": "python", "javascript": "javascript", "typescript": "javascript",
        "node": "javascript", "java": "java", "kotlin": "kotlin",
        "go": "go", "golang": "go", "rust": "rust", "c++": "cpp", "c#": "csharp"
    }
    for keyword, lang in lang_keywords.items():
        if keyword in goal_lower:
            requirements["language"] = lang
            break

    # Framework-Vorgaben (NEU)
    framework_keywords = {
        "flask": "flask", "fastapi": "fastapi", "django": "django",
        "express": "express", "react": "react", "vue": "vue", "angular": "angular",
        "tkinter": "tkinter", "pyqt": "pyqt", "electron": "electron"
    }
    for keyword, fw in framework_keywords.items():
        if keyword in goal_lower:
            requirements["framework"] = fw
            break

    # UI-Typ (NEU)
    if any(kw in goal_lower for kw in ["desktop", "fenster", "gui"]):
        requirements["ui_type"] = "desktop"
    elif any(kw in goal_lower for kw in ["webapp", "website", "webseite", "browser"]):
        requirements["ui_type"] = "webapp"
    elif any(kw in goal_lower for kw in ["api", "rest", "endpoint", "backend"]):
        requirements["ui_type"] = "api"
    elif any(kw in goal_lower for kw in ["cli", "kommandozeile", "terminal", "console"]):
        requirements["ui_type"] = "cli"

    return requirements


def _infer_blueprint_from_requirements(user_goal: str) -> dict:
    """
    Erstellt einen Fallback-Blueprint basierend auf erkannten Benutzer-Anforderungen.
    ÄNDERUNG 30.01.2026: Framework-basierte Erkennung hat Vorrang.

    Priorität: Framework > UI-Typ > Datenbank > Sprache > Default
    """
    reqs = _extract_user_requirements(user_goal)
    blueprint = {}

    # PRIORITÄT 1: Framework hat Vorrang (wenn explizit genannt)
    if reqs.get("framework"):
        fw = reqs["framework"]
        if fw == "flask":
            blueprint = {"project_type": "flask_app", "app_type": "webapp", "test_strategy": "playwright",
                         "language": "python", "requires_server": True, "server_port": 5000}
        elif fw == "fastapi":
            blueprint = {"project_type": "fastapi_app", "app_type": "api", "test_strategy": "pytest_only",
                         "language": "python", "requires_server": True, "server_port": 8000}
        elif fw == "django":
            blueprint = {"project_type": "django_app", "app_type": "webapp", "test_strategy": "playwright",
                         "language": "python", "requires_server": True, "server_port": 8000}
        elif fw == "tkinter":
            blueprint = {"project_type": "tkinter_desktop", "app_type": "desktop", "test_strategy": "pyautogui",
                         "language": "python", "requires_server": False}
        elif fw == "pyqt":
            blueprint = {"project_type": "pyqt_desktop", "app_type": "desktop", "test_strategy": "pyautogui",
                         "language": "python", "requires_server": False}
        elif fw == "express":
            blueprint = {"project_type": "nodejs_express", "app_type": "webapp", "test_strategy": "playwright",
                         "language": "javascript", "requires_server": True, "server_port": 3000}
        elif fw == "electron":
            blueprint = {"project_type": "electron_desktop", "app_type": "desktop", "test_strategy": "pyautogui",
                         "language": "javascript", "requires_server": False}
        elif fw in ("react", "vue", "angular"):
            blueprint = {"project_type": f"{fw}_spa", "app_type": "webapp", "test_strategy": "playwright",
                         "language": "javascript", "requires_server": True, "server_port": 3000}

    # PRIORITÄT 2: UI-Typ als nächstes
    elif reqs.get("ui_type") == "desktop":
        blueprint = {"project_type": "tkinter_desktop", "app_type": "desktop", "test_strategy": "pyautogui",
                     "language": "python", "requires_server": False}
    elif reqs.get("ui_type") == "api":
        blueprint = {"project_type": "fastapi_app", "app_type": "api", "test_strategy": "pytest_only",
                     "language": "python", "requires_server": True, "server_port": 8000}
    elif reqs.get("ui_type") == "webapp":
        blueprint = {"project_type": "flask_app", "app_type": "webapp", "test_strategy": "playwright",
                     "language": "python", "requires_server": True, "server_port": 5000}
    elif reqs.get("ui_type") == "cli":
        blueprint = {"project_type": "python_cli", "app_type": "cli", "test_strategy": "cli_test",
                     "language": "python", "requires_server": False}

    # PRIORITÄT 3: Datenbank ohne UI → Python Script
    elif reqs.get("database"):
        blueprint = {"project_type": "python_script", "app_type": "cli", "test_strategy": "pytest_only",
                     "language": "python", "requires_server": False}

    # PRIORITÄT 4: Sprache bekannt aber nichts anderes
    elif reqs.get("language") == "javascript":
        blueprint = {"project_type": "nodejs_app", "app_type": "webapp", "test_strategy": "playwright",
                     "language": "javascript", "requires_server": True, "server_port": 3000}
    elif reqs.get("language") == "python":
        blueprint = {"project_type": "python_script", "app_type": "cli", "test_strategy": "pytest_only",
                     "language": "python", "requires_server": False}
    elif reqs.get("language") == "go":
        blueprint = {"project_type": "go_app", "app_type": "cli", "test_strategy": "pytest_only",
                     "language": "go", "requires_server": False}

    # PRIORITÄT 5: Absoluter Fallback - nur wenn wirklich NICHTS erkannt
    else:
        blueprint = {"project_type": "static_html", "app_type": "webapp", "test_strategy": "playwright",
                     "language": "html", "requires_server": False}

    # Erkannte Anforderungen ERZWINGEN (überschreibt Default-Werte)
    if reqs.get("database"):
        blueprint["database"] = reqs["database"]
    if reqs.get("language") and "language" not in blueprint:
        blueprint["language"] = reqs["language"]

    # Begründung für Transparenz
    blueprint["reasoning"] = f"FALLBACK basierend auf Benutzer-Anforderungen: {reqs}"

    return blueprint


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
            # ÄNDERUNG 30.01.2026: HELP_NEEDED als spezieller Status
            if event in ("Status", "Working", "Result", "Complete", "Error", "HELP_NEEDED"):
                agent_lower = agent.lower().replace("-", "").replace(" ", "")
                # ÄNDERUNG 28.01.2026: Session-Key ueber Mapping aufloesen
                session_key = AGENT_TO_SESSION_KEY.get(agent, agent_lower)
                is_active = event in ("Status", "Working")
                is_blocked = event == "HELP_NEEDED"
                session_mgr.set_agent_active(session_key, is_active)
                # ÄNDERUNG 30.01.2026: Blocked-Status für HELP_NEEDED
                if is_blocked:
                    session_mgr.set_agent_blocked(session_key, True, message)
        except Exception:
            pass  # Session-Updates sollten nicht den Workflow stoppen

    # ÄNDERUNG 30.01.2026: Helper für HELP_NEEDED Events gemäß Kommunikationsprotokoll
    def _log_help_needed(self, agent: str, reason: str, context: dict = None, action_required: str = "manual_review"):
        """
        Sendet ein HELP_NEEDED Event wenn ein Agent Unterstützung benötigt.

        Args:
            agent: Der blockierte Agent
            reason: Grund der Blockierung (z.B. "critical_vulnerabilities")
            context: Zusätzliche Kontext-Informationen
            action_required: Erforderliche Aktion (z.B. "security_review_required")
        """
        project_id = os.path.basename(self.project_path) if self.project_path else None
        help_msg = create_help_needed(
            agent=agent,
            reason=reason,
            context=context,
            action_required=action_required,
            project_id=project_id
        )
        # Sende über bestehenden _ui_log Kanal
        self._ui_log(*help_msg.to_legacy())

    # =========================================================================
    # HELP_NEEDED HANDLER - ÄNDERUNG 31.01.2026
    # =========================================================================

    def _handle_help_needed_events(self, iteration: int) -> Dict[str, Any]:
        """
        Zentraler HELP_NEEDED Handler - verarbeitet blockierte Agents.

        Stufe 1: Automatische Hilfs-Agenten starten
        Stufe 2: Priorisierung und Konsens-Mechanismus

        Args:
            iteration: Aktuelle DevLoop-Iteration

        Returns:
            Dict mit Status und durchgefuehrten Aktionen
        """
        session_mgr = get_session_manager()
        blocked_agents = session_mgr.get_blocked_agents()

        if not blocked_agents:
            return {"status": "no_blocks", "actions": []}

        self._ui_log("HelpHandler", "Status",
                     f"Verarbeite {len(blocked_agents)} blockierte Agents...")

        # STUFE 2: Priorisierung - Critical zuerst
        priority_order = {"critical": 0, "high": 1, "normal": 2, "low": 3}
        sorted_agents = sorted(
            blocked_agents.items(),
            key=lambda x: priority_order.get(x[1].get("priority", "normal"), 2)
        )

        actions_taken = []

        for agent_name, block_info in sorted_agents:
            reason_str = block_info.get("reason", "{}")

            try:
                reason_data = json.loads(reason_str)
                action_required = reason_data.get("action_required", "")
            except (json.JSONDecodeError, TypeError):
                action_required = ""

            # STUFE 1: Automatische Aktionen basierend auf action_required
            if action_required == "create_test_files":
                # Test-Generator automatisch starten
                self._ui_log("HelpHandler", "Action",
                            "Starte Test-Generator fuer fehlende Unit-Tests...")
                success = self._run_automatic_test_generator(iteration)
                actions_taken.append({
                    "agent": agent_name,
                    "action": "test_generator",
                    "success": success
                })
                if success:
                    session_mgr.clear_agent_blocked(agent_name)
                    self._ui_log("HelpHandler", "Success",
                                f"Test-Generator hat Tests erstellt - {agent_name} Blockade aufgehoben")

            elif action_required == "security_review_required":
                # Bei kritischen Security Issues: Warnung + Eskalation an Coder
                self._ui_log("HelpHandler", "Warning",
                            "Kritische Security-Issues - Coder muss in naechster Iteration fixen")
                actions_taken.append({
                    "agent": agent_name,
                    "action": "escalate_to_coder",
                    "success": True  # Eskalation ist erfolgreich
                })
                # NICHT clear_agent_blocked - bleibt blockiert bis gefixt

            else:
                # Unbekannte Aktion - nur loggen
                self._ui_log("HelpHandler", "Info",
                            f"Unbekannte Aktion fuer {agent_name}: {action_required}")
                actions_taken.append({
                    "agent": agent_name,
                    "action": "unknown",
                    "success": False
                })

        return {
            "status": "processed",
            "blocked_count": len(blocked_agents),
            "actions": actions_taken
        }

    def _run_automatic_test_generator(self, iteration: int) -> bool:
        """
        Startet den Test-Generator Agent automatisch.

        Args:
            iteration: Aktuelle Iteration (fuer Logging)

        Returns:
            True wenn Tests erfolgreich erstellt wurden
        """
        try:
            from agents.test_generator_agent import (
                create_test_generator,
                create_test_generation_task,
                extract_test_files
            )
            from backend.test_templates import create_fallback_tests

            # Sammle vorhandene Code-Dateien
            code_files = {}
            if self.project_path and os.path.exists(self.project_path):
                for filename in os.listdir(self.project_path):
                    if filename.endswith(".py") and not filename.startswith("test_"):
                        filepath = os.path.join(self.project_path, filename)
                        try:
                            with open(filepath, "r", encoding="utf-8") as f:
                                code_files[filename] = f.read()
                        except Exception as e:
                            self._ui_log("HelpHandler", "Warning", f"Datei nicht lesbar: {filename}")

            if not code_files:
                self._ui_log("HelpHandler", "Warning", "Keine Python-Dateien zum Testen gefunden")
                # Fallback zu Templates trotzdem versuchen
                project_type = self.tech_blueprint.get("project_type", "python_script") if self.tech_blueprint else "python_script"
                created = create_fallback_tests(self.project_path, project_type)
                return len(created) > 0

            # Erstelle Test-Generator Agent
            test_agent = create_test_generator(
                self.config,
                self.project_rules,
                router=self.model_router
            )

            task = create_test_generation_task(
                test_agent,
                code_files,
                self.tech_blueprint.get("project_type", "python_script") if self.tech_blueprint else "python_script",
                self.tech_blueprint or {}
            )

            # Fuehre Task aus
            from crewai import Crew
            crew = Crew(agents=[test_agent], tasks=[task], verbose=True)
            result = crew.kickoff()

            # Parse und speichere Tests
            result_str = str(result) if result else ""
            if result_str and "### FILENAME:" in result_str:
                test_files = extract_test_files(result_str)

                for filepath, content in test_files.items():
                    full_path = os.path.join(self.project_path, filepath)
                    os.makedirs(os.path.dirname(full_path), exist_ok=True)
                    with open(full_path, "w", encoding="utf-8") as f:
                        f.write(content)

                self._ui_log("HelpHandler", "Result",
                            f"Test-Generator hat {len(test_files)} Dateien erstellt")
                return len(test_files) > 0

            # Fallback: Template-Tests
            self._ui_log("HelpHandler", "Info", "Verwende Template-Tests als Fallback")
            project_type = self.tech_blueprint.get("project_type", "python_script") if self.tech_blueprint else "python_script"
            created = create_fallback_tests(self.project_path, project_type)
            return len(created) > 0

        except Exception as e:
            self._ui_log("HelpHandler", "Error", f"Test-Generator fehlgeschlagen: {e}")
            # Letzter Fallback: Templates
            try:
                from backend.test_templates import create_fallback_tests
                project_type = self.tech_blueprint.get("project_type", "python_script") if self.tech_blueprint else "python_script"
                created = create_fallback_tests(self.project_path, project_type)
                if created:
                    self._ui_log("HelpHandler", "Info", f"Template-Fallback erstellt: {created}")
                    return True
            except Exception:
                pass
            return False

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

    # ÄNDERUNG 30.01.2026: Einfache README-Generierung ohne LLM (schneller, kostengünstiger)
    def _generate_simple_readme(self, context: str) -> str:
        """
        Generiert eine einfache README.md basierend auf dem Kontext.
        Verwendet kein LLM, sondern Template-basierte Generierung.

        Args:
            context: Der vom DocumentationService generierte Kontext

        Returns:
            README-Inhalt als String
        """
        ts = self.tech_blueprint
        project_name = os.path.basename(self.project_path) if self.project_path else "Projekt"

        # Basis-Template
        readme_parts = [
            f"# {project_name}",
            "",
            f"**Generiert von AgentSmith Multi-Agent System**",
            f"*Erstellt am: {datetime.now().strftime('%d.%m.%Y %H:%M')}*",
            "",
            "## Beschreibung",
            "",
        ]

        # Briefing-Ziel wenn vorhanden
        if self.discovery_briefing and self.discovery_briefing.get("projectGoal"):
            readme_parts.append(self.discovery_briefing["projectGoal"])
        elif hasattr(self, 'doc_service') and self.doc_service.data.get("goal"):
            readme_parts.append(self.doc_service.data["goal"])
        else:
            readme_parts.append("*Keine Beschreibung verfügbar.*")

        readme_parts.extend(["", "## Technische Details", ""])

        # TechStack-Details
        readme_parts.append(f"- **Projekttyp:** {ts.get('project_type', 'unbekannt')}")
        readme_parts.append(f"- **Sprache:** {ts.get('language', 'unbekannt')}")
        if ts.get("database"):
            readme_parts.append(f"- **Datenbank:** {ts['database']}")
        if ts.get("requires_server"):
            readme_parts.append(f"- **Server-Port:** {ts.get('server_port', 'nicht definiert')}")

        # Installation
        if ts.get("install_command"):
            readme_parts.extend([
                "",
                "## Installation",
                "",
                "```bash",
                ts["install_command"],
                "```",
            ])

        # Start
        if ts.get("run_command"):
            readme_parts.extend([
                "",
                "## Starten",
                "",
                "```bash",
                ts["run_command"],
                "```",
            ])

        # Windows-Batch falls vorhanden
        if self.project_path and os.path.exists(os.path.join(self.project_path, "run.bat")):
            readme_parts.extend([
                "",
                "Oder unter Windows:",
                "",
                "```batch",
                "run.bat",
                "```",
            ])

        # Lizenz-Hinweis
        readme_parts.extend([
            "",
            "## Lizenz",
            "",
            "Erstellt mit AgentSmith - Multi-Agent Development System",
            "",
            "---",
            f"*Auto-generiert am {datetime.now().strftime('%d.%m.%Y')}*"
        ])

        return "\n".join(readme_parts)

    # ÄNDERUNG 31.01.2026: Echter Documentation Manager Agent für bessere README-Qualität
    def _generate_readme_with_agent(self, context: str) -> str:
        """
        Generiert README.md mit dem echten Documentation Manager Agent.
        Nutzt LLM für intelligente, kontextbezogene Dokumentation.

        Args:
            context: Der vom DocumentationService generierte Kontext

        Returns:
            README-Inhalt als String
        """
        from agents.documentation_manager_agent import (
            create_documentation_manager,
            get_readme_task_description
        )
        from backend.agent_factory import init_agents

        try:
            # Agent erstellen
            agents = init_agents(
                self.config,
                self.project_rules,
                router=self.model_router,
                include=["documentation_manager"]
            )
            doc_agent = agents.get("documentation_manager")

            if not doc_agent:
                self._ui_log("DocumentationManager", "Warning",
                             "Agent konnte nicht erstellt werden, verwende Template")
                return self._generate_simple_readme(context)

            # Task erstellen und ausführen
            task_description = get_readme_task_description(context)
            doc_task = Task(
                description=task_description,
                expected_output="README.md Inhalt in Markdown",
                agent=doc_agent
            )

            self._ui_log("DocumentationManager", "Status", "LLM generiert README.md...")
            self._update_worker_status("documentation_manager", "working", "README-Generierung")

            readme_content = str(doc_task.execute_sync())

            self._update_worker_status("documentation_manager", "idle")
            self._ui_log("DocumentationManager", "Status", "README.md erfolgreich generiert")

            return readme_content

        except Exception as agent_err:
            self._ui_log("DocumentationManager", "Warning",
                         f"Agent-Generierung fehlgeschlagen: {agent_err}, verwende Template")
            return self._generate_simple_readme(context)

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

            # ÄNDERUNG 30.01.2026: Globaler Agent-Timeout aus Config
            AGENT_TIMEOUT = self.config.get("agent_timeout_seconds", 300)

            # 🔎 RESEARCH PHASE (Nur beim ersten Mal) - Mit Timeout und Retry-Schleife
            # ÄNDERUNG 30.01.2026: Retry-Schleife für Fallback bei 404/Rate-Limit Fehlern
            start_context = ""
            research_query = ""
            research_result = ""
            MAX_RESEARCHER_RETRIES = 3
            if self.is_first_run:
                # Research-Timeout aus Config lesen (in Minuten), in Sekunden umrechnen
                timeout_minutes = self.config.get("research_timeout_minutes", 5)
                RESEARCH_TIMEOUT_SECONDS = timeout_minutes * 60
                research_query = f"Suche technische Details für: {user_goal}"

                for researcher_attempt in range(MAX_RESEARCHER_RETRIES):
                    # Hole Modell bei jedem Versuch neu (ermöglicht Fallback)
                    research_model = self.model_router.get_model("researcher") if self.model_router else "unknown"

                    # ResearchOutput Event: Status "searching"
                    self._ui_log("Researcher", "ResearchOutput", json.dumps({
                        "query": research_query,
                        "result": "",
                        "status": "searching",
                        "model": research_model,
                        "timeout_seconds": RESEARCH_TIMEOUT_SECONDS,
                        "attempt": researcher_attempt + 1,
                        "max_attempts": MAX_RESEARCHER_RETRIES
                    }, ensure_ascii=False))

                    try:
                        self._ui_log("Researcher", "Status", f"Sucht Kontext... (max. {RESEARCH_TIMEOUT_SECONDS}s, Versuch {researcher_attempt + 1}/{MAX_RESEARCHER_RETRIES})")
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
                        break  # Erfolg - Schleife verlassen

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
                        break  # Timeout - kein Retry sinnvoll

                    except Exception as e:
                        # ÄNDERUNG 30.01.2026: Retry bei 404/Model-Unavailable/Empty-Response mit Fallback
                        if is_model_unavailable_error(e) or is_rate_limit_error(e) or is_empty_response_error(e):
                            self._ui_log("Researcher", "Warning", f"Modell {research_model} nicht verfügbar (Versuch {researcher_attempt + 1}/{MAX_RESEARCHER_RETRIES}): {str(e)[:80]}")
                            self.model_router.mark_rate_limited_sync(research_model)
                            self._update_worker_status("researcher", "idle")

                            if researcher_attempt < MAX_RESEARCHER_RETRIES - 1:
                                self._ui_log("Researcher", "Info", "Wechsle zu Fallback-Modell...")
                                continue  # Nächster Versuch mit Fallback-Modell
                            else:
                                self._ui_log("Researcher", "Error", f"Recherche nach {MAX_RESEARCHER_RETRIES} Versuchen fehlgeschlagen")
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
                            "error": str(e),
                            "attempt": researcher_attempt + 1
                        }, ensure_ascii=False))
                        break  # Anderer Fehler - kein Retry

            # 🧠 META-ORCHESTRATOR mit Retry
            # ÄNDERUNG 30.01.2026: Retry-Logik bei 404/Rate-Limit Fehlern
            MAX_META_RETRIES = 3
            plan_data = None
            for meta_attempt in range(MAX_META_RETRIES):
                current_meta_model = self.model_router.get_model("meta_orchestrator") if self.model_router else "unknown"
                try:
                    self._ui_log("Orchestrator", "Status", f"Analysiere Intent (Versuch {meta_attempt + 1}/{MAX_META_RETRIES})...")
                    set_current_agent("Meta-Orchestrator", project_id)  # Budget-Tracking
                    meta_orchestrator = MetaOrchestratorV2()
                    plan_data = meta_orchestrator.orchestrate(user_goal + start_context)
                    self._ui_log("Orchestrator", "Analysis", json.dumps(plan_data["analysis"], ensure_ascii=False))
                    break  # Erfolg
                except Exception as meta_err:
                    # ÄNDERUNG 30.01.2026: Auch leere Antworten als Retry-Fall behandeln
                    if is_model_unavailable_error(meta_err) or is_rate_limit_error(meta_err) or is_empty_response_error(meta_err):
                        self._ui_log("Orchestrator", "Warning",
                            f"Meta-Modell {current_meta_model} nicht verfügbar (Versuch {meta_attempt + 1}/{MAX_META_RETRIES})")
                        self.model_router.mark_rate_limited_sync(current_meta_model)
                        if meta_attempt < MAX_META_RETRIES - 1:
                            continue  # Nächster Versuch mit Fallback
                    self._ui_log("Orchestrator", "Error", f"Meta-Orchestrator Fehler: {str(meta_err)[:200]}")
                    raise meta_err

            if not plan_data:
                # ÄNDERUNG 30.01.2026: HELP_NEEDED Event bevor RuntimeError
                self._log_help_needed(
                    agent="Orchestrator",
                    reason="no_orchestration_plan",
                    context={
                        "user_goal": user_goal[:200],
                        "attempts": MAX_META_RETRIES,
                        "research_available": bool(start_context)
                    },
                    action_required="clarify_requirements"
                )
                raise RuntimeError("Meta-Orchestrator konnte keinen Plan erstellen nach allen Versuchen")

            # 📦 PROJEKTSTRUKTUR (Nur beim ersten Mal)
            if self.is_first_run:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                project_name = f"project_{timestamp}"
                # Absoluten Pfad verwenden für konsistentes Verhalten
                self.project_path = os.path.join(self.base_dir, "projects", project_name)
                os.makedirs(self.project_path, exist_ok=True)

                # ÄNDERUNG 31.01.2026: Standard-Projektstruktur automatisch erstellen
                # Diese Ordner sind den Agenten bekannt und sollten entsprechend genutzt werden
                STANDARD_PROJECT_DIRS = ["tests", "docs", "src", "assets"]
                for dir_name in STANDARD_PROJECT_DIRS:
                    os.makedirs(os.path.join(self.project_path, dir_name), exist_ok=True)
                self._ui_log("System", "ProjectStructure", f"Standard-Ordner erstellt: {', '.join(STANDARD_PROJECT_DIRS)}")

                # Aktualisiere project_id nach Projekt-Erstellung
                project_id = project_name
                # ÄNDERUNG 30.01.2026: Project-ID sofort für Budget-Tracking setzen
                set_current_agent("System", project_id)

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
                                # ÄNDERUNG 30.01.2026: Timeout aus globaler Config
                                timeout_seconds=AGENT_TIMEOUT
                            )
                            break  # Erfolg - Schleife verlassen
                        except Exception as ts_error:
                            # ÄNDERUNG 30.01.2026: Auch leere Antworten als Retry-Fall (deepseek-r1 Bug)
                            if is_model_unavailable_error(ts_error) or is_rate_limit_error(ts_error) or is_empty_response_error(ts_error):
                                self._ui_log("TechStack", "Warning",
                                    f"Modell {current_techstack_model} nicht verfügbar/leer (Versuch {techstack_attempt + 1}/{MAX_TECHSTACK_RETRIES}), wechsle zu Fallback...")
                                self.model_router.mark_rate_limited_sync(current_techstack_model)
                                if techstack_attempt == MAX_TECHSTACK_RETRIES - 1:
                                    # Alle Versuche fehlgeschlagen - intelligenter Fallback basierend auf user_goal
                                    fallback_blueprint = _infer_blueprint_from_requirements(user_goal)
                                    self._ui_log("TechStack", "Error",
                                        f"Alle TechStack-Modelle nicht verfügbar, verwende requirement-basierten Fallback: {fallback_blueprint['project_type']}")
                                    techstack_result = json.dumps(fallback_blueprint)
                                continue
                            else:
                                # Anderer Fehler - weiterleiten
                                raise ts_error
                    # ÄNDERUNG 30.01.2026: Robusteres JSON-Parsing mit intelligenter Fallback-Logik
                    # Respektiert Benutzer-Vorgaben und fällt nicht blind auf static_html zurück
                    try:
                        json_text = None

                        # Schritt 1: JSON aus Markdown Code-Block extrahieren
                        code_block_match = re.search(r'```(?:json)?\s*(\{[\s\S]*?\})\s*```', techstack_result)
                        if code_block_match:
                            json_text = code_block_match.group(1)

                        # Schritt 2: Falls kein Code-Block, einfaches JSON-Regex (double quotes)
                        if not json_text:
                            json_match = re.search(r'\{[^{}]*"project_type"[^{}]*\}', techstack_result, re.DOTALL)
                            if json_match:
                                json_text = json_match.group()

                        # Schritt 3: Falls immer noch nichts, versuche single-quotes Variante
                        if not json_text:
                            single_quote_match = re.search(r"\{[^{}]*'project_type'[^{}]*\}", techstack_result, re.DOTALL)
                            if single_quote_match:
                                json_text = _repair_json(single_quote_match.group())
                                self._ui_log("TechArchitect", "Info", "JSON mit single quotes erkannt, repariere...")

                        # Schritt 4: JSON parsen
                        if json_text:
                            try:
                                self.tech_blueprint = json.loads(json_text)
                            except json.JSONDecodeError:
                                # Versuche JSON zu reparieren (single quotes etc.)
                                repaired = _repair_json(json_text)
                                self.tech_blueprint = json.loads(repaired)
                                self._ui_log("TechArchitect", "Info", "JSON erfolgreich repariert")
                        else:
                            raise ValueError("Kein JSON gefunden in TechStack-Antwort")

                    except (json.JSONDecodeError, KeyError, ValueError) as e:
                        # INTELLIGENTER FALLBACK: Analysiere user_goal statt blind static_html
                        self.tech_blueprint = _infer_blueprint_from_requirements(user_goal)
                        self._ui_log("TechArchitect", "Warning",
                            f"Blueprint-Parsing fehlgeschlagen ({e}), verwende requirement-basierten Fallback: {self.tech_blueprint['project_type']}")
                    
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

                    # ÄNDERUNG 30.01.2026: Quality Gate Validierung nach TechStack
                    # Als Instanzvariable speichern für Schema/Design/Code Validierungen
                    self.quality_gate = QualityGate(user_goal, self.discovery_briefing)
                    ts_validation = self.quality_gate.validate_techstack(self.tech_blueprint)
                    self._ui_log("QualityGate", "TechStackValidation", json.dumps({
                        "step": "TechStack",
                        "passed": ts_validation.passed,
                        "score": ts_validation.score,
                        "issues": ts_validation.issues,
                        "warnings": ts_validation.warnings,
                        "requirements": self.quality_gate.get_requirements_summary()
                    }, ensure_ascii=False))

                    if not ts_validation.passed:
                        self._ui_log("QualityGate", "Warning",
                            f"TechStack-Blueprint verletzt Benutzer-Anforderungen: {', '.join(ts_validation.issues)}")

                # ÄNDERUNG 30.01.2026: Documentation Service initialisieren
                self.doc_service = DocumentationService(self.project_path)
                self.doc_service.collect_goal(user_goal)
                self.doc_service.collect_briefing(self.discovery_briefing or {})
                self.doc_service.collect_techstack(self.tech_blueprint)

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
                                    # ÄNDERUNG 30.01.2026: Timeout aus globaler Config
                                    timeout_seconds=AGENT_TIMEOUT
                                )
                                break  # Erfolg
                        except Exception as db_error:
                            # ÄNDERUNG 30.01.2026: Auch leere Antworten als Retry-Fall
                            if is_model_unavailable_error(db_error) or is_rate_limit_error(db_error) or is_empty_response_error(db_error):
                                self._ui_log("DBDesigner", "Warning",
                                    f"Modell {current_db_model} nicht verfügbar/leer (Versuch {db_attempt + 1}/{MAX_DB_RETRIES}), wechsle...")
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

                    # ÄNDERUNG 30.01.2026: Quality Gate - Schema Validierung
                    if self.database_schema and hasattr(self, 'quality_gate'):
                        schema_validation = self.quality_gate.validate_schema(
                            self.database_schema, self.tech_blueprint
                        )
                        self._ui_log("QualityGate", "SchemaValidation", json.dumps({
                            "step": "DBSchema",
                            "passed": schema_validation.passed,
                            "score": schema_validation.score,
                            "issues": schema_validation.issues,
                            "warnings": schema_validation.warnings
                        }, ensure_ascii=False))
                        # Sammle Schema für Dokumentation
                        if hasattr(self, 'doc_service') and self.doc_service:
                            self.doc_service.collect_schema(self.database_schema)
                            self.doc_service.collect_quality_validation("DBSchema", {
                                "passed": schema_validation.passed,
                                "score": schema_validation.score,
                                "issues": schema_validation.issues,
                                "warnings": schema_validation.warnings
                            })

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
                                    # ÄNDERUNG 30.01.2026: Timeout aus globaler Config
                                    timeout_seconds=AGENT_TIMEOUT
                                )
                                break  # Erfolg
                        except Exception as des_error:
                            # ÄNDERUNG 30.01.2026: Auch leere Antworten als Retry-Fall
                            if is_model_unavailable_error(des_error) or is_rate_limit_error(des_error) or is_empty_response_error(des_error):
                                self._ui_log("Designer", "Warning",
                                    f"Modell {current_design_model} nicht verfügbar/leer (Versuch {design_attempt + 1}/{MAX_DESIGN_RETRIES}), wechsle...")
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

                        # ÄNDERUNG 30.01.2026: Quality Gate - Design Validierung
                        if hasattr(self, 'quality_gate'):
                            design_validation = self.quality_gate.validate_design(
                                self.design_concept, self.tech_blueprint
                            )
                            self._ui_log("QualityGate", "DesignValidation", json.dumps({
                                "step": "Design",
                                "passed": design_validation.passed,
                                "score": design_validation.score,
                                "issues": design_validation.issues,
                                "warnings": design_validation.warnings
                            }, ensure_ascii=False))
                            # Sammle Design für Dokumentation
                            if hasattr(self, 'doc_service') and self.doc_service:
                                self.doc_service.collect_design(self.design_concept)
                                self.doc_service.collect_quality_validation("Design", {
                                    "passed": design_validation.passed,
                                    "score": design_validation.score,
                                    "issues": design_validation.issues,
                                    "warnings": design_validation.warnings
                                })

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

                # ÄNDERUNG 30.01.2026: Dokumentation generieren bei Erfolg
                try:
                    if hasattr(self, 'doc_service') and self.doc_service:
                        self._ui_log("DocumentationManager", "Status", "Generiere Projekt-Dokumentation...")
                        # README Kontext vorbereiten
                        readme_context = self.doc_service.generate_readme_context()

                        # ÄNDERUNG 31.01.2026: Echter Documentation Manager Agent für bessere Qualität
                        readme_content = self._generate_readme_with_agent(readme_context)
                        readme_path = self.doc_service.save_readme(readme_content)
                        if readme_path:
                            self._ui_log("DocumentationManager", "Result", f"README.md erstellt: {readme_path}")

                        # CHANGELOG aus Iterations-Daten
                        changelog_path = self.doc_service.save_changelog()
                        if changelog_path:
                            self._ui_log("DocumentationManager", "Result", f"CHANGELOG.md erstellt: {changelog_path}")

                        self._ui_log("DocumentationManager", "DocumentationComplete", json.dumps({
                            "readme": readme_path or "",
                            "changelog": changelog_path or "",
                            "summary": self.doc_service.get_summary()
                        }, ensure_ascii=False))
                except Exception as doc_err:
                    self._ui_log("DocumentationManager", "Warning", f"Dokumentations-Generierung fehlgeschlagen: {doc_err}")

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
