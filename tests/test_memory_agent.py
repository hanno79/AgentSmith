# -*- coding: utf-8 -*-
"""
Tests für memory_agent.py
"""

import os
import json
import pytest
from agents.memory_agent import (
    load_memory,
    save_memory,
    update_memory,
    get_lessons_for_prompt,
    learn_from_error
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

        # Verify
        assert "pritn" in lessons

        loaded = load_memory(temp_memory_file)
        assert len(loaded["history"]) == 1
        assert len(loaded["lessons"]) == 1

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
