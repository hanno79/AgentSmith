# -*- coding: utf-8 -*-
"""
Budget Tracker: Echtes Kosten-Tracking mit OpenRouter API Integration.

Features:
- Echte Kosten von OpenRouter API
- Historische Daten mit Persistenz
- Kostenprognose mit linearer Regression
- Alert-System (Slack/Discord Webhooks)
- Per-Project Budget Tracking
"""

import os
import json
import time
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, asdict, field
from pathlib import Path
import statistics


@dataclass
class UsageRecord:
    """Einzelner Nutzungseintrag."""
    timestamp: str
    agent: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_usd: float
    project_id: Optional[str] = None
    task_description: Optional[str] = None


@dataclass
class ProjectBudget:
    """Budget für ein einzelnes Projekt."""
    project_id: str
    name: str
    total_budget: float
    spent: float = 0.0
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    alerts_sent: List[str] = field(default_factory=list)


@dataclass
class BudgetConfig:
    """Budget-Konfiguration."""
    global_monthly_cap: float = 10000.0
    global_daily_cap: float = 500.0
    auto_pause: bool = True
    alert_thresholds: List[int] = field(default_factory=lambda: [50, 75, 90, 100])
    slack_webhook_url: Optional[str] = None
    discord_webhook_url: Optional[str] = None
    email_alerts: bool = False
    email_recipients: List[str] = field(default_factory=list)


class BudgetTracker:
    """
    Zentrales Budget-Tracking mit echten Daten.

    Speichert alle Nutzungsdaten persistent und berechnet
    echte Kosten basierend auf OpenRouter API.
    """

    # OpenRouter Modell-Preise (pro 1M Tokens)
    MODEL_PRICES = {
        # Free Tier
        "openrouter/meta-llama/llama-3.3-70b-instruct:free": {"input": 0.0, "output": 0.0},
        "openrouter/qwen/qwen3-coder:free": {"input": 0.0, "output": 0.0},
        "openrouter/google/gemma-3-27b-it:free": {"input": 0.0, "output": 0.0},
        "openrouter/mistralai/mixtral-8x7b-instruct:free": {"input": 0.0, "output": 0.0},
        "openrouter/nvidia/nemotron-3-nano-30b-a3b:free": {"input": 0.0, "output": 0.0},
        # Paid Tier
        "openrouter/anthropic/claude-sonnet-4": {"input": 3.0, "output": 15.0},
        "openrouter/anthropic/claude-haiku-4": {"input": 0.25, "output": 1.25},
        "openrouter/openai/gpt-4-turbo": {"input": 10.0, "output": 30.0},
        "openrouter/openai/gpt-4o": {"input": 2.5, "output": 10.0},
    }

    def __init__(self, data_dir: str = None):
        """
        Initialisiert den BudgetTracker.

        Args:
            data_dir: Verzeichnis für Datenpersistenz (default: ./budget_data)
        """
        if data_dir is None:
            data_dir = os.path.join(os.path.dirname(__file__), "budget_data")

        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Dateipfade
        self.usage_file = self.data_dir / "usage_history.json"
        self.config_file = self.data_dir / "budget_config.json"
        self.projects_file = self.data_dir / "projects.json"

        # Lade persistierte Daten
        self.usage_history: List[UsageRecord] = self._load_usage_history()
        self.config: BudgetConfig = self._load_config()
        self.projects: Dict[str, ProjectBudget] = self._load_projects()

        # OpenRouter API Key
        self.openrouter_api_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")

        # Callback für Alerts
        self.on_alert: Optional[Callable[[str, str, Dict], None]] = None

    def _load_usage_history(self) -> List[UsageRecord]:
        """Lädt Nutzungshistorie aus Datei."""
        if self.usage_file.exists():
            try:
                with open(self.usage_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return [UsageRecord(**record) for record in data]
            except Exception as e:
                print(f"Fehler beim Laden der Usage History: {e}")
        return []

    def _save_usage_history(self):
        """Speichert Nutzungshistorie in Datei."""
        with open(self.usage_file, "w", encoding="utf-8") as f:
            json.dump([asdict(r) for r in self.usage_history], f, indent=2)

    def _load_config(self) -> BudgetConfig:
        """Lädt Budget-Konfiguration aus Datei."""
        if self.config_file.exists():
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return BudgetConfig(**data)
            except Exception as e:
                print(f"Fehler beim Laden der Config: {e}")
        return BudgetConfig()

    def _save_config(self):
        """Speichert Budget-Konfiguration in Datei."""
        with open(self.config_file, "w", encoding="utf-8") as f:
            json.dump(asdict(self.config), f, indent=2)

    def _load_projects(self) -> Dict[str, ProjectBudget]:
        """Lädt Projekte aus Datei."""
        if self.projects_file.exists():
            try:
                with open(self.projects_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return {k: ProjectBudget(**v) for k, v in data.items()}
            except Exception as e:
                print(f"Fehler beim Laden der Projekte: {e}")
        return {}

    def _save_projects(self):
        """Speichert Projekte in Datei."""
        with open(self.projects_file, "w", encoding="utf-8") as f:
            json.dump({k: asdict(v) for k, v in self.projects.items()}, f, indent=2)

    def calculate_cost(self, model: str, prompt_tokens: int, completion_tokens: int) -> float:
        """
        Berechnet die Kosten für einen API-Aufruf.

        Args:
            model: Modell-ID
            prompt_tokens: Anzahl Input-Tokens
            completion_tokens: Anzahl Output-Tokens

        Returns:
            Kosten in USD
        """
        prices = self.MODEL_PRICES.get(model, {"input": 0.0, "output": 0.0})

        # Preise sind pro 1M Tokens
        input_cost = (prompt_tokens / 1_000_000) * prices["input"]
        output_cost = (completion_tokens / 1_000_000) * prices["output"]

        return round(input_cost + output_cost, 6)

    def record_usage(
        self,
        agent: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        project_id: Optional[str] = None,
        task_description: Optional[str] = None
    ) -> UsageRecord:
        """
        Zeichnet eine API-Nutzung auf.

        Args:
            agent: Name des Agenten
            model: Verwendetes Modell
            prompt_tokens: Input-Tokens
            completion_tokens: Output-Tokens
            project_id: Optionale Projekt-ID
            task_description: Optionale Beschreibung

        Returns:
            Der erstellte UsageRecord
        """
        cost = self.calculate_cost(model, prompt_tokens, completion_tokens)
        total_tokens = prompt_tokens + completion_tokens

        record = UsageRecord(
            timestamp=datetime.now().isoformat(),
            agent=agent,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            cost_usd=cost,
            project_id=project_id,
            task_description=task_description
        )

        self.usage_history.append(record)
        self._save_usage_history()

        # Update Projekt-Kosten falls vorhanden
        if project_id and project_id in self.projects:
            self.projects[project_id].spent += cost
            self._save_projects()

        # Prüfe Budget-Alerts
        self._check_alerts()

        return record

    def fetch_openrouter_usage(self) -> Optional[Dict]:
        """
        Holt echte Nutzungsdaten von der OpenRouter API.

        Returns:
            Usage-Daten von OpenRouter oder None bei Fehler
        """
        if not self.openrouter_api_key:
            return None

        try:
            # OpenRouter Usage API
            response = requests.get(
                "https://openrouter.ai/api/v1/auth/key",
                headers={"Authorization": f"Bearer {self.openrouter_api_key}"},
                timeout=10
            )

            if response.status_code == 200:
                return response.json()
            else:
                print(f"OpenRouter API Error: {response.status_code}")
                return None

        except Exception as e:
            print(f"Fehler beim Abrufen der OpenRouter Usage: {e}")
            return None

    def get_stats(self, period_days: int = 30) -> Dict[str, Any]:
        """
        Berechnet aktuelle Budget-Statistiken.

        Args:
            period_days: Betrachtungszeitraum in Tagen

        Returns:
            Dictionary mit Budget-Statistiken
        """
        now = datetime.now()
        cutoff = now - timedelta(days=period_days)

        # Filtere nach Zeitraum
        recent_records = [
            r for r in self.usage_history
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
            r.cost_usd for r in self.usage_history
            if datetime.fromisoformat(r.timestamp) > week_ago
        )
        prev_week = sum(
            r.cost_usd for r in self.usage_history
            if two_weeks_ago < datetime.fromisoformat(r.timestamp) <= week_ago
        )

        if prev_week > 0:
            burn_rate_change = round(((last_week - prev_week) / prev_week) * 100, 1)
        else:
            burn_rate_change = 0.0

        # Verbleibendes Budget
        remaining = self.config.global_monthly_cap - total_cost

        # Projected Runout
        if daily_avg > 0:
            days_remaining = int(remaining / daily_avg)
            projected_runout = (now + timedelta(days=days_remaining)).strftime("%Y-%m-%d")
        else:
            days_remaining = 999
            projected_runout = "N/A"

        # Hole echte OpenRouter-Daten falls verfügbar
        openrouter_data = self.fetch_openrouter_usage()

        return {
            "total_budget": self.config.global_monthly_cap,
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
            "data_source": "real" if len(self.usage_history) > 0 else "no_data"
        }

    def get_costs_by_agent(self, period_days: int = 7) -> List[Dict[str, Any]]:
        """
        Berechnet Kosten pro Agent.

        Args:
            period_days: Betrachtungszeitraum

        Returns:
            Liste mit Kosten pro Agent
        """
        cutoff = datetime.now() - timedelta(days=period_days)
        recent_records = [
            r for r in self.usage_history
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
        total_cost = sum(a["cost"] for a in agent_costs.values())
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

    def get_hourly_heatmap(self, period_days: int = 1) -> Dict[str, Any]:
        """
        Erstellt eine Heatmap der Token-Nutzung nach Stunde und Agent.

        Args:
            period_days: Betrachtungszeitraum

        Returns:
            Heatmap-Daten
        """
        cutoff = datetime.now() - timedelta(days=period_days)
        recent_records = [
            r for r in self.usage_history
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

    def predict_costs(self, days_ahead: int = 30) -> Dict[str, Any]:
        """
        Prognostiziert zukünftige Kosten mit linearer Regression.

        Args:
            days_ahead: Tage in die Zukunft

        Returns:
            Prognose-Daten
        """
        if len(self.usage_history) < 7:
            return {
                "prediction_available": False,
                "reason": "Nicht genug Daten (mindestens 7 Tage benötigt)"
            }

        # Aggregiere tägliche Kosten
        daily_costs: Dict[str, float] = {}
        for record in self.usage_history:
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

        # Lineare Regression (einfach)
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
        if len(costs) >= 2:
            recent_avg = statistics.mean(costs[-7:]) if len(costs) >= 7 else statistics.mean(costs)
            older_avg = statistics.mean(costs[:-7]) if len(costs) > 7 else costs[0]
            trend = "rising" if recent_avg > older_avg * 1.1 else "falling" if recent_avg < older_avg * 0.9 else "stable"
        else:
            trend = "unknown"

        return {
            "prediction_available": True,
            "trend": trend,
            "slope_per_day": round(slope, 4),
            "predictions": predictions,
            "total_predicted_30d": round(sum(p["predicted_cost"] for p in predictions[:30]), 2),
            "confidence": "low" if n < 14 else "medium" if n < 30 else "high"
        }

    def _check_alerts(self):
        """Prüft Budget-Schwellen und sendet Alerts."""
        stats = self.get_stats()

        if stats["total_budget"] <= 0:
            return

        usage_percent = ((stats["total_budget"] - stats["remaining"]) / stats["total_budget"]) * 100

        for threshold in self.config.alert_thresholds:
            alert_key = f"threshold_{threshold}"

            if usage_percent >= threshold and alert_key not in getattr(self, '_sent_alerts', set()):
                self._send_alert(
                    level="warning" if threshold < 90 else "critical",
                    title=f"Budget Alert: {threshold}% erreicht",
                    message=f"Das Budget hat {threshold}% erreicht. Verbleibend: ${stats['remaining']:.2f}",
                    data={"threshold": threshold, "usage_percent": usage_percent, "remaining": stats["remaining"]}
                )

                if not hasattr(self, '_sent_alerts'):
                    self._sent_alerts = set()
                self._sent_alerts.add(alert_key)

    def _send_alert(self, level: str, title: str, message: str, data: Dict):
        """
        Sendet einen Alert über konfigurierte Kanäle.

        Args:
            level: "info", "warning", "critical"
            title: Alert-Titel
            message: Alert-Nachricht
            data: Zusätzliche Daten
        """
        # Callback aufrufen falls vorhanden
        if self.on_alert:
            self.on_alert(level, title, data)

        # Slack Webhook
        if self.config.slack_webhook_url:
            self._send_slack_alert(level, title, message, data)

        # Discord Webhook
        if self.config.discord_webhook_url:
            self._send_discord_alert(level, title, message, data)

    def _send_slack_alert(self, level: str, title: str, message: str, data: Dict):
        """Sendet Alert an Slack."""
        color = "#ff0000" if level == "critical" else "#ffaa00" if level == "warning" else "#36a64f"

        payload = {
            "attachments": [{
                "color": color,
                "title": f":warning: {title}",
                "text": message,
                "fields": [
                    {"title": k, "value": str(v), "short": True}
                    for k, v in data.items()
                ],
                "footer": "Agent Smith Budget Tracker",
                "ts": int(time.time())
            }]
        }

        try:
            requests.post(self.config.slack_webhook_url, json=payload, timeout=5)
        except Exception as e:
            print(f"Slack Alert fehlgeschlagen: {e}")

    def _send_discord_alert(self, level: str, title: str, message: str, data: Dict):
        """Sendet Alert an Discord."""
        color = 0xff0000 if level == "critical" else 0xffaa00 if level == "warning" else 0x36a64f

        payload = {
            "embeds": [{
                "title": f"⚠️ {title}",
                "description": message,
                "color": color,
                "fields": [
                    {"name": k, "value": str(v), "inline": True}
                    for k, v in data.items()
                ],
                "footer": {"text": "Agent Smith Budget Tracker"},
                "timestamp": datetime.now().isoformat()
            }]
        }

        try:
            requests.post(self.config.discord_webhook_url, json=payload, timeout=5)
        except Exception as e:
            print(f"Discord Alert fehlgeschlagen: {e}")

    # ===== Projekt-Management =====

    def create_project(self, project_id: str, name: str, budget: float) -> ProjectBudget:
        """
        Erstellt ein neues Projekt mit eigenem Budget.

        Args:
            project_id: Eindeutige Projekt-ID
            name: Anzeigename
            budget: Budget in USD

        Returns:
            Das erstellte Projekt
        """
        project = ProjectBudget(
            project_id=project_id,
            name=name,
            total_budget=budget
        )
        self.projects[project_id] = project
        self._save_projects()
        return project

    def get_project(self, project_id: str) -> Optional[ProjectBudget]:
        """Gibt ein Projekt zurück."""
        return self.projects.get(project_id)

    def get_all_projects(self) -> List[Dict[str, Any]]:
        """Gibt alle Projekte mit aktuellen Kosten zurück."""
        result = []
        for project in self.projects.values():
            # Berechne aktuelle Kosten
            project_costs = sum(
                r.cost_usd for r in self.usage_history
                if r.project_id == project.project_id
            )

            result.append({
                "project_id": project.project_id,
                "name": project.name,
                "total_budget": project.total_budget,
                "spent": round(project_costs, 2),
                "remaining": round(project.total_budget - project_costs, 2),
                "percentage_used": round((project_costs / project.total_budget) * 100, 1) if project.total_budget > 0 else 0,
                "created_at": project.created_at
            })

        return result

    def delete_project(self, project_id: str) -> bool:
        """Löscht ein Projekt."""
        if project_id in self.projects:
            del self.projects[project_id]
            self._save_projects()
            return True
        return False

    # ===== Config Management =====

    def update_config(
        self,
        monthly_cap: Optional[float] = None,
        daily_cap: Optional[float] = None,
        auto_pause: Optional[bool] = None,
        slack_webhook: Optional[str] = None,
        discord_webhook: Optional[str] = None,
        alert_thresholds: Optional[List[int]] = None
    ):
        """Aktualisiert die Budget-Konfiguration."""
        if monthly_cap is not None:
            self.config.global_monthly_cap = monthly_cap
        if daily_cap is not None:
            self.config.global_daily_cap = daily_cap
        if auto_pause is not None:
            self.config.auto_pause = auto_pause
        if slack_webhook is not None:
            self.config.slack_webhook_url = slack_webhook
        if discord_webhook is not None:
            self.config.discord_webhook_url = discord_webhook
        if alert_thresholds is not None:
            self.config.alert_thresholds = alert_thresholds

        self._save_config()

    def get_config(self) -> Dict[str, Any]:
        """Gibt die aktuelle Konfiguration zurück."""
        return asdict(self.config)

    def get_historical_data(self, period_days: int = 30) -> List[Dict[str, Any]]:
        """
        Gibt historische Tagesdaten zurück.

        Args:
            period_days: Anzahl Tage

        Returns:
            Liste mit täglichen Aggregaten
        """
        cutoff = datetime.now() - timedelta(days=period_days)

        # Aggregiere nach Tag
        daily_data: Dict[str, Dict] = {}

        for record in self.usage_history:
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


# Singleton-Instance
_budget_tracker: Optional[BudgetTracker] = None


def get_budget_tracker() -> BudgetTracker:
    """Gibt die Singleton-Instanz des BudgetTrackers zurück."""
    global _budget_tracker
    if _budget_tracker is None:
        _budget_tracker = BudgetTracker()
    return _budget_tracker
