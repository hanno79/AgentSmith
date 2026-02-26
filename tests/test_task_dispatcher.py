# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 14.02.2026
Version: 1.0
Beschreibung: Unit Tests fuer TaskDispatcher - Task-Verteilung, Batch-Bildung,
              Datei-Extraktion und Hilfs-Methoden.
              Testet Pure-Logic-Funktionen und Dataclasses OHNE LLM/CrewAI-Mocking.

              AENDERUNG 14.02.2026: 8 neue Test-Klassen hinzugefuegt (22 Tests):
              - TestSyncModifiedFilesToManager (8 Tests)
              - TestEmitFixEvent (4 Tests)
              - TestReportProgress (3 Tests)
              - TestGetStats (3 Tests)
              - TestShutdown (2 Tests)
              - TestGetAgentForTask (5 Tests)
              - TestExecuteBatch (5 Tests)
              - TestExecuteAll (4 Tests)
              Gesamt: 97 Tests in 16 Klassen.
"""

import os
import sys
import pytest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.task_dispatcher import TaskDispatcher, TaskExecutionResult
from backend.task_models import (
    DerivedTask, TaskBatch, BatchResult, TaskCategory,
    TaskPriority, TaskStatus, TargetAgent
)


# --- Hilfsfunktionen ---

def _make_dispatcher(**kwargs):
    """Erstellt TaskDispatcher mit Mock-Manager und Mock-Tracker."""
    manager = kwargs.pop("manager", MagicMock())
    if not hasattr(manager, "config"):
        manager.config = {}
    config = kwargs.pop("config", {})
    tracker = kwargs.pop("tracker", MagicMock())
    tracker._generate_summary.return_value = {"total": 0}
    max_parallel = kwargs.pop("max_parallel", 2)
    return TaskDispatcher(
        manager=manager, config=config, tracker=tracker, max_parallel=max_parallel
    )


def _make_task(task_id, deps=None, priority=TaskPriority.MEDIUM,
               affected=None, source_issue="Fix", title=None,
               category=TaskCategory.CODE):
    """Erstellt DerivedTask mit sinnvollen Defaults."""
    return DerivedTask(
        id=task_id,
        title=title or f"Task {task_id}",
        description=f"Beschreibung fuer Task {task_id}",
        category=category,
        priority=priority,
        target_agent=TargetAgent.CODER,
        affected_files=affected or ["file.js"],
        dependencies=deps or [],
        source_issue=source_issue,
        source_type="reviewer",
    )


# ============================================================
# 1. TestTaskExecutionResult - ca. 5 Tests
# ============================================================

class TestTaskExecutionResult:
    """Tests fuer das TaskExecutionResult Dataclass."""

    def test_default_werte(self):
        """Pflichtfelder gesetzt, optionale Felder haben korrekte Defaults."""
        r = TaskExecutionResult(task_id="T-001", success=False)
        assert r.task_id == "T-001"
        assert r.success is False
        assert r.result is None
        assert r.error_message == ""
        assert r.modified_files == []
        assert r.duration_seconds == 0.0
        assert r.agent_used == ""

    def test_custom_werte(self):
        """Alle Felder werden korrekt uebernommen."""
        r = TaskExecutionResult(
            task_id="T-002", success=True, result="OK",
            error_message="Warnung", modified_files=["a.py", "b.js"],
            duration_seconds=5.3, agent_used="coder"
        )
        assert r.success is True
        assert r.result == "OK"
        assert r.error_message == "Warnung"
        assert r.modified_files == ["a.py", "b.js"]
        assert r.duration_seconds == 5.3
        assert r.agent_used == "coder"

    def test_modified_files_mutable_eigene_liste(self):
        """Jede Instanz hat ihre eigene modified_files Liste (kein Shared-State)."""
        r1 = TaskExecutionResult(task_id="T-A", success=True)
        r2 = TaskExecutionResult(task_id="T-B", success=True)
        r1.modified_files.append("shared.py")
        assert "shared.py" not in r2.modified_files, (
            "modified_files darf NICHT zwischen Instanzen geteilt werden"
        )

    def test_success_false_als_default(self):
        """success muss explizit gesetzt werden (kein impliziter True-Default)."""
        r = TaskExecutionResult(task_id="T-X", success=False)
        assert r.success is False

    def test_duration_als_float(self):
        """duration_seconds akzeptiert Float-Werte."""
        r = TaskExecutionResult(task_id="T-D", success=True, duration_seconds=123.456)
        assert abs(r.duration_seconds - 123.456) < 0.001


# ============================================================
# 2. TestDispatch - ca. 15 Tests
# ============================================================

class TestDispatch:
    """Tests fuer dispatch() - Batch-Bildung mit Abhaengigkeitsanalyse."""

    def test_leere_task_liste(self):
        """Leere Task-Liste ergibt leere Batch-Liste."""
        d = _make_dispatcher()
        assert d.dispatch([]) == []
        d.shutdown()

    def test_ein_task_ein_batch(self):
        """Ein einzelner Task erzeugt genau einen Batch mit einem Task."""
        d = _make_dispatcher()
        batches = d.dispatch([_make_task("T-001")])
        assert len(batches) == 1
        assert len(batches[0].tasks) == 1
        assert batches[0].tasks[0].id == "T-001"
        d.shutdown()

    def test_drei_unabhaengige_tasks_ein_batch(self):
        """Drei unabhaengige Tasks werden in einem Batch gruppiert."""
        d = _make_dispatcher()
        tasks = [_make_task("T-001"), _make_task("T-002"), _make_task("T-003")]
        batches = d.dispatch(tasks)
        assert len(batches) == 1, f"Erwartet: 1 Batch, Erhalten: {len(batches)}"
        assert len(batches[0].tasks) == 3
        d.shutdown()

    def test_b_abhaengig_von_a_zwei_batches(self):
        """Task B abhaengig von A erzeugt 2 Batches: [A], [B]."""
        d = _make_dispatcher()
        tasks = [_make_task("T-A"), _make_task("T-B", deps=["T-A"])]
        batches = d.dispatch(tasks)
        assert len(batches) == 2
        assert batches[0].tasks[0].id == "T-A"
        assert batches[1].tasks[0].id == "T-B"
        d.shutdown()

    def test_kette_a_b_c_drei_batches(self):
        """Kette A->B->C erzeugt 3 sequentielle Batches."""
        d = _make_dispatcher()
        tasks = [
            _make_task("T-A"),
            _make_task("T-B", deps=["T-A"]),
            _make_task("T-C", deps=["T-B"]),
        ]
        batches = d.dispatch(tasks)
        assert len(batches) == 3
        assert batches[0].tasks[0].id == "T-A"
        assert batches[1].tasks[0].id == "T-B"
        assert batches[2].tasks[0].id == "T-C"
        d.shutdown()

    def test_parallele_und_serielle_gemischt(self):
        """A und B unabhaengig, C abhaengig von B: 2 Batches [A,B], [C]."""
        d = _make_dispatcher()
        tasks = [
            _make_task("T-A"),
            _make_task("T-B"),
            _make_task("T-C", deps=["T-B"]),
        ]
        batches = d.dispatch(tasks)
        assert len(batches) == 2
        batch1_ids = sorted([t.id for t in batches[0].tasks])
        assert "T-A" in batch1_ids and "T-B" in batch1_ids
        assert batches[1].tasks[0].id == "T-C"
        d.shutdown()

    def test_batch_ids_fortlaufend(self):
        """Batch-IDs folgen dem Format BATCH-001, BATCH-002, etc."""
        d = _make_dispatcher()
        tasks = [
            _make_task("T-1"),
            _make_task("T-2", deps=["T-1"]),
            _make_task("T-3", deps=["T-2"]),
        ]
        batches = d.dispatch(tasks)
        assert batches[0].batch_id == "BATCH-001"
        assert batches[1].batch_id == "BATCH-002"
        assert batches[2].batch_id == "BATCH-003"
        d.shutdown()

    def test_deadlock_zirkulaer_forciert_ersten(self):
        """Zirkulaere Abhaengigkeit A<->B wird aufgeloest (erster Task forciert)."""
        d = _make_dispatcher()
        tasks = [_make_task("T-A", deps=["T-B"]), _make_task("T-B", deps=["T-A"])]
        batches = d.dispatch(tasks)
        assert len(batches) >= 1, "Deadlock-Handling muss Batches liefern"
        alle_ids = [t.id for b in batches for t in b.tasks]
        assert "T-A" in alle_ids and "T-B" in alle_ids
        d.shutdown()

    def test_mehrere_abhaengigkeiten_auf_gleichen_task(self):
        """Zwei Tasks abhaengig vom selben Task: [A], [B,C]."""
        d = _make_dispatcher()
        tasks = [
            _make_task("T-A"),
            _make_task("T-B", deps=["T-A"]),
            _make_task("T-C", deps=["T-A"]),
        ]
        batches = d.dispatch(tasks)
        assert len(batches) == 2
        batch2_ids = sorted([t.id for t in batches[1].tasks])
        assert "T-B" in batch2_ids and "T-C" in batch2_ids
        d.shutdown()

    def test_priority_order_fortlaufend(self):
        """priority_order im Batch ist fortlaufend (1, 2, 3, ...)."""
        d = _make_dispatcher()
        tasks = [
            _make_task("T-1"),
            _make_task("T-2", deps=["T-1"]),
        ]
        batches = d.dispatch(tasks)
        assert batches[0].priority_order == 1
        assert batches[1].priority_order == 2
        d.shutdown()

    def test_einzelner_task_batch_inhalt(self):
        """Ein Batch enthaelt die korrekten Task-Objekte."""
        d = _make_dispatcher()
        t = _make_task("T-SOLO", title="Einzeltask")
        batches = d.dispatch([t])
        assert batches[0].tasks[0].title == "Einzeltask"
        d.shutdown()

    def test_batch_status_initial_pending(self):
        """Neu erstellte Batches haben Status PENDING."""
        d = _make_dispatcher()
        batches = d.dispatch([_make_task("T-1")])
        assert batches[0].status == TaskStatus.PENDING
        d.shutdown()

    def test_diamant_abhaengigkeit(self):
        """Diamant: A, B+C abhaengig von A, D abhaengig von B+C."""
        d = _make_dispatcher()
        tasks = [
            _make_task("T-A"),
            _make_task("T-B", deps=["T-A"]),
            _make_task("T-C", deps=["T-A"]),
            _make_task("T-D", deps=["T-B", "T-C"]),
        ]
        batches = d.dispatch(tasks)
        assert len(batches) == 3, f"Diamant braucht 3 Batches, erhalten: {len(batches)}"
        d.shutdown()

    def test_viele_unabhaengige_tasks(self):
        """10 unabhaengige Tasks landen alle in einem Batch."""
        d = _make_dispatcher()
        tasks = [_make_task(f"T-{i:03d}") for i in range(10)]
        batches = d.dispatch(tasks)
        assert len(batches) == 1
        assert len(batches[0].tasks) == 10
        d.shutdown()

    def test_c_abhaengig_von_b_nicht_a(self):
        """A unabhaengig, B unabhaengig, C nur von B: [A,B], [C]."""
        d = _make_dispatcher()
        tasks = [
            _make_task("T-A"),
            _make_task("T-B"),
            _make_task("T-C", deps=["T-B"]),
        ]
        batches = d.dispatch(tasks)
        assert len(batches) == 2
        # A und B muessen im ersten Batch sein
        b1_ids = {t.id for t in batches[0].tasks}
        assert b1_ids == {"T-A", "T-B"}
        d.shutdown()


# ============================================================
# 3. TestBuildTaskDescription - ca. 5 Tests
# ============================================================

class TestBuildTaskDescription:
    """Tests fuer _build_task_description."""

    def test_enthaelt_task_titel(self):
        """Beschreibung enthaelt den Task-Titel."""
        d = _make_dispatcher()
        task = _make_task("T-001", title="Login reparieren")
        desc = d._build_task_description(task)
        assert "Login reparieren" in desc
        d.shutdown()

    def test_enthaelt_tech_stack_sektion(self):
        """Bei vorhandenem tech_blueprint wird Tech-Stack-Sektion eingefuegt."""
        d = _make_dispatcher()
        d.manager.tech_blueprint = {
            "language": "javascript", "framework": "next", "project_type": "webapp"
        }
        task = _make_task("T-002")
        desc = d._build_task_description(task)
        assert "javascript" in desc, "Sprache fehlt in Tech-Sektion"
        assert "next" in desc, "Framework fehlt in Tech-Sektion"
        assert "webapp" in desc, "Projekt-Typ fehlt in Tech-Sektion"
        d.shutdown()

    def test_enthaelt_affected_files(self):
        """Affected Files werden in der Beschreibung aufgelistet."""
        d = _make_dispatcher()
        task = _make_task("T-003", affected=["auth.py", "login.js"])
        desc = d._build_task_description(task)
        assert "auth.py" in desc, "Datei auth.py fehlt"
        assert "login.js" in desc, "Datei login.js fehlt"
        d.shutdown()

    def test_enthaelt_source_issue_truncated(self):
        """source_issue wird auf 500 Zeichen abgeschnitten."""
        d = _make_dispatcher()
        langer_issue = "A" * 1000
        task = _make_task("T-004", source_issue=langer_issue)
        desc = d._build_task_description(task)
        # Pruefe dass max 500 Zeichen des Issues in der Beschreibung sind
        assert "A" * 500 in desc
        assert "A" * 501 not in desc
        d.shutdown()

    def test_ohne_tech_blueprint_keine_tech_sektion(self):
        """Ohne tech_blueprint wird keine Tech-Stack-Sektion eingefuegt."""
        d = _make_dispatcher()
        # manager hat kein tech_blueprint Attribut
        d.manager.tech_blueprint = {}
        task = _make_task("T-005")
        desc = d._build_task_description(task)
        assert "Tech-Stack" not in desc, "Tech-Sektion darf ohne Blueprint nicht erscheinen"
        d.shutdown()


# ============================================================
# 4. TestExtractModifiedFiles - ca. 15 Tests
# ============================================================

class TestExtractModifiedFiles:
    """Tests fuer _extract_modified_files."""

    def _dispatcher_with_blueprint(self, lang="javascript", framework="next"):
        """Erstellt Dispatcher mit tech_blueprint."""
        d = _make_dispatcher()
        d.manager.tech_blueprint = {
            "language": lang, "framework": framework, "project_type": "webapp"
        }
        return d

    def test_findet_dateinamen_im_text(self):
        """Einfache Dateinamen werden erkannt."""
        d = _make_dispatcher()
        task = _make_task("T-001")
        ergebnis = d._extract_modified_files("Ich habe page.js geaendert.", task)
        assert "page.js" in ergebnis

    def test_framework_blacklist_next_js(self):
        """Framework-Namen wie 'next.js' werden herausgefiltert."""
        d = _make_dispatcher()
        task = _make_task("T-002")
        text = "Dieses Projekt nutzt next.js und hat page.js als Hauptdatei."
        ergebnis = d._extract_modified_files(text, task)
        assert "next.js" not in ergebnis, "next.js ist ein Framework-Name, keine Datei"
        assert "page.js" in ergebnis

    def test_garbage_filter_unbekannte_datei(self):
        """Muell-Dateinamen wie 'UNBEKANNTE_DATEI.js' werden gefiltert."""
        d = _make_dispatcher()
        task = _make_task("T-003")
        text = "UNBEKANNTE_DATEI.js wurde erstellt."
        ergebnis = d._extract_modified_files(text, task)
        assert not any("UNBEKANNTE" in f for f in ergebnis)

    def test_tech_stack_filter_js_filtert_py(self):
        """Bei JS-Projekt werden .py Dateien herausgefiltert."""
        d = self._dispatcher_with_blueprint("javascript", "next")
        task = _make_task("T-004")
        text = "app.py und page.js wurden bearbeitet."
        ergebnis = d._extract_modified_files(text, task)
        assert "app.py" not in ergebnis, ".py soll bei JS-Projekt gefiltert werden"
        assert "page.js" in ergebnis

    def test_tech_stack_filter_python_filtert_jsx(self):
        """Bei Python-Projekt werden .jsx Dateien herausgefiltert."""
        d = self._dispatcher_with_blueprint("python", "flask")
        task = _make_task("T-005")
        text = "App.jsx und server.py wurden bearbeitet."
        ergebnis = d._extract_modified_files(text, task)
        assert not any(".jsx" in f for f in ergebnis), ".jsx soll bei Python gefiltert werden"
        assert "server.py" in ergebnis

    def test_pages_router_blacklist_bei_nextjs(self):
        """pages/ Dateien werden bei Next.js Projekten gefiltert."""
        d = _make_dispatcher()
        d.manager.tech_blueprint = {
            "language": "javascript", "framework": "next", "project_type": "next"
        }
        task = _make_task("T-006")
        text = "pages/index.js und app/page.js bearbeitet."
        ergebnis = d._extract_modified_files(text, task)
        assert not any("pages/" in f for f in ergebnis), "pages/ soll bei Next.js gefiltert werden"

    def test_existing_files_validierung(self):
        """Nur existierende Dateien bleiben nach Validierung uebrig."""
        d = _make_dispatcher()
        task = _make_task("T-007")
        existing = ["src/app.js", "src/utils.js"]
        text = "app.js und phantom.js und utils.js bearbeitet."
        ergebnis = d._extract_modified_files(text, task, existing_files=existing)
        assert "app.js" in ergebnis or "src/app.js" in ergebnis
        assert not any("phantom" in f for f in ergebnis)

    def test_fallback_auf_affected_files(self):
        """Wenn keine Dateien gefunden werden, Fallback auf affected_files."""
        d = _make_dispatcher()
        affected = ["fallback.js"]
        task = _make_task("T-008", affected=affected)
        ergebnis = d._extract_modified_files("Alles erledigt ohne Dateinamen.", task)
        assert ergebnis == affected

    def test_max_10_ergebnisse(self):
        """Maximal 10 Dateien werden zurueckgegeben."""
        d = _make_dispatcher()
        task = _make_task("T-009")
        # 15 verschiedene Dateinamen erzeugen
        dateien = " ".join([f"file{i}.js" for i in range(15)])
        ergebnis = d._extract_modified_files(dateien, task)
        assert len(ergebnis) <= 10, f"Max 10 Dateien, erhalten: {len(ergebnis)}"

    def test_duplikat_entfernung(self):
        """Doppelte Dateinamen werden dedupliziert."""
        d = _make_dispatcher()
        task = _make_task("T-010")
        text = "page.js und page.js und page.js bearbeitet."
        ergebnis = d._extract_modified_files(text, task)
        assert ergebnis.count("page.js") == 1, "Duplikate muessen entfernt werden"

    def test_vue_js_framework_blacklist(self):
        """vue.js als Framework-Name wird gefiltert."""
        d = _make_dispatcher()
        task = _make_task("T-011")
        text = "Das Projekt nutzt vue.js mit App.vue als Einstieg."
        ergebnis = d._extract_modified_files(text, task)
        assert "vue.js" not in ergebnis

    def test_node_js_framework_blacklist(self):
        """node.js als Framework-Name wird gefiltert."""
        d = _make_dispatcher()
        task = _make_task("T-012")
        text = "node.js Server mit server.js."
        ergebnis = d._extract_modified_files(text, task)
        assert "node.js" not in ergebnis
        assert "server.js" in ergebnis

    def test_relative_pfade_garbage_filter(self):
        """Relative Pfade wie './globals.css' werden gefiltert."""
        d = _make_dispatcher()
        task = _make_task("T-013")
        text = "./globals.css und styles.css bearbeitet."
        ergebnis = d._extract_modified_files(text, task)
        assert not any(f.startswith("./") for f in ergebnis)

    def test_leerer_text_ohne_affected(self):
        """Leerer Text ohne affected_files ergibt leere Liste."""
        d = _make_dispatcher()
        task = _make_task("T-014")
        # affected_files hat Default ["file.js"] → Fallback greift
        task.affected_files = []
        ergebnis = d._extract_modified_files("", task)
        assert ergebnis == []

    def test_beispieldatei_garbage_filter(self):
        """BeispielDatei wird als Platzhalter gefiltert."""
        d = _make_dispatcher()
        task = _make_task("T-015")
        text = "BeispielDatei.py wurde geaendert."
        ergebnis = d._extract_modified_files(text, task)
        assert not any("BeispielDatei" in f for f in ergebnis)


# ============================================================
# 5. TestExtractFileContentFromResult - ca. 10 Tests
# ============================================================

class TestExtractFileContentFromResult:
    """Tests fuer _extract_file_content_from_result."""

    def _lang_genug(self, code):
        """Erzeugt Code mit min. 10 Zeichen + Zeilenumbrueche."""
        return code + "\n# Padding fuer Mindestlaenge\n"

    def test_markdown_code_block_mit_kommentar(self):
        """Erkennt Code-Block mit Dateiname als Kommentar."""
        d = _make_dispatcher()
        code = self._lang_genug("import os\ndef main():\n    pass")
        text = f"Fix:\n```python\n# app.py\n{code}```\n"
        content = d._extract_file_content_from_result("app.py", text)
        assert content is not None, "Code sollte extrahiert werden"
        assert "def main" in content
        d.shutdown()

    def test_datei_label_format(self):
        """Erkennt 'Datei: file.js' Format."""
        d = _make_dispatcher()
        code = self._lang_genug("function helper() {\n  return true;\n}")
        text = f"Loesung:\nDatei: utils.js\n```js\n{code}```\n"
        content = d._extract_file_content_from_result("utils.js", text)
        assert content is not None, "Code nach 'Datei:' Label nicht extrahiert"
        assert "helper" in content
        d.shutdown()

    def test_markdown_header_format(self):
        """Erkennt '### file.js' Format."""
        d = _make_dispatcher()
        code = self._lang_genug("const data = {};\nexport default data;")
        text = f"### config.js\n```js\n{code}```\n"
        content = d._extract_file_content_from_result("config.js", text)
        assert content is not None
        assert "data" in content
        d.shutdown()

    def test_eckige_klammern_format(self):
        """Erkennt '[file.js]:' Format."""
        d = _make_dispatcher()
        code = self._lang_genug("export const API_URL = '/api';\nconst x = 1;")
        text = f"[config.js]:\n```js\n{code}```\n"
        content = d._extract_file_content_from_result("config.js", text)
        assert content is not None
        d.shutdown()

    def test_leerer_result_text_none(self):
        """Leerer result_text ergibt None."""
        d = _make_dispatcher()
        assert d._extract_file_content_from_result("file.js", "") is None
        d.shutdown()

    def test_leerer_filename_none(self):
        """Leerer Dateiname ergibt None."""
        d = _make_dispatcher()
        assert d._extract_file_content_from_result("", "etwas code") is None
        d.shutdown()

    def test_none_result_text(self):
        """None als result_text ergibt None."""
        d = _make_dispatcher()
        assert d._extract_file_content_from_result("file.js", None) is None
        d.shutdown()

    def test_code_block_zu_kurz_none(self):
        """Code-Block mit weniger als 10 Zeichen ergibt None."""
        d = _make_dispatcher()
        text = "Datei: x.js\n```js\nhi\n```\n"
        content = d._extract_file_content_from_result("x.js", text)
        assert content is None, "Zu kurzer Code-Block sollte None ergeben"
        d.shutdown()

    def test_fallback_groesster_code_block(self):
        """Fallback: Groesster Code-Block wenn nur 1 Datei."""
        d = _make_dispatcher()
        code = self._lang_genug("class BigProcessor:\n    def run(self):\n        return True")
        text = f"Ergebnis:\n```python\n{code}```\n"
        content = d._extract_file_content_from_result("processor.py", text)
        assert content is not None, "Fallback auf groessten Code-Block erwartet"
        assert "BigProcessor" in content
        d.shutdown()

    def test_basename_match_bei_vollem_pfad(self):
        """Basename-Match funktioniert bei vollem Pfad als Dateiname."""
        d = _make_dispatcher()
        code = self._lang_genug("import yaml\nDEFAULT = 30\ndef load():\n    pass")
        text = f"Datei: config.py\n```python\n{code}```\n"
        content = d._extract_file_content_from_result("src/config/config.py", text)
        assert content is not None, "Basename-Match sollte funktionieren"
        d.shutdown()


# ============================================================
# 6. TestCollectModifiedFiles - ca. 3 Tests
# ============================================================

class TestCollectModifiedFiles:
    """Tests fuer _collect_modified_files."""

    def test_sammelt_aus_mehreren_results(self):
        """Dateien aus mehreren Results werden zusammengefuehrt."""
        d = _make_dispatcher()
        results = [
            TaskExecutionResult(task_id="T-1", success=True, modified_files=["a.py"]),
            TaskExecutionResult(task_id="T-2", success=True, modified_files=["b.js"]),
        ]
        collected = d._collect_modified_files(results)
        assert "a.py" in collected and "b.js" in collected
        d.shutdown()

    def test_dedupliziert(self):
        """Duplikate werden entfernt."""
        d = _make_dispatcher()
        results = [
            TaskExecutionResult(task_id="T-1", success=True, modified_files=["x.py", "y.js"]),
            TaskExecutionResult(task_id="T-2", success=True, modified_files=["y.js", "z.ts"]),
        ]
        collected = d._collect_modified_files(results)
        assert len(collected) == 3, f"Erwartet: 3 eindeutige Dateien, Erhalten: {len(collected)}"
        d.shutdown()

    def test_leere_results(self):
        """Leere Results ergeben leere Liste."""
        d = _make_dispatcher()
        results = [
            TaskExecutionResult(task_id="T-1", success=True, modified_files=[]),
            TaskExecutionResult(task_id="T-2", success=False, modified_files=[]),
        ]
        assert d._collect_modified_files(results) == []
        d.shutdown()


# ============================================================
# 7. TestHasCriticalFailure - ca. 5 Tests
# ============================================================

class TestHasCriticalFailure:
    """Tests fuer _has_critical_failure."""

    def test_critical_task_failed_true(self):
        """Fehlgeschlagener CRITICAL-Task wird als kritisch erkannt."""
        d = _make_dispatcher()
        task = _make_task("T-001", priority=TaskPriority.CRITICAL)
        batch = TaskBatch(batch_id="B-001", tasks=[task])
        result = BatchResult(batch_id="B-001", success=False, failed_tasks=["T-001"])
        assert d._has_critical_failure(batch, result) is True
        d.shutdown()

    def test_medium_task_failed_false(self):
        """Fehlgeschlagener MEDIUM-Task ist KEIN kritischer Fehler."""
        d = _make_dispatcher()
        task = _make_task("T-002", priority=TaskPriority.MEDIUM)
        batch = TaskBatch(batch_id="B-002", tasks=[task])
        result = BatchResult(batch_id="B-002", success=False, failed_tasks=["T-002"])
        assert d._has_critical_failure(batch, result) is False
        d.shutdown()

    def test_high_task_failed_false(self):
        """Fehlgeschlagener HIGH-Task ist KEIN kritischer Fehler."""
        d = _make_dispatcher()
        task = _make_task("T-003", priority=TaskPriority.HIGH)
        batch = TaskBatch(batch_id="B-003", tasks=[task])
        result = BatchResult(batch_id="B-003", success=False, failed_tasks=["T-003"])
        assert d._has_critical_failure(batch, result) is False
        d.shutdown()

    def test_kein_task_failed_false(self):
        """Kein fehlgeschlagener Task ergibt keinen kritischen Fehler."""
        d = _make_dispatcher()
        task = _make_task("T-004", priority=TaskPriority.CRITICAL)
        batch = TaskBatch(batch_id="B-004", tasks=[task])
        result = BatchResult(batch_id="B-004", success=True, failed_tasks=[])
        assert d._has_critical_failure(batch, result) is False
        d.shutdown()

    def test_low_task_failed_false(self):
        """Fehlgeschlagener LOW-Task ist KEIN kritischer Fehler."""
        d = _make_dispatcher()
        task = _make_task("T-005", priority=TaskPriority.LOW)
        batch = TaskBatch(batch_id="B-005", tasks=[task])
        result = BatchResult(batch_id="B-005", success=False, failed_tasks=["T-005"])
        assert d._has_critical_failure(batch, result) is False
        d.shutdown()


# ============================================================
# 8. TestDispatcherInit - ca. 5 Tests
# ============================================================

class TestDispatcherInit:
    """Tests fuer die Initialisierung des TaskDispatchers."""

    @patch("os.cpu_count", return_value=8)
    def test_max_parallel_none_nutzt_cpu_count(self, mock_cpu):
        """Bei max_parallel=None wird os.cpu_count() verwendet."""
        d = _make_dispatcher(max_parallel=None)
        assert d.max_parallel == 8, f"Erwartet: 8, Erhalten: {d.max_parallel}"
        d.shutdown()

    def test_max_parallel_explizit(self):
        """Expliziter max_parallel Wert wird uebernommen."""
        d = _make_dispatcher(max_parallel=4)
        assert d.max_parallel == 4
        d.shutdown()

    def test_tracker_none_erstellt_neuen(self):
        """Bei tracker=None wird ein neuer TaskTracker erstellt."""
        manager = MagicMock()
        manager.config = {}
        d = TaskDispatcher(manager=manager, config={}, tracker=None, max_parallel=1)
        assert d.tracker is not None, "Tracker darf nicht None sein"
        d.shutdown()

    def test_agent_cache_initial_leer(self):
        """_agent_cache ist nach Initialisierung ein leeres Dict."""
        d = _make_dispatcher()
        assert d._agent_cache == {}, "Agent-Cache muss initial leer sein"
        d.shutdown()

    def test_set_progress_callback_setzt_callback(self):
        """set_progress_callback speichert die Callback-Funktion."""
        d = _make_dispatcher()
        cb = MagicMock()
        d.set_progress_callback(cb)
        assert d._progress_callback is cb
        # Callback wird bei _report_progress aufgerufen
        d._report_progress("test", "ok", 1.0)
        cb.assert_called_once_with("test", "ok", 1.0)
        d.shutdown()


# ============================================================
# 9. TestSyncModifiedFilesToManager - 8 Tests
# ============================================================

class TestSyncModifiedFilesToManager:
    """Tests fuer _sync_modified_files_to_manager."""

    def test_current_code_none_wird_dict(self):
        """Wenn current_code None ist, wird es zu einem leeren Dict initialisiert."""
        d = _make_dispatcher()
        d.manager.current_code = None
        d.manager._ui_log = MagicMock()
        # result_text mit Code-Block fuer Extraktion
        code = "import os\ndef main():\n    pass\n# Padding fuer Mindestlaenge"
        text = f"Datei: app.py\n```python\n{code}\n```\n"
        d._sync_modified_files_to_manager(["app.py"], text)
        assert isinstance(d.manager.current_code, dict), (
            "current_code muss nach Sync ein Dict sein"
        )
        d.shutdown()

    def test_current_code_string_skip(self):
        """Wenn current_code ein String ist, wird Sync uebersprungen."""
        d = _make_dispatcher()
        d.manager.current_code = "alter code als string"
        d.manager._ui_log = MagicMock()
        d._sync_modified_files_to_manager(["app.py"], "Datei: app.py\n```python\nimport os\ndef x(): pass\n```\n")
        # current_code bleibt String (wird nicht konvertiert)
        assert isinstance(d.manager.current_code, str), (
            "current_code soll bei String belassen werden"
        )
        d.shutdown()

    def test_current_code_dict_sync_erfolg(self):
        """Bei Dict-current_code werden Dateien synchronisiert."""
        d = _make_dispatcher()
        d.manager.current_code = {}
        d.manager._ui_log = MagicMock()
        code = "import os\ndef main():\n    return True\n# Padding fuer Mindestlaenge"
        text = f"Datei: utils.py\n```python\n{code}\n```\n"
        d._sync_modified_files_to_manager(["utils.py"], text)
        assert "utils.py" in d.manager.current_code, "utils.py soll in current_code sein"
        assert "def main" in d.manager.current_code["utils.py"]
        d.shutdown()

    def test_leere_modified_files_fruehe_rueckkehr(self):
        """Leere modified_files fuehrt zu frueher Rueckkehr ohne Aenderungen."""
        d = _make_dispatcher()
        d.manager.current_code = {"existing.py": "code"}
        d._sync_modified_files_to_manager([], "irgendein Text")
        # current_code unverändert
        assert d.manager.current_code == {"existing.py": "code"}
        d.shutdown()

    def test_manager_ohne_current_code_kein_crash(self):
        """Manager ohne current_code Attribut verursacht keinen Crash."""
        d = _make_dispatcher()
        # Explizit current_code entfernen
        del d.manager.current_code
        # Soll nicht crashen, hasattr()-Check greift
        d._sync_modified_files_to_manager(["file.py"], "text")
        d.shutdown()

    def test_erfolgreiche_sync_ui_log(self):
        """Erfolgreiche Sync loest UI-Log mit Datei-Anzahl aus."""
        d = _make_dispatcher()
        d.manager.current_code = {}
        d.manager._ui_log = MagicMock()
        code = "import os\ndef helper():\n    return 42\n# Padding fuer Mindestlaenge"
        text = f"Datei: helper.py\n```python\n{code}\n```\n"
        d._sync_modified_files_to_manager(["helper.py"], text)
        d.manager._ui_log.assert_called()
        # Pruefe dass "Success" und Dateiname im Aufruf vorkommen
        aufruf_args = d.manager._ui_log.call_args_list
        found_success = any("Success" in str(call) for call in aufruf_args)
        assert found_success, "UI-Log muss 'Success' enthalten"
        d.shutdown()

    def test_fehlgeschlagene_extraktion_warning_log(self):
        """Wenn Code-Extraktion fehlschlaegt, wird Warning geloggt."""
        d = _make_dispatcher()
        d.manager.current_code = {}
        d.manager._ui_log = MagicMock()
        # Text ohne extrahierbaren Code-Block
        d._sync_modified_files_to_manager(["phantom.py"], "Kein Code hier")
        # UI-Log sollte Warning enthalten
        aufruf_args = d.manager._ui_log.call_args_list
        found_warning = any("Warning" in str(call) for call in aufruf_args)
        assert found_warning, "UI-Log muss 'Warning' bei fehlgeschlagener Extraktion enthalten"
        d.shutdown()

    def test_ui_log_fehlt_kein_crash(self):
        """Wenn _ui_log fehlt, kein Crash."""
        d = _make_dispatcher()
        d.manager.current_code = {}
        # _ui_log nicht setzen (MagicMock hat es aber automatisch)
        # Explizit entfernen
        if hasattr(d.manager, '_ui_log'):
            del d.manager._ui_log
        code = "import os\ndef f():\n    return 1\n# Padding fuer Mindestlaenge"
        text = f"Datei: f.py\n```python\n{code}\n```\n"
        # Soll nicht crashen
        d._sync_modified_files_to_manager(["f.py"], text)
        d.shutdown()


# ============================================================
# 10. TestEmitFixEvent - 4 Tests
# ============================================================

class TestEmitFixEvent:
    """Tests fuer _emit_fix_event."""

    def test_on_log_vorhanden_wird_aufgerufen(self):
        """Wenn on_log vorhanden ist, wird es mit Fix + event_type + JSON aufgerufen."""
        d = _make_dispatcher()
        d.manager.on_log = MagicMock()
        d._emit_fix_event("FixStart", {"task_id": "T-001", "title": "Test"})
        d.manager.on_log.assert_called_once()
        args = d.manager.on_log.call_args[0]
        assert args[0] == "Fix"
        assert args[1] == "FixStart"
        assert "T-001" in args[2]
        d.shutdown()

    def test_on_log_none_kein_fehler(self):
        """Wenn on_log None ist, kein Fehler."""
        d = _make_dispatcher()
        d.manager.on_log = None
        # Soll nicht crashen
        d._emit_fix_event("FixStart", {"task_id": "T-001"})
        d.shutdown()

    def test_manager_ohne_on_log_kein_crash(self):
        """Manager ohne on_log Attribut verursacht keinen Crash."""
        d = _make_dispatcher()
        # MagicMock hat on_log automatisch, daher explizit entfernen
        del d.manager.on_log
        # hasattr()-Check im Code verhindert Crash
        d._emit_fix_event("FixOutput", {"task_id": "T-002"})
        d.shutdown()

    def test_non_serializable_wert_default_str(self):
        """Daten mit nicht-serialisierbarem Wert nutzen default=str."""
        d = _make_dispatcher()
        d.manager.on_log = MagicMock()
        from datetime import datetime as dt
        daten = {"timestamp": dt(2026, 2, 14, 12, 0, 0), "task_id": "T-003"}
        # Soll nicht crashen dank default=str
        d._emit_fix_event("FixOutput", daten)
        d.manager.on_log.assert_called_once()
        args = d.manager.on_log.call_args[0]
        assert "2026" in args[2], "datetime muss als String serialisiert werden"
        d.shutdown()


# ============================================================
# 11. TestReportProgress - 3 Tests
# ============================================================

class TestReportProgress:
    """Tests fuer _report_progress."""

    def test_callback_gesetzt_wird_aufgerufen(self):
        """Callback wird mit korrekten Argumenten aufgerufen."""
        d = _make_dispatcher()
        cb = MagicMock()
        d.set_progress_callback(cb)
        d._report_progress("Batch 1/3", "starting", 0.33)
        cb.assert_called_once_with("Batch 1/3", "starting", 0.33)
        d.shutdown()

    def test_kein_callback_kein_fehler(self):
        """Ohne gesetzten Callback kein Fehler."""
        d = _make_dispatcher()
        # _progress_callback ist None nach Init
        d._report_progress("Batch 1/1", "completed", 1.0)
        # Kein Crash = Erfolg
        d.shutdown()

    def test_callback_exception_wird_abgefangen(self):
        """Callback-Exception wird abgefangen, kein Crash."""
        d = _make_dispatcher()
        cb = MagicMock(side_effect=RuntimeError("Callback kaputt"))
        d.set_progress_callback(cb)
        # Soll NICHT crashen
        d._report_progress("Batch 1/1", "error", 0.0)
        cb.assert_called_once()
        d.shutdown()


# ============================================================
# 12. TestGetStats - 3 Tests
# ============================================================

class TestGetStats:
    """Tests fuer get_stats."""

    def test_enthaelt_max_parallel(self):
        """Stats enthalten max_parallel Wert."""
        d = _make_dispatcher(max_parallel=4)
        stats = d.get_stats()
        assert stats["max_parallel"] == 4
        d.shutdown()

    def test_enthaelt_cached_agents(self):
        """Stats enthalten cached_agents Liste."""
        d = _make_dispatcher()
        d._agent_cache["coder"] = MagicMock()
        d._agent_cache["tester"] = MagicMock()
        stats = d.get_stats()
        assert "coder" in stats["cached_agents"]
        assert "tester" in stats["cached_agents"]
        d.shutdown()

    def test_tracker_summary_eingebunden(self):
        """Stats enthalten tracker_summary."""
        d = _make_dispatcher()
        d.tracker._generate_summary.return_value = {"total": 5, "completed": 3}
        stats = d.get_stats()
        assert stats["tracker_summary"] == {"total": 5, "completed": 3}
        d.shutdown()


# ============================================================
# 13. TestShutdown - 2 Tests
# ============================================================

class TestShutdown:
    """Tests fuer shutdown."""

    def test_executor_wird_beendet(self):
        """Executor wird sauber beendet."""
        d = _make_dispatcher()
        d.shutdown()
        # Nach shutdown() sollen keine neuen Tasks angenommen werden
        assert d.executor._shutdown, "Executor muss nach shutdown() als beendet markiert sein"

    def test_mehrfaches_shutdown_kein_fehler(self):
        """Mehrfaches shutdown() verursacht keinen Fehler."""
        d = _make_dispatcher()
        d.shutdown()
        # Zweites shutdown soll nicht crashen
        d.shutdown()


# ============================================================
# 14. TestGetAgentForTask - 5 Tests
# ============================================================

class TestGetAgentForTask:
    """Tests fuer _get_agent_for_task."""

    def test_agent_aus_cache(self):
        """Agent wird aus Cache zurueckgegeben bei Cache-Hit."""
        d = _make_dispatcher()
        mock_agent = MagicMock()
        d._agent_cache["coder"] = mock_agent
        task = _make_task("T-001")
        result = d._get_agent_for_task(task)
        assert result is mock_agent, "Cached Agent muss zurueckgegeben werden"
        d.shutdown()

    def test_agent_factory_liefert_agent(self):
        """Agent wird via agent_factory erstellt und gecached."""
        d = _make_dispatcher()
        mock_agent = MagicMock()
        d.manager.agent_factory = MagicMock()
        d.manager.agent_factory.get.return_value = mock_agent
        task = _make_task("T-002")
        result = d._get_agent_for_task(task)
        assert result is mock_agent
        assert "coder" in d._agent_cache, "Agent muss gecached werden"
        d.shutdown()

    def test_agent_factory_liefert_none_fallback(self):
        """Wenn agent_factory None liefert, wird Fallback versucht."""
        d = _make_dispatcher()
        d.manager.agent_factory = MagicMock()
        d.manager.agent_factory.get.return_value = None
        task = _make_task("T-003")
        # Fallback wird _create_agent_fallback aufrufen, was ImportError wirft
        # (da agents/ Module nicht im Testkontext existieren)
        with patch.object(d, '_create_agent_fallback', return_value=None) as mock_fb:
            result = d._get_agent_for_task(task)
            mock_fb.assert_called_once_with("coder")
        d.shutdown()

    def test_keine_agent_factory_fallback(self):
        """Ohne agent_factory wird Fallback verwendet."""
        d = _make_dispatcher()
        # agent_factory entfernen
        del d.manager.agent_factory
        task = _make_task("T-004")
        with patch.object(d, '_create_agent_fallback', return_value=MagicMock()) as mock_fb:
            result = d._get_agent_for_task(task)
            mock_fb.assert_called_once_with("coder")
            assert result is not None
        d.shutdown()

    def test_exception_in_factory_none(self):
        """Exception in Factory gibt None zurueck."""
        d = _make_dispatcher()
        d.manager.agent_factory = MagicMock()
        d.manager.agent_factory.get.side_effect = RuntimeError("Factory kaputt")
        task = _make_task("T-005")
        result = d._get_agent_for_task(task)
        assert result is None, "Bei Exception muss None zurueckgegeben werden"
        d.shutdown()


# ============================================================
# 15. TestExecuteBatch - 5 Tests
# ============================================================

class TestExecuteBatch:
    """Tests fuer execute_batch mit gemockter _execute_single_task."""

    def _make_batch(self, tasks):
        """Erstellt TaskBatch aus Task-Liste."""
        return TaskBatch(batch_id="B-TEST", tasks=tasks)

    def test_erfolgreicher_batch(self):
        """Erfolgreicher Batch hat success=True und keine failed_tasks."""
        d = _make_dispatcher()
        task = _make_task("T-001")
        success_result = TaskExecutionResult(
            task_id="T-001", success=True, result="OK",
            modified_files=["app.py"], duration_seconds=1.0, agent_used="coder"
        )
        with patch.object(d, '_execute_single_task', return_value=success_result):
            batch = self._make_batch([task])
            result = d.execute_batch(batch)
        assert result.success is True, "Batch muss erfolgreich sein"
        assert "T-001" in result.completed_tasks
        assert result.failed_tasks == []
        d.shutdown()

    def test_fehlgeschlagener_task_in_failed(self):
        """Fehlgeschlagener Task landet in failed_tasks."""
        d = _make_dispatcher()
        task = _make_task("T-002")
        fail_result = TaskExecutionResult(
            task_id="T-002", success=False, error_message="Agent-Fehler"
        )
        with patch.object(d, '_execute_single_task', return_value=fail_result):
            batch = self._make_batch([task])
            result = d.execute_batch(batch)
        assert result.success is False
        assert "T-002" in result.failed_tasks
        assert len(result.errors) > 0
        d.shutdown()

    def test_task_timeout_exception(self):
        """Task-Timeout wird als Exception gefangen."""
        d = _make_dispatcher()
        task = _make_task("T-003")
        # Timeout-Exception simulieren: future.result(timeout=...) wirft TimeoutError
        from concurrent.futures import TimeoutError as FutureTimeout
        with patch.object(d, '_execute_single_task', side_effect=FutureTimeout("Timeout")):
            batch = self._make_batch([task])
            result = d.execute_batch(batch)
        # Task muss in failed_tasks sein (Exception-Path in execute_batch)
        assert "T-003" in result.failed_tasks
        d.shutdown()

    def test_batch_status_aenderung(self):
        """Batch-Status aendert sich auf IN_PROGRESS und dann COMPLETED."""
        d = _make_dispatcher()
        task = _make_task("T-004")
        success_result = TaskExecutionResult(
            task_id="T-004", success=True, result="OK"
        )
        batch = self._make_batch([task])
        assert batch.status == TaskStatus.PENDING, "Initialer Status muss PENDING sein"
        with patch.object(d, '_execute_single_task', return_value=success_result):
            result = d.execute_batch(batch)
        assert batch.status == TaskStatus.COMPLETED, "Status muss COMPLETED sein nach Ausfuehrung"
        d.shutdown()

    def test_tracker_wird_aktualisiert(self):
        """Tracker wird bei Erfolg mit COMPLETED aktualisiert."""
        d = _make_dispatcher()
        task = _make_task("T-005")
        success_result = TaskExecutionResult(
            task_id="T-005", success=True, result="OK",
            modified_files=["result.py"]
        )
        with patch.object(d, '_execute_single_task', return_value=success_result):
            batch = self._make_batch([task])
            d.execute_batch(batch)
        # Tracker muss update_status mit IN_PROGRESS und dann COMPLETED aufgerufen haben
        update_calls = d.tracker.update_status.call_args_list
        statuses = [call[0][1] for call in update_calls]
        assert TaskStatus.IN_PROGRESS in statuses, "Tracker muss IN_PROGRESS erhalten"
        assert TaskStatus.COMPLETED in statuses, "Tracker muss COMPLETED erhalten"
        d.shutdown()

    def test_retry_wird_im_batch_tatsaechlich_ausgefuehrt(self):
        """Fehlerhafte Tasks werden innerhalb desselben Batches erneut ausgefuehrt."""
        d = _make_dispatcher()
        task = _make_task("T-006")
        task.max_retries = 2
        fail_result = TaskExecutionResult(task_id="T-006", success=False, error_message="kaputt")
        success_result = TaskExecutionResult(task_id="T-006", success=True, result="OK")

        # Erstes Ergebnis fehlgeschlagen, zweites erfolgreich -> Retry muss erfolgen.
        d.tracker.increment_retry.return_value = True
        with patch.object(d, "_execute_single_task", side_effect=[fail_result, success_result]) as mock_exec:
            batch = self._make_batch([task])
            result = d.execute_batch(batch)

        assert mock_exec.call_count == 2, "Task muss nach Fehler erneut ausgefuehrt werden"
        assert result.success is True
        assert result.completed_tasks == ["T-006"]
        assert result.failed_tasks == []
        d.shutdown()

    def test_timeout_ausfuehrung_wird_beendet_und_als_failed_markiert(self):
        """Haengende Tasks laufen in Timeout statt den Batch endlos zu blockieren."""
        d = _make_dispatcher()
        task = _make_task("T-007")
        task.timeout_seconds = 1
        task.max_retries = 1

        def _slow_task(_, __=None):
            import time
            time.sleep(2)
            return TaskExecutionResult(task_id="T-007", success=True, result="zu spaet")

        with patch.object(d, "_execute_single_task", side_effect=_slow_task):
            batch = self._make_batch([task])
            result = d.execute_batch(batch)

        assert result.success is False
        assert "T-007" in result.failed_tasks
        assert any("Timeout" in err for err in result.errors)
        d.shutdown()

    def test_timeout_triggert_claude_prozess_kill(self):
        """Bei Timeout wird der aktive Claude-Prozess explizit abgebrochen."""
        manager = MagicMock()
        manager.config = {}
        manager.claude_provider = MagicMock()
        d = _make_dispatcher(manager=manager)
        task = _make_task("T-008")
        task.timeout_seconds = 1
        task.max_retries = 1

        def _slow_until_cancel(_task, cancel_event=None):
            import time
            while cancel_event is not None and not cancel_event.is_set():
                time.sleep(0.05)
            # Ergebnis kommt absichtlich "zu spaet" und darf nicht mehr als Erfolg zaehlen.
            return TaskExecutionResult(task_id="T-008", success=True, result="late")

        with patch.object(d, "_execute_single_task", side_effect=_slow_until_cancel):
            batch = self._make_batch([task])
            result = d.execute_batch(batch)

        manager.claude_provider.kill_active_process.assert_called()
        assert result.success is False
        assert "T-008" in result.failed_tasks
        d.shutdown()


# ============================================================
# 16. TestExecuteAll - 4 Tests
# ============================================================

class TestExecuteAll:
    """Tests fuer execute_all mit gemockter _execute_single_task."""

    def test_leere_task_liste_leere_results(self):
        """Leere Task-Liste ergibt leere Results."""
        d = _make_dispatcher()
        results = d.execute_all([])
        assert results == [], "Leere Tasks muessen leere Results ergeben"
        d.shutdown()

    def test_tasks_im_tracker_registriert(self):
        """Tasks werden im Tracker via log_task registriert."""
        d = _make_dispatcher()
        task = _make_task("T-001")
        success_result = TaskExecutionResult(
            task_id="T-001", success=True, result="OK"
        )
        with patch.object(d, '_execute_single_task', return_value=success_result):
            d.execute_all([task])
        d.tracker.log_task.assert_called_once_with(task)
        d.shutdown()

    def test_kritischer_fehler_abbruch(self):
        """Bei kritischem Fehler wird die Ausfuehrung abgebrochen."""
        d = _make_dispatcher()
        task1 = _make_task("T-001", priority=TaskPriority.CRITICAL)
        task2 = _make_task("T-002", deps=["T-001"])
        fail_result = TaskExecutionResult(
            task_id="T-001", success=False, error_message="Kritischer Fehler"
        )
        with patch.object(d, '_execute_single_task', return_value=fail_result):
            results = d.execute_all([task1, task2])
        # Es sollte nur ein Batch-Result geben (Abbruch nach erstem Batch)
        assert len(results) == 1, (
            f"Erwartet: 1 Result (Abbruch bei kritischem Fehler), Erhalten: {len(results)}"
        )
        d.shutdown()

    def test_progress_callback_wird_aufgerufen(self):
        """Progress-Callback wird bei execute_all aufgerufen."""
        d = _make_dispatcher()
        cb = MagicMock()
        d.set_progress_callback(cb)
        task = _make_task("T-001")
        success_result = TaskExecutionResult(
            task_id="T-001", success=True, result="OK"
        )
        with patch.object(d, '_execute_single_task', return_value=success_result):
            d.execute_all([task])
        assert cb.call_count >= 1, "Progress-Callback muss mindestens einmal aufgerufen werden"
        d.shutdown()
