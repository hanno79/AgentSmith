# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 06.02.2026
Version: 1.0
Beschreibung: Tests fuer PatchMode-Funktionen in dev_loop_coder.py.
              Testet: _get_current_code_dict, _is_targeted_fix_context,
              _get_affected_files_from_feedback, _clean_model_output
"""

import os
import pytest
from unittest.mock import MagicMock

# AENDERUNG 08.02.2026: Refactoring — Utilities in eigenes Modul verschoben
from backend.dev_loop_coder_utils import (
    _get_current_code_dict,
    rebuild_current_code_from_disk,
    _is_targeted_fix_context,
    _get_affected_files_from_feedback,
    _clean_model_output,
)


# ---------------------------------------------------------------------------
# 1. Tests fuer _get_current_code_dict
# ---------------------------------------------------------------------------

class TestGetCurrentCodeDict:
    """Tests fuer _get_current_code_dict(manager)."""

    def test_current_code_already_dict(self):
        """Wenn manager.current_code bereits ein Dict ist, wird es direkt zurueckgegeben."""
        manager = MagicMock()
        manager.current_code = {"app.py": "print('hello')", "utils.py": "x = 1"}
        result = _get_current_code_dict(manager)
        assert result == manager.current_code, (
            "Erwartet: Dict wird direkt zurueckgegeben wenn current_code ein Dict ist"
        )

    def test_reads_files_from_disk(self, tmp_path):
        """Liest Projekt-Dateien korrekt von der Festplatte."""
        # Erstelle Test-Dateien
        (tmp_path / "main.py").write_text("print('main')", encoding="utf-8")
        (tmp_path / "utils.js").write_text("console.log('utils')", encoding="utf-8")

        manager = MagicMock()
        manager.current_code = "some string output"
        manager.project_path = str(tmp_path)

        result = _get_current_code_dict(manager)
        assert "main.py" in result, "Erwartet: main.py wurde gelesen"
        assert "utils.js" in result, "Erwartet: utils.js wurde gelesen"
        assert result["main.py"] == "print('main')", (
            "Erwartet: Inhalt von main.py korrekt gelesen"
        )
        assert result["utils.js"] == "console.log('utils')", (
            "Erwartet: Inhalt von utils.js korrekt gelesen"
        )

    def test_skips_excluded_directories(self, tmp_path):
        """Ueberspringt .git, node_modules, __pycache__ Verzeichnisse."""
        # Erstelle erlaubte Datei
        (tmp_path / "app.py").write_text("ok", encoding="utf-8")

        # Erstelle Dateien in auszuschliessenden Verzeichnissen
        for skip_dir in [".git", "node_modules", "__pycache__"]:
            d = tmp_path / skip_dir
            d.mkdir()
            (d / "should_skip.py").write_text("skip me", encoding="utf-8")

        manager = MagicMock()
        manager.current_code = "string"
        manager.project_path = str(tmp_path)

        result = _get_current_code_dict(manager)
        assert "app.py" in result, "Erwartet: app.py wurde gelesen"
        for key in result:
            assert ".git" not in key, f"Erwartet: .git-Dateien uebersprungen, aber gefunden: {key}"
            assert "node_modules" not in key, (
                f"Erwartet: node_modules-Dateien uebersprungen, aber gefunden: {key}"
            )
            assert "__pycache__" not in key, (
                f"Erwartet: __pycache__-Dateien uebersprungen, aber gefunden: {key}"
            )

    def test_only_code_extensions(self, tmp_path):
        """Nur Dateien mit Code-Extensions werden gelesen."""
        (tmp_path / "app.py").write_text("python code", encoding="utf-8")
        (tmp_path / "style.css").write_text("body {}", encoding="utf-8")
        (tmp_path / "image.png").write_bytes(b"\x89PNG")
        (tmp_path / "data.bin").write_bytes(b"\x00\x01")
        (tmp_path / "readme.md").write_text("# Readme", encoding="utf-8")

        manager = MagicMock()
        manager.current_code = "string"
        manager.project_path = str(tmp_path)

        result = _get_current_code_dict(manager)
        assert "app.py" in result, "Erwartet: .py-Datei wird gelesen"
        assert "style.css" in result, "Erwartet: .css-Datei wird gelesen"
        assert "readme.md" in result, "Erwartet: .md-Datei wird gelesen"
        assert "image.png" not in result, "Erwartet: .png-Datei wird uebersprungen"
        assert "data.bin" not in result, "Erwartet: .bin-Datei wird uebersprungen"

    def test_empty_directory(self, tmp_path):
        """Leeres Verzeichnis ergibt leeres Dict."""
        manager = MagicMock()
        manager.current_code = "string"
        manager.project_path = str(tmp_path)

        result = _get_current_code_dict(manager)
        assert result == {}, "Erwartet: Leeres Dict bei leerem Verzeichnis"

    def test_nonexistent_directory(self):
        """Nicht existentes Verzeichnis ergibt leeres Dict."""
        manager = MagicMock()
        manager.current_code = "string"
        manager.project_path = "/pfad/der/nicht/existiert/xyz_fake_12345"

        result = _get_current_code_dict(manager)
        assert result == {}, "Erwartet: Leeres Dict bei nicht existentem Verzeichnis"

    def test_no_project_path(self):
        """Kein project_path am Manager ergibt leeres Dict."""
        manager = MagicMock(spec=[])
        # manager hat kein project_path-Attribut

        result = _get_current_code_dict(manager)
        assert result == {}, "Erwartet: Leeres Dict wenn project_path fehlt"

    def test_relative_paths_with_forward_slashes(self, tmp_path):
        """Relative Pfade werden mit Forward-Slashes normalisiert."""
        sub = tmp_path / "src"
        sub.mkdir()
        (sub / "app.py").write_text("code", encoding="utf-8")

        manager = MagicMock()
        manager.current_code = "string"
        manager.project_path = str(tmp_path)

        result = _get_current_code_dict(manager)
        # Alle Pfade sollen Forward-Slashes verwenden (kein Backslash)
        for key in result:
            assert "\\" not in key, (
                f"Erwartet: Forward-Slashes in Pfad, aber Backslash gefunden: {key}"
            )
        assert "src/app.py" in result, "Erwartet: Relativer Pfad src/app.py im Dict"


# ---------------------------------------------------------------------------
# 2. Tests fuer _is_targeted_fix_context
# ---------------------------------------------------------------------------

class TestIsTargetedFixContext:
    """Tests fuer _is_targeted_fix_context(feedback)."""

    @pytest.mark.parametrize("error_type", [
        "TypeError: unsupported operand type",
        "NameError: name 'x' is not defined",
        "SyntaxError: invalid syntax",
        "ImportError: No module named 'foo'",
        "AttributeError: 'NoneType' has no attribute 'bar'",
        "KeyError: 'missing_key'",
        "ValueError: invalid literal for int()",
        "ModuleNotFoundError: No module named 'baz'",
    ])
    def test_python_error_types(self, error_type):
        """Python-Error-Types werden als gezielter Fix erkannt."""
        assert _is_targeted_fix_context(error_type) is True, (
            f"Erwartet: True fuer Python-Error '{error_type}'"
        )

    @pytest.mark.parametrize("deutsch", [
        "Syntaxfehler in Zeile 42",
        "Fehler: Datei konnte nicht geladen werden",
        "Eingabe ungültig - Wert erwartet",
        "Test fehlgeschlagen bei Funktion X",
        "Variable nicht gefunden im Scope",
        "Ausdruck nicht definiert",
        "Code fehlerhaft - Klammer fehlt",
        "Formatierung der Ausgabe falsch",
    ])
    def test_deutsche_fehlerbegriffe(self, deutsch):
        """Deutsche Fehlerbegriffe werden erkannt."""
        assert _is_targeted_fix_context(deutsch) is True, (
            f"Erwartet: True fuer deutschen Fehlerbegriff '{deutsch}'"
        )

    @pytest.mark.parametrize("additive", [
        "Erstelle test fuer die Login-Funktion",
        "Fehlende tests/ Dateien ergaenzen",
        "Bitte documentation hinzufügen",
        "Neue Datei add: helpers.py",
        "PFLICHT: Unit-Tests schreiben",
    ])
    def test_additive_indicators(self, additive):
        """Additive Indikatoren (test, documentation, etc.) werden erkannt."""
        assert _is_targeted_fix_context(additive) is True, (
            f"Erwartet: True fuer additiven Indikator '{additive}'"
        )

    def test_leeres_feedback(self):
        """Leeres Feedback ergibt False."""
        assert _is_targeted_fix_context("") is False, (
            "Erwartet: False fuer leeres Feedback"
        )
        assert _is_targeted_fix_context(None) is False, (
            "Erwartet: False fuer None-Feedback"
        )

    def test_generisches_feedback_ohne_indikatoren(self):
        """Generisches Feedback ohne bekannte Indikatoren ergibt False."""
        generic = "Alles sieht gut aus, weiter so"
        assert _is_targeted_fix_context(generic) is False, (
            f"Erwartet: False fuer generisches Feedback '{generic}'"
        )


# ---------------------------------------------------------------------------
# 3. Tests fuer _get_affected_files_from_feedback
# ---------------------------------------------------------------------------

class TestGetAffectedFilesFromFeedback:
    """Tests fuer _get_affected_files_from_feedback(feedback)."""

    def test_python_traceback(self):
        """Extrahiert Dateinamen aus Python-Traceback."""
        feedback = (
            'Traceback (most recent call last):\n'
            '  File "app.py", line 10, in main\n'
            '  File "utils.py", line 5, in helper\n'
            'TypeError: unsupported operand'
        )
        result = _get_affected_files_from_feedback(feedback)
        assert "app.py" in result, "Erwartet: app.py aus Traceback extrahiert"
        assert "utils.py" in result, "Erwartet: utils.py aus Traceback extrahiert"

    def test_javascript_dateien(self):
        """Extrahiert .js/.jsx/.tsx Dateinamen."""
        feedback = "Error in app.js: unexpected token\nAlso check component.jsx: missing import"
        result = _get_affected_files_from_feedback(feedback)
        assert "app.js" in result, "Erwartet: app.js extrahiert"
        assert "component.jsx" in result, "Erwartet: component.jsx extrahiert"

    def test_tests_pfade(self):
        """Extrahiert Test-Dateien aus tests/ Pfaden."""
        feedback = "FAILED tests/test_login.py::test_auth - AssertionError"
        result = _get_affected_files_from_feedback(feedback)
        assert "test_login.py" in result, "Erwartet: test_login.py aus tests/ Pfad extrahiert"

    def test_filtert_system_pfade(self):
        """System-Pfade (site-packages, python3) werden herausgefiltert."""
        feedback = (
            'File "/usr/lib/python3/site-packages/requests/api.py", line 10\n'
            'File "app.py", line 5, in main'
        )
        result = _get_affected_files_from_feedback(feedback)
        # app.py sollte drin sein, aber api.py aus site-packages nicht
        assert "app.py" in result, "Erwartet: app.py wurde extrahiert"
        for f in result:
            assert "api.py" != f or "site-packages" not in feedback.lower(), (
                "Erwartet: Dateien aus site-packages werden nicht extrahiert"
            )

    def test_leeres_feedback(self):
        """Leeres Feedback ergibt leere Liste."""
        assert _get_affected_files_from_feedback("") == [], (
            "Erwartet: Leere Liste bei leerem Feedback"
        )
        assert _get_affected_files_from_feedback(None) == [], (
            "Erwartet: Leere Liste bei None-Feedback"
        )

    def test_max_30_dateien_limit(self):
        """Maximal 30 Dateien werden zurueckgegeben (Fix 53: Limit von 5 auf 30 erhoeht)."""
        # AENDERUNG 14.02.2026: Limit an Fix 53 angepasst (5 → 30)
        lines = [f'File "module_{i}.py", line {i}' for i in range(40)]
        feedback = "\n".join(lines)
        result = _get_affected_files_from_feedback(feedback)
        assert len(result) <= 30, (
            f"Erwartet: Maximal 30 Dateien, erhalten: {len(result)}"
        )

    def test_keine_duplikate(self):
        """Gleiche Dateinamen werden nicht doppelt aufgelistet."""
        feedback = (
            'File "app.py", line 10\n'
            'File "app.py", line 20\n'
            'File "app.py", line 30'
        )
        result = _get_affected_files_from_feedback(feedback)
        assert result.count("app.py") == 1, (
            "Erwartet: app.py nur einmal in der Liste"
        )


# ---------------------------------------------------------------------------
# 4. Tests fuer _clean_model_output
# ---------------------------------------------------------------------------

class TestCleanModelOutput:
    """Tests fuer _clean_model_output(raw_output)."""

    def test_entfernt_think_bloecke(self):
        """Entfernt <think>...</think> Bloecke komplett."""
        raw = "<think>Ich denke nach...</think>### FILENAME: app.py\nprint('hello')"
        result = _clean_model_output(raw)
        assert "<think>" not in result, "Erwartet: <think>-Tag entfernt"
        assert "Ich denke nach" not in result, "Erwartet: Think-Inhalt entfernt"
        assert "print('hello')" in result, "Erwartet: Code bleibt erhalten"

    def test_entfernt_mehrzeilige_think_bloecke(self):
        """Entfernt mehrzeilige <think>-Bloecke."""
        raw = (
            "<think>\nSchritt 1: Analysiere\n"
            "Schritt 2: Plane\n</think>\n"
            "### FILENAME: main.py\ncode_here"
        )
        result = _clean_model_output(raw)
        assert "Schritt 1" not in result, "Erwartet: Mehrzeiliger Think-Inhalt entfernt"
        assert "code_here" in result, "Erwartet: Code nach Think-Block erhalten"

    def test_entfernt_einzelne_think_tags(self):
        """Entfernt einzelne <think> oder </think> Tags."""
        raw = "<think>code\n### FILENAME: app.py\nprint('x')"
        result = _clean_model_output(raw)
        assert "<think>" not in result, "Erwartet: Einzelner <think>-Tag entfernt"

    def test_schneidet_bei_filename_prefix(self):
        """Schneidet unerwuenschten Content vor ### FILENAME: ab."""
        raw = "Hier ist mein Code fuer dich:\n### FILENAME: app.py\nprint('hello')"
        result = _clean_model_output(raw)
        assert result.startswith("### FILENAME:"), (
            "Erwartet: Output beginnt mit ### FILENAME:"
        )

    def test_leerer_input(self):
        """Leerer oder None Input wird zurueckgegeben."""
        assert _clean_model_output("") == "", "Erwartet: Leerer String bei leerem Input"
        assert _clean_model_output(None) is None, "Erwartet: None bei None-Input"

    def test_normaler_code_unveraendert(self):
        """Normaler Code ohne spezielle Tags bleibt unveraendert."""
        code = "def hello():\n    print('world')\n\nhello()"
        result = _clean_model_output(code)
        assert result == code, "Erwartet: Normaler Code bleibt unveraendert"

    def test_code_mit_code_block_prefix(self):
        """Code-Block mit kurzem Prefix wird bereinigt."""
        raw = "OK\n```python\ndef foo():\n    pass\n```"
        result = _clean_model_output(raw)
        assert result.startswith("```"), (
            "Erwartet: Kurzer Prefix vor Code-Block wird entfernt"
        )

    def test_code_block_mit_sinnvollem_prefix_bleibt(self):
        """Code-Block mit sinnvollem Prefix (hier, following, etc.) bleibt."""
        raw = "Hier ist der Code:\n```python\ndef foo():\n    pass\n```"
        result = _clean_model_output(raw)
        assert "Hier ist der Code" in result, (
            "Erwartet: Sinnvoller Prefix bleibt erhalten"
        )


# ---------------------------------------------------------------------------
# 5. Tests fuer rebuild_current_code_from_disk
# ---------------------------------------------------------------------------

class TestRebuildCurrentCodeFromDisk:
    """Tests fuer rebuild_current_code_from_disk(manager) - PatchMode Merge Fix."""

    def test_rekonstruiert_alle_dateien(self, tmp_path):
        """Rekonstruiert current_code mit ALLEN Dateien von der Festplatte."""
        (tmp_path / "package.json").write_text('{"name": "test"}', encoding="utf-8")
        (tmp_path / "app.js").write_text("console.log('app')", encoding="utf-8")
        sub = tmp_path / "src"
        sub.mkdir()
        (sub / "index.jsx").write_text("<App />", encoding="utf-8")

        manager = MagicMock()
        manager.current_code = "### FILENAME: app.js\nconsole.log('old')"
        manager.project_path = str(tmp_path)

        result = rebuild_current_code_from_disk(manager)
        assert "### FILENAME: package.json" in result, (
            "Erwartet: package.json im rekonstruierten Code"
        )
        assert "### FILENAME: app.js" in result, (
            "Erwartet: app.js im rekonstruierten Code"
        )
        assert "### FILENAME: src/index.jsx" in result, (
            "Erwartet: src/index.jsx im rekonstruierten Code"
        )
        # Inhalt von Festplatte, nicht alter current_code
        assert "console.log('app')" in result, (
            "Erwartet: Aktueller Inhalt von Festplatte, nicht alter Code"
        )
        assert "console.log('old')" not in result, (
            "Erwartet: Alter current_code Inhalt nicht mehr vorhanden"
        )

    def test_patchmode_merge_szenario(self, tmp_path):
        """Simuliert PatchMode: 2 gepatcht + 11 alte auf Festplatte -> alle 13 im Output."""
        # Erstelle 5 Dateien (simuliert groesseres Projekt)
        dateien = {
            "package.json": '{"test": "playwright test"}',
            "app.js": "const App = () => 'Hello'",
            "index.html": "<html><body></body></html>",
            "style.css": "body { margin: 0 }",
            "config.json": '{"port": 3000}',
        }
        for name, content in dateien.items():
            (tmp_path / name).write_text(content, encoding="utf-8")

        manager = MagicMock()
        # Simuliere PatchMode-Output: nur 2 Dateien
        manager.current_code = (
            "### FILENAME: package.json\n{\"test\": \"playwright test\"}\n\n"
            "### FILENAME: app.js\nconst App = () => 'Hello'"
        )
        manager.project_path = str(tmp_path)

        result = rebuild_current_code_from_disk(manager)

        # Alle 5 Dateien muessen im rekonstruierten Code sein
        for name in dateien:
            assert f"### FILENAME: {name}" in result, (
                f"Erwartet: {name} im rekonstruierten Code enthalten"
            )
        # Inhalte von Festplatte
        assert '"test": "playwright test"' in result, (
            "Erwartet: Gepatchter package.json Inhalt"
        )
        assert '{"port": 3000}' in result, (
            "Erwartet: Ungepatchte config.json ebenfalls enthalten"
        )

    def test_leeres_projekt_fallback(self):
        """Bei leerem Projekt wird bestehender current_code zurueckgegeben."""
        manager = MagicMock()
        manager.current_code = "alter code"
        manager.project_path = "/pfad/der/nicht/existiert/xyz_fake_12345"

        result = rebuild_current_code_from_disk(manager)
        assert result == "alter code", (
            "Erwartet: Fallback auf bestehenden current_code bei nicht existentem Pfad"
        )

    def test_sortierte_reihenfolge(self, tmp_path):
        """Dateien werden alphabetisch sortiert ausgegeben."""
        (tmp_path / "z_last.py").write_text("z", encoding="utf-8")
        (tmp_path / "a_first.py").write_text("a", encoding="utf-8")
        (tmp_path / "m_middle.py").write_text("m", encoding="utf-8")

        manager = MagicMock()
        manager.current_code = ""
        manager.project_path = str(tmp_path)

        result = rebuild_current_code_from_disk(manager)
        pos_a = result.index("a_first.py")
        pos_m = result.index("m_middle.py")
        pos_z = result.index("z_last.py")
        assert pos_a < pos_m < pos_z, (
            "Erwartet: Dateien alphabetisch sortiert (a < m < z)"
        )
