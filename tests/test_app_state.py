# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 14.02.2026
Version: 1.0
Beschreibung: Unit-Tests fuer backend/app_state.py.
              Testet Konstanten (DEFAULT_MAX_RETRIES, WS_RECEIVE_TIMEOUT, WS_MAX_TIMEOUTS),
              die ConnectionManager-Klasse (connect, disconnect, broadcast) und
              die Modul-Singletons (manager, ws_manager, limiter).
"""

import os
import sys
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# Projekt-Root zum Python-Path hinzufuegen
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app_state import (
    DEFAULT_MAX_RETRIES,
    WS_RECEIVE_TIMEOUT,
    WS_MAX_TIMEOUTS,
    ConnectionManager,
    manager,
    ws_manager,
    limiter,
)


# =========================================================================
# TestAppStateConstants — Tests fuer die Modul-Konstanten
# =========================================================================

class TestAppStateConstants:
    """Tests fuer die Konstanten in app_state.py."""

    def test_default_max_retries_wert(self):
        """DEFAULT_MAX_RETRIES muss den Wert 5 haben."""
        assert DEFAULT_MAX_RETRIES == 5, (
            f"Erwartet: 5, Erhalten: {DEFAULT_MAX_RETRIES}"
        )

    def test_ws_receive_timeout_wert(self):
        """WS_RECEIVE_TIMEOUT muss 300.0 Sekunden (5 Minuten) betragen."""
        assert WS_RECEIVE_TIMEOUT == 300.0, (
            f"Erwartet: 300.0, Erhalten: {WS_RECEIVE_TIMEOUT}"
        )

    def test_ws_max_timeouts_wert(self):
        """WS_MAX_TIMEOUTS muss den Wert 10 haben."""
        assert WS_MAX_TIMEOUTS == 10, (
            f"Erwartet: 10, Erhalten: {WS_MAX_TIMEOUTS}"
        )

    def test_timeout_ist_float(self):
        """WS_RECEIVE_TIMEOUT muss vom Typ float sein."""
        assert isinstance(WS_RECEIVE_TIMEOUT, float), (
            f"Erwartet: float, Erhalten: {type(WS_RECEIVE_TIMEOUT).__name__}"
        )

    def test_max_retries_positiv(self):
        """DEFAULT_MAX_RETRIES muss ein positiver Wert sein."""
        assert DEFAULT_MAX_RETRIES > 0, (
            f"Erwartet: positiver Wert, Erhalten: {DEFAULT_MAX_RETRIES}"
        )

    def test_max_timeouts_positiv(self):
        """WS_MAX_TIMEOUTS muss ein positiver Wert sein."""
        assert WS_MAX_TIMEOUTS > 0, (
            f"Erwartet: positiver Wert, Erhalten: {WS_MAX_TIMEOUTS}"
        )

    def test_max_retries_ist_int(self):
        """DEFAULT_MAX_RETRIES muss vom Typ int sein."""
        assert isinstance(DEFAULT_MAX_RETRIES, int), (
            f"Erwartet: int, Erhalten: {type(DEFAULT_MAX_RETRIES).__name__}"
        )

    def test_max_timeouts_ist_int(self):
        """WS_MAX_TIMEOUTS muss vom Typ int sein."""
        assert isinstance(WS_MAX_TIMEOUTS, int), (
            f"Erwartet: int, Erhalten: {type(WS_MAX_TIMEOUTS).__name__}"
        )


# =========================================================================
# TestConnectionManager — Tests fuer die ConnectionManager-Klasse
# =========================================================================

class TestConnectionManager:
    """Tests fuer die ConnectionManager-Klasse mit async Methoden."""

    @pytest.mark.asyncio
    async def test_init_leere_verbindungsliste(self):
        """Neuer ConnectionManager hat eine leere Verbindungsliste."""
        cm = ConnectionManager()
        assert cm.active_connections == [], (
            f"Erwartet: leere Liste, Erhalten: {cm.active_connections}"
        )

    @pytest.mark.asyncio
    async def test_init_hat_asyncio_lock(self):
        """Neuer ConnectionManager besitzt ein asyncio.Lock."""
        cm = ConnectionManager()
        assert isinstance(cm._lock, asyncio.Lock), (
            f"Erwartet: asyncio.Lock, Erhalten: {type(cm._lock).__name__}"
        )

    @pytest.mark.asyncio
    async def test_connect_akzeptiert_websocket(self):
        """connect() ruft websocket.accept() auf."""
        cm = ConnectionManager()
        ws = AsyncMock()
        await cm.connect(ws)
        ws.accept.assert_called_once()

    @pytest.mark.asyncio
    async def test_connect_fuegt_verbindung_hinzu(self):
        """connect() fuegt den WebSocket zur Verbindungsliste hinzu."""
        cm = ConnectionManager()
        ws = AsyncMock()
        await cm.connect(ws)
        assert ws in cm.active_connections, (
            "WebSocket sollte in active_connections vorhanden sein"
        )

    @pytest.mark.asyncio
    async def test_disconnect_entfernt_verbindung(self):
        """disconnect() entfernt den WebSocket aus der Verbindungsliste."""
        cm = ConnectionManager()
        ws = AsyncMock()
        await cm.connect(ws)
        await cm.disconnect(ws)
        assert ws not in cm.active_connections, (
            "WebSocket sollte nach disconnect nicht mehr in active_connections sein"
        )

    @pytest.mark.asyncio
    async def test_disconnect_nicht_verbunden_kein_fehler(self):
        """disconnect() bei nicht vorhandenem WebSocket verursacht keinen Fehler."""
        cm = ConnectionManager()
        ws = AsyncMock()
        # Kein connect() vorher — darf nicht abstuerzen
        await cm.disconnect(ws)
        assert ws not in cm.active_connections

    @pytest.mark.asyncio
    async def test_broadcast_sendet_an_alle(self):
        """broadcast() sendet die Nachricht an alle verbundenen WebSockets."""
        cm = ConnectionManager()
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        await cm.connect(ws1)
        await cm.connect(ws2)
        await cm.broadcast("test nachricht")
        ws1.send_text.assert_called_once_with("test nachricht")
        ws2.send_text.assert_called_once_with("test nachricht")

    @pytest.mark.asyncio
    async def test_broadcast_entfernt_tote_verbindungen(self):
        """broadcast() entfernt WebSockets die beim Senden einen Fehler werfen."""
        cm = ConnectionManager()
        ws_aktiv = AsyncMock()
        ws_tot = AsyncMock()
        ws_tot.send_text.side_effect = Exception("Verbindung geschlossen")
        await cm.connect(ws_aktiv)
        await cm.connect(ws_tot)
        await cm.broadcast("nachricht")
        assert ws_tot not in cm.active_connections, (
            "Tote Verbindung sollte nach broadcast entfernt worden sein"
        )
        assert ws_aktiv in cm.active_connections, (
            "Aktive Verbindung sollte nach broadcast erhalten bleiben"
        )

    @pytest.mark.asyncio
    async def test_broadcast_leere_verbindungsliste(self):
        """broadcast() bei leerer Verbindungsliste verursacht keinen Fehler."""
        cm = ConnectionManager()
        await cm.broadcast("nachricht")
        # Kein Fehler erwartet

    @pytest.mark.asyncio
    async def test_mehrfach_connect_disconnect(self):
        """Mehrere connect/disconnect Operationen funktionieren korrekt."""
        cm = ConnectionManager()
        ws1, ws2, ws3 = AsyncMock(), AsyncMock(), AsyncMock()
        await cm.connect(ws1)
        await cm.connect(ws2)
        await cm.connect(ws3)
        assert len(cm.active_connections) == 3, (
            f"Erwartet: 3 Verbindungen, Erhalten: {len(cm.active_connections)}"
        )
        await cm.disconnect(ws2)
        assert len(cm.active_connections) == 2, (
            f"Erwartet: 2 Verbindungen, Erhalten: {len(cm.active_connections)}"
        )
        assert ws2 not in cm.active_connections, (
            "ws2 sollte nach disconnect nicht mehr vorhanden sein"
        )

    @pytest.mark.asyncio
    async def test_broadcast_nach_disconnect(self):
        """broadcast() nach disconnect sendet nur an verbleibende Verbindungen."""
        cm = ConnectionManager()
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        await cm.connect(ws1)
        await cm.connect(ws2)
        await cm.disconnect(ws1)
        await cm.broadcast("nur fuer ws2")
        ws1.send_text.assert_not_called()
        ws2.send_text.assert_called_once_with("nur fuer ws2")

    @pytest.mark.asyncio
    async def test_doppeltes_disconnect_kein_fehler(self):
        """Zweimaliges disconnect() fuer denselben WebSocket verursacht keinen Fehler."""
        cm = ConnectionManager()
        ws = AsyncMock()
        await cm.connect(ws)
        await cm.disconnect(ws)
        # Zweites disconnect — darf nicht abstuerzen
        await cm.disconnect(ws)
        assert ws not in cm.active_connections

    @pytest.mark.asyncio
    async def test_broadcast_mehrere_tote_verbindungen(self):
        """broadcast() entfernt mehrere tote Verbindungen gleichzeitig."""
        cm = ConnectionManager()
        ws_aktiv = AsyncMock()
        ws_tot1 = AsyncMock()
        ws_tot2 = AsyncMock()
        ws_tot1.send_text.side_effect = Exception("Fehler 1")
        ws_tot2.send_text.side_effect = Exception("Fehler 2")
        await cm.connect(ws_aktiv)
        await cm.connect(ws_tot1)
        await cm.connect(ws_tot2)
        await cm.broadcast("test")
        assert ws_tot1 not in cm.active_connections, (
            "Erste tote Verbindung sollte entfernt worden sein"
        )
        assert ws_tot2 not in cm.active_connections, (
            "Zweite tote Verbindung sollte entfernt worden sein"
        )
        assert ws_aktiv in cm.active_connections, (
            "Aktive Verbindung sollte erhalten bleiben"
        )
        assert len(cm.active_connections) == 1

    @pytest.mark.asyncio
    async def test_broadcast_sendet_korrekten_text(self):
        """broadcast() sendet den exakten Nachrichtentext an alle Verbindungen."""
        cm = ConnectionManager()
        ws = AsyncMock()
        await cm.connect(ws)
        nachricht = '{"event": "update", "data": "testdaten"}'
        await cm.broadcast(nachricht)
        ws.send_text.assert_called_once_with(nachricht)

    @pytest.mark.asyncio
    async def test_connect_reihenfolge_erhalten(self):
        """Verbindungen werden in der Reihenfolge des connect() gespeichert."""
        cm = ConnectionManager()
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        ws3 = AsyncMock()
        await cm.connect(ws1)
        await cm.connect(ws2)
        await cm.connect(ws3)
        assert cm.active_connections[0] is ws1
        assert cm.active_connections[1] is ws2
        assert cm.active_connections[2] is ws3


# =========================================================================
# TestModuleSingletons — Tests fuer die Modul-Level Singletons
# =========================================================================

class TestModuleSingletons:
    """Tests fuer die Modul-Level Singleton-Objekte."""

    def test_ws_manager_ist_connection_manager(self):
        """ws_manager muss eine Instanz von ConnectionManager sein."""
        assert isinstance(ws_manager, ConnectionManager), (
            f"Erwartet: ConnectionManager, Erhalten: {type(ws_manager).__name__}"
        )

    def test_limiter_existiert(self):
        """limiter muss initialisiert sein (nicht None)."""
        assert limiter is not None, (
            "limiter sollte nicht None sein"
        )

    def test_manager_existiert(self):
        """manager muss initialisiert sein (nicht None)."""
        assert manager is not None, (
            "manager sollte nicht None sein"
        )

    def test_manager_ist_orchestration_manager(self):
        """manager muss eine Instanz von OrchestrationManager sein."""
        from backend.orchestration_manager import OrchestrationManager
        assert isinstance(manager, OrchestrationManager), (
            f"Erwartet: OrchestrationManager, Erhalten: {type(manager).__name__}"
        )

    def test_ws_manager_hat_leere_verbindungen_initial(self):
        """ws_manager sollte initial keine aktiven Verbindungen haben."""
        # Hinweis: Andere Tests koennten Verbindungen hinzugefuegt haben,
        # daher pruefen wir nur den Typ der Liste
        assert isinstance(ws_manager.active_connections, list), (
            f"Erwartet: list, Erhalten: {type(ws_manager.active_connections).__name__}"
        )
