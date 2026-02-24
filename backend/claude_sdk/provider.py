# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 24.02.2026
Version: 1.0
Beschreibung: Claude SDK Provider + Singleton fuer CLI/SDK-Ausfuehrung.
"""

import logging
import os
import shutil
import subprocess
import sys
import threading
import time
from typing import Callable, Optional

from . import loader as state

logger = logging.getLogger(__name__)


class ClaudeSDKProvider:
    """
    Synchroner Wrapper fuer claude-agent-sdk query().

    Bedient alle bestehenden Tracking-Systeme identisch zu CrewAI:
    - set_current_agent() VOR jedem Call
    - ModelStatsDB.record_call() NACH jedem Call (Success + Failure)
    - BudgetTracker.record_usage() NACH jedem Call
    - ui_log_callback fuer WebSocket/Library/Session Events
    """

    def __init__(self):
        self._initialized = False
        logger.info("ClaudeSDKProvider initialisiert (Lazy-Loading)")

    def _ensure_initialized(self):
        if not self._initialized:
            state._ensure_sdk_loaded()
            self._initialized = True

    def run_agent(
        self,
        prompt: str,
        role: str,
        model: str = "sonnet",
        tools: Optional[list] = None,
        cwd: Optional[str] = None,
        system_prompt: Optional[str] = None,
        ui_log_callback: Optional[Callable] = None,
        project_id: Optional[str] = None,
        timeout_seconds: int = 750,
        max_turns: int = 10,
        use_cli_mode: bool = False,
    ) -> str:
        # AENDERUNG 22.02.2026: Fix 75a — CLI-Modus braucht kein SDK-Lazy-Loading
        if not use_cli_mode:
            self._ensure_initialized()

        agent_display_name = role.capitalize()

        try:
            from ..orchestration_budget import set_current_agent

            set_current_agent(agent_display_name, project_id)
        except ImportError:
            logger.debug("orchestration_budget nicht verfuegbar - Budget-Tracking uebersprungen")

        mode_label = "CLI" if use_cli_mode else "SDK"
        if ui_log_callback:
            ui_log_callback(
                agent_display_name,
                "Working",
                f"Claude {mode_label} ({model}) generiert...",
            )

        start_time = time.time()

        try:
            # AENDERUNG 22.02.2026: Fix 75a — CLI-Modus fuer einfache Rollen
            # ROOT-CAUSE-FIX:
            # Symptom: Einfache Rollen (DB-Designer etc.) brauchen 2+ Min
            # Ursache: allowed_tools=[] = ALLE Tools → Claude liest Dateien statt zu antworten
            # Loesung: `claude -p` Subprozess mit --max-turns 1 → keine Tools, direkte Antwort
            if use_cli_mode:
                result = self._run_cli(
                    prompt=prompt,
                    model=model,
                    system_prompt=system_prompt,
                    timeout_seconds=timeout_seconds,
                    max_turns=max_turns,
                )
            else:
                result = self._run_sync(
                    prompt=prompt,
                    model=model,
                    tools=tools,
                    cwd=cwd,
                    system_prompt=system_prompt,
                    max_turns=max_turns,
                    timeout_seconds=timeout_seconds,
                )

            latency_ms = (time.time() - start_time) * 1000
            prompt_tokens_est = len(prompt) // 3
            completion_tokens_est = len(result) // 3
            self._record_success(
                role=role,
                model=model,
                prompt_tokens=prompt_tokens_est,
                completion_tokens=completion_tokens_est,
                latency_ms=latency_ms,
                project_id=project_id,
            )

            if ui_log_callback:
                ui_log_callback(
                    agent_display_name,
                    "Result",
                    f"Claude {mode_label} ({model}): {len(result)} Zeichen in {latency_ms:.0f}ms",
                )

            logger.info(
                "Claude %s %s (%s): %d Zeichen in %.0fms",
                mode_label,
                agent_display_name,
                model,
                len(result),
                latency_ms,
            )
            return result

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            self._record_failure(
                role=role, model=model, latency_ms=latency_ms, project_id=project_id
            )

            if ui_log_callback:
                error_msg = str(e)[:200]
                ui_log_callback(
                    agent_display_name,
                    "Error",
                    f"Claude {mode_label} ({model}) Fehler: {error_msg}",
                )

            logger.error(
                "Claude %s %s (%s) Fehler nach %.0fms: %s",
                mode_label,
                agent_display_name,
                model,
                latency_ms,
                e,
            )
            raise

    # AENDERUNG 22.02.2026: Fix 75a — CLI-Modus fuer einfache Rollen
    # AENDERUNG 24.02.2026: Fix 76a — max_turns aus Config durchreichen statt hardcoded 1
    # ROOT-CAUSE-FIX:
    # Symptom: Alle CLI-Rollen liefern nur ~28 Zeichen → Min-Response-Guard → Fallback auf OpenRouter
    # Ursache: --max-turns 1 war hardcoded, obwohl Config z.B. researcher:15 vorsieht
    # Loesung: max_turns Parameter an _run_cli() durchreichen
    def _run_cli(
        self,
        prompt: str,
        model: str,
        system_prompt: Optional[str],
        timeout_seconds: int,
        max_turns: int = 1,
    ) -> str:
        """
        Einfacher CLI-Modus via subprocess.
        Fuer Rollen die nur Text-Prompt → Text-Antwort brauchen (kein Tool-Use).
        """
        claude_path = shutil.which("claude") or shutil.which("claude.exe")
        if not claude_path:
            raise FileNotFoundError("claude CLI nicht im PATH gefunden")

        model_full = state.CLAUDE_MODEL_MAP.get(model, model)
        cmd = [claude_path, "-p", "--output-format", "text", "--max-turns", str(max_turns)]
        cmd.extend(["--model", model_full])
        # AENDERUNG 24.02.2026: Fix 76c — Default System-Prompt fuer CLI-Modus
        # ROOT-CAUSE-FIX:
        # Symptom: TechStack/DB-Designer/Designer liefern ~28 Zeichen via CLI
        # Ursache: Kein System-Prompt → Claude antwortet konversationell statt strukturiert
        # Loesung: Default System-Prompt wie in _run_sync() (Zeile 226-227)
        effective_system = system_prompt or (
            "Gib nur den angeforderten Output zurueck. "
            "Keine Erklaerungen oder Kommentare ausserhalb des angeforderten Formats."
        )
        cmd.extend(["--system-prompt", effective_system])

        # CLAUDECODE Env-Var entfernen (Nested-Session-Prevention, wie in _run_sync)
        env = os.environ.copy()
        env.pop("CLAUDECODE", None)

        result = subprocess.run(
            cmd,
            input=prompt,
            capture_output=True,
            text=True,
            timeout=timeout_seconds, env=env
        )

        if result.returncode != 0:
            stderr_excerpt = (result.stderr or "")[:500]
            raise RuntimeError(f"claude CLI Fehler (Code {result.returncode}): {stderr_excerpt}")

        output = result.stdout.strip()
        if not output:
            raise ValueError("claude CLI: Leere Antwort erhalten")

        return output

    def _run_sync(
        self,
        prompt: str,
        model: str,
        tools: Optional[list],
        cwd: Optional[str],
        system_prompt: Optional[str],
        max_turns: int,
        timeout_seconds: int,
    ) -> str:
        """Synchroner Wrapper fuer async claude-agent-sdk query()."""
        import anyio

        result_container = {"text": "", "error": None, "traceback_obj": None}
        stop_event = threading.Event()

        async def _async_query():
            option_kwargs = {
                "system_prompt": system_prompt
                or "Gib nur den angeforderten Output zurueck. Keine Erklaerungen oder Kommentare ausserhalb des angeforderten Formats.",
                "allowed_tools": tools or [],
                "max_turns": max_turns,
                "cwd": cwd,
                "include_partial_messages": True,
            }
            try:
                options = state._sdk_options_class(**option_kwargs)
            except TypeError:
                option_kwargs.pop("include_partial_messages", None)
                options = state._sdk_options_class(**option_kwargs)

            result_text = ""
            msg_count = 0
            stream = None
            try:
                stream = state._sdk_query(prompt=prompt, options=options)
                async for message in stream:
                    if stop_event.is_set():
                        logger.warning("Claude SDK Stream abgebrochen (Timeout/Cancellation)")
                        break

                    msg_count += 1
                    if message is None:
                        logger.debug("SDK-DIAG: None-Message #%d", msg_count)
                        continue

                    msg_type_name = type(message).__name__
                    logger.debug("SDK-DIAG: Message #%d = %s", msg_count, msg_type_name)

                    if isinstance(message, state._sdk_assistant_message):
                        error_payload = str(message.error) if message.error else ""
                        if error_payload:
                            err_lower = error_payload.lower()
                            if "rate_limit" in err_lower:
                                raise RuntimeError(
                                    "Claude API: Rate-Limit erreicht (quota erschoepft)"
                                )
                            if "billing" in err_lower:
                                raise RuntimeError(
                                    "Claude API: Billing-Fehler (Account-Problem oder Limit)"
                                )
                            if (
                                "authentication" in err_lower
                                or "invalid_request" in err_lower
                            ):
                                raise RuntimeError(
                                    f"Claude API: Konfigurationsfehler ({error_payload})"
                                )
                            logger.warning("AssistantMessage mit Fehler: %s", message.error)

                        for block in message.content or []:
                            if isinstance(block, state._sdk_text_block):
                                result_text += block.text

                    elif isinstance(message, state._sdk_stream_event):
                        event_obj = getattr(message, "event", {}) or {}
                        event_type = (
                            event_obj.get("type", "unknown")
                            if isinstance(event_obj, dict)
                            else "unknown"
                        )
                        logger.debug("SDK-DIAG: StreamEvent=%s", event_type)
                        if event_type == "rate_limit_event" and not result_text:
                            raise RuntimeError(
                                "Claude API: rate_limit_event empfangen, bevor Text generiert wurde"
                            )

                    elif isinstance(message, state._sdk_result_message):
                        if message.result and not result_text:
                            result_text = message.result
                    else:
                        logger.debug("SDK-DIAG: Unbehandelter Typ: %s", msg_type_name)
            finally:
                if stream is not None and stop_event.is_set() and hasattr(stream, "aclose"):
                    try:
                        await stream.aclose()
                    except Exception:
                        logger.debug("SDK stream cleanup fehlgeschlagen", exc_info=True)
            return result_text

        def _thread_target(cancel_event: threading.Event):
            try:
                result_container["text"] = anyio.run(_async_query)
            except Exception as e:
                if cancel_event.is_set():
                    logger.warning("Claude SDK Thread nach Cancel beendet: %s", e)
                result_container["error"] = e
                result_container["traceback_obj"] = sys.exc_info()[2]

        os.environ.pop("CLAUDECODE", None)
        thread = threading.Thread(target=_thread_target, args=(stop_event,), daemon=True)
        thread.start()
        thread.join(timeout=timeout_seconds)

        if thread.is_alive():
            stop_event.set()
            thread.join(timeout=2)
            raise TimeoutError(
                f"Claude SDK Timeout nach {timeout_seconds}s (Modell: {model})"
            )

        if result_container["error"]:
            traceback_obj = result_container.get("traceback_obj")
            if traceback_obj is not None:
                raise result_container["error"].with_traceback(traceback_obj)
            raise result_container["error"]

        if not result_container["text"]:
            raise ValueError(
                f"Claude SDK ({model}): Leere Antwort erhalten. "
                "Moegliche Ursachen: Modell hat keinen Text generiert oder Stream war leer."
            )

        return result_container["text"]

    def _record_success(
        self,
        role: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        latency_ms: float,
        project_id: Optional[str],
    ):
        model_full = state.CLAUDE_MODEL_MAP.get(model, model)
        model_id = f"claude-sdk/{model_full}"

        try:
            from budget_tracker import get_budget_tracker

            tracker = get_budget_tracker()
            tracker.record_usage(
                agent=role.capitalize(),
                model=model_id,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                project_id=project_id,
            )
        except Exception as e:
            logger.debug("BudgetTracker.record_usage() Fehler: %s", e)

        try:
            from model_stats_db import get_model_stats_db

            stats_db = get_model_stats_db()
            stats_db.record_call(
                run_id=project_id or "unknown",
                agent=role.capitalize(),
                model=model_id,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                cost_usd=0.0,
                latency_ms=latency_ms,
                success=True,
            )
        except Exception as e:
            logger.debug("ModelStatsDB.record_call() Fehler: %s", e)

    def _record_failure(
        self, role: str, model: str, latency_ms: float, project_id: Optional[str]
    ):
        model_full = state.CLAUDE_MODEL_MAP.get(model, model)
        model_id = f"claude-sdk/{model_full}"

        try:
            from model_stats_db import get_model_stats_db

            stats_db = get_model_stats_db()
            stats_db.record_call(
                run_id=project_id or "unknown",
                agent=role.capitalize(),
                model=model_id,
                prompt_tokens=0,
                completion_tokens=0,
                cost_usd=0.0,
                latency_ms=latency_ms,
                success=False,
            )
        except Exception as e:
            logger.debug("ModelStatsDB Failure-Tracking Fehler: %s", e)


_provider_instance = None
_provider_lock = threading.Lock()


def get_claude_sdk_provider() -> ClaudeSDKProvider:
    """Singleton-Getter fuer ClaudeSDKProvider (thread-safe)."""
    global _provider_instance
    if _provider_instance is None:
        with _provider_lock:
            if _provider_instance is None:
                _provider_instance = ClaudeSDKProvider()
    return _provider_instance
