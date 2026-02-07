# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 07.02.2026
Version: 2.0
Beschreibung: TechStack-Architect Agent - Waehlt aus vordefinierten Templates oder
              erstellt Custom-Blueprints fuer neue Tech-Stacks.
              AENDERUNG 07.02.2026: Template-basierter Ansatz statt Blueprint-Erfindung.
"""

from typing import Any, Dict, List, Optional
from crewai import Agent

from agents.agent_utils import get_model_from_config, combine_project_rules


def create_techstack_architect(config: Dict[str, Any], project_rules: Dict[str, List[str]], router=None) -> Agent:
    """
    Erstellt den TechStack-Architect Agenten.
    Waehlt das passende Template und passt es an spezifische Anforderungen an.

    Args:
        config: Anwendungskonfiguration mit mode und models
        project_rules: Dictionary mit globalen und rollenspezifischen Regeln
        router: Optional ModelRouter fuer Fallback bei Rate Limits

    Returns:
        Konfigurierte CrewAI Agent-Instanz
    """
    if router:
        model = router.get_model("techstack_architect")
    else:
        model = get_model_from_config(config, "techstack_architect")

    combined_rules = combine_project_rules(project_rules, "techstack_architect")

    # AENDERUNG 07.02.2026: Template-Summary dynamisch laden
    template_summary = _get_template_summary()

    return Agent(
        role="TechStack-Architect",
        goal=(
            "Analysiere die Projektanforderungen und waehle das beste verfuegbare Template. "
            "Ergaenze spezifische Dependencies die das Template nicht abdeckt. "
            "Gib einen strukturierten JSON-Output aus."
        ),
        backstory=(
            "Du bist ein erfahrener Software-Architekt. Dir stehen vordefinierte, "
            "getestete Tech-Stack Templates zur Verfuegung. Diese Templates enthalten "
            "bewaehrte Dependency-Kombinationen mit exakten Versionen.\n\n"
            f"{template_summary}\n\n"
            "DEINE AUFGABE:\n"
            "1. Analysiere die Benutzeranforderungen\n"
            "2. Waehle das BESTE passende Template (template_id)\n"
            "3. Definiere ZUSAETZLICHE Dependencies die das Template noch braucht\n"
            "   (z.B. openai fuer KI-Features, react-speech-recognition fuer Spracheingabe)\n"
            "4. Passe database und server_port an falls noetig\n\n"
            "AUSGABE-FORMAT (JSON):\n"
            "```json\n"
            "{\n"
            '  "selected_template": "nextjs_tailwind",\n'
            '  "additional_dependencies": {"sqlite3": "5.1.7", "sqlite": "5.0.0"},\n'
            '  "customizations": {\n'
            '    "database": "sqlite",\n'
            '    "server_port": 3000\n'
            "  },\n"
            '  "reasoning": "Kurze Begruendung..."\n'
            "}\n"
            "```\n\n"
            "WENN KEIN Template passt (z.B. Rust, Go, exotischer Stack):\n"
            "```json\n"
            "{\n"
            '  "selected_template": null,\n'
            '  "blueprint": {\n'
            '    "project_type": "go_app",\n'
            '    "app_type": "cli",\n'
            '    "test_strategy": "cli_test",\n'
            '    "language": "go",\n'
            '    "database": "none",\n'
            '    "package_file": "go.mod",\n'
            '    "dependencies": ["github.com/spf13/cobra"],\n'
            '    "install_command": "go mod download",\n'
            '    "run_command": "go run main.go",\n'
            '    "requires_server": false,\n'
            '    "server_port": 0,\n'
            '    "server_startup_time_ms": 0,\n'
            '    "reasoning": "Go CLI braucht kein vordefiniertes Template..."\n'
            "  }\n"
            "}\n"
            "```\n\n"
            "WICHTIG:\n"
            "- Waehle das SPEZIFISCHSTE Template (nextjs_sqlite > nextjs_tailwind wenn Datenbank noetig)\n"
            "- Fuer additional_dependencies: Verwende EXAKTE Versionen (kein ^ oder ~)\n"
            "- Template-Dependencies sind bereits getestet — aendere sie NICHT\n"
            "- app_type bestimmt die Test-Strategie: webapp=playwright, desktop=pyautogui, cli=cli_test\n"
            "- WARNUNG: Frontend-Pakete (bootstrap, tailwindcss, react) sind KEINE Python-Pakete!\n\n"
            f"{combined_rules}"
        ),
        llm=model,
        verbose=True
    )


def _get_template_summary() -> str:
    """Laedt Template-Summary fuer den Agent-Prompt. Graceful Fallback bei Fehler."""
    try:
        from techstack_templates.template_loader import get_template_summary_for_prompt
        summary = get_template_summary_for_prompt()
        if summary:
            return summary
    except ImportError:
        pass
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("Template-Summary konnte nicht geladen werden: %s", e)
    # Fallback: Minimale Template-Liste
    return (
        "VERFUEGBARE TEMPLATES:\n"
        "- nextjs_tailwind: Next.js + Tailwind CSS (Webapp)\n"
        "- nextjs_sqlite: Next.js + Tailwind + SQLite (Webapp mit DB)\n"
        "- flask_webapp: Flask + Jinja2 + SQLite (Python Webapp)\n"
        "- fastapi_api: FastAPI + SQLAlchemy (Python API)\n"
        "- python_cli: Python CLI Tool\n"
        "- python_tkinter: Python Desktop (Tkinter)\n"
        "- static_html: Reines HTML/CSS/JS\n"
        "- express_api: Node.js Express API\n"
        "- react_vite: React + Vite SPA"
    )
