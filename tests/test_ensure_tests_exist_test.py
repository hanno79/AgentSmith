# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 24.02.2026
Version: 1.0
Beschreibung: Aufgesplittete Tests fuer ensure_tests_exist aus dev_loop_test_utils.
"""

import os
import sys
import pytest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.dev_loop_test_utils import ensure_tests_exist

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

