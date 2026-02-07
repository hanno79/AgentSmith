# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 31.01.2026
Version: 1.1
Beschreibung: Helper-Funktionen für DevLoop.
              Extrahiert aus dev_loop_steps.py (Regel 1: Max 500 Zeilen)
              Enthält: Error-Hashing, Truncation-Detection, Sandbox-Checks, Unicode-Sanitization
              AENDERUNG 01.02.2026: Dependency-Versions-Loader hinzugefügt
"""

import re
import ast
import json
import hashlib
from pathlib import Path
from typing import Dict, List, Tuple, Optional

from sandbox_runner import run_sandbox


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

    # AENDERUNG 06.02.2026: ROOT-CAUSE-FIX - JSX-Frameworks direkt an JSX-Validator
    # Symptom: "JavaScript-Syntaxfehler" bei jeder Next.js/React Iteration
    # Ursache: run_sandbox() -> node --check kann JSX-Syntax nicht parsen
    # Loesung: Bei bekannten JSX-Frameworks direkt _validate_jsx() aufrufen
    framework = tech_blueprint.get("framework", "").lower()
    jsx_frameworks = ["next.js", "nextjs", "react", "gatsby", "remix", "preact"]
    if any(fw in framework for fw in jsx_frameworks) or any(
        pt in project_type for pt in ["nextjs", "react", "gatsby", "remix"]
    ):
        from sandbox_runner import _validate_jsx
        return _validate_jsx(code)

    # JavaScript/TypeScript-Projekte: Original run_sandbox nutzen (erkennt JSX automatisch)
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


# =========================================================================
# AENDERUNG 01.02.2026: Dependency-Versions-Loader fuer Coder-Prompt
# =========================================================================

# Häufig verwendete Python-Pakete die in requirements.txt vorkommen
COMMON_PYTHON_PACKAGES = {
    # Web Frameworks
    "flask", "django", "fastapi", "starlette", "tornado", "bottle",
    # ORM/Database
    "sqlalchemy", "flask-sqlalchemy", "alembic", "psycopg2", "pymysql", "aiosqlite",
    # Dependencies von Flask/SQLAlchemy
    "werkzeug", "jinja2", "itsdangerous", "click", "markupsafe", "greenlet",
    # Testing
    "pytest", "pytest-cov", "coverage", "unittest2",
    # Utils
    "requests", "httpx", "aiohttp", "pydantic", "python-dotenv",
    # Security
    "bcrypt", "cryptography", "pyjwt",
}


def get_python_dependency_versions(
    dependencies_path: Optional[Path] = None,
    filter_common: bool = True
) -> str:
    """
    Liest aktuelle Python-Paket-Versionen aus library/dependencies.json
    und formatiert sie für den Coder-Prompt.

    AENDERUNG 01.02.2026: Verhindert dass LLM veraltete/falsche Versionen
    in requirements.txt generiert (z.B. greenlet==2.0.7 statt 3.2.3).

    Args:
        dependencies_path: Pfad zu dependencies.json (default: library/dependencies.json)
        filter_common: Wenn True, nur häufig verwendete Pakete zurückgeben

    Returns:
        Formatierter String mit Paket-Versionen für den Prompt, oder "" bei Fehler
    """
    if dependencies_path is None:
        dependencies_path = Path("library/dependencies.json")

    if not dependencies_path.exists():
        return ""

    try:
        with open(dependencies_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Extrahiere Python-Pakete mit Versionen
        python_section = data.get("python", {})
        packages = python_section.get("packages", [])

        if not packages:
            return ""

        versions = []
        for pkg in packages:
            name = pkg.get("name", "").lower()
            version = pkg.get("version", "")

            if not name or not version:
                continue

            # Filter: Nur häufig verwendete Pakete
            if filter_common and name not in COMMON_PYTHON_PACKAGES:
                continue

            # Format: name==version
            versions.append(f"{name}=={version}")

        if not versions:
            return ""

        # Sortieren für konsistente Ausgabe
        versions.sort()

        header = "AKTUELLE PAKET-VERSIONEN (verwende diese für requirements.txt!):"
        return header + "\n" + "\n".join(versions)

    except (json.JSONDecodeError, IOError, KeyError) as e:
        # Fehler still ignorieren - kein Crash wenn Datei fehlt/ungültig
        return ""


# =========================================================================
# AENDERUNG 02.02.2026: Automatische pytest-Integration fuer Docker-Tests
# =========================================================================

def _ensure_test_dependencies(requirements_content: str, project_files: list) -> str:
    """
    Fuegt pytest hinzu wenn Test-Dateien existieren aber pytest fehlt.

    AENDERUNG 02.02.2026: Fix #9 - Docker-Tests schlagen fehl mit
    "No module named pytest" weil der Coder test_*.py Dateien erstellt,
    aber pytest nicht in requirements.txt einfuegt.

    Args:
        requirements_content: Aktueller Inhalt der requirements.txt
        project_files: Liste der Dateien im Projekt

    Returns:
        Aktualisierter requirements.txt Inhalt mit pytest falls noetig
    """
    from logger_utils import log_event

    # Pruefe ob Test-Dateien existieren
    has_tests = any(
        "test_" in f or "_test.py" in f or f.startswith("tests/")
        for f in project_files
    )

    # Pruefe ob pytest bereits vorhanden ist
    has_pytest = "pytest" in requirements_content.lower()

    if has_tests and not has_pytest:
        log_event("DevLoop", "AutoFix", "pytest zu requirements.txt hinzugefuegt")
        return requirements_content.strip() + "\npytest>=8.0.0\n"

    return requirements_content
