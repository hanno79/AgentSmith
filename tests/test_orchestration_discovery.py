# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 14.02.2026
Version: 1.0
Beschreibung: Tests fuer backend/orchestration_discovery.py — format_briefing_context,
              extract_project_name_from_briefing, extract_project_goal_from_briefing.
"""

import pytest

from backend.orchestration_discovery import (
    format_briefing_context,
    _format_briefing_context_impl,
    extract_project_name_from_briefing,
    extract_project_goal_from_briefing,
)


# =========================================================================
# TestFormatBriefingContext
# =========================================================================

class TestFormatBriefingContext:
    """Tests fuer format_briefing_context()."""

    def test_none_gibt_leer(self):
        """None-Briefing ergibt leeren String."""
        assert format_briefing_context(None) == ""

    def test_leeres_dict_gibt_leer(self):
        """Leeres Dict ergibt leeren String."""
        assert format_briefing_context({}) == ""

    def test_grundstruktur_mit_goal(self):
        """Briefing mit Goal enthaelt Projektziel."""
        briefing = {"goal": "Todo-App bauen"}
        result = format_briefing_context(briefing)
        assert "Todo-App bauen" in result
        assert "PROJEKTBRIEFING" in result

    def test_tech_requirements_language(self):
        """Programmiersprache wird angezeigt."""
        briefing = {
            "goal": "App",
            "techRequirements": {"language": "Python", "deployment": "docker"}
        }
        result = format_briefing_context(briefing)
        assert "Python" in result
        assert "docker" in result

    def test_tech_requirements_nicht_dict(self):
        """Nicht-Dict techRequirements wird ignoriert."""
        briefing = {"goal": "App", "techRequirements": "invalid"}
        result = format_briefing_context(briefing)
        assert "auto" in result  # Default

    def test_agents_liste(self):
        """Agenten-Liste wird angezeigt."""
        briefing = {"goal": "App", "agents": ["coder", "tester", "reviewer"]}
        result = format_briefing_context(briefing)
        assert "coder" in result
        assert "tester" in result

    def test_agents_nicht_liste(self):
        """Nicht-Liste agents wird als 'Nicht definiert' angezeigt."""
        briefing = {"goal": "App", "agents": "invalid"}
        result = format_briefing_context(briefing)
        assert "Nicht definiert" in result

    def test_agents_mit_nicht_strings(self):
        """Agents mit Nicht-Strings wird als 'Nicht definiert' behandelt."""
        briefing = {"goal": "App", "agents": [1, 2, 3]}
        result = format_briefing_context(briefing)
        assert "Nicht definiert" in result

    def test_answers_mit_selected_values(self):
        """Answers mit selectedValues werden angezeigt."""
        briefing = {
            "goal": "App",
            "answers": [
                {
                    "agent": "Coder",
                    "selectedValues": ["React", "TypeScript"],
                    "skipped": False,
                }
            ]
        }
        result = format_briefing_context(briefing)
        assert "Coder" in result
        assert "React" in result

    def test_answers_skipped_werden_ignoriert(self):
        """Uebersprungene Answers werden nicht angezeigt."""
        briefing = {
            "goal": "App",
            "answers": [
                {
                    "agent": "Coder",
                    "selectedValues": ["React"],
                    "skipped": True,
                }
            ]
        }
        result = format_briefing_context(briefing)
        assert "React" not in result

    def test_answers_mit_custom_text(self):
        """CustomText wird angezeigt wenn keine selectedValues."""
        briefing = {
            "goal": "App",
            "answers": [
                {
                    "agent": "Designer",
                    "selectedValues": [],
                    "customText": "Minimalistisch",
                    "skipped": False,
                }
            ]
        }
        result = format_briefing_context(briefing)
        assert "Minimalistisch" in result

    def test_answers_nicht_liste(self):
        """Nicht-Liste answers wird ignoriert."""
        briefing = {"goal": "App", "answers": "invalid"}
        result = format_briefing_context(briefing)
        assert "PROJEKTBRIEFING" in result

    def test_answers_nicht_dict_eintrag(self):
        """Nicht-Dict Answer-Eintrag wird uebersprungen."""
        briefing = {"goal": "App", "answers": ["invalid", 42]}
        result = format_briefing_context(briefing)
        assert "PROJEKTBRIEFING" in result

    def test_answer_agent_none(self):
        """Agent=None wird als 'Unbekannt' behandelt."""
        briefing = {
            "goal": "App",
            "answers": [
                {"agent": None, "selectedValues": ["Vue"], "skipped": False}
            ]
        }
        result = format_briefing_context(briefing)
        assert "Unbekannt" in result
        assert "Vue" in result

    def test_answer_selected_values_nicht_liste(self):
        """Nicht-Liste selectedValues wird als leere Liste behandelt."""
        briefing = {
            "goal": "App",
            "answers": [
                {"agent": "Coder", "selectedValues": "invalid", "customText": "Fallback", "skipped": False}
            ]
        }
        result = format_briefing_context(briefing)
        assert "Fallback" in result

    def test_open_points(self):
        """Offene Punkte werden angezeigt."""
        briefing = {
            "goal": "App",
            "openPoints": ["Performance testen", "Security pruefen"]
        }
        result = format_briefing_context(briefing)
        assert "Offene Punkte" in result
        assert "Performance testen" in result
        assert "Security pruefen" in result

    def test_open_points_nicht_liste(self):
        """Nicht-Liste openPoints wird ignoriert."""
        briefing = {"goal": "App", "openPoints": "invalid"}
        result = format_briefing_context(briefing)
        assert "Offene Punkte" not in result

    def test_open_points_leer(self):
        """Leere openPoints-Liste zeigt keinen Abschnitt."""
        briefing = {"goal": "App", "openPoints": []}
        result = format_briefing_context(briefing)
        assert "Offene Punkte" not in result

    def test_exception_gibt_leer(self):
        """Exception in Implementierung ergibt leeren String."""
        # Nicht-Dict Wert loest in _format_briefing_context_impl() Return "" aus
        assert format_briefing_context("kein_dict") == ""

    def test_vollstaendiges_briefing(self):
        """Vollstaendiges Briefing mit allen Feldern."""
        briefing = {
            "goal": "E-Commerce Shop",
            "techRequirements": {"language": "JavaScript", "deployment": "vercel"},
            "agents": ["coder", "designer", "tester"],
            "answers": [
                {"agent": "Designer", "selectedValues": ["Modern", "Dark"], "skipped": False},
                {"agent": "Tester", "customText": "Playwright nutzen", "skipped": False},
            ],
            "openPoints": ["Payment-Gateway klaeren"],
        }
        result = format_briefing_context(briefing)
        assert "E-Commerce Shop" in result
        assert "JavaScript" in result
        assert "vercel" in result
        assert "coder" in result
        assert "Modern" in result
        assert "Playwright nutzen" in result
        assert "Payment-Gateway" in result


# =========================================================================
# TestFormatBriefingContextImpl
# =========================================================================

class TestFormatBriefingContextImpl:
    """Tests fuer _format_briefing_context_impl()."""

    def test_nicht_dict_gibt_leer(self):
        """Nicht-Dict Input ergibt leeren String."""
        assert _format_briefing_context_impl("string") == ""
        assert _format_briefing_context_impl(42) == ""
        assert _format_briefing_context_impl([]) == ""

    def test_goal_default(self):
        """Fehlendes Goal zeigt 'Nicht definiert'."""
        result = _format_briefing_context_impl({"noGoal": True})
        assert "Nicht definiert" in result

    def test_custom_text_none(self):
        """customText=None wird als leerer String behandelt."""
        briefing = {
            "answers": [
                {"agent": "X", "selectedValues": [], "customText": None, "skipped": False}
            ]
        }
        result = _format_briefing_context_impl(briefing)
        # Keine values, kein customText → kein Eintrag fuer diesen Agent
        assert "X:" not in result


# =========================================================================
# TestExtractProjectName
# =========================================================================

class TestExtractProjectName:
    """Tests fuer extract_project_name_from_briefing()."""

    def test_none_gibt_unbenannt(self):
        """None ergibt 'unbenannt'."""
        assert extract_project_name_from_briefing(None) == "unbenannt"

    def test_leeres_dict_gibt_unbenannt(self):
        """Leeres Dict ergibt 'unbenannt'."""
        assert extract_project_name_from_briefing({}) == "unbenannt"

    def test_nicht_dict_gibt_unbenannt(self):
        """Nicht-Dict ergibt 'unbenannt'."""
        assert extract_project_name_from_briefing("string") == "unbenannt"
        assert extract_project_name_from_briefing(42) == "unbenannt"

    def test_mit_project_name(self):
        """ProjectName wird korrekt extrahiert."""
        assert extract_project_name_from_briefing({"projectName": "MeinProjekt"}) == "MeinProjekt"

    def test_ohne_project_name_key(self):
        """Fehlendes projectName ergibt 'unbenannt'."""
        assert extract_project_name_from_briefing({"goal": "App"}) == "unbenannt"


# =========================================================================
# TestExtractProjectGoal
# =========================================================================

class TestExtractProjectGoal:
    """Tests fuer extract_project_goal_from_briefing()."""

    def test_none_gibt_leer(self):
        """None ergibt leeren String."""
        assert extract_project_goal_from_briefing(None) == ""

    def test_leeres_dict_gibt_leer(self):
        """Leeres Dict ergibt leeren String."""
        assert extract_project_goal_from_briefing({}) == ""

    def test_nicht_dict_gibt_leer(self):
        """Nicht-Dict ergibt leeren String."""
        assert extract_project_goal_from_briefing("string") == ""
        assert extract_project_goal_from_briefing(42) == ""

    def test_mit_goal(self):
        """Goal wird korrekt extrahiert."""
        assert extract_project_goal_from_briefing({"goal": "Todo-App"}) == "Todo-App"

    def test_mit_project_goal_fallback(self):
        """projectGoal wird als Fallback genutzt."""
        assert extract_project_goal_from_briefing({"projectGoal": "Shop"}) == "Shop"

    def test_goal_hat_vorrang(self):
        """goal hat Vorrang vor projectGoal."""
        briefing = {"goal": "Todo", "projectGoal": "Shop"}
        assert extract_project_goal_from_briefing(briefing) == "Todo"

    def test_goal_leer_fallback_auf_project_goal(self):
        """Leeres goal faellt auf projectGoal zurueck."""
        briefing = {"goal": "", "projectGoal": "Shop"}
        assert extract_project_goal_from_briefing(briefing) == "Shop"
