# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 01.02.2026
Version: 1.0
Beschreibung: Budget-Reporting und Statistiken.
              Extrahiert aus budget_tracker.py (Regel 1: Max 500 Zeilen)
"""

import requests
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

from budget_config import UsageRecord, BudgetConfig


def get_today_totals(usage_history: List[UsageRecord]) -> Dict[str, Any]:
    """
    Gibt Token- und Kosten-Totals für heute zurück.

    Args:
        usage_history: Nutzungshistorie

    Returns:
        Dictionary mit total_tokens und total_cost für heute
    """
    now = datetime.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    today_records = [
        r for r in usage_history
        if datetime.fromisoformat(r.timestamp) > today_start
    ]

    total_tokens = sum(r.total_tokens for r in today_records)
    total_cost = sum(r.cost_usd for r in today_records)

    return {
        "total_tokens": total_tokens,
        "total_cost": round(total_cost, 6),
        "records_count": len(today_records)
    }


def get_stats(
    usage_history: List[UsageRecord],
    config: BudgetConfig,
    openrouter_api_key: Optional[str],
    period_days: int = 30
) -> Dict[str, Any]:
    """
    Berechnet aktuelle Budget-Statistiken.

    Args:
        usage_history: Nutzungshistorie
        config: Budget-Konfiguration
        openrouter_api_key: API Key für OpenRouter
        period_days: Betrachtungszeitraum in Tagen

    Returns:
        Dictionary mit Budget-Statistiken
    """
    now = datetime.now()
    cutoff = now - timedelta(days=period_days)

    # Filtere nach Zeitraum
    recent_records = [
        r for r in usage_history
        if datetime.fromisoformat(r.timestamp) > cutoff
    ]

    # Gesamtkosten
    total_cost = sum(r.cost_usd for r in recent_records)

    # Kosten heute
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_records = [
        r for r in recent_records
        if datetime.fromisoformat(r.timestamp) > today_start
    ]
    today_cost = sum(r.cost_usd for r in today_records)

    # Durchschnittliche tägliche Kosten
    if recent_records:
        days_with_data = len(set(
            datetime.fromisoformat(r.timestamp).date()
            for r in recent_records
        ))
        daily_avg = total_cost / max(days_with_data, 1)
    else:
        daily_avg = 0.0

    # Burn Rate Änderung (letzte 7 Tage vs davor)
    week_ago = now - timedelta(days=7)
    two_weeks_ago = now - timedelta(days=14)

    last_week = sum(
        r.cost_usd for r in usage_history
        if datetime.fromisoformat(r.timestamp) > week_ago
    )
    prev_week = sum(
        r.cost_usd for r in usage_history
        if two_weeks_ago < datetime.fromisoformat(r.timestamp) <= week_ago
    )

    if prev_week > 0:
        burn_rate_change = round(((last_week - prev_week) / prev_week) * 100, 1)
    else:
        burn_rate_change = 0.0

    # Verbleibendes Budget
    remaining = config.global_monthly_cap - total_cost

    # Projected Runout
    if daily_avg > 0:
        days_remaining = int(remaining / daily_avg)
        projected_runout = (now + timedelta(days=days_remaining)).strftime("%Y-%m-%d")
    else:
        days_remaining = 999
        projected_runout = "N/A"

    # Hole echte OpenRouter-Daten falls verfügbar
    openrouter_data = fetch_openrouter_usage(openrouter_api_key)

    return {
        "total_budget": config.global_monthly_cap,
        "remaining": max(0, round(remaining, 2)),
        "spent_this_period": round(total_cost, 2),
        "spent_today": round(today_cost, 2),
        "burn_rate_daily": round(daily_avg, 2),
        "burn_rate_change": burn_rate_change,
        "projected_runout": projected_runout,
        "days_remaining": max(0, days_remaining),
        "total_records": len(recent_records),
        "period_days": period_days,
        "openrouter_data": openrouter_data,
        "data_source": "real" if len(usage_history) > 0 else "no_data"
    }


def get_costs_by_agent(usage_history: List[UsageRecord], period_days: int = 7) -> List[Dict[str, Any]]:
    """
    Berechnet Kosten pro Agent.

    Args:
        usage_history: Nutzungshistorie
        period_days: Betrachtungszeitraum

    Returns:
        Liste mit Kosten pro Agent
    """
    cutoff = datetime.now() - timedelta(days=period_days)
    recent_records = [
        r for r in usage_history
        if datetime.fromisoformat(r.timestamp) > cutoff
    ]

    if not recent_records:
        return []

    # Aggregiere nach Agent
    agent_costs: Dict[str, Dict] = {}
    for record in recent_records:
        if record.agent not in agent_costs:
            agent_costs[record.agent] = {
                "name": record.agent,
                "role": record.agent.lower().replace(" ", "_"),
                "cost": 0.0,
                "tokens": 0,
                "calls": 0
            }
        agent_costs[record.agent]["cost"] += record.cost_usd
        agent_costs[record.agent]["tokens"] += record.total_tokens
        agent_costs[record.agent]["calls"] += 1

    # Berechne Prozentsätze
    max_cost = max(a["cost"] for a in agent_costs.values()) if agent_costs else 1

    result = []
    for agent_data in sorted(agent_costs.values(), key=lambda x: x["cost"], reverse=True):
        result.append({
            "name": agent_data["name"],
            "role": agent_data["role"],
            "cost": round(agent_data["cost"], 2),
            "tokens": agent_data["tokens"],
            "calls": agent_data["calls"],
            "percentage": round((agent_data["cost"] / max_cost) * 100, 1) if max_cost > 0 else 0
        })

    return result


def get_hourly_heatmap(usage_history: List[UsageRecord], period_days: int = 1) -> Dict[str, Any]:
    """
    Erstellt eine Heatmap der Token-Nutzung nach Stunde und Agent.

    Args:
        usage_history: Nutzungshistorie
        period_days: Betrachtungszeitraum

    Returns:
        Heatmap-Daten
    """
    cutoff = datetime.now() - timedelta(days=period_days)
    recent_records = [
        r for r in usage_history
        if datetime.fromisoformat(r.timestamp) > cutoff
    ]

    if not recent_records:
        return {"agents": [], "hours": list(range(24)), "data": []}

    # Sammle alle Agenten
    agents = sorted(set(r.agent for r in recent_records))

    # Initialisiere Heatmap
    heatmap: Dict[str, List[int]] = {agent: [0] * 24 for agent in agents}

    # Fülle mit Token-Counts
    for record in recent_records:
        hour = datetime.fromisoformat(record.timestamp).hour
        heatmap[record.agent][hour] += record.total_tokens

    # Normalisiere auf 0-1
    all_values = [v for row in heatmap.values() for v in row if v > 0]
    max_val = max(all_values) if all_values else 1

    data = []
    for agent in agents:
        normalized = [round(v / max_val, 2) if max_val > 0 else 0 for v in heatmap[agent]]
        data.append(normalized)

    return {
        "agents": agents,
        "hours": list(range(24)),
        "data": data
    }


def get_historical_data(usage_history: List[UsageRecord], period_days: int = 30) -> List[Dict[str, Any]]:
    """
    Gibt historische Tagesdaten zurück.

    Args:
        usage_history: Nutzungshistorie
        period_days: Anzahl Tage

    Returns:
        Liste mit täglichen Aggregaten
    """
    cutoff = datetime.now() - timedelta(days=period_days)

    # Aggregiere nach Tag
    daily_data: Dict[str, Dict] = {}

    for record in usage_history:
        record_date = datetime.fromisoformat(record.timestamp)
        if record_date < cutoff:
            continue

        date_str = record_date.date().isoformat()
        if date_str not in daily_data:
            daily_data[date_str] = {
                "date": date_str,
                "cost": 0.0,
                "tokens": 0,
                "calls": 0,
                "agents": set()
            }

        daily_data[date_str]["cost"] += record.cost_usd
        daily_data[date_str]["tokens"] += record.total_tokens
        daily_data[date_str]["calls"] += 1
        daily_data[date_str]["agents"].add(record.agent)

    # Konvertiere zu Liste
    result = []
    for date_str in sorted(daily_data.keys()):
        data = daily_data[date_str]
        result.append({
            "date": data["date"],
            "cost": round(data["cost"], 2),
            "tokens": data["tokens"],
            "calls": data["calls"],
            "active_agents": len(data["agents"])
        })

    return result


def fetch_openrouter_usage(api_key: Optional[str]) -> Optional[Dict]:
    """
    Holt echte Nutzungsdaten von der OpenRouter API.

    Args:
        api_key: OpenRouter API Key

    Returns:
        Usage-Daten von OpenRouter oder None bei Fehler
    """
    if not api_key:
        return None

    try:
        response = requests.get(
            "https://openrouter.ai/api/v1/auth/key",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10
        )

        if response.status_code == 200:
            return response.json()
        return None

    except Exception:
        return None
