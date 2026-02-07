# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 01.02.2026
Version: 1.0
Beschreibung: Installations-Funktionen für Dependencies.
              Extrahiert aus dependency_agent.py (Regel 1: Max 500 Zeilen)
              Enthält: install_dependencies, install_single_package, _validate_install_command
"""

import os
import subprocess
import logging
import shlex
import re
from typing import Dict, Any, List, Optional, Callable

from .dependency_constants import is_builtin_module

logger = logging.getLogger(__name__)


def validate_install_command(install_command: str) -> List[str]:
    """
    Whitelist-Validierung für Installationsbefehle.

    Args:
        install_command: Der zu validierende Befehl

    Returns:
        Liste der Befehlsargumente

    Raises:
        ValueError: Bei ungültigen Befehlen
    """
    if not install_command or not install_command.strip():
        raise ValueError("install_command darf nicht leer sein")

    if any(token in install_command for token in ["&&", ";", "|", "||", "`"]):
        raise ValueError("install_command enthält unzulässige Zeichen")

    parts = shlex.split(install_command, posix=(os.name != "nt"))
    if not parts:
        raise ValueError("install_command ist ungültig")

    base = parts[0].lower()
    package_pattern = re.compile(r"^[A-Za-z0-9@/_.\-]+(==[A-Za-z0-9_.\-]+)?$")

    def _validate_packages(args: List[str]):
        for arg in args:
            if arg.startswith("-"):
                raise ValueError("Nur Paketnamen erlaubt, keine Flags")
            if not package_pattern.match(arg):
                raise ValueError(f"Ungültiger Paketname: {arg}")

    if base == "pip":
        if len(parts) < 3 or parts[1] != "install":
            raise ValueError("Nur 'pip install <paket>' erlaubt")
        _validate_packages(parts[2:])
    elif base == "python":
        if len(parts) < 5 or parts[1] != "-m" or parts[2] != "pip" or parts[3] != "install":
            raise ValueError("Nur 'python -m pip install <paket>' erlaubt")
        _validate_packages(parts[4:])
    elif base == "npm":
        if len(parts) < 2 or parts[1] not in ["install", "i"]:
            raise ValueError("Nur 'npm install' erlaubt")
        _validate_packages(parts[2:])
    # AENDERUNG 07.02.2026: npx als erlaubten Befehl hinzufuegen (shadcn/ui Fix)
    # ROOT-CAUSE-FIX: TechStack-Architect generiert "npx shadcn-ui@latest init"
    elif base == "npx":
        if len(parts) < 2:
            raise ValueError("Nur 'npx <paket> [args]' erlaubt")
        pkg_name = parts[1].split("@")[0]
        if not package_pattern.match(pkg_name):
            raise ValueError(f"Ungueltiger npx-Paketname: {parts[1]}")
    else:
        raise ValueError(f"Befehl nicht erlaubt: {base}")

    return parts


def install_dependencies(install_command: str, project_path: str = None,
                         on_log: Optional[Callable] = None,
                         update_inventory: Optional[Callable] = None) -> Dict[str, Any]:
    """
    Fuehrt einen Installationsbefehl aus.

    Args:
        install_command: z.B. "pip install -r requirements.txt" oder "npm install"
        project_path: Arbeitsverzeichnis fuer die Installation
        on_log: Callback für Logging
        update_inventory: Callback zum Aktualisieren des Inventars

    Returns:
        Dict mit status, output, installed_packages
    """
    def _log(event: str, message: Any):
        if on_log:
            on_log("DependencyAgent", event, message)
        logger.info(f"[DependencyAgent] {event}: {message}")

    if not install_command:
        return {"status": "SKIP", "output": "Kein Installationsbefehl angegeben"}

    # AENDERUNG 07.02.2026: Multi-Command-Support fuer verkettete Befehle
    # ROOT-CAUSE-FIX: TechStack-Architect generiert "npm install && npx shadcn-ui@latest init"
    # Symptom: validate_install_command() blockiert "&&" (Security-Whitelist, berechtigt)
    # Loesung: Commands an "&&" splitten, jeden einzeln validiert ausfuehren
    if "&&" in install_command:
        sub_commands = [cmd.strip() for cmd in install_command.split("&&") if cmd.strip()]
        _log("MultiInstall", {"commands": len(sub_commands), "original": install_command[:200]})
        combined_output = []
        for sub_cmd in sub_commands:
            sub_result = install_dependencies(sub_cmd, project_path, on_log, update_inventory)
            combined_output.append(f"[{sub_cmd}]: {sub_result.get('output', '')[:200]}")
            if sub_result.get("status") not in ["OK", "SKIP"]:
                sub_result["output"] = "\n".join(combined_output)
                return sub_result
        return {"status": "OK", "output": "\n".join(combined_output)}

    # Prüfe ob referenzierte Dateien existieren
    if "requirements.txt" in install_command:
        req_path = os.path.join(project_path, "requirements.txt") if project_path else "requirements.txt"
        if not os.path.exists(req_path):
            _log("InstallSkipped", {
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
            _log("InstallSkipped", {
                "command": install_command,
                "reason": f"package.json nicht gefunden: {pkg_path}"
            })
            return {
                "status": "SKIP",
                "output": f"package.json nicht gefunden in {project_path}. Erstelle die Datei mit 'npm init'."
            }

    _log("InstallStart", {"command": install_command, "path": project_path})

    try:
        # Strikte Validierung und sichere Argument-Liste
        parts = validate_install_command(install_command)

        # Arbeitsverzeichnis
        cwd = project_path if project_path and os.path.isdir(project_path) else None

        # Installation ausfuehren
        _log("InstallProgress", {"status": "running", "command": install_command})

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
            _log("InstallComplete", {"status": "OK", "command": install_command})

            # Inventar aktualisieren
            if update_inventory:
                update_inventory()

            return {
                "status": "OK",
                "output": output.strip(),
                "return_code": result.returncode
            }
        else:
            _log("InstallError", {"status": "FAIL", "output": output[:500]})
            return {
                "status": "FAIL",
                "output": output.strip(),
                "return_code": result.returncode
            }

    except ValueError as e:
        _log("InstallError", {"status": "BLOCKED", "error": str(e)})
        return {"status": "BLOCKED", "output": str(e)}
    except subprocess.TimeoutExpired:
        _log("InstallError", {"status": "TIMEOUT"})
        return {"status": "TIMEOUT", "output": "Installation Timeout nach 300 Sekunden"}
    except Exception as e:
        _log("InstallError", {"status": "ERROR", "error": str(e)})
        return {"status": "ERROR", "output": str(e)}


def install_single_package(name: str, package_type: str = "python",
                           version: str = None, npm_path: Optional[str] = None,
                           project_path: Optional[str] = None,
                           on_log: Optional[Callable] = None,
                           update_inventory: Optional[Callable] = None) -> Dict[str, Any]:
    """
    Installiert ein einzelnes Paket.

    Args:
        name: Paketname
        package_type: "python" oder "npm"
        version: Optionale Versionsnummer
        npm_path: Pfad zu npm (optional)
        project_path: Projektverzeichnis fuer lokale npm-Installation (optional)
        on_log: Callback für Logging
        update_inventory: Callback zum Aktualisieren des Inventars

    Returns:
        Dict mit status, output
    """
    def _log(event: str, message: Any):
        if on_log:
            on_log("DependencyAgent", event, message)
        logger.info(f"[DependencyAgent] {event}: {message}")

    if package_type == "python":
        # Built-in Module überspringen
        if is_builtin_module(name):
            _log("InstallSkipped", {
                "package": name,
                "reason": "Python Built-in Modul (bereits in Standardbibliothek)",
                "type": "python"
            })
            return {
                "status": "SKIP",
                "output": f"{name} ist ein Python Built-in Modul und muss nicht installiert werden"
            }

        package_spec = f"{name}=={version}" if version else name
        command = f"python -m pip install {package_spec}"
        return install_dependencies(command, on_log=on_log, update_inventory=update_inventory)

    elif package_type == "npm":
        # npm nur wenn verfuegbar
        if not npm_path:
            _log("InstallSkipped", {
                "package": name,
                "reason": "npm nicht verfuegbar",
                "type": "npm"
            })
            return {
                "status": "SKIPPED",
                "output": f"npm nicht verfuegbar - {name} uebersprungen"
            }

        # AENDERUNG 07.02.2026: Paketnamen normalisieren + lokale Installation
        # ROOT-CAUSE-FIX: "shadcn/ui" verwirrt npm (kein echtes Scoped Package)
        # Echte scoped packages beginnen mit "@" und bleiben unveraendert
        normalized_name = name
        if "/" in name and not name.startswith("@"):
            normalized_name = name.replace("/", "-")

        package_spec = f"{normalized_name}@{version}" if version else normalized_name

        # Lokal installieren (nicht global mit -g)
        # ROOT-CAUSE-FIX: -g macht keinen Sinn fuer Projekt-Dependencies
        try:
            _log("InstallProgress", {"status": "running", "package": name, "type": "npm"})
            cwd = project_path if project_path and os.path.isdir(project_path) else None
            result = subprocess.run(
                [npm_path, "install", package_spec],
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=300,
                encoding='utf-8',
                errors='replace'
            )

            output = result.stdout + "\n" + result.stderr

            if result.returncode == 0:
                _log("InstallComplete", {"status": "OK", "package": name, "type": "npm"})
                if update_inventory:
                    update_inventory()
                return {"status": "OK", "output": output.strip(), "return_code": 0}
            else:
                _log("InstallError", {"status": "FAIL", "output": output[:500]})
                return {"status": "FAIL", "output": output.strip(), "return_code": result.returncode}

        except subprocess.TimeoutExpired:
            _log("InstallError", {"status": "TIMEOUT", "package": name})
            return {"status": "TIMEOUT", "output": "npm Installation Timeout nach 300 Sekunden"}
        except Exception as e:
            _log("InstallError", {"status": "ERROR", "error": str(e)})
            return {"status": "ERROR", "output": str(e)}

    else:
        return {"status": "ERROR", "output": f"Unbekannter Pakettyp: {package_type}"}
