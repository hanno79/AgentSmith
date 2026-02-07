# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 02.02.2026
Version: 1.0
Beschreibung: Pre-Docker Validator - Validiert Code VOR dem Docker-Lauf.
              Nutzt bestehende Checks aus dev_loop_helpers und error_models.

              Zweck: Fehler frueh erkennen bevor Docker-Tests fehlschlagen.
              Dies reduziert Iterationen und spart Zeit/Ressourcen.

              Wiederverwendete Komponenten:
              - _is_python_file_complete() aus dev_loop_helpers.py
              - AST-Parsing aus run_sandbox_for_project()
              - Import-Analyse neu implementiert
"""

import ast
import re
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Set

# AENDERUNG 02.02.2026: PyPI-Versionsvalidierung
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class ValidationIssue:
    """Repraesentiert ein Validierungsproblem."""
    file_path: str
    issue_type: str  # "truncation", "syntax", "circular_import", "missing_import", "invalid_package"
    line_number: int = 0
    message: str = ""
    suggested_fix: str = ""
    severity: str = "error"  # "error", "warning"


@dataclass
class PreDockerValidationResult:
    """Ergebnis der Pre-Docker Validierung."""
    is_valid: bool
    issues: List[ValidationIssue] = field(default_factory=list)
    warnings: List[ValidationIssue] = field(default_factory=list)
    feedback_for_coder: str = ""

    def add_issue(self, issue: ValidationIssue):
        if issue.severity == "error":
            self.issues.append(issue)
            self.is_valid = False
        else:
            self.warnings.append(issue)


class PreDockerValidator:
    """
    Validiert generierten Code BEVOR Docker-Tests laufen.

    Checks:
    1. Truncation-Detection (unvollstaendiger Code)
    2. Syntax-Validierung (AST-Parsing)
    3. Zirkulaere Import-Erkennung
    4. Requirements.txt Validierung
    """

    # Bekannte ungueltige PyPI-Pakete (haeufige LLM-Fehler)
    INVALID_PACKAGES = {
        "bootstrap",  # CSS Framework, kein Python-Paket
        "jquery",     # JS Library
        "react",      # JS Library
        "vue",        # JS Library
        "angular",    # JS Library
        "axios",      # JS Library
        "express",    # Node.js
        "lodash",     # JS Library
        "moment",     # JS Library (pypi: python-moment)
        "underscore", # JS Library
    }

    # Patterns fuer Truncation-Erkennung
    TRUNCATION_ENDINGS = (
        "(", "[", "{", ":", ",",
        "def ", "class ", "if ", "for ", "while ",
        "return ", "yield ", "raise ", "import ", "from "
    )

    def __init__(self):
        self._import_graph: Dict[str, List[str]] = {}
        # AENDERUNG 02.02.2026: Cache fuer PyPI-Versionsabfragen
        self._pypi_cache: Dict[str, bool] = {}
        self._pypi_check_enabled = REQUESTS_AVAILABLE

    def validate(self, project_files: Dict[str, str]) -> PreDockerValidationResult:
        """
        Fuehrt alle Pre-Docker Validierungen durch.

        Args:
            project_files: Dict mit {filepath: content}

        Returns:
            PreDockerValidationResult mit Issues und Feedback
        """
        result = PreDockerValidationResult(is_valid=True)

        if not project_files:
            return result

        # 1. Truncation-Check
        self._check_truncation(project_files, result)

        # 2. Syntax-Check (AST)
        self._check_syntax(project_files, result)

        # 3. Import-Analyse (Zirkulaere Imports)
        self._check_circular_imports(project_files, result)

        # 4. Requirements.txt Validierung
        self._check_requirements(project_files, result)

        # 5. PyPI-Versionsvalidierung (AENDERUNG 02.02.2026)
        self._check_pypi_versions(project_files, result)

        # Feedback fuer Coder generieren
        result.feedback_for_coder = self._generate_feedback(result)

        return result

    def _check_truncation(
        self,
        project_files: Dict[str, str],
        result: PreDockerValidationResult
    ):
        """Prueft auf unvollstaendigen/abgeschnittenen Code."""
        for filepath, content in project_files.items():
            if not filepath.endswith(".py"):
                continue

            is_complete, reason = self._is_python_file_complete(content, filepath)
            if not is_complete:
                result.add_issue(ValidationIssue(
                    file_path=filepath,
                    issue_type="truncation",
                    message=f"Code unvollstaendig: {reason}",
                    suggested_fix="Generiere die Datei komplett neu mit allen Funktionen und Klassen",
                    severity="error"
                ))

    def _is_python_file_complete(self, content: str, filename: str) -> Tuple[bool, str]:
        """
        Prueft ob eine Python-Datei vollstaendig ist.
        Wiederverwendet Logik aus dev_loop_helpers.py.
        """
        if not content or not content.strip():
            return False, "Datei ist leer"

        lines = content.strip().split('\n')
        last_line = lines[-1].strip() if lines else ""

        # Check 1: Endet mit offenem Konstrukt
        for ending in self.TRUNCATION_ENDINGS:
            if last_line.endswith(ending) or last_line == ending.strip():
                return False, f"Endet mit offenem Konstrukt: '{ending.strip()}'"

        # Check 2: AST-Parsing
        try:
            ast.parse(content)
        except SyntaxError as e:
            # Spezifische Truncation-Indikatoren
            error_msg = str(e).lower()
            if any(ind in error_msg for ind in [
                "unexpected eof",
                "expected an indented block",
                "unterminated string",
                "eof in multi-line"
            ]):
                return False, f"AST-Fehler deutet auf Truncation: {e.msg}"

        # Check 3: Unbalancierte Klammern
        open_parens = content.count('(') - content.count(')')
        open_brackets = content.count('[') - content.count(']')
        open_braces = content.count('{') - content.count('}')

        if open_parens > 0:
            return False, f"{open_parens} ungeschlossene Klammern '('"
        if open_brackets > 0:
            return False, f"{open_brackets} ungeschlossene eckige Klammern '['"
        if open_braces > 0:
            return False, f"{open_braces} ungeschlossene geschweifte Klammern '{{'"

        return True, ""

    def _check_syntax(
        self,
        project_files: Dict[str, str],
        result: PreDockerValidationResult
    ):
        """Prueft Python-Syntax mit AST-Parsing."""
        for filepath, content in project_files.items():
            if not filepath.endswith(".py"):
                continue

            try:
                ast.parse(content)
            except SyntaxError as e:
                # Truncation-Fehler wurden oben schon behandelt
                if not any(ind in str(e).lower() for ind in [
                    "unexpected eof", "expected an indented block"
                ]):
                    result.add_issue(ValidationIssue(
                        file_path=filepath,
                        issue_type="syntax",
                        line_number=e.lineno or 0,
                        message=f"SyntaxError: {e.msg}",
                        suggested_fix=f"Korrigiere Zeile {e.lineno}: {e.text.strip() if e.text else ''}",
                        severity="error"
                    ))

    def _check_circular_imports(
        self,
        project_files: Dict[str, str],
        result: PreDockerValidationResult
    ):
        """
        Analysiert Import-Struktur und erkennt zirkulaere Imports.

        Haeufiges Problem bei LLM-generiertem Code:
        - src/__init__.py importiert aus routes.py
        - routes.py importiert aus src/__init__.py
        """
        # Import-Graph aufbauen
        self._import_graph = {}

        for filepath, content in project_files.items():
            if not filepath.endswith(".py"):
                continue

            imports = self._extract_imports(content)
            self._import_graph[filepath] = imports

        # Zirkulaere Abhaengigkeiten finden
        for filepath in self._import_graph:
            cycle = self._find_import_cycle(filepath, [])
            if cycle:
                cycle_str = " -> ".join(cycle)
                result.add_issue(ValidationIssue(
                    file_path=filepath,
                    issue_type="circular_import",
                    message=f"Zirkulaerer Import erkannt: {cycle_str}",
                    suggested_fix=(
                        "Loesung: 1) __init__.py minimal halten - nur __all__ definieren, "
                        "2) Objekte (db, app) VOR route-Imports erstellen, "
                        "3) Lazy Imports innerhalb von Funktionen verwenden"
                    ),
                    severity="error"
                ))
                break  # Nur ersten Zyklus melden

    def _extract_imports(self, content: str) -> List[str]:
        """Extrahiert importierte Module aus Python-Code."""
        imports = []

        # Pattern: from X import Y oder import X
        import_pattern = re.compile(
            r'^\s*(?:from\s+(\S+)\s+import|import\s+(\S+))',
            re.MULTILINE
        )

        for match in import_pattern.finditer(content):
            module = match.group(1) or match.group(2)
            if module:
                # Nur lokale Imports (src.*, app.*, etc.)
                base_module = module.split('.')[0]
                if base_module in ['src', 'app', 'api', 'routes', 'models', 'views']:
                    imports.append(module)

        return imports

    def _find_import_cycle(
        self,
        current: str,
        visited: List[str]
    ) -> Optional[List[str]]:
        """Findet Zyklen im Import-Graph (DFS)."""
        if current in visited:
            # Zyklus gefunden - gib den Pfad zurueck
            cycle_start = visited.index(current)
            return visited[cycle_start:] + [current]

        if current not in self._import_graph:
            return None

        visited_copy = visited + [current]

        for imported in self._import_graph[current]:
            # Konvertiere Modul-Name zu Dateipfad
            possible_files = self._module_to_files(imported)
            for possible_file in possible_files:
                if possible_file in self._import_graph:
                    cycle = self._find_import_cycle(possible_file, visited_copy)
                    if cycle:
                        return cycle

        return None

    def _module_to_files(self, module: str) -> List[str]:
        """Konvertiert Modul-Name zu moeglichen Dateipfaden."""
        parts = module.split('.')
        possibilities = [
            '/'.join(parts) + '.py',
            '/'.join(parts) + '/__init__.py',
            '\\'.join(parts) + '.py',
            '\\'.join(parts) + '\\__init__.py',
        ]
        return possibilities

    def _check_requirements(
        self,
        project_files: Dict[str, str],
        result: PreDockerValidationResult
    ):
        """Prueft requirements.txt auf ungueltige Pakete."""
        req_files = [f for f in project_files if 'requirements' in f.lower()]

        for req_file in req_files:
            content = project_files[req_file]

            for line_num, line in enumerate(content.split('\n'), 1):
                line = line.strip()
                if not line or line.startswith('#'):
                    continue

                # Extrahiere Paketname (vor ==, >=, etc.)
                package = re.split(r'[=<>!~\[]', line)[0].strip().lower()

                if package in self.INVALID_PACKAGES:
                    result.add_issue(ValidationIssue(
                        file_path=req_file,
                        issue_type="invalid_package",
                        line_number=line_num,
                        message=f"'{package}' ist kein gueltiges Python-Paket",
                        suggested_fix=f"Entferne '{package}' - es ist eine JS/CSS Library, kein Python-Paket",
                        severity="error"
                    ))

    # =========================================================================
    # AENDERUNG 02.02.2026: PyPI-Versionsvalidierung
    # Prueft ob angegebene Paketversionen auf PyPI existieren
    # =========================================================================

    def _check_pypi_versions(
        self,
        project_files: Dict[str, str],
        result: PreDockerValidationResult
    ):
        """
        Prueft ob Paketversionen in requirements.txt auf PyPI existieren.
        Nur bei exakten Versionen (==) wird geprueft.
        """
        if not self._pypi_check_enabled:
            logger.debug("PyPI-Check deaktiviert - requests nicht verfuegbar")
            return

        req_files = [f for f in project_files if 'requirements' in f.lower()]

        for req_file in req_files:
            content = project_files[req_file]

            for line_num, line in enumerate(content.split('\n'), 1):
                line = line.strip()
                if not line or line.startswith('#') or line.startswith('-'):
                    continue

                # Nur exakte Versionen pruefen (==)
                if '==' not in line:
                    continue

                # Paket und Version extrahieren
                try:
                    # Entferne extras wie [security] und environment markers
                    clean_line = re.split(r'\s*;\s*', line)[0]  # Entferne ; markers
                    clean_line = re.sub(r'\[.*?\]', '', clean_line)  # Entferne [extras]
                    parts = clean_line.split('==')
                    if len(parts) != 2:
                        continue
                    package = parts[0].strip().lower()
                    version = parts[1].strip()
                except (ValueError, IndexError):
                    continue

                # PyPI-Abfrage (mit Cache)
                cache_key = f"{package}=={version}"
                if cache_key in self._pypi_cache:
                    exists = self._pypi_cache[cache_key]
                else:
                    exists = self._version_exists_on_pypi(package, version)
                    self._pypi_cache[cache_key] = exists

                if not exists:
                    result.add_issue(ValidationIssue(
                        file_path=req_file,
                        issue_type="pypi_version_not_found",
                        line_number=line_num,
                        message=f"Version '{version}' von '{package}' existiert nicht auf PyPI",
                        suggested_fix=f"Pruefe existierende Versionen auf pypi.org/project/{package} oder verwende '>=' statt '=='",
                        severity="error"
                    ))

    def _version_exists_on_pypi(self, package: str, version: str) -> bool:
        """
        Prueft via PyPI JSON API ob eine spezifische Version existiert.
        Bei Netzwerkfehlern: True zurueckgeben (fail-open).
        """
        if not REQUESTS_AVAILABLE:
            return True

        try:
            url = f"https://pypi.org/pypi/{package}/{version}/json"
            resp = requests.get(url, timeout=5)
            return resp.status_code == 200
        except requests.RequestException as e:
            logger.debug(f"PyPI-Check fehlgeschlagen fuer {package}=={version}: {e}")
            return True  # Fail-open bei Netzwerkproblemen
        except Exception as e:
            logger.warning(f"Unerwarteter Fehler bei PyPI-Check: {e}")
            return True

    def _generate_feedback(self, result: PreDockerValidationResult) -> str:
        """Generiert strukturiertes Feedback fuer den Coder."""
        if result.is_valid and not result.warnings:
            return ""

        feedback = "## PRE-DOCKER VALIDIERUNG FEHLGESCHLAGEN\n\n"

        if result.issues:
            feedback += "### FEHLER (muessen behoben werden):\n"
            for issue in result.issues:
                feedback += f"\n**{issue.file_path}** ({issue.issue_type})\n"
                feedback += f"- Problem: {issue.message}\n"
                if issue.line_number:
                    feedback += f"- Zeile: {issue.line_number}\n"
                feedback += f"- Loesung: {issue.suggested_fix}\n"

        if result.warnings:
            feedback += "\n### WARNUNGEN:\n"
            for warning in result.warnings:
                feedback += f"- {warning.file_path}: {warning.message}\n"

        feedback += "\n### ANLEITUNG ZUR KORREKTUR:\n"
        feedback += "1. Behebe alle FEHLER in der angegebenen Reihenfolge\n"
        feedback += "2. Bei zirkulaeren Imports: __init__.py minimal halten\n"
        feedback += "3. Bei Truncation: Datei komplett neu generieren\n"
        feedback += "4. Bei ungueltigem Paket: Aus requirements.txt entfernen\n"
        feedback += "5. Bei ungueliger Version: Verwende '>=' statt '==' oder pruefe pypi.org\n"

        return feedback


# =============================================================================
# Convenience-Funktion fuer externen Aufruf
# =============================================================================

def validate_before_docker(project_files: Dict[str, str]) -> PreDockerValidationResult:
    """
    Convenience-Funktion: Validiert Code vor Docker-Lauf.

    Args:
        project_files: Dict mit {filepath: content}

    Returns:
        PreDockerValidationResult

    Beispiel:
        result = validate_before_docker({"src/__init__.py": "...", "src/routes.py": "..."})
        if not result.is_valid:
            print(result.feedback_for_coder)
    """
    validator = PreDockerValidator()
    return validator.validate(project_files)
