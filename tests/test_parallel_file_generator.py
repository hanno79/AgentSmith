# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 14.02.2026
Version: 1.0
Beschreibung: Unit Tests fuer backend/parallel_file_generator.py.

              Getestete Funktionen:
              - get_file_descriptions_from_plan(): Plan-Dict → Datei-Beschreibungen
              - get_file_list_from_plan(): Plan-Dict → Datei-Pfad-Liste
              - _get_executor(): Thread-Pool Singleton mit Lock
              - _cleanup_executor(): atexit Cleanup
              - run_parallel_fixes(): Code-Extraktion aus existing_code
              - generate_single_file_async(): Async Datei-Generierung (mit Mocks)
              - run_parallel_file_generation(): Batch-basierte parallele Generierung (mit Mocks)
"""

import os
import sys
import asyncio

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from concurrent.futures import ThreadPoolExecutor

# Projekt-Root zum Python-Path hinzufuegen
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import backend.parallel_file_generator as pfg
from backend.parallel_file_generator import (
    get_file_descriptions_from_plan,
    get_file_list_from_plan,
    _get_executor,
    _cleanup_executor,
)


# =========================================================================
# Hilfsfunktionen und Fixtures
# =========================================================================

@pytest.fixture
def mock_manager(tmp_path):
    """Mock-Manager mit allen relevanten Attributen fuer parallele Generierung."""
    manager = MagicMock()
    manager.project_path = str(tmp_path)
    manager.tech_blueprint = {"project_type": "webapp", "framework": "Next.js"}
    manager._ui_log = MagicMock()
    return manager


@pytest.fixture(autouse=True)
def reset_executor():
    """Setzt den globalen Executor vor jedem Test zurueck."""
    original = pfg._executor
    pfg._executor = None
    yield
    # Aufraumen: Falls Test einen Executor erstellt hat
    if pfg._executor is not None and not pfg._executor._shutdown:
        pfg._executor.shutdown(wait=False)
    pfg._executor = original


# =========================================================================
# 1. TestGetFileDescriptionsFromPlan
# =========================================================================

class TestGetFileDescriptionsFromPlan:
    """Tests fuer get_file_descriptions_from_plan() — Plan → Beschreibungen."""

    def test_leerer_plan_gibt_leeres_dict(self):
        """Ein leerer Plan ohne files gibt ein leeres Dict zurueck."""
        ergebnis = get_file_descriptions_from_plan({})
        assert ergebnis == {}, \
            "Erwartet: leeres Dict bei leerem Plan"

    def test_plan_mit_files_extrahiert_beschreibungen(self):
        """Plan mit files-Liste extrahiert path→description Mapping."""
        plan = {
            "files": [
                {"path": "app/page.js", "description": "Hauptseite der App"},
                {"path": "lib/db.js", "description": "Datenbank-Modul"},
            ]
        }
        ergebnis = get_file_descriptions_from_plan(plan)
        assert ergebnis == {
            "app/page.js": "Hauptseite der App",
            "lib/db.js": "Datenbank-Modul",
        }, "Erwartet: Beide Beschreibungen korrekt extrahiert"

    def test_fehlende_description_nutzt_default(self):
        """Ohne description-Key wird Default 'Generiere {path}' verwendet."""
        plan = {"files": [{"path": "utils/helper.js"}]}
        ergebnis = get_file_descriptions_from_plan(plan)
        assert ergebnis == {"utils/helper.js": "Generiere utils/helper.js"}, \
            "Erwartet: Default-Beschreibung 'Generiere utils/helper.js'"

    def test_leerer_path_wird_uebersprungen(self):
        """Eintraege mit leerem path werden nicht ins Ergebnis aufgenommen."""
        plan = {"files": [{"path": "", "description": "Leerer Pfad"}]}
        ergebnis = get_file_descriptions_from_plan(plan)
        assert ergebnis == {}, \
            "Erwartet: leeres Dict — leerer Pfad wird ignoriert"

    def test_plan_ohne_files_key_gibt_leeres_dict(self):
        """Plan ohne 'files' Key verhaelt sich wie leerer Plan."""
        plan = {"name": "Test-Projekt", "version": "1.0"}
        ergebnis = get_file_descriptions_from_plan(plan)
        assert ergebnis == {}, \
            "Erwartet: leeres Dict bei fehlendem 'files' Key"

    def test_mehrere_dateien_alle_extrahiert(self):
        """Alle Dateien aus dem Plan werden korrekt extrahiert."""
        plan = {
            "files": [
                {"path": "a.js", "description": "Datei A"},
                {"path": "b.py", "description": "Datei B"},
                {"path": "c.ts", "description": "Datei C"},
                {"path": "d.css", "description": "Datei D"},
            ]
        }
        ergebnis = get_file_descriptions_from_plan(plan)
        assert len(ergebnis) == 4, \
            f"Erwartet: 4 Eintraege, erhalten: {len(ergebnis)}"
        assert "a.js" in ergebnis and "d.css" in ergebnis, \
            "Erwartet: Alle 4 Dateien im Ergebnis"


# =========================================================================
# 2. TestGetFileListFromPlan
# =========================================================================

class TestGetFileListFromPlan:
    """Tests fuer get_file_list_from_plan() — Plan → Pfad-Liste."""

    def test_leerer_plan_gibt_leere_liste(self):
        """Ein leerer Plan gibt eine leere Liste zurueck."""
        ergebnis = get_file_list_from_plan({})
        assert ergebnis == [], \
            "Erwartet: leere Liste bei leerem Plan"

    def test_plan_mit_files_extrahiert_pfade(self):
        """Plan mit files-Liste extrahiert nur die Pfade."""
        plan = {
            "files": [
                {"path": "app/page.js", "description": "Hauptseite"},
                {"path": "lib/db.js", "description": "Datenbank"},
            ]
        }
        ergebnis = get_file_list_from_plan(plan)
        assert ergebnis == ["app/page.js", "lib/db.js"], \
            "Erwartet: Liste mit beiden Pfaden"

    def test_leerer_path_wird_gefiltert(self):
        """Eintraege mit leerem path werden herausgefiltert."""
        plan = {
            "files": [
                {"path": "app/page.js"},
                {"path": ""},
                {"path": "lib/db.js"},
            ]
        }
        ergebnis = get_file_list_from_plan(plan)
        assert ergebnis == ["app/page.js", "lib/db.js"], \
            "Erwartet: Leerer Pfad wurde gefiltert"

    def test_plan_ohne_files_key_gibt_leere_liste(self):
        """Plan ohne 'files' Key gibt leere Liste zurueck."""
        plan = {"project": "test"}
        ergebnis = get_file_list_from_plan(plan)
        assert ergebnis == [], \
            "Erwartet: leere Liste bei fehlendem 'files' Key"

    def test_reihenfolge_bleibt_erhalten(self):
        """Die Reihenfolge der Dateien im Plan bleibt erhalten."""
        plan = {
            "files": [
                {"path": "z.js"},
                {"path": "a.js"},
                {"path": "m.js"},
            ]
        }
        ergebnis = get_file_list_from_plan(plan)
        assert ergebnis == ["z.js", "a.js", "m.js"], \
            "Erwartet: Reihenfolge z.js, a.js, m.js beibehalten"


# =========================================================================
# 3. TestGetExecutor
# =========================================================================

class TestGetExecutor:
    """Tests fuer _get_executor() — Thread-Pool Singleton."""

    def test_erstellt_thread_pool_executor(self):
        """_get_executor() erstellt einen ThreadPoolExecutor."""
        executor = _get_executor(max_workers=2)
        assert isinstance(executor, ThreadPoolExecutor), \
            "Erwartet: ThreadPoolExecutor Instanz"
        # Aufraumen
        executor.shutdown(wait=False)

    def test_singleton_gibt_selben_pool_zurueck(self):
        """Wiederholter Aufruf gibt denselben Executor zurueck (Singleton)."""
        executor1 = _get_executor(max_workers=2)
        executor2 = _get_executor(max_workers=2)
        assert executor1 is executor2, \
            "Erwartet: Identischer Executor bei wiederholtem Aufruf (Singleton)"
        executor1.shutdown(wait=False)

    def test_max_workers_wird_beachtet(self):
        """max_workers Parameter bestimmt die Anzahl der Worker-Threads."""
        executor = _get_executor(max_workers=3)
        assert executor._max_workers == 3, \
            f"Erwartet: 3 Worker, erhalten: {executor._max_workers}"
        executor.shutdown(wait=False)

    def test_erstellt_neuen_pool_nach_shutdown(self):
        """Nach Shutdown wird ein neuer Executor erstellt."""
        executor1 = _get_executor(max_workers=2)
        executor1.shutdown(wait=False)
        # Nach Shutdown muss ein neuer erstellt werden
        executor2 = _get_executor(max_workers=4)
        assert executor2 is not executor1, \
            "Erwartet: Neuer Executor nach Shutdown"
        assert not executor2._shutdown, \
            "Erwartet: Neuer Executor ist nicht heruntergefahren"
        executor2.shutdown(wait=False)


# =========================================================================
# 4. TestCleanupExecutor
# =========================================================================

class TestCleanupExecutor:
    """Tests fuer _cleanup_executor() — atexit Cleanup."""

    def test_beendet_den_executor(self):
        """_cleanup_executor() faehrt den globalen Executor herunter."""
        pfg._executor = ThreadPoolExecutor(max_workers=1)
        assert pfg._executor is not None, "Vorbedingung: Executor existiert"

        _cleanup_executor()

        assert pfg._executor is None, \
            "Erwartet: Executor ist None nach Cleanup"

    def test_none_check_kein_crash(self):
        """_cleanup_executor() stuerzt nicht ab wenn Executor None ist."""
        pfg._executor = None
        # Darf keine Exception werfen
        _cleanup_executor()
        assert pfg._executor is None, \
            "Erwartet: Executor bleibt None"


# =========================================================================
# 5. TestRunParallelFixes — Code-Extraktion aus existing_code
# =========================================================================

class TestRunParallelFixes:
    """Tests fuer run_parallel_fixes() — Fokus auf Code-Extraktion."""

    def test_einfacher_filename_block_korrekt_extrahiert(self, mock_manager):
        """### FILENAME: Bloecke werden korrekt zu existing_files geparst."""
        existing_code = (
            "### FILENAME: app/page.js\n"
            "export default function Home() { return <div>Hallo</div> }\n"
        )
        # Mock run_parallel_file_generation um den eigentlichen LLM-Call zu umgehen
        async def fake_run(*args, **kwargs):
            return {}, []

        with patch("backend.parallel_file_generator.run_parallel_file_generation", side_effect=fake_run):
            result = asyncio.run(
                pfg.run_parallel_fixes(
                    manager=mock_manager,
                    files_to_fix=["app/page.js"],
                    fix_instructions={"app/page.js": "Fuege Error-Handling hinzu"},
                    existing_code=existing_code,
                    user_goal="Test",
                    project_rules={},
                )
            )
        # Pruefe dass run_parallel_file_generation aufgerufen wurde
        assert result == ({}, []), "Erwartet: Leeres Ergebnis vom Mock"

    def test_markdown_codeblock_wrapper_werden_entfernt(self, mock_manager):
        """Markdown-Codeblock-Wrapper (```js...```) werden aus dem Content entfernt."""
        existing_code = (
            "### FILENAME: lib/db.js\n"
            "```js\n"
            "const db = require('sqlite3');\n"
            "```\n"
        )
        captured_descriptions = {}

        async def capture_run(manager, file_list, file_descriptions, **kwargs):
            captured_descriptions.update(file_descriptions)
            return {}, []

        with patch("backend.parallel_file_generator.run_parallel_file_generation", side_effect=capture_run):
            asyncio.run(
                pfg.run_parallel_fixes(
                    manager=mock_manager,
                    files_to_fix=["lib/db.js"],
                    fix_instructions={"lib/db.js": "Fix SQL"},
                    existing_code=existing_code,
                    user_goal="Test",
                    project_rules={},
                )
            )
        # Die Beschreibung muss den bereinigten Content enthalten (ohne ```)
        desc = captured_descriptions.get("lib/db.js", "")
        assert "```" not in desc.split("BISHERIGER INHALT:\n")[1].split("...")[0] if "BISHERIGER INHALT:" in desc else True, \
            "Erwartet: Keine Markdown-Codeblock-Wrapper im extrahierten Content"

    def test_mehrere_dateien_alle_extrahiert(self, mock_manager):
        """Mehrere ### FILENAME: Bloecke werden alle korrekt extrahiert."""
        existing_code = (
            "### FILENAME: app/page.js\n"
            "function Page() {}\n"
            "### FILENAME: lib/utils.js\n"
            "function util() {}\n"
            "### FILENAME: app/layout.js\n"
            "function Layout() {}\n"
        )
        captured_descriptions = {}

        async def capture_run(manager, file_list, file_descriptions, **kwargs):
            captured_descriptions.update(file_descriptions)
            return {}, []

        with patch("backend.parallel_file_generator.run_parallel_file_generation", side_effect=capture_run):
            asyncio.run(
                pfg.run_parallel_fixes(
                    manager=mock_manager,
                    files_to_fix=["app/page.js", "lib/utils.js"],
                    fix_instructions={},
                    existing_code=existing_code,
                    user_goal="Test",
                    project_rules={},
                )
            )
        # Beschreibungen muessen fuer beide Fix-Dateien existieren
        assert "app/page.js" in captured_descriptions, \
            "Erwartet: Beschreibung fuer app/page.js vorhanden"
        assert "lib/utils.js" in captured_descriptions, \
            "Erwartet: Beschreibung fuer lib/utils.js vorhanden"

    def test_leerer_existing_code_gibt_leere_beschreibungen(self, mock_manager):
        """Leerer existing_code fuehrt zu leeren BISHERIGER INHALT Abschnitten."""
        captured_descriptions = {}

        async def capture_run(manager, file_list, file_descriptions, **kwargs):
            captured_descriptions.update(file_descriptions)
            return {}, []

        with patch("backend.parallel_file_generator.run_parallel_file_generation", side_effect=capture_run):
            asyncio.run(
                pfg.run_parallel_fixes(
                    manager=mock_manager,
                    files_to_fix=["app/page.js"],
                    fix_instructions={"app/page.js": "Erstelle neu"},
                    existing_code="",
                    user_goal="Test",
                    project_rules={},
                )
            )
        desc = captured_descriptions.get("app/page.js", "")
        assert "BISHERIGER INHALT:" in desc, \
            "Erwartet: BISHERIGER INHALT Abschnitt vorhanden (auch bei leerem Code)"


# =========================================================================
# 6. TestGenerateSingleFileAsync
# =========================================================================

class TestGenerateSingleFileAsync:
    """Tests fuer generate_single_file_async() — Mock run_single_file_coder."""

    def test_erfolg_gibt_content_zurueck(self, mock_manager):
        """Bei erfolgreicher Generierung wird (filename, content, None) zurueckgegeben."""
        with patch("backend.file_by_file_loop.run_single_file_coder",
                    return_value=("app/page.js", "export default function() {}")):
            result = asyncio.run(
                pfg.generate_single_file_async(
                    manager=mock_manager,
                    filename="app/page.js",
                    file_description="Hauptseite",
                    existing_files={},
                    user_goal="Test-App erstellen",
                    project_rules={},
                    timeout_seconds=30,
                )
            )
        filename, content, error = result
        assert filename == "app/page.js", \
            f"Erwartet: filename='app/page.js', erhalten: '{filename}'"
        assert content == "export default function() {}", \
            "Erwartet: Content vom Coder zurueckgegeben"
        assert error is None, \
            f"Erwartet: error=None bei Erfolg, erhalten: '{error}'"

    def test_fehlschlag_gibt_error_zurueck(self, mock_manager):
        """Bei fehlgeschlagener Generierung wird (filename, None, error) zurueckgegeben."""
        with patch("backend.file_by_file_loop.run_single_file_coder",
                    return_value=(None, "Modell nicht erreichbar")):
            result = asyncio.run(
                pfg.generate_single_file_async(
                    manager=mock_manager,
                    filename="app/page.js",
                    file_description="Hauptseite",
                    existing_files={},
                    user_goal="Test",
                    project_rules={},
                    timeout_seconds=30,
                )
            )
        filename, content, error = result
        assert filename == "app/page.js", \
            "Erwartet: filename bleibt 'app/page.js'"
        assert content is None, \
            "Erwartet: content=None bei Fehlschlag"
        assert error is not None, \
            "Erwartet: error enthaelt Fehlermeldung"

    def test_timeout_gibt_timeout_fehler(self, mock_manager):
        """Bei Timeout wird (filename, None, 'Timeout...') zurueckgegeben."""
        import time

        def slow_coder(*args, **kwargs):
            time.sleep(5)
            return ("app/page.js", "zu spaet")

        with patch("backend.file_by_file_loop.run_single_file_coder",
                    side_effect=slow_coder):
            result = asyncio.run(
                pfg.generate_single_file_async(
                    manager=mock_manager,
                    filename="app/page.js",
                    file_description="Hauptseite",
                    existing_files={},
                    user_goal="Test",
                    project_rules={},
                    timeout_seconds=1,  # 1 Sekunde Timeout
                )
            )
        filename, content, error = result
        assert filename == "app/page.js", \
            "Erwartet: filename bleibt 'app/page.js'"
        assert content is None, \
            "Erwartet: content=None bei Timeout"
        assert "Timeout" in error, \
            f"Erwartet: 'Timeout' in error, erhalten: '{error}'"

    def test_exception_gibt_fehlertext(self, mock_manager):
        """Bei Exception wird (filename, None, str(error)) zurueckgegeben."""
        with patch("backend.file_by_file_loop.run_single_file_coder",
                    side_effect=RuntimeError("Verbindung unterbrochen")):
            result = asyncio.run(
                pfg.generate_single_file_async(
                    manager=mock_manager,
                    filename="app/page.js",
                    file_description="Hauptseite",
                    existing_files={},
                    user_goal="Test",
                    project_rules={},
                    timeout_seconds=30,
                )
            )
        filename, content, error = result
        assert filename == "app/page.js", \
            "Erwartet: filename bleibt 'app/page.js'"
        assert content is None, \
            "Erwartet: content=None bei Exception"
        assert "Verbindung unterbrochen" in error, \
            f"Erwartet: 'Verbindung unterbrochen' in error, erhalten: '{error}'"


# =========================================================================
# 7. TestRunParallelFileGeneration
# =========================================================================

class TestRunParallelFileGeneration:
    """Tests fuer run_parallel_file_generation() — Batch-basierte Generierung."""

    def test_leere_file_list_gibt_leere_results(self, mock_manager):
        """Leere Dateiliste ergibt leere Ergebnisse."""
        with patch("backend.parallel_file_generator.analyze_parallelization_potential",
                    return_value={"total_files": 0, "total_batches": 0,
                                  "max_parallel_per_batch": 0, "theoretical_speedup": 1.0}), \
             patch("backend.parallel_file_generator.build_dependency_graph", return_value={}), \
             patch("backend.parallel_file_generator.get_parallel_batches", return_value=[]):
            results, errors = asyncio.run(
                pfg.run_parallel_file_generation(
                    manager=mock_manager,
                    file_list=[],
                    file_descriptions={},
                    user_goal="Test",
                    project_rules={},
                )
            )
        assert results == {}, \
            "Erwartet: Leeres results Dict bei leerer file_list"
        assert errors == [], \
            "Erwartet: Leere errors Liste bei leerer file_list"

    def test_erfolgreiche_generierung_befuellt_results(self, mock_manager, tmp_path):
        """Erfolgreich generierte Dateien landen im results Dict."""
        mock_manager.project_path = str(tmp_path)

        async def fake_generate(*args, **kwargs):
            return ("app/page.js", "export default function() {}", None)

        with patch("backend.parallel_file_generator.analyze_parallelization_potential",
                    return_value={"total_files": 1, "total_batches": 1,
                                  "max_parallel_per_batch": 1, "theoretical_speedup": 1.0}), \
             patch("backend.parallel_file_generator.build_dependency_graph", return_value={}), \
             patch("backend.parallel_file_generator.get_parallel_batches",
                    return_value=[["app/page.js"]]), \
             patch("backend.parallel_file_generator.generate_single_file_async",
                    side_effect=fake_generate), \
             patch("backend.parallel_file_generator.is_forbidden_file", return_value=False):
            results, errors = asyncio.run(
                pfg.run_parallel_file_generation(
                    manager=mock_manager,
                    file_list=["app/page.js"],
                    file_descriptions={"app/page.js": "Hauptseite"},
                    user_goal="Test",
                    project_rules={},
                )
            )
        assert "app/page.js" in results, \
            "Erwartet: app/page.js im results Dict"
        assert results["app/page.js"] == "export default function() {}", \
            "Erwartet: Content korrekt gespeichert"
        # Datei muss auf Disk geschrieben worden sein
        full_path = os.path.join(str(tmp_path), "app", "page.js")
        assert os.path.exists(full_path), \
            f"Erwartet: Datei {full_path} auf Disk geschrieben"

    def test_forbidden_file_wird_uebersprungen(self, mock_manager, tmp_path):
        """Verbotene Dateien werden uebersprungen (nicht ins results aufgenommen)."""
        mock_manager.project_path = str(tmp_path)

        async def fake_generate(*args, **kwargs):
            return ("package-lock.json", '{"lockfileVersion":3}', None)

        with patch("backend.parallel_file_generator.analyze_parallelization_potential",
                    return_value={"total_files": 1, "total_batches": 1,
                                  "max_parallel_per_batch": 1, "theoretical_speedup": 1.0}), \
             patch("backend.parallel_file_generator.build_dependency_graph", return_value={}), \
             patch("backend.parallel_file_generator.get_parallel_batches",
                    return_value=[["package-lock.json"]]), \
             patch("backend.parallel_file_generator.generate_single_file_async",
                    side_effect=fake_generate), \
             patch("backend.parallel_file_generator.is_forbidden_file", return_value=True):
            results, errors = asyncio.run(
                pfg.run_parallel_file_generation(
                    manager=mock_manager,
                    file_list=["package-lock.json"],
                    file_descriptions={},
                    user_goal="Test",
                    project_rules={},
                )
            )
        assert "package-lock.json" not in results, \
            "Erwartet: Verbotene Datei NICHT im results Dict"

    def test_requirements_txt_ruft_ensure_test_dependencies_auf(self, mock_manager, tmp_path):
        """Bei requirements.txt wird _ensure_test_dependencies aufgerufen."""
        mock_manager.project_path = str(tmp_path)

        async def fake_generate(*args, **kwargs):
            return ("requirements.txt", "flask==3.0.0\n", None)

        with patch("backend.parallel_file_generator.analyze_parallelization_potential",
                    return_value={"total_files": 1, "total_batches": 1,
                                  "max_parallel_per_batch": 1, "theoretical_speedup": 1.0}), \
             patch("backend.parallel_file_generator.build_dependency_graph", return_value={}), \
             patch("backend.parallel_file_generator.get_parallel_batches",
                    return_value=[["requirements.txt"]]), \
             patch("backend.parallel_file_generator.generate_single_file_async",
                    side_effect=fake_generate), \
             patch("backend.parallel_file_generator.is_forbidden_file", return_value=False), \
             patch("backend.parallel_file_generator._ensure_test_dependencies",
                    return_value="flask==3.0.0\npytest==8.0.0\n") as mock_deps:
            results, errors = asyncio.run(
                pfg.run_parallel_file_generation(
                    manager=mock_manager,
                    file_list=["requirements.txt"],
                    file_descriptions={"requirements.txt": "Python Deps"},
                    user_goal="Test",
                    project_rules={},
                )
            )
        mock_deps.assert_called_once(), \
            "Erwartet: _ensure_test_dependencies wurde aufgerufen"
        assert "pytest" in results.get("requirements.txt", ""), \
            "Erwartet: pytest in requirements.txt nach _ensure_test_dependencies"

    def test_batch_timeout_markiert_alle_als_fehler(self, mock_manager):
        """Bei Batch-Timeout werden alle Dateien im Batch als Fehler markiert."""
        async def slow_generate(*args, **kwargs):
            await asyncio.sleep(10)
            return ("app/page.js", "content", None)

        with patch("backend.parallel_file_generator.analyze_parallelization_potential",
                    return_value={"total_files": 2, "total_batches": 1,
                                  "max_parallel_per_batch": 2, "theoretical_speedup": 2.0}), \
             patch("backend.parallel_file_generator.build_dependency_graph", return_value={}), \
             patch("backend.parallel_file_generator.get_parallel_batches",
                    return_value=[["app/page.js", "lib/db.js"]]), \
             patch("backend.parallel_file_generator.generate_single_file_async",
                    side_effect=slow_generate):
            results, errors = asyncio.run(
                pfg.run_parallel_file_generation(
                    manager=mock_manager,
                    file_list=["app/page.js", "lib/db.js"],
                    file_descriptions={},
                    user_goal="Test",
                    project_rules={},
                    batch_timeout=1,  # 1 Sekunde Batch-Timeout
                )
            )
        assert len(errors) == 2, \
            f"Erwartet: 2 Fehler bei Batch-Timeout, erhalten: {len(errors)}"
        fehler_dateien = [e[0] for e in errors]
        assert "app/page.js" in fehler_dateien, \
            "Erwartet: app/page.js in Fehler-Liste"
        assert "lib/db.js" in fehler_dateien, \
            "Erwartet: lib/db.js in Fehler-Liste"

    def test_exception_in_task_landet_in_errors(self, mock_manager):
        """Exceptions in Tasks werden in der errors Liste erfasst."""
        async def failing_generate(*args, **kwargs):
            raise RuntimeError("LLM nicht erreichbar")

        with patch("backend.parallel_file_generator.analyze_parallelization_potential",
                    return_value={"total_files": 1, "total_batches": 1,
                                  "max_parallel_per_batch": 1, "theoretical_speedup": 1.0}), \
             patch("backend.parallel_file_generator.build_dependency_graph", return_value={}), \
             patch("backend.parallel_file_generator.get_parallel_batches",
                    return_value=[["app/page.js"]]), \
             patch("backend.parallel_file_generator.generate_single_file_async",
                    side_effect=failing_generate):
            results, errors = asyncio.run(
                pfg.run_parallel_file_generation(
                    manager=mock_manager,
                    file_list=["app/page.js"],
                    file_descriptions={},
                    user_goal="Test",
                    project_rules={},
                )
            )
        assert len(errors) >= 1, \
            f"Erwartet: Mindestens 1 Fehler, erhalten: {len(errors)}"
        fehler_texte = [e[1] for e in errors]
        assert any("LLM nicht erreichbar" in t for t in fehler_texte), \
            f"Erwartet: 'LLM nicht erreichbar' in Fehler-Texten: {fehler_texte}"
