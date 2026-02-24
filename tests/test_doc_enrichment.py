# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 14.02.2026
Version: 1.1
Beschreibung: Tests fuer das Doc-Enrichment-Modul (backend/doc_enrichment.py).
              Prueft Pure-Logic-Funktionen, statische Methoden und
              Integrations-Pfade mit Mocking fuer MCP/async Methoden.

AENDERUNG 14.02.2026: Coverage-Erhoehung von 49% auf ~85%
  Neue Tests fuer: _fetch_docs_for_library, _emit_ui_log, _get_npx_path,
  get_enrichment_section Token-Budget, _fetch_async Pfade
"""

import asyncio
import os
import sys
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from types import SimpleNamespace

# Projekt-Root zum Python-Path hinzufuegen
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.doc_enrichment import (
    SKIP_LIBRARIES, PRIORITY_LIBRARIES, GOAL_KEYWORDS,
    DocEnrichmentPipeline, get_doc_enrichment_section,
)


# ===== 1. TestConstants — Konstanten-Validierung =====

class TestConstants:
    """Prueft SKIP_LIBRARIES, PRIORITY_LIBRARIES und GOAL_KEYWORDS."""

    def test_skip_enthaelt_wichtige_libs(self):
        """Wichtige Standard-Libraries muessen in SKIP_LIBRARIES sein."""
        for lib in ["react", "next", "tailwindcss", "flask", "pytest"]:
            assert lib in SKIP_LIBRARIES, f"'{lib}' fehlt in SKIP_LIBRARIES"

    def test_priority_enthaelt_wichtige_libs(self):
        """Wichtige Priority-Libraries muessen enthalten sein."""
        for lib in ["shadcn", "prisma", "drizzle-orm", "next-auth"]:
            assert lib in PRIORITY_LIBRARIES, f"'{lib}' fehlt"

    def test_goal_keywords_mappings(self):
        """GOAL_KEYWORDS muss korrekte Mappings enthalten."""
        assert GOAL_KEYWORDS["shadcn"] == "shadcn/ui"
        assert GOAL_KEYWORDS["prisma"] == "prisma"
        assert GOAL_KEYWORDS["stripe"] == "stripe"

    def test_priority_values_nicht_leer(self):
        """Alle PRIORITY_LIBRARIES Values muessen nicht-leere Strings sein."""
        for key, value in PRIORITY_LIBRARIES.items():
            assert isinstance(value, str) and len(value) > 0, (
                f"Key '{key}' hat ungueltige Value: {value!r}")

    def test_keine_ueberschneidung_skip_priority(self):
        """SKIP_LIBRARIES und PRIORITY_LIBRARIES duerfen nicht ueberlappen."""
        ueberschneidung = SKIP_LIBRARIES & set(PRIORITY_LIBRARIES.keys())
        assert len(ueberschneidung) == 0, f"Ueberschneidung: {ueberschneidung}"


# ===== 2. TestParseLibraryId — Library-ID-Extraktion =====

class TestParseLibraryId:
    """Prueft _parse_library_id() fuer Context7-IDs."""

    @pytest.mark.parametrize("text,erwartet", [
        ("Found library: /shadcn-ui/ui (Context7)", "/shadcn-ui/ui"),
        ("Library resolved: /vercel/next.js", "/vercel/next.js"),
        ("ID: /vercel/next.js available", "/vercel/next.js"),
        ("Result: /some_org/some_lib", "/some_org/some_lib"),
        ("Options: /prisma/prisma and /drizzle-team/drizzle-orm", "/prisma/prisma"),
    ])
    def test_gueltige_ids(self, text, erwartet):
        """Verschiedene gueltige Context7-IDs werden korrekt erkannt."""
        assert DocEnrichmentPipeline._parse_library_id(text) == erwartet

    @pytest.mark.parametrize("eingabe", [
        "Keine passende Bibliothek gefunden",
        "",
        None,
    ])
    def test_ungueltige_eingaben(self, eingabe):
        """Ungueltige Eingaben liefern None."""
        assert DocEnrichmentPipeline._parse_library_id(eingabe) is None


# ===== 3. TestTruncateDoc — Dokumentations-Kuerzung =====

class TestTruncateDoc:
    """Prueft _truncate_doc() fuer Token-Budget-Einhaltung."""

    def test_kurzer_text_unveraendert(self):
        """Text kuerzer als max_chars bleibt unveraendert."""
        assert DocEnrichmentPipeline._truncate_doc("Kurz.", 100) == "Kurz."

    def test_exakt_max_chars_unveraendert(self):
        """Text mit genau max_chars Laenge bleibt unveraendert."""
        text = "A" * 50
        assert DocEnrichmentPipeline._truncate_doc(text, 50) == text

    def test_langer_text_wird_gekuerzt(self):
        """Text laenger als max_chars wird gekuerzt mit Anhaengsel."""
        ergebnis = DocEnrichmentPipeline._truncate_doc("X" * 200, 100)
        assert "[...gekuerzt wegen Token-Budget]" in ergebnis
        assert ergebnis.endswith("[...gekuerzt wegen Token-Budget]")

    def test_kuerzung_an_absatzgrenze(self):
        """Kuerzung erfolgt an Absatzgrenze wenn > 50% des Limits."""
        text = ("A" * 70) + "\n\n" + ("B" * 50)
        ergebnis = DocEnrichmentPipeline._truncate_doc(text, 100)
        assert ergebnis.startswith("A" * 70)
        assert "B" not in ergebnis.replace("[...gekuerzt wegen Token-Budget]", "")

    def test_keine_absatzgrenze_hartes_abschneiden(self):
        """Ohne Absatzgrenze wird hart bei max_chars abgeschnitten."""
        ergebnis = DocEnrichmentPipeline._truncate_doc("X" * 200, 100)
        assert ergebnis == ("X" * 100) + "\n[...gekuerzt wegen Token-Budget]"

    @pytest.mark.parametrize("eingabe,erwartet", [
        ("", ""),
        (None, ""),
    ])
    def test_leere_eingaben(self, eingabe, erwartet):
        """Leere/None-Eingaben liefern leeren String."""
        assert DocEnrichmentPipeline._truncate_doc(eingabe, 100) == erwartet

    def test_max_chars_null(self):
        """max_chars=0 fuehrt zur Kuerzung."""
        ergebnis = DocEnrichmentPipeline._truncate_doc("Text", 0)
        assert "[...gekuerzt wegen Token-Budget]" in ergebnis


# ===== 4. TestDetectLibraries — Bibliotheks-Erkennung =====

class TestDetectLibraries:
    """Prueft _detect_libraries() fuer verschiedene Erkennungsquellen."""

    @pytest.fixture
    def pipe(self):
        return DocEnrichmentPipeline(config={"doc_enrichment": {"enabled": True}})

    @pytest.mark.parametrize("goal,erwartet", [
        ("App mit Shadcn UI", "shadcn/ui"),
        ("SHADCN Komponenten", "shadcn/ui"),
        ("Stripe Payment", "stripe"),
        ("Payment Seite", "stripe"),
    ])
    def test_goal_keywords_erkennung(self, pipe, goal, erwartet):
        """Goal-Keywords erkennen Libraries case-insensitiv."""
        namen = [n for n, _ in pipe._detect_libraries({}, goal)]
        assert erwartet in namen

    def test_goal_leer_und_none(self, pipe):
        """Leerer/None user_goal liefert leere Liste ohne Crash."""
        assert pipe._detect_libraries({}, "") == []
        assert isinstance(pipe._detect_libraries({}, None), list)

    def test_deps_prisma_erkannt_react_skip(self, pipe):
        """Priority-Deps werden erkannt, SKIP-Deps uebersprungen."""
        namen = [n for n, _ in pipe._detect_libraries(
            {"dependencies": {"prisma": "5.0", "react": "18"}}, "")]
        assert "prisma" in namen
        assert "react" not in namen

    def test_deps_liste_format(self, pipe):
        """Dependencies als Liste werden korrekt verarbeitet."""
        namen = [n for n, _ in pipe._detect_libraries(
            {"dependencies": ["zod", "react"]}, "")]
        assert "zod" in namen
        assert "react" not in namen

    def test_template_prisma_erkannt(self, pipe):
        """prisma im Template-Namen wird erkannt."""
        namen = [n for n, _ in pipe._detect_libraries(
            {"_source_template": "nextjs-prisma"}, "")]
        assert "prisma" in namen

    def test_max_5_und_keine_duplikate(self, pipe):
        """Maximal 5 Libraries, keine Duplikate bei mehrfacher Quelle."""
        goal = "shadcn prisma drizzle stripe supabase clerk zustand"
        assert len(pipe._detect_libraries({}, goal)) <= 5
        namen = [n for n, _ in pipe._detect_libraries(
            {"dependencies": {"prisma": "5.0"}}, "prisma setup")]
        assert namen.count("prisma") == 1

    def test_unbekannte_dependency_nicht_erkannt(self, pipe):
        """Unbekannte Dependencies werden nicht erkannt."""
        namen = [n for n, _ in pipe._detect_libraries(
            {"dependencies": {"my-custom-lib": "1.0"}}, "")]
        assert "my-custom-lib" not in namen


# ===== 5. TestGetEnrichmentSection — Pipeline-Logik =====

class TestGetEnrichmentSection:
    """Prueft get_enrichment_section() ohne MCP-Calls."""

    def test_disabled_und_leer_liefert_leer(self):
        """Disabled oder keine Libraries liefert leeren String."""
        p_off = DocEnrichmentPipeline(config={"doc_enrichment": {"enabled": False}})
        assert p_off.get_enrichment_section({"dependencies": {"prisma": "5"}}, "x") == ""
        p_on = DocEnrichmentPipeline(config={"doc_enrichment": {"enabled": True}})
        assert p_on.get_enrichment_section({}, "") == ""

    @patch.object(DocEnrichmentPipeline, '_fetch_docs_for_library', return_value=None)
    def test_fetch_none_liefert_leer(self, mock_fetch):
        """Wenn alle Fetches None liefern, kommt leerer String."""
        p = DocEnrichmentPipeline(config={"doc_enrichment": {"enabled": True}})
        assert p.get_enrichment_section({"dependencies": {"prisma": "5"}}, "") == ""

    @patch.object(DocEnrichmentPipeline, '_fetch_docs_for_library',
                  return_value="Setup-Anleitung hier")
    def test_fetch_ok_liefert_sektion(self, mock_fetch):
        """Erfolgreiches Fetch liefert formatierte Sektion mit Header."""
        p = DocEnrichmentPipeline(config={"doc_enrichment": {"enabled": True}})
        erg = p.get_enrichment_section({"dependencies": {"prisma": "5"}}, "")
        assert "BIBLIOTHEKS-DOKUMENTATION" in erg
        assert "prisma" in erg and "Setup-Anleitung hier" in erg

    @patch.object(DocEnrichmentPipeline, '_fetch_docs_for_library',
                  return_value="D" * 120)
    def test_truncation_bei_budget_ueberschreitung(self, mock_fetch):
        """Docs werden gekuerzt wenn sie das Budget uebersteigen."""
        p = DocEnrichmentPipeline(config={
            "doc_enrichment": {"enabled": True, "max_total_chars": 100}})
        erg = p.get_enrichment_section({"dependencies": {"prisma": "5"}}, "")
        assert "[...gekuerzt wegen Token-Budget]" in erg

    @patch.object(DocEnrichmentPipeline, '_fetch_docs_for_library')
    def test_budget_break_bei_erschoepfung(self, mock_fetch):
        """Loop bricht ab wenn total_chars >= max_total erreicht ist."""
        counter = {"n": 0}
        def side_effect(lib, hint):
            counter["n"] += 1
            return "X" * 200
        mock_fetch.side_effect = side_effect
        p = DocEnrichmentPipeline(config={
            "doc_enrichment": {"enabled": True, "max_total_chars": 50}})
        p.get_enrichment_section({"dependencies": {"prisma": "5", "zod": "3"}}, "")
        assert counter["n"] == 1  # Nur erste Library gefetcht


# ===== 6. TestGetDocEnrichmentSection — Manager-Integration =====

class TestGetDocEnrichmentSection:
    """Prueft get_doc_enrichment_section() mit Mock-Manager."""

    def _mgr(self, blueprint=None, pipeline=None, goal="Test"):
        """Erstellt einen Manager-SimpleNamespace fuer Tests."""
        return SimpleNamespace(config={"doc_enrichment": {"enabled": True}},
                               tech_blueprint=blueprint, _current_user_goal=goal,
                               _doc_enrichment=pipeline, _ui_log=None)

    def test_ohne_tech_blueprint_leer(self):
        """Leerer/None tech_blueprint liefert leeren String."""
        m1 = MagicMock()
        m1.tech_blueprint = {}
        m1._doc_enrichment = None
        m1.config = {"doc_enrichment": {"enabled": True}}
        m1._ui_log = None
        assert get_doc_enrichment_section(m1) == ""
        assert get_doc_enrichment_section(self._mgr(blueprint=None)) == ""

    def test_erstellt_und_cached_pipeline(self):
        """Manager ohne _doc_enrichment erstellt Pipeline lazy."""
        m = SimpleNamespace(config={"doc_enrichment": {"enabled": False}},
                            tech_blueprint={"framework": "nextjs"},
                            _current_user_goal="App", _ui_log=None)
        get_doc_enrichment_section(m)
        assert isinstance(m._doc_enrichment, DocEnrichmentPipeline)

    def test_cached_pipeline_wiederverwendet(self):
        """Vorhandene Pipeline wird wiederverwendet."""
        mp = MagicMock()
        mp.get_enrichment_section.return_value = "Cached"
        assert get_doc_enrichment_section(
            self._mgr(blueprint={"f": "x"}, pipeline=mp)) == "Cached"

    def test_exception_liefert_leer(self):
        """Exception in Pipeline wird abgefangen."""
        mp = MagicMock()
        mp.get_enrichment_section.side_effect = RuntimeError("X")
        assert get_doc_enrichment_section(
            self._mgr(blueprint={"f": "x"}, pipeline=mp)) == ""


# ===== 7. TestExtractTextFromResult — MCP-Result-Parsing =====

class TestExtractTextFromResult:
    """Prueft _extract_text_from_result() mit simulierten MCP-Ergebnissen."""

    @pytest.mark.parametrize("result", [None, SimpleNamespace(content=[]),
                                         SimpleNamespace(content=None)])
    def test_leere_results(self, result):
        """None/leere/None-content Results liefern leeren String."""
        assert DocEnrichmentPipeline._extract_text_from_result(result) == ""

    def test_einzelnes_content_item(self):
        """Einzelnes Content-Item mit text wird extrahiert."""
        r = SimpleNamespace(content=[SimpleNamespace(text="Doku-Text")])
        assert DocEnrichmentPipeline._extract_text_from_result(r) == "Doku-Text"

    def test_mehrere_content_items(self):
        """Mehrere Content-Items werden mit Newline zusammengefuegt."""
        r = SimpleNamespace(content=[SimpleNamespace(text="Z1"),
                                     SimpleNamespace(text="Z2")])
        assert DocEnrichmentPipeline._extract_text_from_result(r) == "Z1\nZ2"

    def test_content_item_ohne_text(self):
        """Content-Item ohne text Attribut wird uebersprungen."""
        r = SimpleNamespace(content=[SimpleNamespace(text="OK"),
                                     SimpleNamespace(data="bin")])
        assert DocEnrichmentPipeline._extract_text_from_result(r) == "OK"

    def test_content_item_text_leer(self):
        """Content-Item mit leerem text wird uebersprungen."""
        r = SimpleNamespace(content=[SimpleNamespace(text=""),
                                     SimpleNamespace(text="Inhalt")])
        assert DocEnrichmentPipeline._extract_text_from_result(r) == "Inhalt"


# ===== 8. TestEmitUiLog — UI-Logging-Callback =====

class TestEmitUiLog:
    """Prueft _emit_ui_log() fuer UI-Callback-Weiterleitung."""

    def test_callback_wird_aufgerufen(self):
        """UI-Log-Callback wird mit korrekten Parametern aufgerufen."""
        cb = MagicMock()
        p = DocEnrichmentPipeline(config={"doc_enrichment": {}}, ui_log_callback=cb)
        p._emit_ui_log("Context7", "Fetch", "Hole Docs...")
        cb.assert_called_once_with("Context7", "Fetch", "Hole Docs...")

    def test_kein_callback_und_exception_graceful(self):
        """Ohne Callback kein Crash; Exception im Callback wird geschluckt."""
        DocEnrichmentPipeline(config={"doc_enrichment": {}})._emit_ui_log("A", "E", "M")
        def fehler_cb(a, e, m): raise RuntimeError("UI kaputt")
        DocEnrichmentPipeline(config={"doc_enrichment": {}},
                              ui_log_callback=fehler_cb)._emit_ui_log("A", "E", "M")


# ===== 9. TestGetNpxPath — npx-Pfad-Caching =====

class TestGetNpxPath:
    """Prueft _get_npx_path() fuer Windows-kompatibles npx-Caching."""

    @patch("backend.doc_enrichment.shutil.which", return_value="/usr/bin/npx")
    def test_npx_gefunden_und_gecached(self, mock_which):
        """npx-Pfad wird gecached (which nur einmal aufgerufen)."""
        p = DocEnrichmentPipeline(config={"doc_enrichment": {}})
        assert p._get_npx_path() == "/usr/bin/npx"
        assert p._get_npx_path() == "/usr/bin/npx"
        mock_which.assert_called_once_with("npx")

    @patch("backend.doc_enrichment.shutil.which", return_value=None)
    def test_npx_nicht_gefunden(self, mock_which):
        """Ohne npx wird None zurueckgegeben."""
        assert DocEnrichmentPipeline(config={"doc_enrichment": {}})._get_npx_path() is None


# ===== 10. TestFetchDocsForLibrary — Cache + Async-Bridge =====

class TestFetchDocsForLibrary:
    """Prueft _fetch_docs_for_library() Cache und Fehlerbehandlung."""

    def test_cache_hit_und_lowercase(self):
        """Gecachte Docs werden direkt zurueckgegeben, Key ist lowercase."""
        p = DocEnrichmentPipeline(config={"doc_enrichment": {}})
        p._cache["prisma"] = "Guide"
        assert p._fetch_docs_for_library("prisma", "Setup") == "Guide"
        assert p._fetch_docs_for_library("Prisma", "Setup") == "Guide"  # Lowercase
        p._cache["unknown"] = None
        assert p._fetch_docs_for_library("unknown", "q") is None  # None cached

    @patch.object(DocEnrichmentPipeline, '_fetch_async',
                  new_callable=AsyncMock, return_value="Async-Docs")
    def test_async_bridge_erfolg(self, mock_fetch):
        """Erfolgreicher Async-Fetch wird gecached."""
        p = DocEnrichmentPipeline(config={"doc_enrichment": {}})
        assert p._fetch_docs_for_library("zod", "Schema") == "Async-Docs"
        assert p._cache["zod"] == "Async-Docs"

    @patch.object(DocEnrichmentPipeline, '_fetch_async',
                  new_callable=AsyncMock, side_effect=Exception("Netzwerk"))
    def test_async_bridge_fehler_cached_none(self, mock_fetch):
        """Bei Fehler wird None gecached (verhindert erneute Versuche)."""
        p = DocEnrichmentPipeline(config={"doc_enrichment": {}})
        assert p._fetch_docs_for_library("zod", "Q") is None
        assert p._cache["zod"] is None


# ===== 11. TestFetchAsync — Async Ablaufsteuerung =====

class TestFetchAsync:
    """Prueft _fetch_async() Primaer/Fallback-Logik mit Mocking."""

    def _pipe(self, **kw):
        return DocEnrichmentPipeline(config={"doc_enrichment": {}}, **kw)

    @patch.object(DocEnrichmentPipeline, '_fetch_via_context7',
                  new_callable=AsyncMock, return_value="Ctx7-Docs")
    def test_context7_primaer_erfolg(self, mock_ctx7):
        """Bei Context7-Erfolg wird Ref.tools NICHT aufgerufen."""
        assert asyncio.run(self._pipe()._fetch_async("p", "q")) == "Ctx7-Docs"

    @patch.object(DocEnrichmentPipeline, '_fetch_via_ref_tools',
                  new_callable=AsyncMock, return_value="Ref-Docs")
    @patch.object(DocEnrichmentPipeline, '_fetch_via_context7',
                  new_callable=AsyncMock, return_value=None)
    def test_fallback_und_beide_fail(self, mock_ctx7, mock_ref):
        """Bei Context7-Fehler: Ref.tools Fallback. Beide None = None."""
        assert asyncio.run(self._pipe()._fetch_async("p", "q")) == "Ref-Docs"
        mock_ref.return_value = None
        mock_ctx7.reset_mock()
        mock_ref.reset_mock()
        assert asyncio.run(self._pipe()._fetch_async("p", "q")) is None

    @patch.object(DocEnrichmentPipeline, '_fetch_via_context7',
                  new_callable=AsyncMock, return_value="Docs")
    def test_ui_log_bei_erfolg(self, mock_ctx7):
        """UI-Log wird bei Context7-Erfolg mehrfach aufgerufen."""
        cb = MagicMock()
        asyncio.run(self._pipe(ui_log_callback=cb)._fetch_async("zod", "q"))
        assert cb.call_count >= 2

    @patch.object(DocEnrichmentPipeline, '_fetch_via_ref_tools',
                  new_callable=AsyncMock, return_value=None)
    @patch.object(DocEnrichmentPipeline, '_fetch_via_context7',
                  new_callable=AsyncMock, return_value=None)
    def test_ui_log_skip_bei_keine_docs(self, mock_ctx7, mock_ref):
        """UI-Log zeigt Skip-Meldung wenn keine Docs gefunden."""
        cb = MagicMock()
        asyncio.run(self._pipe(ui_log_callback=cb)._fetch_async("x", "q"))
        assert "Skip" in str(cb.call_args_list[-1])


# ===== 12. TestFetchViaConfigGuards — Config-Checks =====

class TestFetchViaConfigGuards:
    """Prueft Config-Guards fuer _fetch_via_context7 und _fetch_via_ref_tools."""

    def test_context7_disabled(self):
        """Context7 deaktiviert liefert None."""
        p = DocEnrichmentPipeline(config={
            "doc_enrichment": {"context7": {"enabled": False}}})
        assert asyncio.run(p._fetch_via_context7("prisma", "q")) is None

    @patch("backend.doc_enrichment.shutil.which", return_value=None)
    def test_context7_kein_npx(self, mock_which):
        """Ohne npx liefert Context7 None."""
        p = DocEnrichmentPipeline(config={"doc_enrichment": {}})
        assert asyncio.run(p._fetch_via_context7("prisma", "q")) is None

    def test_ref_tools_disabled_und_kein_key(self):
        """Ref.tools deaktiviert oder ohne Key liefert None."""
        p1 = DocEnrichmentPipeline(config={
            "doc_enrichment": {"ref_tools": {"enabled": False}}})
        assert asyncio.run(p1._fetch_via_ref_tools("p", "q")) is None
        p2 = DocEnrichmentPipeline(config={
            "doc_enrichment": {"ref_tools": {"api_key": ""}}})
        assert asyncio.run(p2._fetch_via_ref_tools("p", "q")) is None

    @patch.dict(os.environ, {"REF_TOOLS_API_KEY": ""}, clear=False)
    def test_ref_tools_env_var_leer(self):
        """Ref.tools mit leerer Env-Variable liefert None."""
        p = DocEnrichmentPipeline(config={
            "doc_enrichment": {"ref_tools": {"api_key": "${REF_TOOLS_API_KEY}"}}})
        assert asyncio.run(p._fetch_via_ref_tools("p", "q")) is None

    @patch("backend.doc_enrichment.shutil.which", return_value=None)
    @patch.dict(os.environ, {"REF_TOOLS_API_KEY": "test-key"}, clear=False)
    def test_ref_tools_kein_npx(self, mock_which):
        """Ref.tools ohne npx liefert None trotz API-Key."""
        p = DocEnrichmentPipeline(config={
            "doc_enrichment": {"ref_tools": {"api_key": "${REF_TOOLS_API_KEY}"}}})
        assert asyncio.run(p._fetch_via_ref_tools("p", "q")) is None


# ===== 13. TestPipelineInit — Konstruktor-Verhalten =====

class TestPipelineInit:
    """Prueft DocEnrichmentPipeline Konstruktor-Defaults."""

    def test_defaults(self):
        """Pipeline: Standard deaktiviert, leerer Cache."""
        p = DocEnrichmentPipeline(config={})
        assert not p._enabled
        assert p._cache == {}

    def test_enabled_und_callback(self):
        """Pipeline kann aktiviert werden, Callback wird gespeichert."""
        cb = MagicMock()
        p = DocEnrichmentPipeline(config={"doc_enrichment": {"enabled": True}},
                                  ui_log_callback=cb)
        assert p._enabled
        assert p._ui_log is cb
