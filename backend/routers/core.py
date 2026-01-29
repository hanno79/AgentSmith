# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 29.01.2026
Version: 1.0
Beschreibung: Core-API Endpunkte (Run, Status, WebSocket, Reset, Agents).
"""
# ÄNDERUNG 29.01.2026: Core-Endpunkte in eigenes Router-Modul verschoben

import asyncio
import json
from datetime import datetime
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, BackgroundTasks, HTTPException, Request
from pydantic import BaseModel
from ..app_state import manager, ws_manager, limiter, WS_RECEIVE_TIMEOUT
from ..api_logging import log_event

router = APIRouter()


class TaskRequest(BaseModel):
    goal: str


@router.post("/run")
@limiter.limit("10/minute")
async def run_agent_task(request: Request, task_request: TaskRequest, background_tasks: BackgroundTasks):
    print(f"Received /run request for goal: {task_request.goal}")
    loop = asyncio.get_running_loop()

    try:
        def ui_callback(agent: str, event: str, message: str):
            payload = {
                "agent": agent,
                "event": event,
                "message": message,
                "timestamp": str(datetime.now())
            }
            print(f"Log Update from {agent}: {event}")
            asyncio.run_coroutine_threadsafe(ws_manager.broadcast(json.dumps(payload, ensure_ascii=False)), loop)

        manager.on_log = ui_callback
        background_tasks.add_task(manager.run_task, task_request.goal)
        print("Task added to background.")
        return {"status": "started", "goal": task_request.goal}
    except Exception as e:
        import traceback
        print(f"ERROR in /run: {e}")
        print(traceback.format_exc())
        return {"status": "error", "message": str(e)}


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket-Endpunkt mit Ping-Pong Keep-Alive, Timeout und Thread-Safety.
    ÄNDERUNG 29.01.2026: Timeout verhindert Zombie-Connections.
    """
    await ws_manager.connect(websocket)
    try:
        while True:
            try:
                data = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=WS_RECEIVE_TIMEOUT
                )
            except asyncio.TimeoutError:
                print(f"[WebSocket] Timeout - keine Nachricht seit {WS_RECEIVE_TIMEOUT}s")
                break

            try:
                msg = json.loads(data)
                if msg.get("type") == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        pass
    finally:
        await ws_manager.disconnect(websocket)


@router.get("/status")
def get_status():
    return {
        "project_path": manager.project_path,
        "is_first_run": manager.is_first_run,
        "tech_blueprint": manager.tech_blueprint
    }


@router.post("/reset")
@limiter.limit("60/minute")
async def reset_project(request: Request):
    """
    Setzt das aktuelle Projekt komplett zurück.
    Ermöglicht einen Neustart ohne Server-Neustart.
    """
    try:
        manager.project_path = None
        manager.output_path = None
        manager.tech_blueprint = {}
        manager.database_schema = "Kein Datenbank-Schema."
        manager.design_concept = "Kein Design-Konzept."
        manager.current_code = ""
        manager.is_first_run = True
        manager.security_vulnerabilities = []
        manager.force_security_fix = False

        if hasattr(manager, 'office_manager') and manager.office_manager:
            try:
                manager.office_manager.reset_all_workers()
            except Exception as e:
                log_event("API", "Warning", f"Worker-Reset fehlgeschlagen: {e}")

        await ws_manager.broadcast(json.dumps({
            "type": "system",
            "event": "Reset",
            "agent": "System",
            "message": "Projekt wurde zurückgesetzt. Bereit für neuen Task."
        }))

        log_event("API", "Reset", "Projekt wurde vollständig zurückgesetzt")
        return {"status": "success", "message": "Projekt zurückgesetzt"}

    except Exception as e:
        log_event("API", "Error", f"Reset fehlgeschlagen: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/agents")
def get_agents():
    """Gibt eine Liste aller verfügbaren Agenten zurück."""
    mode = manager.config.get("mode", "test")
    models = manager.config.get("models", {}).get(mode, {})

    agents = []
    agent_info = {
        "meta_orchestrator": {"name": "Meta Orchestrator", "description": "Analysiert Prompts und erstellt Ausführungspläne"},
        "orchestrator": {"name": "Orchestrator", "description": "Koordiniert die Agenten und erstellt Dokumentation"},
        "coder": {"name": "Coder", "description": "Generiert Production-Ready Code"},
        "reviewer": {"name": "Reviewer", "description": "Validiert Code-Qualität und Regel-Compliance"},
        "designer": {"name": "Designer", "description": "Erstellt UI/UX Konzepte und Design-Spezifikationen"},
        "tester": {"name": "Tester", "description": "Führt UI-Tests mit Playwright durch"},
        "researcher": {"name": "Researcher", "description": "Web-Recherche für technische Details"},
        "database_designer": {"name": "Database Designer", "description": "Erstellt normalisierte Datenbank-Schemas"},
        "techstack_architect": {"name": "TechStack Architect", "description": "Entscheidet über den optimalen Tech-Stack"},
        "security": {"name": "Security Agent", "description": "Prüft Code auf Sicherheitslücken (OWASP Top 10)"}
    }

    for role, model_config in models.items():
        info = agent_info.get(role, {"name": role, "description": ""})
        if isinstance(model_config, dict):
            model = model_config.get("primary", str(model_config))
        else:
            model = model_config
        agents.append({
            "role": role,
            "name": info["name"],
            "description": info["description"],
            "model": model
        })

    return {"agents": agents, "mode": mode}
