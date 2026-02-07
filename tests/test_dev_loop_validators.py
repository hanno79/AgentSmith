# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 06.02.2026
Version: 1.0
Beschreibung: Tests fuer _is_harmless_warning_only aus backend/dev_loop_validators.py.
              Reine Funktionstests ohne Mocking - die Funktion ist eine Pure Function.
"""

import pytest

from backend.dev_loop_validators import _is_harmless_warning_only


class TestIsHarmlessWarningOnly:
    """Tests fuer _is_harmless_warning_only - Pure Function ohne Mocking."""

    # --- True-Faelle (nur Warnungen, kein Handlungsbedarf) ---

    def test_leerer_output_ist_harmlos(self):
        """Leerer Output = keine Fehler."""
        assert _is_harmless_warning_only("", "") is True, \
            "Erwartet: True, Erhalten: False - leerer Output sollte als harmlos gelten"

    def test_none_stderr_ist_harmlos(self):
        """None als stderr sollte funktionieren dank (None or '') Fallback."""
        # Hinweis: Die Funktion hat `stderr: str` Typ-Hint, aber (None or "") funktioniert
        assert _is_harmless_warning_only(None, None) is True, \
            "Erwartet: True, Erhalten: False - None-Werte sollten als harmlos gelten"

    def test_nur_pip_root_warnung(self):
        """Typische Docker pip-Warnung ist harmlos."""
        stderr = "WARNING: Running pip as the 'root' user can result in broken permissions"
        assert _is_harmless_warning_only(stderr) is True, \
            "Erwartet: True - pip root-Warnung ist harmlos"

    def test_nur_pip_update_notice(self):
        """pip Update-Hinweis ist harmlos."""
        stderr = (
            "[notice] A new release of pip is available: 23.0 -> 24.0\n"
            "[notice] To update, run: pip install --upgrade pip"
        )
        assert _is_harmless_warning_only(stderr) is True, \
            "Erwartet: True - pip Update-Hinweis ist harmlos"

    def test_nur_npm_warnings(self):
        """npm WARN/notice sind harmlos."""
        stderr = "npm WARN deprecated some-package@1.0.0\nnpm notice some info"
        assert _is_harmless_warning_only(stderr) is True, \
            "Erwartet: True - npm WARN und npm notice sind harmlos"

    def test_gemischte_harmlose_warnungen(self):
        """Kombination verschiedener harmloser Warnungen bleibt harmlos."""
        stderr = (
            "WARNING: Running pip as the 'root' user\n"
            "[notice] A new release of pip is available"
        )
        stdout = "npm WARN old package"
        assert _is_harmless_warning_only(stderr, stdout) is True, \
            "Erwartet: True - gemischte harmlose Warnungen bleiben harmlos"

    def test_generische_warning_zeile(self):
        """Zeilen die mit 'warning' beginnen sind harmlos (Case-insensitive Anfang)."""
        stderr = "warning: some generic warning\nWarning: another one"
        assert _is_harmless_warning_only(stderr) is True, \
            "Erwartet: True - generische Warning-Zeilen sind harmlos"

    def test_generische_notice_zeile(self):
        """Zeilen die mit 'notice' oder '[notice]' oder '[warning]' beginnen."""
        stderr = "notice: some info\n[notice] more info\n[warning] also harmless"
        assert _is_harmless_warning_only(stderr) is True, \
            "Erwartet: True - notice/[notice]/[warning] Zeilen sind harmlos"

    def test_nur_leere_zeilen(self):
        """Nur Whitespace/leere Zeilen sind harmlos."""
        stderr = "\n  \n\n  \n"
        assert _is_harmless_warning_only(stderr) is True, \
            "Erwartet: True - leere Zeilen ergeben keinen Fehler"

    def test_warn_prefix_zeile(self):
        """Zeilen die mit 'warn' beginnen sind harmlos."""
        stderr = "warn: some deprecation notice"
        assert _is_harmless_warning_only(stderr) is True, \
            "Erwartet: True - 'warn' Prefix ist harmlos"

    # --- False-Faelle (echte Fehler) ---

    def test_module_not_found_error(self):
        """ModuleNotFoundError ist ein echter Fehler."""
        stderr = "ModuleNotFoundError: No module named 'flask'"
        assert _is_harmless_warning_only(stderr) is False, \
            "Erwartet: False - ModuleNotFoundError ist ein echter Fehler"

    def test_import_error(self):
        """ImportError ist ein echter Fehler."""
        stderr = "ImportError: cannot import name 'Config'"
        assert _is_harmless_warning_only(stderr) is False, \
            "Erwartet: False - ImportError ist ein echter Fehler"

    def test_syntax_error(self):
        """SyntaxError ist ein echter Fehler."""
        stderr = "SyntaxError: unexpected indent"
        assert _is_harmless_warning_only(stderr) is False, \
            "Erwartet: False - SyntaxError ist ein echter Fehler"

    def test_traceback(self):
        """Python Traceback ist ein echter Fehler."""
        stderr = (
            "Traceback (most recent call last)\n"
            "  File 'app.py', line 5\n"
            "NameError: name 'x' is not defined"
        )
        assert _is_harmless_warning_only(stderr) is False, \
            "Erwartet: False - Traceback zeigt einen echten Fehler an"

    def test_error_keyword_in_stdout(self):
        """Fehler-Keywords im stdout werden auch erkannt."""
        stdout = "TypeError: 'NoneType' object is not iterable"
        assert _is_harmless_warning_only("", stdout) is False, \
            "Erwartet: False - TypeError im stdout ist ein echter Fehler"

    def test_pytest_failures(self):
        """pytest FAILURES Marker wird erkannt."""
        stdout = "======== FAILURES ========"
        # Hinweis: "= FAILURES =" ist in error_keywords
        assert _is_harmless_warning_only("", stdout) is False, \
            "Erwartet: False - pytest FAILURES ist ein echter Fehler"

    def test_pytest_errors(self):
        """pytest ERRORS Marker wird erkannt."""
        stdout = "ERRORS"
        assert _is_harmless_warning_only("", stdout) is False, \
            "Erwartet: False - ERRORS ist ein echter Fehler"

    def test_resolution_impossible(self):
        """pip ResolutionImpossible ist ein Fehler."""
        stderr = "ResolutionImpossible: Versions conflict"
        assert _is_harmless_warning_only(stderr) is False, \
            "Erwartet: False - ResolutionImpossible ist ein echter Fehler"

    def test_no_matching_distribution(self):
        """pip 'No matching distribution' ist ein Fehler."""
        stderr = "No matching distribution found for nonexistent-package"
        assert _is_harmless_warning_only(stderr) is False, \
            "Erwartet: False - No matching distribution ist ein echter Fehler"

    def test_failed_keyword(self):
        """FAILED: Keyword wird erkannt."""
        stderr = "FAILED: some test"
        assert _is_harmless_warning_only(stderr) is False, \
            "Erwartet: False - FAILED: ist ein echter Fehler"

    def test_exception_keyword(self):
        """Exception: Keyword wird erkannt."""
        stderr = "Exception: unexpected error occurred"
        assert _is_harmless_warning_only(stderr) is False, \
            "Erwartet: False - Exception: ist ein echter Fehler"

    def test_file_not_found_error(self):
        """FileNotFoundError wird erkannt."""
        stderr = "FileNotFoundError: [Errno 2] No such file"
        assert _is_harmless_warning_only(stderr) is False, \
            "Erwartet: False - FileNotFoundError ist ein echter Fehler"

    def test_could_not_find_version(self):
        """'Could not find a version' pip-Fehler wird erkannt."""
        stderr = "Could not find a version that satisfies the requirement xyz"
        assert _is_harmless_warning_only(stderr) is False, \
            "Erwartet: False - Could not find a version ist ein echter Fehler"

    def test_pytest_error_keyword(self):
        """'pytest: error' Keyword wird erkannt."""
        stderr = "pytest: error: unrecognized option"
        assert _is_harmless_warning_only(stderr) is False, \
            "Erwartet: False - pytest: error ist ein echter Fehler"

    def test_value_error(self):
        """ValueError wird erkannt."""
        stderr = "ValueError: invalid literal for int()"
        assert _is_harmless_warning_only(stderr) is False, \
            "Erwartet: False - ValueError ist ein echter Fehler"

    def test_attribute_error(self):
        """AttributeError wird erkannt."""
        stderr = "AttributeError: 'NoneType' object has no attribute 'split'"
        assert _is_harmless_warning_only(stderr) is False, \
            "Erwartet: False - AttributeError ist ein echter Fehler"

    # --- Gemischte Faelle ---

    def test_warnung_mit_fehler_gemischt(self):
        """Warnungen + echter Fehler = nicht harmlos."""
        stderr = (
            "WARNING: Running pip as the 'root' user\n"
            "ModuleNotFoundError: No module named 'flask'"
        )
        assert _is_harmless_warning_only(stderr) is False, \
            "Erwartet: False - Warnung mit echtem Fehler ist nicht harmlos"

    def test_pip_warnung_mit_syntax_error(self):
        """pip-Warnung + SyntaxError = nicht harmlos."""
        stderr = (
            "[notice] A new release of pip is available\n"
            "SyntaxError: invalid syntax"
        )
        assert _is_harmless_warning_only(stderr) is False, \
            "Erwartet: False - pip-Warnung mit SyntaxError ist nicht harmlos"

    def test_unbekannte_nicht_warning_zeile(self):
        """Zeile die KEIN Warning ist und kein Error-Keyword hat -> nicht harmlos."""
        stderr = "Some random output that is not a warning"
        assert _is_harmless_warning_only(stderr) is False, \
            "Erwartet: False - unbekannter Output ist nicht als harmlos einzustufen"

    def test_error_in_stderr_warnung_in_stdout(self):
        """Fehler in stderr, Warnungen in stdout - trotzdem nicht harmlos."""
        stderr = "ERROR: Something broke"
        stdout = "npm WARN deprecated"
        assert _is_harmless_warning_only(stderr, stdout) is False, \
            "Erwartet: False - ERROR in stderr macht den Output nicht harmlos"

    def test_error_lowercase_keyword(self):
        """'error:' (lowercase) wird als Fehler erkannt."""
        stderr = "error: compilation failed"
        assert _is_harmless_warning_only(stderr) is False, \
            "Erwartet: False - error: (lowercase) ist ein echter Fehler"

    def test_failed_lowercase_keyword(self):
        """'failed:' (lowercase) wird als Fehler erkannt."""
        stderr = "failed: test_something"
        assert _is_harmless_warning_only(stderr) is False, \
            "Erwartet: False - failed: (lowercase) ist ein echter Fehler"

    def test_exception_lowercase_keyword(self):
        """'exception:' (lowercase) wird als Fehler erkannt."""
        stderr = "exception: something went wrong"
        assert _is_harmless_warning_only(stderr) is False, \
            "Erwartet: False - exception: (lowercase) ist ein echter Fehler"
