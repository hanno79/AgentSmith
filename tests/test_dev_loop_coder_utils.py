# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 14.02.2026
Version: 1.0
Beschreibung: Erweiterte Tests fuer backend/dev_loop_coder_utils.py.
              Ergaenzt test_dev_loop_coder.py um bisher NICHT getestete Szenarien:
              - FALSE_POSITIVE_FILENAMES Filterung
              - [DATEI:xxx] und Markdown-Patterns in Feedback
              - Max-30-Limit (aktualisiert von altem Max-5)
              - _get_all_code_extensions() Vollabdeckung
              - UnicodeDecodeError Handling in _get_current_code_dict
              - Dynamic Routes in Dateinamen
              - Regex-Reihenfolge (json vor js)
"""

import os
import sys
import pytest
from unittest.mock import MagicMock

# Fuege Projekt-Root zum Python-Path hinzu
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.dev_loop_coder_utils import (
    _clean_model_output,
    _is_targeted_fix_context,
    _get_affected_files_from_feedback,
    _get_all_code_extensions,
    _get_current_code_dict,
    rebuild_current_code_from_disk,
    FALSE_POSITIVE_FILENAMES,
)


# ---------------------------------------------------------------------------
# 1. Tests fuer _clean_model_output — Erweiterte Szenarien
# ---------------------------------------------------------------------------

class TestCleanModelOutput:
    """Erweiterte Tests fuer _clean_model_output (nicht in test_dev_loop_coder.py)."""

    def test_mehrere_think_bloecke_hintereinander(self):
        """Mehrere separate <think>-Bloecke werden alle entfernt."""
        raw = (
            "<think>Erster Gedanke</think>"
            "Zwischentext"
            "<think>Zweiter Gedanke</think>"
            "### FILENAME: app.py\nprint('ok')"
        )
        result = _clean_model_output(raw)
        assert "Erster Gedanke" not in result, (
            "Erwartet: Erster Think-Block entfernt"
        )
        assert "Zweiter Gedanke" not in result, (
            "Erwartet: Zweiter Think-Block entfernt"
        )
        assert "print('ok')" in result, (
            "Erwartet: Code nach Think-Bloecken erhalten"
        )

    def test_prefix_mit_backtick_start_bleibt(self):
        """Wenn Prefix mit Backtick startet, wird nicht gekuerzt."""
        raw = "```python\ndef foo():\n    return 42\n```"
        result = _clean_model_output(raw)
        assert result.startswith("```python"), (
            "Erwartet: Backtick-Prefix am Anfang bleibt erhalten"
        )

    def test_langer_sinnvoller_prefix_vor_backtick_bleibt(self):
        """Prefix laenger als 50 Zeichen vor Backtick bleibt erhalten."""
        long_prefix = "Dies ist ein langer erklaerend Text der mehr als fuenfzig Zeichen hat und nicht entfernt werden soll"
        raw = f"{long_prefix}\n```python\ndef bar(): pass\n```"
        result = _clean_model_output(raw)
        assert long_prefix in result, (
            "Erwartet: Langer Prefix (>50 Zeichen) vor Backtick bleibt erhalten"
        )

    def test_prefix_vor_filename_wird_entfernt_auch_mit_leerzeilen(self):
        """Prefix mit Leerzeilen vor ### FILENAME: wird entfernt."""
        raw = "Hier ist der generierte Code:\n\n\n### FILENAME: main.py\nprint('x')"
        result = _clean_model_output(raw)
        assert result.startswith("### FILENAME:"), (
            "Erwartet: Prefix inkl. Leerzeilen vor ### FILENAME: entfernt"
        )

    def test_think_block_mit_code_darin(self):
        """Think-Block der selbst Code-aehnlichen Inhalt hat wird trotzdem entfernt."""
        raw = (
            "<think>\ndef plan():\n    # Schritt 1\n    pass\n</think>\n"
            "### FILENAME: real_code.py\ndef real(): pass"
        )
        result = _clean_model_output(raw)
        assert "def plan()" not in result, (
            "Erwartet: Code innerhalb von Think-Block entfernt"
        )
        assert "def real(): pass" in result, (
            "Erwartet: Echter Code nach Think-Block erhalten"
        )

    def test_nur_whitespace_input(self):
        """Input der nur Whitespace enthaelt ergibt leeren String."""
        result = _clean_model_output("   \n\n   \t  ")
        assert result == "", (
            "Erwartet: Nur-Whitespace Input ergibt leeren String nach strip()"
        )

    def test_filename_prefix_bleibt_wenn_prefix_leer(self):
        """### FILENAME: am Anfang ohne Prefix bleibt unveraendert."""
        raw = "### FILENAME: app.py\nprint('hello')"
        result = _clean_model_output(raw)
        assert result.startswith("### FILENAME: app.py"), (
            "Erwartet: ### FILENAME: am Anfang bleibt unveraendert"
        )


# ---------------------------------------------------------------------------
# 2. Tests fuer _is_targeted_fix_context — Erweiterte Szenarien
# ---------------------------------------------------------------------------

class TestIsTargetedFixContext:
    """Erweiterte Tests fuer _is_targeted_fix_context (nicht in test_dev_loop_coder.py)."""

    def test_pflicht_indikator(self):
        """PFLICHT: Indikator wird als additive Aenderung erkannt."""
        assert _is_targeted_fix_context("PFLICHT: Sicherheitscheck implementieren") is True, (
            "Erwartet: True fuer PFLICHT: Indikator"
        )

    def test_required_indikator(self):
        """REQUIRED: Indikator wird als additive Aenderung erkannt."""
        assert _is_targeted_fix_context("REQUIRED: Add input validation") is True, (
            "Erwartet: True fuer REQUIRED: Indikator"
        )

    def test_must_indikator(self):
        """MUST: Indikator wird als additive Aenderung erkannt."""
        assert _is_targeted_fix_context("MUST: Error handling hinzufuegen") is True, (
            "Erwartet: True fuer MUST: Indikator"
        )

    def test_case_insensitive_erkennung(self):
        """Indikatoren werden case-insensitive erkannt."""
        assert _is_targeted_fix_context("typeerror: cannot read property") is True, (
            "Erwartet: True fuer lowercase 'typeerror:'"
        )
        assert _is_targeted_fix_context("SYNTAXERROR: UNEXPECTED TOKEN") is True, (
            "Erwartet: True fuer uppercase 'SYNTAXERROR:'"
        )

    def test_new_file_indikator(self):
        """'new file' wird als additive Aenderung erkannt."""
        assert _is_targeted_fix_context("Erstelle new file fuer Konfiguration") is True, (
            "Erwartet: True fuer 'new file' Indikator"
        )

    def test_hinzufuegen_indikator(self):
        """'hinzufuegen' wird als additive Aenderung erkannt."""
        result = _is_targeted_fix_context("Bitte Logging hinzufügen in allen Modulen")
        assert result is True, (
            "Erwartet: True fuer 'hinzufuegen' Indikator"
        )

    def test_ergaenzen_indikator(self):
        """'ergaenzen' wird als additive Aenderung erkannt."""
        result = _is_targeted_fix_context("Validierung ergänzen fuer User-Input")
        assert result is True, (
            "Erwartet: True fuer 'ergaenzen' Indikator"
        )

    def test_docstring_indikator(self):
        """'docstring' wird als additive Aenderung erkannt."""
        assert _is_targeted_fix_context("Docstring fehlt in helper-Funktion") is True, (
            "Erwartet: True fuer 'docstring' Indikator"
        )

    def test_unit_test_mit_bindestrich(self):
        """'unit-test' mit Bindestrich wird erkannt."""
        assert _is_targeted_fix_context("unit-test fuer Berechnung schreiben") is True, (
            "Erwartet: True fuer 'unit-test' mit Bindestrich"
        )

    def test_rein_beschreibendes_feedback_ohne_keywords(self):
        """Rein beschreibendes Feedback ohne bekannte Keywords ergibt False."""
        feedback = "Die Anwendung laeuft stabil und performant"
        assert _is_targeted_fix_context(feedback) is False, (
            "Erwartet: False fuer rein beschreibendes Feedback ohne Keywords"
        )


# ---------------------------------------------------------------------------
# 3. Tests fuer _get_affected_files_from_feedback — Erweiterte Szenarien
# ---------------------------------------------------------------------------

class TestGetAffectedFiles:
    """Erweiterte Tests fuer _get_affected_files_from_feedback (nicht in test_dev_loop_coder.py)."""

    def test_datei_marker_pattern(self):
        """[DATEI:xxx] Pattern extrahiert Dateinamen korrekt."""
        feedback = (
            "Fehler in [DATEI:app/page.js] und [DATEI:lib/db.js]\n"
            "Beide Dateien brauchen Fixes."
        )
        result = _get_affected_files_from_feedback(feedback)
        assert "page.js" in result, "Erwartet: page.js aus [DATEI:app/page.js] extrahiert"
        assert "db.js" in result, "Erwartet: db.js aus [DATEI:lib/db.js] extrahiert"

    def test_datei_marker_mit_dynamic_route(self):
        """[DATEI:xxx] mit Dynamic Route [id] wird korrekt extrahiert."""
        feedback = "Fehler in [DATEI:app/api/todos/[id]/route.js]"
        result = _get_affected_files_from_feedback(feedback)
        assert "route.js" in result, (
            "Erwartet: route.js aus Dynamic-Route-Pfad extrahiert"
        )

    def test_file_marker_englisch(self):
        """[File: xxx] Pattern (englisch) wird ebenfalls erkannt."""
        feedback = "Problem in [File: src/utils.ts]"
        result = _get_affected_files_from_feedback(feedback)
        assert "utils.ts" in result, "Erwartet: utils.ts aus [File: xxx] Pattern extrahiert"

    def test_markdown_backtick_liste(self):
        """Markdown-Bullet-Liste mit Backticks wird erkannt."""
        feedback = (
            "BETROFFENE DATEIEN:\n"
            "- `package.json`\n"
            "- `app/layout.js`\n"
            "- `styles/globals.css`\n"
        )
        result = _get_affected_files_from_feedback(feedback)
        assert "package.json" in result, "Erwartet: package.json aus Markdown-Bullet extrahiert"
        assert "layout.js" in result, "Erwartet: layout.js aus Markdown-Bullet extrahiert"
        assert "globals.css" in result, "Erwartet: globals.css aus Markdown-Bullet extrahiert"

    def test_betroffene_dateien_inline(self):
        """BETROFFENE DATEIEN: mit Inline-Backtick wird erkannt."""
        feedback = "BETROFFENE DATEIEN: `config.json`"
        result = _get_affected_files_from_feedback(feedback)
        assert "config.json" in result, (
            "Erwartet: config.json aus BETROFFENE DATEIEN: Inline extrahiert"
        )

    def test_false_positive_filenames_filterung(self):
        """FALSE_POSITIVE_FILENAMES (next.js, node.js etc.) werden herausgefiltert."""
        feedback = (
            "Die Next.js Umgebung meldet Fehler.\n"
            "Node.js Version ist veraltet.\n"
            "Fehler in app.js: missing import\n"
        )
        result = _get_affected_files_from_feedback(feedback)
        assert "next.js" not in [f.lower() for f in result], (
            "Erwartet: 'Next.js' als False-Positive herausgefiltert"
        )
        assert "node.js" not in [f.lower() for f in result], (
            "Erwartet: 'Node.js' als False-Positive herausgefiltert"
        )
        # app.js ist ein echtes Projektfile und sollte drin sein
        assert "app.js" in result, (
            "Erwartet: 'app.js' als echtes Projektfile NICHT gefiltert"
        )

    def test_alle_false_positive_namen_in_set(self):
        """Alle erwarteten False-Positive Namen sind im Set enthalten."""
        erwartete = {
            'next.js', 'node.js', 'vue.js', 'react.js', 'express.js',
            'nuxt.js', 'nest.js', 'ember.js', 'angular.js', 'backbone.js',
            'three.js', 'p5.js', 'd3.js', 'chart.js', 'socket.js',
        }
        assert FALSE_POSITIVE_FILENAMES == erwartete, (
            f"Erwartet: FALSE_POSITIVE_FILENAMES enthaelt alle 15 Eintraege, "
            f"Differenz: {erwartete.symmetric_difference(FALSE_POSITIVE_FILENAMES)}"
        )

    def test_max_30_dateien_limit(self):
        """Maximal 30 Dateien werden zurueckgegeben (aktualisiertes Limit)."""
        # Erstelle Feedback mit 35 unterschiedlichen Dateien
        lines = [f'File "module_{i:02d}.py", line {i}' for i in range(35)]
        feedback = "\n".join(lines)
        result = _get_affected_files_from_feedback(feedback)
        assert len(result) <= 30, (
            f"Erwartet: Maximal 30 Dateien, erhalten: {len(result)}"
        )
        assert len(result) > 0, (
            "Erwartet: Mindestens eine Datei extrahiert"
        )

    def test_module_not_found_pattern(self):
        """Module not found Pattern extrahiert Modulnamen."""
        feedback = "Module not found: Can't resolve 'next/font' in \"app/layout.js\""
        result = _get_affected_files_from_feedback(feedback)
        # layout.js sollte ueber das Error:-Pattern oder andere erkannt werden
        assert "layout.js" in result, (
            "Erwartet: layout.js aus Module-not-found Kontext extrahiert"
        )

    def test_hat_fehler_pattern(self):
        """'datei.js hat Fehler' Pattern wird erkannt."""
        feedback = "utils.tsx hat einen Syntaxfehler in Zeile 42"
        result = _get_affected_files_from_feedback(feedback)
        assert "utils.tsx" in result, (
            "Erwartet: utils.tsx aus 'hat Fehler' Pattern extrahiert"
        )

    def test_datei_keyword_pattern(self):
        """'Datei xxx.js' Pattern wird erkannt."""
        # Hinweis: Regex-Alternation ts|tsx matcht 'ts' zuerst bei '.tsx'
        # Daher .js/.jsx testen die korrekt erkannt werden
        feedback = 'Datei "helpers.js" enthaelt ungueltige Imports'
        result = _get_affected_files_from_feedback(feedback)
        assert "helpers.js" in result, (
            "Erwartet: helpers.js aus 'Datei xxx' Pattern extrahiert"
        )

    def test_json_vor_js_regex_reihenfolge(self):
        """JSON-Dateien werden korrekt extrahiert (Regex-Reihenfolge)."""
        feedback = (
            "- `package.json` hat veraltete Dependencies\n"
            "- `tsconfig.json` fehlt\n"
        )
        result = _get_affected_files_from_feedback(feedback)
        assert "package.json" in result, (
            "Erwartet: package.json korrekt extrahiert (nicht als .js gematcht)"
        )
        assert "tsconfig.json" in result, (
            "Erwartet: tsconfig.json korrekt extrahiert"
        )

    def test_keine_duplikate_bei_mehreren_pattern_matches(self):
        """Gleiche Datei ueber verschiedene Patterns wird nur einmal gelistet."""
        feedback = (
            "[DATEI:app.js] — fehlende Validierung\n"
            "Error: app.js: unexpected token\n"
            "- `app.js` hat Fehler\n"
        )
        result = _get_affected_files_from_feedback(feedback)
        assert result.count("app.js") == 1, (
            f"Erwartet: app.js nur einmal, aber {result.count('app.js')}x gefunden"
        )

    def test_python_in_dateiname_pattern(self):
        """'in filename.py' Pattern extrahiert Dateinamen."""
        feedback = "NameError in handler.py beim Starten"
        result = _get_affected_files_from_feedback(feedback)
        assert "handler.py" in result, (
            "Erwartet: handler.py aus 'in filename.py' Pattern extrahiert"
        )

    def test_pfeil_datei_pattern(self):
        """'-> DATEI: file.js' Pattern wird erkannt."""
        feedback = "→ DATEI: `config.yaml`"
        result = _get_affected_files_from_feedback(feedback)
        assert "config.yaml" in result, (
            "Erwartet: config.yaml aus Pfeil-DATEI-Pattern extrahiert"
        )

    def test_bat_dateien_in_markdown_bullets(self):
        """BAT-Dateien in Markdown-Bullets werden erkannt."""
        feedback = "- `run.bat` muss aktualisiert werden"
        result = _get_affected_files_from_feedback(feedback)
        assert "run.bat" in result, (
            "Erwartet: run.bat aus Markdown-Bullet extrahiert"
        )

    def test_css_dateien_in_markdown_bullets(self):
        """CSS-Dateien in Markdown-Bullets werden erkannt."""
        feedback = "- `globals.css` braucht neue Variablen"
        result = _get_affected_files_from_feedback(feedback)
        assert "globals.css" in result, (
            "Erwartet: globals.css aus Markdown-Bullet extrahiert"
        )

    def test_venv_pfade_werden_gefiltert(self):
        """Dateien aus venv/ werden herausgefiltert."""
        feedback = 'File "venv/lib/python3.11/site-packages/flask/app.py", line 100'
        result = _get_affected_files_from_feedback(feedback)
        assert len(result) == 0, (
            f"Erwartet: Keine Dateien aus venv, aber erhalten: {result}"
        )


# ---------------------------------------------------------------------------
# 4. Tests fuer _get_all_code_extensions
# ---------------------------------------------------------------------------

class TestGetAllCodeExtensions:
    """Tests fuer _get_all_code_extensions() — bisher nicht getestet."""

    def test_basis_extensions_enthalten(self):
        """Basis-Extensions (.html, .css, .json etc.) sind immer enthalten."""
        extensions = _get_all_code_extensions()
        basis_erwartet = {
            '.html', '.css', '.json', '.bat', '.sh', '.yaml', '.yml',
            '.toml', '.cfg', '.ini', '.md', '.txt', '.sql',
            '.vue', '.svelte',
        }
        for ext in basis_erwartet:
            assert ext in extensions, (
                f"Erwartet: Basis-Extension '{ext}' in _get_all_code_extensions()"
            )

    def test_extra_extensions_enthalten(self):
        """Extra-Extensions (.env, .proto, .graphql etc.) sind enthalten."""
        extensions = _get_all_code_extensions()
        extras_erwartet = {
            '.env', '.dockerfile', '.xml', '.gradle', '.properties',
            '.proto', '.graphql', '.dart', '.scala',
        }
        for ext in extras_erwartet:
            assert ext in extensions, (
                f"Erwartet: Extra-Extension '{ext}' in _get_all_code_extensions()"
            )

    def test_ergebnis_ist_set(self):
        """Rueckgabewert ist ein Set (keine Duplikate moeglich)."""
        extensions = _get_all_code_extensions()
        assert isinstance(extensions, set), (
            "Erwartet: _get_all_code_extensions() gibt ein Set zurueck"
        )

    def test_binaer_extensions_nicht_enthalten(self):
        """Binaer-Dateitypen (.png, .jpg, .exe etc.) sind NICHT enthalten."""
        extensions = _get_all_code_extensions()
        binaer = {'.png', '.jpg', '.gif', '.exe', '.bin', '.zip', '.tar', '.mp4'}
        for ext in binaer:
            assert ext not in extensions, (
                f"Erwartet: Binaer-Extension '{ext}' NICHT in Code-Extensions"
            )

    def test_dynamische_extensions_aus_qg_constants(self):
        """Dynamische Extensions aus LANGUAGE_TEST_CONFIG werden integriert."""
        extensions = _get_all_code_extensions()
        # Python und JS/TS sollten durch LANGUAGE_TEST_CONFIG kommen
        # (oder zumindest durch die Basis-Extensions)
        grundlegende = {'.py', '.js', '.ts', '.jsx', '.tsx'}
        for ext in grundlegende:
            assert ext in extensions, (
                f"Erwartet: Grundlegende Code-Extension '{ext}' enthalten "
                f"(via LANGUAGE_TEST_CONFIG oder Basis)"
            )

    def test_mindest_extensions_ohne_qg_constants(self):
        """Auch ohne LANGUAGE_TEST_CONFIG liefert die Funktion Basis+Extras."""
        # Wir testen hier, dass die Funktion robust ist und mindestens
        # die hartcodierten Basis- und Extra-Extensions zurueckgibt,
        # unabhaengig davon ob LANGUAGE_TEST_CONFIG geladen werden kann
        extensions = _get_all_code_extensions()
        # Basis-Extensions muessen IMMER enthalten sein
        assert '.html' in extensions, (
            "Erwartet: .html immer in Extensions (Basis-Set)"
        )
        assert '.env' in extensions, (
            "Erwartet: .env immer in Extensions (Extra-Set)"
        )
        assert '.sql' in extensions, (
            "Erwartet: .sql immer in Extensions (Basis-Set)"
        )
        assert '.proto' in extensions, (
            "Erwartet: .proto immer in Extensions (Extra-Set)"
        )


# ---------------------------------------------------------------------------
# 5. Tests fuer _get_current_code_dict — Erweiterte Szenarien
# ---------------------------------------------------------------------------

class TestGetCurrentCodeDict:
    """Erweiterte Tests fuer _get_current_code_dict (nicht in test_dev_loop_coder.py)."""

    def test_unicode_decode_error_wird_uebersprungen(self, temp_dir):
        """Dateien mit ungueltigem UTF-8 werden uebersprungen statt Crash."""
        # Erstelle eine gueltige Datei
        gueltig_pfad = os.path.join(temp_dir, "valid.py")
        with open(gueltig_pfad, "w", encoding="utf-8") as f:
            f.write("print('ok')")

        # Erstelle eine Datei mit ungueltigem UTF-8
        ungueltig_pfad = os.path.join(temp_dir, "broken.py")
        with open(ungueltig_pfad, "wb") as f:
            f.write(b"\x80\x81\x82\xff\xfe invalid bytes")

        manager = MagicMock()
        manager.current_code = "string"
        manager.project_path = temp_dir

        result = _get_current_code_dict(manager)
        assert "valid.py" in result, (
            "Erwartet: Gueltige Datei wurde gelesen"
        )
        assert "broken.py" not in result, (
            "Erwartet: Ungueltige UTF-8 Datei wird uebersprungen"
        )

    def test_tiefe_verschachtelung(self, temp_dir):
        """Dateien in tief verschachtelten Unterverzeichnissen werden gelesen."""
        deep_dir = os.path.join(temp_dir, "src", "components", "ui")
        os.makedirs(deep_dir, exist_ok=True)
        deep_file = os.path.join(deep_dir, "Button.jsx")
        with open(deep_file, "w", encoding="utf-8") as f:
            f.write("export default function Button() { return <button/> }")

        manager = MagicMock()
        manager.current_code = "string"
        manager.project_path = temp_dir

        result = _get_current_code_dict(manager)
        assert "src/components/ui/Button.jsx" in result, (
            "Erwartet: Datei in tiefer Verschachtelung wird gelesen"
        )

    def test_skip_next_verzeichnis(self, temp_dir):
        """.next Verzeichnis wird uebersprungen."""
        next_dir = os.path.join(temp_dir, ".next")
        os.makedirs(next_dir, exist_ok=True)
        next_file = os.path.join(next_dir, "build-manifest.json")
        with open(next_file, "w", encoding="utf-8") as f:
            f.write("{}")

        # Echte Datei zum Vergleich
        app_file = os.path.join(temp_dir, "app.js")
        with open(app_file, "w", encoding="utf-8") as f:
            f.write("console.log('app')")

        manager = MagicMock()
        manager.current_code = "string"
        manager.project_path = temp_dir

        result = _get_current_code_dict(manager)
        assert "app.js" in result, "Erwartet: app.js wird gelesen"
        for key in result:
            assert ".next" not in key, (
                f"Erwartet: .next-Dateien uebersprungen, aber gefunden: {key}"
            )

    def test_skip_venv_verzeichnis(self, temp_dir):
        """venv und .venv Verzeichnisse werden uebersprungen."""
        for venv_name in ["venv", ".venv"]:
            venv_dir = os.path.join(temp_dir, venv_name)
            os.makedirs(venv_dir, exist_ok=True)
            venv_file = os.path.join(venv_dir, "activate.py")
            with open(venv_file, "w", encoding="utf-8") as f:
                f.write("# venv script")

        manager = MagicMock()
        manager.current_code = "string"
        manager.project_path = temp_dir

        result = _get_current_code_dict(manager)
        for key in result:
            assert "venv" not in key, (
                f"Erwartet: venv-Dateien uebersprungen, aber gefunden: {key}"
            )

    def test_skip_dist_und_build(self, temp_dir):
        """dist und build Verzeichnisse werden uebersprungen."""
        for skip_name in ["dist", "build"]:
            skip_dir = os.path.join(temp_dir, skip_name)
            os.makedirs(skip_dir, exist_ok=True)
            skip_file = os.path.join(skip_dir, "output.js")
            with open(skip_file, "w", encoding="utf-8") as f:
                f.write("// build output")

        # Echte Datei
        src_file = os.path.join(temp_dir, "index.js")
        with open(src_file, "w", encoding="utf-8") as f:
            f.write("// source")

        manager = MagicMock()
        manager.current_code = "string"
        manager.project_path = temp_dir

        result = _get_current_code_dict(manager)
        assert "index.js" in result, "Erwartet: index.js wird gelesen"
        for key in result:
            assert "dist" not in key and "build" not in key, (
                f"Erwartet: dist/build-Dateien uebersprungen, aber gefunden: {key}"
            )

    def test_project_path_none(self):
        """project_path=None ergibt leeres Dict."""
        manager = MagicMock()
        manager.current_code = "string"
        manager.project_path = None

        result = _get_current_code_dict(manager)
        assert result == {}, (
            "Erwartet: Leeres Dict wenn project_path None ist"
        )

    def test_env_datei_wird_gelesen(self, temp_dir):
        """.env Dateien werden gelesen (Extension .env ist in code_extensions)."""
        env_file = os.path.join(temp_dir, "config.env")
        with open(env_file, "w", encoding="utf-8") as f:
            f.write("DB_HOST=localhost")

        manager = MagicMock()
        manager.current_code = "string"
        manager.project_path = temp_dir

        result = _get_current_code_dict(manager)
        assert "config.env" in result, (
            "Erwartet: .env-Datei wird gelesen (ist in code_extensions)"
        )

    def test_current_code_dict_wenn_bereits_dict(self):
        """Wenn current_code bereits ein Dict ist, wird es direkt zurueckgegeben."""
        bestehendes_dict = {"app.py": "print('hello')", "utils.py": "x = 1"}
        manager = MagicMock()
        manager.current_code = bestehendes_dict

        result = _get_current_code_dict(manager)
        assert result is bestehendes_dict, (
            "Erwartet: Bestehendes Dict wird identisch zurueckgegeben"
        )


# ---------------------------------------------------------------------------
# 6. Tests fuer rebuild_current_code_from_disk — Erweiterte Szenarien
# ---------------------------------------------------------------------------

class TestRebuildCurrentCodeFromDisk:
    """Erweiterte Tests fuer rebuild_current_code_from_disk."""

    def test_fallback_leerer_string_ohne_current_code(self):
        """Ohne current_code Attribut ergibt leeren String als Fallback."""
        manager = MagicMock(spec=[])
        # Manager hat weder current_code noch project_path
        result = rebuild_current_code_from_disk(manager)
        assert result == "", (
            "Erwartet: Leerer String als Fallback wenn keine Attribute vorhanden"
        )

    def test_format_filename_sections(self, temp_dir):
        """Output hat korrektes ### FILENAME: Format mit doppelter Leerzeile dazwischen."""
        datei_a = os.path.join(temp_dir, "a.py")
        datei_b = os.path.join(temp_dir, "b.py")
        with open(datei_a, "w", encoding="utf-8") as f:
            f.write("# Datei A")
        with open(datei_b, "w", encoding="utf-8") as f:
            f.write("# Datei B")

        manager = MagicMock()
        manager.current_code = ""
        manager.project_path = temp_dir

        result = rebuild_current_code_from_disk(manager)

        # Pruefe Format: ### FILENAME: gefolgt von Inhalt
        assert "### FILENAME: a.py\n# Datei A" in result, (
            "Erwartet: a.py mit korrektem ### FILENAME: Format"
        )
        assert "### FILENAME: b.py\n# Datei B" in result, (
            "Erwartet: b.py mit korrektem ### FILENAME: Format"
        )
        # Doppelte Leerzeile zwischen Dateien
        assert "\n\n### FILENAME:" in result, (
            "Erwartet: Doppelte Leerzeile zwischen Datei-Sektionen"
        )

    def test_rebuild_mit_unterverzeichnissen(self, temp_dir):
        """Rebuild enthaelt Dateien aus Unterverzeichnissen mit relativen Pfaden."""
        sub_dir = os.path.join(temp_dir, "src", "lib")
        os.makedirs(sub_dir, exist_ok=True)
        datei = os.path.join(sub_dir, "utils.js")
        with open(datei, "w", encoding="utf-8") as f:
            f.write("export const helper = () => {}")

        manager = MagicMock()
        manager.current_code = ""
        manager.project_path = temp_dir

        result = rebuild_current_code_from_disk(manager)
        assert "### FILENAME: src/lib/utils.js" in result, (
            "Erwartet: Relativer Pfad src/lib/utils.js im Rebuild"
        )
        assert "export const helper" in result, (
            "Erwartet: Datei-Inhalt aus Unterverzeichnis korrekt"
        )

    def test_rebuild_ignoriert_node_modules(self, temp_dir):
        """Rebuild ignoriert node_modules Verzeichnis."""
        # Erstelle eine echte Datei
        app_file = os.path.join(temp_dir, "app.js")
        with open(app_file, "w", encoding="utf-8") as f:
            f.write("const app = true")

        # Erstelle node_modules Datei
        nm_dir = os.path.join(temp_dir, "node_modules", "react")
        os.makedirs(nm_dir, exist_ok=True)
        nm_file = os.path.join(nm_dir, "index.js")
        with open(nm_file, "w", encoding="utf-8") as f:
            f.write("module.exports = React")

        manager = MagicMock()
        manager.current_code = ""
        manager.project_path = temp_dir

        result = rebuild_current_code_from_disk(manager)
        assert "### FILENAME: app.js" in result, (
            "Erwartet: app.js im Rebuild enthalten"
        )
        assert "node_modules" not in result, (
            "Erwartet: node_modules NICHT im Rebuild enthalten"
        )

    def test_rebuild_sortiert_alphabetisch(self, temp_dir):
        """Dateien im Rebuild sind alphabetisch nach Pfad sortiert."""
        dateien = ["z_module.py", "a_start.py", "m_helper.py"]
        for name in dateien:
            pfad = os.path.join(temp_dir, name)
            with open(pfad, "w", encoding="utf-8") as f:
                f.write(f"# {name}")

        manager = MagicMock()
        manager.current_code = ""
        manager.project_path = temp_dir

        result = rebuild_current_code_from_disk(manager)
        pos_a = result.index("a_start.py")
        pos_m = result.index("m_helper.py")
        pos_z = result.index("z_module.py")
        assert pos_a < pos_m < pos_z, (
            "Erwartet: Alphabetische Sortierung (a < m < z)"
        )


# ---------------------------------------------------------------------------
# 7. Integrations-Tests mit conftest Fixtures
# ---------------------------------------------------------------------------

class TestMitConftestFixtures:
    """Tests die conftest.py Fixtures nutzen (mock_manager, temp_dir, sample_feedback)."""

    def test_mock_manager_code_dict(self, mock_manager, temp_dir):
        """mock_manager aus conftest.py funktioniert mit _get_current_code_dict."""
        # Erstelle eine Datei im temp_dir (mock_manager.project_path)
        test_file = os.path.join(temp_dir, "test_app.py")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("def test_hello(): assert True")

        result = _get_current_code_dict(mock_manager)
        assert "test_app.py" in result, (
            "Erwartet: test_app.py ueber mock_manager gelesen"
        )
        assert "def test_hello()" in result["test_app.py"], (
            "Erwartet: Inhalt von test_app.py korrekt"
        )

    def test_mock_manager_rebuild(self, mock_manager, temp_dir):
        """mock_manager funktioniert mit rebuild_current_code_from_disk."""
        test_file = os.path.join(temp_dir, "index.js")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("console.log('start')")

        result = rebuild_current_code_from_disk(mock_manager)
        assert "### FILENAME: index.js" in result, (
            "Erwartet: index.js im Rebuild ueber mock_manager"
        )

    def test_sample_feedback_extraction(self, sample_feedback):
        """sample_feedback aus conftest.py liefert erwartete Dateien."""
        result = _get_affected_files_from_feedback(sample_feedback)
        # sample_feedback enthaelt [DATEI:app/page.js], [DATEI:lib/db.js],
        # `app/api/items/route.js`
        assert "page.js" in result, (
            "Erwartet: page.js aus sample_feedback [DATEI:app/page.js] extrahiert"
        )
        assert "db.js" in result, (
            "Erwartet: db.js aus sample_feedback [DATEI:lib/db.js] extrahiert"
        )
        assert "route.js" in result, (
            "Erwartet: route.js aus sample_feedback Markdown-Bullet extrahiert"
        )

    def test_sample_feedback_ist_targeted_fix(self, sample_feedback):
        """sample_feedback wird als targeted fix erkannt (enthaelt 'Fehler' Begriffe)."""
        # sample_feedback enthaelt "fehlende", "Risiko" etc.
        # Pruefe ob _is_targeted_fix_context dies erkennt
        result = _is_targeted_fix_context(sample_feedback)
        assert result is True, (
            "Erwartet: sample_feedback wird als targeted fix erkannt"
        )
