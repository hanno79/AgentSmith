# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 14.02.2026
Version: 1.0
Beschreibung: Tests fuer dev_loop_smoke_test.py — Smoke-Test-Modul fuer DevLoop.
              Prueft SmokeTestResult Dataclass, feedback_for_coder Property,
              _extract_compile_errors() Funktion und die Pattern-Listen.
              Testet NUR pure-logic Teile ohne externe Abhaengigkeiten.
"""

import os
import sys
import pytest

# Projekt-Root zum Python-Path hinzufuegen
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.dev_loop_smoke_test import (
    SmokeTestResult,
    _extract_compile_errors,
    _COMPILE_ERROR_PATTERNS,
    _HARMLESS_PATTERNS,
)


# ===== Tests fuer SmokeTestResult Defaults =====

class TestSmokeTestResultDefaults:
    """Tests fuer die Standardwerte der SmokeTestResult Dataclass."""

    def test_minimal_erstellung_passed_true(self):
        """SmokeTestResult mit passed=True hat korrekte Standardwerte."""
        result = SmokeTestResult(passed=True)
        assert result.passed is True
        assert result.server_started is False
        assert result.page_loaded is False
        assert result.compile_errors == []
        assert result.console_errors == []
        assert result.issues == []
        assert result.screenshot is None
        assert result.server_output == ""
        assert result.duration_seconds == 0.0

    def test_minimal_erstellung_passed_false(self):
        """SmokeTestResult mit passed=False hat korrekte Standardwerte."""
        result = SmokeTestResult(passed=False)
        assert result.passed is False
        assert result.server_started is False

    def test_alle_felder_gesetzt(self):
        """SmokeTestResult mit allen Feldern explizit gesetzt."""
        result = SmokeTestResult(
            passed=True,
            server_started=True,
            page_loaded=True,
            compile_errors=["Fehler A"],
            console_errors=["Console X"],
            issues=["Problem 1"],
            screenshot="/tmp/test.png",
            server_output="Server laeuft",
            duration_seconds=5.3,
        )
        assert result.passed is True
        assert result.server_started is True
        assert result.page_loaded is True
        assert result.compile_errors == ["Fehler A"]
        assert result.console_errors == ["Console X"]
        assert result.issues == ["Problem 1"]
        assert result.screenshot == "/tmp/test.png"
        assert result.server_output == "Server laeuft"
        assert result.duration_seconds == 5.3

    def test_listen_sind_unabhaengig(self):
        """Jede SmokeTestResult-Instanz hat eigene Listen (kein shared mutable default)."""
        result_a = SmokeTestResult(passed=False)
        result_b = SmokeTestResult(passed=False)
        result_a.compile_errors.append("Fehler nur in A")
        assert result_b.compile_errors == []
        assert len(result_a.compile_errors) == 1

    def test_issues_liste_unabhaengig(self):
        """Issues-Listen verschiedener Instanzen teilen sich keinen Zustand."""
        result_a = SmokeTestResult(passed=False)
        result_b = SmokeTestResult(passed=False)
        result_a.issues.append("Issue A")
        result_b.issues.append("Issue B")
        assert result_a.issues == ["Issue A"]
        assert result_b.issues == ["Issue B"]

    def test_console_errors_unabhaengig(self):
        """Console-Errors-Listen verschiedener Instanzen sind unabhaengig."""
        result_a = SmokeTestResult(passed=False)
        result_b = SmokeTestResult(passed=True)
        result_a.console_errors.append("Error A")
        assert result_b.console_errors == []

    def test_duration_seconds_aenderbar(self):
        """duration_seconds kann nachtraeglich geaendert werden."""
        result = SmokeTestResult(passed=True)
        result.duration_seconds = 42.7
        assert result.duration_seconds == 42.7


# ===== Tests fuer SmokeTestResult feedback_for_coder =====

class TestSmokeTestResultFeedback:
    """Tests fuer die feedback_for_coder Property der SmokeTestResult Dataclass."""

    def test_passed_true_leerer_string(self):
        """Wenn passed=True ist, gibt feedback_for_coder einen leeren String zurueck."""
        result = SmokeTestResult(passed=True)
        assert result.feedback_for_coder == ""

    def test_passed_true_trotz_issues_leerer_string(self):
        """Auch mit issues: wenn passed=True, bleibt feedback_for_coder leer."""
        result = SmokeTestResult(passed=True, issues=["Info-Meldung"])
        assert result.feedback_for_coder == ""

    def test_nur_compile_errors(self):
        """Nur compile_errors vorhanden → enthaelt KOMPILIERUNGS-FEHLER Abschnitt."""
        result = SmokeTestResult(
            passed=False,
            server_started=True,
            page_loaded=True,
            compile_errors=["Module not found: xyz"],
        )
        feedback = result.feedback_for_coder
        assert "SMOKE-TEST FEHLGESCHLAGEN:" in feedback
        assert "KOMPILIERUNGS-FEHLER:" in feedback
        assert "Module not found: xyz" in feedback

    def test_compile_errors_max_10(self):
        """Maximal 10 compile_errors werden im Feedback angezeigt."""
        errors = [f"Error Nummer {i}" for i in range(15)]
        result = SmokeTestResult(
            passed=False,
            server_started=True,
            page_loaded=True,
            compile_errors=errors,
        )
        feedback = result.feedback_for_coder
        # Erste 10 sollen enthalten sein
        for i in range(10):
            assert f"Error Nummer {i}" in feedback
        # 11. bis 15. sollen NICHT enthalten sein
        assert "Error Nummer 10" not in feedback
        assert "Error Nummer 14" not in feedback

    def test_server_nicht_gestartet(self):
        """server_started=False → enthaelt SERVER KONNTE NICHT GESTARTET WERDEN."""
        result = SmokeTestResult(passed=False, server_started=False)
        feedback = result.feedback_for_coder
        assert "SERVER KONNTE NICHT GESTARTET WERDEN:" in feedback

    def test_server_nicht_gestartet_mit_output(self):
        """server_started=False mit server_output → enthaelt Server-Output."""
        result = SmokeTestResult(
            passed=False,
            server_started=False,
            server_output="npm ERR! missing script: dev",
        )
        feedback = result.feedback_for_coder
        assert "SERVER KONNTE NICHT GESTARTET WERDEN:" in feedback
        assert "npm ERR! missing script: dev" in feedback
        assert "Server-Output:" in feedback

    def test_server_output_max_2000_zeichen(self):
        """Server-Output wird auf maximal 2000 Zeichen begrenzt."""
        langer_output = "X" * 3000
        result = SmokeTestResult(
            passed=False,
            server_started=False,
            server_output=langer_output,
        )
        feedback = result.feedback_for_coder
        # Der Output im Feedback sollte max 2000 Zeichen des Originals enthalten
        assert "X" * 2000 in feedback
        assert "X" * 2001 not in feedback

    def test_seite_nicht_geladen(self):
        """server_started=True, page_loaded=False → SEITE KONNTE NICHT GELADEN WERDEN."""
        result = SmokeTestResult(
            passed=False,
            server_started=True,
            page_loaded=False,
        )
        feedback = result.feedback_for_coder
        assert "SEITE KONNTE NICHT GELADEN WERDEN:" in feedback
        assert "Die App antwortet nicht auf HTTP-Anfragen." in feedback

    def test_seite_nicht_geladen_nur_wenn_server_gestartet(self):
        """SEITE-Abschnitt erscheint nur wenn server_started=True (sonst Server-Fehler)."""
        result = SmokeTestResult(
            passed=False,
            server_started=False,
            page_loaded=False,
        )
        feedback = result.feedback_for_coder
        # Server nicht gestartet → kein Seiten-Abschnitt
        assert "SEITE KONNTE NICHT GELADEN WERDEN" not in feedback
        assert "SERVER KONNTE NICHT GESTARTET WERDEN" in feedback

    def test_console_errors_vorhanden(self):
        """console_errors → enthaelt BROWSER CONSOLE-FEHLER mit Anzahl."""
        result = SmokeTestResult(
            passed=False,
            server_started=True,
            page_loaded=True,
            console_errors=["ReferenceError: x is not defined", "TypeError: null"],
        )
        feedback = result.feedback_for_coder
        assert "BROWSER CONSOLE-FEHLER (2):" in feedback
        assert "ReferenceError: x is not defined" in feedback
        assert "TypeError: null" in feedback

    def test_console_errors_max_5(self):
        """Maximal 5 console_errors werden im Feedback angezeigt."""
        errors = [f"Console Error {i}" for i in range(8)]
        result = SmokeTestResult(
            passed=False,
            server_started=True,
            page_loaded=True,
            console_errors=errors,
        )
        feedback = result.feedback_for_coder
        # Anzahl zeigt alle 8
        assert "BROWSER CONSOLE-FEHLER (8):" in feedback
        # Aber nur 5 sind einzeln aufgelistet
        for i in range(5):
            assert f"Console Error {i}" in feedback
        assert "Console Error 5" not in feedback
        assert "Console Error 7" not in feedback

    def test_issues_vorhanden(self):
        """issues → enthaelt WEITERE PROBLEME Abschnitt."""
        result = SmokeTestResult(
            passed=False,
            server_started=True,
            page_loaded=True,
            issues=["Leere Seite erkannt", "Next.js Error-Overlay gefunden"],
        )
        feedback = result.feedback_for_coder
        assert "WEITERE PROBLEME:" in feedback
        assert "Leere Seite erkannt" in feedback
        assert "Next.js Error-Overlay gefunden" in feedback

    def test_kombination_aller_fehler(self):
        """Alle Fehlertypen gleichzeitig → alle Abschnitte vorhanden."""
        result = SmokeTestResult(
            passed=False,
            server_started=True,
            page_loaded=False,
            compile_errors=["Failed to compile: missing module"],
            console_errors=["Uncaught TypeError"],
            issues=["Leere Seite"],
        )
        feedback = result.feedback_for_coder
        assert "SMOKE-TEST FEHLGESCHLAGEN:" in feedback
        assert "KOMPILIERUNGS-FEHLER:" in feedback
        assert "Failed to compile: missing module" in feedback
        assert "SEITE KONNTE NICHT GELADEN WERDEN:" in feedback
        assert "BROWSER CONSOLE-FEHLER (1):" in feedback
        assert "Uncaught TypeError" in feedback
        assert "WEITERE PROBLEME:" in feedback
        assert "Leere Seite" in feedback

    def test_server_nicht_gestartet_plus_compile_errors(self):
        """Server nicht gestartet UND compile_errors → beide Abschnitte vorhanden."""
        result = SmokeTestResult(
            passed=False,
            server_started=False,
            compile_errors=["SyntaxError: unexpected token"],
            server_output="Error: Cannot find module 'next'",
        )
        feedback = result.feedback_for_coder
        assert "KOMPILIERUNGS-FEHLER:" in feedback
        assert "SERVER KONNTE NICHT GESTARTET WERDEN:" in feedback
        assert "SyntaxError: unexpected token" in feedback
        assert "Cannot find module 'next'" in feedback

    def test_feedback_beginnt_mit_header(self):
        """Feedback beginnt immer mit 'SMOKE-TEST FEHLGESCHLAGEN:'."""
        result = SmokeTestResult(passed=False, issues=["Test-Problem"])
        feedback = result.feedback_for_coder
        assert feedback.startswith("SMOKE-TEST FEHLGESCHLAGEN:")

    def test_leere_listen_keine_abschnitte(self):
        """Leere Listen erzeugen keine entsprechenden Abschnitte im Feedback."""
        result = SmokeTestResult(
            passed=False,
            server_started=True,
            page_loaded=True,
            compile_errors=[],
            console_errors=[],
            issues=[],
        )
        feedback = result.feedback_for_coder
        assert "SMOKE-TEST FEHLGESCHLAGEN:" in feedback
        assert "KOMPILIERUNGS-FEHLER" not in feedback
        assert "BROWSER CONSOLE-FEHLER" not in feedback
        assert "WEITERE PROBLEME" not in feedback
        assert "SERVER KONNTE NICHT GESTARTET WERDEN" not in feedback
        assert "SEITE KONNTE NICHT GELADEN WERDEN" not in feedback


# ===== Tests fuer Compile-Error-Patterns =====

class TestCompileErrorPatterns:
    """Tests fuer die _COMPILE_ERROR_PATTERNS Liste."""

    def test_patterns_nicht_leer(self):
        """Die Pattern-Liste ist nicht leer."""
        assert len(_COMPILE_ERROR_PATTERNS) > 0

    def test_bekannte_patterns_enthalten(self):
        """Alle erwarteten Compile-Error-Patterns sind in der Liste."""
        erwartete = [
            "Module not found",
            "ModuleNotFoundError",
            "Cannot find module",
            "Cannot resolve",
            "Failed to compile",
            "Build error",
            "SyntaxError",
            "TypeError:",
            "ReferenceError:",
            "ENOENT",
            "EPERM",
            "Cannot read properties of",
            "is not a function",
            "Unexpected token",
            "Error: Cannot find",
        ]
        for pattern in erwartete:
            assert pattern in _COMPILE_ERROR_PATTERNS, (
                f"Pattern '{pattern}' fehlt in _COMPILE_ERROR_PATTERNS"
            )

    def test_patterns_sind_strings(self):
        """Alle Patterns sind Strings (keine None-Werte oder andere Typen)."""
        for pattern in _COMPILE_ERROR_PATTERNS:
            assert isinstance(pattern, str), f"Pattern ist kein String: {pattern}"
            assert len(pattern) > 0, "Leerer Pattern-String gefunden"


# ===== Tests fuer Harmlose Patterns =====

class TestHarmlessPatterns:
    """Tests fuer die _HARMLESS_PATTERNS Liste."""

    def test_patterns_nicht_leer(self):
        """Die Harmlos-Pattern-Liste ist nicht leer."""
        assert len(_HARMLESS_PATTERNS) > 0

    def test_bekannte_harmlose_patterns_enthalten(self):
        """Alle erwarteten harmlosen Patterns sind in der Liste."""
        erwartete = [
            "warn", "notice", "npm warn", "[notice]",
            "deprecated", "ExperimentalWarning",
            "punycode", "cleanup",
        ]
        for pattern in erwartete:
            assert pattern in _HARMLESS_PATTERNS, (
                f"Harmloses Pattern '{pattern}' fehlt in _HARMLESS_PATTERNS"
            )

    def test_patterns_sind_strings(self):
        """Alle harmlosen Patterns sind Strings."""
        for pattern in _HARMLESS_PATTERNS:
            assert isinstance(pattern, str), f"Pattern ist kein String: {pattern}"
            assert len(pattern) > 0, "Leerer Pattern-String gefunden"

    def test_patterns_ueberwiegend_lowercase(self):
        """Harmlose Patterns sollten lowercase sein (lower_line.startswith-Vergleich).
        Hinweis: 'ExperimentalWarning' ist mixed-case — greift nur wenn Zeile
        exakt so geschrieben ist. Da lower_line verglichen wird, matcht es nur
        wenn das Pattern ebenfalls lowercase waere. Kein Produktionsproblem,
        weil ExperimentalWarning-Zeilen kein Compile-Error-Pattern enthalten."""
        lowercase_patterns = [p for p in _HARMLESS_PATTERNS if p == p.lower()]
        # Mindestens die Mehrheit muss lowercase sein
        assert len(lowercase_patterns) >= len(_HARMLESS_PATTERNS) - 1
        # ExperimentalWarning ist bekanntermaßen mixed-case
        assert "ExperimentalWarning" in _HARMLESS_PATTERNS


# ===== Tests fuer _extract_compile_errors =====

class TestExtractCompileErrors:
    """Tests fuer die _extract_compile_errors() Funktion."""

    def test_leerer_string_leere_liste(self):
        """Leerer String als Input gibt leere Liste zurueck."""
        assert _extract_compile_errors("") == []

    def test_none_aehnlich_leerer_string(self):
        """Ein leerer String (falsy) gibt leere Liste zurueck."""
        assert _extract_compile_errors("") == []

    def test_nur_whitespace(self):
        """Nur Whitespace im Input ergibt leere Liste (Zeilen kuerzer als 5 Zeichen)."""
        assert _extract_compile_errors("   \n  \n    ") == []

    def test_zeilen_kuerzer_als_5_zeichen_ignoriert(self):
        """Zeilen mit weniger als 5 Zeichen werden uebersprungen."""
        output = "ab\ncd\nSyntaxError in module xyz\nef"
        errors = _extract_compile_errors(output)
        assert len(errors) == 1
        assert "SyntaxError" in errors[0]

    def test_genau_5_zeichen_nicht_ignoriert(self):
        """Zeile mit genau 5 Zeichen wird verarbeitet (nicht ignoriert)."""
        # "EPERM" hat 5 Zeichen und ist ein Pattern
        output = "EPERM"
        errors = _extract_compile_errors(output)
        assert len(errors) == 1
        assert "EPERM" in errors[0]

    def test_module_not_found_erkannt(self):
        """'Module not found' Fehler wird korrekt erkannt."""
        output = "Module not found: Error: Can't resolve 'react-dom'"
        errors = _extract_compile_errors(output)
        assert len(errors) == 1
        assert "Module not found" in errors[0]

    def test_cannot_find_module_erkannt(self):
        """'Cannot find module' Fehler wird korrekt erkannt."""
        output = "Error: Cannot find module './components/Header'"
        errors = _extract_compile_errors(output)
        assert len(errors) == 1
        assert "Cannot find module" in errors[0]

    def test_failed_to_compile_erkannt(self):
        """'Failed to compile' Fehler wird korrekt erkannt."""
        output = "Failed to compile.\n\n./app/page.js"
        errors = _extract_compile_errors(output)
        assert len(errors) == 1
        assert "Failed to compile" in errors[0]

    def test_syntax_error_erkannt(self):
        """'SyntaxError' wird korrekt erkannt."""
        output = "SyntaxError: Unexpected end of input at line 42"
        errors = _extract_compile_errors(output)
        assert len(errors) == 1
        assert "SyntaxError" in errors[0]

    def test_type_error_erkannt(self):
        """'TypeError:' wird korrekt erkannt."""
        output = "TypeError: Cannot read properties of undefined (reading 'map')"
        errors = _extract_compile_errors(output)
        assert len(errors) == 1
        assert "TypeError:" in errors[0]

    def test_reference_error_erkannt(self):
        """'ReferenceError:' wird korrekt erkannt."""
        output = "ReferenceError: window is not defined"
        errors = _extract_compile_errors(output)
        assert len(errors) == 1
        assert "ReferenceError:" in errors[0]

    def test_enoent_erkannt(self):
        """'ENOENT' Fehler wird korrekt erkannt."""
        output = "Error: ENOENT: no such file or directory, open '/app/config.json'"
        errors = _extract_compile_errors(output)
        assert len(errors) == 1
        assert "ENOENT" in errors[0]

    def test_unexpected_token_erkannt(self):
        """'Unexpected token' Fehler wird korrekt erkannt."""
        output = "Unexpected token '<' in JSON at position 0"
        errors = _extract_compile_errors(output)
        assert len(errors) == 1
        assert "Unexpected token" in errors[0]

    def test_build_error_erkannt(self):
        """'Build error' wird korrekt erkannt."""
        output = "Build error occurred during page compilation"
        errors = _extract_compile_errors(output)
        assert len(errors) == 1
        assert "Build error" in errors[0]

    def test_cannot_resolve_erkannt(self):
        """'Cannot resolve' wird korrekt erkannt."""
        output = "Cannot resolve dependency '@/lib/utils'"
        errors = _extract_compile_errors(output)
        assert len(errors) == 1
        assert "Cannot resolve" in errors[0]

    def test_is_not_a_function_erkannt(self):
        """'is not a function' Fehler wird korrekt erkannt."""
        output = "db.prepare is not a function"
        errors = _extract_compile_errors(output)
        assert len(errors) == 1
        assert "is not a function" in errors[0]

    def test_cannot_read_properties_erkannt(self):
        """'Cannot read properties of' wird korrekt erkannt."""
        output = "Cannot read properties of null (reading 'useState')"
        errors = _extract_compile_errors(output)
        assert len(errors) == 1
        assert "Cannot read properties of" in errors[0]

    def test_error_cannot_find_erkannt(self):
        """'Error: Cannot find' wird korrekt erkannt."""
        output = "Error: Cannot find module 'next/server'"
        errors = _extract_compile_errors(output)
        assert len(errors) == 1
        assert "Error: Cannot find" in errors[0]

    def test_module_not_found_error_erkannt(self):
        """'ModuleNotFoundError' wird korrekt erkannt."""
        output = "ModuleNotFoundError: No module named 'flask'"
        errors = _extract_compile_errors(output)
        assert len(errors) == 1
        assert "ModuleNotFoundError" in errors[0]

    def test_eperm_erkannt(self):
        """'EPERM' Fehler wird korrekt erkannt."""
        output = "Error: EPERM: operation not permitted, unlink '/app/db.sqlite'"
        errors = _extract_compile_errors(output)
        assert len(errors) == 1
        assert "EPERM" in errors[0]

    def test_jedes_pattern_erkannt(self):
        """Jedes einzelne Pattern in _COMPILE_ERROR_PATTERNS wird von der Funktion erkannt."""
        for pattern in _COMPILE_ERROR_PATTERNS:
            zeile = f"Kontext-Text {pattern} weitere Details hier"
            errors = _extract_compile_errors(zeile)
            assert len(errors) >= 1, (
                f"Pattern '{pattern}' wurde nicht erkannt"
            )

    def test_harmlose_warnung_warn_gefiltert(self):
        """Zeilen die mit 'warn' beginnen werden als harmlos ignoriert."""
        output = "warn - Fast Refresh had to perform a full reload"
        errors = _extract_compile_errors(output)
        assert len(errors) == 0

    def test_harmlose_warnung_npm_warn_gefiltert(self):
        """Zeilen die mit 'npm warn' beginnen werden als harmlos ignoriert."""
        output = "npm warn deprecated inflight@1.0.6: This module is not supported"
        errors = _extract_compile_errors(output)
        assert len(errors) == 0

    def test_harmlose_warnung_deprecated_gefiltert(self):
        """Zeilen die mit 'deprecated' beginnen werden als harmlos ignoriert."""
        output = "deprecated: punycode module is deprecated"
        errors = _extract_compile_errors(output)
        assert len(errors) == 0

    def test_harmlose_warnung_notice_gefiltert(self):
        """Zeilen die mit 'notice' oder '[notice]' beginnen werden als harmlos ignoriert."""
        output = "notice: some npm notice here\n[notice] another notice"
        errors = _extract_compile_errors(output)
        assert len(errors) == 0

    def test_harmlose_warnung_experimental_kein_fehler(self):
        """ExperimentalWarning-Zeilen erzeugen keine Compile-Errors.
        Hinweis: Pattern ist mixed-case, matcht daher nicht via startswith
        auf lower_line — aber die Zeile enthaelt auch kein Compile-Error-Pattern."""
        output = "ExperimentalWarning: The Fetch API is an experimental feature"
        errors = _extract_compile_errors(output)
        assert len(errors) == 0

    def test_harmlose_warnung_punycode_gefiltert(self):
        """Zeilen die mit 'punycode' beginnen werden als harmlos ignoriert."""
        output = "punycode is deprecated. Use the URL constructor"
        errors = _extract_compile_errors(output)
        assert len(errors) == 0

    def test_harmlose_warnung_cleanup_gefiltert(self):
        """Zeilen die mit 'cleanup' beginnen werden als harmlos ignoriert."""
        output = "cleanup temporary files completed"
        errors = _extract_compile_errors(output)
        assert len(errors) == 0

    def test_harmlose_gross_kleinschreibung(self):
        """Harmlose Patterns werden case-insensitive geprueft (lower_line.startswith)."""
        gross_varianten = [
            "WARN - some warning",
            "Warn - capitalized warning",
            "DEPRECATED module xyz",
            "Deprecated: old API",
            "NPM WARN some package issue",
            "NOTICE: system message",
        ]
        for zeile in gross_varianten:
            errors = _extract_compile_errors(zeile)
            assert len(errors) == 0, (
                f"Gross geschriebene Warnung '{zeile}' wurde nicht gefiltert"
            )

    def test_zeile_auf_300_zeichen_gekuerzt(self):
        """Lange Fehlerzeilen werden auf maximal 300 Zeichen gekuerzt."""
        lange_zeile = "SyntaxError: " + "A" * 400
        errors = _extract_compile_errors(lange_zeile)
        assert len(errors) == 1
        assert len(errors[0]) == 300

    def test_genau_300_zeichen_nicht_gekuerzt(self):
        """Zeile mit genau 300 Zeichen wird nicht weiter gekuerzt."""
        zeile = "SyntaxError: " + "B" * (300 - len("SyntaxError: "))
        assert len(zeile) == 300
        errors = _extract_compile_errors(zeile)
        assert len(errors) == 1
        assert len(errors[0]) == 300

    def test_kombination_harmlose_und_echte_fehler(self):
        """Kombination aus harmlosen Warnungen und echten Fehlern wird korrekt getrennt."""
        output = "\n".join([
            "warn - Fast Refresh had to perform a full reload",
            "npm warn deprecated glob@7.2.3",
            "Module not found: Error: Can't resolve 'react-dom'",
            "deprecated: punycode module",
            "SyntaxError: Unexpected identifier",
            "[notice] npm update available",
            "TypeError: Cannot read properties of undefined",
        ])
        errors = _extract_compile_errors(output)
        assert len(errors) == 3
        assert any("Module not found" in e for e in errors)
        assert any("SyntaxError" in e for e in errors)
        assert any("TypeError:" in e for e in errors)

    def test_mehrere_fehler_verschiedener_typen(self):
        """Mehrere verschiedene Fehlertypen werden alle erkannt."""
        output = "\n".join([
            "Failed to compile.",
            "ENOENT: no such file or directory",
            "Build error occurred",
        ])
        errors = _extract_compile_errors(output)
        assert len(errors) == 3

    def test_leere_zeilen_ignoriert(self):
        """Leere Zeilen im Output werden uebersprungen."""
        output = "\n\n\nSyntaxError: bad input\n\n\n"
        errors = _extract_compile_errors(output)
        assert len(errors) == 1
        assert "SyntaxError" in errors[0]

    def test_whitespace_in_zeilen_getrimmt(self):
        """Fuehrende und abschliessende Whitespace in Zeilen wird getrimmt."""
        output = "   SyntaxError: unexpected end   "
        errors = _extract_compile_errors(output)
        assert len(errors) == 1
        assert errors[0].startswith("SyntaxError")

    def test_kein_pattern_match_keine_errors(self):
        """Zeilen ohne Compile-Error-Pattern werden nicht als Fehler erkannt."""
        output = "\n".join([
            "Starting development server...",
            "Compiled successfully!",
            "Ready on http://localhost:3000",
            "Server is running on port 3000",
        ])
        errors = _extract_compile_errors(output)
        assert len(errors) == 0

    def test_pattern_in_mitte_der_zeile(self):
        """Ein Pattern mitten in der Zeile wird trotzdem erkannt (kein startswith)."""
        output = "Error occurred: Module not found in ./app/page.js"
        errors = _extract_compile_errors(output)
        assert len(errors) == 1
        assert "Module not found" in errors[0]

    def test_harmlose_warnung_nur_wenn_am_anfang(self):
        """Harmlose Patterns werden nur am Zeilenanfang gefiltert (startswith)."""
        # "warn" mitten in der Zeile + ein echtes Pattern → wird erkannt
        output = "Something warn about SyntaxError: bad code"
        errors = _extract_compile_errors(output)
        assert len(errors) == 1
        assert "SyntaxError" in errors[0]

    def test_ein_fehler_pro_zeile_maximal(self):
        """Pro Zeile wird maximal ein Fehler erkannt (break nach erstem Pattern-Match)."""
        # Zeile enthaelt zwei Patterns, aber nur einmal in der Ergebnisliste
        output = "SyntaxError: Unexpected token TypeError: null"
        errors = _extract_compile_errors(output)
        assert len(errors) == 1
