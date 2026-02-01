# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 01.02.2026
Version: 1.1
Beschreibung: Memory Agent Type-Definitionen.
              Extrahiert aus memory_agent.py (Regel 1: Max 500 Zeilen)

              ÄNDERUNG 01.02.2026 v1.1: DataSource und DomainTerm hinzugefügt
"""

from typing import List, Optional, TypedDict


class MemoryEntry(TypedDict):
    """Typdefinition für einen Memory-Eintrag."""
    timestamp: str
    coder_output_preview: str
    review_feedback: Optional[str]
    sandbox_feedback: Optional[str]


class Lesson(TypedDict, total=False):
    """Typdefinition für eine Lesson."""
    pattern: str
    category: str
    action: str
    tags: List[str]
    count: int
    first_seen: str
    last_seen: str


class DataSource(TypedDict):
    """
    Typdefinition für eine bekannte Datenquelle.

    ÄNDERUNG 01.02.2026: Neu hinzugefügt für Known Data Sources.
    """
    name: str
    type: str  # "api", "database", "file", "service"
    url: Optional[str]
    auth_method: str  # "none", "api_key", "oauth", "basic"
    documentation_url: Optional[str]
    last_accessed: str
    reliability_score: float  # 0.0 - 1.0


class DomainTerm(TypedDict):
    """
    Typdefinition für einen Fachbegriff (Domain Vocabulary).

    ÄNDERUNG 01.02.2026: Neu hinzugefügt für Domain Vocabulary.
    """
    term: str
    definition: str
    category: str  # "entity", "concept", "relationship"
    aliases: List[str]
    domain: str  # z.B. "fintech", "healthcare", "agile"
    first_seen: str
    usage_count: int


class MemoryData(TypedDict, total=False):
    """
    Typdefinition für Memory-Daten.

    ÄNDERUNG 01.02.2026: Erweitert um known_data_sources und domain_vocabulary.
    """
    history: List[MemoryEntry]
    lessons: List[Lesson]
    known_data_sources: List[DataSource]
    domain_vocabulary: List[DomainTerm]
