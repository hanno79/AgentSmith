# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 21.02.2026
Version: 1.0
Beschreibung: Claude Agent SDK Provider - Synchroner Wrapper fuer claude-agent-sdk.
              Ermoeglicht die Nutzung von Claude-Modellen (Opus, Sonnet, Haiku) als
              zusaetzliches LLM-Backend neben OpenRouter/LiteLLM.
              Integriert sich nahtlos in die bestehende Output-Pipeline:
              - set_current_agent() VOR Aufruf (Budget-Tracking)
              - ModelStatsDB.record_call() NACH Aufruf (Latenz, Statistiken)
              - BudgetTracker.record_usage() NACH Aufruf (Token-Summen)
              - _ui_log() Callbacks fuer WebSocket + Library + Session
"""

import logging
import time
import threading
from typing import Optional, Callable

logger = logging.getLogger(__name__)

# =====================================================================
# Lazy Imports: claude-agent-sdk wird erst beim ersten Aufruf geladen
# =====================================================================
_sdk_loaded = False
_sdk_query = None
_sdk_options_class = None
_sdk_assistant_message = None
_sdk_text_block = None


def _ensure_sdk_loaded():
    """Laedt claude-agent-sdk Lazy beim ersten Aufruf."""
    global _sdk_loaded, _sdk_query, _sdk_options_class, _sdk_assistant_message, _sdk_text_block
    if _sdk_loaded:
        return
    try:
        from claude_agent_sdk import query, ClaudeAgentOptions, AssistantMessage, TextBlock
        _sdk_query = query
        _sdk_options_class = ClaudeAgentOptions
        _sdk_assistant_message = AssistantMessage
        _sdk_text_block = TextBlock
        _sdk_loaded = True
        logger.info("claude-agent-sdk erfolgreich geladen")
    except ImportError as e:
        logger.error("claude-agent-sdk nicht installiert: %s", e)
        raise ImportError(
            "claude-agent-sdk nicht verfuegbar. Installation: pip install claude-agent-sdk"
        ) from e


# =====================================================================
# Claude SDK Provider
# =====================================================================

# Mapping: Kurzname → Vollstaendige Modell-ID
CLAUDE_MODEL_MAP = {
    "opus": "claude-opus-4-6",
    "sonnet": "claude-sonnet-4-6",
    "haiku": "claude-haiku-4-5",
}

# AENDERUNG 21.02.2026: Fix 59h — Tier-Ordnung fuer PingPong-Eskalation
# Tier 0: Einfache Aufgaben (Haiku), Tier 1: Standard (Sonnet), Tier 2: Komplex (Opus)
_SDK_TIER_ORDER = {
    "fix": 0, "tester": 0,
    "coder": 1, "reviewer": 1, "planner": 1, "designer": 1,
    "db_designer": 1, "security": 1, "documentation_manager": 1,
    "researcher": 2, "techstack_architect": 2,
}


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
        """Initialisiert den Provider. SDK wird lazy beim ersten Aufruf geladen."""
        self._initialized = False
        logger.info("ClaudeSDKProvider initialisiert (Lazy-Loading)")

    def _ensure_initialized(self):
        """Stellt sicher, dass das SDK geladen ist."""
        if not self._initialized:
            _ensure_sdk_loaded()
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
        max_turns: int = 1
    ) -> str:
        """
        Fuehrt einen Claude Agent aus und gibt das Ergebnis als String zurueck.

        Bedient alle Tracking-Systeme identisch zu CrewAI Task.execute_sync():
        1. set_current_agent() VOR dem Call
        2. _ui_log() mit "Working" Event
        3. SDK query() ausfuehren
        4. Budget+Stats Tracking NACH dem Call
        5. _ui_log() mit "Result" oder "Error" Event

        Args:
            prompt: Der Prompt fuer den Agenten
            role: Agent-Rolle (z.B. "coder", "reviewer")
            model: Claude Modell ("opus", "sonnet", "haiku")
            tools: Erlaubte Tools (leer = nur Text-Rueckgabe)
            cwd: Arbeitsverzeichnis fuer den Agenten
            system_prompt: Optionaler System-Prompt
            ui_log_callback: Callback fuer UI-Events (manager._ui_log)
            project_id: Projekt-ID fuer Budget-Tracking
            timeout_seconds: Timeout in Sekunden
            max_turns: Maximale Agentic-Turns (1 = Single-Turn)

        Returns:
            Ergebnis-String vom Claude Agent

        Raises:
            TimeoutError: Wenn timeout_seconds ueberschritten
            ImportError: Wenn claude-agent-sdk nicht installiert
            Exception: Bei sonstigen SDK-Fehlern
        """
        self._ensure_initialized()

        model_full = CLAUDE_MODEL_MAP.get(model, model)
        agent_display_name = role.capitalize()

        # 1. set_current_agent (identisch zu dev_loop_coder.py vor execute_sync())
        try:
            from .orchestration_budget import set_current_agent
            set_current_agent(agent_display_name, project_id)
        except ImportError:
            logger.debug("orchestration_budget nicht verfuegbar - Budget-Tracking uebersprungen")

        # 2. UI-Log: Start-Event
        if ui_log_callback:
            ui_log_callback(
                agent_display_name, "Working",
                f"Claude SDK ({model}) generiert..."
            )

        # 3. Zeitmessung starten (wie LiteLLM start_time/end_time)
        start_time = time.time()

        try:
            # 4. Async→Sync Bridge via Thread
            result = self._run_sync(
                prompt=prompt,
                model=model,
                tools=tools,
                cwd=cwd,
                system_prompt=system_prompt,
                max_turns=max_turns,
                timeout_seconds=timeout_seconds
            )

            end_time = time.time()
            latency_ms = (end_time - start_time) * 1000

            # 5. Budget-Tracking (manuell, da kein LiteLLM-Callback)
            prompt_tokens_est = len(prompt) // 3  # Schaetzung: 1 Token ≈ 3 Zeichen
            completion_tokens_est = len(result) // 3
            self._record_success(
                role=role, model=model,
                prompt_tokens=prompt_tokens_est,
                completion_tokens=completion_tokens_est,
                latency_ms=latency_ms, project_id=project_id
            )

            # 6. UI-Log: Result-Event
            if ui_log_callback:
                ui_log_callback(
                    agent_display_name, "Result",
                    f"Claude SDK ({model}): {len(result)} Zeichen in {latency_ms:.0f}ms"
                )

            logger.info(
                "Claude SDK %s (%s): %d Zeichen in %.0fms",
                agent_display_name, model, len(result), latency_ms
            )
            return result

        except Exception as e:
            end_time = time.time()
            latency_ms = (end_time - start_time) * 1000

            # Failure-Tracking
            self._record_failure(
                role=role, model=model,
                latency_ms=latency_ms, project_id=project_id
            )

            # UI-Log: Error-Event
            if ui_log_callback:
                error_msg = str(e)[:200]
                ui_log_callback(
                    agent_display_name, "Error",
                    f"Claude SDK ({model}) Fehler: {error_msg}"
                )

            logger.error(
                "Claude SDK %s (%s) Fehler nach %.0fms: %s",
                agent_display_name, model, latency_ms, e
            )
            raise

    def _run_sync(
        self,
        prompt: str,
        model: str,
        tools: Optional[list],
        cwd: Optional[str],
        system_prompt: Optional[str],
        max_turns: int,
        timeout_seconds: int
    ) -> str:
        """
        Synchroner Wrapper fuer async claude-agent-sdk query().
        Nutzt einen separaten Thread mit eigenem Event-Loop.

        AENDERUNG: ThreadPoolExecutor + anyio.run() im Thread
        (Gleicher Ansatz wie CodeRabbit WSL-Bridge, Fix 33b)
        """
        import anyio

        result_container = {"text": "", "error": None}

        async def _async_query():
            """Async Ausfuehrung des Claude SDK Calls."""
            options = _sdk_options_class(
                system_prompt=system_prompt or "Gib nur den angeforderten Output zurueck. Keine Erklaerungen oder Kommentare ausserhalb des angeforderten Formats.",
                allowed_tools=tools or [],
                max_turns=max_turns,
                cwd=cwd
            )

            result_text = ""
            # AENDERUNG 21.02.2026: rate_limit_event und andere unbekannte
            # Message-Typen graceful behandeln (SDK v0.1.39 kennt diese nicht)
            try:
                async for message in _sdk_query(prompt=prompt, options=options):
                    if hasattr(message, "result") and message.result:
                        result_text = message.result
                    elif hasattr(message, "content"):
                        # Fallback: AssistantMessage Content extrahieren
                        for block in (message.content or []):
                            if hasattr(block, "text"):
                                result_text += block.text
            except Exception as stream_error:
                error_str = str(stream_error).lower()
                # rate_limit_event, system_event etc. sind informativ,
                # nicht fatal — SDK v0.1.39 wirft aber Exception
                if "unknown message type" in error_str:
                    if result_text:
                        logger.warning(
                            "Claude SDK: Unbekannter Message-Typ ignoriert ('%s'), "
                            "verwende bereits empfangenen Text (%d Zeichen)",
                            str(stream_error)[:80], len(result_text)
                        )
                    else:
                        # AENDERUNG 21.02.2026: Fix 59d — Kein Text empfangen
                        # ROOT-CAUSE: SDK puffert intern, rate_limit_event kommt VOR Yield
                        # → Text ist generiert aber nicht zugreifbar
                        # → Als Rate-Limit behandeln (nicht als fatalen Fehler)
                        logger.warning(
                            "Claude SDK: rate_limit_event ohne empfangenen Text. "
                            "API Rate-Limit waehrend Generierung erreicht. "
                            "Fehler: %s", str(stream_error)[:100]
                        )
                        raise RuntimeError(
                            "Claude SDK rate_limit_event: API-Rate-Limit waehrend "
                            "Code-Generierung erreicht. Text wurde intern generiert "
                            "aber vom SDK nicht zurueckgegeben."
                        ) from stream_error
                else:
                    raise

            return result_text

        def _thread_target():
            """Thread-Funktion fuer Async→Sync Bridge."""
            try:
                # AENDERUNG 21.02.2026: CLAUDECODE Env-Var entfernen
                # ROOT-CAUSE-FIX: claude.exe blockiert Start wenn CLAUDECODE=1 gesetzt ist
                # Symptom: "Cannot be launched inside another Claude Code session"
                # Ursache: Env-Var wird vom uebergeordneten Claude Code Prozess vererbt
                # Loesung: Variable entfernen — Server ist kein interaktiver Claude Code
                import os
                os.environ.pop("CLAUDECODE", None)
                result_container["text"] = anyio.run(_async_query)
            except Exception as e:
                result_container["error"] = e

        # Thread starten mit Timeout
        thread = threading.Thread(target=_thread_target, daemon=True)
        thread.start()
        thread.join(timeout=timeout_seconds)

        if thread.is_alive():
            raise TimeoutError(
                f"Claude SDK Timeout nach {timeout_seconds}s "
                f"(Modell: {model})"
            )

        if result_container["error"]:
            raise result_container["error"]

        if not result_container["text"]:
            raise ValueError(
                f"Claude SDK ({model}): Leere Antwort erhalten. "
                "Moeglicherweise zu restriktiver Prompt."
            )

        return result_container["text"]

    # =================================================================
    # Budget + Stats Tracking (ersetzt LiteLLM Callbacks)
    # =================================================================

    def _record_success(
        self,
        role: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        latency_ms: float,
        project_id: Optional[str]
    ):
        """
        Manuelles Budget+Stats Tracking nach erfolgreichem Call.
        Ersetzt _budget_tracking_callback() aus orchestration_budget.py.
        """
        model_full = CLAUDE_MODEL_MAP.get(model, model)
        model_id = f"claude-sdk/{model_full}"

        # BudgetTracker (budget_tracker.py:147)
        try:
            from budget_tracker import get_budget_tracker
            tracker = get_budget_tracker()
            tracker.record_usage(
                agent=role.capitalize(),
                model=model_id,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                project_id=project_id
            )
        except Exception as e:
            logger.debug("BudgetTracker.record_usage() Fehler: %s", e)

        # ModelStatsDB (model_stats_db.py:95)
        try:
            from model_stats_db import get_model_stats_db
            stats_db = get_model_stats_db()
            stats_db.record_call(
                run_id=project_id or "unknown",
                agent=role.capitalize(),
                model=model_id,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                cost_usd=0.0,  # Max Plan = Flat Rate, keine variablen Kosten
                latency_ms=latency_ms,
                success=True
            )
        except Exception as e:
            logger.debug("ModelStatsDB.record_call() Fehler: %s", e)

    def _record_failure(
        self,
        role: str,
        model: str,
        latency_ms: float,
        project_id: Optional[str]
    ):
        """
        Manuelles Failure-Tracking nach fehlgeschlagenem Call.
        Ersetzt _failure_tracking_callback() aus orchestration_budget.py.
        """
        model_full = CLAUDE_MODEL_MAP.get(model, model)
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
                success=False
            )
        except Exception as e:
            logger.debug("ModelStatsDB Failure-Tracking Fehler: %s", e)


# =====================================================================
# Singleton
# =====================================================================

_provider_instance = None
_provider_lock = threading.Lock()


def get_claude_sdk_provider() -> ClaudeSDKProvider:
    """
    Singleton-Getter fuer den ClaudeSDKProvider.
    Thread-Safe via Lock.
    """
    global _provider_instance
    if _provider_instance is None:
        with _provider_lock:
            if _provider_instance is None:
                _provider_instance = ClaudeSDKProvider()
    return _provider_instance


# =====================================================================
# AENDERUNG 21.02.2026: Multi-Tier SDK Helper (DRY-Prinzip, Regel 13)
# Zentrale Retry-Funktion fuer ALLE Agent-Rollen.
# Ersetzt duplizierten Code in dev_loop_coder.py + dev_loop_review.py
# und wird von file_by_file_loop.py, parallel_patch.py etc. genutzt.
# =====================================================================

def run_sdk_with_retry(
    manager,
    role: str,
    prompt: str,
    timeout_seconds: int,
    agent_display_name: str = None,
    max_retries: int = None,
    heartbeat_interval: int = 15
) -> Optional[str]:
    """
    Fuehrt Claude SDK Call mit Retry-Logik aus.

    Prueft ob die Rolle fuer Claude SDK konfiguriert ist, fuehrt den Call
    mit Heartbeat und Retry aus, und bereinigt Think-Tags.

    Args:
        manager: OrchestrationManager mit claude_provider + config
        role: Agent-Rolle (z.B. "coder", "reviewer", "fix")
        prompt: Der vollstaendige Prompt
        timeout_seconds: Timeout pro Versuch
        agent_display_name: Anzeigename fuer UI-Log (Default: role.capitalize())
        max_retries: Max Versuche (Default: config.claude_sdk.max_retries oder 3)
        heartbeat_interval: Heartbeat-Intervall in Sekunden

    Returns:
        Result-String bei Erfolg, None bei Fehler (→ Caller nutzt OpenRouter Fallback)
    """
    # Pruefen ob Claude SDK fuer diese Rolle konfiguriert ist
    if not hasattr(manager, 'claude_provider') or not manager.claude_provider:
        return None

    provider = manager.get_provider(role)
    if provider != "claude-sdk":
        return None

    # Lazy Import (vermeidet zirkulaere Abhaengigkeiten)
    from .heartbeat_utils import run_with_heartbeat
    from .dev_loop_coder_utils import _clean_model_output

    sdk_config = manager.config.get("claude_sdk", {})
    claude_model = sdk_config.get("agent_models", {}).get(role, sdk_config.get("default_model", "sonnet"))
    display_name = agent_display_name or role.capitalize()
    retries = max_retries or sdk_config.get("max_retries", 3)

    # AENDERUNG 21.02.2026: Fix 59h — PingPong Tier-Eskalation (Haiku→Sonnet→Opus)
    tier_override = getattr(manager, '_sdk_tier_escalation', None)
    if tier_override and _SDK_TIER_ORDER.get(tier_override, 0) > _SDK_TIER_ORDER.get(role, 0):
        override_model = sdk_config.get("agent_models", {}).get(tier_override, "sonnet")
        manager._ui_log(display_name, "TierEscalation",
            f"PingPong-Eskalation: {role}({claude_model}) → {tier_override}({override_model})")
        claude_model = override_model
        role = tier_override

    for sdk_attempt in range(retries):
        try:
            raw_output = run_with_heartbeat(
                func=lambda: manager.claude_provider.run_agent(
                    prompt=prompt,
                    role=role,
                    model=claude_model,
                    ui_log_callback=manager._ui_log,
                    project_id=getattr(manager, '_stats_run_id', None) or getattr(manager, 'project_id', None),
                    timeout_seconds=timeout_seconds
                ),
                ui_log_callback=manager._ui_log,
                agent_name=display_name,
                task_description=f"Claude SDK ({claude_model}) Versuch {sdk_attempt + 1}/{retries}",
                heartbeat_interval=heartbeat_interval,
                timeout_seconds=timeout_seconds + 60
            )

            # Think-Tags bereinigen
            cleaned = _clean_model_output(raw_output)
            if cleaned != raw_output:
                manager._ui_log(display_name, "ThinkTagFilter",
                                "Model-Output bereinigt (Think-Tags entfernt)")

            if cleaned:
                return cleaned

        except Exception as sdk_error:
            manager._ui_log(display_name, "Warning",
                            f"Claude SDK Versuch {sdk_attempt + 1}/{retries} fehlgeschlagen: "
                            f"{str(sdk_error)[:200]}")
            if sdk_attempt < retries - 1:
                continue

            # Alle Retries erschoepft → Fallback signalisieren
            manager._ui_log(display_name, "Warning",
                            f"Claude SDK erschoepft nach {retries} Versuchen, Fallback auf OpenRouter")
            logger.warning("Claude SDK %s (%s) fehlgeschlagen nach %d Versuchen, Fallback: %s",
                           display_name, claude_model, retries, sdk_error)

    return None
