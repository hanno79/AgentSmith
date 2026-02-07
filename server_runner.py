# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 29.01.2026
Version: 1.2
Beschreibung: Server Runner - Startet Projekt-Server und wartet auf Verfügbarkeit.
              Ermöglicht stabile Tests gegen laufende Server.
              ÄNDERUNG 29.01.2026: app_type-basierte Server-Erkennung (Desktop/CLI brauchen keinen Server)
              ÄNDERUNG 06.02.2026: Pre-Server Dependency-Installation, Framework-aware Timeouts,
                                   App-Readiness-Check nach Port-Bind (Root-Cause-Fix für Next.js-Fehler)
"""

import os
import json
import re
import socket
import subprocess
import time
import logging
import urllib.request
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass
from contextlib import contextmanager

logger = logging.getLogger(__name__)

# Konstanten
DEFAULT_STARTUP_TIMEOUT = 30  # Sekunden
DEFAULT_PORT_CHECK_INTERVAL = 0.5  # Sekunden
DEFAULT_PORT = 5000

# ÄNDERUNG 07.02.2026: Framework-basierte Startup-Timeouts (erweitert fuer alle Sprachen)
# Node.js-Projekte brauchen deutlich mehr Zeit (npm install + Compile)
# JVM-basierte Projekte (Spring, Java, Kotlin) brauchen am laengsten
FRAMEWORK_STARTUP_TIMEOUTS = {
    "nodejs": 90, "nextjs": 90, "react": 90, "vue": 90, "angular": 90,
    "python": 30, "flask": 30, "fastapi": 30, "django": 45,
    "spring": 120, "java": 120, "kotlin": 120,
    "go": 15, "rust": 15,
    "rails": 60, "ruby": 60,
    "laravel": 60, "php": 60,
    "dotnet": 90, "csharp": 90,
    "default": 45,
}

# AENDERUNG 07.02.2026: Dependency-Installer Dispatch-Tabelle
# Erweitert von 2 Sprachen (npm, pip) auf 9 Sprachen
DEPENDENCY_INSTALLERS = {
    "javascript": {"check_file": "package.json", "check_dir": "node_modules", "cmd": ["npm", "install"]},
    "typescript": {"check_file": "package.json", "check_dir": "node_modules", "cmd": ["npm", "install"]},
    "python": {"check_file": "requirements.txt", "cmd": ["pip", "install", "-r", "requirements.txt"]},
    "java": {"check_file": "pom.xml", "cmd": ["mvn", "install", "-DskipTests"]},
    "kotlin": {"check_file": "build.gradle.kts", "cmd": ["gradle", "build", "-x", "test"]},
    "go": {"check_file": "go.mod", "cmd": ["go", "mod", "download"]},
    "rust": {"check_file": "Cargo.toml", "cmd": ["cargo", "build"]},
    "ruby": {"check_file": "Gemfile", "check_dir": "vendor", "cmd": ["bundle", "install"]},
    "csharp": {"check_file": "*.csproj", "cmd": ["dotnet", "restore"]},
    "php": {"check_file": "composer.json", "check_dir": "vendor", "cmd": ["composer", "install"]},
}


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


# ÄNDERUNG 06.02.2026: Hilfsfunktionen fuer robusteren Server-Start


def _detect_framework_key(tech_blueprint: Dict[str, Any]) -> str:
    """
    Erkennt Framework-Key für Timeout-Lookup.

    Args:
        tech_blueprint: Projekt-Blueprint

    Returns:
        Key aus FRAMEWORK_STARTUP_TIMEOUTS
    """
    language = tech_blueprint.get("language", "").lower()
    project_type = tech_blueprint.get("project_type", "").lower()
    framework = tech_blueprint.get("framework", "").lower()

    for key in [framework, project_type, language]:
        if key in FRAMEWORK_STARTUP_TIMEOUTS:
            return key
        if any(n in key for n in ["node", "next", "react", "vue", "angular", "express"]):
            return "nodejs"
        if "python" in key or key in ["flask", "fastapi", "django"]:
            return "python"
    return "default"


def _normalize_package_json_versions(project_path: str) -> None:
    """
    AENDERUNG 07.02.2026: Entfernt ^ und ~ Prefixe aus package.json Versionen.
    ROOT-CAUSE-FIX: Coder generiert "next": "^13.5.6" → npm installiert 16.x statt 13.x
    Symptom: Turbopack-Crash weil Next.js 16 inkompatibel mit Pages-Router Setup
    Ursache: Caret-Range ^13.x erlaubt npm freie Versions-Wahl jenseits Major-Version
    Loesung: System-Level Version-Pinning BEVOR npm install laeuft — unabhaengig vom Coder
    """
    pkg_path = os.path.join(project_path, "package.json")
    if not os.path.exists(pkg_path):
        return
    try:
        with open(pkg_path, "r", encoding="utf-8") as f:
            pkg = json.load(f)
        changed = False
        for dep_key in ("dependencies", "devDependencies", "peerDependencies"):
            deps = pkg.get(dep_key)
            if not deps or not isinstance(deps, dict):
                continue
            for name, version in list(deps.items()):
                if isinstance(version, str) and version and version[0] in ("^", "~"):
                    deps[name] = version[1:]
                    changed = True
        if changed:
            with open(pkg_path, "w", encoding="utf-8") as f:
                json.dump(pkg, f, indent=2, ensure_ascii=False)
            logger.info("package.json: Caret/Tilde-Versionen auf exakte Versionen normalisiert")
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"package.json Version-Normalisierung fehlgeschlagen: {e}")


def _install_dependencies(project_path: str, tech_blueprint: Dict[str, Any]) -> bool:
    """
    Installiert Projekt-Dependencies vor Server-Start.
    AENDERUNG 07.02.2026: Dispatch-Tabelle statt hardcoded if/elif.
    Unterstuetzt: npm, pip, mvn, gradle, go mod, cargo, bundle, dotnet, composer.
    """
    # AENDERUNG 07.02.2026: Version-Normalisierung VOR npm install
    # Entfernt ^ und ~ aus package.json → verhindert unkontrollierte Major-Version-Spruenge
    _normalize_package_json_versions(project_path)

    language = tech_blueprint.get("language", "").lower()
    project_type = tech_blueprint.get("project_type", "").lower()

    # Sprache bestimmen (Node.js Frameworks auf "javascript" mappen)
    effective_language = language
    if any(n in project_type for n in ["node", "next", "react", "vue", "angular", "express"]):
        effective_language = "javascript"

    # Installer-Config aus Dispatch-Tabelle holen
    installer = DEPENDENCY_INSTALLERS.get(effective_language)
    if not installer:
        logger.debug(f"Kein Dependency-Installer fuer Sprache: {effective_language}")
        return True

    check_file = installer.get("check_file", "")
    check_dir = installer.get("check_dir")
    cmd = installer.get("cmd", [])

    # Pruefen ob check_file existiert (Wildcard-Support fuer *.csproj)
    import glob as glob_mod
    if "*" in check_file:
        found_files = glob_mod.glob(os.path.join(project_path, check_file))
        if not found_files:
            return True  # Keine passende Datei -> nichts zu installieren
    else:
        if not os.path.exists(os.path.join(project_path, check_file)):
            return True  # Check-Datei fehlt -> nichts zu installieren

    # Pruefen ob Dependencies bereits installiert (check_dir)
    if check_dir and os.path.exists(os.path.join(project_path, check_dir)):
        logger.debug(f"Dependencies bereits installiert ({check_dir} existiert)")
        return True

    logger.info(f"{effective_language}-Projekt: Fuehre {' '.join(cmd)} aus...")
    try:
        result = subprocess.run(
            cmd,
            cwd=project_path, capture_output=True, text=True,
            timeout=120, shell=(os.name == 'nt')
        )
        if result.returncode != 0:
            logger.error(f"{cmd[0]} fehlgeschlagen: {result.stderr[:500]}")
            return False
        logger.info(f"{cmd[0]} erfolgreich")
    except subprocess.TimeoutExpired:
        logger.error(f"{cmd[0]} Timeout nach 120s")
        return False
    except FileNotFoundError:
        logger.warning(f"{cmd[0]} nicht gefunden - uebersprungen (Tool nicht installiert)")
        return True  # Graceful: Tool nicht installiert ist kein Fehler
    except Exception as e:
        logger.warning(f"{cmd[0]} Fehler: {e}")

    return True


def _wait_for_app_ready(url: str, timeout: int = 15) -> bool:
    """
    Wartet bis die App tatsaechlich Inhalt liefert (nicht nur Port offen).
    Verhindert "leere Seite" bei Next.js/React wo Port gebunden aber App noch kompiliert.
    """
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            response = urllib.request.urlopen(url, timeout=3)
            content = response.read().decode("utf-8", errors="ignore")
            if len(content) > 100 and ("<div" in content or "<html" in content):
                logger.info(f"App bereit nach {time.time() - start_time:.1f}s")
                return True
        except Exception:
            pass
        time.sleep(1)

    logger.warning(f"App-Readiness-Timeout nach {timeout}s - Test wird trotzdem versucht")
    return False


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

    # ÄNDERUNG 06.02.2026: Dependencies vor Server-Start installieren
    if not _install_dependencies(project_path, tech_blueprint):
        logger.error("Dependency-Installation fehlgeschlagen - Server-Start abgebrochen")
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

        # ÄNDERUNG 06.02.2026: Framework-basierter Timeout statt hartem 30s Default
        # ROOT-CAUSE-FIX 06.02.2026 (v2):
        # Symptom: Server-Start scheiterte mit 3s Timeout bei Next.js
        # Ursache: TechStack-Agent generiert server_startup_time_ms: 3000 (Beispiel-Wert)
        #          -> 3s Timeout, FRAMEWORK_STARTUP_TIMEOUTS (90s) wurde NIE erreicht
        # Loesung: max(blueprint_wert, framework_minimum) - Blueprint darf nur ERHOEHEN, nicht senken
        framework_key = _detect_framework_key(tech_blueprint)
        framework_timeout = FRAMEWORK_STARTUP_TIMEOUTS.get(
            framework_key, FRAMEWORK_STARTUP_TIMEOUTS["default"]
        )
        blueprint_timeout_ms = tech_blueprint.get("server_startup_time_ms")
        if blueprint_timeout_ms is not None:
            blueprint_timeout = blueprint_timeout_ms / 1000
            startup_timeout = max(blueprint_timeout, framework_timeout)
            if blueprint_timeout < framework_timeout:
                logger.warning(
                    f"Blueprint-Timeout ({blueprint_timeout}s) unter Framework-Minimum "
                    f"({framework_timeout}s fuer {framework_key}) - verwende {startup_timeout}s"
                )
        else:
            startup_timeout = framework_timeout

        logger.info(f"Server-Timeout: {startup_timeout}s")

        if wait_for_port(port, timeout=int(startup_timeout)):
            # ÄNDERUNG 06.02.2026: Warte auf tatsaechliche App-Bereitschaft
            _wait_for_app_ready(url, timeout=15)
            logger.info(f"Server gestartet auf {url}")
            return ServerInfo(process=process, port=port, url=url, project_path=project_path)
        else:
            # ÄNDERUNG 06.02.2026: stderr-Capture fuer bessere Fehler-Diagnostik
            stderr_output = ""
            try:
                if process.stderr:
                    stderr_output = process.stderr.read(500).decode("utf-8", errors="ignore")
            except Exception:
                pass
            stop_server(ServerInfo(process=process, port=port, url=url, project_path=project_path))
            error_msg = f"Server-Start fehlgeschlagen (Timeout nach {startup_timeout}s)"
            if stderr_output:
                error_msg += f". stderr: {stderr_output.strip()}"
            logger.error(error_msg)
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
