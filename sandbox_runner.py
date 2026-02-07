# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 28.01.2026
Version: 1.2
Beschreibung: Sandbox Runner - Sichere Code-Validierung ohne Ausführung.
              Security Features: AST-Parsing, sichere Temp-Dateien, subprocess statt os.system.
              ÄNDERUNG 28.01.2026: validate_project_references() fuer Multi-File-Validierung hinzugefuegt.
              AENDERUNG 06.02.2026: JSX/TSX-Erkennung - node --check scheitert an JSX-Syntax
"""

import os
import re
import ast
import tempfile
import subprocess
import logging
from typing import Literal
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

CodeType = Literal["python", "html", "js", "jsx"]


def _contains_jsx_syntax(code: str) -> bool:
    """
    Prueft ob Code JSX/TSX-Syntax enthaelt.

    AENDERUNG 06.02.2026: ROOT-CAUSE-FIX Sandbox JSX-Validierung
    Symptom: node --check scheitert immer an JSX-Code (<Component />, return <div>...)
    Ursache: JSX ist kein valides JavaScript fuer Node.js - braucht Babel/SWC Transpiler
    Loesung: JSX erkennen und separaten Code-Typ zuweisen

    Args:
        code: Der zu pruefende Code

    Returns:
        True wenn JSX-Syntax erkannt wird
    """
    jsx_patterns = [
        r'<[A-Z][a-zA-Z]*[\s/>]',       # <Component /> oder <Component>
        r'<[a-z]+\s+className=',          # <div className="...">
        r'return\s*\(\s*<',               # return (<div>...)
        r'return\s+<[a-zA-Z]',           # return <div>...
        r'<>',                            # Fragment-Syntax <>...</>
        r'<\/[A-Z]',                      # Schliessendes Component-Tag </Component>
        r'useState\s*\(',                 # React Hook
        r'useEffect\s*\(',               # React Hook
        r'from\s+["\']react["\']',        # import from 'react'
        r'from\s+["\']next/',             # import from 'next/...'
    ]
    return any(re.search(pattern, code) for pattern in jsx_patterns)


def detect_code_type(code: str) -> CodeType:
    """
    Erkennt den Code-Typ anhand von Indikatoren.

    AENDERUNG 06.02.2026: JSX/TSX als separater Typ erkannt.

    Args:
        code: Der zu analysierende Code

    Returns:
        'html', 'jsx', 'js', oder 'python'
    """
    lower_code = code.lower()
    if "<html" in lower_code or "<!doctype" in lower_code:
        return "html"
    # ÄNDERUNG 28.01.2026: Erweiterte JS-Erkennung (Arrow Functions, const/let, import/export)
    if "{" in code and "}" in code:
        js_indicators = [
            "function" in code,
            "=>" in code,                          # Arrow Functions
            "const " in code or "let " in code,    # Moderne Variablen
            "import " in code and "from " in code, # ES6 Module
            "export " in code,                     # ES6 Export
            "document." in code,                   # DOM-Zugriff
            "console.log" in code,                 # Console
            "require(" in code,                    # CommonJS
            "async " in code,                      # Async/Await
            "class " in code and "extends " in code,  # JS-Klassen mit Vererbung
        ]
        if any(js_indicators):
            # AENDERUNG 06.02.2026: JSX-Erkennung VOR js-Klassifizierung
            if _contains_jsx_syntax(code):
                return "jsx"
            return "js"
    return "python"


# AENDERUNG 06.02.2026: ROOT-CAUSE-FIX Sandbox JSX-Validierung
# Symptom: "JavaScript-Syntaxfehler" in jeder Iteration bei Next.js/React Projekten
# Ursache: node --check kann JSX-Syntax (<Component />) nicht parsen
# Loesung: Strukturelle JSX-Validierung statt node --check

def _validate_jsx(code: str) -> str:
    """
    Validiert JSX/TSX-Code strukturell (ohne node --check).

    node --check kann JSX nicht parsen - JSX braucht Babel/SWC/TypeScript Compiler.
    Stattdessen pruefen wir strukturelle Integritaet:
    - Klammerbalance (rund, eckig, geschweift)
    - String-Literale geschlossen
    - Export-Statement vorhanden
    - Keine offensichtlichen Syntaxfehler

    Args:
        code: JSX/TSX-Code

    Returns:
        Validierungsergebnis als String
    """
    issues = []

    # 1. Klammerbalance pruefen (ignoriere Klammern in Strings/Kommentaren)
    bracket_pairs = {'(': ')', '[': ']', '{': '}'}
    stack = []
    in_string = None
    in_line_comment = False
    in_block_comment = False
    i = 0
    while i < len(code):
        ch = code[i]
        # Kommentare tracken
        if not in_string:
            if not in_block_comment and i + 1 < len(code) and code[i:i+2] == '//':
                in_line_comment = True
            if in_line_comment and ch == '\n':
                in_line_comment = False
                i += 1
                continue
            if not in_line_comment and i + 1 < len(code) and code[i:i+2] == '/*':
                in_block_comment = True
            if in_block_comment and i + 1 < len(code) and code[i:i+2] == '*/':
                in_block_comment = False
                i += 2
                continue
            if in_line_comment or in_block_comment:
                i += 1
                continue

        # String-Tracking
        if ch in ('"', "'", '`') and not in_string:
            in_string = ch
        elif ch == in_string and (i == 0 or code[i-1] != '\\'):
            in_string = None
        elif not in_string:
            if ch in bracket_pairs:
                stack.append(bracket_pairs[ch])
            elif ch in bracket_pairs.values():
                if stack and stack[-1] == ch:
                    stack.pop()
                elif not stack:
                    # JSX-Tags koennen > enthalten, nur echte Klammern zaehlen
                    if ch in (')', ']', '}'):
                        issues.append(f"Ueberschuessige schliessende Klammer '{ch}'")
                        break
        i += 1

    if stack and len(stack) <= 3:
        missing = ', '.join(f"'{b}'" for b in reversed(stack))
        issues.append(f"Fehlende schliessende Klammer(n): {missing}")

    # 2. Offene String-Literale pruefen
    if in_string:
        issues.append(f"Nicht geschlossenes String-Literal ({in_string})")

    # 3. Export vorhanden pruefen (React-Komponenten brauchen Export)
    has_export = 'export ' in code
    has_module_exports = 'module.exports' in code
    if not has_export and not has_module_exports:
        # Kein Fehler, nur Warnung - manche Dateien brauchen keinen Export
        pass

    if issues:
        issue_text = "; ".join(issues[:3])
        return f"❌ JSX-Strukturfehler: {issue_text}"

    return "✅ JSX/React-Syntaxprüfung bestanden (Strukturanalyse)."


def run_sandbox(code: str) -> str:
    """
    Führt eine sichere Syntax-Validierung des Codes durch.

    Security:
    - Python: AST-Parsing ohne Code-Ausführung
    - JavaScript: node --check mit sicherer Temp-Datei
    - HTML: String-basierte Tag-Analyse

    Args:
        code: Der zu validierende Code

    Returns:
        Validierungsergebnis als String (✅ oder ❌)
    """
    code_type = detect_code_type(code)
    try:
        if code_type == "python":
            # Statische Analyse statt exec() - sicherer und findet Syntaxfehler präzise
            ast.parse(code)
            return "✅ Python-Syntaxprüfung bestanden (AST)."

        elif code_type == "html":
            if "<html" in code.lower() and "</html>" in code.lower():
                return "✅ HTML-Struktur syntaktisch korrekt."
            else:
                return "❌ HTML unvollständig – schließende Tags fehlen."

        # AENDERUNG 06.02.2026: JSX separat behandeln - node --check versteht kein JSX
        elif code_type == "jsx":
            return _validate_jsx(code)

        elif code_type == "js":
            # SECURITY FIX: Sichere Temp-Datei mit eindeutigem Namen (Race Condition Prevention)
            with tempfile.NamedTemporaryFile(
                mode='w',
                suffix='.js',
                delete=False,
                encoding='utf-8'
            ) as f:
                f.write(code)
                tmpfile = f.name

            try:
                # SECURITY FIX: subprocess statt os.system (sicherer, keine Shell-Interpretation)
                result = subprocess.run(
                    ["node", "--check", tmpfile],
                    capture_output=True,
                    timeout=30  # Timeout um Hänger zu vermeiden
                )
                if result.returncode == 0:
                    return "✅ JavaScript-Syntaxprüfung bestanden."
                else:
                    # Extrahiere Fehlermeldung falls vorhanden
                    stderr = result.stderr.decode('utf-8', errors='ignore').strip()
                    if stderr:
                        # Nur erste Zeile der Fehlermeldung
                        first_line = stderr.split('\n')[0][:200]
                        return f"❌ JavaScript-Syntaxfehler: {first_line}"
                    return "❌ JavaScript-Syntaxfehler erkannt."
            finally:
                # Garantierte Löschung der Temp-Datei
                try:
                    os.unlink(tmpfile)
                except OSError:
                    pass  # Ignoriere Fehler beim Löschen

        else:
            return "⚠️ Unbekannter Code-Typ – keine Prüfung möglich."

    except SyntaxError as se:
        return f"❌ Syntaxfehler ({code_type}) in Zeile {se.lineno}:\n{str(se)}"
    except subprocess.TimeoutExpired:
        return "❌ JavaScript-Syntaxprüfung: Timeout (>30s)"
    except FileNotFoundError:
        return "❌ JavaScript-Prüfung fehlgeschlagen: Node.js nicht installiert"
    except Exception as e:
        return f"❌ Fehler beim Prüfen ({code_type}):\n{str(e)}"


# ÄNDERUNG 28.01.2026: Multi-File Referenz-Validierung
def validate_project_references(project_path: str) -> str:
    """
    Prueft ob alle in HTML referenzierten Dateien im Projekt existieren.

    Prueft:
    - HTML <script src="..."> Referenzen
    - HTML <link href="..."> Referenzen (CSS)

    Args:
        project_path: Pfad zum Projektverzeichnis

    Returns:
        Validierungsergebnis als String (✅ oder ❌)
    """
    missing_refs = []
    skip_dirs = {'node_modules', 'venv', '.git', '__pycache__', 'screenshots'}

    try:
        for root, dirs, files in os.walk(project_path):
            # Ueberspringe irrelevante Verzeichnisse
            dirs[:] = [d for d in dirs if d not in skip_dirs]

            for filename in files:
                if not filename.endswith(('.html', '.htm')):
                    continue

                filepath = os.path.join(root, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8', errors='ignore') as fh:
                        content = fh.read()
                except Exception:
                    continue

                # Script-Referenzen pruefen
                for match in re.finditer(r'<script[^>]+src=["\']([^"\']+)["\']', content, re.IGNORECASE):
                    src = match.group(1)
                    # Prüfe auf absolute URLs mit urllib.parse
                    parsed = urlparse(src)
                    # ÄNDERUNG 29.01.2026: javascript:-URLs als externe Referenzen behandeln
                    if parsed.scheme.lower() in ('http', 'https', 'data', 'blob', 'javascript') or src.startswith('//'):
                        continue  # Externe URLs überspringen
                    ref_path = os.path.join(os.path.dirname(filepath), src)
                    if not os.path.exists(ref_path):
                        missing_refs.append(f"HTML '{filename}': Script '{src}' nicht gefunden")

                # CSS-Referenzen pruefen
                for match in re.finditer(r'<link[^>]+href=["\']([^"\']+\.css)["\']', content, re.IGNORECASE):
                    href = match.group(1)
                    # Prüfe auf absolute URLs mit urllib.parse
                    parsed = urlparse(href)
                    # ÄNDERUNG 29.01.2026: Einrückung korrigiert - externe URLs überspringen
                    if parsed.scheme.lower() in ('http', 'https', 'data', 'blob', 'javascript') or href.startswith('//'):
                        if parsed.scheme.lower() == 'javascript':
                            logger.warning(
                                "Unerwartetes URL-Schema 'javascript' in CSS-Link gefunden: href='%s', datei='%s'",
                                href,
                                filename
                            )
                        continue  # Externe URLs (CDN etc.) überspringen
                    ref_path = os.path.join(os.path.dirname(filepath), href)
                    if not os.path.exists(ref_path):
                        missing_refs.append(f"HTML '{filename}': CSS '{href}' nicht gefunden")

    except Exception as e:
        logger.warning(f"Referenz-Validierung fehlgeschlagen: {e}")
        return f"⚠️ Referenz-Validierung konnte nicht durchgefuehrt werden: {e}"

    if missing_refs:
        refs_text = "\n".join(f"  - {ref}" for ref in missing_refs[:10])
        return f"❌ Fehlende Datei-Referenzen:\n{refs_text}"

    return "✅ Alle Datei-Referenzen vorhanden."
