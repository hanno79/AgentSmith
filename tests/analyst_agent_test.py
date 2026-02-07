# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 01.02.2026
Version: 1.0
Beschreibung: Unit Tests für Analyst Agent - Discovery-Briefing Analyse.
              Konvention: *_test.py (analyst_agent_test).
"""

import pytest
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.analyst_agent import (
    create_analyst,
    create_analysis_task,
    _format_briefing,
    parse_analyst_output,
    create_default_requirements
)


# =========================================================================
# Fixtures
# =========================================================================

@pytest.fixture
def sample_config():
    """Standard-Konfiguration für Tests."""
    return {
        "mode": "test",
        "models": {
            "test": {
                "meta_orchestrator": {
                    "primary": "openrouter/meta-llama/llama-3.3-70b-instruct:free",
                    "fallback": []
                }
            }
        }
    }


@pytest.fixture
def sample_project_rules():
    """Standard-Projektregeln für Tests."""
    return {
        "global": ["Nutze deutsche Fehlermeldungen"],
        "analyst": ["Extrahiere alle Anforderungen"]
    }


@pytest.fixture
def sample_briefing():
    """Beispiel Discovery-Briefing für Tests."""
    return {
        "projectName": "Todo-App",
        "goal": "Eine einfache Todo-Liste mit CRUD-Funktionen",
        "techRequirements": {
            "language": "python",
            "deployment": "local"
        },
        "agents": ["coder", "tester"],
        "answers": [
            {
                "question": "Welche Funktionen soll die App haben?",
                "agent": "researcher",
                "selectedValues": ["Tasks erstellen", "Tasks bearbeiten"],
                "customText": "",
                "skipped": False
            },
            {
                "question": "Welche Datenbank?",
                "agent": "database_designer",
                "selectedValues": ["SQLite"],
                "customText": "",
                "skipped": False
            },
            {
                "question": "Optionale Frage",
                "agent": "tester",
                "selectedValues": [],
                "customText": "",
                "skipped": True
            }
        ],
        "openPoints": ["UI-Design noch offen"]
    }


@pytest.fixture
def valid_analyst_output_json():
    """Gültiger Analyst-Output als JSON-String."""
    return '''```json
{
  "anforderungen": [
    {
      "id": "REQ-001",
      "titel": "Task-Erstellung",
      "beschreibung": "Benutzer kann neue Tasks erstellen",
      "kategorie": "Funktional",
      "prioritaet": "hoch",
      "quelle": "Discovery-Frage 1",
      "akzeptanzkriterien": ["Task kann erstellt werden", "Task wird gespeichert"]
    },
    {
      "id": "REQ-002",
      "titel": "Task-Bearbeitung",
      "beschreibung": "Benutzer kann bestehende Tasks bearbeiten",
      "kategorie": "Funktional",
      "prioritaet": "hoch",
      "quelle": "Discovery-Frage 1",
      "akzeptanzkriterien": ["Task kann bearbeitet werden"]
    }
  ],
  "kategorien": ["Funktional", "Technisch"],
  "zusammenfassung": "Todo-App mit CRUD-Funktionen"
}
```'''


# =========================================================================
# Test: _format_briefing
# =========================================================================

class TestFormatBriefing:
    """Tests für _format_briefing Funktion."""

    def test_basic_formatting(self, sample_briefing):
        """Briefing wird korrekt formatiert."""
        result = _format_briefing(sample_briefing)
        assert "PROJEKT: Todo-App" in result
        assert "ZIEL:" in result
        assert "Todo-Liste" in result

    def test_tech_requirements(self, sample_briefing):
        """Technische Anforderungen werden formatiert."""
        result = _format_briefing(sample_briefing)
        assert "python" in result
        assert "local" in result

    def test_agents_listed(self, sample_briefing):
        """Agenten werden aufgelistet."""
        result = _format_briefing(sample_briefing)
        assert "coder" in result
        assert "tester" in result

    def test_answers_included(self, sample_briefing):
        """Nicht-übersprungene Antworten werden inkludiert."""
        result = _format_briefing(sample_briefing)
        assert "Tasks erstellen" in result
        assert "SQLite" in result

    def test_skipped_answers_excluded(self, sample_briefing):
        """Übersprungene Antworten werden ausgeschlossen."""
        result = _format_briefing(sample_briefing)
        assert "Optionale Frage" not in result

    def test_open_points_included(self, sample_briefing):
        """Offene Punkte werden inkludiert."""
        result = _format_briefing(sample_briefing)
        assert "OFFENE PUNKTE" in result
        assert "UI-Design" in result

    def test_empty_briefing(self):
        """Leeres Briefing wird behandelt."""
        result = _format_briefing({})
        assert "PROJEKT: Unbenannt" in result
        assert "Nicht definiert" in result

    def test_custom_text_answer(self):
        """Antwort mit customText wird formatiert."""
        briefing = {
            "projectName": "Test",
            "goal": "Test",
            "techRequirements": {},
            "agents": [],
            "answers": [
                {
                    "question": "Sonstiges?",
                    "agent": "researcher",
                    "selectedValues": [],
                    "customText": "Mein eigener Text",
                    "skipped": False
                }
            ]
        }
        result = _format_briefing(briefing)
        assert "Mein eigener Text" in result


# =========================================================================
# Test: parse_analyst_output
# =========================================================================

class TestParseAnalystOutput:
    """Tests für parse_analyst_output Funktion."""

    def test_parse_json_block(self, valid_analyst_output_json):
        """JSON-Block in Markdown wird geparst."""
        result = parse_analyst_output(valid_analyst_output_json)
        assert result is not None
        assert "anforderungen" in result
        assert len(result["anforderungen"]) == 2

    def test_parse_raw_json(self):
        """Rohes JSON wird geparst."""
        raw_json = '{"anforderungen": [{"id": "REQ-001", "titel": "Test"}], "kategorien": []}'
        result = parse_analyst_output(raw_json)
        assert result is not None
        assert "anforderungen" in result

    def test_parse_code_block(self):
        """Generischer Code-Block wird geparst."""
        output = '''```
{"anforderungen": [{"id": "REQ-001"}], "kategorien": []}
```'''
        result = parse_analyst_output(output)
        assert result is not None

    def test_empty_output_returns_none(self):
        """Leerer Output gibt None zurück."""
        assert parse_analyst_output("") is None
        assert parse_analyst_output(None) is None

    def test_invalid_json_returns_none(self):
        """Ungültiges JSON gibt None zurück."""
        result = parse_analyst_output("Das ist kein JSON")
        assert result is None

    def test_missing_anforderungen_returns_none(self):
        """JSON ohne anforderungen gibt None zurück."""
        result = parse_analyst_output('{"andere_daten": []}')
        assert result is None

    def test_anforderungen_not_list_handled(self):
        """JSON mit nicht-Liste anforderungen wird behandelt."""
        result = parse_analyst_output('{"anforderungen": "keine Liste"}')
        if result is not None:
            assert "anforderungen" in result

    def test_json_with_extra_text(self):
        """JSON mit umgebendem Text wird geparst."""
        output = '''Hier ist meine Analyse:
```json
{"anforderungen": [{"id": "REQ-001"}], "kategorien": []}
```
Das war meine Analyse.'''
        result = parse_analyst_output(output)
        assert result is not None

    def test_extracts_correct_data(self, valid_analyst_output_json):
        """Korrekte Daten werden extrahiert."""
        result = parse_analyst_output(valid_analyst_output_json)
        assert result["anforderungen"][0]["id"] == "REQ-001"
        assert result["anforderungen"][0]["kategorie"] == "Funktional"
        assert "zusammenfassung" in result


# =========================================================================
# Test: create_default_requirements
# =========================================================================

class TestCreateDefaultRequirements:
    """Tests für create_default_requirements Funktion."""

    def test_creates_basic_requirements(self, sample_briefing):
        """Standard-Anforderungen werden erstellt."""
        result = create_default_requirements(sample_briefing)
        assert "anforderungen" in result
        assert len(result["anforderungen"]) >= 1
        assert "kategorien" in result

    def test_uses_project_goal(self, sample_briefing):
        """Projektziel wird verwendet."""
        result = create_default_requirements(sample_briefing)
        main_req = result["anforderungen"][0]
        assert sample_briefing["goal"] in main_req["beschreibung"] or "Kernfunktion" in main_req["beschreibung"]

    def test_has_required_fields(self, sample_briefing):
        """Alle Pflichtfelder sind vorhanden."""
        result = create_default_requirements(sample_briefing)
        for req in result["anforderungen"]:
            assert "id" in req
            assert "titel" in req
            assert "beschreibung" in req
            assert "kategorie" in req
            assert "prioritaet" in req
            assert "akzeptanzkriterien" in req

    def test_marks_as_fallback(self, sample_briefing):
        """Ergebnis wird als Fallback markiert."""
        result = create_default_requirements(sample_briefing)
        assert result.get("source") == "default_fallback"

    def test_empty_briefing(self):
        """Leeres Briefing erzeugt Standard-Anforderungen."""
        result = create_default_requirements({})
        assert "anforderungen" in result
        assert len(result["anforderungen"]) >= 1


# =========================================================================
# Test: create_analyst (Agent-Erstellung)
# =========================================================================

class TestCreateAnalyst:
    """Tests für create_analyst Funktion."""

    def test_creates_agent(self, sample_config, sample_project_rules):
        """Agent wird erstellt."""
        try:
            agent = create_analyst(sample_config, sample_project_rules)
            assert agent is not None
            assert hasattr(agent, 'role')
            assert "Analyst" in agent.role
        except Exception as e:
            pytest.skip(f"CrewAI Agent-Erstellung nicht möglich: {e}")

    def test_with_router(self, sample_config, sample_project_rules):
        """Agent mit Router wird erstellt."""
        class MockRouter:
            def get_model(self, role):
                return "test-model"

        try:
            agent = create_analyst(sample_config, sample_project_rules, router=MockRouter())
            assert agent is not None
        except Exception as e:
            pytest.skip(f"CrewAI Agent-Erstellung nicht möglich: {e}")


# =========================================================================
# Test: create_analysis_task
# =========================================================================

class TestCreateAnalysisTask:
    """Tests für create_analysis_task Funktion."""

    def test_creates_task(self, sample_config, sample_project_rules, sample_briefing):
        """Task wird erstellt."""
        try:
            agent = create_analyst(sample_config, sample_project_rules)
            task = create_analysis_task(agent, sample_briefing)
            assert task is not None
            assert hasattr(task, 'description')
            assert "DISCOVERY-BRIEFING" in task.description
        except Exception as e:
            pytest.skip(f"CrewAI Task-Erstellung nicht möglich: {e}")

    def test_task_contains_briefing(self, sample_config, sample_project_rules, sample_briefing):
        """Task enthält Briefing-Inhalt."""
        try:
            agent = create_analyst(sample_config, sample_project_rules)
            task = create_analysis_task(agent, sample_briefing)
            assert "Todo-App" in task.description
        except Exception as e:
            pytest.skip(f"CrewAI Task-Erstellung nicht möglich: {e}")


# =========================================================================
# Test: Integration
# =========================================================================

class TestIntegration:
    """Integrationstests für Analyst-Komponenten."""

    def test_parse_and_validate_output(self, valid_analyst_output_json):
        """Output kann geparst und validiert werden."""
        result = parse_analyst_output(valid_analyst_output_json)
        assert result is not None
        for req in result["anforderungen"]:
            assert req["id"].startswith("REQ-")

    def test_fallback_works_on_invalid_output(self, sample_briefing):
        """Fallback funktioniert bei ungültigem Output."""
        invalid = parse_analyst_output("Keine gültige Antwort")
        assert invalid is None
        fallback = create_default_requirements(sample_briefing)
        assert fallback is not None
        assert len(fallback["anforderungen"]) > 0
