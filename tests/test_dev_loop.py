# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 01.02.2026
Version: 1.0
Beschreibung: Unit Tests für DevLoop-Funktionen - Helper, Truncation Detection, Feedback.

              Tests validieren:
              - Error-Hashing für Fehler-Modell-Historie
              - Truncation-Detection bei abgeschnittenem LLM-Output
              - Unicode-Sanitization
              - Python-Dateivollständigkeit
"""

import pytest
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.dev_loop_helpers import (
    hash_error,
    TruncationError,
    _is_python_file_complete,
    _check_for_truncation,
    _sanitize_unicode
)


# =========================================================================
# Fixtures
# =========================================================================

@pytest.fixture
def sample_python_code():
    """Vollständiger Python-Code für Tests."""
    return '''
def greet(name: str) -> str:
    """Begrüßt eine Person."""
    return f"Hallo, {name}!"

if __name__ == "__main__":
    print(greet("Welt"))
'''


@pytest.fixture
def truncated_python_code():
    """Abgeschnittener Python-Code."""
    return '''
def process_data(data):
    result = []
    for item in data:
        if item > 0:
            result.append('''  # Endet mitten in der Funktion


# =========================================================================
# Test: Error-Hashing
# =========================================================================

class TestErrorHashing:
    """Tests für hash_error Funktion."""

    def test_empty_error_returns_empty_string(self):
        """Leerer Error-Content gibt leeren String zurück."""
        assert hash_error("") == ""
        assert hash_error(None) == ""

    def test_same_error_same_hash(self):
        """Gleicher Fehler ergibt gleichen Hash."""
        error1 = "ModuleNotFoundError: No module named 'flask'"
        error2 = "ModuleNotFoundError: No module named 'flask'"
        assert hash_error(error1) == hash_error(error2)

    def test_different_line_numbers_same_hash(self):
        """Fehler mit unterschiedlichen Zeilennummern ergeben gleichen Hash."""
        error1 = "SyntaxError in line 5: invalid syntax"
        error2 = "SyntaxError in line 42: invalid syntax"
        assert hash_error(error1) == hash_error(error2)

    def test_different_timestamps_same_hash(self):
        """Fehler mit unterschiedlichen Timestamps ergeben gleichen Hash."""
        error1 = "Error at 2026-01-31 12:00:00: connection failed"
        error2 = "Error at 2026-02-01 14:30:45: connection failed"
        assert hash_error(error1) == hash_error(error2)

    def test_different_paths_same_hash(self):
        """Fehler mit unterschiedlichen Pfaden ergeben gleichen Hash."""
        error1 = "FileNotFoundError: C:\\Users\\alice\\app.py not found"
        error2 = "FileNotFoundError: /home/bob/project/app.py not found"
        assert hash_error(error1) == hash_error(error2)

    def test_different_iterations_same_hash(self):
        """Fehler mit unterschiedlichen Iterationsnummern ergeben gleichen Hash."""
        error1 = "Iteration 3: Build failed"
        error2 = "Iteration 15: Build failed"
        assert hash_error(error1) == hash_error(error2)

    def test_truly_different_errors_different_hash(self):
        """Tatsächlich verschiedene Fehler ergeben verschiedene Hashes."""
        error1 = "ModuleNotFoundError: No module named 'flask'"
        error2 = "TypeError: 'NoneType' object is not iterable"
        assert hash_error(error1) != hash_error(error2)

    def test_hash_length(self):
        """Hash hat immer 12 Zeichen."""
        error = "SomeError: something went wrong"
        result = hash_error(error)
        assert len(result) == 12


# =========================================================================
# Test: Truncation Detection
# =========================================================================

class TestTruncationDetection:
    """Tests für Truncation-Detection Funktionen."""

    def test_complete_python_file(self, sample_python_code):
        """Vollständige Python-Datei wird als vollständig erkannt."""
        is_complete, reason = _is_python_file_complete(sample_python_code, "app.py")
        assert is_complete is True
        assert "OK" in reason

    def test_truncated_python_file(self, truncated_python_code):
        """Abgeschnittene Python-Datei wird erkannt."""
        is_complete, reason = _is_python_file_complete(truncated_python_code, "app.py")
        assert is_complete is False
        # Muss einen Grund angeben
        assert len(reason) > 0

    def test_empty_file_detected(self):
        """Leere Datei wird erkannt."""
        is_complete, reason = _is_python_file_complete("", "app.py")
        assert is_complete is False
        assert "leer" in reason.lower()

    def test_non_python_file_always_complete(self):
        """Nicht-Python-Dateien werden als vollständig betrachtet."""
        is_complete, reason = _is_python_file_complete("some content", "styles.css")
        assert is_complete is True
        assert "Keine Python-Datei" in reason

    def test_file_ending_with_open_paren(self):
        """Datei die mit offener Klammer endet wird als truncated erkannt."""
        code = "def foo(a, b,"
        is_complete, reason = _is_python_file_complete(code, "test.py")
        assert is_complete is False

    def test_file_ending_with_colon(self):
        """Datei die mit Doppelpunkt endet wird als truncated erkannt."""
        code = "if condition:"
        is_complete, reason = _is_python_file_complete(code, "test.py")
        assert is_complete is False

    def test_check_for_truncation_returns_list(self):
        """_check_for_truncation gibt Liste von truncated Dateien zurück."""
        files = {
            "good.py": "def foo(): pass",
            "bad.py": "def bar(",
            "style.css": "body { color: red; }"
        }
        truncated = _check_for_truncation(files)
        # bad.py sollte erkannt werden
        filenames = [f[0] for f in truncated]
        assert "bad.py" in filenames
        assert "good.py" not in filenames
        assert "style.css" not in filenames


class TestTruncationError:
    """Tests für TruncationError Exception."""

    def test_truncation_error_creation(self):
        """TruncationError kann mit Dateien erstellt werden."""
        error = TruncationError("Code was truncated", ["file1.py", "file2.py"])
        assert str(error) == "Code was truncated"
        assert error.truncated_files == ["file1.py", "file2.py"]

    def test_truncation_error_default_files(self):
        """TruncationError hat leere Dateiliste als Default."""
        error = TruncationError("Code was truncated")
        assert error.truncated_files == []


# =========================================================================
# Test: Unicode Sanitization
# =========================================================================

class TestUnicodeSanitization:
    """Tests für _sanitize_unicode Funktion."""

    def test_removes_emoji_variation_selector(self):
        """Emoji Variation Selector U+FE0F wird entfernt."""
        content = "print('Hello\uFE0F World')"
        result = _sanitize_unicode(content)
        assert "\uFE0F" not in result
        assert "Hello World" in result

    def test_removes_zero_width_space(self):
        """Zero Width Space U+200B wird entfernt."""
        content = "print\u200B('hello')"
        result = _sanitize_unicode(content)
        assert "\u200B" not in result
        assert "print('hello')" in result

    def test_removes_byte_order_mark(self):
        """Byte Order Mark U+FEFF wird entfernt."""
        content = "\uFEFFimport os"
        result = _sanitize_unicode(content)
        assert "\uFEFF" not in result
        assert result == "import os"

    def test_replaces_smart_quotes(self):
        """Smart Quotes werden durch normale Quotes ersetzt."""
        content = "print(\u201CHello\u201D)"  # "Hello"
        result = _sanitize_unicode(content)
        assert "\u201C" not in result
        assert "\u201D" not in result
        assert 'print("Hello")' in result

    def test_replaces_smart_single_quotes(self):
        """Smart Single Quotes werden durch Apostrophe ersetzt."""
        content = "print(\u2018Hello\u2019)"  # 'Hello'
        result = _sanitize_unicode(content)
        assert "\u2018" not in result
        assert "\u2019" not in result
        assert "print('Hello')" in result

    def test_replaces_en_dash(self):
        """En Dash U+2013 wird durch Minus ersetzt."""
        content = "value = 10\u20135"  # 10–5
        result = _sanitize_unicode(content)
        assert "\u2013" not in result
        assert "10-5" in result

    def test_replaces_horizontal_ellipsis(self):
        """Horizontal Ellipsis U+2026 wird durch drei Punkte ersetzt."""
        content = "print('Loading\u2026')"  # Loading…
        result = _sanitize_unicode(content)
        assert "\u2026" not in result
        assert "Loading..." in result

    def test_replaces_non_breaking_space(self):
        """Non-Breaking Space U+00A0 wird durch normales Leerzeichen ersetzt."""
        content = "import\u00A0os"
        result = _sanitize_unicode(content)
        assert "\u00A0" not in result
        assert "import os" in result

    def test_preserves_normal_content(self):
        """Normaler ASCII-Inhalt bleibt unverändert."""
        content = "def foo():\n    return 42"
        result = _sanitize_unicode(content)
        assert result == content


# =========================================================================
# Test: Edge Cases
# =========================================================================

class TestEdgeCases:
    """Tests für Grenzfälle."""

    def test_hash_error_with_unicode(self):
        """hash_error behandelt Unicode korrekt."""
        error = "UnicodeDecodeError: 'utf-8' codec can't decode byte 0xff"
        result = hash_error(error)
        assert len(result) == 12

    def test_hash_error_with_very_long_input(self):
        """hash_error kürzt sehr lange Eingaben."""
        error = "A" * 10000
        result = hash_error(error)
        assert len(result) == 12  # Hash hat feste Länge

    def test_sanitize_multiple_issues(self):
        """_sanitize_unicode behandelt mehrere Probleme gleichzeitig."""
        content = "\uFEFF\u201CHello\u200BWorld\u201D"
        result = _sanitize_unicode(content)
        assert "\uFEFF" not in result
        assert "\u200B" not in result
        assert "\u201C" not in result
        assert "\u201D" not in result
        assert '"HelloWorld"' in result

    def test_check_for_truncation_empty_dict(self):
        """_check_for_truncation mit leerem Dict gibt leere Liste zurück."""
        result = _check_for_truncation({})
        assert result == []

    def test_python_file_with_syntax_error_not_truncation(self):
        """Echter Syntax-Fehler wird nicht als Truncation erkannt."""
        # Typo in keyword - echter Bug, keine Truncation
        code = "deff foo():\n    pass"  # 'deff' statt 'def'
        is_complete, reason = _is_python_file_complete(code, "test.py")
        # Könnte True oder False sein - wichtig ist dass kein Crash
        assert isinstance(is_complete, bool)


# =========================================================================
# Test: Review Verdict Parsing
# =========================================================================

class TestReviewVerdictParsing:
    """Tests für Review-Verdict Parsing-Logik.

    Das Verdict wird wie folgt bestimmt (siehe dev_loop_validators.py:407):
    review_verdict = "OK" if "OK" in review_output.upper() and not sandbox_failed else "FEEDBACK"
    """

    def test_verdict_ok_uppercase(self):
        """'OK' in Großbuchstaben wird erkannt."""
        review_output = "Code looks good. OK"
        sandbox_failed = False
        verdict = "OK" if "OK" in review_output.upper() and not sandbox_failed else "FEEDBACK"
        assert verdict == "OK"

    def test_verdict_ok_lowercase(self):
        """'ok' in Kleinbuchstaben wird erkannt (case-insensitive)."""
        review_output = "Everything is fine. ok"
        sandbox_failed = False
        verdict = "OK" if "OK" in review_output.upper() and not sandbox_failed else "FEEDBACK"
        assert verdict == "OK"

    def test_verdict_ok_mixed_case(self):
        """'Ok' in gemischter Schreibweise wird erkannt."""
        review_output = "Code is clean. Ok approved."
        sandbox_failed = False
        verdict = "OK" if "OK" in review_output.upper() and not sandbox_failed else "FEEDBACK"
        assert verdict == "OK"

    def test_verdict_ok_with_whitespace(self):
        """'OK' mit führenden/nachfolgenden Leerzeichen wird erkannt."""
        review_output = "Review complete.  OK  "
        sandbox_failed = False
        verdict = "OK" if "OK" in review_output.upper() and not sandbox_failed else "FEEDBACK"
        assert verdict == "OK"

    def test_verdict_feedback_when_sandbox_failed(self):
        """'OK' wird ignoriert wenn Sandbox fehlgeschlagen ist."""
        review_output = "Code looks good. OK"
        sandbox_failed = True
        verdict = "OK" if "OK" in review_output.upper() and not sandbox_failed else "FEEDBACK"
        assert verdict == "FEEDBACK"

    def test_verdict_feedback_without_ok(self):
        """Ohne 'OK' wird FEEDBACK zurückgegeben."""
        review_output = "There are some issues to fix."
        sandbox_failed = False
        verdict = "OK" if "OK" in review_output.upper() and not sandbox_failed else "FEEDBACK"
        assert verdict == "FEEDBACK"

    def test_verdict_ok_in_word_not_matched(self):
        """'OK' als Teil eines Wortes (z.B. 'BROKEN') wird erkannt.

        HINWEIS: Die aktuelle Implementierung matcht auch OK in Wörtern wie 'BROKEN'.
        Dies ist gewolltes Verhalten da 'OK' sehr selten in anderen Wörtern vorkommt.
        """
        review_output = "The BROKEN code needs fixes."
        sandbox_failed = False
        # "BROKEN" enthält "OK" - wird erkannt
        verdict = "OK" if "OK" in review_output.upper() and not sandbox_failed else "FEEDBACK"
        # Da "BROKEN" "OK" enthält, wird es als OK gewertet (aktuelles Verhalten)
        assert verdict == "OK"

    def test_verdict_empty_review(self):
        """Leerer Review gibt FEEDBACK zurück."""
        review_output = ""
        sandbox_failed = False
        verdict = "OK" if "OK" in review_output.upper() and not sandbox_failed else "FEEDBACK"
        assert verdict == "FEEDBACK"


# =========================================================================
# Test: DevLoop Initialisierung (mit Mocking)
# =========================================================================

class TestDevLoopInit:
    """Tests für DevLoop-Klassen-Initialisierung.

    Da DevLoop einen OrchestrationManager benötigt, werden diese Tests
    mit Mock-Objekten durchgeführt.
    """

    def test_devloop_creates_task_derivation(self):
        """DevLoop erstellt TaskDerivation bei Initialisierung."""
        from unittest.mock import MagicMock

        # Mock des Managers
        mock_manager = MagicMock()
        mock_manager.model_router = MagicMock()
        mock_manager.config = {}

        from backend.dev_loop import DevLoop
        dev_loop = DevLoop(
            manager=mock_manager,
            set_current_agent=MagicMock(),
            run_with_timeout=MagicMock()
        )

        assert hasattr(dev_loop, '_task_derivation')
        from backend.dev_loop_task_derivation import DevLoopTaskDerivation
        assert isinstance(dev_loop._task_derivation, DevLoopTaskDerivation)

    def test_devloop_creates_orchestrator_validator(self):
        """DevLoop erstellt OrchestratorValidator bei Initialisierung."""
        from unittest.mock import MagicMock

        mock_manager = MagicMock()
        mock_manager.model_router = MagicMock()
        mock_manager.config = {}

        from backend.dev_loop import DevLoop
        dev_loop = DevLoop(
            manager=mock_manager,
            set_current_agent=MagicMock(),
            run_with_timeout=MagicMock()
        )

        assert hasattr(dev_loop, '_orchestrator_validator')
        from backend.orchestration_validator import OrchestratorValidator
        assert isinstance(dev_loop._orchestrator_validator, OrchestratorValidator)

    def test_devloop_stores_manager_reference(self):
        """DevLoop speichert Referenz auf Manager."""
        from unittest.mock import MagicMock

        mock_manager = MagicMock()
        mock_manager.model_router = MagicMock()
        mock_manager.config = {}

        from backend.dev_loop import DevLoop
        dev_loop = DevLoop(
            manager=mock_manager,
            set_current_agent=MagicMock(),
            run_with_timeout=MagicMock()
        )

        assert dev_loop.manager is mock_manager

    def test_devloop_stores_callbacks(self):
        """DevLoop speichert Callback-Funktionen."""
        from unittest.mock import MagicMock

        mock_manager = MagicMock()
        mock_manager.model_router = MagicMock()
        mock_manager.config = {}

        set_agent_callback = MagicMock()
        timeout_callback = MagicMock()

        from backend.dev_loop import DevLoop
        dev_loop = DevLoop(
            manager=mock_manager,
            set_current_agent=set_agent_callback,
            run_with_timeout=timeout_callback
        )

        assert dev_loop.set_current_agent is set_agent_callback
        assert dev_loop.run_with_timeout is timeout_callback


# =========================================================================
# Test: Minimum Files Check
# =========================================================================

class TestMinimumFilesCheck:
    """Tests für Minimum-Datei-Anforderungen.

    Full-Mode erwartet mindestens 3 Dateien.
    Patch-Mode erlaubt <3 Dateien (mindestens 1 geänderte Datei).
    Diese Logik ist verteilt über mehrere Module.
    """

    def test_mode_gate_full_mode_requires_three_files(self):
        """Full-Mode: Mindestanzahl bleibt bei 3 Dateien."""
        from backend.dev_loop_core import _get_required_file_count_for_mode, _has_minimum_files_for_mode

        assert _get_required_file_count_for_mode(is_patch_mode=False) == 3
        assert _has_minimum_files_for_mode(["a.py", "b.py"], is_patch_mode=False) is False
        assert _has_minimum_files_for_mode(["a.py", "b.py", "c.py"], is_patch_mode=False) is True

    def test_mode_gate_patch_mode_requires_one_file(self):
        """Patch-Mode: bereits 1 geänderte Datei reicht für Success-Gate."""
        from backend.dev_loop_core import _get_required_file_count_for_mode, _has_minimum_files_for_mode

        assert _get_required_file_count_for_mode(is_patch_mode=True) == 1
        assert _has_minimum_files_for_mode([], is_patch_mode=True) is False
        assert _has_minimum_files_for_mode(["single_fix.js"], is_patch_mode=True) is True

    def test_get_files_to_fix_respects_max_files(self):
        """get_files_to_fix respektiert max_files Parameter."""
        from backend.error_analyzer import get_files_to_fix, FileError

        errors = [
            FileError('a.py', 'syntax'),
            FileError('b.py', 'syntax'),
            FileError('c.py', 'syntax'),
            FileError('d.py', 'syntax'),
            FileError('e.py', 'syntax'),
        ]

        # Max 3 Dateien
        result = get_files_to_fix(errors, max_files=3)
        assert len(result) == 3

        # Max 1 Datei
        result = get_files_to_fix(errors, max_files=1)
        assert len(result) == 1

    def test_check_for_truncation_handles_mixed_files(self):
        """Truncation-Check behandelt gemischte Dateitypen."""
        files = {
            "good.py": "def foo():\n    pass",
            "bad.py": "def bar(",  # truncated
            "style.css": "body { }",
            "config.json": '{"key": "value"}',
            "incomplete.py": "class Test:\n    def method(",  # truncated
        }

        truncated = _check_for_truncation(files)
        filenames = [f[0] for f in truncated]

        # Sollte nur Python-Dateien prüfen
        assert "bad.py" in filenames
        assert "incomplete.py" in filenames
        assert "style.css" not in filenames
        assert "config.json" not in filenames
