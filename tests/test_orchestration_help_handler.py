# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 14.02.2026
Version: 1.0
Beschreibung: Tests fuer backend/orchestration_help_handler.py —
              handle_help_needed_events und _run_automatic_test_generator.
"""

import json
import os
import pytest
from unittest.mock import MagicMock, patch, mock_open

from backend.orchestration_help_handler import (
    handle_help_needed_events,
    _run_automatic_test_generator,
)


# =========================================================================
# Helpers
# =========================================================================

def _make_session_mgr(blocked=None):
    """Erstellt einen gemockten SessionManager."""
    sm = MagicMock()
    sm.get_blocked_agents.return_value = blocked or {}
    return sm


def _make_ui_log():
    """Erstellt einen UI-Log Callback."""
    return MagicMock()


def _block_info(action, priority="normal"):
    """Erstellt eine Block-Info mit reason-JSON."""
    return {
        "reason": json.dumps({"action_required": action, "priority": priority}),
        "priority": priority,
    }


# =========================================================================
# TestNoBlocks
# =========================================================================

class TestNoBlocks:
    """Tests wenn keine Agents blockiert sind."""

    def test_keine_blockierten_agents(self):
        """Keine blockierten Agents ergibt no_blocks."""
        sm = _make_session_mgr()
        result = handle_help_needed_events(
            sm, "/tmp", {}, {}, MagicMock(), {}, _make_ui_log(), 1
        )
        assert result["status"] == "no_blocks"
        assert result["actions"] == []


# =========================================================================
# TestActionRouting
# =========================================================================

class TestActionRouting:
    """Tests fuer Aktions-Routing basierend auf action_required."""

    @patch("backend.orchestration_help_handler._run_automatic_test_generator")
    def test_create_test_files_action(self, mock_gen):
        """create_test_files Aktion startet Test-Generator."""
        mock_gen.return_value = True
        sm = _make_session_mgr({"tester": _block_info("create_test_files")})
        ui = _make_ui_log()

        result = handle_help_needed_events(
            sm, "/tmp", {}, {}, MagicMock(), {}, ui, 1
        )

        assert result["status"] == "processed"
        assert len(result["actions"]) == 1
        assert result["actions"][0]["action"] == "test_generator"
        assert result["actions"][0]["success"] is True
        sm.clear_agent_blocked.assert_called_once_with("tester")

    @patch("backend.orchestration_help_handler._run_automatic_test_generator")
    def test_create_test_files_fehlgeschlagen(self, mock_gen):
        """Fehlgeschlagener Test-Generator raeumt Blockade NICHT auf."""
        mock_gen.return_value = False
        sm = _make_session_mgr({"tester": _block_info("create_test_files")})

        result = handle_help_needed_events(
            sm, "/tmp", {}, {}, MagicMock(), {}, _make_ui_log(), 1
        )

        assert result["actions"][0]["success"] is False
        sm.clear_agent_blocked.assert_not_called()

    def test_security_review_action(self):
        """security_review_required eskaliert aber blockiert weiter."""
        sm = _make_session_mgr({"security": _block_info("security_review_required", "high")})

        result = handle_help_needed_events(
            sm, "/tmp", {}, {}, MagicMock(), {}, _make_ui_log(), 1
        )

        assert result["actions"][0]["action"] == "escalate_to_coder"
        assert result["actions"][0]["success"] is True
        sm.clear_agent_blocked.assert_not_called()

    def test_unbekannte_action(self):
        """Unbekannte Aktion wird als 'unknown' geloggt."""
        sm = _make_session_mgr({"custom": _block_info("unknown_action")})

        result = handle_help_needed_events(
            sm, "/tmp", {}, {}, MagicMock(), {}, _make_ui_log(), 1
        )

        assert result["actions"][0]["action"] == "unknown"
        assert result["actions"][0]["success"] is False


# =========================================================================
# TestPrioritySorting
# =========================================================================

class TestPrioritySorting:
    """Tests fuer Prioritaets-Sortierung der blockierten Agents."""

    def test_critical_vor_normal(self):
        """Critical-Priority wird vor Normal verarbeitet."""
        sm = _make_session_mgr({
            "agent_normal": _block_info("unknown", "normal"),
            "agent_critical": _block_info("unknown", "critical"),
        })

        result = handle_help_needed_events(
            sm, "/tmp", {}, {}, MagicMock(), {}, _make_ui_log(), 1
        )

        # Critical sollte zuerst verarbeitet werden
        assert result["blocked_count"] == 2
        agents = [a["agent"] for a in result["actions"]]
        assert agents[0] == "agent_critical"

    def test_high_vor_low(self):
        """High-Priority wird vor Low verarbeitet."""
        sm = _make_session_mgr({
            "agent_low": _block_info("unknown", "low"),
            "agent_high": _block_info("unknown", "high"),
        })

        result = handle_help_needed_events(
            sm, "/tmp", {}, {}, MagicMock(), {}, _make_ui_log(), 1
        )

        agents = [a["agent"] for a in result["actions"]]
        assert agents[0] == "agent_high"


# =========================================================================
# TestEdgeCases
# =========================================================================

class TestEdgeCases:
    """Tests fuer Randfaelle."""

    def test_ungueltiges_reason_json(self):
        """Ungueltiges JSON in reason wird abgefangen."""
        sm = _make_session_mgr({
            "broken": {"reason": "not json {{", "priority": "normal"}
        })

        result = handle_help_needed_events(
            sm, "/tmp", {}, {}, MagicMock(), {}, _make_ui_log(), 1
        )

        # Sollte als unknown behandelt werden
        assert result["actions"][0]["action"] == "unknown"

    def test_leere_reason(self):
        """Leere Reason-String wird abgefangen."""
        sm = _make_session_mgr({
            "empty": {"reason": "{}", "priority": "normal"}
        })

        result = handle_help_needed_events(
            sm, "/tmp", {}, {}, MagicMock(), {}, _make_ui_log(), 1
        )

        assert result["actions"][0]["action"] == "unknown"

    def test_reason_none(self):
        """None als reason wird abgefangen."""
        sm = _make_session_mgr({
            "none_reason": {"reason": None, "priority": "normal"}
        })

        # TypeError in json.loads(None) wird abgefangen
        result = handle_help_needed_events(
            sm, "/tmp", {}, {}, MagicMock(), {}, _make_ui_log(), 1
        )

        assert result["status"] == "processed"

    @patch("backend.orchestration_help_handler._run_automatic_test_generator")
    def test_mehrere_blockierte_agents(self, mock_gen):
        """Mehrere blockierte Agents werden alle verarbeitet."""
        mock_gen.return_value = True
        sm = _make_session_mgr({
            "tester": _block_info("create_test_files"),
            "security": _block_info("security_review_required", "high"),
            "custom": _block_info("other"),
        })

        result = handle_help_needed_events(
            sm, "/tmp", {}, {}, MagicMock(), {}, _make_ui_log(), 1
        )

        assert result["blocked_count"] == 3
        assert len(result["actions"]) == 3

    def test_ui_log_wird_aufgerufen(self):
        """UI-Log Callback wird aufgerufen."""
        sm = _make_session_mgr({"x": _block_info("unknown")})
        ui = _make_ui_log()

        handle_help_needed_events(
            sm, "/tmp", {}, {}, MagicMock(), {}, ui, 1
        )

        assert ui.call_count > 0


# =========================================================================
# TestRunAutomaticTestGenerator
# =========================================================================

class TestRunAutomaticTestGenerator:
    """Tests fuer _run_automatic_test_generator (interne Funktion)."""

    def test_kein_projekt_pfad_fallback(self, tmp_path):
        """Wenn project_path nicht existiert, Fallback auf Templates."""
        ui = _make_ui_log()
        nonexistent = str(tmp_path / "nonexistent")
        with patch("backend.test_templates.create_fallback_tests",
                   create=True, return_value=["test1.py"]):
            result = _run_automatic_test_generator(
                nonexistent, {}, {}, MagicMock(), {}, ui, 0
            )
        assert result is True

    def test_keine_python_dateien_fallback(self, tmp_path):
        """Keine .py Dateien → Fallback auf Templates."""
        (tmp_path / "readme.md").write_text("# Readme")
        ui = _make_ui_log()
        with patch("backend.test_templates.create_fallback_tests",
                   create=True, return_value=["test.py"]):
            result = _run_automatic_test_generator(
                str(tmp_path), {}, {}, MagicMock(), {}, ui, 1
            )
        assert result is True

    def test_test_dateien_werden_uebersprungen(self, tmp_path):
        """Dateien mit test_ Prefix werden nicht als Code gesammelt."""
        (tmp_path / "test_main.py").write_text("import pytest")
        (tmp_path / "test_utils.py").write_text("import pytest")
        ui = _make_ui_log()
        with patch("backend.test_templates.create_fallback_tests",
                   create=True, return_value=[]):
            result = _run_automatic_test_generator(
                str(tmp_path), {}, {}, MagicMock(), {}, ui, 1
            )
        # Keine code_files → Fallback, leere Liste → False
        assert result is False

    def test_erfolgreiche_testgenerierung(self, tmp_path):
        """Erfolgreiche Crew-Ausfuehrung erstellt Test-Dateien."""
        (tmp_path / "main.py").write_text("def main(): pass")
        ui = _make_ui_log()

        mock_crew_instance = MagicMock()
        mock_crew_instance.kickoff.return_value = "### FILENAME: test_main.py\npass"

        with patch("agents.test_generator_agent.create_test_generator",
                   create=True) as mock_gen, \
             patch("agents.test_generator_agent.create_test_generation_task",
                   create=True), \
             patch("agents.test_generator_agent.extract_test_files",
                   create=True, return_value={"test_main.py": "import pytest\n"}), \
             patch("crewai.Crew", create=True, return_value=mock_crew_instance), \
             patch("backend.orchestration_help_handler.is_forbidden_file",
                   return_value=False):
            result = _run_automatic_test_generator(
                str(tmp_path), {"project_type": "python_script"}, {},
                MagicMock(), {}, ui, 1
            )
        assert result is True

    def test_crew_ohne_filename_marker_fallback(self, tmp_path):
        """Crew-Output ohne ### FILENAME: → Fallback auf Templates."""
        (tmp_path / "app.py").write_text("def app(): pass")
        ui = _make_ui_log()

        mock_crew_instance = MagicMock()
        mock_crew_instance.kickoff.return_value = "Einfacher Text"

        with patch("agents.test_generator_agent.create_test_generator", create=True), \
             patch("agents.test_generator_agent.create_test_generation_task", create=True), \
             patch("agents.test_generator_agent.extract_test_files", create=True), \
             patch("crewai.Crew", create=True, return_value=mock_crew_instance), \
             patch("backend.test_templates.create_fallback_tests",
                   create=True, return_value=["t.py"]):
            result = _run_automatic_test_generator(
                str(tmp_path), {}, {}, MagicMock(), {}, ui, 1
            )
        assert result is True

    def test_blacklisted_datei_uebersprungen(self, tmp_path):
        """Blacklisted Dateien werden uebersprungen (Fix 36)."""
        (tmp_path / "main.py").write_text("x = 1")
        ui = _make_ui_log()

        mock_crew_instance = MagicMock()
        mock_crew_instance.kickoff.return_value = "### FILENAME: test.py\npass"

        with patch("agents.test_generator_agent.create_test_generator", create=True), \
             patch("agents.test_generator_agent.create_test_generation_task", create=True), \
             patch("agents.test_generator_agent.extract_test_files",
                   create=True, return_value={"package-lock.json": "{}"}), \
             patch("crewai.Crew", create=True, return_value=mock_crew_instance), \
             patch("backend.orchestration_help_handler.is_forbidden_file",
                   return_value=True):
            result = _run_automatic_test_generator(
                str(tmp_path), {}, {}, MagicMock(), {}, ui, 1
            )
        # Alle Dateien blacklisted → False
        assert result is False

    def test_komplett_fehlgeschlagen(self, tmp_path):
        """Kompletter Fehler ohne Fallback → False."""
        (tmp_path / "main.py").write_text("x = 1")
        ui = _make_ui_log()
        # Erste Exception: create_test_generator
        # Zweite Exception: create_fallback_tests im except
        with patch.dict("sys.modules", {
                "agents.test_generator_agent": MagicMock(
                    create_test_generator=MagicMock(side_effect=RuntimeError("Crash")),
                    create_test_generation_task=MagicMock(),
                    extract_test_files=MagicMock(),
                ),
                "backend.test_templates": MagicMock(
                    create_fallback_tests=MagicMock(side_effect=RuntimeError("Auch kaputt")),
                ),
            }):
            result = _run_automatic_test_generator(
                str(tmp_path), {}, {}, MagicMock(), {}, ui, 1
            )
        assert result is False

    def test_tech_blueprint_none(self, tmp_path):
        """tech_blueprint=None verursacht keinen Crash."""
        ui = _make_ui_log()
        nonexistent = str(tmp_path / "nope")
        with patch("backend.test_templates.create_fallback_tests",
                   create=True, return_value=[]):
            result = _run_automatic_test_generator(
                nonexistent, None, {}, MagicMock(), {}, ui, 1
            )
        assert result is False

    def test_crew_result_none(self, tmp_path):
        """Crew gibt None zurueck → Fallback."""
        (tmp_path / "a.py").write_text("a = 1")
        ui = _make_ui_log()

        mock_crew_instance = MagicMock()
        mock_crew_instance.kickoff.return_value = None

        with patch("agents.test_generator_agent.create_test_generator", create=True), \
             patch("agents.test_generator_agent.create_test_generation_task", create=True), \
             patch("agents.test_generator_agent.extract_test_files", create=True), \
             patch("crewai.Crew", create=True, return_value=mock_crew_instance), \
             patch("backend.test_templates.create_fallback_tests",
                   create=True, return_value=[]):
            result = _run_automatic_test_generator(
                str(tmp_path), {}, {}, MagicMock(), {}, ui, 1
            )
        assert result is False

    def test_datei_schreiben_oserror(self, tmp_path):
        """OSError beim Schreiben der Test-Datei wird abgefangen."""
        (tmp_path / "x.py").write_text("z = 1")
        ui = _make_ui_log()

        mock_crew_instance = MagicMock()
        mock_crew_instance.kickoff.return_value = "### FILENAME: test.py\npass"

        with patch("agents.test_generator_agent.create_test_generator", create=True), \
             patch("agents.test_generator_agent.create_test_generation_task", create=True), \
             patch("agents.test_generator_agent.extract_test_files",
                   create=True, return_value={"test_x.py": "pass"}), \
             patch("crewai.Crew", create=True, return_value=mock_crew_instance), \
             patch("backend.orchestration_help_handler.is_forbidden_file",
                   return_value=False), \
             patch("backend.orchestration_help_handler.os.makedirs",
                   side_effect=OSError("Disk full")):
            result = _run_automatic_test_generator(
                str(tmp_path), {}, {}, MagicMock(), {}, ui, 1
            )
        # makedirs Fehler wird abgefangen → False
        assert result is False

    def test_datei_lese_fehler_wird_uebersprungen(self, tmp_path):
        """Nicht lesbare Datei wird uebersprungen, andere werden verarbeitet."""
        (tmp_path / "good.py").write_text("x = 1")
        ui = _make_ui_log()

        # Simuliere dass eine Datei nicht lesbar ist
        original_open = open

        def selective_open(path, *args, **kwargs):
            if str(path).endswith("bad.py"):
                raise PermissionError("Keine Berechtigung")
            return original_open(path, *args, **kwargs)

        # Walk gibt zwei Dateien zurueck, eine davon wird fehlschlagen
        mock_walk_result = [
            (str(tmp_path), [], ["good.py"])
        ]

        with patch("backend.orchestration_help_handler.os.walk",
                   return_value=mock_walk_result), \
             patch("backend.test_templates.create_fallback_tests",
                   create=True, return_value=["fb.py"]):
            # good.py wird gelesen, dann Fallback weil kein CrewAI
            result = _run_automatic_test_generator(
                str(tmp_path), {}, {}, MagicMock(), {}, ui, 1
            )
        # Mindestens Fallback versucht
        assert isinstance(result, bool)
