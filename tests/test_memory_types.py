# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 14.02.2026
Version: 1.0
Beschreibung: Unit Tests fuer agents/memory_types.py - MemoryEntry, Lesson,
              DataSource, DomainTerm und MemoryData TypedDicts.
"""

import os
import sys
import pytest

# Projekt-Root zum Python-Path hinzufuegen
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.memory_types import (
    MemoryEntry,
    Lesson,
    DataSource,
    DomainTerm,
    MemoryData,
)


# =========================================================================
# Tests fuer MemoryEntry TypedDict
# =========================================================================
class TestMemoryEntry:
    """Tests fuer die MemoryEntry Typdefinition."""

    def test_gueltige_instanz(self):
        """MemoryEntry kann mit allen Feldern erstellt werden."""
        entry: MemoryEntry = {
            "timestamp": "2026-02-14 10:00:00",
            "coder_output_preview": "def hello(): print('Hello')",
            "review_feedback": "Code ist gut",
            "sandbox_feedback": "Python-Syntax OK"
        }
        assert entry["timestamp"] == "2026-02-14 10:00:00"
        assert entry["coder_output_preview"] == "def hello(): print('Hello')"
        assert entry["review_feedback"] == "Code ist gut"
        assert entry["sandbox_feedback"] == "Python-Syntax OK"

    def test_optionale_felder_none(self):
        """review_feedback und sandbox_feedback koennen None sein."""
        entry: MemoryEntry = {
            "timestamp": "2026-02-14 10:00:00",
            "coder_output_preview": "code...",
            "review_feedback": None,
            "sandbox_feedback": None
        }
        assert entry["review_feedback"] is None
        assert entry["sandbox_feedback"] is None

    def test_ist_dict_kompatibel(self):
        """MemoryEntry ist dict-kompatibel (TypedDict)."""
        entry: MemoryEntry = {
            "timestamp": "t", "coder_output_preview": "c",
            "review_feedback": None, "sandbox_feedback": None
        }
        assert isinstance(entry, dict)

    def test_erwartete_keys(self):
        """MemoryEntry hat die erwarteten Annotations."""
        erwartete = {"timestamp", "coder_output_preview", "review_feedback", "sandbox_feedback"}
        assert set(MemoryEntry.__annotations__.keys()) == erwartete

    def test_langer_coder_output(self):
        """Langer Coder-Output wird gespeichert."""
        langer_code = "x = 1\n" * 100
        entry: MemoryEntry = {
            "timestamp": "t", "coder_output_preview": langer_code,
            "review_feedback": None, "sandbox_feedback": None
        }
        assert len(entry["coder_output_preview"]) > 500


# =========================================================================
# Tests fuer Lesson TypedDict (total=False)
# =========================================================================
class TestLesson:
    """Tests fuer die Lesson Typdefinition."""

    def test_gueltige_instanz_alle_felder(self):
        """Lesson mit allen Feldern."""
        lesson: Lesson = {
            "pattern": "ModuleNotFoundError",
            "category": "error",
            "action": "VERMEIDE FEHLER: Modul nicht gefunden",
            "tags": ["global", "python"],
            "count": 3,
            "first_seen": "2026-01-22 09:00:00",
            "last_seen": "2026-02-14 10:00:00"
        }
        assert lesson["pattern"] == "ModuleNotFoundError"
        assert lesson["category"] == "error"
        assert lesson["count"] == 3
        assert "python" in lesson["tags"]

    def test_total_false_erlaubt_partielle_erstellung(self):
        """Lesson hat total=False, partielle Instanzen sind moeglich."""
        # TypedDict(total=False) erlaubt fehlende Felder zur Laufzeit
        lesson: Lesson = {"pattern": "SyntaxError", "category": "error"}
        assert lesson["pattern"] == "SyntaxError"
        assert "count" not in lesson

    def test_tags_als_leere_liste(self):
        """Tags kann eine leere Liste sein."""
        lesson: Lesson = {
            "pattern": "p", "category": "c", "action": "a",
            "tags": [], "count": 0, "first_seen": "t", "last_seen": "t"
        }
        assert lesson["tags"] == []

    def test_count_startwert(self):
        """Count beginnt typischerweise bei 1."""
        lesson: Lesson = {"pattern": "p", "count": 1}
        assert lesson["count"] == 1

    def test_erwartete_annotations(self):
        """Lesson hat die erwarteten Annotations."""
        erwartete = {"pattern", "category", "action", "tags", "count", "first_seen", "last_seen"}
        assert set(Lesson.__annotations__.keys()) == erwartete


# =========================================================================
# Tests fuer DataSource TypedDict
# =========================================================================
class TestDataSource:
    """Tests fuer die DataSource Typdefinition."""

    def test_gueltige_api_quelle(self):
        """DataSource mit API-Typ."""
        ds: DataSource = {
            "name": "OpenWeather API",
            "type": "api",
            "url": "https://api.openweathermap.org",
            "auth_method": "api_key",
            "documentation_url": "https://openweathermap.org/api",
            "last_accessed": "2026-02-14",
            "reliability_score": 0.95
        }
        assert ds["name"] == "OpenWeather API"
        assert ds["type"] == "api"
        assert ds["auth_method"] == "api_key"
        assert ds["reliability_score"] == 0.95

    def test_database_typ(self):
        """DataSource mit Datenbank-Typ."""
        ds: DataSource = {
            "name": "Projekt-DB",
            "type": "database",
            "url": None,
            "auth_method": "basic",
            "documentation_url": None,
            "last_accessed": "2026-02-14",
            "reliability_score": 1.0
        }
        assert ds["type"] == "database"
        assert ds["url"] is None

    def test_auth_method_none(self):
        """auth_method 'none' fuer oeffentliche Quellen."""
        ds: DataSource = {
            "name": "Oeffentliche API",
            "type": "api",
            "url": "https://api.example.com",
            "auth_method": "none",
            "documentation_url": None,
            "last_accessed": "2026-02-14",
            "reliability_score": 0.5
        }
        assert ds["auth_method"] == "none"

    def test_reliability_score_grenzen(self):
        """reliability_score liegt zwischen 0.0 und 1.0."""
        ds_low: DataSource = {
            "name": "N", "type": "api", "url": None,
            "auth_method": "none", "documentation_url": None,
            "last_accessed": "t", "reliability_score": 0.0
        }
        ds_high: DataSource = {
            "name": "N", "type": "api", "url": None,
            "auth_method": "none", "documentation_url": None,
            "last_accessed": "t", "reliability_score": 1.0
        }
        assert ds_low["reliability_score"] == 0.0
        assert ds_high["reliability_score"] == 1.0

    def test_erwartete_annotations(self):
        """DataSource hat die erwarteten Annotations."""
        erwartete = {
            "name", "type", "url", "auth_method",
            "documentation_url", "last_accessed", "reliability_score"
        }
        assert set(DataSource.__annotations__.keys()) == erwartete

    def test_typ_varianten(self):
        """Verschiedene type-Werte (api, database, file, service)."""
        for typ in ["api", "database", "file", "service"]:
            ds: DataSource = {
                "name": "N", "type": typ, "url": None,
                "auth_method": "none", "documentation_url": None,
                "last_accessed": "t", "reliability_score": 0.5
            }
            assert ds["type"] == typ


# =========================================================================
# Tests fuer DomainTerm TypedDict
# =========================================================================
class TestDomainTerm:
    """Tests fuer die DomainTerm Typdefinition."""

    def test_gueltige_instanz(self):
        """DomainTerm mit allen Feldern."""
        term: DomainTerm = {
            "term": "Sprint",
            "definition": "Zeitlich begrenzter Entwicklungszyklus in Scrum",
            "category": "concept",
            "aliases": ["Iteration", "Zyklus"],
            "domain": "agile",
            "first_seen": "2026-01-15",
            "usage_count": 10
        }
        assert term["term"] == "Sprint"
        assert term["category"] == "concept"
        assert "Iteration" in term["aliases"]
        assert term["domain"] == "agile"
        assert term["usage_count"] == 10

    def test_entity_kategorie(self):
        """DomainTerm mit Kategorie 'entity'."""
        term: DomainTerm = {
            "term": "Benutzer",
            "definition": "Endanwender des Systems",
            "category": "entity",
            "aliases": ["User", "Nutzer"],
            "domain": "allgemein",
            "first_seen": "2026-02-14",
            "usage_count": 5
        }
        assert term["category"] == "entity"

    def test_relationship_kategorie(self):
        """DomainTerm mit Kategorie 'relationship'."""
        term: DomainTerm = {
            "term": "gehoert_zu",
            "definition": "Zuordnung zwischen Entitaeten",
            "category": "relationship",
            "aliases": [],
            "domain": "datenmodell",
            "first_seen": "2026-02-14",
            "usage_count": 1
        }
        assert term["category"] == "relationship"
        assert term["aliases"] == []

    def test_leere_aliases(self):
        """aliases kann eine leere Liste sein."""
        term: DomainTerm = {
            "term": "T", "definition": "D", "category": "concept",
            "aliases": [], "domain": "test", "first_seen": "t", "usage_count": 0
        }
        assert term["aliases"] == []

    def test_erwartete_annotations(self):
        """DomainTerm hat die erwarteten Annotations."""
        erwartete = {"term", "definition", "category", "aliases", "domain", "first_seen", "usage_count"}
        assert set(DomainTerm.__annotations__.keys()) == erwartete


# =========================================================================
# Tests fuer MemoryData TypedDict (total=False)
# =========================================================================
class TestMemoryData:
    """Tests fuer die MemoryData Typdefinition."""

    def test_volle_instanz(self):
        """MemoryData mit allen Feldern."""
        data: MemoryData = {
            "history": [
                {
                    "timestamp": "t",
                    "coder_output_preview": "c",
                    "review_feedback": None,
                    "sandbox_feedback": None
                }
            ],
            "lessons": [
                {"pattern": "p", "category": "error", "action": "a",
                 "tags": [], "count": 1, "first_seen": "t", "last_seen": "t"}
            ],
            "known_data_sources": [],
            "domain_vocabulary": []
        }
        assert len(data["history"]) == 1
        assert len(data["lessons"]) == 1
        assert data["known_data_sources"] == []
        assert data["domain_vocabulary"] == []

    def test_total_false_erlaubt_partielle_erstellung(self):
        """MemoryData hat total=False, partielle Instanzen sind moeglich."""
        data: MemoryData = {"history": [], "lessons": []}
        assert data["history"] == []
        assert "known_data_sources" not in data

    def test_leere_instanz(self):
        """Komplett leere MemoryData ist moeglich (total=False)."""
        data: MemoryData = {}
        assert isinstance(data, dict)

    def test_erwartete_annotations(self):
        """MemoryData hat die erwarteten Annotations."""
        erwartete = {"history", "lessons", "known_data_sources", "domain_vocabulary"}
        assert set(MemoryData.__annotations__.keys()) == erwartete

    def test_mit_conftest_sample_data(self, sample_memory_data):
        """MemoryData ist kompatibel mit sample_memory_data aus conftest.py."""
        # sample_memory_data aus conftest.py ist ein MemoryData-kompatibles Dict
        data: MemoryData = sample_memory_data
        assert len(data["history"]) > 0
        assert len(data["lessons"]) > 0
        assert "domain_vocabulary" in data
        assert "known_data_sources" in data

    def test_history_entry_struktur(self, sample_memory_data):
        """History-Eintraege haben die korrekte MemoryEntry-Struktur."""
        entry = sample_memory_data["history"][0]
        assert "timestamp" in entry
        assert "coder_output_preview" in entry
        assert "review_feedback" in entry
        assert "sandbox_feedback" in entry

    def test_lesson_entry_struktur(self, sample_memory_data):
        """Lesson-Eintraege haben die korrekte Lesson-Struktur."""
        lesson = sample_memory_data["lessons"][0]
        assert "pattern" in lesson
        assert "category" in lesson
        assert "action" in lesson
        assert "tags" in lesson
        assert "count" in lesson
