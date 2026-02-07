# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 31.01.2026
Version: 1.0
Beschreibung: Utility-Funktionen für Orchestration Manager.
              Extrahiert aus orchestration_manager.py (Regel 1: Max 500 Zeilen)
              - JSON-Reparatur und Extraktion
              - Requirements-Extraktion aus User Goal
              - Blueprint-Inferenz
              - Timeout-Wrapper
"""

import re
import logging
import threading
from typing import Optional, Dict, List

# ÄNDERUNG 02.02.2026: Import UI_TYPE_KEYWORDS für intelligente UI-Typ Erkennung
from backend.qg_constants import UI_TYPE_KEYWORDS

logger = logging.getLogger(__name__)


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
            logger.debug("run_with_timeout: Ausnahme in Ziel-Funktion: %s", e, exc_info=True)

    logger.info("run_with_timeout: Operation startet (Timeout %ds)", timeout_seconds)
    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    thread.join(timeout=timeout_seconds)

    if thread.is_alive():
        msg = f"Operation dauerte länger als {timeout_seconds}s"
        logger.error("[run_with_timeout] - %s", msg)
        raise TimeoutError(msg)
    if exception[0]:
        exc = exception[0]
        logger.error("[run_with_timeout] - Unerwarteter Fehler: %s", exc, exc_info=True)
        raise Exception(f"Unerwarteter Fehler in Timeout-Operation: {exc}") from exc
    return result[0]


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


def _extract_json_from_text(text: str) -> Optional[str]:
    """
    Extrahiert JSON-Objekt aus Text durch Klammer-Zählung.
    Funktioniert auch mit verschachtelten Objekten, im Gegensatz zu Regex.
    ÄNDERUNG 31.01.2026: Robuste JSON-Extraktion durch Klammer-Zählung

    Args:
        text: Der Text, der JSON enthalten könnte

    Returns:
        Das extrahierte JSON als String, oder None wenn keines gefunden
    """
    # Finde erste öffnende Klammer
    start = text.find('{')
    if start == -1:
        return None

    depth = 0
    in_string = False
    escape_next = False

    for i, char in enumerate(text[start:], start):
        if escape_next:
            escape_next = False
            continue
        if char == '\\':
            escape_next = True
            continue
        if char == '"' and not escape_next:
            in_string = not in_string
            continue
        if in_string:
            continue
        if char == '{':
            depth += 1
        elif char == '}':
            depth -= 1
            if depth == 0:
                return text[start:i+1]

    return None  # Unbalancierte Klammern


def _extract_user_requirements(user_goal: str) -> dict:
    """
    Extrahiert ALLE erkennbaren Anforderungen aus dem Benutzer-Goal.
    ÄNDERUNG 30.01.2026: Erweitert um mehr Keywords (Datenbanken, Sprachen, Frameworks).

    Benutzer-Vorgaben dürfen NICHT ignoriert werden!

    Args:
        user_goal: Das Benutzerziel als String

    Returns:
        Dict mit erkannten Anforderungen (database, language, framework, ui_type)
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

    # ÄNDERUNG 02.02.2026: Intelligente UI-Typ Erkennung (Bug #1 Fix)
    # Problem: "gui" ist zu generisch - kann webapp/desktop bedeuten
    # Lösung: Explizite Keywords (webapp, website) haben Priorität über generische (gui)
    ui_matches: Dict[str, List[str]] = {}
    for ui_type, keywords in UI_TYPE_KEYWORDS.items():
        matching_keywords = [kw for kw in keywords if kw in goal_lower]
        if matching_keywords:
            ui_matches[ui_type] = matching_keywords

    if ui_matches:
        # Priorisiere explizite Matches über generische wie "gui"
        webapp_explicit = ["webapp", "website", "webseite", "web app", "browser"]
        desktop_explicit = ["desktop", "fenster", "window"]

        # webapp explizit genannt = webapp (höchste Priorität)
        if "webapp" in ui_matches and any(kw in webapp_explicit for kw in ui_matches["webapp"]):
            requirements["ui_type"] = "webapp"
        # desktop explizit genannt, aber nur wenn webapp NICHT auch genannt
        elif "desktop" in ui_matches and any(kw in desktop_explicit for kw in ui_matches["desktop"]):
            if "webapp" not in ui_matches:
                requirements["ui_type"] = "desktop"
            else:
                requirements["ui_type"] = "webapp"  # webapp hat Vorrang bei Konflikt
        # api/cli explizit genannt
        elif "api" in ui_matches:
            requirements["ui_type"] = "api"
        elif "cli" in ui_matches:
            requirements["ui_type"] = "cli"
        # Fallback: "gui" alleine ohne expliziten Typ = desktop (alte Logik)
        elif "desktop" in ui_matches:
            requirements["ui_type"] = "desktop"

    return requirements


def _infer_blueprint_from_requirements(user_goal: str) -> dict:
    """
    Erstellt einen Fallback-Blueprint basierend auf erkannten Benutzer-Anforderungen.
    ÄNDERUNG 30.01.2026: Framework-basierte Erkennung hat Vorrang.
    ÄNDERUNG 02.02.2026: try/except + Sprache aus reqs immer übernehmen wenn gesetzt.

    Priorität: Framework > UI-Typ > Datenbank > Sprache > Default

    Args:
        user_goal: Das Benutzerziel als String

    Returns:
        Blueprint-Dict mit project_type, app_type, test_strategy, language, etc.
    """
    try:
        return _infer_blueprint_from_requirements_impl(user_goal)
    except Exception as e:
        logger.error("_infer_blueprint_from_requirements fehlgeschlagen (user_goal=%s, reqs-Kontext): %s",
                     (user_goal[:100] if user_goal else ""), e, exc_info=True)
        return {
            "project_type": "python_script",
            "app_type": "cli",
            "test_strategy": "pytest_only",
            "language": "python",
            "requires_server": False,
            "reasoning": f"Fallback nach Fehler: {e}"
        }


def _infer_blueprint_from_requirements_impl(user_goal: str) -> dict:
    """Interne Implementierung der Blueprint-Inferenz."""
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
    if reqs.get("language"):
        blueprint["language"] = reqs["language"]

    # Begründung für Transparenz
    blueprint["reasoning"] = f"FALLBACK basierend auf Benutzer-Anforderungen: {reqs}"

    return blueprint
