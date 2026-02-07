# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 02.02.2026
Version: 1.2
Beschreibung: Error-Analyzer Extraktor-Methoden.
              Extrahiert aus error_analyzer.py (Regel 1: Max 500 Zeilen)

              Enthält:
              - extract_python_syntax_errors
              - extract_python_import_errors
              - extract_python_runtime_errors
              - extract_javascript_errors
              - extract_test_failures
              - extract_truncation_errors
              - extract_pip_dependency_errors (NEU v1.1)
              - analyze_docker_error (v1.1, erweitert v1.2)
              - extract_circular_import_errors (NEU v1.2)

              AENDERUNG 02.02.2026 v1.2: Zirkulaere Import-Erkennung
              - extract_circular_import_errors() hinzugefuegt
              - analyze_docker_error() um Import-Patterns erweitert
              - ResolutionImpossible und Dependency-Konflikte erkannt
              AENDERUNG 02.02.2026 v1.1: Issue #10 - pip/Docker Fehler-Erkennung
              - extract_pip_dependency_errors() hinzugefuegt
              - analyze_docker_error() fuer direkten Aufruf hinzugefuegt
"""

from typing import Dict, List, Optional, Set

from backend.error_models import (
    FileError,
    PYTHON_TRACEBACK_PATTERN,
    PYTHON_SYNTAX_ERROR_PATTERN,
    GERMAN_SYNTAX_ERROR_PATTERN,
    UNKNOWN_FILE_SYNTAX_PATTERN,
    PYTHON_IMPORT_ERROR_PATTERN,
    JAVASCRIPT_ERROR_PATTERN,
    TEST_FAILURE_PATTERN,
    TRUNCATION_PATTERN,
    PIP_ERROR_PATTERNS,  # AENDERUNG 02.02.2026: Issue #10
    IMPORT_ERROR_PATTERNS,  # AENDERUNG 02.02.2026: Zirkulaere Import-Erkennung
    CONFIG_ERROR_PATTERNS,  # AENDERUNG 03.02.2026: pytest.ini/Config-Fehler
)
from backend.error_utils import (
    normalize_path,
    find_file_from_traceback,
    find_file_with_syntax_error,
    extract_error_message_from_traceback,
)

import logging
import re as regex_re

logger = logging.getLogger(__name__)


def extract_python_syntax_errors(
    output: str,
    project_files: Dict[str, str]
) -> List[FileError]:
    """
    Extrahiert Python Syntax-Fehler.

    Unterstuetzt auch deutsches Sandbox-Format
    und findet Dateien heuristisch wenn Pfad <unknown> ist.
    """
    errors = []

    # 1. Standard Python Traceback Format
    for match in PYTHON_SYNTAX_ERROR_PATTERN.finditer(output):
        file_path = match.group(1)
        line_num = int(match.group(2))
        message = match.group(3)

        normalized = normalize_path(file_path, project_files)
        if normalized:
            errors.append(FileError(
                file_path=normalized,
                error_type="syntax",
                line_numbers=[line_num],
                error_message=f"SyntaxError: {message}",
                severity="error"
            ))

    # 2. Deutsches Sandbox-Format: "Python-Syntaxfehler in Zeile X"
    for match in GERMAN_SYNTAX_ERROR_PATTERN.finditer(output):
        line_num = int(match.group(1))
        message = match.group(2).strip() if match.group(2) else "Syntaxfehler"

        # Finde die Datei heuristisch wenn nicht angegeben
        found_file = find_file_with_syntax_error(project_files, line_num)
        if found_file:
            errors.append(FileError(
                file_path=found_file,
                error_type="syntax",
                line_numbers=[line_num],
                error_message=f"SyntaxError: {message}",
                severity="error"
            ))

    # 3. Format mit <unknown>: "invalid syntax (<unknown>, line X)"
    for match in UNKNOWN_FILE_SYNTAX_PATTERN.finditer(output):
        line_num = int(match.group(1))

        # Finde die Datei heuristisch
        found_file = find_file_with_syntax_error(project_files, line_num)
        if found_file:
            errors.append(FileError(
                file_path=found_file,
                error_type="syntax",
                line_numbers=[line_num],
                error_message=f"SyntaxError: invalid syntax at line {line_num}",
                severity="error"
            ))

    return errors


def extract_python_import_errors(
    output: str,
    project_files: Dict[str, str]
) -> List[FileError]:
    """Extrahiert Python Import-Fehler."""
    errors = []

    for match in PYTHON_IMPORT_ERROR_PATTERN.finditer(output):
        error_type = match.group(1)
        message = match.group(2)

        # Versuche die Datei aus dem Traceback zu finden
        file_path = find_file_from_traceback(output, project_files)

        if file_path:
            errors.append(FileError(
                file_path=file_path,
                error_type="import",
                line_numbers=[],
                error_message=f"{error_type}: {message}",
                suggested_fix=f"Pruefe Import-Statement fuer: {message}",
                severity="error"
            ))

    return errors


def extract_python_runtime_errors(
    output: str,
    project_files: Dict[str, str]
) -> List[FileError]:
    """Extrahiert Python Runtime-Fehler aus Tracebacks."""
    errors = []
    seen_files: Set[str] = set()

    for match in PYTHON_TRACEBACK_PATTERN.finditer(output):
        file_path = match.group(1)
        line_num = int(match.group(2))

        normalized = normalize_path(file_path, project_files)
        if normalized and normalized not in seen_files:
            seen_files.add(normalized)

            # Extrahiere die Fehlermeldung (letzte Zeile des Tracebacks)
            error_msg = extract_error_message_from_traceback(output)

            errors.append(FileError(
                file_path=normalized,
                error_type="runtime",
                line_numbers=[line_num],
                error_message=error_msg,
                severity="error"
            ))

    return errors


def extract_javascript_errors(
    output: str,
    project_files: Dict[str, str]
) -> List[FileError]:
    """Extrahiert JavaScript/TypeScript-Fehler."""
    errors = []

    for match in JAVASCRIPT_ERROR_PATTERN.finditer(output):
        file_path = match.group(1)
        line_num = int(match.group(2))

        normalized = normalize_path(file_path, project_files)
        if normalized:
            # Extrahiere Fehlermeldung
            start_pos = match.end()
            end_pos = output.find('\n', start_pos)
            message = output[start_pos:end_pos].strip() if end_pos > start_pos else ""

            errors.append(FileError(
                file_path=normalized,
                error_type="syntax" if "syntax" in message.lower() else "runtime",
                line_numbers=[line_num],
                error_message=message,
                severity="error"
            ))

    return errors


def extract_test_failures(
    output: str,
    project_files: Dict[str, str]
) -> List[FileError]:
    """Extrahiert Test-Fehler."""
    errors = []

    for match in TEST_FAILURE_PATTERN.finditer(output):
        status = match.group(1)
        test_name = match.group(2)
        message = match.group(3) if match.group(3) else ""

        # Versuche Datei aus Test-Namen abzuleiten
        # z.B. "test_api.py::test_login" -> "test_api.py"
        if "::" in test_name:
            file_part = test_name.split("::")[0]
        else:
            file_part = test_name

        normalized = normalize_path(file_part, project_files)
        if normalized:
            errors.append(FileError(
                file_path=normalized,
                error_type="test",
                line_numbers=[],
                error_message=f"{status}: {message}",
                severity="error" if status in ["FAILED", "ERROR"] else "warning"
            ))

    return errors


def extract_truncation_errors(
    output: str,
    project_files: Dict[str, str]
) -> List[FileError]:
    """Erkennt Truncation-Probleme (abgeschnittener Code)."""
    errors = []

    if TRUNCATION_PATTERN.search(output):
        # Versuche die betroffene Datei zu identifizieren
        # Oft ist es die letzte erwaehnte Datei
        last_file = None
        for match in PYTHON_TRACEBACK_PATTERN.finditer(output):
            file_path = match.group(1)
            normalized = normalize_path(file_path, project_files)
            if normalized:
                last_file = normalized

        if last_file:
            errors.append(FileError(
                file_path=last_file,
                error_type="truncation",
                line_numbers=[],
                error_message="Code wurde moeglicherweise abgeschnitten (Truncation)",
                suggested_fix="Datei komplett neu generieren mit kuerzerer Laenge",
                severity="error"
            ))

    return errors


# =============================================================================
# AENDERUNG 02.02.2026: Issue #10 - pip/Docker Fehler-Erkennung
# =============================================================================

def extract_pip_dependency_errors(
    output: str,
    project_files: Dict[str, str]
) -> List[FileError]:
    """
    Extrahiert pip/Docker Dependency-Fehler.

    Erkennt Fehler wie:
    - "No module named pytest"
    - "ERROR: No matching distribution found for bootstrap"
    - "ModuleNotFoundError: No module named 'xyz'"

    Diese Fehler betreffen requirements.txt, nicht Python-Dateien.
    """
    errors = []
    seen_modules: Set[str] = set()  # Verhindere Duplikate

    for pattern, error_type in PIP_ERROR_PATTERNS:
        for match in pattern.finditer(output):
            module_name = match.group(1)

            # Ueberspringe bereits erkannte Module
            if module_name.lower() in seen_modules:
                continue
            seen_modules.add(module_name.lower())

            # Bestimme die Ziel-Datei (requirements.txt)
            target_file = _find_requirements_file(project_files)

            # Generiere Fix-Vorschlag basierend auf Fehlertyp
            if error_type == "missing_module":
                fix_suggestion = f"Fuege '{module_name}' zu {target_file} hinzu"
            elif error_type == "invalid_package":
                # AENDERUNG 02.02.2026: Verbesserte Fehlermeldung fuer Versionsfehler
                if "==" in module_name or ">=" in module_name:
                    # Version angegeben - wahrscheinlich existiert die Version nicht
                    pkg_name = module_name.split("==")[0].split(">=")[0].split("~=")[0]
                    fix_suggestion = f"Version von '{pkg_name}' ungueltig in {target_file} - aendere zu '>=' oder pruefe existierende Versionen auf PyPI"
                else:
                    fix_suggestion = f"Pruefe Paketname '{module_name}' in {target_file} - evtl. Tippfehler oder falscher Name"
            elif error_type == "import_error":
                fix_suggestion = f"Pruefe ob '{module_name}' korrekt installiert und importiert wird"
            elif error_type == "pip_install_failed":
                fix_suggestion = f"pip install fuer '{module_name}' fehlgeschlagen - pruefe Paketname und Version"
            elif error_type == "dependency_conflict":
                # AENDERUNG 02.02.2026: Dependency-Konflikt Behandlung hinzugefuegt
                fix_suggestion = f"Dependency-Konflikt in {target_file} - pruefe Versionsangaben und entferne Konflikte"
            elif error_type == "version_not_found":
                fix_suggestion = f"Ungueltige Paketversion in {target_file} - verwende >= statt == oder pruefe PyPI"
            else:
                fix_suggestion = f"Pruefe Dependency: {module_name}"

            errors.append(FileError(
                file_path=target_file,
                error_type="pip_dependency",
                line_numbers=[],
                error_message=match.group(0),
                suggested_fix=fix_suggestion,
                severity="error"
            ))

    return errors


def _find_requirements_file(project_files: Dict[str, str]) -> str:
    """
    Findet die requirements.txt Datei im Projekt.

    Sucht nach:
    1. requirements.txt (Standard)
    2. requirements/*.txt
    3. Andere *requirements*.txt Dateien
    """
    # 1. Standard requirements.txt
    if "requirements.txt" in project_files:
        return "requirements.txt"

    # 2. Suche nach requirements-Dateien
    for path in project_files:
        path_lower = path.lower()
        if "requirements" in path_lower and path_lower.endswith(".txt"):
            return path

    # 3. Fallback: Erstelle requirements.txt (wird vom Fix erstellt)
    return "requirements.txt"


def analyze_docker_error(error_output: str) -> Optional[Dict]:
    """
    Analysiert Docker/pip Fehler und gibt Fix-Vorschlag zurueck.

    Diese Funktion ist fuer direkten Aufruf gedacht (z.B. aus TargetedFix).

    AENDERUNG 02.02.2026: Erweitert um ImportError und zirkulaere Import-Erkennung

    Args:
        error_output: Der Fehler-Output aus Docker/pip

    Returns:
        Dict mit Fehlerdetails oder None wenn kein Fehler erkannt
        {
            "type": "missing_module" | "invalid_package" | "circular_import" | ...,
            "module": "pytest" oder "src/__init__.py",
            "fix": "Add 'pytest' to requirements.txt",
            "file": "requirements.txt" oder "src/__init__.py",
            "line": 3  # Optional: Zeilennummer bei zirkulaeren Imports
        }
    """
    # 1. Pruefe auf zirkulaere Import-Fehler (hoechste Prioritaet)
    for pattern, error_type in IMPORT_ERROR_PATTERNS:
        match = pattern.search(error_output)
        if match:
            if error_type == "circular_import":
                file_path = match.group(1)
                line_num = int(match.group(2))
                return {
                    "type": "circular_import",
                    "module": file_path,
                    "fix": f"Zirkulaerer Import in {file_path} Zeile {line_num} - Importe umstrukturieren oder lazy import verwenden",
                    "file": file_path,
                    "line": line_num
                }
            elif error_type == "conftest_import":
                file_path = match.group(1)
                return {
                    "type": "conftest_import",
                    "module": file_path,
                    "fix": f"ImportError beim Laden von conftest - pruefe Modul-Struktur und __init__.py",
                    "file": file_path
                }
            elif error_type == "incomplete_import":
                module_name = match.group(1)
                return {
                    "type": "incomplete_import",
                    "module": module_name,
                    "fix": f"Unvollstaendiger Import von {module_name} - Code wurde abgeschnitten",
                    "file": f"{module_name.replace('.', '/')}/__init__.py"
                }

    # 2. Pruefe auf pip/Dependency-Fehler
    for pattern, error_type in PIP_ERROR_PATTERNS:
        match = pattern.search(error_output)
        if match:
            # Dependency-Konflikt hat keine Gruppe, behandle separat
            if error_type == "dependency_conflict":
                return {
                    "type": "dependency_conflict",
                    "module": "requirements.txt",
                    "fix": "Paket-Versionskonflikte in requirements.txt - pruefe kompatible Versionen",
                    "file": "requirements.txt"
                }

            module_name = match.group(1) if match.lastindex >= 1 else "unknown"

            # Generiere Fix-Vorschlag basierend auf Fehlertyp
            if error_type in ("missing_module", "import_error"):
                fix = f"Add '{module_name}' to requirements.txt"
            elif error_type == "invalid_package":
                fix = f"Check package name '{module_name}' - possibly misspelled"
            elif error_type == "pip_install_failed":
                fix = f"pip install failed for '{module_name}' - check name and version"
            else:
                fix = f"Check dependency: {module_name}"

            return {
                "type": error_type,
                "module": module_name,
                "fix": fix,
                "file": "requirements.txt"
            }

    return None


def extract_circular_import_errors(
    output: str,
    project_files: Dict[str, str]
) -> List[FileError]:
    """
    Extrahiert zirkulaere Import-Fehler.

    AENDERUNG 02.02.2026: Neu hinzugefuegt fuer TargetedFix

    Erkennt Fehler wie:
    - "src/__init__.py:3: in <module>" (zirkulaerer Import)
    - "ImportError while loading conftest" (Test-Import fehlgeschlagen)
    - "from src import" ohne nachfolgenden Namen (abgeschnittener Import)
    """
    errors = []
    seen_files: Set[str] = set()

    for pattern, error_type in IMPORT_ERROR_PATTERNS:
        for match in pattern.finditer(output):
            if error_type == "circular_import":
                file_path = match.group(1)
                line_num = int(match.group(2))

                # Normalisiere Pfad
                normalized = normalize_path(file_path, project_files)
                target_file = normalized or file_path

                if target_file not in seen_files:
                    seen_files.add(target_file)
                    errors.append(FileError(
                        file_path=target_file,
                        error_type="import",
                        line_numbers=[line_num],
                        error_message=f"Zirkulaerer Import in Zeile {line_num}",
                        suggested_fix="Importe umstrukturieren: db vor routes definieren, oder lazy imports verwenden",
                        severity="error"
                    ))

            elif error_type == "conftest_import":
                file_path = match.group(1)
                normalized = normalize_path(file_path, project_files)
                target_file = normalized or file_path

                if target_file not in seen_files:
                    seen_files.add(target_file)
                    errors.append(FileError(
                        file_path=target_file,
                        error_type="import",
                        line_numbers=[],
                        error_message="ImportError beim Laden von conftest",
                        suggested_fix="Pruefe Modul-Struktur und __init__.py Dateien",
                        severity="error"
                    ))

    return errors


# =============================================================================
# AENDERUNG 03.02.2026: pytest.ini und Config-Fehler Erkennung
# =============================================================================

def extract_config_errors(
    output: str,
    project_files: Dict[str, str]
) -> List[FileError]:
    """
    Extrahiert Config-Datei Fehler (pytest.ini, setup.cfg, etc.).

    AENDERUNG 03.02.2026: Neu hinzugefuegt fuer TargetedFix

    Erkennt Fehler wie:
    - "ERROR: C:\\...\\pytest.ini:1: unexpected line: 'ini'"
    - "setup.cfg: invalid section"
    - INI/Config Syntax-Fehler
    """
    import re as regex_module  # Lokaler Import um Konflikte zu vermeiden
    errors = []
    seen_files: Set[str] = set()

    for pattern, error_type in CONFIG_ERROR_PATTERNS:
        for match in pattern.finditer(output):
            if error_type == "config_error" and match.lastindex and match.lastindex >= 3:
                # Format: ERROR: path:line: message
                file_path = match.group(1)
                line_num = int(match.group(2))
                message = match.group(3)

                # Normalisiere nur Dateinamen (Config-Dateien sind oft im Root)
                basename = file_path.split("\\")[-1].split("/")[-1]

                if basename not in seen_files:
                    seen_files.add(basename)
                    errors.append(FileError(
                        file_path=basename,
                        error_type="config",
                        line_numbers=[line_num],
                        error_message=f"Config-Fehler: {message}",
                        suggested_fix="Pruefe die INI/Config-Syntax - korrekte Section-Header verwenden",
                        severity="error"
                    ))

            elif error_type == "config_syntax":
                # Einfacherer Pattern fuer "unexpected line"
                # Versuche Dateiname aus Kontext zu finden
                context_patterns = [
                    r"([a-zA-Z_]+\.(?:ini|cfg|toml)):",
                    r"ERROR:\s*([^\s:]+\.(?:ini|cfg|toml))",
                ]
                for ctx_pattern in context_patterns:
                    ctx_match = regex_module.search(ctx_pattern, output)
                    if ctx_match:
                        basename = ctx_match.group(1).split("\\")[-1].split("/")[-1]
                        if basename not in seen_files:
                            seen_files.add(basename)
                            errors.append(FileError(
                                file_path=basename,
                                error_type="config",
                                line_numbers=[1],  # Default Zeile 1
                                error_message=f"Config-Syntax ungueltig: {match.group(1) if match.lastindex and match.lastindex >= 1 else 'unknown'}",
                                suggested_fix="Verwende korrektes INI-Format: [section] ohne Praefix",
                                severity="error"
                            ))
                        break

    return errors


# =============================================================================
# AENDERUNG 03.02.2026: Fix 7 - Automatische Environment Constraint Erkennung
# =============================================================================

# Bekannte Modul-Alternativen fuer die Sandbox
KNOWN_MODULE_ALTERNATIVES = {
    "bleach": "Verwende re.sub(r'<[^>]+>', '', text) fuer HTML-Sanitisierung",
    "lxml": "Verwende html.parser oder xml.etree.ElementTree",
    "numpy": "Verwende Standard-Python-Math oder statistics-Modul",
    "pandas": "Verwende csv-Modul und Standard-Datenstrukturen",
    "scipy": "Verwende Standard-Python-Math",
    "matplotlib": "Nur Text-Output moeglich, keine Grafiken",
    "pillow": "Keine Bildverarbeitung verfuegbar",
    "pil": "Keine Bildverarbeitung verfuegbar",
}


def detect_environment_constraints(error_output: str) -> List[dict]:
    """
    Erkennt Umgebungs-Constraints aus Fehler-Output.

    AENDERUNG 03.02.2026: Fix 7 - Automatische Erkennung von Sandbox-Limitierungen

    Args:
        error_output: Der Fehler-Output (z.B. aus Docker/Sandbox)

    Returns:
        Liste von Constraint-Dicts mit:
        - constraint: Eindeutiger Identifier (z.B. "bleach_not_available")
        - description: Menschenlesbare Beschreibung
        - alternative: Optional - Alternativer Ansatz
        - priority: "high", "medium", "low"
    """
    constraints = []
    seen_modules = set()

    # Pattern fuer ModuleNotFoundError / ImportError
    module_patterns = [
        r"ModuleNotFoundError:\s*No module named ['\"]?([^'\"]+)['\"]?",
        r"ImportError:\s*No module named ['\"]?([^'\"]+)['\"]?",
        r"No module named ['\"]?(\w+)['\"]?",
    ]

    for pattern in module_patterns:
        matches = regex_re.findall(pattern, error_output, regex_re.IGNORECASE)
        for module_name in matches:
            # Bereinige Modulname (nur Basis-Modul, nicht Sub-Module)
            base_module = module_name.split(".")[0].strip()

            if base_module in seen_modules:
                continue
            seen_modules.add(base_module)

            # Erstelle Constraint
            constraint = {
                "constraint": f"{base_module}_not_available",
                "description": f"Modul '{base_module}' ist in der Sandbox nicht verfuegbar",
                "priority": "high"
            }

            # Fuege bekannte Alternative hinzu wenn vorhanden
            alternative = KNOWN_MODULE_ALTERNATIVES.get(base_module.lower())
            if alternative:
                constraint["alternative"] = alternative

            constraints.append(constraint)
            logger.info(f"[EnvConstraint] Erkannt: {base_module} nicht verfuegbar")

    return constraints


def save_detected_constraints(error_output: str, memory_path: str) -> int:
    """
    Erkennt und speichert Environment Constraints automatisch.

    AENDERUNG 03.02.2026: Fix 7 - Wrapper fuer automatische Speicherung

    Args:
        error_output: Der Fehler-Output
        memory_path: Pfad zur Memory-Datei

    Returns:
        Anzahl der neu gespeicherten Constraints
    """
    # Lazy import um zirkulaere Abhaengigkeiten zu vermeiden
    from agents.memory_core import save_environment_constraint

    constraints = detect_environment_constraints(error_output)
    saved_count = 0

    for constraint in constraints:
        try:
            result = save_environment_constraint(memory_path, constraint)
            if "hinzugefuegt" in result.lower():
                saved_count += 1
                logger.info(f"[EnvConstraint] Gespeichert: {constraint['constraint']}")
        except Exception as e:
            logger.warning(f"[EnvConstraint] Speichern fehlgeschlagen: {e}")

    return saved_count
