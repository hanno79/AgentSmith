# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 14.02.2026
Version: 1.0
Beschreibung: Tests fuer backend/routers/dependencies.py —
              Whitelist-Validierung und Dependency-Endpoints.
"""
# ÄNDERUNG 24.02.2026: Header ergänzt und Testabdeckung für get_dependency_agent bei ImportError dokumentiert.

import pytest
from unittest.mock import MagicMock, patch
from fastapi import HTTPException


# =========================================================================
# TestValidateInstallCommand
# =========================================================================

class TestValidateInstallCommand:
    """Tests fuer _validate_install_command() — Whitelist-Validierung."""

    @pytest.fixture(autouse=True)
    def _patch_app_state(self):
        """Mocke app_state Importe bevor Router geladen wird."""
        with patch("backend.routers.dependencies.manager") as mock_mgr, \
             patch("backend.routers.dependencies.limiter"):
            mock_mgr.config = {}
            yield

    def _validate(self, cmd):
        from backend.routers.dependencies import _validate_install_command
        return _validate_install_command(cmd)

    def test_pip_install_gueltig(self):
        """pip install pytest ist gueltig."""
        result = self._validate("pip install pytest")
        assert result == ["pip", "install", "pytest"]

    def test_pip_install_mehrere_pakete(self):
        """pip install mit mehreren Paketen ist gueltig."""
        result = self._validate("pip install pytest requests flask")
        assert len(result) == 5

    def test_pip_install_mit_version(self):
        """pip install paket==1.0.0 ist gueltig."""
        result = self._validate("pip install requests==2.31.0")
        assert "requests==2.31.0" in result

    def test_python_m_pip_install(self):
        """python -m pip install ist gueltig."""
        result = self._validate("python -m pip install pytest")
        assert result[0] == "python"

    def test_npm_install_gueltig(self):
        """npm install react ist gueltig."""
        result = self._validate("npm install react")
        assert result == ["npm", "install", "react"]

    def test_npm_i_kurzform(self):
        """npm i (Kurzform) ist gueltig."""
        result = self._validate("npm i lodash")
        assert result == ["npm", "i", "lodash"]

    def test_npm_scoped_package(self):
        """npm install @next/jest ist gueltig."""
        result = self._validate("npm install @next/jest")
        assert "@next/jest" in result

    def test_leerer_command_abgelehnt(self):
        """Leerer Command wird abgelehnt."""
        with pytest.raises(HTTPException) as exc_info:
            self._validate("")
        assert exc_info.value.status_code == 400

    def test_nur_whitespace_abgelehnt(self):
        """Nur Whitespace wird abgelehnt."""
        with pytest.raises(HTTPException) as exc_info:
            self._validate("   ")
        assert exc_info.value.status_code == 400

    def test_command_injection_ampersand(self):
        """&& Command-Injection wird blockiert."""
        with pytest.raises(HTTPException) as exc_info:
            self._validate("pip install pytest && rm -rf /")
        assert "unzulässige Zeichen" in exc_info.value.detail

    def test_command_injection_semicolon(self):
        """; Command-Injection wird blockiert."""
        with pytest.raises(HTTPException) as exc_info:
            self._validate("pip install pytest; cat /etc/passwd")
        assert exc_info.value.status_code == 400

    def test_command_injection_pipe(self):
        """| Pipe-Injection wird blockiert."""
        with pytest.raises(HTTPException) as exc_info:
            self._validate("pip install pytest | grep x")
        assert exc_info.value.status_code == 400

    def test_command_injection_backtick(self):
        """` Backtick-Injection wird blockiert."""
        with pytest.raises(HTTPException) as exc_info:
            self._validate("pip install `whoami`")
        assert exc_info.value.status_code == 400

    def test_unerlaubter_befehl(self):
        """Nicht-whitelisted Befehl wird abgelehnt."""
        with pytest.raises(HTTPException) as exc_info:
            self._validate("curl http://evil.com")
        assert "nicht erlaubt" in exc_info.value.detail

    def test_pip_ohne_install(self):
        """pip ohne install Subcommand wird abgelehnt."""
        with pytest.raises(HTTPException) as exc_info:
            self._validate("pip uninstall pytest")
        assert exc_info.value.status_code == 400

    def test_npm_ohne_install(self):
        """npm ohne install/i wird abgelehnt."""
        with pytest.raises(HTTPException) as exc_info:
            self._validate("npm uninstall react")
        assert exc_info.value.status_code == 400

    def test_flags_verboten(self):
        """Flags wie --force werden abgelehnt."""
        with pytest.raises(HTTPException) as exc_info:
            self._validate("pip install --force pytest")
        assert "keine Flags" in exc_info.value.detail

    def test_python_m_pip_ohne_install(self):
        """python -m pip ohne install wird abgelehnt."""
        with pytest.raises(HTTPException) as exc_info:
            self._validate("python -m pip list")
        assert exc_info.value.status_code == 400


# =========================================================================
# TestDependencyEndpoints
# =========================================================================

class TestDependencyEndpoints:
    """Tests fuer Dependency API-Endpoints mit gemocktem Agent."""

    @pytest.fixture(autouse=True)
    def _patch_deps(self):
        """Mocke alle externen Dependencies."""
        with patch("backend.routers.dependencies.manager") as mock_mgr, \
             patch("backend.routers.dependencies.limiter"), \
             patch("backend.routers.dependencies.log_event"):
            mock_mgr.config = {"dependency_agent": {}}
            self.mock_manager = mock_mgr
            yield

    def test_get_dependency_agent_none_bei_import_fehler(self):
        """get_dependency_agent gibt None bei Import-Fehler."""
        import backend.routers.dependencies as dep_mod
        dep_mod._dependency_agent = None
        with patch("agents.dependency_agent.DependencyAgent", side_effect=ImportError("not found")):
            # Import schlaegt fehl → None
            result = dep_mod.get_dependency_agent()
            assert result is None

    def test_inventory_endpoint_agent_nicht_verfuegbar(self):
        """Inventory gibt 503 wenn Agent None."""
        from backend.routers.dependencies import get_dependency_inventory
        with patch("backend.routers.dependencies.get_dependency_agent", return_value=None):
            with pytest.raises(HTTPException) as exc_info:
                get_dependency_inventory()
            assert exc_info.value.status_code == 503

    def test_inventory_endpoint_erfolg(self):
        """Inventory gibt Ergebnis bei verfuegbarem Agent."""
        mock_agent = MagicMock()
        mock_agent.get_inventory.return_value = {"python": {"packages": ["pytest"]}}
        from backend.routers.dependencies import get_dependency_inventory
        with patch("backend.routers.dependencies.get_dependency_agent", return_value=mock_agent):
            result = get_dependency_inventory()
            assert result["status"] == "ok"
            assert "inventory" in result

    def test_check_dependency_nicht_verfuegbar(self):
        """Check gibt 503 wenn Agent None."""
        from backend.routers.dependencies import check_dependency
        with patch("backend.routers.dependencies.get_dependency_agent", return_value=None):
            with pytest.raises(HTTPException) as exc_info:
                check_dependency("pytest")
            assert exc_info.value.status_code == 503

    def test_check_dependency_erfolg(self):
        """Check gibt Ergebnis bei verfuegbarem Agent."""
        mock_agent = MagicMock()
        mock_agent.check_dependency.return_value = {"installed": True, "version": "7.0"}
        from backend.routers.dependencies import check_dependency
        with patch("backend.routers.dependencies.get_dependency_agent", return_value=mock_agent):
            result = check_dependency("pytest", "python", "7.0")
            assert result["status"] == "ok"
            assert result["package"] == "pytest"

    def test_scan_endpoint_nicht_verfuegbar(self):
        """Scan gibt 503 wenn Agent None."""
        from backend.routers.dependencies import scan_dependencies
        with patch("backend.routers.dependencies.get_dependency_agent", return_value=None):
            with pytest.raises(HTTPException) as exc_info:
                scan_dependencies()
            assert exc_info.value.status_code == 503

    def test_health_endpoint_erfolg(self):
        """Health gibt Score bei verfuegbarem Agent."""
        mock_agent = MagicMock()
        mock_agent.get_inventory.return_value = {
            "health_score": 95,
            "python": {"packages": ["a", "b"]},
            "npm": {"packages": ["c"]},
            "system": {"git": True},
            "last_updated": "2026-02-14"
        }
        from backend.routers.dependencies import get_dependency_health
        with patch("backend.routers.dependencies.get_dependency_agent", return_value=mock_agent):
            result = get_dependency_health()
            assert result["health_score"] == 95
            assert result["python_packages"] == 2
            assert result["npm_packages"] == 1

    def test_vulnerabilities_nicht_verfuegbar(self):
        """Vulnerabilities gibt 503 wenn Agent None."""
        from backend.routers.dependencies import get_dependency_vulnerabilities
        with patch("backend.routers.dependencies.get_dependency_agent", return_value=None):
            with pytest.raises(HTTPException) as exc_info:
                get_dependency_vulnerabilities()
            assert exc_info.value.status_code == 503
