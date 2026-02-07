# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 02.02.2026
Version: 1.4
Beschreibung: Analysiert Fehler-Output und identifiziert betroffene Dateien.
              Extrahiert Fehlerdetails aus Sandbox-Output und Reviewer-Feedback.

              AENDERUNG 02.02.2026 v1.4: Zirkulaere Import-Erkennung fuer TargetedFix
              - extract_circular_import_errors() integriert
              - Erkennt conftest ImportError und zirkulaere Imports

              AENDERUNG 02.02.2026 v1.3: Issue #10 - pip/Docker Fehler-Erkennung
              - extract_pip_dependency_errors() integriert
              - analyze_docker_error() exportiert

              AENDERUNG 01.02.2026 v1.2: Refaktoriert in Module (Regel 1: Max 500 Zeilen)
              - error_models.py: FileError dataclass, Regex-Patterns
              - error_utils.py: Hilfsfunktionen
              - error_extractors.py: Extract-Methoden

              AENDERUNG 31.01.2026 v1.1:
              - Deutsches Sandbox-Format Pattern hinzugefuegt
              - Heuristik fuer <unknown> Dateipfade implementiert
"""

import re
from typing import List, Dict, Set, Optional

# Interne Module
from backend.error_models import (
    FileError,
    PYTHON_TRACEBACK_PATTERN,
    PYTHON_SYNTAX_ERROR_PATTERN,
    GERMAN_SYNTAX_ERROR_PATTERN,
    UNKNOWN_FILE_SYNTAX_PATTERN,
    PYTHON_IMPORT_ERROR_PATTERN,
    JAVASCRIPT_ERROR_PATTERN,
    TRUNCATION_PATTERN,
    TEST_FAILURE_PATTERN,
    ERROR_PRIORITY_MAP,
)
from backend.error_utils import (
    normalize_path,
    find_file_from_traceback,
    find_file_with_syntax_error,
    extract_error_message_from_traceback,
    classify_error_from_message,
    analyze_dependencies,
    merge_errors,
)
from backend.error_extractors import (
    extract_python_syntax_errors,
    extract_python_import_errors,
    extract_python_runtime_errors,
    extract_javascript_errors,
    extract_test_failures,
    extract_truncation_errors,
    extract_pip_dependency_errors,  # AENDERUNG 02.02.2026: Issue #10
    analyze_docker_error,  # AENDERUNG 02.02.2026: Issue #10
    extract_circular_import_errors,  # AENDERUNG 02.02.2026: Zirkulaere Imports
    extract_config_errors,  # AENDERUNG 03.02.2026: pytest.ini/Config-Fehler
    detect_environment_constraints,  # AENDERUNG 03.02.2026: Fix 7 - EnvConstraints
    save_detected_constraints,  # AENDERUNG 03.02.2026: Fix 7 - EnvConstraints
)

# Re-Exports fuer Rückwärtskompatibilität
__all__ = [
    "FileError",
    "ErrorAnalyzer",
    "analyze_errors",
    "get_files_to_fix",
    "analyze_docker_error",  # AENDERUNG 02.02.2026: Issue #10
    "detect_environment_constraints",  # AENDERUNG 03.02.2026: Fix 7
    "save_detected_constraints",  # AENDERUNG 03.02.2026: Fix 7
]


class ErrorAnalyzer:
    """
    Analysiert Fehler-Output aus verschiedenen Quellen und extrahiert
    strukturierte Informationen ueber betroffene Dateien.
    """

    # Regex-Pattern als Klassen-Attribute für Rückwärtskompatibilität
    PYTHON_TRACEBACK_PATTERN = PYTHON_TRACEBACK_PATTERN
    PYTHON_SYNTAX_ERROR_PATTERN = PYTHON_SYNTAX_ERROR_PATTERN
    GERMAN_SYNTAX_ERROR_PATTERN = GERMAN_SYNTAX_ERROR_PATTERN
    UNKNOWN_FILE_SYNTAX_PATTERN = UNKNOWN_FILE_SYNTAX_PATTERN
    PYTHON_IMPORT_ERROR_PATTERN = PYTHON_IMPORT_ERROR_PATTERN
    JAVASCRIPT_ERROR_PATTERN = JAVASCRIPT_ERROR_PATTERN
    TRUNCATION_PATTERN = TRUNCATION_PATTERN
    TEST_FAILURE_PATTERN = TEST_FAILURE_PATTERN

    def __init__(self, project_path: str = ""):
        self.project_path = project_path

    def analyze_sandbox_output(
        self,
        sandbox_result: str,
        project_files: Dict[str, str]
    ) -> List[FileError]:
        """
        Analysiert Sandbox/Test-Output und extrahiert Fehlerinformationen.
        """
        errors: List[FileError] = []

        if not sandbox_result:
            return errors

        # Extraktoren aufrufen
        errors.extend(extract_python_syntax_errors(sandbox_result, project_files))
        errors.extend(extract_python_import_errors(sandbox_result, project_files))
        errors.extend(extract_python_runtime_errors(sandbox_result, project_files))
        errors.extend(extract_javascript_errors(sandbox_result, project_files))
        errors.extend(extract_test_failures(sandbox_result, project_files))
        errors.extend(extract_truncation_errors(sandbox_result, project_files))
        # AENDERUNG 02.02.2026: Issue #10 - pip/Docker Fehler erkennen
        errors.extend(extract_pip_dependency_errors(sandbox_result, project_files))
        # AENDERUNG 02.02.2026: Zirkulaere Import-Fehler erkennen (fuer TargetedFix)
        errors.extend(extract_circular_import_errors(sandbox_result, project_files))
        # AENDERUNG 03.02.2026: pytest.ini/Config-Fehler erkennen
        errors.extend(extract_config_errors(sandbox_result, project_files))

        return merge_errors(errors)

    def analyze_review_feedback(
        self,
        review_output: str,
        project_files: Dict[str, str]
    ) -> List[FileError]:
        """
        Extrahiert Fehler aus Reviewer-Feedback.
        """
        errors: List[FileError] = []

        if not review_output:
            return errors

        # Pattern fuer Reviewer-Feedback
        file_mention_pattern = re.compile(
            r'(?:Datei|File|In)\s+[`"]?([^\s`",:]+)[`"]?\s*(?:Zeile|Line|:)?\s*(\d+)?[:\s]*(.+)',
            re.IGNORECASE | re.MULTILINE
        )

        for match in file_mention_pattern.finditer(review_output):
            file_path = match.group(1)
            line_num = int(match.group(2)) if match.group(2) else 0
            message = match.group(3).strip() if match.group(3) else ""

            normalized_path = normalize_path(file_path, project_files)
            if normalized_path:
                error = FileError(
                    file_path=normalized_path,
                    error_type=classify_error_from_message(message),
                    line_numbers=[line_num] if line_num else [],
                    error_message=message,
                    severity="warning"
                )
                errors.append(error)

        # Auch nach expliziten FEHLER/ERROR Markierungen suchen
        error_pattern = re.compile(
            r'(?:FEHLER|ERROR|PROBLEM|BUG)(?:\s+in)?\s*[`"]?([^\s`",:]+)[`"]?[:\s]*(.+)?',
            re.IGNORECASE | re.MULTILINE
        )

        for match in error_pattern.finditer(review_output):
            file_path = match.group(1)
            message = match.group(2).strip() if match.group(2) else ""

            normalized_path = normalize_path(file_path, project_files)
            if normalized_path:
                error = FileError(
                    file_path=normalized_path,
                    error_type="review",
                    line_numbers=[],
                    error_message=message,
                    severity="error"
                )
                errors.append(error)

        return merge_errors(errors)

    def prioritize_fixes(self, errors: List[FileError]) -> List[FileError]:
        """
        Sortiert Fehler nach Abhaengigkeiten und Prioritaet.
        """
        # Abhaengigkeiten analysieren
        errors = analyze_dependencies(errors)

        # Sortieren nach: 1. Keine Abhaengigkeiten zuerst, 2. Prioritaet
        def sort_key(error: FileError):
            has_deps = 1 if error.dependencies else 0
            priority = ERROR_PRIORITY_MAP.get(error.error_type, 6)
            return (has_deps, priority, error.file_path)

        return sorted(errors, key=sort_key)

    def get_affected_files(self, errors: List[FileError]) -> Set[str]:
        """Gibt alle betroffenen Dateipfade zurueck."""
        return {e.file_path for e in errors}

    def group_by_file(self, errors: List[FileError]) -> Dict[str, List[FileError]]:
        """Gruppiert Fehler nach Datei."""
        grouped: Dict[str, List[FileError]] = {}
        for error in errors:
            if error.file_path not in grouped:
                grouped[error.file_path] = []
            grouped[error.file_path].append(error)
        return grouped

    # Private Methoden delegieren an error_utils
    def _normalize_path(self, file_path: str, project_files: Dict[str, str]) -> Optional[str]:
        return normalize_path(file_path, project_files)

    def _find_file_from_traceback(self, output: str, project_files: Dict[str, str]) -> Optional[str]:
        return find_file_from_traceback(output, project_files)

    def _extract_error_message_from_traceback(self, output: str) -> str:
        return extract_error_message_from_traceback(output)

    def _classify_error_from_message(self, message: str) -> str:
        return classify_error_from_message(message)

    def _analyze_dependencies(self, errors: List[FileError]) -> List[FileError]:
        return analyze_dependencies(errors)

    def _merge_errors(self, errors: List[FileError]) -> List[FileError]:
        return merge_errors(errors)


# =============================================================================
# Hilfsfunktionen fuer externe Nutzung
# =============================================================================

def analyze_errors(
    sandbox_output: str = "",
    review_output: str = "",
    project_files: Dict[str, str] = None
) -> List[FileError]:
    """
    Convenience-Funktion zur Fehleranalyse.
    """
    if project_files is None:
        project_files = {}

    analyzer = ErrorAnalyzer()

    errors = []
    if sandbox_output:
        errors.extend(analyzer.analyze_sandbox_output(sandbox_output, project_files))
    if review_output:
        errors.extend(analyzer.analyze_review_feedback(review_output, project_files))

    return analyzer.prioritize_fixes(errors)


def get_files_to_fix(errors: List[FileError], max_files: int = 7) -> List[str]:
    """
    Gibt die Dateipfade zurueck die gefixt werden sollten.

    AENDERUNG 02.02.2026: Default von 3 auf 7 erhoeht (Bug #12)
    """
    files = []
    seen = set()

    for error in errors:
        if error.file_path not in seen:
            files.append(error.file_path)
            seen.add(error.file_path)

            if len(files) >= max_files:
                break

    return files
