# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 14.02.2026
Version: 1.0
Beschreibung: Tests fuer den TraceabilityService - Traceability-Matrix Sammlung,
              Luecken-Zusammenfassung, Markdown-Report-Generierung und Speicherung.
"""

import os

import pytest

from backend.traceability_service import TraceabilityService


# =========================================================================
# Hilfsfunktionen
# =========================================================================

def _erstelle_leere_data() -> dict:
    """Erstellt eine leere Datenstruktur analog zu DocumentationService.data."""
    return {
        "anforderungen": [],
        "features": [],
        "user_stories": [],
        "tasks": [],
        "file_by_file_plan": None,
        "file_generations": [],
        "traceability": None,
    }


def _erstelle_volle_data() -> dict:
    """Erstellt eine Datenstruktur mit Beispieldaten fuer Report-Tests."""
    return {
        "anforderungen": [
            {"id": "REQ-001", "titel": "Login-Funktion", "kategorie": "Funktional", "prioritaet": "hoch"},
            {"id": "REQ-002", "titel": "Dashboard", "kategorie": "UI/UX", "prioritaet": "mittel"},
        ],
        "features": [
            {"id": "FEAT-001", "titel": "Login-Formular", "anforderungen": ["REQ-001"]},
            {"id": "FEAT-002", "titel": "Dashboard-Ansicht", "anforderungen": ["REQ-002"]},
        ],
        "user_stories": [
            {
                "id": "US-001", "titel": "Login-Story", "feature_id": "FEAT-001",
                "gegeben": "ein Benutzer auf der Login-Seite",
                "wenn": "er Benutzername und Passwort eingibt",
                "dann": "wird er zum Dashboard weitergeleitet",
            },
        ],
        "tasks": [
            {"id": "TASK-001", "titel": "Login erstellen"},
            {"id": "TASK-002", "titel": "Dashboard erstellen"},
        ],
        "file_by_file_plan": {
            "total_files": 3,
            "files": [
                {"path": "login.py", "description": "Login-Formular-Implementierung mit Validierung"},
                {"path": "dashboard.py", "description": "Dashboard-Seite mit Widgets"},
                {"path": "utils.py", "description": "Hilfsfunktionen fuer Auth"},
            ],
        },
        "file_generations": [
            {"filepath": "login.py", "success": True},
            {"filepath": "dashboard.py", "success": True},
            {"filepath": "utils.py", "success": False, "error": "Timeout beim Generieren der Datei"},
        ],
        "traceability": {
            "coverage": 0.75,
            "gaps": {"anforderungen_ohne_features": 0},
            "timestamp": "2026-02-14T10:00:00",
        },
    }


# =========================================================================
# 1. TestSummarizeGaps
# =========================================================================

class TestSummarizeGaps:
    """Tests fuer _summarize_gaps - Luecken-Zaehlung in der Traceability-Matrix."""

    def test_leere_matrix_ergibt_null_luecken(self):
        """Leere Matrix hat keine Luecken (0 Elemente = 0 Luecken)."""
        service = TraceabilityService(None, _erstelle_leere_data())
        ergebnis = service._summarize_gaps({})

        assert ergebnis["anforderungen_ohne_features"] == 0
        assert ergebnis["features_ohne_user_stories"] == 0
        assert ergebnis["features_ohne_tasks"] == 0
        assert ergebnis["tasks_ohne_dateien"] == 0

    def test_matrix_mit_luecken_zaehlt_korrekt(self):
        """Matrix mit Luecken in jeder Kategorie zaehlt korrekt."""
        matrix = {
            "anforderungen": {
                "REQ-001": {"features": []},           # Luecke
                "REQ-002": {"features": ["FEAT-001"]},  # Keine Luecke
                "REQ-003": {},                           # Luecke (kein features-Key)
            },
            "features": {
                "FEAT-001": {"user_stories": [], "tasks": []},       # 2 Luecken
                "FEAT-002": {"user_stories": ["US-001"], "tasks": ["TASK-001"]},  # OK
            },
            "tasks": {
                "TASK-001": {"dateien": []},            # Luecke
                "TASK-002": {"dateien": ["login.py"]},  # OK
                "TASK-003": {},                          # Luecke (kein dateien-Key)
            },
        }
        service = TraceabilityService(None, _erstelle_leere_data())
        ergebnis = service._summarize_gaps(matrix)

        assert ergebnis["anforderungen_ohne_features"] == 2
        assert ergebnis["features_ohne_user_stories"] == 1
        assert ergebnis["features_ohne_tasks"] == 1
        assert ergebnis["tasks_ohne_dateien"] == 2

    def test_matrix_ohne_luecken_ergibt_null(self):
        """Vollstaendig verknuepfte Matrix hat keine Luecken."""
        matrix = {
            "anforderungen": {
                "REQ-001": {"features": ["FEAT-001"]},
            },
            "features": {
                "FEAT-001": {"user_stories": ["US-001"], "tasks": ["TASK-001"]},
            },
            "tasks": {
                "TASK-001": {"dateien": ["login.py"]},
            },
        }
        service = TraceabilityService(None, _erstelle_leere_data())
        ergebnis = service._summarize_gaps(matrix)

        assert ergebnis["anforderungen_ohne_features"] == 0
        assert ergebnis["features_ohne_user_stories"] == 0
        assert ergebnis["features_ohne_tasks"] == 0
        assert ergebnis["tasks_ohne_dateien"] == 0

    def test_alle_kategorien_im_ergebnis_vorhanden(self):
        """Ergebnis enthaelt immer alle vier Kategorien."""
        service = TraceabilityService(None, _erstelle_leere_data())
        ergebnis = service._summarize_gaps({})

        erwartete_keys = {
            "anforderungen_ohne_features",
            "features_ohne_user_stories",
            "features_ohne_tasks",
            "tasks_ohne_dateien",
        }
        assert set(ergebnis.keys()) == erwartete_keys


# =========================================================================
# 2. TestCollectTraceabilityMatrix
# =========================================================================

class TestCollectTraceabilityMatrix:
    """Tests fuer collect_traceability_matrix - Speicherung in data['traceability']."""

    def test_speichert_in_data_traceability(self):
        """Matrix-Daten werden in data['traceability'] gespeichert."""
        data = _erstelle_leere_data()
        service = TraceabilityService(None, data)

        matrix = {
            "summary": {"coverage": 0.85, "total": 10},
            "anforderungen": {},
            "features": {},
            "tasks": {},
        }
        service.collect_traceability_matrix(matrix)

        assert data["traceability"] is not None
        assert "summary" in data["traceability"]
        assert "coverage" in data["traceability"]
        assert "gaps" in data["traceability"]
        assert "timestamp" in data["traceability"]

    def test_coverage_wird_aus_summary_extrahiert(self):
        """Coverage-Wert wird korrekt aus matrix.summary.coverage extrahiert."""
        data = _erstelle_leere_data()
        service = TraceabilityService(None, data)

        matrix = {"summary": {"coverage": 0.92}, "anforderungen": {}, "features": {}, "tasks": {}}
        service.collect_traceability_matrix(matrix)

        assert data["traceability"]["coverage"] == 0.92

    def test_summary_wird_vollstaendig_uebernommen(self):
        """Gesamtes Summary-Dict wird uebernommen."""
        data = _erstelle_leere_data()
        service = TraceabilityService(None, data)

        summary_input = {"coverage": 0.5, "total_anforderungen": 3, "extra_feld": "test"}
        matrix = {"summary": summary_input, "anforderungen": {}, "features": {}, "tasks": {}}
        service.collect_traceability_matrix(matrix)

        assert data["traceability"]["summary"] == summary_input

    def test_gaps_werden_berechnet(self):
        """Gaps werden durch _summarize_gaps berechnet und gespeichert."""
        data = _erstelle_leere_data()
        service = TraceabilityService(None, data)

        matrix = {
            "summary": {},
            "anforderungen": {"REQ-001": {"features": []}},
            "features": {},
            "tasks": {},
        }
        service.collect_traceability_matrix(matrix)

        assert data["traceability"]["gaps"]["anforderungen_ohne_features"] == 1

    def test_timestamp_wird_gesetzt(self):
        """Timestamp wird als ISO-Format gesetzt."""
        data = _erstelle_leere_data()
        service = TraceabilityService(None, data)

        matrix = {"summary": {}, "anforderungen": {}, "features": {}, "tasks": {}}
        service.collect_traceability_matrix(matrix)

        timestamp = data["traceability"]["timestamp"]
        assert isinstance(timestamp, str)
        # ISO-Format enthaelt 'T' als Trenner
        assert "T" in timestamp

    def test_leere_summary_ergibt_coverage_null(self):
        """Leeres Summary ohne coverage-Key ergibt Coverage 0.0."""
        data = _erstelle_leere_data()
        service = TraceabilityService(None, data)

        matrix = {"summary": {}, "anforderungen": {}, "features": {}, "tasks": {}}
        service.collect_traceability_matrix(matrix)

        assert data["traceability"]["coverage"] == 0.0


# =========================================================================
# 3. TestGenerateTraceabilityReport
# =========================================================================

class TestGenerateTraceabilityReport:
    """Tests fuer generate_traceability_report - Markdown-Report-Generierung."""

    def test_leerer_data_erzeugt_grundstruktur(self):
        """Report mit leeren Daten enthaelt Ueberschrift und Zusammenfassung."""
        data = _erstelle_leere_data()
        service = TraceabilityService(None, data)
        report = service.generate_traceability_report()

        assert "# Traceability Report" in report
        assert "## Zusammenfassung" in report
        assert "Generiert am:" in report

    def test_zusammenfassung_zeigt_nullwerte(self):
        """Zusammenfassung zeigt 0 fuer leere Listen."""
        data = _erstelle_leere_data()
        service = TraceabilityService(None, data)
        report = service.generate_traceability_report()

        assert "**Anforderungen:** 0" in report
        assert "**Features:** 0" in report
        assert "**User Stories:** 0" in report
        assert "**Tasks:** 0" in report
        assert "**Generierte Dateien:** 0" in report

    def test_anforderungen_sektion_wird_angezeigt(self):
        """Anforderungen-Sektion erscheint mit korrekten Daten."""
        data = _erstelle_leere_data()
        data["anforderungen"] = [
            {"id": "REQ-001", "titel": "Login-Funktion", "kategorie": "Funktional", "prioritaet": "hoch"},
        ]
        service = TraceabilityService(None, data)
        report = service.generate_traceability_report()

        assert "## Anforderungen" in report
        assert "[REQ-001]" in report
        assert "Login-Funktion" in report
        assert "Funktional" in report
        assert "hoch" in report

    def test_anforderungen_default_werte(self):
        """Anforderungen ohne optionale Felder bekommen Standardwerte."""
        data = _erstelle_leere_data()
        data["anforderungen"] = [{"id": "REQ-001"}]
        service = TraceabilityService(None, data)
        report = service.generate_traceability_report()

        assert "REQ-001" in report
        assert "Unbenannt" in report
        assert "Unbekannt" in report
        assert "mittel" in report

    def test_anforderungen_max_10_anzeige(self):
        """Mehr als 10 Anforderungen werden abgeschnitten mit Hinweis."""
        data = _erstelle_leere_data()
        data["anforderungen"] = [
            {"id": f"REQ-{i:03d}", "titel": f"Anforderung {i}"}
            for i in range(15)
        ]
        service = TraceabilityService(None, data)
        report = service.generate_traceability_report()

        assert "... und 5 weitere" in report
        # Die ersten 10 sind im Report
        assert "REQ-009" in report
        # Die 11. ist NICHT im Report (nur der Hinweis)
        assert "[REQ-010]" not in report

    def test_features_sektion_wird_angezeigt(self):
        """Features-Sektion erscheint mit korrekten Daten und Refs."""
        data = _erstelle_leere_data()
        data["features"] = [
            {"id": "FEAT-001", "titel": "Login-Formular", "anforderungen": ["REQ-001", "REQ-002"]},
        ]
        service = TraceabilityService(None, data)
        report = service.generate_traceability_report()

        assert "## Features" in report
        assert "[FEAT-001]" in report
        assert "Login-Formular" in report
        assert "REQ-001, REQ-002" in report

    def test_features_max_10_anzeige(self):
        """Mehr als 10 Features werden abgeschnitten mit Hinweis."""
        data = _erstelle_leere_data()
        data["features"] = [
            {"id": f"FEAT-{i:03d}", "titel": f"Feature {i}", "anforderungen": []}
            for i in range(12)
        ]
        service = TraceabilityService(None, data)
        report = service.generate_traceability_report()

        assert "... und 2 weitere" in report

    def test_user_stories_sektion_wird_angezeigt(self):
        """User Stories Sektion mit GEGEBEN/WENN/DANN wird angezeigt."""
        data = _erstelle_leere_data()
        data["user_stories"] = [
            {
                "id": "US-001", "titel": "Login-Story", "feature_id": "FEAT-001",
                "gegeben": "ein Benutzer", "wenn": "er sich einloggt", "dann": "sieht er das Dashboard",
            },
        ]
        service = TraceabilityService(None, data)
        report = service.generate_traceability_report()

        assert "## User Stories" in report
        assert "[US-001]" in report
        assert "Login-Story" in report
        assert "Feature: FEAT-001" in report
        assert "GEGEBEN: ein Benutzer" in report
        assert "WENN: er sich einloggt" in report
        assert "DANN: sieht er das Dashboard" in report

    def test_user_stories_max_15_anzeige(self):
        """Mehr als 15 User Stories werden abgeschnitten mit Hinweis."""
        data = _erstelle_leere_data()
        data["user_stories"] = [
            {
                "id": f"US-{i:03d}", "titel": f"Story {i}", "feature_id": "FEAT-001",
                "gegeben": "A", "wenn": "B", "dann": "C",
            }
            for i in range(20)
        ]
        service = TraceabilityService(None, data)
        report = service.generate_traceability_report()

        assert "... und 5 weitere" in report
        # Die 15. (Index 14, US-014) ist noch drin
        assert "US-014" in report
        # Die 16. (Index 15, US-015) ist NICHT als einzelner Eintrag drin
        assert "[US-015]" not in report

    def test_user_stories_default_werte(self):
        """User Stories ohne optionale Felder bekommen '?' als Standard."""
        data = _erstelle_leere_data()
        data["user_stories"] = [{"id": "US-001"}]
        service = TraceabilityService(None, data)
        report = service.generate_traceability_report()

        assert "US-???" not in report  # id ist vorhanden
        assert "Unbenannt" in report
        assert "GEGEBEN: ?" in report
        assert "WENN: ?" in report
        assert "DANN: ?" in report

    def test_leere_user_stories_keine_sektion(self):
        """Ohne User Stories erscheint keine User Stories Sektion."""
        data = _erstelle_leere_data()
        service = TraceabilityService(None, data)
        report = service.generate_traceability_report()

        assert "## User Stories" not in report

    def test_file_by_file_plan_sektion(self):
        """File-by-File Plan wird mit Dateien und Beschreibungen angezeigt."""
        data = _erstelle_leere_data()
        data["file_by_file_plan"] = {
            "total_files": 2,
            "files": [
                {"path": "login.py", "description": "Login-Formular-Implementierung"},
                {"path": "dashboard.py", "description": "Dashboard-Seite"},
            ],
        }
        service = TraceabilityService(None, data)
        report = service.generate_traceability_report()

        assert "## File-by-File Plan" in report
        assert "**Geplante Dateien:** 2" in report
        assert "`login.py`" in report
        assert "`dashboard.py`" in report

    def test_file_by_file_plan_max_5_dateien(self):
        """Nur die ersten 5 Dateien des Plans werden angezeigt."""
        data = _erstelle_leere_data()
        data["file_by_file_plan"] = {
            "total_files": 7,
            "files": [
                {"path": f"file_{i}.py", "description": f"Datei {i}"} for i in range(7)
            ],
        }
        service = TraceabilityService(None, data)
        report = service.generate_traceability_report()

        assert "`file_4.py`" in report
        assert "`file_5.py`" not in report

    def test_file_by_file_plan_none_keine_sektion(self):
        """Ohne Plan (None) erscheint keine Plan-Sektion."""
        data = _erstelle_leere_data()
        data["file_by_file_plan"] = None
        service = TraceabilityService(None, data)
        report = service.generate_traceability_report()

        assert "## File-by-File Plan" not in report

    def test_file_generations_sektion_success(self):
        """Erfolgreiche Datei-Generierungen werden gezaehlt."""
        data = _erstelle_leere_data()
        data["file_generations"] = [
            {"filepath": "login.py", "success": True},
            {"filepath": "dashboard.py", "success": True},
        ]
        service = TraceabilityService(None, data)
        report = service.generate_traceability_report()

        assert "## Datei-Generierung" in report
        assert "**Erfolgreich:** 2/2" in report

    def test_file_generations_sektion_mixed(self):
        """Gemischte Erfolge und Fehler werden korrekt angezeigt."""
        data = _erstelle_leere_data()
        data["file_generations"] = [
            {"filepath": "login.py", "success": True},
            {"filepath": "broken.py", "success": False, "error": "Timeout beim Generieren"},
        ]
        service = TraceabilityService(None, data)
        report = service.generate_traceability_report()

        assert "**Erfolgreich:** 1/2" in report
        assert "**Fehlgeschlagen:**" in report
        assert "`broken.py`" in report
        assert "Timeout beim Generieren" in report

    def test_file_generations_fehlgeschlagen_max_5(self):
        """Nur die ersten 5 fehlgeschlagenen Dateien werden angezeigt."""
        data = _erstelle_leere_data()
        data["file_generations"] = [
            {"filepath": f"fail_{i}.py", "success": False, "error": f"Fehler {i}"} for i in range(8)
        ]
        service = TraceabilityService(None, data)
        report = service.generate_traceability_report()

        assert "`fail_4.py`" in report
        assert "`fail_5.py`" not in report

    def test_file_generations_leer_keine_sektion(self):
        """Ohne Generierungen erscheint keine Generierungs-Sektion."""
        data = _erstelle_leere_data()
        data["file_generations"] = []
        service = TraceabilityService(None, data)
        report = service.generate_traceability_report()

        assert "## Datei-Generierung" not in report

    def test_coverage_anzeige_mit_traceability(self):
        """Coverage wird als Prozentsatz angezeigt wenn Traceability vorhanden."""
        data = _erstelle_leere_data()
        data["traceability"] = {"coverage": 0.85}
        service = TraceabilityService(None, data)
        report = service.generate_traceability_report()

        assert "**Coverage:** 85.0%" in report

    def test_coverage_null_anzeige(self):
        """Coverage 0.0 wird korrekt als 0.0% angezeigt."""
        data = _erstelle_leere_data()
        data["traceability"] = {"coverage": 0.0}
        service = TraceabilityService(None, data)
        report = service.generate_traceability_report()

        assert "**Coverage:** 0.0%" in report

    def test_keine_coverage_ohne_traceability(self):
        """Ohne Traceability-Daten erscheint keine Coverage-Zeile."""
        data = _erstelle_leere_data()
        data["traceability"] = None
        service = TraceabilityService(None, data)
        report = service.generate_traceability_report()

        assert "**Coverage:**" not in report

    def test_vollstaendiger_report_alle_sektionen(self):
        """Vollstaendiger Report enthaelt alle Sektionen."""
        data = _erstelle_volle_data()
        service = TraceabilityService(None, data)
        report = service.generate_traceability_report()

        assert "# Traceability Report" in report
        assert "## Zusammenfassung" in report
        assert "## Anforderungen" in report
        assert "## Features" in report
        assert "## User Stories" in report
        assert "## File-by-File Plan" in report
        assert "## Datei-Generierung" in report
        assert "**Coverage:**" in report

    def test_report_ist_string(self):
        """Report wird als String zurueckgegeben."""
        data = _erstelle_leere_data()
        service = TraceabilityService(None, data)
        report = service.generate_traceability_report()

        assert isinstance(report, str)

    def test_beschreibung_wird_auf_50_zeichen_gekuerzt(self):
        """Datei-Beschreibung im Plan wird auf 50 Zeichen gekuerzt."""
        data = _erstelle_leere_data()
        data["file_by_file_plan"] = {
            "total_files": 1,
            "files": [
                {"path": "test.py", "description": "A" * 100},
            ],
        }
        service = TraceabilityService(None, data)
        report = service.generate_traceability_report()

        # Beschreibung wird auf 50 Zeichen gekuerzt
        assert "A" * 50 in report
        assert "A" * 51 not in report

    def test_error_wird_auf_50_zeichen_gekuerzt(self):
        """Fehlermeldung bei fehlgeschlagener Generierung wird auf 50 Zeichen gekuerzt."""
        data = _erstelle_leere_data()
        data["file_generations"] = [
            {"filepath": "fail.py", "success": False, "error": "X" * 100},
        ]
        service = TraceabilityService(None, data)
        report = service.generate_traceability_report()

        assert "X" * 50 in report
        assert "X" * 51 not in report


# =========================================================================
# 4. TestSaveTraceabilityReport
# =========================================================================

class TestSaveTraceabilityReport:
    """Tests fuer save_traceability_report - Speicherung auf Festplatte."""

    def test_erfolgreiche_speicherung(self, tmp_path):
        """Report wird korrekt in docs/TRACEABILITY.md gespeichert."""
        data = _erstelle_leere_data()
        service = TraceabilityService(str(tmp_path), data)
        ergebnis = service.save_traceability_report()

        assert ergebnis is not None
        erwarteter_pfad = os.path.join(str(tmp_path), "docs", "TRACEABILITY.md")
        assert ergebnis == erwarteter_pfad
        assert os.path.exists(erwarteter_pfad)

    def test_gespeicherter_inhalt_ist_report(self, tmp_path):
        """Gespeicherter Dateiinhalt entspricht dem generierten Report."""
        data = _erstelle_volle_data()
        service = TraceabilityService(str(tmp_path), data)
        pfad = service.save_traceability_report()

        with open(pfad, "r", encoding="utf-8") as f:
            inhalt = f.read()

        assert "# Traceability Report" in inhalt
        assert "## Zusammenfassung" in inhalt

    def test_erstellt_docs_verzeichnis(self, tmp_path):
        """docs-Verzeichnis wird automatisch erstellt wenn es nicht existiert."""
        data = _erstelle_leere_data()
        service = TraceabilityService(str(tmp_path), data)

        docs_dir = os.path.join(str(tmp_path), "docs")
        assert not os.path.exists(docs_dir)

        service.save_traceability_report()

        assert os.path.exists(docs_dir)

    def test_kein_project_path_ergibt_none(self):
        """Ohne project_path wird None zurueckgegeben."""
        data = _erstelle_leere_data()
        service = TraceabilityService(None, data)
        ergebnis = service.save_traceability_report()

        assert ergebnis is None

    def test_leerer_project_path_ergibt_none(self):
        """Leerer String als project_path wird als falsy behandelt und ergibt None."""
        data = _erstelle_leere_data()
        service = TraceabilityService("", data)
        ergebnis = service.save_traceability_report()

        assert ergebnis is None

    def test_exception_ergibt_none(self, tmp_path, monkeypatch):
        """Bei Schreibfehler wird None zurueckgegeben statt Exception."""
        data = _erstelle_leere_data()
        service = TraceabilityService(str(tmp_path), data)

        # os.makedirs zum Fehlschlagen bringen
        def _raise_os_error(*args, **kwargs):
            raise OSError("Simulierter Schreibfehler")

        monkeypatch.setattr("os.makedirs", _raise_os_error)
        ergebnis = service.save_traceability_report()

        assert ergebnis is None

    def test_existierendes_docs_verzeichnis_kein_fehler(self, tmp_path):
        """Bereits existierendes docs-Verzeichnis erzeugt keinen Fehler."""
        data = _erstelle_leere_data()
        docs_dir = os.path.join(str(tmp_path), "docs")
        os.makedirs(docs_dir)

        service = TraceabilityService(str(tmp_path), data)
        ergebnis = service.save_traceability_report()

        assert ergebnis is not None
        assert os.path.exists(ergebnis)

    def test_datei_ist_utf8_kodiert(self, tmp_path):
        """Gespeicherte Datei verwendet UTF-8 Kodierung."""
        data = _erstelle_leere_data()
        data["anforderungen"] = [
            {"id": "REQ-001", "titel": "Umlaute: äöüß", "kategorie": "Funktional", "prioritaet": "hoch"},
        ]
        service = TraceabilityService(str(tmp_path), data)
        pfad = service.save_traceability_report()

        with open(pfad, "r", encoding="utf-8") as f:
            inhalt = f.read()

        assert "Umlaute: äöüß" in inhalt


# =========================================================================
# 5. TestInit
# =========================================================================

class TestInit:
    """Tests fuer __init__ - Konstruktor-Verhalten."""

    def test_project_path_wird_gespeichert(self, tmp_path):
        """project_path wird korrekt als Attribut gespeichert."""
        data = _erstelle_leere_data()
        service = TraceabilityService(str(tmp_path), data)

        assert service.project_path == str(tmp_path)

    def test_data_referenz_wird_gespeichert(self):
        """data-Dict wird als Referenz (nicht Kopie) gespeichert."""
        data = _erstelle_leere_data()
        service = TraceabilityService(None, data)

        # Aenderung am Original muss sich im Service widerspiegeln
        data["anforderungen"].append({"id": "REQ-001"})
        assert len(service.data["anforderungen"]) == 1

    def test_none_project_path_akzeptiert(self):
        """None als project_path wird ohne Fehler akzeptiert."""
        data = _erstelle_leere_data()
        service = TraceabilityService(None, data)

        assert service.project_path is None
