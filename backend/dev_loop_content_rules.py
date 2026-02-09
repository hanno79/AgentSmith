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
              - Hydration-Schutz (Next.js: suppressHydrationWarning, Date-Formatting)
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

        # AENDERUNG 09.02.2026: Fix 39 — Hydration-Schutz (Next.js)
        # Regel: suppressHydrationWarning in layout.js (Browser-Extensions)
        if 'layout' in filename.lower() and ext in ('js', 'jsx', 'ts', 'tsx'):
            _check_hydration_safety(filename, content, warnings)

        # Regel: Date-Formatting in Client-Components (Hydration-Mismatch)
        if ext in ('js', 'jsx', 'ts', 'tsx') and jsx_mode:
            _check_date_hydration(filename, content, warnings)

    return warnings


def _check_esm_compliance(filename: str, content: str, warnings: List[str]) -> None:
    """Prueft ob CommonJS-Patterns (require, module.exports) verwendet werden."""
    # AENDERUNG 09.02.2026: Fix 38 — Config-Dateien von ESM-Check ausnehmen
    # ROOT-CAUSE-FIX:
    # Symptom: next.config.js, postcss.config.js, tailwind.config.js als ESM-Verletzung
    # Ursache: Diese Config-Dateien MUESSEN CommonJS (module.exports) verwenden
    # Loesung: Bekannte Config-Dateien + test-Dateien von ESM-Pruefung ausnehmen
    basename = filename.replace("\\", "/").split("/")[-1].lower()
    ESM_EXEMPT_FILES = {
        "next.config.js", "next.config.mjs",
        "postcss.config.js", "postcss.config.mjs",
        "tailwind.config.js", "tailwind.config.mjs",
        "jest.config.js", "jest.config.mjs",
        "babel.config.js", ".babelrc.js",
        "eslint.config.js", ".eslintrc.js",
        "prettier.config.js",
        "webpack.config.js",
        "vite.config.js", "vite.config.ts",
        "tsconfig.json",
    }
    if basename in ESM_EXEMPT_FILES:
        return
    # Test-Dateien ausnehmen (oft CommonJS fuer jest/mocha)
    if basename.endswith(('.test.js', '.spec.js', '.test.ts', '.spec.ts')):
        return
    normalized = filename.replace("\\", "/")
    if normalized.startswith("tests/") or "/tests/" in normalized or "/__tests__/" in normalized:
        return

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


# AENDERUNG 09.02.2026: Fix 39 — Hydration-Error Praevention
# ROOT-CAUSE-FIX:
# Symptom: Next.js Hydration-Error im Browser ("server rendered HTML didn't match the client")
# Ursache 1: <body> ohne suppressHydrationWarning → Browser-Extensions modifizieren DOM
# Ursache 2: Date.toLocaleDateString() in Client-Components → Server/Client-Locale-Mismatch
# Loesung: Content-basierte Checks als Validator-Warnungen


def _check_hydration_safety(filename: str, content: str, warnings: List[str]) -> None:
    """Prueft ob layout.js suppressHydrationWarning auf html/body hat."""
    if '<body' in content and 'suppressHydrationWarning' not in content:
        warnings.append(
            f"[{filename}] HYDRATION-WARNUNG: <body> ohne suppressHydrationWarning "
            f"— Browser-Extensions verursachen Hydration-Errors ohne dieses Attribut"
        )
    if '<html' in content and 'suppressHydrationWarning' not in content:
        warnings.append(
            f"[{filename}] HYDRATION-WARNUNG: <html> ohne suppressHydrationWarning "
            f"— fuege suppressHydrationWarning zum <html>-Tag hinzu"
        )


def _check_date_hydration(filename: str, content: str, warnings: List[str]) -> None:
    """Prueft ob Date-Formatierung direkt in JSX gerendert wird (Hydration-Mismatch)."""
    # Nur Client-Components pruefen (die 'use client' haben)
    if "'use client'" not in content and '"use client"' not in content:
        return
    # toLocaleDateString/toLocaleString/toLocaleTimeString in JSX
    date_patterns = re.findall(
        r'\.to(?:Locale(?:Date|Time)?String|LocaleString)\s*\(',
        content
    )
    if date_patterns:
        warnings.append(
            f"[{filename}] HYDRATION-WARNUNG: Date.toLocale*String() in Client-Component "
            f"— verursacht Server/Client Mismatch. Verwende useEffect+useState oder ISO-String"
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
