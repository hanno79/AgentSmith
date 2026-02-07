# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 01.02.2026
Version: 1.0
Beschreibung: Budget-Alerts - Slack, Discord und Webhook-Benachrichtigungen.
              Extrahiert aus budget_tracker.py (Regel 1: Max 500 Zeilen)
"""

import time
import requests
import logging
from datetime import datetime
from typing import Dict, Any, Optional, Callable, Set

from budget_config import BudgetConfig

logger = logging.getLogger(__name__)


class AlertManager:
    """Verwaltet Budget-Alerts und Benachrichtigungen."""

    def __init__(self, config: BudgetConfig):
        """
        Initialisiert den AlertManager.

        Args:
            config: Budget-Konfiguration
        """
        self.config = config
        self._sent_alerts: Set[str] = set()
        self.on_alert: Optional[Callable[[str, str, Dict], None]] = None

    def check_alerts(self, stats: Dict[str, Any]) -> None:
        """
        Prüft Budget-Schwellen und sendet Alerts.

        Args:
            stats: Aktuelle Budget-Statistiken
        """
        if stats["total_budget"] <= 0:
            return

        usage_percent = ((stats["total_budget"] - stats["remaining"]) / stats["total_budget"]) * 100

        for threshold in self.config.alert_thresholds:
            alert_key = f"threshold_{threshold}"

            if usage_percent >= threshold and alert_key not in self._sent_alerts:
                self.send_alert(
                    level="warning" if threshold < 90 else "critical",
                    title=f"Budget Alert: {threshold}% erreicht",
                    message=f"Das Budget hat {threshold}% erreicht. Verbleibend: ${stats['remaining']:.2f}",
                    data={"threshold": threshold, "usage_percent": usage_percent, "remaining": stats["remaining"]}
                )
                self._sent_alerts.add(alert_key)

    def send_alert(self, level: str, title: str, message: str, data: Dict) -> None:
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

    def _send_slack_alert(self, level: str, title: str, message: str, data: Dict) -> None:
        """
        Sendet Alert an Slack.

        Args:
            level: Alert-Level
            title: Alert-Titel
            message: Alert-Nachricht
            data: Zusätzliche Daten
        """
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
            response = requests.post(
                self.config.slack_webhook_url, json=payload, timeout=5
            )
            if not response.ok:
                logger.warning(
                    "Slack Alert HTTP %s: %s",
                    response.status_code,
                    getattr(response, "text", response.reason) or response.reason,
                )
        except Exception as e:
            logger.warning("Slack Alert fehlgeschlagen: %s", e)

    def _send_discord_alert(self, level: str, title: str, message: str, data: Dict) -> None:
        """
        Sendet Alert an Discord.

        Args:
            level: Alert-Level
            title: Alert-Titel
            message: Alert-Nachricht
            data: Zusätzliche Daten
        """
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
            response = requests.post(
                self.config.discord_webhook_url, json=payload, timeout=5
            )
            if not (200 <= getattr(response, "status_code", 0) < 300):
                logger.warning(
                    "Discord Alert HTTP %s: %s",
                    getattr(response, "status_code", "?"),
                    getattr(response, "text", "") or getattr(response, "reason", ""),
                )
        except Exception as e:
            logger.warning("Discord Alert fehlgeschlagen: %s", e)

    def reset_alerts(self) -> None:
        """Setzt alle gesendeten Alerts zurück (z.B. bei neuem Monat)."""
        self._sent_alerts.clear()
