# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 01.02.2026
Version: 1.0
Beschreibung: Unit Tests für DocumentationService.

              Tests validieren:
              - Datensammlung (collect_*)
              - README/CHANGELOG Generierung
              - Orchestrator-Entscheidungen
              - JSON Export und Zusammenfassung
"""

import pytest
import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.documentation_service import DocumentationService


# =========================================================================
# Fixtures
# =========================================================================

@pytest.fixture
def doc_service():
    """Erstellt DocumentationService-Instanz."""
    return DocumentationService()


@pytest.fixture
def doc_service_with_path(tmp_path):
    """Erstellt DocumentationService mit temporärem Projekt-Pfad."""
    return DocumentationService(project_path=str(tmp_path))


@pytest.fixture
def sample_techstack():
    """Beispiel TechStack für Tests."""
    return {
        "project_type": "web",
        "language": "Python",
        "app_type": "API",
        "database": "SQLite",
        "requires_server": True,
        "server_port": 8000,
        "dependencies": ["flask", "sqlalchemy"],
        "install_command": "pip install -r requirements.txt",
        "run_command": "python app.py"
    }


@pytest.fixture
def sample_briefing():
    """Beispiel Briefing für Tests."""
    return {
        "project_goal": "REST API für Benutzerverwaltung",
        "target_audience": "Entwickler",
        "key_features": ["Authentication", "User CRUD", "Roles"]
    }


# =========================================================================
# Test: Initialisierung
# =========================================================================

class TestDocumentationServiceInit:
    """Tests für DocumentationService Initialisierung."""

    def test_init_with_project_path(self, tmp_path):
        """Initialisierung mit Projekt-Pfad."""
        service = DocumentationService(str(tmp_path))
        assert service.project_path == str(tmp_path)

    def test_init_without_project_path(self):
        """Initialisierung ohne Projekt-Pfad."""
        service = DocumentationService()
        assert service.project_path is None

    def test_init_creates_data_dict(self, doc_service):
        """Data Dictionary wird initialisiert."""
        assert "goal" in doc_service.data
        assert "briefing" in doc_service.data
        assert "techstack" in doc_service.data
        assert "code_files" in doc_service.data
        assert "iterations" in doc_service.data
        assert "orchestrator_decisions" in doc_service.data

    def test_init_creates_traceability_service(self, doc_service):
        """TraceabilityService wird erstellt."""
        assert hasattr(doc_service, '_traceability_service')

    def test_set_project_path(self, doc_service, tmp_path):
        """set_project_path setzt Pfad korrekt."""
        doc_service.set_project_path(str(tmp_path))
        assert doc_service.project_path == str(tmp_path)


# =========================================================================
# Test: collect_* Methoden
# =========================================================================

class TestCollectMethods:
    """Tests für Datensammlung."""

    def test_collect_goal(self, doc_service):
        """collect_goal speichert Ziel."""
        doc_service.collect_goal("Eine App bauen")
        assert doc_service.data["goal"] == "Eine App bauen"

    def test_collect_briefing(self, doc_service, sample_briefing):
        """collect_briefing speichert Briefing."""
        doc_service.collect_briefing(sample_briefing)
        assert doc_service.data["briefing"] == sample_briefing

    def test_collect_techstack(self, doc_service, sample_techstack):
        """collect_techstack speichert TechStack."""
        doc_service.collect_techstack(sample_techstack)
        assert doc_service.data["techstack"]["language"] == "Python"

    def test_collect_schema(self, doc_service):
        """collect_schema speichert Schema."""
        schema = "CREATE TABLE users (id INT, name TEXT);"
        doc_service.collect_schema(schema)
        assert doc_service.data["schema"] == schema

    def test_collect_design(self, doc_service):
        """collect_design speichert Design."""
        design = "MVC-Architektur mit Repository-Pattern"
        doc_service.collect_design(design)
        assert doc_service.data["design"] == design


class TestCollectCodeFile:
    """Tests für collect_code_file."""

    def test_counts_lines_correctly(self, doc_service):
        """Zählt Zeilen korrekt."""
        content = "line1\nline2\nline3"
        doc_service.collect_code_file("app.py", content)
        assert doc_service.data["code_files"][0]["lines"] == 3

    def test_calculates_size_correctly(self, doc_service):
        """Berechnet Größe korrekt."""
        content = "12345"
        doc_service.collect_code_file("app.py", content)
        assert doc_service.data["code_files"][0]["size"] == 5

    def test_stores_description(self, doc_service):
        """Speichert Beschreibung."""
        doc_service.collect_code_file("app.py", "code", "Hauptdatei")
        assert doc_service.data["code_files"][0]["description"] == "Hauptdatei"

    def test_handles_empty_content(self, doc_service):
        """Behandelt leeren Inhalt."""
        doc_service.collect_code_file("empty.py", "")
        assert doc_service.data["code_files"][0]["lines"] == 0
        assert doc_service.data["code_files"][0]["size"] == 0

    def test_handles_none_content(self, doc_service):
        """Behandelt None als Inhalt."""
        doc_service.collect_code_file("none.py", None)
        assert doc_service.data["code_files"][0]["lines"] == 0

    def test_adds_timestamp(self, doc_service):
        """Fügt Zeitstempel hinzu."""
        doc_service.collect_code_file("app.py", "code")
        assert "timestamp" in doc_service.data["code_files"][0]


class TestCollectIteration:
    """Tests für collect_iteration."""

    def test_stores_iteration_number(self, doc_service):
        """Speichert Iterations-Nummer."""
        doc_service.collect_iteration(1, "Änderungen", "success")
        assert doc_service.data["iterations"][0]["number"] == 1

    def test_truncates_long_changes(self, doc_service):
        """Kürzt lange Änderungstexte auf 500 Zeichen."""
        long_text = "X" * 1000
        doc_service.collect_iteration(1, long_text, "success")
        assert len(doc_service.data["iterations"][0]["changes"]) == 500

    def test_truncates_review_summary(self, doc_service):
        """Kürzt Review-Summary auf 300 Zeichen."""
        long_text = "X" * 500
        doc_service.collect_iteration(1, "changes", "success", review_summary=long_text)
        assert len(doc_service.data["iterations"][0]["review_summary"]) == 300

    def test_truncates_test_result(self, doc_service):
        """Kürzt Test-Result auf 200 Zeichen."""
        long_text = "X" * 300
        doc_service.collect_iteration(1, "changes", "success", test_result=long_text)
        assert len(doc_service.data["iterations"][0]["test_result"]) == 200

    def test_stores_status(self, doc_service):
        """Speichert Status korrekt."""
        doc_service.collect_iteration(1, "changes", "failed")
        assert doc_service.data["iterations"][0]["status"] == "failed"


class TestCollectSecurityFinding:
    """Tests für collect_security_finding."""

    def test_stores_finding(self, doc_service):
        """Speichert Finding korrekt."""
        finding = {"severity": "high", "description": "SQL Injection"}
        doc_service.collect_security_finding(finding)
        assert doc_service.data["security_findings"][0]["severity"] == "high"

    def test_adds_timestamp(self, doc_service):
        """Fügt Zeitstempel hinzu."""
        doc_service.collect_security_finding({"severity": "low"})
        assert "timestamp" in doc_service.data["security_findings"][0]


class TestCollectTestResult:
    """Tests für collect_test_result."""

    def test_stores_test_name(self, doc_service):
        """Speichert Test-Namen."""
        doc_service.collect_test_result("test_login", True)
        assert doc_service.data["test_results"][0]["name"] == "test_login"

    def test_stores_passed_status(self, doc_service):
        """Speichert passed Status."""
        doc_service.collect_test_result("test_login", True)
        assert doc_service.data["test_results"][0]["passed"] is True

    def test_truncates_long_details(self, doc_service):
        """Kürzt Details auf 200 Zeichen."""
        long_details = "X" * 300
        doc_service.collect_test_result("test", True, details=long_details)
        assert len(doc_service.data["test_results"][0]["details"]) == 200


class TestCollectQualityValidation:
    """Tests für collect_quality_validation."""

    def test_stores_step_name(self, doc_service):
        """Speichert Step-Namen."""
        result = {"passed": True, "score": 0.95}
        doc_service.collect_quality_validation("TechStack", result)
        assert doc_service.data["quality_validations"][0]["step"] == "TechStack"

    def test_stores_validation_result(self, doc_service):
        """Speichert Validierungsergebnis."""
        result = {"passed": True, "score": 0.95, "issues": [], "warnings": []}
        doc_service.collect_quality_validation("Schema", result)
        assert doc_service.data["quality_validations"][0]["score"] == 0.95


# =========================================================================
# Test: collect_orchestrator_decision
# =========================================================================

class TestCollectOrchestratorDecision:
    """Tests für Orchestrator-Entscheidungen."""

    def test_stores_basic_decision(self, doc_service):
        """Speichert grundlegende Entscheidung."""
        doc_service.collect_orchestrator_decision(
            iteration=1,
            action="fix",
            target_agent="coder"
        )
        decision = doc_service.data["orchestrator_decisions"][0]
        assert decision["iteration"] == 1
        assert decision["action"] == "fix"
        assert decision["target_agent"] == "coder"

    def test_truncates_long_root_cause(self, doc_service):
        """Kürzt lange Root Cause auf 500 Zeichen."""
        long_root_cause = "X" * 1000
        doc_service.collect_orchestrator_decision(
            iteration=1,
            action="fix",
            target_agent="coder",
            root_cause=long_root_cause
        )
        assert len(doc_service.data["orchestrator_decisions"][0]["root_cause"]) == 500

    def test_truncates_error_hash(self, doc_service):
        """Kürzt Error Hash auf 12 Zeichen."""
        long_hash = "a" * 64
        doc_service.collect_orchestrator_decision(
            iteration=1,
            action="fix",
            target_agent="coder",
            error_hash=long_hash
        )
        assert len(doc_service.data["orchestrator_decisions"][0]["error_hash"]) == 12

    def test_stores_model_switch_flag(self, doc_service):
        """Speichert Model-Switch Flag."""
        doc_service.collect_orchestrator_decision(
            iteration=1,
            action="model_switch",
            target_agent="coder",
            model_switch=True
        )
        assert doc_service.data["orchestrator_decisions"][0]["model_switch_recommended"] is True

    def test_handles_none_values(self, doc_service):
        """Behandelt None-Werte korrekt."""
        doc_service.collect_orchestrator_decision(
            iteration=1,
            action="proceed",
            target_agent="tester",
            root_cause=None,
            error_hash=None
        )
        decision = doc_service.data["orchestrator_decisions"][0]
        assert decision["root_cause"] is None
        assert decision["error_hash"] is None


# =========================================================================
# Test: README/CHANGELOG Generierung
# =========================================================================

class TestGenerateReadmeContext:
    """Tests für README-Kontext-Generierung."""

    def test_includes_goal(self, doc_service):
        """Enthält Projektziel."""
        doc_service.collect_goal("Eine REST API bauen")
        context = doc_service.generate_readme_context()
        assert "Eine REST API bauen" in context

    def test_includes_techstack_details(self, doc_service, sample_techstack):
        """Enthält TechStack-Details."""
        doc_service.collect_techstack(sample_techstack)
        context = doc_service.generate_readme_context()
        assert "Python" in context
        assert "web" in context

    def test_includes_database_if_present(self, doc_service, sample_techstack):
        """Enthält Datenbank wenn vorhanden."""
        doc_service.collect_techstack(sample_techstack)
        context = doc_service.generate_readme_context()
        assert "SQLite" in context

    def test_includes_server_port(self, doc_service, sample_techstack):
        """Enthält Server-Port wenn vorhanden."""
        doc_service.collect_techstack(sample_techstack)
        context = doc_service.generate_readme_context()
        assert "8000" in context

    def test_includes_dependencies(self, doc_service, sample_techstack):
        """Enthält Dependencies."""
        doc_service.collect_techstack(sample_techstack)
        context = doc_service.generate_readme_context()
        assert "flask" in context

    def test_includes_install_command(self, doc_service, sample_techstack):
        """Enthält Installationsbefehl."""
        doc_service.collect_techstack(sample_techstack)
        context = doc_service.generate_readme_context()
        assert "pip install" in context

    def test_includes_code_files(self, doc_service):
        """Listet Code-Dateien auf."""
        doc_service.collect_code_file("app.py", "code\ncode\ncode")
        context = doc_service.generate_readme_context()
        assert "app.py" in context
        assert "3 Zeilen" in context

    def test_truncates_schema_preview(self, doc_service):
        """Kürzt Schema-Vorschau auf 500 Zeichen."""
        long_schema = "X" * 1000
        doc_service.collect_schema(long_schema)
        context = doc_service.generate_readme_context()
        assert "..." in context  # Truncation-Marker

    def test_handles_empty_techstack(self, doc_service):
        """Behandelt leeren TechStack."""
        context = doc_service.generate_readme_context()
        assert "unbekannt" in context


class TestGenerateChangelogEntries:
    """Tests für CHANGELOG-Generierung."""

    def test_empty_iterations_message(self, doc_service):
        """Leere Iterationen geben Hinweis."""
        result = doc_service.generate_changelog_entries()
        assert "Keine Iterations-Daten" in result

    def test_sorts_iterations_descending(self, doc_service):
        """Sortiert Iterationen absteigend."""
        doc_service.collect_iteration(1, "First", "success")
        doc_service.collect_iteration(2, "Second", "success")
        result = doc_service.generate_changelog_entries()
        # Iteration 2 sollte vor Iteration 1 kommen
        idx_2 = result.find("Iteration 2")
        idx_1 = result.find("Iteration 1")
        assert idx_2 < idx_1

    def test_shows_status_emoji(self, doc_service):
        """Zeigt Status als Text."""
        doc_service.collect_iteration(1, "changes", "success")
        doc_service.collect_iteration(2, "changes", "failed")
        result = doc_service.generate_changelog_entries()
        assert "OK" in result
        assert "FEHLER" in result

    def test_includes_changes_section(self, doc_service):
        """Enthält Änderungen-Abschnitt."""
        doc_service.collect_iteration(1, "Neue Funktion hinzugefügt", "success")
        result = doc_service.generate_changelog_entries()
        assert "Neue Funktion hinzugefügt" in result

    def test_includes_review_section(self, doc_service):
        """Enthält Review-Abschnitt wenn vorhanden."""
        doc_service.collect_iteration(1, "changes", "success", review_summary="Code sieht gut aus")
        result = doc_service.generate_changelog_entries()
        assert "Code sieht gut aus" in result


# =========================================================================
# Test: get_summary und export_to_json
# =========================================================================

class TestGetSummary:
    """Tests für Zusammenfassung."""

    def test_includes_goal_truncated(self, doc_service):
        """Kürzt Ziel auf 100 Zeichen."""
        long_goal = "X" * 200
        doc_service.collect_goal(long_goal)
        summary = doc_service.get_summary()
        assert len(summary["goal"]) == 100

    def test_counts_code_files(self, doc_service):
        """Zählt Code-Dateien."""
        doc_service.collect_code_file("a.py", "code")
        doc_service.collect_code_file("b.py", "code")
        summary = doc_service.get_summary()
        assert summary["code_files_count"] == 2

    def test_counts_iterations(self, doc_service):
        """Zählt Iterationen."""
        doc_service.collect_iteration(1, "changes", "success")
        doc_service.collect_iteration(2, "changes", "success")
        summary = doc_service.get_summary()
        assert summary["iterations_count"] == 2

    def test_includes_techstack_info(self, doc_service, sample_techstack):
        """Enthält TechStack-Info."""
        doc_service.collect_techstack(sample_techstack)
        summary = doc_service.get_summary()
        assert summary["techstack"] == "web"
        assert summary["language"] == "Python"


class TestExportToJson:
    """Tests für JSON-Export."""

    def test_returns_valid_json(self, doc_service):
        """Gibt valides JSON zurück."""
        doc_service.collect_goal("Test")
        result = doc_service.export_to_json()
        parsed = json.loads(result)
        assert "goal" in parsed

    def test_includes_all_data(self, doc_service, sample_techstack):
        """Enthält alle Daten."""
        doc_service.collect_goal("Test Goal")
        doc_service.collect_techstack(sample_techstack)
        doc_service.collect_iteration(1, "changes", "success")
        result = json.loads(doc_service.export_to_json())
        assert result["goal"] == "Test Goal"
        assert result["techstack"]["language"] == "Python"
        assert len(result["iterations"]) == 1

    def test_includes_metadata(self, doc_service, tmp_path):
        """Enthält Metadaten."""
        doc_service.set_project_path(str(tmp_path))
        result = json.loads(doc_service.export_to_json())
        assert "created_at" in result
        assert "project_path" in result


# =========================================================================
# Test: Dateispeicherung
# =========================================================================

class TestFileSaving:
    """Tests für Dateispeicherung."""

    def test_save_readme_without_path_returns_none(self, doc_service):
        """save_readme ohne Pfad gibt None zurück."""
        result = doc_service.save_readme("# README")
        assert result is None

    def test_save_readme_creates_file(self, doc_service_with_path, tmp_path):
        """save_readme erstellt Datei."""
        content = "# Test README"
        path = doc_service_with_path.save_readme(content)
        assert path is not None
        assert os.path.exists(path)
        with open(path, 'r', encoding='utf-8') as f:
            assert f.read() == content

    def test_save_changelog_without_path_returns_none(self, doc_service):
        """save_changelog ohne Pfad gibt None zurück."""
        result = doc_service.save_changelog()
        assert result is None

    def test_save_changelog_creates_file(self, doc_service_with_path, tmp_path):
        """save_changelog erstellt Datei."""
        doc_service_with_path.collect_iteration(1, "changes", "success")
        path = doc_service_with_path.save_changelog()
        assert path is not None
        assert os.path.exists(path)


# =========================================================================
# Test: Dart AI Feature-Dokumentation
# =========================================================================

class TestDartAIFeatures:
    """Tests für Dart AI Feature-Dokumentation."""

    def test_collect_anforderungen(self, doc_service):
        """collect_anforderungen speichert Anforderungen."""
        anforderungen = [
            {"id": "REQ-001", "titel": "Login", "kategorie": "Auth"},
            {"id": "REQ-002", "titel": "Logout", "kategorie": "Auth"}
        ]
        doc_service.collect_anforderungen(anforderungen)
        assert len(doc_service.data["anforderungen"]) == 2

    def test_collect_features(self, doc_service):
        """collect_features speichert Features."""
        features = [
            {"id": "FEAT-001", "titel": "User Auth", "anforderungen": ["REQ-001"]}
        ]
        doc_service.collect_features(features)
        assert len(doc_service.data["features"]) == 1

    def test_collect_tasks(self, doc_service):
        """collect_tasks speichert Tasks."""
        tasks = [
            {"id": "TASK-001", "beschreibung": "Login implementieren"}
        ]
        doc_service.collect_tasks(tasks)
        assert len(doc_service.data["tasks"]) == 1

    def test_collect_file_by_file_plan(self, doc_service):
        """collect_file_by_file_plan speichert Plan."""
        plan = {
            "files": [
                {"path": "auth.py", "description": "Auth Modul", "priority": 1},
                {"path": "user.py", "description": "User Modul", "priority": 2}
            ]
        }
        doc_service.collect_file_by_file_plan(plan)
        assert doc_service.data["file_by_file_plan"]["total_files"] == 2

    def test_collect_file_generation_result_success(self, doc_service):
        """collect_file_generation_result speichert Erfolg."""
        doc_service.collect_file_generation_result("app.py", True, lines=100)
        assert doc_service.data["file_generations"][0]["success"] is True
        assert doc_service.data["file_generations"][0]["lines"] == 100

    def test_collect_file_generation_result_failure(self, doc_service):
        """collect_file_generation_result speichert Fehler."""
        doc_service.collect_file_generation_result("app.py", False, error="Syntax Error")
        assert doc_service.data["file_generations"][0]["success"] is False
        assert "Syntax Error" in doc_service.data["file_generations"][0]["error"]

    def test_truncates_file_generation_error(self, doc_service):
        """Kürzt Fehler auf 200 Zeichen."""
        long_error = "X" * 300
        doc_service.collect_file_generation_result("app.py", False, error=long_error)
        assert len(doc_service.data["file_generations"][0]["error"]) == 200
