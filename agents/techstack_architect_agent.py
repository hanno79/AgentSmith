# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 24.01.2026
Version: 1.1
Beschreibung: TechStack-Architect Agent - Analysiert Anforderungen und entscheidet über die technische Umsetzung.
"""

from typing import Any, Dict, List, Optional
from crewai import Agent

# ÄNDERUNG 24.01.2026: Zentrale Hilfsfunktion verwenden (Single Source of Truth)
from agents.agent_utils import get_model_from_config, combine_project_rules


def create_techstack_architect(config: Dict[str, Any], project_rules: Dict[str, List[str]], router=None) -> Agent:
    """
    Erstellt den TechStack-Architect Agenten.
    Analysiert Anforderungen und gibt einen JSON-Blueprint aus.

    Args:
        config: Anwendungskonfiguration mit mode und models
        project_rules: Dictionary mit globalen und rollenspezifischen Regeln
        router: Optional ModelRouter für Fallback bei Rate Limits

    Returns:
        Konfigurierte CrewAI Agent-Instanz
    """
    if router:
        model = router.get_model("techstack_architect")
    else:
        model = get_model_from_config(config, "techstack_architect")

    combined_rules = combine_project_rules(project_rules, "techstack_architect")

    return Agent(
        role="TechStack-Architect",
        goal=(
            "Analysiere die Projektanforderungen und entscheide, welche Technologien "
            "und welches Ausgabeformat am besten geeignet sind. "
            "Gib einen strukturierten JSON-Blueprint aus."
        ),
        backstory=(
            "Du bist ein erfahrener Software-Architekt mit Expertise in verschiedenen Tech-Stacks. "
            "Du analysierst Anforderungen und entscheidest die optimale technische Umsetzung.\n\n"
            "Technologie-Entscheidung:\n\n"
            "1. **static_html**: Einfache Webseiten (HTML/CSS/JS)\n"
            "   - Sprache: html\n"
            "   - Keine Build-Tools nötig\n\n"
            "2. **python_cli** / **python_script**: Python-Anwendungen\n"
            "   - Sprache: python\n"
            "   - Package-File: requirements.txt\n\n"
            "3. **flask_app** / **fastapi_app**: Python Web-Backends\n"
            "   - Sprache: python\n"
            "   - Package-File: requirements.txt\n\n"
            "4. **nodejs_app**: Node.js Anwendungen (Backend oder CLI)\n"
            "   - Sprache: javascript\n"
            "   - Package-File: package.json\n\n"
            "5. **php_app**, **cpp_app**, **go_app**, etc.: Beliebige andere Stacks\n\n"
            "Du gibst IMMER einen validen JSON-Block aus mit:\n"
            "```json\n"
            "{\n"
            '  "project_type": "nodejs_express",\n'
            '  "language": "javascript",\n'
            '  "database": "sqlite",\n'
            '  "package_file": "package.json",\n'
            '  "dependencies": ["express", "sqlite3"],\n'
            '  "install_command": "npm install",\n'
            '  "run_command": "node index.js",\n'
            '  "reasoning": "Kurze Begründung..."\n'
            "}\n"
            "```\n"
            "Falls keine Bibliotheken nötig sind (z.B. static_html), lass install_command leer.\n"
            "Definiere run_command so, dass es direkt im Projektordner ausgeführt werden kann.\n\n"
            "WICHTIG: Dein Blueprint MUSS die Grundlage für ein sofort ausführbares Ergebnis sein. "
            "Berücksichtige bei Web-Projekten sowohl Backend als auch Frontend. "
            "Der `install_command` und `run_command` sollten, wenn möglich, alle nötigen Schritte "
            "automatisieren (z.B. `npm install && npm run build` oder `pip install -r requirements.txt`).\n\n"
            f"{combined_rules}"
        ),
        llm=model,
        verbose=True
    )
