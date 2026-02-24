# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 14.02.2026
Version: 1.0
Beschreibung: Unit Tests fuer agents/tester_types.py - UITestResult TypedDict
              und Tester-Konstanten.
"""

import os
import sys
import pytest

# Projekt-Root zum Python-Path hinzufuegen
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.tester_types import (
    UITestResult,
    DEFAULT_GLOBAL_TIMEOUT,
    DEFAULT_NETWORKIDLE_TIMEOUT,
    MAX_RETRIES,
    RETRY_DELAY,
)


# =========================================================================
# Tests fuer UITestResult TypedDict
# =========================================================================
class TestUITestResult:
    """Tests fuer die UITestResult Typdefinition."""

    def test_gueltige_instanz_mit_allen_feldern(self):
        """UITestResult kann mit allen Pflichtfeldern erstellt werden."""
        result: UITestResult = {
            "status": "OK",
            "issues": [],
            "screenshot": None
        }
        assert result["status"] == "OK"
        assert result["issues"] == []
        assert result["screenshot"] is None

    def test_status_ok(self):
        """Status OK wird korrekt gespeichert."""
        result: UITestResult = {"status": "OK", "issues": [], "screenshot": None}
        assert result["status"] == "OK"

    def test_status_fail_mit_issues(self):
        """Status FAIL mit Issues-Liste."""
        result: UITestResult = {
            "status": "FAIL",
            "issues": ["Button nicht sichtbar", "Farbe falsch"],
            "screenshot": "/tmp/screenshot.png"
        }
        assert result["status"] == "FAIL"
        assert len(result["issues"]) == 2
        assert "Button nicht sichtbar" in result["issues"]

    def test_status_review(self):
        """Status REVIEW wird korrekt gespeichert."""
        result: UITestResult = {"status": "REVIEW", "issues": ["Manuell pruefen"], "screenshot": None}
        assert result["status"] == "REVIEW"

    def test_status_baseline(self):
        """Status BASELINE wird korrekt gespeichert."""
        result: UITestResult = {"status": "BASELINE", "issues": [], "screenshot": "/tmp/base.png"}
        assert result["status"] == "BASELINE"
        assert result["screenshot"] == "/tmp/base.png"

    def test_status_error(self):
        """Status ERROR wird korrekt gespeichert."""
        result: UITestResult = {"status": "ERROR", "issues": ["Timeout"], "screenshot": None}
        assert result["status"] == "ERROR"

    def test_status_skip(self):
        """Status SKIP wird korrekt gespeichert."""
        result: UITestResult = {"status": "SKIP", "issues": [], "screenshot": None}
        assert result["status"] == "SKIP"

    def test_screenshot_mit_pfad(self):
        """Screenshot kann einen Dateipfad enthalten."""
        result: UITestResult = {
            "status": "OK",
            "issues": [],
            "screenshot": "C:\\Temp\\screenshots\\test.png"
        }
        assert result["screenshot"] == "C:\\Temp\\screenshots\\test.png"

    def test_leere_issues_liste(self):
        """Leere Issues-Liste bei erfolgreichem Test."""
        result: UITestResult = {"status": "OK", "issues": [], "screenshot": None}
        assert result["issues"] == []
        assert isinstance(result["issues"], list)

    def test_mehrere_issues(self):
        """Mehrere Issues koennen in der Liste gespeichert werden."""
        issues = [
            "Element #submit nicht gefunden",
            "CSS-Klasse .header fehlt",
            "Responsive Layout fehlerhaft"
        ]
        result: UITestResult = {"status": "FAIL", "issues": issues, "screenshot": None}
        assert len(result["issues"]) == 3

    def test_uitestresult_ist_dict_kompatibel(self):
        """UITestResult ist dict-kompatibel (TypedDict-Eigenschaft)."""
        result: UITestResult = {"status": "OK", "issues": [], "screenshot": None}
        assert isinstance(result, dict)
        assert "status" in result

    def test_uitestresult_keys(self):
        """UITestResult hat genau die erwarteten Keys in __annotations__."""
        erwartete_keys = {"status", "issues", "screenshot"}
        assert set(UITestResult.__annotations__.keys()) == erwartete_keys


# =========================================================================
# Tests fuer Tester-Konstanten
# =========================================================================
class TestTesterKonstanten:
    """Tests fuer konfigurierbare Konstanten."""

    def test_default_global_timeout_ist_positiv(self):
        """DEFAULT_GLOBAL_TIMEOUT ist positiv (Millisekunden)."""
        assert DEFAULT_GLOBAL_TIMEOUT > 0
        assert DEFAULT_GLOBAL_TIMEOUT == 10000

    def test_default_networkidle_timeout_ist_positiv(self):
        """DEFAULT_NETWORKIDLE_TIMEOUT ist positiv (Millisekunden)."""
        assert DEFAULT_NETWORKIDLE_TIMEOUT > 0
        assert DEFAULT_NETWORKIDLE_TIMEOUT == 3000

    def test_max_retries_ist_positiv(self):
        """MAX_RETRIES ist eine positive Ganzzahl."""
        assert MAX_RETRIES > 0
        assert MAX_RETRIES == 3
        assert isinstance(MAX_RETRIES, int)

    def test_retry_delay_ist_positiv(self):
        """RETRY_DELAY ist positiv (Sekunden)."""
        assert RETRY_DELAY > 0
        assert RETRY_DELAY == 2

    def test_networkidle_kleiner_als_global_timeout(self):
        """Netzwerk-Idle-Timeout muss kleiner als globaler Timeout sein."""
        assert DEFAULT_NETWORKIDLE_TIMEOUT < DEFAULT_GLOBAL_TIMEOUT

    def test_konstanten_sind_integers(self):
        """Alle Konstanten sind ganzzahlige Werte."""
        assert isinstance(DEFAULT_GLOBAL_TIMEOUT, int)
        assert isinstance(DEFAULT_NETWORKIDLE_TIMEOUT, int)
        assert isinstance(MAX_RETRIES, int)
        assert isinstance(RETRY_DELAY, int)
