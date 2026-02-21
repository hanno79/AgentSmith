# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 14.02.2026
Version: 1.0
Beschreibung: Unit-Tests fuer backend/orchestration_worker_status.py.
              Testet AGENT_NAMES_MAPPING, handle_worker_status_change
              und update_worker_status mit gemocktem OfficeManager/WorkerPool.
"""

import os
import sys
import json
import asyncio
import unittest
from unittest.mock import MagicMock, patch, AsyncMock

# Projekt-Root zum Python-Path hinzufuegen
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.orchestration_worker_status import (
    AGENT_NAMES_MAPPING,
    handle_worker_status_change,
    update_worker_status,
)
from backend.worker_pool import WorkerStatus, Worker, WorkerPool


# -- Hilfsfunktionen --

def _erstelle_mock_pool(office="coder", anzahl_worker=2):
    """Erstellt einen echten WorkerPool mit der gewuenschten Anzahl Worker."""
    pool = WorkerPool(office=office, max_workers=anzahl_worker)
    return pool


def _erstelle_mock_office_manager(pools=None):
    """
    Erstellt einen Mock OfficeManager mit get_pool()-Methode.
    Wenn pools angegeben, gibt get_pool den entsprechenden Pool zurueck.
    """
    manager = MagicMock()
    if pools:
        manager.get_pool = MagicMock(side_effect=lambda office: pools.get(office))
    else:
        manager.get_pool = MagicMock(return_value=None)
    return manager


class TestAgentNamesMapping:
    """Tests fuer das AGENT_NAMES_MAPPING Dictionary."""

    def test_mapping_enthaelt_standard_offices(self):
        """Alle Standard-Offices sind im Mapping vorhanden."""
        erwartete_offices = [
            "coder", "tester", "designer", "db_designer",
            "security", "researcher", "reviewer",
            "techstack_architect", "documentation_manager", "planner", "fix"
        ]
        for office in erwartete_offices:
            assert office in AGENT_NAMES_MAPPING, (
                f"Office '{office}' fehlt im AGENT_NAMES_MAPPING"
            )

    def test_mapping_werte_sind_strings(self):
        """Alle Werte im Mapping sind nicht-leere Strings."""
        for key, value in AGENT_NAMES_MAPPING.items():
            assert isinstance(value, str), (
                f"Wert fuer '{key}' ist kein String: {type(value)}"
            )
            assert len(value) > 0, f"Wert fuer '{key}' ist leer"

    def test_coder_mapping(self):
        """Coder Office wird auf 'Coder' gemappt."""
        assert AGENT_NAMES_MAPPING["coder"] == "Coder"

    def test_tester_mapping(self):
        """Tester Office wird auf 'Tester' gemappt."""
        assert AGENT_NAMES_MAPPING["tester"] == "Tester"

    def test_fix_mapping(self):
        """Fix Office wird auf 'Fix' gemappt (Fix 14)."""
        assert AGENT_NAMES_MAPPING["fix"] == "Fix"

    def test_planner_mapping(self):
        """Planner Office wird auf 'Planner' gemappt."""
        assert AGENT_NAMES_MAPPING["planner"] == "Planner"


class TestHandleWorkerStatusChange:
    """Tests fuer die async handle_worker_status_change Funktion."""

    def test_sendet_log_mit_korrektem_agent_namen(self):
        """Log-Callback wird mit dem gemappten Agent-Namen aufgerufen."""
        on_log = MagicMock()
        daten = {"office": "coder", "status": "working"}

        # AENDERUNG 21.02.2026: asyncio.run() statt get_event_loop().run_until_complete()
        # ROOT-CAUSE-FIX: get_event_loop() wirft RuntimeError in Python 3.12+
        asyncio.run(handle_worker_status_change(daten, on_log))

        on_log.assert_called_once()
        aufruf_args = on_log.call_args[0]
        assert aufruf_args[0] == "Coder", (
            f"Erwartet Agent 'Coder', erhalten: {aufruf_args[0]}"
        )
        assert aufruf_args[1] == "WorkerStatus", (
            f"Erwartet Event 'WorkerStatus', erhalten: {aufruf_args[1]}"
        )

    def test_sendet_json_daten_als_message(self):
        """Die Daten werden als JSON-String gesendet."""
        on_log = MagicMock()
        daten = {"office": "tester", "event": "task_assigned"}

        asyncio.run(handle_worker_status_change(daten, on_log))

        aufruf_args = on_log.call_args[0]
        nachricht = json.loads(aufruf_args[2])
        assert nachricht["office"] == "tester"
        assert nachricht["event"] == "task_assigned"

    def test_unbekanntes_office_wird_system(self):
        """Unbekanntes Office wird auf 'System' gemappt."""
        on_log = MagicMock()
        daten = {"office": "unbekannt_xyz", "status": "idle"}

        asyncio.run(handle_worker_status_change(daten, on_log))

        aufruf_args = on_log.call_args[0]
        assert aufruf_args[0] == "System", (
            f"Unbekanntes Office sollte 'System' werden, erhalten: {aufruf_args[0]}"
        )

    def test_kein_office_key_wird_system(self):
        """Daten ohne 'office' Key verwenden 'System' als Fallback."""
        on_log = MagicMock()
        daten = {"status": "idle"}

        asyncio.run(handle_worker_status_change(daten, on_log))

        aufruf_args = on_log.call_args[0]
        assert aufruf_args[0] == "System"

    def test_none_callback_kein_fehler(self):
        """None als Callback verursacht keinen Fehler."""
        daten = {"office": "coder", "status": "working"}
        # Sollte ohne Fehler durchlaufen
        asyncio.run(handle_worker_status_change(daten, None))


class TestUpdateWorkerStatusWorking:
    """Tests fuer update_worker_status mit Status 'working'."""

    def test_worker_wird_auf_working_gesetzt(self):
        """Idle Worker wird auf WORKING gesetzt wenn Status 'working'."""
        pool = _erstelle_mock_pool("coder", 2)
        office_manager = _erstelle_mock_office_manager({"coder": pool})
        on_log = MagicMock()

        # Alle Worker sind initial IDLE
        assert len(pool.get_idle_workers()) == 2

        update_worker_status(
            office_manager, "coder", "working", on_log,
            task_description="Code generieren",
            model="test-model"
        )

        # Ein Worker sollte jetzt WORKING sein
        aktive = pool.get_active_workers()
        assert len(aktive) == 1, (
            f"Erwartet 1 aktiver Worker, erhalten: {len(aktive)}"
        )
        assert aktive[0].current_task_description == "Code generieren"
        assert aktive[0].model == "test-model"

    def test_log_callback_enthaelt_task_assigned(self):
        """Log-Callback wird mit event 'task_assigned' aufgerufen."""
        pool = _erstelle_mock_pool("coder", 1)
        office_manager = _erstelle_mock_office_manager({"coder": pool})
        on_log = MagicMock()

        update_worker_status(
            office_manager, "coder", "working", on_log,
            task_description="Testaufgabe"
        )

        on_log.assert_called()
        # Finde den WorkerStatus-Aufruf (nicht den Error-Aufruf)
        for aufruf in on_log.call_args_list:
            args = aufruf[0]
            if args[1] == "WorkerStatus":
                daten = json.loads(args[2])
                assert daten["event"] == "task_assigned"
                break

    def test_kein_worker_verfuegbar_kein_fehler(self):
        """Wenn alle Worker belegt sind, passiert nichts (kein Fehler)."""
        pool = _erstelle_mock_pool("coder", 1)
        office_manager = _erstelle_mock_office_manager({"coder": pool})
        on_log = MagicMock()

        # Ersten Worker auf WORKING setzen
        pool.workers["coder_1"].status = WorkerStatus.WORKING

        # Zweiter Versuch sollte nichts tun (return)
        update_worker_status(
            office_manager, "coder", "working", on_log,
            task_description="Zweite Aufgabe"
        )
        # on_log wird NICHT aufgerufen wenn kein idle Worker da ist
        # (die Funktion kehrt frueh zurueck)


class TestUpdateWorkerStatusIdle:
    """Tests fuer update_worker_status mit Status 'idle'."""

    def test_worker_wird_auf_idle_gesetzt(self):
        """Aktiver Worker wird auf IDLE zurueckgesetzt.

        Hinweis: Die Funktion prueft zuerst get_idle_workers() um
        die Bedingung `workers or worker_status == "working"` zu erfuellen.
        Daher brauchen wir mindestens 2 Worker: einen IDLE (damit aeussere
        Bedingung True), einen WORKING (der dann auf IDLE gesetzt wird).
        """
        pool = _erstelle_mock_pool("tester", 2)
        office_manager = _erstelle_mock_office_manager({"tester": pool})
        on_log = MagicMock()

        # Worker 1 auf WORKING setzen, Worker 2 bleibt IDLE
        # Der IDLE-Worker erfuellt die aeussere Bedingung (workers=True),
        # dann sucht get_active_workers() den WORKING-Worker und setzt ihn IDLE
        working_worker = pool.workers["tester_1"]
        working_worker.status = WorkerStatus.WORKING
        working_worker.current_task_description = "Test laeuft"
        working_worker.current_task = "task-1"

        update_worker_status(
            office_manager, "tester", "idle", on_log
        )

        assert working_worker.status == WorkerStatus.IDLE, (
            f"Erwartet IDLE, erhalten: {working_worker.status}"
        )
        assert working_worker.current_task_description is None
        assert working_worker.current_task is None

    def test_idle_inkrementiert_tasks_completed(self):
        """Tasks_completed wird beim Idle-Setzen inkrementiert.

        Braucht mind. 2 Worker (1 IDLE + 1 WORKING), damit die
        Idle-Pfad-Bedingung erfuellt wird.
        """
        pool = _erstelle_mock_pool("coder", 2)
        office_manager = _erstelle_mock_office_manager({"coder": pool})
        on_log = MagicMock()

        worker = pool.workers["coder_1"]
        worker.status = WorkerStatus.WORKING
        worker.tasks_completed = 5

        update_worker_status(
            office_manager, "coder", "idle", on_log
        )

        assert worker.tasks_completed == 6, (
            f"Erwartet tasks_completed=6, erhalten: {worker.tasks_completed}"
        )

    def test_log_callback_enthaelt_task_completed(self):
        """Log-Callback wird mit event 'task_completed' bei idle aufgerufen."""
        pool = _erstelle_mock_pool("designer", 1)
        office_manager = _erstelle_mock_office_manager({"designer": pool})
        on_log = MagicMock()

        pool.workers["designer_1"].status = WorkerStatus.WORKING

        update_worker_status(
            office_manager, "designer", "idle", on_log
        )

        on_log.assert_called()
        for aufruf in on_log.call_args_list:
            args = aufruf[0]
            if args[1] == "WorkerStatus":
                daten = json.loads(args[2])
                assert daten["event"] == "task_completed"
                break

    def test_kein_aktiver_worker_kein_fehler(self):
        """Wenn kein aktiver Worker vorhanden, passiert nichts."""
        pool = _erstelle_mock_pool("security", 1)
        office_manager = _erstelle_mock_office_manager({"security": pool})
        on_log = MagicMock()

        # Alle Worker sind bereits IDLE
        update_worker_status(
            office_manager, "security", "idle", on_log
        )
        # Kein WorkerStatus-Log (fruehe Rueckkehr)


class TestUpdateWorkerStatusFehler:
    """Tests fuer Fehlerbehandlung in update_worker_status."""

    def test_unbekanntes_office_kein_crash(self):
        """Unbekanntes Office verursacht keinen Absturz."""
        office_manager = _erstelle_mock_office_manager({})
        on_log = MagicMock()

        # get_pool gibt None zurueck fuer unbekanntes Office
        update_worker_status(
            office_manager, "unbekannt", "working", on_log,
            task_description="Test"
        )
        # Kein Error-Log, weil pool None ist und frueh zurueckgekehrt wird

    def test_pool_none_kein_crash(self):
        """None Pool verursacht keinen Absturz."""
        office_manager = MagicMock()
        office_manager.get_pool = MagicMock(return_value=None)
        on_log = MagicMock()

        update_worker_status(
            office_manager, "coder", "working", on_log
        )
        # Sollte ohne Fehler zurueckkehren

    def test_exception_in_pool_wird_geloggt(self):
        """Exceptions im Pool werden als Error geloggt."""
        office_manager = MagicMock()
        office_manager.get_pool = MagicMock(side_effect=RuntimeError("Pool kaputt"))
        on_log = MagicMock()

        update_worker_status(
            office_manager, "coder", "working", on_log
        )

        # Error-Log sollte gesendet worden sein
        on_log.assert_called()
        fehler_aufruf = on_log.call_args[0]
        assert fehler_aufruf[0] == "System"
        assert fehler_aufruf[1] == "Error"
        assert "Pool kaputt" in fehler_aufruf[2]

    def test_agent_name_mapping_fuer_log(self):
        """Agent-Name im Log kommt aus dem AGENT_NAMES_MAPPING (Office->Name)."""
        pool = _erstelle_mock_pool("coder", 1)
        office_manager = _erstelle_mock_office_manager({"coder": pool})
        on_log = MagicMock()

        # Working-Pfad: setzt idle Worker auf working
        update_worker_status(
            office_manager, "coder", "working", on_log,
            task_description="Test"
        )

        on_log.assert_called()
        for aufruf in on_log.call_args_list:
            args = aufruf[0]
            if args[1] == "WorkerStatus":
                # AGENT_NAMES_MAPPING["coder"] == "Coder"
                assert args[0] == "Coder", (
                    f"Coder Agent-Name sollte 'Coder' sein, erhalten: {args[0]}"
                )
                break
