# -*- coding: utf-8 -*-
"""
Tests für MetaOrchestratorV2
"""

import pytest
from agents.meta_orchestrator_agent import MetaOrchestratorV2


class TestMetaOrchestratorV2:
    """Tests für die MetaOrchestratorV2 Klasse."""

    @pytest.fixture
    def orchestrator(self):
        """Erstellt eine MetaOrchestratorV2 Instanz."""
        return MetaOrchestratorV2()

    # ==================== analyze_prompt Tests ====================

    def test_analyze_prompt_web_project(self, orchestrator):
        """Test: Erkennung von Web-Projekten."""
        result = orchestrator.analyze_prompt("Erstelle eine HTML Webseite mit CSS")

        assert result["needs_ui"] is True
        assert "web" in result["project_type"]

    def test_analyze_prompt_database_project(self, orchestrator):
        """Test: Erkennung von Datenbank-Projekten."""
        result = orchestrator.analyze_prompt("Erstelle eine SQLite Datenbank mit Tabellen")

        assert result["needs_database"] is True
        assert "database" in result["project_type"]

    def test_analyze_prompt_data_project(self, orchestrator):
        """Test: Erkennung von Data-Projekten."""
        result = orchestrator.analyze_prompt("Analysiere diese CSV Daten und erstelle Statistiken")

        assert result["needs_data"] is True
        assert result["needs_research"] is True
        assert "data" in result["project_type"]

    def test_analyze_prompt_design_project(self, orchestrator):
        """Test: Erkennung von Design-Projekten."""
        result = orchestrator.analyze_prompt("Gestalte ein UI mit modernen Farben und Layout")

        assert result["needs_ui"] is True
        assert "design" in result["project_type"]

    def test_analyze_prompt_automation_project(self, orchestrator):
        """Test: Erkennung von Automatisierungs-Projekten."""
        result = orchestrator.analyze_prompt("Erstelle ein automatisiertes Script für Workflows")

        assert "automation" in result["project_type"]

    def test_analyze_prompt_general_project(self, orchestrator):
        """Test: Fallback auf 'general' bei unbekannten Prompts."""
        result = orchestrator.analyze_prompt("Mach etwas Cooles")

        assert "general" in result["project_type"]
        assert result["needs_ui"] is False
        assert result["needs_database"] is False

    def test_analyze_prompt_case_insensitive(self, orchestrator):
        """Test: Case-insensitive Erkennung."""
        result1 = orchestrator.analyze_prompt("HTML Webseite")
        result2 = orchestrator.analyze_prompt("html webseite")
        result3 = orchestrator.analyze_prompt("HtMl WeBsEiTe")

        assert result1["needs_ui"] == result2["needs_ui"] == result3["needs_ui"] is True

    def test_analyze_prompt_multiple_categories(self, orchestrator):
        """Test: Erkennung mehrerer Kategorien gleichzeitig."""
        result = orchestrator.analyze_prompt(
            "Erstelle eine HTML Webseite mit SQLite Datenbank und CSV Import"
        )

        assert "web" in result["project_type"]
        assert "database" in result["project_type"]
        assert "data" in result["project_type"]
        assert result["needs_ui"] is True
        assert result["needs_database"] is True
        assert result["needs_data"] is True

    def test_analyze_prompt_research_keyword(self, orchestrator):
        """Test: Erkennung von 'research' Keyword."""
        result = orchestrator.analyze_prompt("Research über Python Bibliotheken")

        assert result["needs_research"] is True

    # ==================== build_plan Tests ====================

    def test_build_plan_basic(self, orchestrator):
        """Test: Basis-Plan enthält immer techstack_architect, coder, reviewer, memory."""
        analysis = {
            "project_type": ["general"],
            "needs_ui": False,
            "needs_data": False,
            "needs_research": False,
            "needs_database": False
        }
        plan = orchestrator.build_plan(analysis)

        assert "techstack_architect" in plan
        assert "coder" in plan
        assert "reviewer" in plan
        assert "memory" in plan
        assert plan[-1] == "memory"  # Memory ist immer am Ende

    def test_build_plan_with_ui(self, orchestrator):
        """Test: UI-Projekte fügen designer und tester hinzu."""
        analysis = {
            "project_type": ["web"],
            "needs_ui": True,
            "needs_data": False,
            "needs_research": False,
            "needs_database": False
        }
        plan = orchestrator.build_plan(analysis)

        assert "designer" in plan
        assert "tester" in plan
        assert plan.index("designer") < plan.index("coder")

    def test_build_plan_with_research(self, orchestrator):
        """Test: Research-Projekte fügen researcher am Anfang hinzu."""
        analysis = {
            "project_type": ["data"],
            "needs_ui": False,
            "needs_data": True,
            "needs_research": True,
            "needs_database": False
        }
        plan = orchestrator.build_plan(analysis)

        assert "researcher" in plan
        assert plan[0] == "researcher"

    def test_build_plan_with_database(self, orchestrator):
        """Test: Database-Projekte fügen database_designer vor coder hinzu."""
        analysis = {
            "project_type": ["database"],
            "needs_ui": False,
            "needs_data": False,
            "needs_research": False,
            "needs_database": True
        }
        plan = orchestrator.build_plan(analysis)

        assert "database_designer" in plan
        assert plan.index("database_designer") < plan.index("coder")

    def test_build_plan_full_stack(self, orchestrator):
        """Test: Vollständiges Projekt mit allen Agenten."""
        analysis = {
            "project_type": ["web", "database", "data"],
            "needs_ui": True,
            "needs_data": True,
            "needs_research": True,
            "needs_database": True
        }
        plan = orchestrator.build_plan(analysis)

        assert "researcher" in plan
        assert "designer" in plan
        assert "database_designer" in plan
        assert "tester" in plan
        assert plan[0] == "researcher"
        assert plan[-1] == "memory"

    def test_build_plan_order(self, orchestrator):
        """Test: Korrekte Reihenfolge der Agenten."""
        analysis = {
            "project_type": ["web", "database"],
            "needs_ui": True,
            "needs_data": False,
            "needs_research": False,
            "needs_database": True
        }
        plan = orchestrator.build_plan(analysis)

        # Überprüfe relative Reihenfolge
        assert plan.index("techstack_architect") < plan.index("coder")
        assert plan.index("database_designer") < plan.index("coder")
        assert plan.index("coder") < plan.index("reviewer")

    # ==================== explain_plan Tests ====================

    def test_explain_plan_format(self, orchestrator):
        """Test: explain_plan gibt lesbare Beschreibung zurück."""
        plan = ["techstack_architect", "coder", "reviewer", "memory"]
        explanation = orchestrator.explain_plan(plan)

        assert "TechStack-Architect" in explanation
        assert "Coder-Agent" in explanation
        assert "Reviewer-Agent" in explanation
        assert "Memory-Agent" in explanation

    def test_explain_plan_bullet_points(self, orchestrator):
        """Test: Jeder Agent wird mit Bullet Point aufgelistet."""
        plan = ["coder", "reviewer"]
        explanation = orchestrator.explain_plan(plan)

        lines = explanation.strip().split("\n")
        assert all(line.startswith("•") for line in lines)

    # ==================== orchestrate Tests ====================

    def test_orchestrate_returns_complete_result(self, orchestrator):
        """Test: orchestrate gibt vollständiges Ergebnis zurück."""
        result = orchestrator.orchestrate("Erstelle eine HTML Webseite")

        assert "analysis" in result
        assert "plan" in result
        assert "explanation" in result

        assert isinstance(result["analysis"], dict)
        assert isinstance(result["plan"], list)
        assert isinstance(result["explanation"], str)

    def test_orchestrate_integration(self, orchestrator):
        """Test: Integration von analyze_prompt und build_plan."""
        result = orchestrator.orchestrate(
            "Erstelle eine Webseite mit Datenbank und CSV-Import"
        )

        # Analyse sollte alle Kategorien erkennen
        assert result["analysis"]["needs_ui"] is True
        assert result["analysis"]["needs_database"] is True
        assert result["analysis"]["needs_data"] is True

        # Plan sollte entsprechende Agenten enthalten
        assert "designer" in result["plan"]
        assert "database_designer" in result["plan"]
        assert "researcher" in result["plan"]

    # ==================== available_agents Tests ====================

    def test_available_agents_completeness(self, orchestrator):
        """Test: Alle erwarteten Agenten sind definiert."""
        expected_agents = [
            "coder", "reviewer", "designer", "tester",
            "researcher", "database_designer", "techstack_architect", "memory"
        ]

        for agent in expected_agents:
            assert agent in orchestrator.available_agents

    def test_available_agents_have_descriptions(self, orchestrator):
        """Test: Alle Agenten haben Beschreibungen."""
        for agent, description in orchestrator.available_agents.items():
            assert len(description) > 0
            assert isinstance(description, str)
