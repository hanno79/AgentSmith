# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 30.01.2026
Version: 1.0
Beschreibung: Documentation Service - Aggregiert und speichert Projekt-Dokumentation.
              Sammelt Informationen von allen Agenten für README und CHANGELOG.
"""

import os
import json
from datetime import datetime
from typing import Dict, Any, List, Optional


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
            "quality_validations": []
        }
        self.created_at = datetime.now()

    def set_project_path(self, project_path: str) -> None:
        """Setzt den Projekt-Pfad nachträglich."""
        self.project_path = project_path

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
