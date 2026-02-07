# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 01.02.2026
Version: 1.0
Beschreibung: Unit Tests für ReporterService - Projektbericht-Datensammlung.

              Tests validieren:
              - Initialisierung und Grundzustand
              - Alle collect_* Methoden
              - Generierungs-Methoden (generate_summary, get_report_data)
              - Speicher-Methoden (save_report, export_to_json)
              - Edge Cases und Fehlerbehandlung
"""

import pytest
import sys
import os
import json
import tempfile
import shutil
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.reporter_service import ReporterService


# =========================================================================
# Fixtures
# =========================================================================

@pytest.fixture
def reporter():
    """Standard ReporterService für Tests."""
    return ReporterService()


@pytest.fixture
def reporter_with_path():
    """ReporterService mit Projekt-Pfad für Speicher-Tests."""
    temp_dir = tempfile.mkdtemp()
    service = ReporterService(project_path=temp_dir)
    yield service
    # Cleanup
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def filled_reporter(reporter):
    """ReporterService mit vorausgefüllten Daten."""
    reporter.collect_project_info("Test Projekt", "Test-Ziel")
    reporter.collect_counts(anforderungen=5, features=3, tasks=10, files=8)
    reporter.collect_test_results(passed=7, total=10)
    reporter.collect_iteration(5)
    reporter.collect_error("SyntaxError", "Unexpected token", "coder")
    reporter.collect_agent_usage("coder", tokens=5000, cost=0.01)
    reporter.collect_agent_usage("tester", tokens=2000, cost=0.005)
    reporter.collect_milestone("Phase 1", "completed")
    reporter.add_recommendation("Mehr Tests schreiben", "high")
    return reporter


# =========================================================================
# Test: Initialisierung
# =========================================================================

class TestInitialization:
    """Tests für ReporterService Initialisierung."""

    def test_init_without_path(self):
        """Initialisierung ohne Pfad funktioniert."""
        service = ReporterService()
        assert service.project_path is None
        assert "project_name" in service.data
        assert service.data["project_name"] == ""

    def test_init_with_path(self):
        """Initialisierung mit Pfad funktioniert."""
        service = ReporterService(project_path="/tmp/test")
        assert service.project_path == "/tmp/test"

    def test_default_values(self, reporter):
        """Standard-Werte sind korrekt initialisiert."""
        assert reporter.data["anforderungen_count"] == 0
        assert reporter.data["features_count"] == 0
        assert reporter.data["tasks_count"] == 0
        assert reporter.data["files_count"] == 0
        assert reporter.data["tests_passed"] == 0
        assert reporter.data["tests_total"] == 0
        assert reporter.data["coverage"] == 0.0
        assert reporter.data["iterations_count"] == 0
        assert reporter.data["errors"] == []
        assert reporter.data["agent_usage"] == {}
        assert reporter.data["total_cost"] == 0.0
        assert reporter.data["milestones"] == []
        assert reporter.data["recommendations"] == []

    def test_start_date_set(self, reporter):
        """Start-Datum wird automatisch gesetzt."""
        assert reporter.data["start_date"] is not None
        assert "T" in reporter.data["start_date"]  # ISO-Format

    def test_end_date_none(self, reporter):
        """End-Datum ist initial None."""
        assert reporter.data["end_date"] is None


# =========================================================================
# Test: collect_project_info
# =========================================================================

class TestCollectProjectInfo:
    """Tests für collect_project_info Methode."""

    def test_basic_info(self, reporter):
        """Basis-Informationen werden gesetzt."""
        reporter.collect_project_info("Mein Projekt", "Ein Test-Ziel")
        assert reporter.data["project_name"] == "Mein Projekt"
        assert reporter.data["goal"] == "Ein Test-Ziel"

    def test_overwrite_info(self, reporter):
        """Informationen können überschrieben werden."""
        reporter.collect_project_info("Alt", "Alt-Ziel")
        reporter.collect_project_info("Neu", "Neu-Ziel")
        assert reporter.data["project_name"] == "Neu"
        assert reporter.data["goal"] == "Neu-Ziel"

    def test_unicode_info(self, reporter):
        """Unicode-Zeichen werden korrekt behandelt."""
        reporter.collect_project_info("Täst-Prüjekt", "Zïel mit Ümläuten")
        assert reporter.data["project_name"] == "Täst-Prüjekt"


# =========================================================================
# Test: collect_counts
# =========================================================================

class TestCollectCounts:
    """Tests für collect_counts Methode."""

    def test_all_counts(self, reporter):
        """Alle Counts werden gesetzt."""
        reporter.collect_counts(anforderungen=5, features=3, tasks=10, files=8)
        assert reporter.data["anforderungen_count"] == 5
        assert reporter.data["features_count"] == 3
        assert reporter.data["tasks_count"] == 10
        assert reporter.data["files_count"] == 8

    def test_partial_counts(self, reporter):
        """Nur angegebene Counts werden gesetzt."""
        reporter.collect_counts(anforderungen=5)
        assert reporter.data["anforderungen_count"] == 5
        assert reporter.data["features_count"] == 0  # Default

    def test_zero_counts(self, reporter):
        """Null-Werte funktionieren."""
        reporter.collect_counts(anforderungen=0, features=0, tasks=0, files=0)
        assert reporter.data["anforderungen_count"] == 0


# =========================================================================
# Test: collect_test_results
# =========================================================================

class TestCollectTestResults:
    """Tests für collect_test_results Methode."""

    def test_basic_results(self, reporter):
        """Test-Ergebnisse werden gesetzt."""
        reporter.collect_test_results(passed=7, total=10)
        assert reporter.data["tests_passed"] == 7
        assert reporter.data["tests_total"] == 10

    def test_coverage_calculation(self, reporter):
        """Coverage wird korrekt berechnet."""
        reporter.collect_test_results(passed=7, total=10)
        assert reporter.data["coverage"] == 0.7

    def test_coverage_zero_total(self, reporter):
        """Coverage bei 0 Tests ist 0."""
        reporter.collect_test_results(passed=0, total=0)
        assert reporter.data["coverage"] == 0.0

    def test_coverage_full(self, reporter):
        """100% Coverage wird korrekt berechnet."""
        reporter.collect_test_results(passed=10, total=10)
        assert reporter.data["coverage"] == 1.0


# =========================================================================
# Test: collect_iteration
# =========================================================================

class TestCollectIteration:
    """Tests für collect_iteration Methode."""

    def test_basic_iteration(self, reporter):
        """Iteration wird gesetzt."""
        reporter.collect_iteration(5)
        assert reporter.data["iterations_count"] == 5

    def test_update_iteration(self, reporter):
        """Iteration kann aktualisiert werden."""
        reporter.collect_iteration(3)
        reporter.collect_iteration(5)
        assert reporter.data["iterations_count"] == 5


# =========================================================================
# Test: collect_error
# =========================================================================

class TestCollectError:
    """Tests für collect_error Methode."""

    def test_basic_error(self, reporter):
        """Fehler wird hinzugefügt."""
        reporter.collect_error("SyntaxError", "Unexpected token", "coder")
        assert len(reporter.data["errors"]) == 1
        assert reporter.data["errors"][0]["type"] == "SyntaxError"
        assert reporter.data["errors"][0]["message"] == "Unexpected token"
        assert reporter.data["errors"][0]["agent"] == "coder"

    def test_multiple_errors(self, reporter):
        """Mehrere Fehler werden gesammelt."""
        reporter.collect_error("Error1", "Msg1")
        reporter.collect_error("Error2", "Msg2")
        reporter.collect_error("Error3", "Msg3")
        assert len(reporter.data["errors"]) == 3

    def test_error_timestamp(self, reporter):
        """Fehler hat Timestamp."""
        reporter.collect_error("Error", "Msg")
        assert "timestamp" in reporter.data["errors"][0]

    def test_error_with_details(self, reporter):
        """Fehler mit Details."""
        reporter.collect_error("Error", "Msg", "agent", details={"line": 42})
        assert reporter.data["errors"][0]["details"]["line"] == 42

    def test_error_without_agent(self, reporter):
        """Fehler ohne Agent."""
        reporter.collect_error("Error", "Msg")
        assert reporter.data["errors"][0]["agent"] == ""


# =========================================================================
# Test: collect_agent_usage
# =========================================================================

class TestCollectAgentUsage:
    """Tests für collect_agent_usage Methode."""

    def test_basic_usage(self, reporter):
        """Agent-Nutzung wird erfasst."""
        reporter.collect_agent_usage("coder", tokens=1000, cost=0.01)
        assert "coder" in reporter.data["agent_usage"]
        assert reporter.data["agent_usage"]["coder"]["calls"] == 1
        assert reporter.data["agent_usage"]["coder"]["tokens"] == 1000
        assert reporter.data["agent_usage"]["coder"]["cost"] == 0.01

    def test_multiple_calls(self, reporter):
        """Mehrere Aufrufe werden akkumuliert."""
        reporter.collect_agent_usage("coder", tokens=1000, cost=0.01)
        reporter.collect_agent_usage("coder", tokens=2000, cost=0.02)
        assert reporter.data["agent_usage"]["coder"]["calls"] == 2
        assert reporter.data["agent_usage"]["coder"]["tokens"] == 3000
        assert reporter.data["agent_usage"]["coder"]["cost"] == 0.03

    def test_total_cost_updated(self, reporter):
        """Gesamtkosten werden aktualisiert."""
        reporter.collect_agent_usage("coder", tokens=1000, cost=0.01)
        reporter.collect_agent_usage("tester", tokens=500, cost=0.005)
        assert reporter.data["total_cost"] == 0.015

    def test_success_tracking(self, reporter):
        """Erfolgreiche Aufrufe werden gezählt."""
        reporter.collect_agent_usage("coder", tokens=1000, cost=0.01, success=True)
        reporter.collect_agent_usage("coder", tokens=1000, cost=0.01, success=False)
        assert reporter.data["agent_usage"]["coder"]["success_count"] == 1
        assert reporter.data["agent_usage"]["coder"]["error_count"] == 1

    def test_multiple_agents(self, reporter):
        """Mehrere Agenten werden getrennt erfasst."""
        reporter.collect_agent_usage("coder", tokens=1000, cost=0.01)
        reporter.collect_agent_usage("tester", tokens=500, cost=0.005)
        assert len(reporter.data["agent_usage"]) == 2


# =========================================================================
# Test: collect_milestone
# =========================================================================

class TestCollectMilestone:
    """Tests für collect_milestone Methode."""

    def test_add_milestone(self, reporter):
        """Meilenstein wird hinzugefügt."""
        reporter.collect_milestone("Phase 1", "in_progress")
        assert len(reporter.data["milestones"]) == 1
        assert reporter.data["milestones"][0]["name"] == "Phase 1"
        assert reporter.data["milestones"][0]["status"] == "in_progress"

    def test_update_milestone(self, reporter):
        """Bestehender Meilenstein wird aktualisiert."""
        reporter.collect_milestone("Phase 1", "in_progress")
        reporter.collect_milestone("Phase 1", "completed")
        assert len(reporter.data["milestones"]) == 1
        assert reporter.data["milestones"][0]["status"] == "completed"

    def test_milestone_timestamps(self, reporter):
        """Meilenstein hat Timestamps."""
        reporter.collect_milestone("Phase 1", "pending")
        assert "created_at" in reporter.data["milestones"][0]
        assert "updated_at" in reporter.data["milestones"][0]


# =========================================================================
# Test: add_recommendation
# =========================================================================

class TestAddRecommendation:
    """Tests für add_recommendation Methode."""

    def test_add_recommendation(self, reporter):
        """Empfehlung wird hinzugefügt."""
        reporter.add_recommendation("Mehr Tests", "high")
        assert len(reporter.data["recommendations"]) == 1
        assert reporter.data["recommendations"][0]["text"] == "Mehr Tests"
        assert reporter.data["recommendations"][0]["priority"] == "high"

    def test_default_priority(self, reporter):
        """Standard-Priorität ist 'medium'."""
        reporter.add_recommendation("Test")
        assert reporter.data["recommendations"][0]["priority"] == "medium"

    def test_category(self, reporter):
        """Kategorie wird gesetzt."""
        reporter.add_recommendation("Optimieren", "high", "performance")
        assert reporter.data["recommendations"][0]["category"] == "performance"

    def test_multiple_recommendations(self, reporter):
        """Mehrere Empfehlungen werden gesammelt."""
        reporter.add_recommendation("Empf 1")
        reporter.add_recommendation("Empf 2")
        reporter.add_recommendation("Empf 3")
        assert len(reporter.data["recommendations"]) == 3


# =========================================================================
# Test: generate_summary
# =========================================================================

class TestGenerateSummary:
    """Tests für generate_summary Methode."""

    def test_basic_summary(self, filled_reporter):
        """Zusammenfassung wird generiert."""
        summary = filled_reporter.generate_summary()
        assert "Test Projekt" in summary
        assert "5 Anforderungen" in summary
        assert "3 Features" in summary
        assert "10 Tasks" in summary
        assert "8 Dateien" in summary
        assert "7/10" in summary  # Tests
        assert "70%" in summary  # Coverage
        assert "$0.0150" in summary  # Kosten (0.01 + 0.005)

    def test_empty_summary(self, reporter):
        """Leere Zusammenfassung funktioniert."""
        summary = reporter.generate_summary()
        assert "0 Anforderungen" in summary
        assert "0/0" in summary  # Tests


# =========================================================================
# Test: get_report_data
# =========================================================================

class TestGetReportData:
    """Tests für get_report_data Methode."""

    def test_returns_all_data(self, filled_reporter):
        """Alle Daten werden zurückgegeben."""
        data = filled_reporter.get_report_data()
        assert data["project_name"] == "Test Projekt"
        assert data["anforderungen_count"] == 5
        assert len(data["errors"]) == 1
        assert len(data["agent_usage"]) == 2

    def test_end_date_set(self, reporter):
        """End-Datum wird gesetzt."""
        data = reporter.get_report_data()
        assert data["end_date"] is not None

    def test_cost_per_iteration(self, reporter):
        """Kosten pro Iteration werden berechnet."""
        reporter.collect_agent_usage("coder", tokens=1000, cost=0.10)
        reporter.collect_iteration(5)
        data = reporter.get_report_data()
        assert data["cost_per_iteration"] == 0.02  # 0.10 / 5


# =========================================================================
# Test: get_error_summary
# =========================================================================

class TestGetErrorSummary:
    """Tests für get_error_summary Methode."""

    def test_empty_errors(self, reporter):
        """Leere Fehler-Zusammenfassung."""
        summary = reporter.get_error_summary()
        assert summary == {}

    def test_error_grouping(self, reporter):
        """Fehler werden nach Typ gruppiert."""
        reporter.collect_error("SyntaxError", "Msg1")
        reporter.collect_error("SyntaxError", "Msg2")
        reporter.collect_error("TypeError", "Msg3")
        summary = reporter.get_error_summary()
        assert summary["SyntaxError"] == 2
        assert summary["TypeError"] == 1


# =========================================================================
# Test: get_agent_performance
# =========================================================================

class TestGetAgentPerformance:
    """Tests für get_agent_performance Methode."""

    def test_empty_performance(self, reporter):
        """Leere Performance-Daten."""
        perf = reporter.get_agent_performance()
        assert perf == []

    def test_performance_sorted_by_cost(self, reporter):
        """Performance ist nach Kosten sortiert."""
        reporter.collect_agent_usage("cheap", tokens=100, cost=0.01)
        reporter.collect_agent_usage("expensive", tokens=1000, cost=0.10)
        reporter.collect_agent_usage("medium", tokens=500, cost=0.05)
        perf = reporter.get_agent_performance()
        assert perf[0]["agent"] == "expensive"
        assert perf[1]["agent"] == "medium"
        assert perf[2]["agent"] == "cheap"

    def test_success_rate_calculation(self, reporter):
        """Erfolgsrate wird berechnet."""
        reporter.collect_agent_usage("coder", tokens=100, cost=0.01, success=True)
        reporter.collect_agent_usage("coder", tokens=100, cost=0.01, success=True)
        reporter.collect_agent_usage("coder", tokens=100, cost=0.01, success=False)
        perf = reporter.get_agent_performance()
        # 2 von 3 erfolgreich = 66.7%
        assert perf[0]["success_rate"] == pytest.approx(0.666, rel=0.01)


# =========================================================================
# Test: save_report
# =========================================================================

class TestSaveReport:
    """Tests für save_report Methode."""

    def test_save_without_path_returns_none(self, reporter):
        """Ohne Pfad wird None zurückgegeben."""
        result = reporter.save_report("# Report")
        assert result is None

    def test_save_creates_file(self, reporter_with_path):
        """Report wird als Datei gespeichert."""
        result = reporter_with_path.save_report("# Test Report\nInhalt")
        assert result is not None
        assert os.path.exists(result)
        with open(result, encoding="utf-8") as f:
            content = f.read()
        assert "Test Report" in content

    def test_save_creates_docs_folder(self, reporter_with_path):
        """docs-Ordner wird erstellt."""
        reporter_with_path.save_report("# Report")
        docs_path = os.path.join(reporter_with_path.project_path, "docs")
        assert os.path.isdir(docs_path)

    def test_custom_filename(self, reporter_with_path):
        """Benutzerdefinierter Dateiname wird verwendet."""
        result = reporter_with_path.save_report("# Report", "CUSTOM_REPORT.md")
        assert "CUSTOM_REPORT.md" in result


# =========================================================================
# Test: save_data
# =========================================================================

class TestSaveData:
    """Tests für save_data Methode."""

    def test_save_data_without_path_returns_none(self, reporter):
        """Ohne Pfad wird None zurückgegeben."""
        result = reporter.save_data()
        assert result is None

    def test_save_data_creates_json(self, reporter_with_path):
        """Daten werden als JSON gespeichert."""
        reporter_with_path.collect_project_info("Test", "Ziel")
        result = reporter_with_path.save_data()
        assert result is not None
        assert os.path.exists(result)
        with open(result, encoding="utf-8") as f:
            data = json.load(f)
        assert data["project_name"] == "Test"


# =========================================================================
# Test: export_to_json
# =========================================================================

class TestExportToJson:
    """Tests für export_to_json Methode."""

    def test_export_returns_json_string(self, reporter):
        """JSON-String wird zurückgegeben."""
        reporter.collect_project_info("Test", "Ziel")
        result = reporter.export_to_json()
        assert isinstance(result, str)
        data = json.loads(result)
        assert data["project_name"] == "Test"

    def test_export_valid_json(self, filled_reporter):
        """Export ist gültiges JSON."""
        result = filled_reporter.export_to_json()
        data = json.loads(result)
        assert "errors" in data
        assert "agent_usage" in data


# =========================================================================
# Test: Edge Cases
# =========================================================================

class TestEdgeCases:
    """Tests für Edge Cases."""

    def test_unicode_in_all_fields(self, reporter):
        """Unicode-Zeichen in allen Feldern."""
        reporter.collect_project_info("日本語プロジェクト", "目標")
        reporter.collect_error("エラー", "メッセージ", "エージェント")
        reporter.add_recommendation("推奨事項", "high", "パフォーマンス")
        data = reporter.get_report_data()
        assert data["project_name"] == "日本語プロジェクト"

    def test_very_long_strings(self, reporter):
        """Sehr lange Strings werden behandelt."""
        long_string = "A" * 10000
        reporter.collect_error("Error", long_string)
        assert len(reporter.data["errors"][0]["message"]) == 10000

    def test_concurrent_operations(self, reporter):
        """Mehrere gleichzeitige Operationen."""
        for i in range(100):
            reporter.collect_error(f"Error{i}", f"Msg{i}")
            reporter.collect_agent_usage(f"agent{i%5}", tokens=100, cost=0.001)
        assert len(reporter.data["errors"]) == 100
        assert len(reporter.data["agent_usage"]) == 5

    def test_negative_values(self, reporter):
        """Negative Werte werden akzeptiert."""
        reporter.collect_counts(anforderungen=-1)  # Sollte nicht vorkommen, aber kein Crash
        assert reporter.data["anforderungen_count"] == -1
