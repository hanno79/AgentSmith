# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 09.02.2026
Version: 1.0
Beschreibung: SQLite-basierte Modell-Statistiken fuer Performance-Tracking.
              Erfasst Latenz, Token-Verbrauch, Kosten und Erfolgsrate pro Modell/Agent.
              Ergaenzt das bestehende JSON-Budget-Tracking um schnelle Abfragen.
"""

import os
import sqlite3
import logging
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

# Singleton-Instance
_instance = None
_instance_lock = threading.Lock()

DB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "budget_data")
DB_PATH = os.path.join(DB_DIR, "model_stats.db")


class ModelStatsDB:
    """
    SQLite-Datenbank fuer Modell-Performance-Statistiken.

    AENDERUNG 09.02.2026: Neues Modul fuer datenbasierte Modell-Auswahl.
    ROOT-CAUSE-FIX:
    Symptom: Keine Daten ueber Modell-Performance (Latenz, Erfolgsrate, Kosten/Token)
    Ursache: Bestehendes JSON-Tracking erfasst nur Tokens+Kosten, keine Latenz/Runs
    Loesung: SQLite-DB mit llm_calls + runs Tabellen fuer schnelle Aggregationen
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
            CREATE TABLE IF NOT EXISTS llm_calls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                run_id TEXT,
                agent TEXT NOT NULL,
                model TEXT NOT NULL,
                prompt_tokens INTEGER DEFAULT 0,
                completion_tokens INTEGER DEFAULT 0,
                total_tokens INTEGER DEFAULT 0,
                cost_usd REAL DEFAULT 0.0,
                latency_ms REAL DEFAULT 0.0,
                success INTEGER DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT UNIQUE NOT NULL,
                goal TEXT,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                total_cost_usd REAL DEFAULT 0.0,
                total_tokens INTEGER DEFAULT 0,
                total_calls INTEGER DEFAULT 0,
                iterations INTEGER DEFAULT 0,
                final_score REAL,
                status TEXT DEFAULT 'running'
            );

            CREATE INDEX IF NOT EXISTS idx_calls_model ON llm_calls(model);
            CREATE INDEX IF NOT EXISTS idx_calls_agent ON llm_calls(agent);
            CREATE INDEX IF NOT EXISTS idx_calls_run ON llm_calls(run_id);
            CREATE INDEX IF NOT EXISTS idx_calls_timestamp ON llm_calls(timestamp);
            CREATE INDEX IF NOT EXISTS idx_runs_status ON runs(status);
        """)
        conn.commit()
        logger.info("ModelStatsDB initialisiert: %s", self.db_path)

    def record_call(self, run_id: str, agent: str, model: str,
                    prompt_tokens: int, completion_tokens: int,
                    cost_usd: float, latency_ms: float, success: bool = True):
        """
        Zeichnet einen einzelnen LLM-API-Call auf.

        Args:
            run_id: Projekt-/Run-ID (z.B. project_20260209_184502)
            agent: Agent-Name (z.B. Coder, Reviewer)
            model: Modell-ID (z.B. deepseek/deepseek-r1-0528)
            prompt_tokens: Anzahl Input-Tokens
            completion_tokens: Anzahl Output-Tokens
            cost_usd: Kosten in USD
            latency_ms: Antwortzeit in Millisekunden
            success: True bei Erfolg, False bei Fehler
        """
        try:
            conn = self._get_conn()
            conn.execute(
                """INSERT INTO llm_calls
                   (timestamp, run_id, agent, model, prompt_tokens, completion_tokens,
                    total_tokens, cost_usd, latency_ms, success)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (datetime.now().isoformat(), run_id, agent, model,
                 prompt_tokens, completion_tokens,
                 prompt_tokens + completion_tokens,
                 cost_usd, latency_ms, 1 if success else 0)
            )
            conn.commit()
        except Exception as e:
            logger.warning("ModelStatsDB.record_call fehlgeschlagen: %s", e)

    def start_run(self, run_id: str, goal: str = ""):
        """Registriert den Start eines neuen Runs."""
        try:
            conn = self._get_conn()
            conn.execute(
                """INSERT OR IGNORE INTO runs (run_id, goal, started_at)
                   VALUES (?, ?, ?)""",
                (run_id, goal[:500] if goal else "", datetime.now().isoformat())
            )
            conn.commit()
            logger.info("ModelStatsDB: Run gestartet: %s", run_id)
        except Exception as e:
            logger.warning("ModelStatsDB.start_run fehlgeschlagen: %s", e)

    def finish_run(self, run_id: str, iterations: int = 0,
                   final_score: float = None, status: str = "success"):
        """
        Markiert einen Run als abgeschlossen und aggregiert Statistiken.

        Args:
            run_id: Projekt-/Run-ID
            iterations: Anzahl DevLoop-Iterationen
            final_score: Endpunktzahl des Quality Gate
            status: success, failed, error
        """
        try:
            conn = self._get_conn()
            # Aggregierte Werte aus llm_calls berechnen
            row = conn.execute(
                """SELECT COALESCE(SUM(cost_usd), 0) as total_cost,
                          COALESCE(SUM(total_tokens), 0) as total_tokens,
                          COUNT(*) as total_calls
                   FROM llm_calls WHERE run_id = ?""",
                (run_id,)
            ).fetchone()

            conn.execute(
                """UPDATE runs SET
                       finished_at = ?,
                       total_cost_usd = ?,
                       total_tokens = ?,
                       total_calls = ?,
                       iterations = ?,
                       final_score = ?,
                       status = ?
                   WHERE run_id = ?""",
                (datetime.now().isoformat(),
                 row["total_cost"] if row else 0.0,
                 row["total_tokens"] if row else 0,
                 row["total_calls"] if row else 0,
                 iterations, final_score, status, run_id)
            )
            conn.commit()
            logger.info("ModelStatsDB: Run beendet: %s (Status: %s, Calls: %s)",
                        run_id, status, row["total_calls"] if row else 0)
        except Exception as e:
            logger.warning("ModelStatsDB.finish_run fehlgeschlagen: %s", e)

    def get_model_stats(self, agent: str = None, days: int = 30) -> List[Dict[str, Any]]:
        """
        Aggregierte Statistiken pro Modell (optional gefiltert nach Agent).

        Returns:
            Liste von Dicts mit: model, agent, calls, avg_latency_ms,
            avg_tokens, total_cost, success_rate
        """
        try:
            conn = self._get_conn()
            since = (datetime.now() - timedelta(days=days)).isoformat()
            query = """
                SELECT model, agent,
                       COUNT(*) as calls,
                       ROUND(AVG(latency_ms), 1) as avg_latency_ms,
                       ROUND(AVG(total_tokens), 0) as avg_tokens,
                       ROUND(SUM(cost_usd), 4) as total_cost,
                       ROUND(AVG(success) * 100, 1) as success_rate
                FROM llm_calls
                WHERE timestamp > ?
            """
            params = [since]
            if agent:
                query += " AND agent = ?"
                params.append(agent)
            query += " GROUP BY model, agent ORDER BY calls DESC"

            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]
        except Exception as e:
            logger.warning("ModelStatsDB.get_model_stats fehlgeschlagen: %s", e)
            return []

    def get_run_summary(self, run_id: str = None, limit: int = 20) -> List[Dict[str, Any]]:
        """Zusammenfassung eines oder aller Runs."""
        try:
            conn = self._get_conn()
            if run_id:
                rows = conn.execute(
                    "SELECT * FROM runs WHERE run_id = ?", (run_id,)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM runs ORDER BY started_at DESC LIMIT ?", (limit,)
                ).fetchall()
            return [dict(r) for r in rows]
        except Exception as e:
            logger.warning("ModelStatsDB.get_run_summary fehlgeschlagen: %s", e)
            return []

    def get_best_models_per_role(self, days: int = 30) -> Dict[str, Dict[str, Any]]:
        """
        Ermittelt das beste Modell pro Agent-Rolle basierend auf:
        - Erfolgsrate (Gewicht: 40%)
        - Latenz (Gewicht: 30%)
        - Kosten pro Token (Gewicht: 30%)

        Returns:
            Dict {agent: {model, score, calls, avg_latency_ms, success_rate, cost_per_1k_tokens}}
        """
        try:
            conn = self._get_conn()
            since = (datetime.now() - timedelta(days=days)).isoformat()
            rows = conn.execute("""
                SELECT agent, model,
                       COUNT(*) as calls,
                       AVG(latency_ms) as avg_latency_ms,
                       AVG(success) * 100 as success_rate,
                       CASE WHEN SUM(total_tokens) > 0
                            THEN SUM(cost_usd) / SUM(total_tokens) * 1000
                            ELSE 0
                       END as cost_per_1k_tokens,
                       AVG(total_tokens) as avg_tokens
                FROM llm_calls
                WHERE timestamp > ? AND calls > 0
                GROUP BY agent, model
                HAVING COUNT(*) >= 3
                ORDER BY agent, success_rate DESC, avg_latency_ms ASC
            """, (since,)).fetchall()

            # Pro Agent das beste Modell waehlen
            best = {}
            for row in rows:
                row_dict = dict(row)
                agent = row_dict["agent"]
                if agent in best:
                    continue  # Erstes Ergebnis pro Agent ist das beste (sortiert)

                # Score berechnen (0-100)
                sr = row_dict["success_rate"] or 0
                lat = row_dict["avg_latency_ms"] or 0
                cpt = row_dict["cost_per_1k_tokens"] or 0

                # Normalisierung: niedrigere Latenz/Kosten = besser
                lat_score = max(0, 100 - (lat / 100))  # 0ms=100, 10000ms=0
                cost_score = max(0, 100 - (cpt * 100))  # 0$/1k=100, 1$/1k=0

                score = round(sr * 0.4 + lat_score * 0.3 + cost_score * 0.3, 1)

                best[agent] = {
                    "model": row_dict["model"],
                    "score": score,
                    "calls": row_dict["calls"],
                    "avg_latency_ms": round(lat, 1),
                    "success_rate": round(sr, 1),
                    "cost_per_1k_tokens": round(cpt, 6),
                    "avg_tokens": round(row_dict["avg_tokens"] or 0),
                }

            return best
        except Exception as e:
            logger.warning("ModelStatsDB.get_best_models_per_role fehlgeschlagen: %s", e)
            return {}


def get_model_stats_db(db_path: str = None) -> ModelStatsDB:
    """Singleton-Getter fuer die ModelStatsDB Instanz."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = ModelStatsDB(db_path)
    return _instance
