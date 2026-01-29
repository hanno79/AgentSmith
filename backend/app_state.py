# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 29.01.2026
Version: 1.0
Beschreibung: Zentrale App-Objekte für FastAPI-Router.
"""
# ÄNDERUNG 29.01.2026: Zentrale App-Objekte für Router-Splitting

import asyncio
from slowapi import Limiter
from slowapi.util import get_remote_address
from .orchestration_manager import OrchestrationManager

# ÄNDERUNG 25.01.2026: Konstante für Default max_retries
DEFAULT_MAX_RETRIES = 5

# ÄNDERUNG 29.01.2026: WebSocket Receive-Timeout (60 Sekunden)
WS_RECEIVE_TIMEOUT = 60.0


# Speicher für aktive WebSocket-Verbindungen
# ÄNDERUNG 29.01.2026: Thread-Safety mit asyncio.Lock für Verbindungsstabilität
class ConnectionManager:
    def __init__(self):
        self.active_connections: list = []
        self._lock = asyncio.Lock()

    async def connect(self, websocket):
        await websocket.accept()
        async with self._lock:
            self.active_connections.append(websocket)

    async def disconnect(self, websocket):
        """Async disconnect mit Lock-Schutz."""
        async with self._lock:
            try:
                self.active_connections.remove(websocket)
            except ValueError:
                pass  # Bereits getrennt

    async def broadcast(self, message: str):
        """Broadcast mit Error-Handling und Thread-Safety."""
        async with self._lock:
            connections = list(self.active_connections)

        dead_connections = []
        for connection in connections:
            try:
                await connection.send_text(message)
            except Exception as e:
                print(f"[WebSocket] Broadcast-Fehler, entferne tote Verbindung: {e}")
                dead_connections.append(connection)

        if dead_connections:
            async with self._lock:
                for dead in dead_connections:
                    try:
                        self.active_connections.remove(dead)
                    except ValueError:
                        pass  # Bereits entfernt


manager = OrchestrationManager()
ws_manager = ConnectionManager()
limiter = Limiter(key_func=get_remote_address)
