# -*- coding: utf-8 -*-
"""
Researcher Agent: Web-Recherche mit DuckDuckGo für technische Informationen.
"""

from typing import Any, Dict, List, Union, Optional
from crewai import Agent
from langchain_community.tools import DuckDuckGoSearchRun


def _get_model_from_config(config: Dict[str, Any], role: str) -> str:
    """Hilfsfunktion: Extrahiert Modell aus Config (unterstützt String und Dict-Format)."""
    mode = config.get("mode", "test")
    model_config = config.get("models", {}).get(mode, {}).get(role)
    if isinstance(model_config, str):
        return model_config
    elif isinstance(model_config, dict):
        return model_config.get("primary", "gpt-4")
    return "gpt-4"


def create_researcher(config: Dict[str, Any], project_rules: Dict[str, List[str]], router=None) -> Agent:
    """
    Erstellt den Researcher-Agenten, der das Web nach Informationen durchsucht.
    Nutzt DuckDuckGoSearchRun als Tool.

    Args:
        config: Anwendungskonfiguration mit mode und models
        project_rules: Dictionary mit globalen und rollenspezifischen Regeln
        router: Optional ModelRouter für Fallback bei Rate Limits

    Returns:
        Konfigurierte CrewAI Agent-Instanz mit Search-Tool
    """
    if router:
        model = router.get_model("researcher")
    else:
        model = _get_model_from_config(config, "researcher")

    # Tool initialisieren
    from crewai.tools import BaseTool
    import json

    class SearchTool(BaseTool):
        name: str = "DuckDuckGoSearch"
        description: str = "Search the web for information. Input MUST be a single search query string."

        def _run(self, query) -> str:
            # Normalisiere verschiedene Input-Formate
            search_query = query
            
            # Falls Liste übergeben wurde, nimm erstes Element
            if isinstance(query, list):
                if len(query) > 0:
                    first_item = query[0]
                    if isinstance(first_item, dict) and "query" in first_item:
                        search_query = first_item["query"]
                    elif isinstance(first_item, str):
                        search_query = first_item
                    else:
                        search_query = str(first_item)
                else:
                    return "Error: Empty query list"
            
            # Falls Dict übergeben wurde, extrahiere query-Feld
            elif isinstance(query, dict):
                search_query = query.get("query", str(query))
            
            # Falls JSON-String, versuche zu parsen
            elif isinstance(query, str) and query.strip().startswith("["):
                try:
                    parsed = json.loads(query)
                    if isinstance(parsed, list) and len(parsed) > 0:
                        first = parsed[0]
                        search_query = first.get("query", str(first)) if isinstance(first, dict) else str(first)
                except:
                    search_query = query
            
            return DuckDuckGoSearchRun().run(str(search_query))

    search_tool = SearchTool()

    global_rules = "\n".join(project_rules.get("global", []))
    role_rules = "\n".join(project_rules.get("researcher", []))
    combined_rules = f"Globale Regeln:\n{global_rules}\n\nResearcher-spezifische Regeln:\n{role_rules}"

    return Agent(
        role="Researcher",
        goal="Suche präzise technische Informationen, Dokumentationen und Lösungen im Web.",
        backstory=(
            "Du bist ein technischer Researcher. Deine Aufgabe ist es, für den Planer und Coder "
            "die nötigen Fakten zu beschaffen (z.B. aktuelle API-Docs, Bibliotheken, Lösungen für Fehler). "
            "Nutze dein Search-Tool, um verifizierte Informationen zu finden.\n\n"
            f"{combined_rules}"
        ),
        tools=[search_tool],
        llm=model,
        verbose=True
    )
