# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 06.02.2026
Version: 1.0
Beschreibung: Unit Tests fuer PreDockerValidator - Validierung von generiertem Code
              vor dem Docker-Lauf.

              Tests validieren:
              - ValidationIssue Erstellung
              - PreDockerValidationResult Fehler- und Warnungsverwaltung
              - Truncation-Erkennung (_is_python_file_complete)
              - Syntax-Checks (AST-Parsing)
              - Import-Extraktion und zirkulaere Import-Erkennung
              - Modul-zu-Dateipfad-Konvertierung
              - Requirements-Validierung (ungueltige Pakete)
              - Feedback-Generierung
              - Convenience-Funktion validate_before_docker
"""

import pytest
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.pre_docker_validator import (
    PreDockerValidator,
    PreDockerValidationResult,
    ValidationIssue,
    validate_before_docker,
)


# =========================================================================
# Fixtures
# =========================================================================

@pytest.fixture
def validator():
    """Erstellt PreDockerValidator mit deaktiviertem PyPI-Check."""
    v = PreDockerValidator()
    # PyPI-Netzwerkaufrufe deaktivieren fuer stabile Tests
    v._pypi_check_enabled = False
    return v


@pytest.fixture
def valid_python_project():
    """Gueltiges Python-Projekt ohne Fehler."""
    return {
        "app.py": "def hello():\n    return 'world'\n",
        "utils.py": "def add(a, b):\n    return a + b\n",
        "requirements.txt": "flask>=3.0.0\nrequests>=2.31.0\n",
    }


@pytest.fixture
def truncated_python_project():
    """Python-Projekt mit abgeschnittenem Code."""
    return {
        "app.py": "def hello():\n    return 'world'\n\ndef broken(\n",
    }


# =========================================================================
# Test: ValidationIssue Erstellung
# =========================================================================

class TestValidationIssue:
    """Tests fuer die ValidationIssue Datenklasse."""

    def test_erstellung_mit_standardwerten(self):
        """ValidationIssue wird korrekt mit Standardwerten erstellt."""
        issue = ValidationIssue(
            file_path="test.py",
            issue_type="syntax"
        )
        assert issue.file_path == "test.py"
        assert issue.issue_type == "syntax"
        assert issue.line_number == 0, "Erwartet: 0, Erhalten: {}".format(issue.line_number)
        assert issue.message == "", "Erwartet: leerer String"
        assert issue.suggested_fix == "", "Erwartet: leerer String"
        assert issue.severity == "error", "Erwartet: 'error', Erhalten: '{}'".format(issue.severity)


# =========================================================================
# Test: PreDockerValidationResult
# =========================================================================

class TestPreDockerValidationResult:
    """Tests fuer die PreDockerValidationResult Datenklasse."""

    def test_add_issue_error_setzt_is_valid_false(self):
        """Hinzufuegen eines Error-Issues setzt is_valid auf False."""
        result = PreDockerValidationResult(is_valid=True)
        error_issue = ValidationIssue(
            file_path="app.py",
            issue_type="syntax",
            message="SyntaxError in Zeile 5",
            severity="error"
        )
        result.add_issue(error_issue)

        assert result.is_valid is False, "Erwartet: is_valid=False nach Error-Issue"
        assert len(result.issues) == 1, "Erwartet: 1 Issue, Erhalten: {}".format(len(result.issues))
        assert len(result.warnings) == 0, "Erwartet: 0 Warnings"

    def test_add_issue_warning_behaelt_is_valid(self):
        """Hinzufuegen einer Warnung aendert is_valid nicht."""
        result = PreDockerValidationResult(is_valid=True)
        warning_issue = ValidationIssue(
            file_path="app.py",
            issue_type="style",
            message="Code-Stil Warnung",
            severity="warning"
        )
        result.add_issue(warning_issue)

        assert result.is_valid is True, "Erwartet: is_valid=True nach Warning-Issue"
        assert len(result.issues) == 0, "Erwartet: 0 Issues"
        assert len(result.warnings) == 1, "Erwartet: 1 Warning, Erhalten: {}".format(len(result.warnings))


# =========================================================================
# Test: _is_python_file_complete
# =========================================================================

class TestIsPythonFileComplete:
    """Tests fuer die Truncation-Erkennung in Python-Dateien."""

    def test_leere_datei(self, validator):
        """Leere Datei wird als unvollstaendig erkannt."""
        is_complete, reason = validator._is_python_file_complete("", "test.py")
        assert is_complete is False, "Erwartet: unvollstaendig bei leerem Inhalt"
        assert "leer" in reason.lower(), "Erwartet: 'leer' in Begruendung, Erhalten: '{}'".format(reason)

    def test_gueltige_vollstaendige_datei(self, validator):
        """Vollstaendige Python-Datei wird als komplett erkannt."""
        content = "def hello():\n    return 'world'\n"
        is_complete, reason = validator._is_python_file_complete(content, "test.py")
        assert is_complete is True, "Erwartet: vollstaendig, Erhalten: ({}, '{}')".format(is_complete, reason)
        assert reason == "", "Erwartet: leere Begruendung bei vollstaendigem Code"

    def test_endet_mit_offenem_konstrukt(self, validator):
        """Datei die mit offenem Konstrukt endet wird erkannt."""
        content = "def hello():\n    return 'world'\n\ndef broken(\n"
        is_complete, reason = validator._is_python_file_complete(content, "test.py")
        assert is_complete is False, "Erwartet: unvollstaendig bei offenem Konstrukt"
        assert "Endet mit offenem Konstrukt" in reason, \
            "Erwartet: 'Endet mit offenem Konstrukt' in Begruendung, Erhalten: '{}'".format(reason)

    def test_unbalancierte_klammern(self, validator):
        """Unbalancierte Klammern werden erkannt."""
        # Inhalt mit mehr oeffnenden als schliessenden Klammern
        # Muss syntaktisch parsebar sein damit Check 2 (AST) nicht greift
        content = "x = '(' + '(' + ')'\n"
        # Dieser Code ist syntaktisch korrekt, aber hat unbalancierte Klammern
        # in den String-Literalen - zaehlt trotzdem als Zeichen
        # Besseres Beispiel: Code der AST parst aber unbalancierte Klammern hat
        content = "# kommentar (\ndef hello():\n    return 'world'\n"
        is_complete, reason = validator._is_python_file_complete(content, "test.py")
        assert is_complete is False, "Erwartet: unvollstaendig bei unbalancierten Klammern"
        assert "ungeschlossene Klammern" in reason, \
            "Erwartet: 'ungeschlossene Klammern' in Begruendung, Erhalten: '{}'".format(reason)

    def test_ast_truncation_unexpected_eof(self, validator):
        """AST-Fehler 'unexpected eof' wird als Truncation erkannt."""
        # Code der einen unexpected EOF SyntaxError ausloest
        content = "def hello():\n"
        is_complete, reason = validator._is_python_file_complete(content, "test.py")
        assert is_complete is False, "Erwartet: unvollstaendig bei unexpected EOF"
        # Kann durch TRUNCATION_ENDINGS (":") oder AST-Fehler erkannt werden
        assert reason != "", "Erwartet: nicht-leere Begruendung"


# =========================================================================
# Test: _check_syntax
# =========================================================================

class TestCheckSyntax:
    """Tests fuer die Syntax-Validierung."""

    def test_gueltiger_code_keine_issues(self, validator):
        """Gueltiger Python-Code erzeugt keine Syntax-Issues."""
        project_files = {
            "app.py": "def hello():\n    return 'world'\n",
        }
        result = PreDockerValidationResult(is_valid=True)
        validator._check_syntax(project_files, result)

        assert len(result.issues) == 0, "Erwartet: keine Issues bei gueltigem Code"
        assert result.is_valid is True

    def test_syntax_fehler_erzeugt_issue(self, validator):
        """Echter Syntax-Fehler wird als Issue gemeldet."""
        # Syntax-Fehler der nicht als Truncation gilt
        # (nicht "unexpected eof" oder "expected an indented block")
        project_files = {
            "app.py": "def hello():\n    return 'world'\n\nx = 1 +* 2\n",
        }
        result = PreDockerValidationResult(is_valid=True)
        validator._check_syntax(project_files, result)

        assert len(result.issues) > 0, "Erwartet: mindestens 1 Issue bei Syntax-Fehler"
        assert result.is_valid is False
        syntax_issues = [i for i in result.issues if i.issue_type == "syntax"]
        assert len(syntax_issues) > 0, "Erwartet: mindestens 1 Syntax-Issue"


# =========================================================================
# Test: _extract_imports
# =========================================================================

class TestExtractImports:
    """Tests fuer die Import-Extraktion."""

    def test_lokale_imports_werden_extrahiert(self, validator):
        """Lokale Imports (src, app, etc.) werden korrekt extrahiert."""
        content = "from src.routes import blueprint\nimport src.models\n"
        imports = validator._extract_imports(content)

        assert "src.routes" in imports, "Erwartet: 'src.routes' in Imports"
        assert "src.models" in imports, "Erwartet: 'src.models' in Imports"

    def test_stdlib_imports_werden_ignoriert(self, validator):
        """Standard-Library Imports werden nicht extrahiert."""
        content = "import os\nimport sys\nfrom pathlib import Path\nimport json\n"
        imports = validator._extract_imports(content)

        assert len(imports) == 0, "Erwartet: keine lokalen Imports bei stdlib-only, Erhalten: {}".format(imports)

    def test_leerer_inhalt(self, validator):
        """Leerer Inhalt gibt leere Import-Liste zurueck."""
        imports = validator._extract_imports("")
        assert imports == [], "Erwartet: leere Liste bei leerem Inhalt"


# =========================================================================
# Test: _module_to_files
# =========================================================================

class TestModuleToFiles:
    """Tests fuer die Modul-zu-Dateipfad Konvertierung."""

    def test_src_routes_erzeugt_erwartete_pfade(self, validator):
        """'src.routes' wird in die erwarteten Dateipfade konvertiert."""
        paths = validator._module_to_files("src.routes")

        assert "src/routes.py" in paths, "Erwartet: 'src/routes.py' in Pfaden"
        assert "src/routes/__init__.py" in paths, "Erwartet: 'src/routes/__init__.py' in Pfaden"
        # Windows-Pfade
        assert "src\\routes.py" in paths, "Erwartet: 'src\\routes.py' in Pfaden"
        assert "src\\routes\\__init__.py" in paths, "Erwartet: 'src\\routes\\__init__.py' in Pfaden"
        assert len(paths) == 4, "Erwartet: 4 Pfad-Varianten, Erhalten: {}".format(len(paths))


# =========================================================================
# Test: _find_import_cycle
# =========================================================================

class TestFindImportCycle:
    """Tests fuer die Zyklus-Erkennung im Import-Graph."""

    def test_zyklus_erkannt(self, validator):
        """Zirkulaerer Import-Zyklus wird erkannt."""
        # Manuell einen Import-Graph mit Zyklus setzen
        validator._import_graph = {
            "src/__init__.py": ["src.routes"],
            "src/routes.py": ["src"],
        }
        cycle = validator._find_import_cycle("src/__init__.py", [])
        assert cycle is not None, "Erwartet: Zyklus gefunden"

    def test_kein_zyklus(self, validator):
        """Kein Zyklus wird korrekt als None zurueckgegeben."""
        validator._import_graph = {
            "src/__init__.py": ["src.routes"],
            "src/routes.py": [],
        }
        cycle = validator._find_import_cycle("src/__init__.py", [])
        assert cycle is None, "Erwartet: kein Zyklus (None)"


# =========================================================================
# Test: _check_circular_imports
# =========================================================================

class TestCheckCircularImports:
    """Tests fuer die zirkulaere Import-Pruefung auf Projektebene."""

    def test_projekt_mit_zirkulaeren_imports(self, validator):
        """Projekt mit zirkulaeren Imports erzeugt Issue."""
        project_files = {
            "src/__init__.py": "from src.routes import bp\n",
            "src/routes.py": "from src import app\n",
        }
        result = PreDockerValidationResult(is_valid=True)
        validator._check_circular_imports(project_files, result)

        circular_issues = [i for i in result.issues if i.issue_type == "circular_import"]
        assert len(circular_issues) > 0, "Erwartet: mindestens 1 zirkulaerer Import Issue"
        assert result.is_valid is False

    def test_projekt_ohne_zirkulaere_imports(self, validator):
        """Projekt ohne zirkulaere Imports erzeugt kein Issue."""
        project_files = {
            "src/__init__.py": "# Kein Import\napp = 'myapp'\n",
            "src/routes.py": "from src import app\n",
        }
        result = PreDockerValidationResult(is_valid=True)
        validator._check_circular_imports(project_files, result)

        circular_issues = [i for i in result.issues if i.issue_type == "circular_import"]
        assert len(circular_issues) == 0, \
            "Erwartet: keine zirkulaeren Import Issues, Erhalten: {}".format(len(circular_issues))
        assert result.is_valid is True


# =========================================================================
# Test: _check_requirements
# =========================================================================

class TestCheckRequirements:
    """Tests fuer die Requirements-Validierung."""

    def test_ungueltiges_paket_erkannt(self, validator):
        """Ungueltiges JS/CSS-Paket in requirements.txt wird erkannt."""
        project_files = {
            "requirements.txt": "flask>=3.0.0\nbootstrap==5.3.0\njquery==3.6.0\n",
        }
        result = PreDockerValidationResult(is_valid=True)
        validator._check_requirements(project_files, result)

        invalid_issues = [i for i in result.issues if i.issue_type == "invalid_package"]
        assert len(invalid_issues) >= 2, \
            "Erwartet: mindestens 2 ungueltige Pakete (bootstrap, jquery), Erhalten: {}".format(len(invalid_issues))
        assert result.is_valid is False

    def test_gueltige_pakete_keine_issues(self, validator):
        """Gueltige Python-Pakete erzeugen keine Issues."""
        project_files = {
            "requirements.txt": "flask>=3.0.0\nrequests>=2.31.0\npytest>=7.0.0\n",
        }
        result = PreDockerValidationResult(is_valid=True)
        validator._check_requirements(project_files, result)

        invalid_issues = [i for i in result.issues if i.issue_type == "invalid_package"]
        assert len(invalid_issues) == 0, \
            "Erwartet: keine ungueltigen Pakete, Erhalten: {}".format(len(invalid_issues))
        assert result.is_valid is True


# =========================================================================
# Test: _generate_feedback
# =========================================================================

class TestGenerateFeedback:
    """Tests fuer die Feedback-Generierung."""

    def test_valides_result_leerer_string(self, validator):
        """Valides Result ohne Warnungen gibt leeren String zurueck."""
        result = PreDockerValidationResult(is_valid=True)
        feedback = validator._generate_feedback(result)

        assert feedback == "", "Erwartet: leerer Feedback-String bei validem Result"

    def test_result_mit_issues_enthaelt_header(self, validator):
        """Result mit Issues generiert Feedback mit Header."""
        result = PreDockerValidationResult(is_valid=False)
        result.issues.append(ValidationIssue(
            file_path="app.py",
            issue_type="syntax",
            message="SyntaxError in Zeile 5",
            severity="error"
        ))
        feedback = validator._generate_feedback(result)

        assert "PRE-DOCKER VALIDIERUNG FEHLGESCHLAGEN" in feedback, \
            "Erwartet: Header im Feedback"
        assert "FEHLER" in feedback, "Erwartet: 'FEHLER' Abschnitt im Feedback"
        assert "app.py" in feedback, "Erwartet: Dateiname im Feedback"


# =========================================================================
# Test: validate_before_docker (Convenience-Funktion)
# =========================================================================

class TestValidateBeforeDocker:
    """Tests fuer die Convenience-Funktion validate_before_docker."""

    def test_gueltiges_projekt(self, valid_python_project, monkeypatch):
        """Gueltiges Projekt wird als valid erkannt."""
        # PyPI-Check global deaktivieren
        monkeypatch.setattr(
            "backend.pre_docker_validator.REQUESTS_AVAILABLE", False
        )
        result = validate_before_docker(valid_python_project)

        assert result.is_valid is True, \
            "Erwartet: is_valid=True bei gueltigem Projekt, Issues: {}".format(
                [(i.file_path, i.message) for i in result.issues]
            )
        assert len(result.issues) == 0, "Erwartet: keine Issues"

    def test_projekt_mit_truncation(self, truncated_python_project, monkeypatch):
        """Projekt mit Truncation wird als invalid erkannt."""
        # PyPI-Check global deaktivieren
        monkeypatch.setattr(
            "backend.pre_docker_validator.REQUESTS_AVAILABLE", False
        )
        result = validate_before_docker(truncated_python_project)

        assert result.is_valid is False, "Erwartet: is_valid=False bei truncated Code"
        assert len(result.issues) > 0, "Erwartet: mindestens 1 Issue"
        # Feedback sollte generiert werden
        assert result.feedback_for_coder != "", "Erwartet: nicht-leeres Feedback"
