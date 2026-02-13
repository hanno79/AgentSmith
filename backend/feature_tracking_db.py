# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 13.02.2026
Version: 1.0
Beschreibung: SQLite-basierte Feature-Tracking-Datenbank fuer Kanban-Board und Dependency-Graph.
              Erfasst Status, Abhaengigkeiten und Fortschritt aller geplanten Features/Dateien.
              Folgt dem gleichen Pattern wie model_stats_db.py (WAL-Mode, Thread-local, Singleton).

              AENDERUNG 13.02.2026: Neues Modul fuer Feature-Tracking.
              ROOT-CAUSE-FIX:
              Symptom: Kein Ueberblick welche Features geplant, in Arbeit oder fertig sind
              Ursache: Planner-Output wird nur als transientes JSON weitergereicht, nicht persistent gespeichert
              Loesung: SQLite-DB mit features-Tabelle + Scheduling-Score fuer Dependency-basierte Reihenfolge
"""

import os
import json
import sqlite3
import logging
import threading
from datetime import datetime
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

# Singleton-Instance
_instance = None
_instance_lock = threading.Lock()

DB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "budget_data")
DB_PATH = os.path.join(DB_DIR, "feature_tracking.db")


class FeatureTrackingDB:
    """
    SQLite-Datenbank fuer Feature/Datei-Tracking mit Dependency-Graph.

    Status-Flow: pending → in_progress → review → done
                                       → failed (bei Fehler)
    """

    def __init__(self, db_path: str = None):
        self.db_path = db_path or DB_PATH
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._local = threading.local()
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        """Thread-lokale Connection (SQLite ist nicht thread-safe)."""
        if not hasattr(self._local, 'conn') or self._local.conn is None:
            self._local.conn = sqlite3.connect(self.db_path, timeout=10)
            self._local.conn.execute("PRAGMA journal_mode=WAL")
            self._local.conn.execute("PRAGMA busy_timeout=5000")
            self._local.conn.row_factory = sqlite3.Row
        return self._local.conn

    def _init_db(self):
        """Erstellt Schema falls nicht vorhanden."""
        conn = self._get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS features (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                file_path TEXT,
                category TEXT DEFAULT 'file',
                status TEXT DEFAULT 'pending',
                priority INTEGER DEFAULT 5,
                depends_on TEXT DEFAULT '[]',
                assigned_agent TEXT,
                estimated_lines INTEGER DEFAULT 0,
                actual_lines INTEGER DEFAULT 0,
                error_message TEXT,
                iteration_count INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                completed_at TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_features_run_id ON features(run_id);
            CREATE INDEX IF NOT EXISTS idx_features_status ON features(status);
        """)
        conn.commit()
        logger.info("FeatureTrackingDB initialisiert: %s", self.db_path)

    # ------------------------------------------------------------------
    # Schreib-Operationen
    # ------------------------------------------------------------------

    def create_features_from_plan(self, run_id: str, plan_files: List[Dict]) -> List[int]:
        """
        Erstellt Features aus dem Planner-Output.

        Args:
            run_id: Projekt-Run-ID (z.B. project_20260213_120000)
            plan_files: Liste aus parse_planner_output()["files"]
                        Jedes Dict hat: path, description, depends_on[], priority, estimated_lines

        Returns:
            Liste der erstellten Feature-IDs
        """
        try:
            conn = self._get_conn()
            now = datetime.now().isoformat()
            feature_ids = []

            for f in plan_files:
                path = f.get("path", "")
                title = os.path.basename(path) if path else f.get("description", "Unbekannt")[:80]
                # Kategorie aus Pfad ableiten
                category = self._categorize_file(path)

                cursor = conn.execute(
                    """INSERT INTO features
                       (run_id, title, description, file_path, category, status, priority,
                        depends_on, estimated_lines, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, 'pending', ?, ?, ?, ?, ?)""",
                    (run_id, title,
                     f.get("description", ""),
                     path, category,
                     f.get("priority", 5),
                     json.dumps(f.get("depends_on", []), ensure_ascii=False),
                     f.get("estimated_lines", 0),
                     now, now)
                )
                feature_ids.append(cursor.lastrowid)

            conn.commit()
            logger.info("FeatureTrackingDB: %d Features erstellt fuer Run %s", len(feature_ids), run_id)
            return feature_ids
        except Exception as e:
            logger.warning("FeatureTrackingDB.create_features_from_plan fehlgeschlagen: %s", e)
            return []

    def update_status(self, feature_id: int, status: str,
                      agent: str = None, error: str = None):
        """Aendert den Status eines Features."""
        try:
            conn = self._get_conn()
            now = datetime.now().isoformat()
            updates = ["status = ?", "updated_at = ?"]
            params = [status, now]

            if agent:
                updates.append("assigned_agent = ?")
                params.append(agent)
            if error:
                updates.append("error_message = ?")
                params.append(error[:500])
            if status == "in_progress":
                updates.append("iteration_count = iteration_count + 1")
            if status in ("done", "failed"):
                updates.append("completed_at = ?")
                params.append(now)

            params.append(feature_id)
            conn.execute(
                f"UPDATE features SET {', '.join(updates)} WHERE id = ?",
                params
            )
            conn.commit()
        except Exception as e:
            logger.warning("FeatureTrackingDB.update_status fehlgeschlagen: %s", e)

    def mark_done(self, feature_id: int, actual_lines: int = 0):
        """Markiert ein Feature als erfolgreich abgeschlossen."""
        try:
            conn = self._get_conn()
            now = datetime.now().isoformat()
            conn.execute(
                """UPDATE features SET status = 'done', actual_lines = ?,
                   completed_at = ?, updated_at = ? WHERE id = ?""",
                (actual_lines, now, now, feature_id)
            )
            conn.commit()
        except Exception as e:
            logger.warning("FeatureTrackingDB.mark_done fehlgeschlagen: %s", e)

    def mark_failed(self, feature_id: int, error_message: str):
        """Markiert ein Feature als fehlgeschlagen."""
        self.update_status(feature_id, "failed", error=error_message)

    # ------------------------------------------------------------------
    # Lese-Operationen
    # ------------------------------------------------------------------

    def get_features(self, run_id: str, status: str = None) -> List[Dict[str, Any]]:
        """Alle Features eines Runs (optional gefiltert nach Status)."""
        try:
            conn = self._get_conn()
            query = "SELECT * FROM features WHERE run_id = ?"
            params = [run_id]
            if status:
                query += " AND status = ?"
                params.append(status)
            query += " ORDER BY priority ASC, id ASC"
            rows = conn.execute(query, params).fetchall()
            return [self._row_to_dict(r) for r in rows]
        except Exception as e:
            logger.warning("FeatureTrackingDB.get_features fehlgeschlagen: %s", e)
            return []

    def get_feature_by_path(self, run_id: str, file_path: str) -> Optional[Dict[str, Any]]:
        """Findet ein Feature anhand des Dateipfads."""
        try:
            conn = self._get_conn()
            row = conn.execute(
                "SELECT * FROM features WHERE run_id = ? AND file_path = ?",
                (run_id, file_path)
            ).fetchone()
            return self._row_to_dict(row) if row else None
        except Exception as e:
            logger.warning("FeatureTrackingDB.get_feature_by_path fehlgeschlagen: %s", e)
            return None

    def get_next_feature(self, run_id: str) -> Optional[Dict[str, Any]]:
        """
        Naechstes Feature nach Scheduling-Score.
        Score = (100 * unblocking_count) + (10 * (10 - priority)) + (1 * id)

        Nur Features deren Abhaengigkeiten alle 'done' sind werden beruecksichtigt.
        """
        try:
            pending = self.get_features(run_id, status="pending")
            if not pending:
                return None

            done_paths = {f["file_path"] for f in self.get_features(run_id, status="done")}
            all_features = self.get_features(run_id)

            best = None
            best_score = -1

            for feat in pending:
                # Pruefe ob alle Abhaengigkeiten erfuellt sind
                deps = json.loads(feat.get("depends_on", "[]")) if isinstance(feat.get("depends_on"), str) else feat.get("depends_on", [])
                if any(d not in done_paths for d in deps):
                    continue  # Blockiert

                # Berechne wie viele andere Features auf dieses warten
                unblocking = sum(
                    1 for other in all_features
                    if other["status"] == "pending" and feat["file_path"] in
                    (json.loads(other.get("depends_on", "[]")) if isinstance(other.get("depends_on"), str) else other.get("depends_on", []))
                )

                priority = feat.get("priority", 5)
                score = (100 * unblocking) + (10 * (10 - priority)) + (1 * feat["id"])
                if score > best_score:
                    best_score = score
                    best = feat

            return best
        except Exception as e:
            logger.warning("FeatureTrackingDB.get_next_feature fehlgeschlagen: %s", e)
            return None

    def get_stats(self, run_id: str) -> Dict[str, int]:
        """Zaehler pro Status fuer einen Run."""
        try:
            conn = self._get_conn()
            rows = conn.execute(
                """SELECT status, COUNT(*) as cnt
                   FROM features WHERE run_id = ?
                   GROUP BY status""",
                (run_id,)
            ).fetchall()

            stats = {"pending": 0, "in_progress": 0, "review": 0, "done": 0, "failed": 0, "total": 0}
            for row in rows:
                stats[row["status"]] = row["cnt"]
                stats["total"] += row["cnt"]

            if stats["total"] > 0:
                stats["percentage"] = round(stats["done"] / stats["total"] * 100, 1)
            else:
                stats["percentage"] = 0.0

            return stats
        except Exception as e:
            logger.warning("FeatureTrackingDB.get_stats fehlgeschlagen: %s", e)
            return {"pending": 0, "in_progress": 0, "review": 0, "done": 0, "failed": 0, "total": 0, "percentage": 0.0}

    def get_dependency_graph(self, run_id: str) -> Dict[str, Any]:
        """Abhaengigkeiten als Graph-Daten (Nodes + Edges) fuer Frontend."""
        try:
            features = self.get_features(run_id)
            nodes = []
            edges = []

            # Mapping file_path → feature_id fuer Edge-Erstellung
            path_to_id = {f["file_path"]: f["id"] for f in features if f.get("file_path")}

            for feat in features:
                nodes.append({
                    "id": feat["id"],
                    "title": feat["title"],
                    "file_path": feat.get("file_path", ""),
                    "status": feat["status"],
                    "priority": feat.get("priority", 5),
                    "category": feat.get("category", "file")
                })

                deps = json.loads(feat.get("depends_on", "[]")) if isinstance(feat.get("depends_on"), str) else feat.get("depends_on", [])
                for dep_path in deps:
                    source_id = path_to_id.get(dep_path)
                    if source_id:
                        edges.append({
                            "source": source_id,
                            "target": feat["id"]
                        })

            return {"nodes": nodes, "edges": edges}
        except Exception as e:
            logger.warning("FeatureTrackingDB.get_dependency_graph fehlgeschlagen: %s", e)
            return {"nodes": [], "edges": []}

    # ------------------------------------------------------------------
    # Hilfsfunktionen
    # ------------------------------------------------------------------

    @staticmethod
    def _categorize_file(path: str) -> str:
        """Leitet Kategorie aus dem Dateipfad ab."""
        if not path:
            return "feature"
        lower = path.lower()
        if any(x in lower for x in ["test", "spec", "__test__"]):
            return "test"
        if any(x in lower for x in ["config", ".env", "tailwind", "postcss", "next.config", "tsconfig"]):
            return "config"
        if any(x in lower for x in ["layout", "page", "route", "api/"]):
            return "feature"
        return "file"

    @staticmethod
    def _row_to_dict(row) -> Dict[str, Any]:
        """Konvertiert sqlite3.Row zu Dict mit JSON-Parsing fuer depends_on."""
        d = dict(row)
        # depends_on von JSON-String zu Liste konvertieren
        if isinstance(d.get("depends_on"), str):
            try:
                d["depends_on"] = json.loads(d["depends_on"])
            except (json.JSONDecodeError, TypeError):
                d["depends_on"] = []
        return d


def get_feature_tracking_db(db_path: str = None) -> FeatureTrackingDB:
    """Singleton-Getter fuer die FeatureTrackingDB Instanz."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = FeatureTrackingDB(db_path)
    return _instance
