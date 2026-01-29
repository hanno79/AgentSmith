# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 28.01.2026
Version: 1.1
Beschreibung: Sandbox Runner - Sichere Code-Validierung ohne Ausführung.
              Security Features: AST-Parsing, sichere Temp-Dateien, subprocess statt os.system.
              ÄNDERUNG 28.01.2026: validate_project_references() fuer Multi-File-Validierung hinzugefuegt.
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

CodeType = Literal["python", "html", "js"]


def detect_code_type(code: str) -> CodeType:
    """
    Erkennt den Code-Typ anhand von Indikatoren.

    Args:
        code: Der zu analysierende Code

    Returns:
        'html', 'js', oder 'python'
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
            return "js"
    return "python"


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
                    if parsed.scheme in ('http', 'https', 'data', 'blob', 'javascript') or src.startswith('//') or src.lower().startswith('javascript:'):
                        continue  # Externe URLs überspringen
                    ref_path = os.path.join(os.path.dirname(filepath), src)
                    if not os.path.exists(ref_path):
                        missing_refs.append(f"HTML '{filename}': Script '{src}' nicht gefunden")

                # CSS-Referenzen pruefen
                for match in re.finditer(r'<link[^>]+href=["\']([^"\']+\.css)["\']', content, re.IGNORECASE):
                    href = match.group(1)
                    # Prüfe auf absolute URLs mit urllib.parse
                    parsed = urlparse(href)
                    # ÄNDERUNG 29.01.2026: javascript:-URLs als externe Referenzen behandeln
                    if parsed.scheme in ('http', 'https', 'data', 'blob', 'javascript') or href.startswith('//') or href.lower().startswith('javascript:'):
                        continue  # Externe URLs überspringen
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
