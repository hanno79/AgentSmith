# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 06.02.2026
Version: 1.0
Beschreibung: Unit Tests fuer TaskDispatcher - Task-Verteilung und Batch-Bildung.
              Testet Initialisierung, Batch-Bildung, Datei-Extraktion, Callbacks, Statistiken.
"""

import pytest
import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.task_dispatcher import TaskDispatcher, TaskExecutionResult
from backend.task_models import (
    DerivedTask, TaskBatch, BatchResult, TaskCategory,
    TaskPriority, TaskStatus, TargetAgent
)


# --- Hilfsfunktionen ---

def _make_task(id, title="Test", priority=TaskPriority.MEDIUM,
               deps=None, affected=None, source_issue=""):
    """Helper: Erstellt DerivedTask mit sinnvollen Defaults."""
    return DerivedTask(
        id=id, title=title, description=f"Beschreibung fuer {title}",
        category=TaskCategory.CODE, priority=priority,
        target_agent=TargetAgent.CODER,
        affected_files=affected or [], dependencies=deps or [],
        source_issue=source_issue
    )


@pytest.fixture
def dispatcher():
    """Fixture: Erstellt TaskDispatcher mit Mocks, fuehrt nach Test shutdown() aus."""
    manager = MagicMock()
    config = {"agent_timeout_seconds": 30}
    tracker = MagicMock()
    tracker._generate_summary.return_value = {"total": 0}
    router = MagicMock()
    d = TaskDispatcher(manager=manager, config=config, tracker=tracker,
                       router=router, max_parallel=2)
    yield d
    d.shutdown()


# --- TestTaskDispatcherInit ---

class TestTaskDispatcherInit:
    """Tests fuer die Initialisierung des TaskDispatchers."""

    @patch("os.cpu_count", return_value=8)
    def test_default_max_parallel_nutzt_cpu_count(self, mock_cpu):
        """Bei max_parallel=None wird os.cpu_count() verwendet."""
        manager, tracker = MagicMock(), MagicMock()
        tracker._generate_summary.return_value = {}
        d = TaskDispatcher(manager=manager, config={}, tracker=tracker)
        assert d.max_parallel == 8, f"Erwartet: 8, Erhalten: {d.max_parallel}"
        d.shutdown()

    def test_expliziter_max_parallel_wert(self, dispatcher):
        """Expliziter max_parallel Wert wird uebernommen."""
        assert dispatcher.max_parallel == 2, f"Erwartet: 2, Erhalten: {dispatcher.max_parallel}"


# --- TestBuildTaskDescription ---

class TestBuildTaskDescription:
    """Tests fuer _build_task_description."""

    def test_enthaelt_affected_files(self, dispatcher):
        """Affected Files werden in der Beschreibung aufgelistet."""
        task = _make_task("T-001", title="Fix Login", affected=["auth.py", "login.js"])
        desc = dispatcher._build_task_description(task)
        assert "auth.py" in desc, "Datei auth.py fehlt in Beschreibung"
        assert "login.js" in desc, "Datei login.js fehlt in Beschreibung"
        assert "Fix Login" in desc, "Titel fehlt in Beschreibung"

    def test_ohne_affected_files(self, dispatcher):
        """Ohne affected_files wird 'Nicht spezifiziert' angezeigt."""
        task = _make_task("T-002", affected=[])
        desc = dispatcher._build_task_description(task)
        assert "Nicht spezifiziert" in desc, "Fallback 'Nicht spezifiziert' fehlt"

    def test_mit_source_issue(self, dispatcher):
        """Source Issue wird in der Beschreibung eingebunden."""
        issue = "Fehler bei der Authentifizierung in Zeile 42"
        task = _make_task("T-003", source_issue=issue)
        desc = dispatcher._build_task_description(task)
        assert issue in desc, "Source-Issue Text fehlt in Beschreibung"

    def test_ohne_source_issue(self, dispatcher):
        """Ohne Source Issue wird 'Kein Original-Issue' angezeigt."""
        task = _make_task("T-004", source_issue="")
        desc = dispatcher._build_task_description(task)
        assert "Kein Original-Issue" in desc, "Fallback 'Kein Original-Issue' fehlt"


# --- TestBuildDependencyGraph ---

class TestBuildDependencyGraph:
    """Tests fuer _build_dependency_graph."""

    def test_leere_liste_ergibt_leeren_graph(self, dispatcher):
        """Leere Task-Liste ergibt leeren Abhaengigkeits-Graph."""
        assert dispatcher._build_dependency_graph([]) == {}

    def test_unabhaengige_tasks(self, dispatcher):
        """Tasks ohne dependencies haben leere Listen im Graph."""
        tasks = [_make_task("T-001", deps=[]), _make_task("T-002", deps=[])]
        graph = dispatcher._build_dependency_graph(tasks)
        assert graph["T-001"] == [] and graph["T-002"] == []

    def test_mit_abhaengigkeiten(self, dispatcher):
        """Dependencies werden korrekt im Graph abgebildet."""
        tasks = [
            _make_task("T-001", deps=[]),
            _make_task("T-002", deps=["T-001"]),
            _make_task("T-003", deps=["T-001", "T-002"]),
        ]
        graph = dispatcher._build_dependency_graph(tasks)
        assert graph["T-001"] == []
        assert graph["T-002"] == ["T-001"]
        assert graph["T-003"] == ["T-001", "T-002"]


# --- TestExtractModifiedFiles ---

class TestExtractModifiedFiles:
    """Tests fuer _extract_modified_files."""

    def test_python_dateien_werden_erkannt(self, dispatcher):
        """Python-Dateinamen werden aus dem Ergebnis-Text extrahiert."""
        task = _make_task("T-001")
        result = "Ich habe die Dateien 'app.py' und 'utils.py' geaendert."
        files = dispatcher._extract_modified_files(result, task)
        assert "app.py" in files, "app.py wurde nicht extrahiert"
        assert "utils.py" in files, "utils.py wurde nicht extrahiert"

    def test_js_dateien_werden_erkannt(self, dispatcher):
        """JavaScript-Dateinamen werden aus dem Ergebnis-Text extrahiert."""
        task = _make_task("T-002")
        result = 'Geaendert: "App.js" und "helper.ts" in src/'
        files = dispatcher._extract_modified_files(result, task)
        assert any("App.js" in f for f in files), "App.js wurde nicht extrahiert"
        assert any("helper.ts" in f for f in files), "helper.ts wurde nicht extrahiert"

    def test_fallback_auf_affected_files(self, dispatcher):
        """Ohne erkennbare Dateien wird auf affected_files zurueckgefallen."""
        affected = ["src/main.py", "config/settings.py"]
        task = _make_task("T-003", affected=affected)
        files = dispatcher._extract_modified_files("Alles bearbeitet.", task)
        assert files == affected, f"Erwartet: {affected}, Erhalten: {files}"

    def test_leerer_result_mit_affected_files(self, dispatcher):
        """Leerer Result-Text fuehrt zu Fallback auf affected_files."""
        affected = ["server.py"]
        task = _make_task("T-004", affected=affected)
        assert dispatcher._extract_modified_files("", task) == affected

    def test_leerer_result_ohne_affected_files(self, dispatcher):
        """Leerer Result-Text ohne affected_files ergibt leere Liste."""
        task = _make_task("T-005", affected=[])
        assert dispatcher._extract_modified_files("", task) == []


# --- TestExtractFileContentFromResult ---

class TestExtractFileContentFromResult:
    """Tests fuer _extract_file_content_from_result."""

    def test_code_block_mit_dateiname_kommentar(self, dispatcher):
        """Erkennt Code-Block mit Dateiname als Kommentar-Zeile."""
        text = "Fix:\n```python\n# app.py\nimport os\nimport sys\n\ndef main():\n    print('Hi')\n\nif __name__ == '__main__':\n    main()\n```\n"
        content = dispatcher._extract_file_content_from_result("app.py", text)
        assert content is not None, "Code sollte extrahiert werden"
        assert "def main():" in content, "Funktion main() fehlt"

    def test_code_nach_datei_label(self, dispatcher):
        """Erkennt Code-Block nach 'Datei: filename.py' Format."""
        text = "Loesung:\nDatei: utils.py\n```python\nimport logging\n\nlogger = logging.getLogger(__name__)\n\ndef helper_function(data):\n    return data.strip()\n```\n"
        content = dispatcher._extract_file_content_from_result("utils.py", text)
        assert content is not None, "Code nach 'Datei:' Label nicht extrahiert"
        assert "helper_function" in content

    def test_basename_match(self, dispatcher):
        """Erkennt Datei auch wenn nur der Basename im Result steht."""
        text = "Fix:\nDatei: config.py\n```python\nimport yaml\n\nDEFAULT_TIMEOUT = 30\nMAX_RETRIES = 3\n\ndef load_config(path):\n    with open(path) as f:\n        return yaml.safe_load(f)\n```\n"
        content = dispatcher._extract_file_content_from_result("src/config/config.py", text)
        assert content is not None, "Basename-Match sollte funktionieren"
        assert "load_config" in content

    def test_generischer_code_block_fallback(self, dispatcher):
        """Fallback auf groessten Code-Block wenn kein Dateiname-Match."""
        text = "Loesung:\n```python\nimport os\nimport sys\nimport json\n\nclass DataProcessor:\n    def __init__(self):\n        self.data = []\n\n    def process(self, item):\n        self.data.append(item)\n        return len(self.data)\n```\n"
        content = dispatcher._extract_file_content_from_result("processor.py", text)
        assert content is not None, "Fallback auf groessten Code-Block erwartet"
        assert "DataProcessor" in content

    def test_none_bei_leerem_input(self, dispatcher):
        """Leerer Input oder leerer Dateiname ergibt None."""
        assert dispatcher._extract_file_content_from_result("", "code") is None
        assert dispatcher._extract_file_content_from_result("f.py", "") is None
        assert dispatcher._extract_file_content_from_result("f.py", None) is None


# --- TestCollectModifiedFiles ---

class TestCollectModifiedFiles:
    """Tests fuer _collect_modified_files."""

    def test_deduplizierung(self, dispatcher):
        """Duplikate werden entfernt, alle Dateien gesammelt."""
        results = [
            TaskExecutionResult(task_id="T-001", success=True, modified_files=["app.py", "utils.py"]),
            TaskExecutionResult(task_id="T-002", success=True, modified_files=["utils.py", "config.py"]),
        ]
        collected = dispatcher._collect_modified_files(results)
        assert len(collected) == 3, f"Erwartet: 3 eindeutige Dateien, Erhalten: {collected}"
        for f in ["app.py", "utils.py", "config.py"]:
            assert f in collected, f"{f} fehlt"

    def test_leere_results(self, dispatcher):
        """Leere Results ergeben eine leere Dateiliste."""
        results = [
            TaskExecutionResult(task_id="T-001", success=True, modified_files=[]),
            TaskExecutionResult(task_id="T-002", success=False, modified_files=[]),
        ]
        assert dispatcher._collect_modified_files(results) == []


# --- TestHasCriticalFailure ---

class TestHasCriticalFailure:
    """Tests fuer _has_critical_failure."""

    def test_critical_task_fehlgeschlagen(self, dispatcher):
        """Fehlgeschlagener CRITICAL-Task wird als kritischer Fehler erkannt."""
        task = _make_task("T-001", priority=TaskPriority.CRITICAL)
        batch = TaskBatch(batch_id="B-001", tasks=[task])
        result = BatchResult(batch_id="B-001", success=False, failed_tasks=["T-001"])
        assert dispatcher._has_critical_failure(batch, result) is True

    def test_medium_task_fehlgeschlagen_nicht_kritisch(self, dispatcher):
        """Fehlgeschlagener MEDIUM-Task ist KEIN kritischer Fehler."""
        task = _make_task("T-002", priority=TaskPriority.MEDIUM)
        batch = TaskBatch(batch_id="B-002", tasks=[task])
        result = BatchResult(batch_id="B-002", success=False, failed_tasks=["T-002"])
        assert dispatcher._has_critical_failure(batch, result) is False

    def test_keine_fehler(self, dispatcher):
        """Keine Fehler im Batch ergibt keinen kritischen Fehler."""
        task = _make_task("T-003", priority=TaskPriority.CRITICAL)
        batch = TaskBatch(batch_id="B-003", tasks=[task])
        result = BatchResult(batch_id="B-003", success=True, failed_tasks=[])
        assert dispatcher._has_critical_failure(batch, result) is False


# --- TestDispatch ---

class TestDispatch:
    """Tests fuer dispatch() - Batch-Bildung."""

    def test_leere_liste(self, dispatcher):
        """Leere Task-Liste ergibt leere Batch-Liste."""
        assert dispatcher.dispatch([]) == []

    def test_unabhaengige_tasks_ein_batch(self, dispatcher):
        """Unabhaengige Tasks werden in einem Batch gruppiert."""
        tasks = [_make_task("T-001"), _make_task("T-002"), _make_task("T-003")]
        batches = dispatcher.dispatch(tasks)
        assert len(batches) == 1, f"Erwartet: 1 Batch, Erhalten: {len(batches)}"
        assert len(batches[0].tasks) == 3

    def test_abhaengigkeitskette_mehrere_batches(self, dispatcher):
        """Tasks mit Abhaengigkeitskette erzeugen sequentielle Batches."""
        tasks = [
            _make_task("T-001"), _make_task("T-002", deps=["T-001"]),
            _make_task("T-003", deps=["T-002"]),
        ]
        batches = dispatcher.dispatch(tasks)
        assert len(batches) == 3, f"Erwartet: 3 Batches, Erhalten: {len(batches)}"
        assert batches[0].tasks[0].id == "T-001"
        assert batches[1].tasks[0].id == "T-002"
        assert batches[2].tasks[0].id == "T-003"

    def test_deadlock_forciert_ersten_task(self, dispatcher):
        """Bei zirkulaerer Abhaengigkeit wird der erste Task forciert."""
        tasks = [_make_task("T-001", deps=["T-002"]), _make_task("T-002", deps=["T-001"])]
        batches = dispatcher.dispatch(tasks)
        assert len(batches) >= 1, "Deadlock-Handling sollte Batches erstellen"
        all_ids = [t.id for b in batches for t in b.tasks]
        assert "T-001" in all_ids and "T-002" in all_ids

    def test_gemischte_abhaengigkeiten(self, dispatcher):
        """Parallele und sequentielle Tasks werden korrekt gebatched."""
        tasks = [
            _make_task("T-001"), _make_task("T-002"),
            _make_task("T-003", deps=["T-001", "T-002"]),
        ]
        batches = dispatcher.dispatch(tasks)
        assert len(batches) == 2, f"Erwartet: 2 Batches, Erhalten: {len(batches)}"
        batch_1_ids = [t.id for t in batches[0].tasks]
        assert "T-001" in batch_1_ids and "T-002" in batch_1_ids
        assert batches[1].tasks[0].id == "T-003"

    def test_batch_ids_fortlaufend(self, dispatcher):
        """Batch-IDs folgen dem Format BATCH-001, BATCH-002."""
        tasks = [_make_task("T-001"), _make_task("T-002", deps=["T-001"])]
        batches = dispatcher.dispatch(tasks)
        assert batches[0].batch_id == "BATCH-001"
        assert batches[1].batch_id == "BATCH-002"


# --- TestReportProgress ---

class TestReportProgress:
    """Tests fuer _report_progress."""

    def test_callback_wird_aufgerufen(self, dispatcher):
        """Callback wird mit korrekten Parametern aufgerufen."""
        callback = MagicMock()
        dispatcher._progress_callback = callback
        dispatcher._report_progress("Batch 1/3", "starting", 0.33)
        callback.assert_called_once_with("Batch 1/3", "starting", 0.33)

    def test_ohne_callback_kein_fehler(self, dispatcher):
        """Ohne Callback wird kein Fehler geworfen."""
        dispatcher._progress_callback = None
        dispatcher._report_progress("Batch 1/1", "completed", 1.0)

    def test_fehlerhafter_callback_abgefangen(self, dispatcher):
        """Ein fehlerhafter Callback wirft keine Exception nach aussen."""
        dispatcher._progress_callback = MagicMock(side_effect=ValueError("Fehler"))
        dispatcher._report_progress("Batch 1/1", "error", 0.5)


# --- TestGetStats ---

class TestGetStats:
    """Tests fuer get_stats."""

    def test_stats_struktur(self, dispatcher):
        """Statistiken enthalten alle erwarteten Schluessel."""
        stats = dispatcher.get_stats()
        assert "max_parallel" in stats, "'max_parallel' fehlt"
        assert "cached_agents" in stats, "'cached_agents' fehlt"
        assert "tracker_summary" in stats, "'tracker_summary' fehlt"
        assert stats["max_parallel"] == 2
        assert isinstance(stats["cached_agents"], list)
        assert isinstance(stats["tracker_summary"], dict)


# --- TestSetProgressCallback ---

class TestSetProgressCallback:
    """Tests fuer set_progress_callback."""

    def test_callback_setzen_und_nutzen(self, dispatcher):
        """Callback wird ueber set_progress_callback gesetzt und genutzt."""
        ergebnisse = []
        dispatcher.set_progress_callback(lambda s, st, p: ergebnisse.append((s, st, p)))
        dispatcher._report_progress("Test-Stage", "running", 0.75)
        assert len(ergebnisse) == 1
        assert ergebnisse[0] == ("Test-Stage", "running", 0.75)


# --- TestTaskExecutionResult ---

class TestTaskExecutionResult:
    """Tests fuer das TaskExecutionResult Datenmodell."""

    def test_default_werte(self):
        """Default-Werte werden korrekt gesetzt."""
        result = TaskExecutionResult(task_id="T-001", success=True)
        assert result.task_id == "T-001"
        assert result.success is True
        assert result.result is None
        assert result.error_message == ""
        assert result.modified_files == []
        assert result.duration_seconds == 0.0
        assert result.agent_used == ""

    def test_vollstaendige_erstellung(self):
        """Alle Felder werden korrekt gesetzt."""
        result = TaskExecutionResult(
            task_id="T-002", success=False, result="Fehlgeschlagen",
            error_message="Import-Fehler", modified_files=["fix.py"],
            duration_seconds=12.5, agent_used="coder"
        )
        assert result.task_id == "T-002"
        assert result.success is False
        assert result.error_message == "Import-Fehler"
        assert result.modified_files == ["fix.py"]
        assert result.duration_seconds == 12.5
        assert result.agent_used == "coder"


# --- TestShutdown ---

class TestShutdown:
    """Tests fuer shutdown."""

    def test_shutdown_beendet_executor(self):
        """Shutdown beendet den ThreadPoolExecutor sauber."""
        manager, tracker = MagicMock(), MagicMock()
        tracker._generate_summary.return_value = {}
        d = TaskDispatcher(manager=manager, config={}, tracker=tracker, max_parallel=2)
        assert d.executor._shutdown is False, "Executor sollte vor shutdown aktiv sein"
        d.shutdown()
        assert d.executor._shutdown is True, "Executor sollte nach shutdown beendet sein"
