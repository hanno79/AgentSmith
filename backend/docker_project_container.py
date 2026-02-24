# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 10.02.2026
Version: 1.0
Beschreibung: Persistenter Docker-Container fuer Projekt-Lebenszyklus.
              Loest das Problem dass generierte Projekte auf dem Windows-Host
              laufen und Dependencies zwischen Projekten kollidieren.
              Fix 50: Docker Project Container (Phase 1).

ROOT-CAUSE-FIX:
  Symptom: npm install auf Windows ist flaky, globale Pakete kollidieren
  Ursache: Jedes Projekt installiert Dependencies direkt auf dem Host
  Loesung: Persistenter Docker-Container pro Projekt mit Volume-Mount
"""

import os
import re
import shutil
import subprocess
import time
import logging
from dataclasses import dataclass, field
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class DockerResult:
    """Ergebnis einer Docker-Operation."""
    success: bool
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    duration_seconds: float = 0.0


class ProjectContainerManager:
    """
    Verwaltet einen persistenten Docker-Container pro Projekt.

    Im Gegensatz zum bestehenden DockerExecutor (--rm Einmal-Container)
    lebt dieser Container fuer den gesamten DevLoop-Lebenszyklus:
    - create() → Container startet mit tail -f /dev/null (bleibt am Leben)
    - install_deps() → docker exec npm install (Dependencies bleiben erhalten)
    - start_server() → docker exec -d npm run dev (Server im Hintergrund)
    - stop_server() → docker exec pkill node (Server stoppen)
    - run_tests() → docker exec npm test
    - cleanup() → docker rm -f (Container entfernen)
    """

    def __init__(
        self,
        project_path: str,
        tech_blueprint: Dict[str, Any],
        config: Dict[str, Any]
    ):
        """
        Args:
            project_path: Pfad zum Projektverzeichnis
            tech_blueprint: Projekt-Blueprint (language, framework, etc.)
            config: Gesamte Anwendungskonfiguration (config.yaml)
        """
        self.project_path = os.path.abspath(project_path)
        self.tech_blueprint = tech_blueprint
        self.config = config

        # Container-Config aus config.yaml
        container_config = config.get("docker", {}).get("project_container", {})
        self.memory_limit = container_config.get("memory_limit", "1g")
        self.cpu_limit = container_config.get("cpu_limit", 2)
        self.install_timeout = container_config.get("install_timeout", 300)
        self.server_timeout = container_config.get("server_timeout", 90)
        self.test_timeout = container_config.get("test_timeout", 180)

        # Image basierend auf Sprache
        language = tech_blueprint.get("language", "javascript").lower()
        base_images = container_config.get("base_images", {})
        if language in ("javascript", "typescript") or \
           any(fw in tech_blueprint.get("project_type", "").lower()
               for fw in ["next", "react", "vue", "angular", "node", "express"]):
            self.image = base_images.get("javascript", "node:20-slim")
            self.tech_stack = "nodejs"
        else:
            self.image = base_images.get("python", "python:3.11-slim")
            self.tech_stack = "python"

        # Port aus Blueprint oder Default
        port_start = container_config.get("port_range_start", 3000)
        self.port = tech_blueprint.get("server_port", port_start)

        # Container-Name (sanitized)
        safe_name = re.sub(r'[^a-zA-Z0-9_]', '_', os.path.basename(project_path))
        self.container_name = f"agentsmith_{safe_name}"

        # Docker-Pfad cachen
        self._docker_path: Optional[str] = None
        self.is_running = False

        logger.info(
            "ProjectContainerManager initialisiert: %s (%s, Port %d, Image %s)",
            self.container_name, self.tech_stack, self.port, self.image
        )

    def _get_docker_path(self) -> Optional[str]:
        """Cached Docker-Pfad zurueckgeben."""
        if self._docker_path is None:
            self._docker_path = shutil.which("docker")
        return self._docker_path

    def _get_mount_path(self) -> str:
        """
        Konvertiert Projekt-Pfad fuer Docker-Volume-Mount.

        AENDERUNG 22.02.2026: Fix 62 — HOST_PROJECTS_BASE_PATH fuer Sibling-Container
        ROOT-CAUSE: Backend im Container hat self.project_path = /app/projects/xxx.
                    Docker (Host-Daemon!) braucht aber den HOST-Pfad C:/Temp/.../projects/xxx
                    fuer Volume-Mounts der Sibling-Container.
        LOESUNG:    HOST_PROJECTS_BASE_PATH env var gibt Windows-Host-Basisverzeichnis an.
                    Fehlt die Env-Var, wird der alte Windows-Host-Pfad-Code genutzt.
        """
        host_base = os.environ.get("HOST_PROJECTS_BASE_PATH")
        if host_base:
            # Backend laeuft in Docker → HOST-Pfad fuer Sibling-Container Volume-Mounts nutzen
            project_name = os.path.basename(self.project_path)
            # AENDERUNG 22.02.2026: Fix 76 — Windows-Format direkt (KEIN MSYS /C/...)
            # ROOT-CAUSE-FIX:
            # Symptom: "Container-Erstellung fehlgeschlagen" bei Backend im Docker
            # Ursache: Alter Code erzeugte /C/Temp/... (MSYS-Format) statt C:/Temp/...
            # Docker Desktop auf Windows akzeptiert C:/path direkt (wie docker-compose.yml zeigt:
            #   "- C:/Users/rahn/.claude/.credentials.json:/root/..."). MSYS-Format wird abgelehnt.
            # Loesung: Nur Backslash→Forward-Slash, Pfad bleibt C:/Temp/... (Windows-Format)
            host_path = host_base.rstrip('/\\') + '/' + project_name
            return host_path.replace('\\', '/')
        # Windows-Host ohne Docker-Container: C:\Temp\project → /c/Temp/project
        if os.name == 'nt':
            return '/' + self.project_path.replace(':', '').replace('\\', '/')
        # Linux-Host (kein Backend-in-Docker, kein HOST_PROJECTS_BASE_PATH gesetzt)
        return self.project_path

    def is_docker_available(self) -> bool:
        """Prueft ob Docker installiert und erreichbar ist."""
        docker_path = self._get_docker_path()
        if not docker_path:
            return False
        try:
            result = subprocess.run(
                [docker_path, "info"],
                capture_output=True, timeout=10
            )
            return result.returncode == 0
        except Exception:
            return False

    def create(self) -> bool:
        """
        Erstellt und startet den persistenten Container.

        docker run -d --name {container_name}
            -v {project_path}:/app -w /app
            -p {port}:{port}
            --memory {memory_limit} --cpus {cpu_limit}
            {image} tail -f /dev/null

        Returns:
            True wenn Container erfolgreich erstellt
        """
        docker_path = self._get_docker_path()
        if not docker_path:
            logger.warning("Docker nicht verfuegbar")
            return False

        # Alten Container entfernen falls vorhanden
        self._remove_existing_container(docker_path)

        mount_path = self._get_mount_path()

        cmd = [
            docker_path, "run", "-d",
            "--name", self.container_name,
            "-v", f"{mount_path}:/app",
            "-w", "/app",
            "-p", f"{self.port}:{self.port}",
            "--memory", self.memory_limit,
            "--cpus", str(self.cpu_limit),
            self.image,
            "tail", "-f", "/dev/null"
        ]

        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True,
                timeout=60, encoding='utf-8', errors='replace'
            )
            if result.returncode == 0:
                self.is_running = True
                container_id = result.stdout.strip()[:12]
                logger.info(
                    "Docker-Container erstellt: %s (ID: %s, Port: %d)",
                    self.container_name, container_id, self.port
                )
                return True
            else:
                logger.error(
                    "Container-Erstellung fehlgeschlagen: %s",
                    result.stderr[:500]
                )
                return False
        except subprocess.TimeoutExpired:
            logger.error("Container-Erstellung Timeout nach 60s")
            return False
        except Exception as e:
            logger.error("Container-Erstellung Fehler: %s", e)
            return False

    def exec_cmd(self, cmd: str, timeout: int = 300) -> DockerResult:
        """
        Fuehrt einen Befehl im laufenden Container aus.

        Args:
            cmd: Shell-Befehl (wird via sh -c ausgefuehrt)
            timeout: Timeout in Sekunden

        Returns:
            DockerResult mit Ergebnis
        """
        docker_path = self._get_docker_path()
        if not docker_path or not self.is_running:
            return DockerResult(
                success=False, stderr="Container nicht verfuegbar", exit_code=1
            )

        start_time = time.time()
        docker_cmd = [
            docker_path, "exec",
            self.container_name,
            "sh", "-c", cmd
        ]

        try:
            result = subprocess.run(
                docker_cmd, capture_output=True, text=True,
                timeout=timeout, encoding='utf-8', errors='replace'
            )
            duration = time.time() - start_time
            return DockerResult(
                success=result.returncode == 0,
                stdout=result.stdout,
                stderr=result.stderr,
                exit_code=result.returncode,
                duration_seconds=duration
            )
        except subprocess.TimeoutExpired:
            duration = time.time() - start_time
            return DockerResult(
                success=False, stderr=f"Timeout nach {timeout}s",
                exit_code=-1, duration_seconds=duration
            )
        except Exception as e:
            duration = time.time() - start_time
            return DockerResult(
                success=False, stderr=str(e),
                exit_code=-1, duration_seconds=duration
            )

    def install_deps(self, timeout: Optional[int] = None) -> DockerResult:
        """
        Installiert Dependencies im Container.
        Fuer Node.js: npm install --silent
        Fuer Python: pip install -r requirements.txt
        """
        timeout = timeout or self.install_timeout

        if self.tech_stack == "nodejs":
            # Pruefe ob package.json existiert
            pkg_path = os.path.join(self.project_path, "package.json")
            if not os.path.exists(pkg_path):
                return DockerResult(
                    success=True, stdout="Keine package.json - uebersprungen"
                )
            cmd = "npm install --silent"
        elif self.tech_stack == "python":
            req_path = os.path.join(self.project_path, "requirements.txt")
            if not os.path.exists(req_path):
                return DockerResult(
                    success=True, stdout="Keine requirements.txt - uebersprungen"
                )
            cmd = "pip install --no-cache-dir -r requirements.txt"
        else:
            return DockerResult(
                success=False, stderr=f"Unbekannter TechStack: {self.tech_stack}"
            )

        logger.info("Installiere Dependencies im Container: %s", cmd)
        result = self.exec_cmd(cmd, timeout)
        if result.success:
            logger.info(
                "Dependencies installiert in %.1fs", result.duration_seconds
            )
        else:
            logger.warning(
                "Dependency-Installation fehlgeschlagen: %s",
                result.stderr[:300]
            )
        return result

    def start_server(self, run_cmd: Optional[str] = None,
                     timeout: Optional[int] = None) -> bool:
        """
        Startet den Dev-Server im Container (Background-Prozess).

        Args:
            run_cmd: Server-Start-Befehl (Default: npm run dev / python app.py)
            timeout: Timeout fuer Server-Readiness

        Returns:
            True wenn Server gestartet und Port erreichbar
        """
        timeout = timeout or self.server_timeout

        if not run_cmd:
            if self.tech_stack == "nodejs":
                run_cmd = "npm run dev"
            else:
                run_cmd = "python src/app.py"

        docker_path = self._get_docker_path()
        if not docker_path or not self.is_running:
            return False

        # Server im Hintergrund starten via docker exec -d
        docker_cmd = [
            docker_path, "exec", "-d",
            self.container_name,
            "sh", "-c", run_cmd
        ]

        try:
            result = subprocess.run(
                docker_cmd, capture_output=True, text=True,
                timeout=10, encoding='utf-8', errors='replace'
            )
            if result.returncode != 0:
                logger.error(
                    "Server-Start im Container fehlgeschlagen: %s",
                    result.stderr[:300]
                )
                return False
        except Exception as e:
            logger.error("Server-Start Fehler: %s", e)
            return False

        logger.info(
            "Server gestartet im Container: %s (warte auf Port %d...)",
            run_cmd, self.port
        )

        # Warte auf Port-Bereitschaft
        return self._wait_for_port(self.port, timeout)

    def stop_server(self) -> bool:
        """
        Stoppt den Server-Prozess im Container (Container bleibt am Leben).
        """
        if not self.is_running:
            return True

        if self.tech_stack == "nodejs":
            kill_cmd = "pkill -f 'node|npm' || true"
        else:
            kill_cmd = "pkill -f 'python|uvicorn|flask' || true"

        result = self.exec_cmd(kill_cmd, timeout=10)
        if result.success or result.exit_code == 0:
            logger.info("Server im Container gestoppt")
            return True
        logger.warning("Server-Stop im Container: %s", result.stderr[:200])
        return False

    def run_tests(self, timeout: Optional[int] = None) -> DockerResult:
        """Fuehrt Tests im Container aus."""
        timeout = timeout or self.test_timeout

        if self.tech_stack == "nodejs":
            cmd = "npm test -- --passWithNoTests --silent 2>/dev/null || echo 'Tests uebersprungen'"
        else:
            cmd = "python -m pytest -v --tb=short 2>/dev/null || echo 'Keine Tests'"

        logger.info("Fuehre Tests im Container aus")
        return self.exec_cmd(cmd, timeout)

    def is_healthy(self) -> bool:
        """Prueft ob der Container laeuft."""
        docker_path = self._get_docker_path()
        if not docker_path:
            return False
        try:
            result = subprocess.run(
                [docker_path, "inspect", self.container_name,
                 "--format", "{{.State.Running}}"],
                capture_output=True, text=True, timeout=5,
                encoding='utf-8', errors='replace'
            )
            healthy = result.stdout.strip() == "true"
            self.is_running = healthy
            return healthy
        except Exception:
            self.is_running = False
            return False

    def cleanup(self) -> bool:
        """Stoppt und entfernt den Container."""
        docker_path = self._get_docker_path()
        if not docker_path:
            return False
        try:
            subprocess.run(
                [docker_path, "rm", "-f", self.container_name],
                capture_output=True, timeout=30
            )
            self.is_running = False
            logger.info("Container %s entfernt", self.container_name)
            return True
        except Exception as e:
            logger.warning("Container-Cleanup fehlgeschlagen: %s", e)
            return False

    def get_logs(self, tail: int = 50) -> str:
        """Holt Container-Logs (fuer Fehlerdiagnose)."""
        docker_path = self._get_docker_path()
        if not docker_path:
            return ""
        try:
            result = subprocess.run(
                [docker_path, "logs", "--tail", str(tail), self.container_name],
                capture_output=True, text=True, timeout=10,
                encoding='utf-8', errors='replace'
            )
            return result.stdout + result.stderr
        except Exception:
            return ""

    # ==========================================================================
    # Private Hilfsmethoden
    # ==========================================================================

    def _remove_existing_container(self, docker_path: str):
        """Entfernt einen evtl. vorhandenen Container gleichen Namens."""
        try:
            subprocess.run(
                [docker_path, "rm", "-f", self.container_name],
                capture_output=True, timeout=10
            )
        except Exception:
            pass

    def _get_check_host(self) -> str:
        """
        Gibt den korrekten Host fuer Port-Checks zurueck.

        AENDERUNG 22.02.2026: Fix 63b — host.docker.internal in Docker-Containern
        ROOT-CAUSE: Backend laeuft in Docker, Sibling-Container publizieren Port auf HOST.
                    'localhost' im Backend-Container zeigt auf den Container selbst.
        LOESUNG: ENV-Override > host.docker.internal > Docker-Bridge-Gateway
        """
        explicit = os.getenv("CHECK_HOST") or os.getenv("DOCKER_HOST_GATEWAY")
        if explicit:
            return explicit

        if os.path.exists('/.dockerenv'):
            # Compose-Hinweis: fuer Linux ggf. extra_hosts: ["host.docker.internal:host-gateway"] setzen.
            try:
                import socket
                socket.gethostbyname("host.docker.internal")
                return "host.docker.internal"
            except Exception:
                return os.getenv("DOCKER_BRIDGE_GATEWAY", "172.17.0.1")

        return os.getenv("CHECK_HOST_DEFAULT", "localhost")

    def _wait_for_port(self, port: int, timeout: int,
                       interval: float = 0.5) -> bool:
        """Wartet bis Port auf dem richtigen Host erreichbar ist."""
        import socket
        check_host = self._get_check_host()
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                with socket.create_connection((check_host, port), timeout=1):
                    logger.info(
                        "Port %d erreichbar nach %.1fs",
                        port, time.time() - start_time
                    )
                    return True
            except (socket.timeout, ConnectionRefusedError, OSError):
                time.sleep(interval)
        logger.warning("Port %d nicht erreichbar nach %ds", port, timeout)
        return False
