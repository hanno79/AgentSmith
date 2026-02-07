# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 29.01.2026
Version: 1.0
Beschreibung: Konfigurations- und Modell-Endpoints.
"""
# ÄNDERUNG 29.01.2026: Config-Endpunkte in eigenes Router-Modul verschoben

import os
import sys
import yaml
import aiohttp
import logging
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from ..app_state import manager, DEFAULT_MAX_RETRIES

try:
    from ruamel.yaml import YAML
    RUAMEL_AVAILABLE = True
except ImportError:
    RUAMEL_AVAILABLE = False

# Füge Projektroot zum Path hinzu für model_router Import
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, _project_root)

from model_router import get_model_router

router = APIRouter()
logger = logging.getLogger(__name__)


class ModeRequest(BaseModel):
    mode: str


class ModelRequest(BaseModel):
    model: str


class MaxRetriesRequest(BaseModel):
    max_retries: int


class MaxModelAttemptsRequest(BaseModel):
    max_model_attempts: int


class ResearchTimeoutRequest(BaseModel):
    research_timeout_minutes: int


# ÄNDERUNG 30.01.2026: Globaler Timeout für Agenten-Operationen
class AgentTimeoutRequest(BaseModel):
    agent_timeout_seconds: int


# ÄNDERUNG 03.02.2026: Feature 10a - Token-Limits pro Agent
class TokenLimitRequest(BaseModel):
    max_tokens: int


# AENDERUNG 06.02.2026: Docker-Toggle ueber UI
class DockerEnabledRequest(BaseModel):
    enabled: bool


@router.get("/config")
def get_config():
    """Gibt die aktuelle Konfiguration zurück."""
    return {
        "mode": manager.config.get("mode", "test"),
        "project_type": manager.config.get("project_type", "webapp"),
        "max_retries": manager.config.get("max_retries", DEFAULT_MAX_RETRIES),
        "research_timeout_minutes": manager.config.get("research_timeout_minutes", 5),
        # ÄNDERUNG 30.01.2026: Globaler Agent-Timeout
        "agent_timeout_seconds": manager.config.get("agent_timeout_seconds", 300),
        "include_designer": manager.config.get("include_designer", True),
        "models": manager.config.get("models", {}),
        "available_modes": ["test", "production", "premium"],
        # ÄNDERUNG 03.02.2026: Feature 10a - Token-Limits
        "token_limits": manager.config.get("token_limits", {"default": 4096}),
        # AENDERUNG 06.02.2026: Docker-Status fuer Frontend-Toggle
        "docker_enabled": manager.config.get("docker", {}).get("enabled", False)
    }


@router.put("/config/mode")
def set_mode(request: ModeRequest):
    """Wechselt zwischen test, production und premium Modus."""
    if request.mode not in ["test", "production", "premium"]:
        raise HTTPException(status_code=400, detail="Invalid mode. Use 'test', 'production' or 'premium'")
    manager.config["mode"] = request.mode
    _save_config()
    return {"status": "ok", "mode": request.mode}


@router.put("/config/max-retries")
def set_max_retries(request: MaxRetriesRequest):
    """Setzt die maximale Anzahl an Retries (1-100)."""
    if not 1 <= request.max_retries <= 100:
        raise HTTPException(status_code=400, detail="max_retries must be between 1 and 100")
    manager.config["max_retries"] = request.max_retries
    _save_config()
    return {"status": "ok", "max_retries": request.max_retries}


@router.put("/config/research-timeout")
def set_research_timeout(request: ResearchTimeoutRequest):
    """Setzt den Research Timeout in Minuten (1-60)."""
    if not 1 <= request.research_timeout_minutes <= 60:
        raise HTTPException(status_code=400, detail="research_timeout_minutes must be between 1 and 60")
    manager.config["research_timeout_minutes"] = request.research_timeout_minutes
    _save_config()
    return {"status": "ok", "research_timeout_minutes": request.research_timeout_minutes}


# ÄNDERUNG 30.01.2026: Globaler Timeout für Agenten-Operationen
# ÄNDERUNG 02.02.2026: Max von 600 auf 1800 (30 min) erhöht für langsame Free-Modelle
@router.put("/config/agent-timeout")
def set_agent_timeout(request: AgentTimeoutRequest):
    """Setzt den globalen Agent Timeout in Sekunden (60-1800)."""
    if not 60 <= request.agent_timeout_seconds <= 1800:
        raise HTTPException(status_code=400, detail="agent_timeout_seconds muss zwischen 60 und 1800 liegen")
    manager.config["agent_timeout_seconds"] = request.agent_timeout_seconds
    _save_config()
    return {"status": "ok", "agent_timeout_seconds": request.agent_timeout_seconds}


# AENDERUNG 06.02.2026: Docker-Toggle ueber UI
@router.put("/config/docker")
def set_docker_enabled(request: DockerEnabledRequest):
    """Aktiviert oder deaktiviert Docker-Isolation fuer Tests."""
    if "docker" not in manager.config:
        manager.config["docker"] = {}
    manager.config["docker"]["enabled"] = request.enabled
    _save_config()
    logger.info("[Docker] Docker-Isolation %s", "aktiviert" if request.enabled else "deaktiviert")
    return {"status": "ok", "docker_enabled": request.enabled}


# ÄNDERUNG 03.02.2026: Feature 10a - Token-Limits pro Agent
@router.get("/config/token-limits")
def get_token_limits():
    """Gibt alle Token-Limits pro Agent zurück."""
    default_limits = {
        "default": 4096,
        "coder": 8192,
        "tester": 4096,
        "reviewer": 2048,
        "planner": 2048,
        "designer": 4096,
        "security": 2048,
        "researcher": 4096,
        "orchestrator": 2048,
        "discovery": 1500
    }
    return manager.config.get("token_limits", default_limits)


@router.put("/config/token-limit/{agent_role}")
def set_token_limit(agent_role: str, request: TokenLimitRequest):
    # ÄNDERUNG 07.02.2026: Validierung von 32000 auf 131072 erhöht (OpenRouter Maximum)
    """Setzt das Token-Limit fuer einen Agent (100-131072)."""
    if not 100 <= request.max_tokens <= 131072:
        raise HTTPException(
            status_code=400,
            detail="max_tokens muss zwischen 100 und 131072 liegen"
        )

    # Initialisiere token_limits falls nicht vorhanden
    if "token_limits" not in manager.config:
        manager.config["token_limits"] = {
            "default": 4096,
            "coder": 8192,
            "tester": 4096,
            "reviewer": 2048
        }

    manager.config["token_limits"][agent_role] = request.max_tokens
    _save_config()

    logger.info(f"[TokenLimit] {agent_role} auf {request.max_tokens} gesetzt")
    return {
        "status": "ok",
        "agent": agent_role,
        "max_tokens": request.max_tokens
    }


@router.put("/config/max-model-attempts")
def set_max_model_attempts(request: MaxModelAttemptsRequest):
    """Setzt nach wie vielen Fehlversuchen das Modell gewechselt wird (1 bis max_retries-1)."""
    max_retries = manager.config.get("max_retries", DEFAULT_MAX_RETRIES)
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
    if model_name.startswith("openrouter/"):
        return True
    if model_name.startswith("gpt-") or model_name.startswith("claude-"):
        return True
    available_models = manager.config.get("available_models", [])
    if available_models and model_name in available_models:
        return True
    allow_unlisted = manager.config.get("allow_unlisted_models", False)
    if allow_unlisted:
        return len(model_name.strip()) > 0
    return False


@router.put("/config/model/{agent_role}")
def set_agent_model(agent_role: str, request: ModelRequest):
    """Setzt das Modell für einen bestimmten Agenten."""
    mode = manager.config.get("mode", "test")

    if agent_role not in manager.config.get("models", {}).get(mode, {}):
        raise HTTPException(status_code=404, detail=f"Agent role '{agent_role}' not found")

    if not _is_valid_model(request.model):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid model name: '{request.model}'. Model must be a valid OpenRouter model ID or configured model."
        )

    manager.config["models"][mode][agent_role] = request.model
    _save_config()
    return {"status": "ok", "agent": agent_role, "model": request.model}


@router.get("/config/model/{agent_role}")
def get_agent_model(agent_role: str):
    """Gibt das aktuelle Modell für einen Agenten zurück."""
    mode = manager.config.get("mode", "test")
    models = manager.config.get("models", {}).get(mode, {})

    if agent_role not in models:
        raise HTTPException(status_code=404, detail=f"Agent role '{agent_role}' not found")

    return {"agent": agent_role, "model": models[agent_role], "mode": mode}


# ÄNDERUNG 29.01.2026: Neue Endpoints für Modell-Prioritätslisten (Drag & Drop im Hub)
@router.get("/config/model-priority/{agent_role}")
def get_model_priority(agent_role: str):
    """Gibt die Modell-Prioritaetsliste fuer einen Agenten zurueck."""
    mode = manager.config.get("mode", "test")
    model_config = manager.config.get("models", {}).get(mode, {}).get(agent_role)

    if model_config is None:
        raise HTTPException(status_code=404, detail=f"Agent role '{agent_role}' not found")

    # Altes Format: nur ein String
    if isinstance(model_config, str):
        return {"agent": agent_role, "models": [model_config], "mode": mode}

    # Neues Format: primary + fallback Liste
    models = []
    primary = model_config.get("primary", "")
    if primary:
        models.append(primary)
    fallbacks = model_config.get("fallback", [])
    if isinstance(fallbacks, list):
        models.extend(fallbacks)
    elif fallbacks:
        models.append(fallbacks)

    return {"agent": agent_role, "models": models, "mode": mode}


# Bekannte Agent-Rollen (muss mit config.yaml / models[mode] uebereinstimmen)
# AENDERUNG 01.02.2026: Alle Rollen aus config.yaml hinzugefuegt
# AENDERUNG 07.02.2026: fix + task_deriver hinzugefuegt (Fix 14)
# AENDERUNG 07.02.2026: planner, analyst, konzepter hinzugefuegt (fehlten trotz agent_factory Implementierung)
KNOWN_AGENT_ROLES = frozenset({
    "meta_orchestrator", "orchestrator", "researcher", "coder", "tester",
    "designer", "database_designer", "security", "reviewer", "techstack_architect",
    "documentation_manager", "test_generator", "orchestrator_validator",
    "validator", "reporter", "fix", "task_deriver", "planner", "analyst", "konzepter"
})


@router.put("/config/model-priority/{agent_role}")
async def set_model_priority(agent_role: str, request: Request):
    """Setzt die Modell-Prioritaetsliste (Body: {"models": [...]}, max 5)."""
    data = await request.json()
    models = data.get("models", [])

    if not models or len(models) < 1:
        raise HTTPException(status_code=400, detail="Mindestens 1 Modell erforderlich")

    # Validiere alle Modelle
    for model in models[:5]:
        if not _is_valid_model(model):
            raise HTTPException(
                status_code=400,
                detail=f"Ungültiges Modell: '{model}'"
            )

    mode = manager.config.get("mode", "test")

    # Rolle muss bekannt sein, bevor wir config mutieren
    if agent_role not in KNOWN_AGENT_ROLES:
        logger.warning("set_model_priority: Unbekannte Rolle '%s'", agent_role)
        raise HTTPException(
            status_code=400,
            detail=f"Unbekannte Rolle: '{agent_role}'"
        )

    # Stelle sicher dass models[mode] existiert
    if "models" not in manager.config:
        manager.config["models"] = {}
    if mode not in manager.config["models"]:
        manager.config["models"][mode] = {}

    # Speichere als primary + fallback Format
    manager.config["models"][mode][agent_role] = {
        "primary": models[0],
        "fallback": models[1:5]  # Max 4 Fallbacks
    }

    _save_config()
    logger.info("Modell-Priorität für %s gesetzt: %s", agent_role, models[:5])
    return {"status": "ok", "agent": agent_role, "models": models[:5], "mode": mode}


_models_cache = {"data": None, "timestamp": None}
MODELS_CACHE_DURATION = timedelta(hours=1)


async def fetch_openrouter_models():
    """Holt Modelle von OpenRouter API mit Caching (1 Stunde)."""
    now = datetime.now()

    if _models_cache["data"] and _models_cache["timestamp"]:
        if now - _models_cache["timestamp"] < MODELS_CACHE_DURATION:
            return _models_cache["data"]

    try:
        api_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("Kein API-Key gefunden")

        # ÄNDERUNG 29.01.2026: Async HTTP für non-blocking WebSocket-Stabilität
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://openrouter.ai/api/v1/models",
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                response.raise_for_status()
                data = await response.json()
                models = data.get("data", [])

        free_models = []
        paid_models = []

        for m in models:
            provider = m["id"].split("/")[0].title()

            model_data = {
                "id": f"openrouter/{m['id']}",
                "name": m.get("name", m["id"]),
                "provider": provider,
                "context_length": m.get("context_length", 0),
                "pricing": m.get("pricing", {})
            }

            pricing = m.get("pricing", {})
            is_free = (
                str(pricing.get("prompt", "1")) == "0" and
                str(pricing.get("completion", "1")) == "0"
            )

            if is_free:
                free_models.append(model_data)
            else:
                paid_models.append(model_data)

        free_models.sort(key=lambda x: x["name"])
        paid_models.sort(key=lambda x: x["name"])

        result = {"free_models": free_models, "paid_models": paid_models}

        _models_cache["data"] = result
        _models_cache["timestamp"] = now

        # ÄNDERUNG 29.01.2026: Logging statt print
        logger.info(
            "OpenRouter API: %s Free + %s Paid Modelle geladen",
            len(free_models),
            len(paid_models)
        )
        return result

    except Exception as e:
        # ÄNDERUNG 29.01.2026: Logging statt print mit Stacktrace
        logger.exception("OpenRouter API Fehler: %s", e)
        if _models_cache["data"]:
            return _models_cache["data"]
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


@router.get("/models/available")
async def get_available_models():
    """Listet verfügbare OpenRouter Modelle auf (dynamisch von API)."""
    return await fetch_openrouter_models()


@router.get("/models/router-status")
def get_router_status():
    """Gibt den Status des ModelRouters zurück (Rate Limits, Nutzung)."""
    try:
        router_instance = get_model_router(manager.config)
        return router_instance.get_status()
    except Exception as e:
        return {"error": str(e), "rate_limited_models": {}, "usage_stats": {}}


@router.post("/models/clear-rate-limits")
def clear_rate_limits():
    """Setzt alle Rate-Limit-Markierungen zurück."""
    try:
        router_instance = get_model_router(manager.config)
        router_instance.clear_rate_limits()
        return {"status": "ok", "message": "Alle Rate-Limits zurückgesetzt"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _save_config():
    """Speichert Konfiguration zurück in config.yaml."""
    config_path = os.path.join(manager.base_dir, "config.yaml")

    if RUAMEL_AVAILABLE:
        yaml_loader = YAML()
        yaml_loader.preserve_quotes = True
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                existing_data = yaml_loader.load(f) or {}

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
            # ÄNDERUNG 30.01.2026: Globaler Agent-Timeout speichern
            if "agent_timeout_seconds" in manager.config:
                existing_data["agent_timeout_seconds"] = manager.config["agent_timeout_seconds"]
            if "include_designer" in manager.config:
                existing_data["include_designer"] = manager.config["include_designer"]
            if "project_type" in manager.config:
                existing_data["project_type"] = manager.config["project_type"]
            # AENDERUNG 06.02.2026: Docker-Toggle persistieren
            if "docker" in manager.config:
                if "docker" not in existing_data:
                    existing_data["docker"] = {}
                existing_data["docker"]["enabled"] = manager.config["docker"].get("enabled", False)

            with open(config_path, "w", encoding="utf-8") as f:
                yaml_loader.dump(existing_data, f)
        except Exception as e:
            # ÄNDERUNG 29.01.2026: Fehler beim Schreiben sichtbar loggen
            logger.exception("Konnte %s nicht schreiben (yaml.dump fallback). Fehler: %s", config_path, e)
            with open(config_path, "w", encoding="utf-8") as f:
                yaml.dump(manager.config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    else:
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(manager.config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
