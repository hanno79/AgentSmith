# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 01.02.2026
Version: 1.0
Beschreibung: Service für Projektbericht-Datensammlung.
              Sammelt Metriken, Fehler, Agent-Nutzung und generiert Reports.
"""

import os
import json
from datetime import datetime
from typing import Dict, List, Any, Optional


class ReporterService:
    """
    Service zum Sammeln und Generieren von Projektberichten.

    Sammelt während der Projektausführung:
    - Fortschritts-Metriken (Anforderungen, Features, Tasks, Dateien)
    - Fehler und deren Kontext
    - Agent-Nutzungsdaten (Aufrufe, Tokens, Kosten)
    - Meilensteine und deren Status
    """

    def __init__(self, project_path: Optional[str] = None):
        """
        Initialisiert den Reporter Service.

        Args:
            project_path: Pfad zum Projekt-Verzeichnis für Report-Speicherung
        """
        self.project_path = project_path
        self.data = {
            "project_name": "",
            "goal": "",
            "start_date": datetime.now().isoformat(),
            "end_date": None,
            "anforderungen_count": 0,
            "features_count": 0,
            "tasks_count": 0,
            "files_count": 0,
            "tests_passed": 0,
            "tests_total": 0,
            "coverage": 0.0,
            "iterations_count": 0,
            "errors": [],
            "agent_usage": {},
            "total_cost": 0.0,
            "cost_per_iteration": 0.0,
            "milestones": [],
            "recommendations": []
        }

    # =========================================================================
    # Sammel-Methoden
    # =========================================================================

    def collect_project_info(self, name: str, goal: str) -> None:
        """
        Sammelt Projekt-Grundinformationen.

        Args:
            name: Projektname
            goal: Projektziel
        """
        self.data["project_name"] = name
        self.data["goal"] = goal

    def collect_counts(
        self,
        anforderungen: int = 0,
        features: int = 0,
        tasks: int = 0,
        files: int = 0
    ) -> None:
        """
        Sammelt Anzahl-Metriken.

        Args:
            anforderungen: Anzahl Anforderungen
            features: Anzahl Features
            tasks: Anzahl Tasks
            files: Anzahl generierte Dateien
        """
        self.data["anforderungen_count"] = anforderungen
        self.data["features_count"] = features
        self.data["tasks_count"] = tasks
        self.data["files_count"] = files

    def collect_test_results(self, passed: int, total: int) -> None:
        """
        Sammelt Test-Ergebnisse.

        Args:
            passed: Anzahl bestandene Tests
            total: Gesamtanzahl Tests
        """
        self.data["tests_passed"] = passed
        self.data["tests_total"] = total
        self.data["coverage"] = passed / total if total > 0 else 0.0

    def collect_iteration(self, iteration: int) -> None:
        """
        Aktualisiert Iterations-Zähler.

        Args:
            iteration: Aktuelle Iterationsnummer
        """
        self.data["iterations_count"] = iteration

    def collect_error(
        self,
        error_type: str,
        message: str,
        agent: str = "",
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Sammelt einen Fehler.

        Args:
            error_type: Typ des Fehlers (z.B. "SyntaxError", "ValidationError")
            message: Fehlermeldung
            agent: Agent der den Fehler verursacht hat
            details: Optional zusätzliche Details
        """
        self.data["errors"].append({
            "type": error_type,
            "message": message,
            "agent": agent,
            "details": details or {},
            "timestamp": datetime.now().isoformat()
        })

    def collect_agent_usage(
        self,
        agent: str,
        tokens: int,
        cost: float,
        success: bool = True
    ) -> None:
        """
        Sammelt Agent-Nutzungsdaten.

        Args:
            agent: Name des Agenten
            tokens: Verbrauchte Tokens
            cost: Kosten in USD
            success: Ob der Aufruf erfolgreich war
        """
        if agent not in self.data["agent_usage"]:
            self.data["agent_usage"][agent] = {
                "calls": 0,
                "tokens": 0,
                "cost": 0.0,
                "success_count": 0,
                "error_count": 0
            }

        self.data["agent_usage"][agent]["calls"] += 1
        self.data["agent_usage"][agent]["tokens"] += tokens
        self.data["agent_usage"][agent]["cost"] += cost

        if success:
            self.data["agent_usage"][agent]["success_count"] += 1
        else:
            self.data["agent_usage"][agent]["error_count"] += 1

        self.data["total_cost"] += cost

    def collect_milestone(self, name: str, status: str) -> None:
        """
        Sammelt Meilenstein-Status.

        Args:
            name: Name des Meilensteins
            status: Status ("pending", "in_progress", "completed", "blocked")
        """
        # Prüfe ob Meilenstein bereits existiert
        for ms in self.data["milestones"]:
            if ms["name"] == name:
                ms["status"] = status
                ms["updated_at"] = datetime.now().isoformat()
                return

        # Neuer Meilenstein
        self.data["milestones"].append({
            "name": name,
            "status": status,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        })

    def add_recommendation(
        self,
        recommendation: str,
        priority: str = "medium",
        category: str = "general"
    ) -> None:
        """
        Fügt eine Empfehlung hinzu.

        Args:
            recommendation: Text der Empfehlung
            priority: Priorität ("low", "medium", "high", "critical")
            category: Kategorie ("performance", "security", "architecture", "general")
        """
        self.data["recommendations"].append({
            "text": recommendation,
            "priority": priority,
            "category": category,
            "timestamp": datetime.now().isoformat()
        })

    # =========================================================================
    # Generierungs-Methoden
    # =========================================================================

    def get_report_data(self) -> Dict[str, Any]:
        """
        Gibt alle gesammelten Daten für den Reporter-Agent zurück.

        Returns:
            Dict mit allen Report-Daten
        """
        self.data["end_date"] = datetime.now().isoformat()

        # Kosten pro Iteration berechnen
        if self.data["iterations_count"] > 0:
            self.data["cost_per_iteration"] = (
                self.data["total_cost"] / self.data["iterations_count"]
            )

        return self.data

    def generate_summary(self) -> str:
        """
        Generiert eine kurze Zusammenfassung.

        Returns:
            Zusammenfassungstext
        """
        d = self.data
        success_rate = d["tests_passed"] / d["tests_total"] if d["tests_total"] > 0 else 0

        return (
            f"Projekt '{d['project_name']}' mit {d['anforderungen_count']} Anforderungen, "
            f"{d['features_count']} Features und {d['tasks_count']} Tasks. "
            f"{d['files_count']} Dateien generiert. "
            f"Tests: {d['tests_passed']}/{d['tests_total']} ({success_rate:.0%}). "
            f"Kosten: ${d['total_cost']:.4f} in {d['iterations_count']} Iterationen."
        )

    def get_error_summary(self) -> Dict[str, int]:
        """
        Gibt eine Zusammenfassung der Fehler nach Typ zurück.

        Returns:
            Dict mit Fehlertypen und Anzahl
        """
        summary = {}
        for err in self.data["errors"]:
            err_type = err.get("type", "Unknown")
            summary[err_type] = summary.get(err_type, 0) + 1
        return summary

    def get_agent_performance(self) -> List[Dict[str, Any]]:
        """
        Gibt Agent-Performance-Daten sortiert nach Kosten zurück.

        Returns:
            Liste der Agenten mit Performance-Daten
        """
        result = []
        for agent, data in self.data["agent_usage"].items():
            total_calls = data["calls"]
            success_rate = (
                data["success_count"] / total_calls if total_calls > 0 else 0
            )
            result.append({
                "agent": agent,
                "calls": total_calls,
                "tokens": data["tokens"],
                "cost": data["cost"],
                "success_rate": success_rate
            })

        # Nach Kosten sortieren (absteigend)
        return sorted(result, key=lambda x: x["cost"], reverse=True)

    # =========================================================================
    # Speicher-Methoden
    # =========================================================================

    def save_report(
        self,
        content: str,
        filename: str = "PROJECT_REPORT.md"
    ) -> Optional[str]:
        """
        Speichert den generierten Bericht.

        Args:
            content: Markdown-Inhalt des Reports
            filename: Dateiname für den Report

        Returns:
            Pfad zur gespeicherten Datei oder None
        """
        if not self.project_path:
            return None
        try:
            docs_path = os.path.join(self.project_path, "docs")
            os.makedirs(docs_path, exist_ok=True)
            filepath = os.path.join(docs_path, filename)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            return filepath
        except (OSError, IOError) as e:
            self.logger.error("Fehler beim Speichern des Berichts: %s", e)
            return None

    def save_data(self, filename: str = "report_data.json") -> Optional[str]:
        """
        Speichert die Rohdaten als JSON.

        Args:
            filename: Dateiname für die JSON-Datei

        Returns:
            Pfad zur gespeicherten Datei oder None
        """
        if not self.project_path:
            return None
        try:
            docs_path = os.path.join(self.project_path, "docs")
            os.makedirs(docs_path, exist_ok=True)
            filepath = os.path.join(docs_path, filename)
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(self.get_report_data(), f, ensure_ascii=False, indent=2)
            return filepath
        except (OSError, IOError, ValueError, TypeError) as e:
            self.logger.error("Fehler beim Speichern der Report-Daten: %s", e)
            return None

    def export_to_json(self) -> str:
        """
        Exportiert alle Daten als JSON-String.

        Returns:
            JSON-String mit allen Daten
        """
        return json.dumps(self.get_report_data(), ensure_ascii=False, indent=2)
