"""
Author: rahn
Datum: 30.01.2026
Version: 1.3
Beschreibung: Schritt-Funktionen fuer den DevLoop.
              ÄNDERUNG 30.01.2026: HELP_NEEDED Events bei kritischen Security-Issues und fehlenden Tests.
              ÄNDERUNG 30.01.2026: Fix - Unit-Test HELP_NEEDED wird IMMER geprüft (auch bei Security-Issues).
              AENDERUNG 31.01.2026: hash_error() fuer Fehler-Modell-Historie.
"""

import os
import re
import json
import base64
import time
import hashlib
import traceback
from datetime import datetime
from typing import Dict, Any, List, Tuple
from concurrent.futures import ThreadPoolExecutor

from crewai import Task

from agents.memory_agent import (
    get_lessons_for_prompt, learn_from_error,
    extract_error_pattern, generate_tags_from_context
)
from budget_tracker import get_budget_tracker
from sandbox_runner import run_sandbox
from unit_test_runner import run_unit_tests
from main import save_multi_file_output
from content_validator import validate_run_bat
from agents.tester_agent import test_project, summarize_ui_result
from .agent_factory import init_agents
from .orchestration_helpers import (
    format_test_feedback,
    is_rate_limit_error,
    is_server_error,
    is_litellm_internal_error,
    is_empty_or_invalid_response,
    is_empty_response_error,  # ÄNDERUNG 30.01.2026: Leere LLM-Antworten erkennen
    is_model_unavailable_error,  # ÄNDERUNG 30.01.2026: 404-Fehler erkennen
    create_human_readable_verdict,
    extract_vulnerabilities,
    truncate_review_output  # ÄNDERUNG 31.01.2026: Review-Output Truncation gegen Wiederholungen
)
# ÄNDERUNG 29.01.2026: Heartbeat für stabile WebSocket-Verbindung
from .heartbeat_utils import run_with_heartbeat
# ÄNDERUNG 30.01.2026: HELP_NEEDED Events gemäß Kommunikationsprotokoll
from .agent_message import create_help_needed
# ÄNDERUNG 30.01.2026: Test-Generator für Free-Tier-Modelle die Unit-Tests ignorieren
from agents.test_generator_agent import create_test_generator, create_test_generation_task, extract_test_files
from backend.test_templates import create_fallback_tests

# ÄNDERUNG 29.01.2026: Dev-Loop Schritte aus OrchestrationManager ausgelagert


# =========================================================================
# AENDERUNG 31.01.2026: Error-Hashing fuer Fehler-Modell-Historie
# =========================================================================

def hash_error(error_content: str) -> str:
    """
    Erstellt einen stabilen Hash aus einem Fehler-Inhalt fuer den Vergleich.

    Normalisiert den Fehler-Text um zu erkennen, ob es sich um denselben
    Fehlertyp handelt, auch wenn Zeilennummern, Timestamps oder Pfade variieren.

    Args:
        error_content: Der Fehler-Text (z.B. Sandbox-Output, Feedback)

    Returns:
        12-stelliger Hash-String zur eindeutigen Fehler-Identifikation
    """
    if not error_content:
        return ""

    # Normalisiere: Entferne variable Teile
    normalized = error_content

    # Zeilennummern entfernen (line 5, Zeile 12, etc.)
    normalized = re.sub(r'[Ll]ine \d+', 'line X', normalized)
    normalized = re.sub(r'[Zz]eile \d+', 'Zeile X', normalized)

    # Timestamps entfernen (2026-01-31, 12:34:56)
    normalized = re.sub(r'\d{4}-\d{2}-\d{2}', 'DATE', normalized)
    normalized = re.sub(r'\d{2}:\d{2}:\d{2}', 'TIME', normalized)

    # Windows/Unix-Pfade entfernen
    normalized = re.sub(r'[A-Z]:\\[^\s\'"]+', 'PATH', normalized)
    normalized = re.sub(r'/[a-zA-Z0-9_/.-]+', 'PATH', normalized)

    # Iterations-Nummern entfernen
    normalized = re.sub(r'[Ii]teration \d+', 'Iteration X', normalized)

    # Whitespace normalisieren
    normalized = ' '.join(normalized.split())

    # Nur erste 500 Zeichen fuer stabilen Hash (groessere Aenderungen = anderer Fehler)
    hash_input = normalized[:500].lower()

    return hashlib.md5(hash_input.encode('utf-8', errors='ignore')).hexdigest()[:12]


# =========================================================================
# ÄNDERUNG 31.01.2026: Projekt-Typ-aware Sandbox-Check
# =========================================================================

import ast


def run_sandbox_for_project(code: str, tech_blueprint: dict) -> str:
    """
    Führt Syntax-Check durch, berücksichtigt den Projekt-Typ aus dem Blueprint.

    WICHTIG: Bei Python-Projekten wird NUR Python-Syntax geprüft.
    JavaScript-Checks werden nur bei JavaScript-Projekten durchgeführt.

    Dies verhindert falsche "JavaScript-Syntaxfehler" bei:
    - Qt Style Sheets (.qss)
    - CSS-Dateien
    - Python-Code mit Braces (z.B. Dict-Literale)

    Args:
        code: Der zu validierende Code
        tech_blueprint: Blueprint mit Projekt-Typ und Sprache

    Returns:
        Validierungsergebnis als String (✅ oder ❌)
    """
    language = tech_blueprint.get("language", "").lower()
    project_type = tech_blueprint.get("project_type", "").lower()

    # Python-Projekte: NUR Python-Syntax prüfen
    if language == "python" or any(pt in project_type for pt in [
        "python", "flask", "fastapi", "django", "tkinter", "pyqt", "pyside", "desktop"
    ]):
        try:
            # AST-Parsing ist sicher und schnell
            ast.parse(code)
            return "✅ Python-Syntaxprüfung bestanden (AST)."
        except SyntaxError as se:
            return f"❌ Python-Syntaxfehler in Zeile {se.lineno}:\n{str(se)}"
        except Exception as e:
            return f"❌ Python-Prüfung fehlgeschlagen:\n{str(e)}"

    # JavaScript/TypeScript-Projekte: Original run_sandbox nutzen
    if language in ["javascript", "typescript"] or any(pt in project_type for pt in [
        "nodejs", "express", "react", "vue", "angular", "electron"
    ]):
        return run_sandbox(code)

    # HTML-Projekte: Original run_sandbox für HTML-Prüfung
    if language == "html" or "static_html" in project_type:
        return run_sandbox(code)

    # Fallback: Für unbekannte Sprachen nur minimale Prüfung
    if code and code.strip():
        return "✅ Code vorhanden (keine spezifische Syntax-Prüfung für diese Sprache)."
    else:
        return "❌ Kein Code vorhanden."


# =========================================================================
# ÄNDERUNG 31.01.2026: Truncation Detection für abgeschnittene LLM-Outputs
# =========================================================================


class TruncationError(Exception):
    """
    Wird geworfen wenn LLM-Output abgeschnitten wurde.

    Ermöglicht dem DevLoop, automatisch auf ein anderes Modell zu wechseln
    wenn Free-Tier-Modelle lange Outputs abschneiden.
    """
    def __init__(self, message: str, truncated_files: List[str] = None):
        super().__init__(message)
        self.truncated_files = truncated_files or []


def _is_python_file_complete(content: str, filename: str) -> Tuple[bool, str]:
    """
    Prüft ob eine Python-Datei syntaktisch vollständig ist.

    Verwendet ast.parse() um Syntax-Fehler zu erkennen, die auf
    abgeschnittenen Output hinweisen (z.B. offene Klammern, unvollständige Strings).

    Args:
        content: Der Dateiinhalt
        filename: Der Dateiname (für Logging)

    Returns:
        Tuple (is_complete, reason): True wenn vollständig, sonst False mit Grund
    """
    if not filename.endswith('.py'):
        return True, "Keine Python-Datei"

    if not content or not content.strip():
        return False, "Datei ist leer"

    try:
        ast.parse(content)
        return True, "Syntax OK"
    except SyntaxError as e:
        # Typische Truncation-Indikatoren
        content_stripped = content.rstrip()

        # Endet mit offenem Konstrukt?
        truncation_endings = ('(', '[', '{', ',', ':', '=', 'def ', 'class ',
                              'if ', 'elif ', 'else:', 'for ', 'while ', 'try:',
                              'except', 'with ', 'import ', 'from ')

        if any(content_stripped.endswith(ending) for ending in truncation_endings):
            return False, f"Endet mit offenem Konstrukt: ...{content_stripped[-30:]}"

        # Unvollständiger String?
        error_msg = str(e).lower()
        if 'unterminated string' in error_msg or 'eof in multi-line' in error_msg:
            return False, f"Unvollständiger String: {error_msg}"

        # 'unexpected EOF' ist ein starker Truncation-Indikator
        if 'unexpected eof' in error_msg or 'expected an indented block' in error_msg:
            return False, f"Unerwartetes Dateiende: {error_msg}"

        # Andere Syntax-Fehler könnten echte Bugs sein, nicht Truncation
        # Aber wenn die Datei in der Mitte eines Statements endet, ist es wahrscheinlich Truncation
        if len(content) > 100 and not content_stripped.endswith(('\n', ')', ']', '}', '"""', "'''")):
            return False, f"Endet nicht mit gültigem Abschluss: {error_msg}"

        # Echter Syntax-Fehler, keine Truncation
        return True, f"Syntax-Fehler (kein Truncation): {error_msg}"


def _check_for_truncation(files_dict: Dict[str, str]) -> List[Tuple[str, str]]:
    """
    Prüft alle Dateien auf Truncation.

    Args:
        files_dict: Dict mit Dateiname → Inhalt

    Returns:
        Liste von (filename, reason) Tupeln für abgeschnittene Dateien
    """
    truncated = []
    for filename, content in files_dict.items():
        is_complete, reason = _is_python_file_complete(content, filename)
        if not is_complete:
            truncated.append((filename, reason))
    return truncated


# =========================================================================
# ÄNDERUNG 30.01.2026: Test-Generierung für Free-Tier-Modelle
# =========================================================================

def run_test_generator(manager, code_files: Dict[str, str], iteration: int) -> bool:
    """
    Führt den Test-Generator Agent aus wenn keine Tests vorhanden sind.

    Args:
        manager: OrchestrationManager Instanz
        code_files: Dict mit Dateiname → Inhalt
        iteration: Aktuelle Iteration

    Returns:
        True wenn Tests erstellt wurden
    """
    manager._ui_log("TestGenerator", "Status", "Starte Test-Generierung...")

    try:
        # Erstelle Test-Generator Agent
        test_agent = create_test_generator(
            manager.config,
            manager.project_rules,
            router=manager.model_router
        )

        # Erstelle Task
        task = create_test_generation_task(
            test_agent,
            code_files,
            manager.tech_blueprint.get("project_type", "python_script"),
            manager.tech_blueprint
        )

        # Führe Task aus
        from crewai import Crew
        crew = Crew(agents=[test_agent], tasks=[task], verbose=True)
        result = crew.kickoff()

        # Parse Output und erstelle Dateien
        result_str = str(result)
        if result_str and "### FILENAME:" in result_str:
            test_files = extract_test_files(result_str)
            if test_files:
                # Speichere Test-Dateien
                for filename, content in test_files.items():
                    full_path = os.path.join(manager.project_path, filename)
                    os.makedirs(os.path.dirname(full_path), exist_ok=True)
                    with open(full_path, "w", encoding="utf-8") as f:
                        f.write(content)

                manager._ui_log("TestGenerator", "Result",
                    f"Tests erstellt: {', '.join(test_files.keys())}")
                return True

        # Agent hat keine Tests erstellt → Fallback
        manager._ui_log("TestGenerator", "Warning",
            "Agent hat keine Tests erstellt, verwende Templates...")
        return False

    except Exception as e:
        manager._ui_log("TestGenerator", "Error", f"Test-Generator fehlgeschlagen: {e}")
        return False


def ensure_tests_exist(manager, iteration: int) -> bool:
    """
    Stellt sicher dass Unit-Tests existieren.
    Ruft Test-Generator auf wenn nötig, dann Fallback zu Templates.

    Diese Funktion löst das Problem dass Free-Tier-Modelle (xiaomi, qwen, etc.)
    die Anweisung zum Erstellen von Unit-Tests ignorieren.

    Args:
        manager: OrchestrationManager Instanz
        iteration: Aktuelle Iteration

    Returns:
        True wenn Tests existieren (oder erstellt wurden)
    """
    tests_dir = os.path.join(manager.project_path, "tests")

    # Prüfe ob Tests existieren
    if os.path.exists(tests_dir):
        test_files = [f for f in os.listdir(tests_dir) if f.startswith("test_") and f.endswith(".py")]
        if test_files:
            manager._ui_log("Tester", "Info", f"Tests vorhanden: {len(test_files)} Dateien")
            return True

    # Auch Root-Level test_*.py prüfen
    root_test_files = [f for f in os.listdir(manager.project_path)
                       if f.startswith("test_") and f.endswith(".py")]
    if root_test_files:
        manager._ui_log("Tester", "Info", f"Tests im Root: {len(root_test_files)} Dateien")
        return True

    manager._ui_log("Tester", "Warning", "Keine Unit-Tests gefunden, starte Test-Generierung...")

    # Sammle vorhandene Code-Dateien
    code_files = {}
    for filename in os.listdir(manager.project_path):
        if filename.endswith(".py") and not filename.startswith("test_"):
            filepath = os.path.join(manager.project_path, filename)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    code_files[filename] = f.read()
            except Exception as e:
                manager._ui_log("TestGenerator", "Warning", f"Konnte {filename} nicht lesen: {e}")

    if not code_files:
        manager._ui_log("TestGenerator", "Warning", "Keine Python-Dateien zum Testen gefunden")
        return False

    # Versuch 1: Test-Generator Agent (nur bei Iteration > 1 um nicht jeden Run zu verlangsamen)
    if iteration > 0:
        if run_test_generator(manager, code_files, iteration):
            return True

    # Versuch 2: Template-basierte Tests
    manager._ui_log("Tester", "Info", "Verwende Template-Tests als Fallback...")
    project_type = manager.tech_blueprint.get("project_type", "python_script")
    created = create_fallback_tests(manager.project_path, project_type)

    if created:
        manager._ui_log("Tester", "Result", f"Template-Tests erstellt: {', '.join(created)}")
        return True
    else:
        manager._ui_log("Tester", "Error", "Keine passenden Test-Templates gefunden")
        return False


def build_coder_prompt(manager, user_goal: str, feedback: str, iteration: int) -> str:
    """
    Baut den Coder-Prompt basierend auf Kontext, Feedback und Security-Tasks.
    """
    c_prompt = f"Ziel: {user_goal}\nTech: {manager.tech_blueprint}\nDB: {manager.database_schema}\n"

    briefing_context = manager.get_briefing_context()
    if briefing_context:
        c_prompt += f"\n{briefing_context}\n"

    if not manager.is_first_run:
        c_prompt += f"\nAlt-Code:\n{manager.current_code}\n"
    if feedback:
        c_prompt += f"\nKorrektur: {feedback}\n"

    if iteration == 0 and not feedback:
        c_prompt += "\n\n🛡️ SECURITY BASICS (von Anfang an beachten!):\n"
        c_prompt += "- Kein innerHTML/document.write mit User-Input (XSS-Risiko)\n"
        c_prompt += "- Keine String-Konkatenation in SQL/DB-Queries (Injection-Risiko)\n"
        c_prompt += "- Keine hardcoded API-Keys, Passwörter oder Secrets im Code\n"
        c_prompt += "- Bei eval(): Nur mit Button-Input, NIEMALS mit User-Text-Input\n"
        c_prompt += "- Nutze textContent statt innerHTML wenn möglich\n\n"

    try:
        memory_path = os.path.join(manager.base_dir, "memory", "global_memory.json")
        tech_stack = manager.tech_blueprint.get("project_type", "") if manager.tech_blueprint else ""
        lessons = get_lessons_for_prompt(memory_path, tech_stack=tech_stack)
        if lessons and lessons.strip():
            c_prompt += f"\n\n📚 LESSONS LEARNED (aus früheren Projekten - UNBEDINGT BEACHTEN!):\n{lessons}\n"
            manager._ui_log("Memory", "LessonsApplied", f"Coder erhält {len(lessons.splitlines())} Lektionen")
    except Exception as les_err:
        manager._ui_log("Memory", "Warning", f"Lektionen konnten nicht geladen werden: {les_err}")

    if hasattr(manager, 'security_vulnerabilities') and manager.security_vulnerabilities:
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        sorted_vulns = sorted(
            manager.security_vulnerabilities,
            key=lambda v: severity_order.get(v.get("severity", "medium"), 2)
        )

        coder_tasks = []
        task_prompt_lines = []

        for i, vuln in enumerate(sorted_vulns, 1):
            task_id = f"SEC-{i:03d}"
            severity = vuln.get("severity", "medium").upper()
            description = vuln.get("description", "Unbekannte Schwachstelle")
            fix = vuln.get("fix", "Bitte beheben")
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

            file_hint = f"\n   -> DATEI: {affected_file}" if affected_file else ""
            task_prompt_lines.append(
                f"TASK {task_id} [{severity}]: {description}{file_hint}\n"
                f"   -> LÖSUNG: {fix}"
            )

        manager._ui_log("Coder", "CoderTasksOutput", json.dumps({
            "tasks": coder_tasks,
            "count": len(coder_tasks),
            "iteration": iteration + 1
        }, ensure_ascii=False))

        c_prompt += "\n\n⚠️ SECURITY TASKS (priorisiert nach Severity - CRITICAL zuerst):\n"
        c_prompt += "\n".join(task_prompt_lines)
        c_prompt += "\n\nWICHTIG: Bearbeite die Tasks in der angegebenen Reihenfolge! Implementiere die LÖSUNG für jeden Task!\n"

    c_prompt += "\n\n🧪 UNIT-TEST REQUIREMENT:\n"
    c_prompt += "- Erstelle IMMER Unit-Tests für alle neuen Funktionen/Klassen\n"
    c_prompt += "- Test-Dateien: tests/test_<modulname>.py oder tests/<modulname>.test.js\n"
    c_prompt += "- Mindestens 3 Test-Cases pro Funktion (normal, edge-case, error-case)\n"
    c_prompt += "- Format: ### FILENAME: tests/test_<modulname>.py\n"
    c_prompt += "- Tests müssen AUSFÜHRBAR sein (pytest bzw. npm test)\n"

    if manager.tech_blueprint and manager.tech_blueprint.get("requires_server"):
        c_prompt += "\n🔌 API-TESTS:\n"
        c_prompt += "- Teste JEDEN API-Endpoint mit mindestens 2 Test-Cases\n"
        c_prompt += "- Prüfe Erfolgs-Response UND Fehler-Response\n"
        c_prompt += "- Python: pytest + Flask test_client oder requests\n"
        c_prompt += "- JavaScript: jest + supertest\n"

    c_prompt += "\nFormat: ### FILENAME: path/to/file.ext"
    return c_prompt


def run_coder_task(manager, project_rules: Dict[str, Any], c_prompt: str, agent_coder) -> Tuple[str, Any]:
    """
    Fuehrt den Coder-Task mit Retry-Logik und Heartbeat-Updates aus.
    ÄNDERUNG 29.01.2026: Modellwechsel erst nach 2 gleichen Fehlern mit demselben Modell.
    """
    task_coder = Task(description=c_prompt, expected_output="Code", agent=agent_coder)
    MAX_CODER_RETRIES = 6  # Erhöht: 2 Versuche pro Modell x 3 Modelle
    # ÄNDERUNG 30.01.2026: Timeout aus globaler Config
    CODER_TIMEOUT_SECONDS = manager.config.get("agent_timeout_seconds", 300)
    # ÄNDERUNG 29.01.2026: Modellwechsel erst nach X gleichen Fehlern
    ERRORS_BEFORE_MODEL_SWITCH = 2
    current_code = ""

    # Fehler-Tracker: (modell, fehlertyp) -> anzahl
    error_tracker = {}
    last_error_type = None

    for coder_attempt in range(MAX_CODER_RETRIES):
        current_model = manager.model_router.get_model("coder") if manager.model_router else "unknown"
        try:
            # ÄNDERUNG 29.01.2026: Heartbeat-Wrapper für stabile WebSocket-Verbindung
            current_code = run_with_heartbeat(
                func=lambda: str(task_coder.execute_sync()).strip(),
                ui_log_callback=manager._ui_log,
                agent_name="Coder",
                task_description=f"Code-Generierung (Versuch {coder_attempt + 1}/{MAX_CODER_RETRIES})",
                heartbeat_interval=15,
                timeout_seconds=CODER_TIMEOUT_SECONDS
            )
            break
        except TimeoutError as te:
            error_type = "timeout"
            error_key = (current_model, error_type)

            # Bei neuem Fehlertyp: Tracker zurücksetzen
            if last_error_type and last_error_type != error_type:
                error_tracker = {}
            last_error_type = error_type

            error_tracker[error_key] = error_tracker.get(error_key, 0) + 1
            error_count = error_tracker[error_key]

            manager._ui_log("Coder", "Timeout",
                            f"Coder-Modell {current_model} timeout nach {CODER_TIMEOUT_SECONDS}s (Fehler {error_count}/{ERRORS_BEFORE_MODEL_SWITCH})")

            # Erst nach ERRORS_BEFORE_MODEL_SWITCH gleichen Fehlern Modell wechseln
            if error_count >= ERRORS_BEFORE_MODEL_SWITCH:
                manager._ui_log("Coder", "Status", f"🔄 Modellwechsel nach {error_count} Timeouts")
                manager.model_router.mark_rate_limited_sync(current_model)
                agent_coder = init_agents(
                    manager.config,
                    project_rules,
                    router=manager.model_router,
                    include=["coder"]
                ).get("coder")
                task_coder = Task(description=c_prompt, expected_output="Code", agent=agent_coder)
                error_tracker = {}  # Tracker zurücksetzen nach Modellwechsel

            if coder_attempt == MAX_CODER_RETRIES - 1:
                manager._ui_log("Coder", "Error", f"Alle {MAX_CODER_RETRIES} Versuche fehlgeschlagen (Timeout)")
                raise te
            continue

        except Exception as error:
            # ÄNDERUNG 29.01.2026: LiteLLM interne Bugs wie Rate-Limits behandeln
            if is_litellm_internal_error(error):
                error_type = "litellm_bug"
                error_key = (current_model, error_type)

                # Bei neuem Fehlertyp: Tracker zurücksetzen
                if last_error_type and last_error_type != error_type:
                    error_tracker = {}
                last_error_type = error_type

                error_tracker[error_key] = error_tracker.get(error_key, 0) + 1
                error_count = error_tracker[error_key]

                manager._ui_log("Coder", "Warning",
                                f"LiteLLM-Bug erkannt (Fehler {error_count}/{ERRORS_BEFORE_MODEL_SWITCH}): {str(error)[:100]}")

                # Erst nach ERRORS_BEFORE_MODEL_SWITCH gleichen Fehlern Modell wechseln
                if error_count >= ERRORS_BEFORE_MODEL_SWITCH:
                    manager._ui_log("Coder", "Status", f"🔄 Modellwechsel nach {error_count} LiteLLM-Bugs")
                    manager.model_router.mark_rate_limited_sync(current_model)
                    agent_coder = init_agents(
                        manager.config,
                        project_rules,
                        router=manager.model_router,
                        include=["coder"]
                    ).get("coder")
                    task_coder = Task(description=c_prompt, expected_output="Code", agent=agent_coder)
                    error_tracker = {}  # Tracker zurücksetzen nach Modellwechsel

                if coder_attempt == MAX_CODER_RETRIES - 1:
                    manager._ui_log("Coder", "Error", f"Alle {MAX_CODER_RETRIES} Versuche fehlgeschlagen (LiteLLM-Bug): {str(error)[:200]}")
                    raise error
                continue

            if is_rate_limit_error(error):
                # Rate-Limit: Sofort wechseln (keine Wartezeit sinnvoll)
                manager.model_router.mark_rate_limited_sync(current_model)
                manager._ui_log(
                    "ModelRouter",
                    "RateLimit",
                    f"Modell {current_model} pausiert, wechsle zu Fallback..."
                )
                agent_coder = init_agents(
                    manager.config,
                    project_rules,
                    router=manager.model_router,
                    include=["coder"]
                ).get("coder")
                task_coder = Task(description=c_prompt, expected_output="Code", agent=agent_coder)
                error_tracker = {}  # Tracker zurücksetzen

                if coder_attempt == MAX_CODER_RETRIES - 1:
                    manager._ui_log("Coder", "Error", f"Alle {MAX_CODER_RETRIES} Versuche fehlgeschlagen: {str(error)[:200]}")
                    raise error
                continue

            # ÄNDERUNG 29.01.2026: Server-Fehler-Delay im Caller statt im Helper
            if is_server_error(error):
                manager._ui_log("Coder", "Warning", "Server-Fehler erkannt - kurze Pause von 5s")
                time.sleep(5)
            manager._ui_log("Coder", "Error", f"Unerwarteter Fehler: {str(error)[:200]}")
            raise error

    return current_code, agent_coder


# =========================================================================
# ÄNDERUNG 31.01.2026: Unicode-Sanitization gegen Free-Tier LLM Emoji-Output
# =========================================================================

def _sanitize_unicode(content: str) -> str:
    """
    Entfernt/ersetzt problematische Unicode-Zeichen die Python-Syntaxfehler verursachen.

    ÄNDERUNG 31.01.2026: Defense in Depth gegen Free-Tier LLM Unicode-Output.
    ERWEITERUNG 31.01.2026: Zusaetzliche Zeichen nach Live-Monitoring hinzugefuegt.

    Problem: Modelle wie xiaomi/mimo-v2-flash:free generieren:
    - Unsichtbare Variation Selectors (U+FE0F) die Python-Syntax brechen
    - "Smart" Zeichen (Typografie) die wie ASCII aussehen aber ungueltig sind

    GRUPPE 1 - Unsichtbare Zeichen (werden entfernt):
    - U+FE0F: Emoji Variation Selector-16
    - U+FE0E: Text Variation Selector-15
    - U+200B: Zero Width Space
    - U+200C: Zero Width Non-Joiner
    - U+200D: Zero Width Joiner
    - U+FEFF: Byte Order Mark

    GRUPPE 2 - Smart-Zeichen (werden durch ASCII ersetzt):
    - U+2011: Non-Breaking Hyphen -> -
    - U+2013: En Dash -> -
    - U+2014: Em Dash -> --
    - U+2018/U+2019: Smart Single Quotes -> '
    - U+201C/U+201D: Smart Double Quotes -> "
    - U+2026: Horizontal Ellipsis -> ...
    - U+00A0: Non-Breaking Space -> Space

    Args:
        content: Der zu bereinigende Code-String

    Returns:
        Bereinigter Code ohne problematische Unicode-Zeichen
    """
    # Gruppe 1: Komplett entfernen (unsichtbar)
    invisible_chars = [
        '\uFE0F',  # Emoji Variation Selector-16
        '\uFE0E',  # Text Variation Selector-15
        '\u200B',  # Zero Width Space
        '\u200C',  # Zero Width Non-Joiner
        '\u200D',  # Zero Width Joiner
        '\uFEFF',  # Byte Order Mark
    ]
    for char in invisible_chars:
        content = content.replace(char, '')

    # Gruppe 2: Ersetzen durch ASCII-Aequivalent
    replacements = {
        '\u2011': '-',    # Non-Breaking Hyphen
        '\u2013': '-',    # En Dash
        '\u2014': '--',   # Em Dash
        '\u2018': "'",    # Left Single Quotation Mark
        '\u2019': "'",    # Right Single Quotation Mark (Apostroph)
        '\u201C': '"',    # Left Double Quotation Mark
        '\u201D': '"',    # Right Double Quotation Mark
        '\u2026': '...',  # Horizontal Ellipsis
        '\u00A0': ' ',    # Non-Breaking Space
    }
    for unicode_char, ascii_char in replacements.items():
        content = content.replace(unicode_char, ascii_char)

    return content


def save_coder_output(manager, current_code: str, output_path: str, iteration: int, max_retries: int) -> List[str]:
    """
    Speichert Coder-Output und sendet UI-Events.
    ÄNDERUNG 31.01.2026: Truncation-Detection für abgeschnittene LLM-Outputs.
    ÄNDERUNG 31.01.2026: Unicode-Sanitization vor Datei-Speicherung.
    """
    # ÄNDERUNG 31.01.2026: Unicode-Sanitization vor Datei-Speicherung
    # Entfernt unsichtbare Zeichen (U+FE0F etc.) die Python-Syntax brechen
    sanitized_code = _sanitize_unicode(current_code)

    def_file = os.path.basename(output_path)
    created_files = save_multi_file_output(manager.project_path, sanitized_code, def_file)
    manager._ui_log("Coder", "Files", f"Created: {', '.join(created_files)}")

    # ÄNDERUNG 31.01.2026: Truncation-Detection
    # Prüfe ob Python-Dateien vollständig sind (nicht abgeschnitten)
    try:
        files_to_check = {}
        for filename in created_files:
            if filename.endswith('.py'):
                filepath = os.path.join(manager.project_path, filename)
                if os.path.exists(filepath):
                    with open(filepath, 'r', encoding='utf-8') as f:
                        files_to_check[filename] = f.read()

        truncated_files = _check_for_truncation(files_to_check)
        if truncated_files:
            truncated_names = [f[0] for f in truncated_files]
            truncation_details = "; ".join([f"{f[0]}: {f[1]}" for f in truncated_files])
            manager._ui_log("Coder", "TruncationWarning", json.dumps({
                "truncated_files": truncated_names,
                "details": truncation_details,
                "iteration": iteration + 1,
                "action": "model_switch_recommended"
            }, ensure_ascii=False))
            manager._ui_log("Coder", "Warning",
                f"⚠️ Abgeschnittene Dateien erkannt: {', '.join(truncated_names)}")
    except Exception as trunc_err:
        manager._ui_log("Coder", "Warning", f"Truncation-Check fehlgeschlagen: {trunc_err}")

    current_model = manager.model_router.get_model("coder") if manager.model_router else "unknown"
    manager._ui_log("Coder", "CodeOutput", json.dumps({
        "code": current_code,
        "files": created_files,
        "iteration": iteration + 1,
        "max_iterations": max_retries,
        "model": current_model
    }, ensure_ascii=False))
    manager._update_worker_status("coder", "idle")

    try:
        tracker = get_budget_tracker()
        today_totals = tracker.get_today_totals()
        manager._ui_log("Coder", "TokenMetrics", json.dumps({
            "total_tokens": today_totals.get("total_tokens", 0),
            "total_cost": today_totals.get("total_cost", 0.0)
        }, ensure_ascii=False))
    except Exception as budget_err:
        # ÄNDERUNG 29.01.2026: Budget-Tracker Fehler sichtbar loggen
        manager._ui_log(
            "Coder",
            "Warning",
            "Fehler bei get_budget_tracker/tracker.get_today_totals; Details siehe Stacktrace."
        )
        manager._ui_log("Coder", "Warning", traceback.format_exc())

    return created_files


def run_sandbox_and_tests(
    manager,
    current_code: str,
    created_files: List[str],
    iteration: int,
    project_type: str
) -> Tuple[str, bool, Dict[str, Any], Dict[str, Any], str]:
    """
    Fuehrt Sandbox, Unit-Tests und UI-Tests aus.
    ÄNDERUNG 31.01.2026: Projekt-Typ-aware Sandbox-Check - keine JS-Checks bei Python-Projekten.
    """
    # ÄNDERUNG 31.01.2026: Nutze Projekt-Typ-aware Sandbox statt generischem run_sandbox()
    sandbox_result = run_sandbox_for_project(current_code, manager.tech_blueprint)
    manager._ui_log("Sandbox", "Result", sandbox_result)
    sandbox_failed = sandbox_result.startswith("❌")

    try:
        from sandbox_runner import validate_project_references
        ref_result = validate_project_references(manager.project_path)
        if ref_result.startswith("❌"):
            sandbox_result += f"\n{ref_result}"
            sandbox_failed = True
            manager._ui_log("Sandbox", "Referenzen", ref_result)
        else:
            manager._ui_log("Sandbox", "Referenzen", ref_result)
    except Exception as ref_err:
        manager._ui_log("Sandbox", "Warning", f"Referenz-Validierung fehlgeschlagen: {ref_err}")

    try:
        bat_result = validate_run_bat(manager.project_path, manager.tech_blueprint)
        if bat_result.issues:
            for issue in bat_result.issues:
                manager._ui_log("Tester", "RunBatWarning", issue)
        if bat_result.warnings:
            for warning in bat_result.warnings:
                manager._ui_log("Tester", "RunBatInfo", warning)
    except Exception as bat_err:
        manager._ui_log("Tester", "Warning", f"run.bat-Validierung fehlgeschlagen: {bat_err}")

    if sandbox_failed:
        try:
            memory_path = os.path.join(manager.base_dir, "memory", "global_memory.json")
            error_msg = extract_error_pattern(sandbox_result)
            tags = generate_tags_from_context(manager.tech_blueprint, sandbox_result)
            # ÄNDERUNG 29.01.2026: Non-blocking Memory-Operation für WebSocket-Stabilität
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(learn_from_error, memory_path, error_msg, tags)
                learn_result = future.result(timeout=5)  # Max 5s warten
            manager._ui_log("Memory", "Learning", f"Sandbox: {learn_result}")
        except Exception as mem_err:
            manager._ui_log("Memory", "Error", f"Memory-Operation fehlgeschlagen: {mem_err}")

    unit_test_result = {"status": "SKIP", "summary": "Keine Unit-Tests", "test_count": 0}
    try:
        manager._ui_log("UnitTest", "Status", "Führe Unit-Tests durch...")
        manager._update_worker_status("tester", "working", "Unit-Tests...", "pytest/jest")

        # ÄNDERUNG 30.01.2026: Stelle sicher dass Tests existieren bevor wir sie ausführen
        # (Free-Tier-Modelle ignorieren oft die Anweisung zum Erstellen von Unit-Tests)
        ensure_tests_exist(manager, iteration)

        unit_test_result = run_unit_tests(manager.project_path, manager.tech_blueprint)
        manager._ui_log("UnitTest", "Result", json.dumps({
            "status": unit_test_result.get("status"),
            "summary": unit_test_result.get("summary"),
            "test_count": unit_test_result.get("test_count", 0),
            "iteration": iteration + 1
        }, ensure_ascii=False))
        if unit_test_result.get("status") == "FAIL":
            sandbox_failed = True
            sandbox_result += f"\n\n❌ UNIT-TESTS FEHLGESCHLAGEN:\n{unit_test_result.get('summary', '')}"
            if unit_test_result.get("details"):
                sandbox_result += f"\n{unit_test_result.get('details', '')[:1000]}"
    except ImportError:
        manager._ui_log("UnitTest", "Warning", "unit_test_runner.py nicht gefunden - übersprungen")
    except Exception as ut_err:
        manager._ui_log("UnitTest", "Error", f"Unit-Test Fehler: {ut_err}")

    test_summary = "Keine UI-Tests durchgeführt."
    manager._ui_log("Tester", "Status", f"Starte Tests für Projekt-Typ '{project_type}'...")
    manager._update_worker_status("tester", "working", f"Teste {project_type}...", manager.model_router.get_model("tester") if manager.model_router else "")
    ui_result = {"status": "SKIP", "issues": [], "screenshot": None}

    try:
        ui_result = test_project(manager.project_path, manager.tech_blueprint, manager.config)
        test_summary = summarize_ui_result(ui_result)
        manager._ui_log("Tester", "Result", test_summary)

        screenshot_base64 = None
        if ui_result.get("screenshot") and os.path.exists(ui_result["screenshot"]):
            try:
                with open(ui_result["screenshot"], "rb") as img_file:
                    screenshot_base64 = f"data:image/png;base64,{base64.b64encode(img_file.read()).decode('utf-8')}"
            except Exception as img_err:
                manager._ui_log("Tester", "Warning", f"Screenshot konnte nicht geladen werden: {img_err}")

        manager._ui_log("Tester", "UITestResult", json.dumps({
            "status": ui_result["status"],
            "issues": ui_result.get("issues", []),
            "screenshot": screenshot_base64,
            "model": manager.model_router.get_model("tester") if hasattr(manager, 'model_router') else ""
        }, ensure_ascii=False))
        manager._update_worker_status("tester", "idle")

        if ui_result["status"] in ["FAIL", "ERROR"]:
            sandbox_failed = True
            try:
                memory_path = os.path.join(manager.base_dir, "memory", "global_memory.json")
                error_msg = extract_error_pattern(test_summary)
                tags = generate_tags_from_context(manager.tech_blueprint, test_summary)
                tags.append("ui-test")
                # ÄNDERUNG 29.01.2026: Non-blocking Memory-Operation für WebSocket-Stabilität
                with ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(learn_from_error, memory_path, error_msg, tags)
                    learn_result = future.result(timeout=5)  # Max 5s warten
                manager._ui_log("Memory", "Learning", f"Test: {learn_result}")
            except Exception as mem_err:
                manager._ui_log("Memory", "Error", f"Memory-Operation fehlgeschlagen: {mem_err}")
    except Exception as te:
        test_summary = f"❌ Test-Runner Fehler: {te}"
        manager._ui_log("Tester", "Error", test_summary)
        manager._update_worker_status("tester", "idle")
        sandbox_failed = True
        ui_result = {"status": "ERROR", "issues": [str(te)], "screenshot": None}

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
            "has_visible_content": True
        },
        "overall_status": "PASS" if (unit_ok and ui_ok) else "FAIL"
    }

    manager._ui_log("Tester", "TestSummary", json.dumps({
        "overall_status": test_result.get("overall_status"),
        "unit_status": test_result["unit_tests"]["status"],
        "unit_passed": test_result["unit_tests"]["passed"],
        "ui_status": test_result["ui_tests"]["status"],
        "ui_issues_count": len(test_result["ui_tests"]["issues"]),
        "iteration": iteration + 1
    }, ensure_ascii=False))

    return sandbox_result, sandbox_failed, test_result, ui_result, test_summary


def run_review(
    manager,
    project_rules: Dict[str, Any],
    current_code: str,
    sandbox_result: str,
    test_summary: str,
    sandbox_failed: bool,
    run_with_timeout
) -> Tuple[str, str, str]:
    """
    Fuehrt den Review-Task mit Retry-Logik aus.
    ÄNDERUNG 29.01.2026: Modellwechsel erst nach 2 gleichen Fehlern mit demselben Modell.
    """
    r_prompt = f"Review Code:\n{current_code}\nSandbox: {sandbox_result}\nTester: {test_summary}"
    manager._update_worker_status("reviewer", "working", "Prüfe Code...", manager.model_router.get_model("reviewer") if manager.model_router else "")

    MAX_REVIEW_RETRIES = 6  # Erhöht: 2 Versuche pro Modell x 3 Modelle
    # ÄNDERUNG 30.01.2026: Timeout aus globaler Config
    REVIEWER_TIMEOUT_SECONDS = manager.config.get("agent_timeout_seconds", 300)
    # ÄNDERUNG 29.01.2026: Modellwechsel erst nach X gleichen Fehlern
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
            # ÄNDERUNG 29.01.2026: Heartbeat-Wrapper für stabile WebSocket-Verbindung
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

                # Bei neuem Fehlertyp: Tracker zurücksetzen
                if last_error_type and last_error_type != error_type:
                    error_tracker = {}
                last_error_type = error_type

                error_tracker[error_key] = error_tracker.get(error_key, 0) + 1
                error_count = error_tracker[error_key]

                manager._ui_log("Reviewer", "NoResponse",
                                f"Modell {current_model} lieferte keine Antwort (Fehler {error_count}/{ERRORS_BEFORE_MODEL_SWITCH})")

                # Erst nach ERRORS_BEFORE_MODEL_SWITCH gleichen Fehlern Modell wechseln
                if error_count >= ERRORS_BEFORE_MODEL_SWITCH:
                    manager._ui_log("Reviewer", "Status", f"🔄 Modellwechsel nach {error_count} gleichen Fehlern")
                    manager.model_router.mark_rate_limited_sync(current_model)
                    agent_reviewer = init_agents(
                        manager.config,
                        project_rules,
                        router=manager.model_router,
                        include=["reviewer"]
                    ).get("reviewer")
                    manager.agent_reviewer = agent_reviewer
                    error_tracker = {}  # Tracker zurücksetzen nach Modellwechsel
                continue
            break
        except TimeoutError as te:
            error_type = "timeout"
            error_key = (current_model, error_type)

            # Bei neuem Fehlertyp: Tracker zurücksetzen
            if last_error_type and last_error_type != error_type:
                error_tracker = {}
            last_error_type = error_type

            error_tracker[error_key] = error_tracker.get(error_key, 0) + 1
            error_count = error_tracker[error_key]

            manager._ui_log("Reviewer", "Timeout",
                            f"Reviewer-Modell {current_model} timeout nach {REVIEWER_TIMEOUT_SECONDS}s (Fehler {error_count}/{ERRORS_BEFORE_MODEL_SWITCH})")

            # Erst nach ERRORS_BEFORE_MODEL_SWITCH gleichen Fehlern Modell wechseln
            if error_count >= ERRORS_BEFORE_MODEL_SWITCH:
                manager._ui_log("Reviewer", "Status", f"🔄 Modellwechsel nach {error_count} Timeouts")
                manager.model_router.mark_rate_limited_sync(current_model)
                agent_reviewer = init_agents(
                    manager.config,
                    project_rules,
                    router=manager.model_router,
                    include=["reviewer"]
                ).get("reviewer")
                manager.agent_reviewer = agent_reviewer
                error_tracker = {}  # Tracker zurücksetzen nach Modellwechsel
            continue
        except Exception as error:
            if is_rate_limit_error(error):
                # Rate-Limit: Sofort wechseln (keine Wartezeit sinnvoll)
                manager.model_router.mark_rate_limited_sync(current_model)
                manager._ui_log("ModelRouter", "RateLimit", f"Reviewer-Modell {current_model} pausiert, wechsle zu Fallback...")
                agent_reviewer = init_agents(
                    manager.config,
                    project_rules,
                    router=manager.model_router,
                    include=["reviewer"]
                ).get("reviewer")
                manager.agent_reviewer = agent_reviewer
                error_tracker = {}  # Tracker zurücksetzen
                continue
            raise error

    if is_empty_or_invalid_response(review_output):
        review_output = "FEHLER: Alle Review-Modelle haben versagt. Bitte prüfe die API-Verbindung und Modell-Verfügbarkeit."
        manager._ui_log("Reviewer", "AllModelsFailed", "Kein Modell konnte eine gültige Antwort liefern.")

    # ÄNDERUNG 31.01.2026: Review-Output Truncation gegen Wiederholungsschleifen
    # Einige LLMs (z.B. llama-3.3-70b-instruct) wiederholen Saetze in langen Outputs
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


def run_security_rescan(manager, project_rules: Dict[str, Any], current_code: str, iteration: int) -> Tuple[bool, List[Dict[str, Any]]]:
    """
    Fuehrt Security-Rescan fuer den generierten Code aus.
    ÄNDERUNG 30.01.2026: Retry/Fallback bei 404/Rate-Limit Fehlern hinzugefügt.
    """
    security_passed = True
    security_rescan_vulns = []
    MAX_SECURITY_RETRIES = 3
    # ÄNDERUNG 30.01.2026: Timeout aus globaler Config
    SECURITY_TIMEOUT = manager.config.get("agent_timeout_seconds", 300)

    if manager.agent_security and current_code:
        manager._ui_log("Security", "RescanStart", f"Prüfe generierten Code (Iteration {iteration + 1})...")

        security_rescan_prompt = f"""Prüfe diesen Code auf Sicherheitsprobleme:

{current_code}

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

        # ÄNDERUNG 30.01.2026: Retry-Schleife mit Fallback bei 404/Rate-Limit
        for security_attempt in range(MAX_SECURITY_RETRIES):
            current_security_model = manager.model_router.get_model("security") if manager.model_router else "unknown"
            manager._update_worker_status("security", "working",
                f"Security-Scan (Versuch {security_attempt + 1}/{MAX_SECURITY_RETRIES})",
                current_security_model)

            # Neuen Agent mit aktuellem Modell erstellen
            agent_security = init_agents(
                manager.config,
                project_rules,
                router=manager.model_router,
                include=["security"]
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
                security_rescan_vulns = extract_vulnerabilities(security_rescan_result)
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
                # ÄNDERUNG 30.01.2026: Retry bei 404/Rate-Limit/Leere Antwort mit Fallback-Modell
                should_retry = (
                    is_rate_limit_error(sec_err) or
                    is_model_unavailable_error(sec_err) or
                    is_empty_response_error(sec_err)
                )
                if should_retry:
                    error_type = "Rate-Limit" if is_rate_limit_error(sec_err) else \
                                 "404/Nicht verfügbar" if is_model_unavailable_error(sec_err) else \
                                 "Leere Antwort"
                    manager._ui_log("Security", "Warning",
                        f"Security-Modell {current_security_model} {error_type} (Versuch {security_attempt + 1}/{MAX_SECURITY_RETRIES})")
                    manager.model_router.mark_rate_limited_sync(current_security_model)
                    if security_attempt < MAX_SECURITY_RETRIES - 1:
                        manager._ui_log("Security", "Info", "Wechsle zu Fallback-Modell...")
                        continue  # Nächster Versuch mit Fallback

                manager._ui_log("Security", "Error", f"Security-Rescan fehlgeschlagen: {sec_err}")
                manager._update_worker_status("security", "idle")
                # Fail-Closed bei Security-Fehlern
                security_passed = False
                break

    return security_passed, security_rescan_vulns


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
        manager.agent_coder = init_agents(
            manager.config,
            project_rules,
            router=manager.model_router,
            include=["coder"]
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

        history_summary = "\n".join([
            f"- Modell '{a['model']}' (Iteration {a['iteration']}): {a['feedback'][:200]}"
            for a in failed_attempts_history[-3:]
        ])
        feedback += f"\n\n🔄 MODELLWECHSEL: Das vorherige Modell ({old_model}) konnte dieses Problem nicht loesen.\n"
        feedback += f"BISHERIGE VERSUCHE (diese Ansaetze haben NICHT funktioniert):\n{history_summary}\n"
        feedback += "\nWICHTIG: Versuche einen VOELLIG ANDEREN Ansatz! Was bisher versucht wurde, funktioniert nicht!\n"

        manager._ui_log("Coder", "Status", f"🔄 Modellwechsel: {old_model} -> {current_coder_model} (Versuch {len(models_used)})")
    else:
        manager._ui_log("Coder", "Warning", f"Kein weiteres Modell verfuegbar - fahre mit {current_coder_model} fort")

    return current_coder_model, model_attempt, models_used, feedback
