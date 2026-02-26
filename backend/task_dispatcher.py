"""
Author: rahn
Datum: 02.02.2026
Version: 1.1
Beschreibung: Task-Dispatcher fuer das Universal Task Derivation System (UTDS).
              Verteilt Tasks an passende Agenten und orchestriert parallele Ausfuehrung.

              AENDERUNG 02.02.2026 v1.1: Verbessertes Debug-Logging fuer Fehleranalyse
              - Detailliertes Logging in _execute_single_task
              - Agent-Factory Diagnostik in _get_agent_for_task
"""

import os
import asyncio
import logging
import re
import time
import threading
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable
from datetime import datetime

from crewai import Task, Crew

from backend.task_models import (
    DerivedTask, TaskBatch, BatchResult, TaskStatus, TargetAgent,
    TaskPriority, filter_ready_tasks, sort_tasks_by_priority, priority_to_int
)
from backend.task_tracker import TaskTracker

logger = logging.getLogger(__name__)


@dataclass
class TaskExecutionResult:
    """Ergebnis einer Task-Ausfuehrung."""
    task_id: str
    success: bool
    result: Optional[str] = None
    error_message: str = ""
    modified_files: List[str] = field(default_factory=list)
    duration_seconds: float = 0.0
    agent_used: str = ""


class TaskDispatcher:
    """
    Verteilt Tasks an passende Agenten und orchestriert Parallelisierung.

    Features:
    - Multi-Agent Support (Coder, Tester, Security, Docs)
    - Abhaengigkeits-bewusste Batch-Bildung
    - CPU-basierte dynamische Parallelisierung
    - Task-Tracker Integration
    """

    def __init__(
        self,
        manager,
        config: Dict[str, Any],
        tracker: TaskTracker = None,
        router=None,
        max_parallel: int = None
    ):
        """
        Initialisiert den TaskDispatcher.

        Args:
            manager: SessionManager fuer Agenten-Erstellung
            config: Anwendungskonfiguration
            tracker: TaskTracker fuer Traceability
            router: Model Router fuer Agenten
            max_parallel: Max parallele Agenten (None = CPU-basiert)
        """
        self.manager = manager
        self.config = config
        self.tracker = tracker or TaskTracker()
        self.router = router

        # CPU-basierte Parallelisierung
        if max_parallel is None:
            self.max_parallel = os.cpu_count() or 4
        else:
            self.max_parallel = max_parallel

        self.executor = ThreadPoolExecutor(max_workers=self.max_parallel)
        self._progress_callback: Optional[Callable] = None

        # Agent Factory Cache
        self._agent_cache: Dict[str, Any] = {}

    def set_progress_callback(self, callback: Callable[[str, str, float], None]):
        """
        Setzt Callback fuer Fortschritts-Updates.

        Args:
            callback: Funktion(task_id, status, progress_percent)
        """
        self._progress_callback = callback

    def dispatch(self, tasks: List[DerivedTask]) -> List[TaskBatch]:
        """
        Erstellt Batches fuer parallele Verarbeitung.

        Gruppiert unabhaengige Tasks in Batches,
        beachtet Abhaengigkeiten zwischen Tasks.

        Args:
            tasks: Liste von DerivedTask-Objekten

        Returns:
            Liste von TaskBatch-Objekten in Ausfuehrungsreihenfolge
        """
        if not tasks:
            return []

        # Tasks nach Prioritaet sortieren
        sorted_tasks = sort_tasks_by_priority(tasks)

        # Abhaengigkeits-Graph aufbauen
        dependency_graph = self._build_dependency_graph(sorted_tasks)

        # Batches erstellen
        batches = []
        completed_ids: List[str] = []
        remaining = list(sorted_tasks)
        batch_counter = 0

        while remaining:
            # Finde alle Tasks ohne unerfuellte Abhaengigkeiten
            ready = [t for t in remaining if t.is_ready(completed_ids)]

            if not ready:
                # Deadlock - Zirkulaere Abhaengigkeit oder Fehler
                logger.warning(f"[TaskDispatcher] Deadlock erkannt. Verbleibend: {len(remaining)}")
                # Forciere ersten verbleibenden Task
                ready = [remaining[0]]

            # Batch erstellen
            batch_counter += 1
            batch = TaskBatch(
                batch_id=f"BATCH-{batch_counter:03d}",
                tasks=ready,
                priority_order=batch_counter
            )
            batches.append(batch)

            # Tasks als "scheduled" markieren
            for task in ready:
                remaining.remove(task)
                completed_ids.append(task.id)

        logger.info(f"[TaskDispatcher] {len(batches)} Batches erstellt fuer {len(tasks)} Tasks")
        return batches

    def execute_batch(self, batch: TaskBatch) -> BatchResult:
        """
        Fuehrt einen Batch parallel aus.

        Args:
            batch: TaskBatch zum Ausfuehren

        Returns:
            BatchResult mit Ergebnissen
        """
        start_time = time.time()
        batch.status = TaskStatus.IN_PROGRESS
        batch.started_at = datetime.now()

        # AENDERUNG 26.02.2026: Root-Cause-Fix - echte Retry-Runden je Batch.
        # Vorher wurden Retry-Status gesetzt, aber nie erneut ausgefuehrt.
        final_results: Dict[str, TaskExecutionResult] = {}
        pending_tasks = list(batch.tasks)
        round_counter = 0

        while pending_tasks:
            round_counter += 1
            futures = {}
            future_start_times = {}
            future_timeouts = {}
            future_cancel_events = {}
            retry_tasks: List[DerivedTask] = []

            # Tasks parallel starten
            for task in pending_tasks:
                self.tracker.update_status(task.id, TaskStatus.IN_PROGRESS)
                cancel_event = threading.Event()
                future = self.executor.submit(self._execute_single_task, task, cancel_event)
                futures[future] = task
                future_start_times[future] = time.time()
                future_timeouts[future] = self._get_task_timeout_seconds(task)
                future_cancel_events[future] = cancel_event

            # Auf Ergebnisse warten + harte Timeout-Absicherung
            while futures:
                done, not_done = wait(
                    list(futures.keys()),
                    timeout=0.5,
                    return_when=FIRST_COMPLETED
                )

                if not done:
                    now = time.time()
                    timed_out = []
                    for future in not_done:
                        task = futures[future]
                        started = future_start_times.get(future, now)
                        timeout_seconds = future_timeouts.get(future, 120)
                        if (now - started) >= timeout_seconds:
                            timed_out.append(future)

                    for future in timed_out:
                        task = futures.pop(future)
                        future_start_times.pop(future, None)
                        timeout_seconds = future_timeouts.pop(future, 120)
                        cancel_event = future_cancel_events.pop(future, None)
                        if cancel_event is not None:
                            cancel_event.set()
                        cancelled = future.cancel()
                        if not cancelled:
                            logger.warning(
                                "[TaskDispatcher] Task %s Timeout nach %ss (Future konnte nicht direkt gecancelt werden)",
                                task.id,
                                timeout_seconds,
                            )
                        self._abort_running_task(task, f"timeout_{timeout_seconds}s")

                        timeout_msg = f"Task Timeout nach {timeout_seconds}s"
                        timeout_result = TaskExecutionResult(
                            task_id=task.id,
                            success=False,
                            error_message=timeout_msg,
                        )
                        can_retry = self._handle_task_failure(task, timeout_msg)
                        if can_retry:
                            retry_tasks.append(task)
                        else:
                            final_results[task.id] = timeout_result
                    continue

                for future in done:
                    task = futures.pop(future)
                    future_start_times.pop(future, None)
                    future_timeouts.pop(future, None)
                    future_cancel_events.pop(future, None)
                    try:
                        result = future.result()
                    except Exception as e:
                        logger.error(f"[TaskDispatcher] Task {task.id} Exception: {e}")
                        result = TaskExecutionResult(
                            task_id=task.id,
                            success=False,
                            error_message=str(e),
                        )

                    if result.success:
                        final_results[task.id] = result
                        self.tracker.update_status(
                            task.id,
                            TaskStatus.COMPLETED,
                            result=result.result,
                            modified_files=result.modified_files
                        )
                    else:
                        can_retry = self._handle_task_failure(task, result.error_message)
                        if can_retry:
                            retry_tasks.append(task)
                        else:
                            final_results[task.id] = result

            pending_tasks = retry_tasks
            if pending_tasks:
                logger.info(
                    "[TaskDispatcher] Retry-Runde %d abgeschlossen, %d Task(s) werden erneut ausgefuehrt",
                    round_counter,
                    len(pending_tasks),
                )

        results = list(final_results.values())

        # Batch-Ergebnis zusammenstellen
        batch.status = TaskStatus.COMPLETED
        batch.completed_at = datetime.now()

        completed = [r.task_id for r in results if r.success]
        failed = [r.task_id for r in results if not r.success]

        return BatchResult(
            batch_id=batch.batch_id,
            success=len(failed) == 0,
            completed_tasks=completed,
            failed_tasks=failed,
            execution_time_seconds=time.time() - start_time,
            modified_files=self._collect_modified_files(results),
            errors=[r.error_message for r in results if r.error_message]
        )

    def _get_task_timeout_seconds(self, task: DerivedTask) -> int:
        """Liefert einen gueltigen Timeout-Wert fuer eine Task-Ausfuehrung."""
        try:
            timeout_seconds = int(getattr(task, "timeout_seconds", 120) or 120)
        except (TypeError, ValueError):
            timeout_seconds = 120
        return timeout_seconds if timeout_seconds > 0 else 120

    def _abort_running_task(self, task: DerivedTask, reason: str) -> None:
        """
        Bricht bekannte laufende Subprozesse fuer einen Task aktiv ab.

        Root-Cause-Fix:
        - Future.cancel() stoppt bereits laufende Worker-Threads nicht.
        - Daher killen wir den aktiven Claude-CLI-Prozess explizit, damit
          keine Zombie-Aufrufe nach Timeout weiterlaufen.
        """
        claude_provider = getattr(self.manager, "claude_provider", None)
        if not claude_provider:
            return
        killer = getattr(claude_provider, "kill_active_process", None)
        if callable(killer):
            try:
                killer()
                logger.warning(
                    "[TaskDispatcher] Aktiver Claude-Prozess fuer Task %s abgebrochen (%s)",
                    task.id,
                    reason,
                )
            except Exception as kill_err:
                logger.warning(
                    "[TaskDispatcher] Prozess-Abbruch fuer Task %s fehlgeschlagen: %s",
                    task.id,
                    kill_err,
                )

    def _handle_task_failure(self, task: DerivedTask, error_message: str) -> bool:
        """
        Verarbeitet einen Task-Fehler inkl. Retry-Entscheidung.

        Nutzt primär die Task-Metadaten (retry_count/max_retries), damit das Verhalten
        auch bei gemocktem Tracker deterministisch bleibt.
        """
        prev_retry = int(getattr(task, "retry_count", 0) or 0)
        try:
            max_retries = int(getattr(task, "max_retries", 2) or 2)
        except (TypeError, ValueError):
            max_retries = 2

        expected_retry = prev_retry + 1
        expected_can_retry = expected_retry < max_retries

        tracker_can_retry = None
        try:
            tracker_can_retry = self.tracker.increment_retry(task.id)
        except Exception as retry_err:
            logger.warning("[TaskDispatcher] Retry-Inkrement fehlgeschlagen fuer %s: %s", task.id, retry_err)

        # Task-Objekt lokal konsistent halten (wichtig fuer Runtime-Entscheidung im selben Batch).
        if getattr(task, "retry_count", 0) < expected_retry:
            task.retry_count = expected_retry

        can_retry = tracker_can_retry if isinstance(tracker_can_retry, bool) else expected_can_retry

        if can_retry:
            self.tracker.update_status(
                task.id,
                TaskStatus.PENDING,
                error_message=f"Retry geplant. Fehler: {error_message}"
            )
            logger.info(f"[TaskDispatcher] Task {task.id} wird wiederholt (Retry verfuegbar)")
            return True

        self.tracker.update_status(
            task.id,
            TaskStatus.FAILED,
            error_message=f"Max Retries erreicht. Letzter Fehler: {error_message}"
        )
        logger.warning(f"[TaskDispatcher] Task {task.id} FAILED nach max retries")
        return False

    async def execute_batch_async(self, batch: TaskBatch) -> BatchResult:
        """
        Asynchrone Batch-Ausfuehrung.

        Args:
            batch: TaskBatch zum Ausfuehren

        Returns:
            BatchResult mit Ergebnissen
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.execute_batch, batch)

    def execute_all(self, tasks: List[DerivedTask]) -> List[BatchResult]:
        """
        Fuehrt alle Tasks aus (Batching + Execution).

        Args:
            tasks: Liste von Tasks

        Returns:
            Liste von BatchResults
        """
        # Tasks im Tracker registrieren
        for task in tasks:
            self.tracker.log_task(task)

        # Batches erstellen
        batches = self.dispatch(tasks)

        # Batches sequenziell ausfuehren (intern parallel)
        results = []
        completed_ids = []

        for i, batch in enumerate(batches):
            self._report_progress(f"Batch {i+1}/{len(batches)}", "starting", i / len(batches))

            result = self.execute_batch(batch)
            results.append(result)

            # Erfolgreiche Tasks zu completed hinzufuegen
            completed_ids.extend(result.completed_tasks)

            # Bei kritischen Fehlern abbrechen
            if result.failed_tasks and self._has_critical_failure(batch, result):
                logger.warning("[TaskDispatcher] Kritischer Fehler - Abbruch")
                break

            self._report_progress(f"Batch {i+1}/{len(batches)}", "completed", (i+1) / len(batches))

        return results

    async def execute_all_async(self, tasks: List[DerivedTask]) -> List[BatchResult]:
        """Asynchrone Version von execute_all."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.execute_all, tasks)

    def _execute_single_task(
        self,
        task: DerivedTask,
        cancel_event: Optional[threading.Event] = None
    ) -> TaskExecutionResult:
        """
        Fuehrt einen einzelnen Task aus.

        Args:
            task: DerivedTask zum Ausfuehren

        Returns:
            TaskExecutionResult
        """
        start_time = time.time()
        task_timeout_seconds = self._get_task_timeout_seconds(task)

        # AENDERUNG 02.02.2026: Verbessertes Debug-Logging fuer Fehleranalyse
        logger.info(f"[UTDS] Starte Task {task.id}: {task.title[:50]} | Agent: {task.target_agent.value}")

        try:
            if cancel_event is not None and cancel_event.is_set():
                return TaskExecutionResult(
                    task_id=task.id,
                    success=False,
                    error_message="Task vor Start abgebrochen",
                    duration_seconds=time.time() - start_time,
                )

            # Agent fuer Task-Typ holen
            agent = self._get_agent_for_task(task)

            if agent is None:
                logger.error(f"[UTDS] Task {task.id} FAILED: Kein Agent fuer '{task.target_agent.value}'")
                logger.error(f"[UTDS] Manager hat agent_factory: {hasattr(self.manager, 'agent_factory')}")
                return TaskExecutionResult(
                    task_id=task.id,
                    success=False,
                    error_message=f"Kein Agent fuer {task.target_agent.value} verfuegbar"
                )

            # AENDERUNG 07.02.2026: Fix-Agent Start-Event (Fix 14)
            is_fix = task.target_agent.value == "fix"
            if is_fix:
                self._emit_fix_event("FixStart", {
                    "task_id": task.id,
                    "affected_files": task.affected_files,
                    "error_type": task.category.value,
                    "title": task.title[:100]
                })

            existing_files = self._list_existing_project_files()

            # AENDERUNG 24.02.2026: Fix 76b — Claude SDK CLI-Modus fuer UTDS-Tasks
            # SDK-First: Schneller und direkter als CrewAI, Fallback auf CrewAI bei Fehler
            task_description = self._build_task_description(task)
            fix_target_file = None
            if is_fix:
                fix_prompt, fix_target_file = self._build_fix_task_prompt(task, existing_files)
                if not fix_prompt or not fix_target_file:
                    error_msg = (
                        "Fix-Task ohne aufloesbare Zieldatei. "
                        "UTDS muss affected_files oder Dateiname im Issue liefern."
                    )
                    self._emit_fix_event("FixOutput", {
                        "task_id": task.id,
                        "success": False,
                        "affected_files": task.affected_files,
                        "modified_files": [],
                        "error": error_msg,
                        "duration": round(time.time() - start_time, 1),
                    })
                    return TaskExecutionResult(
                        task_id=task.id,
                        success=False,
                        error_message=error_msg,
                        duration_seconds=time.time() - start_time,
                        agent_used=task.target_agent.value,
                    )
                task_description = fix_prompt

            sdk_result_text = None
            agent_role = task.target_agent.value
            try:
                from backend.claude_sdk import run_sdk_with_retry
                if hasattr(self.manager, "claude_provider") and self.manager.claude_provider:
                    sdk_result_text = run_sdk_with_retry(
                        self.manager, role=agent_role, prompt=task_description,
                        timeout_seconds=task_timeout_seconds,
                        agent_display_name=f"UTDS-{agent_role.capitalize()}"
                    )
            except Exception as sdk_err:
                logger.debug("[UTDS] SDK-Versuch fuer %s fehlgeschlagen: %s", agent_role, sdk_err)

            if cancel_event is not None and cancel_event.is_set():
                return TaskExecutionResult(
                    task_id=task.id,
                    success=False,
                    error_message="Task nach SDK-Phase abgebrochen",
                    duration_seconds=time.time() - start_time,
                    agent_used=task.target_agent.value
                )

            if sdk_result_text:
                result_text = sdk_result_text
                logger.info("[UTDS] Task %s via Claude SDK erfolgreich (%d Zeichen)", task.id, len(result_text))
            else:
                if cancel_event is not None and cancel_event.is_set():
                    return TaskExecutionResult(
                        task_id=task.id,
                        success=False,
                        error_message="Task vor Crew-Fallback abgebrochen",
                        duration_seconds=time.time() - start_time,
                        agent_used=task.target_agent.value
                    )
                # Fallback: CrewAI Task erstellen
                crew_task = Task(
                    description=task_description,
                    expected_output="Korrigierter Code oder Loesung",
                    agent=agent
                )

                # Crew ausfuehren
                crew = Crew(
                    agents=[agent],
                    tasks=[crew_task],
                    verbose=False
                )

                result = crew.kickoff()
                result_text = str(result) if result else ""

            if is_fix and fix_target_file:
                from agents.fix_agent import extract_corrected_content

                corrected_content = extract_corrected_content(result_text, fix_target_file)
                if not corrected_content:
                    error_msg = (
                        f"Fix-Output enthaelt keine extrahierbare Korrektur fuer {fix_target_file}"
                    )
                    self._emit_fix_event("FixOutput", {
                        "task_id": task.id,
                        "success": False,
                        "affected_files": task.affected_files,
                        "modified_files": [],
                        "error": error_msg,
                        "duration": round(time.time() - start_time, 1),
                    })
                    return TaskExecutionResult(
                        task_id=task.id,
                        success=False,
                        error_message=error_msg,
                        duration_seconds=time.time() - start_time,
                        agent_used=task.target_agent.value,
                    )

                if cancel_event is not None and cancel_event.is_set():
                    return TaskExecutionResult(
                        task_id=task.id,
                        success=False,
                        error_message="Task vor Datei-Synchronisierung abgebrochen",
                        duration_seconds=time.time() - start_time,
                        agent_used=task.target_agent.value,
                    )

                write_ok = self._write_file_to_project(fix_target_file, corrected_content)
                sync_ok = self._sync_single_file_to_manager(fix_target_file, corrected_content)
                if not write_ok or not sync_ok:
                    sync_error = (
                        f"Fix-Task Synchronisierung fehlgeschlagen "
                        f"(write_ok={write_ok}, sync_ok={sync_ok}) fuer {fix_target_file}"
                    )
                    self._emit_fix_event("FixOutput", {
                        "task_id": task.id,
                        "success": False,
                        "affected_files": task.affected_files,
                        "modified_files": [],
                        "error": sync_error,
                        "duration": round(time.time() - start_time, 1),
                    })
                    return TaskExecutionResult(
                        task_id=task.id,
                        success=False,
                        error_message=sync_error,
                        duration_seconds=time.time() - start_time,
                        agent_used=task.target_agent.value,
                    )
                modified_files = [fix_target_file]
            else:
                # Ergebnis analysieren
                modified_files = self._extract_modified_files(result_text, task, existing_files=existing_files)

                # ÄNDERUNG 03.02.2026: UTDS-Fixes zu manager.current_code synchronisieren
                # Verhindert dass Fixes bei nächster Coder-Iteration verloren gehen
                self._sync_modified_files_to_manager(modified_files, result_text)

            # AENDERUNG 07.02.2026: Fix-Agent Output-Event (Fix 14)
            if is_fix:
                model_name = ""
                if hasattr(agent, 'llm') and hasattr(agent.llm, 'model'):
                    model_name = agent.llm.model
                self._emit_fix_event("FixOutput", {
                    "task_id": task.id,
                    "success": bool(modified_files),
                    "affected_files": task.affected_files,
                    "modified_files": modified_files,
                    "model": model_name,
                    "duration": round(time.time() - start_time, 1)
                })

            if is_fix and not modified_files:
                return TaskExecutionResult(
                    task_id=task.id,
                    success=False,
                    error_message="Fix-Task lieferte keine geaenderte Datei",
                    duration_seconds=time.time() - start_time,
                    agent_used=task.target_agent.value,
                )

            return TaskExecutionResult(
                task_id=task.id,
                success=True,
                result=result_text[:2000],  # Truncate
                modified_files=modified_files,
                duration_seconds=time.time() - start_time,
                agent_used=task.target_agent.value
            )

        except Exception as e:
            # AENDERUNG 02.02.2026: Detailliertes Logging fuer besseres Debugging
            logger.error(f"[TaskDispatcher] Task {task.id} Fehler: {e}")
            logger.exception(f"[TaskDispatcher] Task {task.id} Stacktrace fuer Debugging:")
            return TaskExecutionResult(
                task_id=task.id,
                success=False,
                error_message=str(e),
                duration_seconds=time.time() - start_time
            )

    def _get_agent_for_task(self, task: DerivedTask) -> Optional[Any]:
        """
        Holt oder erstellt einen Agenten fuer den Task-Typ.
        AENDERUNG 20.02.2026: Fix 58d — 3 Versuche statt 2 + Cache-Invalidierung
        ROOT-CAUSE-FIX: 20/20 UTDS-Batch-Ausfuehrungen schlugen fehl weil Agent-Erstellung
        bei erschoepften Modell-Credits scheiterte. Korrekte Fixes gingen komplett verloren.

        Args:
            task: DerivedTask

        Returns:
            CrewAI Agent oder None
        """
        agent_type = task.target_agent.value

        # Cache pruefen
        if agent_type in self._agent_cache:
            logger.debug(f"[UTDS] Agent '{agent_type}' aus Cache geholt")
            return self._agent_cache[agent_type]

        # Versuch 1: Agent erstellen ueber agent_factory
        try:
            if hasattr(self.manager, 'agent_factory'):
                logger.debug(f"[UTDS] Versuche Agent '{agent_type}' via agent_factory")
                agent = self.manager.agent_factory.get(agent_type)
                if agent:
                    self._agent_cache[agent_type] = agent
                    logger.info(f"[UTDS] Agent '{agent_type}' erfolgreich erstellt via factory")
                    return agent
                else:
                    logger.warning(f"[UTDS] agent_factory.get('{agent_type}') lieferte None")
        except Exception as e:
            logger.warning(f"[UTDS] Factory-Fehler fuer '{agent_type}': {e}")

        # Versuch 2: Fallback: Direkter Import mit aktuellem Modell
        try:
            logger.debug(f"[UTDS] Versuche Agent '{agent_type}' via Fallback-Import")
            agent = self._create_agent_fallback(agent_type)
            if agent:
                self._agent_cache[agent_type] = agent
                logger.info(f"[UTDS] Agent '{agent_type}' erfolgreich erstellt via Fallback")
                return agent
        except Exception as e:
            logger.warning(f"[UTDS] Fallback-Fehler fuer '{agent_type}': {e}")

        # Versuch 3 (NEU Fix 58d): Coder als Universal-Fallback fuer alle UTDS-Tasks
        # Wenn der spezifische Agent-Typ nicht erstellt werden kann, nutze den Coder-Agent
        # als Ersatz — der Coder kann generisch Code-Fixes erstellen
        if agent_type != "coder":
            try:
                logger.info(f"[UTDS] Verwende Coder als Universal-Fallback fuer '{agent_type}'")
                agent = self._create_agent_fallback("coder")
                if agent:
                    self._agent_cache[agent_type] = agent
                    return agent
            except Exception as e:
                logger.error(f"[UTDS] Auch Coder-Fallback fehlgeschlagen: {e}")

        logger.error(f"[UTDS] Alle 3 Versuche fuer '{agent_type}' fehlgeschlagen")
        return None

    def _create_agent_fallback(self, agent_type: str) -> Optional[Any]:
        """
        Fallback Agent-Erstellung.

        AENDERUNG 06.02.2026: tech_blueprint an alle Agents durchreichen.
        """
        try:
            # AENDERUNG 06.02.2026: Tech-Stack-Kontext fuer alle Agents
            tech_blueprint = getattr(self.manager, 'tech_blueprint', {})
            # Tech-Kontext als project_rules injizieren (da create_coder/tester/reviewer
            # kein tech_blueprint akzeptieren, aber project_rules in Backstory einfliessen)
            rules = {}
            if tech_blueprint:
                language = tech_blueprint.get('language', 'unbekannt')
                framework = tech_blueprint.get('framework', 'keins')
                project_type = tech_blueprint.get('project_type', 'unbekannt')
                rules['tech_stack_context'] = (
                    f"TECH-STACK: Sprache={language}, Framework={framework}, Typ={project_type}. "
                    f"ALLE Code-Aenderungen MUESSEN in '{language}' sein!"
                )

            if agent_type == "coder":
                from agents.coder_agent import create_coder
                return create_coder(self.config, rules, router=self.router)
            elif agent_type == "fix":
                from agents.fix_agent import create_fix_agent
                return create_fix_agent(
                    self.config, rules, router=self.router,
                    tech_blueprint=tech_blueprint
                )
            elif agent_type == "tester":
                from agents.tester_agent import create_tester
                return create_tester(self.config, rules, router=self.router)
            elif agent_type == "security":
                # Security nutzt Coder mit speziellem Prompt
                from agents.coder_agent import create_coder
                return create_coder(self.config, rules, router=self.router)
            elif agent_type == "reviewer":
                from agents.reviewer_agent import create_reviewer
                return create_reviewer(self.config, rules, router=self.router)
            else:
                logger.warning(f"[TaskDispatcher] Unbekannter Agent-Typ: {agent_type}")
                return None
        except ImportError as e:
            logger.error(f"[TaskDispatcher] Import-Fehler: {e}")
            return None

    def _build_task_description(self, task: DerivedTask) -> str:
        """
        Erstellt die Task-Beschreibung fuer CrewAI.

        AENDERUNG 06.02.2026: ROOT-CAUSE-FIX Tech-Stack-Kontext fuer alle Agents
        Symptom: Fix-Agent erzeugt Python-Code (BeispielDatei.py) fuer JavaScript-Projekte
        Ursache: Agents erhalten KEINEN Tech-Stack-Kontext in der Task-Beschreibung
        Loesung: Tech-Stack aus manager.tech_blueprint in jede Task-Beschreibung einfuegen
        """
        # AENDERUNG 06.02.2026: Tech-Stack-Kontext aus Manager extrahieren
        tech_blueprint = getattr(self.manager, 'tech_blueprint', {})
        tech_section = ""
        if tech_blueprint:
            language = tech_blueprint.get('language', 'unbekannt')
            framework = tech_blueprint.get('framework', 'keins')
            project_type = tech_blueprint.get('project_type', 'unbekannt')
            tech_section = f"""
### Tech-Stack (WICHTIG - beachte bei Code-Generierung!):
- Sprache: {language}
- Framework: {framework}
- Projekt-Typ: {project_type}
- ALLE generierten Dateien MUESSEN zur Sprache '{language}' passen!
"""

        desc = f"""## Task: {task.title}

{task.description}
{tech_section}
### Betroffene Dateien:
{chr(10).join(f'- {f}' for f in task.affected_files) if task.affected_files else '- Nicht spezifiziert'}

### Kategorie: {task.category.value}
### Prioritaet: {task.priority.value}

### Original-Issue:
{task.source_issue[:500] if task.source_issue else 'Kein Original-Issue'}

### Anforderungen:
1. Behebe das Problem vollstaendig
2. Generiere nur den betroffenen Code
3. Keine zusaetzlichen Aenderungen
4. Teste gedanklich die Loesung
"""
        return desc

    def _list_existing_project_files(self) -> List[str]:
        """Liest vorhandene Projektdateien fuer Datei-Aufloesung und Validierung."""
        existing_files = []
        project_path = getattr(self.manager, "project_path", None)
        if project_path and os.path.isdir(str(project_path)):
            for root, dirs, files in os.walk(str(project_path)):
                dirs[:] = [
                    d for d in dirs if d not in ("node_modules", ".next", ".git", "__pycache__")
                ]
                for fname in files:
                    rel = os.path.relpath(os.path.join(root, fname), str(project_path)).replace("\\", "/")
                    existing_files.append(rel)
        return existing_files

    def _resolve_fix_target_file(self, task: DerivedTask, existing_files: List[str]) -> Optional[str]:
        """Bestimmt die zu korrigierende Datei fuer einen Fix-Task."""
        candidates = []
        for af in task.affected_files or []:
            if isinstance(af, str) and af.strip():
                candidates.append(af.replace("\\", "/").strip())

        if not candidates:
            issue_text = f"{task.source_issue or ''}\n{task.description or ''}"
            file_pattern = r'([a-zA-Z0-9_/\\.-]+\.(?:py|jsx|json|tsx|js|ts|html|css|yaml|yml|md|java|go|rs|cs|cpp|hpp|kt|kts|rb|swift|php|vue|svelte|dart|scala|xml|gradle|sql|sh|bat|toml))'
            for match in re.findall(file_pattern, issue_text):
                candidates.append(match.replace("\\", "/").strip())

        if not candidates:
            return None

        existing_set = {ef.replace("\\", "/") for ef in existing_files or []}
        for candidate in candidates:
            if candidate in existing_set:
                return candidate
            base = os.path.basename(candidate)
            base_matches = [ef for ef in existing_set if os.path.basename(ef) == base]
            if len(base_matches) == 1:
                return base_matches[0]

            # Fallback: direkte Existenzpruefung, falls existing_files leer ist.
            project_path = getattr(self.manager, "project_path", None)
            if project_path:
                project_root = os.path.abspath(str(project_path))
                candidate_path = os.path.abspath(os.path.join(project_root, candidate))
                try:
                    if (os.path.commonpath([project_root, candidate_path]) == project_root
                            and os.path.isfile(candidate_path)):
                        return candidate
                except ValueError:
                    continue

        # Keine aufloesbare Datei gefunden -> harter Fehler statt unspezifischem Crew-Fallback.
        return None

    def _read_project_file(self, rel_path: str) -> str:
        """Liest eine Projektdatei als UTF-8 Text (best effort)."""
        project_path = getattr(self.manager, "project_path", None)
        if not project_path or not rel_path:
            return ""
        project_root = os.path.abspath(str(project_path))
        full_path = os.path.abspath(os.path.join(project_root, rel_path))
        try:
            if os.path.commonpath([project_root, full_path]) != project_root:
                return ""
        except ValueError:
            return ""
        if not os.path.isfile(full_path):
            return ""
        try:
            with open(full_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception:
            return ""

    def _extract_line_numbers(self, text: str) -> List[int]:
        """Extrahiert Zeilennummern aus Fehlertexten."""
        if not text:
            return []
        numbers = set()
        for m in re.findall(r"(?:line|zeile)\s+(\d+)", text, flags=re.IGNORECASE):
            try:
                numbers.add(int(m))
            except ValueError:
                pass
        return sorted(numbers)[:10]

    def _build_fix_task_prompt(self, task: DerivedTask, existing_files: List[str]) -> tuple[Optional[str], Optional[str]]:
        """Erstellt einen dateibezogenen Prompt fuer Fix-Tasks."""
        from agents.fix_agent import build_fix_prompt

        target_file = self._resolve_fix_target_file(task, existing_files)
        if not target_file:
            return None, None

        current_content = self._read_project_file(target_file)
        error_message = task.source_issue or task.description or task.title
        line_numbers = self._extract_line_numbers(f"{task.source_issue}\n{task.description}")
        prompt = build_fix_prompt(
            file_path=target_file,
            current_content=current_content,
            error_type=task.category.value,
            error_message=error_message,
            line_numbers=line_numbers,
            context_files=None,
            suggested_fix=task.description[:500] if task.description else "",
        )
        return prompt, target_file

    def _write_file_to_project(self, rel_path: str, content: str) -> bool:
        """Schreibt korrigierten Dateiinhalt in das Projektverzeichnis."""
        project_path = getattr(self.manager, "project_path", None)
        if not project_path or not rel_path:
            return False
        project_root = os.path.abspath(str(project_path))
        target_path = os.path.abspath(os.path.join(project_root, rel_path))
        try:
            if os.path.commonpath([project_root, target_path]) != project_root:
                logger.warning("[UTDS] Schreibversuch ausserhalb Projektpfad blockiert: %s", rel_path)
                return False
        except ValueError:
            return False

        try:
            target_dir = os.path.dirname(target_path)
            if target_dir:
                os.makedirs(target_dir, exist_ok=True)
            with open(target_path, "w", encoding="utf-8") as f:
                f.write(content)

            # Harte Validierung: Read-after-write muss den geschriebenen Inhalt liefern.
            with open(target_path, "r", encoding="utf-8") as f:
                persisted = f.read()
            if persisted != content:
                logger.warning(
                    "[UTDS] Read-after-write Mismatch fuer %s (expected=%d, actual=%d)",
                    rel_path,
                    len(content),
                    len(persisted),
                )
                return False
            return True
        except Exception as e:
            logger.error("[UTDS] Fehler beim Schreiben von %s: %s", rel_path, e)
            return False

    def _sync_single_file_to_manager(self, filename: str, content: str) -> bool:
        """Synchronisiert eine einzelne Datei in manager.current_code."""
        if not hasattr(self.manager, "current_code"):
            return False

        if self.manager.current_code is None:
            self.manager.current_code = {}

        if isinstance(self.manager.current_code, dict):
            self.manager.current_code[filename] = content
            return self.manager.current_code.get(filename) == content

        if isinstance(self.manager.current_code, str):
            try:
                from .dev_loop_coder_utils import rebuild_current_code_from_disk

                self.manager.current_code = rebuild_current_code_from_disk(self.manager)
            except Exception:
                return False

            if isinstance(self.manager.current_code, dict):
                return self.manager.current_code.get(filename) == content
            if isinstance(self.manager.current_code, str):
                marker = f"### FILENAME: {filename}"
                return marker in self.manager.current_code
        return False

    def _emit_fix_event(self, event_type: str, data: Dict) -> None:
        """
        AENDERUNG 07.02.2026: Sendet Fix-Agent Event an Frontend via on_log (Fix 14).
        """
        if hasattr(self.manager, 'on_log') and self.manager.on_log:
            import json
            event_data = json.dumps(data, ensure_ascii=False, default=str)
            self.manager.on_log("Fix", event_type, event_data)

    def _build_dependency_graph(self, tasks: List[DerivedTask]) -> Dict[str, List[str]]:
        """Erstellt Abhaengigkeits-Graph."""
        graph = {}
        for task in tasks:
            graph[task.id] = task.dependencies
        return graph

    def _extract_modified_files(self, result: str, task: DerivedTask,
                                existing_files: List[str] = None) -> List[str]:
        """
        Extrahiert geaenderte Dateien aus Ergebnis.

        AENDERUNG 07.02.2026: Fix 20 — Blacklist + Tech-Stack-Filter + Dateivalidierung
        ROOT-CAUSE-FIX:
        Symptom: UTDS/Fix-Agent erstellt UNBEKANNTE_DATEI.js, module.ex, ./globals.css
        Ursache: Regex akzeptiert .ex (Elixir) obwohl Projekt JS ist, keine Validierung
        Loesung: Dreifach-Filter: Blacklist + Tech-Stack + Validierung gegen existierende Dateien

        Args:
            result: Ergebnis-Text mit Code-Bloecken
            task: DerivedTask mit affected_files
            existing_files: Optionale Liste existierender Projektdateien
        """
        # AENDERUNG 07.02.2026: Extensions fuer alle 12 unterstuetzten Sprachen
        # Laengere Extensions zuerst (jsx vor js, json vor js, tsx vor ts)
        file_pattern = r'["\']?([a-zA-Z0-9_/\\.-]+\.(?:py|jsx|json|tsx|js|ts|html|css|yaml|yml|md|java|go|rs|cs|cpp|hpp|kt|kts|rb|swift|php|vue|svelte|dart|scala|ex|xml|gradle|sql|sh|bat|toml))["\']?'
        matches = re.findall(file_pattern, result)

        # AENDERUNG 06.02.2026: ROOT-CAUSE-FIX Framework-Namen in Patch-Liste
        _FRAMEWORK_NAMES = {
            "next.js", "vue.js", "node.js", "react.js", "angular.js", "nuxt.js", "svelte.js",
            "express.js", "gatsby.js", "remix.js", "ember.js",
        }
        matches = [m for m in matches if m.lower() not in _FRAMEWORK_NAMES]

        # AENDERUNG 07.02.2026: Schritt 1 — Blacklist fuer Muell-Dateinamen (Fix 20)
        _GARBAGE_PATTERNS = [
            r'^UNBEKANNTE',           # Platzhalter "UNBEKANNTE_DATEI"
            r'^BeispielDatei',        # Platzhalter
            r'^\.\/',                 # Relative Pfade "./globals.css"
            r'^module\.ex$',          # Elixir-Fehlmatch
            r'^request\.json$',       # Artefakt aus await request.json()
            r'DATEI',                 # "DATEI" als Name
        ]
        matches = [m for m in matches if not any(re.search(p, m) for p in _GARBAGE_PATTERNS)]

        # AENDERUNG 07.02.2026: Schritt 2 — Tech-Stack-Filter (Fix 20)
        tech_blueprint = getattr(self.manager, 'tech_blueprint', {})
        if tech_blueprint:
            lang = tech_blueprint.get('language', '').lower()
            framework = tech_blueprint.get('framework', '').lower()
            if lang in ('javascript', 'typescript') or 'next' in framework or 'react' in framework:
                matches = [m for m in matches if not m.endswith(('.py', '.ex', '.rb', '.go', '.rs', '.kt', '.swift', '.java'))]
            elif lang == 'python':
                matches = [m for m in matches if not m.endswith(('.jsx', '.tsx', '.ex', '.rb', '.go', '.rs', '.kt', '.swift'))]

        # AENDERUNG 08.02.2026: Schritt 2b — Pages Router Blacklist bei Next.js (Fix 23C)
        # ROOT-CAUSE-FIX: UTDS generiert pages/ Tasks obwohl Projekt App Router nutzt
        # Symptom: pages/index.js, pages/_app.js, pages/api/* neben app/ Dateien
        if tech_blueprint:
            project_type = tech_blueprint.get('project_type', '').lower()
            if 'next' in project_type:
                matches = [m for m in matches if not m.startswith('pages/') and not m.startswith('pages\\')]

        # AENDERUNG 07.02.2026: Schritt 3 — Validierung gegen existierende Dateien (Fix 20)
        if existing_files:
            validated = []
            affected_files_normalized = {
                af.replace("\\", "/") for af in (task.affected_files or []) if isinstance(af, str)
            }
            for m in matches:
                m_normalized = m.replace("\\", "/")
                m_basename = os.path.basename(m_normalized)
                if (m_normalized in existing_files
                        or m_basename in [os.path.basename(ef) for ef in existing_files]
                        or any(ef.endswith(f"/{m_normalized}") for ef in existing_files)
                        or m_normalized in affected_files_normalized):
                    validated.append(m)
            matches = validated

        found = list(set(matches))[:10]

        # Fallback auf affected_files
        if not found and task.affected_files:
            return task.affected_files

        return found

    def _sync_modified_files_to_manager(self, modified_files: List[str], result_text: str):
        """
        Synchronisiert UTDS-modifizierte Dateien zurück zu manager.current_code.

        ÄNDERUNG 03.02.2026: Verhindert dass Fixes bei nächster Iteration verloren gehen.
        Root Cause Fix für zyklisches Regenerieren.

        Args:
            modified_files: Liste der modifizierten Dateinamen
            result_text: Der vollständige Ergebnis-Text mit Code-Blöcken
        """
        if not modified_files or not hasattr(self.manager, 'current_code'):
            return

        # FIX 05.02.2026: current_code kann String ODER Dict sein
        # Wenn String: NICHT konvertieren (würde andere Funktionen wie merge_repaired_files brechen)
        # Sync nur durchführen wenn current_code bereits ein Dict ist oder None
        if self.manager.current_code is None:
            self.manager.current_code = {}
        elif isinstance(self.manager.current_code, str):
            # String belassen - Dateien sind auf Festplatte gespeichert,
            # beim nächsten Coder-Durchlauf wird Code neu geladen
            logger.info("[UTDS-Sync] current_code ist String - Sync übersprungen (Dateien sind auf Festplatte)")
            if hasattr(self.manager, '_ui_log'):
                self.manager._ui_log("UTDS-Sync", "Info",
                    f"Dateien direkt gespeichert: {', '.join(modified_files[:3])}")
            return

        synced_count = 0
        for filename in modified_files:
            # Extrahiere neuen Code-Inhalt aus result_text
            new_content = self._extract_file_content_from_result(filename, result_text)
            if new_content:
                # Update current_code Dictionary
                self.manager.current_code[filename] = new_content
                synced_count += 1
                logger.info(f"[UTDS-Sync] {filename} nach current_code synchronisiert ({len(new_content)} chars)")

        # ÄNDERUNG 03.02.2026: UI-Log für Sichtbarkeit im Projekt-Log
        # ÄNDERUNG 03.02.2026: UI-Log für Sichtbarkeit im Projekt-Log
        if synced_count > 0:
            logger.info(f"[UTDS-Sync] {synced_count}/{len(modified_files)} Dateien synchronisiert")
            if hasattr(self.manager, '_ui_log'):
                self.manager._ui_log("UTDS-Sync", "Success",
                    f"{synced_count} Datei(en) nach current_code synchronisiert: {', '.join(modified_files[:3])}")
        elif modified_files:
            # Log wenn keine Dateien extrahiert werden konnten (Debugging)
            logger.warning(f"[UTDS-Sync] Code-Extraktion fehlgeschlagen für: {modified_files}")
            if hasattr(self.manager, '_ui_log'):
                self.manager._ui_log("UTDS-Sync", "Warning",
                    f"Code-Extraktion fehlgeschlagen für {len(modified_files)} Datei(en)")

    def _extract_file_content_from_result(self, filename: str, result_text: str) -> Optional[str]:
        """
        Extrahiert den Code-Inhalt für eine Datei aus dem Ergebnis-Text.

        ÄNDERUNG 03.02.2026: Unterstützt verschiedene Code-Block-Formate.

        Args:
            filename: Name der Datei
            result_text: Vollständiger Ergebnis-Text

        Returns:
            Extrahierter Code-Inhalt oder None
        """
        if not result_text or not filename:
            return None

        # ÄNDERUNG 03.02.2026: Erweiterte Patterns für robustere Code-Extraktion
        # Unterstützt verschiedene Formate die LLMs/CrewAI produzieren
        basename = filename.split("/")[-1].split("\\")[-1]  # Nur Dateiname ohne Pfad
        patterns = [
            # 1. Markdown Code-Block mit Dateiname im Kommentar
            rf'```(?:python|javascript|js|jsx|ts|tsx|html|css|json|ini|cfg|yaml|toml)?\s*\n(?:#\s*{re.escape(filename)}|//\s*{re.escape(filename)})\s*\n(.*?)```',
            # 2. Code-Block nach "Datei: filename.py" oder "File: filename.py"
            rf'(?:Datei|File|###?):\s*{re.escape(filename)}\s*\n```[a-z]*\n(.*?)```',
            # 3. Mit Basename statt vollem Pfad
            rf'(?:Datei|File|###?):\s*{re.escape(basename)}\s*\n```[a-z]*\n(.*?)```',
            # 4. Markdown-Header: **filename.py** oder ### filename.py
            rf'(?:\*\*|###?\s+){re.escape(basename)}(?:\*\*)?[:\s]*\n```[a-z]*\n(.*?)```',
            # 5. [filename.py] Format
            rf'\[{re.escape(basename)}\][:\s]*\n```[a-z]*\n(.*?)```',
            # 6. Generischer Code-Block nach Dateiname
            rf'{re.escape(basename)}[:\s]*\n```[a-z]*\n(.*?)```',
            # 7. INI/CFG spezifisch: [pytest] section direkt erkennen
            rf'```(?:ini|cfg|toml)?\s*\n(\[(?:pytest|tool|metadata).*?)```',
        ]

        for pattern in patterns:
            match = re.search(pattern, result_text, re.DOTALL | re.IGNORECASE)
            if match:
                content = match.group(1).strip()
                if content and len(content) > 10:
                    return content

        # Fallback 1: Suche nach Code-Block der den Dateinamen im Text erwähnt
        code_blocks = re.findall(r'```[a-z]*\n(.*?)```', result_text, re.DOTALL)
        for block in code_blocks:
            # Prüfe ob der Block zum Dateinamen passt (Heuristik)
            if basename.endswith('.py') and ('def ' in block or 'import ' in block or 'class ' in block):
                if len(block) > 50:
                    return block.strip()
            elif basename.endswith('.ini') and '[' in block and ']' in block:
                return block.strip()
            elif basename.endswith('.cfg') and '[' in block:
                return block.strip()

        # Fallback 2: Größter Code-Block wenn nur eine Datei
        if code_blocks:
            longest = max(code_blocks, key=len)
            if len(longest) > 50:
                return longest.strip()

        return None

    def _collect_modified_files(self, results: List[TaskExecutionResult]) -> List[str]:
        """Sammelt alle geaenderten Dateien."""
        all_files = []
        for r in results:
            all_files.extend(r.modified_files)
        return list(set(all_files))

    def _has_critical_failure(self, batch: TaskBatch, result: BatchResult) -> bool:
        """Prueft ob ein kritischer Fehler aufgetreten ist."""
        for task in batch.tasks:
            if task.id in result.failed_tasks:
                if task.priority == TaskPriority.CRITICAL:
                    return True
        return False

    def _report_progress(self, stage: str, status: str, progress: float):
        """Meldet Fortschritt an Callback."""
        if self._progress_callback:
            try:
                self._progress_callback(stage, status, progress)
            except Exception as e:
                logger.warning(f"[TaskDispatcher] Progress-Callback Fehler: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """Liefert Dispatcher-Statistiken."""
        return {
            "max_parallel": self.max_parallel,
            "cached_agents": list(self._agent_cache.keys()),
            "tracker_summary": self.tracker._generate_summary()
        }

    def shutdown(self):
        """Beendet den Executor sauber."""
        self.executor.shutdown(wait=True)
