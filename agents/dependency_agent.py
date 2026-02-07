# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 01.02.2026
Version: 2.0
Beschreibung: Dependency Agent - IT-Abteilung des Bueros (Orchestrator).
              REFAKTORIERT: Aus 996 Zeilen → 5 Module + Orchestrator
              Verwaltet Software-Installationen, fuehrt Inventar und prueft Verfuegbarkeit.

              Module:
              - dependency_constants.py: Konstanten, Built-in Module, NPM Packages
              - dependency_checker.py: Verfügbarkeitsprüfung
              - dependency_installer.py: Installation
              - dependency_inventory.py: Inventar-Verwaltung
              - dependency_security.py: Vulnerability-Checks

              ÄNDERUNG 01.02.2026: Aufsplitten in 5 Module (Regel 1: Max 500 Zeilen).
              ÄNDERUNG 31.01.2026: Built-in Module Filter.
              ÄNDERUNG 28.01.2026: Intelligente npm/pip Paketerkennung.
"""

import os
import time
import logging
import shutil
from datetime import datetime
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

# =========================================================================
# Re-exports aus dependency_constants.py
# =========================================================================
from .dependency_constants import (
    INVENTORY_PATH,
    NPM_PACKAGES,
    PYTHON_BUILTIN_MODULES,
    WINDOWS_NPM_PATHS,
    is_builtin_module,
    filter_builtin_modules
)

# =========================================================================
# Re-exports aus dependency_checker.py
# =========================================================================
from .dependency_checker import (
    check_dependency,
    detect_package_type,
    check_python_package,
    check_npm_package,
    check_system_tool,
    compare_versions
)

# =========================================================================
# Re-exports aus dependency_installer.py
# =========================================================================
from .dependency_installer import (
    validate_install_command,
    install_dependencies as _install_deps,
    install_single_package as _install_single
)

# =========================================================================
# Re-exports aus dependency_inventory.py
# =========================================================================
from .dependency_inventory import (
    scan_inventory,
    scan_python_packages,
    scan_npm_packages,
    scan_system_tools,
    calculate_health_score,
    save_inventory,
    load_inventory_from_file
)

# =========================================================================
# Re-exports aus dependency_security.py
# =========================================================================
from .dependency_security import check_vulnerabilities


# =========================================================================
# DependencyAgent Klasse
# =========================================================================
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

        # npm-Pfad mit Windows-Fallback cachen
        self._npm_path = self._find_npm_path()

        logger.info("DependencyAgent initialisiert (IT-Abteilung bereit)")

    def _find_npm_path(self) -> Optional[str]:
        """Findet npm-Pfad mit Windows-Fallback."""
        # Standard PATH-Suche
        npm_path = shutil.which("npm")
        if npm_path:
            logger.info(f"npm gefunden via PATH: {npm_path}")
            return npm_path

        # Windows-Fallback
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
    # VERFUEGBARKEITSPRUEFUNG (delegiert an checker Modul)
    # =========================================================================

    def check_dependency(self, name: str, package_type: str = "auto",
                         min_version: str = None, blueprint: Dict[str, Any] = None) -> Dict[str, Any]:
        """Prueft ob eine Dependency installiert ist."""
        # AENDERUNG 07.02.2026: Blueprint durchreichen fuer korrekte Pakettyp-Erkennung
        return check_dependency(name, package_type, min_version, self._npm_path, blueprint)

    def _detect_package_type(self, name: str, blueprint: Dict[str, Any] = None) -> str:
        """Erkennt automatisch den Pakettyp."""
        return detect_package_type(name, blueprint)

    def _compare_versions(self, v1: str, v2: str) -> int:
        """Vergleicht zwei Versionsnummern."""
        return compare_versions(v1, v2)

    # =========================================================================
    # INSTALLATION (delegiert an installer Modul)
    # =========================================================================

    def install_dependencies(self, install_command: str, project_path: str = None) -> Dict[str, Any]:
        """Fuehrt einen Installationsbefehl aus."""
        return _install_deps(
            install_command,
            project_path,
            on_log=self.on_log,
            update_inventory=self.update_inventory
        )

    def install_single_package(self, name: str, package_type: str = "python",
                               version: str = None, project_path: str = None) -> Dict[str, Any]:
        """Installiert ein einzelnes Paket."""
        # AENDERUNG 07.02.2026: project_path fuer lokale npm-Installation durchreichen
        return _install_single(
            name, package_type, version,
            npm_path=self._npm_path,
            project_path=project_path,
            on_log=self.on_log,
            update_inventory=self.update_inventory
        )

    # =========================================================================
    # INVENTAR (delegiert an inventory Modul)
    # =========================================================================

    def get_inventory(self, force_refresh: bool = False) -> Dict[str, Any]:
        """Gibt das aktuelle Inventar zurueck."""
        now = datetime.now()
        if (not force_refresh and self._inventory_cache and self._cache_timestamp and
            (now - self._cache_timestamp).total_seconds() < self._cache_duration):
            return self._inventory_cache

        # Neu scannen
        inventory = scan_inventory(self._npm_path, self.on_log)

        # Cache aktualisieren
        self._inventory_cache = inventory
        self._cache_timestamp = now

        return inventory

    def update_inventory(self) -> Dict[str, Any]:
        """Aktualisiert das Inventar und speichert es."""
        inventory = self.get_inventory(force_refresh=True)
        save_inventory(inventory)
        return inventory

    def load_inventory_from_file(self) -> Dict[str, Any]:
        """Laedt das Inventar aus der Datei."""
        return load_inventory_from_file()

    # =========================================================================
    # VULNERABILITY CHECK (delegiert an security Modul)
    # =========================================================================

    def check_vulnerabilities(self) -> Dict[str, Any]:
        """Prueft auf bekannte Schwachstellen."""
        return check_vulnerabilities(self.check_vulns, self.on_log)

    # =========================================================================
    # WORKFLOW INTEGRATION
    # =========================================================================

    def prepare_for_task(self, tech_blueprint: Dict[str, Any], project_path: str,
                         max_duration: int = 120) -> Dict[str, Any]:
        """
        Bereitet die Umgebung fuer einen Task vor.

        Args:
            tech_blueprint: Blueprint vom TechStack-Agent
            project_path: Pfad zum Projektverzeichnis
            max_duration: Maximale Gesamtdauer in Sekunden (Default: 120)

        Returns:
            Dict mit status und details
        """
        # AENDERUNG 07.02.2026: Gesamt-Timeout verhindert Blockierung bei vielen Dependencies
        start_time = time.time()
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

        # 2. Einzelne Dependencies pruefen (mit Zeitlimit)
        dependencies = tech_blueprint.get("dependencies", [])
        for idx, dep in enumerate(dependencies):
            # Zeitlimit pruefen
            elapsed = time.time() - start_time
            if elapsed > max_duration:
                remaining = len(dependencies) - idx
                results["warnings"].append(
                    f"Dependency-Phase nach {int(elapsed)}s abgebrochen ({remaining} Pakete uebersprungen)")
                self._log("PrepareTimeout", {"elapsed": int(elapsed), "skipped": remaining})
                break

            # AENDERUNG 07.02.2026: Blueprint an check_dependency durchreichen
            check = self.check_dependency(dep, blueprint=tech_blueprint)
            if not check.get("installed"):
                if self.auto_install:
                    pkg_type = self._detect_package_type(dep, tech_blueprint)
                    # AENDERUNG 07.02.2026: project_path fuer lokale npm-Installation
                    install = self.install_single_package(dep, pkg_type, project_path=project_path)
                    if install.get("status") != "OK":
                        results["warnings"].append(f"Konnte {dep} nicht installieren")
                else:
                    results["warnings"].append(f"Dependency nicht installiert: {dep}")

        # 3. Inventar aktualisieren
        results["inventory"] = self.update_inventory()

        if results["warnings"]:
            results["status"] = "WARNING"

        elapsed_total = int(time.time() - start_time)
        self._log("PrepareComplete", {
            "status": results["status"],
            "warnings": len(results["warnings"]),
            "duration_s": elapsed_total
        })

        return results


# =========================================================================
# Singleton-Instanz
# =========================================================================
_dependency_agent = None


def get_dependency_agent(config: Dict[str, Any] = None) -> DependencyAgent:
    """Gibt die Singleton-Instanz des DependencyAgent zurueck. Bei geaenderter config wird neu initialisiert."""
    global _dependency_agent
    config_dict = config if config is not None else {}
    if _dependency_agent is None:
        _dependency_agent = DependencyAgent(config)
    elif config is not None and _dependency_agent.config != config_dict:
        _dependency_agent = DependencyAgent(config)
    return _dependency_agent


# =========================================================================
# Expliziter __all__ Export
# =========================================================================
__all__ = [
    # Klasse
    'DependencyAgent',
    'get_dependency_agent',
    # Konstanten
    'INVENTORY_PATH',
    'NPM_PACKAGES',
    'PYTHON_BUILTIN_MODULES',
    'WINDOWS_NPM_PATHS',
    # Hilfs-Funktionen
    'is_builtin_module',
    'filter_builtin_modules',
    # Checker
    'check_dependency',
    'detect_package_type',
    'check_python_package',
    'check_npm_package',
    'check_system_tool',
    'compare_versions',
    # Installer
    'validate_install_command',
    # Inventory
    'scan_inventory',
    'scan_python_packages',
    'scan_npm_packages',
    'scan_system_tools',
    'calculate_health_score',
    'save_inventory',
    'load_inventory_from_file',
    # Security
    'check_vulnerabilities'
]
