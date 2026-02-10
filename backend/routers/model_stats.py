# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 09.02.2026
Version: 1.0
Beschreibung: API-Endpoints fuer Modell-Statistiken und Run-Uebersicht.
              Liest aus der SQLite-DB (model_stats_db.py).
"""

import logging
from typing import Optional
from fastapi import APIRouter, Query

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/stats", tags=["Model Stats"])


@router.get("/models")
async def get_model_stats(
    agent: Optional[str] = Query(None, description="Filter nach Agent-Rolle"),
    days: int = Query(30, description="Zeitraum in Tagen")
):
    """Aggregierte Statistiken pro Modell (optional gefiltert nach Agent)."""
    try:
        from model_stats_db import get_model_stats_db
        db = get_model_stats_db()
        stats = db.get_model_stats(agent=agent, days=days)
        return {"status": "ok", "count": len(stats), "stats": stats}
    except Exception as e:
        logger.warning("GET /stats/models Fehler: %s", e)
        return {"status": "error", "message": str(e), "stats": []}


@router.get("/runs")
async def get_runs(
    run_id: Optional[str] = Query(None, description="Einzelner Run"),
    limit: int = Query(20, description="Max. Anzahl Runs")
):
    """Zusammenfassung aller oder eines einzelnen Runs."""
    try:
        from model_stats_db import get_model_stats_db
        db = get_model_stats_db()
        runs = db.get_run_summary(run_id=run_id, limit=limit)
        return {"status": "ok", "count": len(runs), "runs": runs}
    except Exception as e:
        logger.warning("GET /stats/runs Fehler: %s", e)
        return {"status": "error", "message": str(e), "runs": []}


@router.get("/best-models")
async def get_best_models(
    days: int = Query(30, description="Zeitraum in Tagen")
):
    """Bestes Modell pro Agent-Rolle (gewichteter Score)."""
    try:
        from model_stats_db import get_model_stats_db
        db = get_model_stats_db()
        best = db.get_best_models_per_role(days=days)
        return {"status": "ok", "recommendations": best}
    except Exception as e:
        logger.warning("GET /stats/best-models Fehler: %s", e)
        return {"status": "error", "message": str(e), "recommendations": {}}
