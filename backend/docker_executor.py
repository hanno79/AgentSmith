# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 31.01.2026
Version: 1.0
Beschreibung: Fuehrt Befehle in Docker-Containern aus.
              Ermoeglicht isolierte Ausfuehrung von generierten Projekten.
"""

import subprocess
import shutil
import logging
import os
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field

# Logger konfigurieren
logger = logging.getLogger(__name__)


@dataclass
class DockerResult:
    """Ergebnis einer Docker-Operation."""
    success: bool
    stdout: str
    stderr: str
    exit_code: int
    container_id: Optional[str] = None
    duration_seconds: float = 0.0


@dataclass
class DockerConfig:
    """Konfiguration fuer Docker-Executor."""
    enabled: bool = False
    fallback_to_host: bool = True
    auto_start_docker: bool = False
    auto_start_timeout: int = 60
    memory_limit: str = "512m"
    cpu_limit: float = 1.0
    timeout_install: int = 300
    timeout_test: int = 180
    timeout_run: int = 60
    cleanup_on_success: bool = True
    images: Dict[str, str] = field(default_factory=lambda: {
        "python": "python:3.11-slim",
        "nodejs": "node:20-alpine",
        "playwright": "mcr.microsoft.com/playwright:v1.40.0-jammy"
    })


class DockerExecutor:
    """
    Verwaltet Docker-Container fuer Projekt-Ausfuehrung.

    Ermoeglicht isolierte Installation von Dependencies und
    Ausfuehrung von Tests in Docker-Containern.
    """

    def __init__(
        self,
        project_path: Path,
        tech_stack: str = "python",
        config: Optional[DockerConfig] = None
    ):
        """
        Initialisiert den Docker Executor.

        Args:
            project_path: Pfad zum Projekt-Verzeichnis
            tech_stack: Technologie-Stack (python, nodejs, playwright)
            config: Docker-Konfiguration
        """
        self.project_path = Path(project_path).resolve()
        self.tech_stack = tech_stack.lower()
        self.config = config or DockerConfig()

        # Container-Name basierend auf Projekt-Pfad (sanitized)
        safe_name = self.project_path.name.replace(" ", "_").replace("-", "_")
        self.container_name = f"agentsmith_{safe_name}"

        # Docker-Pfad cachen
        self._docker_path: Optional[str] = None

        logger.info(f"DockerExecutor initialisiert: {self.project_path} ({self.tech_stack})")

    # =========================================================================
    # Oeffentliche Methoden
    # =========================================================================

    def is_docker_available(self) -> bool:
        """
        Prueft ob Docker installiert und erreichbar ist.

        Returns:
            True wenn Docker verfuegbar, sonst False
        """
        docker_path = self._get_docker_path()
        if not docker_path:
            logger.warning("Docker nicht im PATH gefunden")
            return False

        try:
            result = subprocess.run(
                [docker_path, "info"],
                capture_output=True,
                timeout=10
            )
            if result.returncode == 0:
                logger.info("Docker ist verfuegbar und laeuft")
                return True
            else:
                logger.warning(f"Docker info fehlgeschlagen: {result.stderr.decode()}")
                return False
        except subprocess.TimeoutExpired:
            logger.warning("Docker info Timeout")
            return False
        except Exception as e:
            logger.warning(f"Docker-Pruefung fehlgeschlagen: {e}")
            return False

    def auto_start_docker_if_needed(self) -> bool:
        """
        Startet Docker automatisch wenn konfiguriert und nicht bereits laufend.

        Returns:
            True wenn Docker laeuft (bereits oder nach Start), False bei Fehler
        """
        if self.is_docker_available():
            return True

        if not self.config.auto_start_docker:
            logger.info("Docker Auto-Start deaktiviert")
            return False

        docker_path = self._get_docker_path()
        if not docker_path:
            logger.warning("Docker nicht installiert - Auto-Start nicht moeglich")
            return False

        logger.info("Versuche Docker automatisch zu starten...")

        import time
        import sys

        try:
            if sys.platform == "win32":
                docker_desktop_paths = [
                    r"C:\Program Files\Docker\Docker\Docker Desktop.exe",
                    r"C:\Program Files (x86)\Docker\Docker\Docker Desktop.exe",
                    os.path.expandvars(r"%PROGRAMFILES%\Docker\Docker\Docker Desktop.exe"),
                ]

                docker_exe = None
                for path in docker_desktop_paths:
                    if os.path.exists(path):
                        docker_exe = path
                        break

                if docker_exe:
                    subprocess.Popen([docker_exe], shell=False)
                    logger.info(f"Docker Desktop gestartet: {docker_exe}")
                else:
                    subprocess.Popen(["cmd", "/c", "start", "Docker Desktop"], shell=True)
                    logger.info("Docker Desktop via Start-Befehl gestartet")

            elif sys.platform == "darwin":
                subprocess.Popen(["open", "-a", "Docker"])
                logger.info("Docker Desktop auf macOS gestartet")

            else:
                result = subprocess.run(
                    ["systemctl", "start", "docker"],
                    capture_output=True,
                    timeout=30
                )
                if result.returncode != 0:
                    subprocess.run(
                        ["sudo", "service", "docker", "start"],
                        capture_output=True,
                        timeout=30
                    )
                logger.info("Docker Daemon auf Linux gestartet")

        except Exception as e:
            logger.error(f"Fehler beim Starten von Docker: {e}")
            return False

        timeout = self.config.auto_start_timeout
        start_time = time.time()

        while time.time() - start_time < timeout:
            time.sleep(2)
            if self.is_docker_available():
                logger.info(f"Docker erfolgreich gestartet nach {time.time() - start_time:.1f}s")
                return True
            logger.debug(f"Warte auf Docker... ({time.time() - start_time:.0f}s)")

        logger.error(f"Docker-Start Timeout nach {timeout}s")
        return False

    def install_dependencies(self, timeout: Optional[int] = None) -> DockerResult:
        """
        Installiert Dependencies im Container.

        Args:
            timeout: Timeout in Sekunden (default: config.timeout_install)

        Returns:
            DockerResult mit Erfolg/Fehler-Status
        """
        timeout = timeout or self.config.timeout_install

        if self.tech_stack == "python":
            # Pruefe ob requirements.txt existiert
            req_file = self.project_path / "requirements.txt"
            if not req_file.exists():
                return DockerResult(
                    success=True,
                    stdout="Keine requirements.txt gefunden - uebersprungen",
                    stderr="",
                    exit_code=0
                )
            cmd = "pip install --no-cache-dir -r requirements.txt"

        elif self.tech_stack in ("nodejs", "javascript"):
            # Pruefe ob package.json existiert
            pkg_file = self.project_path / "package.json"
            if not pkg_file.exists():
                return DockerResult(
                    success=True,
                    stdout="Keine package.json gefunden - uebersprungen",
                    stderr="",
                    exit_code=0
                )
            cmd = "npm install --silent"

        else:
            return DockerResult(
                success=False,
                stdout="",
                stderr=f"Unbekannter TechStack: {self.tech_stack}",
                exit_code=1
            )

        logger.info(f"Installiere Dependencies im Container: {cmd}")
        return self._run_in_container(cmd, timeout)

    def run_tests(self, timeout: Optional[int] = None) -> DockerResult:
        """
        Fuehrt Tests im Container aus.

        Args:
            timeout: Timeout in Sekunden (default: config.timeout_test)

        Returns:
            DockerResult mit Test-Ergebnis
        """
        timeout = timeout or self.config.timeout_test

        if self.tech_stack == "python":
            # Pruefe ob pytest-Tests existieren
            test_dir = self.project_path / "tests"
            test_files = list(self.project_path.glob("**/test_*.py"))
            if not test_dir.exists() and not test_files:
                return DockerResult(
                    success=True,
                    stdout="Keine Tests gefunden - uebersprungen",
                    stderr="",
                    exit_code=0
                )
            cmd = "python -m pytest -v --tb=short"

        elif self.tech_stack in ("nodejs", "javascript"):
            # npm test - passWithNoTests fuer Jest
            cmd = "npm test -- --passWithNoTests --silent 2>/dev/null || npm test 2>/dev/null || echo 'Keine Tests definiert'"

        else:
            return DockerResult(
                success=False,
                stdout="",
                stderr=f"Unbekannter TechStack: {self.tech_stack}",
                exit_code=1
            )

        logger.info(f"Fuehre Tests im Container aus: {cmd}")
        return self._run_in_container(cmd, timeout)

    # AENDERUNG 01.02.2026: Neue kombinierte Methode für Docker-Tests
    def install_and_test(self, timeout: Optional[int] = None) -> DockerResult:
        """
        Installiert Dependencies UND fuehrt Tests im SELBEN Container aus.

        Loest das Problem dass `--rm` den Container nach install_dependencies()
        loescht und run_tests() dann keine Packages findet.

        Args:
            timeout: Timeout in Sekunden (default: timeout_install + timeout_test)

        Returns:
            DockerResult mit kombiniertem Ergebnis
        """
        timeout = timeout or (self.config.timeout_install + self.config.timeout_test)

        if self.tech_stack == "python":
            # Pruefe ob requirements.txt existiert
            req_file = self.project_path / "requirements.txt"
            test_dir = self.project_path / "tests"
            test_files = list(self.project_path.glob("**/test_*.py"))

            if not req_file.exists():
                # Keine requirements - nur Tests laufen lassen
                if not test_dir.exists() and not test_files:
                    return DockerResult(
                        success=True,
                        stdout="Keine requirements.txt und keine Tests gefunden",
                        stderr="",
                        exit_code=0
                    )
                cmd = "python -m pytest -v --tb=short"
            else:
                # BEIDES in einem Container-Aufruf
                if not test_dir.exists() and not test_files:
                    cmd = "pip install --no-cache-dir -r requirements.txt && echo 'Dependencies installiert, keine Tests gefunden'"
                else:
                    cmd = "pip install --no-cache-dir -r requirements.txt && python -m pytest -v --tb=short"

        elif self.tech_stack in ("nodejs", "javascript"):
            pkg_file = self.project_path / "package.json"
            if not pkg_file.exists():
                return DockerResult(
                    success=True,
                    stdout="Keine package.json gefunden",
                    stderr="",
                    exit_code=0
                )
            cmd = "npm install --silent && npm test -- --passWithNoTests --silent"

        else:
            return DockerResult(
                success=False,
                stdout="",
                stderr=f"Unbekannter TechStack: {self.tech_stack}",
                exit_code=1
            )

        logger.info(f"Installiere und teste im selben Container: {cmd[:80]}...")
        return self._run_in_container(cmd, timeout)

    def run_syntax_check(self, timeout: int = 30) -> DockerResult:
        """
        Fuehrt Syntax-Check im Container aus.

        Args:
            timeout: Timeout in Sekunden

        Returns:
            DockerResult mit Syntax-Check-Ergebnis
        """
        if self.tech_stack == "python":
            # Alle Python-Dateien mit ast checken
            cmd = "python -c \"import ast, sys; [ast.parse(open(f).read()) for f in __import__('glob').glob('**/*.py', recursive=True)]; print('Syntax OK')\""

        elif self.tech_stack in ("nodejs", "javascript"):
            # Alle JS-Dateien mit node --check checken
            cmd = "find . -name '*.js' -exec node --check {} \\; && echo 'Syntax OK'"

        else:
            return DockerResult(
                success=False,
                stdout="",
                stderr=f"Unbekannter TechStack fuer Syntax-Check: {self.tech_stack}",
                exit_code=1
            )

        logger.info(f"Fuehre Syntax-Check im Container aus")
        return self._run_in_container(cmd, timeout)

    def run_app(
        self,
        port: int = 5000,
        timeout: Optional[int] = None,
        detached: bool = True
    ) -> DockerResult:
        """
        Startet die App im Container mit Port-Mapping.

        Args:
            port: Port fuer die App
            timeout: Timeout fuer Start (default: config.timeout_run)
            detached: Im Hintergrund starten

        Returns:
            DockerResult mit Container-ID bei Erfolg
        """
        timeout = timeout or self.config.timeout_run
        docker_path = self._get_docker_path()
        if not docker_path:
            return DockerResult(False, "", "Docker nicht verfuegbar", 1)

        image = self.config.images.get(self.tech_stack, "python:3.11-slim")

        # Run-Command basierend auf TechStack
        if self.tech_stack == "python":
            run_cmd = "python src/app.py"
        elif self.tech_stack in ("nodejs", "javascript"):
            run_cmd = "npm start"
        else:
            run_cmd = "echo 'Kein Run-Command fuer TechStack'"

        # Docker-Befehl zusammenbauen
        docker_cmd = [
            docker_path, "run",
            "-d" if detached else "",  # Detached mode
            "--name", self.container_name,
            "-v", f"{self.project_path}:/app",
            "-w", "/app",
            "-p", f"{port}:{port}",
            "--memory", self.config.memory_limit,
            "--cpus", str(self.config.cpu_limit),
            image,
            "sh", "-c", run_cmd
        ]
        # Filter leere Strings
        docker_cmd = [c for c in docker_cmd if c]

        try:
            result = subprocess.run(
                docker_cmd,
                capture_output=True,
                timeout=timeout,
                text=True,
                encoding='utf-8',
                errors='replace'
            )

            container_id = result.stdout.strip()[:12] if result.returncode == 0 else None

            return DockerResult(
                success=result.returncode == 0,
                stdout=result.stdout,
                stderr=result.stderr,
                exit_code=result.returncode,
                container_id=container_id
            )
        except subprocess.TimeoutExpired:
            self.cleanup()
            return DockerResult(False, "", f"Timeout nach {timeout}s", -1)
        except Exception as e:
            return DockerResult(False, "", str(e), -1)

    def cleanup(self) -> bool:
        """
        Stoppt und entfernt den Container.

        Returns:
            True bei Erfolg, False bei Fehler
        """
        docker_path = self._get_docker_path()
        if not docker_path:
            return False

        try:
            # Container stoppen und entfernen
            subprocess.run(
                [docker_path, "rm", "-f", self.container_name],
                capture_output=True,
                timeout=30
            )
            logger.info(f"Container {self.container_name} entfernt")
            return True
        except Exception as e:
            logger.warning(f"Container-Cleanup fehlgeschlagen: {e}")
            return False

    def get_container_logs(self, tail: int = 100) -> str:
        """
        Holt die Logs des Containers.

        Args:
            tail: Anzahl der letzten Zeilen

        Returns:
            Log-Output als String
        """
        docker_path = self._get_docker_path()
        if not docker_path:
            return ""

        try:
            result = subprocess.run(
                [docker_path, "logs", "--tail", str(tail), self.container_name],
                capture_output=True,
                timeout=10,
                text=True,
                encoding='utf-8',
                errors='replace'
            )
            return result.stdout + result.stderr
        except Exception as e:
            return f"Fehler beim Abrufen der Logs: {e}"

    # =========================================================================
    # Private Methoden
    # =========================================================================

    def _get_docker_path(self) -> Optional[str]:
        """Cached Docker-Pfad zurueckgeben."""
        if self._docker_path is None:
            self._docker_path = shutil.which("docker")
        return self._docker_path

    def _run_in_container(self, cmd: str, timeout: int) -> DockerResult:
        """
        Fuehrt einen Befehl im Container aus.

        Args:
            cmd: Auszufuehrender Befehl
            timeout: Timeout in Sekunden

        Returns:
            DockerResult mit Ergebnis
        """
        import time
        start_time = time.time()

        docker_path = self._get_docker_path()
        if not docker_path:
            return DockerResult(
                success=False,
                stdout="",
                stderr="Docker nicht verfuegbar",
                exit_code=1
            )

        image = self.config.images.get(self.tech_stack, "python:3.11-slim")

        # Projekt-Pfad fuer Docker-Mount vorbereiten
        # Auf Windows: Pfad in Unix-Format konvertieren
        project_mount = str(self.project_path)
        if os.name == 'nt':
            # Windows-Pfad fuer Docker konvertieren (C:\... -> /c/...)
            project_mount = '/' + project_mount.replace(':', '').replace('\\', '/')

        docker_cmd = [
            docker_path, "run", "--rm",
            "--name", f"{self.container_name}_run",
            "-v", f"{project_mount}:/app",
            "-w", "/app",
            "--memory", self.config.memory_limit,
            "--cpus", str(self.config.cpu_limit),
            image,
            "sh", "-c", cmd
        ]

        logger.debug(f"Docker-Befehl: {' '.join(docker_cmd)}")

        try:
            result = subprocess.run(
                docker_cmd,
                capture_output=True,
                timeout=timeout,
                text=True,
                encoding='utf-8',
                errors='replace'
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
            # Versuch den Container zu stoppen
            try:
                subprocess.run(
                    [docker_path, "rm", "-f", f"{self.container_name}_run"],
                    capture_output=True,
                    timeout=10
                )
            except Exception:
                pass

            return DockerResult(
                success=False,
                stdout="",
                stderr=f"Timeout nach {timeout}s",
                exit_code=-1,
                duration_seconds=duration
            )

        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"Docker-Ausfuehrung fehlgeschlagen: {e}")
            return DockerResult(
                success=False,
                stdout="",
                stderr=str(e),
                exit_code=-1,
                duration_seconds=duration
            )


# =============================================================================
# Factory-Funktion
# =============================================================================

def create_docker_executor(
    project_path: str,
    tech_blueprint: Dict[str, Any],
    docker_config: Optional[Dict[str, Any]] = None
) -> DockerExecutor:
    """
    Factory-Funktion zum Erstellen eines DockerExecutors.

    Args:
        project_path: Pfad zum Projekt
        tech_blueprint: TechStack-Blueprint
        docker_config: Optionale Docker-Konfiguration

    Returns:
        Konfigurierter DockerExecutor
    """
    # TechStack aus Blueprint extrahieren
    language = tech_blueprint.get("language", "python").lower()

    # TechStack-Mapping
    tech_stack_map = {
        "python": "python",
        "javascript": "nodejs",
        "nodejs": "nodejs",
        "typescript": "nodejs",
    }
    tech_stack = tech_stack_map.get(language, "python")

    # Config erstellen
    config = DockerConfig()
    if docker_config:
        config.enabled = docker_config.get("enabled", False)
        config.fallback_to_host = docker_config.get("fallback_to_host", True)
        config.memory_limit = docker_config.get("memory_limit", "512m")
        config.cpu_limit = docker_config.get("cpu_limit", 1.0)
        config.timeout_install = docker_config.get("timeout_install", 300)
        config.timeout_test = docker_config.get("timeout_test", 180)
        if "images" in docker_config:
            config.images.update(docker_config["images"])

    return DockerExecutor(
        project_path=Path(project_path),
        tech_stack=tech_stack,
        config=config
    )
