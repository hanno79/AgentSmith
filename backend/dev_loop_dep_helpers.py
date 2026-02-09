# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 08.02.2026
Version: 1.0
Beschreibung: Dependency-Hilfsfunktionen fuer DevLoop.
              Extrahiert aus dev_loop_helpers.py (Regel 1: Max 500 Zeilen)
              Enthaelt: get_python_dependency_versions, _ensure_test_dependencies
              AENDERUNG 08.02.2026: Modul-Extraktion aus dev_loop_helpers.py
"""

import json
from pathlib import Path
from typing import Optional


# =========================================================================
# AENDERUNG 01.02.2026: Dependency-Versions-Loader fuer Coder-Prompt
# =========================================================================

# Haeufig verwendete Python-Pakete die in requirements.txt vorkommen
COMMON_PYTHON_PACKAGES = {
    # Web Frameworks
    "flask", "django", "fastapi", "starlette", "tornado", "bottle",
    # ORM/Database
    "sqlalchemy", "flask-sqlalchemy", "alembic", "psycopg2", "pymysql", "aiosqlite",
    # Dependencies von Flask/SQLAlchemy
    "werkzeug", "jinja2", "itsdangerous", "click", "markupsafe", "greenlet",
    # Testing
    "pytest", "pytest-cov", "coverage", "unittest2",
    # Utils
    "requests", "httpx", "aiohttp", "pydantic", "python-dotenv",
    # Security
    "bcrypt", "cryptography", "pyjwt",
}


def get_python_dependency_versions(
    dependencies_path: Optional[Path] = None,
    filter_common: bool = True
) -> str:
    """
    Liest aktuelle Python-Paket-Versionen aus library/dependencies.json
    und formatiert sie fuer den Coder-Prompt.

    AENDERUNG 01.02.2026: Verhindert dass LLM veraltete/falsche Versionen
    in requirements.txt generiert (z.B. greenlet==2.0.7 statt 3.2.3).

    Args:
        dependencies_path: Pfad zu dependencies.json (default: library/dependencies.json)
        filter_common: Wenn True, nur haeufig verwendete Pakete zurueckgeben

    Returns:
        Formatierter String mit Paket-Versionen fuer den Prompt, oder "" bei Fehler
    """
    if dependencies_path is None:
        dependencies_path = Path("library/dependencies.json")

    if not dependencies_path.exists():
        return ""

    try:
        with open(dependencies_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Extrahiere Python-Pakete mit Versionen
        python_section = data.get("python", {})
        packages = python_section.get("packages", [])

        if not packages:
            return ""

        versions = []
        for pkg in packages:
            name = pkg.get("name", "").lower()
            version = pkg.get("version", "")

            if not name or not version:
                continue

            # Filter: Nur haeufig verwendete Pakete
            if filter_common and name not in COMMON_PYTHON_PACKAGES:
                continue

            # Format: name==version
            versions.append(f"{name}=={version}")

        if not versions:
            return ""

        # Sortieren fuer konsistente Ausgabe
        versions.sort()

        header = "AKTUELLE PAKET-VERSIONEN (verwende diese fuer requirements.txt!):"
        return header + "\n" + "\n".join(versions)

    except (json.JSONDecodeError, IOError, KeyError):
        # Fehler still ignorieren - kein Crash wenn Datei fehlt/ungueltig
        return ""


# =========================================================================
# AENDERUNG 02.02.2026: Automatische pytest-Integration fuer Docker-Tests
# =========================================================================

def _ensure_test_dependencies(requirements_content: str, project_files: list) -> str:
    """
    Fuegt pytest hinzu wenn Test-Dateien existieren aber pytest fehlt.

    AENDERUNG 02.02.2026: Fix #9 - Docker-Tests schlagen fehl mit
    "No module named pytest" weil der Coder test_*.py Dateien erstellt,
    aber pytest nicht in requirements.txt einfuegt.

    Args:
        requirements_content: Aktueller Inhalt der requirements.txt
        project_files: Liste der Dateien im Projekt

    Returns:
        Aktualisierter requirements.txt Inhalt mit pytest falls noetig
    """
    from logger_utils import log_event

    # Pruefe ob Test-Dateien existieren
    has_tests = any(
        "test_" in f or "_test.py" in f or f.startswith("tests/")
        for f in project_files
    )

    # Pruefe ob pytest bereits vorhanden ist
    has_pytest = "pytest" in requirements_content.lower()

    if has_tests and not has_pytest:
        log_event("DevLoop", "AutoFix", "pytest zu requirements.txt hinzugefuegt")
        return requirements_content.strip() + "\npytest>=8.0.0\n"

    return requirements_content
