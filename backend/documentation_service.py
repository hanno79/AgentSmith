# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 01.02.2026
Version: 1.2
Beschreibung: Documentation Service - Aggregiert und speichert Projekt-Dokumentation.
              Sammelt Informationen von allen Agenten für README und CHANGELOG.
              AENDERUNG 31.01.2026: Dart AI Feature-Ableitung Dokumentation
              (anforderungen, features, tasks, file_by_file, traceability).
              AENDERUNG 31.01.2026: Traceability-Logik in TraceabilityService ausgelagert (Regel 1).
"""

import os
import json
from datetime import datetime
from typing import Dict, Any, List, Optional

from backend.traceability_service import TraceabilityService


class DocumentationService:
    """
    Service-Klasse für Dokumentations-Management.

    Sammelt Informationen von allen Agenten und bereitet sie
    für die Dokumentations-Generierung vor.
    """

    def __init__(self, project_path: Optional[str] = None):
        """
        Initialisiert den Documentation Service.

        Args:
            project_path: Pfad zum Projekt-Verzeichnis (kann später gesetzt werden)
        """
        self.project_path = project_path
        self.data: Dict[str, Any] = {
            "goal": "",
            "briefing": {},
            "techstack": {},
            "schema": "",
            "design": "",
            "code_files": [],
            "iterations": [],
            "security_findings": [],
            "test_results": [],
            "quality_validations": [],
            # AENDERUNG 31.01.2026: Dart AI Feature-Ableitung
            "anforderungen": [],
            "features": [],
            "tasks": [],
            "file_by_file_plan": {},
            "file_generations": [],
            "traceability": {},
            # AENDERUNG 01.02.2026: Orchestrator-Entscheidungen
            "orchestrator_decisions": []
        }
        self.created_at = datetime.now()
        self._traceability_service = TraceabilityService(self.project_path, self.data)

    def set_project_path(self, project_path: str) -> None:
        """Setzt den Projekt-Pfad nachträglich."""
        self.project_path = project_path
        self._traceability_service.project_path = project_path

    def collect_goal(self, user_goal: str) -> None:
        """
        Sammelt das Benutzer-Ziel.

        Args:
            user_goal: Die ursprüngliche Benutzer-Anfrage
        """
        self.data["goal"] = user_goal

    def collect_briefing(self, briefing: Dict[str, Any]) -> None:
        """
        Sammelt das Discovery-Briefing.

        Args:
            briefing: Discovery-Briefing Dictionary
        """
        self.data["briefing"] = briefing

    def collect_techstack(self, blueprint: Dict[str, Any]) -> None:
        """
        Sammelt TechStack-Blueprint.

        Args:
            blueprint: Das TechStack-Blueprint Dictionary
        """
        self.data["techstack"] = blueprint

    def collect_schema(self, schema: str) -> None:
        """
        Sammelt Datenbank-Schema.

        Args:
            schema: Das generierte DB-Schema
        """
        self.data["schema"] = schema

    def collect_design(self, design_concept: str) -> None:
        """
        Sammelt Design-Konzept.

        Args:
            design_concept: Das generierte Design-Konzept
        """
        self.data["design"] = design_concept

    def collect_code_file(self, filename: str, content: str, description: str = "") -> None:
        """
        Sammelt Information über eine Code-Datei.

        Args:
            filename: Name der Datei
            content: Inhalt der Datei (für Statistiken)
            description: Optionale Beschreibung
        """
        self.data["code_files"].append({
            "filename": filename,
            "lines": len(content.split("\n")) if content else 0,
            "size": len(content) if content else 0,
            "description": description,
            "timestamp": datetime.now().isoformat()
        })

    def collect_iteration(
        self,
        iteration: int,
        changes: str,
        status: str,
        review_summary: str = "",
        test_result: str = ""
    ) -> None:
        """
        Sammelt Iterations-Daten für CHANGELOG.

        Args:
            iteration: Iterations-Nummer
            changes: Beschreibung der Änderungen
            status: Status (success, failed, partial)
            review_summary: Zusammenfassung des Reviews
            test_result: Testergebnis
        """
        self.data["iterations"].append({
            "number": iteration,
            "timestamp": datetime.now().isoformat(),
            "changes": changes[:500] if changes else "",  # Max 500 Zeichen
            "status": status,
            "review_summary": review_summary[:300] if review_summary else "",
            "test_result": test_result[:200] if test_result else ""
        })

    def collect_security_finding(self, finding: Dict[str, Any]) -> None:
        """
        Sammelt Security-Findings.

        Args:
            finding: Security-Finding Dictionary mit severity, description, etc.
        """
        self.data["security_findings"].append({
            **finding,
            "timestamp": datetime.now().isoformat()
        })

    def collect_test_result(self, test_name: str, passed: bool, details: str = "") -> None:
        """
        Sammelt Test-Ergebnisse.

        Args:
            test_name: Name des Tests
            passed: Ob der Test bestanden wurde
            details: Optionale Details
        """
        self.data["test_results"].append({
            "name": test_name,
            "passed": passed,
            "details": details[:200] if details else "",
            "timestamp": datetime.now().isoformat()
        })

    def collect_quality_validation(self, step: str, result: Dict[str, Any]) -> None:
        """
        Sammelt Quality Gate Validierungsergebnisse.

        Args:
            step: Name des validierten Steps (z.B. "TechStack", "Schema")
            result: ValidationResult als Dictionary
        """
        self.data["quality_validations"].append({
            "step": step,
            "passed": result.get("passed", False),
            "score": result.get("score", 0.0),
            "issues": result.get("issues", []),
            "warnings": result.get("warnings", []),
            "timestamp": datetime.now().isoformat()
        })

    # AENDERUNG 01.02.2026: Orchestrator-Entscheidungen dokumentieren
    def collect_orchestrator_decision(
        self,
        iteration: int,
        action: str,
        target_agent: str,
        root_cause: str = None,
        model_switch: bool = False,
        error_hash: str = None
    ) -> None:
        """
        Sammelt Orchestrator-Validierungsentscheidungen.

        Args:
            iteration: Aktuelle Iteration
            action: Die gewählte Aktion (proceed, fix, model_switch, escalate)
            target_agent: Der Ziel-Agent für die nächste Aktion
            root_cause: Erkannte Root Cause (falls vorhanden)
            model_switch: Ob Modellwechsel empfohlen wurde
            error_hash: Hash des Fehlers (für Tracking)
        """
        self.data["orchestrator_decisions"].append({
            "iteration": iteration,
            "action": action,
            "target_agent": target_agent,
            "root_cause": root_cause[:500] if root_cause else None,
            "model_switch_recommended": model_switch,
            "error_hash": error_hash[:12] if error_hash else None,
            "timestamp": datetime.now().isoformat()
        })

    # AENDERUNG 01.02.2026: UTDS Task-Derivation Dokumentation
    def collect_task_derivation(self, derivation_result: Dict[str, Any]) -> None:
        """
        Sammelt UTDS Task-Derivation Details.

        Args:
            derivation_result: TaskDerivationResult als Dict
        """
        if "task_derivations" not in self.data:
            self.data["task_derivations"] = []

        self.data["task_derivations"].append({
            "timestamp": datetime.now().isoformat(),
            "source": derivation_result.get("source", "unknown"),
            "total_tasks": derivation_result.get("total_tasks", 0),
            "by_category": derivation_result.get("tasks_by_category", {}),
            "by_priority": derivation_result.get("tasks_by_priority", {}),
            "by_agent": derivation_result.get("tasks_by_agent", {}),
            "derivation_time": derivation_result.get("derivation_time_seconds", 0)
        })

    def collect_task_execution_results(self, batch_results: List[Dict[str, Any]]) -> None:
        """
        Sammelt Batch-Execution Ergebnisse.

        Args:
            batch_results: Liste von BatchResult Dicts
        """
        if "task_executions" not in self.data:
            self.data["task_executions"] = []

        for result in batch_results:
            self.data["task_executions"].append({
                "batch_id": result.get("batch_id", ""),
                "success": result.get("success", False),
                "completed_tasks": len(result.get("completed_tasks", [])),
                "failed_tasks": len(result.get("failed_tasks", [])),
                "execution_time": result.get("execution_time_seconds", 0),
                "modified_files": result.get("modified_files", [])[:10],
                "timestamp": datetime.now().isoformat()
            })

    def get_task_derivation_summary(self) -> Dict[str, Any]:
        """
        Erstellt eine Zusammenfassung aller Task-Derivations.

        Returns:
            Dict mit Statistiken
        """
        derivations = self.data.get("task_derivations", [])
        executions = self.data.get("task_executions", [])

        if not derivations:
            return {"total_derivations": 0}

        total_tasks = sum(d.get("total_tasks", 0) for d in derivations)
        total_completed = sum(e.get("completed_tasks", 0) for e in executions)
        total_failed = sum(e.get("failed_tasks", 0) for e in executions)

        # Aggregiere Kategorien
        categories = {}
        for d in derivations:
            for cat, count in d.get("by_category", {}).items():
                categories[cat] = categories.get(cat, 0) + count

        return {
            "total_derivations": len(derivations),
            "total_tasks": total_tasks,
            "total_completed": total_completed,
            "total_failed": total_failed,
            "success_rate": total_completed / max(total_completed + total_failed, 1),
            "categories": categories,
            "sources": list(set(d.get("source", "") for d in derivations))
        }

    def generate_readme_context(self) -> str:
        """
        Bereitet Kontext für README-Generierung vor.

        Dieser Kontext wird an den Documentation Manager Agent übergeben.

        Returns:
            Formatierter String mit allen relevanten Informationen
        """
        techstack = self.data["techstack"]
        briefing = self.data["briefing"]

        context_parts = [
            f"## Projektbeschreibung\n{self.data['goal']}",
            "",
            "## Technische Details",
            f"- **Projekttyp:** {techstack.get('project_type', 'unbekannt')}",
            f"- **Sprache:** {techstack.get('language', 'unbekannt')}",
            f"- **App-Typ:** {techstack.get('app_type', 'unbekannt')}",
        ]

        if techstack.get("database"):
            context_parts.append(f"- **Datenbank:** {techstack['database']}")

        if techstack.get("requires_server"):
            context_parts.append(f"- **Server-Port:** {techstack.get('server_port', 'nicht definiert')}")

        # Dependencies
        if techstack.get("dependencies"):
            deps = techstack["dependencies"]
            if isinstance(deps, list):
                context_parts.append(f"- **Dependencies:** {', '.join(deps)}")

        # Installation und Start
        context_parts.append("")
        context_parts.append("## Installation & Start")
        if techstack.get("install_command"):
            context_parts.append(f"- **Installation:** `{techstack['install_command']}`")
        if techstack.get("run_command"):
            context_parts.append(f"- **Start:** `{techstack['run_command']}`")

        # Briefing-Details wenn vorhanden
        if briefing:
            context_parts.append("")
            context_parts.append("## Projekt-Kontext")
            if briefing.get("project_goal"):
                context_parts.append(f"- **Ziel:** {briefing['project_goal']}")
            if briefing.get("target_audience"):
                context_parts.append(f"- **Zielgruppe:** {briefing['target_audience']}")
            if briefing.get("key_features"):
                features = briefing["key_features"]
                if isinstance(features, list):
                    context_parts.append(f"- **Features:** {', '.join(features)}")

        # Code-Dateien
        if self.data["code_files"]:
            context_parts.append("")
            context_parts.append("## Erstellte Dateien")
            for f in self.data["code_files"]:
                context_parts.append(f"- `{f['filename']}` ({f['lines']} Zeilen)")

        # Schema
        if self.data["schema"]:
            context_parts.append("")
            context_parts.append("## Datenbank-Schema")
            # Nur erste 500 Zeichen des Schemas
            schema_preview = self.data["schema"][:500]
            if len(self.data["schema"]) > 500:
                schema_preview += "..."
            context_parts.append(f"```sql\n{schema_preview}\n```")

        return "\n".join(context_parts)

    def generate_changelog_entries(self) -> str:
        """
        Generiert CHANGELOG-Einträge aus den Iterations-Daten.

        Returns:
            Formatierter CHANGELOG-String
        """
        if not self.data["iterations"]:
            return "Keine Iterations-Daten vorhanden."

        entries = [
            f"# CHANGELOG",
            f"",
            f"Generiert am: {datetime.now().strftime('%d.%m.%Y %H:%M')}",
            ""
        ]

        for iteration in sorted(self.data["iterations"], key=lambda x: x["number"], reverse=True):
            status_emoji = "OK" if iteration["status"] == "success" else "FEHLER"
            entries.append(f"## Iteration {iteration['number']} [{status_emoji}]")
            entries.append(f"*{iteration['timestamp'][:10]}*")
            entries.append("")

            if iteration["changes"]:
                entries.append(f"### Änderungen")
                entries.append(iteration["changes"])
                entries.append("")

            if iteration["review_summary"]:
                entries.append(f"### Review")
                entries.append(iteration["review_summary"])
                entries.append("")

            if iteration["test_result"]:
                entries.append(f"### Tests")
                entries.append(iteration["test_result"])
                entries.append("")

        return "\n".join(entries)

    def save_readme(self, content: str) -> Optional[str]:
        """
        Speichert README.md im Projekt-Verzeichnis.

        Args:
            content: Der README-Inhalt

        Returns:
            Pfad zur erstellten Datei oder None bei Fehler
        """
        if not self.project_path:
            return None

        try:
            path = os.path.join(self.project_path, "README.md")
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            return path
        except Exception as e:
            print(f"FEHLER beim Speichern von README.md: {e}")
            return None

    def save_changelog(self) -> Optional[str]:
        """
        Generiert und speichert CHANGELOG.md.

        Returns:
            Pfad zur erstellten Datei oder None bei Fehler
        """
        if not self.project_path:
            return None

        try:
            content = self.generate_changelog_entries()
            path = os.path.join(self.project_path, "CHANGELOG.md")
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            return path
        except Exception as e:
            print(f"FEHLER beim Speichern von CHANGELOG.md: {e}")
            return None

    def get_summary(self) -> Dict[str, Any]:
        """
        Gibt eine Zusammenfassung aller gesammelten Daten zurück.

        Returns:
            Dictionary mit Zusammenfassung
        """
        return {
            "goal": self.data["goal"][:100] if self.data["goal"] else "",
            "techstack": self.data["techstack"].get("project_type", "unbekannt"),
            "language": self.data["techstack"].get("language", "unbekannt"),
            "code_files_count": len(self.data["code_files"]),
            "iterations_count": len(self.data["iterations"]),
            "security_findings_count": len(self.data["security_findings"]),
            "test_results_count": len(self.data["test_results"]),
            "quality_validations_count": len(self.data["quality_validations"]),
            "has_schema": bool(self.data["schema"]),
            "has_design": bool(self.data["design"]),
            "created_at": self.created_at.isoformat()
        }

    def export_to_json(self) -> str:
        """
        Exportiert alle gesammelten Daten als JSON.

        Returns:
            JSON-String mit allen Daten
        """
        export_data = {
            **self.data,
            "created_at": self.created_at.isoformat(),
            "project_path": self.project_path
        }
        return json.dumps(export_data, indent=2, ensure_ascii=False)

    # =========================================================================
    # AENDERUNG 31.01.2026: Dart AI Feature-Ableitung Dokumentation
    # =========================================================================

    def collect_anforderungen(self, anforderungen: List[Dict[str, Any]]) -> None:
        """
        Sammelt analysierte Anforderungen vom Analyst-Agenten.

        Args:
            anforderungen: Liste der Anforderungen mit id, titel, kategorie, etc.
        """
        self.data["anforderungen"] = anforderungen

    def collect_features(self, features: List[Dict[str, Any]]) -> None:
        """
        Sammelt extrahierte Features vom Konzepter-Agenten.

        Args:
            features: Liste der Features mit id, titel, anforderungen, etc.
        """
        self.data["features"] = features

    def collect_tasks(self, tasks: List[Dict[str, Any]]) -> None:
        """
        Sammelt erstellte Tasks vom Planner-Agenten.

        Args:
            tasks: Liste der Tasks mit id, beschreibung, dateien, etc.
        """
        self.data["tasks"] = tasks

    def collect_file_by_file_plan(self, plan: Dict[str, Any]) -> None:
        """
        Sammelt den File-by-File Generierungsplan.

        Args:
            plan: Der Plan mit files-Liste und Metadaten
        """
        self.data["file_by_file_plan"] = {
            "total_files": len(plan.get("files", [])),
            "files": [
                {
                    "path": f.get("path", ""),
                    "description": f.get("description", "")[:100],
                    "priority": f.get("priority", 0),
                    "depends_on": f.get("depends_on", [])
                }
                for f in plan.get("files", [])
            ],
            "timestamp": datetime.now().isoformat()
        }

    def collect_file_generation_result(
        self,
        filepath: str,
        success: bool,
        lines: int = 0,
        error: str = None
    ) -> None:
        """
        Sammelt das Ergebnis einer einzelnen Datei-Generierung.

        Args:
            filepath: Pfad der generierten Datei
            success: Ob die Generierung erfolgreich war
            lines: Anzahl der Zeilen (bei Erfolg)
            error: Fehlermeldung (bei Misserfolg)
        """
        self.data["file_generations"].append({
            "filepath": filepath,
            "success": success,
            "lines": lines,
            "error": error[:200] if error else None,
            "timestamp": datetime.now().isoformat()
        })

    def collect_traceability_matrix(self, matrix: Dict[str, Any]) -> None:
        """Delegiert an TraceabilityService."""
        self._traceability_service.collect_traceability_matrix(matrix)

    def generate_traceability_report(self) -> str:
        """Delegiert an TraceabilityService."""
        return self._traceability_service.generate_traceability_report()

    def save_traceability_report(self) -> Optional[str]:
        """Delegiert an TraceabilityService."""
        return self._traceability_service.save_traceability_report()
