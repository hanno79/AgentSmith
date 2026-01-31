# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 28.01.2026
Version: 1.0
Beschreibung: Unit Test Runner - Fuehrt pytest (Python) oder npm test (JavaScript) aus.
              Wird im DEV-Loop vor den Playwright UI-Tests aufgerufen.
              Erkennt automatisch das Test-Framework basierend auf tech_blueprint.
"""

import os
import subprocess
import logging
import re
import shutil
from pathlib import Path
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)


def run_unit_tests(project_path: str, tech_blueprint: Dict[str, Any]) -> Dict[str, Any]:
    """
    Fuehrt Unit-Tests basierend auf Tech-Stack durch.

    Args:
        project_path: Pfad zum Projektverzeichnis
        tech_blueprint: Blueprint mit language, project_type, etc.

    Returns:
        Dict mit status, summary, details, test_count
    """
    language = tech_blueprint.get("language", "python")
    project_type = str(tech_blueprint.get("project_type", "")).lower()

    logger.info(f"Unit-Test-Runner gestartet fuer {language}/{project_type}")

    # Python-Projekte: pytest
    if language == "python" or "python" in project_type or "flask" in project_type or "fastapi" in project_type:
        return _run_pytest(project_path)

    # JavaScript-Projekte: npm test (jest/vitest/mocha)
    elif language == "javascript" or "node" in project_type or "react" in project_type or "vue" in project_type:
        return _run_npm_test(project_path, project_type)

    # Statische HTML-Projekte: Keine Unit-Tests
    elif language == "html" or project_type == "static_html":
        return {
            "status": "SKIP",
            "summary": "Statisches HTML-Projekt - keine Unit-Tests erforderlich",
            "details": "",
            "test_count": 0
        }

    # Fallback
    return {
        "status": "SKIP",
        "summary": f"Keine Unit-Tests fuer Tech-Stack: {language}/{project_type}",
        "details": "",
        "test_count": 0
    }


def _run_pytest(project_path: str) -> Dict[str, Any]:
    """
    Fuehrt pytest aus.

    Args:
        project_path: Pfad zum Projektverzeichnis

    Returns:
        Dict mit status, summary, details, test_count
    """
    # Pruefen ob tests/ Verzeichnis existiert
    tests_dir = os.path.join(project_path, "tests")
    if not os.path.exists(tests_dir):
        # Alternativ: Test-Dateien im Root suchen
        test_files = _find_python_test_files(project_path)
        if not test_files:
            return {
                "status": "SKIP",
                "summary": "Kein tests/ Verzeichnis und keine *_test.py Dateien gefunden",
                "details": "",
                "test_count": 0
            }

    try:
        # ÄNDERUNG 28.01.2026: python -m pytest statt direktem pytest-Aufruf
        # Damit funktioniert es auch wenn pytest nicht im PATH ist
        result = subprocess.run(
            ["python", "-m", "pytest", project_path, "--tb=short", "-q", "--no-header"],
            cwd=project_path,
            capture_output=True,
            timeout=120,
            text=True,
            encoding='utf-8',
            errors='replace'
        )

        stdout = result.stdout.strip()
        stderr = result.stderr.strip()
        output = stdout if stdout else stderr

        # Test-Anzahl extrahieren (z.B. "5 passed" oder "3 passed, 2 failed")
        test_count = _extract_pytest_count(output)

        if result.returncode == 0:
            return {
                "status": "OK",
                "summary": f"Alle {test_count} Unit-Tests bestanden",
                "details": output,
                "test_count": test_count
            }
        elif result.returncode == 5:
            # Exit code 5 = keine Tests gefunden
            return {
                "status": "SKIP",
                "summary": "Keine Tests gefunden (pytest exit code 5)",
                "details": output,
                "test_count": 0
            }
        else:
            # Tests fehlgeschlagen
            failed_info = _extract_pytest_failures(output)
            return {
                "status": "FAIL",
                "summary": f"Unit-Tests fehlgeschlagen: {failed_info}",
                "details": output,
                "test_count": test_count
            }

    except subprocess.TimeoutExpired:
        return {
            "status": "FAIL",
            "summary": "pytest Timeout nach 120 Sekunden",
            "details": "Tests laufen zu lange - moeglicherweise Endlosschleife",
            "test_count": 0
        }
    except FileNotFoundError:
        return {
            "status": "SKIP",
            "summary": "Python oder pytest nicht gefunden - uebersprungen",
            "details": "Installiere mit: pip install pytest",
            "test_count": 0
        }
    except Exception as e:
        logger.warning(f"pytest Fehler: {e}")
        return {
            "status": "FAIL",
            "summary": f"pytest Fehler: {str(e)[:200]}",
            "details": str(e),
            "test_count": 0
        }


def _run_npm_test(project_path: str, project_type: str) -> Dict[str, Any]:
    """
    Fuehrt npm test (jest/vitest/mocha) aus.

    Args:
        project_path: Pfad zum Projektverzeichnis
        project_type: Projekttyp (react_app, vue_app, nodejs_express, etc.)

    Returns:
        Dict mit status, summary, details, test_count
    """
    package_json = os.path.join(project_path, "package.json")

    if not os.path.exists(package_json):
        return {
            "status": "SKIP",
            "summary": "Keine package.json gefunden",
            "details": "",
            "test_count": 0
        }

    # Pruefen ob test-Script in package.json existiert
    try:
        import json
        with open(package_json, 'r', encoding='utf-8') as f:
            pkg = json.load(f)

        scripts = pkg.get("scripts", {})
        if "test" not in scripts:
            return {
                "status": "SKIP",
                "summary": "Kein 'test' Script in package.json",
                "details": "Fuege 'test': 'jest' oder 'vitest' hinzu",
                "test_count": 0
            }

    except Exception as e:
        logger.warning(f"package.json lesen fehlgeschlagen: {e}")

    try:
        # Validierung und Auflösung von project_path
        project_path_resolved = Path(project_path).resolve()
        
        # Prüfe ob npm verfügbar ist
        npm_path = shutil.which('npm')
        if not npm_path:
            return {
                "status": "SKIP",
                "summary": "npm nicht im PATH gefunden",
                "details": "Node.js und npm müssen installiert sein",
                "test_count": 0
            }
        
        # npm test mit --passWithNoTests (falls jest)
        # shell=False für Sicherheit - Command-Injection verhindern
        # AENDERUNG 31.01.2026: Vollstaendigen npm_path verwenden (Windows: npm.cmd)
        result = subprocess.run(
            [npm_path, "test", "--", "--passWithNoTests", "--silent"],
            cwd=str(project_path_resolved),
            capture_output=True,
            timeout=180,
            text=True,
            encoding='utf-8',
            errors='replace',
            shell=False  # SECURITY: Keine Shell-Interpretation
        )

        stdout = result.stdout.strip()
        stderr = result.stderr.strip()
        output = stdout if stdout else stderr

        # Test-Anzahl extrahieren
        test_count = _extract_npm_test_count(output)

        if result.returncode == 0:
            return {
                "status": "OK",
                "summary": f"Alle {test_count} npm Tests bestanden",
                "details": output,
                "test_count": test_count
            }
        else:
            failed_info = _extract_npm_test_failures(output)
            return {
                "status": "FAIL",
                "summary": f"npm Tests fehlgeschlagen: {failed_info}",
                "details": output,
                "test_count": test_count
            }

    except subprocess.TimeoutExpired:
        return {
            "status": "FAIL",
            "summary": "npm test Timeout nach 180 Sekunden",
            "details": "Tests laufen zu lange",
            "test_count": 0
        }
    except FileNotFoundError:
        return {
            "status": "SKIP",
            "summary": "npm nicht installiert - uebersprungen",
            "details": "Node.js und npm muessen installiert sein",
            "test_count": 0
        }
    except Exception as e:
        logger.warning(f"npm test Fehler: {e}")
        return {
            "status": "FAIL",
            "summary": f"npm test Fehler: {str(e)[:200]}",
            "details": str(e),
            "test_count": 0
        }


def _find_python_test_files(project_path: str) -> List[str]:
    """
    Sucht nach Python-Test-Dateien im Projekt.

    Args:
        project_path: Pfad zum Projektverzeichnis

    Returns:
        Liste der gefundenen Test-Dateien
    """
    test_files = []
    skip_dirs = {'node_modules', 'venv', '.git', '__pycache__', 'screenshots', '.venv'}

    try:
        for root, dirs, files in os.walk(project_path):
            dirs[:] = [d for d in dirs if d not in skip_dirs]

            for filename in files:
                if filename.endswith('.py') and (filename.endswith('_test.py') or filename.startswith('test_')):
                    test_files.append(os.path.join(root, filename))

    except Exception as e:
        logger.warning(f"Fehler beim Suchen nach Test-Dateien: {e}")

    return test_files


def _extract_pytest_count(output: str) -> int:
    """Extrahiert die Anzahl der Tests aus pytest-Output."""
    # Suche nach "X passed" oder "X passed, Y failed"
    match = re.search(r'(\d+)\s+passed', output)
    passed = int(match.group(1)) if match else 0

    match = re.search(r'(\d+)\s+failed', output)
    failed = int(match.group(1)) if match else 0

    return passed + failed


def _extract_pytest_failures(output: str) -> str:
    """Extrahiert Fehler-Info aus pytest-Output."""
    # Suche nach "X passed, Y failed"
    match = re.search(r'(\d+)\s+failed', output)
    if match:
        failed = match.group(1)
        return f"{failed} Test(s) fehlgeschlagen"

    # Suche nach FAILED-Zeilen
    failed_tests = re.findall(r'FAILED\s+(.+?)(?:\s+-|$)', output)
    if failed_tests:
        return f"{len(failed_tests)} Test(s): {', '.join(failed_tests[:3])}"

    return "Details siehe Output"


def _extract_npm_test_count(output: str) -> int:
    """Extrahiert die Anzahl der Tests aus npm test/jest-Output."""
    # Jest-Format: "Tests: X passed, Y total"
    match = re.search(r'Tests:\s+(\d+)\s+passed', output)
    if match:
        return int(match.group(1))

    # Alternative: "X tests passed"
    match = re.search(r'(\d+)\s+tests?\s+passed', output)
    if match:
        return int(match.group(1))

    return 0


def _extract_npm_test_failures(output: str) -> str:
    """Extrahiert Fehler-Info aus npm test/jest-Output."""
    # Jest-Format: "X failed"
    match = re.search(r'(\d+)\s+failed', output)
    if match:
        return f"{match.group(1)} Test(s) fehlgeschlagen"

    # Suche nach FAIL-Zeilen
    failed_tests = re.findall(r'FAIL\s+(.+?)(?:\n|$)', output)
    if failed_tests:
        return f"{len(failed_tests)} Test-Suite(s) fehlgeschlagen"

    return "Details siehe Output"


def select_test_framework(tech_blueprint: Dict[str, Any]) -> str:
    """
    Waehlt das passende Test-Framework basierend auf tech_blueprint.

    Args:
        tech_blueprint: Blueprint mit language, project_type

    Returns:
        Framework-Name: "pytest", "jest", "vitest", "none"
    """
    language = tech_blueprint.get("language", "python")
    project_type = str(tech_blueprint.get("project_type", "")).lower()

    if language == "python":
        return "pytest"
    elif language == "javascript":
        if project_type in ["vue_app"]:
            return "vitest"
        else:
            return "jest"
    elif language == "html" or project_type == "static_html":
        return "none"
    else:
        return "unknown"
