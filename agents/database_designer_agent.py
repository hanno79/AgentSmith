# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 24.01.2026
Version: 1.1
Beschreibung: Database Designer Agent - Spezialist für normalisierte Datenbankschemas mit ERD-Generierung.
"""

from typing import Any, Dict, List, Optional
from crewai import Agent

# ÄNDERUNG 24.01.2026: Zentrale Hilfsfunktion verwenden (Single Source of Truth)
from agents.agent_utils import get_model_from_config, combine_project_rules


def create_database_designer(config: Dict[str, Any], project_rules: Dict[str, List[str]], router=None) -> Agent:
    """
    Erstellt den Database Designer Agenten.
    Spezialisiert auf normalisierte Schemas, ERDs und Multi-Backend-Support.

    Args:
        config: Anwendungskonfiguration mit mode und models
        project_rules: Dictionary mit globalen und rollenspezifischen Regeln
        router: Optional ModelRouter für Fallback bei Rate Limits

    Returns:
        Konfigurierte CrewAI Agent-Instanz
    """
    if router:
        model = router.get_model("database_designer")
    else:
        model = get_model_from_config(config, "database_designer")

    combined_rules = combine_project_rules(project_rules, "database_designer")

    return Agent(
        role="Database Designer",
        goal=(
            "Erstelle saubere, normalisierte Datenbankschemas (mindestens 3NF). "
            "Definiere korrekte Primär- und Fremdschlüssel, Constraints und Indexes. "
            "Generiere ein Mermaid ERD-Diagramm zur Dokumentation."
        ),
        backstory=(
            "Du bist ein erfahrener Datenbankarchitekt mit Expertise in relationalen Datenbanken. "
            "Du kennst die Normalisierungsformen (1NF, 2NF, 3NF, BCNF) und wendest sie konsequent an. "
            "Du erstellst Schemas, die Datenredundanz vermeiden und Datenintegrität garantieren.\n\n"
            "Deine Ausgabe enthält immer:\n"
            "1. **DDL-Statements** (CREATE TABLE) mit korrekten Datentypen\n"
            "2. **PRIMARY KEY** für jede Tabelle\n"
            "3. **FOREIGN KEY** mit ON DELETE/ON UPDATE Aktionen\n"
            "4. **Constraints** (NOT NULL, UNIQUE, CHECK wo sinnvoll)\n"
            "5. **Mermaid ERD** zur Visualisierung der Beziehungen\n"
            "6. **Index-Empfehlungen** für häufige Abfragen\n\n"
            "Du unterstützt verschiedene Backends:\n"
            "- SQLite: Einfache Syntax, INTEGER PRIMARY KEY für Auto-Increment\n"
            "- PostgreSQL: SERIAL für Auto-Increment, erweiterte Datentypen\n"
            "- MySQL: AUTO_INCREMENT, ENGINE=InnoDB für Foreign Keys\n\n"
            f"{combined_rules}"
        ),
        llm=model,
        verbose=True
    )
