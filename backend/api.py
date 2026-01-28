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
from datetime import datetime, timedelta
import requests
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
from .library_manager import get_library_manager

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

# ÄNDERUNG 25.01.2026: Dynamische OpenRouter Modell-API mit Caching
_models_cache = {"data": None, "timestamp": None}
MODELS_CACHE_DURATION = timedelta(hours=1)

def fetch_openrouter_models():
    """
    Holt Modelle von OpenRouter API mit Caching.
    Cache-Dauer: 1 Stunde.
    """
    now = datetime.now()

    # Cache prüfen
    if _models_cache["data"] and _models_cache["timestamp"]:
        if now - _models_cache["timestamp"] < MODELS_CACHE_DURATION:
            return _models_cache["data"]

    try:
        api_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("Kein API-Key gefunden")

        response = requests.get(
            "https://openrouter.ai/api/v1/models",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10
        )
        response.raise_for_status()
        models = response.json().get("data", [])

        # Filtern und formatieren
        free_models = []
        paid_models = []

        for m in models:
            # Provider aus ID extrahieren (z.B. "Anthropic" aus "anthropic/claude-3")
            provider = m["id"].split("/")[0].title()

            model_data = {
                "id": f"openrouter/{m['id']}",
                "name": m.get("name", m["id"]),
                "provider": provider,
                "context_length": m.get("context_length", 0),
                "pricing": m.get("pricing", {})
            }

            # Free wenn prompt UND completion = 0
            pricing = m.get("pricing", {})
            is_free = (
                str(pricing.get("prompt", "1")) == "0" and
                str(pricing.get("completion", "1")) == "0"
            )

            if is_free:
                free_models.append(model_data)
            else:
                paid_models.append(model_data)

        # Nach Name sortieren
        free_models.sort(key=lambda x: x["name"])
        paid_models.sort(key=lambda x: x["name"])

        result = {"free_models": free_models, "paid_models": paid_models}

        # Cache aktualisieren
        _models_cache["data"] = result
        _models_cache["timestamp"] = now

        print(f"OpenRouter API: {len(free_models)} Free + {len(paid_models)} Paid Modelle geladen")
        return result

    except Exception as e:
        print(f"OpenRouter API Fehler: {e}")
        # Fallback auf Cache oder Fallback-Liste
        if _models_cache["data"]:
            return _models_cache["data"]
        # Fallback auf statische Liste wenn API nicht erreichbar
        return {
            "free_models": [
                {"id": "openrouter/meta-llama/llama-3.3-70b-instruct:free", "name": "Llama 3.3 70B", "provider": "Meta"},
                {"id": "openrouter/google/gemma-3-27b-it:free", "name": "Gemma 3 27B", "provider": "Google"}
            ],
            "paid_models": [
                {"id": "openrouter/anthropic/claude-haiku-4.5", "name": "Claude Haiku 4.5", "provider": "Anthropic"},
                {"id": "openrouter/openai/gpt-5-mini", "name": "GPT-5 Mini", "provider": "OpenAI"}
            ]
        }

@app.get("/models/available")
def get_available_models():
    """Listet verfügbare OpenRouter Modelle auf (dynamisch von API)."""
    return fetch_openrouter_models()

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

# ÄNDERUNG 25.01.2026: Reset-Endpunkt für Projekt-Neustart
@app.post("/reset")
async def reset_project():
    """
    Setzt das aktuelle Projekt komplett zurück.
    Ermöglicht einen Neustart ohne Server-Neustart.
    """
    try:
        # OrchestrationManager Felder zurücksetzen
        manager.project_path = None
        manager.output_path = None
        manager.tech_blueprint = {}
        manager.database_schema = "Kein Datenbank-Schema."
        manager.design_concept = "Kein Design-Konzept."
        manager.current_code = ""
        manager.is_first_run = True
        manager.security_vulnerabilities = []
        manager.force_security_fix = False

        # Worker-Pool zurücksetzen (falls vorhanden)
        if hasattr(manager, 'office_manager') and manager.office_manager:
            try:
                manager.office_manager.reset_all_workers()
            except Exception as e:
                log_event("API", "Warning", f"Worker-Reset fehlgeschlagen: {e}")

        # Broadcast Reset-Event an alle Clients
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


# =====================================================================
# LIBRARY / ARCHIV ENDPOINTS
# ÄNDERUNG 28.01.2026: Protokoll- und Archiv-System
# =====================================================================

@app.get("/library/current")
def get_current_project_protocol():
    """Gibt das aktuelle Projekt-Protokoll zurück."""
    library = get_library_manager()
    project = library.get_current_project()
    if not project:
        return {"status": "no_project", "project": None}
    return {"status": "ok", "project": project}


@app.get("/library/entries")
def get_protocol_entries(agent: Optional[str] = None, limit: int = 100):
    """
    Gibt Protokoll-Einträge des aktuellen Projekts zurück.

    Args:
        agent: Optional - nur Einträge von diesem Agent
        limit: Maximale Anzahl Einträge
    """
    library = get_library_manager()
    entries = library.get_entries(agent_filter=agent, limit=limit)
    return {"status": "ok", "entries": entries, "count": len(entries)}


@app.get("/library/archive")
def get_archived_projects():
    """Gibt alle archivierten Projekte zurück (ohne Einträge)."""
    library = get_library_manager()
    projects = library.get_archived_projects()
    return {"status": "ok", "projects": projects, "count": len(projects)}


@app.get("/library/archive/{project_id}")
def get_archived_project(project_id: str):
    """Lädt ein archiviertes Projekt vollständig."""
    library = get_library_manager()
    project = library.get_archived_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail=f"Projekt '{project_id}' nicht gefunden")
    return {"status": "ok", "project": project}


@app.get("/library/search")
def search_archives(q: str, limit: int = 20):
    """
    Durchsucht alle Archive nach einem Begriff.

    Args:
        q: Suchbegriff
        limit: Maximale Ergebnisse
    """
    library = get_library_manager()
    results = library.search_archives(q, limit=limit)
    return {"status": "ok", "results": results, "count": len(results)}


# =====================================================================
# EXTERNAL BUREAU ENDPOINTS
# AENDERUNG 28.01.2026: Externe Specialists (CodeRabbit, EXA Search, etc.)
# =====================================================================

# Lazy-load External Bureau Manager
_external_bureau_manager = None

def get_external_bureau_manager():
    """Lazy-load des External Bureau Managers."""
    global _external_bureau_manager
    if _external_bureau_manager is None:
        try:
            from agents.external_bureau_manager import ExternalBureauManager
            _external_bureau_manager = ExternalBureauManager(manager.config)
        except Exception as e:
            log_event("API", "Error", f"External Bureau Manager konnte nicht geladen werden: {e}")
            return None
    return _external_bureau_manager


@app.get("/external-bureau/status")
def get_external_bureau_status():
    """Gibt den Status des External Bureau zurueck."""
    bureau = get_external_bureau_manager()
    if not bureau:
        return {
            "enabled": False,
            "error": "External Bureau Manager nicht verfuegbar",
            "specialists": []
        }
    return bureau.get_status()


@app.get("/external-bureau/specialists")
def get_all_specialists(category: Optional[str] = None):
    """
    Listet alle externen Specialists auf.

    Args:
        category: Optional - "all", "combat", "intelligence", "creative"
    """
    bureau = get_external_bureau_manager()
    if not bureau:
        return {"specialists": [], "error": "External Bureau nicht verfuegbar"}

    if category:
        specialists = bureau.get_specialists_by_category(category)
    else:
        specialists = bureau.get_all_specialists()

    return {"specialists": specialists, "count": len(specialists)}


@app.post("/external-bureau/specialists/{specialist_id}/activate")
def activate_specialist(specialist_id: str):
    """Aktiviert einen Specialist."""
    bureau = get_external_bureau_manager()
    if not bureau:
        raise HTTPException(status_code=503, detail="External Bureau nicht verfuegbar")

    result = bureau.activate_specialist(specialist_id)
    if result["success"]:
        return result
    raise HTTPException(status_code=400, detail=result["message"])


@app.post("/external-bureau/specialists/{specialist_id}/deactivate")
def deactivate_specialist(specialist_id: str):
    """Deaktiviert einen Specialist."""
    bureau = get_external_bureau_manager()
    if not bureau:
        raise HTTPException(status_code=503, detail="External Bureau nicht verfuegbar")

    result = bureau.deactivate_specialist(specialist_id)
    if result["success"]:
        return result
    raise HTTPException(status_code=400, detail=result["message"])


@app.get("/external-bureau/findings")
def get_external_findings():
    """Gibt alle gesammelten Findings aller Specialists zurueck."""
    bureau = get_external_bureau_manager()
    if not bureau:
        return {"findings": [], "error": "External Bureau nicht verfuegbar"}

    findings = bureau.get_combined_findings()
    return {"findings": findings, "count": len(findings)}


class SearchRequest(BaseModel):
    query: str
    num_results: int = 10


@app.post("/external-bureau/search")
async def run_external_search(request: SearchRequest):
    """Fuehrt eine EXA Search durch."""
    bureau = get_external_bureau_manager()
    if not bureau:
        raise HTTPException(status_code=503, detail="External Bureau nicht verfuegbar")

    result = await bureau.run_search(request.query)
    if not result:
        raise HTTPException(status_code=400, detail="EXA Search nicht verfuegbar oder nicht aktiviert")

    return {
        "success": result.success,
        "findings": [f.__dict__ if hasattr(f, '__dict__') else f for f in result.findings],
        "summary": result.summary,
        "duration_ms": result.duration_ms,
        "error": result.error
    }


class ReviewRequest(BaseModel):
    project_path: Optional[str] = None
    files: Optional[list] = None


@app.post("/external-bureau/review")
async def run_external_review(request: ReviewRequest):
    """Fuehrt ein Review mit allen aktiven COMBAT-Specialists durch."""
    bureau = get_external_bureau_manager()
    if not bureau:
        raise HTTPException(status_code=503, detail="External Bureau nicht verfuegbar")

    context = {
        "project_path": request.project_path or manager.project_path or ".",
        "files": request.files or []
    }

    results = await bureau.run_review_specialists(context)

    return {
        "results": [
            {
                "success": r.success,
                "findings_count": len(r.findings),
                "summary": r.summary,
                "duration_ms": r.duration_ms,
                "error": r.error
            }
            for r in results
        ],
        "total_findings": sum(len(r.findings) for r in results)
    }


# Hilfsfunktion fuer Logging
def log_event(agent: str, event: str, message: str):
    """Logged ein Event in die Konsole und optional ins UI."""
    print(f"[{agent}] {event}: {message}")
