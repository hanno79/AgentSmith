# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 29.01.2026
Version: 1.0
Beschreibung: Library- und Archiv-Endpoints.
"""
# ÄNDERUNG 29.01.2026: Library-Endpunkte in eigenes Router-Modul verschoben

import re
from typing import Optional
from fastapi import APIRouter, HTTPException
from ..library_manager import get_library_manager

router = APIRouter()


def sanitize_search_query(query: str, max_length: int = 200) -> str:
    """Sanitize search query to prevent injection attacks."""
    if not query:
        return ""
    query = query[:max_length]
    query = re.sub(r'[^\w\s\-_.,!?]', '', query)
    return query.strip()


@router.get("/library/current")
def get_current_project_protocol():
    """Gibt das aktuelle Projekt-Protokoll zurück."""
    library = get_library_manager()
    project = library.get_current_project()
    if not project:
        return {"status": "no_project", "project": None}
    return {"status": "ok", "project": project}


@router.get("/library/entries")
def get_protocol_entries(agent: Optional[str] = None, limit: int = 100):
    """
    Gibt Protokoll-Einträge des aktuellen Projekts zurück.

    Args:
        agent: Optional - nur Einträge von diesem Agent
        limit: Maximale Anzahl Einträge
    """
    library = get_library_manager()
    entries = library.get_entries(agent_filter=agent, limit=limit)
    return {"status": "ok", "entries": entries, "count": len(entries)}


@router.get("/library/archive")
def get_archived_projects():
    """Gibt alle archivierten Projekte zurück (ohne Einträge)."""
    library = get_library_manager()
    projects = library.get_archived_projects()
    return {"status": "ok", "projects": projects, "count": len(projects)}


@router.get("/library/archive/{project_id}")
def get_archived_project(project_id: str):
    """Lädt ein archiviertes Projekt vollständig."""
    library = get_library_manager()
    project = library.get_archived_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail=f"Projekt '{project_id}' nicht gefunden")
    return {"status": "ok", "project": project}


@router.get("/library/search")
def search_archives(q: str, limit: int = 20):
    """
    Durchsucht alle Archive nach einem Begriff.

    Args:
        q: Suchbegriff
        limit: Maximale Ergebnisse
    """
    sanitized_query = sanitize_search_query(q)
    if not sanitized_query:
        return {"status": "ok", "results": [], "count": 0}

    library = get_library_manager()
    results = library.search_archives(sanitized_query, limit=limit)
    return {"status": "ok", "results": results, "count": len(results)}
