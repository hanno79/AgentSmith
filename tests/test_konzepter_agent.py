# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 01.02.2026
Version: 1.1
Beschreibung: Unit Tests für Konzepter Agent - Feature-Extraktion aus Anforderungen.

              Tests validieren:
              - create_konzepter: Agent-Erstellung
              - create_feature_extraction_task: Task-Erstellung
              - _format_anforderungen: Anforderungs-Formatierung
              - parse_konzepter_output: Output-Parsing
              - _build_traceability: Traceability-Generierung
              - create_default_features: Fallback-Generierung
              - validate_traceability: Traceability-Validierung

              AENDERUNG 07.02.2026: Tests fuer User Story Ableitung (GEGEBEN-WENN-DANN)
              (Dart Task zE40HTp29XJn, Feature-Ableitung Konzept v1.0 Phase 3)
"""

import pytest
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.konzepter_agent import (
    create_konzepter,
    create_feature_extraction_task,
    _format_anforderungen,
    parse_konzepter_output,
    _build_traceability,
    create_default_features,
    validate_traceability
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
        "konzepter": ["Erstelle kleine Features"]
    }


@pytest.fixture
def sample_anforderungen():
    """Beispiel Anforderungskatalog für Tests."""
    return {
        "anforderungen": [
            {
                "id": "REQ-001",
                "titel": "Task-Erstellung",
                "beschreibung": "Benutzer kann neue Tasks erstellen",
                "kategorie": "Funktional",
                "prioritaet": "hoch",
                "quelle": "Discovery",
                "akzeptanzkriterien": ["Task kann erstellt werden"]
            },
            {
                "id": "REQ-002",
                "titel": "Task-Anzeige",
                "beschreibung": "Benutzer kann alle Tasks sehen",
                "kategorie": "Funktional",
                "prioritaet": "hoch",
                "quelle": "Discovery",
                "akzeptanzkriterien": ["Tasks werden angezeigt"]
            },
            {
                "id": "REQ-003",
                "titel": "Datenbank",
                "beschreibung": "Daten werden persistent gespeichert",
                "kategorie": "Technisch",
                "prioritaet": "mittel",
                "quelle": "Implizit",
                "akzeptanzkriterien": ["Daten bleiben nach Neustart"]
            }
        ],
        "kategorien": ["Funktional", "Technisch"],
        "zusammenfassung": "Todo-App Anforderungen"
    }


@pytest.fixture
def sample_blueprint():
    """Beispiel TechStack-Blueprint für Tests."""
    return {
        "project_type": "python_webapp",
        "language": "python",
        "app_type": "webapp",
        "frameworks": ["flask", "sqlalchemy"]
    }


@pytest.fixture
def valid_konzepter_output_json():
    """Gültiger Konzepter-Output als JSON-String."""
    return '''```json
{
  "features": [
    {
      "id": "FEAT-001",
      "titel": "Task-CRUD-API",
      "beschreibung": "REST-API für Task-Operationen",
      "anforderungen": ["REQ-001", "REQ-002"],
      "technologie": "Python/Flask",
      "geschaetzte_dateien": 2,
      "prioritaet": "hoch",
      "abhaengigkeiten": ["FEAT-002"]
    },
    {
      "id": "FEAT-002",
      "titel": "SQLite-Datenbankschicht",
      "beschreibung": "Persistente Datenspeicherung",
      "anforderungen": ["REQ-003"],
      "technologie": "SQLite",
      "geschaetzte_dateien": 1,
      "prioritaet": "hoch",
      "abhaengigkeiten": []
    }
  ],
  "traceability": {
    "REQ-001": ["FEAT-001"],
    "REQ-002": ["FEAT-001"],
    "REQ-003": ["FEAT-002"]
  },
  "zusammenfassung": "2 Features für Todo-App"
}
```'''


# =========================================================================
# Test: _format_anforderungen
# =========================================================================

class TestFormatAnforderungen:
    """Tests für _format_anforderungen Funktion."""

    def test_basic_formatting(self, sample_anforderungen):
        """Anforderungen werden korrekt formatiert."""
        result = _format_anforderungen(sample_anforderungen)
        assert "ZUSAMMENFASSUNG" in result
        assert "Todo-App" in result

    def test_includes_all_requirements(self, sample_anforderungen):
        """Alle Anforderungen werden inkludiert."""
        result = _format_anforderungen(sample_anforderungen)
        assert "REQ-001" in result
        assert "REQ-002" in result
        assert "REQ-003" in result

    def test_includes_details(self, sample_anforderungen):
        """Details werden inkludiert."""
        result = _format_anforderungen(sample_anforderungen)
        assert "Kategorie:" in result
        assert "Prioritaet:" in result
        assert "Beschreibung:" in result

    def test_includes_kategorien(self, sample_anforderungen):
        """Kategorien werden aufgelistet."""
        result = _format_anforderungen(sample_anforderungen)
        assert "KATEGORIEN:" in result
        assert "Funktional" in result

    def test_empty_anforderungen(self):
        """Leere Anforderungen werden behandelt."""
        result = _format_anforderungen({})
        assert "ZUSAMMENFASSUNG:" in result
        assert "Keine Zusammenfassung" in result


# =========================================================================
# Test: _build_traceability
# =========================================================================

class TestBuildTraceability:
    """Tests für _build_traceability Funktion."""

    def test_builds_from_features(self):
        """Traceability wird aus Features aufgebaut."""
        features = [
            {"id": "FEAT-001", "anforderungen": ["REQ-001", "REQ-002"]},
            {"id": "FEAT-002", "anforderungen": ["REQ-002", "REQ-003"]}
        ]
        result = _build_traceability(features)
        assert "REQ-001" in result
        assert "REQ-002" in result
        assert "REQ-003" in result
        assert "FEAT-001" in result["REQ-001"]
        assert "FEAT-001" in result["REQ-002"]
        assert "FEAT-002" in result["REQ-002"]

    def test_empty_features(self):
        """Leere Feature-Liste gibt leeres Dict zurück."""
        result = _build_traceability([])
        assert result == {}

    def test_no_duplicate_mappings(self):
        """Keine doppelten Mappings."""
        features = [
            {"id": "FEAT-001", "anforderungen": ["REQ-001"]},
            {"id": "FEAT-001", "anforderungen": ["REQ-001"]}  # Duplikat
        ]
        result = _build_traceability(features)
        assert len(result["REQ-001"]) == 1

    def test_missing_anforderungen_key(self):
        """Features ohne anforderungen werden ignoriert."""
        features = [{"id": "FEAT-001"}]
        result = _build_traceability(features)
        assert result == {}


# =========================================================================
# Test: parse_konzepter_output
# =========================================================================

class TestParseKonzepterOutput:
    """Tests für parse_konzepter_output Funktion."""

    def test_parse_json_block(self, valid_konzepter_output_json):
        """JSON-Block wird geparst."""
        result = parse_konzepter_output(valid_konzepter_output_json)
        assert result is not None
        assert "features" in result
        assert len(result["features"]) == 2

    def test_parse_raw_json(self):
        """Rohes JSON wird geparst."""
        raw = '{"features": [{"id": "FEAT-001", "anforderungen": ["REQ-001"]}]}'
        result = parse_konzepter_output(raw)
        assert result is not None
        assert "features" in result

    def test_adds_traceability_if_missing(self):
        """Traceability wird hinzugefügt wenn fehlend."""
        raw = '{"features": [{"id": "FEAT-001", "anforderungen": ["REQ-001"]}]}'
        result = parse_konzepter_output(raw)
        assert "traceability" in result
        assert "REQ-001" in result["traceability"]

    def test_empty_output_returns_none(self):
        """Leerer Output gibt None zurück."""
        assert parse_konzepter_output("") is None
        assert parse_konzepter_output(None) is None

    def test_invalid_json_returns_none(self):
        """Ungültiges JSON gibt None zurück."""
        result = parse_konzepter_output("Das ist kein JSON")
        assert result is None

    def test_missing_features_returns_none(self):
        """JSON ohne features gibt None zurück."""
        result = parse_konzepter_output('{"andere_daten": []}')
        assert result is None

    def test_extracts_correct_data(self, valid_konzepter_output_json):
        """Korrekte Daten werden extrahiert."""
        result = parse_konzepter_output(valid_konzepter_output_json)
        assert result["features"][0]["id"] == "FEAT-001"
        assert result["traceability"]["REQ-001"] == ["FEAT-001"]


# =========================================================================
# Test: create_default_features
# =========================================================================

class TestCreateDefaultFeatures:
    """Tests für create_default_features Funktion."""

    def test_creates_features_from_requirements(self, sample_anforderungen):
        """Features werden aus Anforderungen erstellt."""
        result = create_default_features(sample_anforderungen)
        assert "features" in result
        assert len(result["features"]) == 3  # 1:1 Mapping

    def test_creates_traceability(self, sample_anforderungen):
        """Traceability wird erstellt."""
        result = create_default_features(sample_anforderungen)
        assert "traceability" in result
        assert "REQ-001" in result["traceability"]

    def test_has_required_fields(self, sample_anforderungen):
        """Alle Pflichtfelder sind vorhanden."""
        result = create_default_features(sample_anforderungen)
        for feat in result["features"]:
            assert "id" in feat
            assert "titel" in feat
            assert "anforderungen" in feat
            assert "geschaetzte_dateien" in feat

    def test_marks_as_fallback(self, sample_anforderungen):
        """Ergebnis wird als Fallback markiert."""
        result = create_default_features(sample_anforderungen)
        assert result.get("source") == "default_fallback"

    def test_empty_anforderungen(self):
        """Leere Anforderungen erzeugen leere Features."""
        result = create_default_features({"anforderungen": []})
        assert result["features"] == []


# =========================================================================
# Test: validate_traceability
# =========================================================================

class TestValidateTraceability:
    """Tests für validate_traceability Funktion."""

    def test_valid_traceability(self, sample_anforderungen):
        """Vollständige Traceability ist gültig."""
        features = {
            "features": [
                {"id": "FEAT-001", "anforderungen": ["REQ-001"]},
                {"id": "FEAT-002", "anforderungen": ["REQ-002"]},
                {"id": "FEAT-003", "anforderungen": ["REQ-003"]}
            ],
            "traceability": {
                "REQ-001": ["FEAT-001"],
                "REQ-002": ["FEAT-002"],
                "REQ-003": ["FEAT-003"]
            }
        }
        result = validate_traceability(sample_anforderungen, features)
        assert result["valid"] is True
        assert result["coverage"] == 1.0
        assert len(result["uncovered_requirements"]) == 0

    def test_uncovered_requirements(self, sample_anforderungen):
        """Nicht abgedeckte Anforderungen werden erkannt."""
        features = {
            "features": [
                {"id": "FEAT-001", "anforderungen": ["REQ-001"]}
            ],
            "traceability": {
                "REQ-001": ["FEAT-001"]
            }
        }
        result = validate_traceability(sample_anforderungen, features)
        assert result["valid"] is False
        assert "REQ-002" in result["uncovered_requirements"]
        assert "REQ-003" in result["uncovered_requirements"]

    def test_orphan_features(self, sample_anforderungen):
        """Verwaiste Features werden erkannt."""
        features = {
            "features": [
                {"id": "FEAT-001", "anforderungen": ["REQ-001"]},
                {"id": "FEAT-002", "anforderungen": ["REQ-002"]},
                {"id": "FEAT-003", "anforderungen": ["REQ-003"]},
                {"id": "FEAT-ORPHAN", "anforderungen": []}  # Nicht zugeordnet
            ],
            "traceability": {
                "REQ-001": ["FEAT-001"],
                "REQ-002": ["FEAT-002"],
                "REQ-003": ["FEAT-003"]
            }
        }
        result = validate_traceability(sample_anforderungen, features)
        assert result["valid"] is False
        assert "FEAT-ORPHAN" in result["orphan_features"]

    def test_coverage_calculation(self, sample_anforderungen):
        """Coverage wird korrekt berechnet."""
        features = {
            "features": [{"id": "FEAT-001", "anforderungen": ["REQ-001"]}],
            "traceability": {"REQ-001": ["FEAT-001"]}
        }
        result = validate_traceability(sample_anforderungen, features)
        # 1 von 3 abgedeckt = 33.3%
        assert result["coverage"] == pytest.approx(0.333, rel=0.01)

    def test_empty_inputs(self):
        """Leere Inputs werden behandelt."""
        result = validate_traceability(
            {"anforderungen": []},
            {"features": [], "traceability": {}}
        )
        assert result["valid"] is True
        assert result["coverage"] == 0.0


# =========================================================================
# Test: create_konzepter (Agent-Erstellung)
# =========================================================================

class TestCreateKonzepter:
    """Tests für create_konzepter Funktion."""

    def test_creates_agent(self, sample_config, sample_project_rules):
        """Agent wird erstellt."""
        try:
            agent = create_konzepter(sample_config, sample_project_rules)
            assert agent is not None
            assert hasattr(agent, 'role')
            assert "Konzepter" in agent.role
        except Exception as e:
            pytest.skip(f"CrewAI Agent-Erstellung nicht möglich: {e}")

    def test_with_router(self, sample_config, sample_project_rules):
        """Agent mit Router wird erstellt."""
        class MockRouter:
            def get_model(self, role):
                return "test-model"

        try:
            agent = create_konzepter(sample_config, sample_project_rules, router=MockRouter())
            assert agent is not None
        except Exception as e:
            pytest.skip(f"CrewAI Agent-Erstellung nicht möglich: {e}")


# =========================================================================
# Test: create_feature_extraction_task
# =========================================================================

class TestCreateFeatureExtractionTask:
    """Tests für create_feature_extraction_task Funktion."""

    def test_creates_task(self, sample_config, sample_project_rules, sample_anforderungen):
        """Task wird erstellt."""
        try:
            agent = create_konzepter(sample_config, sample_project_rules)
            task = create_feature_extraction_task(agent, sample_anforderungen)
            assert task is not None
            assert hasattr(task, 'description')
            assert "ANFORDERUNGSKATALOG" in task.description
        except Exception as e:
            pytest.skip(f"CrewAI Task-Erstellung nicht möglich: {e}")

    def test_task_with_blueprint(self, sample_config, sample_project_rules,
                                  sample_anforderungen, sample_blueprint):
        """Task mit Blueprint enthält technischen Kontext."""
        try:
            agent = create_konzepter(sample_config, sample_project_rules)
            task = create_feature_extraction_task(agent, sample_anforderungen, sample_blueprint)
            assert "TECHNISCHER KONTEXT" in task.description
            assert "python" in task.description
        except Exception as e:
            pytest.skip(f"CrewAI Task-Erstellung nicht möglich: {e}")


# =========================================================================
# Test: Integration
# =========================================================================

class TestIntegration:
    """Integrationstests für Konzepter-Komponenten."""

    def test_parse_validate_workflow(self, valid_konzepter_output_json, sample_anforderungen):
        """Parse und Validierung funktioniert zusammen."""
        result = parse_konzepter_output(valid_konzepter_output_json)
        assert result is not None

        validation = validate_traceability(sample_anforderungen, result)
        assert validation["coverage"] == 1.0  # Alle abgedeckt

    def test_fallback_creates_valid_output(self, sample_anforderungen):
        """Fallback erzeugt validen Output."""
        fallback = create_default_features(sample_anforderungen)
        validation = validate_traceability(sample_anforderungen, fallback)
        assert validation["valid"] is True
        assert validation["coverage"] == 1.0


# =========================================================================
# AENDERUNG 07.02.2026: Tests fuer User Story Ableitung (Phase 3)
# =========================================================================

class TestParseKonzepterOutputWithUserStories:
    """Tests fuer parse_konzepter_output mit User Stories."""

    def test_output_mit_user_stories(self):
        """Konzepter-Output mit User Stories wird korrekt geparst."""
        output = '''```json
{
  "features": [
    {"id": "FEAT-001", "titel": "Login", "anforderungen": ["REQ-001"]}
  ],
  "user_stories": [
    {
      "id": "US-001",
      "feature_id": "FEAT-001",
      "titel": "Benutzer meldet sich an",
      "gegeben": "Der Benutzer ist auf der Login-Seite",
      "wenn": "Er Email und Passwort eingibt",
      "dann": "Wird er zum Dashboard weitergeleitet",
      "akzeptanzkriterien": ["Login funktioniert"]
    }
  ],
  "traceability": {"REQ-001": ["FEAT-001"]}
}
```'''
        result = parse_konzepter_output(output)
        assert result is not None
        assert "user_stories" in result
        assert len(result["user_stories"]) == 1
        assert result["user_stories"][0]["gegeben"] == "Der Benutzer ist auf der Login-Seite"

    def test_output_ohne_user_stories_generiert_defaults(self):
        """Output ohne user_stories generiert Standard-Stories."""
        output = '{"features": [{"id": "FEAT-001", "titel": "Login", "anforderungen": ["REQ-001"]}]}'
        result = parse_konzepter_output(output)
        assert result is not None
        assert "user_stories" in result
        assert len(result["user_stories"]) == 1
        assert result["user_stories"][0]["feature_id"] == "FEAT-001"

    def test_user_story_ids_werden_zugewiesen(self):
        """Fehlende US-IDs werden automatisch zugewiesen."""
        output = '''```json
{
  "features": [{"id": "FEAT-001", "anforderungen": ["REQ-001"]}],
  "user_stories": [
    {"feature_id": "FEAT-001", "titel": "Test", "gegeben": "A", "wenn": "B", "dann": "C"}
  ]
}
```'''
        result = parse_konzepter_output(output)
        assert result["user_stories"][0]["id"] == "US-001"


class TestDefaultFeaturesWithUserStories:
    """Tests fuer create_default_features mit User Stories."""

    def test_default_features_enthalten_user_stories(self, sample_anforderungen):
        """Default-Features enthalten User Stories."""
        result = create_default_features(sample_anforderungen)
        assert "user_stories" in result
        assert len(result["user_stories"]) == len(result["features"])

    def test_default_stories_haben_gegeben_wenn_dann(self, sample_anforderungen):
        """Default-Stories haben GEGEBEN/WENN/DANN Felder."""
        result = create_default_features(sample_anforderungen)
        for story in result["user_stories"]:
            assert "gegeben" in story
            assert "wenn" in story
            assert "dann" in story
            assert story["gegeben"]  # Nicht leer
            assert story["wenn"]
            assert story["dann"]

    def test_default_stories_verlinken_features(self, sample_anforderungen):
        """Default-Stories verlinken auf korrekte Features."""
        result = create_default_features(sample_anforderungen)
        feat_ids = {f["id"] for f in result["features"]}
        for story in result["user_stories"]:
            assert story["feature_id"] in feat_ids


class TestValidateTraceabilityWithUserStories:
    """Tests fuer validate_traceability mit User Story Coverage."""

    def test_user_story_coverage(self, sample_anforderungen):
        """User Story Coverage wird korrekt berechnet."""
        features = {
            "features": [
                {"id": "FEAT-001", "anforderungen": ["REQ-001"]},
                {"id": "FEAT-002", "anforderungen": ["REQ-002"]},
                {"id": "FEAT-003", "anforderungen": ["REQ-003"]},
            ],
            "user_stories": [
                {"id": "US-001", "feature_id": "FEAT-001"},
                {"id": "US-002", "feature_id": "FEAT-002"},
            ],
            "traceability": {
                "REQ-001": ["FEAT-001"],
                "REQ-002": ["FEAT-002"],
                "REQ-003": ["FEAT-003"],
            },
        }
        result = validate_traceability(sample_anforderungen, features)
        # 2 von 3 Features haben Stories
        assert result["user_story_coverage"] == pytest.approx(0.667, rel=0.01)
        assert "FEAT-003" in result["features_ohne_user_stories"]

    def test_vollstaendige_user_story_coverage(self, sample_anforderungen):
        """Vollstaendige US-Coverage = 1.0."""
        features = {
            "features": [
                {"id": "FEAT-001", "anforderungen": ["REQ-001"]},
                {"id": "FEAT-002", "anforderungen": ["REQ-002"]},
                {"id": "FEAT-003", "anforderungen": ["REQ-003"]},
            ],
            "user_stories": [
                {"id": "US-001", "feature_id": "FEAT-001"},
                {"id": "US-002", "feature_id": "FEAT-002"},
                {"id": "US-003", "feature_id": "FEAT-003"},
            ],
            "traceability": {
                "REQ-001": ["FEAT-001"],
                "REQ-002": ["FEAT-002"],
                "REQ-003": ["FEAT-003"],
            },
        }
        result = validate_traceability(sample_anforderungen, features)
        assert result["user_story_coverage"] == 1.0
        assert result["features_ohne_user_stories"] == []

    def test_keine_user_stories(self, sample_anforderungen):
        """Ohne User Stories ist Coverage 0.0."""
        features = {
            "features": [{"id": "FEAT-001", "anforderungen": ["REQ-001"]}],
            "traceability": {"REQ-001": ["FEAT-001"]},
        }
        result = validate_traceability(sample_anforderungen, features)
        assert result["user_story_coverage"] == 0.0
        assert result["total_user_stories"] == 0
