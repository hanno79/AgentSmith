# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 14.02.2026
Version: 1.0
Beschreibung: Unit-Tests fuer backend/session_utils.py.
              Testet die Lazy-Load Funktion get_session_manager_instance()
              inkl. Caching, Fehlerbehandlung und Singleton-Verhalten.
"""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# Projekt-Root zum Python-Path hinzufuegen
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import backend.session_utils as session_utils_modul
from backend.session_utils import get_session_manager_instance


class TestGetSessionManagerInstance:
    """Tests fuer die Lazy-Load Funktion get_session_manager_instance."""

    def setup_method(self):
        """Setzt den Modul-Level Cache vor jedem Test zurueck."""
        session_utils_modul._session_manager = None

    def test_gibt_session_manager_zurueck(self):
        """Funktion gibt eine SessionManager-Instanz zurueck."""
        mock_sm = MagicMock()

        with patch("backend.session_manager.get_session_manager", return_value=mock_sm):
            ergebnis = get_session_manager_instance()

            assert ergebnis is mock_sm, (
                f"Erwartet Mock-SessionManager, erhalten: {ergebnis}"
            )

    def test_lazy_load_wird_nur_einmal_aufgerufen(self):
        """Der Session Manager wird nur beim ersten Aufruf geladen (Lazy-Load)."""
        mock_sm = MagicMock()

        with patch("backend.session_manager.get_session_manager", return_value=mock_sm) as mock_getter:
            # Erster Aufruf: laedt den Manager
            ergebnis1 = get_session_manager_instance()
            # Zweiter Aufruf: nutzt den Cache
            ergebnis2 = get_session_manager_instance()

            assert ergebnis1 is ergebnis2, (
                "Zweiter Aufruf sollte dieselbe Instanz zurueckgeben"
            )

    def test_fehler_gibt_none_zurueck(self):
        """Beliebige Exception beim Laden gibt None zurueck."""
        with patch(
            "backend.session_manager.get_session_manager",
            side_effect=RuntimeError("Initialisierung fehlgeschlagen")
        ):
            ergebnis = get_session_manager_instance()

            assert ergebnis is None, (
                "Bei RuntimeError sollte None zurueckgegeben werden"
            )

    def test_erneuter_versuch_nach_fehler(self):
        """Nach einem fehlgeschlagenen Laden wird beim naechsten Aufruf erneut versucht."""
        mock_sm = MagicMock()

        # Erster Aufruf: Fehler
        with patch(
            "backend.session_manager.get_session_manager",
            side_effect=RuntimeError("Fehler")
        ):
            ergebnis1 = get_session_manager_instance()
            assert ergebnis1 is None

        # Cache zuruecksetzen da Fehler den Cache nicht setzt
        session_utils_modul._session_manager = None

        # Zweiter Aufruf: Erfolg
        with patch("backend.session_manager.get_session_manager", return_value=mock_sm):
            ergebnis2 = get_session_manager_instance()
            assert ergebnis2 is mock_sm, (
                "Nach Fehler-Recovery sollte der Manager zurueckgegeben werden"
            )

    def test_log_event_bei_fehler(self):
        """Bei Fehler wird log_event aufgerufen."""
        with patch(
            "backend.session_manager.get_session_manager",
            side_effect=ValueError("Konfigurations-Fehler")
        ):
            with patch.object(session_utils_modul, "log_event") as mock_log:
                get_session_manager_instance()

                mock_log.assert_called_once()
                aufruf_args = mock_log.call_args[0]
                assert aufruf_args[0] == "API"
                assert aufruf_args[1] == "Error"
                assert "konnte nicht geladen werden" in aufruf_args[2]
                assert "Konfigurations-Fehler" in aufruf_args[2]


class TestSessionUtilsModulVariable:
    """Tests fuer die Modul-Level Variable _session_manager."""

    def setup_method(self):
        """Setzt den Modul-Level Cache vor jedem Test zurueck."""
        session_utils_modul._session_manager = None

    def test_initial_none(self):
        """_session_manager ist initial None (nach Reset)."""
        assert session_utils_modul._session_manager is None

    def test_wird_nach_erfolgreichem_laden_gesetzt(self):
        """_session_manager wird nach erfolgreichem Laden auf die Instanz gesetzt."""
        mock_sm = MagicMock()

        with patch("backend.session_manager.get_session_manager", return_value=mock_sm):
            get_session_manager_instance()

            assert session_utils_modul._session_manager is mock_sm

    def test_bleibt_none_nach_fehler(self):
        """_session_manager bleibt None nach einem Fehler."""
        with patch(
            "backend.session_manager.get_session_manager",
            side_effect=Exception("Fehler")
        ):
            get_session_manager_instance()

            assert session_utils_modul._session_manager is None

    def test_cached_instanz_wird_wiederverwendet(self):
        """Einmal gesetzt, wird die gecachte Instanz wiederverwendet."""
        mock_sm = MagicMock()
        session_utils_modul._session_manager = mock_sm

        # Kein Mock noetig - der Cache verhindert den Import
        ergebnis = get_session_manager_instance()

        assert ergebnis is mock_sm, (
            "Gecachte Instanz sollte direkt zurueckgegeben werden"
        )

    def test_manuell_gesetzter_cache_wird_respektiert(self):
        """Manuell gesetzter _session_manager wird von der Funktion respektiert."""
        sentinel = object()
        session_utils_modul._session_manager = sentinel

        ergebnis = get_session_manager_instance()

        assert ergebnis is sentinel, (
            "Manuell gesetzter Cache-Wert sollte zurueckgegeben werden"
        )


class TestSessionUtilsIntegration:
    """Integrationstests fuer session_utils mit echtem SessionManager."""

    def setup_method(self):
        """Setzt den Modul-Level Cache vor jedem Test zurueck."""
        session_utils_modul._session_manager = None

    def test_echter_session_manager_wird_geladen(self):
        """Der echte SessionManager kann ueber die Funktion geladen werden."""
        # SessionManager Singleton zuruecksetzen fuer sauberen Test
        from backend.session_manager import SessionManager
        original_instance = SessionManager._instance
        original_initialized = getattr(SessionManager, '_initialized', False)

        try:
            SessionManager._instance = None

            ergebnis = get_session_manager_instance()

            assert ergebnis is not None, (
                "Echter SessionManager sollte geladen werden koennen"
            )
            # Pruefe dass es ein SessionManager ist
            assert hasattr(ergebnis, 'current_session'), (
                "Ergebnis sollte current_session Attribut haben"
            )
        finally:
            # Singleton wiederherstellen
            SessionManager._instance = original_instance

    def test_singleton_verhalten_ueber_cache(self):
        """Mehrfache Aufrufe geben dieselbe Instanz zurueck (Singleton+Cache)."""
        from backend.session_manager import SessionManager
        original_instance = SessionManager._instance

        try:
            SessionManager._instance = None

            ergebnis1 = get_session_manager_instance()
            ergebnis2 = get_session_manager_instance()

            assert ergebnis1 is ergebnis2, (
                "Beide Aufrufe sollten dieselbe Singleton-Instanz zurueckgeben"
            )
        finally:
            SessionManager._instance = original_instance

    def test_geladener_manager_hat_erwartete_attribute(self):
        """Geladener Manager hat die erwarteten Session-Attribute."""
        from backend.session_manager import SessionManager
        original_instance = SessionManager._instance

        try:
            SessionManager._instance = None

            ergebnis = get_session_manager_instance()

            assert ergebnis is not None
            assert hasattr(ergebnis, 'logs'), "Manager sollte logs haben"
            assert hasattr(ergebnis, 'agent_snapshots'), "Manager sollte agent_snapshots haben"
            assert "status" in ergebnis.current_session, (
                "current_session sollte 'status' Schluessel haben"
            )
        finally:
            SessionManager._instance = original_instance
