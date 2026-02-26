# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 21.02.2026
Version: 1.0
Beschreibung: Unit-Tests fuer ClaudeSDKProvider (backend/claude_sdk_provider.py).
              Testet: Pipeline-Integration, Budget-Tracking, Fehlerbehandlung, Singleton.
              Alle SDK-Calls werden gemockt (kein echter API-Aufruf noetig).
"""

import os
import sys
import types
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

# Projekt-Root zum Path hinzufuegen
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# =========================================================================
# Fixtures
# =========================================================================

@pytest.fixture(autouse=True)
def reset_singleton():
    """Setzt den Provider-Singleton vor jedem Test zurueck."""
    import backend.claude_sdk.loader as loader
    import backend.claude_sdk.provider as provider_mod
    provider_mod._provider_instance = None
    loader._sdk_loaded = False
    loader._sdk_query = None
    loader._sdk_options_class = None
    loader._sdk_assistant_message = None
    loader._sdk_text_block = None
    loader._sdk_stream_event = None
    loader._sdk_result_message = None
    yield
    provider_mod._provider_instance = None
    loader._sdk_loaded = False


@pytest.fixture
def mock_sdk():
    """Mockt claude-agent-sdk Imports und gibt Mock-Objekte zurueck."""
    mock_query = MagicMock()
    mock_options_class = MagicMock()
    mock_assistant_message = MagicMock()
    mock_text_block = MagicMock()
    mock_result_message = MagicMock()
    mock_stream_event = type("StreamEvent", (), {})

    sdk_mod = types.ModuleType("claude_agent_sdk")
    sdk_mod.query = mock_query
    sdk_mod.ClaudeAgentOptions = mock_options_class
    sdk_mod.AssistantMessage = mock_assistant_message
    sdk_mod.TextBlock = mock_text_block
    sdk_mod.ResultMessage = mock_result_message

    sdk_types_mod = types.ModuleType("claude_agent_sdk.types")
    sdk_types_mod.StreamEvent = mock_stream_event

    with patch.dict('sys.modules', {
        'claude_agent_sdk': sdk_mod,
        'claude_agent_sdk.types': sdk_types_mod,
    }):
        yield {
            "query": mock_query,
            "options_class": mock_options_class,
            "assistant_message": mock_assistant_message,
            "text_block": mock_text_block,
            "result_message": mock_result_message,
            "stream_event": mock_stream_event,
        }


@pytest.fixture
def provider(mock_sdk):
    """Erstellt einen initialisierten ClaudeSDKProvider mit gemocktem SDK."""
    from backend.claude_sdk_provider import ClaudeSDKProvider, _ensure_sdk_loaded
    _ensure_sdk_loaded()
    p = ClaudeSDKProvider()
    return p


# =========================================================================
# Test: CLAUDE_MODEL_MAP
# =========================================================================

class TestClaudeModelMap:
    """Tests fuer das Modell-Mapping."""

    def test_opus_mapping(self):
        from backend.claude_sdk_provider import CLAUDE_MODEL_MAP
        # AENDERUNG 25.02.2026: Fix 83 — Aktualisiert auf Opus 4.6
        assert CLAUDE_MODEL_MAP["opus"] == "claude-opus-4-6"

    def test_sonnet_mapping(self):
        from backend.claude_sdk_provider import CLAUDE_MODEL_MAP
        # AENDERUNG 25.02.2026: Fix 83 — Aktualisiert auf Sonnet 4.6
        assert CLAUDE_MODEL_MAP["sonnet"] == "claude-sonnet-4-6"

    def test_haiku_mapping(self):
        from backend.claude_sdk_provider import CLAUDE_MODEL_MAP
        assert CLAUDE_MODEL_MAP["haiku"] == "claude-haiku-4-5-20251001"


# =========================================================================
# Test: Singleton
# =========================================================================

class TestSingleton:
    """Tests fuer den Singleton-Getter."""

    def test_singleton_gibt_gleiche_instanz(self, mock_sdk):
        from backend.claude_sdk_provider import get_claude_sdk_provider
        p1 = get_claude_sdk_provider()
        p2 = get_claude_sdk_provider()
        assert p1 is p2, "Singleton muss dieselbe Instanz zurueckgeben"

    def test_singleton_thread_safe(self, mock_sdk):
        """Prueft dass der Singleton auch bei parallelen Zugriffen konsistent ist."""
        import threading
        from backend.claude_sdk_provider import get_claude_sdk_provider

        results = []

        def get_instance():
            results.append(get_claude_sdk_provider())

        threads = [threading.Thread(target=get_instance) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Alle 10 Instanzen muessen identisch sein
        assert all(r is results[0] for r in results), "Erwartet: Alle Threads erhalten dieselbe Instanz"


# =========================================================================
# Test: run_agent — Erfolgsfall
# =========================================================================

class TestRunAgentSuccess:
    """Tests fuer erfolgreiche run_agent() Aufrufe."""

    def test_run_agent_gibt_text_zurueck(self, provider):
        """Prueft dass run_agent() den Ergebnis-Text zurueckgibt."""
        with patch.object(provider, '_run_sync', return_value="Generierter Code hier"):
            result = provider.run_agent(
                prompt="Erstelle eine Hello-World App",
                role="coder",
                model="sonnet"
            )
            assert result == "Generierter Code hier"

    @patch.object(
        __import__('backend.claude_sdk_provider', fromlist=['ClaudeSDKProvider']).ClaudeSDKProvider,
        '_run_sync',
        return_value="Test-Ergebnis"
    )
    def test_run_agent_ruft_set_current_agent_auf(self, mock_run_sync, provider):
        """Prueft dass set_current_agent() VOR dem Call aufgerufen wird."""
        # Lazy-Import: set_current_agent wird innerhalb run_agent() aus orchestration_budget importiert
        with patch('backend.orchestration_budget.set_current_agent') as mock_set_agent:
            provider.run_agent(
                prompt="Test",
                role="coder",
                model="sonnet",
                project_id="test-projekt"
            )
            mock_set_agent.assert_called_once_with("Coder", "test-projekt")

    @patch.object(
        __import__('backend.claude_sdk_provider', fromlist=['ClaudeSDKProvider']).ClaudeSDKProvider,
        '_run_sync',
        return_value="Review-OK"
    )
    def test_run_agent_ruft_ui_log_callback_auf(self, mock_run_sync, provider):
        """Prueft dass ui_log_callback mit 'Working' und 'Result' Events aufgerufen wird."""
        mock_callback = MagicMock()
        provider.run_agent(
            prompt="Review-Prompt",
            role="reviewer",
            model="sonnet",
            ui_log_callback=mock_callback
        )
        # Pruefen: Working-Event
        calls = [c[0] for c in mock_callback.call_args_list]
        event_types = [c[1] for c in calls]
        assert "Working" in event_types, "Erwartet: 'Working' Event"
        assert "Result" in event_types, "Erwartet: 'Result' Event"

    @patch.object(
        __import__('backend.claude_sdk_provider', fromlist=['ClaudeSDKProvider']).ClaudeSDKProvider,
        '_run_sync',
        return_value="Code-Output"
    )
    def test_run_agent_ruft_record_success_auf(self, mock_run_sync, provider):
        """Prueft dass Budget+Stats Tracking nach erfolgreichem Call aufgerufen wird."""
        with patch.object(provider, '_record_success') as mock_record:
            provider.run_agent(prompt="Test", role="coder", model="opus")
            mock_record.assert_called_once()
            call_args = mock_record.call_args
            assert call_args.kwargs.get("role") == "coder" or call_args[1].get("role") == "coder" \
                or (len(call_args[0]) > 0 and call_args[0][0] == "coder")


# =========================================================================
# Test: run_agent — Fehlerfall
# =========================================================================

class TestRunAgentFailure:
    """Tests fuer Fehlerfaelle bei run_agent()."""

    @patch.object(
        __import__('backend.claude_sdk_provider', fromlist=['ClaudeSDKProvider']).ClaudeSDKProvider,
        '_run_sync',
        side_effect=TimeoutError("Claude SDK Timeout nach 750s")
    )
    def test_timeout_wird_weitergeleitet(self, mock_run_sync, provider):
        """Prueft dass TimeoutError korrekt weitergeleitet wird."""
        with pytest.raises(TimeoutError, match="Timeout"):
            provider.run_agent(prompt="Test", role="coder", model="sonnet")

    @patch.object(
        __import__('backend.claude_sdk_provider', fromlist=['ClaudeSDKProvider']).ClaudeSDKProvider,
        '_run_sync',
        side_effect=ValueError("Leere Antwort erhalten")
    )
    def test_leere_antwort_wird_als_fehler_gemeldet(self, mock_run_sync, provider):
        """Prueft dass leere Antworten als Fehler behandelt werden."""
        with pytest.raises(ValueError, match="Leere Antwort"):
            provider.run_agent(prompt="Test", role="coder", model="sonnet")

    @patch.object(
        __import__('backend.claude_sdk_provider', fromlist=['ClaudeSDKProvider']).ClaudeSDKProvider,
        '_run_sync',
        side_effect=RuntimeError("SDK-Fehler")
    )
    def test_fehler_ruft_record_failure_auf(self, mock_run_sync, provider):
        """Prueft dass Failure-Tracking bei Fehler aufgerufen wird."""
        with patch.object(provider, '_record_failure') as mock_record:
            with pytest.raises(RuntimeError):
                provider.run_agent(prompt="Test", role="coder", model="opus")
            mock_record.assert_called_once()

    @patch.object(
        __import__('backend.claude_sdk_provider', fromlist=['ClaudeSDKProvider']).ClaudeSDKProvider,
        '_run_sync',
        side_effect=RuntimeError("SDK kaputt")
    )
    def test_fehler_sendet_error_ui_log(self, mock_run_sync, provider):
        """Prueft dass bei Fehler ein Error-Event an UI geloggt wird."""
        mock_callback = MagicMock()
        with pytest.raises(RuntimeError):
            provider.run_agent(
                prompt="Test", role="coder", model="sonnet",
                ui_log_callback=mock_callback
            )
        calls = [c[0] for c in mock_callback.call_args_list]
        event_types = [c[1] for c in calls]
        assert "Error" in event_types, "Erwartet: 'Error' Event bei Fehler"


# =========================================================================
# Test: _record_success und _record_failure
# =========================================================================

class TestRecordTracking:
    """Tests fuer Budget- und Stats-Tracking."""

    def test_record_success_modell_id_format(self, provider):
        """Prueft dass die Modell-ID als 'claude-sdk/claude-opus-4-1-20250805' formatiert wird."""
        # Lazy-Imports: budget_tracker und model_stats_db werden innerhalb der Methode importiert
        with patch('budget_tracker.get_budget_tracker') as mock_bt, \
             patch('model_stats_db.get_model_stats_db') as mock_stats:
            mock_bt.return_value = MagicMock()
            mock_stats.return_value = MagicMock()

            provider._record_success(
                role="coder", model="opus",
                prompt_tokens=1000, completion_tokens=500,
                latency_ms=5000.0, project_id="test-id"
            )

            # BudgetTracker Aufruf pruefen
            bt_call = mock_bt.return_value.record_usage.call_args
            # AENDERUNG 25.02.2026: Fix 83 — Aktualisiert auf Opus 4.6
            assert "claude-sdk/claude-opus-4-6" in str(bt_call), \
                f"Erwartet: claude-sdk/claude-opus-4-6, Erhalten: {bt_call}"

    def test_record_success_stats_db_aufruf(self, provider):
        """Prueft dass ModelStatsDB.record_call() mit korrekten Parametern aufgerufen wird."""
        with patch('model_stats_db.get_model_stats_db') as mock_stats:
            mock_db = MagicMock()
            mock_stats.return_value = mock_db

            provider._record_success(
                role="reviewer", model="sonnet",
                prompt_tokens=2000, completion_tokens=300,
                latency_ms=8000.0, project_id="projekt-42"
            )

            mock_db.record_call.assert_called_once()
            call_kwargs = mock_db.record_call.call_args.kwargs if mock_db.record_call.call_args.kwargs else {}
            # Alternativ: positional args
            if call_kwargs:
                assert call_kwargs.get("success") is True
                # AENDERUNG 25.02.2026: Fix 83 — Aktualisiert auf Sonnet 4.6
                assert call_kwargs.get("model") == "claude-sdk/claude-sonnet-4-6"
                assert call_kwargs.get("run_id") == "projekt-42"

    def test_record_failure_success_false(self, provider):
        """Prueft dass Failure-Tracking mit success=False aufgerufen wird."""
        with patch('model_stats_db.get_model_stats_db') as mock_stats:
            mock_db = MagicMock()
            mock_stats.return_value = mock_db

            provider._record_failure(
                role="coder", model="haiku",
                latency_ms=1000.0, project_id="fail-test"
            )

            mock_db.record_call.assert_called_once()
            call_kwargs = mock_db.record_call.call_args.kwargs if mock_db.record_call.call_args.kwargs else {}
            if call_kwargs:
                assert call_kwargs.get("success") is False

    def test_record_success_graceful_bei_import_fehler(self, provider):
        """Prueft dass Tracking-Fehler (z.B. ImportError) nicht crashen."""
        with patch('budget_tracker.get_budget_tracker', side_effect=ImportError("test")), \
             patch('model_stats_db.get_model_stats_db', side_effect=ImportError("test")):
            # Darf NICHT crashen
            provider._record_success(
                role="coder", model="opus",
                prompt_tokens=0, completion_tokens=0,
                latency_ms=0.0, project_id=None
            )


# =========================================================================
# Test: is_claude_sdk_error (orchestration_helpers.py)
# =========================================================================

class TestIsClaudeSdkError:
    """Tests fuer die Claude SDK Fehlererkennung."""

    def test_erkennt_claude_sdk_fehler(self):
        from backend.orchestration_helpers import is_claude_sdk_error
        error = RuntimeError("Claude SDK Timeout nach 750s")
        assert is_claude_sdk_error(error) is True

    def test_erkennt_import_error(self):
        from backend.orchestration_helpers import is_claude_sdk_error
        error = ImportError("claude-agent-sdk nicht verfuegbar")
        assert is_claude_sdk_error(error) is True

    def test_erkennt_anyio_fehler(self):
        from backend.orchestration_helpers import is_claude_sdk_error
        error = RuntimeError("anyio.BrokenResourceError: connection lost")
        assert is_claude_sdk_error(error) is True

    def test_erkennt_openrouter_nicht_als_sdk(self):
        from backend.orchestration_helpers import is_claude_sdk_error
        error = RuntimeError("litellm.Timeout: OpenrouterException - Provider returned error")
        assert is_claude_sdk_error(error) is False

    def test_erkennt_rate_limit_nicht_als_sdk(self):
        from backend.orchestration_helpers import is_claude_sdk_error
        error = RuntimeError("Rate limit exceeded for model gpt-4")
        assert is_claude_sdk_error(error) is False


# =========================================================================
# Test: SDK Lazy-Loading
# =========================================================================

class TestLazyLoading:
    """Tests fuer das Lazy-Loading des SDK."""

    def test_sdk_wird_nicht_beim_import_geladen(self):
        """Prueft dass das SDK erst beim ersten Aufruf geladen wird."""
        import backend.claude_sdk.loader as loader
        assert loader._sdk_loaded is False, "SDK darf beim Import noch NICHT geladen sein"

    def test_sdk_wird_bei_ensure_geladen(self, mock_sdk):
        """Prueft dass _ensure_sdk_loaded() das SDK laedt."""
        import backend.claude_sdk.loader as loader
        loader._ensure_sdk_loaded()
        assert loader._sdk_loaded is True

    def test_import_error_bei_fehlendem_sdk(self):
        """Prueft dass ImportError geworfen wird wenn SDK nicht installiert."""
        import backend.claude_sdk.loader as loader
        # Sicherstellen dass kein echtes claude_agent_sdk verfuegbar
        with patch.dict('sys.modules', {'claude_agent_sdk': None, 'claude_agent_sdk.types': None}):
            loader._sdk_loaded = False
            with pytest.raises(ImportError, match="claude-agent-sdk"):
                loader._ensure_sdk_loaded()


# =========================================================================
# Test: Token-Schaetzung
# =========================================================================

class TestTokenSchaetzung:
    """Tests fuer die zeichenbasierte Token-Schaetzung."""

    @patch.object(
        __import__('backend.claude_sdk_provider', fromlist=['ClaudeSDKProvider']).ClaudeSDKProvider,
        '_run_sync',
        return_value="x" * 3000  # 3000 Zeichen = ~1000 Tokens
    )
    def test_token_schaetzung_ratio_3(self, mock_run_sync, provider):
        """Prueft dass Token-Schaetzung mit Ratio ~3 Zeichen/Token funktioniert."""
        with patch.object(provider, '_record_success') as mock_record:
            provider.run_agent(
                prompt="a" * 9000,  # 9000 Zeichen = ~3000 Tokens
                role="coder",
                model="sonnet"
            )
            call_args = mock_record.call_args
            # prompt_tokens sollte ~3000 sein (9000 // 3)
            # completion_tokens sollte ~1000 sein (3000 // 3)
            if call_args.kwargs:
                assert call_args.kwargs.get("prompt_tokens") == 3000
                assert call_args.kwargs.get("completion_tokens") == 1000


# =========================================================================
# Test: rate_limit_event Handling (Fix 21.02.2026)
# =========================================================================

class TestRateLimitEventHandling:
    """Tests fuer graceful Behandlung von unbekannten Message-Typen im Stream."""

    def test_rate_limit_event_mit_text_gibt_text_zurueck(self, provider):
        """StreamEvent nach Text wird ignoriert und liefert den bereits empfangenen Text."""

        import backend.claude_sdk.loader as loader

        class DummyTextBlock:
            def __init__(self, text):
                self.text = text

        class DummyAssistantMessage:
            def __init__(self, text):
                self.error = None
                self.content = [DummyTextBlock(text)]

        class DummyStreamEvent:
            def __init__(self, event):
                self.event = event

        async def fake_query_gen(prompt, options):
            yield DummyAssistantMessage("### FILENAME: app/page.js\nexport default function Home() {}")
            yield DummyStreamEvent({"type": "rate_limit_event"})

        loader._sdk_query = fake_query_gen
        loader._sdk_options_class = MagicMock()
        loader._sdk_assistant_message = DummyAssistantMessage
        loader._sdk_text_block = DummyTextBlock
        loader._sdk_stream_event = DummyStreamEvent
        loader._sdk_result_message = type("DummyResultMessage", (), {})
        loader._sdk_loaded = True
        provider._initialized = True

        with patch.object(provider, '_record_success'):
            result = provider.run_agent(
                prompt="Test", role="coder", model="opus",
                timeout_seconds=30
            )
            assert "app/page.js" in result, "Erwartet: Bereits empfangener Text wird zurueckgegeben"

    def test_rate_limit_event_ohne_text_wirft_runtime_error(self, provider):
        """rate_limit_event OHNE vorherigen Text → RuntimeError mit klarer Meldung (Fix 59d)."""
        import backend.claude_sdk.loader as loader

        class DummyStreamEvent:
            def __init__(self, event):
                self.event = event

        async def fake_query_gen(prompt, options):
            yield DummyStreamEvent({"type": "rate_limit_event"})

        loader._sdk_query = fake_query_gen
        loader._sdk_options_class = MagicMock()
        loader._sdk_assistant_message = type("DummyAssistant", (), {})
        loader._sdk_text_block = type("DummyTextBlock", (), {})
        loader._sdk_stream_event = DummyStreamEvent
        loader._sdk_result_message = type("DummyResultMessage", (), {})
        loader._sdk_loaded = True
        provider._initialized = True

        with patch.object(provider, '_record_failure'):
            with pytest.raises(RuntimeError, match="rate_limit_event"):
                provider.run_agent(
                    prompt="Test", role="coder", model="opus",
                    timeout_seconds=30
                )


class TestRuntimeGuard:
    """Tests fuer Runtime-Guard (SDK/CLI Version + Token-Cap)."""

    def test_run_agent_reicht_max_output_tokens_durch(self, provider):
        with patch.object(provider, "_run_sync", return_value="x" * 300) as mock_run:
            provider.run_agent(
                prompt="test",
                role="coder",
                model="haiku",
                max_output_tokens=1234,
            )
            assert mock_run.call_args.kwargs.get("max_output_tokens") == 1234

    def test_probe_sdk_runtime_bevorzugt_neuere_system_cli(self, provider):
        with patch("backend.claude_sdk.provider.importlib.metadata.version", return_value="0.1.39"), \
             patch.object(provider, "_find_bundled_cli_path", return_value="C:/bundled/claude.exe"), \
             patch.object(provider, "_read_cli_version", side_effect=["1.0.0", "1.1.0"]), \
             patch.object(provider, "_probe_cli_runtime_cap", return_value=8192), \
             patch("backend.claude_sdk.provider.shutil.which", return_value="C:/system/claude.exe"):
            result = provider.probe_sdk_runtime(configured_coder_limit=65536)

        assert result["sdk_in_affected_range"] is True
        assert result["limit_mismatch"] is True
        assert result["effective_coder_limit"] == 8192
        assert result["prefer_system_cli"] is True

class TestRateLimitEventHandlingWeitere:
    def test_andere_stream_fehler_werden_weitergeleitet(self, provider):
        """Nicht-rate_limit Fehler im Stream → Exception unveraendert weiterleiten."""
        import backend.claude_sdk.loader as loader

        async def fake_query_gen(prompt, options):
            raise ConnectionError("API connection lost")
            yield  # pragma: no cover

        loader._sdk_query = fake_query_gen
        loader._sdk_options_class = MagicMock()
        loader._sdk_assistant_message = type("DummyAssistant", (), {})
        loader._sdk_text_block = type("DummyTextBlock", (), {})
        loader._sdk_stream_event = type("DummyStreamEvent", (), {})
        loader._sdk_result_message = type("DummyResultMessage", (), {})
        loader._sdk_loaded = True
        provider._initialized = True

        with patch.object(provider, '_record_failure'):
            with pytest.raises(ConnectionError, match="API connection lost"):
                provider.run_agent(
                    prompt="Test", role="coder", model="opus",
                    timeout_seconds=30
                )
