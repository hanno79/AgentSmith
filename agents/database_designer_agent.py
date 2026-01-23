# -*- coding: utf-8 -*-
"""
Database Designer Agent v1.0
Spezialist für normalisierte Datenbankschemas mit ERD-Generierung.
"""

from crewai import Agent


def create_database_designer(config, project_rules):
    """
    Erstellt den Database Designer Agenten.
    Spezialisiert auf normalisierte Schemas, ERDs und Multi-Backend-Support.
    """
    mode = config.get("mode", "test")
    model = config.get("models", {}).get(mode, {}).get("database_designer", "gpt-4")

    global_rules = "\n".join(project_rules.get("global", []))
    role_rules = "\n".join(project_rules.get("database_designer", []))
    combined_rules = f"Globale Regeln:\n{global_rules}\n\nDatabase-Designer-spezifische Regeln:\n{role_rules}"

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
        model=model,
        verbose=True
    )
