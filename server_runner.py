# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 29.01.2026
Version: 1.1
Beschreibung: Server Runner - Startet Projekt-Server und wartet auf Verfügbarkeit.
              Ermöglicht stabile Tests gegen laufende Server.
              ÄNDERUNG 29.01.2026: app_type-basierte Server-Erkennung (Desktop/CLI brauchen keinen Server)
"""

import os
import socket
import subprocess
import time
import logging
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass
from contextlib import contextmanager

logger = logging.getLogger(__name__)

# Konstanten
DEFAULT_STARTUP_TIMEOUT = 30  # Sekunden
DEFAULT_PORT_CHECK_INTERVAL = 0.5  # Sekunden
DEFAULT_PORT = 5000


@dataclass
class ServerInfo:
    """Informationen über einen laufenden Server."""
    process: subprocess.Popen
    port: int
    url: str
    project_path: str


def is_port_available(port: int, host: str = "localhost") -> bool:
    """
    Prüft ob ein Port bereits belegt ist (Server läuft).

    Args:
        port: Port-Nummer
        host: Hostname (default: localhost)

    Returns:
        True wenn Port erreichbar ist (Server läuft)
    """
    try:
        with socket.create_connection((host, port), timeout=1):
            return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False


def wait_for_port(port: int, timeout: int = DEFAULT_STARTUP_TIMEOUT,
                  interval: float = DEFAULT_PORT_CHECK_INTERVAL,
                  host: str = "localhost") -> bool:
    """
    Wartet bis ein Port erreichbar ist.

    Args:
        port: Port-Nummer
        timeout: Maximale Wartezeit in Sekunden
        interval: Prüf-Intervall in Sekunden
        host: Hostname

    Returns:
        True wenn Port innerhalb des Timeouts erreichbar wurde
    """
    start_time = time.time()
    while time.time() - start_time < timeout:
        if is_port_available(port, host):
            logger.info(f"Port {port} ist jetzt erreichbar (nach {time.time() - start_time:.1f}s)")
            return True
        time.sleep(interval)

    logger.warning(f"Timeout: Port {port} nicht erreichbar nach {timeout}s")
    return False


def detect_server_port(tech_blueprint: Dict[str, Any]) -> int:
    """
    Ermittelt den Server-Port aus dem tech_blueprint.

    Args:
        tech_blueprint: Projekt-Blueprint

    Returns:
        Port-Nummer (oder Default-Port)
    """
    # Expliziter Port im Blueprint
    if "server_port" in tech_blueprint:
        return tech_blueprint["server_port"]

    # Port aus run_command extrahieren
    run_cmd = tech_blueprint.get("run_command", "")

    # Flask Default: 5000
    if "flask" in run_cmd.lower() or tech_blueprint.get("project_type") == "flask_app":
        return 5000

    # FastAPI/Uvicorn Default: 8000
    if "uvicorn" in run_cmd.lower() or "fastapi" in run_cmd.lower():
        return 8000

    # Node Express Default: 3000
    if "node" in run_cmd.lower() or tech_blueprint.get("language") == "javascript":
        return 3000

    # Django Default: 8000
    if "django" in run_cmd.lower() or "manage.py" in run_cmd.lower():
        return 8000

    return DEFAULT_PORT


def detect_test_url(tech_blueprint: Dict[str, Any], port: int) -> str:
    """
    Ermittelt die Test-URL aus dem tech_blueprint.

    Args:
        tech_blueprint: Projekt-Blueprint
        port: Server-Port

    Returns:
        URL für Tests
    """
    # Explizite URL im Blueprint
    if "test_url" in tech_blueprint:
        return tech_blueprint["test_url"]

    project_type = tech_blueprint.get("project_type", "")

    # Statische HTML-Projekte brauchen keinen Server
    if project_type == "static_html":
        return None

    # Server-basierte Projekte
    return f"http://localhost:{port}"


def requires_server(tech_blueprint: Dict[str, Any]) -> bool:
    """
    Prüft ob das Projekt einen laufenden Server benötigt.

    ÄNDERUNG 29.01.2026: Berücksichtigt app_type aus Blueprint.
    Desktop- und CLI-Apps brauchen keinen Server.

    Args:
        tech_blueprint: Projekt-Blueprint

    Returns:
        True wenn Server gestartet werden muss
    """
    project_type = tech_blueprint.get("project_type", "")
    app_type = tech_blueprint.get("app_type", "")

    # ÄNDERUNG 29.01.2026: Desktop und CLI brauchen keinen Server
    if app_type in ["desktop", "cli"]:
        logger.debug(f"app_type={app_type} - kein Server nötig")
        return False

    # Diese Typen brauchen einen Server
    server_types = [
        "flask_app", "fastapi_app", "django_app",
        "nodejs_express", "nodejs_app",
        "webapp"  # Generischer Webapp-Typ
    ]

    # ÄNDERUNG 29.01.2026: Diese Typen brauchen KEINEN Server
    no_server_types = [
        "static_html", "python_cli", "python_script",
        "tkinter_desktop", "pyqt_desktop", "wxpython_desktop",
        "cli_tool", "console_app"
    ]

    if project_type in no_server_types:
        logger.debug(f"project_type={project_type} - kein Server nötig")
        return False

    # Explizite Markierung im Blueprint
    if "requires_server" in tech_blueprint:
        return tech_blueprint["requires_server"]

    # Prüfe ob run_command auf Server hinweist
    run_cmd = tech_blueprint.get("run_command", "")
    server_indicators = ["flask", "uvicorn", "node", "npm start", "python -m http.server"]

    if any(ind in run_cmd.lower() for ind in server_indicators):
        return True

    # Prüfe ob run_command auf Desktop-Frameworks hinweist
    desktop_indicators = ["tkinter", "pyqt", "wxpython", "kivy", "pyside"]
    if any(ind in run_cmd.lower() for ind in desktop_indicators):
        logger.debug(f"Desktop-Framework in run_command erkannt - kein Server nötig")
        return False

    return project_type in server_types


def start_server(project_path: str, tech_blueprint: Dict[str, Any],
                 timeout: int = DEFAULT_STARTUP_TIMEOUT) -> Optional[ServerInfo]:
    """
    Startet den Projekt-Server via run.bat/run_command.

    Args:
        project_path: Pfad zum Projektverzeichnis
        tech_blueprint: Projekt-Blueprint
        timeout: Startup-Timeout in Sekunden

    Returns:
        ServerInfo mit Prozess und URL, oder None bei Fehler
    """
    if not requires_server(tech_blueprint):
        logger.info("Projekt benötigt keinen Server")
        return None

    port = detect_server_port(tech_blueprint)
    url = detect_test_url(tech_blueprint, port)

    # Prüfe ob Port bereits belegt
    if is_port_available(port):
        logger.warning(f"Port {port} bereits belegt - ein Server läuft möglicherweise schon")
        # Wir geben trotzdem ServerInfo zurück, aber ohne eigenen Prozess
        return ServerInfo(process=None, port=port, url=url, project_path=project_path)

    # Bestimme Start-Befehl
    run_bat = os.path.join(project_path, "run.bat")
    run_sh = os.path.join(project_path, "run.sh")
    run_cmd = tech_blueprint.get("run_command", "")

    if os.path.exists(run_bat):
        cmd = run_bat
        shell = True
    elif os.path.exists(run_sh):
        cmd = ["bash", run_sh]
        shell = False
    elif run_cmd:
        cmd = run_cmd
        shell = True
    else:
        logger.error("Kein Startbefehl gefunden (run.bat, run.sh oder run_command)")
        return None

    logger.info(f"Starte Server: {cmd}")

    try:
        # Server im Hintergrund starten
        process = subprocess.Popen(
            cmd,
            cwd=project_path,
            shell=shell,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            # Wichtig: Eigene Prozessgruppe für sauberes Cleanup
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
        )

        # Warte auf Port
        startup_timeout = tech_blueprint.get("server_startup_time_ms", timeout * 1000) / 1000

        if wait_for_port(port, timeout=int(startup_timeout)):
            logger.info(f"Server gestartet auf {url}")
            return ServerInfo(process=process, port=port, url=url, project_path=project_path)
        else:
            # Timeout - Server stoppen
            stop_server(ServerInfo(process=process, port=port, url=url, project_path=project_path))
            logger.error(f"Server-Start fehlgeschlagen (Timeout nach {startup_timeout}s)")
            return None

    except Exception as e:
        logger.error(f"Fehler beim Server-Start: {e}")
        return None


def stop_server(server_info: ServerInfo) -> bool:
    """
    Stoppt einen laufenden Server.

    Args:
        server_info: ServerInfo vom start_server()

    Returns:
        True wenn erfolgreich gestoppt
    """
    if server_info is None or server_info.process is None:
        return True

    try:
        # Unter Windows: taskkill für Prozessgruppe
        if os.name == 'nt':
            subprocess.run(
                ['taskkill', '/F', '/T', '/PID', str(server_info.process.pid)],
                capture_output=True,
                timeout=5
            )
        else:
            # Unix: SIGTERM an Prozessgruppe
            import signal
            os.killpg(os.getpgid(server_info.process.pid), signal.SIGTERM)

        server_info.process.wait(timeout=5)
        logger.info(f"Server gestoppt (PID {server_info.process.pid})")
        return True

    except Exception as e:
        logger.warning(f"Fehler beim Server-Stop: {e}")
        # Versuche force kill
        try:
            server_info.process.kill()
            return True
        except Exception:
            return False


@contextmanager
def managed_server(project_path: str, tech_blueprint: Dict[str, Any],
                   timeout: int = DEFAULT_STARTUP_TIMEOUT):
    """
    Context Manager für sauberes Server-Lifecycle-Management.

    Usage:
        with managed_server(project_path, blueprint) as server:
            if server:
                # Server läuft auf server.url
                test_web_ui(server.url)
            else:
                # Kein Server nötig oder Fehler
                test_web_ui(html_file_path)

    Args:
        project_path: Pfad zum Projektverzeichnis
        tech_blueprint: Projekt-Blueprint
        timeout: Startup-Timeout

    Yields:
        ServerInfo oder None
    """
    server = None
    try:
        server = start_server(project_path, tech_blueprint, timeout)
        yield server
    finally:
        if server:
            stop_server(server)


def get_test_target(project_path: str, tech_blueprint: Dict[str, Any],
                    html_fallback: str = None) -> Tuple[str, bool]:
    """
    Ermittelt das Test-Ziel (URL oder Datei-Pfad).

    Args:
        project_path: Pfad zum Projektverzeichnis
        tech_blueprint: Projekt-Blueprint
        html_fallback: Fallback HTML-Datei

    Returns:
        Tuple von (target, needs_server)
        - target: URL oder Dateipfad
        - needs_server: True wenn Server gestartet werden muss
    """
    if requires_server(tech_blueprint):
        port = detect_server_port(tech_blueprint)
        url = detect_test_url(tech_blueprint, port)
        return (url, True)

    # Statisches Projekt - HTML-Datei verwenden
    if html_fallback:
        return (html_fallback, False)

    # Versuche index.html zu finden
    from file_utils import find_html_file
    html_file = find_html_file(project_path)
    if html_file:
        return (html_file, False)

    return (None, False)
