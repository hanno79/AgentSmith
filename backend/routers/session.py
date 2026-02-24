# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 29.01.2026
Version: 1.0
Beschreibung: Session-Management Endpunkte.
"""
# ÄNDERUNG 29.01.2026: Session-Endpunkte in eigenes Router-Modul verschoben

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from ..library_manager import get_library_manager
from ..session_utils import get_session_manager_instance

router = APIRouter()


@router.get("/session/current")
def get_current_session():
    """
    Gibt den aktuellen Session-Status zurueck.
    Wird vom Frontend nach Refresh/Reconnect aufgerufen.

    Returns:
        Kompletter Session-State mit goal, status, logs, agent_data
    """
    session_mgr = get_session_manager_instance()
    if not session_mgr:
        return {
            "session": {
                "project_id": None,
                "goal": "",
                "status": "Idle",
                "active_agents": {},
                "started_at": None,
                "last_update": None
            },
            "agent_data": {},
            "recent_logs": [],
            "is_active": False
        }

    return session_mgr.get_current_state()


@router.get("/session/logs")
def get_session_logs(limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0)):
    """
    Gibt die letzten N Logs zurueck.

    Args:
        limit: Maximale Anzahl Logs (1-500)
        offset: Start-Offset

    Returns:
        Liste von Log-Eintraegen
    """
    session_mgr = get_session_manager_instance()
    if not session_mgr:
        return {"logs": [], "total": 0}

    # ÄNDERUNG 29.01.2026: Atomare Logs + Total aus SessionManager
    logs, total = session_mgr.get_logs(limit=limit, offset=offset)
    return {"logs": logs, "total": total}


class RestoreSessionRequest(BaseModel):
    project_id: str


@router.post("/session/restore")
def restore_session(request: RestoreSessionRequest):
    """
    Stellt eine Session aus der Library wieder her.

    Args:
        project_id: ID des Projekts aus der Library

    Returns:
        Wiederhergestellte Session-Info
    """
    session_mgr = get_session_manager_instance()
    if not session_mgr:
        raise HTTPException(status_code=503, detail="Session Manager nicht verfuegbar")

    library_mgr = get_library_manager()
    project_data = library_mgr.get_project(request.project_id)

    if not project_data:
        raise HTTPException(status_code=404, detail=f"Projekt {request.project_id} nicht gefunden")

    restored = session_mgr.restore_from_library(project_data)
    return {"status": "ok", "session": restored}


@router.post("/session/reset")
async def reset_session():
    """
    Setzt die aktuelle Session zurueck.
    Nuetzlich wenn Frontend einen sauberen Zustand braucht.

    AENDERUNG 22.02.2026: Fix 68d — Stop laufenden Run + WebSocket-Broadcast
    ROOT-CAUSE-FIX:
    Symptom: Button bleibt nach Reset ausgegraut (Frontend weiss nicht dass Run gestoppt)
    Ursache: reset() loeschte nur das Dict, Background-Task lief weiter; kein WS-Event
    Loesung: Stop-Flag + WebSocket "Stopped" Event damit Frontend Button freischaltet

    Returns:
        Bestaetigung
    """
    import json
    from datetime import datetime
    from ..app_state import manager as orch_manager, ws_manager

    # 1. Stop-Flag setzen (beendet DevLoop-Iteration kooperativ)
    if hasattr(orch_manager, 'stop'):
        orch_manager.stop()

    # 2. Session-Dict zuruecksetzen
    session_mgr = get_session_manager_instance()
    if session_mgr:
        session_mgr.reset()

    # 3. Frontend ueber Stop informieren → Button wird freigegeben
    payload = json.dumps({
        "agent": "System",
        "event": "Stopped",
        "message": "Run wurde durch Reset gestoppt",
        "timestamp": str(datetime.now())
    }, ensure_ascii=False)
    await ws_manager.broadcast(payload)

    return {"status": "ok", "message": "Session zurueckgesetzt"}


@router.get("/session/status")
def get_session_status():
    """
    Gibt nur den Status-Teil der Session zurueck (leichtgewichtig).

    Returns:
        Status-Info
    """
    session_mgr = get_session_manager_instance()
    if not session_mgr:
        return {"status": "Idle", "is_active": False}

    return {
        "status": session_mgr.current_session.get("status", "Idle"),
        "is_active": session_mgr.is_active(),
        "goal": session_mgr.current_session.get("goal", ""),
        "iteration": session_mgr.current_session.get("iteration", 0),
        "project_id": session_mgr.current_session.get("project_id")
    }
