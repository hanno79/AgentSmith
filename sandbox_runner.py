# -*- coding: utf-8 -*-
"""
Sandbox Runner: Sichere Code-Validierung ohne Ausführung.
Verwendet AST-Parsing für Python und Syntax-Checks für JS/HTML.

Security Features:
- AST-Parsing für Python (keine Code-Ausführung)
- Sichere Temp-Dateien mit tempfile (Race Condition Prevention)
- subprocess statt os.system (sicherer)
"""

import os
import ast
import tempfile
import subprocess
from typing import Literal

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
    if "function" in code and "{" in code and "}" in code:
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
