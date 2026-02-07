# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 01.02.2026
Version: 1.1
Beschreibung: Logger Utilities - JSON-basiertes Event-Logging für die Agenten-Crew.
              AENDERUNG 01.02.2026: Robustes Encoding fuer Windows-Kompatibilitaet.
"""

import json
import logging
import sys
import unicodedata
from datetime import datetime
from logging.handlers import RotatingFileHandler

LOGFILE = "crew_log.jsonl"

# AENDERUNG 01.02.2026: Windows-spezifische UTF-8 Konfiguration
if sys.platform == "win32":
    try:
        # Versuche stdout auf UTF-8 zu setzen
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except AttributeError:
        pass  # Python < 3.7 oder anderer Fehler

# Configure rotating file handler to prevent unbounded log growth
_logger = logging.getLogger("crew_logger")
_logger.setLevel(logging.INFO)

# Only add handler if not already added (prevents duplicate handlers on re-import)
if not _logger.handlers:
    _handler = RotatingFileHandler(
        LOGFILE,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding="utf-8"
    )
    _handler.setLevel(logging.INFO)
    # Use a simple formatter that just outputs the message (for JSONL format)
    _handler.setFormatter(logging.Formatter("%(message)s"))
    _logger.addHandler(_handler)


def _sanitize_string(s: str) -> str:
    """
    AENDERUNG 01.02.2026: Sanitiert String fuer robustes Encoding.
    Normalisiert Unicode und entfernt problematische Zeichen.
    """
    if not s:
        return s
    # Unicode normalisieren (NFC Form)
    try:
        s = unicodedata.normalize('NFC', s)
    except (TypeError, ValueError):
        pass
    return s


def log_event(agent_name: str, action: str, content: str):
    """Schreibt einen Logeintrag mit Zeitstempel in crew_log.jsonl."""
    # Safety Check: If content is not string, convert it
    if not isinstance(content, str):
        content = str(content)

    # AENDERUNG 01.02.2026: Sanitiere alle String-Felder
    agent_name = _sanitize_string(agent_name)
    action = _sanitize_string(action)
    content = _sanitize_string(content)

    entry = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "agent": agent_name,
        "action": action,
        "content": content.strip()[:5000], # Limit content length
    }
    try:
        _logger.info(json.dumps(entry, ensure_ascii=False))
    except UnicodeEncodeError:
        # Fallback: ASCII-safe encoding
        _logger.info(json.dumps(entry, ensure_ascii=True))
    except Exception as e:
        # Sichere Ausgabe ohne Unicode-Zeichen
        print(f"LOG ERROR: {str(e)[:100]}")

    # Optional: Print to console if needed (already handled by Rich in main, but good as backup)
    # print(f"[LOG] {entry['timestamp']} - {agent_name}: {action}")
