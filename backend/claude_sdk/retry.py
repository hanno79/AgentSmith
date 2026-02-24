# -*- coding: utf-8 -*-
"""Claude SDK Retry/Heartbeat-Logik."""

import logging
from typing import Optional

from . import loader as state

logger = logging.getLogger(__name__)


def run_sdk_with_retry(
    manager,
    role: str,
    prompt: str,
    timeout_seconds: int,
    agent_display_name: str = None,
    max_retries: int = None,
    heartbeat_interval: int = 15,
) -> Optional[str]:
    """
    Fuehrt Claude SDK Call mit Retry-Logik aus.

    HINWEIS: Die Imports von heartbeat/_clean_model_output bleiben absichtlich lazy,
    um zirkulaere Abhaengigkeiten zu vermeiden.
    """
    if not hasattr(manager, "claude_provider") or not manager.claude_provider:
        logger.warning("SDK skip: claude_provider nicht vorhanden fuer Rolle=%s", role)
        return None

    provider = manager.get_provider(role)
    if provider != "claude-sdk":
        logger.warning("SDK skip: Provider=%s fuer Rolle=%s (nicht claude-sdk)", provider, role)
        return None

    from ..heartbeat_utils import run_with_heartbeat
    from ..dev_loop_coder_utils import _clean_model_output

    sdk_config = manager.config.get("claude_sdk", {})
    claude_model = sdk_config.get("agent_models", {}).get(
        role, sdk_config.get("default_model", "sonnet")
    )
    display_name = agent_display_name or role.capitalize()
    retries = max_retries or sdk_config.get("max_retries", 3)
    sdk_max_turns = sdk_config.get("max_turns_by_role", {}).get(
        role, sdk_config.get("default_max_turns", 10)
    )

    sdk_tier = state._SDK_TIER_ORDER.get(role, 1)
    if sdk_tier >= 2:
        max_retries_tier2 = sdk_config.get("max_retries_tier2", 1)
        retries = min(retries, max_retries_tier2)
        if retries < (max_retries or sdk_config.get("max_retries", 3)):
            logger.info(
                "SDK Tier-2 (%s): max_retries auf %d begrenzt (schneller Fallback)",
                role,
                retries,
            )
    elif sdk_tier == 1 and role not in ("coder", "reviewer"):
        max_retries_t1 = sdk_config.get("max_retries_tier1_non_coder", 2)
        retries = min(retries, max_retries_t1)
        if retries < (max_retries or sdk_config.get("max_retries", 3)):
            logger.info(
                "SDK Tier-1 Non-Coder (%s): max_retries auf %d begrenzt", role, retries
            )

    tier_override = getattr(manager, "_sdk_tier_escalation", None)
    if tier_override and state._SDK_TIER_ORDER.get(tier_override, 0) > state._SDK_TIER_ORDER.get(
        role, 0
    ):
        override_model = sdk_config.get("agent_models", {}).get(tier_override, "sonnet")
        manager._ui_log(
            display_name,
            "TierEscalation",
            f"PingPong-Eskalation: {role}({claude_model}) → {tier_override}({override_model})",
        )
        claude_model = override_model
        role = tier_override

    # AENDERUNG 22.02.2026: Fix 75a — CLI-Modus fuer einfache Rollen
    # ROOT-CAUSE-FIX:
    # Symptom: allowed_tools=[] = ALLE Tools → Claude liest Dateien statt zu antworten
    # Loesung: cli_mode_roles in config.yaml → `claude -p` Subprozess ohne Tools
    cli_roles = sdk_config.get("cli_mode_roles", [])
    use_cli = role in cli_roles

    for sdk_attempt in range(retries):
        try:
            raw_output = run_with_heartbeat(
                func=lambda: manager.claude_provider.run_agent(
                    prompt=prompt,
                    role=role,
                    model=claude_model,
                    ui_log_callback=manager._ui_log,
                    project_id=getattr(manager, "_stats_run_id", None)
                    or getattr(manager, "project_id", None),
                    timeout_seconds=timeout_seconds,
                    max_turns=sdk_max_turns,
                    use_cli_mode=use_cli,
                ),
                ui_log_callback=manager._ui_log,
                agent_name=display_name,
                task_description=f"Claude SDK ({claude_model}) Versuch {sdk_attempt + 1}/{retries}",
                heartbeat_interval=heartbeat_interval,
                timeout_seconds=timeout_seconds + 60,
            )

            cleaned = _clean_model_output(raw_output)
            if cleaned != raw_output:
                manager._ui_log(
                    display_name, "ThinkTagFilter", "Model-Output bereinigt (Think-Tags entfernt)"
                )

            min_chars = sdk_config.get("min_response_chars", 200)
            if cleaned and len(cleaned) >= min_chars:
                return cleaned
            if cleaned:
                manager._ui_log(
                    display_name,
                    "Warning",
                    f"Claude SDK Antwort zu kurz ({len(cleaned)} < {min_chars} Zeichen), "
                    f"Retry {sdk_attempt + 1}/{retries}...",
                )
                continue

        except Exception as sdk_error:
            error_str = str(sdk_error)
            manager._ui_log(
                display_name,
                "Warning",
                f"Claude SDK Versuch {sdk_attempt + 1}/{retries} fehlgeschlagen: {error_str[:200]}",
            )
            if sdk_attempt < retries - 1:
                if "rate_limit" in error_str.lower() or "429" in error_str:
                    backoff_seconds = (sdk_attempt + 1) * 30
                    manager._ui_log(
                        display_name,
                        "Info",
                        f"Rate-Limit erkannt, warte {backoff_seconds}s vor Retry...",
                    )
                    import time

                    time.sleep(backoff_seconds)
                continue

            manager._ui_log(
                display_name,
                "Warning",
                f"Claude SDK erschoepft nach {retries} Versuchen, Fallback auf OpenRouter",
            )
            logger.warning(
                "Claude SDK %s (%s) fehlgeschlagen nach %d Versuchen, Fallback: %s",
                display_name,
                claude_model,
                retries,
                sdk_error,
            )

    return None
