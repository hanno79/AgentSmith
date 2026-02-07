# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 01.02.2026
Version: 1.0
Beschreibung: Verfügbarkeitsprüfung für Dependencies.
              Extrahiert aus dependency_agent.py (Regel 1: Max 500 Zeilen)
              Enthält: check_dependency, detect_package_type, _check_* Methoden, compare_versions
# ÄNDERUNG [02.02.2026]: try/except + Logging, packaging.version für compare_versions
"""

import subprocess
import json
import logging
import shutil
import re
from datetime import datetime
from typing import Dict, Any, Optional

from .dependency_constants import NPM_PACKAGES, is_builtin_module

logger = logging.getLogger(__name__)

try:
    from packaging.version import Version, InvalidVersion
except ImportError:
    Version = None
    InvalidVersion = Exception  # Fallback


def _log_error(function_name: str, message: str, exc: Exception = None) -> None:
    """Loggt Fehler im Projektformat [TIMESTAMP] [ERROR] [FUNKTION] - Nachricht."""
    ts = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S") + "Z"
    detail = f": {exc}" if exc else ""
    logger.error("[%s] [ERROR] [%s] - %s%s", ts, function_name, message, detail)


def check_dependency(name: str, package_type: str = "auto",
                     min_version: str = None, npm_path: Optional[str] = None,
                     blueprint: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Prueft ob eine Dependency installiert ist.

    Args:
        name: Name des Pakets (z.B. "pytest", "react")
        package_type: "python", "npm", "system" oder "auto" (automatische Erkennung)
        min_version: Optionale Mindestversion
        npm_path: Pfad zu npm (optional)
        blueprint: TechStack Blueprint für Kontext (optional)

    Returns:
        Dict mit installed, version, meets_requirement
    """
    try:
        if package_type == "auto":
            package_type = detect_package_type(name, blueprint)

        if package_type == "python":
            return check_python_package(name, min_version)
        elif package_type == "npm":
            return check_npm_package(name, min_version, npm_path)
        elif package_type == "system":
            return check_system_tool(name, min_version)
        else:
            return {"installed": False, "version": None, "error": f"Unbekannter Pakettyp: {package_type}"}
    except Exception as e:
        _log_error("check_dependency", "Abhängigkeitsprüfung fehlgeschlagen", e)
        return {"installed": False, "version": None, "error": f"Abhängigkeitsprüfung fehlgeschlagen: {e}"}


def detect_package_type(name: str, blueprint: Dict[str, Any] = None) -> str:
    """
    Erkennt automatisch den Pakettyp basierend auf Namen.
    Erweitert um Blueprint-Kontext fuer hybride Projekte.

    Args:
        name: Paketname
        blueprint: Optional - TechStack Blueprint fuer Kontext

    Returns:
        "python", "npm" oder "system"
    """
    try:
        return _detect_package_type_impl(name, blueprint)
    except Exception as e:
        _log_error("detect_package_type", "Pakettyp-Erkennung fehlgeschlagen", e)
        return "python"


def _detect_package_type_impl(name: str, blueprint: Dict[str, Any] = None) -> str:
    """Interne Implementierung der Pakettyp-Erkennung."""
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

    # 3. NPM_PACKAGES Konstante nutzen (umfassender)
    if name_lower in NPM_PACKAGES:
        return "npm"

    # 4. Scoped npm packages (@scope/package)
    if name.startswith("@"):
        return "npm"

    # 5. Typische npm-Paketnamen-Muster
    # AENDERUNG 07.02.2026: UI-Library Keywords hinzugefuegt (shadcn/ui Fix)
    npm_keywords = ["react", "vue", "angular", "svelte", "webpack", "vite", "eslint",
                    "shadcn", "radix", "chakra", "mantine", "headless", "mui", "primereact"]
    if any(kw in name_lower for kw in npm_keywords):
        return "npm"

    # 6. Blueprint-Kontext als Fallback
    # AENDERUNG 07.02.2026: TypeScript-Blueprint erkennt npm (nicht nur "javascript")
    if blueprint:
        bp_lang = blueprint.get("language", "").lower()
        if bp_lang in ("javascript", "typescript"):
            return "npm"

    # Default: Python versuchen
    return "python"


def check_python_package(name: str, min_version: str = None) -> Dict[str, Any]:
    """Prueft ob ein Python-Paket installiert ist."""
    # Built-in Module sind immer "installiert"
    if is_builtin_module(name):
        return {
            "installed": True,
            "version": "builtin",
            "meets_requirement": True,
            "type": "python",
            "note": "Python Built-in Modul (Standardbibliothek)"
        }

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
                meets_requirement = compare_versions(version, min_version) >= 0

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


def check_npm_package(name: str, min_version: str = None, npm_path: Optional[str] = None) -> Dict[str, Any]:
    """Prueft ob ein NPM-Paket global installiert ist."""
    try:
        if not npm_path:
            npm_path = shutil.which("npm")
        if not npm_path:
            return {"installed": False, "version": None, "error": "npm nicht verfuegbar", "type": "npm"}

        result = subprocess.run(
            [npm_path, "list", "-g", name, "--depth=0", "--json"],
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
                    meets_requirement = compare_versions(version, min_version) >= 0
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


def check_system_tool(name: str, min_version: str = None) -> Dict[str, Any]:
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
                match = re.search(r'(\d+\.\d+\.?\d*)', result.stdout)
                if match:
                    version = match.group(1)
        except Exception:
            pass

        meets_requirement = True
        if min_version and version:
            meets_requirement = compare_versions(version, min_version) >= 0

        return {
            "installed": True,
            "version": version,
            "path": path,
            "meets_requirement": meets_requirement,
            "type": "system"
        }

    except Exception as e:
        return {"installed": False, "version": None, "error": str(e), "type": "system"}


def compare_versions(v1: str, v2: str) -> int:
    """
    Vergleicht zwei Versionsnummern (PEP 440). Gibt -1, 0 oder 1 zurueck.
    Nutzt packaging.version.Version für robuste SemVer/PEP-440-Vergleiche.
    """
    if not v1 or not v2:
        return 0
    if Version is not None:
        try:
            a, b = Version(str(v1).strip()), Version(str(v2).strip())
            if a > b:
                return 1
            if a < b:
                return -1
            return 0
        except (InvalidVersion, TypeError, ValueError) as e:
            logger.debug("compare_versions: Ungültige Version (%s, %s): %s", v1, v2, e)
    # Fallback: manuelle Segment-Vergleiche
    try:
        def normalize(v):
            return [int(x) for x in str(v).split(".")[:3]]

        parts1 = normalize(v1)
        parts2 = normalize(v2)
        while len(parts1) < 3:
            parts1.append(0)
        while len(parts2) < 3:
            parts2.append(0)
        if parts1 > parts2:
            return 1
        if parts1 < parts2:
            return -1
        return 0
    except Exception:
        return 0
