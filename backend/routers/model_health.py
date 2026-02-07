# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 06.02.2026
Version: 1.0
Beschreibung: Health-Check Endpoints fuer Modell-Verfuegbarkeit.
              Aus config.py ausgelagert (Regel 1: max 500 Zeilen).
"""
# AENDERUNG 06.02.2026: Aus config.py extrahiert um Zeilengrenze einzuhalten

import os
import sys
import logging
from fastapi import APIRouter, HTTPException

from ..app_state import manager

# Projektroot fuer model_router Import
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, _project_root)

from model_router import get_model_router

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/models/health-check")
async def run_health_check():
    """
    Fuehrt Health-Check fuer alle Primary-Modelle durch.
    Markiert unavailable Modelle automatisch.
    """
    try:
        router_instance = get_model_router(manager.config)
        results = await router_instance.health_check_all_primary_models()
        return {
            "status": "ok",
            "results": results,
            "unavailable_count": len(router_instance.permanently_unavailable)
        }
    except Exception as e:
        logger.exception("Health-Check Fehler: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/models/health-check/{model_id:path}")
async def check_single_model(model_id: str):
    """
    Prueft ein einzelnes Modell auf Verfuegbarkeit.

    Args:
        model_id: Modell-ID (z.B. "openrouter/xiaomi/mimo-v2-flash:free")
    """
    try:
        router_instance = get_model_router(manager.config)
        available, reason = await router_instance.check_model_health(model_id)

        # Erweiterte Erkennung fuer permanent unavailable
        permanent_patterns = [
            "not found", "404", "free period ended", "free tier ended",
            "subscription required", "model deprecated", "model discontinued",
            "please migrate to"
        ]
        is_permanent = not available and any(p in reason.lower() for p in permanent_patterns)

        if is_permanent:
            router_instance.mark_permanently_unavailable(model_id, reason)

        return {
            "model": model_id,
            "available": available,
            "reason": reason,
            "is_permanent": is_permanent,
            "marked_unavailable": model_id in router_instance.permanently_unavailable
        }
    except Exception as e:
        logger.exception("Einzelner Health-Check Fehler fuer %s: %s", model_id, e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/models/health-status")
def get_health_status():
    """Gibt den aktuellen Health-Status aller Modelle zurueck."""
    try:
        router_instance = get_model_router(manager.config)
        return router_instance.get_health_status()
    except Exception as e:
        return {"error": str(e), "permanently_unavailable": {}}


@router.post("/models/recheck-unavailable")
async def recheck_unavailable_models():
    """
    Prueft ob zuvor als unavailable markierte Modelle wieder verfuegbar sind.
    """
    try:
        router_instance = get_model_router(manager.config)
        results = await router_instance.recheck_unavailable_models()
        return {
            "status": "ok",
            "rechecked": results,
            "still_unavailable": list(router_instance.permanently_unavailable.keys())
        }
    except Exception as e:
        logger.exception("Recheck-Unavailable Fehler: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/models/reactivate/{model_id:path}")
def reactivate_model(model_id: str):
    """
    Reaktiviert ein als unavailable markiertes Modell manuell.

    Args:
        model_id: Modell-ID zum Reaktivieren
    """
    try:
        router_instance = get_model_router(manager.config)
        success = router_instance.reactivate_model(model_id)
        return {
            "status": "ok" if success else "not_found",
            "model": model_id,
            "reactivated": success
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
