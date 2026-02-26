# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 24.02.2026
Version: 1.0
Beschreibung: Claude SDK Provider + Singleton fuer CLI/SDK-Ausfuehrung.
"""

import logging
import importlib.metadata
import os
import re
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
        # AENDERUNG 25.02.2026: Fix 85 — Aktiven CLI-Prozess tracken fuer sauberen Stop
        self._current_process = None
        logger.info("ClaudeSDKProvider initialisiert (Lazy-Loading)")

    def kill_active_process(self):
        """Beendet den aktuell laufenden CLI-Prozess (fuer Reset/Stop)."""
        proc = self._current_process
        if proc is not None:
            try:
                if proc.poll() is None:
                    proc.kill()
                    proc.wait(timeout=3)
                    logger.info("CLI-Prozess durch Stop/Reset beendet (PID=%s)", proc.pid)
            except Exception as e:
                logger.debug("kill_active_process: %s", e)

    @staticmethod
    def _parse_version_tuple(version_text: Optional[str]) -> Optional[tuple]:
        """Parst semver-artige Versionsstrings robust in ein vergleichbares Tuple."""
        if not version_text:
            return None
        match = re.search(r"(\d+)\.(\d+)\.(\d+)", version_text)
        if not match:
            return None
        return tuple(int(match.group(i)) for i in range(1, 4))

    @classmethod
    def _is_version_newer(cls, candidate: Optional[str], baseline: Optional[str]) -> bool:
        cand_t = cls._parse_version_tuple(candidate)
        base_t = cls._parse_version_tuple(baseline)
        if not cand_t:
            return False
        if not base_t:
            return True
        return cand_t > base_t

    @staticmethod
    def _read_cli_version(cli_path: str) -> Optional[str]:
        """Liest die CLI-Version via --version (best effort)."""
        try:
            result = subprocess.run(
                [cli_path, "--version"],
                capture_output=True,
                text=True,
                timeout=8,
            )
        except Exception:
            return None

        combined = f"{result.stdout or ''}\n{result.stderr or ''}"
        match = re.search(r"(\d+\.\d+\.\d+)", combined)
        return match.group(1) if match else None

    @staticmethod
    def _extract_token_cap_from_text(text: str) -> Optional[int]:
        if not text:
            return None

        patterns = [
            r"(?:max(?:imum)?|limit)[^0-9]{0,30}(\d{3,6})\s*tokens?",
            r"(\d{3,6})\s*tokens?[^a-zA-Z]{0,20}(?:max(?:imum)?|limit)",
            r"context[^0-9]{0,20}(\d{3,6})",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                try:
                    return int(match.group(1))
                except (TypeError, ValueError):
                    continue
        return None

    @classmethod
    def _probe_cli_runtime_cap(cls, cli_path: str, model_full: str, requested: int = 65536) -> Optional[int]:
        """
        Ermittelt das zur Laufzeit gemeldete Token-Limit (best effort).
        Strategie: absichtlich hohes Token-Limit setzen und Fehlermeldung parsen.
        """
        if not cli_path:
            return None

        env = os.environ.copy()
        env.pop("CLAUDECODE", None)
        base_cmd = [
            cli_path,
            "-p",
            "--output-format",
            "text",
            "--max-turns",
            "1",
            "--model",
            model_full,
        ]
        prompts = "Respond with OK."
        token_flags = ("--max-output-tokens", "--max-tokens")

        for token_flag in token_flags:
            cmd = list(base_cmd)
            cmd.extend([token_flag, str(requested)])
            try:
                result = subprocess.run(
                    cmd,
                    input=prompts,
                    capture_output=True,
                    text=True,
                    timeout=15,
                    env=env,
                )
            except Exception:
                continue

            if result.returncode == 0:
                return requested

            combined = f"{result.stdout or ''}\n{result.stderr or ''}"
            parsed = cls._extract_token_cap_from_text(combined)
            if parsed:
                return parsed

        return None

    @classmethod
    def _find_bundled_cli_path(cls) -> Optional[str]:
        """
        Sucht nach einer vom SDK mitgelieferten Claude-CLI (best effort).
        Falls keine bundler-spezifische Binary gefunden wird, bleibt das Feld leer.
        """
        try:
            import claude_agent_sdk  # type: ignore
        except Exception:
            return None

        pkg_dir = os.path.dirname(getattr(claude_agent_sdk, "__file__", "") or "")
        if not pkg_dir or not os.path.isdir(pkg_dir):
            return None

        candidate_names = ("claude", "claude.exe", "claude-code", "claude-code.exe")
        for root, _, files in os.walk(pkg_dir):
            lower = {f.lower(): f for f in files}
            for name in candidate_names:
                if name in lower:
                    candidate = os.path.join(root, lower[name])
                    if os.path.isfile(candidate):
                        return candidate
        return None

    def probe_sdk_runtime(self, configured_coder_limit: int) -> dict:
        """
        Prueft SDK/CLI-Laufzeitinfos fuer Haiku und liefert eine Mitigation-Empfehlung.
        """
        sdk_version = None
        try:
            sdk_version = importlib.metadata.version("claude-agent-sdk")
        except Exception:
            sdk_version = None

        bundled_cli_path = self._find_bundled_cli_path()
        bundled_cli_version = self._read_cli_version(bundled_cli_path) if bundled_cli_path else None
        system_cli_path = shutil.which("claude") or shutil.which("claude.exe")
        system_cli_version = self._read_cli_version(system_cli_path) if system_cli_path else None

        reported_limit = None
        probe_path = bundled_cli_path or system_cli_path
        if probe_path:
            reported_limit = self._probe_cli_runtime_cap(
                cli_path=probe_path,
                model_full=state.CLAUDE_MODEL_MAP.get("haiku", "haiku"),
                requested=max(int(configured_coder_limit or 0), 65536),
            )

        sdk_in_affected_range = False
        sdk_vtuple = self._parse_version_tuple(sdk_version)
        if sdk_vtuple is not None:
            # Bekannter Problemstart: 0.1.39; obere Schranke defensiv auf <0.2.0.
            sdk_in_affected_range = (0, 1, 39) <= sdk_vtuple < (0, 2, 0)

        effective_limit = int(configured_coder_limit or 0)
        if reported_limit and reported_limit > 0:
            effective_limit = min(effective_limit, int(reported_limit))

        limit_mismatch = bool(
            reported_limit
            and configured_coder_limit
            and int(reported_limit) < int(configured_coder_limit)
        )
        mitigation_required = sdk_in_affected_range or limit_mismatch
        prefer_system_cli = (
            mitigation_required
            and bool(system_cli_path)
            and self._is_version_newer(system_cli_version, bundled_cli_version)
        )

        return {
            "sdk_version": sdk_version,
            "bundled_cli_path": bundled_cli_path,
            "bundled_cli_version": bundled_cli_version,
            "system_cli_path": system_cli_path,
            "system_cli_version": system_cli_version,
            "reported_haiku_limit": reported_limit,
            "configured_coder_limit": configured_coder_limit,
            "effective_coder_limit": effective_limit,
            "sdk_in_affected_range": sdk_in_affected_range,
            "limit_mismatch": limit_mismatch,
            "mitigation_required": mitigation_required,
            "prefer_system_cli": prefer_system_cli,
        }

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
        max_output_tokens: Optional[int] = None,
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
                    max_output_tokens=max_output_tokens,
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
                    max_output_tokens=max_output_tokens,
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
        max_output_tokens: Optional[int] = None,
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
        if max_output_tokens:
            cmd.extend(["--max-output-tokens", str(max_output_tokens)])
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

        # AENDERUNG 25.02.2026: Fix 85 — Popen statt subprocess.run fuer kill_active_process()
        # ROOT-CAUSE-FIX:
        # Symptom: Reset stoppt CLI-Prozess nicht (subprocess.run blockiert bis Timeout)
        # Ursache: subprocess.run() ist nicht unterbrechbar von aussen
        # Loesung: Popen + communicate() + _current_process Tracking → kill() bei Reset
        proc = subprocess.Popen(
            cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, env=env
        )
        self._current_process = proc
        try:
            stdout, stderr = proc.communicate(input=prompt, timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()
            raise
        finally:
            self._current_process = None

        if proc.returncode != 0 and max_output_tokens:
            combined_err = f"{stdout or ''}\n{stderr or ''}".lower()
            if "unknown option" in combined_err or "unknown argument" in combined_err:
                cmd_without_max = list(cmd)
                if "--max-output-tokens" in cmd_without_max:
                    idx = cmd_without_max.index("--max-output-tokens")
                    del cmd_without_max[idx : idx + 2]
                proc2 = subprocess.Popen(
                    cmd_without_max, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE, text=True, env=env
                )
                self._current_process = proc2
                try:
                    stdout, stderr = proc2.communicate(input=prompt, timeout=timeout_seconds)
                except subprocess.TimeoutExpired:
                    proc2.kill()
                    proc2.communicate()
                    raise
                finally:
                    self._current_process = None
                proc = proc2

        if proc.returncode != 0:
            # AENDERUNG 24.02.2026: Fix 76d — Bessere Fehler-Diagnostik
            # Manche CLIs schreiben Fehler nach stdout statt stderr
            stderr_excerpt = (stderr or "")[:500]
            stdout_excerpt = (stdout or "")[:500]
            raise RuntimeError(
                f"claude CLI Fehler (Code {proc.returncode}): "
                f"stderr={stderr_excerpt} stdout={stdout_excerpt}"
            )

        output = stdout.strip()
        if not output:
            raise ValueError("claude CLI: Leere Antwort erhalten")

        # AENDERUNG 26.02.2026: Fix 91b — CLI-Output Preview loggen
        # ROOT-CAUSE-FIX:
        # Symptom: 28-Zeichen-Antworten ohne Kontext was zurueckkommt
        # Ursache: _run_cli() gibt Output zurueck ohne zu loggen
        # Loesung: DEBUG-Level Preview fuer alle CLI-Antworten
        logger.debug(
            "CLI %s Output (%d Zeichen): %.100s%s",
            model,
            len(output),
            output,
            "..." if len(output) > 100 else "",
        )

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
        max_output_tokens: Optional[int] = None,
    ) -> str:
        """Synchroner Wrapper fuer async claude-agent-sdk query()."""
        import anyio

        result_container = {"text": "", "error": None, "traceback_obj": None}
        stop_event = threading.Event()

        async def _async_query():
            base_option_kwargs = {
                "system_prompt": system_prompt
                or "Gib nur den angeforderten Output zurueck. Keine Erklaerungen oder Kommentare ausserhalb des angeforderten Formats.",
                "allowed_tools": tools or [],
                "max_turns": max_turns,
                "cwd": cwd,
                "include_partial_messages": True,
            }

            token_keys = ["max_output_tokens", "max_tokens", "max_tokens_to_sample"]
            token_variants = [None]
            if max_output_tokens and int(max_output_tokens) > 0:
                token_variants = token_keys + [None]

            last_error = None
            options = None
            for token_key in token_variants:
                option_kwargs = dict(base_option_kwargs)
                if token_key:
                    option_kwargs[token_key] = int(max_output_tokens)
                try:
                    options = state._sdk_options_class(**option_kwargs)
                    break
                except TypeError as e:
                    last_error = e
                    option_kwargs.pop("include_partial_messages", None)
                    try:
                        options = state._sdk_options_class(**option_kwargs)
                        break
                    except TypeError as e2:
                        last_error = e2
                        continue

            if options is None and last_error is not None:
                raise last_error

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
