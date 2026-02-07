# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 07.02.2026
Version: 1.0
Beschreibung: Unit-Tests fuer backend/user_story_helpers.py.
              Testet Parsing, Validierung, Fallback-Generierung und Formatierung
              von User Stories (GEGEBEN-WENN-DANN).

              AENDERUNG 07.02.2026: Initiale Erstellung (Dart Task zE40HTp29XJn)
"""

import pytest
from backend.user_story_helpers import (
    parse_user_stories,
    assign_user_story_ids,
    create_default_user_stories,
    validate_user_stories,
    build_user_story_traceability,
    format_user_story_text,
    US_REQUIRED_FIELDS,
)


# =========================================================================
# Test: parse_user_stories
# =========================================================================

class TestParseUserStories:
    """Tests fuer parse_user_stories()."""

    def test_gueltige_stories(self):
        """Gueltige User Stories werden korrekt extrahiert."""
        output = {
            "features": [{"id": "FEAT-001"}],
            "user_stories": [
                {
                    "id": "US-001",
                    "feature_id": "FEAT-001",
                    "titel": "Login",
                    "gegeben": "Benutzer auf Login-Seite",
                    "wenn": "Credentials eingegeben",
                    "dann": "Weiterleitung zum Dashboard",
                }
            ],
        }
        result = parse_user_stories(output)
        assert len(result) == 1
        assert result[0]["id"] == "US-001"

    def test_leerer_output(self):
        """Leerer Output gibt leere Liste zurueck."""
        assert parse_user_stories({}) == []
        assert parse_user_stories(None) == []

    def test_keine_liste(self):
        """Nicht-Liste user_stories wird ignoriert."""
        output = {"user_stories": "invalid"}
        result = parse_user_stories(output)
        assert result == []

    def test_fehlende_ids_werden_zugewiesen(self):
        """Stories ohne ID bekommen automatisch US-001, US-002, ..."""
        output = {
            "user_stories": [
                {"feature_id": "FEAT-001", "titel": "Story A",
                 "gegeben": "A", "wenn": "B", "dann": "C"},
                {"feature_id": "FEAT-002", "titel": "Story B",
                 "gegeben": "D", "wenn": "E", "dann": "F"},
            ]
        }
        result = parse_user_stories(output)
        assert result[0]["id"] == "US-001"
        assert result[1]["id"] == "US-002"


# =========================================================================
# Test: assign_user_story_ids
# =========================================================================

class TestAssignUserStoryIds:
    """Tests fuer assign_user_story_ids()."""

    def test_ids_zuweisen(self):
        """Fehlende IDs werden fortlaufend zugewiesen."""
        stories = [
            {"titel": "A"},
            {"id": "US-005", "titel": "B"},
            {"titel": "C"},
        ]
        result = assign_user_story_ids(stories)
        assert result[0]["id"] == "US-001"
        assert result[1]["id"] == "US-005"  # Existierende bleibt
        assert result[2]["id"] == "US-003"

    def test_leere_liste(self):
        """Leere Liste gibt leere Liste zurueck."""
        assert assign_user_story_ids([]) == []

    def test_alle_ids_vorhanden(self):
        """Wenn alle IDs vorhanden sind, keine Aenderung."""
        stories = [{"id": "US-001"}, {"id": "US-002"}]
        result = assign_user_story_ids(stories)
        assert result[0]["id"] == "US-001"
        assert result[1]["id"] == "US-002"


# =========================================================================
# Test: create_default_user_stories
# =========================================================================

class TestCreateDefaultUserStories:
    """Tests fuer create_default_user_stories()."""

    def test_ein_feature_eine_story(self):
        """1 Feature ergibt 1 Standard-User-Story."""
        features = [
            {"id": "FEAT-001", "titel": "Login-Formular", "beschreibung": "Auth mit Email"}
        ]
        result = create_default_user_stories(features)
        assert len(result) == 1
        assert result[0]["id"] == "US-001"
        assert result[0]["feature_id"] == "FEAT-001"
        assert "Login-Formular" in result[0]["titel"]
        assert result[0]["gegeben"]  # Nicht leer
        assert result[0]["wenn"]  # Nicht leer
        assert result[0]["dann"]  # Nicht leer
        assert len(result[0]["akzeptanzkriterien"]) >= 1

    def test_drei_features_drei_stories(self):
        """3 Features ergeben 3 Standard-User-Stories."""
        features = [
            {"id": f"FEAT-{i:03d}", "titel": f"Feature {i}"} for i in range(1, 4)
        ]
        result = create_default_user_stories(features)
        assert len(result) == 3
        assert result[0]["id"] == "US-001"
        assert result[1]["id"] == "US-002"
        assert result[2]["id"] == "US-003"

    def test_fallback_source_marker(self):
        """Default-Stories haben 'default_fallback' als Source."""
        features = [{"id": "FEAT-001", "titel": "Test"}]
        result = create_default_user_stories(features)
        assert result[0].get("source") == "default_fallback"

    def test_leere_features(self):
        """Leere Feature-Liste ergibt leere Story-Liste."""
        assert create_default_user_stories([]) == []


# =========================================================================
# Test: validate_user_stories
# =========================================================================

class TestValidateUserStories:
    """Tests fuer validate_user_stories()."""

    def _make_valid_story(self, us_id="US-001", feat_id="FEAT-001"):
        return {
            "id": us_id,
            "feature_id": feat_id,
            "titel": "Testgeschichte",
            "gegeben": "Benutzer ist angemeldet",
            "wenn": "Er den Button klickt",
            "dann": "Wird die Aktion ausgefuehrt",
            "akzeptanzkriterien": ["Funktioniert korrekt"],
        }

    def test_gueltige_stories(self):
        """Valide Stories ergeben valid=True und coverage=1.0."""
        features = [{"id": "FEAT-001"}]
        stories = [self._make_valid_story()]
        result = validate_user_stories(features, stories)
        assert result["valid"] is True
        assert result["coverage"] == 1.0
        assert len(result["errors"]) == 0

    def test_fehlende_pflichtfelder(self):
        """Fehlende Pflichtfelder ergeben Errors."""
        features = [{"id": "FEAT-001"}]
        stories = [{"id": "US-001"}]  # Alles ausser id fehlt
        result = validate_user_stories(features, stories)
        assert result["valid"] is False
        assert len(result["errors"]) > 0

    def test_doppelte_ids(self):
        """Doppelte US-IDs werden als Error erkannt."""
        features = [{"id": "FEAT-001"}]
        stories = [
            self._make_valid_story("US-001", "FEAT-001"),
            self._make_valid_story("US-001", "FEAT-001"),
        ]
        result = validate_user_stories(features, stories)
        assert result["valid"] is False
        assert any("Doppelte" in e for e in result["errors"])

    def test_unbekanntes_feature(self):
        """Referenz auf unbekanntes Feature ergibt Warning."""
        features = [{"id": "FEAT-001"}]
        stories = [self._make_valid_story("US-001", "FEAT-999")]
        result = validate_user_stories(features, stories)
        assert len(result["warnings"]) > 0
        assert any("FEAT-999" in w for w in result["warnings"])

    def test_feature_ohne_story(self):
        """Feature ohne User Story ergibt Warning."""
        features = [{"id": "FEAT-001"}, {"id": "FEAT-002"}]
        stories = [self._make_valid_story("US-001", "FEAT-001")]
        result = validate_user_stories(features, stories)
        assert "FEAT-002" in result["uncovered_features"]
        assert result["coverage"] == 0.5

    def test_kurze_gegeben_wenn_dann(self):
        """Zu kurze GEGEBEN/WENN/DANN Werte ergeben Warnings."""
        features = [{"id": "FEAT-001"}]
        stories = [{
            "id": "US-001",
            "feature_id": "FEAT-001",
            "titel": "Test",
            "gegeben": "Ab",
            "wenn": "Cd",
            "dann": "Ef",
            "akzeptanzkriterien": ["OK"],
        }]
        result = validate_user_stories(features, stories)
        assert any("zu kurz" in w for w in result["warnings"])

    def test_keine_akzeptanzkriterien(self):
        """Fehlende Akzeptanzkriterien ergeben Warning."""
        features = [{"id": "FEAT-001"}]
        story = self._make_valid_story()
        story["akzeptanzkriterien"] = []
        result = validate_user_stories(features, [story])
        assert any("Akzeptanzkriterien" in w for w in result["warnings"])


# =========================================================================
# Test: build_user_story_traceability
# =========================================================================

class TestBuildUserStoryTraceability:
    """Tests fuer build_user_story_traceability()."""

    def test_mapping(self):
        """FEAT-ID wird korrekt auf US-IDs gemappt."""
        stories = [
            {"id": "US-001", "feature_id": "FEAT-001"},
            {"id": "US-002", "feature_id": "FEAT-001"},
            {"id": "US-003", "feature_id": "FEAT-002"},
        ]
        result = build_user_story_traceability(stories)
        assert result["FEAT-001"] == ["US-001", "US-002"]
        assert result["FEAT-002"] == ["US-003"]

    def test_leere_liste(self):
        """Leere Story-Liste ergibt leeres Mapping."""
        assert build_user_story_traceability([]) == {}

    def test_keine_duplikate(self):
        """Gleiche US-ID erscheint nicht doppelt pro Feature."""
        stories = [
            {"id": "US-001", "feature_id": "FEAT-001"},
            {"id": "US-001", "feature_id": "FEAT-001"},
        ]
        result = build_user_story_traceability(stories)
        assert len(result["FEAT-001"]) == 1


# =========================================================================
# Test: format_user_story_text
# =========================================================================

class TestFormatUserStoryText:
    """Tests fuer format_user_story_text()."""

    def test_vollstaendige_formatierung(self):
        """Alle Felder werden korrekt formatiert."""
        story = {
            "id": "US-001",
            "feature_id": "FEAT-001",
            "titel": "Login-Test",
            "gegeben": "Benutzer auf Login-Seite",
            "wenn": "Credentials eingeben",
            "dann": "Weiterleitung zum Dashboard",
            "akzeptanzkriterien": ["Fehler bei falschem Passwort"],
        }
        text = format_user_story_text(story)
        assert "[US-001]" in text
        assert "Login-Test" in text
        assert "GEGEBEN:" in text
        assert "WENN:" in text
        assert "DANN:" in text
        assert "AKZEPTANZKRITERIEN:" in text
        assert "Fehler bei falschem Passwort" in text

    def test_ohne_akzeptanzkriterien(self):
        """Story ohne Akzeptanzkriterien hat kein AK-Abschnitt."""
        story = {
            "id": "US-002",
            "feature_id": "FEAT-001",
            "titel": "Test",
            "gegeben": "A",
            "wenn": "B",
            "dann": "C",
        }
        text = format_user_story_text(story)
        assert "AKZEPTANZKRITERIEN" not in text

    def test_fehlende_felder_fallback(self):
        """Fehlende Felder zeigen '???' als Fallback."""
        text = format_user_story_text({})
        assert "US-???" in text
        assert "???" in text
