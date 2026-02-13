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
# AENDERUNG 09.02.2026: Fix 36 — Zentrale Blacklist fuer verbotene Dateien
# ROOT-CAUSE-FIX:
# Symptom: package-lock.json wird generiert und gespeichert trotz Prompt-Verbot
# Ursache: Blacklist nur als Prompt-Text, kein System-Filter an Schreibstellen
# Loesung: Zentrale FORBIDDEN_FILES + is_forbidden_file() an allen Schreibstellen
# =========================================================================

FORBIDDEN_FILES = {
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "bun.lockb",
}

FORBIDDEN_DIRS = {
    "node_modules/",
    ".next/",
    "dist/",
    "build/",
    ".cache/",
    "__pycache__/",
}


def is_forbidden_file(filename: str) -> bool:
    """
    Prueft ob ein Dateiname auf der System-Blacklist steht.
    Zentrale Funktion fuer alle Schreibstellen in der Pipeline.

    Args:
        filename: Relativer Dateipfad (z.B. "package-lock.json" oder "node_modules/foo/bar.js")

    Returns:
        True wenn die Datei NICHT geschrieben werden darf
    """
    if not filename:
        return False
    normalized = filename.replace("\\", "/").strip("/")
    basename = normalized.split("/")[-1]

    # Exakter Dateiname-Match (case-insensitive)
    if basename.lower() in {f.lower() for f in FORBIDDEN_FILES}:
        return True

    # Verzeichnis-Praefix-Match
    for forbidden_dir in FORBIDDEN_DIRS:
        if normalized.lower().startswith(forbidden_dir.lower()):
            return True

    return False


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
# AENDERUNG 08.02.2026: Pro-Datei Validierung (Fix 31)
# =========================================================================


def _parse_code_to_files(code: str) -> dict:
    """
    Parst concatenierten Code-String (### FILENAME: ...) zu Dict {filename: content}.

    AENDERUNG 08.02.2026: Fix 31 — Pro-Datei Sandbox-Validierung
    ROOT-CAUSE-FIX:
    Symptom: "Nicht geschlossenes String-Literal (`)" in JEDER Iteration
    Ursache: _validate_jsx() bekommt ALLE Dateien als einen String, Backticks bluten ueber Dateigrenzen
    Loesung: Code an ### FILENAME: Markern aufteilen (gleiche Regex wie main.py:save_multi_file_output)

    Args:
        code: Concatenierter Code-String mit ### FILENAME: Markern

    Returns:
        Dict {filename: content} oder {} wenn kein Multi-File-Format erkannt
    """
    pattern = r"###\s*(?:FILENAME|FILE|PATH|DATEI|PFAD)?:?\s*(.+?):?\s*[\r\n]+"
    parts = re.split(pattern, code)
    if len(parts) < 3:
        return {}
    code_dict = {}
    for i in range(1, len(parts), 2):
        if i + 1 >= len(parts):
            break
        filename = parts[i].strip().rstrip(':')
        content = parts[i + 1].strip()
        # AENDERUNG 09.02.2026: Fix 36 — Blacklisted Dateien aus Code-Dict filtern
        if is_forbidden_file(filename):
            continue
        if filename and content:
            code_dict[filename] = content
    return code_dict


def _validate_files_individually(code_dict: dict, tech_blueprint: dict) -> str:
    """
    Validiert jede Datei separat und gibt Ergebnis MIT Dateinamen zurueck.

    AENDERUNG 08.02.2026: Fix 31 — Pro-Datei Sandbox-Validierung
    Jede Datei wird nach Extension validiert:
    - .py → AST-Parse
    - .jsx/.tsx (oder .js/.ts bei JSX-Frameworks) → _validate_jsx()
    - .js/.ts (ohne JSX-Framework) → run_sandbox()
    - .css → Klammerbalance
    - .json → JSON-Parse

    Args:
        code_dict: Dict {filename: content} aus _parse_code_to_files()
        tech_blueprint: Blueprint mit Projekt-Typ und Sprache

    Returns:
        Validierungsergebnis als String (✅ oder ❌) mit Dateinamen bei Fehlern
    """
    from sandbox_runner import _validate_jsx, _contains_jsx_syntax

    project_type = tech_blueprint.get("project_type", "").lower()
    framework = tech_blueprint.get("framework", "").lower()
    jsx_mode = any(fw in framework for fw in ["next.js", "nextjs", "react", "gatsby", "remix", "preact"]) or \
               any(pt in project_type for pt in ["nextjs", "react", "gatsby", "remix"])
    errors = []

    for filename, content in code_dict.items():
        ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''

        # Python
        if ext == 'py':
            try:
                ast.parse(content)
            except SyntaxError as se:
                errors.append(f"[{filename}] Python-Syntaxfehler Zeile {se.lineno}: {se.msg}")

        # AENDERUNG 13.02.2026: Fix 56a — Pure-JS in JSX-Frameworks nicht durch JSX-Validator
        # ROOT-CAUSE-FIX:
        # Symptom: validators.js "JSX-Strukturfehler" obwohl KEIN JSX enthalten
        # Ursache: jsx_mode=True routet ALLE .js zu _validate_jsx(), auch pure JS
        # Loesung: _contains_jsx_syntax() als Gate — nur echte JSX-Dateien validieren
        elif ext in ('jsx', 'tsx') or (ext in ('js', 'ts') and jsx_mode and _contains_jsx_syntax(content)):
            result = _validate_jsx(content)
            if result.startswith("❌"):
                errors.append(f"[{filename}] {result[2:].strip()}")

        # Reines JS (kein JSX-Framework)
        elif ext in ('js', 'ts'):
            result = run_sandbox(content)
            if result.startswith("❌"):
                errors.append(f"[{filename}] {result[2:].strip()}")

        # CSS — Klammerbalance pruefen
        elif ext == 'css':
            open_count = content.count('{')
            close_count = content.count('}')
            if open_count != close_count:
                errors.append(f"[{filename}] CSS: {open_count} oeffnende vs {close_count} schliessende Klammern")

        # JSON — Syntax pruefen
        elif ext == 'json':
            try:
                json.loads(content)
            except json.JSONDecodeError as je:
                errors.append(f"[{filename}] JSON-Fehler Zeile {je.lineno}: {je.msg}")

        # HTML, bat, config etc. — keine Pruefung noetig

    # AENDERUNG 09.02.2026: Dreifach-Schutz Content-Regeln (Fix 36 Audit)
    # Ausgelagert in dev_loop_content_rules.py (Regel 1: Max 500 Zeilen)
    from .dev_loop_content_rules import validate_content_rules
    warnings = validate_content_rules(code_dict, tech_blueprint)

    if errors:
        error_list = "\n".join(errors[:5])  # Max 5 Fehler
        warning_list = "\n".join(warnings[:3]) if warnings else ""
        result = f"❌ Validierungsfehler:\n{error_list}"
        if warning_list:
            result += f"\n⚠️ Content-Warnungen:\n{warning_list}"
        return result

    if warnings:
        warning_list = "\n".join(warnings[:5])
        return f"⚠️ Alle {len(code_dict)} Dateien syntaktisch OK, aber Content-Warnungen:\n{warning_list}"

    return f"✅ Alle {len(code_dict)} Dateien validiert (Pro-Datei-Pruefung)."


def run_sandbox_for_project(code: str, tech_blueprint: dict) -> str:
    """
    Führt Syntax-Check durch, berücksichtigt den Projekt-Typ aus dem Blueprint.

    WICHTIG: Bei Python-Projekten wird NUR Python-Syntax geprüft.
    JavaScript-Checks werden nur bei JavaScript-Projekten durchgeführt.

    AENDERUNG 08.02.2026: Pro-Datei Validierung (Fix 31)
    Bei Multi-File-Output (### FILENAME: Marker) wird jede Datei SEPARAT validiert.
    Dies verhindert Backtick-Bleed zwischen Dateien und gibt Fehler MIT Dateinamen zurueck.

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
        # AENDERUNG 08.02.2026: Auch Python-Projekte pro Datei validieren (Fix 31)
        code_dict = _parse_code_to_files(code)
        if code_dict:
            py_errors = []
            for filename, content in code_dict.items():
                if filename.endswith('.py'):
                    try:
                        ast.parse(content)
                    except SyntaxError as se:
                        py_errors.append(f"[{filename}] Python-Syntaxfehler Zeile {se.lineno}: {se.msg}")
            if py_errors:
                return f"❌ Validierungsfehler:\n" + "\n".join(py_errors[:5])
            return f"✅ Alle {len(code_dict)} Dateien validiert (Python AST)."

        # Fallback: Einzelner String
        try:
            ast.parse(code)
            return "✅ Python-Syntaxprüfung bestanden (AST)."
        except SyntaxError as se:
            return f"❌ Python-Syntaxfehler in Zeile {se.lineno}:\n{str(se)}"
        except Exception as e:
            return f"❌ Python-Prüfung fehlgeschlagen:\n{str(e)}"

    # AENDERUNG 08.02.2026: Pro-Datei Validierung (Fix 31)
    # ROOT-CAUSE-FIX:
    # Symptom: "Nicht geschlossenes String-Literal (`)" in JEDER Iteration
    # Ursache: _validate_jsx() bekommt ALLE Dateien als einen String, Backticks bluten
    # Loesung: Code in einzelne Dateien aufteilen, jede separat validieren
    code_dict = _parse_code_to_files(code)
    if code_dict:
        return _validate_files_individually(code_dict, tech_blueprint)

    # Fallback: Kein Multi-File-Format erkannt → bisheriges Verhalten
    # AENDERUNG 06.02.2026: ROOT-CAUSE-FIX - JSX-Frameworks direkt an JSX-Validator
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
# AENDERUNG 10.02.2026: Fix 48 — Truncation-Guard VOR Datei-Schreibung
# ROOT-CAUSE-FIX:
# Symptom: Abgeschnittene JS-Dateien werden auf Disk geschrieben (z.B. `import { cl;`)
# Ursache: _is_python_file_complete() prueft NUR .py-Dateien, JS/JSX wird ignoriert
# Loesung: validate_before_write() mit JS-Klammer-Balancierung + Schrumpf-Erkennung
# =========================================================================

def _is_js_file_complete(content: str) -> Tuple[bool, str]:
    """
    Prueft ob eine JS/JSX/TS-Datei strukturell vollstaendig ist.

    Checks:
    - Balancierte Klammern {}, [], ()
    - Ungeschlossene String-Literale
    - Abruptes Ende (endet mit offenem Konstrukt)

    Returns:
        Tuple (is_complete, reason)
    """
    if not content or not content.strip():
        return False, "Datei ist leer"

    # Entferne Kommentare und Strings fuer Klammer-Zaehlung
    # Einfach: Zaehle nur oeffnende/schliessende Klammern
    open_braces = content.count('{')
    close_braces = content.count('}')
    open_parens = content.count('(')
    close_parens = content.count(')')
    open_brackets = content.count('[')
    close_brackets = content.count(']')

    # Signifikante Imbalance = Truncation (kleine Diff koennte Template-Literal sein)
    brace_diff = open_braces - close_braces
    if brace_diff > 2:
        return False, f"Unbalancierte Klammern: {open_braces} oeffnend, {close_braces} schliessend (Diff: {brace_diff})"

    paren_diff = open_parens - close_parens
    if paren_diff > 2:
        return False, f"Unbalancierte Parenthesen: {open_parens} oeffnend, {close_parens} schliessend (Diff: {paren_diff})"

    bracket_diff = open_brackets - close_brackets
    if bracket_diff > 2:
        return False, f"Unbalancierte Brackets: {open_brackets} oeffnend, {close_brackets} schliessend (Diff: {bracket_diff})"

    # Pruefe auf abruptes Ende
    content_stripped = content.rstrip()
    truncation_endings = ('{', '(', '[', ',', ':', '=', '=>', '&&', '||', '+', 'import ', 'from ')
    if any(content_stripped.endswith(ending) for ending in truncation_endings):
        return False, f"Endet mit offenem Konstrukt: ...{content_stripped[-40:]}"

    # Pruefe auf abgeschnittenen Import (wie `import { cl;`)
    import_pattern = re.compile(r'import\s*\{[^}]*;\s*$', re.MULTILINE)
    if import_pattern.search(content):
        return False, "Abgeschnittener Import-Statement erkannt"

    return True, "Strukturell OK"


def validate_before_write(filename: str, content: str, old_content: str = None) -> Tuple[bool, str]:
    """
    Prueft ob Datei-Inhalt valide ist VOR dem Schreiben.
    Bei Truncation: Return (False, reason) → alte Version behalten.

    Prueft:
    - Python-Dateien: ast.parse() via _is_python_file_complete()
    - JS/JSX/TS-Dateien: Klammer-Balancierung via _is_js_file_complete()
    - Alle Dateien: Schrumpf-Erkennung (>70% kuerzer als Original)

    Returns: (is_valid, reason)
    """
    # Python-Check
    if filename.endswith('.py'):
        is_complete, reason = _is_python_file_complete(content, filename)
        if not is_complete:
            return False, f"Truncation erkannt: {reason}"

    # JS/JSX/TS-Check
    js_extensions = ('.js', '.jsx', '.ts', '.tsx', '.mjs')
    if any(filename.endswith(ext) for ext in js_extensions):
        is_complete, reason = _is_js_file_complete(content)
        if not is_complete:
            return False, f"Truncation erkannt: {reason}"

    # Schrumpf-Erkennung: Neuer Inhalt deutlich kuerzer als alter
    if old_content and len(old_content) > 50 and len(content) < len(old_content) * 0.3:
        shrink_pct = 100 - int(len(content) / len(old_content) * 100)
        return False, f"Inhalt um {shrink_pct}% geschrumpft ({len(content)} vs {len(old_content)} Zeichen)"

    return True, "OK"


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
# AENDERUNG 08.02.2026: Re-Exports aus dev_loop_dep_helpers.py (Regel 1 Refactoring)
# =========================================================================
from .dev_loop_dep_helpers import (  # noqa: F401
    COMMON_PYTHON_PACKAGES,
    get_python_dependency_versions,
    _ensure_test_dependencies
)


# AENDERUNG 09.02.2026: Re-Export aus dev_loop_content_rules.py (Regel 1 Refactoring)
from .dev_loop_content_rules import extract_filenames_from_feedback  # noqa: F401
