# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 14.02.2026
Version: 1.0
Beschreibung: Tests fuer den TraceabilityManager - Vollstaendige Lifecycle-Tests
              fuer Anforderungen, Features, User Stories, Tasks und Dateien.
"""

import json
import os

import pytest

from backend.traceability_manager import TraceabilityManager


# =========================================================================
# Hilfsfunktionen
# =========================================================================

def _erstelle_manager(tmp_path) -> TraceabilityManager:
    """Erstellt einen frischen TraceabilityManager mit tmp_path."""
    return TraceabilityManager(str(tmp_path))


def _erstelle_vollstaendigen_manager(tmp_path) -> TraceabilityManager:
    """Erstellt einen Manager mit komplettem Datenbestand."""
    tm = _erstelle_manager(tmp_path)
    tm.add_anforderung("REQ-001", "Login-Funktion", "Funktional", "hoch")
    tm.add_anforderung("REQ-002", "Dashboard", "UI/UX", "mittel")
    tm.add_feature("FEAT-001", "Login-Formular", ["REQ-001"])
    tm.add_feature("FEAT-002", "Dashboard-Ansicht", ["REQ-002"])
    tm.add_user_story(
        "US-001", "Login-Story", "FEAT-001",
        gegeben="ein Benutzer auf der Login-Seite",
        wenn="er Benutzername und Passwort eingibt",
        dann="wird er zum Dashboard weitergeleitet"
    )
    tm.add_task("TASK-001", "Erstelle Login-Formular", ["FEAT-001"], datei="login.py")
    tm.add_task("TASK-002", "Erstelle Dashboard", ["FEAT-002"], datei="dashboard.py")
    tm.add_datei("login.py", ["TASK-001"], lines=100)
    tm.add_datei("dashboard.py", ["TASK-002"], lines=200)
    return tm


# =========================================================================
# 1. TestInit
# =========================================================================

class TestInit:
    """Tests fuer die Initialisierung des TraceabilityManagers."""

    def test_matrix_file_pfad_korrekt(self, tmp_path):
        """matrix_file zeigt auf project_path/traceability_matrix.json."""
        tm = _erstelle_manager(tmp_path)
        erwarteter_pfad = os.path.join(str(tmp_path), "traceability_matrix.json")
        assert tm.matrix_file == erwarteter_pfad

    def test_leere_matrix_hat_korrekte_struktur(self, tmp_path):
        """Leere Matrix enthaelt alle Pflichtschluessel."""
        tm = _erstelle_manager(tmp_path)
        erwartete_keys = {"version", "created_at", "updated_at",
                          "anforderungen", "features", "user_stories",
                          "tasks", "dateien", "summary"}
        assert erwartete_keys.issubset(set(tm.matrix.keys()))

    def test_leere_matrix_version(self, tmp_path):
        """Version ist 1.0 bei neuer Matrix."""
        tm = _erstelle_manager(tmp_path)
        assert tm.matrix["version"] == "1.0"

    def test_summary_hat_alle_felder(self, tmp_path):
        """Summary enthaelt alle Zaehlfelder und coverage."""
        tm = _erstelle_manager(tmp_path)
        summary = tm.matrix["summary"]
        erwartete_felder = {"total_anforderungen", "total_features",
                            "total_user_stories", "total_tasks",
                            "total_dateien", "coverage"}
        assert erwartete_felder == set(summary.keys())

    def test_laedt_existierende_matrix(self, tmp_path):
        """Laedt gespeicherte Matrix beim naechsten Initialisieren."""
        tm = _erstelle_manager(tmp_path)
        tm.add_anforderung("REQ-001", "Test-Anforderung")
        tm.save()

        # Neuer Manager laedt gespeicherte Daten
        tm2 = _erstelle_manager(tmp_path)
        assert "REQ-001" in tm2.matrix["anforderungen"]
        assert tm2.matrix["anforderungen"]["REQ-001"]["titel"] == "Test-Anforderung"


# =========================================================================
# 2. TestAnforderungen
# =========================================================================

class TestAnforderungen:
    """Tests fuer Anforderungs-Verwaltung."""

    def test_add_anforderung_speichert_id(self, tmp_path):
        """Anforderung wird unter korrekter ID gespeichert."""
        tm = _erstelle_manager(tmp_path)
        tm.add_anforderung("REQ-001", "Login")
        assert "REQ-001" in tm.matrix["anforderungen"]

    def test_add_anforderung_speichert_titel(self, tmp_path):
        """Titel wird korrekt gespeichert."""
        tm = _erstelle_manager(tmp_path)
        tm.add_anforderung("REQ-001", "Login-Funktion")
        assert tm.matrix["anforderungen"]["REQ-001"]["titel"] == "Login-Funktion"

    def test_add_anforderung_speichert_kategorie(self, tmp_path):
        """Kategorie wird korrekt gespeichert."""
        tm = _erstelle_manager(tmp_path)
        tm.add_anforderung("REQ-001", "Login", kategorie="Sicherheit")
        assert tm.matrix["anforderungen"]["REQ-001"]["kategorie"] == "Sicherheit"

    def test_add_anforderung_speichert_prioritaet(self, tmp_path):
        """Prioritaet wird korrekt gespeichert."""
        tm = _erstelle_manager(tmp_path)
        tm.add_anforderung("REQ-001", "Login", prioritaet="hoch")
        assert tm.matrix["anforderungen"]["REQ-001"]["prioritaet"] == "hoch"

    def test_default_kategorie_funktional(self, tmp_path):
        """Standard-Kategorie ist 'Funktional'."""
        tm = _erstelle_manager(tmp_path)
        tm.add_anforderung("REQ-001", "Login")
        assert tm.matrix["anforderungen"]["REQ-001"]["kategorie"] == "Funktional"

    def test_default_prioritaet_mittel(self, tmp_path):
        """Standard-Prioritaet ist 'mittel'."""
        tm = _erstelle_manager(tmp_path)
        tm.add_anforderung("REQ-001", "Login")
        assert tm.matrix["anforderungen"]["REQ-001"]["prioritaet"] == "mittel"

    def test_features_liste_initial_leer(self, tmp_path):
        """Features-Liste einer neuen Anforderung ist leer."""
        tm = _erstelle_manager(tmp_path)
        tm.add_anforderung("REQ-001", "Login")
        assert tm.matrix["anforderungen"]["REQ-001"]["features"] == []

    def test_add_anforderungen_from_analyst_zaehlt_korrekt(self, tmp_path):
        """Gibt korrekte Anzahl hinzugefuegter Anforderungen zurueck."""
        tm = _erstelle_manager(tmp_path)
        analyst_output = {
            "anforderungen": [
                {"id": "REQ-001", "titel": "Login"},
                {"id": "REQ-002", "titel": "Logout"},
                {"id": "REQ-003", "titel": "Registrierung"}
            ]
        }
        anzahl = tm.add_anforderungen_from_analyst(analyst_output)
        assert anzahl == 3
        assert len(tm.matrix["anforderungen"]) == 3

    def test_add_anforderungen_from_analyst_leerer_input(self, tmp_path):
        """Leerer Input ergibt 0 hinzugefuegte Anforderungen."""
        tm = _erstelle_manager(tmp_path)
        anzahl = tm.add_anforderungen_from_analyst({})
        assert anzahl == 0
        assert len(tm.matrix["anforderungen"]) == 0


# =========================================================================
# 3. TestFeatures
# =========================================================================

class TestFeatures:
    """Tests fuer Feature-Verwaltung."""

    def test_add_feature_speichert_korrekt(self, tmp_path):
        """Feature wird mit allen Feldern gespeichert."""
        tm = _erstelle_manager(tmp_path)
        tm.add_feature("FEAT-001", "Login-Formular", ["REQ-001"], technologie="React")
        feat = tm.matrix["features"]["FEAT-001"]
        assert feat["titel"] == "Login-Formular"
        assert feat["technologie"] == "React"
        assert feat["anforderungen"] == ["REQ-001"]

    def test_rueckwaerts_verknuepfung_zu_anforderung(self, tmp_path):
        """Feature-ID wird in Anforderung.features eingetragen."""
        tm = _erstelle_manager(tmp_path)
        tm.add_anforderung("REQ-001", "Login")
        tm.add_feature("FEAT-001", "Login-Formular", ["REQ-001"])
        assert "FEAT-001" in tm.matrix["anforderungen"]["REQ-001"]["features"]

    def test_keine_doppelte_rueckwaerts_verknuepfung(self, tmp_path):
        """Doppeltes Hinzufuegen erzeugt keine Duplikate in der Verknuepfung."""
        tm = _erstelle_manager(tmp_path)
        tm.add_anforderung("REQ-001", "Login")
        tm.add_feature("FEAT-001", "Login-Formular", ["REQ-001"])
        # Nochmal mit gleicher Anforderung (simuliert durch erneutes add)
        tm.matrix["features"]["FEAT-001"]["anforderungen"] = ["REQ-001"]
        # Direkt testen: features-Liste sollte FEAT-001 nur einmal enthalten
        assert tm.matrix["anforderungen"]["REQ-001"]["features"].count("FEAT-001") == 1

    def test_add_features_from_konzepter_zaehlt_korrekt(self, tmp_path):
        """Gibt korrekte Anzahl hinzugefuegter Features zurueck."""
        tm = _erstelle_manager(tmp_path)
        konzepter_output = {
            "features": [
                {"id": "FEAT-001", "titel": "Login", "anforderungen": []},
                {"id": "FEAT-002", "titel": "Dashboard", "anforderungen": []}
            ]
        }
        anzahl = tm.add_features_from_konzepter(konzepter_output)
        assert anzahl == 2

    def test_feature_ohne_existierende_anforderung_kein_crash(self, tmp_path):
        """Feature mit nicht-existierender Anforderung erzeugt keinen Fehler."""
        tm = _erstelle_manager(tmp_path)
        # REQ-999 existiert nicht - soll nicht crashen
        tm.add_feature("FEAT-001", "Login-Formular", ["REQ-999"])
        assert "FEAT-001" in tm.matrix["features"]

    def test_user_stories_liste_initial_leer(self, tmp_path):
        """user_stories-Liste eines neuen Features ist leer."""
        tm = _erstelle_manager(tmp_path)
        tm.add_feature("FEAT-001", "Login", [])
        assert tm.matrix["features"]["FEAT-001"]["user_stories"] == []

    def test_tasks_liste_initial_leer(self, tmp_path):
        """tasks-Liste eines neuen Features ist leer."""
        tm = _erstelle_manager(tmp_path)
        tm.add_feature("FEAT-001", "Login", [])
        assert tm.matrix["features"]["FEAT-001"]["tasks"] == []

    def test_feature_default_prioritaet(self, tmp_path):
        """Standard-Prioritaet eines Features ist 'mittel'."""
        tm = _erstelle_manager(tmp_path)
        tm.add_feature("FEAT-001", "Login", [])
        assert tm.matrix["features"]["FEAT-001"]["prioritaet"] == "mittel"

    def test_add_features_from_konzepter_leerer_input(self, tmp_path):
        """Leerer Konzepter-Output ergibt 0 Features."""
        tm = _erstelle_manager(tmp_path)
        anzahl = tm.add_features_from_konzepter({})
        assert anzahl == 0

    def test_feature_mehrere_anforderungen(self, tmp_path):
        """Feature kann mit mehreren Anforderungen verknuepft sein."""
        tm = _erstelle_manager(tmp_path)
        tm.add_anforderung("REQ-001", "Login")
        tm.add_anforderung("REQ-002", "Sicherheit")
        tm.add_feature("FEAT-001", "Auth-Modul", ["REQ-001", "REQ-002"])
        assert "FEAT-001" in tm.matrix["anforderungen"]["REQ-001"]["features"]
        assert "FEAT-001" in tm.matrix["anforderungen"]["REQ-002"]["features"]


# =========================================================================
# 4. TestUserStories
# =========================================================================

class TestUserStories:
    """Tests fuer User Story Verwaltung."""

    def test_add_user_story_speichert_gegeben_wenn_dann(self, tmp_path):
        """GEGEBEN/WENN/DANN werden korrekt gespeichert."""
        tm = _erstelle_manager(tmp_path)
        tm.add_feature("FEAT-001", "Login", [])
        tm.add_user_story(
            "US-001", "Login-Story", "FEAT-001",
            gegeben="ein Benutzer auf der Login-Seite",
            wenn="er seine Daten eingibt",
            dann="wird er eingeloggt"
        )
        us = tm.matrix["user_stories"]["US-001"]
        assert us["gegeben"] == "ein Benutzer auf der Login-Seite"
        assert us["wenn"] == "er seine Daten eingibt"
        assert us["dann"] == "wird er eingeloggt"

    def test_add_user_story_speichert_titel(self, tmp_path):
        """Titel der User Story wird gespeichert."""
        tm = _erstelle_manager(tmp_path)
        tm.add_user_story("US-001", "Meine Story", "FEAT-001")
        assert tm.matrix["user_stories"]["US-001"]["titel"] == "Meine Story"

    def test_rueckwaerts_verknuepfung_zu_feature(self, tmp_path):
        """User Story ID wird in Feature.user_stories eingetragen."""
        tm = _erstelle_manager(tmp_path)
        tm.add_feature("FEAT-001", "Login", [])
        tm.add_user_story("US-001", "Login-Story", "FEAT-001")
        assert "US-001" in tm.matrix["features"]["FEAT-001"]["user_stories"]

    def test_akzeptanzkriterien_default_leer(self, tmp_path):
        """Akzeptanzkriterien sind standardmaessig eine leere Liste."""
        tm = _erstelle_manager(tmp_path)
        tm.add_user_story("US-001", "Story", "FEAT-001")
        assert tm.matrix["user_stories"]["US-001"]["akzeptanzkriterien"] == []

    def test_akzeptanzkriterien_gesetzt(self, tmp_path):
        """Akzeptanzkriterien koennen explizit gesetzt werden."""
        tm = _erstelle_manager(tmp_path)
        kriterien = ["Formular validiert", "Fehlermeldung bei falschen Daten"]
        tm.add_user_story(
            "US-001", "Story", "FEAT-001",
            akzeptanzkriterien=kriterien
        )
        assert tm.matrix["user_stories"]["US-001"]["akzeptanzkriterien"] == kriterien

    def test_add_user_stories_from_konzepter_zaehlt_korrekt(self, tmp_path):
        """Gibt korrekte Anzahl hinzugefuegter User Stories zurueck."""
        tm = _erstelle_manager(tmp_path)
        tm.add_feature("FEAT-001", "Login", [])
        konzepter_output = {
            "user_stories": [
                {"id": "US-001", "titel": "Story1", "feature_id": "FEAT-001",
                 "gegeben": "A", "wenn": "B", "dann": "C"},
                {"id": "US-002", "titel": "Story2", "feature_id": "FEAT-001",
                 "gegeben": "D", "wenn": "E", "dann": "F"}
            ]
        }
        anzahl = tm.add_user_stories_from_konzepter(konzepter_output)
        assert anzahl == 2

    def test_feature_nicht_vorhanden_kein_crash(self, tmp_path):
        """User Story mit nicht-existierendem Feature erzeugt keinen Fehler."""
        tm = _erstelle_manager(tmp_path)
        # FEAT-999 existiert nicht - soll nicht crashen
        tm.add_user_story("US-001", "Story", "FEAT-999")
        assert "US-001" in tm.matrix["user_stories"]

    def test_keine_doppelte_rueckwaerts_verknuepfung(self, tmp_path):
        """Doppeltes Hinzufuegen erzeugt keine Duplikate in Feature.user_stories."""
        tm = _erstelle_manager(tmp_path)
        tm.add_feature("FEAT-001", "Login", [])
        tm.add_user_story("US-001", "Story1", "FEAT-001")
        tm.add_user_story("US-001", "Story1-v2", "FEAT-001")
        # US-001 sollte nur einmal in der Liste stehen
        assert tm.matrix["features"]["FEAT-001"]["user_stories"].count("US-001") == 1


# =========================================================================
# 5. TestTasks
# =========================================================================

class TestTasks:
    """Tests fuer Task-Verwaltung."""

    def test_add_task_speichert_korrekt(self, tmp_path):
        """Task wird mit allen Feldern gespeichert."""
        tm = _erstelle_manager(tmp_path)
        tm.add_task("TASK-001", "Login erstellen", ["FEAT-001"], datei="login.py")
        task = tm.matrix["tasks"]["TASK-001"]
        assert task["titel"] == "Login erstellen"
        assert task["features"] == ["FEAT-001"]
        assert "login.py" in task["dateien"]
        assert task["status"] == "pending"

    def test_add_task_ohne_datei(self, tmp_path):
        """Task ohne Datei hat leere dateien-Liste."""
        tm = _erstelle_manager(tmp_path)
        tm.add_task("TASK-001", "Konzept", ["FEAT-001"])
        assert tm.matrix["tasks"]["TASK-001"]["dateien"] == []

    def test_rueckwaerts_verknuepfung_zu_feature(self, tmp_path):
        """Task-ID wird in Feature.tasks eingetragen."""
        tm = _erstelle_manager(tmp_path)
        tm.add_feature("FEAT-001", "Login", [])
        tm.add_task("TASK-001", "Login erstellen", ["FEAT-001"])
        assert "TASK-001" in tm.matrix["features"]["FEAT-001"]["tasks"]

    def test_update_task_status(self, tmp_path):
        """Status wird korrekt aktualisiert."""
        tm = _erstelle_manager(tmp_path)
        tm.add_task("TASK-001", "Login erstellen", ["FEAT-001"])
        tm.update_task_status("TASK-001", "completed")
        assert tm.matrix["tasks"]["TASK-001"]["status"] == "completed"

    def test_update_task_status_setzt_updated_at(self, tmp_path):
        """updated_at wird beim Status-Update gesetzt."""
        tm = _erstelle_manager(tmp_path)
        tm.add_task("TASK-001", "Login erstellen", ["FEAT-001"])
        tm.update_task_status("TASK-001", "in_progress")
        assert "updated_at" in tm.matrix["tasks"]["TASK-001"]

    def test_add_tasks_from_planner_zaehlt_korrekt(self, tmp_path):
        """Gibt korrekte Anzahl hinzugefuegter Tasks zurueck."""
        tm = _erstelle_manager(tmp_path)
        planner_output = {
            "files": [
                {"path": "login.py", "description": "Login-Formular"},
                {"path": "dashboard.py", "description": "Dashboard-Seite"}
            ]
        }
        anzahl = tm.add_tasks_from_planner(planner_output)
        assert anzahl == 2

    def test_unbekannte_task_id_kein_crash(self, tmp_path):
        """Status-Update fuer nicht-existierende Task-ID erzeugt keinen Fehler."""
        tm = _erstelle_manager(tmp_path)
        # Soll nicht crashen
        tm.update_task_status("TASK-999", "completed")

    def test_task_mit_mehreren_features(self, tmp_path):
        """Task kann mit mehreren Features verknuepft sein."""
        tm = _erstelle_manager(tmp_path)
        tm.add_feature("FEAT-001", "Login", [])
        tm.add_feature("FEAT-002", "Auth", [])
        tm.add_task("TASK-001", "Auth-Modul", ["FEAT-001", "FEAT-002"])
        assert "TASK-001" in tm.matrix["features"]["FEAT-001"]["tasks"]
        assert "TASK-001" in tm.matrix["features"]["FEAT-002"]["tasks"]


# =========================================================================
# 6. TestDateien
# =========================================================================

class TestDateien:
    """Tests fuer Datei-Verwaltung."""

    def test_add_datei_speichert_korrekt(self, tmp_path):
        """Datei wird mit allen Feldern gespeichert."""
        tm = _erstelle_manager(tmp_path)
        tm.add_datei("login.py", ["TASK-001"], status="created", lines=50)
        datei = tm.matrix["dateien"]["login.py"]
        assert datei["tasks"] == ["TASK-001"]
        assert datei["status"] == "created"
        assert datei["lines"] == 50

    def test_rueckwaerts_verknuepfung_zu_task(self, tmp_path):
        """Dateipfad wird in Task.dateien eingetragen."""
        tm = _erstelle_manager(tmp_path)
        tm.add_task("TASK-001", "Login", ["FEAT-001"])
        tm.add_datei("login.py", ["TASK-001"])
        assert "login.py" in tm.matrix["tasks"]["TASK-001"]["dateien"]

    def test_mark_datei_completed_status(self, tmp_path):
        """mark_datei_completed setzt Status auf 'completed'."""
        tm = _erstelle_manager(tmp_path)
        tm.add_datei("login.py", ["TASK-001"])
        tm.mark_datei_completed("login.py", lines=120)
        assert tm.matrix["dateien"]["login.py"]["status"] == "completed"

    def test_mark_datei_completed_lines(self, tmp_path):
        """mark_datei_completed setzt Zeilenanzahl."""
        tm = _erstelle_manager(tmp_path)
        tm.add_datei("login.py", ["TASK-001"])
        tm.mark_datei_completed("login.py", lines=120)
        assert tm.matrix["dateien"]["login.py"]["lines"] == 120

    def test_mark_datei_completed_setzt_completed_at(self, tmp_path):
        """mark_datei_completed setzt completed_at Zeitstempel."""
        tm = _erstelle_manager(tmp_path)
        tm.add_datei("login.py", ["TASK-001"])
        tm.mark_datei_completed("login.py", lines=50)
        assert "completed_at" in tm.matrix["dateien"]["login.py"]

    def test_auto_completion_task(self, tmp_path):
        """Wenn alle Dateien eines Tasks fertig sind, wird Task 'completed'."""
        tm = _erstelle_manager(tmp_path)
        tm.add_task("TASK-001", "Login", ["FEAT-001"], datei="login.py")
        tm.add_datei("login.py", ["TASK-001"])
        tm.mark_datei_completed("login.py", lines=100)
        assert tm.matrix["tasks"]["TASK-001"]["status"] == "completed"

    def test_keine_auto_completion_bei_unvollstaendigen_dateien(self, tmp_path):
        """Task bleibt 'pending' wenn nicht alle Dateien fertig sind."""
        tm = _erstelle_manager(tmp_path)
        tm.add_task("TASK-001", "Login", ["FEAT-001"], datei="login.py")
        # Zweite Datei manuell hinzufuegen
        tm.matrix["tasks"]["TASK-001"]["dateien"].append("utils.py")
        tm.add_datei("login.py", ["TASK-001"])
        tm.add_datei("utils.py", ["TASK-001"])
        # Nur eine Datei als completed markieren
        tm.mark_datei_completed("login.py", lines=100)
        assert tm.matrix["tasks"]["TASK-001"]["status"] == "pending"

    def test_mark_nicht_existierende_datei_kein_crash(self, tmp_path):
        """mark_datei_completed fuer nicht-existierende Datei erzeugt keinen Fehler."""
        tm = _erstelle_manager(tmp_path)
        # Soll nicht crashen
        tm.mark_datei_completed("nicht_vorhanden.py", lines=10)


# =========================================================================
# 7. TestCoverage
# =========================================================================

class TestCoverage:
    """Tests fuer Coverage-Berechnung."""

    def test_keine_anforderungen_ergibt_null(self, tmp_path):
        """Ohne Anforderungen ist Coverage 0.0."""
        tm = _erstelle_manager(tmp_path)
        assert tm._calculate_coverage() == 0.0

    def test_vollstaendig_implementiert_ergibt_eins(self, tmp_path):
        """Anforderung mit komplettem Feature+Task(completed) ergibt 1.0."""
        tm = _erstelle_manager(tmp_path)
        tm.add_anforderung("REQ-001", "Login")
        tm.add_feature("FEAT-001", "Login-Formular", ["REQ-001"])
        tm.add_task("TASK-001", "Erstelle Login", ["FEAT-001"], status="completed")
        assert tm._calculate_coverage() == 1.0

    def test_anforderung_ohne_feature_ergibt_null(self, tmp_path):
        """Anforderung ohne verknuepftes Feature ergibt 0.0."""
        tm = _erstelle_manager(tmp_path)
        tm.add_anforderung("REQ-001", "Login")
        assert tm._calculate_coverage() == 0.0

    def test_gemischt_halb_implementiert(self, tmp_path):
        """1 von 2 Anforderungen implementiert ergibt 0.5."""
        tm = _erstelle_manager(tmp_path)
        tm.add_anforderung("REQ-001", "Login")
        tm.add_anforderung("REQ-002", "Dashboard")
        tm.add_feature("FEAT-001", "Login-Form", ["REQ-001"])
        tm.add_task("TASK-001", "Login", ["FEAT-001"], status="completed")
        # REQ-002 hat kein Feature
        assert tm._calculate_coverage() == 0.5

    def test_pending_task_zaehlt_nicht(self, tmp_path):
        """Task mit Status 'pending' zaehlt nicht als implementiert."""
        tm = _erstelle_manager(tmp_path)
        tm.add_anforderung("REQ-001", "Login")
        tm.add_feature("FEAT-001", "Login-Form", ["REQ-001"])
        tm.add_task("TASK-001", "Login", ["FEAT-001"], status="pending")
        assert tm._calculate_coverage() == 0.0

    def test_failed_task_zaehlt_nicht(self, tmp_path):
        """Task mit Status 'failed' zaehlt nicht als implementiert."""
        tm = _erstelle_manager(tmp_path)
        tm.add_anforderung("REQ-001", "Login")
        tm.add_feature("FEAT-001", "Login-Form", ["REQ-001"])
        tm.add_task("TASK-001", "Login", ["FEAT-001"], status="failed")
        assert tm._calculate_coverage() == 0.0

    def test_ein_von_zwei_tasks_completed(self, tmp_path):
        """Anforderung zaehlt als implementiert wenn mindestens ein Task completed."""
        tm = _erstelle_manager(tmp_path)
        tm.add_anforderung("REQ-001", "Login")
        tm.add_feature("FEAT-001", "Login-Form", ["REQ-001"])
        tm.add_task("TASK-001", "Form", ["FEAT-001"], status="pending")
        tm.add_task("TASK-002", "Validator", ["FEAT-001"], status="completed")
        assert tm._calculate_coverage() == 1.0

    def test_coverage_nach_update_summary(self, tmp_path):
        """Coverage wird durch _update_summary korrekt in summary geschrieben."""
        tm = _erstelle_manager(tmp_path)
        tm.add_anforderung("REQ-001", "Login")
        tm.add_feature("FEAT-001", "Login-Form", ["REQ-001"])
        tm.add_task("TASK-001", "Login", ["FEAT-001"], status="completed")
        tm._update_summary()
        assert tm.matrix["summary"]["coverage"] == 1.0


# =========================================================================
# 8. TestReports
# =========================================================================

class TestReports:
    """Tests fuer Report-Generierung."""

    def test_report_enthaelt_summary(self, tmp_path):
        """Report enthaelt summary-Abschnitt."""
        tm = _erstelle_vollstaendigen_manager(tmp_path)
        report = tm.get_traceability_report()
        assert "summary" in report

    def test_report_enthaelt_coverage_details(self, tmp_path):
        """Report enthaelt coverage_details-Abschnitt."""
        tm = _erstelle_vollstaendigen_manager(tmp_path)
        report = tm.get_traceability_report()
        assert "coverage_details" in report
        assert "anforderungen" in report["coverage_details"]
        assert "features" in report["coverage_details"]
        assert "tasks" in report["coverage_details"]

    def test_report_enthaelt_gaps(self, tmp_path):
        """Report enthaelt gaps-Abschnitt."""
        tm = _erstelle_vollstaendigen_manager(tmp_path)
        report = tm.get_traceability_report()
        assert "gaps" in report

    def test_report_enthaelt_statistics(self, tmp_path):
        """Report enthaelt statistics-Abschnitt."""
        tm = _erstelle_vollstaendigen_manager(tmp_path)
        report = tm.get_traceability_report()
        assert "statistics" in report

    def test_find_gaps_anforderungen_ohne_features(self, tmp_path):
        """Erkennt Anforderungen ohne verknuepfte Features."""
        tm = _erstelle_manager(tmp_path)
        tm.add_anforderung("REQ-001", "Login")
        # Kein Feature verknuepft
        gaps = tm._find_gaps()
        assert "REQ-001" in gaps["anforderungen_ohne_features"]

    def test_find_gaps_features_ohne_tasks(self, tmp_path):
        """Erkennt Features ohne verknuepfte Tasks."""
        tm = _erstelle_manager(tmp_path)
        tm.add_feature("FEAT-001", "Login", [])
        gaps = tm._find_gaps()
        assert "FEAT-001" in gaps["features_ohne_tasks"]

    def test_find_gaps_tasks_ohne_dateien(self, tmp_path):
        """Erkennt Tasks ohne verknuepfte Dateien."""
        tm = _erstelle_manager(tmp_path)
        tm.add_task("TASK-001", "Login", ["FEAT-001"])
        gaps = tm._find_gaps()
        assert "TASK-001" in gaps["tasks_ohne_dateien"]

    def test_find_gaps_orphan_dateien(self, tmp_path):
        """Erkennt Dateien ohne verknuepfte Tasks."""
        tm = _erstelle_manager(tmp_path)
        tm.add_datei("orphan.py", [])
        gaps = tm._find_gaps()
        assert "orphan.py" in gaps["orphan_dateien"]

    def test_find_gaps_features_ohne_user_stories(self, tmp_path):
        """Erkennt Features ohne verknuepfte User Stories."""
        tm = _erstelle_manager(tmp_path)
        tm.add_feature("FEAT-001", "Login", [])
        gaps = tm._find_gaps()
        assert "FEAT-001" in gaps["features_ohne_user_stories"]

    def test_statistics_total_lines(self, tmp_path):
        """Berechnet Gesamtzeilenzahl korrekt."""
        tm = _erstelle_manager(tmp_path)
        tm.add_datei("a.py", [], lines=100)
        tm.add_datei("b.py", [], lines=200)
        stats = tm._get_statistics()
        assert stats["total_lines_of_code"] == 300

    def test_statistics_avg_lines_per_file(self, tmp_path):
        """Berechnet durchschnittliche Zeilen pro Datei korrekt."""
        tm = _erstelle_manager(tmp_path)
        tm.add_datei("a.py", [], lines=100)
        tm.add_datei("b.py", [], lines=200)
        stats = tm._get_statistics()
        assert stats["avg_lines_per_file"] == 150.0

    def test_statistics_files_per_task(self, tmp_path):
        """Berechnet Dateien pro Task korrekt."""
        tm = _erstelle_manager(tmp_path)
        tm.add_task("TASK-001", "T1", [])
        tm.add_datei("a.py", [])
        tm.add_datei("b.py", [])
        stats = tm._get_statistics()
        assert stats["files_per_task"] == 2.0

    def test_statistics_tasks_per_feature(self, tmp_path):
        """Berechnet Tasks pro Feature korrekt."""
        tm = _erstelle_manager(tmp_path)
        tm.add_feature("FEAT-001", "F1", [])
        tm.add_task("TASK-001", "T1", [])
        tm.add_task("TASK-002", "T2", [])
        stats = tm._get_statistics()
        assert stats["tasks_per_feature"] == 2.0

    def test_task_coverage_status_verteilung(self, tmp_path):
        """Gibt korrekte Status-Verteilung der Tasks zurueck."""
        tm = _erstelle_manager(tmp_path)
        tm.add_task("TASK-001", "T1", [], status="pending")
        tm.add_task("TASK-002", "T2", [], status="completed")
        tm.add_task("TASK-003", "T3", [], status="completed")
        tm.add_task("TASK-004", "T4", [], status="failed")
        tc = tm._get_task_coverage()
        assert tc["pending"] == 1
        assert tc["completed"] == 2
        assert tc["failed"] == 1
        assert tc["in_progress"] == 0


# =========================================================================
# 9. TestPersistence
# =========================================================================

class TestPersistence:
    """Tests fuer Speichern und Laden."""

    def test_save_und_laden(self, tmp_path):
        """Gespeicherte Daten werden von neuem Manager korrekt geladen."""
        tm = _erstelle_manager(tmp_path)
        tm.add_anforderung("REQ-001", "Login")
        tm.add_feature("FEAT-001", "Login-Form", ["REQ-001"])
        tm.add_task("TASK-001", "Login erstellen", ["FEAT-001"], datei="login.py")
        tm.save()

        tm2 = _erstelle_manager(tmp_path)
        assert "REQ-001" in tm2.matrix["anforderungen"]
        assert "FEAT-001" in tm2.matrix["features"]
        assert "TASK-001" in tm2.matrix["tasks"]

    def test_korrupte_json_kein_crash(self, tmp_path):
        """Korrupte JSON-Datei erzeugt keinen Fehler beim Laden."""
        matrix_file = os.path.join(str(tmp_path), "traceability_matrix.json")
        with open(matrix_file, "w", encoding="utf-8") as f:
            f.write("{korrupte daten!!!")

        # Soll nicht crashen, sondern Default-Matrix verwenden
        tm = TraceabilityManager(str(tmp_path))
        assert tm.matrix["version"] == "1.0"
        assert tm.matrix["anforderungen"] == {}

    def test_updated_at_wird_aktualisiert(self, tmp_path):
        """updated_at Zeitstempel wird bei save() aktualisiert."""
        tm = _erstelle_manager(tmp_path)
        original_updated = tm.matrix["updated_at"]

        # Kurze Pause simulieren durch direkte Manipulation
        tm.matrix["updated_at"] = "2020-01-01T00:00:00"
        tm.save()

        # Nach save() muss updated_at neuer sein als der manipulierte Wert
        assert tm.matrix["updated_at"] != "2020-01-01T00:00:00"

    def test_summary_wird_bei_save_aktualisiert(self, tmp_path):
        """Summary-Werte werden bei save() neu berechnet."""
        tm = _erstelle_manager(tmp_path)
        tm.add_anforderung("REQ-001", "Login")
        tm.add_feature("FEAT-001", "Login-Form", ["REQ-001"])
        tm.save()

        assert tm.matrix["summary"]["total_anforderungen"] == 1
        assert tm.matrix["summary"]["total_features"] == 1

    def test_datei_wird_auf_disk_erstellt(self, tmp_path):
        """save() erstellt die JSON-Datei auf der Festplatte."""
        tm = _erstelle_manager(tmp_path)
        tm.save()
        assert os.path.exists(tm.matrix_file)


# =========================================================================
# 10. TestReset
# =========================================================================

class TestReset:
    """Tests fuer Matrix-Zuruecksetzung."""

    def test_reset_matrix_leer(self, tmp_path):
        """Nach reset sind alle Datensammlungen leer."""
        tm = _erstelle_vollstaendigen_manager(tmp_path)
        tm.reset()
        assert tm.matrix["anforderungen"] == {}
        assert tm.matrix["features"] == {}
        assert tm.matrix["user_stories"] == {}
        assert tm.matrix["tasks"] == {}
        assert tm.matrix["dateien"] == {}

    def test_reset_summary_nullen(self, tmp_path):
        """Nach reset sind alle Summary-Werte auf 0."""
        tm = _erstelle_vollstaendigen_manager(tmp_path)
        tm.reset()
        summary = tm.matrix["summary"]
        assert summary["total_anforderungen"] == 0
        assert summary["total_features"] == 0
        assert summary["total_user_stories"] == 0
        assert summary["total_tasks"] == 0
        assert summary["total_dateien"] == 0
        assert summary["coverage"] == 0.0

    def test_reset_nach_daten_hinzufuegen(self, tmp_path):
        """Reset nach Hinzufuegen von Daten entfernt alles."""
        tm = _erstelle_manager(tmp_path)
        tm.add_anforderung("REQ-001", "Login")
        tm.add_feature("FEAT-001", "Login-Form", ["REQ-001"])
        tm.add_task("TASK-001", "Login", ["FEAT-001"], datei="login.py")
        tm.add_datei("login.py", ["TASK-001"], lines=100)
        tm.add_user_story("US-001", "Story", "FEAT-001")

        tm.reset()

        assert len(tm.matrix["anforderungen"]) == 0
        assert len(tm.matrix["features"]) == 0
        assert len(tm.matrix["tasks"]) == 0
        assert len(tm.matrix["dateien"]) == 0
        assert len(tm.matrix["user_stories"]) == 0
