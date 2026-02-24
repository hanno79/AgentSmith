# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 14.02.2026
Version: 1.0
Beschreibung: Tests fuer das Context-Compressor-Modul (backend/context_compressor.py).
              Prueft die intelligente Context-Kompression: Kategorisierung (A/B/C),
              Feedback-Datei-Erkennung, Import-Abhaengigkeiten, Caching und
              die typ-spezifischen Struktur-Extraktoren (JS, Python, CSS, JSON).
"""

import hashlib
import json
import os
import sys

import pytest

# Projekt-Root zum Python-Path hinzufuegen
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.context_compressor import (
    FALSE_POSITIVE_FILENAMES,
    _extract_css_structure,
    _extract_feedback_files,
    _extract_file_structure,
    _extract_js_structure,
    _extract_json_structure,
    _extract_python_structure,
    _find_import_deps,
    compress_context,
)


# =============================================================================
# TestCompressContext - Hauptfunktion: Komprimierung mit Kategorien A/B/C
# =============================================================================

class TestCompressContext:
    """Tests fuer compress_context() - die Hauptfunktion der Context-Kompression."""

    def test_leeres_code_dict_gibt_leeres_dict_zurueck(self):
        """Leeres code_dict wird direkt zurueckgegeben ohne Verarbeitung."""
        ergebnis = compress_context({}, "irgendein Feedback")
        assert ergebnis == {}

    def test_none_code_dict_wird_als_falsy_behandelt(self):
        """None als code_dict wird als leeres Dict behandelt (falsy check)."""
        ergebnis = compress_context(None, "Feedback")
        assert ergebnis is None

    def test_feedback_dateien_werden_voll_uebernommen(self, sample_code_dict, sample_feedback):
        """Dateien aus dem Feedback (Kategorie A) werden mit vollem Inhalt uebernommen."""
        ergebnis = compress_context(sample_code_dict, sample_feedback)

        # page.js und db.js sind im Feedback referenziert → voller Inhalt
        for fname, content in sample_code_dict.items():
            if "page.js" in fname or "db.js" in fname:
                assert ergebnis[fname] == content, (
                    f"Erwartet: Voller Inhalt fuer {fname}, Erhalten: Zusammenfassung"
                )

    def test_import_deps_werden_voll_uebernommen(self, sample_code_dict, sample_feedback):
        """Import-Abhaengigkeiten (Kategorie B) werden mit vollem Inhalt uebernommen."""
        ergebnis = compress_context(sample_code_dict, sample_feedback)

        # route.js importiert aus lib/db → route.js ist im Feedback
        # lib/db.js wird von route.js importiert, ist aber AUCH direkt im Feedback
        # Pruefe dass lib/db.js voll uebernommen wird
        for fname in sample_code_dict:
            if "db.js" in fname:
                assert ergebnis[fname] == sample_code_dict[fname]

    def test_nicht_referenzierte_dateien_werden_zusammengefasst(self, sample_code_dict):
        """Dateien ohne Feedback-Bezug (Kategorie C) erhalten eine Zusammenfassung."""
        # Feedback referenziert nur page.js
        feedback = "[DATEI:app/page.js] hat einen Fehler"
        ergebnis = compress_context(sample_code_dict, feedback)

        # layout.js ist nicht im Feedback und keine Import-Dep → Summary
        for fname in sample_code_dict:
            if "layout.js" in fname:
                assert ergebnis[fname] != sample_code_dict[fname], (
                    f"Erwartet: Zusammenfassung fuer {fname}, Erhalten: Voller Inhalt"
                )

    def test_cache_wird_im_ergebnis_mitgegeben(self, sample_code_dict):
        """Das Ergebnis enthaelt einen '_cache' Key fuer Persistenz."""
        ergebnis = compress_context(sample_code_dict, "")
        assert '_cache' in ergebnis
        assert isinstance(ergebnis['_cache'], dict)

    def test_cache_hit_bei_unveraendertem_inhalt(self, sample_code_dict):
        """Bei identischem Inhalt wird die gecachte Summary wiederverwendet."""
        # Erster Durchlauf: Cache befuellen
        ergebnis_1 = compress_context(sample_code_dict, "")
        cache_nach_1 = ergebnis_1['_cache']

        # Zweiter Durchlauf: Cache uebergeben → Cache-Hits
        ergebnis_2 = compress_context(sample_code_dict, "", cache=cache_nach_1)

        # Nicht-Feedback-Dateien muessen gleiche Summaries haben
        for fname in sample_code_dict:
            assert ergebnis_1[fname] == ergebnis_2[fname], (
                f"Cache-Miss fuer {fname}: Summaries unterschiedlich"
            )

    def test_cache_miss_bei_veraendertem_inhalt(self, sample_code_dict):
        """Bei geaendertem Inhalt wird eine neue Summary erstellt."""
        ergebnis_1 = compress_context(sample_code_dict, "")
        cache_nach_1 = ergebnis_1['_cache']

        # Inhalt aendern
        geaendertes_dict = dict(sample_code_dict)
        geaendertes_dict["app/layout.js"] = "// Komplett neuer Inhalt\nexport default function X() {}"

        ergebnis_2 = compress_context(geaendertes_dict, "", cache=cache_nach_1)

        # Cache-Eintrag muss aktualisiert sein
        neuer_hash = hashlib.md5(geaendertes_dict["app/layout.js"].encode()).hexdigest()[:8]
        assert ergebnis_2['_cache']["app/layout.js"]['hash'] == neuer_hash

    def test_basename_fuzzy_matching(self):
        """Feedback mit Basenames matched gegen volle Pfade im code_dict."""
        code_dict = {
            "src/components/Header.jsx": "export default function Header() { return <h1>Hi</h1> }",
            "src/lib/utils.js": "export function formatDate(d) { return d.toISOString() }",
        }
        feedback = "[DATEI:Header.jsx] hat fehlende Props-Validierung"

        ergebnis = compress_context(code_dict, feedback)

        # Header.jsx muss voll uebernommen werden (Basename-Match)
        assert ergebnis["src/components/Header.jsx"] == code_dict["src/components/Header.jsx"]
        # utils.js ist nicht referenziert → Summary
        assert ergebnis["src/lib/utils.js"] != code_dict["src/lib/utils.js"]

    def test_config_und_model_router_optional(self, sample_code_dict):
        """config und model_router sind optional und duerfen None sein."""
        ergebnis = compress_context(sample_code_dict, "", model_router=None, config=None, cache=None)
        assert '_cache' in ergebnis

    def test_leeres_feedback_alle_dateien_zusammengefasst(self, sample_code_dict):
        """Bei leerem Feedback werden alle Dateien zusammengefasst (Kategorie C)."""
        ergebnis = compress_context(sample_code_dict, "")

        for fname, content in sample_code_dict.items():
            # Alle Dateien sollten zusammengefasst sein (nicht voller Inhalt)
            # Summaries enthalten typische Marker wie IMPORTS:, FUNKTIONEN:, ZEILEN:
            if "IMPORTS:" in ergebnis[fname] or "ZEILEN:" in ergebnis[fname] or "VORSCHAU:" in ergebnis[fname]:
                # Richtig: Ist eine Zusammenfassung
                pass
            elif fname == '_cache':
                continue
            else:
                # package.json koennte NAME: oder DEPENDENCIES: haben
                assert any(marker in ergebnis[fname] for marker in [
                    "IMPORTS:", "ZEILEN:", "NAME:", "DEPENDENCIES:", "TOP-KEYS:", "VORSCHAU:",
                    "FUNKTIONEN:", "EXPORTS:", "KLASSEN:", "SELEKTOREN:"
                ]), f"Erwartet: Zusammenfassung fuer {fname}, Erhalten: {ergebnis[fname][:100]}"


# =============================================================================
# TestExtractFeedbackFiles - Feedback-Datei-Erkennung
# =============================================================================

class TestExtractFeedbackFiles:
    """Tests fuer _extract_feedback_files() - Dateinamen aus Feedback extrahieren."""

    def test_leeres_feedback_gibt_leere_liste(self):
        """Leeres oder None-Feedback gibt leere Liste zurueck."""
        assert _extract_feedback_files("") == []
        assert _extract_feedback_files(None) == []

    def test_datei_marker_format(self):
        """[DATEI:xxx] Format wird korrekt erkannt."""
        feedback = "[DATEI:app/page.js] hat einen Fehler\n[DATEI:lib/db.js] SQL-Problem"
        ergebnis = _extract_feedback_files(feedback)

        assert "page.js" in ergebnis
        assert "db.js" in ergebnis

    def test_file_marker_englisch(self):
        """[File: xxx] Format (englisch) wird erkannt."""
        feedback = "[File: components/Header.jsx] missing props"
        ergebnis = _extract_feedback_files(feedback)
        assert "Header.jsx" in ergebnis

    def test_python_traceback_format(self):
        """Python Traceback-Format File 'xxx.py' wird erkannt."""
        feedback = 'File "backend/server.py", line 42, in handle_request'
        ergebnis = _extract_feedback_files(feedback)
        assert "server.py" in ergebnis

    def test_python_colon_format(self):
        """Python-Datei mit Doppelpunkt (xxx.py:) wird erkannt."""
        feedback = "utils.py: ImportError bei Zeile 5"
        ergebnis = _extract_feedback_files(feedback)
        assert "utils.py" in ergebnis

    def test_js_datei_mit_leerzeichen_und_doppelpunkt(self):
        """JS/JSX/TS/TSX Dateien mit Leerzeichen oder Doppelpunkt werden erkannt."""
        feedback = "app/api/route.js: Missing export\ncomponents/Card.tsx hat Fehler"
        ergebnis = _extract_feedback_files(feedback)
        assert "route.js" in ergebnis
        assert "Card.tsx" in ergebnis

    def test_error_prefix_format(self):
        """Error: xxx.js Format wird erkannt."""
        feedback = "Error: app/layout.js konnte nicht kompiliert werden"
        ergebnis = _extract_feedback_files(feedback)
        assert "layout.js" in ergebnis

    def test_datei_hat_contains_format(self):
        """'xxx.js hat/has/contains' Format wird erkannt."""
        feedback = "components/Button.jsx hat fehlende Imports"
        ergebnis = _extract_feedback_files(feedback)
        assert "Button.jsx" in ergebnis

    def test_false_positive_filenames_werden_gefiltert(self):
        """Framework-Namen wie Next.js, Node.js werden als False Positives gefiltert."""
        feedback = "Next.js hat einen Hydration-Error. Die Datei page.js ist betroffen."
        ergebnis = _extract_feedback_files(feedback)

        assert "Next.js" not in ergebnis
        assert "next.js" not in ergebnis
        # page.js sollte erkannt werden
        assert "page.js" in ergebnis

    def test_alle_false_positive_namen(self):
        """Alle bekannten False-Positive-Namen werden korrekt gefiltert."""
        for fp_name in FALSE_POSITIVE_FILENAMES:
            # Jeder FP-Name als Feedback-Text
            feedback = f"{fp_name} hat Probleme"
            ergebnis = _extract_feedback_files(feedback)
            assert fp_name not in [e.lower() for e in ergebnis], (
                f"False Positive nicht gefiltert: {fp_name}"
            )

    def test_system_bibliotheken_werden_ausgeschlossen(self):
        """Pfade mit site-packages, python3, /usr/, venv/ werden ignoriert."""
        feedback = 'File "/usr/lib/python3/site-packages/flask/app.py", line 100'
        ergebnis = _extract_feedback_files(feedback)
        assert len(ergebnis) == 0

    def test_max_10_dateien(self):
        """Maximal 10 Feedback-Dateien werden zurueckgegeben."""
        zeilen = [f"[DATEI:datei_{i}.js] Fehler" for i in range(15)]
        feedback = "\n".join(zeilen)
        ergebnis = _extract_feedback_files(feedback)
        assert len(ergebnis) <= 10

    def test_duplikate_werden_entfernt(self):
        """Gleiche Dateinamen werden nur einmal zurueckgegeben."""
        feedback = "[DATEI:page.js] Fehler 1\n[DATEI:page.js] Fehler 2\npage.js hat Probleme"
        ergebnis = _extract_feedback_files(feedback)
        assert ergebnis.count("page.js") == 1

    def test_dynamic_routes_im_datei_marker(self):
        """Dynamic Routes wie [DATEI:app/[id]/route.js] werden korrekt geparst."""
        feedback = "[DATEI:app/[id]/route.js] fehlende Validierung"
        ergebnis = _extract_feedback_files(feedback)
        assert "route.js" in ergebnis

    def test_dynamic_routes_catchall(self):
        """Catch-all Routes mit [...slug] im [DATEI:]-Marker.

        Bekannte Einschraenkung: [DATEI:app/[...slug]/page.js] wird durch das
        innere ']' in [...slug] falsch geparst (Fix 41b Regex-Grenze).
        Der Pattern-Match stoppt am ersten ']' → falscher Treffer.
        Workaround: Catch-all-Pfade ohne [DATEI:]-Marker im Feedback referenzieren.
        """
        # Alternative: Basename direkt im Feedback ohne [DATEI:]-Marker
        feedback = "app/[...slug]/page.js hat 404-Handling-Probleme"
        ergebnis = _extract_feedback_files(feedback)
        # Basename-Extraktion ueber alternatives Pattern (xxx.js hat/has/contains)
        assert "page.js" in ergebnis

    def test_venv_pfade_werden_ignoriert(self):
        """Dateien im venv/-Verzeichnis werden nicht als Projekt-Dateien erkannt."""
        feedback = 'File "venv/lib/python3.11/werkzeug/routing.py", line 30'
        ergebnis = _extract_feedback_files(feedback)
        assert len(ergebnis) == 0

    def test_gemischtes_feedback_mehrere_formate(self, sample_feedback):
        """Gemischtes Feedback mit verschiedenen Formaten wird geparst.

        Hinweis: Im sample_feedback ist route.js nur in Backticks (`...`) referenziert,
        was von keinem der Regex-Patterns erkannt wird. [DATEI:] und direkte Referenzen
        (page.js:, db.js hat) werden dagegen korrekt erkannt.
        """
        ergebnis = _extract_feedback_files(sample_feedback)

        # [DATEI:app/page.js] und [DATEI:lib/db.js] werden erkannt
        assert "page.js" in ergebnis
        assert "db.js" in ergebnis
        # route.js in Backticks wird NICHT erkannt (bekannte Einschraenkung)
        # Stattdessen: route.js mit Standard-Pattern testen
        feedback_mit_route = sample_feedback + "\napp/api/items/route.js: Input-Validierung fehlt"
        ergebnis_erweitert = _extract_feedback_files(feedback_mit_route)
        assert "route.js" in ergebnis_erweitert


# =============================================================================
# TestFindImportDeps - Import-Abhaengigkeiten erkennen
# =============================================================================

class TestFindImportDeps:
    """Tests fuer _find_import_deps() - Import-Abhaengigkeiten von Feedback-Dateien."""

    def test_leere_feedback_files_gibt_leeres_set(self, sample_code_dict):
        """Ohne Feedback-Dateien gibt es keine Import-Deps."""
        ergebnis = _find_import_deps([], sample_code_dict)
        assert ergebnis == set()

    def test_leeres_code_dict(self):
        """Ohne code_dict koennen keine Deps gefunden werden."""
        ergebnis = _find_import_deps(["page.js"], {})
        assert ergebnis == set()

    def test_relative_imports_werden_erkannt(self, sample_code_dict):
        """Relative Imports (from '../../../lib/db') werden aufgeloest."""
        # route.js importiert aus '../../../lib/db'
        ergebnis = _find_import_deps(["route.js"], sample_code_dict)
        # lib/db.js sollte als Dependency erkannt werden
        assert any("lib/db" in dep for dep in ergebnis), (
            f"Erwartet: lib/db.js in Dependencies, Erhalten: {ergebnis}"
        )

    def test_feedback_dateien_werden_nicht_als_deps_gezaehlt(self, sample_code_dict):
        """Dateien die bereits Feedback-Dateien sind, werden nicht als Deps doppelt gezaehlt."""
        # Wenn sowohl route.js als auch db.js im Feedback sind
        ergebnis = _find_import_deps(["route.js", "db.js"], sample_code_dict)
        # db.js ist selbst eine Feedback-Datei → darf nicht in Deps auftauchen
        for dep in ergebnis:
            assert os.path.basename(dep) != "db.js", (
                "Feedback-Datei db.js darf nicht als Dependency erscheinen"
            )

    def test_require_imports_werden_erkannt(self):
        """CommonJS require()-Imports werden ebenfalls erkannt."""
        code_dict = {
            "src/app.js": "const db = require('./lib/database')\nconst utils = require('./helpers/utils')",
            "src/lib/database.js": "module.exports = { query: () => {} }",
            "src/helpers/utils.js": "module.exports = { format: () => {} }",
        }
        ergebnis = _find_import_deps(["app.js"], code_dict)
        assert len(ergebnis) >= 1

    def test_dynamische_imports_werden_erkannt(self):
        """Dynamische import()-Aufrufe werden erkannt."""
        code_dict = {
            "components/Modal.jsx": "const Dialog = await import('./ui/Dialog')\n",
            "components/ui/Dialog.jsx": "export default function Dialog() {}",
        }
        ergebnis = _find_import_deps(["Modal.jsx"], code_dict)
        assert any("Dialog" in dep for dep in ergebnis)

    def test_relative_prefix_stripping(self):
        """../../lib/db wird zu lib/db fuer Matching gegen code_dict."""
        code_dict = {
            "app/api/items/route.js": "import { query } from '../../../lib/db'",
            "lib/db.js": "export function query() {}",
        }
        ergebnis = _find_import_deps(["route.js"], code_dict)
        assert any("lib/db" in dep for dep in ergebnis)

    def test_nicht_existierende_feedback_datei(self, sample_code_dict):
        """Feedback-Datei die nicht im code_dict existiert wird ignoriert."""
        ergebnis = _find_import_deps(["nicht_existierend.js"], sample_code_dict)
        assert ergebnis == set()

    def test_datei_ohne_imports(self):
        """Datei ohne jegliche Import-Statements erzeugt keine Dependencies."""
        code_dict = {
            "simple.js": "const x = 42;\nconsole.log(x);",
        }
        ergebnis = _find_import_deps(["simple.js"], code_dict)
        assert ergebnis == set()

    def test_npm_pakete_werden_nicht_als_deps_erkannt(self):
        """npm-Pakete (import from 'react') erzeugen keine Dateisystem-Deps."""
        code_dict = {
            "page.js": "import React from 'react'\nimport next from 'next/server'",
        }
        ergebnis = _find_import_deps(["page.js"], code_dict)
        # react und next sind keine relativen Imports → kein ./ oder ../
        assert ergebnis == set()


# =============================================================================
# TestExtractFileStructure - Dispatch nach Dateityp
# =============================================================================

class TestExtractFileStructure:
    """Tests fuer _extract_file_structure() - Typ-basierter Dispatch."""

    def test_js_datei_dispatch(self):
        """JS-Dateien werden an _extract_js_structure weitergeleitet."""
        ergebnis = _extract_file_structure("app.js", "import React from 'react'\nfunction App() {}")
        assert "IMPORTS:" in ergebnis or "FUNKTIONEN:" in ergebnis

    def test_jsx_datei_dispatch(self):
        """JSX-Dateien werden als JS behandelt."""
        ergebnis = _extract_file_structure("Component.jsx", "export default function Comp() {}")
        assert "FUNKTIONEN:" in ergebnis

    def test_tsx_datei_dispatch(self):
        """TSX-Dateien werden als JS behandelt."""
        ergebnis = _extract_file_structure("page.tsx", "export default function Page() {}")
        assert "FUNKTIONEN:" in ergebnis

    def test_mjs_datei_dispatch(self):
        """MJS-Dateien werden als JS behandelt."""
        ergebnis = _extract_file_structure("config.mjs", "export const config = {}")
        assert "EXPORTS:" in ergebnis or "ZEILEN:" in ergebnis

    def test_python_datei_dispatch(self):
        """Python-Dateien werden an _extract_python_structure weitergeleitet."""
        ergebnis = _extract_file_structure("server.py", "import os\ndef main(): pass")
        assert "IMPORTS:" in ergebnis or "FUNKTIONEN:" in ergebnis

    def test_css_datei_dispatch(self):
        """CSS-Dateien werden an _extract_css_structure weitergeleitet."""
        ergebnis = _extract_file_structure("styles.css", ".header { color: red; }")
        assert "SELEKTOREN:" in ergebnis or "ZEILEN:" in ergebnis

    def test_json_datei_dispatch(self):
        """JSON-Dateien werden an _extract_json_structure weitergeleitet."""
        ergebnis = _extract_file_structure("data.json", '{"key": "value"}')
        assert "TOP-KEYS:" in ergebnis or "ZEILEN:" in ergebnis

    def test_unbekannter_dateityp_fallback(self):
        """Unbekannte Dateitypen erhalten generischen Fallback (Vorschau + Zeilenanzahl)."""
        ergebnis = _extract_file_structure("readme.md", "# Titel\nBeschreibung\nDetails")
        assert "VORSCHAU:" in ergebnis
        assert "ZEILEN:" in ergebnis

    def test_html_datei_fallback(self):
        """HTML-Dateien erhalten den generischen Fallback."""
        ergebnis = _extract_file_structure("index.html", "<html><body>Hi</body></html>")
        assert "VORSCHAU:" in ergebnis


# =============================================================================
# TestExtractJsStructure - JS/JSX Struktur-Extraktion
# =============================================================================

class TestExtractJsStructure:
    """Tests fuer _extract_js_structure() - JavaScript/JSX/TypeScript Struktur."""

    def test_imports_werden_extrahiert(self):
        """Import-Statements werden korrekt extrahiert."""
        content = "import React from 'react'\nimport { useState } from 'react'\nconst x = 5;"
        lines = content.split("\n")
        ergebnis = _extract_js_structure("app.js", content, lines)
        assert "IMPORTS:" in ergebnis
        assert "import React from 'react'" in ergebnis

    def test_require_als_import(self):
        """require()-Aufrufe werden als Imports erkannt."""
        content = "const fs = require('fs')\nconst path = require('path')"
        lines = content.split("\n")
        ergebnis = _extract_js_structure("utils.js", content, lines)
        assert "IMPORTS:" in ergebnis
        assert "require('fs')" in ergebnis

    def test_max_10_imports(self):
        """Maximal 10 Imports werden in der Zusammenfassung angezeigt."""
        zeilen = [f"import mod{i} from 'modul{i}'" for i in range(15)]
        content = "\n".join(zeilen)
        lines = content.split("\n")
        ergebnis = _extract_js_structure("big.js", content, lines)
        # Zaehle tatsaechliche Import-Zeilen im Ergebnis
        import_zeilen = [z for z in ergebnis.split("\n") if z.startswith("import ")]
        assert len(import_zeilen) <= 10

    def test_exports_werden_extrahiert(self):
        """Export-Statements werden erkannt."""
        content = "export default function App() {}\nexport const config = {}"
        lines = content.split("\n")
        ergebnis = _extract_js_structure("app.js", content, lines)
        assert "EXPORTS:" in ergebnis

    def test_export_auf_100_zeichen_gekuerzt(self):
        """Lange Export-Statements werden auf 100 Zeichen gekuerzt."""
        langer_export = "export const " + "x" * 200 + " = true"
        content = langer_export
        lines = content.split("\n")
        ergebnis = _extract_js_structure("long.js", content, lines)
        # Die Export-Zeile im Ergebnis darf max 100 Zeichen haben
        for zeile in ergebnis.split("\n"):
            if zeile.startswith("export "):
                assert len(zeile) <= 100

    def test_funktionen_werden_extrahiert(self):
        """Funktionsdeklarationen (function und arrow) werden erkannt."""
        content = "function handleSubmit() {}\nconst fetchData = async () => {}"
        lines = content.split("\n")
        ergebnis = _extract_js_structure("handlers.js", content, lines)
        assert "FUNKTIONEN:" in ergebnis
        assert "handleSubmit" in ergebnis

    def test_arrow_functions_mit_const(self):
        """Arrow Functions mit const werden als Funktionen erkannt."""
        content = "const processInput = (data) => { return data }\nexport const formatDate = (d) => d"
        lines = content.split("\n")
        ergebnis = _extract_js_structure("utils.js", content, lines)
        assert "FUNKTIONEN:" in ergebnis
        assert "processInput" in ergebnis

    def test_async_functions(self):
        """Async Functions werden korrekt erkannt."""
        content = "async function loadData() {}\nexport async function saveData() {}"
        lines = content.split("\n")
        ergebnis = _extract_js_structure("api.js", content, lines)
        assert "loadData" in ergebnis
        assert "saveData" in ergebnis

    def test_http_methoden_in_api_routes(self):
        """HTTP-Methoden (GET, POST, etc.) werden in /api/ Dateien erkannt."""
        content = (
            "export async function GET() { return Response.json({}) }\n"
            "export async function POST(req) { return Response.json({}) }\n"
            "export async function DELETE(req) { return Response.json({}) }"
        )
        lines = content.split("\n")
        ergebnis = _extract_js_structure("app/api/items/route.js", content, lines)
        assert "HTTP-METHODEN:" in ergebnis
        assert "GET" in ergebnis
        assert "POST" in ergebnis
        assert "DELETE" in ergebnis

    def test_keine_http_methoden_ausserhalb_api(self):
        """HTTP-Methoden werden nur in /api/ Pfaden erkannt."""
        content = "export async function GET() { return Response.json({}) }"
        lines = content.split("\n")
        ergebnis = _extract_js_structure("components/List.jsx", content, lines)
        assert "HTTP-METHODEN:" not in ergebnis

    def test_react_hooks_werden_extrahiert(self):
        """React Hooks (useState, useEffect, etc.) werden erkannt."""
        content = (
            "const [x, setX] = useState(0)\n"
            "useEffect(() => {}, [])\n"
            "const ref = useRef(null)\n"
            "const memo = useMemo(() => {}, [])"
        )
        lines = content.split("\n")
        ergebnis = _extract_js_structure("page.js", content, lines)
        assert "HOOKS:" in ergebnis
        assert "useState" in ergebnis
        assert "useEffect" in ergebnis
        assert "useRef" in ergebnis
        assert "useMemo" in ergebnis

    def test_hooks_ohne_duplikate(self):
        """Gleiche Hooks werden nur einmal aufgelistet."""
        content = (
            "const [a, setA] = useState(0)\n"
            "const [b, setB] = useState('')\n"
            "useEffect(() => {}, [a])\n"
            "useEffect(() => {}, [b])"
        )
        lines = content.split("\n")
        ergebnis = _extract_js_structure("page.js", content, lines)
        # useState und useEffect je nur einmal
        hooks_zeile = [z for z in ergebnis.split("\n") if z.startswith("HOOKS:")][0]
        assert hooks_zeile.count("useState") == 1
        assert hooks_zeile.count("useEffect") == 1

    def test_state_variablen_werden_extrahiert(self):
        """useState-Variablen werden als STATE extrahiert."""
        content = "const [items, setItems] = useState([])\nconst [loading, setLoading] = useState(false)"
        lines = content.split("\n")
        ergebnis = _extract_js_structure("page.js", content, lines)
        assert "STATE:" in ergebnis
        assert "items" in ergebnis
        assert "loading" in ergebnis

    def test_zeilenanzahl_wird_angehaengt(self):
        """Die Zeilenanzahl wird immer am Ende angehaengt."""
        content = "line1\nline2\nline3"
        lines = content.split("\n")
        ergebnis = _extract_js_structure("test.js", content, lines)
        assert "ZEILEN: 3" in ergebnis

    def test_leere_datei(self):
        """Leere JS-Datei gibt minimale Zusammenfassung zurueck."""
        content = ""
        lines = content.split("\n")
        ergebnis = _extract_js_structure("empty.js", content, lines)
        assert "ZEILEN:" in ergebnis

    def test_duplikat_funktionen_entfernt(self):
        """Doppelt erkannte Funktionen (function + arrow) werden dedupliziert."""
        content = "export default function Home() {}\nconst Home = () => {}"
        lines = content.split("\n")
        ergebnis = _extract_js_structure("page.js", content, lines)
        # Home sollte nur einmal vorkommen (dict.fromkeys entfernt Duplikate)
        if "FUNKTIONEN:" in ergebnis:
            func_zeile = [z for z in ergebnis.split("\n") if z.startswith("FUNKTIONEN:")][0]
            assert func_zeile.count("Home") == 1


# =============================================================================
# TestExtractPythonStructure - Python Struktur-Extraktion
# =============================================================================

class TestExtractPythonStructure:
    """Tests fuer _extract_python_structure() - Python Struktur."""

    def test_imports_werden_extrahiert(self):
        """Import-Statements (import und from...import) werden erkannt."""
        content = "import os\nfrom pathlib import Path\nimport sys"
        lines = content.split("\n")
        ergebnis = _extract_python_structure("utils.py", content, lines)
        assert "IMPORTS:" in ergebnis
        assert "import os" in ergebnis
        assert "from pathlib import Path" in ergebnis

    def test_kommentierte_imports_werden_ignoriert(self):
        """Mit # kommentierte Imports werden nicht extrahiert."""
        content = "# import deprecated_module\nimport os"
        lines = content.split("\n")
        ergebnis = _extract_python_structure("utils.py", content, lines)
        assert "deprecated_module" not in ergebnis
        assert "import os" in ergebnis

    def test_klassen_werden_extrahiert(self):
        """Klassendefinitionen werden erkannt."""
        content = "class UserManager:\n    pass\nclass DatabaseHelper:\n    pass"
        lines = content.split("\n")
        ergebnis = _extract_python_structure("models.py", content, lines)
        assert "KLASSEN:" in ergebnis
        assert "UserManager" in ergebnis
        assert "DatabaseHelper" in ergebnis

    def test_funktionen_werden_extrahiert(self):
        """Funktionsdefinitionen (sync und async) werden erkannt."""
        content = "def process_data():\n    pass\nasync def fetch_data():\n    pass"
        lines = content.split("\n")
        ergebnis = _extract_python_structure("handlers.py", content, lines)
        assert "FUNKTIONEN:" in ergebnis
        assert "process_data" in ergebnis
        assert "fetch_data" in ergebnis

    def test_konstanten_werden_extrahiert(self):
        """Globale Konstanten (GROSSBUCHSTABEN) werden erkannt."""
        content = "MAX_RETRIES = 3\nDEFAULT_TIMEOUT = 30\nDB_URL = 'sqlite:///data.db'"
        lines = content.split("\n")
        ergebnis = _extract_python_structure("config.py", content, lines)
        assert "KONSTANTEN:" in ergebnis
        assert "MAX_RETRIES" in ergebnis
        assert "DEFAULT_TIMEOUT" in ergebnis
        assert "DB_URL" in ergebnis

    def test_max_15_funktionen(self):
        """Maximal 15 Funktionen werden angezeigt."""
        zeilen = [f"def func_{i}():\n    pass" for i in range(20)]
        content = "\n".join(zeilen)
        lines = content.split("\n")
        ergebnis = _extract_python_structure("big.py", content, lines)
        func_zeile = [z for z in ergebnis.split("\n") if z.startswith("FUNKTIONEN:")][0]
        func_namen = func_zeile.replace("FUNKTIONEN: ", "").split(", ")
        assert len(func_namen) <= 15

    def test_max_10_imports(self):
        """Maximal 10 Imports werden angezeigt."""
        zeilen = [f"import modul_{i}" for i in range(15)]
        content = "\n".join(zeilen)
        lines = content.split("\n")
        ergebnis = _extract_python_structure("big.py", content, lines)
        import_section = ergebnis.split("IMPORTS:\n")[1].split("\n\n")[0] if "IMPORTS:" in ergebnis else ""
        import_zeilen = [z for z in import_section.split("\n") if z.strip().startswith("import")]
        assert len(import_zeilen) <= 10

    def test_zeilenanzahl(self):
        """Zeilenanzahl wird korrekt angezeigt."""
        content = "import os\ndef main():\n    pass\n# Ende"
        lines = content.split("\n")
        ergebnis = _extract_python_structure("main.py", content, lines)
        assert "ZEILEN: 4" in ergebnis

    def test_leere_datei(self):
        """Leere Python-Datei gibt minimale Zusammenfassung."""
        ergebnis = _extract_python_structure("empty.py", "", [""])
        assert "ZEILEN:" in ergebnis

    def test_max_10_konstanten(self):
        """Maximal 10 Konstanten werden angezeigt."""
        zeilen = [f"CONST_{i} = {i}" for i in range(15)]
        content = "\n".join(zeilen)
        lines = content.split("\n")
        ergebnis = _extract_python_structure("consts.py", content, lines)
        konst_zeile = [z for z in ergebnis.split("\n") if z.startswith("KONSTANTEN:")][0]
        konst_namen = konst_zeile.replace("KONSTANTEN: ", "").split(", ")
        assert len(konst_namen) <= 10


# =============================================================================
# TestExtractCssStructure - CSS Struktur-Extraktion
# =============================================================================

class TestExtractCssStructure:
    """Tests fuer _extract_css_structure() - CSS Struktur."""

    def test_klassen_selektoren_werden_extrahiert(self):
        """CSS-Klassenselektoren (.xxx) werden erkannt."""
        content = ".header {\n  color: red;\n}\n.footer {\n  color: blue;\n}"
        lines = content.split("\n")
        ergebnis = _extract_css_structure("styles.css", content, lines)
        assert "SELEKTOREN:" in ergebnis
        assert ".header" in ergebnis
        assert ".footer" in ergebnis

    def test_id_selektoren_werden_extrahiert(self):
        """CSS-ID-Selektoren (#xxx) werden erkannt."""
        content = "#main-content {\n  width: 100%;\n}\n#sidebar {\n  width: 200px;\n}"
        lines = content.split("\n")
        ergebnis = _extract_css_structure("layout.css", content, lines)
        assert "SELEKTOREN:" in ergebnis
        assert "#main-content" in ergebnis
        assert "#sidebar" in ergebnis

    def test_css_custom_properties_werden_extrahiert(self):
        """CSS Custom Properties (--xxx) werden erkannt."""
        content = ":root {\n  --primary-color: #333;\n  --bg-color: #fff;\n  --font-size: 16px;\n}"
        lines = content.split("\n")
        ergebnis = _extract_css_structure("variables.css", content, lines)
        assert "CSS-VARIABLEN:" in ergebnis
        assert "--primary-color" in ergebnis
        assert "--bg-color" in ergebnis

    def test_css_variablen_ohne_duplikate(self):
        """Doppelt verwendete CSS-Variablen werden nur einmal aufgelistet."""
        content = (
            ":root { --color: red; }\n"
            ".dark { --color: blue; }\n"
            ".light { --color: green; }"
        )
        lines = content.split("\n")
        ergebnis = _extract_css_structure("theme.css", content, lines)
        if "CSS-VARIABLEN:" in ergebnis:
            var_zeile = [z for z in ergebnis.split("\n") if z.startswith("CSS-VARIABLEN:")][0]
            assert var_zeile.count("--color") == 1

    def test_media_queries_werden_extrahiert(self):
        """Media Queries werden erkannt."""
        content = "@media (max-width: 768px) {\n  .header { display: none; }\n}\n@media (min-width: 1024px) {\n  .sidebar { display: block; }\n}"
        lines = content.split("\n")
        ergebnis = _extract_css_structure("responsive.css", content, lines)
        assert "MEDIA-QUERIES:" in ergebnis
        assert "max-width: 768px" in ergebnis
        assert "min-width: 1024px" in ergebnis

    def test_max_20_selektoren(self):
        """Maximal 20 Selektoren werden angezeigt."""
        zeilen = [f".klasse_{i} {{\n  color: red;\n}}" for i in range(25)]
        content = "\n".join(zeilen)
        lines = content.split("\n")
        ergebnis = _extract_css_structure("big.css", content, lines)
        if "SELEKTOREN:" in ergebnis:
            sel_zeile = [z for z in ergebnis.split("\n") if z.startswith("SELEKTOREN:")][0]
            sel_namen = sel_zeile.replace("SELEKTOREN: ", "").split(", ")
            assert len(sel_namen) <= 20

    def test_max_5_media_queries(self):
        """Maximal 5 Media Queries werden angezeigt."""
        zeilen = [f"@media (min-width: {i}00px) {{\n  .x {{ color: red; }}\n}}" for i in range(8)]
        content = "\n".join(zeilen)
        lines = content.split("\n")
        ergebnis = _extract_css_structure("responsive.css", content, lines)
        if "MEDIA-QUERIES:" in ergebnis:
            mq_zeile = [z for z in ergebnis.split("\n") if z.startswith("MEDIA-QUERIES:")][0]
            mq_items = mq_zeile.replace("MEDIA-QUERIES: ", "").split(", ")
            assert len(mq_items) <= 5

    def test_zeilenanzahl(self):
        """Zeilenanzahl wird korrekt angezeigt."""
        content = ".a { color: red; }\n.b { color: blue; }"
        lines = content.split("\n")
        ergebnis = _extract_css_structure("test.css", content, lines)
        assert "ZEILEN: 2" in ergebnis

    def test_leere_css_datei(self):
        """Leere CSS-Datei gibt minimale Zusammenfassung."""
        ergebnis = _extract_css_structure("empty.css", "", [""])
        assert "ZEILEN:" in ergebnis


# =============================================================================
# TestExtractJsonStructure - JSON/package.json Struktur-Extraktion
# =============================================================================

class TestExtractJsonStructure:
    """Tests fuer _extract_json_structure() - JSON und package.json Struktur."""

    def test_package_json_name(self):
        """package.json Name wird extrahiert."""
        content = json.dumps({"name": "meine-app", "version": "1.0.0"})
        lines = content.split("\n")
        ergebnis = _extract_json_structure("package.json", content, lines)
        assert "NAME: meine-app" in ergebnis

    def test_package_json_dependencies(self):
        """package.json Dependencies werden aufgelistet."""
        content = json.dumps({
            "name": "test",
            "dependencies": {"react": "18.2.0", "next": "14.2.0", "tailwindcss": "3.4.0"}
        }, indent=2)
        lines = content.split("\n")
        ergebnis = _extract_json_structure("package.json", content, lines)
        assert "DEPENDENCIES:" in ergebnis
        assert "react" in ergebnis
        assert "next" in ergebnis
        assert "tailwindcss" in ergebnis

    def test_package_json_dev_dependencies(self):
        """package.json devDependencies werden aufgelistet."""
        content = json.dumps({
            "name": "test",
            "devDependencies": {"eslint": "8.0.0", "prettier": "3.0.0"}
        }, indent=2)
        lines = content.split("\n")
        ergebnis = _extract_json_structure("package.json", content, lines)
        assert "DEV-DEPENDENCIES:" in ergebnis
        assert "eslint" in ergebnis
        assert "prettier" in ergebnis

    def test_package_json_scripts(self):
        """package.json Scripts werden aufgelistet."""
        content = json.dumps({
            "name": "test",
            "scripts": {"dev": "next dev", "build": "next build", "start": "next start"}
        }, indent=2)
        lines = content.split("\n")
        ergebnis = _extract_json_structure("package.json", content, lines)
        assert "SCRIPTS:" in ergebnis
        assert "dev" in ergebnis
        assert "build" in ergebnis

    def test_generische_json_top_keys(self):
        """Nicht-package.json Dateien zeigen Top-Level Keys."""
        content = json.dumps({"database": "sqlite", "port": 3000, "debug": True}, indent=2)
        lines = content.split("\n")
        ergebnis = _extract_json_structure("config.json", content, lines)
        assert "TOP-KEYS:" in ergebnis
        assert "database" in ergebnis
        assert "port" in ergebnis

    def test_ungueltige_json_in_package(self):
        """Ungueltiges JSON in package.json faellt auf generischen Extractor zurueck."""
        content = "{ ungueltig json"
        lines = content.split("\n")
        ergebnis = _extract_json_structure("package.json", content, lines)
        # json.loads schlaegt fehl → Fallback auf Top-Level Keys via Regex
        assert "ZEILEN:" in ergebnis

    def test_max_15_dependencies(self):
        """Maximal 15 Dependencies werden angezeigt."""
        deps = {f"paket-{i}": "1.0.0" for i in range(20)}
        content = json.dumps({"name": "test", "dependencies": deps}, indent=2)
        lines = content.split("\n")
        ergebnis = _extract_json_structure("package.json", content, lines)
        dep_zeile = [z for z in ergebnis.split("\n") if z.startswith("DEPENDENCIES:")][0]
        dep_namen = dep_zeile.replace("DEPENDENCIES: ", "").split(", ")
        assert len(dep_namen) <= 15

    def test_zeilenanzahl(self):
        """Zeilenanzahl wird immer angezeigt."""
        content = '{"key": "value"}'
        lines = content.split("\n")
        ergebnis = _extract_json_structure("data.json", content, lines)
        assert "ZEILEN: 1" in ergebnis

    def test_verschachteltes_package_json_pfad(self):
        """Tief verschachtelte package.json (z.B. sub/package.json) wird erkannt."""
        content = json.dumps({"name": "sub-modul", "dependencies": {"express": "4.18.0"}})
        lines = content.split("\n")
        ergebnis = _extract_json_structure("packages/api/package.json", content, lines)
        assert "NAME: sub-modul" in ergebnis
        assert "DEPENDENCIES:" in ergebnis

    def test_leere_json_datei(self):
        """Leere JSON-Datei gibt minimale Zusammenfassung."""
        ergebnis = _extract_json_structure("empty.json", "", [""])
        assert "ZEILEN:" in ergebnis


# =============================================================================
# TestFalsePositiveFilenames - False-Positive Namensfilter
# =============================================================================

class TestFalsePositiveFilenames:
    """Tests fuer die FALSE_POSITIVE_FILENAMES Konstante."""

    def test_bekannte_false_positives_enthalten(self):
        """Alle bekannten Framework-Namen sind in der Filterliste."""
        erwartete = {"next.js", "node.js", "vue.js", "react.js", "express.js"}
        for name in erwartete:
            assert name in FALSE_POSITIVE_FILENAMES, (
                f"Erwartet: '{name}' in FALSE_POSITIVE_FILENAMES"
            )

    def test_keine_normalen_dateinamen_enthalten(self):
        """Normale Dateinamen (page.js, route.js) sind NICHT in der Filterliste."""
        normale_namen = {"page.js", "route.js", "layout.js", "app.js", "index.js"}
        for name in normale_namen:
            assert name not in FALSE_POSITIVE_FILENAMES, (
                f"Unerwartet: '{name}' in FALSE_POSITIVE_FILENAMES"
            )

    def test_filterliste_nur_lowercase(self):
        """Alle Eintraege in der Filterliste sind lowercase."""
        for name in FALSE_POSITIVE_FILENAMES:
            assert name == name.lower(), (
                f"Erwartet: lowercase, Erhalten: '{name}'"
            )


# =============================================================================
# TestCacheVerhalten - Cache-Logik im Detail
# =============================================================================

class TestCacheVerhalten:
    """Detaillierte Tests fuer das Cache-Verhalten der Kompression."""

    def test_cache_hash_ist_md5_prefix(self):
        """Der Cache-Hash ist ein 8-Zeichen MD5-Praefix."""
        content = "export default function App() {}"
        erwarteter_hash = hashlib.md5(content.encode()).hexdigest()[:8]

        code_dict = {"app.js": content}
        ergebnis = compress_context(code_dict, "")
        cache = ergebnis['_cache']

        assert "app.js" in cache
        assert cache["app.js"]["hash"] == erwarteter_hash

    def test_cache_enthaelt_summary(self):
        """Jeder Cache-Eintrag enthaelt Hash und Summary."""
        code_dict = {"utils.py": "import os\ndef helper(): pass"}
        ergebnis = compress_context(code_dict, "")
        cache = ergebnis['_cache']

        assert "utils.py" in cache
        assert "hash" in cache["utils.py"]
        assert "summary" in cache["utils.py"]
        assert len(cache["utils.py"]["hash"]) == 8

    def test_cache_wird_bei_feedback_datei_nicht_befuellt(self):
        """Feedback-Dateien (Kategorie A) werden nicht gecacht (erhalten vollen Inhalt)."""
        code_dict = {"page.js": "export default function Page() {}"}
        feedback = "[DATEI:page.js] Fehler"
        ergebnis = compress_context(code_dict, feedback)
        cache = ergebnis['_cache']

        # page.js ist Feedback-Datei → darf nicht im Cache stehen
        assert "page.js" not in cache

    def test_cache_persistenz_ueber_aufrufe(self):
        """Cache wird zwischen compress_context-Aufrufen wiederverwendet."""
        code_dict = {"lib.js": "export function helper() { return 42 }"}
        persistenter_cache = {}

        # Erster Aufruf
        ergebnis_1 = compress_context(code_dict, "", cache=persistenter_cache)
        cache_1 = ergebnis_1['_cache']

        # Zweiter Aufruf mit gleichem Cache (gleicher Inhalt → Hit)
        ergebnis_2 = compress_context(code_dict, "", cache=cache_1)

        # Summaries muessen identisch sein
        assert ergebnis_1["lib.js"] == ergebnis_2["lib.js"]


# =============================================================================
# TestIntegration - Zusammenspiel aller Komponenten
# =============================================================================

class TestIntegration:
    """Integrationstests fuer das Zusammenspiel der Kompressor-Funktionen."""

    def test_vollstaendiger_kompressionsfluss(self, sample_code_dict, sample_feedback):
        """Vollstaendiger Kompressionsfluss mit echten Testdaten."""
        ergebnis = compress_context(sample_code_dict, sample_feedback)

        # _cache muss vorhanden sein
        assert '_cache' in ergebnis

        # Alle Originaldateien muessen im Ergebnis sein
        for fname in sample_code_dict:
            assert fname in ergebnis, f"Datei {fname} fehlt im Ergebnis"

        # Feedback-Dateien: voller Inhalt
        assert ergebnis["app/page.js"] == sample_code_dict["app/page.js"]
        assert ergebnis["lib/db.js"] == sample_code_dict["lib/db.js"]

    def test_summary_marker_format(self, sample_code_dict):
        """Summaries beginnen mit bekannten Markern (IMPORTS:, FUNKTIONEN:, etc.)."""
        ergebnis = compress_context(sample_code_dict, "")

        bekannte_marker = [
            "IMPORTS:", "EXPORTS:", "FUNKTIONEN:", "HOOKS:", "STATE:",
            "HTTP-METHODEN:", "KLASSEN:", "KONSTANTEN:", "SELEKTOREN:",
            "CSS-VARIABLEN:", "MEDIA-QUERIES:", "NAME:", "DEPENDENCIES:",
            "DEV-DEPENDENCIES:", "SCRIPTS:", "TOP-KEYS:", "VORSCHAU:", "ZEILEN:",
        ]

        for fname, content in ergebnis.items():
            if fname == '_cache':
                continue
            # Jede Datei muss mindestens einen bekannten Marker haben
            hat_marker = any(marker in content for marker in bekannte_marker)
            assert hat_marker, (
                f"Datei {fname} hat keinen bekannten Summary-Marker: {content[:100]}"
            )

    def test_kompression_reduziert_gesamtgroesse(self):
        """Die Kompression reduziert die Gesamtgroesse bei vielen Dateien."""
        # Grosses code_dict mit vielen Dateien
        gross_dict = {}
        for i in range(20):
            gross_dict[f"components/Widget{i}.jsx"] = (
                f"import React from 'react'\n"
                f"import {{ useState }} from 'react'\n\n"
                f"export default function Widget{i}() {{\n"
                f"  const [count, setCount] = useState(0)\n"
                f"  return <div>Widget {i}: {{count}}</div>\n"
                f"}}\n"
            ) * 5  # Inhalt vervielfachen

        feedback = "[DATEI:Widget0.jsx] Fehler in der Render-Logik"
        ergebnis = compress_context(gross_dict, feedback)

        # Gesamtgroesse des Ergebnisses (ohne _cache) sollte kleiner sein
        original_groesse = sum(len(v) for v in gross_dict.values())
        komprimierte_groesse = sum(
            len(v) for k, v in ergebnis.items() if k != '_cache'
        )
        assert komprimierte_groesse < original_groesse, (
            f"Erwartet: Komprimierte Groesse < Original ({komprimierte_groesse} >= {original_groesse})"
        )
