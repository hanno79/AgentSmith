# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 08.02.2026
Version: 1.1
Beschreibung: Utility-Funktionen fuer den DevLoop Coder.
              Extrahiert aus dev_loop_coder.py (Regel 1: Max 500 Zeilen).
              Enthaelt: Model-Output-Bereinigung, PatchMode-Erkennung,
              Datei-Extraktion, Code-Dict-Lesen, Rebuild-von-Disk.
              AENDERUNG 21.02.2026: Fix 59e — Fehlende-Datei-Erkennung.
"""

import logging
import os
import posixpath
import re
from typing import Dict, List

logger = logging.getLogger(__name__)


# AENDERUNG 03.02.2026: Fix 8 - Think-Tag Filtering
# Entfernt Model-spezifische Tags (z.B. <think> von moonshotai/kimi-k2.5)

def _clean_model_output(raw_output: str) -> str:
    """
    Entfernt Model-spezifische Tags aus dem Output.

    AENDERUNG 03.02.2026: Fix 8 fuer moonshotai/kimi-k2.5 <think> Tags.
    Manche Modelle leaken ihren "Denkprozess" in den Code-Output.

    Args:
        raw_output: Roher Model-Output

    Returns:
        Bereinigter Output ohne Think-Tags
    """
    if not raw_output:
        return raw_output

    cleaned = raw_output

    # Entferne <think>...</think> Bloecke komplett
    cleaned = re.sub(r'<think>.*?</think>', '', cleaned, flags=re.DOTALL)

    # Entferne einzelne <think> oder </think> Tags
    cleaned = re.sub(r'</?think>', '', cleaned)

    # Entferne alles vor dem ersten "### FILENAME:" (haeufiges Code-Format)
    if "### FILENAME:" in cleaned:
        idx = cleaned.find("### FILENAME:")
        # Nur kuerzen wenn vor dem Marker unerwuenschter Content ist
        prefix = cleaned[:idx].strip()
        if prefix and not prefix.startswith("```"):
            cleaned = cleaned[idx:]

    # Alternative: Entferne alles vor dem ersten Code-Block
    elif "```" in cleaned:
        idx = cleaned.find("```")
        prefix = cleaned[:idx].strip()
        # Nur kuerzen wenn Prefix kurz und kein sinnvoller Text ist
        if prefix and len(prefix) < 50 and not any(
            kw in prefix.lower() for kw in ["hier", "here", "following", "code"]
        ):
            cleaned = cleaned[idx:]

    return cleaned.strip()


# AENDERUNG 03.02.2026: Patch-Modus Helper-Funktionen
# Verhindert dass Coder bei Fehlern kompletten Code ueberschreibt

def _is_targeted_fix_context(feedback: str) -> bool:
    """
    Prueft ob Feedback auf einen gezielten Fix oder additive Aenderung hinweist.

    Args:
        feedback: Das Fehler-Feedback

    Returns:
        True wenn Patch-Modus sinnvoll, False sonst
    """
    if not feedback:
        return False

    # Spezifische Error-Indikatoren die auf gezielten Fix hinweisen
    # AENDERUNG 03.02.2026: Deutsche Fehlerbegriffe hinzugefuegt fuer PatchMode-Aktivierung
    fix_indicators = [
        # Englische Error-Typen
        "TypeError:", "NameError:", "SyntaxError:", "ImportError:",
        "AttributeError:", "KeyError:", "ValueError:", "ModuleNotFoundError:",
        "expected", "got", "argument", "parameter", "takes",
        "missing", "undefined", "not defined", "cannot import",
        # Deutsche Fehlerbegriffe
        "Syntaxfehler", "Fehler:", "ungültig", "fehlgeschlagen",
        "nicht gefunden", "nicht definiert", "fehlerhaft", "Formatierung"
    ]

    # FIX 05.02.2026: Additive Aenderungen (Tests, Docs, Features) sollten auch PatchMode nutzen
    additive_indicators = [
        "unit-test", "test", "tests/", "test_", "_test.",
        "erstelle test", "add test", "create test",
        "dokumentation", "documentation", "docstring",
        "hinzufügen", "ergänzen", "add", "create", "new file",
        "PFLICHT:", "REQUIRED:", "MUST:"
    ]

    feedback_lower = feedback.lower()
    return (any(ind.lower() in feedback_lower for ind in fix_indicators) or
            any(ind.lower() in feedback_lower for ind in additive_indicators))


# AENDERUNG 10.02.2026: Fix 42c - False-Positive Dateinamen filtern
# "Next.js" aus "die Next.js Umgebung" matcht als Dateiname, ist aber keiner
# Ebenso "Node.js", "Vue.js" etc. aus beschreibendem Text
FALSE_POSITIVE_FILENAMES = {
    'next.js', 'node.js', 'vue.js', 'react.js', 'express.js',
    'nuxt.js', 'nest.js', 'ember.js', 'angular.js', 'backbone.js',
    'three.js', 'p5.js', 'd3.js', 'chart.js', 'socket.js',
}


def _get_affected_files_from_feedback(feedback: str) -> List[str]:
    """
    Extrahiert betroffene Dateinamen aus Feedback.

    Args:
        feedback: Das Fehler-Feedback

    Returns:
        Liste der betroffenen Dateinamen
    """
    if not feedback:
        return []

    # AENDERUNG 06.02.2026: Erweiterte Patterns fuer JavaScript/Next.js Fehler
    # AENDERUNG 10.02.2026: Fix 41 - [DATEI:xxx] Pattern aus Reviewer/Security-Feedback
    # ROOT-CAUSE-FIX: Ohne diese Patterns erkennt PatchMode keine Dateien aus
    # dem Reviewer-Feedback → Fallback auf ALLE Dateien → Context-Overflow
    file_patterns = [
        # AENDERUNG 10.02.2026: Fix 41b - Dynamic Routes sicher ([id], [slug], [...catchall])
        r'\[DATEI:(.+?\.[a-z]{1,4})\]',    # [DATEI:app/api/todos/[id]/route.js]
        r'\[(?:File|Datei):\s*(.+?\.[a-z]{1,4})\]',  # [File: app/api/todos/[id]/route.js]
        r'File "([^"]+\.py)"',           # Python Traceback
        r'in ([a-zA-Z_][a-zA-Z0-9_]*\.py)',  # "in filename.py"
        r'([a-zA-Z_][a-zA-Z0-9_]*\.py):',    # "filename.py:"
        r'tests/([^/\s]+\.py)',           # Tests
        r'([a-zA-Z_][a-zA-Z0-9_]*\.(?:js|jsx|ts|tsx))[\s:]',  # JS/TS: filename.js:
        r'(?:in|from)\s+["\'"]([^"\']+\.(?:js|jsx|ts|tsx))["\'"]',  # import from 'file.js'
        r'Module not found.*?["\'"]([^"\']+)["\'"]',          # Module not found: 'xyz'
        r'Error:\s*([a-zA-Z0-9_/.\\-]+\.(?:js|jsx|ts|tsx))',  # Error: file.js
        r'([a-zA-Z0-9_/.-]+\.(?:js|jsx|ts|tsx))\s+(?:hat|has|contains)',  # datei.js hat Fehler
        r'(?:Datei|File|Syntax)\s+["\'"]?([a-zA-Z0-9_/.-]+\.(?:js|jsx|ts|tsx))',  # Datei "x.js"
        # AENDERUNG 10.02.2026: Fix 48b — Fallback fuer Reviewer-Markdown-Format
        # ROOT-CAUSE-FIX: Reviewer gibt "BETROFFENE DATEIEN: - `file.js`" aus,
        # Parser erkannte nur [DATEI:xxx] → leere affected_files → PatchModeAllFiles
        r'-\s+`([a-zA-Z0-9_/.\[\]-]+\.(?:js|jsx|ts|tsx|py|json|css|bat))`',  # - `package.json`
        r'[→>]\s*(?:DATEI|BETROFFENE DATEIEN):\s*`?([a-zA-Z0-9_/.\[\]-]+\.[a-z]{1,4})`?',  # → DATEI: file.js
        r'BETROFFENE\s+DATEIEN?:.*?`([a-zA-Z0-9_/.\[\]-]+\.[a-z]{1,4})`',  # BETROFFENE DATEIEN: `file.js`
    ]

    found_files = []
    for pattern in file_patterns:
        matches = re.findall(pattern, feedback)
        for match in matches:
            # Nur Dateinamen, nicht volle Pfade aus System-Bibliotheken
            if not any(skip in match.lower() for skip in ['site-packages', 'python3', '/usr/', 'venv/']):
                basename = os.path.basename(match)
                # AENDERUNG 10.02.2026: Fix 42c - False-Positive Dateinamen filtern
                # "Next.js" aus beschreibendem Text ist kein echtes Projekt-File
                if basename.lower() in FALSE_POSITIVE_FILENAMES:
                    continue
                if basename not in found_files:
                    found_files.append(basename)

    # AENDERUNG 13.02.2026: Fix 53 — Limit erhoeht fuer parallelen PatchMode
    # Fix 42c (FALSE_POSITIVE_FILENAMES) filtert false positives jetzt zuverlaessig
    # Bei 30+ Dateien ist paralleler Patch essentiell fuer Timeout-Vermeidung
    return found_files[:30]


# AENDERUNG 07.02.2026: Dynamische Code-Extensions aus qg_constants
# Single Source of Truth: LANGUAGE_TEST_CONFIG definiert code_extensions pro Sprache
# Vorher: 27 hardcodierte Extensions, fehlten Kotlin (.kt), Swift (.swift), C++ (.cpp) etc.
def _get_all_code_extensions() -> set:
    """Sammelt alle Code-Extensions dynamisch aus qg_constants + Extras."""
    try:
        from .qg_constants import LANGUAGE_TEST_CONFIG
        dynamic = set()
        for lang_cfg in LANGUAGE_TEST_CONFIG.values():
            dynamic.update(lang_cfg.get("code_extensions", []))
    except ImportError:
        dynamic = set()

    # Zusaetzliche Config/Build/Template Extensions (nicht in LANGUAGE_TEST_CONFIG)
    extras = {
        '.env', '.dockerfile', '.xml', '.gradle', '.properties',
        '.proto', '.graphql', '.dart', '.scala', '.ex', '.exs',
        '.elm', '.zig', '.lua', '.jl', '.r', '.pl',
    }
    # Basis-Extensions die immer dabei sein muessen
    basis = {
        '.html', '.css', '.json', '.bat', '.sh', '.yaml', '.yml',
        '.toml', '.cfg', '.ini', '.md', '.txt', '.sql',
        '.vue', '.svelte',
    }
    return dynamic | extras | basis


# AENDERUNG 06.02.2026: ROOT-CAUSE-FIX PatchModeFallback
# Symptom: PatchModeFallback "Keine spezifischen Dateien gefunden" in jeder Iteration
# Ursache: manager.current_code ist immer ein String (LLM-Output), nie ein Dict
#          isinstance(manager.current_code, dict) war daher immer False
# Loesung: Projekt-Dateien von Festplatte lesen statt auf Dict-Format zu pruefen

def _get_current_code_dict(manager) -> Dict[str, str]:
    """
    Liest aktuelle Projekt-Dateien als Dict {filename: content}.

    Primaer von Festplatte (aktueller Stand inkl. UTDS-Aenderungen),
    Fallback auf Parsing des current_code Strings.
    """
    if isinstance(getattr(manager, 'current_code', None), dict):
        return manager.current_code

    code_dict = {}
    project_path = getattr(manager, 'project_path', None)
    if not project_path or not os.path.exists(str(project_path)):
        return code_dict

    skip_dirs = {
        '.git', 'node_modules', '__pycache__', '.next',
        'venv', '.venv', 'dist', 'build', '.cache'
    }
    # AENDERUNG 07.02.2026: Dynamische Extensions aus qg_constants (Single Source of Truth)
    code_extensions = _get_all_code_extensions()

    project_path_str = str(project_path)
    for root, dirs, files in os.walk(project_path_str):
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        for filename in files:
            _, ext = os.path.splitext(filename)
            if ext.lower() in code_extensions:
                filepath = os.path.join(root, filename)
                rel_path = os.path.relpath(filepath, project_path_str).replace('\\', '/')
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        code_dict[rel_path] = f.read()
                except UnicodeDecodeError:
                    logger.debug(f"Encoding-Fehler (non-UTF8): {rel_path}")
                except Exception as e:
                    logger.debug(f"Datei nicht lesbar: {rel_path}: {e}")

    return code_dict


# ROOT-CAUSE-FIX 07.02.2026: PatchMode Merge
# Symptom: manager.current_code enthielt nach PatchMode nur 2 Dateien statt aller 13
# Ursache: run_coder_task() gibt nur Patch-Output zurueck, Zeile 293 ueberschreibt komplett
# Loesung: Nach Datei-Speicherung current_code von Festplatte rekonstruieren (alle Dateien)
def rebuild_current_code_from_disk(manager) -> str:
    """
    Baut manager.current_code aus allen Dateien auf der Festplatte neu auf.

    Nutzt _get_current_code_dict() um alle Projekt-Dateien zu lesen und
    formatiert sie im ### FILENAME: Format das der Rest der Pipeline erwartet.

    Returns:
        Vollstaendiger Code-String mit allen Projekt-Dateien im ### FILENAME: Format
    """
    code_dict = _get_current_code_dict(manager)
    if not code_dict:
        return getattr(manager, 'current_code', '') or ''

    parts = []
    for filepath in sorted(code_dict.keys()):
        parts.append(f"### FILENAME: {filepath}\n{code_dict[filepath]}")

    return "\n\n".join(parts)


# AENDERUNG 21.02.2026: Fix 59e — Fehlende-Datei-Erkennung
def detect_missing_files(manager) -> List[Dict[str, str]]:
    """
    Erkennt Dateien die vom Code referenziert werden aber nicht existieren.
    Typisch: API-Routen die 404 zurueckgeben, fehlende Imports.

    Returns:
        Liste von Dicts mit 'file', 'reason', 'referenced_by'
    """
    missing = []
    code_dict = _get_current_code_dict(manager)
    if not code_dict:
        return missing

    for filepath, content in code_dict.items():
        # 1. fetch('/api/xxx') Aufrufe → Route-Datei muss existieren
        for match in re.finditer(r'''fetch\s*\(\s*['"`](/api/[^'"`\s)]+)['"`]''', content):
            api_path = match.group(1)
            # Query-Parameter und Trailing-Slash entfernen
            api_path = api_path.split('?')[0].rstrip('/')
            # Dynamische Segmente ignorieren (z.B. /api/bugs/123)
            # Pruefen ob es ein statischer API-Pfad ist (max 3 Segmente)
            segments = api_path.strip('/').split('/')
            if len(segments) > 3 or not all(s.isalpha() or s == 'api' for s in segments):
                continue
            route_file = f"app{api_path}/route.js"
            if route_file not in code_dict:
                # Auch .ts Variante pruefen
                route_file_ts = f"app{api_path}/route.ts"
                if route_file_ts not in code_dict:
                    missing.append({
                        "file": route_file,
                        "reason": f"fetch('{api_path}') in {filepath} aber Route-Datei fehlt",
                        "referenced_by": filepath
                    })

        # 2. Import-Pfade pruefen (nur relative Imports)
        for match in re.finditer(
            r'''(?:import\s+.*?from\s+|require\s*\(\s*)['"](\./[^'"]+)['"]''',
            content
        ):
            import_path = match.group(1)
            # Relative Aufloesung gegen filepath
            dir_of_file = posixpath.dirname(filepath)
            resolved = posixpath.normpath(posixpath.join(dir_of_file, import_path))
            # Extensions pruefen
            found = False
            for ext in ['', '.js', '.jsx', '.ts', '.tsx', '/index.js', '/index.ts']:
                if (resolved + ext) in code_dict:
                    found = True
                    break
            if not found and resolved not in code_dict:
                # Nur wenn der Import nicht ein npm-Package ist
                if not import_path.startswith('./node_modules'):
                    missing.append({
                        "file": resolved + '.js',
                        "reason": f"Import '{import_path}' in {filepath} aber Datei fehlt",
                        "referenced_by": filepath
                    })

    # Deduplizieren nach Datei-Pfad
    seen = set()
    unique_missing = []
    for mf in missing:
        if mf["file"] not in seen:
            seen.add(mf["file"])
            unique_missing.append(mf)

    return unique_missing
