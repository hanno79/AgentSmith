# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 14.02.2026
Version: 1.1
Beschreibung: Tests fuer backend/worker_pool.py — Worker, WorkerPool, OfficeManager.
              Synchrone Pure-Logic-Funktionen und async-Methoden.

              AENDERUNG 14.02.2026 v1.1: Async-Tests ergaenzt fuer assign_task,
              _execute_task, _process_queue, _notify_status_change,
              OfficeManager.assign_task_to_office und _handle_pool_status_change.
"""

import pytest
import asyncio
from datetime import datetime
from unittest.mock import MagicMock

from backend.worker_pool import Worker, WorkerPool, WorkerStatus, OfficeManager


class TestWorkerStatus:
    """Tests fuer WorkerStatus Enum."""

    def test_idle_wert(self):
        assert WorkerStatus.IDLE.value == "idle"

    def test_working_wert(self):
        assert WorkerStatus.WORKING.value == "working"

    def test_error_wert(self):
        assert WorkerStatus.ERROR.value == "error"

    def test_offline_wert(self):
        assert WorkerStatus.OFFLINE.value == "offline"


class TestWorker:
    """Tests fuer Worker Dataclass."""

    def test_default_werte(self):
        """Worker hat korrekte Defaults."""
        w = Worker(id="w1", name="Alex", office="coder")
        assert w.status == WorkerStatus.IDLE
        assert w.current_task is None
        assert w.current_task_description is None
        assert w.model is None
        assert w.tasks_completed == 0
        assert w.last_activity is None

    def test_to_dict_grundstruktur(self):
        """to_dict enthaelt alle erwarteten Felder."""
        w = Worker(id="w1", name="Alex", office="coder")
        d = w.to_dict()
        assert d["id"] == "w1"
        assert d["name"] == "Alex"
        assert d["office"] == "coder"
        assert d["status"] == "idle"
        assert d["current_task"] is None
        assert d["tasks_completed"] == 0
        assert d["last_activity"] is None

    def test_to_dict_mit_last_activity(self):
        """to_dict formatiert last_activity als ISO-String."""
        now = datetime.now()
        w = Worker(id="w1", name="Alex", office="coder", last_activity=now)
        assert w.to_dict()["last_activity"] == now.isoformat()

    def test_to_dict_mit_modell(self):
        """to_dict enthaelt Modell-Info."""
        w = Worker(id="w1", name="Alex", office="coder", model="gpt-4")
        assert w.to_dict()["model"] == "gpt-4"

    def test_status_aenderung(self):
        """Status kann geaendert werden."""
        w = Worker(id="w1", name="Alex", office="coder")
        w.status = WorkerStatus.WORKING
        assert w.status == WorkerStatus.WORKING


class TestWorkerPool:
    """Tests fuer WorkerPool — synchrone Methoden."""

    def test_init_erstellt_worker(self):
        pool = WorkerPool("coder", max_workers=3)
        assert len(pool.workers) == 3

    def test_init_worker_namen_und_ids(self):
        pool = WorkerPool("coder", max_workers=2)
        namen = [w.name for w in pool.workers.values()]
        assert "Alex" in namen and "Jordan" in namen
        pool2 = WorkerPool("tester", max_workers=2)
        assert "tester_1" in pool2.workers and "tester_2" in pool2.workers

    def test_init_max_workers_begrenzt(self):
        """Max-Workers begrenzt auf verfuegbare Namen."""
        pool = WorkerPool("db_designer", max_workers=5)
        assert len(pool.workers) == 1

    def test_get_worker_vorhanden(self):
        pool = WorkerPool("coder", max_workers=1)
        w = pool.get_worker("coder_1")
        assert w is not None and w.name == "Alex"

    def test_get_worker_nicht_vorhanden(self):
        pool = WorkerPool("coder", max_workers=1)
        assert pool.get_worker("unknown_99") is None

    def test_get_idle_workers_alle_idle(self):
        pool = WorkerPool("coder", max_workers=3)
        assert len(pool.get_idle_workers()) == 3

    def test_get_idle_workers_einer_working(self):
        pool = WorkerPool("coder", max_workers=3)
        pool.workers["coder_1"].status = WorkerStatus.WORKING
        assert len(pool.get_idle_workers()) == 2

    def test_get_active_workers_initial_leer(self):
        pool = WorkerPool("coder", max_workers=3)
        assert pool.get_active_workers() == []

    def test_get_active_workers_einer_working(self):
        pool = WorkerPool("coder", max_workers=3)
        pool.workers["coder_1"].status = WorkerStatus.WORKING
        active = pool.get_active_workers()
        assert len(active) == 1 and active[0].id == "coder_1"

    def test_get_status_grundstruktur(self):
        pool = WorkerPool("coder", max_workers=2)
        status = pool.get_status()
        assert status["office"] == "coder"
        assert status["total_workers"] == 2
        assert status["active_workers"] == 0
        assert status["idle_workers"] == 2
        assert len(status["workers"]) == 2

    def test_get_status_mit_active(self):
        pool = WorkerPool("coder", max_workers=3)
        pool.workers["coder_1"].status = WorkerStatus.WORKING
        pool.workers["coder_2"].status = WorkerStatus.WORKING
        status = pool.get_status()
        assert status["active_workers"] == 2 and status["idle_workers"] == 1

    def test_to_dict_gleich_get_status(self):
        pool = WorkerPool("coder", max_workers=1)
        assert pool.to_dict() == pool.get_status()

    def test_worker_names_coder_acht(self):
        assert len(WorkerPool.WORKER_NAMES["coder"]) == 8

    def test_worker_names_tester_drei(self):
        assert len(WorkerPool.WORKER_NAMES["tester"]) == 3

    def test_worker_names_reviewer_eins(self):
        assert len(WorkerPool.WORKER_NAMES["reviewer"]) == 1

    def test_reset_setzt_worker_zurueck(self):
        """reset() setzt alle Worker auf IDLE."""
        pool = WorkerPool("coder", max_workers=2)
        pool.workers["coder_1"].status = WorkerStatus.WORKING
        pool.workers["coder_1"].current_task = "task-1"
        pool.workers["coder_1"].model = "gpt-4"
        pool.reset()
        for w in pool.workers.values():
            assert w.status == WorkerStatus.IDLE
            assert w.current_task is None
            assert w.model is None


class TestOfficeManager:
    """Tests fuer OfficeManager — synchrone Methoden."""

    def test_init_erstellt_alle_offices(self):
        om = OfficeManager()
        for name in ["coder", "tester", "reviewer", "security"]:
            assert name in om.pools

    def test_default_config_coder_acht_worker(self):
        om = OfficeManager()
        assert om.pools["coder"].max_workers == 8

    def test_custom_config(self):
        config = {"coder": {"max_workers": 2}, "custom_office": {"max_workers": 1}}
        om = OfficeManager(config=config)
        assert om.pools["coder"].max_workers == 2
        assert "custom_office" in om.pools

    def test_get_pool_vorhanden(self):
        om = OfficeManager()
        pool = om.get_pool("coder")
        assert pool is not None and pool.office == "coder"

    def test_get_pool_nicht_vorhanden(self):
        assert OfficeManager().get_pool("unknown_office") is None

    def test_get_all_status_grundstruktur(self):
        status = OfficeManager().get_all_status()
        assert "total_workers" in status and "total_active" in status
        assert "offices" in status
        assert status["total_workers"] > 0 and status["total_active"] == 0

    def test_get_active_offices_initial_leer(self):
        assert OfficeManager().get_active_offices() == []

    def test_get_active_offices_mit_working(self):
        om = OfficeManager()
        om.pools["coder"].workers["coder_1"].status = WorkerStatus.WORKING
        assert "coder" in om.get_active_offices()

    def test_to_dict_gleich_get_all_status(self):
        om = OfficeManager()
        assert om.to_dict() == om.get_all_status()

    def test_reset_all_workers(self):
        om = OfficeManager()
        om.pools["coder"].workers["coder_1"].status = WorkerStatus.WORKING
        om.pools["tester"].workers["tester_1"].status = WorkerStatus.ERROR
        om.reset_all_workers()
        for pool in om.pools.values():
            for w in pool.workers.values():
                assert w.status == WorkerStatus.IDLE

    def test_fix_office_vorhanden(self):
        om = OfficeManager()
        assert "fix" in om.pools and om.pools["fix"].max_workers == 2


# AENDERUNG 14.02.2026: Async-Tests fuer assign_task, _execute_task,
# _process_queue, _notify_status_change

class TestWorkerPoolAsync:
    """Tests fuer WorkerPool — async-Methoden."""

    @staticmethod
    async def _cancel_pool_tasks(pool):
        """Hilfsfunktion: Cancelt alle laufenden Tasks im Pool (async-safe)."""
        for task in list(pool._worker_tasks.values()):
            task.cancel()
        await asyncio.gather(*pool._worker_tasks.values(), return_exceptions=True)
        pool._worker_tasks.clear()

    @pytest.mark.asyncio
    async def test_assign_task_idle_worker(self):
        """assign_task weist idle Worker den Task zu und setzt alle Felder."""
        pool = WorkerPool("coder", max_workers=2)
        started = asyncio.Event()
        async def slow_fn():
            started.set()
            await asyncio.sleep(10)

        worker_id = await pool.assign_task("t-1", "Test Task", slow_fn, "gpt-4")
        await started.wait()
        assert worker_id == "coder_1"
        w = pool.get_worker(worker_id)
        assert w.status == WorkerStatus.WORKING
        assert w.current_task == "t-1"
        assert w.current_task_description == "Test Task"
        assert w.model == "gpt-4"
        assert w.last_activity is not None
        await self._cancel_pool_tasks(pool)

    @pytest.mark.asyncio
    async def test_assign_task_kein_idle_worker_queue(self):
        """assign_task reiht in Queue ein wenn kein Worker verfuegbar."""
        pool = WorkerPool("reviewer", max_workers=1)
        started = asyncio.Event()
        async def blocking_fn():
            started.set()
            await asyncio.sleep(10)

        await pool.assign_task("t-1", "Blockiert", blocking_fn, "gpt-4")
        await started.wait()
        result = await pool.assign_task("t-2", "Wartend", blocking_fn)
        assert result is None
        assert pool._task_queue.qsize() == 1
        await self._cancel_pool_tasks(pool)

    @pytest.mark.asyncio
    async def test_assign_task_mit_callback(self):
        """assign_task ruft on_status_change Callback mit task_assigned und task_completed auf."""
        events = []
        async def cb(data):
            events.append(data["event"])
        pool = WorkerPool("coder", max_workers=1, on_status_change=cb)
        async def dummy_fn():
            return "fertig"

        await pool.assign_task("t-cb", "CB", dummy_fn, "gpt-4")
        await asyncio.sleep(0.15)
        assert "task_assigned" in events
        assert "task_completed" in events

    @pytest.mark.asyncio
    async def test_execute_task_erfolg(self):
        """_execute_task: Erfolg setzt Worker IDLE, zaehlt tasks_completed."""
        pool = WorkerPool("coder", max_workers=1)
        w = pool.get_worker("coder_1")
        w.status = WorkerStatus.WORKING
        w.current_task = "t-exec"
        async def ok_fn():
            return {"status": "ok"}

        result = await pool._execute_task(w, ok_fn)
        assert result == {"status": "ok"}
        assert w.status == WorkerStatus.IDLE
        assert w.tasks_completed == 1
        assert w.current_task is None

    @pytest.mark.asyncio
    async def test_execute_task_exception(self):
        """_execute_task: Exception setzt ERROR, dann nach Pause IDLE."""
        pool = WorkerPool("coder", max_workers=1)
        w = pool.get_worker("coder_1")
        w.status = WorkerStatus.WORKING
        w.current_task = "t-fail"
        async def fail_fn():
            raise ValueError("Test-Fehler")

        with pytest.raises(ValueError, match="Test-Fehler"):
            await pool._execute_task(w, fail_fn)
        assert w.status == WorkerStatus.IDLE
        assert w.current_task is None
        assert w.tasks_completed == 0

    @pytest.mark.asyncio
    async def test_execute_task_cancelled(self):
        """_execute_task: CancelledError setzt IDLE und re-raised."""
        pool = WorkerPool("coder", max_workers=1)
        w = pool.get_worker("coder_1")
        w.status = WorkerStatus.WORKING
        async def cancel_fn():
            raise asyncio.CancelledError()

        with pytest.raises(asyncio.CancelledError):
            await pool._execute_task(w, cancel_fn)
        assert w.status == WorkerStatus.IDLE

    @pytest.mark.asyncio
    async def test_execute_task_kwargs(self):
        """_execute_task leitet kwargs an execute_fn weiter."""
        pool = WorkerPool("coder", max_workers=1)
        w = pool.get_worker("coder_1")
        w.status = WorkerStatus.WORKING
        async def add_fn(x=0, y=0):
            return x + y

        assert await pool._execute_task(w, add_fn, x=3, y=7) == 10

    @pytest.mark.asyncio
    async def test_execute_task_entfernt_tracking(self):
        """_execute_task entfernt Worker aus _worker_tasks."""
        pool = WorkerPool("coder", max_workers=1)
        w = pool.get_worker("coder_1")
        w.status = WorkerStatus.WORKING
        pool._worker_tasks[w.id] = MagicMock()
        async def ok_fn():
            return "ok"

        await pool._execute_task(w, ok_fn)
        assert w.id not in pool._worker_tasks

    @pytest.mark.asyncio
    async def test_process_queue_mit_idle(self):
        """_process_queue weist wartende Tasks an idle Worker zu."""
        pool = WorkerPool("coder", max_workers=2)
        ergebnisse = []
        async def track_fn(wert="x"):
            ergebnisse.append(wert)

        await pool._task_queue.put({
            "task_id": "q-1", "description": "Q1",
            "execute_fn": track_fn, "model": None, "kwargs": {"wert": "eins"}
        })
        await pool._process_queue()
        await asyncio.sleep(0.1)
        assert "eins" in ergebnisse

    @pytest.mark.asyncio
    async def test_process_queue_stoppt_ohne_idle(self):
        """_process_queue stoppt wenn kein idle Worker verfuegbar."""
        pool = WorkerPool("reviewer", max_workers=1)
        pool.workers["reviewer_1"].status = WorkerStatus.WORKING
        async def ok_fn():
            return "ok"

        await pool._task_queue.put({
            "task_id": "q-x", "description": "B",
            "execute_fn": ok_fn, "model": None, "kwargs": {}
        })
        await pool._process_queue()
        assert pool._task_queue.qsize() == 1

    @pytest.mark.asyncio
    async def test_notify_status_change(self):
        """_notify_status_change ruft Callback mit korrekten Daten auf."""
        empfangen = []
        async def cb(data):
            empfangen.append(data)
        pool = WorkerPool("coder", max_workers=1, on_status_change=cb)

        await pool._notify_status_change(pool.get_worker("coder_1"), "evt", extra="v")
        assert len(empfangen) == 1
        assert empfangen[0]["event"] == "evt"
        assert empfangen[0]["office"] == "coder"
        assert empfangen[0]["extra"] == "v"
        assert "worker" in empfangen[0] and "pool_status" in empfangen[0]

    @pytest.mark.asyncio
    async def test_notify_ohne_callback(self):
        """_notify_status_change ohne Callback wirft keinen Fehler."""
        pool = WorkerPool("coder", max_workers=1)
        await pool._notify_status_change(pool.get_worker("coder_1"), "no_cb")

    @pytest.mark.asyncio
    async def test_komplett_lifecycle(self):
        """Kompletter Lifecycle: assign → execute → idle mit Events."""
        events = []
        async def cb(data):
            events.append(data["event"])
        pool = WorkerPool("coder", max_workers=1, on_status_change=cb)
        async def arbeit():
            await asyncio.sleep(0.05)
            return "erledigt"

        w_id = await pool.assign_task("t-lc", "Lifecycle", arbeit, "gpt-4")
        assert w_id == "coder_1"
        await asyncio.sleep(0.2)
        w = pool.get_worker("coder_1")
        assert w.status == WorkerStatus.IDLE and w.tasks_completed == 1
        assert "task_assigned" in events and "task_completed" in events


# AENDERUNG 14.02.2026: Async-Tests fuer assign_task_to_office, _handle_pool_status_change

class TestOfficeManagerAsync:
    """Tests fuer OfficeManager — async-Methoden."""

    @pytest.mark.asyncio
    async def test_assign_task_to_office_erfolgreich(self):
        """assign_task_to_office delegiert an Pool.assign_task."""
        om = OfficeManager()
        async def ok_fn():
            return "ok"
        w_id = await om.assign_task_to_office("coder", "t-o", "Test", ok_fn, "gpt-4")
        assert w_id is not None and w_id.startswith("coder_")

    @pytest.mark.asyncio
    async def test_assign_task_to_office_unbekannt(self):
        """assign_task_to_office gibt None fuer unbekanntes Office."""
        om = OfficeManager()
        async def ok_fn():
            return "ok"
        assert await om.assign_task_to_office("nope", "t-x", "X", ok_fn) is None

    @pytest.mark.asyncio
    async def test_assign_task_to_office_kwargs(self):
        """assign_task_to_office leitet kwargs korrekt weiter."""
        om = OfficeManager()
        empf = {}
        async def fn(a="", b=0):
            empf["a"] = a
            empf["b"] = b
        await om.assign_task_to_office("security", "t-k", "K", fn, a="w", b=42)
        await asyncio.sleep(0.1)
        assert empf["a"] == "w" and empf["b"] == 42

    @pytest.mark.asyncio
    async def test_handle_pool_status_change_callback(self):
        """_handle_pool_status_change leitet Daten an on_status_change weiter."""
        empf = []
        async def g_cb(data):
            empf.append(data)
        om = OfficeManager(on_status_change=g_cb)
        async def ok_fn():
            return "ok"
        await om.assign_task_to_office("reviewer", "t-h", "S", ok_fn, "gpt-4")
        await asyncio.sleep(0.1)
        assert len(empf) >= 1 and empf[0]["office"] == "reviewer"

    @pytest.mark.asyncio
    async def test_handle_pool_status_change_ohne_callback(self):
        """_handle_pool_status_change ohne Callback wirft keinen Fehler."""
        om = OfficeManager(on_status_change=None)
        await om._handle_pool_status_change({"test": "daten"})

    @pytest.mark.asyncio
    async def test_mehrere_offices_parallel(self):
        """Mehrere Offices koennen parallel Tasks bearbeiten."""
        om = OfficeManager()
        erg = {}
        async def c_fn():
            erg["coder"] = True
        async def t_fn():
            erg["tester"] = True
        w1 = await om.assign_task_to_office("coder", "t-c", "C", c_fn)
        w2 = await om.assign_task_to_office("tester", "t-t", "T", t_fn)
        assert w1 is not None and w2 is not None
        await asyncio.sleep(0.1)
        assert erg.get("coder") is True and erg.get("tester") is True
