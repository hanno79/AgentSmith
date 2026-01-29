# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 24.01.2026
Version: 1.0
Beschreibung: Logger Utilities - JSON-basiertes Event-Logging für die Agenten-Crew.
"""

import json
import logging
from datetime import datetime
from logging.handlers import RotatingFileHandler

LOGFILE = "crew_log.jsonl"

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

def log_event(agent_name: str, action: str, content: str):
    """Schreibt einen Logeintrag mit Zeitstempel in crew_log.jsonl."""
    # Safety Check: If content is not string, convert it
    if not isinstance(content, str):
        content = str(content)

    entry = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "agent": agent_name,
        "action": action,
        "content": content.strip()[:5000], # Limit content length
    }
    try:
        _logger.info(json.dumps(entry, ensure_ascii=False))
    except Exception as e:
        print(f"❌ LOG ERROR: {e}")
    
    # Optional: Print to console if needed (already handled by Rich in main, but good as backup)
    # print(f"[LOG] {entry['timestamp']} – {agent_name}: {action}")
