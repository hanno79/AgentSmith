# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 28.01.2026
Version: 1.3
Beschreibung: Dependency Agent - IT-Abteilung des Bueros.
              Verwaltet Software-Installationen, fuehrt Inventar und prueft Verfuegbarkeit.
              Kein LLM erforderlich - deterministische Funktionen.
              ÄNDERUNG 28.01.2026: Intelligente npm/pip Paketerkennung für hybride Projekte.
              ÄNDERUNG 28.01.2026: Windows PATH-Fallback für npm-Erkennung.
              ÄNDERUNG 28.01.2026: Fix WinError 2 - Direkte List fuer npm subprocess (keine .split()).
"""

import os
import subprocess
import json
import logging
import shutil
from datetime import datetime
from typing import Dict, Any, List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

# Pfad zur Inventar-Datei
INVENTORY_PATH = Path(__file__).parent.parent / "library" / "dependencies.json"

# ÄNDERUNG 28.01.2026: Bekannte npm-Pakete die NIEMALS via pip installiert werden sollen
NPM_PACKAGES = {
    # React Ecosystem
    "react", "react-dom", "react-router", "react-router-dom", "react-redux",
    "react-query", "react-hook-form", "next", "gatsby", "create-react-app",
    # Vue Ecosystem
    "vue", "vue-router", "vuex", "pinia", "nuxt",
    # Angular
    "angular", "@angular/core", "@angular/cli", "@angular/common",
    # Svelte
    "svelte", "sveltekit", "@sveltejs/kit",
    # Build Tools
    "webpack", "vite", "parcel", "rollup", "esbuild", "turbopack",
    # CSS/Styling
    "tailwindcss", "postcss", "autoprefixer", "sass", "less", "styled-components",
    # Utilities
    "typescript", "eslint", "prettier", "jest", "vitest", "mocha", "chai",
    "axios", "lodash", "moment", "dayjs", "date-fns",
    # Node.js specific
    "express", "fastify", "koa", "nest", "socket.io"
}

# ÄNDERUNG 28.01.2026: Bekannte Windows-Installationspfade für Node.js/npm
WINDOWS_NPM_PATHS = [
    r"C:\Program Files\nodejs\npm.cmd",
    r"C:\Program Files (x86)\nodejs\npm.cmd",
    os.path.expandvars(r"%APPDATA%\npm\npm.cmd"),
    os.path.expandvars(r"%LOCALAPPDATA%\Programs\nodejs\npm.cmd"),
    os.path.expandvars(r"%ProgramFiles%\nodejs\npm.cmd"),
]


class DependencyAgent:
    """
    IT-Abteilung des Bueros - verwaltet alle Software-Dependencies.

    Aufgaben:
    - Installation von Dependencies (pip, npm)
    - Fuehren eines Inventars
    - Verfuegbarkeitspruefungen
    - Vulnerability-Checks
    """

    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialisiert den Dependency-Agent.

        Args:
            config: Optionale Konfiguration mit auto_install, check_vulnerabilities etc.
        """
        self.config = config or {}
        self.auto_install = self.config.get("auto_install", True)
        self.check_vulns = self.config.get("check_vulnerabilities", True)
        self._inventory_cache = None
        self._cache_timestamp = None
        self._cache_duration = self.config.get("cache_inventory", 300)  # 5 Minuten

        # Callback fuer UI-Updates (wird vom Orchestrator gesetzt)
        self.on_log = None

        # ÄNDERUNG 28.01.2026: npm-Pfad mit Windows-Fallback cachen
        self._npm_path = self._find_npm_path()

        logger.info("DependencyAgent initialisiert (IT-Abteilung bereit)")

    def _find_npm_path(self) -> Optional[str]:
        """
        Findet npm-Pfad mit Windows-Fallback.

        1. Versucht shutil.which() (Standard-PATH)
        2. Falls nicht gefunden: Durchsucht bekannte Windows-Pfade

        Returns:
            Vollstaendiger Pfad zu npm oder None
        """
        # Standard PATH-Suche
        npm_path = shutil.which("npm")
        if npm_path:
            logger.info(f"npm gefunden via PATH: {npm_path}")
            return npm_path

        # Windows-Fallback: Bekannte Installationspfade durchsuchen
        if os.name == 'nt':
            for path in WINDOWS_NPM_PATHS:
                expanded = os.path.expandvars(path)
                if os.path.isfile(expanded):
                    logger.info(f"npm gefunden via Fallback: {expanded}")
                    return expanded

        logger.warning("npm nicht gefunden - npm-Pakete werden uebersprungen")
        return None

    def _log(self, event: str, message: Any):
        """Sendet Log-Event an UI wenn Callback gesetzt."""
        if self.on_log:
            self.on_log("DependencyAgent", event, message)
        logger.info(f"[DependencyAgent] {event}: {message}")

    # =========================================================================
    # VERFUEGBARKEITSPRUEFUNG
    # =========================================================================

    def check_dependency(self, name: str, package_type: str = "auto",
                         min_version: str = None) -> Dict[str, Any]:
        """
        Prueft ob eine Dependency installiert ist.

        Args:
            name: Name des Pakets (z.B. "pytest", "react")
            package_type: "python", "npm", "system" oder "auto" (automatische Erkennung)
            min_version: Optionale Mindestversion

        Returns:
            Dict mit installed, version, meets_requirement
        """
        if package_type == "auto":
            package_type = self._detect_package_type(name)

        if package_type == "python":
            return self._check_python_package(name, min_version)
        elif package_type == "npm":
            return self._check_npm_package(name, min_version)
        elif package_type == "system":
            return self._check_system_tool(name, min_version)
        else:
            return {"installed": False, "version": None, "error": f"Unbekannter Pakettyp: {package_type}"}

    def _detect_package_type(self, name: str, blueprint: Dict[str, Any] = None) -> str:
        """
        ÄNDERUNG 28.01.2026: Erkennt automatisch den Pakettyp basierend auf Namen.
        Erweitert um Blueprint-Kontext fuer hybride Projekte.

        Args:
            name: Paketname
            blueprint: Optional - TechStack Blueprint fuer Kontext

        Returns:
            "python", "npm" oder "system"
        """
        # Bekannte Python-Pakete
        python_packages = {"pytest", "flask", "django", "numpy", "pandas", "requests",
                          "sqlalchemy", "celery", "fastapi", "crewai", "langchain",
                          "flask_sqlalchemy", "flask_login", "flask_wtf", "psycopg2"}
        # System-Tools
        system_tools = {"node", "npm", "python", "git", "docker", "curl"}

        name_lower = name.lower()

        # 1. System-Tools haben Vorrang
        if name_lower in system_tools:
            return "system"

        # 2. Bekannte Python-Pakete
        if name_lower in python_packages:
            return "python"

        # 3. ÄNDERUNG 28.01.2026: NPM_PACKAGES Konstante nutzen (umfassender)
        if name_lower in NPM_PACKAGES:
            return "npm"

        # 4. Scoped npm packages (@scope/package)
        if name.startswith("@"):
            return "npm"

        # 5. Typische npm-Paketnamen-Muster
        npm_keywords = ["react", "vue", "angular", "svelte", "webpack", "vite", "eslint"]
        if any(kw in name_lower for kw in npm_keywords):
            return "npm"

        # 6. Blueprint-Kontext als Fallback
        if blueprint and blueprint.get("language") == "javascript":
            return "npm"

        # Default: Python versuchen
        return "python"

    def _check_python_package(self, name: str, min_version: str = None) -> Dict[str, Any]:
        """Prueft ob ein Python-Paket installiert ist."""
        try:
            result = subprocess.run(
                ["python", "-m", "pip", "show", name],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                # Version extrahieren
                version = None
                for line in result.stdout.split("\n"):
                    if line.startswith("Version:"):
                        version = line.split(":", 1)[1].strip()
                        break

                meets_requirement = True
                if min_version and version:
                    meets_requirement = self._compare_versions(version, min_version) >= 0

                return {
                    "installed": True,
                    "version": version,
                    "meets_requirement": meets_requirement,
                    "type": "python"
                }
            else:
                return {"installed": False, "version": None, "type": "python"}

        except Exception as e:
            logger.warning(f"Fehler beim Pruefen von {name}: {e}")
            return {"installed": False, "version": None, "error": str(e), "type": "python"}

    def _check_npm_package(self, name: str, min_version: str = None) -> Dict[str, Any]:
        """Prueft ob ein NPM-Paket global installiert ist."""
        try:
            # ÄNDERUNG 28.01.2026: Gecachten npm-Pfad verwenden
            if not self._npm_path:
                return {"installed": False, "version": None, "error": "npm nicht verfuegbar", "type": "npm"}

            result = subprocess.run(
                [self._npm_path, "list", "-g", name, "--depth=0", "--json"],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                data = json.loads(result.stdout)
                deps = data.get("dependencies", {})
                if name in deps:
                    version = deps[name].get("version")
                    meets_requirement = True
                    if min_version and version:
                        meets_requirement = self._compare_versions(version, min_version) >= 0
                    return {
                        "installed": True,
                        "version": version,
                        "meets_requirement": meets_requirement,
                        "type": "npm"
                    }

            return {"installed": False, "version": None, "type": "npm"}

        except Exception as e:
            logger.warning(f"Fehler beim Pruefen von npm:{name}: {e}")
            return {"installed": False, "version": None, "error": str(e), "type": "npm"}

    def _check_system_tool(self, name: str, min_version: str = None) -> Dict[str, Any]:
        """Prueft ob ein System-Tool verfuegbar ist."""
        try:
            path = shutil.which(name)
            if not path:
                return {"installed": False, "version": None, "type": "system"}

            # Version ermitteln
            version = None
            try:
                result = subprocess.run(
                    [name, "--version"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                # Erste Zeile oft die Version
                if result.stdout:
                    import re
                    match = re.search(r'(\d+\.\d+\.?\d*)', result.stdout)
                    if match:
                        version = match.group(1)
            except Exception:
                pass

            meets_requirement = True
            if min_version and version:
                meets_requirement = self._compare_versions(version, min_version) >= 0

            return {
                "installed": True,
                "version": version,
                "path": path,
                "meets_requirement": meets_requirement,
                "type": "system"
            }

        except Exception as e:
            return {"installed": False, "version": None, "error": str(e), "type": "system"}

    def _compare_versions(self, v1: str, v2: str) -> int:
        """Vergleicht zwei Versionsnummern. Gibt -1, 0 oder 1 zurueck."""
        try:
            def normalize(v):
                return [int(x) for x in v.split(".")[:3]]

            parts1 = normalize(v1)
            parts2 = normalize(v2)

            # Auffuellen mit Nullen
            while len(parts1) < 3:
                parts1.append(0)
            while len(parts2) < 3:
                parts2.append(0)

            if parts1 > parts2:
                return 1
            elif parts1 < parts2:
                return -1
            else:
                return 0
        except Exception:
            return 0

    # =========================================================================
    # INSTALLATION
    # =========================================================================

    def install_dependencies(self, install_command: str, project_path: str = None) -> Dict[str, Any]:
        """
        Fuehrt einen Installationsbefehl aus.

        Args:
            install_command: z.B. "pip install -r requirements.txt" oder "npm install"
            project_path: Arbeitsverzeichnis fuer die Installation

        Returns:
            Dict mit status, output, installed_packages
        """
        if not install_command:
            return {"status": "SKIP", "output": "Kein Installationsbefehl angegeben"}

        # ÄNDERUNG 28.01.2026: Prüfe ob referenzierte Dateien existieren
        if "requirements.txt" in install_command:
            req_path = os.path.join(project_path, "requirements.txt") if project_path else "requirements.txt"
            if not os.path.exists(req_path):
                self._log("InstallSkipped", {
                    "command": install_command,
                    "reason": f"Datei nicht gefunden: {req_path}"
                })
                return {
                    "status": "SKIP",
                    "output": f"requirements.txt nicht gefunden in {project_path or 'aktuellem Verzeichnis'}. Erstelle die Datei oder installiere einzelne Pakete."
                }

        if install_command.strip() in ["npm install", "npm i"] and project_path:
            pkg_path = os.path.join(project_path, "package.json")
            if not os.path.exists(pkg_path):
                self._log("InstallSkipped", {
                    "command": install_command,
                    "reason": f"package.json nicht gefunden: {pkg_path}"
                })
                return {
                    "status": "SKIP",
                    "output": f"package.json nicht gefunden in {project_path}. Erstelle die Datei mit 'npm init'."
                }

        self._log("InstallStart", {"command": install_command, "path": project_path})

        try:
            # Befehl in Teile zerlegen
            import shlex
            if os.name == 'nt':  # Windows
                # Auf Windows shlex nicht verwenden fuer einfache Befehle
                parts = install_command.split()
            else:
                parts = shlex.split(install_command)

            # Sicherheitscheck: Nur erlaubte Befehle
            allowed_commands = {"pip", "python", "npm", "yarn", "pnpm"}
            base_command = parts[0].lower() if parts else ""

            if base_command not in allowed_commands and not base_command.endswith("pip"):
                return {
                    "status": "BLOCKED",
                    "output": f"Befehl '{base_command}' nicht erlaubt. Erlaubt: {allowed_commands}"
                }

            # Arbeitsverzeichnis
            cwd = project_path if project_path and os.path.isdir(project_path) else None

            # Installation ausfuehren
            self._log("InstallProgress", {"status": "running", "command": install_command})

            result = subprocess.run(
                parts,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=300,  # 5 Minuten Timeout
                encoding='utf-8',
                errors='replace'
            )

            output = result.stdout + "\n" + result.stderr

            if result.returncode == 0:
                self._log("InstallComplete", {"status": "OK", "command": install_command})

                # Inventar aktualisieren
                self.update_inventory()

                return {
                    "status": "OK",
                    "output": output.strip(),
                    "return_code": result.returncode
                }
            else:
                self._log("InstallError", {"status": "FAIL", "output": output[:500]})
                return {
                    "status": "FAIL",
                    "output": output.strip(),
                    "return_code": result.returncode
                }

        except subprocess.TimeoutExpired:
            self._log("InstallError", {"status": "TIMEOUT"})
            return {"status": "TIMEOUT", "output": "Installation Timeout nach 300 Sekunden"}
        except Exception as e:
            self._log("InstallError", {"status": "ERROR", "error": str(e)})
            return {"status": "ERROR", "output": str(e)}

    def install_single_package(self, name: str, package_type: str = "python",
                               version: str = None) -> Dict[str, Any]:
        """
        Installiert ein einzelnes Paket.

        Args:
            name: Paketname
            package_type: "python" oder "npm"
            version: Optionale Versionsnummer

        Returns:
            Dict mit status, output
        """
        if package_type == "python":
            package_spec = f"{name}=={version}" if version else name
            command = f"python -m pip install {package_spec}"
            return self.install_dependencies(command)

        elif package_type == "npm":
            # ÄNDERUNG 28.01.2026: npm nur wenn verfuegbar
            if not self._npm_path:
                self._log("InstallSkipped", {
                    "package": name,
                    "reason": "npm nicht verfuegbar",
                    "type": "npm"
                })
                return {
                    "status": "SKIPPED",
                    "output": f"npm nicht verfuegbar - {name} uebersprungen"
                }
            package_spec = f"{name}@{version}" if version else name

            # ÄNDERUNG 28.01.2026: Direkter subprocess-Aufruf mit List statt String
            # Vermeidet .split()-Problem bei Pfaden mit Leerzeichen (WinError 2 Fix)
            try:
                self._log("InstallProgress", {"status": "running", "package": name, "type": "npm"})
                result = subprocess.run(
                    [self._npm_path, "install", "-g", package_spec],
                    capture_output=True,
                    text=True,
                    timeout=300,
                    encoding='utf-8',
                    errors='replace'
                )

                output = result.stdout + "\n" + result.stderr

                if result.returncode == 0:
                    self._log("InstallComplete", {"status": "OK", "package": name, "type": "npm"})
                    self.update_inventory()
                    return {"status": "OK", "output": output.strip(), "return_code": 0}
                else:
                    self._log("InstallError", {"status": "FAIL", "output": output[:500]})
                    return {"status": "FAIL", "output": output.strip(), "return_code": result.returncode}

            except subprocess.TimeoutExpired:
                self._log("InstallError", {"status": "TIMEOUT", "package": name})
                return {"status": "TIMEOUT", "output": "npm Installation Timeout nach 300 Sekunden"}
            except Exception as e:
                self._log("InstallError", {"status": "ERROR", "error": str(e)})
                return {"status": "ERROR", "output": str(e)}

        else:
            return {"status": "ERROR", "output": f"Unbekannter Pakettyp: {package_type}"}

    # =========================================================================
    # INVENTAR
    # =========================================================================

    def get_inventory(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Gibt das aktuelle Inventar zurueck.

        Args:
            force_refresh: Cache ignorieren und neu scannen

        Returns:
            Dict mit python, npm, system Paketen und health_score
        """
        # Cache pruefen
        now = datetime.now()
        if (not force_refresh and self._inventory_cache and self._cache_timestamp and
            (now - self._cache_timestamp).total_seconds() < self._cache_duration):
            return self._inventory_cache

        # Neu scannen
        inventory = self._scan_inventory()

        # Cache aktualisieren
        self._inventory_cache = inventory
        self._cache_timestamp = now

        return inventory

    def _scan_inventory(self) -> Dict[str, Any]:
        """Scannt alle installierten Pakete."""
        self._log("InventoryScan", {"status": "started"})

        inventory = {
            "last_updated": datetime.now().isoformat(),
            "python": self._scan_python_packages(),
            "npm": self._scan_npm_packages(),
            "system": self._scan_system_tools(),
            "health_score": 0
        }

        # ÄNDERUNG 28.01.2026: npm-Status konsistent fuer Health-Score halten
        npm_error = inventory.get("npm", {}).get("error")
        npm_version = inventory.get("npm", {}).get("version")
        system_tools = inventory.get("system", {})
        if "npm" not in system_tools:
            system_tools["npm"] = None
        if npm_error or npm_version == "not installed":
            system_tools["npm"] = None
        inventory["system"] = system_tools

        # Health-Score berechnen
        inventory["health_score"] = self._calculate_health_score(inventory)

        self._log("InventoryScan", {"status": "complete", "health": inventory["health_score"]})

        return inventory

    def _scan_python_packages(self) -> Dict[str, Any]:
        """Scannt installierte Python-Pakete."""
        try:
            result = subprocess.run(
                ["python", "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            python_version = result.stdout.strip().replace("Python ", "") if result.returncode == 0 else "unknown"

            # Pakete auflisten
            result = subprocess.run(
                ["python", "-m", "pip", "list", "--format=json"],
                capture_output=True,
                text=True,
                timeout=60
            )

            packages = []
            if result.returncode == 0:
                pip_list = json.loads(result.stdout)
                for pkg in pip_list:
                    packages.append({
                        "name": pkg.get("name"),
                        "version": pkg.get("version"),
                        "status": "installed"
                    })

            return {
                "version": python_version,
                "packages": packages
            }

        except Exception as e:
            logger.warning(f"Fehler beim Scannen von Python-Paketen: {e}")
            return {"version": "unknown", "packages": [], "error": str(e)}

    def _scan_npm_packages(self) -> Dict[str, Any]:
        """Scannt installierte NPM-Pakete (global)."""
        try:
            # ÄNDERUNG 28.01.2026: Gecachten npm-Pfad verwenden
            if not self._npm_path:
                return {"version": "not installed", "packages": []}

            # npm Version - mit vollstaendigem Pfad
            result = subprocess.run(
                [self._npm_path, "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            npm_version = result.stdout.strip() if result.returncode == 0 else "unknown"

            # Globale Pakete - mit vollstaendigem Pfad
            result = subprocess.run(
                [self._npm_path, "list", "-g", "--depth=0", "--json"],
                capture_output=True,
                text=True,
                timeout=60
            )

            packages = []
            if result.returncode == 0:
                try:
                    data = json.loads(result.stdout)
                    for name, info in data.get("dependencies", {}).items():
                        packages.append({
                            "name": name,
                            "version": info.get("version", "unknown"),
                            "status": "installed"
                        })
                except json.JSONDecodeError:
                    pass

            return {
                "version": npm_version,
                "packages": packages
            }

        except Exception as e:
            logger.warning(f"Fehler beim Scannen von NPM-Paketen: {e}")
            return {"version": "unknown", "packages": [], "error": str(e)}

    def _scan_system_tools(self) -> Dict[str, Any]:
        """Scannt wichtige System-Tools."""
        tools = ["node", "git", "docker", "python", "npm", "curl"]
        result = {}

        for tool in tools:
            check = self._check_system_tool(tool)
            if check.get("installed"):
                result[tool] = check.get("version", "installed")

        return result

    def _calculate_health_score(self, inventory: Dict[str, Any]) -> int:
        """Berechnet einen Health-Score (0-100)."""
        score = 100

        # Abzuege fuer fehlende wichtige Tools
        critical_tools = ["python", "git"]
        for tool in critical_tools:
            if tool not in inventory.get("system", {}):
                score -= 20

        # ÄNDERUNG 28.01.2026: npm-Fehler beeinflusst Health-Score
        npm_error = inventory.get("npm", {}).get("error")
        system_npm = inventory.get("system", {}).get("npm")
        if npm_error or system_npm is None:
            score -= 15
        else:
            # Bonus fuer npm nur bei sauberem Status
            if inventory.get("npm", {}).get("version") and inventory["npm"]["version"] != "not installed":
                score = min(100, score + 5)

        # Abzug wenn wenig Pakete (koennte auf Problem hindeuten)
        python_packages = len(inventory.get("python", {}).get("packages", []))
        if python_packages < 5:
            score -= 10

        return max(0, min(100, score))

    def update_inventory(self) -> Dict[str, Any]:
        """Aktualisiert das Inventar und speichert es in die Datei."""
        inventory = self.get_inventory(force_refresh=True)

        # In Datei speichern
        try:
            INVENTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(INVENTORY_PATH, 'w', encoding='utf-8') as f:
                json.dump(inventory, f, indent=2, ensure_ascii=False)
            logger.info(f"Inventar gespeichert: {INVENTORY_PATH}")
        except Exception as e:
            logger.error(f"Fehler beim Speichern des Inventars: {e}")

        return inventory

    def load_inventory_from_file(self) -> Dict[str, Any]:
        """Laedt das Inventar aus der Datei (ohne Scan)."""
        try:
            if INVENTORY_PATH.exists():
                with open(INVENTORY_PATH, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"Fehler beim Laden des Inventars: {e}")

        return {}

    # =========================================================================
    # VULNERABILITY CHECK
    # =========================================================================

    def check_vulnerabilities(self) -> Dict[str, Any]:
        """
        Prueft auf bekannte Schwachstellen in installierten Paketen.

        Returns:
            Dict mit vulnerabilities Liste und Severity-Counts
        """
        if not self.check_vulns:
            return {"enabled": False, "vulnerabilities": []}

        self._log("VulnerabilityScan", {"status": "started"})

        vulnerabilities = []
        severity_counts = {"critical": 0, "high": 0, "moderate": 0, "low": 0}

        # Python: pip-audit (falls installiert)
        try:
            result = subprocess.run(
                ["python", "-m", "pip_audit", "--format=json"],
                capture_output=True,
                text=True,
                timeout=120
            )
            if result.returncode == 0:
                audit_data = json.loads(result.stdout)
                for vuln in audit_data:
                    vulnerabilities.append({
                        "package": vuln.get("name"),
                        "version": vuln.get("version"),
                        "vulnerability": vuln.get("id"),
                        "severity": vuln.get("severity", "unknown"),
                        "type": "python"
                    })
        except FileNotFoundError:
            logger.info("pip-audit nicht installiert - Python Vulnerability-Check uebersprungen")
        except Exception as e:
            logger.warning(f"pip-audit Fehler: {e}")

        # NPM: npm audit
        try:
            npm_path = shutil.which("npm")
            if npm_path:
                result = subprocess.run(
                    ["npm", "audit", "--json"],
                    capture_output=True,
                    text=True,
                    timeout=120
                )
                if result.stdout:
                    try:
                        audit_data = json.loads(result.stdout)
                        for name, info in audit_data.get("vulnerabilities", {}).items():
                            severity = info.get("severity", "moderate").lower()
                            vulnerabilities.append({
                                "package": name,
                                "severity": severity,
                                "type": "npm"
                            })
                            if severity in severity_counts:
                                severity_counts[severity] += 1
                    except json.JSONDecodeError:
                        pass
        except Exception as e:
            logger.warning(f"npm audit Fehler: {e}")

        # Severity zaehlen
        for vuln in vulnerabilities:
            sev = vuln.get("severity", "").lower()
            if sev in severity_counts:
                severity_counts[sev] += 1

        result = {
            "vulnerabilities": vulnerabilities,
            "counts": severity_counts,
            "total": len(vulnerabilities),
            "timestamp": datetime.now().isoformat()
        }

        self._log("VulnerabilityScan", {
            "status": "complete",
            "total": len(vulnerabilities),
            "critical": severity_counts["critical"]
        })

        return result

    # =========================================================================
    # WORKFLOW INTEGRATION
    # =========================================================================

    def prepare_for_task(self, tech_blueprint: Dict[str, Any], project_path: str) -> Dict[str, Any]:
        """
        Bereitet die Umgebung fuer einen Task vor.
        Wird vom Orchestrator aufgerufen nach dem TechStack-Blueprint.

        Args:
            tech_blueprint: Blueprint vom TechStack-Agent
            project_path: Pfad zum Projektverzeichnis

        Returns:
            Dict mit status und details
        """
        self._log("PrepareStart", {"blueprint": tech_blueprint.get("project_type")})

        results = {
            "status": "OK",
            "install_result": None,
            "inventory": None,
            "warnings": []
        }

        # 1. Dependencies aus Blueprint installieren
        install_command = tech_blueprint.get("install_command")
        if install_command and self.auto_install:
            install_result = self.install_dependencies(install_command, project_path)
            results["install_result"] = install_result

            if install_result.get("status") not in ["OK", "SKIP"]:
                results["status"] = "WARNING"
                results["warnings"].append(f"Installation fehlgeschlagen: {install_result.get('output', '')[:200]}")

        # 2. Einzelne Dependencies pruefen
        dependencies = tech_blueprint.get("dependencies", [])
        for dep in dependencies:
            check = self.check_dependency(dep)
            if not check.get("installed"):
                if self.auto_install:
                    # ÄNDERUNG 28.01.2026: Intelligente Paketttyp-Erkennung
                    pkg_type = self._detect_package_type(dep, tech_blueprint)
                    install = self.install_single_package(dep, pkg_type)
                    if install.get("status") != "OK":
                        results["warnings"].append(f"Konnte {dep} nicht installieren")
                else:
                    results["warnings"].append(f"Dependency nicht installiert: {dep}")

        # 3. Inventar aktualisieren
        results["inventory"] = self.update_inventory()

        if results["warnings"]:
            results["status"] = "WARNING"

        self._log("PrepareComplete", {"status": results["status"], "warnings": len(results["warnings"])})

        return results


# Singleton-Instanz fuer einfachen Zugriff
_dependency_agent = None

def get_dependency_agent(config: Dict[str, Any] = None) -> DependencyAgent:
    """Gibt die Singleton-Instanz des DependencyAgent zurueck."""
    global _dependency_agent
    if _dependency_agent is None:
        _dependency_agent = DependencyAgent(config)
    return _dependency_agent
