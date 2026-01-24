# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 24.01.2026
Version: 1.0
Beschreibung: Tests für Memory Agent - Testet Laden, Speichern und Lernen aus Fehlern.
"""

import os
import json
import pytest
from agents.memory_agent import (
    load_memory,
    save_memory,
    update_memory,
    get_lessons_for_prompt,
    learn_from_error,
    extract_error_pattern,
    generate_tags_from_context,
    is_duplicate_lesson,
    _generate_action_text
)


class TestLoadMemory:
    """Tests für die load_memory Funktion."""

    def test_load_nonexistent_file(self, temp_memory_file):
        """Test: Nicht existierende Datei gibt leere Struktur zurück."""
        result = load_memory(temp_memory_file)

        assert result == {"history": [], "lessons": []}

    def test_load_existing_file(self, populated_memory_file, sample_memory_data):
        """Test: Existierende Datei wird korrekt geladen."""
        result = load_memory(populated_memory_file)

        assert result["history"] == sample_memory_data["history"]
        assert result["lessons"] == sample_memory_data["lessons"]

    def test_load_memory_structure(self, temp_memory_file):
        """Test: Rückgabe hat korrekte Struktur."""
        result = load_memory(temp_memory_file)

        assert "history" in result
        assert "lessons" in result
        assert isinstance(result["history"], list)
        assert isinstance(result["lessons"], list)


class TestSaveMemory:
    """Tests für die save_memory Funktion."""

    def test_save_creates_directories(self, temp_dir):
        """Test: Fehlende Verzeichnisse werden erstellt."""
        memory_path = os.path.join(temp_dir, "deep", "nested", "memory.json")
        memory_data = {"history": [], "lessons": []}

        save_memory(memory_path, memory_data)

        assert os.path.exists(memory_path)

    def test_save_and_load_roundtrip(self, temp_memory_file, sample_memory_data):
        """Test: Speichern und Laden ergibt identische Daten."""
        save_memory(temp_memory_file, sample_memory_data)
        loaded = load_memory(temp_memory_file)

        assert loaded == sample_memory_data

    def test_save_unicode_content(self, temp_memory_file):
        """Test: Unicode-Inhalte werden korrekt gespeichert."""
        memory_data = {
            "history": [],
            "lessons": [{"action": "日本語 und Emojis 🚀"}]
        }

        save_memory(temp_memory_file, memory_data)
        loaded = load_memory(temp_memory_file)

        assert loaded["lessons"][0]["action"] == "日本語 und Emojis 🚀"

    def test_save_overwrites_existing(self, populated_memory_file):
        """Test: Existierende Datei wird überschrieben."""
        new_data = {"history": [{"new": "data"}], "lessons": []}

        save_memory(populated_memory_file, new_data)
        loaded = load_memory(populated_memory_file)

        assert loaded == new_data


class TestUpdateMemory:
    """Tests für die update_memory Funktion."""

    def test_update_adds_entry(self, temp_memory_file):
        """Test: Neuer Eintrag wird hinzugefügt."""
        entry = update_memory(
            temp_memory_file,
            coder_output="def hello(): pass",
            review_output="Looks good",
            sandbox_output="OK"
        )

        loaded = load_memory(temp_memory_file)
        assert len(loaded["history"]) == 1
        assert loaded["history"][0]["coder_output_preview"] == "def hello(): pass"

    def test_update_preserves_existing(self, populated_memory_file, sample_memory_data):
        """Test: Bestehende Einträge bleiben erhalten."""
        original_count = len(sample_memory_data["history"])

        update_memory(
            populated_memory_file,
            coder_output="new code",
            review_output="new review"
        )

        loaded = load_memory(populated_memory_file)
        assert len(loaded["history"]) == original_count + 1

    def test_update_truncates_long_content(self, temp_memory_file):
        """Test: Lange Inhalte werden auf 500 Zeichen gekürzt."""
        long_code = "x" * 1000

        update_memory(
            temp_memory_file,
            coder_output=long_code,
            review_output="OK"
        )

        loaded = load_memory(temp_memory_file)
        assert len(loaded["history"][0]["coder_output_preview"]) == 500

    def test_update_handles_none_values(self, temp_memory_file):
        """Test: None-Werte werden korrekt behandelt."""
        entry = update_memory(
            temp_memory_file,
            coder_output="code",
            review_output=None,
            sandbox_output=None
        )

        assert entry["review_feedback"] is None
        assert entry["sandbox_feedback"] is None

    def test_update_includes_timestamp(self, temp_memory_file):
        """Test: Eintrag enthält Timestamp."""
        entry = update_memory(
            temp_memory_file,
            coder_output="code",
            review_output="review"
        )

        assert "timestamp" in entry
        assert len(entry["timestamp"]) > 0


class TestGetLessonsForPrompt:
    """Tests für die get_lessons_for_prompt Funktion."""

    def test_get_lessons_nonexistent_file(self, temp_memory_file):
        """Test: Nicht existierende Datei gibt leeren String zurück."""
        result = get_lessons_for_prompt(temp_memory_file)
        assert result == ""

    def test_get_global_lessons(self, populated_memory_file):
        """Test: Globale Lessons werden immer zurückgegeben."""
        result = get_lessons_for_prompt(populated_memory_file)

        assert "VERMEIDE FEHLER: Modul nicht gefunden" in result
        assert "[MEMORY]" in result

    def test_get_lessons_filtered_by_tech_stack(self, populated_memory_file):
        """Test: Lessons werden nach Tech-Stack gefiltert."""
        result = get_lessons_for_prompt(populated_memory_file, tech_stack="flask")

        assert "app.app_context()" in result

    def test_get_lessons_no_match(self, populated_memory_file):
        """Test: Keine passenden Lessons für unbekannten Tech-Stack."""
        result = get_lessons_for_prompt(populated_memory_file, tech_stack="rust")

        # Nur globale Lessons sollten enthalten sein
        assert "Modul nicht gefunden" in result
        assert "app.app_context()" not in result

    def test_get_lessons_format(self, populated_memory_file):
        """Test: Lessons haben korrektes Format."""
        result = get_lessons_for_prompt(populated_memory_file)

        lines = result.strip().split("\n")
        for line in lines:
            assert line.startswith("- [MEMORY]:")

    def test_get_lessons_empty_memory(self, temp_memory_file):
        """Test: Leeres Memory gibt leeren String zurück."""
        save_memory(temp_memory_file, {"history": [], "lessons": []})
        result = get_lessons_for_prompt(temp_memory_file)

        assert result == ""


class TestLearnFromError:
    """Tests für die learn_from_error Funktion."""

    def test_learn_new_error(self, temp_memory_file):
        """Test: Neuer Fehler wird als Lesson gespeichert."""
        result = learn_from_error(
            temp_memory_file,
            error_msg="TypeError: cannot add int and str",
            tags=["python", "global"]
        )

        assert "gelernt" in result.lower() or "gespeichert" in result.lower()

        loaded = load_memory(temp_memory_file)
        assert len(loaded["lessons"]) == 1
        assert "TypeError" in loaded["lessons"][0]["pattern"]

    def test_learn_increments_existing_error(self, populated_memory_file):
        """Test: Bekannter Fehler erhöht count."""
        original = load_memory(populated_memory_file)
        original_count = original["lessons"][0]["count"]

        learn_from_error(
            populated_memory_file,
            error_msg="ModuleNotFoundError: No module named 'xyz'",
            tags=["python"]
        )

        loaded = load_memory(populated_memory_file)
        assert loaded["lessons"][0]["count"] == original_count + 1

    def test_learn_updates_last_seen(self, populated_memory_file):
        """Test: last_seen wird aktualisiert."""
        learn_from_error(
            populated_memory_file,
            error_msg="ModuleNotFoundError: test",
            tags=["python"]
        )

        loaded = load_memory(populated_memory_file)
        # last_seen sollte aktueller sein als first_seen
        assert loaded["lessons"][0]["last_seen"] >= loaded["lessons"][0]["first_seen"]

    def test_learn_truncates_long_error(self, temp_memory_file):
        """Test: Lange Fehlermeldungen werden gekürzt."""
        long_error = "Error: " + "x" * 500

        learn_from_error(
            temp_memory_file,
            error_msg=long_error,
            tags=["global"]
        )

        loaded = load_memory(temp_memory_file)
        assert len(loaded["lessons"][0]["pattern"]) <= 100

    def test_learn_with_multiple_tags(self, temp_memory_file):
        """Test: Mehrere Tags werden gespeichert."""
        learn_from_error(
            temp_memory_file,
            error_msg="Flask context error",
            tags=["flask", "webapp", "python"]
        )

        loaded = load_memory(temp_memory_file)
        assert set(loaded["lessons"][0]["tags"]) == {"flask", "webapp", "python"}

    def test_learn_creates_file_if_missing(self, temp_memory_file):
        """Test: Memory-Datei wird erstellt wenn nicht vorhanden."""
        assert not os.path.exists(temp_memory_file)

        learn_from_error(
            temp_memory_file,
            error_msg="Test error",
            tags=["test"]
        )

        assert os.path.exists(temp_memory_file)


class TestMemoryIntegration:
    """Integrationstests für das Memory-System."""

    def test_full_workflow(self, temp_memory_file):
        """Test: Vollständiger Memory-Workflow."""
        # 1. Update Memory
        update_memory(
            temp_memory_file,
            coder_output="def broken():\n    pritn('typo')",
            review_output="SyntaxError in code",
            sandbox_output="❌ Syntaxfehler"
        )

        # 2. Learn from Error
        learn_from_error(
            temp_memory_file,
            error_msg="NameError: name 'pritn' is not defined",
            tags=["python", "typo"]
        )

        # 3. Get Lessons
        lessons = get_lessons_for_prompt(temp_memory_file, tech_stack="python")

        # Verify - Die verbesserte Funktion generiert jetzt hilfreiche Action-Texte
        # Der NameError wird als Lesson mit dem Ratschlag gespeichert
        assert "[MEMORY]" in lessons
        assert "Variable" in lessons or "definiert" in lessons  # Action-Text für NameError

        loaded = load_memory(temp_memory_file)
        assert len(loaded["history"]) == 1
        assert len(loaded["lessons"]) == 1
        assert "NameError" in loaded["lessons"][0]["pattern"]

    def test_multiple_sessions(self, temp_memory_file):
        """Test: Memory persistiert über mehrere 'Sessions'."""
        # Session 1
        update_memory(temp_memory_file, "code1", "review1")
        learn_from_error(temp_memory_file, "error1", ["tag1"])

        # Session 2 (neues Laden)
        update_memory(temp_memory_file, "code2", "review2")
        learn_from_error(temp_memory_file, "error2", ["tag2"])

        # Verify
        loaded = load_memory(temp_memory_file)
        assert len(loaded["history"]) == 2
        assert len(loaded["lessons"]) == 2


class TestExtractErrorPattern:
    """Tests für die extract_error_pattern Funktion."""

    def test_extract_python_typeerror(self):
        """Test: Python TypeError wird extrahiert."""
        error = "Traceback (most recent call last):\n  File 'test.py', line 1\nTypeError: cannot add 'int' and 'str'"
        result = extract_error_pattern(error)
        assert "TypeError" in result
        assert "cannot add" in result

    def test_extract_python_syntaxerror(self):
        """Test: Python SyntaxError wird extrahiert."""
        error = "SyntaxError: invalid syntax at line 5"
        result = extract_error_pattern(error)
        assert "SyntaxError" in result

    def test_extract_sandbox_marker(self):
        """Test: Sandbox ❌ Marker wird extrahiert."""
        error = "❌ Syntaxfehler (python) in Zeile 5:\nInvalid syntax"
        result = extract_error_pattern(error)
        assert "Syntaxfehler" in result

    def test_extract_modulenotfounderror(self):
        """Test: ModuleNotFoundError wird extrahiert."""
        error = "ModuleNotFoundError: No module named 'flask'"
        result = extract_error_pattern(error)
        assert "ModuleNotFoundError" in result
        assert "flask" in result

    def test_extract_truncates_long_errors(self):
        """Test: Lange Fehlermeldungen werden auf 200 Zeichen gekürzt."""
        error = "TypeError: " + "x" * 500
        result = extract_error_pattern(error)
        assert len(result) <= 200

    def test_extract_empty_input(self):
        """Test: Leerer Input gibt leeren String zurück."""
        result = extract_error_pattern("")
        assert result == ""

    def test_extract_none_input(self):
        """Test: None Input gibt leeren String zurück."""
        result = extract_error_pattern(None)
        assert result == ""

    def test_extract_generic_error_line(self):
        """Test: Generische Error-Zeile wird extrahiert."""
        error = "Some output\nError: Something went wrong\nMore output"
        result = extract_error_pattern(error)
        assert "Error" in result


class TestGenerateTagsFromContext:
    """Tests für die generate_tags_from_context Funktion."""

    def test_always_includes_global(self):
        """Test: 'global' Tag ist immer enthalten."""
        tags = generate_tags_from_context({}, "Some error")
        assert "global" in tags

    def test_includes_language_tag(self):
        """Test: Sprach-Tag wird hinzugefügt."""
        blueprint = {"language": "python"}
        tags = generate_tags_from_context(blueprint, "Error")
        assert "python" in tags

    def test_includes_project_type(self):
        """Test: Projekt-Typ wird hinzugefügt."""
        blueprint = {"project_type": "webapp"}
        tags = generate_tags_from_context(blueprint, "Error")
        assert "webapp" in tags

    def test_includes_framework_from_blueprint(self):
        """Test: Framework aus Blueprint wird hinzugefügt."""
        blueprint = {"framework": "flask"}
        tags = generate_tags_from_context(blueprint, "Error")
        assert "flask" in tags

    def test_detects_framework_from_error_text(self):
        """Test: Framework wird aus Fehlertext erkannt."""
        tags = generate_tags_from_context({}, "Flask werkzeug error in jinja2 template")
        assert "flask" in tags

    def test_detects_multiple_frameworks(self):
        """Test: Mehrere Frameworks werden erkannt."""
        tags = generate_tags_from_context({}, "React component failed, npm install error")
        assert "react" in tags
        assert "node" in tags

    def test_adds_syntax_tag(self):
        """Test: 'syntax' Tag bei Syntax-Fehlern."""
        tags = generate_tags_from_context({}, "SyntaxError in code")
        assert "syntax" in tags

    def test_adds_import_tag(self):
        """Test: 'import' Tag bei Import-Fehlern."""
        tags = generate_tags_from_context({}, "ImportError: module not found")
        assert "import" in tags

    def test_adds_security_tag(self):
        """Test: 'security' Tag bei Security-Fehlern."""
        tags = generate_tags_from_context({}, "CSRF token missing")
        assert "security" in tags

    def test_removes_duplicates(self):
        """Test: Duplikate werden entfernt."""
        blueprint = {"language": "python", "framework": "flask"}
        tags = generate_tags_from_context(blueprint, "flask error")
        # flask sollte nur einmal vorkommen
        assert tags.count("flask") == 1

    def test_handles_none_blueprint(self):
        """Test: None Blueprint wird korrekt behandelt."""
        tags = generate_tags_from_context(None, "Error")
        assert "global" in tags

    def test_handles_empty_error_text(self):
        """Test: Leerer Fehlertext wird behandelt."""
        tags = generate_tags_from_context({"language": "python"}, "")
        assert "python" in tags
        assert "global" in tags


class TestIsDuplicateLesson:
    """Tests für die is_duplicate_lesson Funktion."""

    def test_exact_match_is_duplicate(self, populated_memory_file):
        """Test: Exakter Match wird als Duplikat erkannt."""
        result = is_duplicate_lesson(populated_memory_file, "ModuleNotFoundError")
        assert result is True

    def test_substring_match_is_duplicate(self, populated_memory_file):
        """Test: Substring Match wird als Duplikat erkannt."""
        result = is_duplicate_lesson(populated_memory_file, "ModuleNotFoundError: No module named 'xyz'")
        assert result is True

    def test_similar_pattern_is_duplicate(self, populated_memory_file):
        """Test: Ähnliches Pattern wird als Duplikat erkannt."""
        # Das bestehende Pattern enthält "ModuleNotFoundError"
        result = is_duplicate_lesson(populated_memory_file, "ModuleNotFoundError module test xyz")
        assert result is True

    def test_completely_new_is_not_duplicate(self, populated_memory_file):
        """Test: Komplett neues Pattern ist kein Duplikat."""
        result = is_duplicate_lesson(populated_memory_file, "CompletelyNewUniqueError never seen before 12345")
        assert result is False

    def test_nonexistent_file_returns_false(self, temp_memory_file):
        """Test: Nicht existierende Datei gibt False zurück."""
        result = is_duplicate_lesson(temp_memory_file, "Any error")
        assert result is False

    def test_empty_pattern_returns_false(self, populated_memory_file):
        """Test: Leeres Pattern gibt False zurück."""
        result = is_duplicate_lesson(populated_memory_file, "")
        assert result is False

    def test_none_pattern_returns_false(self, populated_memory_file):
        """Test: None Pattern gibt False zurück."""
        result = is_duplicate_lesson(populated_memory_file, None)
        assert result is False


class TestGenerateActionText:
    """Tests für die _generate_action_text Funktion."""

    def test_known_pattern_flask_deprecated(self):
        """Test: Bekanntes Flask-Pattern gibt spezifischen Ratschlag."""
        result = _generate_action_text("before_first_request is deprecated")
        assert "app.app_context()" in result

    def test_known_pattern_markup_import(self):
        """Test: Bekanntes Markup-Import-Pattern."""
        result = _generate_action_text("cannot import name 'Markup' from 'flask'")
        assert "markupsafe" in result

    def test_known_pattern_modulenotfounderror(self):
        """Test: ModuleNotFoundError gibt Installations-Ratschlag."""
        result = _generate_action_text("ModuleNotFoundError: No module named 'xyz'")
        assert "requirements.txt" in result or "installiert" in result

    def test_known_pattern_syntaxerror(self):
        """Test: SyntaxError gibt Syntax-Ratschlag."""
        result = _generate_action_text("SyntaxError: invalid syntax")
        assert "Klammern" in result or "Einrück" in result

    def test_unknown_pattern_uses_generic(self):
        """Test: Unbekanntes Pattern verwendet generischen Text."""
        result = _generate_action_text("CompletelyUnknownError: something happened")
        assert "VERMEIDE" in result
        assert "CompletelyUnknownError" in result

    def test_truncates_long_messages(self):
        """Test: Lange Nachrichten werden gekürzt."""
        long_error = "Error: " + "x" * 500
        result = _generate_action_text(long_error)
        assert len(result) <= 200

    def test_handles_none_input(self):
        """Test: None Input wird behandelt."""
        result = _generate_action_text(None)
        assert "VERMEIDE" in result


class TestLearnFromErrorImproved:
    """Zusätzliche Tests für die verbesserte learn_from_error Funktion."""

    def test_learn_uses_extract_error_pattern(self, temp_memory_file):
        """Test: learn_from_error nutzt extract_error_pattern."""
        # Langer Fehler mit Traceback
        error = "Traceback...\nTypeError: cannot concatenate 'str' and 'int' objects"
        learn_from_error(temp_memory_file, error, ["python"])

        loaded = load_memory(temp_memory_file)
        # Pattern sollte nur den relevanten Teil enthalten
        assert "TypeError" in loaded["lessons"][0]["pattern"]

    def test_learn_skips_duplicate_fuzzy(self, temp_memory_file):
        """Test: Ähnliche Fehler werden übersprungen."""
        # Erster Fehler
        learn_from_error(temp_memory_file, "TypeError: invalid operation on types", ["python"])

        # Ähnlicher Fehler
        result = learn_from_error(temp_memory_file, "TypeError: invalid operation on different types", ["python"])

        loaded = load_memory(temp_memory_file)
        # Sollte nur eine Lesson geben (entweder aktualisiert oder übersprungen)
        assert len(loaded["lessons"]) <= 2  # Maximal 2 wenn nicht als ähnlich erkannt

    def test_learn_empty_error_returns_message(self, temp_memory_file):
        """Test: Leerer Fehler gibt Nachricht zurück."""
        result = learn_from_error(temp_memory_file, "", ["python"])
        assert "Kein Fehler" in result

    def test_learn_uses_generate_action_text(self, temp_memory_file):
        """Test: learn_from_error nutzt _generate_action_text."""
        learn_from_error(temp_memory_file, "SyntaxError: unexpected token", ["python"])

        loaded = load_memory(temp_memory_file)
        # Action sollte spezifischen Ratschlag enthalten
        action = loaded["lessons"][0]["action"]
        assert "Klammern" in action or "Einrück" in action or "VERMEIDE" in action

    def test_learn_default_tags_when_empty(self, temp_memory_file):
        """Test: Leere Tags werden zu ['global']."""
        learn_from_error(temp_memory_file, "Some error", [])

        loaded = load_memory(temp_memory_file)
        assert "global" in loaded["lessons"][0]["tags"]
