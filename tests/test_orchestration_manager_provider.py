# -*- coding: utf-8 -*-
"""
Tests fuer Provider-Entscheidung im OrchestrationManager.
"""

from backend.orchestration_manager import OrchestrationManager


def _build_manager_stub():
    mgr = OrchestrationManager.__new__(OrchestrationManager)
    mgr.claude_provider = object()
    mgr.config = {"claude_sdk": {"agent_models": {"coder": "haiku", "fix": "sonnet"}}}
    mgr._force_openrouter_for_claude = False
    mgr._force_openrouter_reason = ""
    mgr._force_openrouter_activated_at = None
    mgr._claude_short_response_guard = {"total_failures": 2, "by_role": {"fix": 2}}
    mgr._ui_log = lambda *args, **kwargs: None
    return mgr


def test_get_provider_prefers_claude_sdk_when_available():
    mgr = _build_manager_stub()
    assert mgr.get_provider("coder") == "claude-sdk"


def test_get_provider_switches_to_openrouter_after_circuit_breaker():
    mgr = _build_manager_stub()
    mgr.force_openrouter_for_claude("You've hit your limit")
    assert mgr.get_provider("coder") == "openrouter"
    assert mgr.get_provider("fix") == "openrouter"


def test_get_provider_returns_claude_after_reset():
    mgr = _build_manager_stub()
    mgr.force_openrouter_for_claude("You've hit your limit")
    mgr.reset_claude_provider_override()
    assert mgr.get_provider("coder") == "claude-sdk"


def test_reset_claude_provider_override_clears_short_response_guard():
    mgr = _build_manager_stub()
    mgr.force_openrouter_for_claude("Persistent short responses")
    mgr.reset_claude_provider_override()
    assert mgr._claude_short_response_guard == {"total_failures": 0, "by_role": {}}
