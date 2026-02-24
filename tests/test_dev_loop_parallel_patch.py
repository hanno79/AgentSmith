# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 14.02.2026
Version: 1.0
Beschreibung: Tests fuer das Modul backend/dev_loop_parallel_patch.py.
              Prueft ausschliesslich Pure-Logic-Funktionen ohne LLM/Agent-Mocking:
              should_use_parallel_patch, _extract_imports, _get_file_chars,
              group_files_by_dependency, _find_old_content.
"""

import os
import sys

import pytest

# Projekt-Root zum Python-Path hinzufuegen
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.dev_loop_parallel_patch import (
    _extract_imports,
    _find_old_content,
    _get_file_chars,
    group_files_by_dependency,
    should_use_parallel_patch,
)


# =============================================================================
# TestShouldUseParallelPatch — Entscheidungslogik fuer parallelen PatchMode
# =============================================================================

class TestShouldUseParallelPatch:
    """Tests fuer should_use_parallel_patch() — prueft enabled, min_files, min_chars."""

    def test_enabled_false_gibt_false_zurueck(self):
        """Wenn enabled=False in config, wird Parallel-Patch NICHT aktiviert."""
        ergebnis = should_use_parallel_patch(
            ["a.js", "b.js"], {"a.js": "x" * 100}, config={"enabled": False}
        )
        assert ergebnis is False, "Erwartet: False bei enabled=False"

    def test_zwei_dateien_aktiviert_parallel(self):
        """2+ betroffene Dateien aktivieren Parallel-Patch (min_files=2 default)."""
        ergebnis = should_use_parallel_patch(
            ["a.js", "b.js"], {"a.js": "abc", "b.js": "def"}
        )
        assert ergebnis is True, "Erwartet: True bei 2 Dateien (min_files=2)"

    def test_drei_dateien_aktiviert_parallel(self):
        """3 Dateien liegen ueber dem Default-Minimum von 2."""
        ergebnis = should_use_parallel_patch(
            ["a.js", "b.js", "c.js"], {"a.js": "x"}
        )
        assert ergebnis is True, "Erwartet: True bei 3 Dateien"

    def test_eine_datei_unter_min_chars_gibt_false(self):
        """1 Datei mit weniger als 8000 Zeichen → False."""
        ergebnis = should_use_parallel_patch(
            ["a.js"], {"a.js": "x" * 5000}
        )
        assert ergebnis is False, "Erwartet: False bei 1 Datei und 5000 chars"

    def test_eine_datei_ueber_min_chars_gibt_true(self):
        """1 Datei mit >= 8000 Zeichen aktiviert Parallel-Patch."""
        ergebnis = should_use_parallel_patch(
            ["a.js"], {"a.js": "x" * 8000}
        )
        assert ergebnis is True, "Erwartet: True bei 1 Datei und 8000 chars"

    def test_leere_affected_files_gibt_false(self):
        """Leere Liste betroffener Dateien → False."""
        ergebnis = should_use_parallel_patch([], {"a.js": "x" * 10000})
        assert ergebnis is False, "Erwartet: False bei leerer Dateiliste"

    def test_custom_min_files_hoeher(self):
        """Custom min_files=5: Bei 3 Dateien wird NICHT aktiviert."""
        ergebnis = should_use_parallel_patch(
            ["a.js", "b.js", "c.js"],
            {"a.js": "x", "b.js": "y", "c.js": "z"},
            config={"min_files_for_parallel": 5}
        )
        assert ergebnis is False, "Erwartet: False bei 3 Dateien und min_files=5"

    def test_custom_min_chars_niedriger(self):
        """Custom min_chars=1000: 1 Datei mit 1500 Zeichen aktiviert."""
        ergebnis = should_use_parallel_patch(
            ["a.js"],
            {"a.js": "x" * 1500},
            config={"min_chars_for_parallel": 1000}
        )
        assert ergebnis is True, "Erwartet: True bei 1500 chars und min_chars=1000"

    def test_affected_file_nicht_in_code_dict(self):
        """Datei in affected_files aber nicht in code_dict → 0 chars, False."""
        ergebnis = should_use_parallel_patch(
            ["missing.js"], {"other.js": "x" * 10000}
        )
        assert ergebnis is False, "Erwartet: False wenn Datei nicht in code_dict"

    def test_basename_matching_findet_datei(self):
        """code_dict hat vollen Pfad, affected_files nur Basename → chars gefunden."""
        ergebnis = should_use_parallel_patch(
            ["file.js"],
            {"src/components/file.js": "x" * 9000},
            config={"min_chars_for_parallel": 8000}
        )
        assert ergebnis is True, "Erwartet: True durch Basename-Matching"

    def test_endswith_matching_findet_datei(self):
        """affected_file = 'lib/utils.js', code_dict hat 'app/lib/utils.js'."""
        ergebnis = should_use_parallel_patch(
            ["lib/utils.js"],
            {"app/lib/utils.js": "x" * 9000},
            config={"min_chars_for_parallel": 8000}
        )
        assert ergebnis is True, "Erwartet: True durch endswith-Matching"

    def test_none_config_verwendet_defaults(self):
        """config=None nutzt Default-Werte (enabled=True, min_files=2, min_chars=8000)."""
        ergebnis = should_use_parallel_patch(
            ["a.js", "b.js"], {"a.js": "x"}, config=None
        )
        assert ergebnis is True, "Erwartet: True mit Default-Config und 2 Dateien"

    def test_leere_config_verwendet_defaults(self):
        """Leeres config-Dict nutzt Default-Werte."""
        ergebnis = should_use_parallel_patch(
            ["a.js", "b.js"], {"a.js": "x"}, config={}
        )
        assert ergebnis is True, "Erwartet: True mit leerem Config und 2 Dateien"

    def test_genau_min_chars_grenzwert(self):
        """Exakt min_chars Zeichen → True (>= Vergleich)."""
        ergebnis = should_use_parallel_patch(
            ["a.js"],
            {"a.js": "x" * 8000},
            config={"min_chars_for_parallel": 8000}
        )
        assert ergebnis is True, "Erwartet: True bei exakt min_chars Zeichen"

    def test_knapp_unter_min_chars_grenzwert(self):
        """Knapp unter min_chars → False."""
        ergebnis = should_use_parallel_patch(
            ["a.js"],
            {"a.js": "x" * 7999},
            config={"min_chars_for_parallel": 8000}
        )
        assert ergebnis is False, "Erwartet: False bei 7999 chars (min_chars=8000)"


# =============================================================================
# TestExtractImports — Import-Erkennung aus JS/TS/Python Code
# =============================================================================

class TestExtractImports:
    """Tests fuer _extract_imports() — erkennt Imports aus JS/TS und Python Quellcode."""

    def test_js_import_ohne_extension(self):
        """import X from './utils' → Basename mit allen JS/TS-Extensions."""
        ergebnis = _extract_imports("import React from './utils'")
        assert "utils.js" in ergebnis, "Erwartet: utils.js in Ergebnis"
        assert "utils.jsx" in ergebnis, "Erwartet: utils.jsx in Ergebnis"
        assert "utils.ts" in ergebnis, "Erwartet: utils.ts in Ergebnis"
        assert "utils.tsx" in ergebnis, "Erwartet: utils.tsx in Ergebnis"

    def test_js_import_mit_extension(self):
        """import X from './utils.js' → nur diese Extension."""
        ergebnis = _extract_imports("import { func } from './utils.js'")
        assert ergebnis == ["utils.js"], "Erwartet: nur ['utils.js']"

    def test_js_import_relative_parent(self):
        """import X from '../lib/db' → Basename 'db' mit Extensions."""
        ergebnis = _extract_imports("import db from '../lib/db'")
        assert "db.js" in ergebnis, "Erwartet: db.js"
        assert "db.tsx" in ergebnis, "Erwartet: db.tsx"

    def test_js_require_relativ(self):
        """require('./helper') → Basename mit Extensions."""
        ergebnis = _extract_imports("const h = require('./helper')")
        assert "helper.js" in ergebnis, "Erwartet: helper.js"
        assert "helper.jsx" in ergebnis, "Erwartet: helper.jsx"

    def test_js_import_absolut_wird_ignoriert(self):
        """import X from 'react' → kein relativer Import, leer."""
        ergebnis = _extract_imports("import React from 'react'")
        # Relative JS-Imports ergeben nichts; Python-Pattern koennte matchen
        js_ergebnisse = [e for e in ergebnis if not e.endswith(".py")]
        assert js_ergebnisse == [], "Erwartet: Keine JS-Imports fuer absolute Module"

    def test_js_import_mit_doppelten_punkten_tief(self):
        """import X from '../../shared/constants' → Basename constants mit Extensions."""
        ergebnis = _extract_imports("import { API_URL } from '../../shared/constants'")
        assert "constants.js" in ergebnis, "Erwartet: constants.js"

    def test_python_relative_import(self):
        """from .utils import func → utils.py."""
        ergebnis = _extract_imports("from .utils import func")
        assert "utils.py" in ergebnis, "Erwartet: utils.py"

    def test_python_absolute_import(self):
        """from models import User → models.py."""
        ergebnis = _extract_imports("from models import User")
        assert "models.py" in ergebnis, "Erwartet: models.py"

    def test_leerer_string_gibt_leere_liste(self):
        """Leerer String → keine Imports."""
        ergebnis = _extract_imports("")
        assert ergebnis == [], "Erwartet: Leere Liste bei leerem String"

    def test_kein_import_im_code(self):
        """Code ohne Imports → leere Liste."""
        ergebnis = _extract_imports("const x = 42;\nfunction add(a, b) { return a + b; }")
        assert ergebnis == [], "Erwartet: Leere Liste ohne Imports"

    def test_mehrere_js_imports(self):
        """Mehrere Import-Zeilen → alle Basenames extrahiert."""
        code = (
            "import A from './alpha'\n"
            "import B from './beta.js'\n"
        )
        ergebnis = _extract_imports(code)
        # alpha ohne Extension → 4 Varianten, beta.js → 1
        assert "alpha.js" in ergebnis, "Erwartet: alpha.js"
        assert "beta.js" in ergebnis, "Erwartet: beta.js"

    def test_require_mit_extension(self):
        """require('./config.json') → config.json (Extension vorhanden)."""
        ergebnis = _extract_imports("const cfg = require('./config.json')")
        assert "config.json" in ergebnis, "Erwartet: config.json"

    def test_gemischte_js_und_python_imports(self):
        """JS- und Python-Imports im selben Code → beide erkannt."""
        code = (
            "import stuff from './mylib'\n"
            "from .helpers import do_thing\n"
        )
        ergebnis = _extract_imports(code)
        assert "mylib.js" in ergebnis, "Erwartet: mylib.js aus JS-Import"
        assert "helpers.py" in ergebnis, "Erwartet: helpers.py aus Python-Import"

    def test_js_import_mit_einfachen_anfuehrungszeichen(self):
        """Import mit Single-Quotes wird erkannt."""
        ergebnis = _extract_imports("import X from './single'")
        assert "single.js" in ergebnis, "Erwartet: single.js"

    def test_js_import_mit_doppelten_anfuehrungszeichen(self):
        """Import mit Double-Quotes wird erkannt."""
        ergebnis = _extract_imports('import X from "./double"')
        assert "double.js" in ergebnis, "Erwartet: double.js"


# =============================================================================
# TestGetFileChars — Zeichenanzahl per Basename-/Endswith-Matching
# =============================================================================

class TestGetFileChars:
    """Tests fuer _get_file_chars() — Zeichenanzahl-Ermittlung mit Matching."""

    def test_exaktes_matching(self):
        """Dateiname stimmt exakt ueberein → Zeichenanzahl."""
        ergebnis = _get_file_chars("file.js", {"file.js": "abc"})
        assert ergebnis == 3, "Erwartet: 3 Zeichen bei exaktem Match"

    def test_basename_matching(self):
        """code_dict hat vollen Pfad, Suche mit Basename → gefunden."""
        ergebnis = _get_file_chars("file.js", {"src/components/file.js": "abcdef"})
        assert ergebnis == 6, "Erwartet: 6 Zeichen durch Basename-Matching"

    def test_endswith_matching(self):
        """fname='lib/db.js', code_dict='app/lib/db.js' → endswith Match."""
        ergebnis = _get_file_chars("lib/db.js", {"app/lib/db.js": "x"})
        assert ergebnis == 1, "Erwartet: 1 Zeichen durch endswith-Matching"

    def test_nicht_gefunden_gibt_null(self):
        """Datei nicht im code_dict → 0."""
        ergebnis = _get_file_chars("missing.js", {"other.js": "content"})
        assert ergebnis == 0, "Erwartet: 0 bei nicht gefundener Datei"

    def test_leeres_code_dict(self):
        """Leeres code_dict → 0."""
        ergebnis = _get_file_chars("any.js", {})
        assert ergebnis == 0, "Erwartet: 0 bei leerem code_dict"


# =============================================================================
# TestGroupFilesByDependency — Gruppierung mit Union-Find und Char-Split
# =============================================================================

class TestGroupFilesByDependency:
    """Tests fuer group_files_by_dependency() — Union-Find + dynamischer Char-Split."""

    # --- Wenige Dateien (unter max_per_group) ---

    def test_eine_datei_kleine_gruppe(self):
        """1 Datei, klein → 1 Gruppe mit dieser Datei."""
        gruppen = group_files_by_dependency(
            ["a.js"], {"a.js": "kurz"}, max_per_group=3
        )
        assert len(gruppen) == 1, "Erwartet: 1 Gruppe"
        assert "a.js" in gruppen[0], "Erwartet: a.js in Gruppe"

    def test_drei_kleine_dateien_eine_gruppe(self):
        """3 kleine Dateien, max_per_group=3 → 1 Gruppe (unter max_chars)."""
        code = {"a.js": "x" * 100, "b.js": "y" * 100, "c.js": "z" * 100}
        gruppen = group_files_by_dependency(
            ["a.js", "b.js", "c.js"], code, max_per_group=3
        )
        assert len(gruppen) == 1, "Erwartet: 1 Gruppe bei 3 kleinen Dateien"

    def test_drei_dateien_ueber_max_chars_gesplittet(self):
        """3 Dateien je 6000 Zeichen, max_chars=15000 → Split noetig (18000 > 15000)."""
        code = {"a.js": "x" * 6000, "b.js": "y" * 6000, "c.js": "z" * 6000}
        gruppen = group_files_by_dependency(
            ["a.js", "b.js", "c.js"], code,
            max_per_group=3, max_chars_per_group=15000
        )
        assert len(gruppen) >= 2, (
            f"Erwartet: >= 2 Gruppen bei 18000 chars und max_chars=15000, "
            f"erhalten: {len(gruppen)}"
        )

    # --- Union-Find Dependency-Grouping ---

    def test_import_verbindet_dateien(self):
        """A importiert B → beide in derselben Gruppe."""
        code = {
            "a.js": "import helper from './b'",
            "b.js": "export default function() {}",
            "c.js": "const x = 1;",
            "d.js": "const y = 2;",
        }
        gruppen = group_files_by_dependency(
            ["a.js", "b.js", "c.js", "d.js"], code, max_per_group=4
        )
        # Finde Gruppe mit a.js
        gruppe_a = [g for g in gruppen if "a.js" in g][0]
        assert "b.js" in gruppe_a, "Erwartet: b.js in selber Gruppe wie a.js"

    def test_unabhaengige_dateien_separate_gruppen(self):
        """A, B, C ohne Imports → separate Gruppen (bei max_per_group=1)."""
        code = {"a.js": "const a=1;", "b.js": "const b=2;", "c.js": "const c=3;"}
        gruppen = group_files_by_dependency(
            ["a.js", "b.js", "c.js"], code, max_per_group=1
        )
        assert len(gruppen) == 3, "Erwartet: 3 separate Gruppen bei max_per_group=1"

    def test_zwei_dep_paare_getrennt(self):
        """A→B und C→D bilden 2 Gruppen."""
        code = {
            "a.js": "import x from './b'",
            "b.js": "export const x = 1;",
            "c.js": "import y from './d'",
            "d.js": "export const y = 2;",
        }
        gruppen = group_files_by_dependency(
            ["a.js", "b.js", "c.js", "d.js"], code,
            max_per_group=4, max_chars_per_group=50000
        )
        # Finde Gruppen
        gruppe_a = [g for g in gruppen if "a.js" in g][0]
        gruppe_c = [g for g in gruppen if "c.js" in g][0]
        assert "b.js" in gruppe_a, "Erwartet: b.js mit a.js"
        assert "d.js" in gruppe_c, "Erwartet: d.js mit c.js"
        # A/B und C/D sollten in verschiedenen Gruppen sein
        assert gruppe_a != gruppe_c or len(gruppen) == 1, (
            "Erwartet: A/B und C/D in verschiedenen Gruppen (oder alle zusammen)"
        )

    def test_transitive_deps_vereinigt(self):
        """A→B→C: Transitive Verbindung → alle in einer Gruppe."""
        code = {
            "a.js": "import x from './b'",
            "b.js": "import y from './c'\nexport const x = 1;",
            "c.js": "export const y = 2;",
        }
        gruppen = group_files_by_dependency(
            ["a.js", "b.js", "c.js"], code,
            max_per_group=3, max_chars_per_group=50000
        )
        # Alle sollten in 1 Gruppe sein
        assert len(gruppen) == 1, "Erwartet: 1 Gruppe bei transitiver Abhaengigkeit"
        assert set(gruppen[0]) == {"a.js", "b.js", "c.js"}, (
            "Erwartet: Alle 3 Dateien in einer Gruppe"
        )

    # --- Dynamischer Split nach Zeichenanzahl ---

    def test_grosse_datei_eigene_gruppe(self):
        """1 Datei > max_chars → eigene Gruppe."""
        code = {"big.js": "x" * 20000, "small.js": "y" * 100}
        gruppen = group_files_by_dependency(
            ["big.js", "small.js"], code,
            max_per_group=5, max_chars_per_group=15000
        )
        # big.js sollte alleine in einer Gruppe sein
        gruppe_big = [g for g in gruppen if "big.js" in g][0]
        assert gruppe_big == ["big.js"], "Erwartet: big.js alleine in eigener Gruppe"

    def test_split_nach_max_per_group(self):
        """max_per_group=2 bei 4 Dateien → mindestens 2 Gruppen."""
        code = {"a.js": "x", "b.js": "y", "c.js": "z", "d.js": "w"}
        gruppen = group_files_by_dependency(
            ["a.js", "b.js", "c.js", "d.js"], code,
            max_per_group=2, max_chars_per_group=50000
        )
        assert len(gruppen) >= 2, "Erwartet: >= 2 Gruppen bei max_per_group=2"
        for g in gruppen:
            assert len(g) <= 2, f"Erwartet: max 2 Dateien pro Gruppe, erhalten: {len(g)}"

    def test_chars_limit_erzwingt_split(self):
        """2 Dateien je 10000 chars, max_chars=12000 → 2 Gruppen."""
        code = {"a.js": "x" * 10000, "b.js": "y" * 10000}
        gruppen = group_files_by_dependency(
            ["a.js", "b.js"], code,
            max_per_group=5, max_chars_per_group=12000
        )
        assert len(gruppen) == 2, (
            f"Erwartet: 2 Gruppen bei 20000 chars und max_chars=12000, "
            f"erhalten: {len(gruppen)}"
        )

    # --- Edge Cases ---

    def test_leere_affected_files(self):
        """Leere Dateiliste → leere Gruppenliste."""
        gruppen = group_files_by_dependency([], {"a.js": "x"})
        assert gruppen == [[]], "Erwartet: Liste mit leerer Gruppe bei leerer Eingabe"

    def test_dateien_nicht_in_code_dict(self):
        """Dateien nicht im code_dict → 0 chars, Gruppe trotzdem erstellt."""
        gruppen = group_files_by_dependency(
            ["missing.js"], {}, max_per_group=3
        )
        assert len(gruppen) == 1, "Erwartet: 1 Gruppe auch ohne code_dict-Eintrag"
        assert "missing.js" in gruppen[0], "Erwartet: missing.js in Gruppe"

    def test_max_per_group_eins_jede_datei_eigene_gruppe(self):
        """max_per_group=1 → jede Datei bekommt eigene Gruppe."""
        code = {"a.js": "x", "b.js": "y", "c.js": "z"}
        gruppen = group_files_by_dependency(
            ["a.js", "b.js", "c.js"], code,
            max_per_group=1, max_chars_per_group=50000
        )
        assert len(gruppen) == 3, "Erwartet: 3 Gruppen bei max_per_group=1"

    def test_alle_dateien_verbunden_ueber_max_per_group(self):
        """Alle abhaengig, Gruppe > max_per_group → wird gesplittet."""
        # A→B, B→C, C→D → alle verbunden, aber max_per_group=2
        code = {
            "a.js": "import x from './b'",
            "b.js": "import y from './c'",
            "c.js": "import z from './d'",
            "d.js": "export const z = 1;",
        }
        gruppen = group_files_by_dependency(
            ["a.js", "b.js", "c.js", "d.js"], code,
            max_per_group=2, max_chars_per_group=50000
        )
        assert len(gruppen) >= 2, "Erwartet: >= 2 Gruppen trotz Abhaengigkeiten"
        for g in gruppen:
            assert len(g) <= 2, f"Erwartet: max 2 Dateien pro Gruppe"

    def test_viele_kleine_dateien(self):
        """10 kleine Dateien, max_per_group=3 → mehrere Gruppen."""
        dateien = [f"file{i}.js" for i in range(10)]
        code = {f: "x" * 50 for f in dateien}
        gruppen = group_files_by_dependency(
            dateien, code, max_per_group=3, max_chars_per_group=50000
        )
        assert len(gruppen) >= 2, "Erwartet: Mehrere Gruppen bei 10 Dateien"
        # Alle Dateien muessen enthalten sein
        alle_in_gruppen = [f for g in gruppen for f in g]
        assert set(alle_in_gruppen) == set(dateien), (
            "Erwartet: Alle Dateien in Gruppen enthalten"
        )

    def test_keine_doppelten_dateien_in_gruppen(self):
        """Keine Datei darf in mehreren Gruppen vorkommen."""
        code = {
            "a.js": "import x from './b'",
            "b.js": "export const x = 1;",
            "c.js": "const c = 3;",
        }
        gruppen = group_files_by_dependency(
            ["a.js", "b.js", "c.js"], code,
            max_per_group=2, max_chars_per_group=50000
        )
        alle = [f for g in gruppen for f in g]
        assert len(alle) == len(set(alle)), "Erwartet: Keine doppelten Dateien"

    def test_einzelne_datei_gibt_eine_gruppe(self):
        """Genau 1 Datei → exakt 1 Gruppe."""
        gruppen = group_files_by_dependency(
            ["only.js"], {"only.js": "content"}, max_per_group=3
        )
        assert len(gruppen) == 1, "Erwartet: 1 Gruppe bei 1 Datei"
        assert gruppen[0] == ["only.js"], "Erwartet: ['only.js']"

    def test_basename_matching_fuer_deps(self):
        """code_dict mit vollen Pfaden, affected_files als Basenames."""
        code = {
            "src/a.js": "import x from './b'",
            "src/b.js": "export const x = 1;",
        }
        gruppen = group_files_by_dependency(
            ["a.js", "b.js"], code, max_per_group=3, max_chars_per_group=50000
        )
        assert len(gruppen) == 1, "Erwartet: 1 Gruppe (a.js importiert b.js)"
        assert set(gruppen[0]) == {"a.js", "b.js"}, "Erwartet: Beide in einer Gruppe"

    @pytest.mark.parametrize("max_chars,erwartete_min_gruppen", [
        (50000, 1),   # Alles passt in eine Gruppe
        (200, 2),     # Split erzwungen
        (50, 3),      # Noch staerkerer Split
    ])
    def test_parametrisierter_char_split(self, max_chars, erwartete_min_gruppen):
        """Verschiedene max_chars Werte fuehren zu unterschiedlichen Gruppen-Anzahlen."""
        code = {"a.js": "x" * 100, "b.js": "y" * 100, "c.js": "z" * 100}
        gruppen = group_files_by_dependency(
            ["a.js", "b.js", "c.js"], code,
            max_per_group=3, max_chars_per_group=max_chars
        )
        assert len(gruppen) >= erwartete_min_gruppen, (
            f"Erwartet: >= {erwartete_min_gruppen} Gruppen bei max_chars={max_chars}, "
            f"erhalten: {len(gruppen)}"
        )


# =============================================================================
# TestFindOldContent — Inhalts-Suche mit Basename-/Endswith-Matching
# =============================================================================

class TestFindOldContent:
    """Tests fuer _find_old_content() — findet bisherigen Datei-Inhalt."""

    def test_exakter_match(self):
        """Dateiname stimmt exakt ueberein → Inhalt zurueckgegeben."""
        ergebnis = _find_old_content("file.js", {"file.js": "alter Inhalt"})
        assert ergebnis == "alter Inhalt", "Erwartet: 'alter Inhalt'"

    def test_basename_match(self):
        """code_dict mit vollem Pfad, fname als Basename → gefunden."""
        ergebnis = _find_old_content(
            "file.js", {"src/components/file.js": "content123"}
        )
        assert ergebnis == "content123", "Erwartet: 'content123' per Basename"

    def test_endswith_match(self):
        """fname='lib/utils.js', code_dict='app/lib/utils.js' → endswith-Match."""
        ergebnis = _find_old_content(
            "lib/utils.js", {"app/lib/utils.js": "util code"}
        )
        assert ergebnis == "util code", "Erwartet: 'util code' per endswith"

    def test_nicht_gefunden_gibt_leerstring(self):
        """Datei nicht im code_dict → leerer String."""
        ergebnis = _find_old_content("missing.js", {"other.js": "x"})
        assert ergebnis == "", "Erwartet: Leerer String bei nicht gefundener Datei"

    def test_leeres_code_dict(self):
        """Leeres code_dict → leerer String."""
        ergebnis = _find_old_content("any.js", {})
        assert ergebnis == "", "Erwartet: Leerer String bei leerem code_dict"
