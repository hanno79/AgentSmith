# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 02.02.2026
Version: 1.1
Beschreibung: Tests fuer backend.orchestration_utils.
              AENDERUNG 06.02.2026: Tests fuer _repair_json, _extract_user_requirements,
              _infer_blueprint_from_requirements hinzugefuegt (Coverage-Erhoehung).
"""

import json
import time
import pytest

from backend.orchestration_utils import (
    run_with_timeout,
    _extract_json_from_text,
    _repair_json,
    _extract_user_requirements,
    _infer_blueprint_from_requirements,
)


class TestRunWithTimeout:
    """Tests für run_with_timeout."""

    def test_completes_before_timeout(self):
        def fast():
            return 42
        result = run_with_timeout(fast, timeout_seconds=5)
        assert result == 42

    def test_returns_value_before_timeout(self):
        def with_value():
            return {"key": "value"}
        result = run_with_timeout(with_value, timeout_seconds=10)
        assert result == {"key": "value"}

    def test_exceeds_timeout_raises(self):
        def slow():
            time.sleep(3)
            return 1
        with pytest.raises(TimeoutError) as exc_info:
            run_with_timeout(slow, timeout_seconds=1)
        assert "länger als" in str(exc_info.value) or "1s" in str(exc_info.value)

    def test_exception_in_func_propagates(self):
        def failing():
            raise ValueError("Test-Fehler")
        with pytest.raises(Exception) as exc_info:
            run_with_timeout(failing, timeout_seconds=5)
        assert "Test-Fehler" in str(exc_info.value) or "Unerwarteter Fehler" in str(exc_info.value)


class TestExtractJsonFromText:
    """Tests für _extract_json_from_text."""

    def test_valid_json_embedded(self):
        text = "Hier ist die Antwort: {\"a\": 1, \"b\": 2} und mehr Text."
        extracted = _extract_json_from_text(text)
        assert extracted is not None
        data = json.loads(extracted)
        assert data == {"a": 1, "b": 2}

    def test_nested_json(self):
        text = "Result: {\"x\": {\"y\": 3}}"
        extracted = _extract_json_from_text(text)
        assert extracted is not None
        data = json.loads(extracted)
        assert data == {"x": {"y": 3}}

    def test_no_json_returns_none(self):
        text = "Kein JSON hier, nur Text."
        assert _extract_json_from_text(text) is None

    def test_malformed_unbalanced_returns_none_or_partial(self):
        text = "{\"a\": 1"
        result = _extract_json_from_text(text)
        # Kann None sein (unbalanciert) oder bei Klammer-Ende den String zurückgeben
        assert result is None or "{" in (result or "")

    def test_empty_string_returns_none(self):
        assert _extract_json_from_text("") is None


# =========================================================================
# AENDERUNG 06.02.2026: Neue Tests fuer Coverage-Erhoehung
# =========================================================================


class TestRepairJson:
    """Tests fuer _repair_json - repariert ungueltige JSON-Strings."""

    def test_single_quotes_zu_double_quotes(self):
        """Single-Quotes in Keys und Values werden ersetzt."""
        text = "{'name': 'test', 'value': 'hello'}"
        result = _repair_json(text)
        assert '"name"' in result
        assert '"test"' in result

    def test_trailing_commas_entfernt(self):
        """Trailing Commas vor } und ] werden entfernt."""
        text = '{"a": 1, "b": 2,}'
        result = _repair_json(text)
        assert ",}" not in result
        # Ergebnis sollte parsbar sein
        parsed = json.loads(result)
        assert parsed == {"a": 1, "b": 2}

    def test_javascript_comments_entfernt(self):
        """JavaScript-Kommentare werden entfernt."""
        text = '{"a": 1 // Kommentar\n}'
        result = _repair_json(text)
        assert "Kommentar" not in result
        assert '"a"' in result

    def test_block_comments_entfernt(self):
        """Block-Kommentare /* */ werden entfernt."""
        text = '{"a": /* wert */ 1}'
        result = _repair_json(text)
        assert "wert" not in result


class TestExtractUserRequirements:
    """Tests fuer _extract_user_requirements - erkennt Anforderungen aus User-Goal."""

    def test_erkennt_datenbank(self):
        """SQLite-Datenbank wird erkannt."""
        reqs = _extract_user_requirements("Erstelle eine App mit SQLite Datenbank")
        assert reqs.get("database") == "sqlite"

    def test_erkennt_postgres(self):
        """PostgreSQL wird erkannt."""
        reqs = _extract_user_requirements("Backend mit PostgreSQL")
        assert reqs.get("database") == "postgres"

    def test_erkennt_sprache_python(self):
        """Python als Sprache wird erkannt."""
        reqs = _extract_user_requirements("Schreibe ein Python-Skript")
        assert reqs.get("language") == "python"

    def test_erkennt_sprache_javascript(self):
        """JavaScript/Node wird erkannt."""
        reqs = _extract_user_requirements("Erstelle eine Node.js App")
        assert reqs.get("language") == "javascript"

    def test_erkennt_framework_flask(self):
        """Flask-Framework wird erkannt."""
        reqs = _extract_user_requirements("Baue eine Flask-Webanwendung")
        assert reqs.get("framework") == "flask"

    def test_erkennt_ui_typ_webapp(self):
        """Webapp UI-Typ wird erkannt."""
        reqs = _extract_user_requirements("Erstelle eine Website mit Login")
        assert reqs.get("ui_type") == "webapp"

    def test_erkennt_ui_typ_desktop(self):
        """Desktop UI-Typ wird erkannt."""
        reqs = _extract_user_requirements("Erstelle eine Desktop-Anwendung")
        assert reqs.get("ui_type") == "desktop"

    def test_erkennt_ui_typ_api(self):
        """API UI-Typ wird erkannt."""
        reqs = _extract_user_requirements("Baue eine REST API")
        assert reqs.get("ui_type") == "api"

    def test_erkennt_ui_typ_cli(self):
        """CLI UI-Typ wird erkannt."""
        reqs = _extract_user_requirements("Erstelle ein CLI-Tool fuer Terminal")
        assert reqs.get("ui_type") == "cli"

    def test_kein_match_leere_requirements(self):
        """Unspezifisches Goal ergibt leere Requirements."""
        reqs = _extract_user_requirements("Mach etwas Cooles")
        assert "database" not in reqs
        assert "language" not in reqs
        assert "framework" not in reqs

    def test_kombination_framework_und_datenbank(self):
        """Mehrere Requirements gleichzeitig erkannt."""
        reqs = _extract_user_requirements("Flask App mit SQLite Datenbank")
        assert reqs.get("framework") == "flask"
        assert reqs.get("database") == "sqlite"


class TestInferBlueprintFromRequirements:
    """Tests fuer _infer_blueprint_from_requirements - erstellt Blueprint aus Goal."""

    def test_flask_projekt(self):
        """Flask-Goal erzeugt flask_app Blueprint."""
        bp = _infer_blueprint_from_requirements("Erstelle eine Flask-Webanwendung")
        assert bp["project_type"] == "flask_app"
        assert bp["language"] == "python"
        assert bp["requires_server"] is True

    def test_react_projekt(self):
        """React-Goal erzeugt react_spa Blueprint."""
        bp = _infer_blueprint_from_requirements("Baue eine React Single Page App")
        assert bp["project_type"] == "react_spa"
        assert bp["language"] == "javascript"
        assert bp["requires_server"] is True

    def test_desktop_app(self):
        """Desktop-Goal erzeugt tkinter_desktop Blueprint."""
        bp = _infer_blueprint_from_requirements("Erstelle eine Desktop-Anwendung mit Fenster")
        assert bp["project_type"] == "tkinter_desktop"
        assert bp["app_type"] == "desktop"
        assert bp["requires_server"] is False

    def test_cli_tool(self):
        """CLI-Goal erzeugt python_cli Blueprint."""
        bp = _infer_blueprint_from_requirements("Baue ein CLI Terminal Tool")
        assert bp["project_type"] == "python_cli"
        assert bp["app_type"] == "cli"

    def test_api_projekt(self):
        """API-Goal erzeugt fastapi_app Blueprint."""
        bp = _infer_blueprint_from_requirements("Erstelle eine REST API")
        assert bp["project_type"] == "fastapi_app"
        assert bp["app_type"] == "api"

    def test_fallback_ohne_erkennbares_goal(self):
        """Unspezifisches Goal erzeugt static_html Fallback."""
        bp = _infer_blueprint_from_requirements("Mach etwas Cooles")
        assert bp["project_type"] == "static_html"
        assert "reasoning" in bp

    def test_datenbank_wird_uebernommen(self):
        """Datenbank-Anforderung wird in Blueprint gesetzt."""
        bp = _infer_blueprint_from_requirements("Python-Skript mit SQLite")
        assert bp.get("database") == "sqlite"

    def test_sprache_wird_erzwungen(self):
        """Explizite Sprache ueberschreibt Default."""
        bp = _infer_blueprint_from_requirements("Erstelle eine JavaScript-Anwendung")
        assert bp["language"] == "javascript"

    def test_fehlerbehandlung_gibt_fallback(self):
        """Bei leerem Goal kommt kein Crash sondern Fallback."""
        bp = _infer_blueprint_from_requirements("")
        assert "project_type" in bp
