# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 31.01.2026
Version: 1.0
Beschreibung: Dependency Checker - Prueft kritische Dependencies beim Server-Start.
              Installiert fehlende Packages automatisch.
"""

import subprocess
import sys
import logging
from typing import List, Tuple

logger = logging.getLogger(__name__)

# Kritische Packages die fuer den Betrieb benoetigt werden
# Format: (package_import_name, package_install_name, zweck)
CRITICAL_PACKAGES: List[Tuple[str, str, str]] = [
    ("pyautogui", "pyautogui", "Desktop-App Testing"),
    ("playwright", "playwright", "Web-App Testing"),
    ("pytest", "pytest", "Unit Testing"),
    ("PIL", "Pillow", "Screenshot-Verarbeitung"),
]


def check_package(import_name: str) -> bool:
    """
    Prueft ob ein Package importiert werden kann.

    Args:
        import_name: Name des Packages fuer Import

    Returns:
        True wenn Package verfuegbar
    """
    try:
        __import__(import_name)
        return True
    except ImportError:
        return False


def install_package(install_name: str) -> bool:
    """
    Installiert ein Package via pip.

    Args:
        install_name: Name des Packages fuer pip install

    Returns:
        True wenn Installation erfolgreich
    """
    try:
        logger.info(f"Installiere {install_name}...")
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", install_name, "-q"],
            capture_output=True,
            text=True,
            timeout=120  # 2 Minuten Timeout
        )
        if result.returncode == 0:
            logger.info(f"{install_name} erfolgreich installiert")
            return True
        else:
            logger.error(f"Installation von {install_name} fehlgeschlagen: {result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        logger.error(f"Installation von {install_name} Timeout nach 120s")
        return False
    except Exception as e:
        logger.error(f"Installation von {install_name} Fehler: {e}")
        return False


def check_and_install_dependencies(auto_install: bool = True) -> dict:
    """
    Prueft kritische Dependencies und installiert fehlende automatisch.

    Args:
        auto_install: Wenn True, werden fehlende Packages installiert

    Returns:
        Dict mit Status-Informationen:
        {
            "checked": [...],
            "missing": [...],
            "installed": [...],
            "failed": [...]
        }
    """
    result = {
        "checked": [],
        "missing": [],
        "installed": [],
        "failed": []
    }

    logger.info("Pruefe kritische Dependencies...")

    for import_name, install_name, purpose in CRITICAL_PACKAGES:
        result["checked"].append(import_name)

        if check_package(import_name):
            logger.debug(f"{import_name} OK ({purpose})")
        else:
            logger.warning(f"{import_name} fehlt ({purpose})")
            result["missing"].append(import_name)

            if auto_install:
                if install_package(install_name):
                    result["installed"].append(import_name)
                    # Versuche erneut zu importieren
                    if check_package(import_name):
                        logger.info(f"{import_name} jetzt verfuegbar")
                    else:
                        result["failed"].append(import_name)
                else:
                    result["failed"].append(import_name)

    # Zusammenfassung loggen
    if result["installed"]:
        logger.info(f"Installierte Packages: {', '.join(result['installed'])}")
    if result["failed"]:
        logger.warning(f"Fehlgeschlagene Installationen: {', '.join(result['failed'])}")
    if not result["missing"]:
        logger.info("Alle kritischen Dependencies sind verfuegbar")

    return result


def get_dependency_status() -> dict:
    """
    Gibt den aktuellen Status aller Dependencies zurueck ohne zu installieren.

    Returns:
        Dict mit Package-Status
    """
    status = {}
    for import_name, install_name, purpose in CRITICAL_PACKAGES:
        status[import_name] = {
            "available": check_package(import_name),
            "purpose": purpose,
            "install_name": install_name
        }
    return status


# Beim Import des Moduls automatisch pruefen (aber nicht installieren)
# Die Installation erfolgt explizit beim Server-Start
if __name__ == "__main__":
    # Direkter Aufruf: Pruefe und installiere
    import logging
    logging.basicConfig(level=logging.INFO)
    result = check_and_install_dependencies(auto_install=True)
    print(f"\nErgebnis: {result}")
