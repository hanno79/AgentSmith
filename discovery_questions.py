# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 01.02.2026
Version: 1.0
Beschreibung: Frage-Templates fuer Discovery Session.
              Extrahiert aus discovery_session.py (Regel 1: Max 500 Zeilen)
"""

from typing import Dict, List

from discovery_models import AnswerMode, AnswerOption, GuidedQuestion


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
