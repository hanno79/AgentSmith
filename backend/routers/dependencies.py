# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 29.01.2026
Version: 1.0
Beschreibung: Dependency-Agent Endpunkte für Inventar und Installationen.
"""
# ÄNDERUNG 29.01.2026: Dependency-Endpunkte in eigenes Router-Modul verschoben

from typing import Optional, List
import os
import re
import shlex
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from ..api_logging import log_event
from ..app_state import manager, limiter

router = APIRouter()

_dependency_agent = None


def get_dependency_agent():
    """Lazy-load des Dependency Agents."""
    global _dependency_agent
    if _dependency_agent is None:
        try:
            from agents.dependency_agent import DependencyAgent
            dep_config = manager.config.get("dependency_agent", {})
            _dependency_agent = DependencyAgent(dep_config)
        except Exception as e:
            log_event("API", "Error", f"Dependency Agent konnte nicht geladen werden: {e}")
            return None
    return _dependency_agent


@router.get("/dependencies/inventory")
def get_dependency_inventory(force_refresh: bool = False):
    """
    Gibt das aktuelle Dependency-Inventar zurueck.

    Args:
        force_refresh: Cache ignorieren und neu scannen
    """
    agent = get_dependency_agent()
    if not agent:
        raise HTTPException(status_code=503, detail="Dependency Agent nicht verfuegbar")

    inventory = agent.get_inventory(force_refresh=force_refresh)
    return {"status": "ok", "inventory": inventory}


@router.get("/dependencies/check/{name}")
def check_dependency(name: str, package_type: str = "auto", min_version: Optional[str] = None):
    """
    Prueft ob eine bestimmte Dependency installiert ist.

    Args:
        name: Paketname (z.B. "pytest", "react")
        package_type: "python", "npm", "system" oder "auto"
        min_version: Optionale Mindestversion
    """
    agent = get_dependency_agent()
    if not agent:
        raise HTTPException(status_code=503, detail="Dependency Agent nicht verfuegbar")

    result = agent.check_dependency(name, package_type, min_version)
    return {"status": "ok", "package": name, "result": result}


class InstallRequest(BaseModel):
    install_command: str
    project_path: Optional[str] = None


def _validate_install_command(install_command: str) -> List[str]:
    """
    ÄNDERUNG 29.01.2026: Whitelist-Validierung für Installationsbefehle.
    """
    if not install_command or not install_command.strip():
        raise HTTPException(status_code=400, detail="install_command darf nicht leer sein")

    if any(token in install_command for token in ["&&", ";", "|", "||", "`"]):
        raise HTTPException(status_code=400, detail="install_command enthält unzulässige Zeichen")

    parts = shlex.split(install_command, posix=(os.name != "nt"))
    if not parts:
        raise HTTPException(status_code=400, detail="install_command ist ungültig")

    base = parts[0].lower()
    package_pattern = re.compile(r"^[A-Za-z0-9@/_.\-]+(==[A-Za-z0-9_.\-]+)?$")

    def _validate_packages(args: List[str]):
        for arg in args:
            if arg.startswith("-"):
                raise HTTPException(status_code=400, detail="Nur Paketnamen erlaubt, keine Flags")
            if not package_pattern.match(arg):
                raise HTTPException(status_code=400, detail=f"Ungültiger Paketname: {arg}")

    if base == "pip":
        if len(parts) < 3 or parts[1] != "install":
            raise HTTPException(status_code=400, detail="Nur 'pip install <paket>' erlaubt")
        _validate_packages(parts[2:])
    elif base == "python":
        if len(parts) < 5 or parts[1] != "-m" or parts[2] != "pip" or parts[3] != "install":
            raise HTTPException(status_code=400, detail="Nur 'python -m pip install <paket>' erlaubt")
        _validate_packages(parts[4:])
    elif base == "npm":
        if len(parts) < 2 or parts[1] not in ["install", "i"]:
            raise HTTPException(status_code=400, detail="Nur 'npm install' erlaubt")
        _validate_packages(parts[2:])
    else:
        raise HTTPException(status_code=400, detail=f"Befehl nicht erlaubt: {base}")

    return parts


@router.post("/dependencies/install")
@limiter.limit("5/minute")
def install_dependencies(request: Request, install_request: InstallRequest):
    """
    Fuehrt einen Installationsbefehl aus.

    Body:
        install_command: z.B. "pip install pytest" oder "npm install"
        project_path: Optional - Arbeitsverzeichnis
    """
    agent = get_dependency_agent()
    if not agent:
        raise HTTPException(status_code=503, detail="Dependency Agent nicht verfuegbar")

    # ÄNDERUNG 29.01.2026: Installationsbefehl validieren
    _validate_install_command(install_request.install_command)
    result = agent.install_dependencies(install_request.install_command, install_request.project_path)
    return result


class SinglePackageRequest(BaseModel):
    name: str
    package_type: str = "python"
    version: Optional[str] = None


@router.post("/dependencies/install-package")
@limiter.limit("5/minute")
def install_single_package(request: Request, package_request: SinglePackageRequest):
    """
    Installiert ein einzelnes Paket.

    Body:
        name: Paketname
        package_type: "python" oder "npm"
        version: Optional - Versionsnummer
    """
    agent = get_dependency_agent()
    if not agent:
        raise HTTPException(status_code=503, detail="Dependency Agent nicht verfuegbar")

    result = agent.install_single_package(package_request.name, package_request.package_type, package_request.version)
    return result


@router.post("/dependencies/scan")
def scan_dependencies():
    """Fuehrt einen vollstaendigen Scan aller Dependencies durch."""
    agent = get_dependency_agent()
    if not agent:
        raise HTTPException(status_code=503, detail="Dependency Agent nicht verfuegbar")

    inventory = agent.update_inventory()
    return {"status": "ok", "inventory": inventory}


@router.get("/dependencies/health")
def get_dependency_health():
    """Gibt den Health-Score des Dependency-Systems zurueck."""
    agent = get_dependency_agent()
    if not agent:
        raise HTTPException(status_code=503, detail="Dependency Agent nicht verfuegbar")

    inventory = agent.get_inventory()
    return {
        "status": "ok",
        "health_score": inventory.get("health_score", 0),
        "python_packages": len(inventory.get("python", {}).get("packages", [])),
        "npm_packages": len(inventory.get("npm", {}).get("packages", [])),
        "system_tools": len(inventory.get("system", {})),
        "last_updated": inventory.get("last_updated")
    }


@router.get("/dependencies/vulnerabilities")
def get_dependency_vulnerabilities():
    """Prueft auf bekannte Schwachstellen in installierten Paketen."""
    agent = get_dependency_agent()
    if not agent:
        raise HTTPException(status_code=503, detail="Dependency Agent nicht verfuegbar")

    result = agent.check_vulnerabilities()
    return {"status": "ok", "vulnerabilities": result}
