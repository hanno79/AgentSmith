# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 14.02.2026
Version: 1.0
Beschreibung: Unit-Tests fuer backend/dev_loop_augment.py.
              Testet get_augment_context() mit verschiedenen Szenarien:
              - Kein External Bureau, niedrige Iteration, deaktiviert
              - CLI nicht verfuegbar, npx nicht gefunden
              - Erfolgreicher Subprocess-Aufruf
              - Timeout, FileNotFoundError, OSError
"""

import os
import sys
import subprocess
import pytest
from unittest.mock import MagicMock, patch, PropertyMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.dev_loop_augment import get_augment_context


# =========================================================================
# Fixtures
# =========================================================================

@pytest.fixture
def mock_manager():
    """Manager mit External Bureau und Augment-Config."""
    manager = MagicMock()
    manager._ui_log = MagicMock()
    manager.project_path = "C:\\Temp\\test_project"
    manager.config = {
        "external_specialists": {
            "augment_context": {
                "use_for_context": True,
                "timeout_seconds": 60,
                "cli_command": "npx @augmentcode/auggie"
            }
        }
    }
    # External Bureau mit Augment-Specialist
    augment_specialist = MagicMock()
    augment_specialist.check_available.return_value = True
    augment_specialist.status = "ready"  # Nicht READY enum
    manager.external_bureau = MagicMock()
    manager.external_bureau.get_specialist.return_value = augment_specialist
    return manager


# =========================================================================
# TestKeinExternalBureau
# =========================================================================

class TestKeinExternalBureau:
    """Tests fuer fruehe Rueckkehr wenn External Bureau fehlt."""

    def test_kein_external_bureau_attribut(self):
        """Manager ohne external_bureau → leerer String."""
        manager = MagicMock(spec=["_ui_log", "config"])
        result = get_augment_context(manager, "error", "review", 3)
        assert result == "", \
            "Erwartet: Leerer String wenn external_bureau nicht vorhanden"

    def test_external_bureau_none(self):
        """external_bureau = None → leerer String."""
        manager = MagicMock()
        manager.external_bureau = None
        result = get_augment_context(manager, "error", "review", 3)
        assert result == "", \
            "Erwartet: Leerer String wenn external_bureau None ist"

    def test_external_bureau_false(self):
        """external_bureau = False → leerer String."""
        manager = MagicMock()
        manager.external_bureau = False
        result = get_augment_context(manager, "error", "review", 3)
        assert result == "", \
            "Erwartet: Leerer String wenn external_bureau False ist"


# =========================================================================
# TestIterationCheck
# =========================================================================

class TestIterationCheck:
    """Tests fuer Iterations-Pruefung (nur bei Iteration 2+)."""

    def test_iteration_0_leerer_string(self, mock_manager):
        """Iteration 0 → leerer String (zu frueh)."""
        result = get_augment_context(mock_manager, "error", "review", 0)
        assert result == "", \
            "Erwartet: Leerer String bei Iteration 0"

    def test_iteration_1_leerer_string(self, mock_manager):
        """Iteration 1 → leerer String (zu frueh)."""
        result = get_augment_context(mock_manager, "error", "review", 1)
        assert result == "", \
            "Erwartet: Leerer String bei Iteration 1"

    def test_iteration_2_geht_weiter(self, mock_manager):
        """Iteration 2 → geht weiter (prueft naechste Bedingungen)."""
        with patch("shutil.which", return_value="/usr/bin/npx"), \
             patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout="Architektur-Kontext", stderr=""
            )
            result = get_augment_context(mock_manager, "error", "review", 2)
        assert result != "", \
            "Erwartet: Nicht-leerer String bei Iteration 2+"


# =========================================================================
# TestConfigPruefung
# =========================================================================

class TestConfigPruefung:
    """Tests fuer Konfigurations-Pruefung (use_for_context)."""

    def test_use_for_context_false(self, mock_manager):
        """use_for_context=False → leerer String."""
        mock_manager.config["external_specialists"]["augment_context"]["use_for_context"] = False
        result = get_augment_context(mock_manager, "error", "review", 3)
        assert result == "", \
            "Erwartet: Leerer String wenn use_for_context False"

    def test_fehlende_augment_context_config(self, mock_manager):
        """Keine augment_context Sektion → leerer String."""
        mock_manager.config = {"external_specialists": {}}
        result = get_augment_context(mock_manager, "error", "review", 3)
        assert result == "", \
            "Erwartet: Leerer String ohne augment_context Config"

    def test_fehlende_external_specialists_config(self, mock_manager):
        """Keine external_specialists Sektion → leerer String."""
        mock_manager.config = {}
        result = get_augment_context(mock_manager, "error", "review", 3)
        assert result == "", \
            "Erwartet: Leerer String ohne external_specialists Config"


# =========================================================================
# TestSpecialistPruefung
# =========================================================================

class TestSpecialistPruefung:
    """Tests fuer Augment-Specialist Verfuegbarkeitspruefung."""

    def test_kein_augment_specialist(self, mock_manager):
        """get_specialist('augment') gibt None → leerer String."""
        mock_manager.external_bureau.get_specialist.return_value = None
        result = get_augment_context(mock_manager, "error", "review", 3)
        assert result == "", \
            "Erwartet: Leerer String wenn Specialist None"

    def test_specialist_nicht_verfuegbar(self, mock_manager):
        """check_available() gibt False → leerer String + Log."""
        augment = mock_manager.external_bureau.get_specialist.return_value
        augment.check_available.return_value = False
        result = get_augment_context(mock_manager, "error", "review", 3)
        assert result == "", \
            "Erwartet: Leerer String wenn CLI nicht verfuegbar"
        mock_manager._ui_log.assert_called()


# =========================================================================
# TestNpxPfadAufloesung
# =========================================================================

class TestNpxPfadAufloesung:
    """Tests fuer npx-Pfad Aufloesung (shutil.which)."""

    def test_npx_nicht_im_path(self, mock_manager):
        """npx nicht gefunden → leerer String + Log."""
        with patch("shutil.which", return_value=None):
            result = get_augment_context(mock_manager, "error", "review", 3)
        assert result == "", \
            "Erwartet: Leerer String wenn npx nicht im PATH"
        # Pruefe NotFound-Log
        log_calls = [str(c) for c in mock_manager._ui_log.call_args_list]
        assert any("NotFound" in c or "npx" in c for c in log_calls), \
            "Erwartet: Log-Eintrag ueber fehlenden npx"

    def test_npx_im_path_gefunden(self, mock_manager):
        """npx im PATH → wird in Kommando verwendet."""
        with patch("shutil.which", return_value="/usr/local/bin/npx"), \
             patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout="Context Output", stderr=""
            )
            result = get_augment_context(mock_manager, "error", "review", 3)
        # Pruefe dass der volle Pfad im Kommando verwendet wird
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "/usr/local/bin/npx", \
            f"Erwartet: Voller npx-Pfad, erhalten: {cmd[0]}"


# =========================================================================
# TestSubprocessAusfuehrung
# =========================================================================

class TestSubprocessAusfuehrung:
    """Tests fuer den subprocess.run() Aufruf."""

    def test_erfolgreicher_aufruf(self, mock_manager):
        """Erfolgreicher subprocess → Content zurueck."""
        with patch("shutil.which", return_value="/usr/bin/npx"), \
             patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="Projekt verwendet Next.js mit App Router.",
                stderr=""
            )
            result = get_augment_context(mock_manager, "error", "review", 3)
        assert "Next.js" in result, \
            f"Erwartet: 'Next.js' im Ergebnis, erhalten: '{result}'"

    def test_content_auf_2000_zeichen_begrenzt(self, mock_manager):
        """Ausgabe wird auf 2000 Zeichen begrenzt."""
        with patch("shutil.which", return_value="/usr/bin/npx"), \
             patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="X" * 5000,
                stderr=""
            )
            result = get_augment_context(mock_manager, "error", "review", 3)
        assert len(result) == 2000, \
            f"Erwartet: 2000 Zeichen, erhalten: {len(result)}"

    def test_returncode_nicht_null(self, mock_manager):
        """returncode ≠ 0 → leerer String."""
        with patch("shutil.which", return_value="/usr/bin/npx"), \
             patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stdout="",
                stderr="Fehler aufgetreten"
            )
            result = get_augment_context(mock_manager, "error", "review", 3)
        assert result == "", \
            "Erwartet: Leerer String bei returncode ≠ 0"

    def test_leerer_stdout(self, mock_manager):
        """Leerer stdout → leerer String."""
        with patch("shutil.which", return_value="/usr/bin/npx"), \
             patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="  \n  ",  # nur Whitespace
                stderr=""
            )
            result = get_augment_context(mock_manager, "error", "review", 3)
        assert result == "", \
            "Erwartet: Leerer String bei leerem stdout"

    def test_timeout_expired(self, mock_manager):
        """subprocess.TimeoutExpired → leerer String + Log."""
        with patch("shutil.which", return_value="/usr/bin/npx"), \
             patch("subprocess.run", side_effect=subprocess.TimeoutExpired("cmd", 60)):
            result = get_augment_context(mock_manager, "error", "review", 3)
        assert result == "", \
            "Erwartet: Leerer String bei Timeout"

    def test_file_not_found_error(self, mock_manager):
        """FileNotFoundError → leerer String + Log."""
        with patch("shutil.which", return_value="/usr/bin/npx"), \
             patch("subprocess.run", side_effect=FileNotFoundError("npx nicht da")):
            result = get_augment_context(mock_manager, "error", "review", 3)
        assert result == "", \
            "Erwartet: Leerer String bei FileNotFoundError"

    def test_os_error(self, mock_manager):
        """OSError → leerer String + Log."""
        with patch("shutil.which", return_value="/usr/bin/npx"), \
             patch("subprocess.run", side_effect=OSError("Betriebssystemfehler")):
            result = get_augment_context(mock_manager, "error", "review", 3)
        assert result == "", \
            "Erwartet: Leerer String bei OSError"

    def test_generelle_exception(self, mock_manager):
        """Generelle Exception → leerer String (aeusserer try-catch)."""
        # Specialist-Fehler (in aeusserem try)
        augment = mock_manager.external_bureau.get_specialist.return_value
        augment.check_available.side_effect = RuntimeError("Interner Fehler")
        result = get_augment_context(mock_manager, "error", "review", 3)
        assert result == "", \
            "Erwartet: Leerer String bei genereller Exception"

    def test_custom_cli_command_ohne_npx(self, mock_manager):
        """cli_command ohne 'npx' Prefix → kein shutil.which Aufruf."""
        mock_manager.config["external_specialists"]["augment_context"]["cli_command"] = \
            "auggie-cli"
        with patch("shutil.which") as mock_which, \
             patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout="Custom Output", stderr=""
            )
            result = get_augment_context(mock_manager, "error", "review", 3)
        # shutil.which soll NICHT aufgerufen werden
        mock_which.assert_not_called()
        assert "Custom Output" in result


# =========================================================================
# TestKonfigurationsDefaults
# =========================================================================

class TestKonfigurationsDefaults:
    """Tests fuer Default-Werte in der Konfiguration."""

    def test_default_timeout_300(self, mock_manager):
        """Ohne timeout_seconds Config → Default 300s."""
        del mock_manager.config["external_specialists"]["augment_context"]["timeout_seconds"]
        with patch("shutil.which", return_value="/usr/bin/npx"), \
             patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout="Output", stderr=""
            )
            get_augment_context(mock_manager, "error", "review", 3)
        # Pruefe timeout Parameter
        assert mock_run.call_args[1]["timeout"] == 300, \
            "Erwartet: Default-Timeout 300s"

    def test_custom_timeout(self, mock_manager):
        """Custom timeout_seconds wird verwendet."""
        mock_manager.config["external_specialists"]["augment_context"]["timeout_seconds"] = 120
        with patch("shutil.which", return_value="/usr/bin/npx"), \
             patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout="Output", stderr=""
            )
            get_augment_context(mock_manager, "error", "review", 3)
        assert mock_run.call_args[1]["timeout"] == 120, \
            "Erwartet: Custom-Timeout 120s"

    def test_sandbox_result_none(self, mock_manager):
        """sandbox_result=None → 'Keine' im Query."""
        with patch("shutil.which", return_value="/usr/bin/npx"), \
             patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout="Output", stderr=""
            )
            result = get_augment_context(mock_manager, None, None, 3)
        assert result == "Output", \
            "Erwartet: Funktioniert auch mit None sandbox_result"
