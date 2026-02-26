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
import json
import re
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


def _truncate_prompt_to_token_limit(prompt: str, token_limit: int) -> str:
    """
    Begrenzt den Prompt grob auf token_limit (1 Token ~= 3 Zeichen),
    damit SDK-interne Token-Cap-Pruefungen nicht verletzt werden.
    """
    if not prompt or token_limit is None:
        return prompt
    try:
        limit = int(token_limit)
    except (TypeError, ValueError):
        return prompt
    if limit <= 0:
        return prompt

    max_chars = limit * 3
    if len(prompt) <= max_chars:
        return prompt

    marker = "\n\n[... Prompt gekuerzt wegen effektivem Token-Limit ...]\n\n"
    if max_chars <= len(marker) + 20:
        return prompt[:max_chars]

    content_budget = max_chars - len(marker)
    head_budget = int(content_budget * 0.6)
    tail_budget = content_budget - head_budget
    truncated = (
        prompt[:head_budget]
        + marker
        + prompt[-tail_budget:]
    )
    logger.warning(
        "Claude SDK Prompt gekuerzt: ~%d -> ~%d Tokens (Limit=%d)",
        len(prompt) // 3,
        len(truncated) // 3,
        limit,
    )
    return truncated


def _is_claude_hard_limit_error(text: str) -> bool:
    """
    Erkennt globale Claude-Account-Limits, bei denen alle weiteren SDK/CLI-Calls
    im selben Run ebenfalls fehlschlagen wuerden.
    """
    if not text:
        return False
    text_l = text.lower()
    patterns = [
        "you've hit your limit",
        "you have hit your limit",
        "hit your limit",
        "out of credits",
        "run out of credits",
        "credits exhausted",
        "insufficient credits",
        "no credits",
        "credit limit",
    ]
    return any(p in text_l for p in patterns)


def _activate_claude_circuit_breaker(manager, reason: str) -> None:
    """Aktiviert globalen OpenRouter-Fallback falls Manager dies unterstuetzt."""
    activator = getattr(manager, "force_openrouter_for_claude", None)
    if callable(activator):
        activator(reason)


def _get_short_response_guard(manager) -> dict:
    """
    Liefert den Guard-State fuer wiederholte Kurzantworten.

    Struktur:
    {
      "total_failures": int,
      "by_role": {role: int}
    }
    """
    guard = getattr(manager, "_claude_short_response_guard", None)
    if not isinstance(guard, dict):
        guard = {"total_failures": 0, "by_role": {}}
        try:
            setattr(manager, "_claude_short_response_guard", guard)
        except Exception:
            # Bei read-only Test-Doubles weiter mit lokalem Dict.
            pass
    guard.setdefault("total_failures", 0)
    guard.setdefault("by_role", {})
    return guard


def _clear_short_response_guard_on_success(manager) -> None:
    """Setzt den Kurzantwort-Guard nach erfolgreicher SDK-Antwort zurueck."""
    guard = _get_short_response_guard(manager)
    if int(guard.get("total_failures", 0) or 0) <= 0:
        return
    guard["total_failures"] = 0
    guard["by_role"] = {}


def _record_short_response_failure(
    manager,
    role: str,
    preview: str,
    threshold: int,
    display_name: str,
) -> bool:
    """
    Erhoeht den Kurzantwort-Zaehler.

    Returns:
        True wenn der globale Circuit-Breaker ausgelost werden soll.
    """
    guard = _get_short_response_guard(manager)
    by_role = guard.get("by_role", {})
    by_role[role] = int(by_role.get(role, 0) or 0) + 1
    guard["by_role"] = by_role
    guard["total_failures"] = int(guard.get("total_failures", 0) or 0) + 1

    total_failures = int(guard["total_failures"])
    role_failures = int(by_role[role])
    manager._ui_log(
        display_name,
        "Warning",
        f"Claude SDK Kurzantwort-Fehler persistiert (global={total_failures}, role={role_failures}, "
        f"preview='{(preview or '')[:80]}')",
    )

    if threshold <= 0:
        return False
    return total_failures >= threshold


def _is_allowed_short_response(sdk_config: dict, role: str, text: str) -> bool:
    """
    Erlaubt definierte Kurzantwort-Sentinels als gueltigen Erfolg.

    Beispiel: Security darf exakt "SECURE" liefern.
    """
    if not text:
        return False
    normalized = text.strip().lower()
    if not normalized:
        return False

    defaults_by_role = {
        "security": {"secure"},
    }
    allowed = set(defaults_by_role.get(role, set()))

    global_allow = sdk_config.get("short_response_allowlist", []) or []
    role_allow = (
        (sdk_config.get("short_response_allowlist_by_role", {}) or {}).get(role, []) or []
    )
    allowed.update(str(v).strip().lower() for v in global_allow if str(v).strip())
    allowed.update(str(v).strip().lower() for v in role_allow if str(v).strip())

    return normalized in allowed


def _extract_json_candidates(text: str) -> list[str]:
    """Extrahiert moegliche JSON-Kandidaten aus einer Antwort."""
    if not text:
        return []
    candidates = []
    patterns = [
        r"```json\s*(.*?)\s*```",
        r"```\s*(\{[\s\S]*?\})\s*```",
        r"(\{[\s\S]*\"tasks\"[\s\S]*\})",
    ]
    for pattern in patterns:
        for match in re.findall(pattern, text, flags=re.IGNORECASE | re.DOTALL):
            if isinstance(match, str) and match.strip():
                candidates.append(match.strip())
    stripped = text.strip()
    if stripped:
        candidates.append(stripped)
    # Reihenfolge beibehalten + deduplizieren.
    return list(dict.fromkeys(candidates))


def _validate_role_output(role: str, text: str) -> tuple[Optional[bool], str]:
    """
    Rollenbasierte Output-Validierung.

    Returns:
        (None, "") wenn keine Rollenregel existiert.
        (True, "") wenn valide.
        (False, reason) wenn invalide.
    """
    if not text:
        return None, ""

    role_l = (role or "").strip().lower()
    if role_l == "fix":
        has_correction_header = bool(
            re.search(r"###\s*correction\s*:\s*.+", text, flags=re.IGNORECASE)
        )
        has_code_fence = "```" in text
        if has_correction_header and has_code_fence:
            return True, ""
        return False, "Fix-Output ohne erwartetes CORRECTION-Format"

    if role_l == "task_deriver":
        for candidate in _extract_json_candidates(text):
            try:
                data = json.loads(candidate)
            except Exception:
                continue
            if isinstance(data, dict) and isinstance(data.get("tasks"), list):
                return True, ""
        return False, "TaskDeriver-Output ist kein parsebares Task-JSON"

    return None, ""


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
    configured_role_limit = manager.config.get("token_limits", {}).get(role)
    get_effective_limit = getattr(manager, "get_effective_token_limit", None)
    if callable(get_effective_limit):
        effective_token_limit = get_effective_limit(role, configured_role_limit)
    else:
        effective_token_limit = configured_role_limit
    prompt = _truncate_prompt_to_token_limit(prompt, effective_token_limit)

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

    short_response_exhausted = False
    last_short_preview = ""

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
                    max_output_tokens=effective_token_limit,
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

            # AENDERUNG 26.02.2026: Root-Cause-Fix — Globales Claude-Limit sofort erkennen.
            # Bei "You've hit your limit" sind alle weiteren Claude-Calls im Run nutzlos.
            if _is_claude_hard_limit_error(cleaned or raw_output):
                reason = (cleaned or raw_output or "")[:300]
                manager._ui_log(
                    display_name,
                    "Warning",
                    "Claude-Hard-Limit erkannt. Aktiviere globalen OpenRouter-Fallback.",
                )
                _activate_claude_circuit_breaker(manager, reason)
                return None

            min_chars = sdk_config.get("min_response_chars", 200)
            if cleaned and _is_allowed_short_response(sdk_config, role, cleaned):
                manager._ui_log(
                    display_name,
                    "Info",
                    f"Claude SDK Kurzantwort-Sentinel akzeptiert: '{cleaned.strip()[:80]}'",
                )
                _clear_short_response_guard_on_success(manager)
                return cleaned.strip()

            role_validation, role_validation_reason = _validate_role_output(role, cleaned or "")
            if role_validation is True:
                _clear_short_response_guard_on_success(manager)
                return cleaned
            if role_validation is False:
                preview = (cleaned or "")[:100].replace("\n", " ")
                last_short_preview = preview
                is_last_attempt = sdk_attempt >= retries - 1
                retry_msg = (
                    "kein weiterer Retry"
                    if is_last_attempt
                    else f"Retry {sdk_attempt + 1}/{retries}..."
                )
                manager._ui_log(
                    display_name,
                    "Warning",
                    f"Claude SDK Rollen-Validator fehlgeschlagen ({role}): {role_validation_reason}. "
                    f"Inhalt: '{preview}' | {retry_msg}",
                )
                if is_last_attempt:
                    short_response_exhausted = True
                    break
                continue

            if cleaned and len(cleaned) >= min_chars:
                _clear_short_response_guard_on_success(manager)
                return cleaned
            if cleaned:
                # AENDERUNG 26.02.2026: Fix 91a — Inhalt kurzer Antworten loggen
                # ROOT-CAUSE-FIX:
                # Symptom: 28-Zeichen-Antworten ohne Diagnostik was der Inhalt ist
                # Ursache: Nur Laenge geloggt, nicht der tatsaechliche Text
                # Loesung: Ersten 100 Zeichen des Inhalts mitloggen
                preview = cleaned[:100].replace("\n", " ")
                last_short_preview = preview
                is_last_attempt = sdk_attempt >= retries - 1
                retry_msg = "kein weiterer Retry" if is_last_attempt else f"Retry {sdk_attempt + 1}/{retries}..."
                manager._ui_log(
                    display_name,
                    "Warning",
                    f"Claude SDK Antwort zu kurz ({len(cleaned)} < {min_chars} Zeichen), "
                    f"Inhalt: '{preview}' | {retry_msg}",
                )
                if is_last_attempt:
                    short_response_exhausted = True
                    break
                continue
            if raw_output:
                raw_preview = raw_output[:100].replace("\n", " ")
                manager._ui_log(
                    display_name,
                    "Warning",
                    f"Claude SDK leere Ausgabe nach Bereinigung "
                    f"(Versuch {sdk_attempt + 1}/{retries}, raw_len={len(raw_output)}, "
                    f"raw_preview='{raw_preview}')",
                )
                continue

        except Exception as sdk_error:
            error_str = str(sdk_error)

            if _is_claude_hard_limit_error(error_str):
                manager._ui_log(
                    display_name,
                    "Warning",
                    "Claude-Hard-Limit erkannt. Aktiviere globalen OpenRouter-Fallback.",
                )
                _activate_claude_circuit_breaker(manager, error_str[:300])
                return None

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

    # AENDERUNG 26.02.2026: Root-Cause-Fix — Persistente Kurzantworten global abfangen.
    # Wenn mehrere SDK-Calls nur Mini-Texte liefern (z.B. 28 Zeichen), ist Claude fuer
    # den laufenden Run wahrscheinlich degradiert. Dann run-weit auf OpenRouter schalten.
    if short_response_exhausted:
        threshold = int(
            sdk_config.get("short_response_global_fallback_threshold", 3) or 3
        )
        should_trip = _record_short_response_failure(
            manager=manager,
            role=role,
            preview=last_short_preview,
            threshold=threshold,
            display_name=display_name,
        )
        if should_trip:
            reason = (
                "Persistent short Claude responses "
                f"(threshold={threshold}, role={role}, preview='{last_short_preview[:120]}')"
            )
            manager._ui_log(
                display_name,
                "Warning",
                "Claude-Kurzantwort-Muster erkannt. Aktiviere globalen OpenRouter-Fallback.",
            )
            _activate_claude_circuit_breaker(manager, reason)

    return None
