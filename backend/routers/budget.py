# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 29.01.2026
Version: 1.0
Beschreibung: Budget-Endpoints für Dashboard und Projekte.
"""
# ÄNDERUNG 29.01.2026: Budget-Endpunkte in eigenes Router-Modul verschoben

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, field_validator
from typing import Optional
from budget_tracker import get_budget_tracker

router = APIRouter()


class BudgetCapsRequest(BaseModel):
    monthly: float
    daily: float
    auto_pause: bool = True
    slack_webhook: Optional[str] = None
    discord_webhook: Optional[str] = None

    # ÄNDERUNG 29.01.2026: Pydantic V2 Validator-API verwenden
    # ÄNDERUNG 29.01.2026: Keine negativen Caps erlauben
    @field_validator("monthly", "daily")
    def _non_negative_caps(cls, value, info):
        if value < 0:
            raise ValueError(f"{info.field_name} darf nicht negativ sein")
        return value


class ProjectCreateRequest(BaseModel):
    project_id: str
    name: str
    budget: float


@router.get("/budget/stats")
def get_budget_stats(period_days: int = Query(default=30, ge=1, le=365)):
    """Gibt echte Budget-Statistiken zurück."""
    tracker = get_budget_tracker()
    return tracker.get_stats(period_days=period_days)


@router.get("/budget/costs/agents")
def get_agent_costs(period_days: int = Query(default=7, ge=1, le=90)):
    """Gibt echte Kosten pro Agent zurück."""
    tracker = get_budget_tracker()
    agents = tracker.get_costs_by_agent(period_days=period_days)
    return {
        "agents": agents,
        "period": f"{period_days}d",
        "data_source": "real" if agents else "no_data"
    }


@router.get("/budget/heatmap")
def get_token_heatmap(period_days: int = Query(default=1, ge=1, le=7)):
    """Gibt echte Token-Nutzungs-Heatmap zurück."""
    tracker = get_budget_tracker()
    heatmap = tracker.get_hourly_heatmap(period_days=period_days)
    heatmap["data_source"] = "real" if heatmap["agents"] else "no_data"
    return heatmap


@router.get("/budget/caps")
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


@router.put("/budget/caps")
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


@router.get("/budget/recommendations")
def get_budget_recommendations():
    """Gibt intelligente Optimierungs-Empfehlungen basierend auf echten Daten zurück."""
    tracker = get_budget_tracker()
    stats = tracker.get_stats()
    agent_costs = tracker.get_costs_by_agent(period_days=7)
    prediction = tracker.predict_costs(days_ahead=30)

    recommendations = []

    if agent_costs:
        if agent_costs[0]["cost"] > 0:
            most_expensive = agent_costs[0]
            recommendations.append({
                "type": "recommendation",
                "title": f"Optimize {most_expensive['name']}",
                "description": f"{most_expensive['name']} verursacht die höchsten Kosten (${most_expensive['cost']:.2f}). "
                               f"Erwäge ein günstigeres Modell für weniger komplexe Aufgaben.",
                "agent": most_expensive["role"]
            })

    if stats["burn_rate_change"] > 20:
        recommendations.append({
            "type": "warning",
            "title": "Rising Costs",
            "description": f"Die Burn Rate ist um {stats['burn_rate_change']:.1f}% gestiegen. "
                           f"Überprüfe die Nutzungsmuster.",
            "agent": None
        })

    if stats["remaining"] < stats["total_budget"] * 0.2:
        recommendations.append({
            "type": "critical",
            "title": "Low Budget",
            "description": f"Nur noch ${stats['remaining']:.2f} verbleibend ({stats['days_remaining']} Tage). "
                           f"Budget erhöhen oder Nutzung reduzieren.",
            "agent": None
        })

    if prediction.get("prediction_available"):
        recommendations.append({
            "type": "info",
            "title": f"Trend: {prediction['trend'].capitalize()}",
            "description": f"Prognostizierte Kosten für 30 Tage: ${prediction['total_predicted_30d']:.2f}. "
                           f"Confidence: {prediction['confidence']}.",
            "agent": None
        })

    if not recommendations:
        recommendations.append({
            "type": "info",
            "title": "Keine Daten",
            "description": "Noch keine Nutzungsdaten vorhanden. Empfehlungen werden nach einigen Agent-Runs verfügbar.",
            "agent": None
        })

    return {"recommendations": recommendations}


@router.get("/budget/prediction")
def get_budget_prediction(days_ahead: int = Query(default=30, ge=1, le=90)):
    """Gibt Kostenprognose basierend auf linearer Regression zurück."""
    tracker = get_budget_tracker()
    return tracker.predict_costs(days_ahead=days_ahead)


@router.get("/budget/history")
def get_budget_history(period_days: int = Query(default=30, ge=1, le=365)):
    """Gibt historische Tagesdaten zurück."""
    tracker = get_budget_tracker()
    history = tracker.get_historical_data(period_days=period_days)
    return {
        "history": history,
        "period_days": period_days,
        "data_source": "real" if history else "no_data"
    }


@router.get("/budget/projects")
def get_projects():
    """Gibt alle Projekte mit deren Budgets zurück."""
    tracker = get_budget_tracker()
    return {"projects": tracker.get_all_projects()}


@router.post("/budget/projects")
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


@router.delete("/budget/projects/{project_id}")
def delete_project(project_id: str):
    """Löscht ein Projekt."""
    tracker = get_budget_tracker()
    if tracker.delete_project(project_id):
        return {"status": "ok"}
    raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")


@router.get("/budget/projects/{project_id}")
def get_project(project_id: str):
    """Gibt Details zu einem Projekt zurück."""
    tracker = get_budget_tracker()
    project = tracker.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")

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
