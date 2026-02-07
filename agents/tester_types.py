# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 01.02.2026
Version: 1.0
Beschreibung: Gemeinsame Typen für Tester-Module.
              Extrahiert aus tester_agent.py (Regel 1: Max 500 Zeilen)
"""

from typing import List, Optional
from typing_extensions import TypedDict


class UITestResult(TypedDict):
    """Typdefinition für UI-Testergebnisse."""
    status: str  # "OK", "FAIL", "REVIEW", "BASELINE", "ERROR", "SKIP"
    issues: List[str]
    screenshot: Optional[str]


# Konfigurierbare Konstanten (Standardwerte)
DEFAULT_GLOBAL_TIMEOUT = 10000  # 10 Sekunden
DEFAULT_NETWORKIDLE_TIMEOUT = 3000  # 3 Sekunden
MAX_RETRIES = 3
RETRY_DELAY = 2  # Sekunden Basis-Wartezeit
