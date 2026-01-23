import asyncio
from datetime import datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from .orchestration_manager import OrchestrationManager
import json

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

manager = OrchestrationManager()

# Speicher für aktive WebSocket-Verbindungen
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)

ws_manager = ConnectionManager()

class TaskRequest(BaseModel):
    goal: str

@app.post("/run")
async def run_agent_task(request: TaskRequest, background_tasks: BackgroundTasks):
    print(f"Received /run request for goal: {request.goal}")
    # Haupt-Event-Loop einfangen
    loop = asyncio.get_running_loop()
    
    try:
        # Callback für Log-Updates via WebSocket
        def ui_callback(agent: str, event: str, message: str):
            payload = {
                "agent": agent,
                "event": event,
                "message": message,
                "timestamp": str(datetime.now())
            }
            print(f"Log Update from {agent}: {event}")
            # Thread-sicherer Broadcast über den Haupt-Loop
            asyncio.run_coroutine_threadsafe(ws_manager.broadcast(json.dumps(payload)), loop)

        manager.on_log = ui_callback
        background_tasks.add_task(manager.run_task, request.goal)
        print("Task added to background.")
        return {"status": "started", "goal": request.goal}
    except Exception as e:
        import traceback
        print(f"ERROR in /run: {e}")
        print(traceback.format_exc())
        return {"status": "error", "message": str(e)}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)

@app.get("/status")
def get_status():
    return {
        "project_path": manager.project_path,
        "is_first_run": manager.is_first_run,
        "tech_blueprint": manager.tech_blueprint
    }
