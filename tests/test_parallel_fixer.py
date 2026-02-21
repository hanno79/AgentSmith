# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 14.02.2026
Version: 1.0
Beschreibung: Tests fuer backend/parallel_fixer.py
              Testet FixResult, ParallelFixStats, ParallelFixer.__init__,
              _split_by_dependencies, _get_context_files, _update_progress,
              get_stats, shutdown und should_use_parallel_fix.

              NUR Pure-Logic-Funktionen — KEIN CrewAI/LLM.
"""

import os
import sys
import pytest
from unittest.mock import MagicMock, patch, call
from dataclasses import fields

# Projekt-Root zum Python-Path hinzufuegen
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# FileError direkt aus error_models importieren (kein CrewAI noetig)
from backend.error_models import FileError

# CrewAI-Imports in parallel_fixer mocken, damit kein CrewAI installiert sein muss
_crewai_mock = MagicMock()
sys.modules.setdefault("crewai", _crewai_mock)

# fix_agent Modul mocken (benoetigt CrewAI intern)
_fix_agent_mock = MagicMock()
sys.modules.setdefault("agents.fix_agent", _fix_agent_mock)

# error_analyzer re-exportiert FileError — Mock mit echtem FileError
# AENDERUNG 21.02.2026: setdefault statt direkter Zuweisung
# ROOT-CAUSE-FIX: Direktes sys.modules[...] = Mock ueberschrieb das echte Modul
# fuer ALLE nachfolgenden Tests → get_files_to_fix wurde zu MagicMock
_error_analyzer_mock = MagicMock()
_error_analyzer_mock.FileError = FileError
_error_analyzer_mock.ErrorAnalyzer = MagicMock
sys.modules.setdefault("backend.error_analyzer", _error_analyzer_mock)

from backend.parallel_fixer import (
    FixResult,
    ParallelFixStats,
    ParallelFixer,
    should_use_parallel_fix,
)


# =========================================================================
# Hilfs-Fixtures
# =========================================================================

@pytest.fixture
def mock_manager():
    """Mock-SessionManager fuer ParallelFixer."""
    manager = MagicMock()
    manager.update_agent_status = MagicMock()
    return manager


@pytest.fixture
def sample_config():
    """Minimale Konfiguration fuer ParallelFixer."""
    return {"default_model": "test-model", "mode": "test"}


@pytest.fixture
def fixer(mock_manager, sample_config):
    """Standard-ParallelFixer-Instanz fuer Tests."""
    return ParallelFixer(
        manager=mock_manager,
        config=sample_config,
        max_parallel=3,
        max_retries=2,
    )


def _make_error(
    file_path="src/app.py",
    error_type="syntax",
    line_numbers=None,
    error_message="SyntaxError: unexpected indent",
    dependencies=None,
    severity="error",
):
    """Hilfsfunktion: Erstellt ein FileError-Objekt."""
    return FileError(
        file_path=file_path,
        error_type=error_type,
        line_numbers=line_numbers or [],
        error_message=error_message,
        dependencies=dependencies or [],
        severity=severity,
    )


# =========================================================================
# TestFixResult
# =========================================================================

class TestFixResult:
    """Tests fuer die FixResult Dataclass (Zeile 29-38)."""

    def test_erstellen_mit_pflichtfeldern(self):
        """FixResult mit nur file_path und success erstellen."""
        result = FixResult(file_path="src/main.py", success=True)
        assert result.file_path == "src/main.py"
        assert result.success is True

    def test_default_werte(self):
        """Alle optionalen Felder haben korrekte Defaults."""
        result = FixResult(file_path="x.py", success=False)
        assert result.new_content is None
        assert result.error_message == ""
        assert result.duration_seconds == 0.0
        assert result.attempts == 1
        assert result.original_error is None

    def test_vollstaendige_erstellung(self):
        """FixResult mit allen Feldern befuellt."""
        error = _make_error()
        result = FixResult(
            file_path="src/app.py",
            success=True,
            new_content="print('fixed')",
            error_message="",
            duration_seconds=2.5,
            attempts=3,
            original_error=error,
        )
        assert result.new_content == "print('fixed')"
        assert result.duration_seconds == 2.5
        assert result.attempts == 3
        assert result.original_error is error

    def test_fehlgeschlagenes_ergebnis(self):
        """FixResult fuer fehlgeschlagene Korrektur."""
        result = FixResult(
            file_path="broken.py",
            success=False,
            error_message="Timeout bei Korrektur",
        )
        assert result.success is False
        assert "Timeout" in result.error_message
        assert result.new_content is None

    def test_dataclass_felder_vollstaendig(self):
        """Alle erwarteten Felder sind vorhanden."""
        feld_namen = {f.name for f in fields(FixResult)}
        erwartet = {
            "file_path", "success", "new_content", "error_message",
            "duration_seconds", "attempts", "original_error",
        }
        assert feld_namen == erwartet, (
            f"Erwartet: {erwartet}, Erhalten: {feld_namen}"
        )


# =========================================================================
# TestParallelFixStats
# =========================================================================

class TestParallelFixStats:
    """Tests fuer die ParallelFixStats Dataclass (Zeile 42-50)."""

    def test_default_werte(self):
        """Alle Felder starten mit korrekten Defaults."""
        stats = ParallelFixStats()
        assert stats.total_files == 0
        assert stats.successful_fixes == 0
        assert stats.failed_fixes == 0
        assert stats.total_duration_seconds == 0.0
        assert stats.parallel_batches == 0
        assert stats.files_fixed == []
        assert stats.files_failed == []

    def test_mit_werten(self):
        """Stats mit gesetzten Werten."""
        stats = ParallelFixStats(
            total_files=5,
            successful_fixes=3,
            failed_fixes=2,
            total_duration_seconds=12.7,
            parallel_batches=2,
            files_fixed=["a.py", "b.py", "c.py"],
            files_failed=["d.py", "e.py"],
        )
        assert stats.total_files == 5
        assert stats.successful_fixes == 3
        assert stats.failed_fixes == 2
        assert stats.total_duration_seconds == 12.7
        assert stats.parallel_batches == 2
        assert len(stats.files_fixed) == 3
        assert len(stats.files_failed) == 2

    def test_listen_sind_unabhaengig(self):
        """Verschiedene Instanzen teilen sich keine Listen (mutable default)."""
        stats1 = ParallelFixStats()
        stats2 = ParallelFixStats()
        stats1.files_fixed.append("x.py")
        assert "x.py" not in stats2.files_fixed, (
            "Mutable-Default-Fehler: Listen werden geteilt"
        )

    def test_dataclass_felder_vollstaendig(self):
        """Alle erwarteten Felder sind vorhanden."""
        feld_namen = {f.name for f in fields(ParallelFixStats)}
        erwartet = {
            "total_files", "successful_fixes", "failed_fixes",
            "total_duration_seconds", "parallel_batches",
            "files_fixed", "files_failed",
        }
        assert feld_namen == erwartet


# =========================================================================
# TestParallelFixerInit
# =========================================================================

class TestParallelFixerInit:
    """Tests fuer ParallelFixer.__init__ (Zeile 64-88)."""

    def test_standard_initialisierung(self, mock_manager, sample_config):
        """Standard-Initialisierung mit Default-Werten."""
        fixer = ParallelFixer(manager=mock_manager, config=sample_config)
        assert fixer.manager is mock_manager
        assert fixer.config is sample_config
        assert fixer.max_parallel == 3
        assert fixer.max_retries == 2
        assert fixer.router is None
        assert fixer.executor is not None
        assert isinstance(fixer.stats, ParallelFixStats)
        assert fixer._progress_callback is None
        fixer.shutdown()

    def test_benutzerdefinierte_parameter(self, mock_manager, sample_config):
        """Initialisierung mit benutzerdefinierten Werten."""
        mock_router = MagicMock()
        fixer = ParallelFixer(
            manager=mock_manager,
            config=sample_config,
            max_parallel=5,
            max_retries=4,
            router=mock_router,
        )
        assert fixer.max_parallel == 5
        assert fixer.max_retries == 4
        assert fixer.router is mock_router
        fixer.shutdown()

    def test_manager_none_erlaubt(self, sample_config):
        """Manager kann None sein (optional)."""
        fixer = ParallelFixer(manager=None, config=sample_config)
        assert fixer.manager is None
        fixer.shutdown()

    def test_stats_initial_leer(self, fixer):
        """Stats sind nach Initialisierung leer."""
        stats = fixer.get_stats()
        assert stats.total_files == 0
        assert stats.successful_fixes == 0
        assert stats.files_fixed == []
        fixer.shutdown()


# =========================================================================
# TestSplitByDependencies
# =========================================================================

class TestSplitByDependencies:
    """Tests fuer ParallelFixer._split_by_dependencies (Zeile 442-463)."""

    def test_alle_unabhaengig(self, fixer):
        """Fehler ohne Abhaengigkeiten landen in 'independent'."""
        errors = [
            _make_error("a.py"),
            _make_error("b.py"),
            _make_error("c.py"),
        ]
        independent, dependent = fixer._split_by_dependencies(errors)
        assert len(independent) == 3
        assert len(dependent) == 0
        fixer.shutdown()

    def test_alle_abhaengig(self, fixer):
        """Fehler mit Abhaengigkeiten landen in 'dependent'."""
        errors = [
            _make_error("a.py", dependencies=["b.py"]),
            _make_error("c.py", dependencies=["d.py", "e.py"]),
        ]
        independent, dependent = fixer._split_by_dependencies(errors)
        assert len(independent) == 0
        assert len(dependent) == 2
        fixer.shutdown()

    def test_gemischt(self, fixer):
        """Gemischte Fehler werden korrekt aufgeteilt."""
        errors = [
            _make_error("a.py"),
            _make_error("b.py", dependencies=["a.py"]),
            _make_error("c.py"),
            _make_error("d.py", dependencies=["c.py"]),
        ]
        independent, dependent = fixer._split_by_dependencies(errors)
        assert len(independent) == 2
        assert len(dependent) == 2
        # Reihenfolge pruefen
        assert independent[0].file_path == "a.py"
        assert independent[1].file_path == "c.py"
        assert dependent[0].file_path == "b.py"
        assert dependent[1].file_path == "d.py"
        fixer.shutdown()

    def test_leere_liste(self, fixer):
        """Leere Fehlerliste ergibt leere Tupel."""
        independent, dependent = fixer._split_by_dependencies([])
        assert independent == []
        assert dependent == []
        fixer.shutdown()

    def test_leere_dependency_liste_zaehlt_als_unabhaengig(self, fixer):
        """Fehler mit leerer dependencies-Liste sind unabhaengig."""
        errors = [_make_error("x.py", dependencies=[])]
        independent, dependent = fixer._split_by_dependencies(errors)
        assert len(independent) == 1
        assert len(dependent) == 0
        fixer.shutdown()


# =========================================================================
# TestGetContextFiles
# =========================================================================

class TestGetContextFiles:
    """Tests fuer ParallelFixer._get_context_files (Zeile 466-495)."""

    def test_dependencies_als_kontext(self, fixer):
        """Abhaengigkeiten werden als Kontext-Dateien aufgenommen."""
        error = _make_error("app.py", dependencies=["lib/utils.py", "lib/db.py"])
        existing = {
            "app.py": "import utils",
            "lib/utils.py": "def helper(): pass",
            "lib/db.py": "def query(): pass",
        }
        context = fixer._get_context_files(error, existing)
        assert "lib/utils.py" in context
        assert "lib/db.py" in context
        assert len(context) <= 3
        fixer.shutdown()

    def test_max_2_dependencies(self, fixer):
        """Maximal 2 Abhaengigkeiten werden aufgenommen ([:2])."""
        error = _make_error(
            "app.py",
            dependencies=["a.py", "b.py", "c.py", "d.py"],
        )
        existing = {
            "app.py": "code",
            "a.py": "a", "b.py": "b", "c.py": "c", "d.py": "d",
        }
        context = fixer._get_context_files(error, existing)
        assert "a.py" in context
        assert "b.py" in context
        # c.py und d.py werden NICHT aufgenommen ([:2] Limit)
        assert "c.py" not in context
        assert "d.py" not in context
        fixer.shutdown()

    def test_fehlermeldung_dateien(self, fixer):
        """Dateien aus der Fehlermeldung werden als Kontext aufgenommen."""
        error = _make_error(
            "app.py",
            error_message="ImportError in lib/helpers.py: cannot import name 'calc'",
        )
        existing = {
            "app.py": "import helpers",
            "lib/helpers.py": "def calc(): pass",
        }
        context = fixer._get_context_files(error, existing)
        assert "lib/helpers.py" in context
        fixer.shutdown()

    def test_max_3_kontext_dateien(self, fixer):
        """Insgesamt maximal 3 Kontext-Dateien."""
        error = _make_error(
            "app.py",
            dependencies=["dep1.py", "dep2.py"],
            error_message="Fehler in extra1.py und extra2.py",
        )
        existing = {
            "app.py": "x",
            "dep1.py": "d1",
            "dep2.py": "d2",
            "extra1.py": "e1",
            "extra2.py": "e2",
        }
        context = fixer._get_context_files(error, existing)
        assert len(context) <= 3
        # 2 Dependencies + maximal 1 aus Fehlermeldung
        assert "dep1.py" in context
        assert "dep2.py" in context
        fixer.shutdown()

    def test_dependency_nicht_vorhanden(self, fixer):
        """Nicht existierende Abhaengigkeiten werden uebersprungen."""
        error = _make_error(
            "app.py",
            dependencies=["nicht_vorhanden.py"],
        )
        existing = {"app.py": "code"}
        context = fixer._get_context_files(error, existing)
        assert len(context) == 0
        fixer.shutdown()

    def test_keine_deps_keine_erwaehnung(self, fixer):
        """Keine Dependencies und keine Erwaehnung ergibt leeren Kontext."""
        error = _make_error("app.py", dependencies=[], error_message="generic error")
        existing = {"app.py": "code", "other.py": "other"}
        context = fixer._get_context_files(error, existing)
        assert context == {}
        fixer.shutdown()

    def test_eigene_datei_aus_fehlermeldung(self, fixer):
        """Wenn die eigene Datei in der Fehlermeldung steht — kein Duplikat-Problem."""
        error = _make_error(
            "app.py",
            error_message="Fehler in app.py Zeile 42",
        )
        existing = {"app.py": "code"}
        context = fixer._get_context_files(error, existing)
        # app.py koennte im Kontext landen — das ist OK (kein Ausschluss)
        assert len(context) <= 3
        fixer.shutdown()

    def test_keine_duplikate_zwischen_deps_und_fehlermeldung(self, fixer):
        """Datei die in deps UND Fehlermeldung steht wird nur einmal aufgenommen."""
        error = _make_error(
            "app.py",
            dependencies=["lib/db.py"],
            error_message="Fehler in lib/db.py",
        )
        existing = {
            "app.py": "x",
            "lib/db.py": "db code",
        }
        context = fixer._get_context_files(error, existing)
        # lib/db.py aus deps, Fehlermeldung ueberspringt es (path not in context)
        assert len(context) == 1
        assert "lib/db.py" in context
        fixer.shutdown()


# =========================================================================
# TestProgressCallback
# =========================================================================

class TestProgressCallback:
    """Tests fuer set_progress_callback und _update_progress (Zeile 91-518)."""

    def test_set_progress_callback(self, fixer):
        """Callback wird korrekt gesetzt."""
        callback = MagicMock()
        fixer.set_progress_callback(callback)
        assert fixer._progress_callback is callback
        fixer.shutdown()

    def test_update_progress_mit_callback(self, fixer):
        """_update_progress ruft Callback korrekt auf."""
        callback = MagicMock()
        fixer.set_progress_callback(callback)
        fixer._update_progress("src/app.py", "erfolgreich", 75.0)
        callback.assert_called_once_with("src/app.py", "erfolgreich", 75.0)
        fixer.shutdown()

    def test_update_progress_ohne_callback(self, fixer):
        """_update_progress ohne Callback verursacht keinen Fehler."""
        # Kein Callback gesetzt — darf nicht abstuerzen
        fixer._update_progress("src/app.py", "laeuft", 50.0)
        fixer.shutdown()

    def test_update_progress_callback_fehler_wird_gefangen(self, fixer):
        """Callback-Fehler werden gefangen und nicht weitergeworfen."""
        callback = MagicMock(side_effect=RuntimeError("Callback kaputt"))
        fixer.set_progress_callback(callback)
        # Soll NICHT abstuerzen
        fixer._update_progress("src/app.py", "test", 10.0)
        callback.assert_called_once()
        fixer.shutdown()

    def test_update_progress_session_manager(self, fixer, mock_manager):
        """_update_progress sendet Update an SessionManager."""
        fixer._update_progress("src/main.py", "running", 25.0)
        mock_manager.update_agent_status.assert_called_once_with(
            "parallel_fixer",
            {
                "status": "running",
                "current_file": "src/main.py",
                "progress": 25.0,
                "message": "running",
            },
        )
        fixer.shutdown()

    def test_update_progress_manager_none(self, sample_config):
        """_update_progress mit manager=None verursacht keinen Fehler."""
        fixer = ParallelFixer(manager=None, config=sample_config)
        # Soll NICHT abstuerzen
        fixer._update_progress("x.py", "ok", 100.0)
        fixer.shutdown()

    def test_update_progress_manager_fehler_wird_ignoriert(self, fixer, mock_manager):
        """SessionManager-Fehler werden ignoriert (pass im except)."""
        mock_manager.update_agent_status.side_effect = Exception("DB Fehler")
        # Soll NICHT abstuerzen
        fixer._update_progress("src/app.py", "test", 50.0)
        fixer.shutdown()


# =========================================================================
# TestGetStatsUndShutdown
# =========================================================================

class TestGetStatsUndShutdown:
    """Tests fuer get_stats und shutdown (Zeile 520-526)."""

    def test_get_stats_gibt_stats_zurueck(self, fixer):
        """get_stats() gibt das interne stats-Objekt zurueck."""
        stats = fixer.get_stats()
        assert isinstance(stats, ParallelFixStats)
        assert stats is fixer.stats
        fixer.shutdown()

    def test_stats_aenderbar(self, fixer):
        """Stats-Objekt kann veraendert werden und bleibt konsistent."""
        fixer.stats.total_files = 10
        fixer.stats.successful_fixes = 7
        fixer.stats.files_fixed.append("test.py")
        stats = fixer.get_stats()
        assert stats.total_files == 10
        assert stats.successful_fixes == 7
        assert "test.py" in stats.files_fixed
        fixer.shutdown()

    def test_shutdown_beendet_executor(self, fixer):
        """shutdown() beendet den ThreadPoolExecutor."""
        fixer.shutdown()
        # Nach shutdown soll der Executor keine neuen Tasks annehmen
        # (concurrent.futures wirft RuntimeError bei submit nach shutdown)
        with pytest.raises(RuntimeError):
            fixer.executor.submit(lambda: None)

    def test_mehrfaches_shutdown(self, fixer):
        """Mehrfaches shutdown() verursacht keinen Fehler."""
        fixer.shutdown()
        # Zweites shutdown soll nicht abstuerzen
        fixer.shutdown()


# =========================================================================
# TestShouldUseParallelFix
# =========================================================================

class TestShouldUseParallelFix:
    """Tests fuer should_use_parallel_fix (Zeile 579-609)."""

    def test_einzelne_datei_immer_true(self):
        """Einzelne Datei: Immer True (Zeile 609)."""
        errors = [_make_error("app.py")]
        assert should_use_parallel_fix(errors) is True

    def test_mehrere_unabhaengige_dateien(self):
        """Mehrere unabhaengige Dateien: True."""
        errors = [
            _make_error("a.py"),
            _make_error("b.py"),
            _make_error("c.py"),
        ]
        assert should_use_parallel_fix(errors) is True

    def test_zu_viele_dateien_default_threshold(self):
        """Mehr als 7 einzigartige Dateien: False (default max_threshold=7)."""
        errors = [_make_error(f"file_{i}.py") for i in range(8)]
        assert should_use_parallel_fix(errors) is False

    def test_genau_threshold_dateien(self):
        """Genau 7 einzigartige Dateien: True (1 <= 7 <= 7)."""
        errors = [_make_error(f"file_{i}.py") for i in range(7)]
        assert should_use_parallel_fix(errors) is True

    def test_benutzerdefinierter_threshold(self):
        """Benutzerdefinierter max_threshold wird beachtet."""
        errors = [_make_error(f"file_{i}.py") for i in range(4)]
        # max_threshold=3 → 4 Dateien > 3 → False
        assert should_use_parallel_fix(errors, max_threshold=3) is False
        # max_threshold=5 → 4 Dateien <= 5 → True
        assert should_use_parallel_fix(errors, max_threshold=5) is True

    def test_keine_zirkulaere_abhaengigkeiten(self):
        """Abhaengigkeiten auf nicht-fehlerhafte Dateien: OK (True)."""
        errors = [
            _make_error("a.py", dependencies=["external.py"]),
            _make_error("b.py", dependencies=["other.py"]),
        ]
        # external.py und other.py sind NICHT in der Fehlerliste
        assert should_use_parallel_fix(errors) is True

    def test_eine_zirkulaere_abhaengigkeit_ok(self):
        """Maximal 1 zirkulaere Abhaengigkeit: True (Zeile 606: <= 1)."""
        errors = [
            _make_error("a.py", dependencies=["b.py"]),
            _make_error("b.py"),
        ]
        # b.py ist in der Fehlerliste UND Abhaengigkeit von a.py → 1 circular
        assert should_use_parallel_fix(errors) is True

    def test_mehrere_zirkulaere_abhaengigkeiten_false(self):
        """Mehr als 1 zirkulaere Abhaengigkeit: False."""
        errors = [
            _make_error("a.py", dependencies=["b.py", "c.py"]),
            _make_error("b.py", dependencies=["a.py"]),
            _make_error("c.py"),
        ]
        # b.py und c.py sind in Fehlerliste UND deps von a.py → 2 circular
        assert should_use_parallel_fix(errors) is False

    def test_leere_fehlerliste(self):
        """Leere Liste: unique_files=0 → 0 < 1 → Bedingung False → False."""
        assert should_use_parallel_fix([]) is False

    def test_duplikat_dateipfade(self):
        """Mehrere Fehler in derselben Datei zaehlen als 1 unique file."""
        errors = [
            _make_error("app.py", error_type="syntax"),
            _make_error("app.py", error_type="runtime"),
            _make_error("app.py", error_type="import"),
        ]
        # 3 Fehler aber nur 1 unique file → True (Einzeldatei)
        assert should_use_parallel_fix(errors) is True

    def test_zu_viele_mit_zirkulaer_aber_einzeldatei(self):
        """8+ Dateien aber alle gleich → unique_files=1 → True (Zeile 609)."""
        errors = [_make_error("same.py") for _ in range(10)]
        assert should_use_parallel_fix(errors) is True

    def test_viele_dateien_ueber_threshold_nicht_single_file(self):
        """Viele unterschiedliche Dateien ueber Threshold: False."""
        errors = [_make_error(f"f{i}.py") for i in range(20)]
        # 20 unique > 7 und 20 != 1 → False
        assert should_use_parallel_fix(errors) is False

    def test_zwei_dateien_mit_gegenseitiger_abhaengigkeit(self):
        """Zwei Dateien die sich gegenseitig abhaengen: 2 circular → False."""
        errors = [
            _make_error("a.py", dependencies=["b.py"]),
            _make_error("b.py", dependencies=["a.py"]),
        ]
        # circular = {a.py, b.py} → len = 2 > 1 → False
        assert should_use_parallel_fix(errors) is False

    def test_threshold_1_nur_einzeldateien(self):
        """max_threshold=1: Nur einzelne Dateien erlaubt."""
        single = [_make_error("a.py")]
        double = [_make_error("a.py"), _make_error("b.py")]
        assert should_use_parallel_fix(single, max_threshold=1) is True
        # 2 Dateien > threshold 1 aber unique==2 != 1 → False
        assert should_use_parallel_fix(double, max_threshold=1) is False
