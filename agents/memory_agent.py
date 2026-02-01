# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 01.02.2026
Version: 1.4
Beschreibung: Memory Agent - Verwaltet Projekt- und Langzeiterinnerungen.
              Speichert Erkenntnisse aus Code-, Review- und Sandbox-Ergebnissen.

              AENDERUNG 01.02.2026 v1.4: DataSource und DomainTerm hinzugefügt
              - Known Data Sources für bekannte Datenquellen
              - Domain Vocabulary für Fachbegriffe

              AENDERUNG 01.02.2026 v1.3: Refaktoriert in Module (Regel 1: Max 500 Zeilen)
              - memory_types.py: TypedDefs
              - memory_encryption.py: Verschlüsselungs-Funktionen
              - memory_core.py: Load/Save Memory
              - memory_learning.py: Lern-Funktionen
              - memory_features.py: Feature-Derivation Recording

              ÄNDERUNG 29.01.2026: Async-Versionen für non-blocking I/O.
              AENDERUNG 31.01.2026: Dart AI Feature-Ableitung Memory-Funktionen.
"""

from typing import Any, Dict, List, Optional, Union
import re

# Type-Definitionen
from agents.memory_types import (
    MemoryEntry,
    Lesson,
    MemoryData,
    DataSource,
    DomainTerm,
)

# Encryption-Funktionen (für internen Gebrauch)
from agents.memory_encryption import (
    MEMORY_ENCRYPTION_ENABLED,
    MEMORY_ENCRYPTION_KEY,
    encrypt_data as _encrypt_data,
    decrypt_data as _decrypt_data,
)

# Core-Funktionen
from agents.memory_core import (
    load_memory,
    save_memory,
    save_memory_async,
    update_memory,
    update_memory_async,
    get_lessons_for_prompt,
    # Data Sources (NEU 01.02.2026)
    add_data_source,
    get_data_sources,
    # Domain Vocabulary (NEU 01.02.2026)
    add_domain_term,
    get_vocabulary,
    search_vocabulary,
)

# Lern-Funktionen
from agents.memory_learning import (
    learn_from_error,
    extract_error_pattern,
    generate_tags_from_context,
    is_duplicate_lesson,
    _generate_action_text,
)

# Feature-Recording-Funktionen
from agents.memory_features import (
    record_feature_derivation,
    record_file_by_file_session,
    record_file_by_file_session_async,
    # AENDERUNG 01.02.2026: UTDS Task-Derivation Recording
    record_task_derivation,
)

# Re-Exports für Rückwärtskompatibilität
__all__ = [
    # Types
    "MemoryEntry",
    "Lesson",
    "MemoryData",
    "DataSource",
    "DomainTerm",
    # Core
    "load_memory",
    "save_memory",
    "save_memory_async",
    "update_memory",
    "update_memory_async",
    "get_lessons_for_prompt",
    # Data Sources (NEU 01.02.2026)
    "add_data_source",
    "get_data_sources",
    # Domain Vocabulary (NEU 01.02.2026)
    "add_domain_term",
    "get_vocabulary",
    "search_vocabulary",
    # Learning
    "learn_from_error",
    "extract_error_pattern",
    "generate_tags_from_context",
    "is_duplicate_lesson",
    # Features
    "record_feature_derivation",
    "record_file_by_file_session",
    "record_file_by_file_session_async",
    # AENDERUNG 01.02.2026: UTDS
    "record_task_derivation",
]


# =============================================================================
# Rückwärtskompatibilität: Private Funktionen als Module-Level Aliases
# =============================================================================

# Encryption (intern, aber für Legacy-Code)
_get_fernet = None  # Nicht mehr direkt exponiert

def _encrypt_data_compat(data: str) -> str:
    """Rückwärtskompatibilität für _encrypt_data."""
    return _encrypt_data(data)

def _decrypt_data_compat(data: str) -> str:
    """Rückwärtskompatibilität für _decrypt_data."""
    return _decrypt_data(data)
