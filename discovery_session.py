# -*- coding: utf-8 -*-
"""
Author: rahn / Claude
Datum: 29.01.2026
Version: 1.0
Beschreibung: Discovery Session - Strukturierter Projektauftakt-Dialog.
              Implementiert das Guided Choice System fuer interaktive Anforderungserhebung.
"""

import os
import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.table import Table
from rich.text import Text
from rich.box import ROUNDED

# Memory-Agent Integration
try:
    from agents.memory_agent import load_memory, get_lessons_for_prompt
    MEMORY_AVAILABLE = True
except ImportError:
    MEMORY_AVAILABLE = False

console = Console()


# ============================================================================
# ENUMS & DATA CLASSES
# ============================================================================

class AnswerMode(Enum):
    """Modi fuer Antwortoptionen."""
    SINGLE = "single"           # Eine Option waehlen
    MULTIPLE = "multiple"       # Mehrere Optionen kombinieren
    CUSTOM = "custom"           # Freitext
    COMBINATION = "combination" # Option + eigene Ergaenzung
    SKIP = "skip"              # Wird als offener Punkt notiert


class SessionPhase(Enum):
    """Phasen der Discovery Session."""
    VISION = "vision"           # Phase 1: Freie Eingabe
    TEAM_SETUP = "team_setup"   # Phase 2: Agenten-Auswahl
    GUIDED_QA = "guided_qa"     # Phase 3: Geführte Fragen
    SUMMARY = "summary"         # Zusammenfassung
    BRIEFING = "briefing"       # Output generieren


@dataclass
class AnswerOption:
    """Eine Antwortoption mit Empfehlung."""
    text: str
    value: Any
    is_recommended: bool = False
    reason: Optional[str] = None
    source: Optional[str] = None  # "memory", "researcher", "standard"


@dataclass
class GuidedQuestion:
    """Eine geführte Frage mit Optionen."""
    agent: str
    question: str
    options: List[AnswerOption]
    mode: AnswerMode = AnswerMode.SINGLE
    required: bool = True
    category: str = "general"
    help_text: Optional[str] = None


@dataclass
class Answer:
    """Eine Antwort auf eine GuidedQuestion."""
    question_id: str
    agent: str
    selected_options: List[Any]
    custom_text: Optional[str] = None
    skipped: bool = False
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class ProjectBriefing:
    """Das generierte Projektbriefing."""
    project_name: str
    auftraggeber: str
    datum: str
    teilnehmende_agenten: List[str]
    projektziel: str
    scope_enthalten: List[str]
    scope_ausgeschlossen: List[str]
    datengrundlage: List[str]
    technische_anforderungen: Dict[str, Any]
    erfolgskriterien: List[str]
    timeline: Dict[str, str]
    offene_punkte: List[str]


# ============================================================================
# MEMORY-BASED OPTION GENERATOR
# ============================================================================

class OptionGenerator:
    """Generiert intelligente Optionen aus Memory, Researcher und Standards."""

    def __init__(self, memory_path: str = None):
        self.memory_path = memory_path
        self._memory_cache = None

    def _load_memory(self) -> Dict:
        """Laedt Memory-Daten mit Caching."""
        if self._memory_cache is not None:
            return self._memory_cache

        if not MEMORY_AVAILABLE or not self.memory_path:
            return {"history": [], "lessons": []}

        try:
            self._memory_cache = load_memory(self.memory_path)
            return self._memory_cache
        except Exception:
            return {"history": [], "lessons": []}

    def enhance_options_from_memory(
        self,
        base_options: List['AnswerOption'],
        context: Dict,
        category: str
    ) -> List['AnswerOption']:
        """
        Erweitert Basis-Optionen mit Vorschlaegen aus dem Memory.

        Prioritaet:
        1. Memory-Agent (hoechste) - "In deinem letzten Projekt..."
        2. Researcher - Best Practices aus Web
        3. Vordefinierte Standards (Fallback)
        """
        memory = self._load_memory()
        enhanced = list(base_options)

        # Suche relevante Lessons im Memory
        lessons = memory.get("lessons", [])
        history = memory.get("history", [])

        for lesson in lessons:
            tags = lesson.get("tags", [])

            # Pruefe ob Lesson zum Kontext passt
            if category in tags or any(t in str(context).lower() for t in tags):
                # Erstelle Option aus Lesson
                action = lesson.get("action", "")
                if action and len(action) > 10:
                    # Pruefe ob aehnliche Option bereits existiert
                    exists = any(action.lower() in opt.text.lower() for opt in enhanced)
                    if not exists:
                        enhanced.insert(0, AnswerOption(
                            text=f"[Memory] {action[:80]}...",
                            value=f"memory_{lesson.get('pattern', 'unknown')[:30]}",
                            is_recommended=True,
                            reason=f"Basierend auf {lesson.get('count', 1)} frueheren Erfahrungen",
                            source="memory"
                        ))
                        break  # Nur eine Memory-Option pro Frage

        # Analysiere History fuer haeufige Patterns
        if history and len(history) >= 3:
            # Extrahiere Tech-Stack aus letzten Projekten
            recent_tech = self._extract_recent_tech(history[-5:])
            if recent_tech and category == "technical":
                for tech in recent_tech[:2]:
                    exists = any(tech.lower() in opt.text.lower() for opt in enhanced)
                    if not exists:
                        enhanced.insert(1, AnswerOption(
                            text=f"[Zuletzt verwendet] {tech}",
                            value=f"recent_{tech.lower()}",
                            is_recommended=False,
                            reason="In frueheren Projekten verwendet",
                            source="memory"
                        ))

        return enhanced[:7]  # Max 7 Optionen

    def _extract_recent_tech(self, history: List[Dict]) -> List[str]:
        """Extrahiert Tech-Stack aus History."""
        tech_keywords = ["python", "javascript", "react", "flask", "fastapi",
                        "django", "node", "typescript", "vue", "angular"]
        found = []

        for entry in history:
            code = entry.get("coder_output_preview", "").lower()
            for tech in tech_keywords:
                if tech in code and tech not in found:
                    found.append(tech.capitalize())

        return found

    def get_context_recommendations(self, vision: str) -> Dict[str, str]:
        """Analysiert Vision und gibt kontextbasierte Empfehlungen."""
        recommendations = {}
        vision_lower = vision.lower()

        # Sprach-Empfehlungen
        if any(w in vision_lower for w in ["data", "daten", "analyse", "ml", "ki"]):
            recommendations["language"] = "python"
            recommendations["language_reason"] = "Beste Wahl fuer Datenanalyse und ML"
        elif any(w in vision_lower for w in ["web", "frontend", "ui", "react"]):
            recommendations["language"] = "javascript"
            recommendations["language_reason"] = "Standard fuer Web-Frontends"
        elif any(w in vision_lower for w in ["api", "backend", "server"]):
            recommendations["language"] = "python"
            recommendations["language_reason"] = "FastAPI/Flask ideal fuer APIs"

        # Datenbank-Empfehlungen
        if any(w in vision_lower for w in ["user", "nutzer", "login", "auth"]):
            recommendations["database"] = "postgresql"
            recommendations["database_reason"] = "Robust fuer Benutzerdaten"
        elif any(w in vision_lower for w in ["dokument", "json", "flexibel"]):
            recommendations["database"] = "mongodb"
            recommendations["database_reason"] = "Flexibles Schema"

        return recommendations


# ============================================================================
# QUESTION TEMPLATES
# ============================================================================

class QuestionTemplates:
    """Vordefinierte Frage-Templates pro Agent-Rolle."""

    @staticmethod
    def get_analyst_questions(context: Dict) -> List[GuidedQuestion]:
        """Fragen vom Analyst: Warum? Kontext? Stakeholder?"""
        return [
            GuidedQuestion(
                agent="Analyst",
                question="Was ist der primaere Geschaeftszweck dieses Projekts?",
                category="context",
                options=[
                    AnswerOption("Interne Prozessoptimierung", "internal_optimization"),
                    AnswerOption("Kundenprodukt / Externe Nutzung", "customer_facing", is_recommended=True, reason="Hoehere Qualitaetsanforderungen"),
                    AnswerOption("Forschung / Prototyp", "research"),
                    AnswerOption("Datenanalyse / Reporting", "analytics"),
                    AnswerOption("Eigene Angabe", "custom"),
                ],
                help_text="Hilft uns, die richtige Balance zwischen Geschwindigkeit und Qualitaet zu finden."
            ),
            GuidedQuestion(
                agent="Analyst",
                question="Wer sind die Hauptnutzer des Systems?",
                category="stakeholders",
                mode=AnswerMode.MULTIPLE,
                options=[
                    AnswerOption("Technische Mitarbeiter", "technical"),
                    AnswerOption("Nicht-technische Endnutzer", "non_technical", is_recommended=True, reason="Erfordert bessere UX"),
                    AnswerOption("Administratoren", "admins"),
                    AnswerOption("Externe Kunden", "external"),
                    AnswerOption("Nur ich selbst", "self"),
                ],
                help_text="Beeinflusst UI-Komplexitaet und Dokumentationstiefe."
            ),
            GuidedQuestion(
                agent="Analyst",
                question="Gibt es ein bestehendes System, das ersetzt oder erweitert wird?",
                category="context",
                options=[
                    AnswerOption("Nein, Neuentwicklung", "greenfield", is_recommended=True),
                    AnswerOption("Ja, bestehendes System ersetzen", "replacement"),
                    AnswerOption("Ja, bestehendes System erweitern", "extension"),
                    AnswerOption("Weiss ich noch nicht", "unknown"),
                ],
                required=False
            ),
        ]

    @staticmethod
    def get_data_researcher_questions(context: Dict) -> List[GuidedQuestion]:
        """Fragen vom Data Researcher: Welche Daten? Woher? Qualitaet?"""
        return [
            GuidedQuestion(
                agent="Data Researcher",
                question="Welche Datenquellen werden benoetigt?",
                category="data",
                mode=AnswerMode.MULTIPLE,
                options=[
                    AnswerOption("Lokale Dateien (CSV, JSON, etc.)", "local_files"),
                    AnswerOption("Datenbank (SQL, NoSQL)", "database"),
                    AnswerOption("REST API / Web Services", "api", is_recommended=True, reason="Flexibel und erweiterbar"),
                    AnswerOption("Web Scraping", "scraping"),
                    AnswerOption("Manuelle Eingabe", "manual"),
                    AnswerOption("Keine Daten noetig", "none"),
                ],
            ),
            GuidedQuestion(
                agent="Data Researcher",
                question="Wie gross ist das erwartete Datenvolumen?",
                category="data",
                options=[
                    AnswerOption("Klein (< 1.000 Datensaetze)", "small"),
                    AnswerOption("Mittel (1.000 - 100.000)", "medium", is_recommended=True),
                    AnswerOption("Gross (100.000 - 1 Mio.)", "large"),
                    AnswerOption("Sehr gross (> 1 Mio.)", "xlarge"),
                    AnswerOption("Unbekannt", "unknown"),
                ],
                help_text="Beeinflusst Datenbankwahl und Architektur."
            ),
        ]

    @staticmethod
    def get_coder_questions(context: Dict) -> List[GuidedQuestion]:
        """Fragen vom Coder: Technische Rahmenbedingungen?"""
        return [
            GuidedQuestion(
                agent="Coder",
                question="Gibt es Vorgaben fuer die Programmiersprache?",
                category="technical",
                options=[
                    AnswerOption("Python", "python", is_recommended=True, reason="Flexibel, grosse Community"),
                    AnswerOption("JavaScript / TypeScript", "javascript"),
                    AnswerOption("Java", "java"),
                    AnswerOption("C# / .NET", "csharp"),
                    AnswerOption("Keine Vorgabe - beste Wahl treffen", "auto"),
                ],
            ),
            GuidedQuestion(
                agent="Coder",
                question="Welche Deployment-Umgebung ist geplant?",
                category="technical",
                options=[
                    AnswerOption("Lokale Ausfuehrung", "local", is_recommended=True, reason="Einfachster Start"),
                    AnswerOption("Cloud (AWS, Azure, GCP)", "cloud"),
                    AnswerOption("Docker Container", "docker"),
                    AnswerOption("Kubernetes", "kubernetes"),
                    AnswerOption("Serverless", "serverless"),
                    AnswerOption("Noch unklar", "unknown"),
                ],
            ),
            GuidedQuestion(
                agent="Coder",
                question="Soll das Projekt Open Source sein?",
                category="technical",
                options=[
                    AnswerOption("Nein, proprietaer", "proprietary"),
                    AnswerOption("Ja, MIT Lizenz", "mit", is_recommended=True, reason="Permissiv und weit verbreitet"),
                    AnswerOption("Ja, Apache 2.0", "apache"),
                    AnswerOption("Ja, GPL", "gpl"),
                    AnswerOption("Noch nicht entschieden", "unknown"),
                ],
                required=False
            ),
        ]

    @staticmethod
    def get_tester_questions(context: Dict) -> List[GuidedQuestion]:
        """Fragen vom Tester: Erfolgskriterien? Validierung?"""
        return [
            GuidedQuestion(
                agent="Tester",
                question="Welche Test-Abdeckung wird erwartet?",
                category="quality",
                options=[
                    AnswerOption("Minimal (nur kritische Pfade)", "minimal"),
                    AnswerOption("Standard (Unit + Integration)", "standard", is_recommended=True),
                    AnswerOption("Umfassend (inkl. E2E)", "comprehensive"),
                    AnswerOption("Keine automatisierten Tests", "none"),
                ],
                help_text="Beeinflusst Entwicklungszeit und Wartbarkeit."
            ),
            GuidedQuestion(
                agent="Tester",
                question="Wie wird der Erfolg des Projekts gemessen?",
                category="quality",
                mode=AnswerMode.MULTIPLE,
                options=[
                    AnswerOption("Funktionalitaet vollstaendig", "functionality"),
                    AnswerOption("Performance-Ziele erreicht", "performance"),
                    AnswerOption("Benutzerakzeptanz", "user_acceptance", is_recommended=True),
                    AnswerOption("Code-Qualitaet (Reviews bestanden)", "code_quality"),
                    AnswerOption("Eigene Kriterien", "custom"),
                ],
            ),
        ]

    @staticmethod
    def get_designer_questions(context: Dict) -> List[GuidedQuestion]:
        """Fragen vom Designer: UI/UX Anforderungen?"""
        return [
            GuidedQuestion(
                agent="Designer",
                question="Welchen Stil soll die Benutzeroberflaeche haben?",
                category="design",
                options=[
                    AnswerOption("Modern / Minimalistisch", "modern", is_recommended=True, reason="Zeitlos und benutzerfreundlich"),
                    AnswerOption("Corporate / Professionell", "corporate"),
                    AnswerOption("Verspielt / Kreativ", "playful"),
                    AnswerOption("Technisch / Dashboard", "technical"),
                    AnswerOption("Keine UI (CLI/API only)", "none"),
                ],
            ),
            GuidedQuestion(
                agent="Designer",
                question="Auf welchen Geraeten soll die Anwendung laufen?",
                category="design",
                mode=AnswerMode.MULTIPLE,
                options=[
                    AnswerOption("Desktop Browser", "desktop", is_recommended=True),
                    AnswerOption("Mobile (Smartphone)", "mobile"),
                    AnswerOption("Tablet", "tablet"),
                    AnswerOption("Native App", "native"),
                ],
            ),
        ]

    @staticmethod
    def get_planner_questions(context: Dict) -> List[GuidedQuestion]:
        """Fragen vom Planner: Timeline? Lieferformat?"""
        return [
            GuidedQuestion(
                agent="Planner",
                question="Wie ist der gewuenschte Zeitrahmen?",
                category="timeline",
                options=[
                    AnswerOption("So schnell wie moeglich", "asap"),
                    AnswerOption("1-2 Wochen", "short", is_recommended=True),
                    AnswerOption("1 Monat", "medium"),
                    AnswerOption("3+ Monate", "long"),
                    AnswerOption("Kein fester Termin", "flexible"),
                ],
            ),
            GuidedQuestion(
                agent="Planner",
                question="In welchem Format soll das Ergebnis geliefert werden?",
                category="delivery",
                mode=AnswerMode.MULTIPLE,
                options=[
                    AnswerOption("Quellcode (Git Repository)", "source", is_recommended=True),
                    AnswerOption("Dokumentation (README, Wiki)", "docs"),
                    AnswerOption("Lauffaehiges Deployment", "deployed"),
                    AnswerOption("Docker Image", "docker"),
                    AnswerOption("Installationspaket", "package"),
                ],
            ),
        ]

    @staticmethod
    def get_security_questions(context: Dict) -> List[GuidedQuestion]:
        """Fragen vom Security Agent: Sicherheitsanforderungen?"""
        return [
            GuidedQuestion(
                agent="Security",
                question="Welches Sicherheitsniveau wird benoetigt?",
                category="security",
                options=[
                    AnswerOption("Basis (Standard-Praktiken)", "basic", is_recommended=True),
                    AnswerOption("Erhoeht (Authentifizierung, Verschluesselung)", "elevated"),
                    AnswerOption("Hoch (Compliance, Audit-Logs)", "high"),
                    AnswerOption("Kritisch (Finanz/Gesundheit)", "critical"),
                ],
                help_text="Beeinflusst Architektur und Entwicklungsaufwand."
            ),
            GuidedQuestion(
                agent="Security",
                question="Werden sensible Daten verarbeitet?",
                category="security",
                mode=AnswerMode.MULTIPLE,
                options=[
                    AnswerOption("Keine sensiblen Daten", "none"),
                    AnswerOption("Personendaten (DSGVO relevant)", "personal", is_recommended=True, reason="Erfordert Datenschutz-Massnahmen"),
                    AnswerOption("Finanzdaten", "financial"),
                    AnswerOption("Gesundheitsdaten", "health"),
                    AnswerOption("Geschaeftsgeheimnisse", "confidential"),
                ],
            ),
        ]


# ============================================================================
# GUIDED CHOICE UI
# ============================================================================

class GuidedChoiceUI:
    """Rich Console UI fuer Guided Choice Interaktion."""

    def __init__(self, console: Console = None):
        self.console = console or Console()

    def display_question(self, question: GuidedQuestion) -> Answer:
        """Zeigt eine Frage mit Optionen an und sammelt Antwort."""

        # Header mit Agent-Name
        agent_colors = {
            "Analyst": "blue",
            "Data Researcher": "green",
            "Coder": "yellow",
            "Tester": "magenta",
            "Designer": "cyan",
            "Planner": "red",
            "Security": "bright_red",
        }
        color = agent_colors.get(question.agent, "white")

        # Panel mit Frage
        question_text = Text()
        question_text.append(f"\n{question.question}\n", style="bold")

        if question.help_text:
            question_text.append(f"\n{question.help_text}\n", style="dim italic")

        self.console.print(Panel(
            question_text,
            title=f"[bold {color}]{question.agent} fragt[/bold {color}]",
            border_style=color,
            box=ROUNDED
        ))

        # Optionen anzeigen
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Nr", style="dim", width=4)
        table.add_column("Option", style="white")
        table.add_column("Info", style="dim italic")

        for i, opt in enumerate(question.options, 1):
            marker = "[bold green]*[/bold green]" if opt.is_recommended else " "
            info = ""
            if opt.is_recommended and opt.reason:
                info = f"[green]EMPFOHLEN: {opt.reason}[/green]"
            elif opt.source:
                info = f"[dim](Quelle: {opt.source})[/dim]"

            table.add_row(f"{marker}{i}", opt.text, info)

        # Extra-Optionen
        table.add_row("", "", "")
        table.add_row("0", "[dim]Eigene Angabe eingeben[/dim]", "")
        if not question.required:
            table.add_row("s", "[dim]Ueberspringen (spaeter klaeren)[/dim]", "")

        self.console.print(table)
        self.console.print()

        # Eingabe sammeln
        if question.mode == AnswerMode.MULTIPLE:
            self.console.print("[dim]Mehrere Optionen moeglich (z.B. 1,3,4)[/dim]")

        while True:
            choice = Prompt.ask(
                "[bold]Deine Wahl[/bold]",
                default="1" if question.options and question.options[0].is_recommended else None
            )

            # Parse Eingabe
            if choice.lower() == 's' and not question.required:
                return Answer(
                    question_id=f"{question.agent}_{question.category}",
                    agent=question.agent,
                    selected_options=[],
                    skipped=True
                )

            if choice == '0':
                custom = Prompt.ask("[bold]Eigene Angabe[/bold]")
                return Answer(
                    question_id=f"{question.agent}_{question.category}",
                    agent=question.agent,
                    selected_options=[],
                    custom_text=custom
                )

            try:
                if question.mode == AnswerMode.MULTIPLE:
                    indices = [int(x.strip()) for x in choice.split(',')]
                else:
                    indices = [int(choice)]

                selected = []
                for idx in indices:
                    if 1 <= idx <= len(question.options):
                        selected.append(question.options[idx - 1].value)
                    else:
                        raise ValueError(f"Ungueltige Option: {idx}")

                return Answer(
                    question_id=f"{question.agent}_{question.category}",
                    agent=question.agent,
                    selected_options=selected
                )

            except (ValueError, IndexError) as e:
                self.console.print(f"[red]Ungueltige Eingabe: {e}. Bitte erneut versuchen.[/red]")

    def display_summary(self, agent: str, summary_text: str) -> bool:
        """Zeigt Zusammenfassung und fragt nach Bestaetigung."""

        self.console.print(Panel(
            summary_text,
            title=f"[bold cyan]{agent} fasst zusammen[/bold cyan]",
            border_style="cyan",
            box=ROUNDED
        ))

        return Confirm.ask("[bold]Ist das korrekt?[/bold]", default=True)


# ============================================================================
# DISCOVERY SESSION CONTROLLER
# ============================================================================

class DiscoverySession:
    """Hauptcontroller fuer die Discovery Session."""

    def __init__(self, config: Dict = None, memory_path: str = None):
        self.config = config or {}
        self.memory_path = memory_path
        self.ui = GuidedChoiceUI()
        self.option_generator = OptionGenerator(memory_path)  # Memory-Integration
        self.answers: List[Answer] = []
        self.selected_agents: List[str] = []
        self.vision: str = ""
        self.open_points: List[str] = []
        self.context_recommendations: Dict[str, str] = {}  # Kontext-Empfehlungen
        self.on_log: Optional[Callable] = None  # Callback fuer Logging

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

        # Standard-Agenten
        agents = ["Analyst", "Coder", "Tester", "Planner"]

        # Bedingte Agenten
        if analysis.get("needs_ui", False):
            agents.insert(2, "Designer")

        if analysis.get("needs_data", False) or analysis.get("categories", {}).get("data", False):
            agents.insert(1, "Data Researcher")

        if analysis.get("needs_security", True):  # Default: Ja
            agents.append("Security")

        self.selected_agents = agents

        # Anzeige
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

        # Generiere Kontext-Empfehlungen aus Vision
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

        # Fragen pro Agent
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
                    # Memory-Integration: Erweitere Optionen mit Memory-Vorschlaegen
                    enhanced_options = self.option_generator.enhance_options_from_memory(
                        question.options,
                        {"vision": self.vision, "agent": agent, **context},
                        question.category
                    )
                    question.options = enhanced_options

                    # Kontext-Empfehlungen anwenden
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

                # Zusammenfassung nach jeder Runde
                summary = self._generate_agent_summary(agent)
                confirmed = self.ui.display_summary(agent, summary)

                if not confirmed:
                    # Korrektur-Loop: Letzte Fragen dieses Agenten wiederholen
                    console.print("[yellow]Verstanden - lass uns die Punkte korrigieren...[/yellow]")
                    agent_answers = [a for a in self.answers if a.agent == agent]

                    for i, old_answer in enumerate(agent_answers):
                        if Confirm.ask(f"[dim]Moechtest du '{old_answer.question_id}' aendern?[/dim]", default=False):
                            # Frage erneut stellen
                            matching_q = [q for q in questions if f"{agent}_{q.category}" == old_answer.question_id]
                            if matching_q:
                                new_answer = self.ui.display_question(matching_q[0])
                                # Alte Antwort ersetzen
                                idx = self.answers.index(old_answer)
                                self.answers[idx] = new_answer

                    # Erneute Zusammenfassung
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

        # Antworten auswerten
        tech_answers = [a for a in self.answers if "technical" in a.question_id or "Coder" in a.agent]
        data_answers = [a for a in self.answers if "data" in a.question_id or "Data" in a.agent]

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
        # Einfache Heuristik: Erste 3-5 Worte
        words = self.vision.split()[:5]
        return "_".join(words).lower().replace(".", "").replace(",", "")[:50]

    def _extract_scope_included(self) -> List[str]:
        """Extrahiert enthaltenen Scope aus Antworten."""
        included = []
        for answer in self.answers:
            if not answer.skipped and answer.selected_options:
                included.extend([str(v) for v in answer.selected_options])
        return included[:10]  # Max 10 Items

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

        # Phase 2: Team (nutzt Meta-Orchestrator falls vorhanden)
        if meta_orchestrator:
            analysis = meta_orchestrator.analyze_prompt(vision)
        else:
            # Fallback: Einfache Analyse
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

        return briefing


# ============================================================================
# STANDALONE TEST
# ============================================================================

if __name__ == "__main__":
    session = DiscoverySession()
    briefing = session.run()

    # Speichern
    with open("project_briefing.md", "w", encoding="utf-8") as f:
        f.write(session.briefing_to_markdown(briefing))

    console.print("[bold green]Briefing gespeichert: project_briefing.md[/bold green]")
