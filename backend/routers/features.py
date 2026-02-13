# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 13.02.2026
Version: 1.0
Beschreibung: API-Endpoints fuer Feature-Tracking und Kanban-Board.
              Liest aus der SQLite-DB (feature_tracking_db.py).
"""

import logging
from typing import Optional
from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/features", tags=["Feature Tracking"])


class PriorityUpdate(BaseModel):
    """Request-Body fuer Prioritaets-Aenderung."""
    priority: int


class StatusUpdate(BaseModel):
    """Request-Body fuer Status-Aenderung (Drag-and-Drop)."""
    status: str


@router.get("/{run_id}")
async def get_features(
    run_id: str,
    status: Optional[str] = Query(None, description="Filter nach Status (pending, in_progress, review, done, failed)")
):
    """Alle Features eines Runs (optional gefiltert nach Status)."""
    try:
        from backend.feature_tracking_db import get_feature_tracking_db
        db = get_feature_tracking_db()
        features = db.get_features(run_id, status=status)

        # Gruppiere nach Status fuer Kanban-Spalten
        grouped = {"pending": [], "in_progress": [], "review": [], "done": [], "failed": []}
        for f in features:
            s = f.get("status", "pending")
            if s in grouped:
                grouped[s].append(f)

        return {"status": "ok", "count": len(features), "features": features, "grouped": grouped}
    except Exception as e:
        logger.warning("GET /features/%s Fehler: %s", run_id, e)
        return {"status": "error", "message": str(e), "features": [], "grouped": {}}


@router.get("/{run_id}/stats")
async def get_feature_stats(run_id: str):
    """Zaehler pro Status fuer einen Run."""
    try:
        from backend.feature_tracking_db import get_feature_tracking_db
        db = get_feature_tracking_db()
        stats = db.get_stats(run_id)
        return {"status": "ok", "stats": stats}
    except Exception as e:
        logger.warning("GET /features/%s/stats Fehler: %s", run_id, e)
        return {"status": "error", "message": str(e), "stats": {}}


@router.get("/{run_id}/graph")
async def get_dependency_graph(run_id: str):
    """Dependency-Graph Daten (Nodes + Edges) fuer Visualisierung."""
    try:
        from backend.feature_tracking_db import get_feature_tracking_db
        db = get_feature_tracking_db()
        graph = db.get_dependency_graph(run_id)
        return {"status": "ok", "graph": graph}
    except Exception as e:
        logger.warning("GET /features/%s/graph Fehler: %s", run_id, e)
        return {"status": "error", "message": str(e), "graph": {"nodes": [], "edges": []}}


@router.put("/{feature_id}/priority")
async def update_priority(feature_id: int, body: PriorityUpdate):
    """Prioritaet eines Features aendern (fuer Drag-and-Drop Reorder)."""
    try:
        from backend.feature_tracking_db import get_feature_tracking_db
        db = get_feature_tracking_db()
        conn = db._get_conn()
        conn.execute(
            "UPDATE features SET priority = ?, updated_at = datetime('now') WHERE id = ?",
            (body.priority, feature_id)
        )
        conn.commit()
        return {"status": "ok", "feature_id": feature_id, "priority": body.priority}
    except Exception as e:
        logger.warning("PUT /features/%s/priority Fehler: %s", feature_id, e)
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{feature_id}/status")
async def update_feature_status(feature_id: int, body: StatusUpdate):
    """Status eines Features aendern (fuer Drag-and-Drop zwischen Spalten)."""
    valid_statuses = {"pending", "in_progress", "review", "done", "failed"}
    if body.status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Ungueltiger Status: {body.status}")
    try:
        from backend.feature_tracking_db import get_feature_tracking_db
        db = get_feature_tracking_db()
        db.update_status(feature_id, body.status)
        return {"status": "ok", "feature_id": feature_id, "new_status": body.status}
    except Exception as e:
        logger.warning("PUT /features/%s/status Fehler: %s", feature_id, e)
        raise HTTPException(status_code=500, detail=str(e))
