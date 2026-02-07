# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 01.02.2026
Version: 1.0
Beschreibung: Unit Tests für Dart AI Validators - Anforderungs-, Feature- und Plan-Validierung.

              Tests validieren:
              - validate_anforderungen: Analyst-Output Validierung
              - validate_features: Konzepter-Output Validierung
              - validate_file_by_file_plan: Plan-Validierung
              - validate_file_by_file_output: Output-Completeness Check
"""

import pytest
import sys
import os
import tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.dart_ai_validators import (
    validate_anforderungen,
    validate_features,
    validate_file_by_file_plan,
    validate_file_by_file_output
)
from backend.validation_result import ValidationResult


# =========================================================================
# Fixtures
# =========================================================================

@pytest.fixture
def valid_briefing():
    """Standard Discovery-Briefing für Tests."""
    return {
        "answers": [
            {"question": "Was ist das Projektziel?", "answer": "Todo-App erstellen", "skipped": False},
            {"question": "Welche Features?", "answer": "CRUD für Tasks", "skipped": False},
            {"question": "Welche Technik?", "answer": "Python Flask", "skipped": False}
        ]
    }


@pytest.fixture
def valid_analyst_output():
    """Gültiger Analyst-Output für Tests."""
    return {
        "anforderungen": [
            {
                "id": "ANF-001",
                "titel": "Task-Erstellung",
                "beschreibung": "Benutzer kann neue Tasks erstellen",
                "kategorie": "funktional",
                "prioritaet": "hoch"
            },
            {
                "id": "ANF-002",
                "titel": "Task-Anzeige",
                "beschreibung": "Benutzer kann alle Tasks sehen",
                "kategorie": "funktional",
                "prioritaet": "hoch"
            }
        ],
        "kategorien": ["funktional", "nicht-funktional"]
    }


@pytest.fixture
def valid_konzepter_output():
    """Gültiger Konzepter-Output für Tests."""
    return {
        "features": [
            {
                "id": "FEAT-001",
                "titel": "Task-Management",
                "beschreibung": "CRUD-Operationen für Tasks",
                "anforderungen": ["ANF-001", "ANF-002"],
                "geschaetzte_dateien": 2
            }
        ],
        "traceability": {
            "ANF-001": ["FEAT-001"],
            "ANF-002": ["FEAT-001"]
        }
    }


@pytest.fixture
def valid_file_plan():
    """Gültiger File-by-File Plan für Tests."""
    return {
        "files": [
            {
                "path": "app.py",
                "description": "Flask Hauptanwendung",
                "depends_on": []
            },
            {
                "path": "models.py",
                "description": "Datenbank-Modelle",
                "depends_on": []
            },
            {
                "path": "routes.py",
                "description": "API-Routen",
                "depends_on": ["app.py", "models.py"]
            }
        ]
    }


@pytest.fixture
def valid_blueprint():
    """Standard TechStack Blueprint für Tests."""
    return {
        "language": "python",
        "framework": "flask"
    }


# =========================================================================
# Test: validate_anforderungen
# =========================================================================

class TestValidateAnforderungen:
    """Tests für validate_anforderungen Funktion."""

    def test_valid_anforderungen_passes(self, valid_analyst_output, valid_briefing):
        """Gültige Anforderungen bestehen die Validierung."""
        result = validate_anforderungen(valid_analyst_output, valid_briefing)
        assert result.passed is True
        assert len(result.issues) == 0
        assert result.score > 0.8

    def test_empty_anforderungen_fails(self, valid_briefing):
        """Leere Anforderungsliste schlägt fehl."""
        result = validate_anforderungen({"anforderungen": []}, valid_briefing)
        assert result.passed is False
        assert "Keine Anforderungen extrahiert" in result.issues
        assert result.score == 0.0

    def test_none_output_fails(self, valid_briefing):
        """None als Output schlägt fehl."""
        result = validate_anforderungen({}, valid_briefing)
        assert result.passed is False
        assert result.score == 0.0

    def test_missing_required_fields_warning(self, valid_briefing):
        """Fehlende Pflichtfelder erzeugen Warnungen."""
        incomplete_output = {
            "anforderungen": [
                {"id": "ANF-001", "titel": "Test"}  # Fehlt: beschreibung, kategorie, prioritaet
            ],
            "kategorien": []
        }
        result = validate_anforderungen(incomplete_output, valid_briefing)
        assert result.passed is True  # Fehlende Felder sind nur Warnungen
        assert len(result.warnings) > 0
        assert any("fehlt" in w for w in result.warnings)

    def test_duplicate_ids_fails(self, valid_briefing):
        """Doppelte IDs erzeugen einen Fehler."""
        duplicate_output = {
            "anforderungen": [
                {"id": "ANF-001", "titel": "Test 1", "beschreibung": "Desc", "kategorie": "func", "prioritaet": "hoch"},
                {"id": "ANF-001", "titel": "Test 2", "beschreibung": "Desc", "kategorie": "func", "prioritaet": "mittel"}
            ],
            "kategorien": ["func"]
        }
        result = validate_anforderungen(duplicate_output, valid_briefing)
        assert result.passed is False
        assert any("Doppelte" in i for i in result.issues)

    def test_unknown_category_warning(self, valid_briefing):
        """Unbekannte Kategorie erzeugt Warnung."""
        output = {
            "anforderungen": [
                {"id": "ANF-001", "titel": "Test", "beschreibung": "Desc",
                 "kategorie": "unbekannte_kategorie", "prioritaet": "hoch"}
            ],
            "kategorien": ["funktional"]
        }
        result = validate_anforderungen(output, valid_briefing)
        assert any("unbekannte Kategorie" in w for w in result.warnings)

    def test_low_coverage_warning(self):
        """Wenige Anforderungen für viele Discovery-Antworten erzeugen Warnung."""
        big_briefing = {
            "answers": [{"question": f"Q{i}", "answer": f"A{i}", "skipped": False} for i in range(10)]
        }
        small_output = {
            "anforderungen": [
                {"id": "ANF-001", "titel": "Test", "beschreibung": "Desc",
                 "kategorie": "func", "prioritaet": "hoch"}
            ],
            "kategorien": ["func"]
        }
        result = validate_anforderungen(small_output, big_briefing)
        # Sollte Warnung über geringe Abdeckung geben
        assert any("Anforderungen" in w and "Discovery-Antworten" in w for w in result.warnings)

    def test_skipped_answers_not_counted(self, valid_analyst_output):
        """Übersprungene Antworten werden nicht für Coverage gezählt."""
        briefing_with_skips = {
            "answers": [
                {"question": "Q1", "answer": "A1", "skipped": False},
                {"question": "Q2", "answer": "", "skipped": True},
                {"question": "Q3", "answer": "", "skipped": True}
            ]
        }
        result = validate_anforderungen(valid_analyst_output, briefing_with_skips)
        assert result.passed is True

    def test_details_contain_counts(self, valid_analyst_output, valid_briefing):
        """Details enthalten Zählungen."""
        result = validate_anforderungen(valid_analyst_output, valid_briefing)
        assert "total_anforderungen" in result.details
        assert result.details["total_anforderungen"] == 2
        assert "kategorien" in result.details


# =========================================================================
# Test: validate_features
# =========================================================================

class TestValidateFeatures:
    """Tests für validate_features Funktion."""

    def test_valid_features_passes(self, valid_konzepter_output, valid_analyst_output):
        """Gültige Features bestehen die Validierung."""
        anforderungen = valid_analyst_output["anforderungen"]
        result = validate_features(valid_konzepter_output, anforderungen)
        assert result.passed is True
        assert len(result.issues) == 0

    def test_empty_features_fails(self, valid_analyst_output):
        """Leere Feature-Liste schlägt fehl."""
        anforderungen = valid_analyst_output["anforderungen"]
        result = validate_features({"features": []}, anforderungen)
        assert result.passed is False
        assert "Keine Features extrahiert" in result.issues

    def test_missing_required_fields_warning(self, valid_analyst_output):
        """Fehlende Pflichtfelder erzeugen Warnungen."""
        incomplete = {
            "features": [{"id": "FEAT-001"}],  # Fehlt: titel, anforderungen
            "traceability": {}
        }
        anforderungen = valid_analyst_output["anforderungen"]
        result = validate_features(incomplete, anforderungen)
        assert len(result.warnings) > 0
        assert any("fehlt" in w for w in result.warnings)

    def test_duplicate_feature_ids_fails(self, valid_analyst_output):
        """Doppelte Feature-IDs erzeugen Fehler."""
        duplicate = {
            "features": [
                {"id": "FEAT-001", "titel": "Test 1", "anforderungen": ["ANF-001"]},
                {"id": "FEAT-001", "titel": "Test 2", "anforderungen": ["ANF-002"]}
            ],
            "traceability": {}
        }
        anforderungen = valid_analyst_output["anforderungen"]
        result = validate_features(duplicate, anforderungen)
        assert result.passed is False
        assert any("Doppelte" in i for i in result.issues)

    def test_uncovered_anforderungen_warning(self, valid_analyst_output):
        """Nicht abgedeckte Anforderungen erzeugen Warnung."""
        partial = {
            "features": [
                {"id": "FEAT-001", "titel": "Test", "anforderungen": ["ANF-001"]}
            ],
            "traceability": {"ANF-001": ["FEAT-001"]}  # ANF-002 fehlt
        }
        anforderungen = valid_analyst_output["anforderungen"]
        result = validate_features(partial, anforderungen)
        assert any("ohne Features" in w for w in result.warnings)

    def test_invalid_anforderung_reference_warning(self, valid_analyst_output):
        """Referenz auf nicht existierende Anforderung erzeugt Warnung."""
        invalid_ref = {
            "features": [
                {"id": "FEAT-001", "titel": "Test", "anforderungen": ["ANF-999"]}  # ANF-999 existiert nicht
            ],
            "traceability": {}
        }
        anforderungen = valid_analyst_output["anforderungen"]
        result = validate_features(invalid_ref, anforderungen)
        assert any("unbekannte Anforderung" in w for w in result.warnings)

    def test_high_file_estimate_warning(self, valid_analyst_output):
        """Hohe Datei-Schätzung erzeugt Warnung."""
        high_estimate = {
            "features": [
                {"id": "FEAT-001", "titel": "Test", "anforderungen": ["ANF-001"],
                 "geschaetzte_dateien": 10}  # > 3 empfohlen
            ],
            "traceability": {"ANF-001": ["FEAT-001"]}
        }
        anforderungen = valid_analyst_output["anforderungen"]
        result = validate_features(high_estimate, anforderungen)
        assert any("geschaetzte Dateien" in w for w in result.warnings)

    def test_details_contain_coverage(self, valid_konzepter_output, valid_analyst_output):
        """Details enthalten Traceability-Coverage."""
        anforderungen = valid_analyst_output["anforderungen"]
        result = validate_features(valid_konzepter_output, anforderungen)
        assert "traceability_coverage" in result.details
        assert result.details["traceability_coverage"] == 1.0  # 100% abgedeckt


# =========================================================================
# Test: validate_file_by_file_plan
# =========================================================================

class TestValidateFileByFilePlan:
    """Tests für validate_file_by_file_plan Funktion."""

    def test_valid_plan_passes(self, valid_file_plan, valid_blueprint):
        """Gültiger Plan besteht die Validierung."""
        result = validate_file_by_file_plan(valid_file_plan, valid_blueprint)
        assert result.passed is True
        assert len(result.issues) == 0

    def test_empty_files_fails(self, valid_blueprint):
        """Leere Dateiliste schlägt fehl."""
        result = validate_file_by_file_plan({"files": []}, valid_blueprint)
        assert result.passed is False
        assert "Keine Dateien im Plan" in result.issues

    def test_file_without_path_fails(self, valid_blueprint):
        """Datei ohne Pfad erzeugt Fehler."""
        plan = {
            "files": [{"description": "Test ohne Pfad"}]
        }
        result = validate_file_by_file_plan(plan, valid_blueprint)
        assert result.passed is False
        assert any("ohne Pfad" in i for i in result.issues)

    def test_file_without_description_warning(self, valid_blueprint):
        """Datei ohne Beschreibung erzeugt Warnung."""
        plan = {
            "files": [{"path": "test.py"}]  # Keine Beschreibung
        }
        result = validate_file_by_file_plan(plan, valid_blueprint)
        assert any("ohne Beschreibung" in w for w in result.warnings)

    def test_duplicate_paths_fails(self, valid_blueprint):
        """Doppelte Pfade erzeugen Fehler."""
        plan = {
            "files": [
                {"path": "app.py", "description": "App 1"},
                {"path": "app.py", "description": "App 2"}  # Duplikat
            ]
        }
        result = validate_file_by_file_plan(plan, valid_blueprint)
        assert result.passed is False
        assert any("Doppelte" in i for i in result.issues)

    def test_unknown_dependency_warning(self, valid_blueprint):
        """Unbekannte Abhängigkeit erzeugt Warnung."""
        plan = {
            "files": [
                {"path": "app.py", "description": "App", "depends_on": ["nicht_existiert.py"]}
            ]
        }
        result = validate_file_by_file_plan(plan, valid_blueprint)
        assert any("unbekannte Abhaengigkeit" in w for w in result.warnings)

    def test_circular_dependency_fails(self, valid_blueprint):
        """Zirkuläre Abhängigkeit erzeugt Fehler."""
        plan = {
            "files": [
                {"path": "app.py", "description": "App", "depends_on": ["app.py"]}  # Selbst-Referenz
            ]
        }
        result = validate_file_by_file_plan(plan, valid_blueprint)
        assert result.passed is False
        assert any("von sich selbst ab" in i for i in result.issues)

    def test_wrong_extension_warning(self, valid_blueprint):
        """Falsche Dateiendung für Sprache erzeugt Warnung."""
        plan = {
            "files": [
                {"path": "app.js", "description": "JavaScript in Python-Projekt"}  # .js statt .py
            ]
        }
        result = validate_file_by_file_plan(plan, valid_blueprint)
        assert any("unerwartete Endung" in w for w in result.warnings)

    def test_non_code_files_ignored_for_extension_check(self, valid_blueprint):
        """Nicht-Code-Dateien werden bei Endungsprüfung ignoriert."""
        plan = {
            "files": [
                {"path": "README.md", "description": "Dokumentation"},
                {"path": "config.json", "description": "Konfiguration"},
                {"path": "app.py", "description": "Hauptanwendung"}
            ]
        }
        result = validate_file_by_file_plan(plan, valid_blueprint)
        # Sollte keine Warnungen für .md und .json geben
        extension_warnings = [w for w in result.warnings if "unerwartete Endung" in w]
        assert len(extension_warnings) == 0

    def test_details_contain_file_count(self, valid_file_plan, valid_blueprint):
        """Details enthalten Datei-Anzahl."""
        result = validate_file_by_file_plan(valid_file_plan, valid_blueprint)
        assert "total_files" in result.details
        assert result.details["total_files"] == 3


# =========================================================================
# Test: validate_file_by_file_output
# =========================================================================

class TestValidateFileByFileOutput:
    """Tests für validate_file_by_file_output Funktion."""

    def test_all_files_created_passes(self, valid_file_plan):
        """Alle geplanten Dateien erstellt besteht Validierung."""
        created = ["app.py", "models.py", "routes.py"]
        result = validate_file_by_file_output(created, valid_file_plan)
        assert result.passed is True
        assert len(result.issues) == 0

    def test_missing_files_warning(self):
        """Wenige fehlende Dateien erzeugen Warnung."""
        # Plan mit 10 Dateien, 9 erstellt = 90% Erfolgsrate (>70% aber <90%)
        plan = {
            "files": [{"path": f"file{i}.py", "description": f"F{i}"} for i in range(10)]
        }
        created = [f"file{i}.py" for i in range(9)]  # 1 fehlt = 90%
        result = validate_file_by_file_output(created, plan)
        assert result.passed is True
        # Warnung weil <100%, aber kein Fehler weil >70%
        assert any("nicht erstellt" in w or "Erfolgsrate" in w for w in result.warnings)

    def test_many_missing_files_fails(self, valid_file_plan):
        """Viele fehlende Dateien erzeugen Fehler."""
        created = ["app.py"]  # 2 von 3 fehlen = 67%
        result = validate_file_by_file_output(created, valid_file_plan)
        assert result.passed is False
        assert any("Dateien fehlen" in i for i in result.issues)

    def test_unexpected_files_warning(self, valid_file_plan):
        """Unerwartete Dateien erzeugen Warnung."""
        created = ["app.py", "models.py", "routes.py", "extra.py"]  # extra.py nicht geplant
        result = validate_file_by_file_output(created, valid_file_plan)
        assert any("unerwartete Dateien" in w for w in result.warnings)

    def test_empty_plan_handles_gracefully(self):
        """Leerer Plan wird korrekt behandelt."""
        result = validate_file_by_file_output([], {"files": []})
        assert result.passed is True

    def test_low_success_rate_fails(self, valid_file_plan):
        """Niedrige Erfolgsrate erzeugt Fehler."""
        created = []  # Keine Dateien erstellt = 0%
        result = validate_file_by_file_output(created, valid_file_plan)
        assert result.passed is False
        assert any("Erfolgsrate" in i for i in result.issues)

    def test_medium_success_rate_warning(self):
        """Mittlere Erfolgsrate erzeugt Warnung."""
        plan = {
            "files": [
                {"path": "file1.py", "description": "F1"},
                {"path": "file2.py", "description": "F2"},
                {"path": "file3.py", "description": "F3"},
                {"path": "file4.py", "description": "F4"},
                {"path": "file5.py", "description": "F5"}
            ]
        }
        created = ["file1.py", "file2.py", "file3.py", "file4.py"]  # 4 von 5 = 80%
        result = validate_file_by_file_output(created, plan)
        assert result.passed is True
        assert any("Erfolgsrate" in w for w in result.warnings)

    def test_file_line_count_check(self, valid_file_plan):
        """Datei-Zeilenanzahl wird geprüft."""
        # Erstelle temporäre Dateien mit vielen Zeilen
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write("\n".join(["# Line " + str(i) for i in range(300)]))
            temp_path = f.name

        try:
            plan = {"files": [{"path": temp_path, "description": "Test"}]}
            result = validate_file_by_file_output([temp_path], plan, max_lines_per_file=200)
            assert any("Zeilen" in w for w in result.warnings)
        finally:
            os.unlink(temp_path)

    def test_details_contain_counts(self, valid_file_plan):
        """Details enthalten Zählungen."""
        created = ["app.py", "models.py"]
        result = validate_file_by_file_output(created, valid_file_plan)
        assert "planned_count" in result.details
        assert "created_count" in result.details
        assert "missing_count" in result.details
        assert result.details["planned_count"] == 3
        assert result.details["created_count"] == 2
        assert result.details["missing_count"] == 1


# =========================================================================
# Test: Edge Cases und Integration
# =========================================================================

class TestEdgeCases:
    """Tests für Edge Cases und Grenzfälle."""

    def test_unicode_in_anforderungen(self, valid_briefing):
        """Unicode-Zeichen werden korrekt behandelt."""
        output = {
            "anforderungen": [
                {
                    "id": "ANF-001",
                    "titel": "Übung mit Ümläuten",
                    "beschreibung": "Täst mit Sönderzeichen: äöü ß € 日本語",
                    "kategorie": "funktional",
                    "prioritaet": "höch"
                }
            ],
            "kategorien": ["funktional"]
        }
        result = validate_anforderungen(output, valid_briefing)
        assert result.passed is True

    def test_long_strings(self, valid_briefing):
        """Lange Strings werden korrekt behandelt."""
        output = {
            "anforderungen": [
                {
                    "id": "ANF-001",
                    "titel": "A" * 1000,
                    "beschreibung": "B" * 5000,
                    "kategorie": "funktional",
                    "prioritaet": "hoch"
                }
            ],
            "kategorien": ["funktional"]
        }
        result = validate_anforderungen(output, valid_briefing)
        assert result.passed is True

    def test_empty_briefing(self, valid_analyst_output):
        """Leeres Briefing wird korrekt behandelt."""
        result = validate_anforderungen(valid_analyst_output, {"answers": []})
        assert result.passed is True

    def test_score_clamping(self, valid_briefing):
        """Score wird auf 0.0-1.0 begrenzt."""
        # Erzeuge viele Warnungen
        output = {
            "anforderungen": [
                {"id": f"ANF-{i}", "titel": f"Test {i}"} for i in range(20)
            ],
            "kategorien": []
        }
        result = validate_anforderungen(output, valid_briefing)
        assert 0.0 <= result.score <= 1.0

    def test_all_validators_return_validation_result(
        self, valid_analyst_output, valid_konzepter_output, valid_file_plan,
        valid_briefing, valid_blueprint
    ):
        """Alle Validatoren geben ValidationResult zurück."""
        anforderungen = valid_analyst_output["anforderungen"]

        r1 = validate_anforderungen(valid_analyst_output, valid_briefing)
        r2 = validate_features(valid_konzepter_output, anforderungen)
        r3 = validate_file_by_file_plan(valid_file_plan, valid_blueprint)
        r4 = validate_file_by_file_output(["app.py"], valid_file_plan)

        for r in [r1, r2, r3, r4]:
            assert isinstance(r, ValidationResult)
            assert isinstance(r.passed, bool)
            assert isinstance(r.issues, list)
            assert isinstance(r.warnings, list)
            assert isinstance(r.score, float)
            assert isinstance(r.details, dict)
