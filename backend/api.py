# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 24.01.2026
Version: 1.0
Beschreibung: FastAPI Backend - REST API und WebSocket-Endpunkte für das Multi-Agent System.
"""

import asyncio
import os
import yaml
import sys
from datetime import datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, BackgroundTasks, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from .orchestration_manager import OrchestrationManager
import json
try:
    from ruamel.yaml import YAML
    RUAMEL_AVAILABLE = True
except ImportError:
    RUAMEL_AVAILABLE = False

# Füge Projektroot zum Path hinzu für model_router Import
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _project_root)

from model_router import get_model_router, ModelRouter
from budget_tracker import get_budget_tracker

app = FastAPI(
    title="Agent Smith API",
    description="Backend API für das Multi-Agent System",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

manager = OrchestrationManager()

# ÄNDERUNG 25.01.2026: Konstante für Default max_retries
DEFAULT_MAX_RETRIES = 5

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
            asyncio.run_coroutine_threadsafe(ws_manager.broadcast(json.dumps(payload, ensure_ascii=False)), loop)

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


# =====================================================================
# CONFIG API - Mainframe Hub Endpoints
# =====================================================================

class ModeRequest(BaseModel):
    mode: str

class ModelRequest(BaseModel):
    model: str

class MaxRetriesRequest(BaseModel):
    max_retries: int

# ÄNDERUNG 25.01.2026: Request-Model für Modellwechsel-Einstellung
class MaxModelAttemptsRequest(BaseModel):
    max_model_attempts: int

class ResearchTimeoutRequest(BaseModel):
    research_timeout_minutes: int

@app.get("/config")
def get_config():
    """Gibt die aktuelle Konfiguration zurück."""
    return {
        "mode": manager.config.get("mode", "test"),
        "project_type": manager.config.get("project_type", "webapp"),
        "max_retries": manager.config.get("max_retries", DEFAULT_MAX_RETRIES),
        "research_timeout_minutes": manager.config.get("research_timeout_minutes", 5),
        "include_designer": manager.config.get("include_designer", True),
        "models": manager.config.get("models", {}),
        "available_modes": ["test", "production"]
    }

@app.put("/config/mode")
def set_mode(request: ModeRequest):
    """Wechselt zwischen test und production Modus."""
    if request.mode not in ["test", "production"]:
        raise HTTPException(status_code=400, detail="Invalid mode. Use 'test' or 'production'")
    manager.config["mode"] = request.mode
    _save_config()
    return {"status": "ok", "mode": request.mode}

@app.put("/config/max-retries")
def set_max_retries(request: MaxRetriesRequest):
    """Setzt die maximale Anzahl an Retries (1-100)."""
    if not 1 <= request.max_retries <= 100:
        raise HTTPException(status_code=400, detail="max_retries must be between 1 and 100")
    manager.config["max_retries"] = request.max_retries
    _save_config()
    return {"status": "ok", "max_retries": request.max_retries}

@app.put("/config/research-timeout")
def set_research_timeout(request: ResearchTimeoutRequest):
    """Setzt den Research Timeout in Minuten (1-60)."""
    if not 1 <= request.research_timeout_minutes <= 60:
        raise HTTPException(status_code=400, detail="research_timeout_minutes must be between 1 and 60")
    manager.config["research_timeout_minutes"] = request.research_timeout_minutes
    _save_config()
    return {"status": "ok", "research_timeout_minutes": request.research_timeout_minutes}

# ÄNDERUNG 25.01.2026: Endpoint für Modellwechsel-Einstellung (Dual-Slider)
@app.put("/config/max-model-attempts")
def set_max_model_attempts(request: MaxModelAttemptsRequest):
    """Setzt nach wie vielen Fehlversuchen das Modell gewechselt wird (1 bis max_retries-1)."""
    max_retries = manager.config.get("max_retries", DEFAULT_MAX_RETRIES)
    # Validierung: min 1, max max_retries - 1
    if not 1 <= request.max_model_attempts <= max_retries - 1:
        raise HTTPException(
            status_code=400,
            detail=f"max_model_attempts must be between 1 and {max_retries - 1}"
        )
    manager.config["max_model_attempts"] = request.max_model_attempts
    _save_config()
    return {"status": "ok", "max_model_attempts": request.max_model_attempts}

def _is_valid_model(model_name: str) -> bool:
    """Validiert ob ein Modellname gültig ist."""
    if not model_name or not isinstance(model_name, str):
        return False
    # Prüfe gegen verfügbare Modelle oder OpenRouter-Format
    if model_name.startswith("openrouter/"):
        return True
    # Erlaube auch andere bekannte Formate
    if model_name.startswith("gpt-") or model_name.startswith("claude-"):
        return True
    # Prüfe gegen verfügbare Modelle aus der Config
    available_models = manager.config.get("available_models", [])
    if available_models and model_name in available_models:
        return True
    # Prüfe ob allow_unlisted_models aktiviert ist
    allow_unlisted = manager.config.get("allow_unlisted_models", False)
    if allow_unlisted:
        return len(model_name.strip()) > 0
    # Standard: Nur konfigurierte Modelle erlauben
    return False

@app.put("/config/model/{agent_role}")
def set_agent_model(agent_role: str, request: ModelRequest):
    """Setzt das Modell für einen bestimmten Agenten."""
    mode = manager.config.get("mode", "test")

    if agent_role not in manager.config.get("models", {}).get(mode, {}):
        raise HTTPException(status_code=404, detail=f"Agent role '{agent_role}' not found")

    # Validiere Modellname
    if not _is_valid_model(request.model):
        raise HTTPException(status_code=400, detail=f"Invalid model name: '{request.model}'. Model must be a valid OpenRouter model ID or configured model.")

    manager.config["models"][mode][agent_role] = request.model
    _save_config()
    return {"status": "ok", "agent": agent_role, "model": request.model}

@app.get("/config/model/{agent_role}")
def get_agent_model(agent_role: str):
    """Gibt das aktuelle Modell für einen Agenten zurück."""
    mode = manager.config.get("mode", "test")
    models = manager.config.get("models", {}).get(mode, {})

    if agent_role not in models:
        raise HTTPException(status_code=404, detail=f"Agent role '{agent_role}' not found")

    return {"agent": agent_role, "model": models[agent_role], "mode": mode}

@app.get("/models/available")
def get_available_models():
    """Listet verfügbare OpenRouter Modelle auf."""
    return {
        "free_models": [
            {"id": "openrouter/meta-llama/llama-3.3-70b-instruct:free", "name": "Llama 3.3 70B", "provider": "Meta", "strength": "General"},
            {"id": "openrouter/qwen/qwen3-coder:free", "name": "Qwen3 Coder", "provider": "Alibaba", "strength": "Coding"},
            {"id": "openrouter/google/gemma-3-27b-it:free", "name": "Gemma 3 27B", "provider": "Google", "strength": "Creative"},
            {"id": "openrouter/mistralai/mixtral-8x7b-instruct:free", "name": "Mixtral 8x7B", "provider": "Mistral", "strength": "Reasoning"},
            {"id": "openrouter/nvidia/nemotron-3-nano-30b-a3b:free", "name": "Nemotron 30B", "provider": "NVIDIA", "strength": "Fast"}
        ],
        "paid_models": [
            {"id": "openrouter/anthropic/claude-sonnet-4", "name": "Claude Sonnet 4", "provider": "Anthropic", "strength": "Premium"},
            {"id": "openrouter/openai/gpt-4-turbo", "name": "GPT-4 Turbo", "provider": "OpenAI", "strength": "Premium"},
            {"id": "openrouter/anthropic/claude-haiku-4", "name": "Claude Haiku 4", "provider": "Anthropic", "strength": "Fast Premium"}
        ]
    }

@app.get("/models/router-status")
def get_router_status():
    """Gibt den Status des ModelRouters zurück (Rate Limits, Nutzung)."""
    try:
        router = get_model_router(manager.config)
        return router.get_status()
    except Exception as e:
        return {"error": str(e), "rate_limited_models": {}, "usage_stats": {}}

@app.post("/models/clear-rate-limits")
def clear_rate_limits():
    """Setzt alle Rate-Limit-Markierungen zurück."""
    try:
        router = get_model_router(manager.config)
        router.clear_rate_limits()
        return {"status": "ok", "message": "Alle Rate-Limits zurückgesetzt"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ÄNDERUNG 24.01.2026: Security-Feedback Endpoint für Deploy Patches Button
@app.post("/security-feedback")
def trigger_security_fix():
    """
    Markiert Security-Issues als 'must fix' für die nächste Coder-Iteration.
    Wird vom 'Deploy Patches' Button im Frontend aufgerufen.
    """
    try:
        manager.force_security_fix = True
        vulnerabilities_count = len(manager.security_vulnerabilities) if hasattr(manager, 'security_vulnerabilities') else 0
        return {
            "status": "ok",
            "message": f"Security-Fix aktiviert für {vulnerabilities_count} Vulnerabilities",
            "vulnerabilities_count": vulnerabilities_count
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/security-status")
def get_security_status():
    """Gibt den aktuellen Security-Status zurück."""
    try:
        return {
            "vulnerabilities": manager.security_vulnerabilities if hasattr(manager, 'security_vulnerabilities') else [],
            "force_security_fix": manager.force_security_fix if hasattr(manager, 'force_security_fix') else False,
            "count": len(manager.security_vulnerabilities) if hasattr(manager, 'security_vulnerabilities') else 0
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/agents")
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
        # Extrahiere primäres Modell (unterstützt beide Config-Formate: String oder Dict mit primary/fallback)
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


def _save_config():
    """Speichert Konfiguration zurück in config.yaml."""
    config_path = os.path.join(manager.base_dir, "config.yaml")

    if RUAMEL_AVAILABLE:
        # Verwende ruamel.yaml um Kommentare zu erhalten
        yaml_loader = YAML()
        yaml_loader.preserve_quotes = True
        try:
            # Lade existierende Datei
            with open(config_path, "r", encoding="utf-8") as f:
                existing_data = yaml_loader.load(f) or {}
            
            # Aktualisiere nur geänderte Felder
            if "mode" in manager.config:
                existing_data["mode"] = manager.config["mode"]
            if "models" in manager.config:
                existing_data["models"] = manager.config["models"]
            if "max_retries" in manager.config:
                existing_data["max_retries"] = manager.config["max_retries"]
            if "max_model_attempts" in manager.config:
                existing_data["max_model_attempts"] = manager.config["max_model_attempts"]
            if "research_timeout_minutes" in manager.config:
                existing_data["research_timeout_minutes"] = manager.config["research_timeout_minutes"]
            if "include_designer" in manager.config:
                existing_data["include_designer"] = manager.config["include_designer"]
            if "project_type" in manager.config:
                existing_data["project_type"] = manager.config["project_type"]
            
            # Speichere zurück
            with open(config_path, "w", encoding="utf-8") as f:
                yaml_loader.dump(existing_data, f)
        except Exception as e:
            # Fallback zu normalem yaml.dump bei Fehlern
            with open(config_path, "w", encoding="utf-8") as f:
                yaml.dump(manager.config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    else:
        # Fallback zu normalem yaml.dump wenn ruamel.yaml nicht verfügbar
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(manager.config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)


# =====================================================================
# BUDGET API - Budget Dashboard Endpoints (ECHTE DATEN)
# =====================================================================

class BudgetCapsRequest(BaseModel):
    monthly: float
    daily: float
    auto_pause: bool = True
    slack_webhook: Optional[str] = None
    discord_webhook: Optional[str] = None

class ProjectCreateRequest(BaseModel):
    project_id: str
    name: str
    budget: float

@app.get("/budget/stats")
def get_budget_stats(period_days: int = Query(default=30, ge=1, le=365)):
    """Gibt echte Budget-Statistiken zurück."""
    tracker = get_budget_tracker()
    return tracker.get_stats(period_days=period_days)

@app.get("/budget/costs/agents")
def get_agent_costs(period_days: int = Query(default=7, ge=1, le=90)):
    """Gibt echte Kosten pro Agent zurück."""
    tracker = get_budget_tracker()
    agents = tracker.get_costs_by_agent(period_days=period_days)
    return {
        "agents": agents,
        "period": f"{period_days}d",
        "data_source": "real" if agents else "no_data"
    }

@app.get("/budget/heatmap")
def get_token_heatmap(period_days: int = Query(default=1, ge=1, le=7)):
    """Gibt echte Token-Nutzungs-Heatmap zurück."""
    tracker = get_budget_tracker()
    heatmap = tracker.get_hourly_heatmap(period_days=period_days)
    heatmap["data_source"] = "real" if heatmap["agents"] else "no_data"
    return heatmap

@app.get("/budget/caps")
def get_budget_caps():
    """Gibt Budget-Caps aus persistierter Konfiguration zurück."""
    tracker = get_budget_tracker()
    config = tracker.get_config()
    return {
        "monthly": config["global_monthly_cap"],
        "daily": config["global_daily_cap"],
        "auto_pause": config["auto_pause"],
        "alert_thresholds": config["alert_thresholds"],
        "slack_webhook_configured": bool(config.get("slack_webhook_url")),
        "discord_webhook_configured": bool(config.get("discord_webhook_url"))
    }

@app.put("/budget/caps")
def set_budget_caps(request: BudgetCapsRequest):
    """Setzt Budget-Caps und speichert sie persistent."""
    tracker = get_budget_tracker()
    tracker.update_config(
        monthly_cap=request.monthly,
        daily_cap=request.daily,
        auto_pause=request.auto_pause,
        slack_webhook=request.slack_webhook,
        discord_webhook=request.discord_webhook
    )
    return {
        "status": "ok",
        "monthly": request.monthly,
        "daily": request.daily,
        "auto_pause": request.auto_pause
    }

@app.get("/budget/recommendations")
def get_budget_recommendations():
    """Gibt intelligente Optimierungs-Empfehlungen basierend auf echten Daten zurück."""
    tracker = get_budget_tracker()
    stats = tracker.get_stats()
    agent_costs = tracker.get_costs_by_agent(period_days=7)
    prediction = tracker.predict_costs(days_ahead=30)

    recommendations = []

    # Empfehlung basierend auf echten Daten
    if agent_costs:
        # Finde teuersten Agent
        if agent_costs[0]["cost"] > 0:
            most_expensive = agent_costs[0]
            recommendations.append({
                "type": "recommendation",
                "title": f"Optimize {most_expensive['name']}",
                "description": f"{most_expensive['name']} verursacht die höchsten Kosten (${most_expensive['cost']:.2f}). "
                               f"Erwäge ein günstigeres Modell für weniger komplexe Aufgaben.",
                "agent": most_expensive["role"]
            })

    # Warnung bei hoher Burn Rate
    if stats["burn_rate_change"] > 20:
        recommendations.append({
            "type": "warning",
            "title": "Rising Costs",
            "description": f"Die Burn Rate ist um {stats['burn_rate_change']:.1f}% gestiegen. "
                           f"Überprüfe die Nutzungsmuster.",
            "agent": None
        })

    # Warnung bei niedrigem Budget
    if stats["remaining"] < stats["total_budget"] * 0.2:
        recommendations.append({
            "type": "critical",
            "title": "Low Budget",
            "description": f"Nur noch ${stats['remaining']:.2f} verbleibend ({stats['days_remaining']} Tage). "
                           f"Budget erhöhen oder Nutzung reduzieren.",
            "agent": None
        })

    # Trend-Info
    if prediction.get("prediction_available"):
        recommendations.append({
            "type": "info",
            "title": f"Trend: {prediction['trend'].capitalize()}",
            "description": f"Prognostizierte Kosten für 30 Tage: ${prediction['total_predicted_30d']:.2f}. "
                           f"Confidence: {prediction['confidence']}.",
            "agent": None
        })

    # Wenn keine Daten vorhanden
    if not recommendations:
        recommendations.append({
            "type": "info",
            "title": "Keine Daten",
            "description": "Noch keine Nutzungsdaten vorhanden. Empfehlungen werden nach einigen Agent-Runs verfügbar.",
            "agent": None
        })

    return {"recommendations": recommendations}

@app.get("/budget/prediction")
def get_budget_prediction(days_ahead: int = Query(default=30, ge=1, le=90)):
    """Gibt Kostenprognose basierend auf linearer Regression zurück."""
    tracker = get_budget_tracker()
    return tracker.predict_costs(days_ahead=days_ahead)

@app.get("/budget/history")
def get_budget_history(period_days: int = Query(default=30, ge=1, le=365)):
    """Gibt historische Tagesdaten zurück."""
    tracker = get_budget_tracker()
    history = tracker.get_historical_data(period_days=period_days)
    return {
        "history": history,
        "period_days": period_days,
        "data_source": "real" if history else "no_data"
    }

# ===== Projekt-Budgets =====

@app.get("/budget/projects")
def get_projects():
    """Gibt alle Projekte mit deren Budgets zurück."""
    tracker = get_budget_tracker()
    return {"projects": tracker.get_all_projects()}

@app.post("/budget/projects")
def create_project(request: ProjectCreateRequest):
    """Erstellt ein neues Projekt mit eigenem Budget."""
    tracker = get_budget_tracker()
    project = tracker.create_project(
        project_id=request.project_id,
        name=request.name,
        budget=request.budget
    )
    return {"status": "ok", "project": {
        "project_id": project.project_id,
        "name": project.name,
        "total_budget": project.total_budget
    }}

@app.delete("/budget/projects/{project_id}")
def delete_project(project_id: str):
    """Löscht ein Projekt."""
    tracker = get_budget_tracker()
    if tracker.delete_project(project_id):
        return {"status": "ok"}
    raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")

@app.get("/budget/projects/{project_id}")
def get_project(project_id: str):
    """Gibt Details zu einem Projekt zurück."""
    tracker = get_budget_tracker()
    project = tracker.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")

    # Berechne aktuelle Kosten
    project_costs = sum(
        r.cost_usd for r in tracker.usage_history
        if r.project_id == project_id
    )

    return {
        "project_id": project.project_id,
        "name": project.name,
        "total_budget": project.total_budget,
        "spent": round(project_costs, 2),
        "remaining": round(project.total_budget - project_costs, 2),
        "percentage_used": round((project_costs / project.total_budget) * 100, 1) if project.total_budget > 0 else 0
    }
