# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 01.02.2026
Version: 1.0
Beschreibung: Memory Agent Verschlüsselungs-Funktionen.
              Extrahiert aus memory_agent.py (Regel 1: Max 500 Zeilen)
"""

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

# Check if encryption is enabled
MEMORY_ENCRYPTION_ENABLED = os.getenv("MEMORY_ENCRYPTION_ENABLED", "false").lower() == "true"
MEMORY_ENCRYPTION_KEY = os.getenv("MEMORY_ENCRYPTION_KEY", None)


def _get_fernet() -> Optional['Fernet']:
    """Get Fernet instance if encryption is enabled and key is set."""
    if not MEMORY_ENCRYPTION_ENABLED or not MEMORY_ENCRYPTION_KEY:
        return None
    try:
        from cryptography.fernet import Fernet
        # Ensure key is properly formatted (base64 32-byte key)
        key = MEMORY_ENCRYPTION_KEY.encode() if isinstance(MEMORY_ENCRYPTION_KEY, str) else MEMORY_ENCRYPTION_KEY
        return Fernet(key)
    except ImportError as e:
        logger.error(
            "Fernet-Instanz konnte nicht erstellt werden: cryptography-Modul fehlt oder ist fehlerhaft. "
            "MEMORY_ENCRYPTION_KEY ist gesetzt, aber Abhängigkeit nicht verfügbar: %s",
            e,
            exc_info=True,
        )
        return None
    except Exception as e:
        logger.error(
            "Fernet-Instanz konnte nicht erstellt werden: MEMORY_ENCRYPTION_KEY ungültig oder falsches Format "
            "(erwartet: base64-codierter 32-Byte-Schlüssel). Fehler: %s",
            e,
            exc_info=True,
        )
        return None


def encrypt_data(data: str) -> str:
    """Encrypt data if encryption is enabled. Fernet.encrypt returns base64 bytes; no extra encoding."""
    fernet = _get_fernet()
    if fernet:
        encrypted_bytes = fernet.encrypt(data.encode())
        return f"ENCRYPTED:{encrypted_bytes.decode()}"
    return data


def decrypt_data(data: str) -> str:
    """Decrypt data if it's encrypted. Payload after ENCRYPTED: is Fernet base64; pass as bytes to decrypt."""
    if data.startswith("ENCRYPTED:"):
        fernet = _get_fernet()
        if fernet:
            payload = data[10:].encode()
            return fernet.decrypt(payload).decode()
    return data
