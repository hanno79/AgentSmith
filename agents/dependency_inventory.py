# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 01.02.2026
Version: 1.0
Beschreibung: Inventar-Verwaltung für Dependencies.
              Extrahiert aus dependency_agent.py (Regel 1: Max 500 Zeilen)
              Enthält: get_inventory, _scan_* Methoden, health_score
"""

import subprocess
import json
import logging
import shutil
from datetime import datetime
from typing import Dict, Any, Optional, Callable

from .dependency_constants import INVENTORY_PATH
from .dependency_checker import check_system_tool

logger = logging.getLogger(__name__)


def scan_inventory(npm_path: Optional[str] = None,
                   on_log: Optional[Callable] = None) -> Dict[str, Any]:
    """
    Scannt alle installierten Pakete.

    Args:
        npm_path: Pfad zu npm (optional)
        on_log: Callback für Logging

    Returns:
        Vollständiges Inventar Dictionary
    """
    def _log(event: str, message: Any):
        if on_log:
            on_log("DependencyAgent", event, message)
        logger.info(f"[DependencyAgent] {event}: {message}")

    _log("InventoryScan", {"status": "started"})

    inventory = {
        "last_updated": datetime.now().isoformat(),
        "python": scan_python_packages(),
        "npm": scan_npm_packages(npm_path),
        "system": scan_system_tools(),
        "health_score": 0
    }

    # npm-Status konsistent fuer Health-Score halten
    npm_error = inventory.get("npm", {}).get("error")
    npm_version = inventory.get("npm", {}).get("version")
    system_tools = inventory.get("system", {})
    if "npm" not in system_tools:
        system_tools["npm"] = None
    if npm_error or npm_version == "not installed":
        system_tools["npm"] = None
    inventory["system"] = system_tools

    # Health-Score berechnen
    inventory["health_score"] = calculate_health_score(inventory)

    _log("InventoryScan", {"status": "complete", "health": inventory["health_score"]})

    return inventory


def scan_python_packages() -> Dict[str, Any]:
    """Scannt installierte Python-Pakete."""
    try:
        result = subprocess.run(
            ["python", "--version"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            raw = (result.stdout or "").strip() or (result.stderr or "").strip()
            python_version = raw.replace("Python ", "", 1).strip() if raw else "unknown"
        else:
            python_version = "unknown"

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


def scan_npm_packages(npm_path: Optional[str] = None) -> Dict[str, Any]:
    """Scannt installierte NPM-Pakete (global)."""
    try:
        # Gecachten npm-Pfad verwenden
        if not npm_path:
            npm_path = shutil.which("npm")
        if not npm_path:
            return {"version": "not installed", "packages": []}

        # npm Version
        result = subprocess.run(
            [npm_path, "--version"],
            capture_output=True,
            text=True,
            timeout=10
        )
        npm_version = result.stdout.strip() if result.returncode == 0 else "unknown"

        # Globale Pakete
        result = subprocess.run(
            [npm_path, "list", "-g", "--depth=0", "--json"],
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


def scan_system_tools() -> Dict[str, Any]:
    """Scannt wichtige System-Tools."""
    tools = ["node", "git", "docker", "python", "npm", "curl"]
    result = {}

    for tool in tools:
        check = check_system_tool(tool)
        if check.get("installed"):
            result[tool] = check.get("version", "installed")

    return result


def calculate_health_score(inventory: Dict[str, Any]) -> int:
    """Berechnet einen Health-Score (0-100)."""
    score = 100

    # Abzuege fuer fehlende wichtige Tools
    critical_tools = ["python", "git"]
    for tool in critical_tools:
        if tool not in inventory.get("system", {}):
            score -= 20

    # npm-Fehler beeinflusst Health-Score
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


def save_inventory(inventory: Dict[str, Any]) -> bool:
    """
    Speichert das Inventar in die Datei.

    Args:
        inventory: Das zu speichernde Inventar

    Returns:
        True bei Erfolg, False bei Fehler
    """
    try:
        INVENTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(INVENTORY_PATH, 'w', encoding='utf-8') as f:
            json.dump(inventory, f, indent=2, ensure_ascii=False)
        logger.info(f"Inventar gespeichert: {INVENTORY_PATH}")
        return True
    except Exception as e:
        logger.error(f"Fehler beim Speichern des Inventars: {e}")
        return False


def load_inventory_from_file() -> Dict[str, Any]:
    """Laedt das Inventar aus der Datei (ohne Scan)."""
    try:
        if INVENTORY_PATH.exists():
            with open(INVENTORY_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        logger.warning(f"Fehler beim Laden des Inventars: {e}")

    return {}
