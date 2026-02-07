# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 01.02.2026
Version: 1.0
Beschreibung: Security/Vulnerability-Prüfung für Dependencies.
              Extrahiert aus dependency_agent.py (Regel 1: Max 500 Zeilen)
              Enthält: check_vulnerabilities
"""

import subprocess
import json
import logging
import shutil
from datetime import datetime
from typing import Dict, Any, Optional, Callable

logger = logging.getLogger(__name__)


def check_vulnerabilities(check_enabled: bool = True,
                          on_log: Optional[Callable] = None) -> Dict[str, Any]:
    """
    Prueft auf bekannte Schwachstellen in installierten Paketen.

    Args:
        check_enabled: Ob Vulnerability-Checks aktiviert sind
        on_log: Callback für Logging

    Returns:
        Dict mit vulnerabilities Liste und Severity-Counts
    """
    def _log(event: str, message: Any):
        if on_log:
            on_log("DependencyAgent", event, message)
        logger.info(f"[DependencyAgent] {event}: {message}")

    if not check_enabled:
        return {"enabled": False, "vulnerabilities": []}

    _log("VulnerabilityScan", {"status": "started"})

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
                        # Zaehlung nur in der nachfolgenden Schleife, um Doppelzaehlung zu vermeiden
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

    _log("VulnerabilityScan", {
        "status": "complete",
        "total": len(vulnerabilities),
        "critical": severity_counts["critical"]
    })

    return result
