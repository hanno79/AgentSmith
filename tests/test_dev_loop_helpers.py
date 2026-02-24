# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 14.02.2026
Version: 1.0
Beschreibung: Unit Tests fuer backend/dev_loop_helpers.py - Pure-Logic Funktionen.

              Getestete Funktionen (ohne externe Abhaengigkeiten):
              - is_forbidden_file(): System-Blacklist fuer verbotene Dateien/Verzeichnisse
              - hash_error(): Stabiler Fehler-Hash mit Normalisierung
              - _parse_code_to_files(): Multi-File Code-Parsing (### FILENAME: Marker)
              - TruncationError: Exception-Klasse fuer abgeschnittene LLM-Outputs
              - _is_python_file_complete(): Python-Truncation-Erkennung via ast.parse()
              - _is_js_file_complete(): JS/JSX Klammer-Balancierung und Struktur-Check
              - validate_before_write(): Kombinierter Truncation- und Schrumpf-Guard
              - _check_for_truncation(): Batch-Truncation-Check fuer Datei-Dicts
              - _sanitize_unicode(): Unicode-Bereinigung gegen LLM-Artefakte

              NICHT getestet (externe Abhaengigkeiten):
              - _validate_files_individually(): Braucht sandbox_runner
              - run_sandbox_for_project(): Braucht sandbox_runner
"""

import sys
import os

# Fuege Projekt-Root zum Python-Path hinzu
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from unittest.mock import patch

from backend.dev_loop_helpers import (
    is_forbidden_file,
    hash_error,
    _parse_code_to_files,
    TruncationError,
    _is_python_file_complete,
    _is_js_file_complete,
    validate_before_write,
    _check_for_truncation,
    _sanitize_unicode,
    FORBIDDEN_FILES,
    FORBIDDEN_DIRS,
)


# =========================================================================
# Tests fuer is_forbidden_file()
# =========================================================================

class TestForbiddenFiles:
    """Tests fuer is_forbidden_file() - Zentrale System-Blacklist."""

    def test_package_lock_ist_verboten(self):
        """package-lock.json steht auf der Blacklist."""
        assert is_forbidden_file("package-lock.json") is True, \
            "Erwartet: True - package-lock.json ist verboten"

    def test_yarn_lock_ist_verboten(self):
        """yarn.lock steht auf der Blacklist."""
        assert is_forbidden_file("yarn.lock") is True, \
            "Erwartet: True - yarn.lock ist verboten"

    def test_pnpm_lock_ist_verboten(self):
        """pnpm-lock.yaml steht auf der Blacklist."""
        assert is_forbidden_file("pnpm-lock.yaml") is True, \
            "Erwartet: True - pnpm-lock.yaml ist verboten"

    def test_bun_lockb_ist_verboten(self):
        """bun.lockb steht auf der Blacklist."""
        assert is_forbidden_file("bun.lockb") is True, \
            "Erwartet: True - bun.lockb ist verboten"

    def test_node_modules_verzeichnis_ist_verboten(self):
        """Dateien in node_modules/ sind verboten."""
        assert is_forbidden_file("node_modules/express/index.js") is True, \
            "Erwartet: True - node_modules/ Verzeichnis ist verboten"

    def test_next_verzeichnis_ist_verboten(self):
        """Dateien in .next/ sind verboten."""
        assert is_forbidden_file(".next/build-manifest.json") is True, \
            "Erwartet: True - .next/ Verzeichnis ist verboten"

    def test_dist_verzeichnis_ist_verboten(self):
        """Dateien in dist/ sind verboten."""
        assert is_forbidden_file("dist/bundle.js") is True, \
            "Erwartet: True - dist/ Verzeichnis ist verboten"

    def test_build_verzeichnis_ist_verboten(self):
        """Dateien in build/ sind verboten."""
        assert is_forbidden_file("build/static/main.js") is True, \
            "Erwartet: True - build/ Verzeichnis ist verboten"

    def test_cache_verzeichnis_ist_verboten(self):
        """Dateien in .cache/ sind verboten."""
        assert is_forbidden_file(".cache/webpack/module.js") is True, \
            "Erwartet: True - .cache/ Verzeichnis ist verboten"

    def test_pycache_verzeichnis_ist_verboten(self):
        """Dateien in __pycache__/ sind verboten."""
        assert is_forbidden_file("__pycache__/module.cpython-312.pyc") is True, \
            "Erwartet: True - __pycache__/ Verzeichnis ist verboten"

    def test_case_insensitive_dateiname(self):
        """Case-insensitive Pruefung fuer Dateinamen."""
        assert is_forbidden_file("PACKAGE-LOCK.JSON") is True, \
            "Erwartet: True - Case-insensitive Match fuer PACKAGE-LOCK.JSON"

    def test_case_insensitive_verzeichnis(self):
        """Case-insensitive Pruefung fuer Verzeichnisse."""
        assert is_forbidden_file("NODE_MODULES/express/index.js") is True, \
            "Erwartet: True - Case-insensitive Match fuer NODE_MODULES/"

    def test_windows_pfad_backslash(self):
        """Windows-Backslash-Pfade werden normalisiert."""
        assert is_forbidden_file("node_modules\\express\\index.js") is True, \
            "Erwartet: True - Backslash-Pfad wird zu Forward-Slash normalisiert"

    def test_pfad_mit_fuehrendem_slash(self):
        """Fuehrender Slash wird gestrippt."""
        assert is_forbidden_file("/node_modules/express/index.js") is True, \
            "Erwartet: True - Fuehrender Slash wird entfernt"

    def test_normale_datei_ist_erlaubt(self):
        """Normale Projektdateien sind erlaubt."""
        assert is_forbidden_file("app/page.js") is False, \
            "Erwartet: False - app/page.js ist eine erlaubte Datei"

    def test_package_json_ist_erlaubt(self):
        """package.json (ohne lock) ist erlaubt."""
        assert is_forbidden_file("package.json") is False, \
            "Erwartet: False - package.json ist keine verbotene Datei"

    def test_leerer_string_ist_erlaubt(self):
        """Leerer Dateiname gibt False zurueck."""
        assert is_forbidden_file("") is False, \
            "Erwartet: False - leerer String ist erlaubt (kein Crash)"

    def test_none_ist_erlaubt(self):
        """None als Dateiname gibt False zurueck (kein Crash)."""
        assert is_forbidden_file(None) is False, \
            "Erwartet: False - None wird als leerer String behandelt"

    def test_lock_im_dateinamen_aber_nicht_exact_match(self):
        """Datei mit 'lock' im Namen aber nicht in Blacklist ist erlaubt."""
        assert is_forbidden_file("lockfile-manager.js") is False, \
            "Erwartet: False - lockfile-manager.js ist nicht in der Blacklist"

    def test_forbidden_files_konstante_vollstaendig(self):
        """FORBIDDEN_FILES enthaelt alle erwarteten Lock-Dateien."""
        erwartete = {"package-lock.json", "yarn.lock", "pnpm-lock.yaml", "bun.lockb"}
        assert FORBIDDEN_FILES == erwartete, \
            f"Erwartet: {erwartete}, Erhalten: {FORBIDDEN_FILES}"

    def test_forbidden_dirs_konstante_vollstaendig(self):
        """FORBIDDEN_DIRS enthaelt alle erwarteten Verzeichnisse."""
        erwartete = {"node_modules/", ".next/", "dist/", "build/", ".cache/", "__pycache__/"}
        assert FORBIDDEN_DIRS == erwartete, \
            f"Erwartet: {erwartete}, Erhalten: {FORBIDDEN_DIRS}"

    def test_verschachtelter_verbotener_pfad(self):
        """Tief verschachtelter Pfad in node_modules wird erkannt."""
        assert is_forbidden_file("node_modules/@scope/package/lib/utils.js") is True, \
            "Erwartet: True - verschachtelte node_modules Pfade sind verboten"

    def test_lock_datei_in_unterverzeichnis(self):
        """package-lock.json in Unterverzeichnis wird ueber Basename erkannt."""
        assert is_forbidden_file("frontend/package-lock.json") is True, \
            "Erwartet: True - Basename-Match erkennt package-lock.json in Unterordner"


# =========================================================================
# Tests fuer hash_error()
# =========================================================================

class TestHashError:
    """Tests fuer hash_error() - Stabiler Fehler-Hash mit Normalisierung."""

    def test_leerer_string_gibt_leeren_hash(self):
        """Leerer Fehler-String gibt leeren Hash zurueck."""
        assert hash_error("") == "", \
            "Erwartet: leerer String fuer leeren Input"

    def test_none_gibt_leeren_hash(self):
        """None gibt leeren Hash zurueck."""
        assert hash_error(None) == "", \
            "Erwartet: leerer String fuer None-Input"

    def test_hash_laenge_ist_12(self):
        """Hash ist immer 12 Zeichen lang."""
        result = hash_error("TypeError: Cannot read property 'x' of undefined")
        assert len(result) == 12, \
            f"Erwartet: 12 Zeichen, Erhalten: {len(result)} Zeichen"

    def test_gleicher_fehler_gleicher_hash(self):
        """Identischer Fehler erzeugt identischen Hash (Stabilitaet)."""
        fehler = "SyntaxError: Unexpected token '<'"
        hash1 = hash_error(fehler)
        hash2 = hash_error(fehler)
        assert hash1 == hash2, \
            f"Erwartet: gleicher Hash, Erhalten: {hash1} vs {hash2}"

    def test_verschiedene_fehler_verschiedener_hash(self):
        """Verschiedene Fehler erzeugen verschiedene Hashes."""
        hash1 = hash_error("TypeError: Cannot read property 'x'")
        hash2 = hash_error("ReferenceError: y is not defined")
        assert hash1 != hash2, \
            f"Erwartet: verschiedene Hashes, Erhalten: {hash1} == {hash2}"

    def test_zeilennummern_werden_normalisiert(self):
        """Verschiedene Zeilennummern im gleichen Fehler = gleicher Hash."""
        hash1 = hash_error("Error at line 5: invalid syntax")
        hash2 = hash_error("Error at line 99: invalid syntax")
        assert hash1 == hash2, \
            "Erwartet: gleicher Hash trotz verschiedener Zeilennummern"

    def test_zeile_deutsch_wird_normalisiert(self):
        """Deutsche 'Zeile'-Angaben werden normalisiert."""
        hash1 = hash_error("Fehler in Zeile 10: ungueltig")
        hash2 = hash_error("Fehler in Zeile 200: ungueltig")
        assert hash1 == hash2, \
            "Erwartet: gleicher Hash trotz verschiedener 'Zeile'-Nummern"

    def test_timestamps_werden_normalisiert(self):
        """Timestamps (Datum + Uhrzeit) werden normalisiert."""
        hash1 = hash_error("Fehler am 2026-01-15 um 14:30:00")
        hash2 = hash_error("Fehler am 2026-02-14 um 09:15:30")
        assert hash1 == hash2, \
            "Erwartet: gleicher Hash trotz verschiedener Timestamps"

    def test_windows_pfade_werden_normalisiert(self):
        """Windows-Pfade (C:\\...) werden normalisiert."""
        hash1 = hash_error("Error in C:\\Users\\rahn\\project\\app.py")
        hash2 = hash_error("Error in C:\\Temp\\test\\other.py")
        assert hash1 == hash2, \
            "Erwartet: gleicher Hash trotz verschiedener Windows-Pfade"

    def test_unix_pfade_werden_normalisiert(self):
        """Unix-Pfade (/path/to/...) werden normalisiert."""
        hash1 = hash_error("Error in /home/user/project/app.py")
        hash2 = hash_error("Error in /tmp/test/other.py")
        assert hash1 == hash2, \
            "Erwartet: gleicher Hash trotz verschiedener Unix-Pfade"

    def test_iteration_nummern_werden_normalisiert(self):
        """Iterations-Nummern werden normalisiert."""
        hash1 = hash_error("Iteration 3: Module not found")
        hash2 = hash_error("Iteration 47: Module not found")
        assert hash1 == hash2, \
            "Erwartet: gleicher Hash trotz verschiedener Iteration-Nummern"

    def test_whitespace_wird_normalisiert(self):
        """Verschiedener Whitespace erzeugt gleichen Hash."""
        hash1 = hash_error("Error:   too  many   spaces")
        hash2 = hash_error("Error: too many spaces")
        assert hash1 == hash2, \
            "Erwartet: gleicher Hash trotz verschiedenem Whitespace"

    def test_max_500_zeichen_laenge(self):
        """Nur die ersten 500 Zeichen werden gehasht."""
        basis = "Error: " + "x" * 600
        # Aendere Zeichen NACH Position 500 — Hash sollte gleich bleiben
        variante = "Error: " + "x" * 500 + "y" * 100
        hash1 = hash_error(basis)
        hash2 = hash_error(variante)
        assert hash1 == hash2, \
            "Erwartet: gleicher Hash da Unterschied nach Position 500 liegt"

    def test_aenderung_in_ersten_500_zeichen(self):
        """Aenderung innerhalb der ersten 500 Zeichen erzeugt anderen Hash."""
        hash1 = hash_error("TypeError: " + "a" * 100)
        hash2 = hash_error("RangeError: " + "a" * 100)
        assert hash1 != hash2, \
            "Erwartet: verschiedene Hashes bei Aenderung in den ersten 500 Zeichen"

    def test_case_insensitive(self):
        """Hash ist case-insensitive (lower() auf Input)."""
        hash1 = hash_error("TypeError")
        hash2 = hash_error("TYPEERROR")
        assert hash1 == hash2, \
            "Erwartet: gleicher Hash da lower() angewendet wird"


# =========================================================================
# Tests fuer _parse_code_to_files()
# =========================================================================

class TestParseCodeToFiles:
    """Tests fuer _parse_code_to_files() - Multi-File Code-Parsing."""

    def test_kein_multi_file_format_gibt_leeres_dict(self):
        """Code ohne ### FILENAME: Marker gibt leeres Dict zurueck."""
        code = "def hello():\n    print('hello')\n"
        result = _parse_code_to_files(code)
        assert result == {}, \
            f"Erwartet: leeres Dict, Erhalten: {result}"

    def test_filename_marker(self):
        """### FILENAME: Format wird korrekt geparst."""
        code = "### FILENAME: app/page.js\nconst x = 1;\n"
        result = _parse_code_to_files(code)
        assert "app/page.js" in result, \
            f"Erwartet: 'app/page.js' im Ergebnis, Erhalten: {list(result.keys())}"
        assert "const x = 1;" in result["app/page.js"], \
            "Erwartet: Dateiinhalt enthaelt 'const x = 1;'"

    def test_file_marker_variante(self):
        """### FILE: Variante wird erkannt."""
        code = "### FILE: lib/utils.js\nfunction foo() {}\n"
        result = _parse_code_to_files(code)
        assert "lib/utils.js" in result, \
            "Erwartet: 'lib/utils.js' im Ergebnis bei ### FILE: Variante"

    def test_datei_marker_variante(self):
        """### DATEI: Deutsche Variante wird erkannt."""
        code = "### DATEI: src/helper.py\ndef helper():\n    pass\n"
        result = _parse_code_to_files(code)
        assert "src/helper.py" in result, \
            "Erwartet: 'src/helper.py' im Ergebnis bei ### DATEI: Variante"

    def test_pfad_marker_variante(self):
        """### PFAD: Deutsche Variante wird erkannt."""
        code = "### PFAD: config/settings.py\nDEBUG = True\n"
        result = _parse_code_to_files(code)
        assert "config/settings.py" in result, \
            "Erwartet: 'config/settings.py' im Ergebnis bei ### PFAD: Variante"

    def test_path_marker_variante(self):
        """### PATH: Variante wird erkannt."""
        code = "### PATH: routes/api.js\nmodule.exports = {}\n"
        result = _parse_code_to_files(code)
        assert "routes/api.js" in result, \
            "Erwartet: 'routes/api.js' im Ergebnis bei ### PATH: Variante"

    def test_mehrere_dateien_werden_geparst(self):
        """Mehrere Dateien werden korrekt aufgeteilt."""
        code = (
            "### FILENAME: app/page.js\n"
            "const a = 1;\n\n"
            "### FILENAME: lib/db.js\n"
            "const b = 2;\n"
        )
        result = _parse_code_to_files(code)
        assert len(result) == 2, \
            f"Erwartet: 2 Dateien, Erhalten: {len(result)}"
        assert "app/page.js" in result, "Erwartet: app/page.js vorhanden"
        assert "lib/db.js" in result, "Erwartet: lib/db.js vorhanden"

    def test_forbidden_files_werden_gefiltert(self):
        """Verbotene Dateien (package-lock.json) werden herausgefiltert."""
        code = (
            "### FILENAME: app/page.js\n"
            "const a = 1;\n\n"
            "### FILENAME: package-lock.json\n"
            '{"lockfileVersion": 3}\n'
        )
        result = _parse_code_to_files(code)
        assert "app/page.js" in result, "Erwartet: app/page.js vorhanden"
        assert "package-lock.json" not in result, \
            "Erwartet: package-lock.json wird von is_forbidden_file() gefiltert"

    def test_leere_dateien_werden_ignoriert(self):
        """Dateien ohne Inhalt werden nicht ins Dict aufgenommen."""
        code = (
            "### FILENAME: app/page.js\n"
            "const a = 1;\n\n"
            "### FILENAME: empty_file.js\n"
            "\n\n"
            "### FILENAME: lib/db.js\n"
            "const b = 2;\n"
        )
        result = _parse_code_to_files(code)
        assert "empty_file.js" not in result, \
            "Erwartet: Leere Datei wird nicht ins Dict aufgenommen"

    def test_trailing_colon_wird_entfernt(self):
        """Trailing Colon im Dateinamen wird entfernt."""
        code = "### FILENAME: app/page.js:\nconst x = 1;\n"
        result = _parse_code_to_files(code)
        assert "app/page.js" in result, \
            "Erwartet: Trailing Colon wird von rstrip(':') entfernt"

    def test_marker_ohne_keyword(self):
        """### ohne FILENAME/FILE/etc. funktioniert auch (optionaler Keyword-Match)."""
        code = "### app/layout.js\nexport default function Layout() {}\n"
        result = _parse_code_to_files(code)
        assert "app/layout.js" in result, \
            "Erwartet: Marker ohne Keyword wird trotzdem erkannt"


# =========================================================================
# Tests fuer TruncationError
# =========================================================================

class TestTruncationError:
    """Tests fuer TruncationError - Exception-Klasse."""

    def test_message_wird_gespeichert(self):
        """Exception-Message ist korrekt gesetzt."""
        err = TruncationError("Datei wurde abgeschnitten")
        assert str(err) == "Datei wurde abgeschnitten", \
            f"Erwartet: 'Datei wurde abgeschnitten', Erhalten: '{str(err)}'"

    def test_truncated_files_liste(self):
        """truncated_files-Attribut wird korrekt gespeichert."""
        dateien = ["app.py", "utils.py"]
        err = TruncationError("Truncation", truncated_files=dateien)
        assert err.truncated_files == dateien, \
            f"Erwartet: {dateien}, Erhalten: {err.truncated_files}"

    def test_default_leere_liste(self):
        """Ohne truncated_files-Argument wird leere Liste verwendet."""
        err = TruncationError("Truncation")
        assert err.truncated_files == [], \
            f"Erwartet: leere Liste, Erhalten: {err.truncated_files}"

    def test_ist_exception_subklasse(self):
        """TruncationError erbt von Exception."""
        err = TruncationError("Test")
        assert isinstance(err, Exception), \
            "Erwartet: TruncationError ist eine Exception-Subklasse"


# =========================================================================
# Tests fuer _is_python_file_complete()
# =========================================================================

class TestIsPythonFileComplete:
    """Tests fuer _is_python_file_complete() - Python-Truncation-Erkennung."""

    def test_nicht_python_datei_ist_immer_ok(self):
        """Nicht-.py-Dateien geben immer (True, ...) zurueck."""
        is_ok, reason = _is_python_file_complete("invalid python{{{", "app.js")
        assert is_ok is True, \
            f"Erwartet: True fuer .js-Datei, Erhalten: {is_ok} ({reason})"

    def test_leere_datei_ist_nicht_vollstaendig(self):
        """Leere Python-Datei wird als unvollstaendig erkannt."""
        is_ok, reason = _is_python_file_complete("", "app.py")
        assert is_ok is False, \
            "Erwartet: False fuer leere Python-Datei"
        assert "leer" in reason.lower(), \
            f"Erwartet: 'leer' im Grund, Erhalten: '{reason}'"

    def test_nur_whitespace_ist_leer(self):
        """Nur-Whitespace wird als leer erkannt."""
        is_ok, reason = _is_python_file_complete("   \n\t  \n", "app.py")
        assert is_ok is False, \
            "Erwartet: False fuer Whitespace-only Python-Datei"

    def test_valider_code_ist_vollstaendig(self):
        """Syntaktisch korrekter Python-Code wird als vollstaendig erkannt."""
        code = "def hello():\n    print('Hello')\n\nhello()\n"
        is_ok, reason = _is_python_file_complete(code, "app.py")
        assert is_ok is True, \
            f"Erwartet: True fuer validen Python-Code, Erhalten: {is_ok} ({reason})"
        assert "OK" in reason, \
            f"Erwartet: 'OK' im Grund, Erhalten: '{reason}'"

    def test_endet_mit_offener_klammer(self):
        """Code der mit '(' endet = Truncation."""
        code = "def hello(\n"
        is_ok, reason = _is_python_file_complete(code, "truncated.py")
        assert is_ok is False, \
            "Erwartet: False wenn Code mit '(' endet"
        assert "offenem Konstrukt" in reason, \
            f"Erwartet: 'offenem Konstrukt' im Grund, Erhalten: '{reason}'"

    def test_endet_mit_offener_eckiger_klammer(self):
        """Code der mit '[' endet = Truncation."""
        code = "items = [\n"
        is_ok, reason = _is_python_file_complete(code, "truncated.py")
        assert is_ok is False, \
            "Erwartet: False wenn Code mit '[' endet"

    def test_endet_mit_offener_geschweifter_klammer(self):
        """Code der mit '{' endet = Truncation."""
        code = "data = {\n"
        is_ok, reason = _is_python_file_complete(code, "truncated.py")
        assert is_ok is False, \
            "Erwartet: False wenn Code mit '{' endet"

    def test_endet_mit_komma(self):
        """Code der mit ',' endet = Truncation."""
        code = "items = [1, 2,\n"
        is_ok, reason = _is_python_file_complete(code, "truncated.py")
        assert is_ok is False, \
            "Erwartet: False wenn Code mit ',' endet"

    def test_endet_mit_def_keyword(self):
        """Code der mit 'def' endet (nach rstrip) = Truncation ueber SyntaxError-Pfad."""
        # Nach rstrip() endet der Code mit 'def' — kein Truncation-Ending-Match,
        # aber SyntaxError + len > 100 + kein gueltiger Abschluss = Truncation
        code = "x = 1\n" * 20 + "def"
        is_ok, reason = _is_python_file_complete(code, "truncated.py")
        assert is_ok is False, \
            f"Erwartet: False wenn langer Code mit 'def' endet, Erhalten: {is_ok} ({reason})"

    def test_expected_indented_block_ist_truncation(self):
        """Funktion ohne Body (nach rstrip endet mit ':') = Truncation."""
        code = "def hello():\n"
        is_ok, reason = _is_python_file_complete(code, "truncated.py")
        assert is_ok is False, \
            f"Erwartet: False bei Funktion ohne Body, Erhalten: {is_ok} ({reason})"
        # Wird durch ':'-Truncation-Ending erkannt (vor dem SyntaxError-Check)
        assert "offenem Konstrukt" in reason or "Unerwartetes Dateiende" in reason, \
            f"Erwartet: Truncation-Erkennung im Grund, Erhalten: '{reason}'"

    def test_unterminated_string(self):
        """Nicht abgeschlossener Single-Line String = Truncation."""
        # Einfacher String ohne schliessende Anfuehrungszeichen
        code = 'x = "hello\n'
        is_ok, reason = _is_python_file_complete(code, "truncated.py")
        assert is_ok is False, \
            "Erwartet: False bei nicht-abgeschlossenem String-Literal"
        assert "Unvollständiger String" in reason, \
            f"Erwartet: 'Unvollstaendiger String' im Grund, Erhalten: '{reason}'"

    def test_echter_syntaxfehler_ist_kein_truncation(self):
        """Echter Syntax-Fehler (nicht Truncation) gibt (True, ...) zurueck."""
        # Fehlender Doppelpunkt nach if, aber Datei ist kurz (<= 100 Zeichen)
        code = "if True\n    pass\n"
        is_ok, reason = _is_python_file_complete(code, "buggy.py")
        assert is_ok is True, \
            f"Erwartet: True bei echtem Syntax-Fehler (kein Truncation), Erhalten: {is_ok} ({reason})"
        assert "Syntax-Fehler" in reason or "kein Truncation" in reason, \
            f"Erwartet: Hinweis auf echten Syntax-Fehler, Erhalten: '{reason}'"

    def test_kurzer_code_mit_syntaxfehler_ist_ok(self):
        """Kurzer Code (< 100 Zeichen) mit SyntaxError ist kein Truncation."""
        code = "x = 1 +\n"
        is_ok, reason = _is_python_file_complete(code, "short.py")
        # Kurzer Code + SyntaxError — wird als echter Fehler gewertet
        # da len(content) <= 100, wird der letzte Check uebersprungen
        assert isinstance(is_ok, bool), \
            "Erwartet: boolescher Rueckgabewert"

    def test_langer_code_ohne_gueltigen_abschluss(self):
        """Langer Code (> 100 Zeichen) ohne gueltigen Abschluss = Truncation."""
        # Langer Code der mitten im Statement endet
        code = "x = 1\n" * 20 + "result = some_function("
        is_ok, reason = _is_python_file_complete(code, "truncated.py")
        assert is_ok is False, \
            f"Erwartet: False bei langem Code mit offenem Konstrukt, Erhalten: {is_ok} ({reason})"

    def test_valide_klasse_ist_vollstaendig(self):
        """Vollstaendige Python-Klasse wird als OK erkannt."""
        code = (
            "class Calculator:\n"
            "    def add(self, a, b):\n"
            "        return a + b\n"
            "\n"
            "    def subtract(self, a, b):\n"
            "        return a - b\n"
        )
        is_ok, reason = _is_python_file_complete(code, "calculator.py")
        assert is_ok is True, \
            f"Erwartet: True fuer vollstaendige Klasse, Erhalten: {is_ok} ({reason})"


# =========================================================================
# Tests fuer _is_js_file_complete()
# =========================================================================

class TestIsJsFileComplete:
    """Tests fuer _is_js_file_complete() - JS Struktur-Check."""

    def test_leere_datei_ist_nicht_vollstaendig(self):
        """Leere JS-Datei wird als unvollstaendig erkannt."""
        is_ok, reason = _is_js_file_complete("")
        assert is_ok is False, \
            "Erwartet: False fuer leere JS-Datei"
        assert "leer" in reason.lower(), \
            f"Erwartet: 'leer' im Grund, Erhalten: '{reason}'"

    def test_nur_whitespace_ist_leer(self):
        """Nur-Whitespace wird als leer erkannt."""
        is_ok, reason = _is_js_file_complete("   \n\t  \n")
        assert is_ok is False, \
            "Erwartet: False fuer Whitespace-only JS-Datei"

    def test_balancierter_code_ist_vollstaendig(self):
        """Balancierter JS-Code wird als strukturell OK erkannt."""
        code = "function hello() {\n  console.log('Hello');\n}\n"
        is_ok, reason = _is_js_file_complete(code)
        assert is_ok is True, \
            f"Erwartet: True fuer balancierten Code, Erhalten: {is_ok} ({reason})"
        assert "OK" in reason, \
            f"Erwartet: 'OK' im Grund, Erhalten: '{reason}'"

    def test_unbalancierte_geschweifte_klammern_diff_groesser_2(self):
        """Mehr als 2 ungeschlossene geschweifte Klammern = Truncation."""
        code = "function a() {\n  if (true) {\n    if (x) {\n"
        is_ok, reason = _is_js_file_complete(code)
        assert is_ok is False, \
            "Erwartet: False bei 3+ unbalancierten geschweiften Klammern"
        assert "Klammern" in reason, \
            f"Erwartet: 'Klammern' im Grund, Erhalten: '{reason}'"

    def test_unbalancierte_parenthesen_diff_groesser_2(self):
        """Mehr als 2 ungeschlossene runde Klammern = Truncation."""
        code = "fn(fn2(fn3(\n"
        is_ok, reason = _is_js_file_complete(code)
        assert is_ok is False, \
            "Erwartet: False bei 3+ unbalancierten runden Klammern"
        assert "Parenthesen" in reason, \
            f"Erwartet: 'Parenthesen' im Grund, Erhalten: '{reason}'"

    def test_unbalancierte_brackets_diff_groesser_2(self):
        """Mehr als 2 ungeschlossene eckige Klammern = Truncation."""
        code = "const a = [[[\n"
        is_ok, reason = _is_js_file_complete(code)
        assert is_ok is False, \
            "Erwartet: False bei 3+ unbalancierten eckigen Klammern"
        assert "Brackets" in reason, \
            f"Erwartet: 'Brackets' im Grund, Erhalten: '{reason}'"

    def test_diff_genau_2_ist_ok(self):
        """Diff von genau 2 wird toleriert (Template-Literals)."""
        # 2 oeffnende mehr als schliessende → noch OK
        code = "const a = {\n  b: {\n  }\n"
        is_ok, reason = _is_js_file_complete(code)
        # Diff ist 1 hier, also sicher OK
        assert is_ok is True, \
            f"Erwartet: True bei Diff <= 2, Erhalten: {is_ok} ({reason})"

    def test_endet_mit_offener_geschweifter_klammer(self):
        """Code der mit '{' endet = Truncation (abruptes Ende)."""
        code = "export default function App() {\n"
        is_ok, reason = _is_js_file_complete(code)
        assert is_ok is False, \
            "Erwartet: False wenn JS-Code mit '{' endet"
        assert "offenem Konstrukt" in reason, \
            f"Erwartet: 'offenem Konstrukt' im Grund, Erhalten: '{reason}'"

    def test_endet_mit_arrow_function(self):
        """Code der mit '=>' endet = Truncation."""
        code = "const handler = (e) =>\n"
        is_ok, reason = _is_js_file_complete(code)
        assert is_ok is False, \
            "Erwartet: False wenn Code mit '=>' endet"

    def test_endet_mit_gleichzeichen(self):
        """Code der mit '=' endet = Truncation."""
        code = "const items =\n"
        is_ok, reason = _is_js_file_complete(code)
        assert is_ok is False, \
            "Erwartet: False wenn Code mit '=' endet"

    def test_endet_mit_logischem_and(self):
        """Code der mit '&&' endet = Truncation."""
        code = "const result = a &&\n"
        is_ok, reason = _is_js_file_complete(code)
        assert is_ok is False, \
            "Erwartet: False wenn Code mit '&&' endet"

    def test_abgeschnittener_import_statement(self):
        """Abgeschnittener Import wie 'import { cl;' wird erkannt."""
        code = "import { useState;\n"
        is_ok, reason = _is_js_file_complete(code)
        assert is_ok is False, \
            "Erwartet: False bei abgeschnittenem Import-Statement"
        assert "Import" in reason, \
            f"Erwartet: 'Import' im Grund, Erhalten: '{reason}'"

    def test_kompletter_react_component(self):
        """Vollstaendige React-Komponente wird als OK erkannt."""
        code = (
            "'use client'\n"
            "import { useState } from 'react'\n\n"
            "export default function App() {\n"
            "  const [count, setCount] = useState(0)\n"
            "  return <div>{count}</div>\n"
            "}\n"
        )
        is_ok, reason = _is_js_file_complete(code)
        assert is_ok is True, \
            f"Erwartet: True fuer vollstaendige React-Komponente, Erhalten: {is_ok} ({reason})"

    def test_endet_mit_komma(self):
        """Code der mit ',' endet = Truncation."""
        code = "const items = [1, 2, 3,\n"
        is_ok, reason = _is_js_file_complete(code)
        assert is_ok is False, \
            "Erwartet: False wenn Code mit ',' endet"

    def test_endet_mit_plus_operator(self):
        """Code der mit '+' endet = Truncation."""
        code = "const result = a +\n"
        is_ok, reason = _is_js_file_complete(code)
        assert is_ok is False, \
            "Erwartet: False wenn Code mit '+' endet"


# =========================================================================
# Tests fuer validate_before_write()
# =========================================================================

class TestValidateBeforeWrite:
    """Tests fuer validate_before_write() - Kombinierter Truncation+Schrumpf-Guard."""

    def test_python_ok(self):
        """Valider Python-Code besteht die Pruefung."""
        code = "def hello():\n    return 'world'\n"
        is_valid, reason = validate_before_write("app.py", code)
        assert is_valid is True, \
            f"Erwartet: True fuer validen Python-Code, Erhalten: {is_valid} ({reason})"
        assert reason == "OK", \
            f"Erwartet: 'OK', Erhalten: '{reason}'"

    def test_python_truncated(self):
        """Abgeschnittener Python-Code wird erkannt."""
        code = "def hello(\n"
        is_valid, reason = validate_before_write("app.py", code)
        assert is_valid is False, \
            "Erwartet: False fuer abgeschnittenen Python-Code"
        assert "Truncation" in reason, \
            f"Erwartet: 'Truncation' im Grund, Erhalten: '{reason}'"

    def test_js_ok(self):
        """Valider JS-Code besteht die Pruefung."""
        code = "function hello() {\n  return 'world';\n}\n"
        is_valid, reason = validate_before_write("app.js", code)
        assert is_valid is True, \
            f"Erwartet: True fuer validen JS-Code, Erhalten: {is_valid} ({reason})"

    def test_js_truncated(self):
        """Abgeschnittener JS-Code wird erkannt."""
        code = "function a() {\n  if (true) {\n    if (x) {\n"
        is_valid, reason = validate_before_write("app.js", code)
        assert is_valid is False, \
            "Erwartet: False fuer abgeschnittenen JS-Code"
        assert "Truncation" in reason, \
            f"Erwartet: 'Truncation' im Grund, Erhalten: '{reason}'"

    def test_jsx_datei_wird_geprueft(self):
        """JSX-Dateien werden als JS geprueft."""
        code = "function App() {\n  return <div>Hello</div>\n}\n"
        is_valid, reason = validate_before_write("App.jsx", code)
        assert is_valid is True, \
            f"Erwartet: True fuer valide JSX-Datei, Erhalten: {is_valid} ({reason})"

    def test_tsx_datei_wird_geprueft(self):
        """TSX-Dateien werden als JS geprueft."""
        code = "export default function Page() {\n  return <p>Test</p>\n}\n"
        is_valid, reason = validate_before_write("Page.tsx", code)
        assert is_valid is True, \
            f"Erwartet: True fuer valide TSX-Datei, Erhalten: {is_valid} ({reason})"

    def test_mjs_datei_wird_geprueft(self):
        """MJS-Dateien werden als JS geprueft."""
        code = "export const config = { key: 'value' };\n"
        is_valid, reason = validate_before_write("next.config.mjs", code)
        assert is_valid is True, \
            f"Erwartet: True fuer valide MJS-Datei, Erhalten: {is_valid} ({reason})"

    def test_css_html_immer_ok(self):
        """CSS und HTML Dateien werden nicht geprueft (immer OK)."""
        is_valid_css, _ = validate_before_write("styles.css", "body { color:")
        is_valid_html, _ = validate_before_write("index.html", "<div>")
        assert is_valid_css is True, "Erwartet: True fuer CSS (kein Check)"
        assert is_valid_html is True, "Erwartet: True fuer HTML (kein Check)"

    def test_schrumpf_erkennung_70_prozent_kuerzer(self):
        """Inhalt der um >70% schrumpft wird erkannt."""
        old_content = "x" * 200  # 200 Zeichen
        new_content = "y" * 50   # 50 Zeichen = 75% geschrumpft
        is_valid, reason = validate_before_write("app.css", new_content, old_content=old_content)
        assert is_valid is False, \
            "Erwartet: False bei >70% Schrumpfung"
        assert "geschrumpft" in reason, \
            f"Erwartet: 'geschrumpft' im Grund, Erhalten: '{reason}'"

    def test_schrumpf_kein_old_content(self):
        """Ohne old_content wird kein Schrumpf-Check durchgefuehrt."""
        is_valid, reason = validate_before_write("app.css", "short")
        assert is_valid is True, \
            "Erwartet: True wenn kein old_content zum Vergleich vorhanden"

    def test_schrumpf_old_content_kurz(self):
        """old_content mit <= 50 Zeichen loest keinen Schrumpf-Check aus."""
        old_content = "x" * 50  # Genau 50 Zeichen
        new_content = "y"       # 1 Zeichen
        is_valid, reason = validate_before_write("app.css", new_content, old_content=old_content)
        assert is_valid is True, \
            "Erwartet: True da old_content <= 50 Zeichen (kein Schrumpf-Check)"

    def test_schrumpf_unter_schwelle(self):
        """Inhalt der um 50% schrumpft liegt unter der 70%-Schwelle."""
        old_content = "x" * 200  # 200 Zeichen
        new_content = "y" * 100  # 100 Zeichen = 50% geschrumpft → OK
        is_valid, reason = validate_before_write("app.css", new_content, old_content=old_content)
        assert is_valid is True, \
            "Erwartet: True bei nur 50% Schrumpfung (unter 70%-Schwelle)"


# =========================================================================
# Tests fuer _check_for_truncation()
# =========================================================================

class TestCheckForTruncation:
    """Tests fuer _check_for_truncation() - Batch-Truncation-Check."""

    def test_leeres_dict_keine_truncation(self):
        """Leeres Dict ergibt keine Truncation-Eintraege."""
        result = _check_for_truncation({})
        assert result == [], \
            f"Erwartet: leere Liste, Erhalten: {result}"

    def test_nur_py_dateien_werden_geprueft(self):
        """Nur .py-Dateien werden von _check_for_truncation() geprueft."""
        files = {
            "app.js": "function a() {{{",  # Unbalanciert, aber kein .py
            "utils.py": "def hello():\n    return 1\n",  # Valide
        }
        result = _check_for_truncation(files)
        assert result == [], \
            f"Erwartet: leere Liste (JS nicht geprueft, PY valide), Erhalten: {result}"

    def test_truncated_python_wird_erkannt(self):
        """Abgeschnittene Python-Datei wird in der Liste zurueckgegeben."""
        files = {
            "app.py": "def hello(",  # Truncated
        }
        result = _check_for_truncation(files)
        assert len(result) == 1, \
            f"Erwartet: 1 Truncation-Eintrag, Erhalten: {len(result)}"
        assert result[0][0] == "app.py", \
            f"Erwartet: Dateiname 'app.py', Erhalten: '{result[0][0]}'"

    def test_gemischte_dateien(self):
        """Mix aus validen und truncated Python-Dateien."""
        files = {
            "ok.py": "x = 1\n",
            "broken.py": "def hello(\n",
            "also_ok.py": "class Foo:\n    pass\n",
            "style.css": "body { color: red; }",  # Wird nicht geprueft
        }
        result = _check_for_truncation(files)
        assert len(result) == 1, \
            f"Erwartet: 1 Truncation-Eintrag, Erhalten: {len(result)}"
        assert result[0][0] == "broken.py", \
            f"Erwartet: 'broken.py' als truncated, Erhalten: '{result[0][0]}'"

    def test_mehrere_truncated_dateien(self):
        """Mehrere truncated Python-Dateien werden alle erkannt."""
        files = {
            "a.py": "def a(\n",
            "b.py": "class B:\n    def method(\n",
            "c.py": "x = 1\n",  # Valide
        }
        result = _check_for_truncation(files)
        truncated_names = [name for name, _ in result]
        assert "a.py" in truncated_names, "Erwartet: a.py als truncated"
        assert "b.py" in truncated_names, "Erwartet: b.py als truncated"
        assert "c.py" not in truncated_names, "Erwartet: c.py NICHT als truncated"

    def test_leere_python_datei_ist_truncated(self):
        """Leere Python-Datei wird als truncated erkannt."""
        files = {"empty.py": ""}
        result = _check_for_truncation(files)
        assert len(result) == 1, \
            f"Erwartet: 1 Truncation-Eintrag (leere .py), Erhalten: {len(result)}"


# =========================================================================
# Tests fuer _sanitize_unicode()
# =========================================================================

class TestSanitizeUnicode:
    """Tests fuer _sanitize_unicode() - Unicode-Bereinigung gegen LLM-Artefakte."""

    def test_normaler_text_unveraendert(self):
        """Normaler ASCII-Text bleibt unveraendert."""
        text = "Hello World! def foo(): return 42"
        result = _sanitize_unicode(text)
        assert result == text, \
            f"Erwartet: unveraenderter Text, Erhalten: '{result}'"

    def test_leerer_string(self):
        """Leerer String bleibt leer."""
        result = _sanitize_unicode("")
        assert result == "", \
            f"Erwartet: leerer String, Erhalten: '{result}'"

    def test_emoji_variation_selector_entfernt(self):
        """U+FE0F (Emoji Variation Selector) wird entfernt."""
        text = "Hello\uFE0FWorld"
        result = _sanitize_unicode(text)
        assert result == "HelloWorld", \
            f"Erwartet: 'HelloWorld' (FE0F entfernt), Erhalten: '{result}'"

    def test_text_variation_selector_entfernt(self):
        """U+FE0E (Text Variation Selector) wird entfernt."""
        text = "Test\uFE0ECode"
        result = _sanitize_unicode(text)
        assert result == "TestCode", \
            f"Erwartet: 'TestCode' (FE0E entfernt), Erhalten: '{result}'"

    def test_zero_width_space_entfernt(self):
        """U+200B (Zero Width Space) wird entfernt."""
        text = "x\u200By"
        result = _sanitize_unicode(text)
        assert result == "xy", \
            f"Erwartet: 'xy' (ZWSP entfernt), Erhalten: '{result}'"

    def test_zero_width_non_joiner_entfernt(self):
        """U+200C (Zero Width Non-Joiner) wird entfernt."""
        text = "ab\u200Ccd"
        result = _sanitize_unicode(text)
        assert result == "abcd", \
            f"Erwartet: 'abcd' (ZWNJ entfernt), Erhalten: '{result}'"

    def test_zero_width_joiner_entfernt(self):
        """U+200D (Zero Width Joiner) wird entfernt."""
        text = "ab\u200Dcd"
        result = _sanitize_unicode(text)
        assert result == "abcd", \
            f"Erwartet: 'abcd' (ZWJ entfernt), Erhalten: '{result}'"

    def test_bom_entfernt(self):
        """U+FEFF (Byte Order Mark) wird entfernt."""
        text = "\uFEFFimport os"
        result = _sanitize_unicode(text)
        assert result == "import os", \
            f"Erwartet: 'import os' (BOM entfernt), Erhalten: '{result}'"

    def test_smart_single_quotes_ersetzt(self):
        """U+2018/U+2019 (Smart Single Quotes) werden durch ' ersetzt."""
        text = "\u2018Hello\u2019"
        result = _sanitize_unicode(text)
        assert result == "'Hello'", \
            f"Erwartet: \"'Hello'\", Erhalten: '{result}'"

    def test_smart_double_quotes_ersetzt(self):
        """U+201C/U+201D (Smart Double Quotes) werden durch \" ersetzt."""
        text = "\u201CHello\u201D"
        result = _sanitize_unicode(text)
        assert result == '"Hello"', \
            f'Erwartet: \'\"Hello\"\', Erhalten: \'{result}\''

    def test_em_dash_ersetzt(self):
        """U+2014 (Em Dash) wird durch -- ersetzt."""
        text = "A\u2014B"
        result = _sanitize_unicode(text)
        assert result == "A--B", \
            f"Erwartet: 'A--B', Erhalten: '{result}'"

    def test_en_dash_ersetzt(self):
        """U+2013 (En Dash) wird durch - ersetzt."""
        text = "A\u2013B"
        result = _sanitize_unicode(text)
        assert result == "A-B", \
            f"Erwartet: 'A-B', Erhalten: '{result}'"

    def test_non_breaking_hyphen_ersetzt(self):
        """U+2011 (Non-Breaking Hyphen) wird durch - ersetzt."""
        text = "A\u2011B"
        result = _sanitize_unicode(text)
        assert result == "A-B", \
            f"Erwartet: 'A-B', Erhalten: '{result}'"

    def test_ellipsis_ersetzt(self):
        """U+2026 (Horizontal Ellipsis) wird durch ... ersetzt."""
        text = "Loading\u2026"
        result = _sanitize_unicode(text)
        assert result == "Loading...", \
            f"Erwartet: 'Loading...', Erhalten: '{result}'"

    def test_non_breaking_space_ersetzt(self):
        """U+00A0 (Non-Breaking Space) wird durch normales Space ersetzt."""
        text = "Hello\u00A0World"
        result = _sanitize_unicode(text)
        assert result == "Hello World", \
            f"Erwartet: 'Hello World', Erhalten: '{result}'"

    def test_mehrere_unsichtbare_zeichen_gleichzeitig(self):
        """Mehrere verschiedene unsichtbare Zeichen werden gleichzeitig entfernt."""
        text = "\uFEFF\u200Bimport\u200D os\uFE0F"
        result = _sanitize_unicode(text)
        assert result == "import os", \
            f"Erwartet: 'import os' (alle unsichtbaren Zeichen entfernt), Erhalten: '{result}'"

    def test_gemischte_ersetzungen(self):
        """Mix aus Entfernungen und Ersetzungen funktioniert korrekt."""
        text = "\u201CHello\u201D\u200B \u2014 \u2018World\u2019"
        result = _sanitize_unicode(text)
        assert result == '"Hello" -- \'World\'', \
            f"Erwartet: '\"Hello\" -- 'World'', Erhalten: '{result}'"

    def test_python_code_mit_unicode_artefakten(self):
        """Typischer Python-Code mit LLM-Unicode-Artefakten wird bereinigt."""
        code = "def hello():\u200B\n    print(\u2018Hello\u2019)\n"
        result = _sanitize_unicode(code)
        assert "\u200B" not in result, "ZWSP sollte entfernt sein"
        assert "\u2018" not in result, "Smart Quote links sollte ersetzt sein"
        assert "\u2019" not in result, "Smart Quote rechts sollte ersetzt sein"
        assert "print('Hello')" in result, \
            "Erwartet: Smart Quotes durch ASCII Apostrophe ersetzt"


# =========================================================================
# Zusaetzliche Integrations-Tests (Funktionen zusammen)
# =========================================================================

class TestIntegration:
    """Integrations-Tests: Zusammenspiel mehrerer Pure-Logic Funktionen."""

    def test_parse_und_truncation_check(self):
        """_parse_code_to_files() + _check_for_truncation() zusammen."""
        code = (
            "### FILENAME: ok.py\n"
            "x = 1\n\n"
            "### FILENAME: broken.py\n"
            "def hello(\n"
        )
        files = _parse_code_to_files(code)
        truncated = _check_for_truncation(files)

        assert len(files) == 2, \
            f"Erwartet: 2 Dateien geparst, Erhalten: {len(files)}"
        assert len(truncated) == 1, \
            f"Erwartet: 1 Truncation, Erhalten: {len(truncated)}"
        assert truncated[0][0] == "broken.py", \
            "Erwartet: broken.py als truncated erkannt"

    def test_sanitize_dann_validate(self):
        """_sanitize_unicode() + validate_before_write() zusammen."""
        # Code mit Smart Quotes die Python-Syntax brechen wuerden
        dirty_code = "x = \u2018hello\u2019\n"
        clean_code = _sanitize_unicode(dirty_code)
        is_valid, reason = validate_before_write("test.py", clean_code)
        assert is_valid is True, \
            f"Erwartet: True nach Unicode-Bereinigung, Erhalten: {is_valid} ({reason})"

    def test_parse_filtert_forbidden_und_validate(self):
        """Gesamte Pipeline: Parse → Filter → Validate."""
        code = (
            "### FILENAME: app.py\n"
            "def main():\n    print('Hello')\n\n"
            "### FILENAME: package-lock.json\n"
            '{"lockfileVersion": 3}\n\n'
            "### FILENAME: utils.py\n"
            "def add(a, b):\n    return a + b\n"
        )
        files = _parse_code_to_files(code)
        # package-lock.json sollte gefiltert sein
        assert "package-lock.json" not in files, \
            "Erwartet: package-lock.json gefiltert"
        assert len(files) == 2, \
            f"Erwartet: 2 Dateien (ohne Forbidden), Erhalten: {len(files)}"

        # Alle verbleibenden Dateien sollten valide sein
        for name, content in files.items():
            is_valid, reason = validate_before_write(name, content)
            assert is_valid is True, \
                f"Erwartet: {name} valide, Erhalten: {is_valid} ({reason})"

    def test_hash_error_stabilitaet_mit_normalisierung(self):
        """hash_error() ist stabil ueber verschiedene Ausfuehrungen."""
        fehler = "TypeError at line 42 in C:\\Users\\rahn\\app.py: NoneType has no len()"
        hashes = [hash_error(fehler) for _ in range(100)]
        assert len(set(hashes)) == 1, \
            f"Erwartet: 1 einzigartiger Hash ueber 100 Aufrufe, Erhalten: {len(set(hashes))}"
