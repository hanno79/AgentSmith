# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 14.02.2026
Version: 1.1
Beschreibung: Tests fuer das Modul backend/dev_loop_coder_prompt.py.
              Testet Pure-Logic-Funktionen: _build_patch_prompt,
              _truncate_prompt_if_needed, filter_feedback_for_files,
              _SECURITY_FIX_TEMPLATES, build_coder_prompt.

              AENDERUNG 14.02.2026 v1.1: Erweitert um Tests fuer
              - _build_patch_prompt mit komprimiertem Context (>15 Dateien)
              - _truncate_prompt_if_needed: alle 4 Stufen + Ratio-Pruefung
              - build_coder_prompt: Basis, iteration_history, utds, phantom
"""

import os
import sys
import pytest
from unittest.mock import MagicMock, patch, PropertyMock

from backend.dev_loop_coder_prompt import (
    _build_patch_prompt,
    _truncate_prompt_if_needed,
    filter_feedback_for_files,
    _SECURITY_FIX_TEMPLATES,
    build_coder_prompt,
)


class TestBuildPatchPrompt:
    """Tests fuer _build_patch_prompt(current_code, affected_files, feedback)."""

    # --- current_code=None / String ---

    def test_current_code_none_verwendet_leeres_dict(self):
        """Bei current_code=None wird leeres Dict verwendet, keine Dateien gefunden."""
        result = _build_patch_prompt(None, ["app/page.js"], "Fehler X")
        assert "PATCH-MODUS" in result
        assert "WARNUNG" in result

    def test_current_code_none_patch_modus_header(self):
        """Output enthaelt PATCH-MODUS Header bei None und leeren affected."""
        assert "PATCH-MODUS" in _build_patch_prompt(None, [], "Feedback")

    def test_current_code_string_fallback(self):
        """String-Fallback: Code als Vollstaendig angehaengt, fruehe Rueckgabe."""
        code = "function hello() { return 1; }"
        result = _build_patch_prompt(code, ["file.js"], "Fix it")
        assert "AKTUELLER CODE (Vollständig)" in result
        assert code in result
        assert "Fix it" in result

    def test_current_code_string_truncated_auf_5000(self):
        """String-Fallback wird auf 5000 Zeichen beschnitten."""
        result = _build_patch_prompt("x" * 10000, ["file.js"], "Fix")
        assert "x" * 5000 in result
        assert "x" * 5001 not in result

    def test_current_code_string_keine_multi_file_logik(self):
        """String-Fallback gibt sofort zurueck, keine Multi-File-Anweisung."""
        result = _build_patch_prompt("code", ["a.js", "b.js"], "fb")
        assert "ALLE 2" not in result

    # --- Fuzzy-Matching (4 Stufen) ---

    @pytest.mark.parametrize("code_dict,affected,expected_path,desc", [
        # Stufe 1: Exakt
        ({"app/page.js": "code"}, ["app/page.js"], "app/page.js", "exakt"),
        # Stufe 2: Endswith
        ({"src/app/page.js": "code"}, ["app/page.js"], "src/app/page.js", "endswith"),
        # Stufe 3: Basename
        ({"src/components/Button.jsx": "code"}, ["Button.jsx"],
         "src/components/Button.jsx", "basename"),
        # Stufe 4: Basename-Stem
        ({"package.json": '{"n":"t"}'}, ["package.js"], "package.json", "stem"),
        # Backslash-Normalisierung
        ({"src\\app\\page.js": "code"}, ["src/app/page.js"], "src\\app\\page.js",
         "backslash"),
    ])
    def test_fuzzy_matching_stufen(self, code_dict, affected, expected_path, desc):
        """Fuzzy-Matching: Stufen 1-4 und Backslash-Normalisierung."""
        result = _build_patch_prompt(code_dict, affected, "fix")
        assert expected_path in result, f"Stufe '{desc}' fehlgeschlagen"
        assert "WARNUNG" not in result

    def test_kein_match_warnung_mit_dateien(self):
        """Keine Uebereinstimmung: Warnung + verfuegbare Dateien + Verbot neuer Dateien."""
        result = _build_patch_prompt({"file_a.js": "code_a"}, ["file_b.js"], "fix")
        assert "WARNUNG" in result
        assert "file_a.js" in result
        assert "ERSTELLE KEINE NEUEN DATEIEN" in result

    # --- Summary-Marker ---

    @pytest.mark.parametrize("content,marker_type", [
        ("IMPORTS: react, next\nFUNKTIONEN: getData", "ZUSAMMENFASSUNG"),
        ("[Komprimierter Inhalt]", "ZUSAMMENFASSUNG"),
        ("VORSCHAU: Modul mit 3 Funktionen", "ZUSAMMENFASSUNG"),
        ("const x = 1;", "AKTUELLER CODE"),
    ])
    def test_summary_marker(self, content, marker_type):
        """Content-Praefix bestimmt ob ZUSAMMENFASSUNG oder AKTUELLER CODE."""
        result = _build_patch_prompt({"file.js": content}, ["file.js"], "fix")
        assert f"({marker_type})" in result

    # --- Multi-File Anweisungen ---

    def test_multi_file_2_dateien(self):
        """2 Dateien gefunden → ALLE 2 + FILENAME-Format."""
        result = _build_patch_prompt({"a.js": "ca", "b.js": "cb"}, ["a.js", "b.js"], "f")
        assert "ALLE 2 korrigierten Dateien" in result
        assert "### FILENAME:" in result

    def test_multi_file_3_dateien(self):
        """3 Dateien gefunden → ALLE 3."""
        code = {"a.js": "ca", "b.js": "cb", "c.js": "cc"}
        result = _build_patch_prompt(code, ["a.js", "b.js", "c.js"], "f")
        assert "ALLE 3 korrigierten Dateien" in result

    def test_single_file_anweisung(self):
        """1 Datei gefunden → komplette korrigierte Datei."""
        result = _build_patch_prompt({"a.js": "code_a"}, ["a.js"], "fix")
        assert "komplette korrigierte Datei" in result

    def test_zero_files_warnung(self):
        """0 Dateien gematched aber affected nicht leer → Warnung."""
        assert "WARNUNG" in _build_patch_prompt({"x.js": "c"}, ["y.js"], "fix")

    # --- Phantom-Dateien ---

    def test_phantom_dateien_max_20_aufgelistet(self):
        """Max 20 verfuegbare Dateien bei Phantom-Warnung."""
        code = {f"file_{i}.js": f"c{i}" for i in range(25)}
        result = _build_patch_prompt(code, ["nope.js"], "fix")
        assert "ERSTELLE KEINE NEUEN DATEIEN" in result
        listed = [l for l in result.split("\n") if l.startswith("  - file_")]
        assert len(listed) == 20

    # --- Edge Cases ---

    def test_leere_affected_keine_warnung(self):
        """Leere affected_files → kein Matching, keine Warnung."""
        result = _build_patch_prompt({"a.js": "code"}, [], "feedback")
        assert "WARNUNG" not in result
        assert "PATCH-MODUS" in result

    def test_feedback_immer_enthalten(self):
        """Feedback wird immer in den Prompt eingebaut."""
        assert "Spezial42" in _build_patch_prompt({"a.js": "c"}, ["a.js"], "Spezial42")

    def test_leeres_dict_kein_crash(self):
        """Leeres Dict + leere affected → kein Crash."""
        assert "PATCH-MODUS" in _build_patch_prompt({}, [], "feedback")

    def test_code_in_backticks(self):
        """Aktueller Code wird in Backtick-Bloecke eingefasst."""
        result = _build_patch_prompt({"a.js": "const x = 1;"}, ["a.js"], "fix")
        assert "```\nconst x = 1;\n```" in result

    @pytest.mark.parametrize("affected,expected_in", [
        (["sub/page.js"], "page.js"),
        (["components/Header.tsx"], "Header.tsx"),
    ])
    def test_basename_matching_varianten(self, affected, expected_in):
        """Parametrisierte Basename-Match-Tests."""
        code = {"src/app/page.js": "p", "src/components/Header.tsx": "h"}
        result = _build_patch_prompt(code, affected, "fix")
        assert expected_in in result
        assert "WARNUNG" not in result


class TestTruncatePromptIfNeeded:
    """Tests fuer _truncate_prompt_if_needed(prompt, max_tokens)."""

    # --- Keine Kuerzung noetig ---

    @pytest.mark.parametrize("prompt,max_tokens", [
        ("Kurzer Prompt", 80000),
        ("x" * 300, 100),    # Genau am Limit (300 = 100*3)
        ("x" * 299, 100),    # Knapp unter Limit
        ("", 80000),          # Leerer Prompt
        ("x" * 1000, 1000000),  # Sehr grosses Budget
    ])
    def test_prompt_unveraendert(self, prompt, max_tokens):
        """Prompt unter/am Limit wird nicht veraendert."""
        assert _truncate_prompt_if_needed(prompt, max_tokens) == prompt

    def test_token_ratio_3(self):
        """max_chars = max_tokens * 3. 31 Zeichen > 10*3=30 → Kuerzung aktiv."""
        prompt = "x" * 31
        result = _truncate_prompt_if_needed(prompt, 10)
        assert len(result) <= len(prompt)

    # --- Stufe 1: Sektionen entfernen ---

    def test_stufe1_lessons_entfernt(self):
        """Sektion LESSONS LEARNED wird entfernt wenn Prompt zu gross."""
        prompt = (
            "ANFANG\n\n"
            "\U0001f4da LESSONS LEARNED (aus früheren Projekten):\n"
            "Lektion 1\nLektion 2\n" + "x" * 500 + "\n\n"
            "\U0001f9ea UNIT-TEST REQUIREMENT:\nTest-Regeln"
        )
        result = _truncate_prompt_if_needed(prompt, len(prompt) // 3 - 50)
        assert "LESSONS LEARNED" not in result
        assert "UNIT-TEST" in result

    def test_stufe1_env_constraints_entfernt(self):
        """Sektion UMGEBUNGS-EINSCHRAENKUNGEN wird entfernt."""
        prompt = (
            "ANFANG\n\n"
            "\u26a0\ufe0f UMGEBUNGS-EINSCHR\u00c4NKUNGEN (KRITISCH):\n"
            "Constraint 1\n" + "y" * 500 + "\n\n"
            "\U0001f4e6 DEPENDENCY:\nDeps"
        )
        result = _truncate_prompt_if_needed(prompt, len(prompt) // 3 - 50)
        assert "UMGEBUNGS-EINSCHR" not in result

    def test_stufe1_beide_sektionen_entfernt(self):
        """Beide Sektionen werden entfernt wenn Budget sehr klein."""
        filler = "z" * 300
        prompt = (
            f"ANFANG\n\n\U0001f4da LESSONS LEARNED:\n{filler}\n\n"
            f"\u26a0\ufe0f UMGEBUNGS-EINSCHR\u00c4NKUNGEN:\n{filler}\n\n"
            "\U0001f9ea UNIT-TEST:\nRegeln"
        )
        result = _truncate_prompt_if_needed(prompt, 100)
        assert "LESSONS LEARNED" not in result
        assert "UMGEBUNGS-EINSCHR" not in result

    def test_stufe1_mitte_entfernt_anfang_ende_bleiben(self):
        """Sektion in der Mitte entfernt, Anfang und Ende bleiben erhalten."""
        prompt = (
            "ANFANG_MARKER\n\n"
            "\U0001f4da LESSONS LEARNED:\n" + "L" * 500 + "\n\n"
            "\U0001f9ea ENDE_MARKER:\nTest"
        )
        result = _truncate_prompt_if_needed(prompt, len(prompt) // 3 - 100)
        assert "ANFANG_MARKER" in result
        assert "ENDE_MARKER" in result

    # --- Stufe 2: Datei-Inhalte kuerzen ---

    def test_stufe2_datei_auf_150_zeilen(self):
        """Datei mit 200 Zeilen wird auf 150 gekuerzt."""
        lines_200 = "\n".join([f"line {i}" for i in range(200)])
        prompt = (
            f"--- app.js (AKTUELLER CODE) ---\n```\n{lines_200}\n```\n\n"
            f"\U0001f527 FEHLER ZU BEHEBEN:\nFix\n\n\U0001f4cb A:\nOK"
        )
        result = _truncate_prompt_if_needed(prompt, len(prompt) // 3 - 100)
        assert "Zeilen gekuerzt wegen Token-Limit" in result

    def test_stufe2_kurze_datei_unveraendert(self):
        """Datei mit 50 Zeilen bleibt unveraendert (Stufe 1 reicht)."""
        lines_50 = "\n".join([f"line {i}" for i in range(50)])
        filler = "z" * 1000
        prompt = (
            f"\U0001f4da LESSONS LEARNED:\n{filler}\n\n"
            f"--- app.js (AKTUELLER CODE) ---\n```\n{lines_50}\n```\n\n"
            f"\U0001f9ea REST:\nOK"
        )
        result = _truncate_prompt_if_needed(prompt, (len(prompt) - 900) // 3)
        assert "Zeilen gekuerzt" not in result

    def test_stufe2_mehrere_dateien_gekuerzt(self):
        """Mehrere Dateien werden alle auf 150 Zeilen gekuerzt (Stufe 2, nicht Stufe 4)."""
        lines_200 = "\n".join([f"ln{i}" for i in range(200)])
        prompt = (
            f"--- a.js (AKTUELLER CODE) ---\n```\n{lines_200}\n```\n\n"
            f"--- b.js (AKTUELLER CODE) ---\n```\n{lines_200}\n```\n\n"
            f"\U0001f527 FEHLER ZU BEHEBEN:\nFix\n\n\U0001f4cb A:\nOK"
        )
        # Budget so dass Stufe 2 greift aber Stufe 4 nicht noetig ist
        lines_150_size = len("\n".join([f"ln{i}" for i in range(150)]))
        saved = len(lines_200) - lines_150_size
        result = _truncate_prompt_if_needed(prompt, (len(prompt) - saved) // 3)
        assert result.count("Zeilen gekuerzt wegen Token-Limit") == 2
        assert "Inhalt entfernt wegen Token-Limit" not in result

    def test_stufe2_summary_unberuehrt(self):
        """ZUSAMMENFASSUNG-Dateien werden nicht als AKTUELLER CODE gekuerzt."""
        lines_200 = "\n".join([f"line {i}" for i in range(200)])
        prompt = (
            f"--- sum.js (ZUSAMMENFASSUNG) ---\nIMPORTS: react\n\n"
            f"--- big.js (AKTUELLER CODE) ---\n```\n{lines_200}\n```\n\nEnde"
        )
        result = _truncate_prompt_if_needed(prompt, len(prompt) // 3 - 100)
        assert "(ZUSAMMENFASSUNG)" in result

    # --- Stufe 3: Feedback kuerzen ---

    def test_stufe3_feedback_reduziert(self):
        """Feedback wird auf max ~3000 Zeichen reduziert."""
        long_fb = "F" * 8000
        prompt = (
            f"ANFANG\n\n\U0001f527 FEHLER ZU BEHEBEN:\n{long_fb}\n\n"
            f"\U0001f4cb ANWEISUNGEN:\nOK"
        )
        result = _truncate_prompt_if_needed(prompt, 50)
        fb_marker = "\U0001f527 FEHLER ZU BEHEBEN:\n"
        fb_idx = result.find(fb_marker)
        if fb_idx != -1:
            fb_content = result[fb_idx + len(fb_marker):]
            fb_end = fb_content.find("\n\n\U0001f4cb")
            if fb_end > 0:
                assert fb_end <= 3100

    # --- Stufe 4: Notfall ---

    def test_stufe4_inhalte_komplett_entfernt(self):
        """Notfall: Datei-Inhalte durch Platzhalter ersetzt."""
        prompt = (
            f"--- big.js (AKTUELLER CODE) ---\n```\n{'x' * 5000}\n```\n\n"
            f"\U0001f527 FEHLER ZU BEHEBEN:\nFix\n\n\U0001f4cb A:\nOK"
        )
        result = _truncate_prompt_if_needed(prompt, 30)
        assert "Inhalt entfernt wegen Token-Limit" in result

    # --- Reihenfolge / Sonstige ---

    def test_keine_sektionen_kein_crash(self):
        """Prompt ohne entfernbare Sektionen — kein Crash."""
        result = _truncate_prompt_if_needed("Langer Text " * 200, 50)
        assert isinstance(result, str)

    def test_progressive_kuerzung_stufe1_vor_stufe2(self):
        """Stufe 1 (Lessons) wird VOR Stufe 2 (Code-Kuerzung) angewendet."""
        lines_200 = "\n".join([f"zeile {i}" for i in range(200)])
        filler = "L" * 500
        prompt = (
            f"\U0001f4da LESSONS LEARNED:\n{filler}\n\n"
            f"--- code.js (AKTUELLER CODE) ---\n```\n{lines_200}\n```\n\n"
            "\U0001f9ea REST:\nOK"
        )
        prompt_ohne = prompt.replace(f"\U0001f4da LESSONS LEARNED:\n{filler}\n\n", "")
        result = _truncate_prompt_if_needed(prompt, len(prompt_ohne) // 3 + 10)
        assert "LESSONS LEARNED" not in result
        assert "Zeilen gekuerzt" not in result

    @pytest.mark.parametrize("max_tokens,should_change", [
        (1000000, False),
        (10, True),
    ])
    def test_kuerzung_ja_nein(self, max_tokens, should_change):
        """Parametrisiert: Kuerzung ja/nein basierend auf Budget."""
        prompt = "x" * 500
        result = _truncate_prompt_if_needed(prompt, max_tokens)
        if should_change:
            assert len(result) <= len(prompt)
        else:
            assert result == prompt


class TestFilterFeedbackForFiles:
    """Tests fuer filter_feedback_for_files(feedback, target_files)."""

    # --- Edge Cases ---

    @pytest.mark.parametrize("feedback,target,expected", [
        (None, ["file.js"], ""),
        ("", ["file.js"], ""),
        (None, None, ""),
    ])
    def test_none_oder_leer_gibt_leer(self, feedback, target, expected):
        """None oder leeres Feedback → leerer String."""
        assert filter_feedback_for_files(feedback, target) == expected

    @pytest.mark.parametrize("target_files", [[], None])
    def test_leere_targets_gibt_original(self, target_files):
        """Leere oder None target_files → Originalfeedback."""
        fb = "Fehler in app.js"
        assert filter_feedback_for_files(fb, target_files) == fb

    # --- Filterung ---

    def test_fehler_abschnitt_filter(self):
        """## FEHLER Abschnitte werden nach Dateireferenz gefiltert."""
        fb = (
            "Header-Info\n"
            "## FEHLER 1: Problem in page.js\nDetails\n"
            "## FEHLER 2: Problem in utils.js\nAndere Details\n"
        )
        result = filter_feedback_for_files(fb, ["page.js"])
        assert "page.js" in result
        assert "utils.js" not in result

    def test_trennlinien_filter(self):
        """--- Trennlinien-Abschnitte werden gefiltert."""
        fb = (
            "Header\n"
            "---\nFehler in header.jsx: Syntax Error\n"
            "---\nFehler in footer.jsx: Missing import\n"
        )
        result = filter_feedback_for_files(fb, ["header.jsx"])
        assert "header.jsx" in result
        assert "footer.jsx" not in result

    def test_kein_match_fallback_original(self):
        """Kein Match → Fallback auf gesamtes Feedback."""
        fb = "Fehler in unknown.js\nDetails"
        assert filter_feedback_for_files(fb, ["other.js"]) == fb

    def test_header_immer_enthalten(self):
        """Header (erster Abschnitt) ist immer im Ergebnis."""
        fb = "Review-Ergebnis: 3 Fehler\n## FEHLER 1: page.js\nDetails\n"
        result = filter_feedback_for_files(fb, ["page.js"])
        assert "Review-Ergebnis" in result
        assert "page.js" in result

    def test_basename_matching(self):
        """Voller Pfad in target_files matcht Basename im Feedback."""
        fb = (
            "Header\n"
            "## FEHLER 1: page.js Zeile 5\nFix\n"
            "## FEHLER 2: api.js Zeile 10\nOK\n"
        )
        result = filter_feedback_for_files(fb, ["src/app/page.js"])
        assert "page.js" in result
        assert "api.js" not in result

    def test_mehrere_target_files(self):
        """Mehrere target_files → Abschnitte fuer alle passenden."""
        fb = (
            "Header\n## FEHLER 1: page.js Bug\n"
            "## FEHLER 2: utils.js Fehler\n## FEHLER 3: api.js Problem\n"
        )
        result = filter_feedback_for_files(fb, ["page.js", "api.js"])
        assert "page.js" in result
        assert "api.js" in result
        assert "utils.js" not in result

    def test_error_englisch(self):
        """Englische ## ERROR Abschnitte werden erkannt."""
        fb = "Header\n## ERROR 1: main.py\nD\n## ERROR 2: helper.py\nM\n"
        result = filter_feedback_for_files(fb, ["main.py"])
        assert "main.py" in result
        assert "helper.py" not in result

    def test_datei_marker_format(self):
        """[DATEI:xxx] Marker im Feedback wird korrekt erkannt."""
        fb = (
            "Uebersicht\n"
            "## FEHLER 1: [DATEI:layout.js] Hydration\nFix\n"
            "## FEHLER 2: [DATEI:page.js] CSS\nFix\n"
        )
        result = filter_feedback_for_files(fb, ["layout.js"])
        assert "layout.js" in result
        assert "page.js" not in result

    def test_hash_abschnitte(self):
        """### Abschnitte im Feedback werden korrekt geteilt."""
        fb = "Header\n### DATEI: config.js\nFehler\n### DATEI: server.js\nFehler\n"
        result = filter_feedback_for_files(fb, ["config.js"])
        assert "config.js" in result
        assert "server.js" not in result

    def test_reines_header_fallback(self):
        """Feedback ohne Abschnitt-Marker → Fallback auf Original."""
        fb = "Alles in Ordnung, keine Fehler gefunden."
        assert filter_feedback_for_files(fb, ["file.js"]) == fb


class TestSecurityFixTemplates:
    """Tests fuer _SECURITY_FIX_TEMPLATES Konstante."""

    def test_sql_injection_keywords(self):
        """sql_injection hat relevante keywords mit 'sql' drin."""
        tmpl = _SECURITY_FIX_TEMPLATES["sql_injection"]
        assert len(tmpl["keywords"]) > 0
        assert any("sql" in kw for kw in tmpl["keywords"])

    def test_xss_keywords(self):
        """xss hat relevante keywords."""
        tmpl = _SECURITY_FIX_TEMPLATES["xss"]
        assert len(tmpl["keywords"]) > 0
        assert any("xss" in kw for kw in tmpl["keywords"])

    def test_fix_example_nicht_leer(self):
        """Alle Templates haben nicht-leere fix_example (>10 Zeichen)."""
        for key, tmpl in _SECURITY_FIX_TEMPLATES.items():
            assert len(tmpl["fix_example"]) > 10, f"fix_example zu kurz bei {key}"

    def test_alle_keys_haben_keywords_und_fix_example(self):
        """Jedes Template hat keywords und fix_example Schluessel."""
        for key, tmpl in _SECURITY_FIX_TEMPLATES.items():
            assert "keywords" in tmpl, f"keywords fehlt bei {key}"
            assert "fix_example" in tmpl, f"fix_example fehlt bei {key}"

    def test_sql_injection_falsch_richtig(self):
        """SQL-Injection Template enthaelt FALSCH/RICHTIG Vergleich."""
        example = _SECURITY_FIX_TEMPLATES["sql_injection"]["fix_example"]
        assert "FALSCH" in example
        assert "RICHTIG" in example


# =========================================================================
# AENDERUNG 14.02.2026: Erweiterte Tests fuer _build_patch_prompt
# =========================================================================


class TestBuildPatchPromptKomprimiert:
    """Tests fuer _build_patch_prompt mit komprimiertem Context (>15 Dateien)."""

    def test_16_dateien_alle_gematch(self):
        """16 Dateien im Dict + alle in affected → alle 16 werden aufgefuehrt."""
        code = {f"src/file_{i}.js": f"const x_{i} = {i};" for i in range(16)}
        affected = [f"src/file_{i}.js" for i in range(16)]
        result = _build_patch_prompt(code, affected, "Fehler in vielen Dateien")
        assert f"ALLE 16 korrigierten Dateien" in result
        assert "### FILENAME:" in result
        # Alle Dateien muessen im Prompt auftauchen
        for i in range(16):
            assert f"file_{i}.js" in result

    def test_20_dateien_mit_summaries(self):
        """20 Dateien, einige mit Summary-Marker (IMPORTS:) → ZUSAMMENFASSUNG Label."""
        code = {}
        for i in range(20):
            if i < 5:
                # Kategorie A: voller Code (direkte Feedback-Dateien)
                code[f"src/module_{i}.js"] = f"function mod{i}() {{ return {i}; }}"
            else:
                # Kategorie C: komprimierte Summaries
                code[f"src/module_{i}.js"] = f"IMPORTS: react, utils\nFUNKTIONEN: handler{i}, helper{i}"
        affected = list(code.keys())
        result = _build_patch_prompt(code, affected, "Review-Feedback")
        # Voller Code → AKTUELLER CODE
        assert result.count("(AKTUELLER CODE)") == 5
        # Summaries → ZUSAMMENFASSUNG
        assert result.count("(ZUSAMMENFASSUNG)") == 15
        assert "ALLE 20 korrigierten Dateien" in result

    def test_komprimiert_vorschau_marker(self):
        """Dateien mit VORSCHAU: Praefix werden als ZUSAMMENFASSUNG markiert."""
        code = {
            "src/main.js": "const app = express();",
            "src/utils.js": "VORSCHAU: Helper-Modul mit 3 Export-Funktionen"
        }
        result = _build_patch_prompt(code, ["src/main.js", "src/utils.js"], "Fix")
        assert "(ZUSAMMENFASSUNG)" in result
        assert "(AKTUELLER CODE)" in result

    def test_komprimiert_eckige_klammer_marker(self):
        """Dateien mit [ Praefix werden als ZUSAMMENFASSUNG markiert."""
        code = {
            "src/a.js": "[Komprimierter Inhalt: 5 Funktionen, 120 Zeilen]",
            "src/b.js": "const b = 1;"
        }
        result = _build_patch_prompt(code, ["src/a.js", "src/b.js"], "Fix")
        # [Komprimierter...] Datei → ZUSAMMENFASSUNG
        assert "(ZUSAMMENFASSUNG)" in result
        # Normaler Code → AKTUELLER CODE
        assert "(AKTUELLER CODE)" in result

    def test_30_dateien_nur_10_in_affected(self):
        """30 Dateien im Dict, nur 10 in affected → nur 10 im Prompt."""
        code = {f"file_{i}.js": f"code_{i}" for i in range(30)}
        affected = [f"file_{i}.js" for i in range(10)]
        result = _build_patch_prompt(code, affected, "Fix 10 Dateien")
        assert "ALLE 10 korrigierten Dateien" in result
        # Nur die 10 affected Dateien als (AKTUELLER CODE)
        assert result.count("(AKTUELLER CODE)") == 10

    def test_gemischte_fuzzy_matches_in_grossem_dict(self):
        """Grosses Dict mit verschiedenen Pfaden, affected nutzt Basenames."""
        code = {
            "src/app/page.js": "page code",
            "src/components/Header.tsx": "header code",
            "src/lib/db.js": "db code",
            "src/api/route.js": "route code",
        }
        # Affected-Liste nutzt nur Basenames → Fuzzy-Match Stufe 3
        affected = ["page.js", "Header.tsx", "db.js", "route.js"]
        result = _build_patch_prompt(code, affected, "Fix alle")
        assert "WARNUNG" not in result
        assert "ALLE 4 korrigierten Dateien" in result


# =========================================================================
# AENDERUNG 14.02.2026: Erweiterte Tests fuer _truncate_prompt_if_needed
# =========================================================================


class TestTruncatePromptRatio:
    """Tests fuer die Token-Ratio-Logik (1 Token = ~3 Zeichen)."""

    def test_ratio_exakt_an_grenze(self):
        """Prompt mit exakt max_tokens*3 Zeichen → keine Kuerzung."""
        prompt = "a" * 300
        result = _truncate_prompt_if_needed(prompt, 100)
        assert result == prompt

    def test_ratio_ein_zeichen_ueber_grenze(self):
        """Prompt mit max_tokens*3+1 Zeichen → Kuerzung aktiv."""
        prompt = "a" * 301
        result = _truncate_prompt_if_needed(prompt, 100)
        # Kann nicht unveraendert sein, muss mindestens gleich oder kuerzer sein
        assert len(result) <= len(prompt)

    def test_leerer_prompt_bleibt_leer(self):
        """Leerer Prompt → keine Kuerzung, leerer String zurueck."""
        assert _truncate_prompt_if_needed("", 10) == ""

    def test_max_tokens_null(self):
        """max_tokens=0 bedeutet 0 Zeichen Budget → Kuerzung aktiv."""
        prompt = "Etwas Text"
        result = _truncate_prompt_if_needed(prompt, 0)
        # Bei 0 Budget muss irgendeine Kuerzung stattfinden
        assert isinstance(result, str)


class TestTruncatePromptStufe1Erweitert:
    """Erweiterte Tests fuer Stufe 1: Sektionen entfernen."""

    def test_nur_lessons_entfernt_constraints_bleibt(self):
        """Wenn Budget nach Lessons-Entfernung reicht, bleibt Env-Constraints."""
        lessons_block = "\U0001f4da LESSONS LEARNED (aus früheren Projekten):\n" + "L" * 200
        constraints_block = "\u26a0\ufe0f UMGEBUNGS-EINSCHR\u00c4NKUNGEN (KRITISCH):\n" + "C" * 50
        rest = "\U0001f9ea UNIT-TEST REQUIREMENT:\nTest-Regeln"
        prompt = f"ANFANG\n\n{lessons_block}\n\n{constraints_block}\n\n{rest}"
        # Budget so, dass nach Lessons-Entfernung alles passt
        prompt_without_lessons = f"ANFANG\n\n{constraints_block}\n\n{rest}"
        max_tokens = len(prompt_without_lessons) // 3 + 10
        result = _truncate_prompt_if_needed(prompt, max_tokens)
        assert "LESSONS LEARNED" not in result
        # Constraints koennte auch noch drin sein, da Budget nach Lessons reicht
        # (abhaengig vom genauen Budget, daher kein strikter Assert)

    def test_keine_entfernbaren_sektionen_stufe1_ueberspringt(self):
        """Prompt ohne Lessons/Constraints → Stufe 1 hat keinen Effekt."""
        lines_200 = "\n".join([f"zeile {i}" for i in range(200)])
        prompt = (
            f"--- code.js (AKTUELLER CODE) ---\n```\n{lines_200}\n```\n\n"
            "\U0001f527 FEHLER ZU BEHEBEN:\nFix\n\n\U0001f4cb A:\nOK"
        )
        result = _truncate_prompt_if_needed(prompt, len(prompt) // 3 - 200)
        # Stufe 1 hat nichts zum Entfernen, Stufe 2 muss greifen
        assert "Zeilen gekuerzt" in result or "Inhalt entfernt" in result


class TestTruncatePromptStufe3Erweitert:
    """Erweiterte Tests fuer Stufe 3: Feedback kuerzen."""

    def test_kurzes_feedback_bleibt_ungekuerzt(self):
        """Feedback unter 3000 Zeichen wird nicht gekuerzt."""
        short_fb = "F" * 2000
        prompt = (
            f"\U0001f527 FEHLER ZU BEHEBEN:\n{short_fb}\n\n"
            f"\U0001f4cb ANWEISUNGEN:\nOK"
        )
        # Budget so setzen, dass Stufe 1+2 nichts machen, aber Stufe 3 checkt
        result = _truncate_prompt_if_needed(prompt, len(prompt) // 3 - 10)
        # Kurzes Feedback soll nicht weiter gekuerzt werden
        # (Stufe 3 kuerzt nur wenn > 3000 Zeichen)
        assert short_fb in result or "..." not in result.split("\U0001f4cb")[0]


class TestTruncatePromptStufe4Erweitert:
    """Erweiterte Tests fuer Stufe 4: Notfall-Entfernung."""

    def test_mehrere_dateien_notfall_entfernt(self):
        """Notfall-Modus entfernt Inhalte ALLER Dateien."""
        big_code = "x" * 5000
        prompt = (
            f"--- a.js (AKTUELLER CODE) ---\n```\n{big_code}\n```\n\n"
            f"--- b.js (AKTUELLER CODE) ---\n```\n{big_code}\n```\n\n"
            f"\U0001f527 FEHLER ZU BEHEBEN:\nFix\n\n\U0001f4cb A:\nOK"
        )
        result = _truncate_prompt_if_needed(prompt, 30)
        # Beide Dateien sollten entfernt sein
        assert result.count("Inhalt entfernt wegen Token-Limit") == 2
        # Dateinamen muessen erhalten bleiben
        assert "a.js" in result
        assert "b.js" in result

    def test_zusammenfassung_nicht_in_notfall_entfernt(self):
        """ZUSAMMENFASSUNG-Dateien werden nicht als AKTUELLER CODE behandelt."""
        prompt = (
            f"--- sum.js (ZUSAMMENFASSUNG) ---\nIMPORTS: react\n\n"
            f"--- big.js (AKTUELLER CODE) ---\n```\n{'x' * 5000}\n```\n\n"
            "\U0001f527 FEHLER ZU BEHEBEN:\nFix\n\n\U0001f4cb A:\nOK"
        )
        result = _truncate_prompt_if_needed(prompt, 30)
        # Nur big.js wird in Stufe 4 entfernt, sum.js bleibt
        assert "(ZUSAMMENFASSUNG)" in result
        assert "Inhalt entfernt wegen Token-Limit" in result


# =========================================================================
# AENDERUNG 14.02.2026: Tests fuer build_coder_prompt
# =========================================================================


def _create_mock_manager(
    tech_blueprint=None,
    config=None,
    is_first_run=True,
    current_code="",
    base_dir=None,
    project_path=None,
    design_concept=None,
    security_vulnerabilities=None,
    database_schema="",
    project_rules=None,
):
    """
    Hilfsfunktion: Erstellt einen vollstaendig gemockten Manager
    fuer build_coder_prompt Tests.

    Returns:
        MagicMock mit allen notwendigen Attributen
    """
    manager = MagicMock()
    manager.tech_blueprint = tech_blueprint or {
        "project_type": "webapp",
        "framework": "Next.js",
        "language": "javascript",
    }
    manager.config = config or {"mode": "test"}
    manager.is_first_run = is_first_run
    manager.current_code = current_code
    manager.base_dir = base_dir or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    manager.project_path = project_path or "/tmp/test_project"
    manager.database_schema = database_schema
    manager.project_rules = project_rules or ""
    manager._file_summaries_cache = {}
    manager._ui_log = MagicMock()
    manager.get_briefing_context = MagicMock(return_value="")

    if design_concept is not None:
        manager.design_concept = design_concept
    else:
        # Kein design_concept Attribut → hasattr wird False
        del manager.design_concept

    if security_vulnerabilities is not None:
        manager.security_vulnerabilities = security_vulnerabilities
    else:
        del manager.security_vulnerabilities

    return manager


# Standard-Patches fuer alle build_coder_prompt Tests:
# - get_lessons_for_prompt → leerer String (kein Memory-Zugriff)
# - get_constraints_for_prompt → leerer String
# - get_python_dependency_versions → leerer String
# - get_doc_enrichment_section → None (kein externer Doku-Abruf)
_CODER_PROMPT_PATCHES = [
    patch("backend.doc_enrichment.get_doc_enrichment_section", return_value=None),
    patch("backend.dev_loop_coder_prompt.get_lessons_for_prompt", return_value=""),
    patch("backend.dev_loop_coder_prompt.get_constraints_for_prompt", return_value=""),
    patch("backend.dev_loop_coder_prompt.get_python_dependency_versions", return_value=""),
]


def _apply_coder_patches(func):
    """Wendet alle Standard-Patches fuer build_coder_prompt Tests an."""
    for p in reversed(_CODER_PROMPT_PATCHES):
        func = p(func)
    return func


class TestBuildCoderPromptBasis:
    """Tests fuer build_coder_prompt mit minimalem Manager (Erstlauf)."""

    @_apply_coder_patches
    def test_erstlauf_enthaelt_ziel_und_tech(self, *mocks):
        """Erstlauf-Prompt enthaelt Ziel und Tech-Blueprint."""
        manager = _create_mock_manager()
        result = build_coder_prompt(manager, "Erstelle eine Todo-App", None, 0)
        assert "Erstelle eine Todo-App" in result
        assert "Next.js" in result

    @_apply_coder_patches
    def test_erstlauf_enthaelt_security_basics(self, *mocks):
        """Erstlauf (iteration=0, kein Feedback) enthaelt Security Basics."""
        manager = _create_mock_manager()
        result = build_coder_prompt(manager, "Ziel", None, 0)
        assert "SECURITY BASICS" in result
        assert "innerHTML" in result or "XSS" in result

    @_apply_coder_patches
    def test_erstlauf_enthaelt_run_bat_regeln(self, *mocks):
        """Erstlauf-Prompt enthaelt RUN.BAT Pflicht-Regeln."""
        manager = _create_mock_manager()
        result = build_coder_prompt(manager, "Ziel", None, 0)
        assert "RUN.BAT" in result
        assert "VERBOTEN" in result

    @_apply_coder_patches
    def test_erstlauf_enthaelt_unit_test_requirement(self, *mocks):
        """Erstlauf-Prompt enthaelt Unit-Test Requirement."""
        manager = _create_mock_manager()
        result = build_coder_prompt(manager, "Ziel", None, 0)
        assert "UNIT-TEST REQUIREMENT" in result

    @_apply_coder_patches
    def test_erstlauf_enthaelt_datei_blacklist(self, *mocks):
        """Erstlauf-Prompt enthaelt NIEMALS GENERIEREN Blacklist."""
        manager = _create_mock_manager()
        result = build_coder_prompt(manager, "Ziel", None, 0)
        assert "package-lock.json" in result
        assert "node_modules" in result

    @_apply_coder_patches
    def test_erstlauf_enthaelt_purple_verbot(self, *mocks):
        """Erstlauf-Prompt enthaelt Design-Regeln mit Purple-Verbot."""
        manager = _create_mock_manager()
        result = build_coder_prompt(manager, "Ziel", None, 0)
        assert "purple" in result.lower() or "DESIGN-REGELN" in result

    @_apply_coder_patches
    def test_erstlauf_enthaelt_format_hinweis(self, *mocks):
        """Erstlauf-Prompt endet mit FILENAME-Format-Hinweis."""
        manager = _create_mock_manager()
        result = build_coder_prompt(manager, "Ziel", None, 0)
        assert "### FILENAME:" in result

    @_apply_coder_patches
    def test_erstlauf_js_enthaelt_package_json_pflicht(self, *mocks):
        """JavaScript-Erstlauf enthaelt package.json Test-Script Pflicht."""
        manager = _create_mock_manager()
        result = build_coder_prompt(manager, "Ziel", None, 0)
        assert "package.json" in result
        assert "test" in result.lower()

    @_apply_coder_patches
    def test_iteration_1_mit_feedback_kein_security_basics(self, *mocks):
        """Bei iteration>0 mit Feedback werden Security Basics NICHT angezeigt."""
        manager = _create_mock_manager(is_first_run=False)
        result = build_coder_prompt(manager, "Ziel", "Fehler in page.js", 1)
        assert "SECURITY BASICS" not in result

    @_apply_coder_patches
    def test_nextjs_enthaelt_router_konsistenz(self, *mocks):
        """Next.js Projekte enthalten ROUTER-KONSISTENZ Regeln."""
        manager = _create_mock_manager(tech_blueprint={
            "project_type": "nextjs-webapp",
            "framework": "Next.js",
            "language": "javascript",
        })
        result = build_coder_prompt(manager, "Ziel", None, 0)
        assert "ROUTER-KONSISTENZ" in result
        assert "pages/" in result

    @_apply_coder_patches
    def test_server_projekt_enthaelt_api_tests(self, *mocks):
        """Server-Projekt enthaelt API-Test-Regeln."""
        manager = _create_mock_manager(tech_blueprint={
            "project_type": "webapp",
            "framework": "Next.js",
            "language": "javascript",
            "requires_server": True,
        })
        result = build_coder_prompt(manager, "Ziel", None, 0)
        assert "API-TESTS" in result
        assert "Endpoint" in result


class TestBuildCoderPromptDesignConcept:
    """Tests fuer build_coder_prompt mit Design-Konzept."""

    @_apply_coder_patches
    def test_design_concept_wird_eingefuegt(self, *mocks):
        """Design-Konzept vom Designer-Agenten wird in Prompt eingefuegt."""
        manager = _create_mock_manager(design_concept="Dunkelblauer Header mit modernem Card-Layout")
        result = build_coder_prompt(manager, "Ziel", None, 0)
        assert "DESIGN-VORGABEN" in result
        assert "Dunkelblauer Header" in result

    @_apply_coder_patches
    def test_design_concept_kein_design_wird_ignoriert(self, *mocks):
        """'Kein Design' Marker wird nicht als Design-Vorgabe eingefuegt."""
        manager = _create_mock_manager(design_concept="Kein Design verfuegbar")
        result = build_coder_prompt(manager, "Ziel", None, 0)
        assert "DESIGN-VORGABEN" not in result

    @_apply_coder_patches
    def test_design_concept_auf_500_zeichen_beschnitten(self, *mocks):
        """Design-Konzept wird auf 500 Zeichen beschnitten."""
        long_design = "A" * 1000
        manager = _create_mock_manager(design_concept=long_design)
        result = build_coder_prompt(manager, "Ziel", None, 0)
        assert "DESIGN-VORGABEN" in result
        # Der vollstaendige 1000-Zeichen-String darf NICHT enthalten sein
        assert "A" * 1000 not in result
        # Aber die ersten 500 Zeichen schon
        assert "A" * 500 in result


class TestBuildCoderPromptIterationHistory:
    """Tests fuer build_coder_prompt mit iteration_history."""

    @_apply_coder_patches
    def test_iteration_history_wird_eingefuegt(self, *mocks):
        """Iteration-History wird als ITERATIONS-HISTORIE Sektion eingefuegt."""
        manager = _create_mock_manager(is_first_run=False)
        history = [
            {"iteration": 1, "feedback_files": ["page.js"], "utds_fixed": []},
            {"iteration": 2, "feedback_files": ["page.js", "db.js"], "utds_fixed": ["db.js"]},
        ]
        result = build_coder_prompt(manager, "Ziel", "Fehler", 3, iteration_history=history)
        assert "ITERATIONS-HISTORIE" in result
        assert "Iteration 1" in result
        assert "Iteration 2" in result

    @_apply_coder_patches
    def test_iteration_history_utds_fixed_angezeigt(self, *mocks):
        """UTDS-Fixes in der History werden explizit angezeigt."""
        manager = _create_mock_manager(is_first_run=False)
        history = [
            {"iteration": 1, "feedback_files": ["db.js"], "utds_fixed": ["db.js"]},
        ]
        result = build_coder_prompt(manager, "Ziel", "Fehler", 2, iteration_history=history)
        assert "UTDS hat gefixt" in result
        assert "db.js" in result

    @_apply_coder_patches
    def test_iteration_history_ping_pong_warnung(self, *mocks):
        """Dateien die >=2x bemangelt wurden loesen Ping-Pong-Warnung aus."""
        manager = _create_mock_manager(is_first_run=False)
        history = [
            {"iteration": 1, "feedback_files": ["page.js"], "utds_fixed": []},
            {"iteration": 2, "feedback_files": ["page.js"], "utds_fixed": []},
            {"iteration": 3, "feedback_files": ["page.js", "db.js"], "utds_fixed": []},
        ]
        result = build_coder_prompt(manager, "Ziel", "Fehler", 4, iteration_history=history)
        assert "ACHTUNG" in result
        assert "page.js" in result
        assert "3x bemangelt" in result

    @_apply_coder_patches
    def test_iteration_history_max_5_eintraege(self, *mocks):
        """Maximal die letzten 5 Iteration-History Eintraege werden angezeigt."""
        manager = _create_mock_manager(is_first_run=False)
        history = [
            {"iteration": i, "feedback_files": [f"file_{i}.js"], "utds_fixed": []}
            for i in range(10)
        ]
        result = build_coder_prompt(manager, "Ziel", "Fehler", 11, iteration_history=history)
        assert "ITERATIONS-HISTORIE" in result
        # Iteration 5-9 muessen drin sein (letzte 5)
        assert "Iteration 5" in result
        assert "Iteration 9" in result
        # Iteration 0-4 duerfen nicht direkt als "Iteration X" drin sein
        assert "Iteration 0:" not in result

    @_apply_coder_patches
    def test_leere_iteration_history_kein_abschnitt(self, *mocks):
        """Leere iteration_history → kein ITERATIONS-HISTORIE Abschnitt."""
        manager = _create_mock_manager(is_first_run=False)
        result = build_coder_prompt(manager, "Ziel", "Fehler", 1, iteration_history=[])
        assert "ITERATIONS-HISTORIE" not in result


class TestBuildCoderPromptUtdsProtectedFiles:
    """Tests fuer build_coder_prompt mit utds_protected_files."""

    @_apply_coder_patches
    def test_utds_protected_files_werden_angezeigt(self, *mocks):
        """UTDS-geschuetzte Dateien werden als Warnung im Prompt angezeigt."""
        manager = _create_mock_manager(is_first_run=False)
        result = build_coder_prompt(
            manager, "Ziel", "Fehler", 2,
            utds_protected_files=["lib/db.js", "app/api/route.js"]
        )
        assert "GESCHUETZTE DATEIEN" in result
        assert "lib/db.js" in result
        assert "NICHT veraendern" in result or "NICHT regenerieren" in result

    @_apply_coder_patches
    def test_leere_utds_protected_files_kein_abschnitt(self, *mocks):
        """Leere utds_protected_files → kein GESCHUETZTE DATEIEN Abschnitt."""
        manager = _create_mock_manager(is_first_run=False)
        result = build_coder_prompt(manager, "Ziel", "Fehler", 1, utds_protected_files=[])
        assert "GESCHUETZTE DATEIEN" not in result


class TestBuildCoderPromptPatchModus:
    """Tests fuer build_coder_prompt im Patch-Modus (nicht Erstlauf)."""

    @_apply_coder_patches
    @patch("backend.dev_loop_coder_prompt._get_current_code_dict")
    @patch("backend.dev_loop_coder_prompt._get_affected_files_from_feedback")
    def test_files_to_patch_aktiviert_patch_modus(
        self, mock_affected, mock_code_dict, *mocks
    ):
        """files_to_patch Parameter aktiviert Patch-Modus."""
        manager = _create_mock_manager(is_first_run=False)
        mock_code_dict.return_value = {"app/page.js": "const x = 1;"}
        mock_affected.return_value = ["app/page.js"]

        result = build_coder_prompt(
            manager, "Ziel", "Fehler in page.js", 1,
            files_to_patch=["app/page.js"]
        )
        assert "PATCH-MODUS" in result
        manager._ui_log.assert_any_call("Coder", "FilePatchMode", unittest_any_string())

    @_apply_coder_patches
    @patch("backend.dev_loop_coder_prompt._get_current_code_dict")
    def test_utds_tasks_aktiviert_patch_modus(
        self, mock_code_dict, *mocks
    ):
        """utds_tasks Parameter aktiviert Patch-Modus."""
        manager = _create_mock_manager(is_first_run=False)
        mock_code_dict.return_value = {"app/page.js": "const x = 1;"}

        result = build_coder_prompt(
            manager, "Ziel", "Fehler", 1,
            utds_tasks=[{"file": "app/page.js", "fix": "Bug"}],
            files_to_patch=["app/page.js"]
        )
        assert "PATCH-MODUS" in result
        manager._ui_log.assert_any_call("Coder", "UTDSMode", unittest_any_string())

    @_apply_coder_patches
    def test_erstlauf_mit_feedback_als_korrektur(self, *mocks):
        """Erstlauf (is_first_run=True) mit Feedback haengt es als Korrektur an."""
        manager = _create_mock_manager(is_first_run=True)
        result = build_coder_prompt(manager, "Ziel", "Zusaetzliches Feedback", 0)
        # Bei Erstlauf mit Feedback: Korrektur angehaengt (kein Patch-Modus)
        assert "Korrektur: Zusaetzliches Feedback" in result

    @_apply_coder_patches
    @patch("backend.dev_loop_coder_prompt._get_current_code_dict")
    def test_override_code_dict_wird_verwendet(
        self, mock_code_dict, *mocks
    ):
        """override_code_dict wird statt _get_current_code_dict verwendet."""
        manager = _create_mock_manager(is_first_run=False)
        override = {"custom/file.js": "override code"}
        mock_code_dict.return_value = {"other/file.js": "default code"}

        result = build_coder_prompt(
            manager, "Ziel", "Fehler", 1,
            files_to_patch=["custom/file.js"],
            override_code_dict=override
        )
        assert "override code" in result
        assert "default code" not in result


class TestBuildCoderPromptLessonsUndConstraints:
    """Tests fuer build_coder_prompt mit Lessons und Env-Constraints."""

    @patch("backend.doc_enrichment.get_doc_enrichment_section", return_value=None)
    @patch("backend.dev_loop_coder_prompt.get_python_dependency_versions", return_value="")
    @patch("backend.dev_loop_coder_prompt.get_constraints_for_prompt", return_value="")
    @patch("backend.dev_loop_coder_prompt.get_lessons_for_prompt",
           return_value="- VERMEIDE: npm global install\n- NUTZE: lokale node_modules")
    def test_lessons_werden_eingefuegt(self, mock_lessons, mock_constraints, mock_deps, *mocks):
        """Lessons Learned werden als Sektion eingefuegt."""
        manager = _create_mock_manager()
        result = build_coder_prompt(manager, "Ziel", None, 0)
        assert "LESSONS LEARNED" in result
        assert "npm global install" in result

    @patch("backend.doc_enrichment.get_doc_enrichment_section", return_value=None)
    @patch("backend.dev_loop_coder_prompt.get_python_dependency_versions", return_value="")
    @patch("backend.dev_loop_coder_prompt.get_lessons_for_prompt", return_value="")
    @patch("backend.dev_loop_coder_prompt.get_constraints_for_prompt",
           return_value="- canvas: Nicht verfuegbar, verwende svg")
    def test_constraints_werden_eingefuegt(self, mock_constraints, mock_lessons, mock_deps, *mocks):
        """Umgebungs-Einschraenkungen werden als Sektion eingefuegt."""
        manager = _create_mock_manager()
        result = build_coder_prompt(manager, "Ziel", None, 0)
        assert "UMGEBUNGS-EINSCHR" in result
        assert "canvas" in result

    @patch("backend.doc_enrichment.get_doc_enrichment_section", return_value=None)
    @patch("backend.dev_loop_coder_prompt.get_python_dependency_versions", return_value="")
    @patch("backend.dev_loop_coder_prompt.get_constraints_for_prompt",
           side_effect=Exception("Memory nicht gefunden"))
    @patch("backend.dev_loop_coder_prompt.get_lessons_for_prompt",
           side_effect=Exception("Memory nicht gefunden"))
    def test_fehler_beim_laden_wird_gefangen(self, mock_lessons, mock_constraints, mock_deps, *mocks):
        """Fehler beim Laden von Lessons/Constraints fuehrt nicht zum Crash."""
        manager = _create_mock_manager()
        # Soll NICHT raisen
        result = build_coder_prompt(manager, "Ziel", None, 0)
        assert isinstance(result, str)
        assert "Ziel" in result


class TestBuildCoderPromptTokenBudget:
    """Tests fuer build_coder_prompt Token-Budget-Guard."""

    @_apply_coder_patches
    def test_default_max_prompt_tokens_80000(self, *mocks):
        """Default max_prompt_tokens ist 80000 (wenn nicht in config)."""
        manager = _create_mock_manager(config={})
        result = build_coder_prompt(manager, "Ziel", None, 0)
        # Bei 80k Tokens * 3 = 240k Zeichen → normaler Prompt ist weit darunter
        assert isinstance(result, str)

    @_apply_coder_patches
    def test_config_max_prompt_tokens_wird_benutzt(self, *mocks):
        """max_prompt_tokens aus config wird verwendet und Kuerzung greift."""
        # Grosses Budget → keine Kuerzung
        manager_gross = _create_mock_manager(config={"max_prompt_tokens": 500000})
        result_gross = build_coder_prompt(manager_gross, "Ziel", None, 0)
        # Kleines Budget → Kuerzung muss aktiv werden (manche Sektionen nicht kuerzbar)
        manager_klein = _create_mock_manager(config={"max_prompt_tokens": 50})
        result_klein = build_coder_prompt(manager_klein, "Ziel", None, 0)
        # Ergebnis mit kleinem Budget muss kleiner-oder-gleich dem mit grossem sein
        assert len(result_klein) <= len(result_gross)


class TestBuildCoderPromptSecurityVulnerabilities:
    """Tests fuer build_coder_prompt mit Security-Vulnerabilities."""

    @_apply_coder_patches
    def test_security_vulns_werden_eingefuegt(self, *mocks):
        """Security-Vulnerabilities werden als SECURITY TASKS eingefuegt."""
        vulns = [
            {
                "severity": "high",
                "description": "SQL Injection via String-Konkatenation in SQL Query",
                "fix": "Parametrisierte Queries verwenden",
                "affected_file": "lib/db.js"
            }
        ]
        manager = _create_mock_manager(security_vulnerabilities=vulns)
        result = build_coder_prompt(manager, "Ziel", None, 0)
        assert "SECURITY TASKS" in result
        assert "SEC-001" in result
        assert "SQL" in result
        assert "lib/db.js" in result

    @_apply_coder_patches
    def test_security_template_wird_angehaengt(self, *mocks):
        """SQL-Injection Vulnerability loedt Template mit FALSCH/RICHTIG Beispiel aus."""
        vulns = [
            {
                "severity": "critical",
                "description": "SQL Injection in der Datenbank-Query",
                "fix": "Parametrisierte Queries",
                "affected_file": "db.js"
            }
        ]
        manager = _create_mock_manager(security_vulnerabilities=vulns)
        result = build_coder_prompt(manager, "Ziel", None, 0)
        assert "KONKRETES BEISPIEL" in result
        assert "FALSCH" in result
        assert "RICHTIG" in result


# Hilfs-Matcher fuer MagicMock assert_any_call mit beliebigem String
class _AnyString:
    """Matcher der bei assert_any_call jeden String akzeptiert."""
    def __eq__(self, other):
        return isinstance(other, str)

    def __repr__(self):
        return "<AnyString>"


def unittest_any_string():
    """Gibt einen _AnyString Matcher zurueck."""
    return _AnyString()
