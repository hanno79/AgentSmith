# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 02.02.2026
Version: 1.1
Beschreibung: Unit-Tests für agents.dependency_checker und agents.dependency_installer.
              AENDERUNG 07.02.2026: Tests fuer shadcn/ui Fix (Multi-Command, npx, Pakettyp)
"""

import pytest
from unittest.mock import patch, MagicMock

from agents.dependency_checker import (
    check_dependency,
    detect_package_type,
    check_python_package,
    check_npm_package,
    check_system_tool,
    compare_versions,
)
from agents.dependency_installer import (
    validate_install_command,
    install_dependencies,
    install_single_package,
)


class TestCompareVersions:
    """Tests für compare_versions (PEP 440 / SemVer)."""

    def test_ascending(self):
        assert compare_versions("1.0.0", "2.0.0") == -1
        assert compare_versions("0.9", "1.0") == -1

    def test_equal(self):
        assert compare_versions("1.0.0", "1.0.0") == 0
        assert compare_versions("2.3", "2.3.0") == 0

    def test_descending(self):
        assert compare_versions("2.0.0", "1.0.0") == 1
        assert compare_versions("1.1", "1.0") == 1

    def test_complex_semver(self):
        # pre-release / post können je nach packaging-Verhalten variieren
        assert compare_versions("1.0.0", "1.0.1") == -1
        assert compare_versions("2.1.3", "2.1.2") == 1

    def test_invalid_versions_fallback(self):
        # Ungültige Strings sollten 0 zurückgeben oder Fallback nutzen
        result = compare_versions("invalid", "1.0")
        assert result in (-1, 0, 1)

    def test_empty_returns_zero(self):
        assert compare_versions("", "1.0") == 0
        assert compare_versions("1.0", "") == 0


class TestDetectPackageType:
    """Tests für detect_package_type."""

    def test_system_tools(self):
        assert detect_package_type("node") == "system"
        assert detect_package_type("npm") == "system"
        assert detect_package_type("python") == "system"

    def test_known_python(self):
        assert detect_package_type("pytest") == "python"
        assert detect_package_type("flask") == "python"

    def test_npm_scoped(self):
        assert detect_package_type("@scope/package") == "npm"

    def test_npm_keywords(self):
        assert detect_package_type("react") == "npm"
        assert detect_package_type("vue") == "npm"

    def test_blueprint_javascript_fallback(self):
        assert detect_package_type("unknown_xyz", blueprint={"language": "javascript"}) == "npm"

    # AENDERUNG 07.02.2026: Neue Tests fuer shadcn/ui Fix
    def test_shadcn_ui_erkennung(self):
        """shadcn-ui muss als npm erkannt werden (in NPM_PACKAGES)."""
        assert detect_package_type("shadcn-ui") == "npm"
        assert detect_package_type("shadcn") == "npm"

    def test_ui_libraries_erkennung(self):
        """Verbreitete UI-Libraries muessen als npm erkannt werden."""
        assert detect_package_type("chakra-ui") == "npm"
        assert detect_package_type("antd") == "npm"
        assert detect_package_type("zustand") == "npm"
        assert detect_package_type("zod") == "npm"
        assert detect_package_type("framer-motion") == "npm"

    def test_radix_scoped_package(self):
        """@radix-ui/* muss als npm erkannt werden (@ Prefix)."""
        assert detect_package_type("@radix-ui/react-slot") == "npm"
        assert detect_package_type("@chakra-ui/react") == "npm"

    def test_blueprint_typescript_fallback(self):
        """TypeScript-Blueprint muss npm zurueckgeben."""
        assert detect_package_type("unknown_xyz", blueprint={"language": "typescript"}) == "npm"

    def test_shadcn_keyword_erkennung(self):
        """shadcn-basierte Pakete muessen ueber Keyword-Matching erkannt werden."""
        assert detect_package_type("my-shadcn-components") == "npm"

    def test_default_python(self):
        assert detect_package_type("unknown_xyz") == "python"


class TestCheckDependency:
    """Tests für check_dependency (mit Mocks)."""

    @patch("agents.dependency_checker.check_python_package")
    def test_check_dependency_python(self, mock_python):
        mock_python.return_value = {"installed": True, "version": "1.0", "meets_requirement": True}
        out = check_dependency("pytest", package_type="python")
        assert out["installed"] is True
        mock_python.assert_called_once_with("pytest", None)

    @patch("agents.dependency_checker.check_npm_package")
    def test_check_dependency_npm(self, mock_npm):
        mock_npm.return_value = {"installed": False, "version": None, "type": "npm"}
        out = check_dependency("react", package_type="npm")
        assert "installed" in out
        mock_npm.assert_called_once()

    @patch("agents.dependency_checker.check_system_tool")
    def test_check_dependency_system(self, mock_sys):
        mock_sys.return_value = {"installed": True, "version": "20.0", "type": "system"}
        out = check_dependency("node", package_type="system")
        assert out["installed"] is True
        mock_sys.assert_called_once_with("node", None)

    def test_check_dependency_unknown_type(self):
        out = check_dependency("xyz", package_type="unknown_type")
        assert out["installed"] is False
        assert "error" in out
        assert "Unbekannter Pakettyp" in out["error"]


class TestCheckPythonPackage:
    """Tests für check_python_package (mit subprocess-Mock)."""

    @patch("agents.dependency_checker.is_builtin_module")
    def test_builtin_module(self, mock_builtin):
        mock_builtin.return_value = True
        out = check_python_package("json")
        assert out["installed"] is True
        assert out.get("version") == "builtin"
        assert out.get("meets_requirement") is True

    @patch("agents.dependency_checker.subprocess.run")
    def test_installed_package(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Name: pytest\nVersion: 7.0.0\n"
        )
        out = check_python_package("pytest")
        assert out["installed"] is True
        assert out.get("version") == "7.0.0"

    @patch("agents.dependency_checker.subprocess.run")
    def test_not_installed(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="not found")
        out = check_python_package("nonexistent_pkg_xyz")
        assert out["installed"] is False


class TestCheckNpmPackage:
    """Tests für check_npm_package (mit Mocks)."""

    @patch("agents.dependency_checker.shutil.which")
    def test_npm_not_found(self, mock_which):
        mock_which.return_value = None
        out = check_npm_package("react")
        assert out["installed"] is False
        assert "error" in out

    @patch("agents.dependency_checker.subprocess.run")
    @patch("agents.dependency_checker.shutil.which")
    def test_npm_package_present(self, mock_which, mock_run):
        mock_which.return_value = "/usr/bin/npm"
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='{"dependencies": {"react": {"version": "18.0.0"}}}'
        )
        out = check_npm_package("react", npm_path="/usr/bin/npm")
        assert out["installed"] is True
        assert out.get("version") == "18.0.0"


class TestCheckSystemTool:
    """Tests für check_system_tool (mit shutil.which Mock)."""

    @patch("agents.dependency_checker.shutil.which")
    def test_tool_absent(self, mock_which):
        mock_which.return_value = None
        out = check_system_tool("nonexistent_tool_xyz")
        assert out["installed"] is False

    @patch("agents.dependency_checker.subprocess.run")
    @patch("agents.dependency_checker.shutil.which")
    def test_tool_present(self, mock_which, mock_run):
        mock_which.return_value = "/usr/bin/git"
        mock_run.return_value = MagicMock(returncode=0, stdout="git version 2.30.0")
        out = check_system_tool("git")
        assert out["installed"] is True
        assert "path" in out
        assert out["path"] == "/usr/bin/git"


# =========================================================================
# AENDERUNG 07.02.2026: Tests fuer dependency_installer (shadcn/ui Fix)
# =========================================================================

class TestValidateInstallCommand:
    """Tests fuer validate_install_command Whitelist."""

    def test_npm_install_erlaubt(self):
        parts = validate_install_command("npm install")
        assert parts[0] == "npm"
        assert parts[1] == "install"

    def test_pip_install_erlaubt(self):
        parts = validate_install_command("pip install requests")
        assert parts[0] == "pip"

    def test_npx_erlaubt(self):
        """npx muss als erlaubter Befehl erkannt werden."""
        parts = validate_install_command("npx shadcn-ui@latest init")
        assert parts[0] == "npx"
        assert "shadcn-ui@latest" in parts[1]

    def test_und_verkettung_blockiert(self):
        """&& muss weiterhin in validate_install_command blockiert werden."""
        with pytest.raises(ValueError, match="unzulässige Zeichen"):
            validate_install_command("npm install && npx shadcn init")

    def test_npx_ohne_paket_blockiert(self):
        """npx ohne Paketname muss blockiert werden."""
        with pytest.raises(ValueError):
            validate_install_command("npx")

    def test_unbekannter_befehl_blockiert(self):
        with pytest.raises(ValueError, match="Befehl nicht erlaubt"):
            validate_install_command("curl http://example.com")


class TestInstallDependenciesMultiCommand:
    """Tests fuer Multi-Command-Split bei install_dependencies."""

    @patch("agents.dependency_installer.subprocess.run")
    def test_multi_command_split(self, mock_run):
        """install_command mit && wird in einzelne Befehle gesplittet."""
        mock_run.return_value = MagicMock(returncode=0, stdout="OK", stderr="")
        result = install_dependencies(
            "npm install && npx shadcn-ui@latest init",
            project_path=None
        )
        assert result["status"] == "OK"
        assert mock_run.call_count == 2

    @patch("agents.dependency_installer.subprocess.run")
    def test_multi_command_erster_fehler_bricht_ab(self, mock_run):
        """Bei Fehler im ersten Teilbefehl wird abgebrochen."""
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="Fehler")
        result = install_dependencies(
            "npm install && npx shadcn-ui@latest init",
            project_path=None
        )
        assert result["status"] == "FAIL"
        assert mock_run.call_count == 1

    def test_einzelner_befehl_kein_split(self):
        """Einfacher Befehl ohne && wird nicht gesplittet."""
        result = install_dependencies("", project_path=None)
        assert result["status"] == "SKIP"


class TestInstallSinglePackageNpm:
    """Tests fuer install_single_package npm-Aenderungen."""

    @patch("agents.dependency_installer.os.path.isdir", return_value=True)
    @patch("agents.dependency_installer.subprocess.run")
    def test_lokal_statt_global(self, mock_run, mock_isdir):
        """npm-Pakete muessen lokal installiert werden (kein -g)."""
        mock_run.return_value = MagicMock(returncode=0, stdout="OK", stderr="")
        install_single_package("react", package_type="npm",
                               npm_path="/usr/bin/npm", project_path="/tmp/test")
        call_args = mock_run.call_args[0][0]
        assert "-g" not in call_args, "npm install darf kein -g Flag enthalten"
        assert mock_run.call_args[1].get("cwd") == "/tmp/test"

    @patch("agents.dependency_installer.subprocess.run")
    def test_scoped_package_normalisierung(self, mock_run):
        """shadcn/ui wird zu shadcn-ui normalisiert."""
        mock_run.return_value = MagicMock(returncode=0, stdout="OK", stderr="")
        install_single_package("shadcn/ui", package_type="npm",
                               npm_path="/usr/bin/npm", project_path="/tmp/test")
        call_args = mock_run.call_args[0][0]
        assert "shadcn-ui" in call_args, "shadcn/ui muss zu shadcn-ui normalisiert werden"

    @patch("agents.dependency_installer.subprocess.run")
    def test_echte_scoped_packages_unveraendert(self, mock_run):
        """@radix-ui/react-slot bleibt unveraendert (echtes Scoped Package)."""
        mock_run.return_value = MagicMock(returncode=0, stdout="OK", stderr="")
        install_single_package("@radix-ui/react-slot", package_type="npm",
                               npm_path="/usr/bin/npm", project_path="/tmp/test")
        call_args = mock_run.call_args[0][0]
        assert "@radix-ui/react-slot" in call_args

    def test_npm_nicht_verfuegbar(self):
        """Ohne npm-Pfad wird SKIPPED zurueckgegeben."""
        result = install_single_package("react", package_type="npm", npm_path=None)
        assert result["status"] == "SKIPPED"
