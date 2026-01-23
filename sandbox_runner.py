import os
import ast

def detect_code_type(code: str) -> str:
    lower_code = code.lower()
    if "<html" in lower_code or "<!doctype" in lower_code:
        return "html"
    if "function" in code and "{" in code and "}" in code:
        return "js"
    return "python"


def run_sandbox(code: str) -> str:
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
            tmpfile = "sandbox_temp.js"
            with open(tmpfile, "w", encoding="utf-8") as f:
                f.write(code)
            # node --check validiert nur Syntax
            result = os.system(f"node --check {tmpfile} >nul 2>&1")
            os.remove(tmpfile)
            if result == 0:
                return "✅ JavaScript-Syntaxprüfung bestanden."
            else:
                return "❌ JavaScript-Syntaxfehler erkannt."

        else:
            return "⚠️ Unbekannter Code-Typ – keine Prüfung möglich."
    except SyntaxError as se:
        return f"❌ Syntaxfehler ({code_type}) in Zeile {se.lineno}:\n{str(se)}"
    except Exception as e:
        return f"❌ Fehler beim Prüfen ({code_type}):\n{str(e)}"
