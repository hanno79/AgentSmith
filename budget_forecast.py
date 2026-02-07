# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 01.02.2026
Version: 1.0
Beschreibung: Budget-Prognose und Trend-Analyse.
              Extrahiert aus budget_tracker.py (Regel 1: Max 500 Zeilen)
"""

import logging
import statistics
from datetime import datetime, timedelta
from typing import Dict, List, Any

from budget_config import UsageRecord

logger = logging.getLogger(__name__)


def predict_costs(usage_history: List[UsageRecord], days_ahead: int = 30) -> Dict[str, Any]:
    """
    Prognostiziert zukünftige Kosten mit linearer Regression.

    Args:
        usage_history: Nutzungshistorie
        days_ahead: Tage in die Zukunft

    Returns:
        Prognose-Daten
    """
    if len(usage_history) < 7:
        return {
            "prediction_available": False,
            "reason": "Nicht genug Daten (mindestens 7 Tage benötigt)"
        }

    # Aggregiere tägliche Kosten
    daily_costs: Dict[str, float] = {}
    for record in usage_history:
        date = datetime.fromisoformat(record.timestamp).date().isoformat()
        daily_costs[date] = daily_costs.get(date, 0) + record.cost_usd

    if len(daily_costs) < 7:
        return {
            "prediction_available": False,
            "reason": f"Nur {len(daily_costs)} Tage mit Daten verfügbar"
        }

    # Sortiere nach Datum
    sorted_dates = sorted(daily_costs.keys())
    costs = [daily_costs[d] for d in sorted_dates]

    # Lineare Regression
    n = len(costs)
    x = list(range(n))
    x_mean = sum(x) / n
    y_mean = sum(costs) / n

    numerator = sum((x[i] - x_mean) * (costs[i] - y_mean) for i in range(n))
    denominator = sum((x[i] - x_mean) ** 2 for i in range(n))

    if denominator == 0:
        slope = 0
    else:
        slope = numerator / denominator

    intercept = y_mean - slope * x_mean

    # Prognose
    predictions = []
    today = datetime.now().date()
    for i in range(days_ahead):
        future_date = today + timedelta(days=i)
        predicted_cost = intercept + slope * (n + i)
        predictions.append({
            "date": future_date.isoformat(),
            "predicted_cost": round(max(0, predicted_cost), 2)
        })

    # Berechne Trend
    trend = _calculate_trend(costs)

    return {
        "prediction_available": True,
        "trend": trend,
        "slope_per_day": round(slope, 4),
        "predictions": predictions,
        "total_predicted_30d": round(sum(p["predicted_cost"] for p in predictions[:30]), 2),
        "confidence": "low" if n < 14 else "medium" if n < 30 else "high"
    }


def _calculate_trend(costs: List[float]) -> str:
    """
    Berechnet den Trend basierend auf den Kosten.

    Args:
        costs: Liste der täglichen Kosten

    Returns:
        Trend-String: "rising", "falling", "stable", "unknown"
    """
    if len(costs) < 2:
        return "unknown"

    recent_avg = statistics.mean(costs[-7:]) if len(costs) >= 7 else statistics.mean(costs)
    older_avg = statistics.mean(costs[:-7]) if len(costs) > 7 else costs[0]

    if recent_avg > older_avg * 1.1:
        return "rising"
    elif recent_avg < older_avg * 0.9:
        return "falling"
    else:
        return "stable"


def calculate_burn_rate(usage_history: List[UsageRecord], days: int = 7) -> Dict[str, Any]:  # noqa: C901
    """
    Berechnet die aktuelle Burn-Rate.

    Args:
        usage_history: Nutzungshistorie
        days: Betrachtungszeitraum

    Returns:
        Burn-Rate Statistiken
    """
    now = datetime.now()
    cutoff = now - timedelta(days=days)
    recent_costs = 0.0
    for r in usage_history:
        try:
            ts = datetime.fromisoformat(r.timestamp)
            if ts > cutoff:
                recent_costs += r.cost_usd
        except (ValueError, TypeError) as e:
            logger.error("Ungültiger Timestamp in UsageRecord: %s (Record: %s)", e, getattr(r, "timestamp", r))

    daily_rate = recent_costs / days if days > 0 else 0
    weekly_rate = daily_rate * 7
    monthly_rate = daily_rate * 30

    return {
        "period_days": days,
        "total_cost": round(recent_costs, 2),
        "daily_rate": round(daily_rate, 2),
        "weekly_rate": round(weekly_rate, 2),
        "monthly_rate": round(monthly_rate, 2)
    }
