# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 14.02.2026
Version: 1.0
Beschreibung: Unit-Tests fuer backend/heartbeat_utils.py.
              Testet die run_with_heartbeat Funktion inkl. Timeout, Heartbeat-Sender
              und Fehlerbehandlung.
"""

import os
import sys
import json
import time
import threading
import unittest
from unittest.mock import MagicMock, patch, call

# Projekt-Root zum Python-Path hinzufuegen
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.heartbeat_utils import run_with_heartbeat


class TestRunWithHeartbeatErfolg:
    """Tests fuer erfolgreiche Ausfuehrung von run_with_heartbeat."""

    def test_funktion_gibt_ergebnis_zurueck(self):
        """Funktion wird ausgefuehrt und Ergebnis korrekt zurueckgegeben."""
        def einfache_funktion():
            return 42

        ergebnis = run_with_heartbeat(
            func=einfache_funktion,
            ui_log_callback=MagicMock(),
            agent_name="TestAgent",
            task_description="Testaufgabe",
            heartbeat_interval=1,
            timeout_seconds=10
        )
        assert ergebnis == 42, f"Erwartet: 42, Erhalten: {ergebnis}"

    def test_funktion_gibt_none_zurueck(self):
        """Funktion die None zurueckgibt wird korrekt behandelt."""
        def none_funktion():
            return None

        ergebnis = run_with_heartbeat(
            func=none_funktion,
            ui_log_callback=MagicMock(),
            agent_name="TestAgent",
            task_description="None-Aufgabe",
            heartbeat_interval=1,
            timeout_seconds=10
        )
        assert ergebnis is None, f"Erwartet: None, Erhalten: {ergebnis}"

    def test_funktion_gibt_komplexes_objekt_zurueck(self):
        """Funktion die ein Dictionary zurueckgibt funktioniert korrekt."""
        erwartetes_ergebnis = {"status": "ok", "items": [1, 2, 3]}

        def komplexe_funktion():
            return erwartetes_ergebnis

        ergebnis = run_with_heartbeat(
            func=komplexe_funktion,
            ui_log_callback=MagicMock(),
            agent_name="TestAgent",
            task_description="Komplexe Aufgabe",
            heartbeat_interval=1,
            timeout_seconds=10
        )
        assert ergebnis == erwartetes_ergebnis, (
            f"Erwartet: {erwartetes_ergebnis}, Erhalten: {ergebnis}"
        )

    def test_funktion_gibt_string_zurueck(self):
        """Funktion die einen String zurueckgibt wird korrekt behandelt."""
        def string_funktion():
            return "Ergebnis-Text"

        ergebnis = run_with_heartbeat(
            func=string_funktion,
            ui_log_callback=MagicMock(),
            agent_name="TestAgent",
            task_description="String-Aufgabe",
            heartbeat_interval=1,
            timeout_seconds=10
        )
        assert ergebnis == "Ergebnis-Text"


class TestRunWithHeartbeatTimeout:
    """Tests fuer Timeout-Verhalten von run_with_heartbeat."""

    def test_timeout_bei_langer_ausfuehrung(self):
        """TimeoutError wird geworfen wenn Funktion zu lange dauert."""
        def langsame_funktion():
            time.sleep(10)
            return "Niemals erreicht"

        try:
            run_with_heartbeat(
                func=langsame_funktion,
                ui_log_callback=MagicMock(),
                agent_name="TestAgent",
                task_description="Langsame Aufgabe",
                heartbeat_interval=1,
                timeout_seconds=1
            )
            assert False, "TimeoutError haette geworfen werden muessen"
        except TimeoutError as e:
            assert "1s" in str(e), f"Timeout-Meldung sollte Sekundenangabe enthalten: {e}"

    def test_timeout_fehlermeldung_enthaelt_sekunden(self):
        """TimeoutError-Nachricht enthaelt die konfigurierte Sekundenanzahl."""
        def blockierende_funktion():
            time.sleep(10)

        try:
            run_with_heartbeat(
                func=blockierende_funktion,
                ui_log_callback=MagicMock(),
                agent_name="TestAgent",
                task_description="Block-Aufgabe",
                heartbeat_interval=1,
                timeout_seconds=2
            )
            assert False, "TimeoutError erwartet"
        except TimeoutError as e:
            assert "2s" in str(e), f"Erwartet '2s' in Meldung, erhalten: {e}"


class TestRunWithHeartbeatFehler:
    """Tests fuer Fehlerbehandlung in run_with_heartbeat."""

    def test_exception_wird_weitergeleitet(self):
        """Exceptions aus der Funktion werden korrekt weitergeleitet."""
        def fehlerhafte_funktion():
            raise ValueError("Testfehler aus Funktion")

        try:
            run_with_heartbeat(
                func=fehlerhafte_funktion,
                ui_log_callback=MagicMock(),
                agent_name="TestAgent",
                task_description="Fehler-Aufgabe",
                heartbeat_interval=1,
                timeout_seconds=10
            )
            assert False, "ValueError haette geworfen werden muessen"
        except ValueError as e:
            assert "Testfehler aus Funktion" in str(e)

    def test_runtime_error_wird_weitergeleitet(self):
        """RuntimeError aus der Funktion wird korrekt behandelt."""
        def runtime_fehler():
            raise RuntimeError("Kritischer Fehler")

        try:
            run_with_heartbeat(
                func=runtime_fehler,
                ui_log_callback=MagicMock(),
                agent_name="TestAgent",
                task_description="Runtime-Fehler",
                heartbeat_interval=1,
                timeout_seconds=10
            )
            assert False, "RuntimeError erwartet"
        except RuntimeError as e:
            assert "Kritischer Fehler" in str(e)

    def test_type_error_wird_weitergeleitet(self):
        """TypeError wird korrekt durchgereicht."""
        def typ_fehler():
            raise TypeError("Falscher Typ")

        try:
            run_with_heartbeat(
                func=typ_fehler,
                ui_log_callback=MagicMock(),
                agent_name="TestAgent",
                task_description="Typ-Fehler",
                heartbeat_interval=1,
                timeout_seconds=10
            )
            assert False, "TypeError erwartet"
        except TypeError as e:
            assert "Falscher Typ" in str(e)


class TestRunWithHeartbeatCallback:
    """Tests fuer Heartbeat-Callback-Verhalten."""

    def test_heartbeat_wird_gesendet(self):
        """Heartbeat-Callback wird bei laengerer Ausfuehrung aufgerufen."""
        callback = MagicMock()

        def verzoegerte_funktion():
            time.sleep(0.5)
            return "fertig"

        ergebnis = run_with_heartbeat(
            func=verzoegerte_funktion,
            ui_log_callback=callback,
            agent_name="TestAgent",
            task_description="Verzoegert",
            heartbeat_interval=0.2,
            timeout_seconds=5
        )
        assert ergebnis == "fertig"
        # Mindestens ein Heartbeat sollte gesendet worden sein
        # (0.5s Laufzeit bei 0.2s Intervall = ~2 Heartbeats)
        assert callback.call_count >= 1, (
            f"Mindestens 1 Heartbeat erwartet, erhalten: {callback.call_count}"
        )

    def test_heartbeat_callback_parameter(self):
        """Heartbeat-Callback wird mit korrekten Parametern aufgerufen."""
        callback = MagicMock()

        def verzoegerte_funktion():
            time.sleep(0.5)
            return "ok"

        run_with_heartbeat(
            func=verzoegerte_funktion,
            ui_log_callback=callback,
            agent_name="MeinAgent",
            task_description="Meine Aufgabe",
            heartbeat_interval=0.2,
            timeout_seconds=5
        )

        # Pruefe den ersten Heartbeat-Aufruf
        if callback.call_count > 0:
            erster_aufruf = callback.call_args_list[0]
            agent_arg = erster_aufruf[0][0]
            event_arg = erster_aufruf[0][1]
            message_arg = erster_aufruf[0][2]

            assert agent_arg == "MeinAgent", (
                f"Erwartet Agent 'MeinAgent', erhalten: {agent_arg}"
            )
            assert event_arg == "Heartbeat", (
                f"Erwartet Event 'Heartbeat', erhalten: {event_arg}"
            )
            # Message ist JSON
            daten = json.loads(message_arg)
            assert daten["status"] == "working"
            assert daten["task"] == "Meine Aufgabe"
            assert "elapsed_seconds" in daten
            assert "heartbeat_count" in daten

    def test_kein_heartbeat_bei_schneller_funktion(self):
        """Schnelle Funktion erzeugt keinen Heartbeat-Aufruf."""
        callback = MagicMock()

        def schnelle_funktion():
            return "sofort"

        ergebnis = run_with_heartbeat(
            func=schnelle_funktion,
            ui_log_callback=callback,
            agent_name="TestAgent",
            task_description="Schnell",
            heartbeat_interval=5,
            timeout_seconds=10
        )
        assert ergebnis == "sofort"
        # Bei sofortiger Rueckgabe wird kein Heartbeat gesendet
        assert callback.call_count == 0, (
            f"Kein Heartbeat bei schneller Funktion erwartet, erhalten: {callback.call_count}"
        )

    def test_none_callback_verursacht_keinen_fehler(self):
        """None als Callback verursacht keinen Fehler."""
        def test_funktion():
            time.sleep(0.3)
            return "ok"

        ergebnis = run_with_heartbeat(
            func=test_funktion,
            ui_log_callback=None,
            agent_name="TestAgent",
            task_description="Ohne Callback",
            heartbeat_interval=0.1,
            timeout_seconds=5
        )
        assert ergebnis == "ok"

    def test_callback_exception_wird_ignoriert(self):
        """Fehler im Callback werden ignoriert (Heartbeat-Fehler nicht kritisch)."""
        def fehlerhafter_callback(*args):
            raise ConnectionError("WebSocket getrennt")

        def test_funktion():
            time.sleep(0.5)
            return "trotzdem_ok"

        # Sollte nicht abstuerzen trotz Callback-Fehler
        ergebnis = run_with_heartbeat(
            func=test_funktion,
            ui_log_callback=fehlerhafter_callback,
            agent_name="TestAgent",
            task_description="Callback-Fehler",
            heartbeat_interval=0.2,
            timeout_seconds=5
        )
        assert ergebnis == "trotzdem_ok"


class TestRunWithHeartbeatHeartbeatInhalt:
    """Tests fuer den Inhalt der Heartbeat-Nachrichten."""

    def test_heartbeat_count_inkrementiert(self):
        """Heartbeat-Counter wird bei jedem Heartbeat inkrementiert."""
        callback = MagicMock()

        def verzoegerte_funktion():
            time.sleep(0.8)
            return "fertig"

        run_with_heartbeat(
            func=verzoegerte_funktion,
            ui_log_callback=callback,
            agent_name="TestAgent",
            task_description="Counter-Test",
            heartbeat_interval=0.2,
            timeout_seconds=5
        )

        if callback.call_count >= 2:
            # Pruefe dass heartbeat_count inkrementiert
            msg1 = json.loads(callback.call_args_list[0][0][2])
            msg2 = json.loads(callback.call_args_list[1][0][2])
            assert msg1["heartbeat_count"] == 1, (
                f"Erster Heartbeat sollte Count 1 haben, hat: {msg1['heartbeat_count']}"
            )
            assert msg2["heartbeat_count"] == 2, (
                f"Zweiter Heartbeat sollte Count 2 haben, hat: {msg2['heartbeat_count']}"
            )

    def test_elapsed_seconds_steigt(self):
        """Vergangene Sekunden steigen mit jedem Heartbeat."""
        callback = MagicMock()

        def verzoegerte_funktion():
            time.sleep(0.8)
            return "fertig"

        run_with_heartbeat(
            func=verzoegerte_funktion,
            ui_log_callback=callback,
            agent_name="TestAgent",
            task_description="Elapsed-Test",
            heartbeat_interval=0.2,
            timeout_seconds=5
        )

        if callback.call_count >= 2:
            msg1 = json.loads(callback.call_args_list[0][0][2])
            msg2 = json.loads(callback.call_args_list[-1][0][2])
            assert msg2["elapsed_seconds"] >= msg1["elapsed_seconds"], (
                "Vergangene Sekunden sollten nicht sinken"
            )
