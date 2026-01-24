# -*- coding: utf-8 -*-
"""
Model Architect Agent: Entscheidet welches Modell für welche Aufgabe optimal ist.

Der Model-Architect analysiert Aufgaben und wählt das optimale LLM-Modell basierend auf:
- Task-Komplexität (Coding erfordert starke Modelle)
- Kosten (Free-Tier bevorzugen wenn möglich)
- Latenz (schnelle Antworten für einfache Tasks)
- Rate-Limit-Status (Fallback bei überlasteten Modellen)
"""

from typing import Dict, Any, List, Optional
from crewai import Agent


# Modell-Eigenschaften für intelligente Auswahl
MODEL_CAPABILITIES = {
    "openrouter/meta-llama/llama-3.3-70b-instruct:free": {
        "name": "Llama 3.3 70B",
        "provider": "Meta",
        "tier": "free",
        "strengths": ["general", "reasoning", "instruction-following"],
        "weaknesses": ["complex-coding"],
        "latency": "medium",
        "cost_per_1k": 0.0,
        "context_window": 128000,
        "best_for": ["orchestration", "review", "research"]
    },
    "openrouter/qwen/qwen3-coder:free": {
        "name": "Qwen3 Coder",
        "provider": "Alibaba",
        "tier": "free",
        "strengths": ["coding", "debugging", "code-review"],
        "weaknesses": ["creative-writing"],
        "latency": "medium",
        "cost_per_1k": 0.0,
        "context_window": 32000,
        "best_for": ["coder", "techstack_architect"]
    },
    "openrouter/google/gemma-3-27b-it:free": {
        "name": "Gemma 3 27B",
        "provider": "Google",
        "tier": "free",
        "strengths": ["creative", "design", "ui-ux"],
        "weaknesses": ["complex-coding"],
        "latency": "fast",
        "cost_per_1k": 0.0,
        "context_window": 8192,
        "best_for": ["designer", "creative-tasks"]
    },
    "openrouter/mistralai/mixtral-8x7b-instruct:free": {
        "name": "Mixtral 8x7B",
        "provider": "Mistral",
        "tier": "free",
        "strengths": ["reasoning", "analysis", "summarization"],
        "weaknesses": ["long-form-content"],
        "latency": "fast",
        "cost_per_1k": 0.0,
        "context_window": 32000,
        "best_for": ["researcher", "analysis"]
    },
    "openrouter/nvidia/nemotron-3-nano-30b-a3b:free": {
        "name": "Nemotron 30B",
        "provider": "NVIDIA",
        "tier": "free",
        "strengths": ["fast-inference", "simple-tasks"],
        "weaknesses": ["complex-reasoning"],
        "latency": "very-fast",
        "cost_per_1k": 0.0,
        "context_window": 4096,
        "best_for": ["simple-orchestration", "quick-tasks"]
    },
    "openrouter/anthropic/claude-sonnet-4": {
        "name": "Claude Sonnet 4",
        "provider": "Anthropic",
        "tier": "paid",
        "strengths": ["coding", "reasoning", "analysis", "safety"],
        "weaknesses": [],
        "latency": "medium",
        "cost_per_1k": 3.0,
        "context_window": 200000,
        "best_for": ["production", "complex-tasks", "security"]
    },
    "openrouter/openai/gpt-4-turbo": {
        "name": "GPT-4 Turbo",
        "provider": "OpenAI",
        "tier": "paid",
        "strengths": ["coding", "reasoning", "creative", "multimodal"],
        "weaknesses": [],
        "latency": "medium",
        "cost_per_1k": 10.0,
        "context_window": 128000,
        "best_for": ["production", "complex-tasks"]
    }
}

# Task-Typen und ihre Anforderungen
TASK_REQUIREMENTS = {
    "coding": {
        "required_strengths": ["coding"],
        "priority_models": ["qwen3-coder", "claude-sonnet", "gpt-4"],
        "complexity": "high"
    },
    "design": {
        "required_strengths": ["creative", "design"],
        "priority_models": ["gemma-3", "claude-sonnet"],
        "complexity": "medium"
    },
    "review": {
        "required_strengths": ["reasoning", "analysis"],
        "priority_models": ["llama-3.3", "mixtral", "claude-sonnet"],
        "complexity": "medium"
    },
    "research": {
        "required_strengths": ["reasoning", "summarization"],
        "priority_models": ["mixtral", "llama-3.3"],
        "complexity": "low"
    },
    "orchestration": {
        "required_strengths": ["instruction-following", "reasoning"],
        "priority_models": ["llama-3.3", "nemotron"],
        "complexity": "low"
    },
    "security": {
        "required_strengths": ["analysis", "reasoning"],
        "priority_models": ["llama-3.3", "claude-sonnet"],
        "complexity": "high"
    },
    "database": {
        "required_strengths": ["reasoning", "coding"],
        "priority_models": ["llama-3.3", "qwen3-coder"],
        "complexity": "medium"
    }
}


def create_model_architect(config: Dict[str, Any]) -> Agent:
    """
    Erstellt den Model-Architect Agenten.

    Der Model-Architect ist verantwortlich für:
    - Analyse der Aufgabentypen
    - Auswahl optimaler Modelle basierend auf Task-Anforderungen
    - Berücksichtigung von Kosten und Rate-Limits

    Args:
        config: Anwendungskonfiguration mit mode und models

    Returns:
        Konfigurierte CrewAI Agent-Instanz
    """
    mode = config.get("mode", "test")
    model = config.get("models", {}).get(mode, {}).get("meta_orchestrator",
        "openrouter/meta-llama/llama-3.3-70b-instruct:free")

    return Agent(
        role="Model Architect",
        goal=(
            "Analysiere Aufgaben und wähle das optimale LLM-Modell für jeden Agenten. "
            "Berücksichtige dabei: "
            "1) Task-Komplexität - Coding-Aufgaben brauchen spezialisierte Code-Modelle, "
            "2) Kosten - Bevorzuge Free-Tier Modelle wenn die Qualität ausreicht, "
            "3) Latenz - Wähle schnelle Modelle für einfache Tasks, "
            "4) Rate-Limits - Habe Fallback-Optionen bereit."
        ),
        backstory=(
            "Du bist der Model-Architect im Maschinenraum von Agent Smith. "
            "Du kennst die Stärken und Schwächen jedes LLM-Modells genau. "
            "Du weißt, dass Qwen3-Coder exzellent für Code ist, "
            "Gemma für kreative Aufgaben, und Llama für allgemeine Reasoning-Tasks. "
            "Du optimierst für die beste Balance aus Qualität, Kosten und Geschwindigkeit. "
            "Wenn ein Modell rate-limited ist, hast du immer einen Plan B."
        ),
        llm=model,
        verbose=True
    )


def recommend_model_for_task(
    task_type: str,
    prefer_free: bool = True,
    rate_limited_models: Optional[List[str]] = None
) -> str:
    """
    Empfiehlt das optimale Modell für einen bestimmten Task-Typ.

    Args:
        task_type: Art der Aufgabe (coding, design, review, etc.)
        prefer_free: Ob kostenlose Modelle bevorzugt werden sollen
        rate_limited_models: Liste der aktuell rate-limited Modelle

    Returns:
        Modell-ID für den Task
    """
    rate_limited_models = rate_limited_models or []

    # Hole Task-Anforderungen
    requirements = TASK_REQUIREMENTS.get(task_type, TASK_REQUIREMENTS["orchestration"])

    # Filtere verfügbare Modelle
    available_models = []
    for model_id, caps in MODEL_CAPABILITIES.items():
        # Überspringe rate-limited Modelle
        if model_id in rate_limited_models:
            continue

        # Prüfe Tier-Präferenz
        if prefer_free and caps["tier"] != "free":
            continue

        # Prüfe ob Modell die erforderlichen Stärken hat
        has_required_strength = any(
            strength in caps["strengths"]
            for strength in requirements["required_strengths"]
        )

        if has_required_strength:
            available_models.append((model_id, caps))

    if not available_models:
        # Fallback: Nimm irgendein verfügbares Modell
        for model_id, caps in MODEL_CAPABILITIES.items():
            if model_id not in rate_limited_models:
                return model_id

        # Absoluter Fallback
        return "openrouter/meta-llama/llama-3.3-70b-instruct:free"

    # Sortiere nach Latenz (schnellere zuerst)
    latency_order = {"very-fast": 0, "fast": 1, "medium": 2, "slow": 3}
    available_models.sort(key=lambda x: latency_order.get(x[1]["latency"], 2))

    return available_models[0][0]


def get_model_info(model_id: str) -> Optional[Dict[str, Any]]:
    """
    Gibt Informationen über ein Modell zurück.

    Args:
        model_id: OpenRouter Modell-ID

    Returns:
        Dictionary mit Modell-Eigenschaften oder None
    """
    return MODEL_CAPABILITIES.get(model_id)


def get_all_free_models() -> List[Dict[str, Any]]:
    """Gibt alle kostenlosen Modelle zurück."""
    return [
        {"id": model_id, **caps}
        for model_id, caps in MODEL_CAPABILITIES.items()
        if caps["tier"] == "free"
    ]


def get_all_paid_models() -> List[Dict[str, Any]]:
    """Gibt alle kostenpflichtigen Modelle zurück."""
    return [
        {"id": model_id, **caps}
        for model_id, caps in MODEL_CAPABILITIES.items()
        if caps["tier"] == "paid"
    ]
