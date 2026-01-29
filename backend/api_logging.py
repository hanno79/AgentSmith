# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 29.01.2026
Version: 1.0
Beschreibung: Einfaches API-Logging für Endpunkte.
"""
# ÄNDERUNG 29.01.2026: log_event für Router-Splitting zentralisiert


def log_event(agent: str, event: str, message: str):
    """Logged ein Event in die Konsole und optional ins UI."""
    print(f"[{agent}] {event}: {message}")
