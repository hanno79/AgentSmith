# -*- coding: utf-8 -*-
"""
Author: rahn / Claude
Datum: 01.02.2026
Version: 1.2
Beschreibung: Discovery Session - Strukturierter Projektauftakt-Dialog.
              Implementiert das Guided Choice System fuer interaktive Anforderungserhebung.
              ÄNDERUNG 01.02.2026 v1.1: Refaktoriert in Module (Regel 1: Max 500 Zeilen)
              - discovery_models.py: Enums und Dataclasses
              - discovery_questions.py: QuestionTemplates
              - discovery_ui.py: GuidedChoiceUI
              - discovery_intelligence.py: OptionGenerator
              AENDERUNG 01.02.2026 v1.2: UTDS-Integration fuer Task-Ableitung aus Briefing
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Callable
import logging

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm

# Importiere extrahierte Module
from discovery_models import (
    AnswerMode, SessionPhase, AnswerOption,
    GuidedQuestion, Answer, ProjectBriefing
)
from discovery_questions import QuestionTemplates
from discovery_ui import GuidedChoiceUI
from discovery_intelligence import OptionGenerator

# AENDERUNG 01.02.2026: UTDS Import fuer Task-Derivation
try:
    from backend.task_deriver import TaskDeriver
    from backend.task_models import TaskDerivationResult
    UTDS_AVAILABLE = True
except ImportError:
    UTDS_AVAILABLE = False

logger = logging.getLogger(__name__)

console = Console()


class DiscoverySession:
    """Hauptcontroller fuer die Discovery Session."""

    def __init__(self, config: Dict = None, memory_path: str = None, model_router=None):
        self.config = config or {}
        self.memory_path = memory_path
        self.model_router = model_router
        self.ui = GuidedChoiceUI()
        self.option_generator = OptionGenerator(memory_path)
        self.answers: List[Answer] = []
        self.selected_agents: List[str] = []
        self.vision: str = ""
        self.open_points: List[str] = []
        self.context_recommendations: Dict[str, str] = {}
        self.on_log: Optional[Callable] = None

    def _log(self, event: str, message: str):
        """Sendet Log-Event wenn Callback gesetzt."""
        if self.on_log:
            self.on_log("DiscoverySession", event, message)

    # -------------------------------------------------------------------------
    # Phase 1: Vision & Ziel
    # -------------------------------------------------------------------------

    def phase_vision(self) -> str:
        """Phase 1: Freie Eingabe der Projektvision."""
        console.print(Panel.fit(
            "[bold]Phase 1: Vision & Ziel[/bold]\n\n"
            "Beschreibe dein Projekt frei und unstrukturiert.\n"
            "Was moechtest du entwickeln? Welches Problem soll geloest werden?",
            title="[bold blue]Discovery Session[/bold blue]",
            border_style="blue"
        ))

        self.vision = Prompt.ask("\n[bold blue]Deine Projektvision[/bold blue]")
        self._log("PHASE_1_COMPLETE", f"Vision: {self.vision[:100]}...")
        return self.vision

    # -------------------------------------------------------------------------
    # Phase 2: Team-Zusammenstellung
    # -------------------------------------------------------------------------

    def phase_team_setup(self, analysis: Dict) -> List[str]:
        """Phase 2: Automatische Agenten-Auswahl basierend auf Vision."""
        agents = ["Analyst", "Coder", "Tester", "Planner"]

        if analysis.get("needs_ui", False):
            agents.insert(2, "Designer")
        if analysis.get("needs_data", False) or analysis.get("categories", {}).get("data", False):
            agents.insert(1, "Data Researcher")
        if analysis.get("needs_security", True):
            agents.append("Security")

        self.selected_agents = agents

        console.print(Panel.fit(
            "[bold]Phase 2: Team-Zusammenstellung[/bold]\n\n"
            f"Fuer dein Projekt lade ich folgende Experten ein:\n\n"
            + "\n".join([f"  - {a}" for a in agents]),
            title="[bold green]Meta-Orchestrator[/bold green]",
            border_style="green"
        ))

        self._log("PHASE_2_COMPLETE", f"Selected agents: {agents}")
        return agents

    # -------------------------------------------------------------------------
    # Phase 3: Guided Questions
    # -------------------------------------------------------------------------

    def phase_guided_questions(self, context: Dict = None) -> List[Answer]:
        """Phase 3: Gefuehrte Fragen pro Agent."""
        context = context or {}

        self.context_recommendations = self.option_generator.get_context_recommendations(
            self.vision
        )

        console.print(Panel.fit(
            "[bold]Phase 3: Gefuehrte Fragen[/bold]\n\n"
            "Jeder Experte stellt nun seine Kernfragen.\n"
            "Waehle aus den vorgeschlagenen Optionen oder gib eigene Antworten.\n\n"
            "[dim]Optionen mit [Memory] stammen aus frueheren Projekten.[/dim]",
            title="[bold yellow]Discovery Session[/bold yellow]",
            border_style="yellow"
        ))

        question_getters = {
            "Analyst": QuestionTemplates.get_analyst_questions,
            "Data Researcher": QuestionTemplates.get_data_researcher_questions,
            "Coder": QuestionTemplates.get_coder_questions,
            "Tester": QuestionTemplates.get_tester_questions,
            "Designer": QuestionTemplates.get_designer_questions,
            "Planner": QuestionTemplates.get_planner_questions,
            "Security": QuestionTemplates.get_security_questions,
        }

        for agent in self.selected_agents:
            if agent in question_getters:
                questions = question_getters[agent](context)
                console.print(f"\n[bold]--- Runde: {agent} ---[/bold]\n")

                for question in questions:
                    enhanced_options = self.option_generator.enhance_options_from_memory(
                        question.options,
                        {"vision": self.vision, "agent": agent, **context},
                        question.category
                    )
                    question.options = enhanced_options

                    if question.category == "technical" and "language" in self.context_recommendations:
                        rec_lang = self.context_recommendations["language"]
                        rec_reason = self.context_recommendations.get("language_reason", "")
                        for opt in question.options:
                            if rec_lang.lower() in opt.text.lower():
                                opt.is_recommended = True
                                opt.reason = rec_reason

                    answer = self.ui.display_question(question)
                    self.answers.append(answer)

                    if answer.skipped:
                        self.open_points.append(f"{agent}: {question.question}")

                summary = self._generate_agent_summary(agent)
                confirmed = self.ui.display_summary(agent, summary)

                if not confirmed:
                    console.print("[yellow]Verstanden - lass uns die Punkte korrigieren...[/yellow]")
                    agent_answers = [a for a in self.answers if a.agent == agent]

                    for old_answer in agent_answers:
                        if Confirm.ask(f"[dim]Moechtest du '{old_answer.question_id}' aendern?[/dim]", default=False):
                            matching_q = [q for q in questions if f"{agent}_{q.category}" == old_answer.question_id]
                            if matching_q:
                                new_answer = self.ui.display_question(matching_q[0])
                                idx = self.answers.index(old_answer)
                                self.answers[idx] = new_answer

                    summary = self._generate_agent_summary(agent)
                    self.ui.display_summary(agent, summary)

        self._log("PHASE_3_COMPLETE", f"Collected {len(self.answers)} answers")
        return self.answers

    def _generate_agent_summary(self, agent: str) -> str:
        """Generiert Zusammenfassung fuer einen Agenten."""
        agent_answers = [a for a in self.answers if a.agent == agent]
        lines = [f"Basierend auf deinen Angaben verstehe ich Folgendes:\n"]

        for answer in agent_answers:
            if answer.skipped:
                lines.append(f"- (Offener Punkt)")
            elif answer.custom_text:
                lines.append(f"- {answer.custom_text}")
            else:
                lines.append(f"- {', '.join(str(v) for v in answer.selected_options)}")

        return "\n".join(lines)

    # -------------------------------------------------------------------------
    # Phase 4: Projektbriefing generieren
    # -------------------------------------------------------------------------

    def generate_briefing(self) -> ProjectBriefing:
        """Generiert das strukturierte Projektbriefing."""
        briefing = ProjectBriefing(
            project_name=self._extract_project_name(),
            auftraggeber="[Auftraggeber]",
            datum=datetime.now().strftime("%Y-%m-%d"),
            teilnehmende_agenten=self.selected_agents,
            projektziel=self.vision,
            scope_enthalten=self._extract_scope_included(),
            scope_ausgeschlossen=self._extract_scope_excluded(),
            datengrundlage=self._extract_data_sources(),
            technische_anforderungen=self._extract_tech_requirements(),
            erfolgskriterien=self._extract_success_criteria(),
            timeline=self._extract_timeline(),
            offene_punkte=self.open_points
        )

        self._log("BRIEFING_GENERATED", f"Project: {briefing.project_name}")
        return briefing

    def _extract_project_name(self) -> str:
        """Extrahiert Projektnamen aus Vision."""
        words = self.vision.split()[:5]
        return "_".join(words).lower().replace(".", "").replace(",", "")[:50]

    def _extract_scope_included(self) -> List[str]:
        """Extrahiert enthaltenen Scope aus Antworten."""
        included = []
        for answer in self.answers:
            if not answer.skipped and answer.selected_options:
                included.extend([str(v) for v in answer.selected_options])
        return included[:10]

    def _extract_scope_excluded(self) -> List[str]:
        """Extrahiert ausgeschlossenen Scope."""
        return [f"Offener Punkt: {p}" for p in self.open_points]

    def _extract_data_sources(self) -> List[str]:
        """Extrahiert Datenquellen aus Antworten."""
        sources = []
        for answer in self.answers:
            if "Data" in answer.agent and answer.selected_options:
                sources.extend([str(v) for v in answer.selected_options])
        return sources or ["Keine spezifischen Datenquellen angegeben"]

    def _extract_tech_requirements(self) -> Dict[str, Any]:
        """Extrahiert technische Anforderungen."""
        tech = {}
        for answer in self.answers:
            if "Coder" in answer.agent:
                if "language" in answer.question_id.lower():
                    tech["sprache"] = answer.selected_options[0] if answer.selected_options else "auto"
                elif "deployment" in answer.question_id.lower():
                    tech["deployment"] = answer.selected_options[0] if answer.selected_options else "local"
        return tech or {"sprache": "python", "deployment": "local"}

    def _extract_success_criteria(self) -> List[str]:
        """Extrahiert Erfolgskriterien."""
        criteria = []
        for answer in self.answers:
            if "Tester" in answer.agent and "success" in answer.question_id.lower():
                criteria.extend([str(v) for v in answer.selected_options])
        return criteria or ["Funktionalitaet vollstaendig", "Tests bestanden"]

    def _extract_timeline(self) -> Dict[str, str]:
        """Extrahiert Timeline."""
        timeline = {"liefertermin": "Nach Vereinbarung"}
        for answer in self.answers:
            if "Planner" in answer.agent and "timeline" in answer.question_id.lower():
                if answer.selected_options:
                    timeline["liefertermin"] = str(answer.selected_options[0])
        return timeline

    # -------------------------------------------------------------------------
    # AENDERUNG 01.02.2026: UTDS Task-Derivation aus Briefing
    # -------------------------------------------------------------------------

    def _format_briefing_for_utds(self, briefing: ProjectBriefing) -> str:
        """Formatiert das Briefing fuer die UTDS Task-Derivation."""
        parts = [
            f"# Projektauftrag: {briefing.project_name}",
            f"\n## Projektziel\n{briefing.projektziel}",
            "\n## Scope - Enthalten"
        ]
        parts.extend([f"- {item}" for item in briefing.scope_enthalten])

        parts.append("\n## Technische Anforderungen")
        for key, value in briefing.technische_anforderungen.items():
            parts.append(f"- {key}: {value}")

        parts.append("\n## Erfolgskriterien")
        parts.extend([f"- {item}" for item in briefing.erfolgskriterien])

        if briefing.offene_punkte:
            parts.append("\n## Offene Punkte (zu klaeren)")
            parts.extend([f"- {item}" for item in briefing.offene_punkte])

        return "\n".join(parts)

    def derive_tasks_from_briefing(
        self,
        briefing: ProjectBriefing,
        config: Dict = None
    ) -> Optional['TaskDerivationResult']:
        """
        Leitet Tasks aus dem Discovery-Briefing ab.

        Args:
            briefing: Das generierte ProjectBriefing
            config: Optional Konfiguration fuer den TaskDeriver

        Returns:
            TaskDerivationResult oder None wenn UTDS nicht verfuegbar
        """
        if not UTDS_AVAILABLE:
            logger.warning("[DiscoverySession] UTDS nicht verfuegbar - Task-Derivation uebersprungen")
            return None

        try:
            self._log("UTDS_START", "Starte Task-Derivation aus Discovery-Briefing")

            # Briefing formatieren
            briefing_text = self._format_briefing_for_utds(briefing)

            # Kontext fuer UTDS
            context = {
                "tech_stack": briefing.technische_anforderungen.get("sprache", "python"),
                "is_initial": True,
                "discovery_session": True,
                "selected_agents": briefing.teilnehmende_agenten,
                "open_points_count": len(briefing.offene_punkte)
            }

            # TaskDeriver initialisieren (model_router zuerst, dann config)
            deriver = TaskDeriver(self.model_router, config or self.config)

            # Tasks ableiten
            result = deriver.derive_tasks(briefing_text, "discovery", context)

            if result.tasks:
                self._log("UTDS_COMPLETE", f"Abgeleitet: {result.total_tasks} Tasks aus Briefing")
                console.print(Panel.fit(
                    f"[bold green]Task-Derivation abgeschlossen[/bold green]\n\n"
                    f"Abgeleitete Tasks: {result.total_tasks}\n"
                    f"Nach Kategorie: {result.tasks_by_category}\n"
                    f"Nach Prioritaet: {result.tasks_by_priority}",
                    title="[bold cyan]UTDS[/bold cyan]",
                    border_style="cyan"
                ))
            else:
                self._log("UTDS_EMPTY", "Keine Tasks aus Briefing abgeleitet")

            return result

        except Exception as e:
            logger.error(f"[DiscoverySession] UTDS Fehler: {e}")
            self._log("UTDS_ERROR", str(e))
            return None

    def briefing_to_markdown(self, briefing: ProjectBriefing) -> str:
        """Konvertiert Briefing zu Markdown."""
        md = f"""# PROJEKTBRIEFING
==================

**Projekt:** {briefing.project_name}
**Auftraggeber:** {briefing.auftraggeber}
**Datum:** {briefing.datum}
**Teilnehmende Agenten:** {', '.join(briefing.teilnehmende_agenten)}

---

## PROJEKTZIEL

{briefing.projektziel}

---

## SCOPE

### Enthalten:
{chr(10).join(['- ' + item for item in briefing.scope_enthalten])}

### Ausgeschlossen:
{chr(10).join(['- ' + item for item in briefing.scope_ausgeschlossen])}

---

## DATENGRUNDLAGE

{chr(10).join(['- ' + item for item in briefing.datengrundlage])}

---

## TECHNISCHE ANFORDERUNGEN

{chr(10).join([f'- **{k}:** {v}' for k, v in briefing.technische_anforderungen.items()])}

---

## ERFOLGSKRITERIEN

{chr(10).join(['- ' + item for item in briefing.erfolgskriterien])}

---

## TIMELINE

{chr(10).join([f'- **{k}:** {v}' for k, v in briefing.timeline.items()])}

---

## OFFENE PUNKTE

{chr(10).join(['- ' + item for item in briefing.offene_punkte]) if briefing.offene_punkte else '- Keine offenen Punkte'}

---

*Generiert von AgentSmith Discovery Session*
"""
        return md

    # -------------------------------------------------------------------------
    # Hauptmethode: Vollstaendige Session ausfuehren
    # -------------------------------------------------------------------------

    def run(self, meta_orchestrator=None) -> ProjectBriefing:
        """Fuehrt die vollstaendige Discovery Session aus."""
        console.print(Panel.fit(
            "[bold cyan]DISCOVERY SESSION[/bold cyan]\n\n"
            "Willkommen zur strukturierten Projektaufnahme.\n"
            "Spezialisierte Experten werden dir gezielt Fragen stellen,\n"
            "um eine vollstaendige Projektspezifikation zu erarbeiten.",
            border_style="cyan"
        ))

        # Phase 1: Vision
        vision = self.phase_vision()

        # Phase 2: Team
        if meta_orchestrator:
            analysis = meta_orchestrator.analyze_prompt(vision)
        else:
            analysis = {
                "needs_ui": "ui" in vision.lower() or "web" in vision.lower(),
                "needs_data": "data" in vision.lower() or "daten" in vision.lower(),
                "needs_security": True
            }

        self.phase_team_setup(analysis)

        # Phase 3: Guided Questions
        self.phase_guided_questions({"vision": vision, "analysis": analysis})

        # Phase 4: Briefing
        briefing = self.generate_briefing()

        # Output anzeigen
        md = self.briefing_to_markdown(briefing)
        console.print(Panel(md, title="[bold green]Projektbriefing[/bold green]", border_style="green"))

        # AENDERUNG 01.02.2026: UTDS Task-Derivation aus Briefing
        if UTDS_AVAILABLE:
            task_result = self.derive_tasks_from_briefing(briefing)
            if task_result:
                briefing.derived_tasks = task_result  # Optional: Tasks im Briefing speichern
                self._log("PHASE_5_COMPLETE", f"UTDS: {task_result.total_tasks} Tasks abgeleitet")

        return briefing


# ============================================================================
# STANDALONE TEST
# ============================================================================

if __name__ == "__main__":
    session = DiscoverySession()
    briefing = session.run()

    with open("project_briefing.md", "w", encoding="utf-8") as f:
        f.write(session.briefing_to_markdown(briefing))

    console.print("[bold green]Briefing gespeichert: project_briefing.md[/bold green]")
