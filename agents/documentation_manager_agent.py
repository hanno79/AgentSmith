# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 30.01.2026
Version: 1.0
Beschreibung: Documentation Manager Agent - Erstellt und verwaltet Projekt-Dokumentation.
              5. Core Agent laut Dart AI Spezifikation (Agenten-Katalog v1.0).
"""

from typing import Any, Dict, List, Optional
from crewai import Agent

from agents.agent_utils import get_model_from_config, combine_project_rules


def create_documentation_manager(
    config: Dict[str, Any],
    project_rules: Dict[str, List[str]],
    router=None
) -> Agent:
    """
    Erstellt den Documentation Manager Agent.

    Der Documentation Manager ist der 5. Core Agent und verantwortlich für:
    - Erstellung von README.md basierend auf Projekt-Informationen
    - Erstellung von CHANGELOG.md basierend auf Iterations-Historie
    - Konsistenz-Prüfung der Dokumentation
    - Qualitätssicherung der Projekt-Dokumentation

    Args:
        config: Anwendungskonfiguration mit mode und models
        project_rules: Dictionary mit globalen und rollenspezifischen Regeln
        router: Optional ModelRouter für Fallback bei Rate Limits

    Returns:
        Konfigurierte CrewAI Agent-Instanz
    """
    if router:
        model = router.get_model("documentation_manager")
    else:
        # Fallback auf reviewer-Modell wenn documentation_manager nicht konfiguriert
        model = get_model_from_config(
            config,
            "documentation_manager",
            fallback_role="reviewer"
        )

    combined_rules = combine_project_rules(project_rules, "documentation_manager")

    return Agent(
        role="Documentation Manager",
        goal=(
            "Erstelle vollständige, präzise und benutzerfreundliche Projekt-Dokumentation. "
            "Validiere dass alle Informationen konsistent mit dem tatsächlichen Code sind. "
            "Generiere README.md mit klaren Installationsanweisungen und Nutzungshinweisen."
        ),
        backstory=(
            "Du bist ein erfahrener Technical Writer und Dokumentationsspezialist. "
            "Du verstehst sowohl die technischen Details als auch die Bedürfnisse der Endnutzer.\n\n"

            "**Deine Hauptaufgaben:**\n"
            "1. README.md erstellen mit:\n"
            "   - Projektbeschreibung (was macht die Anwendung?)\n"
            "   - Voraussetzungen (Dependencies, Systemanforderungen)\n"
            "   - Installation (Schritt-für-Schritt Anleitung)\n"
            "   - Verwendung (wie startet/nutzt man die App?)\n"
            "   - Projektstruktur (wichtige Dateien/Ordner)\n\n"

            "2. CHANGELOG.md erstellen mit:\n"
            "   - Versionierte Änderungen\n"
            "   - Datum und Beschreibung pro Iteration\n"
            "   - Kategorisierung (Feature, Fix, Verbesserung)\n\n"

            "**Formatierung:**\n"
            "- Verwende klares, strukturiertes Markdown\n"
            "- Nutze Code-Blöcke für Befehle und Beispiele\n"
            "- Halte die Sprache einfach und verständlich\n"
            "- Schreibe auf Deutsch (gemäß Projektregeln)\n\n"

            "**Qualitätskriterien:**\n"
            "- Alle Befehle müssen korrekt und ausführbar sein\n"
            "- Keine Platzhalter oder TODO-Marker in finaler Dokumentation\n"
            "- Konsistenz mit tatsächlichem TechStack und Code\n\n"

            f"{combined_rules}"
        ),
        llm=model,
        verbose=True,
        allow_delegation=False
    )


def get_readme_task_description(context: str) -> str:
    """
    Erstellt die Task-Beschreibung für README-Generierung.

    Args:
        context: Der vom DocumentationService generierte Kontext

    Returns:
        Formatierte Task-Beschreibung
    """
    return f"""
Erstelle eine vollständige README.md Datei basierend auf folgendem Projekt-Kontext:

{context}

**Anforderungen an die README:**

1. **Titel und Beschreibung:**
   - Aussagekräftiger Projekttitel
   - Kurze Beschreibung was die Anwendung macht
   - Optional: Badges für Status/Version

2. **Voraussetzungen:**
   - Benötigte Software (Python-Version, Node.js, etc.)
   - Systemanforderungen wenn relevant

3. **Installation:**
   - Schritt-für-Schritt Anleitung
   - Alle notwendigen Befehle in Code-Blöcken
   - Hinweise für verschiedene Betriebssysteme wenn nötig

4. **Verwendung:**
   - Wie startet man die Anwendung?
   - Beispiele für typische Nutzung
   - Screenshots/GIFs wenn sinnvoll (als Platzhalter markieren)

5. **Projektstruktur:**
   - Übersicht der wichtigsten Dateien/Ordner
   - Kurze Beschreibung der Struktur

6. **Lizenz und Autor:**
   - Lizenzhinweis
   - Autor-Information

**WICHTIG:**
- Schreibe auf Deutsch
- Verwende korrektes Markdown
- Alle Befehle müssen ausführbar sein
- Keine Platzhalter wie [TODO] oder [HIER EINFÜGEN]

Gib NUR den README-Inhalt aus, ohne zusätzliche Erklärungen.
"""


def get_changelog_task_description(iterations_summary: str) -> str:
    """
    Erstellt die Task-Beschreibung für CHANGELOG-Generierung.

    Args:
        iterations_summary: Zusammenfassung der Iterationen

    Returns:
        Formatierte Task-Beschreibung
    """
    return f"""
Erstelle eine CHANGELOG.md Datei basierend auf folgenden Iterations-Daten:

{iterations_summary}

**Format:**

```markdown
# Changelog

Alle wichtigen Änderungen an diesem Projekt werden hier dokumentiert.

## [Version/Iteration] - DATUM

### Hinzugefügt
- Neue Features...

### Geändert
- Änderungen an bestehendem Code...

### Behoben
- Bug-Fixes...
```

**WICHTIG:**
- Schreibe auf Deutsch
- Kategorisiere Änderungen sinnvoll
- Halte Einträge prägnant aber informativ
- Neueste Änderungen zuerst

Gib NUR den CHANGELOG-Inhalt aus.
"""
