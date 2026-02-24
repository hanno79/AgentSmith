# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 24.02.2026
Version: 1.0
Beschreibung: Aufgesplittete Tests fuer run_test_generator aus dev_loop_test_utils.
"""

import os
import sys
import pytest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.dev_loop_test_utils import run_test_generator

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
