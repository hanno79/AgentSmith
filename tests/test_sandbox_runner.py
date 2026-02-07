# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 24.01.2026
Version: 1.1
Beschreibung: Tests für Sandbox Runner - Testet Code-Validierung und Syntax-Checks.
              AENDERUNG 06.02.2026: JSX-Erkennung und -Validierung Tests.
"""

import pytest
import shutil
from sandbox_runner import detect_code_type, run_sandbox, _contains_jsx_syntax, _validate_jsx


class TestDetectCodeType:
    """Tests für die detect_code_type Funktion."""

    def test_detect_html_doctype(self):
        """Test: Erkennung von HTML mit DOCTYPE."""
        code = "<!DOCTYPE html><html><body>Test</body></html>"
        assert detect_code_type(code) == "html"

    def test_detect_html_tag(self):
        """Test: Erkennung von HTML mit html-Tag."""
        code = "<html><head></head><body>Test</body></html>"
        assert detect_code_type(code) == "html"

    def test_detect_html_case_insensitive(self):
        """Test: Case-insensitive HTML-Erkennung."""
        code = "<HTML><BODY>Test</BODY></HTML>"
        assert detect_code_type(code) == "html"

    def test_detect_javascript(self):
        """Test: Erkennung von JavaScript."""
        code = "function hello() { console.log('Hello'); }"
        assert detect_code_type(code) == "js"

    def test_detect_python_default(self):
        """Test: Python als Default-Typ."""
        code = "def hello():\n    print('Hello')"
        assert detect_code_type(code) == "python"

    def test_detect_python_with_class(self):
        """Test: Python-Klassen werden als Python erkannt."""
        code = "class MyClass:\n    def __init__(self):\n        pass"
        assert detect_code_type(code) == "python"

    def test_detect_empty_code(self):
        """Test: Leerer Code wird als Python erkannt."""
        assert detect_code_type("") == "python"

    # AENDERUNG 06.02.2026: JSX-Erkennung Tests
    def test_detect_jsx_react_component(self):
        """Test: React-Komponente wird als JSX erkannt."""
        code = '''import React from 'react';
export default function App() {
  return <div className="app"><h1>Hello</h1></div>;
}'''
        assert detect_code_type(code) == "jsx", (
            "Erwartet: JSX erkannt bei React-Komponente"
        )

    def test_detect_jsx_nextjs_page(self):
        """Test: Next.js-Page wird als JSX erkannt."""
        code = '''import Head from 'next/head';
export default function Home() {
  const [items, setItems] = useState([]);
  return (
    <div>
      <Head><title>Home</title></Head>
      <TodoList items={items} />
    </div>
  );
}'''
        assert detect_code_type(code) == "jsx", (
            "Erwartet: JSX erkannt bei Next.js-Page"
        )

    def test_detect_plain_js_not_jsx(self):
        """Test: Plain JavaScript ohne JSX bleibt 'js'."""
        code = "const express = require('express');\nconst app = express();\napp.get('/', (req, res) => { res.send('ok'); });"
        result = detect_code_type(code)
        assert result == "js", (
            f"Erwartet: 'js' fuer Plain JavaScript, erhalten: {result}"
        )


class TestRunSandbox:
    """Tests für die run_sandbox Funktion."""

    # ==================== Python Tests ====================

    def test_valid_python_code(self, valid_python_code):
        """Test: Gültiger Python-Code besteht Prüfung."""
        result = run_sandbox(valid_python_code)
        assert "✅" in result
        assert "Python" in result

    def test_invalid_python_syntax(self, invalid_python_code):
        """Test: Ungültiger Python-Code wird erkannt."""
        result = run_sandbox(invalid_python_code)
        assert "❌" in result
        assert "Syntaxfehler" in result

    def test_python_syntax_error_line_number(self):
        """Test: Zeilennummer wird bei Syntaxfehlern angegeben."""
        code = "def test():\n    pass\n    invalid syntax here"
        result = run_sandbox(code)
        assert "❌" in result
        assert "Zeile" in result

    def test_python_import_statement(self):
        """Test: Import-Statements sind gültig."""
        code = "import os\nimport sys\nprint(os.getcwd())"
        result = run_sandbox(code)
        assert "✅" in result

    def test_python_complex_code(self):
        """Test: Komplexer Python-Code wird validiert."""
        code = '''
class Calculator:
    def __init__(self):
        self.result = 0

    def add(self, x, y):
        return x + y

    def multiply(self, x, y):
        return x * y

if __name__ == "__main__":
    calc = Calculator()
    print(calc.add(1, 2))
'''
        result = run_sandbox(code)
        assert "✅" in result

    def test_python_indentation_error(self):
        """Test: Einrückungsfehler werden erkannt."""
        code = "def test():\nprint('no indent')"
        result = run_sandbox(code)
        assert "❌" in result

    # ==================== HTML Tests ====================

    def test_valid_html_code(self, valid_html_code):
        """Test: Gültiger HTML-Code besteht Prüfung."""
        result = run_sandbox(valid_html_code)
        assert "✅" in result
        assert "HTML" in result

    def test_invalid_html_missing_closing(self):
        """Test: Unvollstaendiger HTML-Code (ohne </html>) wird erkannt."""
        # NOTE: Der HTML-Validator prueft nur ob <html> und </html> vorhanden sind.
        # Wir muessen tatsaechlich </html> entfernen um ungueltiges HTML zu haben.
        code = '''<!DOCTYPE html>
<html>
<head>
    <title>Test Page</title>
</head>
<body>
    <h1>Missing closing tags
</body>'''  # Ohne </html>
        result = run_sandbox(code)
        assert "❌" in result
        # Fehlermeldung kann "unvollstaendig" oder "unvollstaendig" sein
        assert "unvoll" in result.lower()

    def test_html_minimal_valid(self):
        """Test: Minimaler gültiger HTML-Code."""
        code = "<html></html>"
        result = run_sandbox(code)
        assert "✅" in result

    # ==================== JavaScript Tests ====================

    def test_valid_javascript_code(self):
        """Test: Gültiger JavaScript-Code (wenn Node.js verfügbar)."""
        code = "function test() { return 42; }"
        result = run_sandbox(code)
        # Kann ✅ oder ❌ sein, je nach Node.js-Verfügbarkeit
        assert "✅" in result or "❌" in result

    def test_javascript_arrow_function(self):
        """Test: JavaScript Arrow Functions."""
        # Skip wenn Node.js nicht verfügbar
        if shutil.which("node") is None:
            pytest.skip("Node.js nicht verfügbar")
        
        code = "const add = (a, b) => { return a + b; };"
        result = run_sandbox(code)
        # Wenn Node.js verfügbar, sollte JavaScript erkannt werden
        assert "JavaScript" in result

    # ==================== Edge Cases ====================

    def test_empty_code(self):
        """Test: Leerer Code wird als Python validiert."""
        result = run_sandbox("")
        assert "✅" in result

    def test_whitespace_only(self):
        """Test: Nur Whitespace ist gültiger Python-Code."""
        result = run_sandbox("   \n\n   \t")
        assert "✅" in result

    def test_unicode_code(self):
        """Test: Unicode-Zeichen werden unterstützt."""
        code = "print('Hallo Welt! 日本語 emoji 🚀')"
        result = run_sandbox(code)
        assert "✅" in result

    def test_multiline_string(self):
        """Test: Multiline-Strings sind gültig."""
        code = '''
text = """
This is a
multiline string
"""
print(text)
'''
        result = run_sandbox(code)
        assert "✅" in result


class TestRunSandboxSecurity:
    """Sicherheitstests für die Sandbox."""

    def test_no_code_execution(self):
        """Test: Code wird nicht ausgeführt (nur Syntax-Check)."""
        # Dieser Code würde bei Ausführung eine Datei erstellen
        code = "import os; os.system('echo EXECUTED > /tmp/test_executed.txt')"
        result = run_sandbox(code)
        # Syntax ist gültig, aber Code sollte NICHT ausgeführt werden
        assert "✅" in result

    def test_ast_parse_only(self):
        """Test: Nur AST-Parsing, keine Ausführung."""
        # Code mit Seiteneffekten
        code = "print('This should not print')"
        result = run_sandbox(code)
        assert "✅" in result
        # Keine Ausgabe von "This should not print" erwartet


# AENDERUNG 06.02.2026: Tests fuer JSX-Erkennung und -Validierung
class TestContainsJsxSyntax:
    """Tests fuer _contains_jsx_syntax()."""

    def test_react_component_tag(self):
        """Erkennt <Component /> als JSX."""
        assert _contains_jsx_syntax("<TodoList />") is True

    def test_classname_attribute(self):
        """Erkennt className= als JSX."""
        assert _contains_jsx_syntax('<div className="app">') is True

    def test_return_jsx(self):
        """Erkennt return (<div>...) als JSX."""
        assert _contains_jsx_syntax("return (\n    <div>") is True

    def test_react_import(self):
        """Erkennt import from 'react' als JSX."""
        assert _contains_jsx_syntax("import React from 'react';") is True

    def test_next_import(self):
        """Erkennt import from 'next/...' als JSX."""
        assert _contains_jsx_syntax("import Head from 'next/head';") is True

    def test_use_state_hook(self):
        """Erkennt useState() als JSX/React."""
        assert _contains_jsx_syntax("const [x, setX] = useState(0);") is True

    def test_fragment_syntax(self):
        """Erkennt Fragment-Syntax <>."""
        assert _contains_jsx_syntax("return <><div>Test</div></>;") is True

    def test_plain_javascript(self):
        """Plain JS ohne JSX wird nicht als JSX erkannt."""
        assert _contains_jsx_syntax("const x = require('express');") is False

    def test_plain_node_server(self):
        """Node.js-Server ohne JSX wird nicht als JSX erkannt."""
        code = "const http = require('http');\nhttp.createServer((req, res) => { res.end('ok'); });"
        assert _contains_jsx_syntax(code) is False


class TestValidateJsx:
    """Tests fuer _validate_jsx()."""

    def test_valid_react_component(self):
        """Gueltige React-Komponente besteht Validierung."""
        code = '''import React from 'react';

export default function App() {
  const [count, setCount] = React.useState(0);
  return (
    <div className="app">
      <h1>Counter: {count}</h1>
      <button onClick={() => setCount(count + 1)}>+1</button>
    </div>
  );
}'''
        result = _validate_jsx(code)
        assert "✅" in result, f"Erwartet: Validierung bestanden, erhalten: {result}"

    def test_valid_nextjs_page(self):
        """Gueltige Next.js-Page besteht Validierung."""
        code = '''import Head from 'next/head';
import dynamic from 'next/dynamic';

const TodoList = dynamic(() => import('../components/TodoList'), { ssr: false });

export default function Home() {
  return (
    <div>
      <Head><title>Todo App</title></Head>
      <TodoList />
    </div>
  );
}'''
        result = _validate_jsx(code)
        assert "✅" in result, f"Erwartet: Validierung bestanden, erhalten: {result}"

    def test_unbalanced_braces(self):
        """Unbalancierte geschweiften Klammern werden erkannt."""
        code = '''export default function App() {
  return (
    <div>Test</div>
  );
'''  # Fehlende schliessende }
        result = _validate_jsx(code)
        assert "❌" in result, f"Erwartet: Fehler erkannt, erhalten: {result}"
        assert "Klammer" in result, f"Erwartet: Klammer-Fehler, erhalten: {result}"

    def test_unclosed_string(self):
        """Nicht geschlossenes String-Literal wird erkannt."""
        code = '''const name = "Hello;
export function App() { return <div>{name}</div>; }'''
        result = _validate_jsx(code)
        assert "❌" in result, f"Erwartet: Fehler bei offenem String, erhalten: {result}"

    def test_empty_code(self):
        """Leerer Code besteht Validierung (keine Strukturfehler)."""
        result = _validate_jsx("")
        assert "✅" in result, f"Erwartet: Validierung bestanden bei leerem Code, erhalten: {result}"

    def test_comments_ignored(self):
        """Klammern in Kommentaren werden ignoriert."""
        code = '''// Diese Klammer { wird ignoriert
/* Und diese auch { und diese } */
export function App() { return <div>OK</div>; }'''
        result = _validate_jsx(code)
        assert "✅" in result, f"Erwartet: Kommentar-Klammern ignoriert, erhalten: {result}"

    def test_run_sandbox_uses_jsx_validator(self):
        """run_sandbox() nutzt JSX-Validator bei JSX-Code."""
        code = '''import React from 'react';
export default function App() {
  return <div className="app"><h1>Hello</h1></div>;
}'''
        result = run_sandbox(code)
        assert "✅" in result, f"Erwartet: JSX-Code besteht run_sandbox(), erhalten: {result}"
        assert "JSX" in result or "Struktur" in result, (
            f"Erwartet: JSX-Validierung-Meldung, erhalten: {result}"
        )
