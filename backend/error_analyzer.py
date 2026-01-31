"""
Author: rahn
Datum: 31.01.2026
Version: 1.1
Beschreibung: Analysiert Fehler-Output und identifiziert betroffene Dateien.
              Extrahiert Fehlerdetails aus Sandbox-Output und Reviewer-Feedback.

AENDERUNG 31.01.2026 v1.1:
- Deutsches Sandbox-Format Pattern hinzugefuegt (Python-Syntaxfehler in Zeile X)
- Heuristik fuer <unknown> Dateipfade implementiert
- Prueft Python-Dateien mit ast.parse() um fehlerhafte Datei zu identifizieren
- Erkennt Markdown-Code-Fence-Marker als Truncation-Indikator
"""

import re
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set
from pathlib import Path


@dataclass
class FileError:
    """Repraesentiert einen Fehler in einer spezifischen Datei."""
    file_path: str                          # z.B. "src/ui.py"
    error_type: str                         # "syntax", "import", "runtime", "test", "truncation"
    line_numbers: List[int] = field(default_factory=list)  # z.B. [42, 55, 78]
    error_message: str = ""                 # Vollstaendige Fehlermeldung
    suggested_fix: str = ""                 # Optional: Hinweis zur Korrektur
    dependencies: List[str] = field(default_factory=list)  # Dateien die zuerst gefixt werden muessen
    severity: str = "error"                 # "error", "warning", "info"

    def __hash__(self):
        return hash((self.file_path, self.error_type, tuple(self.line_numbers)))


class ErrorAnalyzer:
    """
    Analysiert Fehler-Output aus verschiedenen Quellen und extrahiert
    strukturierte Informationen ueber betroffene Dateien.
    """

    # Regex-Pattern fuer verschiedene Fehlertypen
    PYTHON_TRACEBACK_PATTERN = re.compile(
        r'File "([^"]+)", line (\d+)',
        re.MULTILINE
    )

    PYTHON_SYNTAX_ERROR_PATTERN = re.compile(
        r'File "([^"]+)", line (\d+)\n.*\n.*SyntaxError: (.+)',
        re.MULTILINE
    )

    # AENDERUNG 31.01.2026: Deutsches Sandbox-Format erkennen
    # Format: "❌ Python-Syntaxfehler in Zeile X: message"
    GERMAN_SYNTAX_ERROR_PATTERN = re.compile(
        r'Python-Syntaxfehler\s+in\s+Zeile\s+(\d+)[:\s]*(.+)?',
        re.IGNORECASE | re.MULTILINE
    )

    # Format: "invalid syntax (<unknown>, line X)" oder "SyntaxError: ... (<unknown>, line X)"
    UNKNOWN_FILE_SYNTAX_PATTERN = re.compile(
        r'(?:invalid syntax|SyntaxError)[^(]*\(<unknown>,\s*line\s+(\d+)\)',
        re.IGNORECASE | re.MULTILINE
    )

    PYTHON_IMPORT_ERROR_PATTERN = re.compile(
        r'(ImportError|ModuleNotFoundError): (.+)',
        re.MULTILINE
    )

    JAVASCRIPT_ERROR_PATTERN = re.compile(
        r'([\w/\\.-]+\.[jt]sx?):(\d+):(\d+).*?(?:error|Error)',
        re.MULTILINE
    )

    TRUNCATION_PATTERN = re.compile(
        r'(truncat|abgeschnitten|unvollstaendig|incomplete|cut off)',
        re.IGNORECASE
    )

    TEST_FAILURE_PATTERN = re.compile(
        r'(FAILED|FAIL|ERROR)\s+([^\s:]+)(?:::|:)\s*(.+)?',
        re.MULTILINE
    )

    def __init__(self, project_path: str = ""):
        self.project_path = project_path

    def analyze_sandbox_output(
        self,
        sandbox_result: str,
        project_files: Dict[str, str]
    ) -> List[FileError]:
        """
        Analysiert Sandbox/Test-Output und extrahiert:
        - Welche Dateien betroffen sind
        - Welche Zeilen fehlerhaft sind
        - Welchen Fehlertyp (Syntax, Import, Runtime, Test)

        Args:
            sandbox_result: Der Output der Sandbox-Ausfuehrung
            project_files: Dict mit Dateipfad -> Inhalt

        Returns:
            Liste von FileError-Objekten
        """
        errors: List[FileError] = []

        if not sandbox_result:
            return errors

        # 1. Python Syntax-Fehler erkennen
        errors.extend(self._extract_python_syntax_errors(sandbox_result, project_files))

        # 2. Python Import-Fehler erkennen
        errors.extend(self._extract_python_import_errors(sandbox_result, project_files))

        # 3. Python Runtime-Fehler (Tracebacks) erkennen
        errors.extend(self._extract_python_runtime_errors(sandbox_result, project_files))

        # 4. JavaScript/TypeScript-Fehler erkennen
        errors.extend(self._extract_javascript_errors(sandbox_result, project_files))

        # 5. Test-Fehler erkennen
        errors.extend(self._extract_test_failures(sandbox_result, project_files))

        # 6. Truncation-Probleme erkennen
        errors.extend(self._extract_truncation_errors(sandbox_result, project_files))

        # Deduplizieren und zusammenfuehren
        return self._merge_errors(errors)

    def analyze_review_feedback(
        self,
        review_output: str,
        project_files: Dict[str, str]
    ) -> List[FileError]:
        """
        Extrahiert Fehler aus Reviewer-Feedback.

        Der Reviewer gibt strukturiertes Feedback, z.B.:
        - "Datei src/ui.py Zeile 42: Fehlende Fehlerbehandlung"
        - "FEHLER in api.py: Import fehlt"

        Args:
            review_output: Das Feedback des Reviewer-Agenten
            project_files: Dict mit Dateipfad -> Inhalt

        Returns:
            Liste von FileError-Objekten
        """
        errors: List[FileError] = []

        if not review_output:
            return errors

        # Pattern fuer Reviewer-Feedback
        # Format: "Datei <pfad> [Zeile <nr>]: <nachricht>"
        file_mention_pattern = re.compile(
            r'(?:Datei|File|In)\s+[`"]?([^\s`",:]+)[`"]?\s*(?:Zeile|Line|:)?\s*(\d+)?[:\s]*(.+)',
            re.IGNORECASE | re.MULTILINE
        )

        for match in file_mention_pattern.finditer(review_output):
            file_path = match.group(1)
            line_num = int(match.group(2)) if match.group(2) else 0
            message = match.group(3).strip() if match.group(3) else ""

            # Pruefen ob Datei im Projekt existiert
            normalized_path = self._normalize_path(file_path, project_files)
            if normalized_path:
                error = FileError(
                    file_path=normalized_path,
                    error_type=self._classify_error_from_message(message),
                    line_numbers=[line_num] if line_num else [],
                    error_message=message,
                    severity="warning"  # Reviewer-Feedback ist oft weniger kritisch
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

            normalized_path = self._normalize_path(file_path, project_files)
            if normalized_path:
                error = FileError(
                    file_path=normalized_path,
                    error_type="review",
                    line_numbers=[],
                    error_message=message,
                    severity="error"
                )
                errors.append(error)

        return self._merge_errors(errors)

    def prioritize_fixes(self, errors: List[FileError]) -> List[FileError]:
        """
        Sortiert Fehler nach Abhaengigkeiten und Prioritaet.

        Reihenfolge:
        1. Syntax-Fehler (blockieren alles)
        2. Import-Fehler (blockieren Ausfuehrung)
        3. Runtime-Fehler
        4. Test-Fehler
        5. Review-Feedback

        Innerhalb der Kategorien: Nach Abhaengigkeiten sortieren.

        Args:
            errors: Liste von FileError-Objekten

        Returns:
            Sortierte Liste von FileError-Objekten
        """
        # Prioritaets-Mapping
        priority_map = {
            "syntax": 0,
            "truncation": 1,
            "import": 2,
            "runtime": 3,
            "test": 4,
            "review": 5,
            "unknown": 6
        }

        # Abhaengigkeiten analysieren
        errors = self._analyze_dependencies(errors)

        # Sortieren nach: 1. Keine Abhaengigkeiten zuerst, 2. Prioritaet
        def sort_key(error: FileError):
            has_deps = 1 if error.dependencies else 0
            priority = priority_map.get(error.error_type, 6)
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

    # =========================================================================
    # Private Hilfsmethoden
    # =========================================================================

    def _extract_python_syntax_errors(
        self,
        output: str,
        project_files: Dict[str, str]
    ) -> List[FileError]:
        """
        Extrahiert Python Syntax-Fehler.

        AENDERUNG 31.01.2026: Unterstuetzt auch deutsches Sandbox-Format
        und findet Dateien heuristisch wenn Pfad <unknown> ist.
        """
        errors = []

        # 1. Standard Python Traceback Format
        for match in self.PYTHON_SYNTAX_ERROR_PATTERN.finditer(output):
            file_path = match.group(1)
            line_num = int(match.group(2))
            message = match.group(3)

            normalized = self._normalize_path(file_path, project_files)
            if normalized:
                errors.append(FileError(
                    file_path=normalized,
                    error_type="syntax",
                    line_numbers=[line_num],
                    error_message=f"SyntaxError: {message}",
                    severity="error"
                ))

        # 2. Deutsches Sandbox-Format: "Python-Syntaxfehler in Zeile X"
        for match in self.GERMAN_SYNTAX_ERROR_PATTERN.finditer(output):
            line_num = int(match.group(1))
            message = match.group(2).strip() if match.group(2) else "Syntaxfehler"

            # Finde die Datei heuristisch wenn nicht angegeben
            found_file = self._find_file_with_syntax_error(project_files, line_num)
            if found_file:
                errors.append(FileError(
                    file_path=found_file,
                    error_type="syntax",
                    line_numbers=[line_num],
                    error_message=f"SyntaxError: {message}",
                    severity="error"
                ))

        # 3. Format mit <unknown>: "invalid syntax (<unknown>, line X)"
        for match in self.UNKNOWN_FILE_SYNTAX_PATTERN.finditer(output):
            line_num = int(match.group(1))

            # Finde die Datei heuristisch
            found_file = self._find_file_with_syntax_error(project_files, line_num)
            if found_file:
                errors.append(FileError(
                    file_path=found_file,
                    error_type="syntax",
                    line_numbers=[line_num],
                    error_message=f"SyntaxError: invalid syntax at line {line_num}",
                    severity="error"
                ))

        return errors

    def _find_file_with_syntax_error(
        self,
        project_files: Dict[str, str],
        line_num: int
    ) -> Optional[str]:
        """
        AENDERUNG 31.01.2026: Findet heuristisch die Datei mit dem Syntax-Fehler.

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

    def _extract_python_import_errors(
        self,
        output: str,
        project_files: Dict[str, str]
    ) -> List[FileError]:
        """Extrahiert Python Import-Fehler."""
        errors = []

        for match in self.PYTHON_IMPORT_ERROR_PATTERN.finditer(output):
            error_type = match.group(1)
            message = match.group(2)

            # Versuche die Datei aus dem Traceback zu finden
            file_path = self._find_file_from_traceback(output, project_files)

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

    def _extract_python_runtime_errors(
        self,
        output: str,
        project_files: Dict[str, str]
    ) -> List[FileError]:
        """Extrahiert Python Runtime-Fehler aus Tracebacks."""
        errors = []
        seen_files: Set[str] = set()

        for match in self.PYTHON_TRACEBACK_PATTERN.finditer(output):
            file_path = match.group(1)
            line_num = int(match.group(2))

            normalized = self._normalize_path(file_path, project_files)
            if normalized and normalized not in seen_files:
                seen_files.add(normalized)

                # Extrahiere die Fehlermeldung (letzte Zeile des Tracebacks)
                error_msg = self._extract_error_message_from_traceback(output)

                errors.append(FileError(
                    file_path=normalized,
                    error_type="runtime",
                    line_numbers=[line_num],
                    error_message=error_msg,
                    severity="error"
                ))

        return errors

    def _extract_javascript_errors(
        self,
        output: str,
        project_files: Dict[str, str]
    ) -> List[FileError]:
        """Extrahiert JavaScript/TypeScript-Fehler."""
        errors = []

        for match in self.JAVASCRIPT_ERROR_PATTERN.finditer(output):
            file_path = match.group(1)
            line_num = int(match.group(2))

            normalized = self._normalize_path(file_path, project_files)
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

    def _extract_test_failures(
        self,
        output: str,
        project_files: Dict[str, str]
    ) -> List[FileError]:
        """Extrahiert Test-Fehler."""
        errors = []

        for match in self.TEST_FAILURE_PATTERN.finditer(output):
            status = match.group(1)
            test_name = match.group(2)
            message = match.group(3) if match.group(3) else ""

            # Versuche Datei aus Test-Namen abzuleiten
            # z.B. "test_api.py::test_login" -> "test_api.py"
            if "::" in test_name:
                file_part = test_name.split("::")[0]
            else:
                file_part = test_name

            normalized = self._normalize_path(file_part, project_files)
            if normalized:
                errors.append(FileError(
                    file_path=normalized,
                    error_type="test",
                    line_numbers=[],
                    error_message=f"{status}: {message}",
                    severity="error" if status in ["FAILED", "ERROR"] else "warning"
                ))

        return errors

    def _extract_truncation_errors(
        self,
        output: str,
        project_files: Dict[str, str]
    ) -> List[FileError]:
        """Erkennt Truncation-Probleme (abgeschnittener Code)."""
        errors = []

        if self.TRUNCATION_PATTERN.search(output):
            # Versuche die betroffene Datei zu identifizieren
            # Oft ist es die letzte erwaehnte Datei
            last_file = None
            for match in self.PYTHON_TRACEBACK_PATTERN.finditer(output):
                file_path = match.group(1)
                normalized = self._normalize_path(file_path, project_files)
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

    def _normalize_path(
        self,
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

    def _find_file_from_traceback(
        self,
        output: str,
        project_files: Dict[str, str]
    ) -> Optional[str]:
        """Findet die Hauptdatei aus einem Traceback."""
        for match in self.PYTHON_TRACEBACK_PATTERN.finditer(output):
            file_path = match.group(1)
            normalized = self._normalize_path(file_path, project_files)
            if normalized:
                return normalized
        return None

    def _extract_error_message_from_traceback(self, output: str) -> str:
        """Extrahiert die Fehlermeldung aus einem Python-Traceback."""
        lines = output.strip().split('\n')

        # Die letzte nicht-leere Zeile ist oft die Fehlermeldung
        for line in reversed(lines):
            line = line.strip()
            if line and not line.startswith('File ') and not line.startswith('^'):
                return line

        return "Unbekannter Fehler"

    def _classify_error_from_message(self, message: str) -> str:
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

    def _analyze_dependencies(self, errors: List[FileError]) -> List[FileError]:
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

    def _merge_errors(self, errors: List[FileError]) -> List[FileError]:
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
                priority = {"syntax": 0, "truncation": 1, "import": 2, "runtime": 3, "test": 4, "review": 5}
                if priority.get(error.error_type, 6) < priority.get(existing.error_type, 6):
                    existing.error_type = error.error_type

                # Kombiniere Fehlermeldungen
                if error.error_message and error.error_message not in existing.error_message:
                    existing.error_message = f"{existing.error_message}\n{error.error_message}"

                # Merge Abhaengigkeiten
                existing.dependencies = list(set(existing.dependencies + error.dependencies))

        return list(merged.values())


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

    Args:
        sandbox_output: Output der Sandbox-Ausfuehrung
        review_output: Feedback des Reviewers
        project_files: Dict mit Dateipfad -> Inhalt

    Returns:
        Priorisierte Liste von FileError-Objekten
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


def get_files_to_fix(errors: List[FileError], max_files: int = 3) -> List[str]:
    """
    Gibt die Dateipfade zurueck die gefixt werden sollten.

    Args:
        errors: Liste von FileError-Objekten
        max_files: Maximale Anzahl Dateien (fuer parallele Verarbeitung)

    Returns:
        Liste von Dateipfaden
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
