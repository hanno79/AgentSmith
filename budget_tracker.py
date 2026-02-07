# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 01.02.2026
Version: 2.0
Beschreibung: Budget Tracker - Orchestrator (refaktoriert).
              REFAKTORIERT: Aus 824 Zeilen → 7 Module + Orchestrator

              Module:
              - budget_config.py: Dataclasses, MODEL_PRICES
              - budget_persistence.py: Laden/Speichern
              - budget_alerts.py: Slack, Discord Alerts
              - budget_projects.py: Projekt-Management
              - budget_reporting.py: Statistiken, Heatmaps
              - budget_forecast.py: Prognosen, Trends

              ÄNDERUNG 01.02.2026: Aufsplitten in 7 Module (Regel 1: Max 500 Zeilen).
"""

import os
import threading
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
from dataclasses import asdict

# =========================================================================
# Re-exports aus Modulen
# =========================================================================
from budget_config import (
    UsageRecord,
    ProjectBudget,
    BudgetConfig,
    MODEL_PRICES,
    MODEL_ALIASES
)

from budget_persistence import (
    load_usage_history,
    save_usage_history,
    load_config,
    save_config,
    load_projects,
    save_projects
)

from budget_alerts import AlertManager

from budget_projects import (
    create_project as _create_project,
    get_project as _get_project,
    get_all_projects as _get_all_projects,
    delete_project as _delete_project,
    update_project_costs
)

from budget_reporting import (
    get_today_totals as _get_today_totals,
    get_stats as _get_stats,
    get_costs_by_agent as _get_costs_by_agent,
    get_hourly_heatmap as _get_hourly_heatmap,
    get_historical_data as _get_historical_data
)

from budget_forecast import predict_costs as _predict_costs


class BudgetTracker:
    """
    Zentrales Budget-Tracking (Orchestrator).

    Delegiert an spezialisierte Module für:
    - Persistenz
    - Alerts
    - Projekt-Management
    - Reporting
    - Prognosen
    """

    # Re-export für Rückwärtskompatibilität
    MODEL_PRICES = MODEL_PRICES

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
        self.usage_history: List[UsageRecord] = load_usage_history(self.usage_file)
        self.config: BudgetConfig = load_config(self.config_file)
        self.projects: Dict[str, ProjectBudget] = load_projects(self.projects_file)

        # OpenRouter API Key
        self.openrouter_api_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")

        # Alert Manager
        self._alert_manager = AlertManager(self.config)

        # Callback für Alerts (Rückwärtskompatibilität)
        self._on_alert: Optional[Callable[[str, str, Dict], None]] = None

    @property
    def on_alert(self) -> Optional[Callable]:
        return self._on_alert

    @on_alert.setter
    def on_alert(self, callback: Optional[Callable[[str, str, Dict], None]]):
        self._on_alert = callback
        self._alert_manager.on_alert = callback

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
        # Normalisiere Modell-Namen
        normalized_model = model.replace("openrouter/", "") if model else ""
        normalized_model = MODEL_ALIASES.get(normalized_model, normalized_model)

        prices = MODEL_PRICES.get(normalized_model, {"input": 0.0, "output": 0.0})

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
        from datetime import datetime

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
        save_usage_history(self.usage_history, self.usage_file)

        # Update Projekt-Kosten falls vorhanden
        if project_id and project_id in self.projects:
            update_project_costs(self.projects, self.projects_file, project_id, cost)

        # Prüfe Budget-Alerts
        stats = self.get_stats()
        self._alert_manager.check_alerts(stats)

        return record

    # =========================================================================
    # Reporting (delegiert)
    # =========================================================================

    def get_today_totals(self) -> Dict[str, Any]:
        """Gibt Token- und Kosten-Totals für heute zurück."""
        return _get_today_totals(self.usage_history)

    def get_stats(self, period_days: int = 30) -> Dict[str, Any]:
        """Berechnet aktuelle Budget-Statistiken."""
        return _get_stats(self.usage_history, self.config, self.openrouter_api_key, period_days)

    def get_costs_by_agent(self, period_days: int = 7) -> List[Dict[str, Any]]:
        """Berechnet Kosten pro Agent."""
        return _get_costs_by_agent(self.usage_history, period_days)

    def get_hourly_heatmap(self, period_days: int = 1) -> Dict[str, Any]:
        """Erstellt eine Heatmap der Token-Nutzung."""
        return _get_hourly_heatmap(self.usage_history, period_days)

    def get_historical_data(self, period_days: int = 30) -> List[Dict[str, Any]]:
        """Gibt historische Tagesdaten zurück."""
        return _get_historical_data(self.usage_history, period_days)

    # =========================================================================
    # Forecast (delegiert)
    # =========================================================================

    def predict_costs(self, days_ahead: int = 30) -> Dict[str, Any]:
        """Prognostiziert zukünftige Kosten."""
        return _predict_costs(self.usage_history, days_ahead)

    # =========================================================================
    # Projekt-Management (delegiert)
    # =========================================================================

    def create_project(self, project_id: str, name: str, budget: float) -> ProjectBudget:
        """Erstellt ein neues Projekt mit eigenem Budget."""
        return _create_project(self.projects, self.projects_file, project_id, name, budget)

    def get_project(self, project_id: str) -> Optional[ProjectBudget]:
        """Gibt ein Projekt zurück."""
        return _get_project(self.projects, project_id)

    def get_all_projects(self) -> List[Dict[str, Any]]:
        """Gibt alle Projekte mit aktuellen Kosten zurück."""
        return _get_all_projects(self.projects, self.usage_history)

    def delete_project(self, project_id: str) -> bool:
        """Löscht ein Projekt."""
        return _delete_project(self.projects, self.projects_file, project_id)

    # =========================================================================
    # Config Management
    # =========================================================================

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

        save_config(self.config, self.config_file)

    def get_config(self) -> Dict[str, Any]:
        """Gibt die aktuelle Konfiguration zurück."""
        return asdict(self.config)

    def fetch_openrouter_usage(self) -> Optional[Dict]:
        """Holt echte Nutzungsdaten von der OpenRouter API."""
        from budget_reporting import fetch_openrouter_usage
        return fetch_openrouter_usage(self.openrouter_api_key)


# =========================================================================
# Singleton-Instance mit Thread-Sicherheit
# =========================================================================
_budget_tracker: Optional[BudgetTracker] = None
_budget_tracker_lock = threading.Lock()


def get_budget_tracker() -> BudgetTracker:
    """Gibt die Singleton-Instanz des BudgetTrackers zurück (thread-safe)."""
    global _budget_tracker
    if _budget_tracker is None:
        with _budget_tracker_lock:
            # Double-checked locking pattern
            if _budget_tracker is None:
                _budget_tracker = BudgetTracker()
    return _budget_tracker


# =========================================================================
# Expliziter __all__ Export
# =========================================================================
__all__ = [
    # Klasse
    'BudgetTracker',
    'get_budget_tracker',
    # Dataclasses
    'UsageRecord',
    'ProjectBudget',
    'BudgetConfig',
    # Konstanten
    'MODEL_PRICES',
    'MODEL_ALIASES'
]
