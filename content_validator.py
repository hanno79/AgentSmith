# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 28.01.2026
Version: 1.1
Beschreibung: Content Validator - Erkennt leere Seiten, fehlende Inhalte und
              Tech-Stack-spezifische Rendering-Probleme.
              Wird von tester_agent.py nach dem Playwright-Screenshot aufgerufen.
              ÄNDERUNG 31.01.2026: JavaScript-Check Guard und flexible run_command Validierung
"""

import json
import os
import re
import logging
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ÄNDERUNG 31.01.2026: Guard-Funktion für JavaScript-Checks
def _should_check_javascript(project_path: str, tech_blueprint: Dict[str, Any]) -> bool:
    """
    Prüft ob JavaScript-Validierung sinnvoll ist.

    Vermeidet irreführende JS-Fehler bei reinen Python-Projekten.

    Args:
        project_path: Pfad zum Projektverzeichnis
        tech_blueprint: Blueprint mit Sprach- und Typ-Informationen

    Returns:
        True wenn JavaScript-Checks durchgeführt werden sollten
    """
    # Sprache aus Blueprint prüfen
    language = tech_blueprint.get("language", "").lower()
    if language in ["python", "go", "rust", "java", "c++", "cpp", "csharp"]:
        return False

    # Projekt-Typ prüfen
    project_type = tech_blueprint.get("project_type", "").lower()
    if any(pt in project_type for pt in ["python", "flask", "fastapi", "django", "tkinter", "pyqt", "desktop"]):
        return False

    # Fallback: Prüfe ob .js/.ts Dateien existieren
    if project_path and os.path.isdir(project_path):
        for root, dirs, files in os.walk(project_path):
            # Skip node_modules
            if "node_modules" in root:
                continue
            for f in files:
                if f.endswith(('.js', '.ts', '.jsx', '.tsx')):
                    return True

    return False


# ÄNDERUNG 31.01.2026: Flexible run_command Prüfung
def _run_command_present(run_cmd: str, bat_content: str) -> bool:
    """
    Prüft ob run_command oder eine Variante davon in bat_content ist.

    Flexibler als exakter String-Match:
    - Erkennt Varianten mit src/ Prefix
    - Erkennt nur den Dateinamen (ohne 'python ')

    Args:
        run_cmd: Erwarteter run_command aus Blueprint
        bat_content: Inhalt der run.bat (lowercase)

    Returns:
        True wenn Befehl oder Variante gefunden
    """
    bat_lower = bat_content.lower()
    run_lower = run_cmd.lower().strip()

    # Exakter Match
    if run_lower in bat_lower:
        return True

    # Varianten mit src/ Prefix
    if "python " in run_lower:
        # z.B. "python main.py" -> prüfe auch "python src/main.py"
        script = run_lower.replace("python ", "").strip()
        if f"python src/{script}" in bat_lower:
            return True
        # Oder Script ohne Python prüfen
        if script in bat_lower:
            return True

    # Varianten mit node
    if "node " in run_lower:
        script = run_lower.replace("node ", "").strip()
        if f"node src/{script}" in bat_lower:
            return True
        if script in bat_lower:
            return True

    # Nur Dateiname (ohne interpreter) prüfen
    for part in run_lower.split():
        if part.endswith(('.py', '.js', '.ts', '.sh', '.bat')):
            if part in bat_lower:
                return True

    return False


@dataclass
class ContentValidationResult:
    """Ergebnis der Inhaltsvalidierung."""
    has_visible_content: bool = False
    issues: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    checks_performed: List[str] = field(default_factory=list)
    is_critical_failure: bool = False


def validate_page_content(page, tech_blueprint: Optional[Dict[str, Any]] = None) -> ContentValidationResult:
    """
    Validiert ob die Seite sichtbaren Inhalt hat.

    Wird NACH page.goto() und page.screenshot() aufgerufen.
    Nutzt page.evaluate() um DOM-Checks im Browser auszufuehren.

    Args:
        page: Playwright Page-Objekt (bereits geladen)
        tech_blueprint: Optionaler Blueprint fuer Tech-Stack-spezifische Checks

    Returns:
        ContentValidationResult mit allen gefundenen Problemen
    """
    result = ContentValidationResult()

    try:
        # Universelle Checks
        basic = _check_basic_content(page)
        result.issues.extend(basic.issues)
        result.warnings.extend(basic.warnings)
        result.checks_performed.extend(basic.checks_performed)
        result.has_visible_content = basic.has_visible_content

        # Tech-Stack-spezifische Checks
        if tech_blueprint:
            project_type = str(tech_blueprint.get("project_type", "")).lower()
            language = str(tech_blueprint.get("language", "")).lower()

            if any(kw in project_type for kw in ["react", "next", "vue", "angular"]) or \
               (language == "javascript" and "node" in project_type):
                # AENDERUNG 06.02.2026: tech_blueprint an _check_react_content weiterreichen
                react_result = _check_react_content(page, tech_blueprint)
                result.issues.extend(react_result.issues)
                result.warnings.extend(react_result.warnings)
                result.checks_performed.extend(react_result.checks_performed)
                # React-Check kann has_visible_content ueberschreiben
                if react_result.is_critical_failure:
                    result.has_visible_content = False

            elif any(kw in project_type for kw in ["flask", "fastapi", "django"]):
                server_result = _check_flask_fastapi_content(page)
                result.issues.extend(server_result.issues)
                result.warnings.extend(server_result.warnings)
                result.checks_performed.extend(server_result.checks_performed)
                if server_result.is_critical_failure:
                    result.has_visible_content = False

            elif project_type == "static_html" or (not project_type and language != "javascript"):
                static_result = _check_static_html_content(page)
                result.issues.extend(static_result.issues)
                result.warnings.extend(static_result.warnings)
                result.checks_performed.extend(static_result.checks_performed)

        # Gesamt-Ergebnis bestimmen
        result.is_critical_failure = not result.has_visible_content or len(result.issues) > 0

    except Exception as e:
        logger.warning(f"Content-Validierung fehlgeschlagen: {e}")
        result.warnings.append(f"Content-Validierung konnte nicht vollstaendig durchgefuehrt werden: {e}")

    return result


def _check_basic_content(page) -> ContentValidationResult:
    """
    Fuehrt universelle Inhalts-Checks durch.
    Prueft ob die Seite sichtbaren Text, Elemente und Mindesthoehe hat.
    """
    result = ContentValidationResult()
    result.checks_performed.append("basic_content")

    try:
        # JavaScript im Browser-Kontext ausfuehren
        page_info = page.evaluate("""() => {
            const body = document.body;
            if (!body) return { noBody: true };

            const innerText = (body.innerText || '').trim();
            const errorPatterns = [
                'cannot get', '404 not found', 'not found',
                'internal server error', 'module not found',
                'error boundary', 'application error',
                'err_connection_refused', 'err_file_not_found',
                'traceback (most recent call last)',
                'syntaxerror', 'referenceerror', 'typeerror',
                'uncaught error', 'unhandled rejection'
            ];

            const pageTextLower = innerText.toLowerCase();
            let foundError = '';
            for (const pattern of errorPatterns) {
                if (pageTextLower.includes(pattern)) {
                    foundError = pattern;
                    break;
                }
            }

            return {
                noBody: false,
                bodyInnerTextLength: innerText.length,
                bodyChildrenCount: body.children.length,
                bodyOffsetHeight: body.offsetHeight,
                bodyScrollHeight: body.scrollHeight,
                title: document.title || '',
                visibleElements: document.querySelectorAll(
                    'h1,h2,h3,h4,p,span,a,button,input,table,form,img,canvas,svg,section,main,article,nav,ul,ol,li'
                ).length,
                hasErrorPattern: foundError !== '',
                errorPattern: foundError,
                pageTextPreview: innerText.substring(0, 500)
            };
        }""")

        if page_info.get("noBody"):
            result.issues.append("Kein <body>-Element gefunden - HTML-Struktur ist fehlerhaft")
            result.has_visible_content = False
            return result

        text_len = page_info.get("bodyInnerTextLength", 0)
        children = page_info.get("bodyChildrenCount", 0)
        height = page_info.get("bodyOffsetHeight", 0)
        visible_elems = page_info.get("visibleElements", 0)
        has_error = page_info.get("hasErrorPattern", False)
        error_pattern = page_info.get("errorPattern", "")
        title = page_info.get("title", "")

        # Kritische Checks
        if text_len == 0 and children == 0:
            result.issues.append(
                "Komplett leere Seite - Body hat keinen Text und keine Kinder-Elemente. "
                "Der generierte Code rendert nichts sichtbares."
            )
            result.has_visible_content = False
        elif text_len == 0 and height < 50:
            result.issues.append(
                "Seite hat DOM-Elemente aber keinen sichtbaren Text und minimale Hoehe "
                f"({height}px). Moeglicherweise unsichtbare oder leere Container."
            )
            result.has_visible_content = False
        elif height < 10:
            result.issues.append(
                f"Seite hat fast keine Hoehe ({height}px) - wahrscheinlich leere Seite"
            )
            result.has_visible_content = False
        else:
            result.has_visible_content = True

        if has_error:
            result.issues.append(
                f"Fehler-Pattern auf der Seite erkannt: '{error_pattern}'. "
                "Die Anwendung zeigt einen Fehler statt den erwarteten Inhalt."
            )
            result.has_visible_content = False

        # Warnungen
        if visible_elems == 0 and text_len > 0:
            result.warnings.append(
                "Keine semantischen HTML-Elemente (z. B. h1, p) gefunden - "
                "nur roher Text im Body"
            )

        if not title:
            result.warnings.append("Seite hat keinen <title> - sollte einen beschreibenden Titel haben")

    except Exception as e:
        logger.warning(f"Basic-Content-Check fehlgeschlagen: {e}")
        result.warnings.append(f"Basis-Inhalts-Check konnte nicht ausgefuehrt werden: {e}")
        result.has_visible_content = True  # Im Zweifel nicht blockieren

    return result


def _check_react_content(page, tech_blueprint=None) -> ContentValidationResult:
    """
    Prueft React-spezifische Rendering-Probleme.

    AENDERUNG 06.02.2026: ROOT-CAUSE-FIX Framework-spezifische Container-IDs
    Symptom: "Kein #root oder #app Container gefunden" bei Next.js-Projekten
    Ursache: Hardcoded getElementById('root')||getElementById('app'), aber Next.js nutzt #__next
    Loesung: Container-IDs dynamisch basierend auf Framework waehlen
    """
    result = ContentValidationResult()
    result.checks_performed.append("react_content")

    # AENDERUNG 06.02.2026: Framework-spezifische Container-IDs
    container_ids = ["root", "app"]  # Standard: React (CRA/Vite)
    if tech_blueprint:
        project_type = str(tech_blueprint.get("project_type", "")).lower()
        if "next" in project_type:
            container_ids = ["__next", "root", "app"]
        elif "vue" in project_type:
            container_ids = ["app", "root"]
        elif "angular" in project_type:
            container_ids = ["root", "app-root"]

    # JavaScript-Code dynamisch mit Container-IDs bauen
    ids_js = " || ".join(f"document.getElementById('{cid}')" for cid in container_ids)

    try:
        react_info = page.evaluate(f"""() => {{
            const root = {ids_js};
            if (!root) return {{ hasRoot: false }};

            return {{
                hasRoot: true,
                rootId: root.id,
                rootChildren: root.children.length,
                rootTextLength: (root.innerText || '').trim().length,
                rootHeight: root.offsetHeight,
                hasReactError: !!(
                    root.querySelector('.error-boundary') ||
                    root.querySelector('[data-error]') ||
                    document.querySelector('#root > div[style*="color: red"]')
                ),
                rawReactVisible: (document.body.innerText || '').includes('React.createElement'),
                rawJsxVisible: (document.body.innerText || '').includes('import React')
            }};
        }}""")

        if not react_info.get("hasRoot"):
            # AENDERUNG 06.02.2026: Fehlermeldung mit Framework-spezifischen Container-IDs
            ids_text = ", ".join(f"#{cid}" for cid in container_ids)
            result.issues.append(
                f"Kein {ids_text} Container gefunden - "
                f"App ist nicht korrekt eingebunden. "
                f"Stelle sicher dass ein <div id=\"{container_ids[0]}\"></div> vorhanden ist."
            )
            result.is_critical_failure = True
            return result

        root_children = react_info.get("rootChildren", 0)
        root_text = react_info.get("rootTextLength", 0)
        root_height = react_info.get("rootHeight", 0)

        if root_children == 0:
            result.issues.append(
                f"React #{react_info.get('rootId', 'root')} Container ist leer - "
                "die App-Komponente wird nicht gerendert. Pruefe ob:\n"
                "  - ReactDOM.createRoot() oder ReactDOM.render() korrekt aufgerufen wird\n"
                "  - Die App-Komponente exportiert und importiert wird\n"
                "  - Keine Build-Fehler vorliegen (JSX ohne Transpiler?)"
            )
            result.is_critical_failure = True

        elif root_text == 0 and root_height < 10:
            result.issues.append(
                "React-App hat keinen sichtbaren Inhalt - "
                "moeglicherweise Build- oder Import-Fehler"
            )
            result.is_critical_failure = True

        if react_info.get("hasReactError"):
            result.issues.append(
                "React Error Boundary aktiv - es gibt einen Rendering-Fehler in der App"
            )
            result.is_critical_failure = True

        if react_info.get("rawReactVisible"):
            result.issues.append(
                "React.createElement() ist als Text auf der Seite sichtbar - "
                "JSX wird nicht transpiliert. Pruefe ob ein Build-Tool (Webpack/Vite) konfiguriert ist."
            )
            result.is_critical_failure = True

        if react_info.get("rawJsxVisible"):
            result.issues.append(
                "Import-Statements sind als Text sichtbar - "
                "JavaScript-Module werden nicht verarbeitet. "
                "Pruefe ob <script type=\"module\"> oder ein Bundler verwendet wird."
            )
            result.is_critical_failure = True

    except Exception as e:
        logger.warning(f"React-Content-Check fehlgeschlagen: {e}")
        result.warnings.append(f"React-spezifischer Check fehlgeschlagen: {e}")

    return result


def _check_flask_fastapi_content(page) -> ContentValidationResult:
    """Prueft Flask/FastAPI/Django-spezifische Probleme."""
    result = ContentValidationResult()
    result.checks_performed.append("server_framework_content")

    try:
        server_info = page.evaluate("""() => {
            const text = (document.body.innerText || '').toLowerCase();
            return {
                hasInternalServerError: text.includes('internal server error'),
                hasTraceback: text.includes('traceback'),
                hasDebugger: text.includes('werkzeug debugger') || text.includes('debugger is active'),
                hasJinjaError: text.includes('jinja2') || text.includes('templatenotfound'),
                hasModuleError: text.includes('modulenotfounderror') || text.includes('no module named'),
                hasImportError: text.includes('importerror'),
                pageTitle: document.title.toLowerCase()
            };
        }""")

        if server_info.get("hasInternalServerError"):
            result.issues.append(
                "Server antwortet mit Internal Server Error (500) - "
                "unbehandelter Fehler im Backend. Pruefe Server-Logs."
            )
            result.is_critical_failure = True

        if server_info.get("hasTraceback"):
            result.issues.append(
                "Python Traceback sichtbar auf der Seite - "
                "unbehandelter Fehler im Backend-Code"
            )
            result.is_critical_failure = True

        if server_info.get("hasJinjaError"):
            result.issues.append(
                "Jinja2 Template-Fehler erkannt - "
                "Template nicht gefunden oder Syntax-Fehler im Template"
            )
            result.is_critical_failure = True

        if server_info.get("hasModuleError") or server_info.get("hasImportError"):
            result.issues.append(
                "Python Import/Module-Fehler erkannt - "
                "fehlende Abhaengigkeit oder falscher Import-Pfad"
            )
            result.is_critical_failure = True

        if server_info.get("hasDebugger"):
            result.warnings.append(
                "Werkzeug Debugger aktiv - nicht fuer Produktion geeignet"
            )

    except Exception as e:
        logger.warning(f"Server-Framework-Check fehlgeschlagen: {e}")
        result.warnings.append(f"Server-Framework-Check fehlgeschlagen: {e}")

    return result


def _check_static_html_content(page) -> ContentValidationResult:
    """Prueft statische HTML-Seiten auf vollstaendigen Inhalt."""
    result = ContentValidationResult()
    result.checks_performed.append("static_html_content")

    try:
        static_info = page.evaluate("""() => {
            const body = document.body;
            return {
                bodyHasText: (body.innerText || '').trim().length > 0,
                bodyHasChildren: body.children.length > 0,
                scriptCount: document.querySelectorAll('script[src]').length,
                linkCount: document.querySelectorAll('link[rel="stylesheet"]').length,
                imgCount: document.querySelectorAll('img').length,
                formCount: document.querySelectorAll('form').length
            };
        }""")

        if not static_info.get("bodyHasText") and not static_info.get("bodyHasChildren"):
            result.issues.append(
                "Statische HTML-Seite hat keinen sichtbaren Inhalt im Body - "
                "weder Text noch HTML-Elemente vorhanden"
            )
            result.is_critical_failure = True

        elif not static_info.get("bodyHasText"):
            result.warnings.append(
                "HTML-Seite hat Elemente aber keinen sichtbaren Text - "
                "moeglicherweise nur leere Container oder unsichtbare Elemente"
            )

    except Exception as e:
        logger.warning(f"Static-HTML-Check fehlgeschlagen: {e}")
        result.warnings.append(f"Statischer HTML-Check fehlgeschlagen: {e}")

    return result


def validate_run_bat(project_path: str, tech_blueprint: Dict[str, Any]) -> ContentValidationResult:
    """
    Validiert ob run.bat korrekt konfiguriert ist.

    Args:
        project_path: Projektverzeichnis
        tech_blueprint: Blueprint mit install_command und run_command

    Returns:
        ContentValidationResult
    """
    result = ContentValidationResult()
    result.checks_performed.append("run_bat_validation")

    run_bat_path = os.path.join(project_path, "run.bat")
    requires_server = tech_blueprint.get("requires_server", False)

    # Pruefen ob run.bat existiert
    if not os.path.exists(run_bat_path):
        if requires_server:
            result.issues.append(
                f"run.bat fehlt im Projektverzeichnis ({project_path}) - "
                "Server-Projekt kann nicht gestartet werden"
            )
            result.is_critical_failure = True
        else:
            result.warnings.append("Keine run.bat vorhanden (optional fuer statische Projekte)")
        return result

    # Inhalt pruefen
    try:
        with open(run_bat_path, "r", encoding="utf-8", errors="ignore") as f:
            bat_content = f.read().strip().lower()
    except Exception as e:
        result.issues.append(f"run.bat konnte nicht gelesen werden: {e}")
        return result

    # Ist run.bat leer oder nur Boilerplate?
    minimal_content = bat_content.replace("@echo off", "").replace("pause", "").replace("echo", "").strip()
    if not minimal_content:
        result.issues.append(
            "run.bat ist leer oder enthaelt nur @echo off und pause - "
            "kein Startbefehl vorhanden"
        )
        result.is_critical_failure = True
        return result

    # install_command vorhanden?
    install_cmd = tech_blueprint.get("install_command", "")
    if install_cmd and install_cmd.lower() not in bat_content:
        result.warnings.append(
            f"run.bat enthaelt nicht den Install-Befehl '{install_cmd}' - "
            "Abhaengigkeiten werden moeglicherweise nicht installiert"
        )

    # run_command vorhanden? (ÄNDERUNG 31.01.2026: Flexibler Check)
    run_cmd = tech_blueprint.get("run_command", "")
    if run_cmd and not _run_command_present(run_cmd, bat_content):
        result.warnings.append(
            f"run.bat enthaelt nicht den Start-Befehl '{run_cmd}' (oder Variante mit src/) - "
            "Anwendung wird moeglicherweise nicht gestartet"
        )

    # AENDERUNG 06.02.2026: Doppelklick-Faehigkeit und Sprach-Marker pruefen
    # Symptom: run.bat hatte "bat" als Zeile 1 und erforderte Argumente
    # Ursache: Coder generierte run.bat mit Argument-Pflicht und Sprach-Marker wurde nicht entfernt
    raw_content_lower = bat_content

    # Pruefen ob Sprach-Marker auf Zeile 1 (z.B. "bat" statt "@echo off")
    first_line = raw_content_lower.split("\n")[0].strip() if raw_content_lower else ""
    if first_line in ("bat", "batch", "cmd", "shell", "bash", "sh"):
        result.warnings.append(
            f"run.bat beginnt mit Sprach-Marker '{first_line}' statt '@echo off' - "
            "moeglicherweise Markdown-Artefakt"
        )

    # Pruefen ob Argument-Pflicht vorhanden (User erwartet Doppelklick)
    if 'if "%~1"==""' in raw_content_lower or "if \"%~1\"==\"\"" in raw_content_lower:
        result.warnings.append(
            "run.bat erfordert Argument (z.B. 'run.bat dev') - "
            "sollte direkt per Doppelklick lauffaehig sein ohne Argumente"
        )

    result.has_visible_content = True  # run.bat hat Inhalt
    return result


# AENDERUNG 07.02.2026: Generische Template-Struktur-Validierung
def validate_template_structure(project_path: str, tech_blueprint: Dict[str, Any]) -> ContentValidationResult:
    """
    Generische Validierung: Prueft ob alle required_files aus dem Template vorhanden sind.
    Wird NUR bei Template-basierten Projekten aufgerufen (_source_template gesetzt).
    Ersetzt die hartcodierte validate_nextjs_structure() fuer Template-Projekte.

    Args:
        project_path: Projektverzeichnis
        tech_blueprint: Blueprint mit _source_template Feld

    Returns:
        ContentValidationResult mit Fehlern fuer fehlende Dateien
    """
    result = ContentValidationResult()
    result.checks_performed.append("template_structure")

    source_template_id = tech_blueprint.get("_source_template")
    if not source_template_id:
        return result

    try:
        from techstack_templates.template_loader import get_template_by_id
        template = get_template_by_id(source_template_id)
        if not template:
            return result

        required_files = template.get("required_files", [])
        missing = []
        for req_file in required_files:
            filepath = os.path.join(project_path, req_file)
            if not os.path.exists(filepath):
                missing.append(req_file)

        if missing:
            result.issues.append(
                f"Pflichtdateien fehlen (Template '{source_template_id}'): {', '.join(missing)}"
            )
            result.is_critical_failure = True
    except ImportError:
        pass
    except Exception as e:
        logger.warning("Template-Struktur-Validierung fehlgeschlagen: %s", e)

    return result


# AENDERUNG 07.02.2026: Next.js Pflichtdateien-Pruefung (Fallback fuer Projekte ohne Template)
# ROOT-CAUSE-FIX:
# Symptom: Generiertes Next.js-Projekt startet nicht / Tailwind wirkt nicht
# Ursache: Coder vergisst pages/_app.js, styles/globals.css, react-dom
# Loesung: Dateisystem-Validierung nach Coder-Output mit Feedback fuer naechste Iteration
def validate_nextjs_structure(project_path: str, tech_blueprint: Dict[str, Any]) -> ContentValidationResult:
    """
    Prueft ob Next.js-Pflichtdateien vorhanden sind.

    Args:
        project_path: Projektverzeichnis
        tech_blueprint: Blueprint mit project_type

    Returns:
        ContentValidationResult mit Warnungen/Fehlern
    """
    result = ContentValidationResult()
    result.checks_performed.append("nextjs_structure")

    project_type = str(tech_blueprint.get("project_type", "")).lower()
    if "next" not in project_type:
        return result

    # 1. pages/_app.js vorhanden?
    app_extensions = ["_app.js", "_app.jsx", "_app.tsx"]
    app_found = any(
        os.path.exists(os.path.join(project_path, "pages", ext))
        for ext in app_extensions
    )
    if not app_found:
        result.issues.append(
            "pages/_app.js fehlt - Tailwind CSS und globale Styles funktionieren NICHT ohne _app.js. "
            "Erstelle pages/_app.js mit: import '../styles/globals.css'"
        )

    # 2. styles/globals.css vorhanden?
    css_names = ["globals.css", "global.css"]
    css_found = any(
        os.path.exists(os.path.join(project_path, "styles", name))
        for name in css_names
    )
    if not css_found:
        # AENDERUNG 07.02.2026: Von warnings auf issues geaendert
        # ROOT-CAUSE-FIX: Als WARNING wurde es vom Coder ignoriert → globals.css nie erstellt
        result.issues.append(
            "styles/globals.css fehlt - Tailwind CSS funktioniert NICHT ohne globals.css. "
            "Erstelle styles/globals.css mit: @tailwind base; @tailwind components; @tailwind utilities;"
        )

    # 3. package.json: react-dom vorhanden?
    pkg_path = os.path.join(project_path, "package.json")
    if os.path.exists(pkg_path):
        try:
            with open(pkg_path, "r", encoding="utf-8") as f:
                pkg = json.load(f)
            deps = pkg.get("dependencies", {})
            if "react" in deps and "react-dom" not in deps:
                result.issues.append(
                    "react-dom fehlt in package.json - Next.js/React braucht zwingend react-dom. "
                    "Fuege 'react-dom' mit gleicher Version wie 'react' hinzu"
                )
            # AENDERUNG 07.02.2026: @next/jest existiert nicht auf npm
            # ROOT-CAUSE-FIX: Coder deklariert @next/jest als devDependency → npm install schlaegt fehl
            # Loesung: Validator meldet ERROR damit Coder in naechster Iteration korrigiert
            dev_deps = pkg.get("devDependencies", {})
            if "@next/jest" in dev_deps or "@next/jest" in deps:
                result.issues.append(
                    "Das Paket @next/jest existiert nicht auf npm. "
                    "Verwende next/jest (import aus 'next/jest') statt @next/jest als separates Paket. "
                    "Entferne @next/jest aus devDependencies und nutze: "
                    "const nextJest = require('next/jest')({ dir: './' })"
                )
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"package.json konnte nicht geprueft werden: {e}")

    # AENDERUNG 07.02.2026: API-Routen Pattern pruefen
    # ROOT-CAUSE-FIX: Coder generiert exports.get/post statt Next.js export default handler
    api_dir = os.path.join(project_path, "pages", "api")
    if os.path.isdir(api_dir):
        for api_file in os.listdir(api_dir):
            if api_file.endswith(('.js', '.jsx', '.ts', '.tsx')):
                api_path = os.path.join(api_dir, api_file)
                try:
                    with open(api_path, "r", encoding="utf-8") as f:
                        api_content = f.read()
                    if "exports." in api_content and "export default" not in api_content:
                        result.issues.append(
                            f"pages/api/{api_file} verwendet 'exports.get/post' statt Next.js Pattern. "
                            "MUSS 'export default function handler(req, res)' verwenden mit "
                            "if (req.method === 'GET') / 'POST' etc."
                        )
                except Exception:
                    pass

    result.is_critical_failure = len(result.issues) > 0
    result.has_visible_content = not result.is_critical_failure
    return result


# AENDERUNG 07.02.2026: Import-Dependency-Vollstaendigkeitspruefung
# ROOT-CAUSE-FIX: Coder importiert Packages im Code die nicht in package.json stehen
# Symptom: Internal Server Error / Module not found zur Laufzeit
# Ursache: Kein Validator vergleicht import-Statements mit package.json
# Loesung: Generischer Import-Scanner mit Feedback an Coder
# Node.js built-in Module die NICHT in package.json stehen muessen
_NODE_BUILTINS = frozenset({
    "assert", "buffer", "child_process", "cluster", "console", "constants",
    "crypto", "dgram", "dns", "domain", "events", "fs", "http", "http2",
    "https", "inspector", "module", "net", "os", "path", "perf_hooks",
    "process", "punycode", "querystring", "readline", "repl", "stream",
    "string_decoder", "sys", "timers", "tls", "trace_events", "tty",
    "url", "util", "v8", "vm", "wasi", "worker_threads", "zlib",
})

# Next.js / React interne Module (werden durch das Framework bereitgestellt)
_FRAMEWORK_MODULES = frozenset({
    "react", "react-dom", "next", "react/jsx-runtime", "react/jsx-dev-runtime",
    "next/router", "next/link", "next/image", "next/head", "next/script",
    "next/dynamic", "next/font", "next/font/google", "next/font/local",
    "next/navigation", "next/headers", "next/server",
})


# AENDERUNG 07.02.2026: Inline-SVG Data-URL Erkennung (Fix 20)
# ROOT-CAUSE-FIX:
# Symptom: SVG Data-URLs in CSS/JSX brechen Sandbox-Parsing (unescapte Anfuehrungszeichen)
# Ursache: Coder generiert background-image: url("data:image/svg+xml,<svg ...>")
# Loesung: Validator meldet WARNING damit Coder in naechster Iteration korrigiert
def validate_no_inline_svg(project_path: str, tech_blueprint: Dict[str, Any]) -> ContentValidationResult:
    """
    Prueft ob CSS/JS/JSX-Dateien inline SVG Data-URLs enthalten.

    Inline SVGs verursachen Parser-Fehler weil unescapte Anfuehrungszeichen
    den Code brechen. Alternativen: separate .svg Dateien, CSS-Gradienten,
    oder URL-encoded SVGs mit %3C/%22.

    Args:
        project_path: Projektverzeichnis
        tech_blueprint: Blueprint mit language-Info

    Returns:
        ContentValidationResult mit Warnungen bei Inline-SVG-Fund
    """
    result = ContentValidationResult()
    result.checks_performed.append("inline_svg_check")

    svg_pattern = re.compile(r'data:image/svg\+xml', re.IGNORECASE)
    found_files = []

    for root_dir, dirs, files in os.walk(project_path):
        dirs[:] = [d for d in dirs if d not in ("node_modules", ".next", ".git")]
        for fname in files:
            if fname.endswith((".css", ".js", ".jsx", ".tsx", ".ts")):
                fpath = os.path.join(root_dir, fname)
                try:
                    with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                    if svg_pattern.search(content):
                        rel_path = os.path.relpath(fpath, project_path).replace("\\", "/")
                        found_files.append(rel_path)
                except Exception:
                    pass

    if found_files:
        result.warnings.append(
            f"Inline SVG Data-URL gefunden in: {', '.join(found_files[:5])}. "
            "Verwende separate .svg Dateien in public/ oder URL-Encoding "
            "(%3C statt <, %22 statt Anfuehrungszeichen). "
            "Inline SVGs brechen Parser wegen unescapter Anfuehrungszeichen."
        )

    return result


def validate_import_dependencies(project_path: str, tech_blueprint: Dict[str, Any]) -> ContentValidationResult:
    """
    Prueft ob alle importierten Packages in package.json deklariert sind.

    Scannt alle JS/TS-Dateien nach import/require-Statements und vergleicht
    die externen Package-Namen mit den deklarierten Dependencies in package.json.

    Args:
        project_path: Projektverzeichnis
        tech_blueprint: Blueprint mit language-Info

    Returns:
        ContentValidationResult mit fehlenden Dependencies als issues
    """
    result = ContentValidationResult()
    result.checks_performed.append("import_dependencies")

    language = str(tech_blueprint.get("language", "")).lower()
    if language not in ("javascript", "typescript"):
        return result

    pkg_path = os.path.join(project_path, "package.json")
    if not os.path.exists(pkg_path):
        return result

    # 1. Package.json Dependencies lesen
    try:
        with open(pkg_path, "r", encoding="utf-8") as f:
            pkg = json.load(f)
    except (json.JSONDecodeError, OSError):
        return result

    declared_deps = set()
    for key in ("dependencies", "devDependencies", "peerDependencies"):
        declared_deps.update(pkg.get(key, {}).keys())

    # 2. Alle JS/TS/JSX/TSX Dateien nach Imports scannen
    import_pattern = re.compile(
        r"""(?:import\s+.*?\s+from\s+['"]([^'"./][^'"]*?)['"]|"""
        r"""require\(\s*['"]([^'"./][^'"]*?)['"]\s*\))"""
    )
    imported_packages = set()

    for root_dir, dirs, files in os.walk(project_path):
        dirs[:] = [d for d in dirs if d not in ("node_modules", ".next", ".git", "tests")]
        for fname in files:
            if fname.endswith((".js", ".jsx", ".ts", ".tsx", ".mjs")):
                fpath = os.path.join(root_dir, fname)
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        content = f.read()
                    for match in import_pattern.finditer(content):
                        pkg_name = match.group(1) or match.group(2)
                        # Scoped packages: @scope/name/sub → @scope/name
                        if pkg_name.startswith("@"):
                            # AENDERUNG 07.02.2026: Path-Aliases filtern (@/lib/utils ist kein npm-Package)
                            # ROOT-CAUSE-FIX: jsconfig.json Aliases (@/) wurden als Scoped Packages gemeldet
                            if pkg_name.startswith(("@/", "@\\")):
                                continue
                            parts = pkg_name.split("/")
                            if len(parts) >= 2:
                                pkg_name = f"{parts[0]}/{parts[1]}"
                        else:
                            # Unscoped: name/sub → name
                            pkg_name = pkg_name.split("/")[0]
                        imported_packages.add(pkg_name)
                except Exception:
                    pass

    # 3. Fehlende Packages ermitteln
    missing = []
    for pkg in sorted(imported_packages):
        # Node.js built-ins ueberspringen
        base_name = pkg.split("/")[0] if not pkg.startswith("@") else pkg
        if base_name in _NODE_BUILTINS:
            continue
        # Framework-Module ueberspringen (werden durch next/react bereitgestellt)
        if pkg in _FRAMEWORK_MODULES:
            continue
        # In package.json deklariert?
        if pkg in declared_deps:
            continue
        missing.append(pkg)

    if missing:
        result.issues.append(
            f"Fehlende Dependencies in package.json: {', '.join(missing)}. "
            "JEDES importierte Package MUSS in package.json dependencies stehen. "
            f"Fuege hinzu: {', '.join(missing)}"
        )
        result.is_critical_failure = True

    return result
