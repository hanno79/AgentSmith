# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 01.02.2026
Version: 1.0
Beschreibung: CLI-Test-Modul für Tester Agent.
              Extrahiert aus tester_agent.py (Regel 1: Max 500 Zeilen)
              ÄNDERUNG 29.01.2026: CLI-App Testing mit subprocess.
"""

import os
import shlex
import logging
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from .tester_types import UITestResult

logger = logging.getLogger(__name__)


def test_cli_app(project_path: str, tech_blueprint: Dict[str, Any],
                 config: Optional[Dict[str, Any]] = None) -> UITestResult:
    """
    Testet CLI-Anwendungen durch Ausführen und Prüfen des Outputs.

    Args:
        project_path: Pfad zum Projektverzeichnis
        tech_blueprint: Blueprint mit run_command
        config: Optionale Konfiguration

    Returns:
        UITestResult Dictionary
    """
    run_command = tech_blueprint.get("run_command", "python main.py --help")
    if not isinstance(run_command, str):
        run_command = "python main.py --help"
    run_command = run_command.strip() or "python main.py --help"
    argv = shlex.split(run_command, posix=(os.name != "nt")) if run_command else ["python", "main.py", "--help"]
    logger.info(f"Starte CLI-Test: {run_command}")

    result: UITestResult = {
        "status": "OK",
        "issues": [],
        "screenshot": None  # CLI hat keine Screenshots
    }

    try:
        # CLI ausfuehren mit Timeout, ohne Shell (shell=False)
        proc = subprocess.run(
            argv,
            cwd=project_path,
            shell=False,
            capture_output=True,
            timeout=30,
            text=True
        )

        # Prüfe Exit-Code
        if proc.returncode != 0:
            result["issues"].append(f"CLI beendet mit Exit-Code {proc.returncode}")
            if proc.stderr:
                result["issues"].append(f"Stderr: {proc.stderr[:300]}")
            result["status"] = "FAIL"
        else:
            result["issues"].append("CLI läuft erfolgreich")
            if proc.stdout:
                output_file = Path(project_path) / "cli_output.txt"
                try:
                    output_file.parent.mkdir(parents=True, exist_ok=True)
                    with open(output_file, "w", encoding="utf-8") as f:
                        f.write(proc.stdout)
                    result["screenshot"] = str(output_file)
                except (OSError, IOError) as e:
                    logger.warning("CLI-Output konnte nicht geschrieben werden: %s", e)

    except subprocess.TimeoutExpired:
        result["status"] = "FAIL"
        result["issues"].append("CLI-Timeout nach 30 Sekunden")
    except Exception as e:
        result["status"] = "ERROR"
        result["issues"].append(f"CLI-Test Fehler: {str(e)[:200]}")

    return result
