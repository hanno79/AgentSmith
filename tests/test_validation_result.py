# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 14.02.2026
Version: 1.0
Beschreibung: Tests fuer backend/validation_result.py
              Testet ValidationResult Dataclass mit allen Default-Werten.
"""

import os
import sys
import pytest

# Projekt-Root zum Python-Path hinzufuegen
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.validation_result import ValidationResult


class TestValidationResultDefaults:
    """Tests fuer ValidationResult Default-Werte."""

    def test_default_passed_ist_pflicht(self):
        """passed ist Pflichtfeld (kein Default)."""
        vr = ValidationResult(passed=True)
        assert vr.passed is True

    def test_default_issues_leer(self):
        """issues ist standardmaessig leere Liste."""
        vr = ValidationResult(passed=True)
        assert vr.issues == []

    def test_default_warnings_leer(self):
        """warnings ist standardmaessig leere Liste."""
        vr = ValidationResult(passed=True)
        assert vr.warnings == []

    def test_default_score_eins(self):
        """score ist standardmaessig 1.0."""
        vr = ValidationResult(passed=True)
        assert vr.score == 1.0

    def test_default_details_leer(self):
        """details ist standardmaessig leeres Dict."""
        vr = ValidationResult(passed=True)
        assert vr.details == {}


class TestValidationResultMitWerten:
    """Tests fuer ValidationResult mit expliziten Werten."""

    def test_passed_false(self):
        """passed=False wird korrekt gespeichert."""
        vr = ValidationResult(passed=False)
        assert vr.passed is False

    def test_issues_liste(self):
        """Issues-Liste wird korrekt gespeichert."""
        issues = ["Fehler 1", "Fehler 2"]
        vr = ValidationResult(passed=False, issues=issues)
        assert vr.issues == issues
        assert len(vr.issues) == 2

    def test_warnings_liste(self):
        """Warnings-Liste wird korrekt gespeichert."""
        warnings = ["Warnung 1"]
        vr = ValidationResult(passed=True, warnings=warnings)
        assert vr.warnings == warnings

    def test_score_benutzerdefiniert(self):
        """Benutzerdefinierter Score wird gespeichert."""
        vr = ValidationResult(passed=False, score=0.5)
        assert vr.score == 0.5

    def test_details_dict(self):
        """Details-Dict wird korrekt gespeichert."""
        details = {"check": "syntax", "duration": 1.5}
        vr = ValidationResult(passed=True, details=details)
        assert vr.details["check"] == "syntax"
        assert vr.details["duration"] == 1.5

    def test_vollstaendig_konfiguriert(self):
        """Alle Felder werden korrekt gesetzt."""
        vr = ValidationResult(
            passed=False,
            issues=["I1"],
            warnings=["W1"],
            score=0.3,
            details={"key": "val"}
        )
        assert vr.passed is False
        assert vr.issues == ["I1"]
        assert vr.warnings == ["W1"]
        assert vr.score == 0.3
        assert vr.details == {"key": "val"}


class TestValidationResultMutierbarkeit:
    """Tests fuer Veraenderbarkeit der Listen-Felder."""

    def test_issues_mutierbar(self):
        """Issues-Liste kann nach Erstellung geaendert werden."""
        vr = ValidationResult(passed=True)
        vr.issues.append("Neues Problem")
        assert len(vr.issues) == 1

    def test_keine_geteilte_default_liste(self):
        """Zwei Instanzen teilen sich NICHT dieselbe Default-Liste."""
        vr1 = ValidationResult(passed=True)
        vr2 = ValidationResult(passed=True)
        vr1.issues.append("Nur in vr1")
        assert len(vr2.issues) == 0

    def test_score_update(self):
        """Score kann nach Erstellung geaendert werden."""
        vr = ValidationResult(passed=True, score=1.0)
        vr.score = 0.7
        assert vr.score == 0.7
