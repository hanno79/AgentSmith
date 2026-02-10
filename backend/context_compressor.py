# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 10.02.2026
Version: 1.0
Beschreibung: Intelligente Context-Kompression fuer den DevLoop Coder-Prompt.
              Fix 41: Statt blind ab Zeile 150 abzuschneiden, werden Dateien
              in 3 Kategorien eingeteilt:
              - Kategorie A (VOLL): Dateien aus Feedback
              - Kategorie B (VOLL): Import-Abhaengigkeiten von A
              - Kategorie C (SUMMARY): Alle anderen → programmatische Zusammenfassung
"""

import hashlib
import logging
import os
import re
from typing import Dict, List, Optional, Set

logger = logging.getLogger(__name__)


def compress_context(
    code_dict: Dict[str, str],
    feedback: str,
    model_router=None,
    config: Optional[dict] = None,
    cache: Optional[dict] = None
) -> Dict[str, str]:
    """
    Komprimiert code_dict intelligent: Feedback-Dateien voll, Rest als Summary.

    Args:
        code_dict: {filename: content} aller Projekt-Dateien
        feedback: Aktuelles Reviewer/Security-Feedback
        model_router: Fuer optionale LLM-Summary (kann None sein)
        config: Konfiguration (max_summary_tokens etc.)
        cache: Summary-Cache persistent ueber Iterationen

    Returns:
        Komprimiertes code_dict mit Summaries fuer Nicht-Feedback-Dateien.
        Enthaelt zusaetzlich '_cache' Key mit aktualisiertem Cache.
    """
    if not code_dict:
        return code_dict

    config = config or {}
    cache = cache or {}

    # Schritt 1: Feedback-Dateien identifizieren (Kategorie A)
    feedback_files = _extract_feedback_files(feedback)
    logger.info(
        "Context-Kompression: %d Feedback-Dateien erkannt: %s",
        len(feedback_files), ", ".join(feedback_files[:5])
    )

    # Schritt 2: Import-Abhaengigkeiten finden (Kategorie B)
    dep_files = _find_import_deps(feedback_files, code_dict)
    logger.info(
        "Context-Kompression: %d Import-Deps erkannt: %s",
        len(dep_files), ", ".join(list(dep_files)[:5])
    )

    # Schritt 3: Komprimiertes Dict aufbauen
    # AENDERUNG 10.02.2026: Basename-Set fuer Fuzzy-Matching (Feedback liefert Basenames,
    # code_dict hat volle Pfade wie 'app/api/bugs/route.js')
    feedback_basenames = set(os.path.basename(f) for f in feedback_files)
    dep_basenames = set(os.path.basename(f) for f in dep_files)

    compressed = {}
    full_count = 0
    summary_count = 0
    cache_hits = 0

    for fname, content in code_dict.items():
        # Kategorie A + B: Voller Inhalt (Basename-Match weil Feedback nur Basenames liefert)
        fname_base = os.path.basename(fname)
        if (fname in feedback_files or fname_base in feedback_basenames
                or fname in dep_files or fname_base in dep_basenames):
            compressed[fname] = content
            full_count += 1
            continue

        # Kategorie C: Zusammenfassung mit Cache
        content_hash = hashlib.md5(content.encode()).hexdigest()[:8]
        if fname in cache and cache[fname].get('hash') == content_hash:
            compressed[fname] = cache[fname]['summary']
            cache_hits += 1
        else:
            summary = _extract_file_structure(fname, content)
            cache[fname] = {'hash': content_hash, 'summary': summary}
            compressed[fname] = summary

        summary_count += 1

    # Optionale LLM-Summary fuer Dateien mit zu kurzer Extraktion
    # AENDERUNG 10.02.2026: Deaktiviert fuer v1.0 - programmatische Extraktion reicht
    # _enhance_with_llm(compressed, code_dict, feedback_files, dep_files, model_router, config)

    logger.info(
        "Context-Kompression fertig: %d voll, %d summaries (%d cache-hits)",
        full_count, summary_count, cache_hits
    )

    # Cache im Ergebnis mitgeben fuer Persistenz ueber Iterationen
    compressed['_cache'] = cache
    return compressed


# AENDERUNG 10.02.2026: Fix 42c - False-Positive Dateinamen (synchron mit dev_loop_coder_utils.py)
FALSE_POSITIVE_FILENAMES = {
    'next.js', 'node.js', 'vue.js', 'react.js', 'express.js',
    'nuxt.js', 'nest.js', 'ember.js', 'angular.js', 'backbone.js',
    'three.js', 'p5.js', 'd3.js', 'chart.js', 'socket.js',
}


def _extract_feedback_files(feedback: str) -> List[str]:
    """
    Extrahiert Dateinamen aus Feedback (gleiche Patterns wie _get_affected_files_from_feedback).

    Nutzt die erweiterten Patterns inkl. [DATEI:xxx] Format.
    """
    if not feedback:
        return []

    # AENDERUNG 10.02.2026: Patterns synchron mit dev_loop_coder_utils.py
    file_patterns = [
        # AENDERUNG 10.02.2026: Fix 41b - Dynamic Routes sicher ([id], [slug])
        r'\[DATEI:(.+?\.[a-z]{1,4})\]',
        r'\[(?:File|Datei):\s*(.+?\.[a-z]{1,4})\]',
        r'File "([^"]+\.py)"',
        r'([a-zA-Z_][a-zA-Z0-9_]*\.py):',
        r'([a-zA-Z0-9_/.-]+\.(?:js|jsx|ts|tsx))[\s:]',
        r'Error:\s*([a-zA-Z0-9_/.\\-]+\.(?:js|jsx|ts|tsx))',
        r'([a-zA-Z0-9_/.-]+\.(?:js|jsx|ts|tsx))\s+(?:hat|has|contains)',
        r'(?:Datei|File|Syntax)\s+["\'"]?([a-zA-Z0-9_/.-]+\.(?:js|jsx|ts|tsx))',
    ]

    found = []
    for pattern in file_patterns:
        matches = re.findall(pattern, feedback)
        for match in matches:
            # System-Bibliotheken ausschliessen
            if any(skip in match.lower() for skip in ['site-packages', 'python3', '/usr/', 'venv/']):
                continue
            basename = os.path.basename(match)
            # AENDERUNG 10.02.2026: Fix 42c - False-Positive Dateinamen filtern
            if basename.lower() in FALSE_POSITIVE_FILENAMES:
                continue
            if basename not in found:
                found.append(basename)

    return found[:10]  # Max 10 Feedback-Dateien


def _find_import_deps(feedback_files: List[str], code_dict: Dict[str, str]) -> Set[str]:
    """
    Findet Dateien die von Feedback-Dateien importiert werden.

    Analysiert relative Imports (from './lib/db') und identifiziert
    die entsprechenden Dateien im code_dict.

    Args:
        feedback_files: Liste der Dateinamen aus Feedback
        code_dict: Alle Projekt-Dateien {filename: content}

    Returns:
        Set von Import-Abhaengigkeiten (ohne Feedback-Dateien selbst)
    """
    deps = set()
    feedback_set = set(feedback_files)

    for fname in feedback_files:
        # Feedback-Datei im code_dict finden (kann relativer Pfad sein)
        content = None
        for code_file, code_content in code_dict.items():
            if code_file.endswith(fname) or os.path.basename(code_file) == fname:
                content = code_content
                break
        if not content:
            continue

        # Relative Imports extrahieren: import X from './lib/db'
        # AENDERUNG 10.02.2026: Auch require() und dynamische Imports
        import_patterns = [
            r"from\s+['\"]\.\.?/([^'\"]+)['\"]",      # import from './lib/db'
            r"require\s*\(\s*['\"]\.\.?/([^'\"]+)['\"]\s*\)",  # require('./lib/db')
            r"import\s*\(\s*['\"]\.\.?/([^'\"]+)['\"]\s*\)",   # import('./lib/db')
        ]

        for pattern in import_patterns:
            imports = re.findall(pattern, content)
            for imp in imports:
                # Relative ../ Prefixe entfernen fuer Matching
                # ../../lib/db -> lib/db, ../components/X -> components/X
                clean_imp = re.sub(r'^(\.\./)+', '', imp)

                # Import-Pfad auf code_dict-Dateien matchen
                for code_file in code_dict:
                    code_basename = os.path.basename(code_file)
                    # Exakter Match oder mit Extension-Ergaenzung
                    if (clean_imp in code_file or
                        code_file.endswith(clean_imp + ".js") or
                        code_file.endswith(clean_imp + ".jsx") or
                        code_file.endswith(clean_imp + ".ts") or
                        code_file.endswith(clean_imp + ".tsx") or
                        code_basename == clean_imp or
                        code_basename.startswith(clean_imp + ".")):
                        if os.path.basename(code_file) not in feedback_set:
                            deps.add(code_file)

    return deps


def _extract_file_structure(filename: str, content: str) -> str:
    """
    Extrahiert die Struktur einer Datei programmatisch (ohne LLM).

    Unterstuetzt JS/JSX/TS/TSX, Python, CSS, JSON, HTML und Config-Dateien.

    Args:
        filename: Dateiname (fuer Typ-Erkennung)
        content: Datei-Inhalt

    Returns:
        Komprimierte Zusammenfassung der Datei-Struktur
    """
    lines = content.split("\n")
    ext = os.path.splitext(filename)[1].lower()

    # Dispatch nach Dateityp
    if ext in ('.js', '.jsx', '.ts', '.tsx', '.mjs'):
        return _extract_js_structure(filename, content, lines)
    elif ext == '.py':
        return _extract_python_structure(filename, content, lines)
    elif ext == '.css':
        return _extract_css_structure(filename, content, lines)
    elif ext == '.json':
        return _extract_json_structure(filename, content, lines)
    else:
        # Generischer Fallback: Erste 20 Zeilen + Zeilenanzahl
        preview = "\n".join(lines[:20])
        return f"VORSCHAU:\n{preview}\n\nZEILEN: {len(lines)}"


def _extract_js_structure(filename: str, content: str, lines: list) -> str:
    """Extrahiert JS/JSX/TS/TSX Struktur per Regex."""
    result = []

    # 1. Imports (max 10)
    imports = [l.strip() for l in lines if re.match(r'^\s*import\s', l) or "require(" in l]
    if imports:
        result.append("IMPORTS:\n" + "\n".join(imports[:10]))

    # 2. Exports (max 5, gekuerzt auf 100 Zeichen)
    exports = [l.strip() for l in lines if re.match(r'^\s*export\s', l)]
    if exports:
        result.append("EXPORTS:\n" + "\n".join(e[:100] for e in exports[:5]))

    # 3. Funktionen und Komponenten
    funcs = re.findall(r'(?:export\s+)?(?:async\s+)?function\s+(\w+)', content)
    arrow_funcs = re.findall(r'(?:export\s+(?:default\s+)?)?const\s+(\w+)\s*=\s*(?:async\s*)?\(', content)
    all_funcs = list(dict.fromkeys(funcs + arrow_funcs))  # Duplikate entfernen, Reihenfolge behalten
    if all_funcs:
        result.append("FUNKTIONEN: " + ", ".join(all_funcs))

    # 4. API-Routes (Next.js App Router)
    if "/api/" in filename:
        methods = re.findall(r'export\s+(?:async\s+)?function\s+(GET|POST|PUT|DELETE|PATCH)', content)
        if methods:
            result.append("HTTP-METHODEN: " + ", ".join(methods))

    # 5. React Hooks
    hooks = re.findall(r'(use(?:State|Effect|Ref|Memo|Callback|Context|Router|Params))\s*\(', content)
    if hooks:
        unique_hooks = list(dict.fromkeys(hooks))
        result.append("HOOKS: " + ", ".join(unique_hooks))

    # 6. State-Variablen
    state_vars = re.findall(r'const\s+\[(\w+),\s*set\w+\]\s*=\s*useState', content)
    if state_vars:
        result.append("STATE: " + ", ".join(state_vars))

    result.append(f"ZEILEN: {len(lines)}")
    return "\n".join(result) if result else f"[JS-Datei mit {len(lines)} Zeilen]"


def _extract_python_structure(filename: str, content: str, lines: list) -> str:
    """Extrahiert Python-Struktur per Regex."""
    result = []

    # 1. Imports (max 10)
    imports = [l.strip() for l in lines
               if re.match(r'^\s*(import|from)\s', l) and not l.strip().startswith('#')]
    if imports:
        result.append("IMPORTS:\n" + "\n".join(imports[:10]))

    # 2. Klassen
    classes = re.findall(r'class\s+(\w+)', content)
    if classes:
        result.append("KLASSEN: " + ", ".join(classes))

    # 3. Funktionen (top-level und Methoden)
    funcs = re.findall(r'^(?:async\s+)?def\s+(\w+)', content, re.MULTILINE)
    if funcs:
        result.append("FUNKTIONEN: " + ", ".join(funcs[:15]))

    # 4. Globale Variablen/Konstanten
    globals_found = re.findall(r'^([A-Z][A-Z0-9_]+)\s*=', content, re.MULTILINE)
    if globals_found:
        result.append("KONSTANTEN: " + ", ".join(globals_found[:10]))

    result.append(f"ZEILEN: {len(lines)}")
    return "\n".join(result) if result else f"[Python-Datei mit {len(lines)} Zeilen]"


def _extract_css_structure(filename: str, content: str, lines: list) -> str:
    """Extrahiert CSS-Struktur: Selektoren und Custom Properties."""
    result = []

    # CSS-Selektoren (Klassen und IDs)
    selectors = re.findall(r'^([.#][a-zA-Z][a-zA-Z0-9_-]*)\s*\{', content, re.MULTILINE)
    if selectors:
        result.append("SELEKTOREN: " + ", ".join(selectors[:20]))

    # CSS Custom Properties
    vars_found = re.findall(r'(--[a-zA-Z][a-zA-Z0-9_-]*)\s*:', content)
    if vars_found:
        unique_vars = list(dict.fromkeys(vars_found))
        result.append("CSS-VARIABLEN: " + ", ".join(unique_vars[:10]))

    # Media Queries
    media = re.findall(r'@media\s*\(([^)]+)\)', content)
    if media:
        result.append("MEDIA-QUERIES: " + ", ".join(media[:5]))

    result.append(f"ZEILEN: {len(lines)}")
    return "\n".join(result) if result else f"[CSS-Datei mit {len(lines)} Zeilen]"


def _extract_json_structure(filename: str, content: str, lines: list) -> str:
    """Extrahiert JSON-Struktur: Top-Level Keys."""
    result = []

    # package.json Spezialbehandlung
    if filename.endswith("package.json"):
        try:
            import json
            data = json.loads(content)
            if "name" in data:
                result.append(f"NAME: {data['name']}")
            if "dependencies" in data:
                deps = list(data["dependencies"].keys())
                result.append("DEPENDENCIES: " + ", ".join(deps[:15]))
            if "devDependencies" in data:
                dev_deps = list(data["devDependencies"].keys())
                result.append("DEV-DEPENDENCIES: " + ", ".join(dev_deps[:10]))
            if "scripts" in data:
                scripts = list(data["scripts"].keys())
                result.append("SCRIPTS: " + ", ".join(scripts[:10]))
        except Exception:
            pass

    if not result:
        # Generisch: Top-Level Keys
        top_keys = re.findall(r'^\s*"([^"]+)"\s*:', content, re.MULTILINE)
        if top_keys:
            result.append("TOP-KEYS: " + ", ".join(top_keys[:15]))

    result.append(f"ZEILEN: {len(lines)}")
    return "\n".join(result) if result else f"[JSON-Datei mit {len(lines)} Zeilen]"
