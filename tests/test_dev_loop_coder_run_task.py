# -*- coding: utf-8 -*-
"""
Tests fuer run_coder_task in backend/dev_loop_coder.py.
Fokus: Model-Unavailable Verhalten (z.B. "no endpoints found").
"""

from unittest.mock import MagicMock, patch

import pytest


def _make_manager():
    manager = MagicMock()
    manager.config = {"agent_timeouts": {"coder": 60}}
    manager.model_router = MagicMock()
    manager.model_router.get_model.return_value = "openrouter/dead-model"
    manager._ui_log = MagicMock()
    return manager


@patch("backend.claude_sdk.run_sdk_with_retry", return_value=None)
@patch("backend.dev_loop_coder._clean_model_output", side_effect=lambda x: x)
@patch("backend.dev_loop_coder.Task")
@patch("backend.dev_loop_coder.run_with_heartbeat")
@patch("backend.dev_loop_coder.init_agents")
@patch("backend.dev_loop_coder.handle_model_error", return_value="permanent")
@patch("backend.dev_loop_coder.is_model_unavailable_error", return_value=True)
@patch("backend.dev_loop_coder.is_openrouter_error", return_value=False)
@patch("backend.dev_loop_coder.is_litellm_internal_error", return_value=False)
@patch("backend.dev_loop_coder.is_rate_limit_error", return_value=False)
@patch("backend.dev_loop_coder.is_server_error", return_value=False)
def test_run_coder_task_model_unavailable_wechselt_sofort(
    _mock_server,
    _mock_rate,
    _mock_litellm,
    _mock_openrouter,
    _mock_unavailable,
    mock_handle_model_error,
    mock_init_agents,
    mock_run_with_heartbeat,
    _mock_task,
    _mock_clean,
    _mock_sdk,
):
    """Bei no-endpoints Fehler wird sofort gewechselt und der naechste Versuch kann erfolgreich sein."""
    from backend.dev_loop_coder import run_coder_task

    manager = _make_manager()
    initial_agent = MagicMock(name="initial_coder")
    switched_agent = MagicMock(name="switched_coder")
    mock_init_agents.return_value = {"coder": switched_agent}

    mock_run_with_heartbeat.side_effect = [
        Exception("OpenrouterException - No endpoints found for deepseek/deepseek-r1-0528:free"),
        "FINAL CODE",
    ]

    code, used_agent = run_coder_task(manager, {}, "prompt", initial_agent)

    assert code == "FINAL CODE"
    assert used_agent is switched_agent
    mock_handle_model_error.assert_called_once()
    assert mock_init_agents.call_count == 1


@patch("backend.claude_sdk.run_sdk_with_retry", return_value=None)
@patch("backend.dev_loop_coder._clean_model_output", side_effect=lambda x: x)
@patch("backend.dev_loop_coder.Task")
@patch("backend.dev_loop_coder.run_with_heartbeat")
@patch("backend.dev_loop_coder.init_agents")
@patch("backend.dev_loop_coder.handle_model_error", return_value="permanent")
@patch("backend.dev_loop_coder.is_model_unavailable_error", return_value=True)
@patch("backend.dev_loop_coder.is_openrouter_error", return_value=False)
@patch("backend.dev_loop_coder.is_litellm_internal_error", return_value=False)
@patch("backend.dev_loop_coder.is_rate_limit_error", return_value=False)
@patch("backend.dev_loop_coder.is_server_error", return_value=False)
def test_run_coder_task_model_unavailable_nach_max_retries_fehler(
    _mock_server,
    _mock_rate,
    _mock_litellm,
    _mock_openrouter,
    _mock_unavailable,
    mock_handle_model_error,
    mock_init_agents,
    mock_run_with_heartbeat,
    _mock_task,
    _mock_clean,
    _mock_sdk,
):
    """Wenn alle Coder-Versuche model-unavailable sind, wird ein Fehler geworfen."""
    from backend.dev_loop_coder import run_coder_task

    manager = _make_manager()
    initial_agent = MagicMock(name="initial_coder")
    mock_init_agents.return_value = {"coder": MagicMock(name="switched_coder")}
    mock_run_with_heartbeat.side_effect = [
        Exception("OpenrouterException - No endpoints found for deepseek/deepseek-r1-0528:free")
    ] * 6

    with pytest.raises(Exception):
        run_coder_task(manager, {}, "prompt", initial_agent)

    assert mock_handle_model_error.call_count == 6
    assert mock_init_agents.call_count == 6
