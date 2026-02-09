# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 09.02.2026
Version: 1.0
Beschreibung: Content-basierte Validierungsregeln (Dreifach-Schutz Ebene 3).
              Prueft generierte Dateien auf Regelverletzungen:
              - ESM-Pflicht (import/export statt require/module.exports)
              - App Router (Next.js: pages/ verboten)
              - Purple-Verbot (CLAUDE.md Regel 19)
              Extrahiert aus dev_loop_helpers.py (Regel 1: Max 500 Zeilen)
"""

import re
from typing import List


def validate_content_rules(code_dict: dict, tech_blueprint: dict) -> List[str]:
    """
    Prueft generierte Dateien auf Content-Regelverletzungen.

    AENDERUNG 09.02.2026: Dreifach-Schutz Content-Regeln (Fix 36 Audit)
    ROOT-CAUSE-FIX:
    Symptom: ESM-Verletzungen, Pages Router, Purple-Farben werden nicht erkannt
    Ursache: Nur Prompt-Schutz, kein Validator-Feedback
    Loesung: Content-basierte Checks als Warnungen an Coder zurueckgeben

    Args:
        code_dict: Dict {filename: content} aus _parse_code_to_files()
        tech_blueprint: Blueprint mit Projekt-Typ und Sprache

    Returns:
        Liste von Warnungen (leer wenn keine Verletzungen)
    """
    warnings = []

    framework = tech_blueprint.get("framework", "").lower()
    project_type = tech_blueprint.get("project_type", "").lower()
    jsx_mode = any(fw in framework for fw in ["next.js", "nextjs", "react", "gatsby", "remix", "preact"]) or \
               any(pt in project_type for pt in ["nextjs", "react", "gatsby", "remix"])

    for filename, content in code_dict.items():
        ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''

        # Regel: ESM-Pflicht (import/export statt require/module.exports)
        if ext in ('js', 'jsx', 'ts', 'tsx', 'mjs') and jsx_mode:
            _check_esm_compliance(filename, content, warnings)

        # Regel: App Router (Next.js: pages/ verboten, nur app/ erlaubt)
        _check_app_router(filename, tech_blueprint, warnings)

        # Regel: Purple-Verbot (CLAUDE.md Regel 19)
        if ext in ('css', 'scss', 'less', 'jsx', 'tsx', 'js', 'ts'):
            _check_purple_colors(filename, content, warnings)

    return warnings


def _check_esm_compliance(filename: str, content: str, warnings: List[str]) -> None:
    """Prueft ob CommonJS-Patterns (require, module.exports) verwendet werden."""
    lines = content.split('\n')
    for line_nr, line in enumerate(lines, 1):
        stripped = line.strip()
        # Kommentare ueberspringen
        if stripped.startswith('//') or stripped.startswith('*') or stripped.startswith('/*'):
            continue
        if re.search(r'\brequire\s*\(', stripped):
            warnings.append(
                f"[{filename}:{line_nr}] ESM-VERLETZUNG: require() gefunden "
                f"— verwende import statt require"
            )
            break  # Nur erste Verletzung pro Datei
        if re.search(r'\bmodule\.exports\b', stripped):
            warnings.append(
                f"[{filename}:{line_nr}] ESM-VERLETZUNG: module.exports gefunden "
                f"— verwende export/export default"
            )
            break


def _check_app_router(filename: str, tech_blueprint: dict, warnings: List[str]) -> None:
    """Prueft ob Pages Router statt App Router verwendet wird (Next.js)."""
    combined = (tech_blueprint.get("framework", "") + tech_blueprint.get("project_type", "")).lower()
    if 'nextjs' not in combined.replace("next.js", "nextjs"):
        return

    normalized_path = filename.replace("\\", "/")
    if normalized_path.startswith("pages/") or "/pages/" in normalized_path:
        warnings.append(
            f"[{filename}] APP-ROUTER-VERLETZUNG: pages/ Router erkannt "
            f"— verwende app/ Router (Next.js 14+)"
        )


def _check_purple_colors(filename: str, content: str, warnings: List[str]) -> None:
    """Prueft ob verbotene Purple/Violet/Indigo Farben verwendet werden (Regel 19)."""
    purple_words = re.findall(r'\b(?:purple|violet|indigo)\b', content, re.IGNORECASE)
    if purple_words:
        warnings.append(
            f"[{filename}] FARB-VERLETZUNG (Regel 19): '{purple_words[0]}' gefunden "
            f"— keine blue-purple Gradients verwenden"
        )


# =========================================================================
# AENDERUNG 09.02.2026: Dateinamen-Extraktion aus Feedback (Fix 35)
# Verschoben von dev_loop_helpers.py (Regel 1: Max 500 Zeilen)
# =========================================================================

def extract_filenames_from_feedback(feedback: str) -> List[str]:
    """
    Extrahiert Dateinamen aus Reviewer-/Security-Feedback.

    AENDERUNG 09.02.2026: Fix 35 — Ping-Pong-Erkennung + Iteration-History.
    ROOT-CAUSE-FIX:
    Symptom: Coder regeneriert Dateien die UTDS gerade gefixt hat (Ping-Pong)
    Ursache: Kein Tracking welche Dateien in welcher Iteration bemangelt wurden
    Loesung: Dateinamen aus Feedback extrahieren fuer Counter + History

    Sucht nach Mustern wie:
    - `app/api/todos/route.js` (Backtick-umschlossen)
    - [DATEI:lib/db.js] (Security-Format)
    - app/api/bugs/route.js (Pfade mit Extension)

    Args:
        feedback: Reviewer- oder Security-Feedback Text

    Returns:
        Liste von Dateinamen (dedupliziert, normalisiert)
    """
    if not feedback:
        return []

    filenames = set()

    # Muster 1: Pfade mit Extension (app/api/todos/route.js etc.)
    # AENDERUNG 09.02.2026: Fix 35b — Laengere Extensions zuerst (json vor js, tsx vor ts)
    # ROOT-CAUSE-FIX: Regex-Alternation matcht von links nach rechts,
    # "js" matchte vor "json" → "package.json" wurde als "package.js" extrahiert
    path_pattern = r'(?:^|\s|`|\[|:)([a-zA-Z0-9_./\\-]+\.(?:json|jsx|js|tsx|ts|py|css|html|mjs))'
    for match in re.finditer(path_pattern, feedback):
        fname = match.group(1).strip()
        # Nur relative Pfade (keine URLs, node_modules oder .next)
        if not fname.startswith(('http', 'node_modules', '.next', '//')):
            filenames.add(fname.replace("\\", "/"))

    # Muster 2: [DATEI:xxx] Format aus Security-Feedback
    datei_pattern = r'\[DATEI:([^\]]+)\]'
    for match in re.finditer(datei_pattern, feedback):
        filenames.add(match.group(1).strip().replace("\\", "/"))

    return list(filenames)
