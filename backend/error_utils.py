# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 01.02.2026
Version: 1.0
Beschreibung: Error-Analyzer Hilfsfunktionen.
              Extrahiert aus error_analyzer.py (Regel 1: Max 500 Zeilen)

              Enthält:
              - normalize_path
              - find_file_from_traceback
              - find_file_with_syntax_error
              - extract_error_message_from_traceback
              - classify_error_from_message
              - analyze_dependencies
              - merge_errors
"""

from pathlib import Path
from typing import Dict, List, Optional, Set

from backend.error_models import (
    FileError,
    PYTHON_TRACEBACK_PATTERN,
    ERROR_PRIORITY_MAP
)


def normalize_path(
    file_path: str,
    project_files: Dict[str, str]
) -> Optional[str]:
    """
    Normalisiert einen Dateipfad und prueft ob er im Projekt existiert.

    Args:
        file_path: Der zu normalisierende Pfad
        project_files: Dict mit Dateipfad -> Inhalt

    Returns:
        Normalisierter Pfad oder None wenn nicht gefunden
    """
    if not file_path:
        return None

    # Entferne fuehrende/nachfolgende Leerzeichen
    file_path = file_path.strip()

    # Direkte Uebereinstimmung
    if file_path in project_files:
        return file_path

    # Versuche mit normalisiertem Pfad
    normalized = file_path.replace('\\', '/')
    if normalized in project_files:
        return normalized

    # Versuche nur den Dateinamen
    file_name = Path(file_path).name
    for proj_path in project_files.keys():
        if proj_path.endswith(file_name) or Path(proj_path).name == file_name:
            return proj_path

    # Versuche relativen Pfad
    for proj_path in project_files.keys():
        if file_path in proj_path or proj_path.endswith(file_path):
            return proj_path

    return None


def find_file_from_traceback(
    output: str,
    project_files: Dict[str, str]
) -> Optional[str]:
    """Findet die Hauptdatei aus einem Traceback."""
    for match in PYTHON_TRACEBACK_PATTERN.finditer(output):
        file_path = match.group(1)
        normalized = normalize_path(file_path, project_files)
        if normalized:
            return normalized
    return None


def find_file_with_syntax_error(
    project_files: Dict[str, str],
    line_num: int
) -> Optional[str]:
    """
    Findet heuristisch die Datei mit dem Syntax-Fehler.

    Strategie:
    1. Pruefe Python-Dateien die lang genug sind
    2. Pruefe ob Zeile syntaktisch problematisch aussieht
    3. Pruefe auf typische Truncation-Marker (``` am Anfang/Ende)
    """
    import ast

    python_files = {
        path: content for path, content in project_files.items()
        if path.endswith('.py')
    }

    candidates = []

    for file_path, content in python_files.items():
        lines = content.split('\n')

        # Datei muss lang genug sein
        if len(lines) < line_num:
            continue

        # Pruefe auf Markdown-Code-Fence-Marker (haeufiger Bug)
        if content.startswith('```') or '```' in content[:50]:
            candidates.append((file_path, 100))  # Hohe Prioritaet
            continue

        # Versuche die Datei zu parsen - wenn Fehler, ist sie kandidat
        try:
            ast.parse(content)
        except SyntaxError as e:
            # Fehler gefunden - pruefe ob Zeile passt
            error_line = e.lineno if e.lineno else line_num
            if abs(error_line - line_num) <= 2:  # Toleranz von 2 Zeilen
                candidates.append((file_path, 50))
            else:
                candidates.append((file_path, 20))

    # Waehle den besten Kandidaten
    if candidates:
        candidates.sort(key=lambda x: -x[1])  # Hoechste Prioritaet zuerst
        return candidates[0][0]

    return None


def extract_error_message_from_traceback(output: str) -> str:
    """Extrahiert die Fehlermeldung aus einem Python-Traceback."""
    lines = output.strip().split('\n')

    # Die letzte nicht-leere Zeile ist oft die Fehlermeldung
    for line in reversed(lines):
        line = line.strip()
        if line and not line.startswith('File ') and not line.startswith('^'):
            return line

    return "Unbekannter Fehler"


def classify_error_from_message(message: str) -> str:
    """Klassifiziert den Fehlertyp basierend auf der Nachricht."""
    message_lower = message.lower()

    if any(kw in message_lower for kw in ['syntax', 'parse', 'unexpected']):
        return "syntax"
    elif any(kw in message_lower for kw in ['import', 'module', 'not found']):
        return "import"
    elif any(kw in message_lower for kw in ['test', 'assert', 'expect']):
        return "test"
    elif any(kw in message_lower for kw in ['truncat', 'abgeschnitten', 'incomplete']):
        return "truncation"
    else:
        return "runtime"


def analyze_dependencies(errors: List[FileError]) -> List[FileError]:
    """
    Analysiert Import-Abhaengigkeiten zwischen fehlerhaften Dateien.

    Wenn Datei A Datei B importiert und beide Fehler haben,
    sollte B zuerst gefixt werden.
    """
    # Einfache Heuristik: Import-Fehler haben keine Abhaengigkeiten,
    # andere Fehler koennten von Import-Fehlern abhaengen

    import_error_files = {e.file_path for e in errors if e.error_type == "import"}

    for error in errors:
        if error.error_type != "import" and error.file_path not in import_error_files:
            # Pruefe ob diese Datei von einer Datei mit Import-Fehler abhaengt
            # (vereinfachte Logik - in Realitaet muesste man Imports parsen)
            error.dependencies = list(import_error_files)

    return errors


def merge_errors(errors: List[FileError]) -> List[FileError]:
    """
    Dedupliziert und merged Fehler fuer dieselbe Datei.

    Wenn mehrere Fehler fuer dieselbe Datei existieren,
    werden sie zu einem zusammengefasst.
    """
    merged: Dict[str, FileError] = {}

    for error in errors:
        key = error.file_path

        if key not in merged:
            merged[key] = error
        else:
            existing = merged[key]
            # Merge Zeilennummern
            existing.line_numbers = list(set(existing.line_numbers + error.line_numbers))
            existing.line_numbers.sort()

            # Behalte den schwerwiegenderen Fehlertyp
            if ERROR_PRIORITY_MAP.get(error.error_type, 6) < ERROR_PRIORITY_MAP.get(existing.error_type, 6):
                existing.error_type = error.error_type

            # Kombiniere Fehlermeldungen
            if error.error_message and error.error_message not in existing.error_message:
                existing.error_message = f"{existing.error_message}\n{error.error_message}"

            # Merge Abhaengigkeiten
            existing.dependencies = list(set(existing.dependencies + error.dependencies))

    return list(merged.values())
