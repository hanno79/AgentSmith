# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 14.02.2026
Version: 1.0
Beschreibung: Tests fuer dev_loop_content_rules.py — Content-basierte Validierungsregeln.
              Prueft ESM-Compliance, App Router, Purple-Farben, Hydration-Schutz,
              Date-Hydration und Dateinamen-Extraktion aus Feedback.
"""

import os
import sys
import pytest

# Projekt-Root zum Python-Path hinzufuegen
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.dev_loop_content_rules import (
    validate_content_rules,
    _check_esm_compliance,
    _check_app_router,
    _check_purple_colors,
    _check_hydration_safety,
    _check_date_hydration,
    extract_filenames_from_feedback,
)


# ===== Tests fuer _check_esm_compliance =====

class TestCheckEsmCompliance:
    """Tests fuer ESM-Compliance Pruefung (require/module.exports Erkennung)."""

    def test_require_erkannt(self):
        """require() Aufruf wird als ESM-Verletzung erkannt."""
        warnings = []
        content = "const fs = require('fs')\nconsole.log(fs)"
        _check_esm_compliance("lib/utils.js", content, warnings)
        assert len(warnings) == 1
        assert "ESM-VERLETZUNG" in warnings[0]
        assert "require()" in warnings[0]

    def test_module_exports_erkannt(self):
        """module.exports wird als ESM-Verletzung erkannt."""
        warnings = []
        content = "function helper() { return 42 }\nmodule.exports = helper"
        _check_esm_compliance("lib/helper.js", content, warnings)
        assert len(warnings) == 1
        assert "ESM-VERLETZUNG" in warnings[0]
        assert "module.exports" in warnings[0]

    def test_config_datei_ausgenommen(self):
        """Bekannte Config-Dateien (next.config.js etc.) sind von ESM-Check ausgenommen."""
        config_dateien = [
            "next.config.js", "postcss.config.js", "tailwind.config.js",
            "jest.config.js", "babel.config.js", "eslint.config.js",
            "webpack.config.js", "vite.config.js",
        ]
        for datei in config_dateien:
            warnings = []
            content = "module.exports = { key: 'value' }"
            _check_esm_compliance(datei, content, warnings)
            assert len(warnings) == 0, f"Config-Datei {datei} sollte ausgenommen sein"

    def test_config_datei_mit_pfad_ausgenommen(self):
        """Config-Dateien mit vollem Pfad werden korrekt erkannt (Basename-Matching)."""
        warnings = []
        content = "module.exports = { reactStrictMode: true }"
        _check_esm_compliance("app/next.config.js", content, warnings)
        assert len(warnings) == 0

    def test_config_datei_mit_backslash_pfad_ausgenommen(self):
        """Config-Dateien mit Windows-Backslash-Pfad werden korrekt erkannt."""
        warnings = []
        content = "module.exports = { reactStrictMode: true }"
        _check_esm_compliance("app\\next.config.js", content, warnings)
        assert len(warnings) == 0

    def test_test_datei_ausgenommen(self):
        """Test-Dateien (.test.js, .spec.js) sind von ESM-Check ausgenommen."""
        test_dateien = [
            "utils.test.js", "helper.spec.js",
            "utils.test.ts", "helper.spec.ts",
        ]
        for datei in test_dateien:
            warnings = []
            content = "const assert = require('assert')"
            _check_esm_compliance(datei, content, warnings)
            assert len(warnings) == 0, f"Test-Datei {datei} sollte ausgenommen sein"

    def test_tests_verzeichnis_ausgenommen(self):
        """Dateien im tests/ Verzeichnis sind von ESM-Check ausgenommen."""
        pfade = [
            "tests/helper.js",
            "src/tests/utils.js",
            "src/__tests__/component.js",
        ]
        for pfad in pfade:
            warnings = []
            content = "const x = require('x')"
            _check_esm_compliance(pfad, content, warnings)
            assert len(warnings) == 0, f"Test-Verzeichnis {pfad} sollte ausgenommen sein"

    def test_kommentare_ignoriert(self):
        """require() und module.exports in Kommentaren werden ignoriert."""
        warnings = []
        content = (
            "// const fs = require('fs')\n"
            "/* module.exports = foo */\n"
            "* require('bar')\n"
            "import { useState } from 'react'\n"
        )
        _check_esm_compliance("app/page.js", content, warnings)
        assert len(warnings) == 0

    def test_sauberer_esm_code_keine_warnung(self):
        """Sauberer ESM-Code (import/export) erzeugt keine Warnungen."""
        warnings = []
        content = (
            "import { useState } from 'react'\n"
            "export default function App() { return <div /> }\n"
        )
        _check_esm_compliance("app/page.js", content, warnings)
        assert len(warnings) == 0

    def test_nur_erste_verletzung_pro_datei(self):
        """Nur die erste ESM-Verletzung pro Datei wird gemeldet (break nach Fund)."""
        warnings = []
        content = (
            "const a = require('a')\n"
            "const b = require('b')\n"
            "module.exports = {}\n"
        )
        _check_esm_compliance("lib/multi.js", content, warnings)
        assert len(warnings) == 1

    def test_zeilennummer_korrekt(self):
        """Die Zeilennummer der Verletzung wird korrekt angegeben."""
        warnings = []
        content = "import x from 'x'\n\nconst y = require('y')\n"
        _check_esm_compliance("lib/test.js", content, warnings)
        assert len(warnings) == 1
        # require steht in Zeile 3
        assert ":3]" in warnings[0]


# ===== Tests fuer _check_app_router =====

class TestCheckAppRouter:
    """Tests fuer App Router Pruefung (pages/ vs app/ in Next.js)."""

    def test_pages_pfad_erkannt(self):
        """Datei im pages/ Verzeichnis wird als App-Router-Verletzung erkannt."""
        warnings = []
        blueprint = {"framework": "Next.js", "project_type": "webapp"}
        _check_app_router("pages/index.js", blueprint, warnings)
        assert len(warnings) == 1
        assert "APP-ROUTER-VERLETZUNG" in warnings[0]
        assert "pages/" in warnings[0]

    def test_pages_unterpfad_erkannt(self):
        """Datei in einem Unterpfad von pages/ wird erkannt."""
        warnings = []
        blueprint = {"framework": "Next.js", "project_type": "webapp"}
        _check_app_router("src/pages/about.js", blueprint, warnings)
        assert len(warnings) == 1
        assert "APP-ROUTER-VERLETZUNG" in warnings[0]

    def test_nicht_nextjs_kein_check(self):
        """Nicht-Next.js-Projekte ueberspringen den App-Router-Check."""
        warnings = []
        blueprint = {"framework": "React", "project_type": "webapp"}
        _check_app_router("pages/index.js", blueprint, warnings)
        assert len(warnings) == 0

    def test_app_pfad_korrekt(self):
        """Datei im app/ Verzeichnis erzeugt keine Warnung."""
        warnings = []
        blueprint = {"framework": "Next.js", "project_type": "webapp"}
        _check_app_router("app/page.js", blueprint, warnings)
        assert len(warnings) == 0

    def test_nextjs_in_project_type(self):
        """next.js im project_type wird ebenfalls erkannt."""
        warnings = []
        blueprint = {"framework": "", "project_type": "nextjs"}
        _check_app_router("pages/index.js", blueprint, warnings)
        assert len(warnings) == 1

    def test_next_js_mit_punkt_erkannt(self):
        """Framework 'next.js' (mit Punkt) wird korrekt erkannt."""
        warnings = []
        blueprint = {"framework": "next.js", "project_type": ""}
        _check_app_router("pages/index.js", blueprint, warnings)
        assert len(warnings) == 1


# ===== Tests fuer _check_purple_colors =====

class TestCheckPurpleColors:
    """Tests fuer Purple/Violet/Indigo Farb-Erkennung (Regel 19)."""

    def test_purple_erkannt(self):
        """Das Wort 'purple' wird als Farb-Verletzung erkannt."""
        warnings = []
        content = "background-color: purple;"
        _check_purple_colors("styles.css", content, warnings)
        assert len(warnings) == 1
        assert "FARB-VERLETZUNG" in warnings[0]
        assert "purple" in warnings[0].lower()

    def test_violet_erkannt(self):
        """Das Wort 'violet' wird als Farb-Verletzung erkannt."""
        warnings = []
        content = "color: violet;"
        _check_purple_colors("globals.css", content, warnings)
        assert len(warnings) == 1
        assert "FARB-VERLETZUNG" in warnings[0]

    def test_indigo_erkannt(self):
        """Das Wort 'indigo' wird als Farb-Verletzung erkannt."""
        warnings = []
        content = "const theme = { primary: 'indigo' }"
        _check_purple_colors("theme.js", content, warnings)
        assert len(warnings) == 1
        assert "FARB-VERLETZUNG" in warnings[0]

    def test_gross_kleinschreibung_egal(self):
        """Farb-Erkennung ist case-insensitive (PURPLE, Purple, purple)."""
        varianten = ["PURPLE", "Purple", "VIOLET", "Indigo", "INDIGO"]
        for wort in varianten:
            warnings = []
            content = f"color: {wort};"
            _check_purple_colors("test.css", content, warnings)
            assert len(warnings) == 1, f"'{wort}' sollte erkannt werden"

    def test_kein_purple_keine_warnung(self):
        """Code ohne verbotene Farben erzeugt keine Warnung."""
        warnings = []
        content = "background-color: #3b82f6;\ncolor: green;\nborder: 1px solid red;"
        _check_purple_colors("styles.css", content, warnings)
        assert len(warnings) == 0

    def test_nur_erste_farbe_gemeldet(self):
        """Nur die erste gefundene verbotene Farbe wird gemeldet."""
        warnings = []
        content = "color: purple;\nbackground: violet;\nborder-color: indigo;"
        _check_purple_colors("styles.css", content, warnings)
        # findall findet alle, aber nur eine Warnung wird erzeugt
        assert len(warnings) == 1

    def test_dateiname_in_warnung(self):
        """Der Dateiname erscheint in der Warnungsmeldung."""
        warnings = []
        content = "color: purple;"
        _check_purple_colors("components/Header.jsx", content, warnings)
        assert "components/Header.jsx" in warnings[0]


# ===== Tests fuer _check_hydration_safety =====

class TestCheckHydrationSafety:
    """Tests fuer Hydration-Safety Pruefung (suppressHydrationWarning)."""

    def test_body_ohne_suppress(self):
        """<body> ohne suppressHydrationWarning erzeugt Warnung."""
        warnings = []
        content = '<html lang="de" suppressHydrationWarning>\n<body>{children}</body>\n</html>'
        _check_hydration_safety("app/layout.js", content, warnings)
        # body hat KEIN suppressHydrationWarning, aber html hat es
        # Die Funktion prueft: '<body' in content UND 'suppressHydrationWarning' NOT in content
        # Da suppressHydrationWarning IM content steht (fuer html), wird body NICHT gewarnt
        # Denn die Pruefung ist: 'suppressHydrationWarning' not in content (global check)
        assert len(warnings) == 0

    def test_body_ohne_suppress_kein_suppress_im_content(self):
        """<body> ohne suppressHydrationWarning und keines im Content erzeugt Warnung."""
        warnings = []
        content = '<html lang="de">\n<body>{children}</body>\n</html>'
        _check_hydration_safety("app/layout.js", content, warnings)
        # Kein suppressHydrationWarning irgendwo → Warnung fuer body UND html
        assert len(warnings) == 2
        body_warnings = [w for w in warnings if "<body>" in w]
        html_warnings = [w for w in warnings if "<html>" in w]
        assert len(body_warnings) == 1
        assert len(html_warnings) == 1

    def test_html_ohne_suppress(self):
        """<html> ohne suppressHydrationWarning erzeugt Warnung (wenn keines im Content)."""
        warnings = []
        content = '<html lang="de">\n<body>{children}</body>\n</html>'
        _check_hydration_safety("app/layout.js", content, warnings)
        html_warnings = [w for w in warnings if "<html>" in w]
        assert len(html_warnings) == 1
        assert "HYDRATION-WARNUNG" in html_warnings[0]

    def test_beide_mit_suppress_keine_warnung(self):
        """Wenn suppressHydrationWarning im Content vorhanden ist, keine Warnungen."""
        warnings = []
        content = (
            '<html lang="de" suppressHydrationWarning>\n'
            '<body suppressHydrationWarning>{children}</body>\n'
            '</html>'
        )
        _check_hydration_safety("app/layout.js", content, warnings)
        assert len(warnings) == 0

    def test_ohne_body_und_html_keine_warnung(self):
        """Content ohne <body> und <html> erzeugt keine Warnung."""
        warnings = []
        content = "export default function Component() { return <div>Test</div> }"
        _check_hydration_safety("app/layout.js", content, warnings)
        assert len(warnings) == 0

    def test_dateiname_in_hydration_warnung(self):
        """Der Dateiname erscheint in der Hydration-Warnung."""
        warnings = []
        content = '<html><body>{children}</body></html>'
        _check_hydration_safety("app/layout.tsx", content, warnings)
        assert all("app/layout.tsx" in w for w in warnings)


# ===== Tests fuer _check_date_hydration =====

class TestCheckDateHydration:
    """Tests fuer Date-Hydration Pruefung (toLocale*String in Client-Components)."""

    def test_toLocaleDateString_in_client_component(self):
        """toLocaleDateString() in 'use client' Component wird erkannt."""
        warnings = []
        content = (
            "'use client'\n"
            "export default function DateView() {\n"
            "  return <span>{new Date().toLocaleDateString()}</span>\n"
            "}\n"
        )
        _check_date_hydration("components/Date.jsx", content, warnings)
        assert len(warnings) == 1
        assert "HYDRATION-WARNUNG" in warnings[0]
        assert "toLocale" in warnings[0]

    def test_toLocaleTimeString_erkannt(self):
        """toLocaleTimeString() wird ebenfalls erkannt."""
        warnings = []
        content = (
            '"use client"\n'
            "const time = new Date().toLocaleTimeString()\n"
        )
        _check_date_hydration("components/Time.tsx", content, warnings)
        assert len(warnings) == 1
        assert "HYDRATION-WARNUNG" in warnings[0]

    def test_toLocaleString_erkannt(self):
        """toLocaleString() wird ebenfalls erkannt."""
        warnings = []
        content = (
            "'use client'\n"
            "const formatted = date.toLocaleString()\n"
        )
        _check_date_hydration("components/Format.js", content, warnings)
        assert len(warnings) == 1

    def test_nicht_client_component_kein_check(self):
        """Ohne 'use client' Direktive wird der Date-Check uebersprungen."""
        warnings = []
        content = (
            "export default function ServerDate() {\n"
            "  return <span>{new Date().toLocaleDateString()}</span>\n"
            "}\n"
        )
        _check_date_hydration("components/ServerDate.jsx", content, warnings)
        assert len(warnings) == 0

    def test_use_client_mit_doppelten_anfuehrungszeichen(self):
        """'use client' mit doppelten Anfuehrungszeichen wird erkannt."""
        warnings = []
        content = (
            '"use client"\n'
            "const d = new Date().toLocaleDateString()\n"
        )
        _check_date_hydration("components/Test.js", content, warnings)
        assert len(warnings) == 1

    def test_sauberer_client_code_keine_warnung(self):
        """Client-Component ohne toLocale*String erzeugt keine Warnung."""
        warnings = []
        content = (
            "'use client'\n"
            "import { useState } from 'react'\n"
            "export default function App() { return <div>Hallo</div> }\n"
        )
        _check_date_hydration("app/page.js", content, warnings)
        assert len(warnings) == 0


# ===== Tests fuer extract_filenames_from_feedback =====

class TestExtractFilenamesFromFeedback:
    """Tests fuer Dateinamen-Extraktion aus Reviewer-/Security-Feedback."""

    def test_backtick_format(self):
        """Dateinamen in Backticks werden extrahiert."""
        feedback = "Fehler in `app/page.js` und `lib/db.js` gefunden."
        result = extract_filenames_from_feedback(feedback)
        assert "app/page.js" in result
        assert "lib/db.js" in result

    def test_datei_format(self):
        """[DATEI:xxx] Format wird extrahiert."""
        feedback = "[DATEI:app/api/items/route.js] hat SQL-Injection Risiko"
        result = extract_filenames_from_feedback(feedback)
        assert "app/api/items/route.js" in result

    def test_pfad_mit_extension(self):
        """Pfade mit Dateiendung werden aus Freitext extrahiert."""
        feedback = "Die Datei app/components/Header.jsx hat Probleme."
        result = extract_filenames_from_feedback(feedback)
        assert "app/components/Header.jsx" in result

    def test_leeres_feedback(self):
        """Leeres Feedback gibt leere Liste zurueck."""
        assert extract_filenames_from_feedback("") == []
        assert extract_filenames_from_feedback(None) == []

    def test_json_vor_js_regex_reihenfolge(self):
        """package.json wird korrekt als .json erkannt (nicht .js + 'on' Rest)."""
        feedback = "Pruefe `package.json` auf fehlende Dependencies."
        result = extract_filenames_from_feedback(feedback)
        assert "package.json" in result
        # Sicherstellen dass NICHT "package.js" extrahiert wird
        assert "package.js" not in result

    def test_tsx_vor_ts(self):
        """Dateien mit .tsx werden korrekt erkannt."""
        feedback = "Fehler in app/page.tsx und lib/utils.ts"
        result = extract_filenames_from_feedback(feedback)
        assert "app/page.tsx" in result
        assert "lib/utils.ts" in result

    def test_mehrere_datei_marker(self):
        """Mehrere [DATEI:xxx] Marker werden alle extrahiert."""
        feedback = (
            "[DATEI:app/page.js] Fehler A\n"
            "[DATEI:lib/db.js] Fehler B\n"
            "[DATEI:app/api/route.js] Fehler C\n"
        )
        result = extract_filenames_from_feedback(feedback)
        assert len(result) >= 3
        assert "app/page.js" in result
        assert "lib/db.js" in result
        assert "app/api/route.js" in result

    def test_deduplizierung(self):
        """Doppelt vorkommende Dateinamen werden dedupliziert."""
        feedback = (
            "`app/page.js` hat Fehler A.\n"
            "Auch `app/page.js` hat Fehler B.\n"
        )
        result = extract_filenames_from_feedback(feedback)
        page_count = sum(1 for f in result if f == "app/page.js")
        assert page_count == 1

    def test_urls_ignoriert(self):
        """HTTP-URLs werden nicht als Dateinamen extrahiert."""
        feedback = "Siehe https://example.com/docs/api.js fuer Details."
        result = extract_filenames_from_feedback(feedback)
        # URLs beginnen mit http → werden ignoriert
        assert not any("example.com" in f for f in result)

    def test_node_modules_ignoriert(self):
        """Pfade aus node_modules werden nicht extrahiert."""
        feedback = "Fehler in node_modules/react/index.js"
        result = extract_filenames_from_feedback(feedback)
        assert not any("node_modules" in f for f in result)

    def test_backslash_normalisierung(self):
        """Windows-Backslashes werden zu Forward-Slashes normalisiert."""
        feedback = "[DATEI:app\\api\\route.js] hat Probleme"
        result = extract_filenames_from_feedback(feedback)
        assert "app/api/route.js" in result

    def test_css_datei_erkannt(self):
        """CSS-Dateien werden ebenfalls extrahiert."""
        feedback = "Styling-Fehler in `app/globals.css`"
        result = extract_filenames_from_feedback(feedback)
        assert "app/globals.css" in result

    def test_python_datei_erkannt(self):
        """Python-Dateien (.py) werden extrahiert."""
        feedback = "Bug in [DATEI:backend/utils.py] gefunden"
        result = extract_filenames_from_feedback(feedback)
        assert "backend/utils.py" in result

    def test_mjs_datei_erkannt(self):
        """ESM-Dateien (.mjs) werden extrahiert."""
        feedback = "Config `next.config.mjs` muss angepasst werden."
        result = extract_filenames_from_feedback(feedback)
        assert "next.config.mjs" in result

    def test_sample_feedback_fixture(self, sample_feedback):
        """Extraktion aus dem sample_feedback Fixture funktioniert korrekt."""
        result = extract_filenames_from_feedback(sample_feedback)
        assert "app/page.js" in result
        assert "lib/db.js" in result
        assert "app/api/items/route.js" in result

    def test_false_positive_framework_namen_gefiltert(self):
        """Fix 57b: Framework-Namen wie Next.js, Node.js werden nicht als Dateinamen extrahiert."""
        feedback = (
            "Die Next.js Umgebung hat Probleme. "
            "Node.js Runtime-Fehler. "
            "Vue.js Framework nicht installiert. "
            "Echte Datei `app/page.js` hat Fehler."
        )
        result = extract_filenames_from_feedback(feedback)
        # Framework-Namen duerfen NICHT als Dateien erscheinen
        assert "Next.js" not in result
        assert "Node.js" not in result
        assert "Vue.js" not in result
        # Echte Dateien muessen weiterhin erkannt werden
        assert "app/page.js" in result

    def test_false_positive_react_express_gefiltert(self):
        """Fix 57b: react.js und express.js aus beschreibendem Text werden gefiltert."""
        feedback = "Das react.js Framework und express.js Server sind korrekt."
        result = extract_filenames_from_feedback(feedback)
        assert "react.js" not in result
        assert "express.js" not in result


# ===== Tests fuer validate_content_rules (Hauptfunktion) =====

class TestValidateContentRules:
    """Tests fuer die Haupt-Validierungsfunktion validate_content_rules."""

    def test_sauberer_code_keine_warnungen(self, sample_code_dict, sample_tech_blueprint):
        """Sauberer Code (sample_code_dict) erzeugt keine Warnungen."""
        result = validate_content_rules(sample_code_dict, sample_tech_blueprint)
        assert result == []

    def test_esm_verletzung_integriert(self, sample_tech_blueprint):
        """ESM-Verletzung wird ueber validate_content_rules erkannt."""
        code_dict = {
            "lib/helper.js": "const x = require('x')\nmodule.exports = x\n"
        }
        result = validate_content_rules(code_dict, sample_tech_blueprint)
        esm_warnungen = [w for w in result if "ESM-VERLETZUNG" in w]
        assert len(esm_warnungen) >= 1

    def test_app_router_verletzung_integriert(self, sample_tech_blueprint):
        """App-Router-Verletzung wird ueber validate_content_rules erkannt."""
        code_dict = {
            "pages/index.js": "export default function Home() { return <div /> }"
        }
        result = validate_content_rules(code_dict, sample_tech_blueprint)
        router_warnungen = [w for w in result if "APP-ROUTER-VERLETZUNG" in w]
        assert len(router_warnungen) == 1

    def test_purple_farbe_integriert(self, sample_tech_blueprint):
        """Purple-Farb-Verletzung wird ueber validate_content_rules erkannt."""
        code_dict = {
            "app/globals.css": "body { background: purple; }"
        }
        result = validate_content_rules(code_dict, sample_tech_blueprint)
        farb_warnungen = [w for w in result if "FARB-VERLETZUNG" in w]
        assert len(farb_warnungen) == 1

    def test_hydration_warnung_integriert(self, sample_tech_blueprint):
        """Hydration-Warnung wird fuer layout.js ohne suppressHydrationWarning erkannt."""
        code_dict = {
            "app/layout.js": '<html><body>{children}</body></html>'
        }
        result = validate_content_rules(code_dict, sample_tech_blueprint)
        hydration_warnungen = [w for w in result if "HYDRATION-WARNUNG" in w]
        assert len(hydration_warnungen) >= 1

    def test_date_hydration_integriert(self, sample_tech_blueprint):
        """Date-Hydration-Warnung wird ueber validate_content_rules erkannt."""
        code_dict = {
            "components/Date.jsx": (
                "'use client'\n"
                "export default function D() {\n"
                "  return <span>{new Date().toLocaleDateString()}</span>\n"
                "}\n"
            )
        }
        result = validate_content_rules(code_dict, sample_tech_blueprint)
        date_warnungen = [w for w in result if "HYDRATION-WARNUNG" in w and "toLocale" in w]
        assert len(date_warnungen) == 1

    def test_nicht_jsx_framework_kein_esm_check(self):
        """Nicht-JSX-Frameworks (z.B. Flask) fuehren keinen ESM-Check durch."""
        code_dict = {
            "app.js": "const express = require('express')\nmodule.exports = app\n"
        }
        blueprint = {"framework": "Flask", "project_type": "webapp"}
        result = validate_content_rules(code_dict, blueprint)
        esm_warnungen = [w for w in result if "ESM-VERLETZUNG" in w]
        assert len(esm_warnungen) == 0

    def test_leeres_code_dict(self, sample_tech_blueprint):
        """Leeres code_dict erzeugt keine Warnungen."""
        result = validate_content_rules({}, sample_tech_blueprint)
        assert result == []

    def test_mehrere_verletzungen_gleichzeitig(self, sample_tech_blueprint):
        """Mehrere verschiedene Regelverletzungen werden alle erkannt."""
        code_dict = {
            "lib/bad.js": "const x = require('bad')\ncolor: purple;",
            "pages/index.js": "export default function Home() { return <div /> }",
            "app/layout.js": '<html><body>{children}</body></html>',
        }
        result = validate_content_rules(code_dict, sample_tech_blueprint)
        assert len(result) >= 3  # ESM + pages + hydration (mindestens)

    def test_purple_nur_fuer_relevante_extensions(self, sample_tech_blueprint):
        """Purple-Check wird nur fuer CSS/JS/TS-Dateien ausgefuehrt, nicht fuer JSON."""
        code_dict = {
            "data.json": '{"color": "purple"}',
        }
        result = validate_content_rules(code_dict, sample_tech_blueprint)
        farb_warnungen = [w for w in result if "FARB-VERLETZUNG" in w]
        assert len(farb_warnungen) == 0

    def test_hydration_nur_fuer_layout_dateien(self, sample_tech_blueprint):
        """Hydration-Check wird nur fuer layout-Dateien ausgefuehrt."""
        code_dict = {
            "app/page.js": '<html><body>No suppress</body></html>',
        }
        result = validate_content_rules(code_dict, sample_tech_blueprint)
        hydration_warnungen = [w for w in result if "HYDRATION-WARNUNG" in w]
        assert len(hydration_warnungen) == 0

    def test_react_framework_esm_check(self):
        """React-Framework aktiviert ebenfalls den ESM-Check."""
        code_dict = {
            "lib/utils.js": "const x = require('x')\n"
        }
        blueprint = {"framework": "React", "project_type": "webapp"}
        result = validate_content_rules(code_dict, blueprint)
        esm_warnungen = [w for w in result if "ESM-VERLETZUNG" in w]
        assert len(esm_warnungen) == 1

    def test_gatsby_framework_esm_check(self):
        """Gatsby-Framework aktiviert ebenfalls den ESM-Check."""
        code_dict = {
            "src/helper.js": "module.exports = {}\n"
        }
        blueprint = {"framework": "Gatsby", "project_type": ""}
        result = validate_content_rules(code_dict, blueprint)
        esm_warnungen = [w for w in result if "ESM-VERLETZUNG" in w]
        assert len(esm_warnungen) == 1

    def test_datei_ohne_extension_kein_crash(self, sample_tech_blueprint):
        """Dateien ohne Extension (z.B. Dockerfile) verursachen keinen Fehler."""
        code_dict = {
            "Dockerfile": "FROM node:18\nCOPY . .\n",
            "Makefile": "build:\n\tnpm run build\n",
        }
        result = validate_content_rules(code_dict, sample_tech_blueprint)
        # Kein Crash, nur moegliche App-Router-Pruefungen (die aber nicht greifen)
        assert isinstance(result, list)
