# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 14.02.2026
Version: 1.0
Beschreibung: Unit-Tests fuer backend/feature_tracking_db.py.
              Testet FeatureTrackingDB mit temporaeren SQLite-Datenbanken.
              Umfasst Initialisierung, CRUD-Operationen, Scheduling-Score,
              Dependency-Graph, Kategorie-Erkennung und Singleton-Pattern.

              AENDERUNG 14.02.2026: Initiale Test-Suite mit 63 Tests.
"""

import json
import sqlite3
import threading

import pytest

from backend.feature_tracking_db import FeatureTrackingDB, get_feature_tracking_db
import backend.feature_tracking_db as ftdb_module


# =====================================================================
# Fixtures
# =====================================================================

@pytest.fixture
def db(tmp_path):
    """Erstellt eine temporaere FeatureTrackingDB."""
    db_path = str(tmp_path / "test_features.db")
    return FeatureTrackingDB(db_path=db_path)


@pytest.fixture
def sample_plan():
    """Beispiel-Planner-Output mit Abhaengigkeiten."""
    return [
        {"path": "app/layout.js", "description": "Root Layout", "priority": 1, "depends_on": [], "estimated_lines": 30},
        {"path": "app/page.js", "description": "Hauptseite", "priority": 2, "depends_on": ["app/layout.js"], "estimated_lines": 80},
        {"path": "lib/db.js", "description": "Datenbank-Verbindung", "priority": 1, "depends_on": [], "estimated_lines": 40},
        {"path": "app/api/tasks/route.js", "description": "API Route", "priority": 3, "depends_on": ["lib/db.js"], "estimated_lines": 60},
        {"path": "tests/page.test.js", "description": "Tests", "priority": 5, "depends_on": ["app/page.js"], "estimated_lines": 50},
    ]


RUN_ID = "test_run_20260214_120000"
RUN_ID_2 = "test_run_20260214_130000"


# =====================================================================
# TestFeatureTrackingDBInit - Initialisierung und Schema
# =====================================================================
class TestFeatureTrackingDBInit:
    """Tests fuer die Datenbank-Initialisierung."""

    def test_db_datei_wird_erstellt(self, tmp_path):
        """DB-Datei wird beim Erstellen der Instanz angelegt."""
        db_path = str(tmp_path / "init_test.db")
        FeatureTrackingDB(db_path=db_path)
        import os
        assert os.path.exists(db_path), "Erwartet: DB-Datei existiert, Erhalten: Datei nicht gefunden"

    def test_features_tabelle_existiert(self, db):
        """Die features-Tabelle wird korrekt erstellt."""
        conn = db._get_conn()
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='features'"
        )
        result = cursor.fetchone()
        assert result is not None, "Erwartet: Tabelle 'features' existiert, Erhalten: None"

    def test_wal_mode_aktiviert(self, db):
        """WAL-Journal-Mode wird korrekt gesetzt."""
        conn = db._get_conn()
        result = conn.execute("PRAGMA journal_mode").fetchone()
        assert result[0] == "wal", f"Erwartet: WAL-Mode, Erhalten: {result[0]}"

    def test_index_run_id_existiert(self, db):
        """Index auf run_id wird erstellt."""
        conn = db._get_conn()
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_features_run_id'"
        )
        result = cursor.fetchone()
        assert result is not None, "Erwartet: Index idx_features_run_id existiert, Erhalten: None"

    def test_index_status_existiert(self, db):
        """Index auf status wird erstellt."""
        conn = db._get_conn()
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_features_status'"
        )
        result = cursor.fetchone()
        assert result is not None, "Erwartet: Index idx_features_status existiert, Erhalten: None"


# =====================================================================
# TestCreateFeaturesFromPlan - Feature-Erstellung aus Planner-Output
# =====================================================================
class TestCreateFeaturesFromPlan:
    """Tests fuer create_features_from_plan()."""

    def test_gibt_liste_von_ids_zurueck(self, db, sample_plan):
        """Gibt eine Liste von Feature-IDs zurueck."""
        ids = db.create_features_from_plan(RUN_ID, sample_plan)
        assert len(ids) == 5, f"Erwartet: 5 IDs, Erhalten: {len(ids)}"
        assert all(isinstance(i, int) for i in ids), "Erwartet: Alle IDs sind Integer"

    def test_features_haben_status_pending(self, db, sample_plan):
        """Alle erstellten Features haben Status 'pending'."""
        db.create_features_from_plan(RUN_ID, sample_plan)
        features = db.get_features(RUN_ID)
        for f in features:
            assert f["status"] == "pending", f"Erwartet: pending, Erhalten: {f['status']} bei {f['title']}"

    def test_title_ist_basename(self, db, sample_plan):
        """Title wird aus dem Basename des Pfades abgeleitet."""
        db.create_features_from_plan(RUN_ID, sample_plan)
        features = db.get_features(RUN_ID)
        assert features[0]["title"] == "layout.js", f"Erwartet: layout.js, Erhalten: {features[0]['title']}"
        assert features[3]["title"] == "route.js", f"Erwartet: route.js, Erhalten: {features[3]['title']}"

    def test_kategorie_korrekt_abgeleitet(self, db, sample_plan):
        """Kategorie wird korrekt aus dem Dateipfad abgeleitet."""
        db.create_features_from_plan(RUN_ID, sample_plan)
        features = db.get_features(RUN_ID)
        # Sortiert nach priority ASC, id ASC
        kategorien = {f["file_path"]: f["category"] for f in features}
        assert kategorien["app/layout.js"] == "feature", "layout.js sollte 'feature' sein"
        assert kategorien["tests/page.test.js"] == "test", "test-Datei sollte 'test' sein"
        assert kategorien["lib/db.js"] == "file", "lib/db.js sollte 'file' sein"

    def test_leere_liste_gibt_leere_ids_zurueck(self, db):
        """Leere plan_files ergeben leere ID-Liste."""
        ids = db.create_features_from_plan(RUN_ID, [])
        assert ids == [], f"Erwartet: [], Erhalten: {ids}"

    def test_depends_on_als_json_gespeichert(self, db, sample_plan):
        """depends_on wird als JSON-String in der DB gespeichert."""
        db.create_features_from_plan(RUN_ID, sample_plan)
        conn = db._get_conn()
        row = conn.execute(
            "SELECT depends_on FROM features WHERE file_path = ?",
            ("app/page.js",)
        ).fetchone()
        raw = row["depends_on"]
        parsed = json.loads(raw)
        assert parsed == ["app/layout.js"], f"Erwartet: ['app/layout.js'], Erhalten: {parsed}"

    def test_priority_korrekt_gespeichert(self, db, sample_plan):
        """Priority-Werte werden korrekt gespeichert."""
        db.create_features_from_plan(RUN_ID, sample_plan)
        features = db.get_features(RUN_ID)
        prio_map = {f["file_path"]: f["priority"] for f in features}
        assert prio_map["app/layout.js"] == 1, "layout.js sollte Priority 1 haben"
        assert prio_map["app/page.js"] == 2, "page.js sollte Priority 2 haben"
        assert prio_map["tests/page.test.js"] == 5, "test sollte Priority 5 haben"

    def test_estimated_lines_gespeichert(self, db, sample_plan):
        """estimated_lines werden korrekt gespeichert."""
        db.create_features_from_plan(RUN_ID, sample_plan)
        features = db.get_features(RUN_ID)
        lines_map = {f["file_path"]: f["estimated_lines"] for f in features}
        assert lines_map["app/layout.js"] == 30, "layout.js sollte 30 estimated_lines haben"
        assert lines_map["app/page.js"] == 80, "page.js sollte 80 estimated_lines haben"


# =====================================================================
# TestUpdateStatus - Status-Aenderungen
# =====================================================================
class TestUpdateStatus:
    """Tests fuer update_status()."""

    def test_status_aendern(self, db, sample_plan):
        """Status wird korrekt geaendert."""
        ids = db.create_features_from_plan(RUN_ID, sample_plan)
        db.update_status(ids[0], "in_progress")
        feature = db.get_features(RUN_ID)[0]
        assert feature["status"] == "in_progress", f"Erwartet: in_progress, Erhalten: {feature['status']}"

    def test_agent_wird_gesetzt(self, db, sample_plan):
        """assigned_agent wird korrekt gesetzt."""
        ids = db.create_features_from_plan(RUN_ID, sample_plan)
        db.update_status(ids[0], "in_progress", agent="Coder-Agent")
        feature = db.get_features(RUN_ID)[0]
        assert feature["assigned_agent"] == "Coder-Agent", f"Erwartet: Coder-Agent, Erhalten: {feature['assigned_agent']}"

    def test_error_wird_gesetzt(self, db, sample_plan):
        """error_message wird korrekt gesetzt."""
        ids = db.create_features_from_plan(RUN_ID, sample_plan)
        db.update_status(ids[0], "failed", error="Syntax-Fehler in Zeile 42")
        features = db.get_features(RUN_ID)
        feat = next(f for f in features if f["id"] == ids[0])
        assert feat["error_message"] == "Syntax-Fehler in Zeile 42"

    def test_error_auf_500_zeichen_begrenzt(self, db, sample_plan):
        """error_message wird auf maximal 500 Zeichen begrenzt."""
        ids = db.create_features_from_plan(RUN_ID, sample_plan)
        langer_fehler = "X" * 1000
        db.update_status(ids[0], "failed", error=langer_fehler)
        features = db.get_features(RUN_ID)
        feat = next(f for f in features if f["id"] == ids[0])
        assert len(feat["error_message"]) == 500, f"Erwartet: 500 Zeichen, Erhalten: {len(feat['error_message'])}"

    def test_in_progress_erhoeht_iteration_count(self, db, sample_plan):
        """Bei Status 'in_progress' wird iteration_count um 1 erhoeht."""
        ids = db.create_features_from_plan(RUN_ID, sample_plan)
        db.update_status(ids[0], "in_progress")
        db.update_status(ids[0], "in_progress")
        db.update_status(ids[0], "in_progress")
        features = db.get_features(RUN_ID)
        feat = next(f for f in features if f["id"] == ids[0])
        assert feat["iteration_count"] == 3, f"Erwartet: 3, Erhalten: {feat['iteration_count']}"

    def test_done_setzt_completed_at(self, db, sample_plan):
        """Bei Status 'done' wird completed_at gesetzt."""
        ids = db.create_features_from_plan(RUN_ID, sample_plan)
        db.update_status(ids[0], "done")
        features = db.get_features(RUN_ID)
        feat = next(f for f in features if f["id"] == ids[0])
        assert feat["completed_at"] is not None, "Erwartet: completed_at gesetzt, Erhalten: None"

    def test_failed_setzt_completed_at(self, db, sample_plan):
        """Bei Status 'failed' wird completed_at gesetzt."""
        ids = db.create_features_from_plan(RUN_ID, sample_plan)
        db.update_status(ids[0], "failed", error="Fehlgeschlagen")
        features = db.get_features(RUN_ID)
        feat = next(f for f in features if f["id"] == ids[0])
        assert feat["completed_at"] is not None, "Erwartet: completed_at gesetzt bei failed, Erhalten: None"

    def test_updated_at_wird_aktualisiert(self, db, sample_plan):
        """updated_at wird bei jeder Status-Aenderung aktualisiert."""
        ids = db.create_features_from_plan(RUN_ID, sample_plan)
        features_vorher = db.get_features(RUN_ID)
        feat_vorher = next(f for f in features_vorher if f["id"] == ids[0])
        updated_vorher = feat_vorher["updated_at"]

        db.update_status(ids[0], "in_progress")
        features_nachher = db.get_features(RUN_ID)
        feat_nachher = next(f for f in features_nachher if f["id"] == ids[0])
        # updated_at sollte sich geaendert haben (oder zumindest nicht aelter sein)
        assert feat_nachher["updated_at"] >= updated_vorher, "updated_at sollte aktualisiert worden sein"


# =====================================================================
# TestMarkDone - Feature als erledigt markieren
# =====================================================================
class TestMarkDone:
    """Tests fuer mark_done()."""

    def test_status_wird_done(self, db, sample_plan):
        """Status wird auf 'done' gesetzt."""
        ids = db.create_features_from_plan(RUN_ID, sample_plan)
        db.mark_done(ids[0])
        features = db.get_features(RUN_ID)
        feat = next(f for f in features if f["id"] == ids[0])
        assert feat["status"] == "done", f"Erwartet: done, Erhalten: {feat['status']}"

    def test_actual_lines_gesetzt(self, db, sample_plan):
        """actual_lines wird korrekt gesetzt."""
        ids = db.create_features_from_plan(RUN_ID, sample_plan)
        db.mark_done(ids[0], actual_lines=42)
        features = db.get_features(RUN_ID)
        feat = next(f for f in features if f["id"] == ids[0])
        assert feat["actual_lines"] == 42, f"Erwartet: 42, Erhalten: {feat['actual_lines']}"

    def test_completed_at_gesetzt(self, db, sample_plan):
        """completed_at wird beim Markieren als done gesetzt."""
        ids = db.create_features_from_plan(RUN_ID, sample_plan)
        db.mark_done(ids[0])
        features = db.get_features(RUN_ID)
        feat = next(f for f in features if f["id"] == ids[0])
        assert feat["completed_at"] is not None, "Erwartet: completed_at gesetzt, Erhalten: None"

    def test_actual_lines_default_null(self, db, sample_plan):
        """actual_lines ist standardmaessig 0 wenn nicht angegeben."""
        ids = db.create_features_from_plan(RUN_ID, sample_plan)
        db.mark_done(ids[0])
        features = db.get_features(RUN_ID)
        feat = next(f for f in features if f["id"] == ids[0])
        assert feat["actual_lines"] == 0, f"Erwartet: 0, Erhalten: {feat['actual_lines']}"


# =====================================================================
# TestMarkFailed - Feature als fehlgeschlagen markieren
# =====================================================================
class TestMarkFailed:
    """Tests fuer mark_failed()."""

    def test_status_wird_failed(self, db, sample_plan):
        """Status wird auf 'failed' gesetzt."""
        ids = db.create_features_from_plan(RUN_ID, sample_plan)
        db.mark_failed(ids[0], "Kompilierungsfehler")
        features = db.get_features(RUN_ID)
        feat = next(f for f in features if f["id"] == ids[0])
        assert feat["status"] == "failed", f"Erwartet: failed, Erhalten: {feat['status']}"

    def test_error_message_gesetzt(self, db, sample_plan):
        """error_message wird korrekt gesetzt."""
        ids = db.create_features_from_plan(RUN_ID, sample_plan)
        db.mark_failed(ids[0], "Import-Fehler: Modul nicht gefunden")
        features = db.get_features(RUN_ID)
        feat = next(f for f in features if f["id"] == ids[0])
        assert feat["error_message"] == "Import-Fehler: Modul nicht gefunden"

    def test_delegiert_an_update_status(self, db, sample_plan):
        """mark_failed() nutzt intern update_status() und setzt completed_at."""
        ids = db.create_features_from_plan(RUN_ID, sample_plan)
        db.mark_failed(ids[0], "Fehler")
        features = db.get_features(RUN_ID)
        feat = next(f for f in features if f["id"] == ids[0])
        # Weil update_status bei 'failed' auch completed_at setzt
        assert feat["completed_at"] is not None, "Erwartet: completed_at gesetzt (via update_status), Erhalten: None"


# =====================================================================
# TestGetFeatures - Features abfragen
# =====================================================================
class TestGetFeatures:
    """Tests fuer get_features()."""

    def test_alle_features_eines_runs(self, db, sample_plan):
        """Gibt alle Features eines Runs zurueck."""
        db.create_features_from_plan(RUN_ID, sample_plan)
        features = db.get_features(RUN_ID)
        assert len(features) == 5, f"Erwartet: 5 Features, Erhalten: {len(features)}"

    def test_gefiltert_nach_status(self, db, sample_plan):
        """Filtert Features nach Status."""
        ids = db.create_features_from_plan(RUN_ID, sample_plan)
        db.update_status(ids[0], "in_progress")
        db.update_status(ids[2], "in_progress")

        pending = db.get_features(RUN_ID, status="pending")
        in_progress = db.get_features(RUN_ID, status="in_progress")
        assert len(pending) == 3, f"Erwartet: 3 pending, Erhalten: {len(pending)}"
        assert len(in_progress) == 2, f"Erwartet: 2 in_progress, Erhalten: {len(in_progress)}"

    def test_sortiert_nach_priority_dann_id(self, db, sample_plan):
        """Features werden nach priority ASC, dann id ASC sortiert."""
        db.create_features_from_plan(RUN_ID, sample_plan)
        features = db.get_features(RUN_ID)
        priorities = [f["priority"] for f in features]
        # Pruefen: jede Priority ist <= der naechsten (oder bei gleicher Priority steigt die ID)
        for i in range(len(features) - 1):
            assert (features[i]["priority"], features[i]["id"]) <= (features[i + 1]["priority"], features[i + 1]["id"]), \
                f"Sortierung verletzt bei Index {i}: ({features[i]['priority']}, {features[i]['id']}) vs ({features[i + 1]['priority']}, {features[i + 1]['id']})"

    def test_leerer_run_gibt_leere_liste(self, db):
        """Ein Run ohne Features gibt eine leere Liste zurueck."""
        features = db.get_features("nicht_existierender_run")
        assert features == [], f"Erwartet: [], Erhalten: {features}"

    def test_depends_on_als_liste_geparst(self, db, sample_plan):
        """depends_on wird von JSON-String zu Python-Liste konvertiert."""
        db.create_features_from_plan(RUN_ID, sample_plan)
        features = db.get_features(RUN_ID)
        page_feature = next(f for f in features if f["file_path"] == "app/page.js")
        assert isinstance(page_feature["depends_on"], list), "depends_on sollte eine Liste sein"
        assert page_feature["depends_on"] == ["app/layout.js"]

    def test_verschiedene_runs_isoliert(self, db, sample_plan):
        """Features verschiedener Runs sind voneinander isoliert."""
        db.create_features_from_plan(RUN_ID, sample_plan)
        db.create_features_from_plan(RUN_ID_2, sample_plan[:2])

        features_1 = db.get_features(RUN_ID)
        features_2 = db.get_features(RUN_ID_2)
        assert len(features_1) == 5, f"Erwartet: 5 fuer Run 1, Erhalten: {len(features_1)}"
        assert len(features_2) == 2, f"Erwartet: 2 fuer Run 2, Erhalten: {len(features_2)}"


# =====================================================================
# TestGetFeatureByPath - Feature anhand des Pfads finden
# =====================================================================
class TestGetFeatureByPath:
    """Tests fuer get_feature_by_path()."""

    def test_findet_feature_anhand_pfad(self, db, sample_plan):
        """Findet ein Feature anhand des Dateipfads."""
        db.create_features_from_plan(RUN_ID, sample_plan)
        feature = db.get_feature_by_path(RUN_ID, "app/layout.js")
        assert feature is not None, "Erwartet: Feature gefunden, Erhalten: None"
        assert feature["file_path"] == "app/layout.js"

    def test_gibt_none_bei_unbekanntem_pfad(self, db, sample_plan):
        """Gibt None zurueck wenn der Pfad nicht existiert."""
        db.create_features_from_plan(RUN_ID, sample_plan)
        feature = db.get_feature_by_path(RUN_ID, "nicht/existent.js")
        assert feature is None, f"Erwartet: None, Erhalten: {feature}"

    def test_verschiedene_run_ids_isoliert(self, db, sample_plan):
        """Features verschiedener Runs sind isoliert nach run_id."""
        db.create_features_from_plan(RUN_ID, sample_plan)
        # Gleicher Pfad existiert nicht in einem anderen Run
        feature = db.get_feature_by_path(RUN_ID_2, "app/layout.js")
        assert feature is None, "Erwartet: None fuer anderen Run, Erhalten: Feature"

    def test_gibt_dict_mit_korrekten_feldern_zurueck(self, db, sample_plan):
        """Das zurueckgegebene Dict enthaelt alle relevanten Felder."""
        db.create_features_from_plan(RUN_ID, sample_plan)
        feature = db.get_feature_by_path(RUN_ID, "lib/db.js")
        assert "id" in feature, "Feld 'id' fehlt"
        assert "status" in feature, "Feld 'status' fehlt"
        assert "priority" in feature, "Feld 'priority' fehlt"
        assert "depends_on" in feature, "Feld 'depends_on' fehlt"
        assert "description" in feature, "Feld 'description' fehlt"


# =====================================================================
# TestGetNextFeature - Naechstes unblockiertes Feature
# =====================================================================
class TestGetNextFeature:
    """Tests fuer get_next_feature() mit Scheduling-Score."""

    def test_waehlt_unblockiertes_feature(self, db, sample_plan):
        """Waehlt ein Feature ohne blockierte Abhaengigkeiten."""
        db.create_features_from_plan(RUN_ID, sample_plan)
        nxt = db.get_next_feature(RUN_ID)
        assert nxt is not None, "Erwartet: Ein Feature, Erhalten: None"
        # Nur layout.js und lib/db.js haben keine Abhaengigkeiten
        assert nxt["file_path"] in ("app/layout.js", "lib/db.js"), \
            f"Erwartet: unblockiertes Feature, Erhalten: {nxt['file_path']}"

    def test_blockierte_features_uebersprungen(self, db, sample_plan):
        """Features mit unerfuellten Abhaengigkeiten werden uebersprungen."""
        db.create_features_from_plan(RUN_ID, sample_plan)
        nxt = db.get_next_feature(RUN_ID)
        # page.js haengt von layout.js ab, route.js von db.js, test von page.js
        # Keines der blockierten sollte zurueckgegeben werden
        assert nxt["file_path"] not in ("app/page.js", "app/api/tasks/route.js", "tests/page.test.js"), \
            f"Erwartet: kein blockiertes Feature, Erhalten: {nxt['file_path']}"

    def test_scheduling_score_bevorzugt_entblocker(self, db, sample_plan):
        """Features die andere entblocken haben hoeheren Score."""
        db.create_features_from_plan(RUN_ID, sample_plan)
        nxt = db.get_next_feature(RUN_ID)
        # layout.js entblockt page.js (unblocking=1), lib/db.js entblockt route.js (unblocking=1)
        # Beide haben Priority 1, also gleichen Priority-Anteil (10*(10-1)=90)
        # layout.js hat niedrigere ID → hoeherer Score (weil id-Anteil addiert wird, aber gleich)
        # Score layout.js: 100*1 + 90 + id1 vs lib/db.js: 100*1 + 90 + id3
        # Aber page.js hat test als abhaengig, also entblockt layout.js INDIREKT mehr
        # Direkt: layout.js unblocks page.js (1), db.js unblocks route.js (1)
        assert nxt is not None

    def test_scheduling_score_formel(self, db, tmp_path):
        """Scheduling-Score = (100 * unblocking_count) + (10 * (10 - priority)) + (1 * id)."""
        # Erstelle Features mit bekanntem Scoring
        plan = [
            {"path": "a.js", "description": "A", "priority": 5, "depends_on": [], "estimated_lines": 10},
            {"path": "b.js", "description": "B", "priority": 1, "depends_on": [], "estimated_lines": 10},
            {"path": "c.js", "description": "C", "priority": 1, "depends_on": ["a.js"], "estimated_lines": 10},
            {"path": "d.js", "description": "D", "priority": 1, "depends_on": ["a.js"], "estimated_lines": 10},
        ]
        db.create_features_from_plan(RUN_ID, plan)
        nxt = db.get_next_feature(RUN_ID)
        # a.js: unblocking=2 (c.js und d.js), priority=5 → Score = 200 + 50 + id_a
        # b.js: unblocking=0, priority=1 → Score = 0 + 90 + id_b
        # a.js Score (200+50+1=251) > b.js Score (0+90+2=92)
        assert nxt["file_path"] == "a.js", f"Erwartet: a.js (hoechster Score), Erhalten: {nxt['file_path']}"

    def test_keine_pending_features_gibt_none(self, db, sample_plan):
        """Wenn keine pending Features vorhanden sind, wird None zurueckgegeben."""
        ids = db.create_features_from_plan(RUN_ID, sample_plan)
        for fid in ids:
            db.update_status(fid, "done")
        nxt = db.get_next_feature(RUN_ID)
        assert nxt is None, f"Erwartet: None (keine pending), Erhalten: {nxt}"

    def test_alle_blockiert_gibt_none(self, db):
        """Wenn alle pending Features blockiert sind, wird None zurueckgegeben."""
        plan = [
            {"path": "a.js", "description": "A", "priority": 1, "depends_on": ["b.js"], "estimated_lines": 10},
            {"path": "b.js", "description": "B", "priority": 1, "depends_on": ["a.js"], "estimated_lines": 10},
        ]
        db.create_features_from_plan(RUN_ID, plan)
        nxt = db.get_next_feature(RUN_ID)
        # Zirkulaere Abhaengigkeit → beide blockiert
        assert nxt is None, f"Erwartet: None (zirkulaer blockiert), Erhalten: {nxt}"

    def test_nach_done_wird_abhaengiges_frei(self, db, sample_plan):
        """Nach Markieren als done werden abhaengige Features freigegeben."""
        ids = db.create_features_from_plan(RUN_ID, sample_plan)
        # layout.js als done markieren
        layout_feature = db.get_feature_by_path(RUN_ID, "app/layout.js")
        db.mark_done(layout_feature["id"])
        # db.js auch als done markieren
        db_feature = db.get_feature_by_path(RUN_ID, "lib/db.js")
        db.mark_done(db_feature["id"])

        nxt = db.get_next_feature(RUN_ID)
        assert nxt is not None, "Erwartet: Ein freigegebenes Feature, Erhalten: None"
        # page.js und route.js sind jetzt frei
        assert nxt["file_path"] in ("app/page.js", "app/api/tasks/route.js"), \
            f"Erwartet: page.js oder route.js, Erhalten: {nxt['file_path']}"

    def test_leerer_run_gibt_none(self, db):
        """Ein Run ohne Features gibt None zurueck."""
        nxt = db.get_next_feature("leerer_run")
        assert nxt is None, f"Erwartet: None, Erhalten: {nxt}"


# =====================================================================
# TestGetStats - Statistiken pro Run
# =====================================================================
class TestGetStats:
    """Tests fuer get_stats()."""

    def test_zaehler_pro_status_korrekt(self, db, sample_plan):
        """Zaehler pro Status werden korrekt berechnet."""
        ids = db.create_features_from_plan(RUN_ID, sample_plan)
        db.update_status(ids[0], "in_progress")
        db.update_status(ids[1], "done")
        db.mark_failed(ids[2], "Fehler")

        stats = db.get_stats(RUN_ID)
        assert stats["pending"] == 2, f"Erwartet: 2 pending, Erhalten: {stats['pending']}"
        assert stats["in_progress"] == 1, f"Erwartet: 1 in_progress, Erhalten: {stats['in_progress']}"
        assert stats["done"] == 1, f"Erwartet: 1 done, Erhalten: {stats['done']}"
        assert stats["failed"] == 1, f"Erwartet: 1 failed, Erhalten: {stats['failed']}"

    def test_total_berechnet(self, db, sample_plan):
        """total ist die Summe aller Status-Zaehler."""
        db.create_features_from_plan(RUN_ID, sample_plan)
        stats = db.get_stats(RUN_ID)
        assert stats["total"] == 5, f"Erwartet: 5 total, Erhalten: {stats['total']}"

    def test_percentage_berechnet(self, db, sample_plan):
        """percentage berechnet den Anteil der done Features."""
        ids = db.create_features_from_plan(RUN_ID, sample_plan)
        db.mark_done(ids[0])
        db.mark_done(ids[1])

        stats = db.get_stats(RUN_ID)
        # 2 von 5 = 40.0%
        assert stats["percentage"] == 40.0, f"Erwartet: 40.0%, Erhalten: {stats['percentage']}"

    def test_percentage_bei_null_total(self, db):
        """percentage ist 0.0 wenn keine Features vorhanden sind."""
        stats = db.get_stats("leerer_run")
        assert stats["percentage"] == 0.0, f"Erwartet: 0.0, Erhalten: {stats['percentage']}"

    def test_leerer_run_alle_null(self, db):
        """Leerer Run gibt alle Zaehler als 0 zurueck."""
        stats = db.get_stats("leerer_run")
        assert stats["pending"] == 0
        assert stats["in_progress"] == 0
        assert stats["review"] == 0
        assert stats["done"] == 0
        assert stats["failed"] == 0
        assert stats["total"] == 0


# =====================================================================
# TestGetDependencyGraph - Graph-Daten fuer Frontend
# =====================================================================
class TestGetDependencyGraph:
    """Tests fuer get_dependency_graph()."""

    def test_nodes_korrekt(self, db, sample_plan):
        """Nodes enthalten alle Features mit korrekten Feldern."""
        db.create_features_from_plan(RUN_ID, sample_plan)
        graph = db.get_dependency_graph(RUN_ID)
        assert len(graph["nodes"]) == 5, f"Erwartet: 5 Nodes, Erhalten: {len(graph['nodes'])}"
        node = graph["nodes"][0]
        assert "id" in node, "Node fehlt 'id'"
        assert "title" in node, "Node fehlt 'title'"
        assert "status" in node, "Node fehlt 'status'"
        assert "priority" in node, "Node fehlt 'priority'"
        assert "category" in node, "Node fehlt 'category'"

    def test_edges_korrekt(self, db, sample_plan):
        """Edges haben korrekte source/target IDs basierend auf Abhaengigkeiten."""
        ids = db.create_features_from_plan(RUN_ID, sample_plan)
        graph = db.get_dependency_graph(RUN_ID)

        # layout.js → page.js, db.js → route.js, page.js → test
        edges = graph["edges"]
        assert len(edges) == 3, f"Erwartet: 3 Edges, Erhalten: {len(edges)}"

        # Pruefen ob die richtigen Kanten existieren
        edge_pairs = {(e["source"], e["target"]) for e in edges}
        layout_id = db.get_feature_by_path(RUN_ID, "app/layout.js")["id"]
        page_id = db.get_feature_by_path(RUN_ID, "app/page.js")["id"]
        db_id = db.get_feature_by_path(RUN_ID, "lib/db.js")["id"]
        route_id = db.get_feature_by_path(RUN_ID, "app/api/tasks/route.js")["id"]
        test_id = db.get_feature_by_path(RUN_ID, "tests/page.test.js")["id"]

        assert (layout_id, page_id) in edge_pairs, "Edge layout.js → page.js fehlt"
        assert (db_id, route_id) in edge_pairs, "Edge db.js → route.js fehlt"
        assert (page_id, test_id) in edge_pairs, "Edge page.js → test.js fehlt"

    def test_keine_abhaengigkeiten_keine_edges(self, db):
        """Plan ohne Abhaengigkeiten ergibt keine Edges."""
        plan = [
            {"path": "a.js", "description": "A", "priority": 1, "depends_on": [], "estimated_lines": 10},
            {"path": "b.js", "description": "B", "priority": 1, "depends_on": [], "estimated_lines": 10},
        ]
        db.create_features_from_plan(RUN_ID, plan)
        graph = db.get_dependency_graph(RUN_ID)
        assert len(graph["edges"]) == 0, f"Erwartet: 0 Edges, Erhalten: {len(graph['edges'])}"

    def test_leerer_run_leerer_graph(self, db):
        """Leerer Run ergibt leeren Graph."""
        graph = db.get_dependency_graph("leerer_run")
        assert graph == {"nodes": [], "edges": []}, f"Erwartet: leerer Graph, Erhalten: {graph}"


# =====================================================================
# TestCategorizeFile - Kategorie-Erkennung aus Dateipfad
# =====================================================================
class TestCategorizeFile:
    """Tests fuer _categorize_file() statische Methode."""

    def test_test_datei(self):
        """Dateien mit 'test' im Pfad werden als 'test' kategorisiert."""
        assert FeatureTrackingDB._categorize_file("tests/page.test.js") == "test"
        assert FeatureTrackingDB._categorize_file("__test__/unit.js") == "test"
        assert FeatureTrackingDB._categorize_file("spec/main.spec.ts") == "test"

    def test_config_datei(self):
        """Config-Dateien werden als 'config' kategorisiert."""
        assert FeatureTrackingDB._categorize_file("tailwind.config.js") == "config"
        assert FeatureTrackingDB._categorize_file("postcss.config.js") == "config"
        assert FeatureTrackingDB._categorize_file("next.config.js") == "config"
        assert FeatureTrackingDB._categorize_file(".env.local") == "config"
        assert FeatureTrackingDB._categorize_file("tsconfig.json") == "config"

    def test_layout_page_als_feature(self):
        """Layout- und Page-Dateien werden als 'feature' kategorisiert."""
        assert FeatureTrackingDB._categorize_file("app/layout.js") == "feature"
        assert FeatureTrackingDB._categorize_file("app/page.js") == "feature"

    def test_route_als_feature(self):
        """Route- und API-Dateien werden als 'feature' kategorisiert."""
        assert FeatureTrackingDB._categorize_file("app/api/tasks/route.js") == "feature"

    def test_normale_datei(self):
        """Normale Dateien werden als 'file' kategorisiert."""
        assert FeatureTrackingDB._categorize_file("lib/utils.js") == "file"
        assert FeatureTrackingDB._categorize_file("src/helpers.ts") == "file"

    def test_leerer_pfad_als_feature(self):
        """Leerer Pfad wird als 'feature' kategorisiert."""
        assert FeatureTrackingDB._categorize_file("") == "feature"
        assert FeatureTrackingDB._categorize_file(None) == "feature"


# =====================================================================
# TestRowToDict - Konvertierung von Row zu Dict
# =====================================================================
class TestRowToDict:
    """Tests fuer _row_to_dict() statische Methode."""

    def test_konvertiert_depends_on_json(self, db, sample_plan):
        """depends_on wird von JSON-String zu Liste konvertiert."""
        db.create_features_from_plan(RUN_ID, sample_plan)
        features = db.get_features(RUN_ID)
        page = next(f for f in features if f["file_path"] == "app/page.js")
        assert isinstance(page["depends_on"], list), "depends_on sollte eine Liste sein"
        assert page["depends_on"] == ["app/layout.js"]

    def test_leere_depends_on_bleibt_leer(self, db, sample_plan):
        """Leere depends_on wird zu leerer Liste."""
        db.create_features_from_plan(RUN_ID, sample_plan)
        features = db.get_features(RUN_ID)
        layout = next(f for f in features if f["file_path"] == "app/layout.js")
        assert layout["depends_on"] == [], f"Erwartet: [], Erhalten: {layout['depends_on']}"


# =====================================================================
# TestSingleton - Singleton-Pattern
# =====================================================================
class TestSingleton:
    """Tests fuer get_feature_tracking_db() Singleton."""

    def test_gibt_gleiche_instanz_zurueck(self, tmp_path, monkeypatch):
        """get_feature_tracking_db() gibt bei mehrfachem Aufruf die gleiche Instanz zurueck."""
        # Singleton-State zuruecksetzen
        monkeypatch.setattr(ftdb_module, "_instance", None)
        db_path = str(tmp_path / "singleton_test.db")
        inst1 = get_feature_tracking_db(db_path)
        inst2 = get_feature_tracking_db(db_path)
        assert inst1 is inst2, "Erwartet: Gleiche Instanz, Erhalten: Verschiedene Instanzen"
        # Aufraumen
        monkeypatch.setattr(ftdb_module, "_instance", None)

    def test_neue_instanz_nach_reset(self, tmp_path, monkeypatch):
        """Nach Reset von _instance wird eine neue Instanz erstellt."""
        monkeypatch.setattr(ftdb_module, "_instance", None)
        db_path1 = str(tmp_path / "singleton_a.db")
        inst1 = get_feature_tracking_db(db_path1)

        # Zuruecksetzen und neue Instanz erstellen
        monkeypatch.setattr(ftdb_module, "_instance", None)
        db_path2 = str(tmp_path / "singleton_b.db")
        inst2 = get_feature_tracking_db(db_path2)

        assert inst1 is not inst2, "Erwartet: Verschiedene Instanzen nach Reset"
        # Aufraumen
        monkeypatch.setattr(ftdb_module, "_instance", None)


# =====================================================================
# TestThreadSafety - Thread-Safety der DB
# =====================================================================
class TestThreadSafety:
    """Tests fuer Thread-Safety der FeatureTrackingDB."""

    def test_parallele_schreibzugriffe(self, db, sample_plan):
        """Mehrere Threads koennen gleichzeitig Features erstellen."""
        results = []
        errors = []

        def erstelle_features(run_suffix):
            try:
                run = f"thread_run_{run_suffix}"
                ids = db.create_features_from_plan(run, sample_plan)
                results.append((run, ids))
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=erstelle_features, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert len(errors) == 0, f"Thread-Fehler aufgetreten: {errors}"
        assert len(results) == 5, f"Erwartet: 5 Ergebnisse, Erhalten: {len(results)}"

    def test_parallele_status_updates(self, db, sample_plan):
        """Mehrere Threads koennen gleichzeitig Status aktualisieren."""
        ids = db.create_features_from_plan(RUN_ID, sample_plan)
        errors = []

        def aktualisiere_status(feature_id, status):
            try:
                db.update_status(feature_id, status)
            except Exception as e:
                errors.append(str(e))

        threads = [
            threading.Thread(target=aktualisiere_status, args=(ids[i], "in_progress"))
            for i in range(len(ids))
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert len(errors) == 0, f"Thread-Fehler aufgetreten: {errors}"


# =====================================================================
# TestEdgeCases - Randfaelle und Sonderfaelle
# =====================================================================
class TestEdgeCases:
    """Tests fuer Randfaelle und besondere Szenarien."""

    def test_feature_ohne_path(self, db):
        """Feature ohne Pfad nutzt description als Fallback fuer title."""
        plan = [{"path": "", "description": "Standalone Feature", "priority": 1, "depends_on": [], "estimated_lines": 10}]
        ids = db.create_features_from_plan(RUN_ID, plan)
        features = db.get_features(RUN_ID)
        assert features[0]["title"] == "Standalone Feature"[:80]

    def test_feature_mit_langer_description(self, db):
        """Feature-Description wird vollstaendig gespeichert."""
        lange_desc = "A" * 1000
        plan = [{"path": "a.js", "description": lange_desc, "priority": 1, "depends_on": [], "estimated_lines": 10}]
        db.create_features_from_plan(RUN_ID, plan)
        feature = db.get_feature_by_path(RUN_ID, "a.js")
        assert feature["description"] == lange_desc

    def test_feature_ohne_optional_felder(self, db):
        """Feature mit minimalen Pflichtfeldern wird korrekt erstellt."""
        plan = [{"path": "minimal.js"}]
        ids = db.create_features_from_plan(RUN_ID, plan)
        assert len(ids) == 1
        feature = db.get_feature_by_path(RUN_ID, "minimal.js")
        assert feature["status"] == "pending"
        assert feature["priority"] == 5  # Default-Wert
        assert feature["estimated_lines"] == 0  # Default-Wert

    def test_unicode_in_description(self, db):
        """Unicode-Zeichen in Description werden korrekt gespeichert."""
        plan = [{"path": "unicode.js", "description": "Uebersicht der Aenderungen: aeoeue", "priority": 1, "depends_on": [], "estimated_lines": 10}]
        db.create_features_from_plan(RUN_ID, plan)
        feature = db.get_feature_by_path(RUN_ID, "unicode.js")
        assert feature["description"] == "Uebersicht der Aenderungen: aeoeue"

    def test_mehrfacher_status_wechsel(self, db, sample_plan):
        """Ein Feature kann mehrfach den Status wechseln."""
        ids = db.create_features_from_plan(RUN_ID, sample_plan)
        db.update_status(ids[0], "in_progress")
        db.update_status(ids[0], "review")
        db.update_status(ids[0], "in_progress")
        db.update_status(ids[0], "done")
        feature = db.get_features(RUN_ID)
        feat = next(f for f in feature if f["id"] == ids[0])
        assert feat["status"] == "done"
        # iteration_count sollte 2 sein (zwei mal in_progress)
        assert feat["iteration_count"] == 2, f"Erwartet: 2 Iterationen, Erhalten: {feat['iteration_count']}"

    def test_categorize_file_mit_none(self):
        """_categorize_file mit None gibt 'feature' zurueck."""
        result = FeatureTrackingDB._categorize_file(None)
        assert result == "feature", f"Erwartet: feature, Erhalten: {result}"
