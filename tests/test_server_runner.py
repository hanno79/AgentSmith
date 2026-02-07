# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 06.02.2026
Version: 1.0
Beschreibung: Unit Tests fuer server_runner.py - Server-Lifecycle-Management.
              Testet: Framework-Erkennung, Dependency-Installation,
              App-Readiness-Check, Port-Erkennung, Server-Start-Logik.
"""

import os
import sys
import json
import socket
import pytest
import subprocess
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server_runner import (
    _detect_framework_key,
    _install_dependencies,
    _wait_for_app_ready,
    is_port_available,
    wait_for_port,
    detect_server_port,
    detect_test_url,
    requires_server,
    start_server,
    stop_server,
    get_test_target,
    FRAMEWORK_STARTUP_TIMEOUTS,
    DEFAULT_STARTUP_TIMEOUT,
    DEFAULT_PORT,
    ServerInfo,
)


# =========================================================================
# Tests fuer FRAMEWORK_STARTUP_TIMEOUTS Konstante
# =========================================================================
class TestFrameworkStartupTimeouts:
    """Tests fuer die Framework-Timeout-Konfiguration."""

    def test_nodejs_timeout_90s(self):
        """Node.js bekommt 90s Timeout (Compile-Zeit)."""
        assert FRAMEWORK_STARTUP_TIMEOUTS["nodejs"] == 90

    def test_python_timeout_30s(self):
        """Python bekommt 30s Timeout."""
        assert FRAMEWORK_STARTUP_TIMEOUTS["python"] == 30

    def test_default_timeout_45s(self):
        """Unbekannte Frameworks bekommen 45s Default."""
        assert FRAMEWORK_STARTUP_TIMEOUTS["default"] == 45

    def test_react_timeout_90s(self):
        """React bekommt 90s wie alle Node.js-Varianten."""
        assert FRAMEWORK_STARTUP_TIMEOUTS["react"] == 90

    def test_alle_node_varianten_gleich(self):
        """Alle Node.js-Varianten haben gleichen Timeout."""
        node_keys = ["nodejs", "nextjs", "react", "vue", "angular"]
        for key in node_keys:
            assert FRAMEWORK_STARTUP_TIMEOUTS[key] == 90, f"{key} sollte 90s haben"


# =========================================================================
# Tests fuer _detect_framework_key
# =========================================================================
class TestDetectFrameworkKey:
    """Tests fuer Framework-Erkennung aus Blueprint."""

    def test_nextjs_erkannt(self):
        """Next.js wird korrekt als nextjs erkannt."""
        bp = {"language": "javascript", "project_type": "nodejs_app", "framework": "nextjs"}
        assert _detect_framework_key(bp) == "nextjs"

    def test_react_erkannt(self):
        """React wird korrekt erkannt."""
        bp = {"language": "javascript", "project_type": "react_app", "framework": "react"}
        assert _detect_framework_key(bp) == "react"

    def test_express_als_nodejs(self):
        """Express wird als nodejs erkannt."""
        bp = {"language": "javascript", "project_type": "nodejs_express", "framework": "express"}
        assert _detect_framework_key(bp) == "nodejs"

    def test_flask_als_flask(self):
        """Flask wird als flask erkannt (eigener Timeout-Key seit 07.02.2026)."""
        bp = {"language": "python", "project_type": "flask_app", "framework": "flask"}
        assert _detect_framework_key(bp) == "flask"

    def test_fastapi_als_fastapi(self):
        """FastAPI wird als fastapi erkannt (eigener Timeout-Key seit 07.02.2026)."""
        bp = {"language": "python", "project_type": "fastapi_app", "framework": "fastapi"}
        assert _detect_framework_key(bp) == "fastapi"

    def test_django_als_django(self):
        """Django wird als django erkannt (eigener Timeout-Key seit 07.02.2026)."""
        bp = {"language": "python", "project_type": "django_app", "framework": "django"}
        assert _detect_framework_key(bp) == "django"

    def test_ruby_als_ruby(self):
        """Ruby wird als ruby erkannt (eigener Timeout-Key seit 07.02.2026)."""
        bp = {"language": "ruby", "project_type": "ruby_app", "framework": ""}
        assert _detect_framework_key(bp) == "ruby"

    def test_go_als_go(self):
        """Go wird als go erkannt (eigener Timeout-Key seit 07.02.2026)."""
        bp = {"language": "go", "project_type": "go_app", "framework": ""}
        assert _detect_framework_key(bp) == "go"

    def test_leeres_blueprint(self):
        """Leeres Blueprint liefert default."""
        bp = {"language": "", "project_type": "", "framework": ""}
        assert _detect_framework_key(bp) == "default"

    def test_vue_erkannt(self):
        """Vue wird korrekt als nodejs erkannt."""
        bp = {"language": "javascript", "project_type": "vue_app", "framework": "vue"}
        assert _detect_framework_key(bp) == "vue"

    def test_angular_erkannt(self):
        """Angular wird korrekt erkannt."""
        bp = {"language": "javascript", "project_type": "angular_app", "framework": "angular"}
        assert _detect_framework_key(bp) == "angular"

    def test_timeout_lookup_nodejs(self):
        """Timeout-Lookup ergibt 90s fuer Node.js."""
        bp = {"language": "javascript", "project_type": "nodejs_app", "framework": "nextjs"}
        key = _detect_framework_key(bp)
        timeout = FRAMEWORK_STARTUP_TIMEOUTS.get(key, FRAMEWORK_STARTUP_TIMEOUTS["default"])
        assert timeout == 90

    def test_timeout_lookup_python(self):
        """Timeout-Lookup ergibt 30s fuer Python."""
        bp = {"language": "python", "project_type": "flask_app", "framework": "flask"}
        key = _detect_framework_key(bp)
        timeout = FRAMEWORK_STARTUP_TIMEOUTS.get(key, FRAMEWORK_STARTUP_TIMEOUTS["default"])
        assert timeout == 30

    def test_timeout_lookup_go(self):
        """Timeout-Lookup ergibt 15s fuer Go (schneller compilierter Start)."""
        bp = {"language": "go", "project_type": "go_app", "framework": ""}
        key = _detect_framework_key(bp)
        timeout = FRAMEWORK_STARTUP_TIMEOUTS.get(key, FRAMEWORK_STARTUP_TIMEOUTS["default"])
        assert timeout == 15

    def test_timeout_lookup_default(self):
        """Timeout-Lookup ergibt 45s fuer wirklich Unbekanntes."""
        bp = {"language": "brainfuck", "project_type": "bf_app", "framework": ""}
        key = _detect_framework_key(bp)
        timeout = FRAMEWORK_STARTUP_TIMEOUTS.get(key, FRAMEWORK_STARTUP_TIMEOUTS["default"])
        assert timeout == 45


# =========================================================================
# Tests fuer _install_dependencies
# =========================================================================
class TestInstallDependencies:
    """Tests fuer automatische Dependency-Installation."""

    def test_nodejs_mit_package_json_ohne_node_modules(self, temp_dir):
        """Node.js: npm install wird aufgerufen wenn node_modules fehlt."""
        package_json = os.path.join(temp_dir, "package.json")
        with open(package_json, "w") as f:
            json.dump({"name": "test", "dependencies": {}}, f)

        bp = {"language": "javascript", "project_type": "nodejs_app"}

        with patch("server_runner.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = _install_dependencies(temp_dir, bp)
            assert result is True
            mock_run.assert_called_once()
            call_args = mock_run.call_args
            assert call_args[0][0] == ["npm", "install"]

    def test_nodejs_mit_node_modules_kein_install(self, temp_dir):
        """Node.js: npm install wird NICHT aufgerufen wenn node_modules existiert."""
        package_json = os.path.join(temp_dir, "package.json")
        with open(package_json, "w") as f:
            json.dump({"name": "test"}, f)
        os.makedirs(os.path.join(temp_dir, "node_modules"))

        bp = {"language": "javascript", "project_type": "nodejs_app"}

        with patch("server_runner.subprocess.run") as mock_run:
            result = _install_dependencies(temp_dir, bp)
            assert result is True
            mock_run.assert_not_called()

    def test_nodejs_ohne_package_json_kein_install(self, temp_dir):
        """Node.js: npm install wird NICHT aufgerufen ohne package.json."""
        bp = {"language": "javascript", "project_type": "nodejs_app"}

        with patch("server_runner.subprocess.run") as mock_run:
            result = _install_dependencies(temp_dir, bp)
            assert result is True
            mock_run.assert_not_called()

    def test_nodejs_npm_install_fehlgeschlagen(self, temp_dir):
        """Node.js: False bei npm install Fehler."""
        package_json = os.path.join(temp_dir, "package.json")
        with open(package_json, "w") as f:
            json.dump({"name": "test"}, f)

        bp = {"language": "javascript", "project_type": "nodejs_app"}

        with patch("server_runner.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stderr="npm ERR! install failed")
            result = _install_dependencies(temp_dir, bp)
            assert result is False

    def test_python_mit_requirements_txt(self, temp_dir):
        """Python: pip install wird aufgerufen mit requirements.txt."""
        req_txt = os.path.join(temp_dir, "requirements.txt")
        with open(req_txt, "w") as f:
            f.write("flask==3.0.0\n")

        bp = {"language": "python", "project_type": "flask_app"}

        with patch("server_runner.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = _install_dependencies(temp_dir, bp)
            assert result is True
            mock_run.assert_called_once()

    def test_python_ohne_requirements_txt(self, temp_dir):
        """Python: pip install wird NICHT aufgerufen ohne requirements.txt."""
        bp = {"language": "python", "project_type": "flask_app"}

        with patch("server_runner.subprocess.run") as mock_run:
            result = _install_dependencies(temp_dir, bp)
            assert result is True
            mock_run.assert_not_called()

    def test_unbekannte_sprache_kein_install(self, temp_dir):
        """Unbekannte Sprache: Kein Install, return True."""
        bp = {"language": "rust", "project_type": "rust_app"}

        with patch("server_runner.subprocess.run") as mock_run:
            result = _install_dependencies(temp_dir, bp)
            assert result is True
            mock_run.assert_not_called()

    def test_nextjs_erkennung_via_project_type(self, temp_dir):
        """Next.js wird auch ueber project_type erkannt."""
        package_json = os.path.join(temp_dir, "package.json")
        with open(package_json, "w") as f:
            json.dump({"name": "test"}, f)

        bp = {"language": "", "project_type": "nextjs_app"}

        with patch("server_runner.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = _install_dependencies(temp_dir, bp)
            assert result is True
            mock_run.assert_called_once()


# =========================================================================
# Tests fuer _wait_for_app_ready
# =========================================================================
class TestWaitForAppReady:
    """Tests fuer App-Readiness-Check nach Port-Bind."""

    def test_url_liefert_inhalt(self):
        """True wenn URL genug HTML-Inhalt liefert."""
        html = "<html><body><div>Hello World Content</div></body></html>" + "x" * 100

        with patch("server_runner.urllib.request.urlopen") as mock_urlopen:
            mock_response = MagicMock()
            mock_response.read.return_value = html.encode("utf-8")
            mock_urlopen.return_value = mock_response
            result = _wait_for_app_ready("http://localhost:3000", timeout=2)
            assert result is True

    def test_url_nicht_erreichbar(self):
        """False wenn URL nicht erreichbar (mit kurzem Timeout)."""
        with patch("server_runner.urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = Exception("Connection refused")
            result = _wait_for_app_ready("http://localhost:9999", timeout=1)
            assert result is False

    def test_url_liefert_zu_wenig_inhalt(self):
        """False wenn URL zu wenig Inhalt liefert."""
        with patch("server_runner.urllib.request.urlopen") as mock_urlopen:
            mock_response = MagicMock()
            mock_response.read.return_value = b"<html></html>"
            mock_urlopen.return_value = mock_response
            result = _wait_for_app_ready("http://localhost:3000", timeout=1)
            assert result is False


# =========================================================================
# Tests fuer detect_server_port
# =========================================================================
class TestDetectServerPort:
    """Tests fuer Port-Erkennung aus Blueprint."""

    def test_expliziter_port(self):
        """Expliziter Port im Blueprint hat Vorrang."""
        bp = {"server_port": 8080}
        assert detect_server_port(bp) == 8080

    def test_flask_default_5000(self):
        """Flask bekommt Port 5000."""
        bp = {"project_type": "flask_app", "run_command": ""}
        assert detect_server_port(bp) == 5000

    def test_nodejs_default_3000(self):
        """Node.js bekommt Port 3000."""
        bp = {"language": "javascript", "run_command": "node server.js"}
        assert detect_server_port(bp) == 3000

    def test_fastapi_default_8000(self):
        """FastAPI bekommt Port 8000."""
        bp = {"run_command": "uvicorn app:app"}
        assert detect_server_port(bp) == 8000

    def test_default_port(self):
        """Unbekanntes Projekt bekommt Default-Port."""
        bp = {"run_command": ""}
        assert detect_server_port(bp) == DEFAULT_PORT


# =========================================================================
# Tests fuer requires_server
# =========================================================================
class TestRequiresServer:
    """Tests fuer Server-Bedarfserkennung."""

    def test_flask_app_braucht_server(self):
        """Flask-App braucht einen Server."""
        bp = {"project_type": "flask_app", "app_type": "webapp"}
        assert requires_server(bp) is True

    def test_nodejs_app_braucht_server(self):
        """Node.js-App braucht einen Server."""
        bp = {"project_type": "nodejs_app", "app_type": "webapp"}
        assert requires_server(bp) is True

    def test_static_html_braucht_keinen_server(self):
        """Statische HTML braucht keinen Server."""
        bp = {"project_type": "static_html", "app_type": ""}
        assert requires_server(bp) is False

    def test_desktop_app_braucht_keinen_server(self):
        """Desktop-App braucht keinen Server."""
        bp = {"project_type": "tkinter_desktop", "app_type": "desktop"}
        assert requires_server(bp) is False

    def test_cli_app_braucht_keinen_server(self):
        """CLI-App braucht keinen Server."""
        bp = {"project_type": "python_cli", "app_type": "cli"}
        assert requires_server(bp) is False

    def test_explizite_markierung_true(self):
        """Explizite requires_server Markierung wird respektiert."""
        bp = {"project_type": "custom", "app_type": "", "requires_server": True}
        assert requires_server(bp) is True

    def test_explizite_markierung_false(self):
        """Explizite requires_server=False wird respektiert."""
        bp = {"project_type": "webapp", "app_type": "", "requires_server": False}
        assert requires_server(bp) is False

    def test_run_command_erkennung(self):
        """Server wird erkannt wenn run_command auf Server hinweist."""
        bp = {"project_type": "custom", "app_type": "", "run_command": "npm start"}
        assert requires_server(bp) is True


# =========================================================================
# Tests fuer start_server Integration
# =========================================================================
class TestStartServer:
    """Tests fuer die start_server Funktion."""

    def test_kein_server_noetig(self, temp_dir):
        """None wenn Projekt keinen Server braucht."""
        bp = {"project_type": "static_html", "app_type": ""}
        result = start_server(temp_dir, bp)
        assert result is None

    def test_port_bereits_belegt(self, temp_dir):
        """ServerInfo ohne Prozess wenn Port bereits belegt."""
        bp = {"project_type": "flask_app", "app_type": "webapp",
              "language": "python", "run_command": ""}
        with patch("server_runner.is_port_available", return_value=True):
            with patch("server_runner._install_dependencies", return_value=True):
                result = start_server(temp_dir, bp)
                assert result is not None
                assert result.process is None
                assert result.port == 5000

    def test_kein_startbefehl(self, temp_dir):
        """None wenn kein Startbefehl gefunden."""
        bp = {"project_type": "flask_app", "app_type": "webapp",
              "language": "python", "run_command": ""}
        with patch("server_runner.is_port_available", return_value=False):
            with patch("server_runner._install_dependencies", return_value=True):
                result = start_server(temp_dir, bp)
                assert result is None

    def test_dependency_install_fehlschlaegt(self, temp_dir):
        """None wenn Dependency-Installation fehlschlaegt."""
        bp = {"project_type": "nodejs_app", "app_type": "webapp",
              "language": "javascript", "run_command": "npm start"}
        with patch("server_runner._install_dependencies", return_value=False):
            result = start_server(temp_dir, bp)
            assert result is None

    def test_blueprint_timeout_ueberschreibt_default(self, temp_dir):
        """Blueprint server_startup_time_ms hat Vorrang."""
        bp = {
            "project_type": "flask_app", "app_type": "webapp",
            "language": "python", "run_command": "",
            "server_startup_time_ms": 60000
        }
        # Mock um den gesamten Flow zu testen
        with patch("server_runner.is_port_available", return_value=False):
            with patch("server_runner._install_dependencies", return_value=True):
                run_bat = os.path.join(temp_dir, "run.bat")
                with open(run_bat, "w") as f:
                    f.write("echo test")

                mock_process = MagicMock()
                mock_process.stderr = None
                with patch("server_runner.subprocess.Popen", return_value=mock_process):
                    with patch("server_runner.wait_for_port", return_value=False) as mock_wait:
                        start_server(temp_dir, bp)
                        # Timeout sollte 60s sein (60000ms / 1000)
                        mock_wait.assert_called_once_with(5000, timeout=60)


# =========================================================================
# Tests fuer detect_test_url
# =========================================================================
class TestDetectTestUrl:
    """Tests fuer URL-Erkennung."""

    def test_explizite_url(self):
        """Explizite URL wird direkt zurueckgegeben."""
        bp = {"test_url": "http://localhost:8080/api"}
        assert detect_test_url(bp, 3000) == "http://localhost:8080/api"

    def test_standard_url_mit_port(self):
        """Standard-URL wird aus Port generiert."""
        bp = {"project_type": "flask_app"}
        assert detect_test_url(bp, 5000) == "http://localhost:5000"

    def test_static_html_keine_url(self):
        """Statische Projekte liefern None."""
        bp = {"project_type": "static_html"}
        assert detect_test_url(bp, 5000) is None


# =========================================================================
# Tests fuer get_test_target
# =========================================================================
class TestGetTestTarget:
    """Tests fuer Test-Ziel-Ermittlung."""

    def test_server_projekt_liefert_url(self):
        """Server-Projekt liefert URL und needs_server=True."""
        bp = {"project_type": "flask_app", "app_type": "webapp", "run_command": ""}
        target, needs_server = get_test_target("/tmp/test", bp)
        assert needs_server is True
        assert "http://localhost" in target

    def test_html_fallback(self):
        """HTML-Fallback wird verwendet wenn angegeben."""
        bp = {"project_type": "static_html", "app_type": ""}
        target, needs_server = get_test_target("/tmp/test", bp, html_fallback="/tmp/index.html")
        assert needs_server is False
        assert target == "/tmp/index.html"
