# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 14.02.2026
Version: 1.0
Beschreibung: Tests fuer backend/dependency_checker.py
              Testet check_package, install_package, check_and_install_dependencies
              und get_dependency_status mit gemockten Imports und Subprocessen.
"""

import os
import sys
import subprocess
import pytest
from unittest.mock import patch, MagicMock

# Projekt-Root zum Python-Path hinzufuegen
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.dependency_checker import (
    CRITICAL_PACKAGES,
    check_package,
    install_package,
    check_and_install_dependencies,
    get_dependency_status,
)


# =========================================================================
# Tests fuer CRITICAL_PACKAGES
# =========================================================================

class TestCriticalPackages:
    """Tests fuer die CRITICAL_PACKAGES Konstante."""

    def test_ist_nicht_leer(self):
        """CRITICAL_PACKAGES enthaelt mindestens ein Package."""
        assert len(CRITICAL_PACKAGES) > 0, (
            "Erwartet: mindestens 1 Eintrag in CRITICAL_PACKAGES, "
            f"Erhalten: {len(CRITICAL_PACKAGES)}"
        )

    def test_enthaelt_pytest(self):
        """pytest ist in der Package-Liste enthalten."""
        import_names = [pkg[0] for pkg in CRITICAL_PACKAGES]
        assert "pytest" in import_names, (
            "Erwartet: 'pytest' in CRITICAL_PACKAGES, "
            f"Erhalten: {import_names}"
        )

    def test_enthaelt_playwright(self):
        """playwright ist in der Package-Liste enthalten."""
        import_names = [pkg[0] for pkg in CRITICAL_PACKAGES]
        assert "playwright" in import_names, (
            "Erwartet: 'playwright' in CRITICAL_PACKAGES, "
            f"Erhalten: {import_names}"
        )

    def test_tuple_format(self):
        """Jeder Eintrag hat das Format (import_name, install_name, zweck)."""
        for idx, entry in enumerate(CRITICAL_PACKAGES):
            assert len(entry) == 3, (
                f"Erwartet: Tuple mit 3 Elementen bei Index {idx}, "
                f"Erhalten: {len(entry)} Elemente: {entry}"
            )
            import_name, install_name, zweck = entry
            assert isinstance(import_name, str) and import_name, (
                f"Erwartet: nicht-leerer String fuer import_name bei Index {idx}, "
                f"Erhalten: {import_name!r}"
            )
            assert isinstance(install_name, str) and install_name, (
                f"Erwartet: nicht-leerer String fuer install_name bei Index {idx}, "
                f"Erhalten: {install_name!r}"
            )
            assert isinstance(zweck, str) and zweck, (
                f"Erwartet: nicht-leerer String fuer zweck bei Index {idx}, "
                f"Erhalten: {zweck!r}"
            )

    def test_enthaelt_pillow(self):
        """PIL/Pillow ist in der Package-Liste enthalten."""
        import_names = [pkg[0] for pkg in CRITICAL_PACKAGES]
        assert "PIL" in import_names, (
            "Erwartet: 'PIL' in CRITICAL_PACKAGES, "
            f"Erhalten: {import_names}"
        )


# =========================================================================
# Tests fuer check_package()
# =========================================================================

class TestCheckPackage:
    """Tests fuer check_package()."""

    def test_verfuegbares_package(self):
        """Verfuegbares Package gibt True zurueck."""
        # 'os' ist immer verfuegbar
        with patch("builtins.__import__", return_value=MagicMock()):
            result = check_package("some_available_package")
        assert result is True, (
            "Erwartet: True fuer verfuegbares Package, "
            f"Erhalten: {result}"
        )

    def test_fehlendes_package(self):
        """Fehlendes Package gibt False zurueck."""
        with patch("builtins.__import__", side_effect=ImportError("Modul nicht gefunden")):
            result = check_package("nicht_existierendes_package")
        assert result is False, (
            "Erwartet: False fuer fehlendes Package, "
            f"Erhalten: {result}"
        )

    def test_echtes_verfuegbares_modul(self):
        """Test mit echtem Standardbibliothek-Modul (sys)."""
        # sys ist immer verfuegbar - ohne Mock testen
        result = check_package("sys")
        assert result is True, (
            "Erwartet: True fuer 'sys' (Standardbibliothek), "
            f"Erhalten: {result}"
        )

    def test_echtes_fehlendes_modul(self):
        """Test mit garantiert nicht existierendem Modul."""
        result = check_package("zzz_dieses_modul_existiert_niemals_12345")
        assert result is False, (
            "Erwartet: False fuer nicht existierendes Modul, "
            f"Erhalten: {result}"
        )


# =========================================================================
# Tests fuer install_package()
# =========================================================================

class TestInstallPackage:
    """Tests fuer install_package()."""

    @patch("backend.dependency_checker.subprocess.run")
    def test_erfolgreiche_installation(self, mock_run):
        """Erfolgreiche pip-Installation gibt True zurueck."""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        result = install_package("testpaket")

        assert result is True, (
            "Erwartet: True bei returncode=0, "
            f"Erhalten: {result}"
        )
        # Pruefe dass subprocess.run mit korrekten Argumenten aufgerufen wurde
        mock_run.assert_called_once()
        call_args = mock_run.call_args
        assert "testpaket" in call_args[0][0], (
            "Erwartet: 'testpaket' in subprocess-Argumenten, "
            f"Erhalten: {call_args[0][0]}"
        )

    @patch("backend.dependency_checker.subprocess.run")
    def test_fehlgeschlagene_installation(self, mock_run):
        """Fehlgeschlagene pip-Installation gibt False zurueck."""
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="ERROR: Could not find package"
        )

        result = install_package("nicht_existierendes_paket")

        assert result is False, (
            "Erwartet: False bei returncode=1, "
            f"Erhalten: {result}"
        )

    @patch("backend.dependency_checker.subprocess.run")
    def test_timeout_gibt_false(self, mock_run):
        """TimeoutExpired bei Installation gibt False zurueck."""
        mock_run.side_effect = subprocess.TimeoutExpired(
            cmd="pip install langsames_paket",
            timeout=120
        )

        result = install_package("langsames_paket")

        assert result is False, (
            "Erwartet: False bei TimeoutExpired, "
            f"Erhalten: {result}"
        )

    @patch("backend.dependency_checker.subprocess.run")
    def test_allgemeine_exception_gibt_false(self, mock_run):
        """Allgemeine Exception bei Installation gibt False zurueck."""
        mock_run.side_effect = OSError("Keine Berechtigung")

        result = install_package("gesperrtes_paket")

        assert result is False, (
            "Erwartet: False bei allgemeiner Exception, "
            f"Erhalten: {result}"
        )

    @patch("backend.dependency_checker.subprocess.run")
    def test_pip_aufruf_parameter(self, mock_run):
        """Prueft korrekte pip-Aufruf-Parameter (sys.executable, -m, pip, install, -q)."""
        mock_run.return_value = MagicMock(returncode=0)

        install_package("beispiel_paket")

        call_args = mock_run.call_args
        cmd = call_args[0][0]
        assert cmd[0] == sys.executable, (
            f"Erwartet: sys.executable='{sys.executable}' als erstes Argument, "
            f"Erhalten: '{cmd[0]}'"
        )
        assert cmd[1:4] == ["-m", "pip", "install"], (
            f"Erwartet: ['-m', 'pip', 'install'], Erhalten: {cmd[1:4]}"
        )
        assert "beispiel_paket" in cmd, (
            f"Erwartet: 'beispiel_paket' in Kommando, Erhalten: {cmd}"
        )
        assert "-q" in cmd, (
            f"Erwartet: '-q' (quiet flag) in Kommando, Erhalten: {cmd}"
        )

    @patch("backend.dependency_checker.subprocess.run")
    def test_timeout_wert_ist_120(self, mock_run):
        """Timeout fuer subprocess.run ist auf 120 Sekunden gesetzt."""
        mock_run.return_value = MagicMock(returncode=0)

        install_package("beliebiges_paket")

        call_kwargs = mock_run.call_args[1]
        assert call_kwargs.get("timeout") == 120, (
            f"Erwartet: timeout=120, "
            f"Erhalten: timeout={call_kwargs.get('timeout')}"
        )


# =========================================================================
# Tests fuer check_and_install_dependencies()
# =========================================================================

class TestCheckAndInstallDependencies:
    """Tests fuer check_and_install_dependencies()."""

    @patch("backend.dependency_checker.check_package", return_value=True)
    def test_alle_vorhanden(self, mock_check):
        """Wenn alle Packages vorhanden sind, bleiben missing/installed/failed leer."""
        result = check_and_install_dependencies(auto_install=True)

        assert result["missing"] == [], (
            f"Erwartet: leere missing-Liste, Erhalten: {result['missing']}"
        )
        assert result["installed"] == [], (
            f"Erwartet: leere installed-Liste, Erhalten: {result['installed']}"
        )
        assert result["failed"] == [], (
            f"Erwartet: leere failed-Liste, Erhalten: {result['failed']}"
        )
        assert len(result["checked"]) == len(CRITICAL_PACKAGES), (
            f"Erwartet: {len(CRITICAL_PACKAGES)} geprueft, "
            f"Erhalten: {len(result['checked'])}"
        )

    @patch("backend.dependency_checker.install_package", return_value=True)
    @patch("backend.dependency_checker.check_package")
    def test_fehlend_mit_auto_install(self, mock_check, mock_install):
        """Fehlende Packages werden bei auto_install=True installiert."""
        # Erstes check_package: fehlt, zweites (nach Installation): verfuegbar
        # Fuer jedes Package: erster Aufruf=False, zweiter Aufruf(nach install)=True
        mock_check.side_effect = [False, True] * len(CRITICAL_PACKAGES)

        result = check_and_install_dependencies(auto_install=True)

        assert len(result["missing"]) == len(CRITICAL_PACKAGES), (
            f"Erwartet: alle {len(CRITICAL_PACKAGES)} als missing, "
            f"Erhalten: {len(result['missing'])}"
        )
        assert len(result["installed"]) == len(CRITICAL_PACKAGES), (
            f"Erwartet: alle {len(CRITICAL_PACKAGES)} als installed, "
            f"Erhalten: {len(result['installed'])}"
        )
        assert result["failed"] == [], (
            f"Erwartet: leere failed-Liste, Erhalten: {result['failed']}"
        )

    @patch("backend.dependency_checker.check_package", return_value=False)
    def test_fehlend_ohne_auto_install(self, mock_check):
        """Ohne auto_install werden fehlende nur gemeldet, nicht installiert."""
        result = check_and_install_dependencies(auto_install=False)

        assert len(result["missing"]) == len(CRITICAL_PACKAGES), (
            f"Erwartet: alle {len(CRITICAL_PACKAGES)} als missing, "
            f"Erhalten: {len(result['missing'])}"
        )
        assert result["installed"] == [], (
            f"Erwartet: leere installed-Liste (kein auto_install), "
            f"Erhalten: {result['installed']}"
        )
        assert result["failed"] == [], (
            f"Erwartet: leere failed-Liste (keine Installation versucht), "
            f"Erhalten: {result['failed']}"
        )

    @patch("backend.dependency_checker.install_package", return_value=False)
    @patch("backend.dependency_checker.check_package", return_value=False)
    def test_installation_fehlgeschlagen(self, mock_check, mock_install):
        """Fehlgeschlagene Installationen landen in failed-Liste."""
        result = check_and_install_dependencies(auto_install=True)

        assert len(result["missing"]) == len(CRITICAL_PACKAGES), (
            f"Erwartet: alle {len(CRITICAL_PACKAGES)} als missing, "
            f"Erhalten: {len(result['missing'])}"
        )
        assert len(result["failed"]) == len(CRITICAL_PACKAGES), (
            f"Erwartet: alle {len(CRITICAL_PACKAGES)} als failed, "
            f"Erhalten: {len(result['failed'])}"
        )
        assert result["installed"] == [], (
            f"Erwartet: leere installed-Liste bei fehlgeschlagener Installation, "
            f"Erhalten: {result['installed']}"
        )

    @patch("backend.dependency_checker.install_package", return_value=True)
    @patch("backend.dependency_checker.check_package")
    def test_installation_ok_aber_import_fehlschlaegt(self, mock_check, mock_install):
        """Package installiert (returncode=0) aber Import klappt danach nicht → failed."""
        # check_package gibt IMMER False zurueck (auch nach Installation)
        mock_check.return_value = False

        result = check_and_install_dependencies(auto_install=True)

        # install_package gibt True, aber zweites check_package gibt False → failed
        assert len(result["failed"]) == len(CRITICAL_PACKAGES), (
            f"Erwartet: alle als failed (Import nach Installation fehlgeschlagen), "
            f"Erhalten: {len(result['failed'])} failed"
        )

    @patch("backend.dependency_checker.check_package")
    def test_gemischt_vorhanden_und_fehlend(self, mock_check):
        """Manche Packages vorhanden, manche fehlend (ohne auto_install)."""
        # Erstes Package vorhanden, Rest fehlt
        side_effects = [True] + [False] * (len(CRITICAL_PACKAGES) - 1)
        mock_check.side_effect = side_effects

        result = check_and_install_dependencies(auto_install=False)

        assert len(result["missing"]) == len(CRITICAL_PACKAGES) - 1, (
            f"Erwartet: {len(CRITICAL_PACKAGES) - 1} missing, "
            f"Erhalten: {len(result['missing'])}"
        )
        assert len(result["checked"]) == len(CRITICAL_PACKAGES), (
            f"Erwartet: alle {len(CRITICAL_PACKAGES)} geprueft, "
            f"Erhalten: {len(result['checked'])}"
        )

    def test_ergebnis_hat_alle_schluessel(self):
        """Ergebnis-Dict enthaelt immer checked, missing, installed, failed."""
        with patch("backend.dependency_checker.check_package", return_value=True):
            result = check_and_install_dependencies()

        erwartete_schluessel = {"checked", "missing", "installed", "failed"}
        assert set(result.keys()) == erwartete_schluessel, (
            f"Erwartet: Schluessel {erwartete_schluessel}, "
            f"Erhalten: {set(result.keys())}"
        )


# =========================================================================
# Tests fuer get_dependency_status()
# =========================================================================

class TestGetDependencyStatus:
    """Tests fuer get_dependency_status()."""

    @patch("backend.dependency_checker.check_package", return_value=True)
    def test_alle_verfuegbar(self, mock_check):
        """Status zeigt alle Packages als verfuegbar an."""
        status = get_dependency_status()

        for import_name, install_name, purpose in CRITICAL_PACKAGES:
            assert import_name in status, (
                f"Erwartet: '{import_name}' im Status-Dict, "
                f"Erhalten: {list(status.keys())}"
            )
            pkg_status = status[import_name]
            assert pkg_status["available"] is True, (
                f"Erwartet: available=True fuer '{import_name}', "
                f"Erhalten: {pkg_status['available']}"
            )

    @patch("backend.dependency_checker.check_package", return_value=False)
    def test_alle_nicht_verfuegbar(self, mock_check):
        """Status zeigt alle Packages als nicht verfuegbar an."""
        status = get_dependency_status()

        for import_name, _, _ in CRITICAL_PACKAGES:
            assert status[import_name]["available"] is False, (
                f"Erwartet: available=False fuer '{import_name}', "
                f"Erhalten: {status[import_name]['available']}"
            )

    @patch("backend.dependency_checker.check_package", return_value=True)
    def test_enthaelt_purpose(self, mock_check):
        """Jeder Eintrag enthaelt das Feld 'purpose'."""
        status = get_dependency_status()

        for import_name, _, purpose in CRITICAL_PACKAGES:
            assert status[import_name]["purpose"] == purpose, (
                f"Erwartet: purpose='{purpose}' fuer '{import_name}', "
                f"Erhalten: '{status[import_name]['purpose']}'"
            )

    @patch("backend.dependency_checker.check_package", return_value=True)
    def test_enthaelt_install_name(self, mock_check):
        """Jeder Eintrag enthaelt das Feld 'install_name'."""
        status = get_dependency_status()

        for import_name, install_name, _ in CRITICAL_PACKAGES:
            assert status[import_name]["install_name"] == install_name, (
                f"Erwartet: install_name='{install_name}' fuer '{import_name}', "
                f"Erhalten: '{status[import_name]['install_name']}'"
            )

    @patch("backend.dependency_checker.check_package", return_value=True)
    def test_anzahl_eintraege(self, mock_check):
        """Status-Dict hat genau so viele Eintraege wie CRITICAL_PACKAGES."""
        status = get_dependency_status()

        assert len(status) == len(CRITICAL_PACKAGES), (
            f"Erwartet: {len(CRITICAL_PACKAGES)} Eintraege, "
            f"Erhalten: {len(status)}"
        )

    @patch("backend.dependency_checker.check_package", return_value=True)
    def test_status_felder_vollstaendig(self, mock_check):
        """Jeder Status-Eintrag hat die Felder available, purpose, install_name."""
        status = get_dependency_status()

        erwartete_felder = {"available", "purpose", "install_name"}
        for import_name in status:
            vorhandene_felder = set(status[import_name].keys())
            assert vorhandene_felder == erwartete_felder, (
                f"Erwartet: Felder {erwartete_felder} fuer '{import_name}', "
                f"Erhalten: {vorhandene_felder}"
            )
