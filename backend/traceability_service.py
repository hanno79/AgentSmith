# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 31.01.2026
Version: 1.0
Beschreibung: Traceability-Service - Traceability-Matrix und Reports.
              Aus documentation_service.py ausgelagert (Regel 1: Dateigroesse).

              AENDERUNG 07.02.2026: User Stories Sektion im Report
              (Dart Task zE40HTp29XJn, Feature-Ableitung Konzept v1.0 Phase 3)
"""

import os
from datetime import datetime
from typing import Dict, Any, Optional


class TraceabilityService:
    """
    Service fuer Traceability-Matrix und Report-Generierung.

    Erwartet Referenz auf die Dokumentations-Daten (anforderungen, features,
    file_by_file_plan, file_generations, traceability).
    """

    def __init__(self, project_path: Optional[str], data: Dict[str, Any]):
        """
        Args:
            project_path: Pfad zum Projekt (fuer save_traceability_report)
            data: Referenz auf DocumentationService.data
        """
        self.project_path = project_path
        self.data = data

    def collect_traceability_matrix(self, matrix: Dict[str, Any]) -> None:
        """
        Sammelt die Traceability-Matrix.

        Args:
            matrix: Die vollstaendige Traceability-Matrix
        """
        self.data["traceability"] = {
            "summary": matrix.get("summary", {}),
            "coverage": matrix.get("summary", {}).get("coverage", 0.0),
            "gaps": self._summarize_gaps(matrix),
            "timestamp": datetime.now().isoformat()
        }

    def _summarize_gaps(self, matrix: Dict[str, Any]) -> Dict[str, int]:
        """
        Fasst die Luecken in der Traceability zusammen.

        Args:
            matrix: Die Traceability-Matrix

        Returns:
            Dict mit Anzahl der Luecken pro Kategorie
        """
        anforderungen = matrix.get("anforderungen", {})
        features = matrix.get("features", {})
        tasks = matrix.get("tasks", {})

        return {
            "anforderungen_ohne_features": sum(
                1 for req in anforderungen.values()
                if not req.get("features")
            ),
            # AENDERUNG 07.02.2026: Features ohne User Stories zaehlen
            "features_ohne_user_stories": sum(
                1 for feat in features.values()
                if not feat.get("user_stories")
            ),
            "features_ohne_tasks": sum(
                1 for feat in features.values()
                if not feat.get("tasks")
            ),
            "tasks_ohne_dateien": sum(
                1 for task in tasks.values()
                if not task.get("dateien")
            )
        }

    def generate_traceability_report(self) -> str:
        """
        Generiert einen Traceability-Report als Markdown.

        Returns:
            Formatierter Markdown-String
        """
        report_parts = [
            "# Traceability Report",
            "",
            f"Generiert am: {datetime.now().strftime('%d.%m.%Y %H:%M')}",
            ""
        ]

        report_parts.append("## Zusammenfassung")
        report_parts.append("")
        report_parts.append(f"- **Anforderungen:** {len(self.data['anforderungen'])}")
        report_parts.append(f"- **Features:** {len(self.data['features'])}")
        report_parts.append(f"- **User Stories:** {len(self.data.get('user_stories', []))}")
        report_parts.append(f"- **Tasks:** {len(self.data['tasks'])}")
        report_parts.append(f"- **Generierte Dateien:** {len(self.data['file_generations'])}")

        if self.data["traceability"]:
            coverage = self.data["traceability"].get("coverage", 0)
            report_parts.append(f"- **Coverage:** {coverage:.1%}")
        report_parts.append("")

        if self.data["anforderungen"]:
            report_parts.append("## Anforderungen")
            report_parts.append("")
            for req in self.data["anforderungen"][:10]:
                report_parts.append(
                    f"- **[{req.get('id', 'REQ-???')}]** {req.get('titel', 'Unbenannt')} "
                    f"({req.get('kategorie', 'Unbekannt')}, {req.get('prioritaet', 'mittel')})"
                )
            if len(self.data["anforderungen"]) > 10:
                report_parts.append(f"- ... und {len(self.data['anforderungen']) - 10} weitere")
            report_parts.append("")

        if self.data["features"]:
            report_parts.append("## Features")
            report_parts.append("")
            for feat in self.data["features"][:10]:
                req_refs = ", ".join(feat.get("anforderungen", []))
                report_parts.append(
                    f"- **[{feat.get('id', 'FEAT-???')}]** {feat.get('titel', 'Unbenannt')} "
                    f"(Refs: {req_refs})"
                )
            if len(self.data["features"]) > 10:
                report_parts.append(f"- ... und {len(self.data['features']) - 10} weitere")
            report_parts.append("")

        # AENDERUNG 07.02.2026: User Stories Sektion (Phase 3)
        user_stories = self.data.get("user_stories", [])
        if user_stories:
            report_parts.append("## User Stories")
            report_parts.append("")
            for story in user_stories[:15]:
                us_id = story.get("id", "US-???")
                titel = story.get("titel", "Unbenannt")
                feat_ref = story.get("feature_id", "???")
                report_parts.append(f"- **[{us_id}]** {titel} (Feature: {feat_ref})")
                report_parts.append(
                    f"  GEGEBEN: {story.get('gegeben', '?')} | "
                    f"WENN: {story.get('wenn', '?')} | "
                    f"DANN: {story.get('dann', '?')}"
                )
            if len(user_stories) > 15:
                report_parts.append(f"- ... und {len(user_stories) - 15} weitere")
            report_parts.append("")

        if self.data["file_by_file_plan"]:
            plan = self.data["file_by_file_plan"]
            report_parts.append("## File-by-File Plan")
            report_parts.append("")
            report_parts.append(f"- **Geplante Dateien:** {plan.get('total_files', 0)}")
            for f in plan.get("files", [])[:5]:
                report_parts.append(f"  - `{f.get('path', '?')}`: {f.get('description', '')[:50]}")
            report_parts.append("")

        if self.data["file_generations"]:
            report_parts.append("## Datei-Generierung")
            report_parts.append("")
            success_count = sum(1 for f in self.data["file_generations"] if f.get("success"))
            total_count = len(self.data["file_generations"])
            report_parts.append(f"- **Erfolgreich:** {success_count}/{total_count}")
            failed = [f for f in self.data["file_generations"] if not f.get("success")]
            if failed:
                report_parts.append("- **Fehlgeschlagen:**")
                for f in failed[:5]:
                    report_parts.append(f"  - `{f.get('filepath', '?')}`: {f.get('error', 'Unbekannt')[:50]}")
            report_parts.append("")

        return "\n".join(report_parts)

    def save_traceability_report(self) -> Optional[str]:
        """
        Generiert und speichert den Traceability-Report.

        Returns:
            Pfad zur erstellten Datei oder None bei Fehler
        """
        if not self.project_path:
            return None
        try:
            content = self.generate_traceability_report()
            docs_path = os.path.join(self.project_path, "docs")
            os.makedirs(docs_path, exist_ok=True)
            path = os.path.join(docs_path, "TRACEABILITY.md")
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            return path
        except Exception as e:
            print(f"FEHLER beim Speichern von TRACEABILITY.md: {e}")
            return None
