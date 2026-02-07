"""
Author: rahn
Datum: 01.02.2026
Version: 1.2
Beschreibung: Task-Ableitung Integration fuer DevLoop.
              Zerlegt Feedback in Tasks und fuehrt sie parallel aus.
              AENDERUNG 01.02.2026 v1.1: WebSocket Events, Memory und Documentation Integration.
              AENDERUNG 01.02.2026 v1.2: Security und Sandbox als UTDS-Quellen (Phase 9)
"""

import os
import json
from typing import Any, Dict, List, Tuple, Optional

from backend.task_models import DerivedTask, TaskStatus, TaskDerivationResult
from backend.task_deriver import TaskDeriver
from backend.task_dispatcher import TaskDispatcher
from backend.task_tracker import TaskTracker
from backend.dart_task_sync import DartTaskSync

# AENDERUNG 01.02.2026: Memory und Documentation Integration
try:
    from agents.memory_agent import record_task_derivation
    MEMORY_AVAILABLE = True
except ImportError:
    MEMORY_AVAILABLE = False


class DevLoopTaskDerivation:
    """
    Integriert das Universal Task Derivation System in den DevLoop.

    Ermoeglicht:
    - Feedback-Zerlegung in einzelne Tasks
    - Parallele Ausfuehrung durch mehrere Agenten
    - Traceability und Dart-Synchronisation
    """

    def __init__(self, manager, config: Dict[str, Any] = None):
        """
        Initialisiert die Task-Derivation Integration.

        Args:
            manager: SessionManager/OrchestrationManager
            config: Konfiguration
        """
        self.manager = manager
        self.config = config or getattr(manager, 'config', {})

        # Dart-Sync initialisieren
        self.dart_sync = DartTaskSync() if os.environ.get("DART_TOKEN") else None

        # Tracker initialisieren
        log_dir = os.path.join(getattr(manager, 'base_dir', '.'), 'library')
        self.tracker = TaskTracker(log_dir=log_dir, dart_sync=self.dart_sync)

        # Deriver initialisieren (mit ModelRouter wenn verfuegbar)
        router = getattr(manager, 'model_router', None)
        self.deriver = TaskDeriver(model_router=router, config=self.config)

        # Dispatcher (lazy init)
        self._dispatcher: Optional[TaskDispatcher] = None

    @property
    def dispatcher(self) -> TaskDispatcher:
        """Lazy-Init des Dispatchers."""
        if self._dispatcher is None:
            self._dispatcher = TaskDispatcher(
                manager=self.manager,
                config=self.config,
                tracker=self.tracker,
                router=getattr(self.manager, 'model_router', None)
            )
        return self._dispatcher

    def process_feedback(
        self,
        feedback: str,
        source: str,
        context: Dict[str, Any] = None
    ) -> Tuple[bool, str, List[str]]:
        """
        Verarbeitet Feedback durch Task-Ableitung und parallele Ausfuehrung.

        Args:
            feedback: Feedback-Text (Review, QG, Security, etc.)
            source: Quelle ("reviewer", "quality_gate", "security", "sandbox")
            context: Zusaetzlicher Kontext

        Returns:
            Tuple (erfolg, zusammengefasstes_feedback, modifizierte_dateien)
        """
        context = context or {}

        # AENDERUNG 01.02.2026: Strukturiertes WebSocket Event - Start
        self._emit_event("DerivationStart", {
            "source": source,
            "feedback_length": len(feedback),
            "has_context": bool(context)
        })

        # 1. Tasks ableiten
        result = self.deriver.derive_tasks(feedback, source, context)

        if not result.tasks:
            self._emit_event("DerivationComplete", {
                "success": False,
                "reason": "no_tasks_derived",
                "source": source
            })
            return False, feedback, []

        # AENDERUNG 01.02.2026: Strukturiertes Event - Tasks abgeleitet
        self._emit_event("TasksDerived", {
            "total": result.total_tasks,
            "by_category": result.tasks_by_category,
            "by_priority": result.tasks_by_priority,
            "by_agent": result.tasks_by_agent,
            "derivation_time": result.derivation_time_seconds
        })

        # 2. Tasks im Tracker registrieren
        task_ids = self.tracker.log_derivation_result(result)

        # AENDERUNG 01.02.2026: Memory-System Integration
        self._record_to_memory(result, True)

        # AENDERUNG 01.02.2026: Documentation-Service Integration
        self._record_to_documentation(result)

        # 3. Tasks ausfuehren mit Batch-Events
        batch_results = []
        batches = self.dispatcher.dispatch(result.tasks)

        for i, batch in enumerate(batches):
            self._emit_event("BatchExecutionStart", {
                "batch_id": batch.batch_id,
                "batch_number": i + 1,
                "total_batches": len(batches),
                "task_count": batch.task_count
            })

            batch_result = self.dispatcher.execute_batch(batch)
            batch_results.append(batch_result)

            self._emit_event("BatchExecutionComplete", {
                "batch_id": batch.batch_id,
                "success": batch_result.success,
                "completed": len(batch_result.completed_tasks),
                "failed": len(batch_result.failed_tasks),
                "execution_time": batch_result.execution_time_seconds
            })

        # 4. Ergebnisse zusammenfassen
        success, summary, modified_files = self._summarize_results(batch_results, result)

        # AENDERUNG 01.02.2026: Execution Results dokumentieren
        self._record_execution_to_documentation(batch_results)

        # AENDERUNG 01.02.2026: Strukturiertes Event - Abgeschlossen
        self._emit_event("DerivationComplete", {
            "success": success,
            "total_tasks": result.total_tasks,
            "completed_tasks": sum(len(br.completed_tasks) for br in batch_results),
            "failed_tasks": sum(len(br.failed_tasks) for br in batch_results),
            "modified_files": modified_files[:10],
            "source": source
        })

        return success, summary, modified_files

    def _emit_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """
        Sendet strukturiertes WebSocket Event an Frontend UND globalen Output-Loop.
        AENDERUNG 05.02.2026: Events auch an server_output.log senden.
        """
        event_data = json.dumps(data, ensure_ascii=False, default=str)
        
        # UI-Logging
        self._log("UTDS", event_type, event_data)
        
        # Global Output Loop - Events broadcasten
        try:
            from backend.session_manager import get_session_manager
            sm = get_session_manager()
            if hasattr(sm, 'broadcast_event'):
                sm.broadcast_event("utds", event_type, event_data)
        except Exception:
            pass
        
        # Server-Output-Log schreiben
        try:
            log_entry = json.dumps({
                "timestamp": datetime.now().isoformat(),
                "agent": "UTDS",
                "action": event_type,
                "content": event_data
            }, ensure_ascii=False)
            
            # In server_output.log schreiben falls vorhanden
            import os
            log_path = os.path.join(os.path.dirname(__file__), '..', 'server_output.log')
            if os.path.exists(log_path):
                with open(log_path, 'a', encoding='utf-8') as f:
                    f.write(log_entry + '\n')
        except Exception:
            pass

    def _record_to_memory(self, result: TaskDerivationResult, success: bool) -> None:
        """Speichert Task-Derivation im Memory-System."""
        if not MEMORY_AVAILABLE:
            return

        try:
            memory_path = os.path.join(
                getattr(self.manager, 'base_dir', '.'),
                "memory", "global_memory.json"
            )
            record_task_derivation(memory_path, result.to_dict(), success)
        except Exception as e:
            self._log("UTDS", "MemoryWarning", f"Memory-Recording fehlgeschlagen: {e}")

    def _record_to_documentation(self, result: TaskDerivationResult) -> None:
        """Dokumentiert Task-Derivation im Documentation-Service."""
        try:
            if hasattr(self.manager, 'doc_service') and self.manager.doc_service:
                self.manager.doc_service.collect_task_derivation(result.to_dict())
        except Exception as e:
            self._log("UTDS", "DocWarning", f"Documentation fehlgeschlagen: {e}")

    def _record_execution_to_documentation(self, batch_results: List) -> None:
        """Dokumentiert Batch-Execution Results."""
        try:
            if hasattr(self.manager, 'doc_service') and self.manager.doc_service:
                results_dicts = [br.to_dict() for br in batch_results]
                self.manager.doc_service.collect_task_execution_results(results_dicts)
        except Exception as e:
            self._log("UTDS", "DocWarning", f"Execution-Documentation fehlgeschlagen: {e}")

    def should_use_task_derivation(
        self,
        feedback: str,
        source: str,
        iteration: int
    ) -> bool:
        """
        Entscheidet ob Task-Ableitung sinnvoll ist.

        Args:
            feedback: Feedback-Text
            source: Feedback-Quelle ("reviewer", "quality_gate", "security", "sandbox", "initial", "discovery")
            iteration: Aktuelle Iteration

        Returns:
            True wenn Task-Ableitung aktiviert werden soll
        """
        # AENDERUNG 01.02.2026: Initial und Discovery immer verarbeiten (Phase 5)
        if source in ["initial", "discovery"]:
            return len(feedback.strip()) >= 30

        # Deaktiviert fuer erste Iteration (nur fuer non-initial Quellen)
        if iteration < 1:
            return False

        # Minimale Feedback-Laenge
        if len(feedback.strip()) < 50:
            return False

        # AENDERUNG 01.02.2026: Quellen-spezifische Indikatoren (Phase 9)
        if source == "security":
            security_indicators = [
                "Vulnerability", "CVE-", "Schwachstelle", "Injection",
                "XSS", "CSRF", "SQL", "Security", "kritisch", "high",
                "medium", "low", "severity", "risk"
            ]
            indicator_count = sum(1 for ind in security_indicators if ind.lower() in feedback.lower())
            return indicator_count >= 1  # Ein Security-Issue reicht

        if source == "sandbox":
            sandbox_indicators = [
                "Error:", "Exception:", "Traceback", "Failed",
                "AssertionError", "TypeError", "ValueError",
                "ImportError", "NameError", "SyntaxError",
                "FAIL:", "ERROR:", "Sandbox-Fehler", "Test-Summary"
            ]
            indicator_count = sum(1 for ind in sandbox_indicators if ind in feedback)
            return indicator_count >= 1  # Ein Sandbox-Fehler reicht

        # Standard: Pruefen ob Feedback mehrere Issues enthaelt (reviewer, quality_gate)
        issue_indicators = [
            "\n-", "\n*", "\n1.", "\n2.",  # Listen
            "Fehler:", "Error:", "Warning:",  # Fehler-Keywords
            "TODO:", "FIXME:", "BUG:",  # Marker
            "Ursache:", "Loesung:", "Betroffene",  # Root Cause Format
        ]

        indicator_count = sum(1 for ind in issue_indicators if ind in feedback)

        # Aktivieren wenn mehrere Indikatoren gefunden
        return indicator_count >= 2

    def _summarize_results(
        self,
        batch_results: List,
        derivation_result: TaskDerivationResult
    ) -> Tuple[bool, str, List[str]]:
        """
        Fasst die Ausfuehrungsergebnisse zusammen.

        Args:
            batch_results: Liste von BatchResults
            derivation_result: Original-Derivation-Result

        Returns:
            Tuple (gesamt_erfolg, zusammenfassung, modifizierte_dateien)
        """
        all_completed = []
        all_failed = []
        all_modified = []
        all_errors = []

        for br in batch_results:
            all_completed.extend(br.completed_tasks)
            all_failed.extend(br.failed_tasks)
            all_modified.extend(br.modified_files)
            all_errors.extend(br.errors)

        total = len(derivation_result.tasks)
        completed = len(all_completed)
        failed = len(all_failed)

        success = completed == total

        # Zusammenfassung erstellen
        summary_parts = [
            f"## Task-Verarbeitung abgeschlossen",
            f"- Gesamt: {total} Tasks",
            f"- Erfolgreich: {completed}",
            f"- Fehlgeschlagen: {failed}",
        ]

        if all_modified:
            # AENDERUNG 02.02.2026: set kann nicht gesliced werden, erst zu list konvertieren
            unique_files = list(set(all_modified))[:5]
            summary_parts.append(f"- Geaenderte Dateien: {', '.join(unique_files)}")

        if all_errors:
            summary_parts.append("\n### Fehler:")
            for err in all_errors[:3]:
                summary_parts.append(f"- {err[:100]}")

        # Wenn nicht alle erfolgreich, verbleibende Issues aufzeigen
        if not success:
            summary_parts.append("\n### Verbleibende Aufgaben:")
            for task in derivation_result.tasks:
                if task.id in all_failed:
                    summary_parts.append(f"- [{task.id}] {task.title}: {task.source_issue[:100]}")

        return success, "\n".join(summary_parts), list(set(all_modified))

    def get_pending_tasks(self) -> List[DerivedTask]:
        """Liefert alle ausstehenden Tasks."""
        return self.tracker.get_pending_tasks()

    def retry_failed_tasks(self) -> Tuple[bool, str]:
        """
        Versucht fehlgeschlagene Tasks erneut.

        Returns:
            Tuple (erfolg, zusammenfassung)
        """
        failed = self.tracker.get_tasks_by_status(TaskStatus.FAILED)
        retryable = [t for t in failed if t.can_retry()]

        if not retryable:
            return True, "Keine wiederholbaren Tasks vorhanden"

        # Tasks zuruecksetzen
        for task in retryable:
            task.status = TaskStatus.PENDING

        # Erneut ausfuehren
        batch_results = self.dispatcher.execute_all(retryable)

        # Zusammenfassen
        completed = sum(len(br.completed_tasks) for br in batch_results)
        return completed == len(retryable), f"Retry: {completed}/{len(retryable)} erfolgreich"

    def get_traceability_report(self) -> Dict[str, Any]:
        """Liefert Traceability-Report."""
        return self.tracker.get_traceability_report()

    def export_report(self, output_path: str = None) -> str:
        """Exportiert Markdown-Report."""
        return self.tracker.export_markdown_report(output_path)

    def _log(self, agent: str, event: str, data: Any):
        """UI-Logging Helper."""
        if hasattr(self.manager, '_ui_log'):
            self.manager._ui_log(agent, event, data)
        else:
            print(f"[{agent}] {event}: {data}")

    def shutdown(self):
        """Beendet Ressourcen sauber."""
        if self._dispatcher:
            self._dispatcher.shutdown()


def integrate_task_derivation(
    manager,
    feedback: str,
    source: str,
    context: Dict[str, Any] = None,
    iteration: int = 0
) -> Tuple[bool, str, List[str]]:
    """
    Convenience-Funktion fuer einfache Integration.

    Args:
        manager: SessionManager/OrchestrationManager
        feedback: Feedback-Text
        source: Feedback-Quelle
        context: Zusaetzlicher Kontext
        iteration: Aktuelle Iteration

    Returns:
        Tuple (verwendet_task_derivation, feedback_oder_summary, modifizierte_dateien)
    """
    # Task-Derivation Instanz holen oder erstellen
    if not hasattr(manager, '_task_derivation'):
        manager._task_derivation = DevLoopTaskDerivation(manager)

    td = manager._task_derivation

    # Pruefen ob Task-Derivation sinnvoll ist
    if not td.should_use_task_derivation(feedback, source, iteration):
        return False, feedback, []

    # Task-Derivation ausfuehren
    return td.process_feedback(feedback, source, context)
