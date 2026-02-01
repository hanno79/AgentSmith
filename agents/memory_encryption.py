# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 01.02.2026
Version: 1.0
Beschreibung: Memory Agent Verschlüsselungs-Funktionen.
              Extrahiert aus memory_agent.py (Regel 1: Max 500 Zeilen)
"""

import os
import base64
from typing import Optional


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
    except Exception:
        return None


def encrypt_data(data: str) -> str:
    """Encrypt data if encryption is enabled."""
    fernet = _get_fernet()
    if fernet:
        encrypted = fernet.encrypt(data.encode())
        return f"ENCRYPTED:{base64.b64encode(encrypted).decode()}"
    return data


def decrypt_data(data: str) -> str:
    """Decrypt data if it's encrypted."""
    if data.startswith("ENCRYPTED:"):
        fernet = _get_fernet()
        if fernet:
            encrypted = base64.b64decode(data[10:])
            return fernet.decrypt(encrypted).decode()
    return data
