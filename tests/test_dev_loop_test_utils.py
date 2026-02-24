# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 14.02.2026
Version: 2.0
Beschreibung: Tests fuer dev_loop_test_utils.py.
              Testet _matches_any_pattern, _is_test_file, _is_code_file,
              run_test_generator und ensure_tests_exist.
              AENDERUNG 14.02.2026: Erweitert um Tests fuer run_test_generator
              und ensure_tests_exist mit vollstaendigem Mocking.
"""

import os
import sys
import pytest
from unittest.mock import MagicMock, patch, mock_open

# Projekt-Root zum Python-Path hinzufuegen
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.dev_loop_test_utils import (
    _matches_any_pattern, _is_test_file, _is_code_file,
    run_test_generator, ensure_tests_exist
)


# =========================================================================
# Wiederverwendbare Test-Konfigurationen
# =========================================================================

PYTHON_CONFIG = {
    "test_patterns": ["test_*.py", "*_test.py"],
    "code_extensions": [".py"],
    "skip_patterns": ["__pycache__", ".pyc", "__init__"],
    "test_command": "pytest",
}

JS_CONFIG = {
    "test_patterns": [
        "*.test.js", "*.test.jsx", "*.spec.js",
        "*.test.ts", "*.test.tsx", "*.spec.ts",
    ],
    "code_extensions": [".js", ".jsx", ".ts", ".tsx"],
    "skip_patterns": ["node_modules", ".min.", "bundle.", "vendor"],
    "test_command": "npm test",
}

CSHARP_CONFIG = {
    "test_patterns": ["*Tests.cs", "*Test.cs", "*_test.cs"],
    "code_extensions": [".cs"],
    "skip_patterns": ["bin/", "obj/", ".Designer."],
}

EMPTY_CONFIG = {
    "test_patterns": [],
    "code_extensions": [],
    "skip_patterns": [],
}


# =========================================================================
# Tests fuer _matches_any_pattern
# =========================================================================

class TestMatchesAnyPattern:
    """Tests fuer _matches_any_pattern - fnmatch Wrapper."""

    def test_match_python_test_prefix(self):
        """Python test_*.py Pattern wird erkannt."""
        assert _matches_any_pattern("test_app.py", ["test_*.py"]) is True

    def test_match_python_test_suffix(self):
        """Python *_test.py Pattern wird erkannt."""
        assert _matches_any_pattern("app_test.py", ["*_test.py"]) is True

    def test_no_match(self):
        """Normale Code-Datei matcht keins der Test-Patterns."""
        assert _matches_any_pattern("app.py", ["test_*.py", "*_test.py"]) is False

    def test_match_js_test(self):
        """JavaScript *.test.js Pattern wird erkannt."""
        assert _matches_any_pattern("App.test.js", ["*.test.js"]) is True

    def test_match_ts_spec(self):
        """TypeScript *.spec.ts Pattern wird erkannt."""
        assert _matches_any_pattern("utils.spec.ts", ["*.spec.ts"]) is True

    def test_leere_patterns(self):
        """Leere Pattern-Liste ergibt immer False."""
        assert _matches_any_pattern("test_app.py", []) is False

    def test_mehrere_patterns_zweites_matcht(self):
        """Bei mehreren Patterns reicht ein Treffer."""
        assert _matches_any_pattern("app_test.py", ["test_*.py", "*_test.py"]) is True

    def test_case_sensitivity(self):
        """Exakter Match funktioniert unabhaengig vom Betriebssystem."""
        assert _matches_any_pattern("test_app.py", ["test_*.py"]) is True

    def test_wildcard_star(self):
        """Wildcard * matcht beliebige Zeichen vor dem Suffix."""
        assert _matches_any_pattern("anything.test.js", ["*.test.js"]) is True

    def test_kein_match_falsche_extension(self):
        """Falsche Dateiendung wird nicht gematcht."""
        assert _matches_any_pattern("test_app.txt", ["test_*.py"]) is False


# =========================================================================
# Tests fuer _is_test_file
# =========================================================================

class TestIsTestFile:
    """Tests fuer _is_test_file mit verschiedenen Sprach-Configs."""

    # --- Python ---
    def test_python_test_prefix(self):
        """Python Test-Datei mit test_ Prefix wird erkannt."""
        assert _is_test_file("test_models.py", PYTHON_CONFIG) is True

    def test_python_test_suffix(self):
        """Python Test-Datei mit _test Suffix wird erkannt."""
        assert _is_test_file("models_test.py", PYTHON_CONFIG) is True

    def test_python_code_datei(self):
        """Normale Python-Datei ist keine Test-Datei."""
        assert _is_test_file("models.py", PYTHON_CONFIG) is False

    def test_python_init_nicht_test(self):
        """__init__.py ist keine Test-Datei."""
        assert _is_test_file("__init__.py", PYTHON_CONFIG) is False

    # --- JavaScript / TypeScript ---
    def test_js_test_datei(self):
        """JavaScript .test.js Datei wird erkannt."""
        assert _is_test_file("App.test.js", JS_CONFIG) is True

    def test_js_spec_datei(self):
        """JavaScript .spec.js Datei wird erkannt."""
        assert _is_test_file("utils.spec.js", JS_CONFIG) is True

    def test_jsx_test_datei(self):
        """JSX .test.jsx Datei wird erkannt."""
        assert _is_test_file("Component.test.jsx", JS_CONFIG) is True

    def test_ts_test_datei(self):
        """TypeScript .test.ts Datei wird erkannt."""
        assert _is_test_file("service.test.ts", JS_CONFIG) is True

    def test_tsx_test_datei(self):
        """TSX .test.tsx Datei wird erkannt."""
        assert _is_test_file("Page.test.tsx", JS_CONFIG) is True

    def test_js_code_datei(self):
        """Normale JS-Datei ist keine Test-Datei."""
        assert _is_test_file("App.js", JS_CONFIG) is False

    # --- C# ---
    def test_csharp_tests(self):
        """C# *Tests.cs Datei wird erkannt."""
        assert _is_test_file("UserTests.cs", CSHARP_CONFIG) is True

    def test_csharp_code(self):
        """Normale C#-Datei ist keine Test-Datei."""
        assert _is_test_file("User.cs", CSHARP_CONFIG) is False

    # --- Edge Cases ---
    def test_leere_config(self):
        """Leere Config ergibt immer False."""
        assert _is_test_file("test_app.py", EMPTY_CONFIG) is False

    def test_fehlende_test_patterns(self):
        """Config ohne test_patterns Key ergibt False."""
        assert _is_test_file("test_app.py", {}) is False


# =========================================================================
# Tests fuer _is_code_file
# =========================================================================

class TestIsCodeFile:
    """Tests fuer _is_code_file mit Extension- und Skip-Pattern-Pruefung."""

    # --- Python ---
    def test_python_code_datei(self):
        """Normale Python-Datei wird als Code erkannt."""
        assert _is_code_file("app.py", PYTHON_CONFIG) is True

    def test_python_test_ist_code(self):
        """Test-Dateien haben .py Extension und sind technisch Code-Dateien.
        _is_code_file prueft nur Extension und skip_patterns, nicht test_patterns."""
        assert _is_code_file("test_app.py", PYTHON_CONFIG) is True

    def test_python_pycache_skip(self):
        """Dateien in __pycache__ werden uebersprungen."""
        assert _is_code_file("__pycache__/module.py", PYTHON_CONFIG) is False

    def test_python_init_skip(self):
        """__init__.py wird uebersprungen (enthaelt __init__ Skip-Pattern)."""
        assert _is_code_file("__init__.py", PYTHON_CONFIG) is False

    def test_python_pyc_skip(self):
        """Kompilierte .pyc Dateien werden uebersprungen."""
        assert _is_code_file("module.pyc", PYTHON_CONFIG) is False

    # --- JavaScript / TypeScript ---
    def test_js_code_datei(self):
        """Normale JS-Datei wird als Code erkannt."""
        assert _is_code_file("App.js", JS_CONFIG) is True

    def test_jsx_code_datei(self):
        """JSX-Datei wird als Code erkannt."""
        assert _is_code_file("Component.jsx", JS_CONFIG) is True

    def test_ts_code_datei(self):
        """TypeScript-Datei wird als Code erkannt."""
        assert _is_code_file("service.ts", JS_CONFIG) is True

    def test_tsx_code_datei(self):
        """TSX-Datei wird als Code erkannt."""
        assert _is_code_file("Page.tsx", JS_CONFIG) is True

    def test_js_node_modules_skip(self):
        """Dateien in node_modules werden uebersprungen."""
        assert _is_code_file("node_modules/lib.js", JS_CONFIG) is False

    def test_js_minified_skip(self):
        """Minifizierte Dateien (.min.) werden uebersprungen."""
        assert _is_code_file("app.min.js", JS_CONFIG) is False

    def test_js_bundle_skip(self):
        """Bundle-Dateien werden uebersprungen."""
        assert _is_code_file("bundle.js", JS_CONFIG) is False

    def test_js_vendor_skip(self):
        """Vendor-Dateien werden uebersprungen."""
        assert _is_code_file("vendor/lib.js", JS_CONFIG) is False

    # --- Nicht-Code-Dateien ---
    def test_html_nicht_code(self):
        """HTML-Dateien sind kein Python-Code."""
        assert _is_code_file("index.html", PYTHON_CONFIG) is False

    def test_json_nicht_code(self):
        """JSON-Dateien sind kein JS-Code."""
        assert _is_code_file("package.json", JS_CONFIG) is False

    def test_markdown_nicht_code(self):
        """Markdown-Dateien sind kein Code."""
        assert _is_code_file("README.md", PYTHON_CONFIG) is False

    # --- Edge Cases ---
    def test_leere_config(self):
        """Leere Config ergibt immer False."""
        assert _is_code_file("app.py", EMPTY_CONFIG) is False

    def test_fehlende_keys(self):
        """Config ohne code_extensions Key ergibt False."""
        assert _is_code_file("app.py", {}) is False


# =========================================================================
# Fixtures fuer run_test_generator und ensure_tests_exist
# =========================================================================

@pytest.fixture
def mock_manager(tmp_path):
    """Erstellt einen Mock-Manager mit allen notwendigen Attributen."""
    manager = MagicMock()
    manager.project_path = str(tmp_path)
    manager.tech_blueprint = {
        "project_type": "python_script",
        "language": "python",
        "framework": "",
    }
    manager.config = {"mode": "test"}
    manager.model_router = MagicMock()
    manager.project_rules = "Beispiel Projekt-Regeln"
    manager._ui_log = MagicMock()
    return manager


# =========================================================================
# Tests fuer run_test_generator
# =========================================================================

class TestRunTestGenerator:
    """Tests fuer run_test_generator - CrewAI Test-Generator mit Mocking."""

    @patch("backend.dev_loop_test_utils.extract_test_files")
    @patch("backend.dev_loop_test_utils.Crew")
    @patch("backend.dev_loop_test_utils.create_test_generation_task")
    @patch("backend.dev_loop_test_utils.create_test_generator")
    def test_erfolgreiche_generierung(
        self, mock_create_gen, mock_create_task, mock_crew_cls,
        mock_extract, mock_manager
    ):
        """Erfolgreiche Test-Generierung: Crew liefert FILENAME-Block zurueck."""
        # Arrange: Crew.kickoff liefert Output mit FILENAME-Block
        mock_crew_instance = MagicMock()
        mock_crew_instance.kickoff.return_value = (
            "### FILENAME: tests/test_app.py\ndef test_hello():\n    assert True\n"
        )
        mock_crew_cls.return_value = mock_crew_instance
        mock_extract.return_value = {
            "tests/test_app.py": "def test_hello():\n    assert True\n"
        }
        code_files = {"app.py": "def hello(): pass"}

        # Act
        ergebnis = run_test_generator(mock_manager, code_files, iteration=1)

        # Assert
        assert ergebnis is True
        mock_create_gen.assert_called_once()
        mock_create_task.assert_called_once()
        mock_crew_cls.assert_called_once()
        mock_extract.assert_called_once()
        # Test-Datei muss auf Disk geschrieben worden sein
        test_pfad = os.path.join(mock_manager.project_path, "tests", "test_app.py")
        assert os.path.exists(test_pfad), (
            f"Erwartet: Test-Datei auf Disk unter {test_pfad}, Erhalten: Datei nicht vorhanden"
        )

    @patch("backend.dev_loop_test_utils.Crew")
    @patch("backend.dev_loop_test_utils.create_test_generation_task")
    @patch("backend.dev_loop_test_utils.create_test_generator")
    def test_fehlgeschlagen_exception(
        self, mock_create_gen, mock_create_task, mock_crew_cls, mock_manager
    ):
        """Test-Generator schlaegt mit Exception fehl → gibt False zurueck."""
        # Arrange: Crew.kickoff wirft Exception
        mock_crew_instance = MagicMock()
        mock_crew_instance.kickoff.side_effect = RuntimeError("API Fehler")
        mock_crew_cls.return_value = mock_crew_instance
        code_files = {"app.py": "def hello(): pass"}

        # Act
        ergebnis = run_test_generator(mock_manager, code_files, iteration=1)

        # Assert
        assert ergebnis is False
        # _ui_log muss mit Error-Level aufgerufen worden sein
        error_calls = [
            call for call in mock_manager._ui_log.call_args_list
            if call[0][1] == "Error"
        ]
        assert len(error_calls) >= 1, (
            "Erwartet: Mindestens ein _ui_log-Aufruf mit Level 'Error'"
        )

    @patch("backend.dev_loop_test_utils.Crew")
    @patch("backend.dev_loop_test_utils.create_test_generation_task")
    @patch("backend.dev_loop_test_utils.create_test_generator")
    def test_keine_tests_im_output(
        self, mock_create_gen, mock_create_task, mock_crew_cls, mock_manager
    ):
        """Crew liefert Output ohne FILENAME-Block → gibt False zurueck."""
        # Arrange: Crew.kickoff liefert unbrauchbaren Output
        mock_crew_instance = MagicMock()
        mock_crew_instance.kickoff.return_value = "Hier sind einige Vorschlaege..."
        mock_crew_cls.return_value = mock_crew_instance
        code_files = {"app.py": "def hello(): pass"}

        # Act
        ergebnis = run_test_generator(mock_manager, code_files, iteration=1)

        # Assert
        assert ergebnis is False
        # _ui_log muss mit Warning-Level aufgerufen worden sein
        warning_calls = [
            call for call in mock_manager._ui_log.call_args_list
            if call[0][1] == "Warning"
        ]
        assert len(warning_calls) >= 1, (
            "Erwartet: Mindestens ein _ui_log-Aufruf mit Level 'Warning'"
        )

    @patch("backend.dev_loop_test_utils.extract_test_files")
    @patch("backend.dev_loop_test_utils.Crew")
    @patch("backend.dev_loop_test_utils.create_test_generation_task")
    @patch("backend.dev_loop_test_utils.create_test_generator")
    def test_filename_block_aber_extract_leer(
        self, mock_create_gen, mock_create_task, mock_crew_cls,
        mock_extract, mock_manager
    ):
        """FILENAME-Block vorhanden aber extract_test_files gibt leeres Dict zurueck."""
        # Arrange
        mock_crew_instance = MagicMock()
        mock_crew_instance.kickoff.return_value = "### FILENAME: noop.py\nkein test"
        mock_crew_cls.return_value = mock_crew_instance
        mock_extract.return_value = {}  # Kein 'test' im Dateinamen
        code_files = {"app.py": "def hello(): pass"}

        # Act
        ergebnis = run_test_generator(mock_manager, code_files, iteration=1)

        # Assert
        assert ergebnis is False

    @patch("backend.dev_loop_test_utils.extract_test_files")
    @patch("backend.dev_loop_test_utils.Crew")
    @patch("backend.dev_loop_test_utils.create_test_generation_task")
    @patch("backend.dev_loop_test_utils.create_test_generator")
    def test_datei_wird_in_unterverzeichnis_geschrieben(
        self, mock_create_gen, mock_create_task, mock_crew_cls,
        mock_extract, mock_manager
    ):
        """Test-Dateien in Unterverzeichnissen werden korrekt erstellt."""
        mock_crew_instance = MagicMock()
        mock_crew_instance.kickoff.return_value = (
            "### FILENAME: tests/unit/test_module.py\nimport pytest\n"
        )
        mock_crew_cls.return_value = mock_crew_instance
        mock_extract.return_value = {
            "tests/unit/test_module.py": "import pytest\ndef test_eins(): pass\n"
        }
        code_files = {"module.py": "def eins(): return 1"}

        # Act
        ergebnis = run_test_generator(mock_manager, code_files, iteration=1)

        # Assert
        assert ergebnis is True
        test_pfad = os.path.join(
            mock_manager.project_path, "tests", "unit", "test_module.py"
        )
        assert os.path.exists(test_pfad), (
            f"Erwartet: Unterverzeichnis-Datei {test_pfad} existiert"
        )

    @patch("backend.dev_loop_test_utils.extract_test_files")
    @patch("backend.dev_loop_test_utils.Crew")
    @patch("backend.dev_loop_test_utils.create_test_generation_task")
    @patch("backend.dev_loop_test_utils.create_test_generator")
    def test_ui_log_status_beim_start(
        self, mock_create_gen, mock_create_task, mock_crew_cls,
        mock_extract, mock_manager
    ):
        """_ui_log wird mit 'Status' aufgerufen beim Start."""
        mock_crew_instance = MagicMock()
        mock_crew_instance.kickoff.return_value = "Kein Output"
        mock_crew_cls.return_value = mock_crew_instance
        code_files = {"app.py": "pass"}

        run_test_generator(mock_manager, code_files, iteration=0)

        # Erster _ui_log-Aufruf muss Status sein
        erster_aufruf = mock_manager._ui_log.call_args_list[0]
        assert erster_aufruf[0][0] == "TestGenerator", (
            "Erwartet: Agent-Name 'TestGenerator' im ersten Log-Aufruf"
        )
        assert erster_aufruf[0][1] == "Status", (
            "Erwartet: Level 'Status' im ersten Log-Aufruf"
        )


# =========================================================================
# Tests fuer ensure_tests_exist
# =========================================================================

class TestEnsureTestsExist:
    """Tests fuer ensure_tests_exist - Hauptfunktion fuer Test-Existenz-Pruefung."""

    def test_tests_existieren_in_tests_verzeichnis(self, mock_manager, tmp_path):
        """Vorhandene Tests im tests/ Verzeichnis → gibt True zurueck."""
        # Arrange: Erstelle tests/ Verzeichnis mit Test-Datei
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_app.py").write_text("def test_hello(): assert True")

        # Act
        ergebnis = ensure_tests_exist(mock_manager, iteration=0)

        # Assert
        assert ergebnis is True
        # _ui_log muss Info-Meldung ueber vorhandene Tests enthalten
        info_calls = [
            call for call in mock_manager._ui_log.call_args_list
            if call[0][1] == "Info" and "vorhanden" in str(call[0][2]).lower()
        ]
        assert len(info_calls) >= 1, (
            "Erwartet: _ui_log-Aufruf mit 'Tests vorhanden' Info"
        )

    def test_tests_existieren_im_root(self, mock_manager, tmp_path):
        """Vorhandene Tests im Root-Verzeichnis → gibt True zurueck."""
        # Arrange: Test-Datei direkt im Projektverzeichnis (kein tests/ Ordner)
        (tmp_path / "test_main.py").write_text("def test_main(): pass")

        # Act
        ergebnis = ensure_tests_exist(mock_manager, iteration=0)

        # Assert
        assert ergebnis is True
        info_calls = [
            call for call in mock_manager._ui_log.call_args_list
            if call[0][1] == "Info" and "root" in str(call[0][2]).lower()
        ]
        assert len(info_calls) >= 1, (
            "Erwartet: _ui_log-Aufruf mit 'Tests im Root' Info"
        )

    def test_nicht_python_mit_test_command(self, mock_manager, tmp_path):
        """Nicht-Python-Projekt mit test_command → gibt True zurueck (natives Tool)."""
        # Arrange: JavaScript-Projekt ohne Test-Dateien
        mock_manager.tech_blueprint = {
            "project_type": "webapp",
            "language": "javascript",
            "framework": "react",
        }

        # Act
        ergebnis = ensure_tests_exist(mock_manager, iteration=0)

        # Assert
        assert ergebnis is True
        info_calls = [
            call for call in mock_manager._ui_log.call_args_list
            if call[0][1] == "Info" and "javascript" in str(call[0][2]).lower()
        ]
        assert len(info_calls) >= 1, (
            "Erwartet: _ui_log-Aufruf mit Hinweis auf JavaScript-Test-Tool"
        )

    @patch("backend.dev_loop_test_utils.run_test_generator")
    def test_keine_tests_python_iteration_groesser_null(
        self, mock_run_gen, mock_manager, tmp_path
    ):
        """Keine Tests + Python + iteration>0 → run_test_generator aufrufen."""
        # Arrange: Python-Datei vorhanden, keine Test-Dateien
        (tmp_path / "app.py").write_text("def main(): pass")
        mock_run_gen.return_value = True

        # Act
        ergebnis = ensure_tests_exist(mock_manager, iteration=1)

        # Assert
        assert ergebnis is True
        mock_run_gen.assert_called_once()
        # Pruefe dass code_files korrekt uebergeben wurde
        call_args = mock_run_gen.call_args
        code_files_arg = call_args[0][1]
        assert "app.py" in code_files_arg, (
            "Erwartet: 'app.py' in code_files-Argument des run_test_generator-Aufrufs"
        )

    @patch("backend.dev_loop_test_utils.create_fallback_tests")
    def test_keine_tests_python_iteration_null_fallback(
        self, mock_fallback, mock_manager, tmp_path
    ):
        """Keine Tests + Python + iteration=0 → Fallback Templates verwenden."""
        # Arrange: Python-Datei vorhanden, keine Test-Dateien, iteration=0
        (tmp_path / "app.py").write_text("def main(): pass")
        mock_fallback.return_value = ["tests/test_app.py"]

        # Act
        ergebnis = ensure_tests_exist(mock_manager, iteration=0)

        # Assert
        assert ergebnis is True
        mock_fallback.assert_called_once_with(
            str(tmp_path), "python_script"
        )

    @patch("backend.dev_loop_test_utils.create_fallback_tests")
    def test_keine_tests_fallback_fehlgeschlagen(
        self, mock_fallback, mock_manager, tmp_path
    ):
        """Fallback Templates geben leere Liste zurueck → False."""
        # Arrange
        (tmp_path / "app.py").write_text("def main(): pass")
        mock_fallback.return_value = []

        # Act
        ergebnis = ensure_tests_exist(mock_manager, iteration=0)

        # Assert
        assert ergebnis is False
        error_calls = [
            call for call in mock_manager._ui_log.call_args_list
            if call[0][1] == "Error"
        ]
        assert len(error_calls) >= 1, (
            "Erwartet: _ui_log Error-Aufruf wenn keine Templates gefunden"
        )

    def test_statisches_projekt_keine_test_patterns(self, mock_manager):
        """Statisches Projekt (HTML/CSS) ohne test_patterns → True."""
        # Arrange: Statisches Projekt
        mock_manager.tech_blueprint = {
            "project_type": "static_html",
            "language": "html",
            "framework": "",
        }

        # Act
        ergebnis = ensure_tests_exist(mock_manager, iteration=0)

        # Assert
        assert ergebnis is True
        info_calls = [
            call for call in mock_manager._ui_log.call_args_list
            if call[0][1] == "Info" and "statisch" in str(call[0][2]).lower()
        ]
        assert len(info_calls) >= 1, (
            "Erwartet: _ui_log Info-Aufruf fuer statisches Projekt"
        )

    @patch("backend.dev_loop_test_utils.run_test_generator")
    @patch("backend.dev_loop_test_utils.create_fallback_tests")
    def test_run_test_generator_fehlschlag_dann_fallback(
        self, mock_fallback, mock_run_gen, mock_manager, tmp_path
    ):
        """run_test_generator gibt False → Fallback Templates werden versucht."""
        # Arrange
        (tmp_path / "main.py").write_text("print('hello')")
        mock_run_gen.return_value = False
        mock_fallback.return_value = ["tests/test_main.py"]

        # Act
        ergebnis = ensure_tests_exist(mock_manager, iteration=1)

        # Assert
        assert ergebnis is True
        mock_run_gen.assert_called_once()
        mock_fallback.assert_called_once()

    def test_keine_code_dateien_vorhanden(self, mock_manager, tmp_path):
        """Keine Python-Dateien im Projektverzeichnis → False."""
        # Arrange: Nur nicht-Python-Dateien vorhanden
        (tmp_path / "readme.txt").write_text("Nur eine Textdatei")
        (tmp_path / "config.json").write_text("{}")

        # Act
        ergebnis = ensure_tests_exist(mock_manager, iteration=0)

        # Assert
        assert ergebnis is False
        warning_calls = [
            call for call in mock_manager._ui_log.call_args_list
            if call[0][1] == "Warning" and "keine" in str(call[0][2]).lower()
        ]
        assert len(warning_calls) >= 1, (
            "Erwartet: _ui_log Warning ueber fehlende Code-Dateien"
        )

    def test_tests_dir_existiert_aber_leer(self, mock_manager, tmp_path):
        """tests/ Verzeichnis existiert aber enthaelt keine Test-Dateien."""
        # Arrange
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "__init__.py").write_text("")  # Kein Test-Pattern
        (tmp_path / "app.py").write_text("def main(): pass")

        # Act — iteration=0 → Fallback wird versucht
        with patch("backend.dev_loop_test_utils.create_fallback_tests") as mock_fb:
            mock_fb.return_value = ["tests/test_app.py"]
            ergebnis = ensure_tests_exist(mock_manager, iteration=0)

        # Assert
        assert ergebnis is True

    def test_tech_blueprint_leer_fallback_python(self, mock_manager, tmp_path):
        """tech_blueprint={} (leer) → Fallback auf Python-Config."""
        # Arrange: Leeres Blueprint, get_test_config_for_project gibt Python zurueck
        mock_manager.tech_blueprint = {}
        (tmp_path / "app.py").write_text("def main(): pass")

        # Act
        with patch("backend.dev_loop_test_utils.create_fallback_tests") as mock_fb:
            mock_fb.return_value = ["tests/test_app.py"]
            ergebnis = ensure_tests_exist(mock_manager, iteration=0)

        # Assert — Leeres Blueprint fallback auf Python
        assert ergebnis is True

    def test_tech_blueprint_none_ohne_code_dateien(self, mock_manager, tmp_path):
        """tech_blueprint=None + keine Code-Dateien → False (keine Dateien zum Testen).

        Hinweis: get_test_config_for_project behandelt None korrekt (Python-Fallback).
        Ohne Code-Dateien wird vor Zeile 205 abgebrochen.
        """
        # Arrange
        mock_manager.tech_blueprint = None
        # Nur eine nicht-Python-Datei, damit code_files leer bleibt
        (tmp_path / "readme.txt").write_text("Nur Text")

        # Act
        ergebnis = ensure_tests_exist(mock_manager, iteration=0)

        # Assert
        assert ergebnis is False

    @patch("backend.dev_loop_test_utils.run_test_generator")
    def test_tech_blueprint_none_mit_code_crasht(self, mock_run_gen, mock_manager, tmp_path):
        """tech_blueprint=None + Code-Dateien + iteration>0 darf nicht crashen.

        Nach dem Fix wird project_type None-safe ermittelt und auf
        'python_script' zurueckgefallen.
        """
        # Arrange
        mock_manager.tech_blueprint = None
        (tmp_path / "app.py").write_text("def main(): pass")
        mock_run_gen.return_value = False  # Generator fehlgeschlagen → Fallback

        # Assert: kein Crash bei None-tech_blueprint
        ergebnis = ensure_tests_exist(mock_manager, iteration=1)
        assert isinstance(ergebnis, bool)

    def test_mehrere_test_dateien_in_tests_dir(self, mock_manager, tmp_path):
        """Mehrere Test-Dateien → korrekte Anzahl wird geloggt."""
        # Arrange
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_a.py").write_text("pass")
        (tests_dir / "test_b.py").write_text("pass")
        (tests_dir / "test_c.py").write_text("pass")

        # Act
        ergebnis = ensure_tests_exist(mock_manager, iteration=0)

        # Assert
        assert ergebnis is True
        info_calls = [
            call for call in mock_manager._ui_log.call_args_list
            if call[0][1] == "Info" and "3" in str(call[0][2])
        ]
        assert len(info_calls) >= 1, (
            "Erwartet: _ui_log Info mit '3 Dateien'"
        )

    @patch("backend.dev_loop_test_utils.run_test_generator")
    def test_code_dateien_werden_korrekt_gesammelt(
        self, mock_run_gen, mock_manager, tmp_path
    ):
        """Nur .py Dateien werden als code_files an run_test_generator uebergeben."""
        # Arrange: Mischung aus Python und Nicht-Python-Dateien
        (tmp_path / "app.py").write_text("def app(): pass")
        (tmp_path / "utils.py").write_text("def helper(): pass")
        (tmp_path / "readme.md").write_text("Dokumentation")
        (tmp_path / "data.json").write_text("{}")
        mock_run_gen.return_value = True

        # Act
        ensure_tests_exist(mock_manager, iteration=1)

        # Assert
        call_args = mock_run_gen.call_args
        code_files_arg = call_args[0][1]
        assert "app.py" in code_files_arg, "Erwartet: app.py in code_files"
        assert "utils.py" in code_files_arg, "Erwartet: utils.py in code_files"
        assert "readme.md" not in code_files_arg, "Nicht erwartet: readme.md in code_files"
        assert "data.json" not in code_files_arg, "Nicht erwartet: data.json in code_files"

    def test_skip_pattern_dateien_nicht_gesammelt(self, mock_manager, tmp_path):
        """Dateien mit Skip-Pattern (conftest.py) werden nicht als Code-Dateien gesammelt.

        Hinweis: Die echte Python-Config aus qg_constants hat skip_patterns:
        ['test_', '_test.py', 'conftest.py']. conftest.py ist kein test_patterns
        Match aber wird durch skip_patterns gefiltert.

        Wichtig: test_*.py Dateien werden als Test-Dateien erkannt und fuehren
        zu einem fruehen Return in ensure_tests_exist (Root-Test-Check).
        Daher testen wir nur conftest.py als skip_pattern.
        """
        # Arrange: Nur conftest.py (Skip-Pattern) und app.py (Code)
        # KEINE test_*.py Dateien, da sonst ensure_tests_exist frueher returnt
        (tmp_path / "conftest.py").write_text("import pytest")
        (tmp_path / "app.py").write_text("def app(): pass")

        # Act
        with patch("backend.dev_loop_test_utils.run_test_generator") as mock_gen:
            mock_gen.return_value = True
            ensure_tests_exist(mock_manager, iteration=1)

            # Assert
            code_files_arg = mock_gen.call_args[0][1]
            assert "conftest.py" not in code_files_arg, (
                "Nicht erwartet: conftest.py sollte durch skip_pattern gefiltert werden"
            )
            assert "app.py" in code_files_arg
