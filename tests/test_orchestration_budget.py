# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 14.02.2026
Version: 1.0
Beschreibung: Unit-Tests fuer backend/orchestration_budget.py.
              Testet set_current_agent, _get_current_tracking_context und Thread-Safety
              der globalen Budget-Tracking-Variablen.
"""

import threading

import pytest

import backend.orchestration_budget as budget_module
from backend.orchestration_budget import (
    set_current_agent,
    _get_current_tracking_context,
    _current_agent_name,
    _current_project_id,
    _budget_tracking_lock,
)


@pytest.fixture(autouse=True)
def reset_globals():
    """Setzt globale Budget-Tracking-Variablen vor und nach jedem Test zurueck."""
    budget_module._current_agent_name = "Unknown"
    budget_module._current_project_id = None
    yield
    budget_module._current_agent_name = "Unknown"
    budget_module._current_project_id = None


# =====================================================================
# TestSetCurrentAgent - Tests fuer set_current_agent()
# =====================================================================
class TestSetCurrentAgent:
    """Tests fuer die Funktion set_current_agent."""

    def test_setzt_agent_name_korrekt(self):
        """Agent-Name wird korrekt gesetzt."""
        set_current_agent("Planner")
        assert budget_module._current_agent_name == "Planner"

    def test_setzt_project_id_wenn_angegeben(self):
        """Project-ID wird gesetzt wenn als Parameter uebergeben."""
        set_current_agent("Coder", project_id="projekt_123")
        assert budget_module._current_project_id == "projekt_123"

    def test_project_id_none_laesst_altes_unveraendert(self):
        """Bei project_id=None bleibt der vorherige Wert erhalten."""
        set_current_agent("Coder", project_id="projekt_abc")
        set_current_agent("Reviewer")  # project_id=None (Standard)
        # Agent-Name wurde ueberschrieben
        assert budget_module._current_agent_name == "Reviewer"
        # Project-ID bleibt unveraendert
        assert budget_module._current_project_id == "projekt_abc"

    def test_mehrfaches_setzen_ueberschreibt_agent_name(self):
        """Mehrmaliges Aufrufen ueberschreibt den Agent-Namen korrekt."""
        set_current_agent("Planner")
        set_current_agent("Coder")
        set_current_agent("Reviewer")
        assert budget_module._current_agent_name == "Reviewer"

    def test_mehrfaches_setzen_ueberschreibt_project_id(self):
        """Mehrmaliges Aufrufen ueberschreibt die Project-ID korrekt."""
        set_current_agent("Agent1", project_id="id_1")
        set_current_agent("Agent2", project_id="id_2")
        assert budget_module._current_project_id == "id_2"

    def test_leerer_string_als_agent_name(self):
        """Leerer String als Agent-Name funktioniert ohne Fehler."""
        set_current_agent("")
        assert budget_module._current_agent_name == ""

    def test_langer_agent_name(self):
        """Langer Agent-Name wird korrekt gespeichert."""
        langer_name = "A" * 500
        set_current_agent(langer_name)
        assert budget_module._current_agent_name == langer_name

    def test_sonderzeichen_in_agent_name(self):
        """Sonderzeichen im Agent-Namen werden korrekt gespeichert."""
        name_mit_sonderzeichen = "Agent-Coder_v2 (Hauptmodul)"
        set_current_agent(name_mit_sonderzeichen)
        assert budget_module._current_agent_name == name_mit_sonderzeichen

    def test_unicode_in_agent_name(self):
        """Unicode-Zeichen im Agent-Namen werden korrekt gespeichert."""
        unicode_name = "Prüf-Agent_München"
        set_current_agent(unicode_name)
        assert budget_module._current_agent_name == unicode_name

    def test_project_id_explizit_none_nach_wert(self):
        """Explizites project_id=None aendert bestehenden Wert NICHT."""
        set_current_agent("Agent", project_id="mein_projekt")
        set_current_agent("Agent2", project_id=None)
        assert budget_module._current_project_id == "mein_projekt"

    def test_leerer_string_als_project_id(self):
        """Leerer String als Project-ID wird gesetzt (ist nicht None)."""
        set_current_agent("Agent", project_id="")
        assert budget_module._current_project_id == ""

    def test_project_id_ueberschreibt_leeren_string(self):
        """Ein neuer Project-ID-Wert ueberschreibt einen leeren String."""
        set_current_agent("Agent", project_id="")
        set_current_agent("Agent", project_id="neues_projekt")
        assert budget_module._current_project_id == "neues_projekt"


# =====================================================================
# TestGetCurrentTrackingContext - Tests fuer _get_current_tracking_context()
# =====================================================================
class TestGetCurrentTrackingContext:
    """Tests fuer die Funktion _get_current_tracking_context."""

    def test_gibt_tuple_zurueck(self):
        """Rueckgabewert ist ein Tuple."""
        ergebnis = _get_current_tracking_context()
        assert isinstance(ergebnis, tuple)

    def test_tuple_hat_zwei_elemente(self):
        """Tuple enthaelt genau zwei Elemente (agent_name, project_id)."""
        ergebnis = _get_current_tracking_context()
        assert len(ergebnis) == 2

    def test_default_werte(self):
        """Default-Werte sind ('Unknown', None) nach Reset."""
        agent_name, project_id = _get_current_tracking_context()
        assert agent_name == "Unknown", (
            f"Erwartet: 'Unknown', Erhalten: '{agent_name}' fuer agent_name"
        )
        assert project_id is None, (
            f"Erwartet: None, Erhalten: '{project_id}' fuer project_id"
        )

    def test_nach_set_current_agent_korrekte_werte(self):
        """Nach set_current_agent gibt _get_current_tracking_context die gesetzten Werte zurueck."""
        set_current_agent("TestAgent", project_id="test_projekt")
        agent_name, project_id = _get_current_tracking_context()
        assert agent_name == "TestAgent"
        assert project_id == "test_projekt"

    def test_nur_agent_name_gesetzt(self):
        """Wenn nur agent_name gesetzt, bleibt project_id auf None."""
        set_current_agent("NurName")
        agent_name, project_id = _get_current_tracking_context()
        assert agent_name == "NurName"
        assert project_id is None

    def test_konsistenz_bei_mehrfachem_aufruf(self):
        """Mehrfacher Aufruf ohne Aenderung liefert immer gleiche Werte."""
        set_current_agent("Stabil", project_id="fix_id")
        ergebnis_1 = _get_current_tracking_context()
        ergebnis_2 = _get_current_tracking_context()
        ergebnis_3 = _get_current_tracking_context()
        assert ergebnis_1 == ergebnis_2 == ergebnis_3

    def test_spiegelt_letzten_set_aufruf_wider(self):
        """Gibt immer die Werte des letzten set_current_agent Aufrufs zurueck."""
        set_current_agent("Erster", project_id="p1")
        set_current_agent("Zweiter", project_id="p2")
        agent_name, project_id = _get_current_tracking_context()
        assert agent_name == "Zweiter"
        assert project_id == "p2"


# =====================================================================
# TestThreadSafety - Thread-Safety Tests
# =====================================================================
class TestThreadSafety:
    """Tests fuer Thread-Safety der Budget-Tracking-Funktionen."""

    def test_paralleles_setzen_kein_crash(self):
        """Paralleles Setzen aus mehreren Threads verursacht keinen Crash."""
        fehler = []

        def setze_agent(name, pid):
            try:
                for _ in range(100):
                    set_current_agent(name, project_id=pid)
            except Exception as e:
                fehler.append(e)

        threads = [
            threading.Thread(target=setze_agent, args=(f"Agent_{i}", f"Projekt_{i}"))
            for i in range(10)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(fehler) == 0, (
            f"Erwartet: keine Fehler, Erhalten: {len(fehler)} Fehler: {fehler}"
        )

    def test_paralleles_lesen_kein_crash(self):
        """Paralleles Lesen aus mehreren Threads verursacht keinen Crash."""
        set_current_agent("LeseTest", project_id="lese_projekt")
        fehler = []

        def lese_kontext():
            try:
                for _ in range(100):
                    ergebnis = _get_current_tracking_context()
                    assert isinstance(ergebnis, tuple)
                    assert len(ergebnis) == 2
            except Exception as e:
                fehler.append(e)

        threads = [threading.Thread(target=lese_kontext) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(fehler) == 0, (
            f"Erwartet: keine Fehler, Erhalten: {len(fehler)} Fehler: {fehler}"
        )

    def test_gleichzeitiges_lesen_und_schreiben(self):
        """Gleichzeitiges Lesen und Schreiben verursacht keinen Crash."""
        fehler = []

        def schreibe():
            try:
                for i in range(200):
                    set_current_agent(f"Schreiber_{i}", project_id=f"p_{i}")
            except Exception as e:
                fehler.append(e)

        def lese():
            try:
                for _ in range(200):
                    name, pid = _get_current_tracking_context()
                    # Werte muessen Strings bzw. None/String sein
                    assert isinstance(name, str)
                    assert pid is None or isinstance(pid, str)
            except Exception as e:
                fehler.append(e)

        schreib_threads = [threading.Thread(target=schreibe) for _ in range(5)]
        lese_threads = [threading.Thread(target=lese) for _ in range(5)]

        alle_threads = schreib_threads + lese_threads
        for t in alle_threads:
            t.start()
        for t in alle_threads:
            t.join()

        assert len(fehler) == 0, (
            f"Erwartet: keine Fehler bei parallelem Lesen/Schreiben, "
            f"Erhalten: {len(fehler)} Fehler: {fehler}"
        )

    def test_barrier_synchronisiertes_setzen(self):
        """Threads setzen gleichzeitig via Barrier - am Ende liegt ein konsistenter Wert vor."""
        anzahl_threads = 5
        barrier = threading.Barrier(anzahl_threads)
        gesetzte_werte = []
        fehler = []

        def setze_synchronisiert(idx):
            try:
                name = f"BarrierAgent_{idx}"
                pid = f"BarrierProjekt_{idx}"
                # Alle Threads warten an der Barrier
                barrier.wait()
                # Alle setzen gleichzeitig
                set_current_agent(name, project_id=pid)
                gesetzte_werte.append((name, pid))
            except Exception as e:
                fehler.append(e)

        threads = [
            threading.Thread(target=setze_synchronisiert, args=(i,))
            for i in range(anzahl_threads)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(fehler) == 0, f"Fehler bei Barrier-Test: {fehler}"

        # Am Ende muss ein konsistenter Wert vorliegen (einer der gesetzten)
        endwert = _get_current_tracking_context()
        agent_name, project_id = endwert

        # Der Wert muss einer der gesetzten sein
        gueltige_namen = [f"BarrierAgent_{i}" for i in range(anzahl_threads)]
        assert agent_name in gueltige_namen, (
            f"Erwartet: einer von {gueltige_namen}, Erhalten: '{agent_name}'"
        )
        gueltige_pids = [f"BarrierProjekt_{i}" for i in range(anzahl_threads)]
        assert project_id in gueltige_pids, (
            f"Erwartet: einer von {gueltige_pids}, Erhalten: '{project_id}'"
        )

    def test_lock_ist_threading_lock(self):
        """Das Budget-Tracking-Lock ist ein threading.Lock Objekt."""
        assert isinstance(_budget_tracking_lock, type(threading.Lock()))

    def test_konsistenz_agent_und_project_nach_parallelem_setzen(self):
        """Nach parallelem Setzen gehoeren agent_name und project_id zusammen."""
        anzahl_threads = 8
        barrier = threading.Barrier(anzahl_threads)
        fehler = []

        def setze_paar(idx):
            try:
                barrier.wait()
                # Jeder Thread setzt immer ein zusammengehoeriges Paar
                set_current_agent(f"Konsistenz_{idx}", project_id=f"KProjekt_{idx}")
            except Exception as e:
                fehler.append(e)

        threads = [
            threading.Thread(target=setze_paar, args=(i,))
            for i in range(anzahl_threads)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(fehler) == 0, f"Fehler bei Konsistenz-Test: {fehler}"

        # Endwert pruefen: Name und ID muessen zum gleichen Index gehoeren
        agent_name, project_id = _get_current_tracking_context()
        # Extrahiere den Index aus dem Agent-Namen
        idx_aus_name = agent_name.split("_")[-1]
        erwartete_pid = f"KProjekt_{idx_aus_name}"
        assert project_id == erwartete_pid, (
            f"Inkonsistenz: agent_name='{agent_name}' aber project_id='{project_id}', "
            f"erwartet project_id='{erwartete_pid}'"
        )
