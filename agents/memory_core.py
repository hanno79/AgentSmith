# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 01.02.2026
Version: 1.1
Beschreibung: Memory Agent Core-Funktionen (Load/Save).
              Extrahiert aus memory_agent.py (Regel 1: Max 500 Zeilen)

              ÄNDERUNG 01.02.2026 v1.1: DataSource und DomainTerm Funktionen hinzugefügt
"""

import os
import json
import asyncio
from datetime import datetime
from typing import Optional

from typing import List
from agents.memory_types import MemoryData, MemoryEntry, DataSource, DomainTerm
from agents.memory_encryption import encrypt_data, decrypt_data


def load_memory(memory_path: str) -> MemoryData:
    """Lädt bestehendes Memory oder erstellt ein leeres. Supports encrypted files."""
    if os.path.exists(memory_path):
        with open(memory_path, "r", encoding="utf-8") as f:
            content = f.read()
        # Decrypt if encrypted, otherwise parse as-is (backwards compatible)
        decrypted_content = decrypt_data(content)
        return json.loads(decrypted_content)
    return {"history": [], "lessons": []}


def save_memory(memory_path: str, memory_data: MemoryData) -> None:
    """Speichert das Memory dauerhaft als JSON. Encrypts if encryption is enabled."""
    dirpath = os.path.dirname(memory_path)
    if dirpath:
        os.makedirs(dirpath, exist_ok=True)
    json_content = json.dumps(memory_data, indent=2, ensure_ascii=False)
    # Encrypt if encryption is enabled
    encrypted_content = encrypt_data(json_content)
    with open(memory_path, "w", encoding="utf-8") as f:
        f.write(encrypted_content)


async def save_memory_async(memory_path: str, memory_data: MemoryData) -> None:
    """
    Async-Version von save_memory.
    Führt blockierende I/O und Encryption in separatem Thread aus.
    """
    def _blocking_save():
        save_memory(memory_path, memory_data)

    await asyncio.to_thread(_blocking_save)


def update_memory(
    memory_path: str,
    coder_output: str,
    review_output: Optional[str],
    sandbox_output: Optional[str] = None
) -> MemoryEntry:
    """
    Fügt neue Erkenntnisse ins Memory hinzu.
    """
    memory_data = load_memory(memory_path)

    entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "coder_output_preview": str(coder_output)[:500],
        "review_feedback": str(review_output)[:500] if review_output else None,
        "sandbox_feedback": str(sandbox_output)[:500] if sandbox_output else None
    }

    memory_data["history"].append(entry)
    save_memory(memory_path, memory_data)

    return entry


async def update_memory_async(
    memory_path: str,
    coder_output: str,
    review_output: Optional[str],
    sandbox_output: Optional[str] = None
) -> MemoryEntry:
    """
    Async-Version von update_memory.
    Führt blockierende I/O in separatem Thread aus.
    """
    # load_memory ist schnell (read-only), bleibt synchron
    memory_data = load_memory(memory_path)

    entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "coder_output_preview": str(coder_output)[:500],
        "review_feedback": str(review_output)[:500] if review_output else None,
        "sandbox_feedback": str(sandbox_output)[:500] if sandbox_output else None
    }

    memory_data["history"].append(entry)
    await save_memory_async(memory_path, memory_data)

    return entry


def get_lessons_for_prompt(memory_path: str, tech_stack: str = None) -> str:
    """
    Lädt Lessons Learned aus dem Memory, gefiltert nach Tech-Stack.
    """
    if not os.path.exists(memory_path):
        return ""

    try:
        with open(memory_path, "r", encoding="utf-8") as f:
            content = f.read()
        # Decrypt if encrypted, otherwise parse as-is (backwards compatible)
        decrypted_content = decrypt_data(content)
        data = json.loads(decrypted_content)
    except Exception:
        return ""

    lessons = data.get("lessons", [])
    relevant_lessons = []

    for lesson in lessons:
        # Simple keywords matching or global
        tags = lesson.get("tags", [])
        if "global" in tags:
            relevant_lessons.append(lesson["action"])
            continue

        # Check if tags match current tech stack
        if tech_stack:
            for tag in tags:
                if tag.lower() in tech_stack.lower():
                    relevant_lessons.append(lesson["action"])
                    break

    if not relevant_lessons:
        return ""

    return "\n".join([f"- [MEMORY]: {l}" for l in relevant_lessons])


# =============================================================================
# Data Sources Funktionen (NEU 01.02.2026)
# =============================================================================

def add_data_source(memory_path: str, source: DataSource) -> str:
    """
    Fügt eine neue Datenquelle hinzu oder aktualisiert bestehende.

    Args:
        memory_path: Pfad zur Memory-Datei
        source: DataSource-Dict mit den Quellinformationen

    Returns:
        Statusmeldung ob hinzugefügt oder aktualisiert
    """
    data = load_memory(memory_path)
    sources = data.get("known_data_sources", [])

    # Duplikat-Check nach Name
    for s in sources:
        if s.get("name") == source["name"]:
            s.update(source)
            data["known_data_sources"] = sources
            save_memory(memory_path, data)
            return f"Datenquelle aktualisiert: {source['name']}"

    sources.append(source)
    data["known_data_sources"] = sources
    save_memory(memory_path, data)
    return f"Datenquelle hinzugefügt: {source['name']}"


def get_data_sources(memory_path: str, source_type: Optional[str] = None) -> List[DataSource]:
    """
    Gibt alle oder gefilterte Datenquellen zurück.

    Args:
        memory_path: Pfad zur Memory-Datei
        source_type: Optional Filter nach Typ ("api", "database", "file", "service")

    Returns:
        Liste der Datenquellen
    """
    data = load_memory(memory_path)
    sources = data.get("known_data_sources", [])

    if source_type:
        return [s for s in sources if s.get("type") == source_type]
    return sources


# =============================================================================
# Domain Vocabulary Funktionen (NEU 01.02.2026)
# =============================================================================

def add_domain_term(memory_path: str, term: DomainTerm) -> str:
    """
    Fügt einen neuen Fachbegriff hinzu oder aktualisiert bestehenden.

    Args:
        memory_path: Pfad zur Memory-Datei
        term: DomainTerm-Dict mit dem Fachbegriff

    Returns:
        Statusmeldung ob hinzugefügt oder aktualisiert
    """
    data = load_memory(memory_path)
    vocab = data.get("domain_vocabulary", [])

    # Duplikat-Check (auch Aliase prüfen)
    term_lower = term["term"].lower()
    for v in vocab:
        if v.get("term", "").lower() == term_lower:
            v["usage_count"] = v.get("usage_count", 0) + 1
            data["domain_vocabulary"] = vocab
            save_memory(memory_path, data)
            return f"Begriff aktualisiert: {term['term']}"

    vocab.append(term)
    data["domain_vocabulary"] = vocab
    save_memory(memory_path, data)
    return f"Begriff hinzugefügt: {term['term']}"


def get_vocabulary(memory_path: str, domain: Optional[str] = None) -> List[DomainTerm]:
    """
    Gibt alle oder gefilterte Fachbegriffe zurück.

    Args:
        memory_path: Pfad zur Memory-Datei
        domain: Optional Filter nach Domain (z.B. "fintech", "healthcare")

    Returns:
        Liste der Fachbegriffe
    """
    data = load_memory(memory_path)
    vocab = data.get("domain_vocabulary", [])

    if domain:
        return [v for v in vocab if v.get("domain") == domain]
    return vocab


def search_vocabulary(memory_path: str, search_term: str) -> List[DomainTerm]:
    """
    Sucht in Begriffen und Aliasen.

    Args:
        memory_path: Pfad zur Memory-Datei
        search_term: Suchbegriff

    Returns:
        Liste der passenden Fachbegriffe
    """
    data = load_memory(memory_path)
    vocab = data.get("domain_vocabulary", [])
    search_lower = search_term.lower()

    results = []
    for v in vocab:
        # Suche im Hauptbegriff
        if search_lower in v.get("term", "").lower():
            results.append(v)
        # Suche in Aliasen
        elif any(search_lower in alias.lower() for alias in v.get("aliases", [])):
            results.append(v)
    return results
