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
from concurrent.futures import ThreadPoolExecutor, as_completed
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

        results: List[TaskExecutionResult] = []
        futures = {}

        # Tasks parallel starten
        for task in batch.tasks:
            self.tracker.update_status(task.id, TaskStatus.IN_PROGRESS)
            future = self.executor.submit(self._execute_single_task, task)
            futures[future] = task

        # Auf Ergebnisse warten
        for future in as_completed(futures):
            task = futures[future]
            try:
                result = future.result(timeout=task.timeout_seconds)
                results.append(result)

                # Tracker aktualisieren
                if result.success:
                    self.tracker.update_status(
                        task.id,
                        TaskStatus.COMPLETED,
                        result=result.result,
                        modified_files=result.modified_files
                    )
                else:
                    # AENDERUNG 02.02.2026: Verbessertes Retry-Handling mit Logging
                    # Retry pruefen
                    can_retry = self.tracker.increment_retry(task.id)
                    if not can_retry:
                        # Max Retries erreicht - Status auf FAILED setzen
                        self.tracker.update_status(
                            task.id,
                            TaskStatus.FAILED,
                            error_message=f"Max Retries erreicht. Letzter Fehler: {result.error_message}"
                        )
                        logger.warning(f"[TaskDispatcher] Task {task.id} FAILED nach max retries")
                    else:
                        # Noch Retries moeglich - explizit auf PENDING setzen fuer Retry-Queue
                        self.tracker.update_status(
                            task.id,
                            TaskStatus.PENDING,
                            error_message=f"Retry geplant. Fehler: {result.error_message}"
                        )
                        logger.info(f"[TaskDispatcher] Task {task.id} wird wiederholt (Retry verfuegbar)")

            except Exception as e:
                logger.error(f"[TaskDispatcher] Task {task.id} Exception: {e}")
                results.append(TaskExecutionResult(
                    task_id=task.id,
                    success=False,
                    error_message=str(e)
                ))
                self.tracker.update_status(
                    task.id,
                    TaskStatus.FAILED,
                    error_message=str(e)
                )

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

    def _execute_single_task(self, task: DerivedTask) -> TaskExecutionResult:
        """
        Fuehrt einen einzelnen Task aus.

        Args:
            task: DerivedTask zum Ausfuehren

        Returns:
            TaskExecutionResult
        """
        start_time = time.time()

        # AENDERUNG 02.02.2026: Verbessertes Debug-Logging fuer Fehleranalyse
        logger.info(f"[UTDS] Starte Task {task.id}: {task.title[:50]} | Agent: {task.target_agent.value}")

        try:
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

            # CrewAI Task erstellen
            crew_task = Task(
                description=self._build_task_description(task),
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

            # AENDERUNG 07.02.2026: existing_files fuer Dateiname-Validierung (Fix 20)
            existing_files = []
            project_path = getattr(self.manager, 'project_path', None)
            if project_path and os.path.isdir(str(project_path)):
                for root, dirs, files in os.walk(str(project_path)):
                    dirs[:] = [d for d in dirs if d not in ('node_modules', '.next', '.git', '__pycache__')]
                    for fname in files:
                        rel = os.path.relpath(os.path.join(root, fname), str(project_path)).replace("\\", "/")
                        existing_files.append(rel)

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
                    "success": True,
                    "affected_files": task.affected_files,
                    "modified_files": modified_files,
                    "model": model_name,
                    "duration": round(time.time() - start_time, 1)
                })

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
            for m in matches:
                m_normalized = m.replace("\\", "/")
                m_basename = os.path.basename(m_normalized)
                if (m_normalized in existing_files
                        or m_basename in [os.path.basename(ef) for ef in existing_files]
                        or any(ef.endswith(f"/{m_normalized}") for ef in existing_files)):
                    validated.append(m)
            if validated:
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
