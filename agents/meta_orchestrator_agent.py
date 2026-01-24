# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 24.01.2026
Version: 2.0
Beschreibung: Meta-Orchestrator - Automatische Erkennung, Auswahl und Steuerung von Agenten.
"""

import re
from typing import List, Dict


class MetaOrchestratorV2:
    """
    Der Meta-Orchestrator v2.0 analysiert den Benutzerprompt und entscheidet,
    welche Agenten für das Projekt benötigt werden und in welcher Reihenfolge.
    """

    def __init__(self):
        self.available_agents = {
            "coder": "💻 Coder-Agent – implementiert Code und Logik",
            "reviewer": "🕵️ Reviewer-Agent – prüft Codequalität und Funktionalität",
            "designer": "🎨 Designer-Agent – gestaltet Layouts, Farben, UI",
            "tester": "🧪 Tester-Agent – überprüft UI und Funktionalität (Playwright)",
            "researcher": "🔎 Research-Agent – recherchiert Daten und Quellen",
            "database_designer": "🗄️ Database-Designer – erstellt normalisierte DB-Schemas",
            "techstack_architect": "🛠️ TechStack-Architect – entscheidet über technische Umsetzung",
            "memory": "🧠 Memory-Agent – merkt sich Projekterfahrungen",
        }

    def analyze_prompt(self, user_prompt: str) -> Dict:
        """Analysiert den Benutzerprompt und bestimmt Projekttyp und Anforderungen."""
        prompt_lower = user_prompt.lower()

        categories = {
            "web": bool(re.search(r"html|css|javascript|webseite|frontend", prompt_lower)),
            "data": bool(re.search(r"csv|data|analyse|statistik|geo|gis|karte", prompt_lower)),
            "design": bool(re.search(r"farbe|ui|ux|layout|stil|design", prompt_lower)),
            "automation": bool(re.search(r"automatisier|workflow|script|bot", prompt_lower)),
            "text": bool(re.search(r"text|bericht|report|analyse", prompt_lower)),
            "database": bool(re.search(r"datenbank|database|sqlite|postgres|mysql|tabelle|schema|sql|backend", prompt_lower)),
        }

        # Bestimme primären Projekttyp
        project_type = [k for k, v in categories.items() if v]
        if not project_type:
            project_type = ["general"]

        return {
            "project_type": project_type,
            "needs_ui": categories["web"] or categories["design"],
            "needs_data": categories["data"],
            "needs_research": categories["data"] or "research" in prompt_lower,
            "needs_database": categories["database"],
        }

    def build_plan(self, analysis: Dict) -> List[str]:
        """Erstellt basierend auf der Analyse einen Ausführungsplan."""
        # TechStack-Architect läuft immer zuerst
        plan = ["techstack_architect", "coder", "reviewer"]

        if analysis["needs_ui"]:
            plan.insert(1, "designer")
            plan.append("tester")

        if analysis["needs_data"] or analysis["needs_research"]:
            plan.insert(0, "researcher")

        if analysis.get("needs_database"):
            # Database Designer kommt vor dem Coder
            coder_index = plan.index("coder") if "coder" in plan else 0
            plan.insert(coder_index, "database_designer")

        # Memory-Agent ist immer aktiv
        plan.append("memory")

        return plan

    def explain_plan(self, plan: List[str]) -> str:
        """Gibt eine lesbare Beschreibung des Plans zurück."""
        return "\n".join([f"• {self.available_agents[a]}" for a in plan])

    def orchestrate(self, user_prompt: str) -> Dict:
        """Gesamter Prozess: Prompt → Analyse → Plan"""
        analysis = self.analyze_prompt(user_prompt)
        plan = self.build_plan(analysis)
        return {
            "analysis": analysis,
            "plan": plan,
            "explanation": self.explain_plan(plan),
        }
