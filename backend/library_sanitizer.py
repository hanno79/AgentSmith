# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 07.02.2026
Version: 1.0
Beschreibung: Sanitizer-Funktionen fuer Library-Archivierung.
              Extrahiert aus library_manager.py (Regel 1: Max 500 Zeilen)
              Enthaelt: Pfad-Anonymisierung, Secret-Redaktion, Token-Neuberechnung
"""

import re
import json
import copy
import hashlib
import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


def hash_text(text: str) -> str:
    """Erzeugt einen kurzen SHA256-Hash eines Textes."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:10]


def sanitize_paths(text: str) -> str:
    """Anonymisiert lokale Dateipfade (Windows + Unix)."""
    # Windows User-Pfade anonymisieren
    text = re.sub(r"([A-Za-z]:\\Users\\)([^\\]+)(\\[^\s\"']*)", r"\1<USER>\3", text)
    text = re.sub(r"([A-Za-z]:/Users/)([^/]+)(/[^\s\"']*)", r"\1<USER>\3", text)

    def _windows_replacer(match: re.Match) -> str:
        path = match.group(0)
        return path if "<USER>" in path else "<LOCAL_PATH>"

    text = re.sub(r"[A-Za-z]:[\\/][^\s\"']+", _windows_replacer, text)

    # Unix User-Pfade anonymisieren
    text = re.sub(r"(/(?:Users|home)/)([^/]+)(/[^\s\"']*)", r"\1<USER>\3", text)

    def _unix_replacer(match: re.Match) -> str:
        path = match.group(0)
        return path if "<USER>" in path else "<LOCAL_PATH>"

    text = re.sub(r"/(?:Users|home|var|tmp|private|opt|etc|usr|root|Volumes)[^\s\"']+", _unix_replacer, text)
    return text


def redact_stack_traces(text: str) -> str:
    """Redigiert Python- und JavaScript-Stacktraces."""
    if "Traceback (most recent call last)" in text:
        trace_id = hash_text(text)
        return re.sub(
            r"Traceback \(most recent call last\):[\s\S]*",
            f"[STACK_TRACE_REDACTED:{trace_id}]",
            text
        )

    stack_line_re = re.compile(r"^\s*at .+\(.+:\d+:\d+\)\s*$", re.MULTILINE)
    if stack_line_re.search(text):
        trace_id = hash_text(text)
        return stack_line_re.sub(f"[STACK_TRACE_REDACTED:{trace_id}]", text)
    return text


def sanitize_text(text: str) -> str:
    """Sanitisiert einen Text: Pfade, Secrets, Stacktraces."""
    sanitized = text

    # .env Inhalte redigieren
    sanitized = re.sub(
        r"(### FILENAME: \.env)([\s\S]*?)(?=### FILENAME:|\Z)",
        r"\1\n[ENV_DATEI_REDAKTIERT]\n",
        sanitized
    )

    # Geheimnisse anonymisieren
    sanitized = re.sub(r"(?i)(DART_TOKEN|SECRET_KEY)\s*=\s*([^\r\n]+)", r"\1=<REDACTED_SECRET>", sanitized)
    sanitized = re.sub(
        r"(app\.config\[['\"]SECRET_KEY['\"]\]\s*=\s*)['\"][^'\"]+['\"]",
        r"\1'<REDACTED_SECRET>'",
        sanitized
    )
    sanitized = re.sub(
        r"os\.environ\.get\(['\"]SECRET_KEY['\"],\s*['\"][^'\"]+['\"]\)",
        "os.environ.get('SECRET_KEY')",
        sanitized
    )

    # User-IDs anonymisieren
    sanitized = re.sub(r'("user_id"\s*:\s*")[^"]+(")', r'\1<REDACTED_USER>\2', sanitized)
    sanitized = re.sub(r"(user_id\s*[:=]\s*)([A-Za-z0-9_\-]+)", r"\1<REDACTED_USER>", sanitized)
    # ÄNDERUNG 24.02.2026: Erweiterte Datenschutz-Redaktion fuer sensible Identifikatoren
    # Redigiert E-Mail-Adressen und externe Request IDs in Log-/Fehlertexten.
    sanitized = re.sub(
        r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
        "[REDACTED_EMAIL]",
        sanitized,
    )
    sanitized = re.sub(
        r"Request ID:\s*[0-9a-fA-F-]{8,}",
        "Request ID: [REDACTED_REQUEST_ID]",
        sanitized,
    )

    sanitized = sanitize_paths(sanitized)
    sanitized = redact_stack_traces(sanitized)
    return sanitized


def sanitize_structure(value: Any) -> Any:
    """Sanitisiert rekursiv eine verschachtelte Datenstruktur."""
    if isinstance(value, dict):
        sanitized_dict = {}
        for key, item in value.items():
            if key == "files" and isinstance(item, list):
                item = [entry for entry in item if not (isinstance(entry, str) and entry.strip().endswith(".env"))]
            sanitized_dict[key] = sanitize_structure(item)
        return sanitized_dict
    if isinstance(value, list):
        return [sanitize_structure(item) for item in value]
    if isinstance(value, str):
        return sanitize_text(value)
    return value


def recalculate_totals(project: Dict[str, Any]) -> None:
    """Berechnet Token-Summen und Kosten aus Eintraegen neu."""
    total_tokens = 0
    total_cost = 0.0
    found_metrics = False

    for entry in project.get("entries", []):
        if entry.get("type") == "TokenMetrics":
            content = entry.get("content")
            try:
                metrics = json.loads(content) if isinstance(content, str) else (content or {})
            except json.JSONDecodeError:
                metrics = {}
            tokens = metrics.get("total_tokens") or metrics.get("token_count")
            cost = metrics.get("total_cost") or metrics.get("cost")
            if tokens is not None:
                total_tokens += int(tokens)
                found_metrics = True
            if cost is not None:
                total_cost += float(cost)
                found_metrics = True
        elif entry.get("metadata"):
            tokens = entry["metadata"].get("tokens")
            cost = entry["metadata"].get("cost")
            if tokens is not None:
                total_tokens += int(tokens)
                found_metrics = True
            if cost is not None:
                total_cost += float(cost)
                found_metrics = True

    if found_metrics:
        project["total_tokens"] = total_tokens
        project["total_cost"] = round(total_cost, 6)
    else:
        project["total_tokens"] = None
        project["total_cost"] = None


def prepare_archive_payload(project: Dict[str, Any]) -> Dict[str, Any]:
    """Erstellt eine sanitisierte Kopie des Projekts fuer die Archivierung."""
    sanitized_project = copy.deepcopy(project)
    sanitized_project = sanitize_structure(sanitized_project)
    recalculate_totals(sanitized_project)
    return sanitized_project
