# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 01.02.2026
Version: 1.0
Beschreibung: Budget-Konfiguration und Dataclasses.
              Extrahiert aus budget_tracker.py (Regel 1: Max 500 Zeilen)
"""

from datetime import datetime
from typing import List, Optional
from dataclasses import dataclass, field


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


# ÄNDERUNG 30.01.2026: Vollständige Preisliste für alle genutzten Modelle
# OpenRouter Modell-Preise (pro 1M Tokens)
# Preise OHNE "openrouter/" Prefix - Normalisierung erfolgt in calculate_cost()
MODEL_PRICES = {
    # === FREE TIER ===
    "meta-llama/llama-3.3-70b-instruct:free": {"input": 0.0, "output": 0.0},
    "qwen/qwen3-coder:free": {"input": 0.0, "output": 0.0},
    "google/gemma-3-27b-it:free": {"input": 0.0, "output": 0.0},
    "mistralai/mixtral-8x7b-instruct:free": {"input": 0.0, "output": 0.0},
    "nvidia/nemotron-3-nano-30b-a3b:free": {"input": 0.0, "output": 0.0},
    "deepseek/deepseek-r1-0528:free": {"input": 0.0, "output": 0.0},
    "z-ai/glm-4.5-air:free": {"input": 0.0, "output": 0.0},
    "xiaomi/mimo-v2-flash:free": {"input": 0.0, "output": 0.0},
    "openai/gpt-oss-120b:free": {"input": 0.0, "output": 0.0},

    # === VALUE TIER (preiswert) ===
    "deepseek/deepseek-r1-0528": {"input": 0.55, "output": 2.19},
    "moonshotai/kimi-k2.5": {"input": 0.50, "output": 2.00},
    "google/gemini-2.5-flash": {"input": 0.075, "output": 0.30},
    "qwen/qwen-3": {"input": 0.20, "output": 0.60},
    "z-ai/glm-4.7": {"input": 0.50, "output": 1.50},
    "mistralai/mistral-medium-3.1": {"input": 0.40, "output": 1.20},

    # === PREMIUM TIER ===
    "google/gemini-3-pro": {"input": 1.25, "output": 5.00},
    "anthropic/claude-sonnet-4": {"input": 3.0, "output": 15.0},
    "anthropic/claude-opus-4.5": {"input": 15.0, "output": 75.0},
    "anthropic/claude-haiku-4": {"input": 0.25, "output": 1.25},
    "openai/gpt-4-turbo": {"input": 10.0, "output": 30.0},
    "openai/gpt-4o": {"input": 2.5, "output": 10.0},
    "openai/gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "x-ai/grok-4.1-fast": {"input": 3.0, "output": 15.0},
}

# ÄNDERUNG [31.01.2026]: Alias-Mapping für korrigierte OpenRouter-IDs
MODEL_ALIASES = {
    "anthropic/claude-opus-4.5-thinking": "anthropic/claude-opus-4.5",
    "x-ai/grok-4.1-thinking": "x-ai/grok-4.1-fast"
}
