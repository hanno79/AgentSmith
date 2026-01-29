# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 28.01.2026
Version: 1.0
Beschreibung: Content Validator - Erkennt leere Seiten, fehlende Inhalte und
              Tech-Stack-spezifische Rendering-Probleme.
              Wird von tester_agent.py nach dem Playwright-Screenshot aufgerufen.
"""

import os
import logging
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


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
                react_result = _check_react_content(page)
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


def _check_react_content(page) -> ContentValidationResult:
    """Prueft React-spezifische Rendering-Probleme."""
    result = ContentValidationResult()
    result.checks_performed.append("react_content")

    try:
        react_info = page.evaluate("""() => {
            const root = document.getElementById('root') || document.getElementById('app');
            if (!root) return { hasRoot: false };

            return {
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
            };
        }""")

        if not react_info.get("hasRoot"):
            result.issues.append(
                "Kein #root oder #app Container gefunden - "
                "React-App ist nicht korrekt eingebunden. "
                "Stelle sicher dass index.html ein <div id=\"root\"></div> enthaelt."
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

    # run_command vorhanden?
    run_cmd = tech_blueprint.get("run_command", "")
    if run_cmd and run_cmd.lower() not in bat_content:
        result.warnings.append(
            f"run.bat enthaelt nicht den Start-Befehl '{run_cmd}' - "
            "Anwendung wird moeglicherweise nicht gestartet"
        )

    result.has_visible_content = True  # run.bat hat Inhalt
    return result
