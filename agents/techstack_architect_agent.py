# -*- coding: utf-8 -*-
"""
TechStack-Architect Agent v1.0
Analysiert Anforderungen und entscheidet über die technische Umsetzung.
"""

from crewai import Agent


def create_techstack_architect(config, project_rules):
    """
    Erstellt den TechStack-Architect Agenten.
    Analysiert Anforderungen und gibt einen JSON-Blueprint aus.
    """
    mode = config.get("mode", "test")
    model = config.get("models", {}).get(mode, {}).get("techstack_architect", "gpt-4")

    global_rules = "\n".join(project_rules.get("global", []))
    role_rules = "\n".join(project_rules.get("techstack_architect", []))
    combined_rules = f"Globale Regeln:\n{global_rules}\n\nTechStack-Architect-spezifische Regeln:\n{role_rules}"

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
        model=model,
        verbose=True
    )
