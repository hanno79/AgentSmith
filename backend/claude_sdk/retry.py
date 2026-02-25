# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 24.02.2026
Version: 1.0
Beschreibung: Claude SDK Retry/Heartbeat-Logik.
"""

import logging
import time
import random
from typing import Optional

from . import loader as state

logger = logging.getLogger(__name__)


# AENDERUNG 25.02.2026: Fix 80b — asyncio.run() durch time.sleep() ersetzt
# ROOT-CAUSE-FIX:
# Symptom: Planner Pre-Call Cooldown wird geloggt aber nicht abgewartet (1s statt 60s)
# Ursache: asyncio.run() crasht innerhalb laufendem Event-Loop (run_planner ist async def,
#          aufgerufen via loop.run_until_complete → asyncio.run() = RuntimeError)
# Loesung: time.sleep() blockiert zuverlaessig unabhaengig vom Event-Loop-Kontext
def _sleep_with_blocking(seconds: float) -> None:
    """Fuehrt einen blockierenden Sleep durch (sicher in jedem Kontext)."""
    if seconds > 0:
        time.sleep(seconds)


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
    configured_retries = sdk_config.get("max_retries", 5)
    retries = max_retries if max_retries is not None else configured_retries
    base_retries = retries
    rate_limit_backoff_base = sdk_config.get("rate_limit_backoff_base", 45)
    rate_limit_backoff_jitter_max = sdk_config.get("rate_limit_backoff_jitter_max_seconds", 5.0)
    rate_limit_backoff_jitter_factor = sdk_config.get("rate_limit_backoff_jitter_factor", 0.25)
    sdk_max_turns = sdk_config.get("max_turns_by_role", {}).get(
        role, sdk_config.get("default_max_turns", 10)
    )

    sdk_tier = state._SDK_TIER_ORDER.get(role, 0)
    if sdk_tier >= 2:
        max_retries_tier2 = sdk_config.get("max_retries_tier2", 1)
        retries = min(retries, max_retries_tier2)
        if retries < base_retries:
            logger.info(
                "SDK Tier-2 (%s): max_retries auf %d begrenzt (schneller Fallback)",
                role,
                retries,
            )
    # AENDERUNG 24.02.2026: Fix 79b — Tier-0 (Fix/Tester) max_retries begrenzen
    # ROOT-CAUSE-FIX:
    # Symptom: 4 parallele Haiku Fix-Tasks × 5 Retries × 300s = 25 Min Worst-Case
    # Ursache: Tier-0 hatte kein Limit, bekam alle 5 Retries bei CLI-Fehlern
    # Loesung: Konfigurierbares Limit (default 2), dann sofort OpenRouter-Fallback
    elif sdk_tier == 0:
        max_retries_t0 = sdk_config.get("max_retries_tier0", 2)
        retries = min(retries, max_retries_t0)
        if retries < base_retries:
            logger.info(
                "SDK Tier-0 (%s): max_retries auf %d begrenzt (schneller Fallback)",
                role,
                retries,
            )
    elif sdk_tier == 1 and role not in ("coder",):
        max_retries_t1 = sdk_config.get("max_retries_tier1_non_coder", 2)
        retries = min(retries, max_retries_t1)
        if retries < base_retries:
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

    # AENDERUNG 24.02.2026: Fix 78 — Pre-Call Cooldown fuer Token-intensive Rollen
    # ROOT-CAUSE-FIX:
    # Symptom: Planner/Reviewer treffen IMMER auf rate_limit_event im async SDK
    # Ursache: Nach 5+ CLI-Aufrufen (TaskDeriver+Researcher+TechStack+DBDesigner+Designer)
    #          ist das TPM-Limit erreicht bevor Planner/Reviewer dran sind
    # Loesung: Konfigurierbarer Pre-Call Cooldown laesst Token-Budget sich erholen
    pre_call_cooldown = sdk_config.get("pre_call_cooldown", {}).get(role, 0)
    if pre_call_cooldown > 0:
        manager._ui_log(
            display_name,
            "Info",
            f"Pre-Call Cooldown: Warte {pre_call_cooldown}s (TPM-Limit Schutz)...",
        )

        _sleep_with_blocking(pre_call_cooldown)

    # Heartbeat-Marge muss groesser als Worst-Case Zusatzzeit sein, damit kein
    # vorzeitiger Timeout bei Cooldown/Backoff-bedingter Verzoegerung ausloest.
    worst_case_backoff = 0.0
    for attempt in range(max(retries - 1, 0)):
        attempt_base = rate_limit_backoff_base * (2 ** attempt)
        attempt_jitter_max = max(
            float(rate_limit_backoff_jitter_max),
            attempt_base * float(rate_limit_backoff_jitter_factor),
        )
        worst_case_backoff += attempt_base + max(attempt_jitter_max, 0.0)
    worst_case_overhead = pre_call_cooldown + worst_case_backoff
    heartbeat_timeout_min_margin = worst_case_overhead + 30
    configured_heartbeat_margin = sdk_config.get("heartbeat_timeout_margin_seconds")
    heartbeat_timeout_margin = heartbeat_timeout_min_margin
    if configured_heartbeat_margin is not None:
        try:
            heartbeat_timeout_margin = max(
                int(configured_heartbeat_margin), heartbeat_timeout_min_margin
            )
        except (TypeError, ValueError):
            heartbeat_timeout_margin = heartbeat_timeout_min_margin

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
                timeout_seconds=timeout_seconds + heartbeat_timeout_margin,
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
            if raw_output:
                manager._ui_log(
                    display_name,
                    "Warning",
                    f"Claude SDK hat nach Bereinigung eine leere Ausgabe erhalten "
                    f"(Versuch {sdk_attempt + 1}/{retries}, raw_len={len(raw_output)})",
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
                    # AENDERUNG 24.02.2026: Fix 78 — Erhoehter Backoff (konfigurierbar)
                    base_backoff_seconds = rate_limit_backoff_base * (2 ** sdk_attempt)
                    jitter_window = max(
                        float(rate_limit_backoff_jitter_max),
                        base_backoff_seconds * float(rate_limit_backoff_jitter_factor),
                    )
                    jitter_seconds = random.uniform(0.0, max(jitter_window, 0.0))
                    backoff_seconds = base_backoff_seconds + jitter_seconds
                    manager._ui_log(
                        display_name,
                        "Info",
                        f"Rate-Limit erkannt, warte {backoff_seconds:.1f}s vor Retry...",
                    )

                    _sleep_with_blocking(backoff_seconds)
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
