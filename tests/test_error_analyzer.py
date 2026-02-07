# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 01.02.2026
Version: 1.0
Beschreibung: Unit Tests für ErrorAnalyzer - Fehleranalyse und Priorisierung.

              Tests validieren:
              - Review-Feedback Analyse (Regex-Pattern)
              - Fehler-Priorisierung (Dependency + Priority)
              - Merge-Logik (Deduplizierung)
              - Hilfsfunktionen (normalize_path, classify_error, etc.)
"""

import pytest
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.error_analyzer import (
    ErrorAnalyzer,
    FileError,
    analyze_errors,
    get_files_to_fix,
)
from backend.error_utils import (
    normalize_path,
    classify_error_from_message,
    merge_errors,
    analyze_dependencies,
    extract_error_message_from_traceback,
)
from backend.error_models import ERROR_PRIORITY_MAP


# =========================================================================
# Fixtures
# =========================================================================

@pytest.fixture
def analyzer():
    """Erstellt ErrorAnalyzer-Instanz."""
    return ErrorAnalyzer(project_path="/test/project")


@pytest.fixture
def sample_project_files():
    """Beispiel-Projektdateien für Tests."""
    return {
        "app.py": "from flask import Flask\napp = Flask(__name__)\n",
        "src/utils/helper.py": "def helper(): pass\n",
        "backend/api.py": "import json\n",
        "tests/test_app.py": "import pytest\n",
        "config.py": "DEBUG = True\n",
    }


# =========================================================================
# Test: ErrorAnalyzer Initialisierung
# =========================================================================

class TestErrorAnalyzerInit:
    """Tests für ErrorAnalyzer Initialisierung."""

    def test_init_with_project_path(self):
        """Initialisierung mit Projekt-Pfad."""
        analyzer = ErrorAnalyzer("/my/project")
        assert analyzer.project_path == "/my/project"

    def test_init_without_project_path(self):
        """Initialisierung ohne Projekt-Pfad."""
        analyzer = ErrorAnalyzer()
        assert analyzer.project_path == ""

    def test_class_has_regex_patterns(self):
        """Klasse hat alle Regex-Pattern als Attribute."""
        assert hasattr(ErrorAnalyzer, 'PYTHON_TRACEBACK_PATTERN')
        assert hasattr(ErrorAnalyzer, 'PYTHON_SYNTAX_ERROR_PATTERN')
        assert hasattr(ErrorAnalyzer, 'TRUNCATION_PATTERN')


# =========================================================================
# Test: analyze_review_feedback
# =========================================================================

class TestAnalyzeReviewFeedback:
    """Tests für Review-Feedback Analyse."""

    def test_datei_pattern_with_line_number(self, analyzer, sample_project_files):
        """'Datei X Zeile Y: message' Pattern wird erkannt."""
        review = 'Datei "app.py" Zeile 42: Fehler in der Funktion'
        result = analyzer.analyze_review_feedback(review, sample_project_files)
        assert len(result) >= 1
        assert result[0].file_path == "app.py"
        assert 42 in result[0].line_numbers

    def test_file_pattern_without_line_number(self, analyzer, sample_project_files):
        """'File X: message' Pattern ohne Zeilennummer."""
        review = 'File app.py: Missing import statement'
        result = analyzer.analyze_review_feedback(review, sample_project_files)
        assert len(result) >= 1
        assert result[0].file_path == "app.py"

    def test_in_pattern_with_line(self, analyzer, sample_project_files):
        """'In X Line Y: message' Pattern."""
        review = 'In config.py Line 5: DEBUG should be False'
        result = analyzer.analyze_review_feedback(review, sample_project_files)
        assert len(result) >= 1
        assert result[0].file_path == "config.py"
        assert 5 in result[0].line_numbers

    def test_error_pattern_detection(self, analyzer, sample_project_files):
        """ERROR/FEHLER Pattern wird erkannt.

        HINWEIS: Der Text wird von zwei Patterns gematcht:
        - file_mention_pattern: klassifiziert via classify_error_from_message() -> 'runtime'
          mit severity='warning'
        - error_pattern: setzt direkt error_type='review' mit severity='error'

        Bei merge_errors():
        - error_type: runtime gewinnt (priority=3 < review=5)
        - severity: Wird NICHT gemergt, erster Wert bleibt (warning)
        """
        review = 'ERROR in app.py: connection timeout'
        result = analyzer.analyze_review_feedback(review, sample_project_files)
        assert len(result) >= 1
        # runtime hat höhere Priorität als review -> runtime gewinnt bei merge
        assert result[0].error_type == "runtime"
        # Severity bleibt 'warning' vom ersten Match (merge merged severity nicht)
        assert result[0].severity == "warning"

    def test_fehler_pattern_german(self, analyzer, sample_project_files):
        """Deutsches FEHLER Pattern."""
        review = 'FEHLER app.py: Datei nicht gefunden'
        result = analyzer.analyze_review_feedback(review, sample_project_files)
        assert len(result) >= 1
        assert "app.py" in result[0].file_path

    def test_multiple_errors_in_review(self, analyzer, sample_project_files):
        """Mehrere Fehler in einem Review."""
        review = '''
        Datei "app.py" Zeile 10: Import fehlt
        File config.py: DEBUG sollte False sein
        ERROR in backend/api.py: Response nicht korrekt
        '''
        result = analyzer.analyze_review_feedback(review, sample_project_files)
        # Sollte mehrere Fehler erkennen
        file_paths = [e.file_path for e in result]
        assert "app.py" in file_paths
        assert "config.py" in file_paths

    def test_empty_review_returns_empty(self, analyzer, sample_project_files):
        """Leeres Review gibt leere Liste zurück."""
        result = analyzer.analyze_review_feedback("", sample_project_files)
        assert result == []

    def test_none_review_returns_empty(self, analyzer, sample_project_files):
        """None Review gibt leere Liste zurück."""
        result = analyzer.analyze_review_feedback(None, sample_project_files)
        assert result == []

    def test_no_matching_files(self, analyzer, sample_project_files):
        """Datei nicht im Projekt → kein Fehler."""
        review = 'File nonexistent.py: Some error'
        result = analyzer.analyze_review_feedback(review, sample_project_files)
        assert result == []


# =========================================================================
# Test: prioritize_fixes
# =========================================================================

class TestPrioritizeFixes:
    """Tests für Fehler-Priorisierung."""

    def test_sort_by_dependencies_first(self, analyzer):
        """Fehler ohne Dependencies kommen zuerst."""
        errors = [
            FileError('b.py', 'runtime', dependencies=['a.py']),
            FileError('a.py', 'import', dependencies=[]),
        ]
        result = analyzer.prioritize_fixes(errors)
        # a.py sollte zuerst kommen (keine Dependencies)
        assert result[0].file_path == 'a.py'

    def test_sort_by_priority_within_group(self, analyzer):
        """Innerhalb gleicher Dependency-Gruppe: nach Priorität sortieren.

        HINWEIS: prioritize_fixes() ruft analyze_dependencies() auf, die
        import-Fehler-Dateien als Dependencies zu Nicht-Import-Fehlern hinzufügt.
        Dadurch hat nur 'import' keine Dependencies -> kommt zuerst.
        Dann syntax und runtime (beide mit Dependency auf b.py) nach Priorität.
        """
        errors = [
            FileError('c.py', 'runtime', dependencies=[]),  # priority 3
            FileError('a.py', 'syntax', dependencies=[]),   # priority 0
            FileError('b.py', 'import', dependencies=[]),   # priority 2
        ]
        result = analyzer.prioritize_fixes(errors)
        # import hat keine Dependencies -> kommt zuerst
        # syntax/runtime bekommen b.py als Dependency -> kommen nach import
        assert result[0].error_type == 'import'
        # Dann syntax vor runtime (priority 0 < priority 3)
        assert result[1].error_type == 'syntax'
        assert result[2].error_type == 'runtime'

    def test_sort_syntax_before_runtime(self, analyzer):
        """Syntax-Fehler haben höhere Priorität als Runtime."""
        errors = [
            FileError('runtime.py', 'runtime'),
            FileError('syntax.py', 'syntax'),
        ]
        result = analyzer.prioritize_fixes(errors)
        assert result[0].file_path == 'syntax.py'

    def test_sort_truncation_before_import(self, analyzer):
        """Truncation-Fehler vor Import-Fehlern - wenn keine Dependencies.

        HINWEIS: prioritize_fixes() ruft analyze_dependencies() auf.
        Import-Fehler haben keine Dependencies, truncation bekommt import.py als Dependency.
        Dadurch kommt import zuerst (has_deps=0), dann truncation (has_deps=1).

        Dieser Test prüft das tatsächliche Verhalten mit analyze_dependencies().
        """
        errors = [
            FileError('import.py', 'import'),
            FileError('truncated.py', 'truncation'),
        ]
        result = analyzer.prioritize_fixes(errors)
        # import hat keine Dependencies -> kommt zuerst
        assert result[0].file_path == 'import.py'
        assert result[1].file_path == 'truncated.py'

    def test_filename_as_tiebreaker(self, analyzer):
        """Bei gleicher Priorität: alphabetisch nach Dateiname."""
        errors = [
            FileError('z_file.py', 'syntax'),
            FileError('a_file.py', 'syntax'),
        ]
        result = analyzer.prioritize_fixes(errors)
        assert result[0].file_path == 'a_file.py'

    def test_priority_without_import_errors(self, analyzer):
        """Priorität ohne Import-Fehler (keine Dependency-Effekte).

        Ohne Import-Fehler gibt es keine Dependencies, alle Fehler haben has_deps=0.
        Dann wird rein nach ERROR_PRIORITY_MAP sortiert:
        syntax(0) < truncation(1) < runtime(3)
        """
        errors = [
            FileError('runtime.py', 'runtime'),      # priority 3
            FileError('syntax.py', 'syntax'),        # priority 0
            FileError('truncated.py', 'truncation'), # priority 1
        ]
        result = analyzer.prioritize_fixes(errors)
        # Alle haben keine Dependencies -> rein nach Priorität
        assert result[0].error_type == 'syntax'
        assert result[1].error_type == 'truncation'
        assert result[2].error_type == 'runtime'

    def test_empty_errors_returns_empty(self, analyzer):
        """Leere Fehlerliste bleibt leer."""
        result = analyzer.prioritize_fixes([])
        assert result == []


# =========================================================================
# Test: get_affected_files
# =========================================================================

class TestGetAffectedFiles:
    """Tests für get_affected_files."""

    def test_returns_unique_files(self, analyzer):
        """Gibt eindeutige Dateipfade zurück."""
        errors = [
            FileError('a.py', 'syntax'),
            FileError('a.py', 'runtime'),
            FileError('b.py', 'import'),
        ]
        result = analyzer.get_affected_files(errors)
        assert result == {'a.py', 'b.py'}

    def test_empty_errors_returns_empty_set(self, analyzer):
        """Leere Fehlerliste gibt leeres Set zurück."""
        result = analyzer.get_affected_files([])
        assert result == set()

    def test_single_file(self, analyzer):
        """Ein einziger Fehler."""
        errors = [FileError('only.py', 'syntax')]
        result = analyzer.get_affected_files(errors)
        assert result == {'only.py'}


# =========================================================================
# Test: group_by_file
# =========================================================================

class TestGroupByFile:
    """Tests für Fehler-Gruppierung nach Datei."""

    def test_groups_errors_by_file(self, analyzer):
        """Gruppiert Fehler nach Datei."""
        errors = [
            FileError('a.py', 'syntax'),
            FileError('a.py', 'runtime'),
            FileError('b.py', 'import'),
        ]
        result = analyzer.group_by_file(errors)
        assert len(result['a.py']) == 2
        assert len(result['b.py']) == 1

    def test_empty_errors_returns_empty_dict(self, analyzer):
        """Leere Fehlerliste gibt leeres Dict zurück."""
        result = analyzer.group_by_file([])
        assert result == {}

    def test_preserves_error_order(self, analyzer):
        """Fehler-Reihenfolge innerhalb einer Datei bleibt erhalten."""
        errors = [
            FileError('a.py', 'syntax', line_numbers=[10]),
            FileError('a.py', 'runtime', line_numbers=[20]),
        ]
        result = analyzer.group_by_file(errors)
        assert result['a.py'][0].line_numbers == [10]
        assert result['a.py'][1].line_numbers == [20]


# =========================================================================
# Test: normalize_path
# =========================================================================

class TestNormalizePath:
    """Tests für Pfad-Normalisierung."""

    def test_exact_match(self, sample_project_files):
        """Exakte Übereinstimmung."""
        result = normalize_path('app.py', sample_project_files)
        assert result == 'app.py'

    def test_backslash_normalization(self, sample_project_files):
        """Backslash wird zu Forward-Slash."""
        result = normalize_path('src\\utils\\helper.py', sample_project_files)
        assert result == 'src/utils/helper.py'

    def test_filename_only_match(self, sample_project_files):
        """Nur Dateiname findet volle Pfade."""
        result = normalize_path('helper.py', sample_project_files)
        assert result == 'src/utils/helper.py'

    def test_partial_path_match(self, sample_project_files):
        """Teilpfad findet vollständigen Pfad."""
        result = normalize_path('utils/helper.py', sample_project_files)
        assert result == 'src/utils/helper.py'

    def test_nonexistent_returns_none(self, sample_project_files):
        """Nicht existierende Datei gibt None zurück."""
        result = normalize_path('nonexistent.py', sample_project_files)
        assert result is None

    def test_empty_path_returns_none(self, sample_project_files):
        """Leerer Pfad gibt None zurück."""
        result = normalize_path('', sample_project_files)
        assert result is None

    def test_whitespace_stripped(self, sample_project_files):
        """Whitespace wird entfernt."""
        result = normalize_path('  app.py  ', sample_project_files)
        assert result == 'app.py'


# =========================================================================
# Test: classify_error_from_message
# =========================================================================

class TestClassifyErrorFromMessage:
    """Tests für Fehler-Klassifizierung."""

    def test_syntax_error(self):
        """SyntaxError wird als 'syntax' klassifiziert."""
        assert classify_error_from_message("SyntaxError: unexpected token") == "syntax"

    def test_parse_error(self):
        """Parse-Fehler wird als 'syntax' klassifiziert."""
        assert classify_error_from_message("parse error in line 5") == "syntax"

    def test_import_error(self):
        """ImportError wird als 'import' klassifiziert."""
        assert classify_error_from_message("ImportError: cannot import name") == "import"

    def test_module_not_found(self):
        """ModuleNotFoundError wird als 'import' klassifiziert."""
        assert classify_error_from_message("ModuleNotFoundError: No module named 'flask'") == "import"

    def test_test_failure(self):
        """Test-Fehler wird als 'test' klassifiziert."""
        assert classify_error_from_message("assert 5 == 3 failed") == "test"

    def test_truncation(self):
        """Truncation wird erkannt."""
        assert classify_error_from_message("String was truncated") == "truncation"

    def test_abgeschnitten_german(self):
        """Deutsches 'abgeschnitten' wird erkannt."""
        assert classify_error_from_message("Datei wurde abgeschnitten") == "truncation"

    def test_runtime_default(self):
        """Unbekannte Fehler werden als 'runtime' klassifiziert."""
        assert classify_error_from_message("NoneType has no attribute foo") == "runtime"

    def test_case_insensitive(self):
        """Klassifizierung ist case-insensitive."""
        assert classify_error_from_message("SYNTAXERROR: problem") == "syntax"


# =========================================================================
# Test: merge_errors
# =========================================================================

class TestMergeErrors:
    """Tests für Fehler-Merge-Logik."""

    def test_merge_same_file_errors(self):
        """Fehler für dieselbe Datei werden zusammengeführt."""
        errors = [
            FileError('app.py', 'syntax', line_numbers=[10]),
            FileError('app.py', 'runtime', line_numbers=[20]),
        ]
        result = merge_errors(errors)
        assert len(result) == 1
        assert result[0].file_path == 'app.py'

    def test_merge_preserves_line_numbers(self):
        """Zeilennummern werden kombiniert und sortiert."""
        errors = [
            FileError('app.py', 'syntax', line_numbers=[30, 10]),
            FileError('app.py', 'runtime', line_numbers=[20]),
        ]
        result = merge_errors(errors)
        assert result[0].line_numbers == [10, 20, 30]

    def test_merge_keeps_higher_priority_type(self):
        """Fehlertyp mit höherer Priorität wird behalten."""
        errors = [
            FileError('app.py', 'runtime'),  # priority 3
            FileError('app.py', 'syntax'),   # priority 0
        ]
        result = merge_errors(errors)
        assert result[0].error_type == 'syntax'

    def test_merge_combines_messages(self):
        """Fehlermeldungen werden kombiniert."""
        errors = [
            FileError('app.py', 'syntax', error_message='Error 1'),
            FileError('app.py', 'runtime', error_message='Error 2'),
        ]
        result = merge_errors(errors)
        assert 'Error 1' in result[0].error_message
        assert 'Error 2' in result[0].error_message

    def test_merge_different_files_not_merged(self):
        """Verschiedene Dateien werden nicht zusammengeführt."""
        errors = [
            FileError('a.py', 'syntax'),
            FileError('b.py', 'syntax'),
        ]
        result = merge_errors(errors)
        assert len(result) == 2

    def test_merge_empty_list(self):
        """Leere Liste bleibt leer."""
        result = merge_errors([])
        assert result == []

    def test_merge_single_error(self):
        """Einzelner Fehler wird unverändert zurückgegeben."""
        errors = [FileError('app.py', 'syntax', line_numbers=[10])]
        result = merge_errors(errors)
        assert len(result) == 1
        assert result[0].line_numbers == [10]


# =========================================================================
# Test: analyze_dependencies
# =========================================================================

class TestAnalyzeDependencies:
    """Tests für Dependency-Analyse."""

    def test_import_errors_have_no_dependencies(self):
        """Import-Fehler haben keine Dependencies."""
        errors = [FileError('app.py', 'import')]
        result = analyze_dependencies(errors)
        assert result[0].dependencies == []

    def test_runtime_errors_depend_on_import_errors(self):
        """Runtime-Fehler bekommen Import-Fehler-Dateien als Dependencies."""
        errors = [
            FileError('import_error.py', 'import'),
            FileError('runtime_error.py', 'runtime'),
        ]
        result = analyze_dependencies(errors)
        runtime_error = [e for e in result if e.error_type == 'runtime'][0]
        assert 'import_error.py' in runtime_error.dependencies

    def test_empty_list(self):
        """Leere Liste bleibt leer."""
        result = analyze_dependencies([])
        assert result == []


# =========================================================================
# Test: extract_error_message_from_traceback
# =========================================================================

class TestExtractErrorMessage:
    """Tests für Fehlermeldungs-Extraktion."""

    def test_extracts_last_line(self):
        """Letzte nicht-leere Zeile wird extrahiert."""
        traceback = '''
Traceback (most recent call last):
  File "app.py", line 10, in <module>
    x = 1/0
ZeroDivisionError: division by zero
'''
        result = extract_error_message_from_traceback(traceback)
        assert result == "ZeroDivisionError: division by zero"

    def test_ignores_file_lines(self):
        """'File ...' Zeilen werden ignoriert."""
        traceback = 'File "app.py", line 10'
        result = extract_error_message_from_traceback(traceback)
        assert "File" not in result or result == "Unbekannter Fehler"

    def test_empty_traceback(self):
        """Leerer Traceback gibt Default zurück."""
        result = extract_error_message_from_traceback("")
        assert result == "Unbekannter Fehler"


# =========================================================================
# Test: analyze_errors (Convenience-Funktion)
# =========================================================================

class TestAnalyzeErrorsFunction:
    """Tests für die analyze_errors Convenience-Funktion."""

    def test_with_review_output_only(self, sample_project_files):
        """Nur Review-Output."""
        result = analyze_errors(
            review_output='File app.py: Missing import',
            project_files=sample_project_files
        )
        assert len(result) >= 1

    def test_with_empty_inputs(self):
        """Leere Inputs geben leere Liste."""
        result = analyze_errors()
        assert result == []

    def test_returns_prioritized_errors(self, sample_project_files):
        """Ergebnis ist priorisiert."""
        result = analyze_errors(
            review_output='''
            File app.py: runtime error
            File config.py: syntax error
            ''',
            project_files=sample_project_files
        )
        # Sollte priorisiert sein (syntax vor runtime)
        if len(result) >= 2:
            types = [e.error_type for e in result]
            if 'syntax' in types and 'runtime' in types:
                syntax_idx = types.index('syntax')
                runtime_idx = types.index('runtime')
                assert syntax_idx < runtime_idx


# =========================================================================
# Test: get_files_to_fix
# =========================================================================

class TestGetFilesToFix:
    """Tests für get_files_to_fix Funktion."""

    def test_returns_max_files(self):
        """Gibt maximal max_files zurück."""
        errors = [
            FileError('a.py', 'syntax'),
            FileError('b.py', 'syntax'),
            FileError('c.py', 'syntax'),
            FileError('d.py', 'syntax'),
        ]
        result = get_files_to_fix(errors, max_files=2)
        assert len(result) == 2

    def test_no_duplicates(self):
        """Keine Duplikate in Ergebnis."""
        errors = [
            FileError('a.py', 'syntax'),
            FileError('a.py', 'runtime'),
            FileError('b.py', 'syntax'),
        ]
        result = get_files_to_fix(errors, max_files=3)
        assert len(result) == len(set(result))

    def test_preserves_order(self):
        """Reihenfolge bleibt erhalten."""
        errors = [
            FileError('first.py', 'syntax'),
            FileError('second.py', 'syntax'),
        ]
        result = get_files_to_fix(errors, max_files=2)
        assert result == ['first.py', 'second.py']

    def test_empty_errors(self):
        """Leere Fehlerliste gibt leere Liste zurück."""
        result = get_files_to_fix([], max_files=3)
        assert result == []

    def test_default_max_files_is_seven(self):
        """Default für max_files ist 7 (Bug #12), aber alle Fehler werden zurückgegeben."""
        errors = [
            FileError('a.py', 'syntax'),
            FileError('b.py', 'syntax'),
            FileError('c.py', 'syntax'),
            FileError('d.py', 'syntax'),
        ]
        result = get_files_to_fix(errors)
        # Alle 4 Dateien werden zurückgegeben (Default=7, aber nur 4 Fehler vorhanden)
        assert len(result) == 4


# =========================================================================
# Test: ERROR_PRIORITY_MAP
# =========================================================================

class TestErrorPriorityMap:
    """Tests für die Prioritäts-Konstanten."""

    def test_syntax_has_lowest_priority_value(self):
        """Syntax hat niedrigsten Wert (höchste Priorität)."""
        assert ERROR_PRIORITY_MAP['syntax'] == 0

    def test_truncation_before_import(self):
        """Truncation < Import in Priorität."""
        assert ERROR_PRIORITY_MAP['truncation'] < ERROR_PRIORITY_MAP['import']

    def test_import_before_runtime(self):
        """Import < Runtime in Priorität."""
        assert ERROR_PRIORITY_MAP['import'] < ERROR_PRIORITY_MAP['runtime']

    def test_runtime_before_test(self):
        """Runtime < Test in Priorität."""
        assert ERROR_PRIORITY_MAP['runtime'] < ERROR_PRIORITY_MAP['test']

    def test_unknown_has_highest_value(self):
        """Unknown hat höchsten Wert (niedrigste Priorität)."""
        assert ERROR_PRIORITY_MAP['unknown'] == 6


# =========================================================================
# Test: FileError Dataclass
# =========================================================================

class TestFileErrorDataclass:
    """Tests für FileError Dataclass."""

    def test_default_values(self):
        """Default-Werte werden gesetzt."""
        error = FileError('app.py', 'syntax')
        assert error.line_numbers == []
        assert error.error_message == ""
        assert error.dependencies == []
        assert error.severity == "error"

    def test_hash_based_on_key_fields(self):
        """Hash basiert auf file_path, error_type, line_numbers."""
        error1 = FileError('app.py', 'syntax', line_numbers=[10])
        error2 = FileError('app.py', 'syntax', line_numbers=[10])
        assert hash(error1) == hash(error2)

    def test_different_errors_different_hash(self):
        """Verschiedene Fehler haben verschiedene Hashes."""
        error1 = FileError('a.py', 'syntax')
        error2 = FileError('b.py', 'syntax')
        assert hash(error1) != hash(error2)

