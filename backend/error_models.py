# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 02.02.2026
Version: 1.2
Beschreibung: Error-Analyzer Datenmodelle und Regex-Patterns.
              Extrahiert aus error_analyzer.py (Regel 1: Max 500 Zeilen)

              AENDERUNG 02.02.2026 v1.2: ImportError Patterns fuer zirkulaere Imports
              - IMPORT_ERROR_PATTERNS hinzugefuegt (conftest, circular, incomplete)
              - Dependency-Konflikt Patterns erweitert (ResolutionImpossible)
              AENDERUNG 02.02.2026 v1.1: Issue #10 - pip/Docker Fehler-Patterns
              - PIP_ERROR_PATTERNS hinzugefuegt
              - pip_dependency zu ERROR_PRIORITY_MAP hinzugefuegt
"""

import re
from dataclasses import dataclass, field
from typing import List


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


# =============================================================================
# Regex-Pattern fuer verschiedene Fehlertypen
# =============================================================================

PYTHON_TRACEBACK_PATTERN = re.compile(
    r'File "([^"]+)", line (\d+)',
    re.MULTILINE
)

PYTHON_SYNTAX_ERROR_PATTERN = re.compile(
    r'File "([^"]+)", line (\d+)\n.*\n.*SyntaxError: (.+)',
    re.MULTILINE
)

# Deutsches Sandbox-Format erkennen
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

# =============================================================================
# AENDERUNG 02.02.2026: Docker/pip Fehler-Patterns fuer TargetedFix
# Issue #10: TargetedFix soll pip/docker-Fehler erkennen
# =============================================================================

PIP_ERROR_PATTERNS = [
    # "No module named pytest" oder "No module named 'pytest'"
    (re.compile(r"No module named ['\"]?(\w+)['\"]?", re.IGNORECASE), "missing_module"),
    # "ERROR: No matching distribution found for bootstrap"
    (re.compile(r"ERROR:\s*No matching distribution found for (\S+)", re.IGNORECASE), "invalid_package"),
    # "ModuleNotFoundError: No module named 'xyz'"
    (re.compile(r"ModuleNotFoundError:\s*No module named ['\"]?([^'\"]+)['\"]?", re.IGNORECASE), "missing_module"),
    # "ImportError: cannot import name 'xyz'"
    (re.compile(r"ImportError:\s*cannot import name ['\"]?(\w+)['\"]?", re.IGNORECASE), "import_error"),
    # "pip install xyz failed" oder aehnlich
    (re.compile(r"pip install (\S+).*(?:failed|error)", re.IGNORECASE), "pip_install_failed"),
    # "Could not find a version that satisfies the requirement xyz"
    (re.compile(r"Could not find a version that satisfies the requirement (\S+)", re.IGNORECASE), "invalid_package"),
    # AENDERUNG 02.02.2026: Dependency-Konflikt Patterns hinzugefuegt
    # AENDERUNG 02.02.2026 v1.5: Capture-Gruppen hinzugefuegt (sonst schlaegt match.group(1) fehl)
    # "ResolutionImpossible" - pip kann Abhaengigkeiten nicht aufloesen
    (re.compile(r"(ResolutionImpossible)", re.IGNORECASE), "dependency_conflict"),
    # "conflicting dependencies" - Versionskonflikte
    (re.compile(r"(conflicting dependencies)", re.IGNORECASE), "dependency_conflict"),
    # "these package versions have conflicting dependencies"
    (re.compile(r"(package versions have conflicting dependencies)", re.IGNORECASE), "dependency_conflict"),
    # AENDERUNG 02.02.2026: Version nicht gefunden mit Paketname
    # "ERROR: No matching distribution found for cssutils==2.8.2" - Extrahiere Paketname mit Version
    (re.compile(r"from versions:.*?(?:ERROR|$)", re.IGNORECASE | re.DOTALL), "version_not_found"),
]

# AENDERUNG 03.02.2026: pytest.ini und Config-Fehler Patterns
# Format: "ERROR: C:\...\pytest.ini:1: unexpected line: 'ini'"
# AENDERUNG 03.02.2026 v1.1: Pattern fuer Windows-Pfade mit C:\ korrigiert
CONFIG_ERROR_PATTERNS = [
    # pytest.ini / setup.cfg Fehler: "ERROR: path:line: message"
    # AENDERUNG 03.02.2026: .+? (non-greedy) statt [^\s:]+ um Windows-Pfade (C:\...) zu erlauben
    (re.compile(r"ERROR:\s*(.+?\.(?:ini|cfg|toml|yaml)):(\d+):\s*(.+)", re.IGNORECASE), "config_error"),
    # pytest unexpected line Format
    (re.compile(r"unexpected line:\s*['\"]?([^'\"]+)['\"]?", re.IGNORECASE), "config_syntax"),
    # INI-Parser Fehler
    (re.compile(r"(?:ini|config).*(?:error|invalid|unexpected)", re.IGNORECASE), "config_error"),
]

# AENDERUNG 02.02.2026: Import-Fehler Patterns fuer zirkulaere Imports und conftest
IMPORT_ERROR_PATTERNS = [
    # "ImportError while loading conftest '/app/tests/conftest.py'"
    (re.compile(r"ImportError while loading.*['\"]([^'\"]+)['\"]", re.IGNORECASE), "conftest_import"),
    # "src/__init__.py:3: in <module>" - Zirkulaerer Import mit Zeilennummer
    (re.compile(r"(\S+\.py):(\d+):\s*in\s*<module>", re.IGNORECASE), "circular_import"),
    # "from src import" gefolgt von nichts (abgebrochener Import)
    (re.compile(r"from\s+(\S+)\s+import\s*$", re.MULTILINE), "incomplete_import"),
]

# =============================================================================
# Prioritaets-Mapping fuer Fehlertypen
# =============================================================================

ERROR_PRIORITY_MAP = {
    "syntax": 0,
    "config": 0,  # AENDERUNG 03.02.2026: Config-Fehler (pytest.ini) blockieren Tests
    "truncation": 1,
    "pip_dependency": 1,  # AENDERUNG 02.02.2026: Hohe Prioritaet - muss vor anderen Fehlern gefixt werden
    "import": 2,
    "runtime": 3,
    "test": 4,
    "review": 5,
    "unknown": 6
}
