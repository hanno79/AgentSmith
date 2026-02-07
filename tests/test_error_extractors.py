# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 06.02.2026
Version: 1.0
Beschreibung: Unit Tests fuer error_extractors.py - Extraktor-Methoden fuer
              verschiedene Fehlertypen (Syntax, Import, Runtime, JS, Tests,
              Truncation, pip/Docker, zirkulaere Imports, Config, Constraints).
"""

import pytest
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.error_extractors import (
    extract_python_syntax_errors,
    extract_python_import_errors,
    extract_python_runtime_errors,
    extract_javascript_errors,
    extract_test_failures,
    extract_truncation_errors,
    extract_pip_dependency_errors,
    _find_requirements_file,
    analyze_docker_error,
    extract_circular_import_errors,
    extract_config_errors,
    detect_environment_constraints,
)


# =========================================================================
# Test: extract_python_syntax_errors
# =========================================================================

class TestExtractPythonSyntaxErrors:
    """Tests fuer Python Syntax-Fehler Extraktion."""

    def test_standard_syntax_error_pattern(self):
        """Standard Python SyntaxError-Format wird korrekt erkannt."""
        project_files = {
            "app.py": "import os\nprint('hello')\nx = \n",
        }
        # PYTHON_SYNTAX_ERROR_PATTERN: File "path", line N\n(eine Zeile)\n...SyntaxError: msg
        # Pattern erwartet genau eine Zeile zwischen File-Zeile und SyntaxError
        output = 'File "app.py", line 3\n    x = \nSyntaxError: invalid syntax'
        result = extract_python_syntax_errors(output, project_files)
        assert len(result) >= 1, "Erwartet: mindestens 1 Fehler, Erhalten: 0"
        fehler = result[0]
        assert fehler.file_path == "app.py"
        assert fehler.error_type == "syntax"
        assert 3 in fehler.line_numbers
        assert "SyntaxError" in fehler.error_message
        assert fehler.severity == "error"

    def test_leerer_output_gibt_leere_liste(self):
        """Leerer Output gibt keine Fehler zurueck."""
        project_files = {"app.py": "print('ok')\n"}
        result = extract_python_syntax_errors("", project_files)
        assert result == [], "Erwartet: leere Liste bei leerem Output"

    def test_deutsches_syntax_fehler_format(self):
        """Deutsches Format 'Python-Syntaxfehler in Zeile X' wird erkannt."""
        # Datei mit echtem Syntax-Fehler damit find_file_with_syntax_error sie findet
        project_files = {
            "rechner.py": "def add(a, b):\n    return a +\n",
        }
        output = "Python-Syntaxfehler in Zeile 2: unexpected EOF while parsing"
        result = extract_python_syntax_errors(output, project_files)
        # find_file_with_syntax_error nutzt AST-Parsing -> findet rechner.py
        assert len(result) >= 1, "Erwartet: mindestens 1 Fehler beim deutschen Format"
        assert result[0].error_type == "syntax"
        assert 2 in result[0].line_numbers
        assert "SyntaxError" in result[0].error_message


# =========================================================================
# Test: extract_python_import_errors
# =========================================================================

class TestExtractPythonImportErrors:
    """Tests fuer Python Import-Fehler Extraktion."""

    def test_module_not_found_mit_traceback(self):
        """ModuleNotFoundError mit Traceback-Kontext wird erkannt."""
        project_files = {
            "app.py": "import flask\napp = flask.Flask(__name__)\n",
        }
        output = (
            'Traceback (most recent call last):\n'
            '  File "app.py", line 1, in <module>\n'
            '    import flask\n'
            'ModuleNotFoundError: No module named \'flask\''
        )
        result = extract_python_import_errors(output, project_files)
        assert len(result) >= 1, "Erwartet: mindestens 1 Import-Fehler"
        fehler = result[0]
        assert fehler.file_path == "app.py"
        assert fehler.error_type == "import"
        assert "ModuleNotFoundError" in fehler.error_message
        assert fehler.severity == "error"

    def test_import_error_erkannt(self):
        """ImportError wird korrekt erkannt."""
        project_files = {
            "utils.py": "from collections import NonExistent\n",
        }
        output = (
            'Traceback (most recent call last):\n'
            '  File "utils.py", line 1, in <module>\n'
            '    from collections import NonExistent\n'
            'ImportError: cannot import name \'NonExistent\''
        )
        result = extract_python_import_errors(output, project_files)
        assert len(result) >= 1, "Erwartet: mindestens 1 ImportError"
        assert "ImportError" in result[0].error_message

    def test_kein_import_fehler_bei_normalem_output(self):
        """Normaler Output ohne Import-Fehler gibt leere Liste."""
        project_files = {"app.py": "print('ok')\n"}
        output = "Alles in Ordnung, keine Fehler gefunden."
        result = extract_python_import_errors(output, project_files)
        assert result == [], "Erwartet: leere Liste bei normalem Output"


# =========================================================================
# Test: extract_python_runtime_errors
# =========================================================================

class TestExtractPythonRuntimeErrors:
    """Tests fuer Python Runtime-Fehler Extraktion."""

    def test_name_error_traceback(self):
        """NameError aus Traceback wird korrekt extrahiert."""
        project_files = {
            "main.py": "def run():\n    print(undeclared_var)\n",
        }
        output = (
            'Traceback (most recent call last):\n'
            '  File "main.py", line 2, in run\n'
            '    print(undeclared_var)\n'
            "NameError: name 'undeclared_var' is not defined"
        )
        result = extract_python_runtime_errors(output, project_files)
        assert len(result) >= 1, "Erwartet: mindestens 1 Runtime-Fehler"
        fehler = result[0]
        assert fehler.file_path == "main.py"
        assert fehler.error_type == "runtime"
        assert 2 in fehler.line_numbers
        assert "NameError" in fehler.error_message

    def test_duplikate_werden_gefiltert(self):
        """Gleiche Datei wird nicht mehrfach erfasst (Dedup via seen_files)."""
        project_files = {
            "api.py": "import json\ndef get(): pass\ndef post(): pass\n",
        }
        output = (
            'Traceback (most recent call last):\n'
            '  File "api.py", line 2, in get\n'
            '    result = data["key"]\n'
            '  File "api.py", line 3, in post\n'
            '    result = data["other"]\n'
            'KeyError: \'key\''
        )
        result = extract_python_runtime_errors(output, project_files)
        # Gleiche Datei darf nur einmal vorkommen (seen_files Set)
        datei_pfade = [e.file_path for e in result]
        assert datei_pfade.count("api.py") == 1, "Erwartet: api.py nur einmal (Deduplizierung)"

    def test_kein_runtime_fehler_bei_leerem_output(self):
        """Leerer Output gibt keine Runtime-Fehler."""
        project_files = {"app.py": "print('ok')\n"}
        result = extract_python_runtime_errors("", project_files)
        assert result == [], "Erwartet: leere Liste bei leerem Output"


# =========================================================================
# Test: extract_javascript_errors
# =========================================================================

class TestExtractJavascriptErrors:
    """Tests fuer JavaScript/TypeScript-Fehler Extraktion."""

    def test_js_error_wird_erkannt(self):
        """JavaScript-Fehler im Format datei.js:zeile:spalte Error wird erkannt."""
        project_files = {
            "app.js": "const x = 1;\nconsole.log(x);\n",
        }
        # JAVASCRIPT_ERROR_PATTERN: ([\w/\\.-]+\.[jt]sx?):(\d+):(\d+).*?(?:error|Error)
        output = "app.js:2:5 TypeError: undefined is not a function\n"
        result = extract_javascript_errors(output, project_files)
        assert len(result) >= 1, "Erwartet: mindestens 1 JS-Fehler"
        fehler = result[0]
        assert fehler.file_path == "app.js"
        assert 2 in fehler.line_numbers
        assert fehler.severity == "error"

    def test_kein_js_fehler_bei_normalem_output(self):
        """Normaler Output ohne JS-Fehler gibt leere Liste."""
        project_files = {"app.js": "console.log('ok');\n"}
        output = "Build successful, no errors."
        result = extract_javascript_errors(output, project_files)
        assert result == [], "Erwartet: leere Liste bei normalem Output"


# =========================================================================
# Test: extract_test_failures
# =========================================================================

class TestExtractTestFailures:
    """Tests fuer Test-Fehler Extraktion."""

    def test_failed_test_wird_erkannt(self):
        """FAILED Test-Pattern wird korrekt erkannt."""
        project_files = {
            "test_api.py": "def test_login(): assert True\n",
        }
        # TEST_FAILURE_PATTERN: (FAILED|FAIL|ERROR)\s+([^\s:]+)(?:::|:)\s*(.+)?
        output = "FAILED test_api.py::test_login: AssertionError: 5 != 3"
        result = extract_test_failures(output, project_files)
        assert len(result) >= 1, "Erwartet: mindestens 1 Test-Fehler"
        fehler = result[0]
        assert fehler.file_path == "test_api.py"
        assert fehler.error_type == "test"
        assert "FAILED" in fehler.error_message

    def test_kein_test_fehler_bei_erfolg(self):
        """Erfolgreicher Testlauf gibt keine Fehler."""
        project_files = {"test_api.py": "def test_ok(): pass\n"}
        output = "===== 5 passed in 0.3s ====="
        result = extract_test_failures(output, project_files)
        assert result == [], "Erwartet: leere Liste bei erfolgreichem Testlauf"


# =========================================================================
# Test: extract_truncation_errors
# =========================================================================

class TestExtractTruncationErrors:
    """Tests fuer Truncation-Fehler Erkennung."""

    def test_truncation_schluesselwort_erkannt(self):
        """Truncation-Schluesselwoerter werden erkannt."""
        project_files = {
            "generator.py": "def generate(): pass\n",
        }
        # Braucht zusaetzlich einen Traceback damit last_file gefunden wird
        output = (
            'File "generator.py", line 50\n'
            "Output wurde truncated wegen Laengenbeschraenkung"
        )
        result = extract_truncation_errors(output, project_files)
        assert len(result) >= 1, "Erwartet: mindestens 1 Truncation-Fehler"
        fehler = result[0]
        assert fehler.error_type == "truncation"
        assert fehler.file_path == "generator.py"

    def test_kein_truncation_bei_normalem_output(self):
        """Normaler Output ohne Truncation-Woerter gibt leere Liste."""
        project_files = {"app.py": "print('ok')\n"}
        output = "Build erfolgreich abgeschlossen."
        result = extract_truncation_errors(output, project_files)
        assert result == [], "Erwartet: leere Liste bei normalem Output"


# =========================================================================
# Test: extract_pip_dependency_errors
# =========================================================================

class TestExtractPipDependencyErrors:
    """Tests fuer pip/Dependency-Fehler Extraktion."""

    def test_missing_module_erkannt(self):
        """Fehlendes Modul 'No module named X' wird erkannt."""
        project_files = {
            "requirements.txt": "flask\nrequests\n",
            "app.py": "import pytest\n",
        }
        output = "No module named pytest"
        result = extract_pip_dependency_errors(output, project_files)
        assert len(result) >= 1, "Erwartet: mindestens 1 pip-Fehler"
        fehler = result[0]
        assert fehler.error_type == "pip_dependency"
        assert fehler.file_path == "requirements.txt"
        assert "pytest" in fehler.suggested_fix

    def test_invalid_package_erkannt(self):
        """Ungueltiges Paket 'No matching distribution' wird erkannt."""
        project_files = {
            "requirements.txt": "bootstrap\n",
        }
        output = "ERROR: No matching distribution found for bootstrap"
        result = extract_pip_dependency_errors(output, project_files)
        assert len(result) >= 1, "Erwartet: mindestens 1 Paket-Fehler"
        fehler = result[0]
        assert fehler.error_type == "pip_dependency"
        assert "bootstrap" in fehler.error_message

    def test_dependency_conflict_erkannt(self):
        """Dependency-Konflikt 'ResolutionImpossible' wird erkannt."""
        project_files = {
            "requirements.txt": "flask==2.0\nwerkzeug==0.16\n",
        }
        output = "ERROR: ResolutionImpossible - conflicting versions"
        result = extract_pip_dependency_errors(output, project_files)
        assert len(result) >= 1, "Erwartet: mindestens 1 Dependency-Konflikt"
        # Pruefen ob ein Eintrag den Typ pip_dependency hat
        typen = [e.error_type for e in result]
        assert "pip_dependency" in typen


# =========================================================================
# Test: _find_requirements_file
# =========================================================================

class TestFindRequirementsFile:
    """Tests fuer die Requirements-Datei Suche."""

    def test_standard_requirements_gefunden(self):
        """Standard requirements.txt wird gefunden."""
        project_files = {
            "requirements.txt": "flask\n",
            "app.py": "import flask\n",
        }
        result = _find_requirements_file(project_files)
        assert result == "requirements.txt", "Erwartet: requirements.txt"

    def test_fallback_wenn_nicht_vorhanden(self):
        """Wenn keine requirements-Datei existiert, wird Default zurueckgegeben."""
        project_files = {
            "app.py": "import flask\n",
            "setup.py": "from setuptools import setup\n",
        }
        result = _find_requirements_file(project_files)
        # Fallback: requirements.txt als Default
        assert result == "requirements.txt", "Erwartet: Fallback zu requirements.txt"


# =========================================================================
# Test: analyze_docker_error
# =========================================================================

class TestAnalyzeDockerError:
    """Tests fuer Docker-Fehler Analyse."""

    def test_zirkulaerer_import_erkannt(self):
        """Zirkulaerer Import im Docker-Output wird erkannt."""
        # IMPORT_ERROR_PATTERNS circular_import: (\S+\.py):(\d+):\s*in\s*<module>
        error_output = (
            "Traceback (most recent call last):\n"
            "  src/__init__.py:3: in <module>\n"
            "    from src.routes import router\n"
            "ImportError: cannot import name 'router'"
        )
        result = analyze_docker_error(error_output)
        assert result is not None, "Erwartet: Dict mit Fehlerdetails"
        assert result["type"] == "circular_import"
        assert result["file"] == "src/__init__.py"
        assert result["line"] == 3

    def test_pip_fehler_erkannt(self):
        """Fehlende pip-Abhaengigkeit wird erkannt."""
        error_output = "No module named 'requests'"
        result = analyze_docker_error(error_output)
        assert result is not None, "Erwartet: Dict mit Fehlerdetails"
        assert result["type"] == "missing_module"
        assert result["file"] == "requirements.txt"

    def test_kein_fehler_gibt_none(self):
        """Output ohne erkannte Fehler gibt None zurueck."""
        error_output = "Alles ok, Server laeuft auf Port 8080."
        result = analyze_docker_error(error_output)
        assert result is None, "Erwartet: None bei fehlerfreiem Output"


# =========================================================================
# Test: extract_circular_import_errors
# =========================================================================

class TestExtractCircularImportErrors:
    """Tests fuer zirkulaere Import-Fehler Extraktion."""

    def test_zirkulaerer_import_gefunden(self):
        """Zirkulaerer Import-Pattern wird korrekt extrahiert."""
        project_files = {
            "src/__init__.py": "from src.routes import router\n",
            "src/routes.py": "from src import app\n",
        }
        # Pattern: (\S+\.py):(\d+):\s*in\s*<module>
        output = (
            "src/__init__.py:1: in <module>\n"
            "    from src.routes import router\n"
            "ImportError: circular import"
        )
        result = extract_circular_import_errors(output, project_files)
        assert len(result) >= 1, "Erwartet: mindestens 1 zirkulaerer Import-Fehler"
        fehler = result[0]
        assert fehler.error_type == "import"
        assert 1 in fehler.line_numbers
        assert "Zirkulaer" in fehler.error_message

    def test_kein_zirkulaerer_import(self):
        """Output ohne zirkulaere Imports gibt leere Liste."""
        project_files = {"app.py": "import os\n"}
        output = "Build erfolgreich, keine Fehler."
        result = extract_circular_import_errors(output, project_files)
        assert result == [], "Erwartet: leere Liste bei fehlerfreiem Output"


# =========================================================================
# Test: extract_config_errors
# =========================================================================

class TestExtractConfigErrors:
    """Tests fuer Config-Datei Fehler Extraktion."""

    def test_pytest_ini_fehler_erkannt(self):
        """pytest.ini Syntax-Fehler wird erkannt."""
        project_files = {
            "pytest.ini": "[pytest]\naddopts = -v\n",
        }
        # CONFIG_ERROR_PATTERNS config_error: ERROR:\s*(.+?\.(?:ini|cfg|toml|yaml)):(\d+):\s*(.+)
        output = "ERROR: C:\\project\\pytest.ini:1: unexpected line: 'ini'"
        result = extract_config_errors(output, project_files)
        assert len(result) >= 1, "Erwartet: mindestens 1 Config-Fehler"
        fehler = result[0]
        assert fehler.error_type == "config"
        assert "pytest.ini" in fehler.file_path
        assert fehler.severity == "error"

    def test_kein_config_fehler_bei_normalem_output(self):
        """Normaler Output ohne Config-Fehler gibt leere Liste."""
        project_files = {"pytest.ini": "[pytest]\naddopts = -v\n"}
        output = "===== 10 passed in 1.2s ====="
        result = extract_config_errors(output, project_files)
        assert result == [], "Erwartet: leere Liste bei normalem Output"


# =========================================================================
# Test: detect_environment_constraints
# =========================================================================

class TestDetectEnvironmentConstraints:
    """Tests fuer Umgebungs-Constraint Erkennung."""

    def test_bekanntes_modul_mit_alternative(self):
        """Bekanntes Modul (z.B. bleach) liefert Alternative."""
        error_output = "ModuleNotFoundError: No module named 'bleach'"
        result = detect_environment_constraints(error_output)
        assert len(result) >= 1, "Erwartet: mindestens 1 Constraint"
        constraint = result[0]
        assert constraint["constraint"] == "bleach_not_available"
        assert constraint["priority"] == "high"
        assert "alternative" in constraint, "Erwartet: Alternative fuer bekanntes Modul"
        assert "HTML" in constraint["alternative"] or "re.sub" in constraint["alternative"]

    def test_unbekanntes_modul_ohne_alternative(self):
        """Unbekanntes Modul hat keine Alternative."""
        error_output = "ModuleNotFoundError: No module named 'mein_spezial_modul'"
        result = detect_environment_constraints(error_output)
        assert len(result) >= 1, "Erwartet: mindestens 1 Constraint"
        constraint = result[0]
        assert constraint["constraint"] == "mein_spezial_modul_not_available"
        assert "alternative" not in constraint, "Erwartet: keine Alternative fuer unbekanntes Modul"

    def test_leerer_output_keine_constraints(self):
        """Leerer Output gibt keine Constraints zurueck."""
        result = detect_environment_constraints("")
        assert result == [], "Erwartet: leere Liste bei leerem Output"
