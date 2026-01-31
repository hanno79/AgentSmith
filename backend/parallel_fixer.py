"""
Author: rahn
Datum: 31.01.2026
Version: 1.0
Beschreibung: Koordiniert parallele Datei-Korrekturen mit mehreren Agenten.
              Ermoeglicht schnelle, gezielte Fehler-Behebungen.
"""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime

from crewai import Task, Crew

from backend.error_analyzer import FileError, ErrorAnalyzer
from agents.fix_agent import (
    create_fix_agent,
    build_fix_prompt,
    extract_corrected_content,
    create_fix_task
)

logger = logging.getLogger(__name__)


@dataclass
class FixResult:
    """Ergebnis einer Datei-Korrektur."""
    file_path: str
    success: bool
    new_content: Optional[str] = None
    error_message: str = ""
    duration_seconds: float = 0.0
    attempts: int = 1
    original_error: Optional[FileError] = None


@dataclass
class ParallelFixStats:
    """Statistiken ueber parallele Fix-Operationen."""
    total_files: int = 0
    successful_fixes: int = 0
    failed_fixes: int = 0
    total_duration_seconds: float = 0.0
    parallel_batches: int = 0
    files_fixed: List[str] = field(default_factory=list)
    files_failed: List[str] = field(default_factory=list)


class ParallelFixer:
    """
    Koordiniert parallele Datei-Korrekturen mit mehreren Agenten.

    Features:
    - Parallele Verarbeitung unabhaengiger Dateien
    - Abhaengigkeits-bewusste Sequenzierung
    - Retry-Logik bei Fehlschlaegen
    - Fortschritts-Tracking
    """

    def __init__(
        self,
        manager,
        config: Dict[str, Any],
        max_parallel: int = 3,
        max_retries: int = 2,
        router=None
    ):
        """
        Initialisiert den ParallelFixer.

        Args:
            manager: SessionManager fuer Status-Updates
            config: Konfiguration mit Modell-Einstellungen
            max_parallel: Maximale Anzahl paralleler Fix-Agenten
            max_retries: Maximale Wiederholungsversuche pro Datei
            router: Optional - Model Router
        """
        self.manager = manager
        self.config = config
        self.max_parallel = max_parallel
        self.max_retries = max_retries
        self.router = router
        self.executor = ThreadPoolExecutor(max_workers=max_parallel)
        self.stats = ParallelFixStats()
        self._progress_callback: Optional[Callable] = None

    def set_progress_callback(self, callback: Callable[[str, str, float], None]):
        """
        Setzt eine Callback-Funktion fuer Fortschritts-Updates.

        Args:
            callback: Funktion(file_path, status, progress_percent)
        """
        self._progress_callback = callback

    def fix_files_parallel(
        self,
        errors: List[FileError],
        existing_files: Dict[str, str],
        project_rules: str = "",
        user_goal: str = ""
    ) -> Dict[str, FixResult]:
        """
        Korrigiert mehrere Dateien parallel.

        Ablauf:
        1. Gruppiere Fehler nach Abhaengigkeiten
        2. Starte parallele Fix-Tasks fuer unabhaengige Dateien
        3. Warte auf Ergebnisse
        4. Merge erfolgreich gefixte Dateien
        5. Wiederhole fuer abhaengige Dateien

        Args:
            errors: Liste von FileError-Objekten
            existing_files: Dict mit Dateipfad -> aktuellem Inhalt
            project_rules: Projektspezifische Regeln
            user_goal: Das urspruengliche Benutzer-Ziel

        Returns:
            Dict mit Dateipfad -> FixResult
        """
        self.stats = ParallelFixStats()
        results: Dict[str, FixResult] = {}

        if not errors:
            logger.info("Keine Fehler zum Korrigieren")
            return results

        # Analysiere und priorisiere Fehler
        analyzer = ErrorAnalyzer()
        prioritized = analyzer.prioritize_fixes(errors)

        # Gruppiere nach Abhaengigkeiten
        independent, dependent = self._split_by_dependencies(prioritized)

        logger.info(f"Parallele Korrektur: {len(independent)} unabhaengig, {len(dependent)} abhaengig")
        self.stats.total_files = len(errors)

        # Phase 1: Unabhaengige Dateien parallel korrigieren
        if independent:
            self._update_progress("batch_start", "Starte unabhaengige Korrekturen", 0)
            batch_results = self._fix_batch_parallel(
                independent,
                existing_files,
                project_rules,
                user_goal
            )
            results.update(batch_results)
            self.stats.parallel_batches += 1

            # Aktualisiere existing_files mit erfolgreichen Fixes
            for path, result in batch_results.items():
                if result.success and result.new_content:
                    existing_files[path] = result.new_content

        # Phase 2: Abhaengige Dateien sequenziell/parallel korrigieren
        if dependent:
            self._update_progress("batch_start", "Starte abhaengige Korrekturen", 50)
            # Abhaengige Dateien in kleineren Batches
            batch_results = self._fix_batch_parallel(
                dependent,
                existing_files,
                project_rules,
                user_goal
            )
            results.update(batch_results)
            self.stats.parallel_batches += 1

        # Statistiken aktualisieren
        for path, result in results.items():
            if result.success:
                self.stats.successful_fixes += 1
                self.stats.files_fixed.append(path)
            else:
                self.stats.failed_fixes += 1
                self.stats.files_failed.append(path)

        self._update_progress("complete", "Parallele Korrektur abgeschlossen", 100)
        logger.info(f"Korrektur abgeschlossen: {self.stats.successful_fixes}/{self.stats.total_files} erfolgreich")

        return results

    async def fix_files_parallel_async(
        self,
        errors: List[FileError],
        existing_files: Dict[str, str],
        project_rules: str = "",
        user_goal: str = ""
    ) -> Dict[str, FixResult]:
        """Asynchrone Version von fix_files_parallel."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self.fix_files_parallel,
            errors,
            existing_files,
            project_rules,
            user_goal
        )

    def fix_single_file(
        self,
        error: FileError,
        current_content: str,
        context_files: Dict[str, str] = None,
        project_rules: str = "",
        user_goal: str = ""
    ) -> FixResult:
        """
        Korrigiert eine einzelne Datei.

        Args:
            error: FileError mit Fehlerdetails
            current_content: Aktueller Dateiinhalt
            context_files: Relevante andere Dateien als Kontext
            project_rules: Projektregeln
            user_goal: Benutzer-Ziel

        Returns:
            FixResult mit Ergebnis
        """
        start_time = datetime.now()

        try:
            # Fix-Agent erstellen
            agent = create_fix_agent(
                config=self.config,
                project_rules=project_rules,
                router=self.router,
                target_file=error.file_path,
                error_info={
                    "file_path": error.file_path,
                    "error_type": error.error_type,
                    "line_numbers": error.line_numbers,
                    "error_message": error.error_message,
                    "suggested_fix": error.suggested_fix
                }
            )

            # Task erstellen
            task = create_fix_task(
                agent=agent,
                file_path=error.file_path,
                current_content=current_content,
                error_type=error.error_type,
                error_message=error.error_message,
                line_numbers=error.line_numbers,
                context_files=context_files
            )

            # Crew ausfuehren
            crew = Crew(
                agents=[agent],
                tasks=[task],
                verbose=False
            )

            result = crew.kickoff()

            # Ergebnis extrahieren
            output = str(result)
            corrected_content = extract_corrected_content(output, error.file_path)

            duration = (datetime.now() - start_time).total_seconds()

            if corrected_content:
                logger.info(f"Korrektur erfolgreich: {error.file_path}")
                return FixResult(
                    file_path=error.file_path,
                    success=True,
                    new_content=corrected_content,
                    duration_seconds=duration,
                    original_error=error
                )
            else:
                logger.warning(f"Keine korrigierte Version extrahiert: {error.file_path}")
                return FixResult(
                    file_path=error.file_path,
                    success=False,
                    error_message="Korrigierter Code konnte nicht extrahiert werden",
                    duration_seconds=duration,
                    original_error=error
                )

        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            logger.error(f"Fehler bei Korrektur von {error.file_path}: {e}")
            return FixResult(
                file_path=error.file_path,
                success=False,
                error_message=str(e),
                duration_seconds=duration,
                original_error=error
            )

    def _fix_batch_parallel(
        self,
        errors: List[FileError],
        existing_files: Dict[str, str],
        project_rules: str,
        user_goal: str
    ) -> Dict[str, FixResult]:
        """
        Korrigiert einen Batch von Dateien parallel.

        Args:
            errors: Liste von FileError-Objekten
            existing_files: Aktuelle Dateiinhalte
            project_rules: Projektregeln
            user_goal: Benutzer-Ziel

        Returns:
            Dict mit Dateipfad -> FixResult
        """
        results: Dict[str, FixResult] = {}

        if not errors:
            return results

        # Begrenze auf max_parallel
        batch_errors = errors[:self.max_parallel]
        remaining_errors = errors[self.max_parallel:]

        # Parallele Ausfuehrung
        futures = {}
        for error in batch_errors:
            if error.file_path not in existing_files:
                logger.warning(f"Datei nicht gefunden: {error.file_path}")
                results[error.file_path] = FixResult(
                    file_path=error.file_path,
                    success=False,
                    error_message="Datei nicht in existing_files gefunden"
                )
                continue

            current_content = existing_files[error.file_path]

            # Kontext-Dateien sammeln (Imports, Abhaengigkeiten)
            context_files = self._get_context_files(error, existing_files)

            # Task an ThreadPool uebergeben
            future = self.executor.submit(
                self._fix_with_retry,
                error,
                current_content,
                context_files,
                project_rules,
                user_goal
            )
            futures[future] = error.file_path

        # Ergebnisse sammeln
        for future in as_completed(futures):
            file_path = futures[future]
            try:
                result = future.result(timeout=300)  # 5 Minuten Timeout
                results[file_path] = result
                self._update_progress(
                    file_path,
                    "erfolgreich" if result.success else "fehlgeschlagen",
                    (len(results) / len(batch_errors)) * 100
                )
            except Exception as e:
                logger.error(f"Timeout/Fehler bei {file_path}: {e}")
                results[file_path] = FixResult(
                    file_path=file_path,
                    success=False,
                    error_message=f"Timeout oder Fehler: {e}"
                )

        # Rekursiv verbleibende Fehler verarbeiten
        if remaining_errors:
            # Aktualisiere existing_files mit bisherigen Erfolgen
            for path, result in results.items():
                if result.success and result.new_content:
                    existing_files[path] = result.new_content

            remaining_results = self._fix_batch_parallel(
                remaining_errors,
                existing_files,
                project_rules,
                user_goal
            )
            results.update(remaining_results)

        return results

    def _fix_with_retry(
        self,
        error: FileError,
        current_content: str,
        context_files: Dict[str, str],
        project_rules: str,
        user_goal: str
    ) -> FixResult:
        """
        Korrigiert eine Datei mit Retry-Logik.

        Args:
            error: FileError
            current_content: Aktueller Inhalt
            context_files: Kontext-Dateien
            project_rules: Projektregeln
            user_goal: Benutzer-Ziel

        Returns:
            FixResult
        """
        last_result = None

        for attempt in range(1, self.max_retries + 1):
            logger.info(f"Korrektur-Versuch {attempt}/{self.max_retries} fuer {error.file_path}")

            result = self.fix_single_file(
                error=error,
                current_content=current_content,
                context_files=context_files,
                project_rules=project_rules,
                user_goal=user_goal
            )
            result.attempts = attempt

            if result.success:
                return result

            last_result = result

            # Bei Retry: Erweitere den Fehlerkontext
            if attempt < self.max_retries:
                error.error_message += f"\n[Vorheriger Versuch fehlgeschlagen: {result.error_message}]"

        return last_result or FixResult(
            file_path=error.file_path,
            success=False,
            error_message="Alle Versuche fehlgeschlagen"
        )

    def _split_by_dependencies(
        self,
        errors: List[FileError]
    ) -> tuple[List[FileError], List[FileError]]:
        """
        Teilt Fehler in unabhaengige und abhaengige auf.

        Args:
            errors: Liste von FileError-Objekten

        Returns:
            Tuple (unabhaengige, abhaengige)
        """
        independent = []
        dependent = []

        for error in errors:
            if error.dependencies:
                dependent.append(error)
            else:
                independent.append(error)

        return independent, dependent

    def _get_context_files(
        self,
        error: FileError,
        existing_files: Dict[str, str]
    ) -> Dict[str, str]:
        """
        Sammelt relevante Kontext-Dateien fuer eine Korrektur.

        Args:
            error: FileError fuer den Kontext benoetigt wird
            existing_files: Alle Projekt-Dateien

        Returns:
            Dict mit relevanten Dateien (max 3)
        """
        context = {}

        # 1. Dateien aus Abhaengigkeiten
        for dep_path in error.dependencies[:2]:
            if dep_path in existing_files:
                context[dep_path] = existing_files[dep_path]

        # 2. Dateien die in der Fehlermeldung erwaehnt werden
        for path in existing_files.keys():
            if len(context) >= 3:
                break
            if path in error.error_message and path not in context:
                context[path] = existing_files[path]

        return context

    def _update_progress(self, file_path: str, status: str, progress: float):
        """Sendet Fortschritts-Update wenn Callback gesetzt."""
        if self._progress_callback:
            try:
                self._progress_callback(file_path, status, progress)
            except Exception as e:
                logger.warning(f"Progress-Callback Fehler: {e}")

        # Auch an SessionManager senden wenn verfuegbar
        if self.manager:
            try:
                self.manager.update_agent_status(
                    "parallel_fixer",
                    {
                        "status": "running",
                        "current_file": file_path,
                        "progress": progress,
                        "message": status
                    }
                )
            except Exception:
                pass  # SessionManager optional

    def get_stats(self) -> ParallelFixStats:
        """Gibt die aktuellen Statistiken zurueck."""
        return self.stats

    def shutdown(self):
        """Faehrt den ThreadPool herunter."""
        self.executor.shutdown(wait=True)


# =============================================================================
# Hilfsfunktionen fuer externe Nutzung
# =============================================================================

def quick_fix(
    file_path: str,
    content: str,
    error_message: str,
    error_type: str = "runtime",
    config: Dict = None
) -> Optional[str]:
    """
    Schnelle Einzeldatei-Korrektur ohne vollstaendigen ParallelFixer.

    Args:
        file_path: Dateipfad
        content: Aktueller Inhalt
        error_message: Fehlermeldung
        error_type: Fehlertyp
        config: Konfiguration

    Returns:
        Korrigierter Inhalt oder None
    """
    if config is None:
        config = {"default_model": "gpt-4o-mini"}

    error = FileError(
        file_path=file_path,
        error_type=error_type,
        error_message=error_message
    )

    fixer = ParallelFixer(
        manager=None,
        config=config,
        max_parallel=1,
        max_retries=1
    )

    result = fixer.fix_single_file(
        error=error,
        current_content=content
    )

    fixer.shutdown()

    return result.new_content if result.success else None


def should_use_parallel_fix(errors: List[FileError], max_threshold: int = 3) -> bool:
    """
    Entscheidet ob parallele Korrektur sinnvoll ist.

    Args:
        errors: Liste von Fehlern
        max_threshold: Maximale Anzahl Dateien fuer parallelen Fix

    Returns:
        True wenn paralleler Fix empfohlen
    """
    unique_files = len(set(e.file_path for e in errors))

    # Parallel fix wenn:
    # - Mehrere aber nicht zu viele Dateien betroffen
    # - Keine zu komplexen Abhaengigkeiten
    if 1 <= unique_files <= max_threshold:
        # Pruefe auf zirkulaere Abhaengigkeiten
        all_deps = set()
        all_files = set(e.file_path for e in errors)
        for e in errors:
            all_deps.update(e.dependencies)

        # Wenn Abhaengigkeiten nur auf nicht-fehlerhafte Dateien zeigen: OK
        circular = all_deps.intersection(all_files)
        if len(circular) <= 1:
            return True

    return unique_files == 1  # Einzelne Datei immer fixbar
