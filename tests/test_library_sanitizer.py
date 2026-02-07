# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 07.02.2026
Version: 1.0
Beschreibung: Tests fuer backend/library_sanitizer.py
              Testet: Pfad-Anonymisierung, Secret-Redaktion, Stacktrace-Entfernung,
              Token-Neuberechnung, Archiv-Sanitisierung
"""

import os
import sys
import json
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.library_sanitizer import (
    hash_text,
    sanitize_paths,
    redact_stack_traces,
    sanitize_text,
    sanitize_structure,
    recalculate_totals,
    prepare_archive_payload,
)


# ============================================================================
# Tests: hash_text
# ============================================================================

class TestHashText:
    """Tests fuer die Hash-Funktion."""

    def test_erzeugt_10_zeichen(self):
        """Hash hat genau 10 Zeichen."""
        result = hash_text("test")
        assert len(result) == 10, f"Erwartet: 10 Zeichen, Erhalten: {len(result)}"

    def test_determinismus(self):
        """Gleicher Input gibt gleichen Hash."""
        assert hash_text("hello") == hash_text("hello")

    def test_unterschiedliche_inputs(self):
        """Unterschiedliche Inputs geben verschiedene Hashes."""
        assert hash_text("a") != hash_text("b")

    def test_hexadezimal(self):
        """Hash besteht aus hexadezimalen Zeichen."""
        result = hash_text("test")
        assert all(c in "0123456789abcdef" for c in result), (
            f"Hash enthaelt nicht-hexadezimale Zeichen: {result}")


# ============================================================================
# Tests: sanitize_paths
# ============================================================================

class TestSanitizePaths:
    """Tests fuer die Pfad-Anonymisierung."""

    def test_windows_user_pfad(self):
        """Windows User-Pfad wird anonymisiert."""
        text = r"Fehler in C:\Users\johndoe\projects\app.py"
        result = sanitize_paths(text)
        assert "johndoe" not in result, "Benutzername nicht anonymisiert"
        assert "<USER>" in result, "<USER> Platzhalter fehlt"

    def test_windows_forward_slash(self):
        """Windows-Pfad mit Forward-Slashes wird anonymisiert."""
        text = "Datei: C:/Users/admin/Desktop/file.txt"
        result = sanitize_paths(text)
        assert "admin" not in result, "Benutzername nicht anonymisiert"

    def test_unix_home_pfad(self):
        """Unix Home-Pfad wird anonymisiert."""
        text = "Fehler in /Users/johndoe/code/app.py"
        result = sanitize_paths(text)
        assert "johndoe" not in result, "Unix Benutzername nicht anonymisiert"
        assert "<USER>" in result

    def test_linux_home_pfad(self):
        """Linux /home/ Pfad wird anonymisiert."""
        text = "Datei: /home/developer/src/main.py"
        result = sanitize_paths(text)
        assert "developer" not in result, "Linux Benutzername nicht anonymisiert"

    def test_text_ohne_pfade(self):
        """Text ohne Pfade bleibt unveraendert."""
        text = "Dies ist normaler Text ohne Dateipfade."
        result = sanitize_paths(text)
        assert result == text, "Text ohne Pfade sollte unveraendert bleiben"

    def test_mehrere_pfade(self):
        """Mehrere Pfade im selben Text werden alle anonymisiert."""
        text = r"A: C:\Users\alice\a.py und B: C:\Users\bob\b.py"
        result = sanitize_paths(text)
        assert "alice" not in result, "alice nicht anonymisiert"
        assert "bob" not in result, "bob nicht anonymisiert"


# ============================================================================
# Tests: redact_stack_traces
# ============================================================================

class TestRedactStackTraces:
    """Tests fuer die Stacktrace-Redigierung."""

    def test_python_stacktrace(self):
        """Python Traceback wird redigiert."""
        text = """Fehler aufgetreten:
Traceback (most recent call last):
  File "app.py", line 42, in main
    raise ValueError("test")
ValueError: test"""
        result = redact_stack_traces(text)
        assert "STACK_TRACE_REDACTED" in result, "Stacktrace nicht redigiert"
        assert 'File "app.py"' not in result, "Dateidetails noch sichtbar"

    def test_javascript_stacktrace(self):
        """JavaScript Stacktrace wird redigiert."""
        text = """Error: Something went wrong
    at Object.handler (/app/api/route.js:15:10)
    at Module.execute (/app/node_modules/next/dist/server.js:42:5)"""
        result = redact_stack_traces(text)
        assert "STACK_TRACE_REDACTED" in result

    def test_text_ohne_stacktrace(self):
        """Text ohne Stacktrace bleibt unveraendert."""
        text = "Alles in Ordnung, kein Fehler aufgetreten."
        result = redact_stack_traces(text)
        assert result == text


# ============================================================================
# Tests: sanitize_text
# ============================================================================

class TestSanitizeText:
    """Tests fuer die vollstaendige Text-Sanitisierung."""

    def test_env_datei_redigiert(self):
        """Inhalte von .env Dateien werden redigiert."""
        text = """### FILENAME: .env
SECRET_KEY=super_secret_value
DATABASE_URL=postgres://localhost
### FILENAME: app.py
print("hello")"""
        result = sanitize_text(text)
        assert "super_secret_value" not in result, "Secret-Wert nicht redigiert"
        assert "ENV_DATEI_REDAKTIERT" in result

    def test_secret_key_redigiert(self):
        """SECRET_KEY Werte werden redigiert."""
        text = "SECRET_KEY = my-super-secret-key-12345"
        result = sanitize_text(text)
        assert "my-super-secret-key-12345" not in result
        assert "REDACTED_SECRET" in result

    def test_dart_token_redigiert(self):
        """DART_TOKEN wird redigiert."""
        text = "DART_TOKEN=drt_abc123xyz"
        result = sanitize_text(text)
        assert "drt_abc123xyz" not in result
        assert "REDACTED_SECRET" in result

    def test_user_id_redigiert(self):
        """User-IDs werden redigiert."""
        text = '{"user_id": "usr_abc123"}'
        result = sanitize_text(text)
        assert "usr_abc123" not in result
        assert "REDACTED_USER" in result

    def test_app_config_secret(self):
        """app.config SECRET_KEY wird redigiert."""
        text = "app.config['SECRET_KEY'] = 'my-secret-value'"
        result = sanitize_text(text)
        assert "my-secret-value" not in result

    def test_os_environ_secret(self):
        """os.environ.get SECRET_KEY wird redigiert."""
        text = "os.environ.get('SECRET_KEY', 'fallback-secret')"
        result = sanitize_text(text)
        assert "fallback-secret" not in result

    def test_kombinierte_sanitisierung(self):
        """Pfade + Secrets + Stacktraces werden zusammen redigiert."""
        text = """SECRET_KEY=abc123
Fehler in C:\\Users\\admin\\app.py
Traceback (most recent call last):
  File "test.py", line 1
Error"""
        result = sanitize_text(text)
        assert "abc123" not in result
        assert "admin" not in result
        assert "STACK_TRACE_REDACTED" in result


# ============================================================================
# Tests: sanitize_structure
# ============================================================================

class TestSanitizeStructure:
    """Tests fuer die rekursive Struktur-Sanitisierung."""

    def test_dict_sanitisierung(self):
        """Dict-Werte werden rekursiv sanitisiert."""
        data = {"key": "SECRET_KEY=abc123"}
        result = sanitize_structure(data)
        assert "abc123" not in str(result)

    def test_liste_sanitisierung(self):
        """Listen-Eintraege werden sanitisiert."""
        data = ["SECRET_KEY=abc123", "normaler Text"]
        result = sanitize_structure(data)
        assert "abc123" not in str(result)
        assert "normaler Text" in str(result)

    def test_env_dateien_gefiltert(self):
        """Dateien mit .env Endung werden aus 'files'-Listen entfernt."""
        data = {"files": [".env", "app.py", "config/.env", "main.js"]}
        result = sanitize_structure(data)
        assert ".env" not in result["files"], ".env nicht aus files entfernt"
        assert "config/.env" not in result["files"]
        assert "app.py" in result["files"]
        assert "main.js" in result["files"]

    def test_verschachtelte_struktur(self):
        """Tief verschachtelte Strukturen werden komplett sanitisiert."""
        data = {
            "level1": {
                "level2": {
                    "secret": "DART_TOKEN=xyz789"
                }
            }
        }
        result = sanitize_structure(data)
        assert "xyz789" not in json.dumps(result)

    def test_zahlen_bleiben(self):
        """Numerische Werte bleiben unveraendert."""
        data = {"count": 42, "cost": 3.14}
        result = sanitize_structure(data)
        assert result["count"] == 42
        assert result["cost"] == 3.14

    def test_none_bleibt(self):
        """None-Werte bleiben unveraendert."""
        data = {"value": None}
        result = sanitize_structure(data)
        assert result["value"] is None


# ============================================================================
# Tests: recalculate_totals
# ============================================================================

class TestRecalculateTotals:
    """Tests fuer die Token-Neuberechnung."""

    def test_token_metrics_summierung(self):
        """TokenMetrics Eintraege werden korrekt summiert."""
        project = {
            "entries": [
                {"type": "TokenMetrics", "content": json.dumps({"total_tokens": 100, "total_cost": 0.01})},
                {"type": "TokenMetrics", "content": json.dumps({"total_tokens": 200, "total_cost": 0.02})},
            ]
        }
        recalculate_totals(project)
        assert project["total_tokens"] == 300, (
            f"Erwartet: 300 Tokens, Erhalten: {project['total_tokens']}")
        assert project["total_cost"] == 0.03

    def test_metadata_tokens(self):
        """Tokens aus Entry-Metadata werden summiert."""
        project = {
            "entries": [
                {"type": "code", "metadata": {"tokens": 500, "cost": 0.05}},
                {"type": "review", "metadata": {"tokens": 300, "cost": 0.03}},
            ]
        }
        recalculate_totals(project)
        assert project["total_tokens"] == 800
        assert project["total_cost"] == 0.08

    def test_keine_metriken(self):
        """Ohne Metriken werden Totals auf None gesetzt."""
        project = {"entries": [{"type": "code", "content": "print('hello')"}]}
        recalculate_totals(project)
        assert project["total_tokens"] is None
        assert project["total_cost"] is None

    def test_leere_entries(self):
        """Leere Entry-Liste setzt Totals auf None."""
        project = {"entries": []}
        recalculate_totals(project)
        assert project["total_tokens"] is None

    def test_gemischte_metriken(self):
        """Gemischte TokenMetrics und Metadata-Tokens werden kombiniert."""
        project = {
            "entries": [
                {"type": "TokenMetrics", "content": json.dumps({"total_tokens": 100, "total_cost": 0.01})},
                {"type": "code", "metadata": {"tokens": 200, "cost": 0.02}},
            ]
        }
        recalculate_totals(project)
        assert project["total_tokens"] == 300
        assert project["total_cost"] == 0.03

    def test_content_als_dict(self):
        """TokenMetrics mit content als Dict (statt String) funktioniert."""
        project = {
            "entries": [
                {"type": "TokenMetrics", "content": {"total_tokens": 150, "total_cost": 0.015}},
            ]
        }
        recalculate_totals(project)
        assert project["total_tokens"] == 150


# ============================================================================
# Tests: prepare_archive_payload
# ============================================================================

class TestPrepareArchivePayload:
    """Tests fuer die vollstaendige Archiv-Vorbereitung."""

    def test_deep_copy(self):
        """Original-Projekt wird nicht veraendert."""
        project = {
            "entries": [{"type": "code", "content": "SECRET_KEY=abc"}],
            "total_tokens": 999
        }
        result = prepare_archive_payload(project)
        # Original unveraendert
        assert "abc" in project["entries"][0]["content"], "Original wurde veraendert"
        # Kopie sanitisiert
        assert "abc" not in result["entries"][0]["content"]

    def test_sanitisierung_und_neuberechnung(self):
        """Kombiniert Sanitisierung mit Token-Neuberechnung."""
        project = {
            "entries": [
                {
                    "type": "TokenMetrics",
                    "content": json.dumps({"total_tokens": 500, "total_cost": 0.05})
                },
                {
                    "type": "code",
                    "content": "SECRET_KEY=geheim123",
                    "metadata": {"tokens": 100}
                }
            ],
            "total_tokens": 0,
            "total_cost": 0
        }
        result = prepare_archive_payload(project)
        # Secrets redigiert
        assert "geheim123" not in json.dumps(result)
        # Totals neu berechnet
        assert result["total_tokens"] == 600
        assert result["total_cost"] == 0.05

    def test_leeres_projekt(self):
        """Leeres Projekt wird korrekt verarbeitet."""
        project = {"entries": [], "total_tokens": 0}
        result = prepare_archive_payload(project)
        assert result["total_tokens"] is None
