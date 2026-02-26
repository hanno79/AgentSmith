# -*- coding: utf-8 -*-
"""
Tests fuer backend/claude_sdk/retry.py.
Fokus: effektives Token-Limit wird vor SDK-Call erzwungen.
"""

from unittest.mock import MagicMock

from backend.claude_sdk.retry import run_sdk_with_retry


def _build_manager():
    manager = MagicMock()
    manager.get_provider.return_value = "claude-sdk"
    manager._ui_log = MagicMock()
    manager._sdk_tier_escalation = None
    manager.get_effective_token_limit = MagicMock(return_value=100)
    manager.force_openrouter_for_claude = MagicMock()
    manager.config = {
        "token_limits": {"coder": 65536},
        "claude_sdk": {
            "agent_models": {"coder": "haiku"},
            "max_retries": 1,
            "max_turns_by_role": {"coder": 5},
            "min_response_chars": 10,
            "cli_mode_roles": [],
        },
    }
    manager.claude_provider = MagicMock()
    return manager


def test_run_sdk_with_retry_enforces_effective_token_limit(monkeypatch):
    manager = _build_manager()
    manager.claude_provider.run_agent.return_value = "ok " * 20

    def fake_run_with_heartbeat(func, **kwargs):
        return func()

    monkeypatch.setattr("backend.heartbeat_utils.run_with_heartbeat", fake_run_with_heartbeat)
    monkeypatch.setattr(
        "backend.dev_loop_coder_utils._clean_model_output", lambda text: text
    )

    long_prompt = "A" * 5000
    result = run_sdk_with_retry(
        manager,
        role="coder",
        prompt=long_prompt,
        timeout_seconds=30,
        agent_display_name="Coder",
    )

    assert result is not None
    kwargs = manager.claude_provider.run_agent.call_args.kwargs
    assert kwargs["max_output_tokens"] == 100
    assert len(kwargs["prompt"]) <= 300


def test_run_sdk_with_retry_switches_to_openrouter_on_hard_limit_output(monkeypatch):
    manager = _build_manager()
    manager.config["claude_sdk"]["max_retries"] = 3
    manager.config["claude_sdk"]["min_response_chars"] = 200
    manager.claude_provider.run_agent.return_value = "You've hit your limit · resets 6pm (UTC)"

    monkeypatch.setattr("backend.heartbeat_utils.run_with_heartbeat", lambda func, **kwargs: func())
    monkeypatch.setattr("backend.dev_loop_coder_utils._clean_model_output", lambda text: text)

    result = run_sdk_with_retry(
        manager,
        role="coder",
        prompt="fix this",
        timeout_seconds=30,
        agent_display_name="Coder",
    )

    assert result is None
    manager.force_openrouter_for_claude.assert_called_once()
    assert manager.claude_provider.run_agent.call_count == 1


def test_run_sdk_with_retry_switches_to_openrouter_on_hard_limit_exception(monkeypatch):
    manager = _build_manager()
    manager.config["claude_sdk"]["max_retries"] = 3
    manager.claude_provider.run_agent.side_effect = RuntimeError(
        "claude CLI Fehler (Code 1): You've hit your limit · resets 6pm (UTC)"
    )

    monkeypatch.setattr("backend.heartbeat_utils.run_with_heartbeat", lambda func, **kwargs: func())
    monkeypatch.setattr("backend.dev_loop_coder_utils._clean_model_output", lambda text: text)

    result = run_sdk_with_retry(
        manager,
        role="coder",
        prompt="fix this",
        timeout_seconds=30,
        agent_display_name="Coder",
    )

    assert result is None
    manager.force_openrouter_for_claude.assert_called_once()
    assert manager.claude_provider.run_agent.call_count == 1


def test_run_sdk_with_retry_trips_global_fallback_on_persistent_short_responses(monkeypatch):
    manager = _build_manager()
    manager.config["claude_sdk"]["max_retries"] = 2
    manager.config["claude_sdk"]["min_response_chars"] = 200
    manager.config["claude_sdk"]["short_response_global_fallback_threshold"] = 2
    manager.claude_provider.run_agent.return_value = "too short"

    monkeypatch.setattr("backend.heartbeat_utils.run_with_heartbeat", lambda func, **kwargs: func())
    monkeypatch.setattr("backend.dev_loop_coder_utils._clean_model_output", lambda text: text)

    result_1 = run_sdk_with_retry(
        manager,
        role="coder",
        prompt="fix this",
        timeout_seconds=30,
        agent_display_name="Coder",
    )
    assert result_1 is None
    manager.force_openrouter_for_claude.assert_not_called()

    result_2 = run_sdk_with_retry(
        manager,
        role="coder",
        prompt="fix this",
        timeout_seconds=30,
        agent_display_name="Coder",
    )
    assert result_2 is None
    manager.force_openrouter_for_claude.assert_called_once()
    assert manager._claude_short_response_guard["total_failures"] == 2
    assert manager._claude_short_response_guard["by_role"]["coder"] == 2


def test_run_sdk_with_retry_clears_short_response_guard_after_success(monkeypatch):
    manager = _build_manager()
    manager.config["claude_sdk"]["max_retries"] = 1
    manager.config["claude_sdk"]["min_response_chars"] = 10
    manager._claude_short_response_guard = {"total_failures": 3, "by_role": {"coder": 2, "fix": 1}}
    manager.claude_provider.run_agent.return_value = "x" * 40

    monkeypatch.setattr("backend.heartbeat_utils.run_with_heartbeat", lambda func, **kwargs: func())
    monkeypatch.setattr("backend.dev_loop_coder_utils._clean_model_output", lambda text: text)

    result = run_sdk_with_retry(
        manager,
        role="coder",
        prompt="fix this",
        timeout_seconds=30,
        agent_display_name="Coder",
    )

    assert result is not None
    assert manager._claude_short_response_guard == {"total_failures": 0, "by_role": {}}


def test_run_sdk_with_retry_accepts_security_secure_short_sentinel(monkeypatch):
    manager = _build_manager()
    manager.config["claude_sdk"]["max_retries"] = 2
    manager.config["claude_sdk"]["min_response_chars"] = 200
    manager.claude_provider.run_agent.return_value = "SECURE"

    monkeypatch.setattr("backend.heartbeat_utils.run_with_heartbeat", lambda func, **kwargs: func())
    monkeypatch.setattr("backend.dev_loop_coder_utils._clean_model_output", lambda text: text)

    result = run_sdk_with_retry(
        manager,
        role="security",
        prompt="scan this code",
        timeout_seconds=30,
        agent_display_name="Security",
    )

    assert result == "SECURE"
    manager.force_openrouter_for_claude.assert_not_called()
    assert manager.claude_provider.run_agent.call_count == 1


def test_run_sdk_with_retry_accepts_fix_correction_format_even_if_short(monkeypatch):
    manager = _build_manager()
    manager.config["claude_sdk"]["max_retries"] = 1
    manager.config["claude_sdk"]["min_response_chars"] = 200
    manager.claude_provider.run_agent.return_value = (
        "### CORRECTION: app.js\n```javascript\nconsole.log('ok');\n```"
    )

    monkeypatch.setattr("backend.heartbeat_utils.run_with_heartbeat", lambda func, **kwargs: func())
    monkeypatch.setattr("backend.dev_loop_coder_utils._clean_model_output", lambda text: text)

    result = run_sdk_with_retry(
        manager,
        role="fix",
        prompt="fix file",
        timeout_seconds=30,
        agent_display_name="Fix",
    )

    assert result is not None
    assert "### CORRECTION:" in result


def test_run_sdk_with_retry_rejects_fix_output_without_correction_format(monkeypatch):
    manager = _build_manager()
    manager.config["claude_sdk"]["max_retries"] = 1
    manager.config["claude_sdk"]["min_response_chars"] = 10
    manager.claude_provider.run_agent.return_value = "x" * 250

    monkeypatch.setattr("backend.heartbeat_utils.run_with_heartbeat", lambda func, **kwargs: func())
    monkeypatch.setattr("backend.dev_loop_coder_utils._clean_model_output", lambda text: text)

    result = run_sdk_with_retry(
        manager,
        role="fix",
        prompt="fix file",
        timeout_seconds=30,
        agent_display_name="Fix",
    )

    assert result is None


def test_run_sdk_with_retry_accepts_task_deriver_with_parseable_task_json(monkeypatch):
    manager = _build_manager()
    manager.config["claude_sdk"]["max_retries"] = 1
    manager.config["claude_sdk"]["min_response_chars"] = 200
    manager.claude_provider.run_agent.return_value = '{"tasks":[{"title":"T1"}]}'

    monkeypatch.setattr("backend.heartbeat_utils.run_with_heartbeat", lambda func, **kwargs: func())
    monkeypatch.setattr("backend.dev_loop_coder_utils._clean_model_output", lambda text: text)

    result = run_sdk_with_retry(
        manager,
        role="task_deriver",
        prompt="derive",
        timeout_seconds=30,
        agent_display_name="TaskDeriver",
    )

    assert result == '{"tasks":[{"title":"T1"}]}'
