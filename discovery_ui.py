# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 01.02.2026
Version: 1.0
Beschreibung: Guided Choice UI fuer Discovery Session.
              Extrahiert aus discovery_session.py (Regel 1: Max 500 Zeilen)
"""

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.table import Table
from rich.text import Text
from rich.box import ROUNDED

from discovery_models import AnswerMode, GuidedQuestion, Answer


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
