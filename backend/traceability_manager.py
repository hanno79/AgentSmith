# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 31.01.2026
Version: 1.0
Beschreibung: Traceability Manager - Verwaltet die Rueckverfolgbarkeit von
              Anforderungen ueber Features zu Tasks und Code-Dateien.
              Teil des Dart AI Feature-Ableitung Konzepts.

              Workflow: Anforderung -> Feature -> User Story -> Task -> Datei
              Jede Ebene ist mit der vorherigen verknuepft.

              AENDERUNG 07.02.2026: User Stories (GEGEBEN-WENN-DANN) hinzugefuegt
              (Dart Task zE40HTp29XJn, Feature-Ableitung Konzept v1.0 Phase 3)
"""

import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class TraceabilityManager:
    """
    Verwaltet die Traceability-Matrix zwischen Anforderungen, Features,
    Tasks und Code-Dateien.
    """

    def __init__(self, project_path: str):
        """
        Initialisiert den Traceability Manager.

        Args:
            project_path: Pfad zum Projektverzeichnis
        """
        self.project_path = project_path
        self.matrix_file = os.path.join(project_path, "traceability_matrix.json")

        # Traceability-Struktur
        self.matrix: Dict[str, Any] = {
            "version": "1.0",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "anforderungen": {},  # id -> {titel, kategorie, features: []}
            "features": {},       # id -> {titel, anforderungen: [], user_stories: [], tasks: []}
            # AENDERUNG 07.02.2026: User Stories Ebene (Phase 3)
            "user_stories": {},   # id -> {titel, feature_id, gegeben, wenn, dann, akzeptanzkriterien}
            "tasks": {},          # id -> {titel, features: [], dateien: [], status}
            "dateien": {},        # pfad -> {tasks: [], status, lines}
            "summary": {
                "total_anforderungen": 0,
                "total_features": 0,
                "total_user_stories": 0,
                "total_tasks": 0,
                "total_dateien": 0,
                "coverage": 0.0
            }
        }

        # Lade existierende Matrix falls vorhanden
        self._load()

    def _load(self) -> None:
        """Laedt die Traceability-Matrix aus der Datei."""
        if os.path.exists(self.matrix_file):
            try:
                with open(self.matrix_file, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    self.matrix.update(loaded)
                logger.info(f"Traceability-Matrix geladen: {self.matrix_file}")
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Fehler beim Laden der Traceability-Matrix: {e}")

    def save(self) -> None:
        """Speichert die Traceability-Matrix in die Datei."""
        try:
            self.matrix["updated_at"] = datetime.now().isoformat()
            self._update_summary()

            os.makedirs(os.path.dirname(self.matrix_file), exist_ok=True)
            with open(self.matrix_file, "w", encoding="utf-8") as f:
                json.dump(self.matrix, f, indent=2, ensure_ascii=False)
            logger.info(f"Traceability-Matrix gespeichert: {self.matrix_file}")
        except IOError as e:
            logger.error(f"Fehler beim Speichern der Traceability-Matrix: {e}")

    def _update_summary(self) -> None:
        """Aktualisiert die Zusammenfassung der Matrix."""
        self.matrix["summary"] = {
            "total_anforderungen": len(self.matrix["anforderungen"]),
            "total_features": len(self.matrix["features"]),
            # AENDERUNG 07.02.2026: User Stories zaehlen
            "total_user_stories": len(self.matrix.get("user_stories", {})),
            "total_tasks": len(self.matrix["tasks"]),
            "total_dateien": len(self.matrix["dateien"]),
            "coverage": self._calculate_coverage()
        }

    def _calculate_coverage(self) -> float:
        """
        Berechnet die Abdeckung: Wie viele Anforderungen haben implementierte Dateien?

        Returns:
            Coverage als Prozentwert (0.0 - 1.0)
        """
        if not self.matrix["anforderungen"]:
            return 0.0

        implemented_reqs = 0
        for req_id, req_data in self.matrix["anforderungen"].items():
            # Pruefe ob mindestens ein Feature implementiert ist
            for feat_id in req_data.get("features", []):
                feat = self.matrix["features"].get(feat_id, {})
                for task_id in feat.get("tasks", []):
                    task = self.matrix["tasks"].get(task_id, {})
                    if task.get("status") == "completed":
                        implemented_reqs += 1
                        break
                else:
                    continue
                break

        return implemented_reqs / len(self.matrix["anforderungen"])

    # =========================================================================
    # ANFORDERUNGEN
    # =========================================================================

    def add_anforderung(
        self,
        id: str,
        titel: str,
        kategorie: str = "Funktional",
        prioritaet: str = "mittel",
        quelle: str = None
    ) -> None:
        """
        Fuegt eine Anforderung zur Matrix hinzu.

        Args:
            id: Eindeutige ID (z.B. REQ-001)
            titel: Titel der Anforderung
            kategorie: Kategorie (Funktional, Sicherheit, UI/UX, etc.)
            prioritaet: Prioritaet (hoch, mittel, niedrig)
            quelle: Quelle der Anforderung
        """
        self.matrix["anforderungen"][id] = {
            "titel": titel,
            "kategorie": kategorie,
            "prioritaet": prioritaet,
            "quelle": quelle,
            "features": [],
            "created_at": datetime.now().isoformat()
        }
        logger.debug(f"Anforderung hinzugefuegt: {id} - {titel}")

    def add_anforderungen_from_analyst(self, analyst_output: Dict[str, Any]) -> int:
        """
        Fuegt alle Anforderungen aus dem Analyst-Output hinzu.

        Args:
            analyst_output: Output des Analyst-Agenten

        Returns:
            Anzahl der hinzugefuegten Anforderungen
        """
        count = 0
        for req in analyst_output.get("anforderungen", []):
            self.add_anforderung(
                id=req.get("id", f"REQ-{count + 1:03d}"),
                titel=req.get("titel", "Unbenannt"),
                kategorie=req.get("kategorie", "Funktional"),
                prioritaet=req.get("prioritaet", "mittel"),
                quelle=req.get("quelle")
            )
            count += 1
        logger.info(f"{count} Anforderungen aus Analyst-Output hinzugefuegt")
        return count

    # =========================================================================
    # FEATURES
    # =========================================================================

    def add_feature(
        self,
        id: str,
        titel: str,
        anforderungen: List[str],
        technologie: str = None,
        prioritaet: str = "mittel"
    ) -> None:
        """
        Fuegt ein Feature zur Matrix hinzu und verknuepft es mit Anforderungen.

        Args:
            id: Eindeutige ID (z.B. FEAT-001)
            titel: Titel des Features
            anforderungen: Liste der verknuepften Anforderungs-IDs
            technologie: Verwendete Technologie
            prioritaet: Prioritaet (hoch, mittel, niedrig)
        """
        self.matrix["features"][id] = {
            "titel": titel,
            "anforderungen": anforderungen,
            "technologie": technologie,
            "prioritaet": prioritaet,
            # AENDERUNG 07.02.2026: User Stories pro Feature
            "user_stories": [],
            "tasks": [],
            "created_at": datetime.now().isoformat()
        }

        # Verknuepfe rueckwaerts zu Anforderungen
        for req_id in anforderungen:
            if req_id in self.matrix["anforderungen"]:
                if id not in self.matrix["anforderungen"][req_id]["features"]:
                    self.matrix["anforderungen"][req_id]["features"].append(id)

        logger.debug(f"Feature hinzugefuegt: {id} - {titel}")

    def add_features_from_konzepter(self, konzepter_output: Dict[str, Any]) -> int:
        """
        Fuegt alle Features aus dem Konzepter-Output hinzu.

        Args:
            konzepter_output: Output des Konzepter-Agenten

        Returns:
            Anzahl der hinzugefuegten Features
        """
        count = 0
        for feat in konzepter_output.get("features", []):
            self.add_feature(
                id=feat.get("id", f"FEAT-{count + 1:03d}"),
                titel=feat.get("titel", "Unbenannt"),
                anforderungen=feat.get("anforderungen", []),
                technologie=feat.get("technologie"),
                prioritaet=feat.get("prioritaet", "mittel")
            )
            count += 1
        logger.info(f"{count} Features aus Konzepter-Output hinzugefuegt")
        return count

    # =========================================================================
    # AENDERUNG 07.02.2026: USER STORIES (Phase 3)
    # =========================================================================

    def add_user_story(
        self,
        id: str,
        titel: str,
        feature_id: str,
        gegeben: str = "",
        wenn: str = "",
        dann: str = "",
        akzeptanzkriterien: List[str] = None,
        prioritaet: str = "mittel"
    ) -> None:
        """
        Fuegt eine User Story zur Matrix hinzu.

        Args:
            id: Eindeutige ID (z.B. US-001)
            titel: Titel der User Story
            feature_id: Verknuepftes Feature (z.B. FEAT-001)
            gegeben: GEGEBEN-Klausel (Vorbedingung)
            wenn: WENN-Klausel (Aktion)
            dann: DANN-Klausel (Erwartetes Ergebnis)
            akzeptanzkriterien: Liste der Akzeptanzkriterien
            prioritaet: Prioritaet (hoch, mittel, niedrig)
        """
        if "user_stories" not in self.matrix:
            self.matrix["user_stories"] = {}

        self.matrix["user_stories"][id] = {
            "titel": titel,
            "feature_id": feature_id,
            "gegeben": gegeben,
            "wenn": wenn,
            "dann": dann,
            "akzeptanzkriterien": akzeptanzkriterien or [],
            "prioritaet": prioritaet,
            "created_at": datetime.now().isoformat()
        }

        # Verknuepfe rueckwaerts zu Feature
        if feature_id in self.matrix["features"]:
            us_list = self.matrix["features"][feature_id].setdefault("user_stories", [])
            if id not in us_list:
                us_list.append(id)

        logger.debug(f"User Story hinzugefuegt: {id} - {titel}")

    def add_user_stories_from_konzepter(self, konzepter_output: Dict[str, Any]) -> int:
        """
        Fuegt alle User Stories aus dem Konzepter-Output hinzu.

        Args:
            konzepter_output: Output des Konzepter-Agenten

        Returns:
            Anzahl der hinzugefuegten User Stories
        """
        count = 0
        for story in konzepter_output.get("user_stories", []):
            self.add_user_story(
                id=story.get("id", f"US-{count + 1:03d}"),
                titel=story.get("titel", "Unbenannt"),
                feature_id=story.get("feature_id", ""),
                gegeben=story.get("gegeben", ""),
                wenn=story.get("wenn", ""),
                dann=story.get("dann", ""),
                akzeptanzkriterien=story.get("akzeptanzkriterien", []),
                prioritaet=story.get("prioritaet", "mittel")
            )
            count += 1
        logger.info(f"{count} User Stories aus Konzepter-Output hinzugefuegt")
        return count

    # =========================================================================
    # TASKS
    # =========================================================================

    def add_task(
        self,
        id: str,
        titel: str,
        features: List[str],
        datei: str = None,
        status: str = "pending"
    ) -> None:
        """
        Fuegt einen Task zur Matrix hinzu.

        Args:
            id: Eindeutige ID (z.B. TASK-001)
            titel: Titel des Tasks
            features: Liste der verknuepften Feature-IDs
            datei: Zielpfad der zu erstellenden Datei
            status: Status (pending, in_progress, completed, failed)
        """
        self.matrix["tasks"][id] = {
            "titel": titel,
            "features": features,
            "dateien": [datei] if datei else [],
            "status": status,
            "created_at": datetime.now().isoformat()
        }

        # Verknuepfe rueckwaerts zu Features
        for feat_id in features:
            if feat_id in self.matrix["features"]:
                if id not in self.matrix["features"][feat_id]["tasks"]:
                    self.matrix["features"][feat_id]["tasks"].append(id)

        logger.debug(f"Task hinzugefuegt: {id} - {titel}")

    def add_tasks_from_planner(self, planner_output: Dict[str, Any]) -> int:
        """
        Fuegt alle Tasks aus dem Planner-Output hinzu.

        Args:
            planner_output: Output des Planner-Agenten

        Returns:
            Anzahl der hinzugefuegten Tasks
        """
        count = 0
        for i, file_info in enumerate(planner_output.get("files", []), 1):
            task_id = f"TASK-{i:03d}"

            # Versuche Feature-Zuordnung aus Beschreibung oder Fallback
            features = file_info.get("features", [])
            if not features:
                # Fallback: Nutze alle Features
                features = list(self.matrix["features"].keys())[:1]

            self.add_task(
                id=task_id,
                titel=file_info.get("description", f"Erstelle {file_info.get('path', 'Datei')}"),
                features=features,
                datei=file_info.get("path"),
                status="pending"
            )
            count += 1
        logger.info(f"{count} Tasks aus Planner-Output hinzugefuegt")
        return count

    def update_task_status(self, task_id: str, status: str) -> None:
        """
        Aktualisiert den Status eines Tasks.

        Args:
            task_id: ID des Tasks
            status: Neuer Status (pending, in_progress, completed, failed)
        """
        if task_id in self.matrix["tasks"]:
            self.matrix["tasks"][task_id]["status"] = status
            self.matrix["tasks"][task_id]["updated_at"] = datetime.now().isoformat()
            logger.debug(f"Task {task_id} Status: {status}")

    # =========================================================================
    # DATEIEN
    # =========================================================================

    def add_datei(
        self,
        pfad: str,
        tasks: List[str],
        status: str = "created",
        lines: int = 0
    ) -> None:
        """
        Fuegt eine erstellte Datei zur Matrix hinzu.

        Args:
            pfad: Relativer Pfad der Datei
            tasks: Liste der verknuepften Task-IDs
            status: Status (created, modified, deleted)
            lines: Anzahl der Zeilen
        """
        self.matrix["dateien"][pfad] = {
            "tasks": tasks,
            "status": status,
            "lines": lines,
            "created_at": datetime.now().isoformat()
        }

        # Verknuepfe rueckwaerts zu Tasks
        for task_id in tasks:
            if task_id in self.matrix["tasks"]:
                if pfad not in self.matrix["tasks"][task_id]["dateien"]:
                    self.matrix["tasks"][task_id]["dateien"].append(pfad)

        logger.debug(f"Datei hinzugefuegt: {pfad}")

    def mark_datei_completed(self, pfad: str, lines: int = 0) -> None:
        """
        Markiert eine Datei als erfolgreich erstellt.

        Args:
            pfad: Pfad der Datei
            lines: Anzahl der Zeilen
        """
        if pfad in self.matrix["dateien"]:
            self.matrix["dateien"][pfad]["status"] = "completed"
            self.matrix["dateien"][pfad]["lines"] = lines
            self.matrix["dateien"][pfad]["completed_at"] = datetime.now().isoformat()

            # Pruefe ob alle Dateien des Tasks fertig sind
            for task_id in self.matrix["dateien"][pfad].get("tasks", []):
                self._check_task_completion(task_id)

    def _check_task_completion(self, task_id: str) -> None:
        """Prueft ob alle Dateien eines Tasks fertig sind."""
        if task_id not in self.matrix["tasks"]:
            return

        task = self.matrix["tasks"][task_id]
        all_completed = True

        for datei_pfad in task.get("dateien", []):
            datei = self.matrix["dateien"].get(datei_pfad, {})
            if datei.get("status") != "completed":
                all_completed = False
                break

        if all_completed and task.get("dateien"):
            self.update_task_status(task_id, "completed")

    # =========================================================================
    # REPORTS
    # =========================================================================

    def get_traceability_report(self) -> Dict[str, Any]:
        """
        Generiert einen vollstaendigen Traceability-Report.

        Returns:
            Report mit Coverage, Gaps und Details
        """
        report = {
            "generated_at": datetime.now().isoformat(),
            "summary": self.matrix["summary"],
            "coverage_details": {
                "anforderungen": self._get_requirement_coverage(),
                "features": self._get_feature_coverage(),
                "tasks": self._get_task_coverage()
            },
            "gaps": self._find_gaps(),
            "statistics": self._get_statistics()
        }

        return report

    def _get_requirement_coverage(self) -> List[Dict[str, Any]]:
        """Gibt Coverage-Details fuer alle Anforderungen."""
        result = []
        for req_id, req in self.matrix["anforderungen"].items():
            features = req.get("features", [])
            implemented_features = 0

            for feat_id in features:
                feat = self.matrix["features"].get(feat_id, {})
                tasks = feat.get("tasks", [])
                completed_tasks = sum(
                    1 for t_id in tasks
                    if self.matrix["tasks"].get(t_id, {}).get("status") == "completed"
                )
                if completed_tasks > 0:
                    implemented_features += 1

            result.append({
                "id": req_id,
                "titel": req.get("titel"),
                "total_features": len(features),
                "implemented_features": implemented_features,
                "coverage": implemented_features / len(features) if features else 0
            })

        return result

    def _get_feature_coverage(self) -> List[Dict[str, Any]]:
        """Gibt Coverage-Details fuer alle Features."""
        result = []
        for feat_id, feat in self.matrix["features"].items():
            tasks = feat.get("tasks", [])
            completed = sum(
                1 for t_id in tasks
                if self.matrix["tasks"].get(t_id, {}).get("status") == "completed"
            )

            result.append({
                "id": feat_id,
                "titel": feat.get("titel"),
                "total_tasks": len(tasks),
                "completed_tasks": completed,
                "coverage": completed / len(tasks) if tasks else 0
            })

        return result

    def _get_task_coverage(self) -> Dict[str, int]:
        """Gibt Task-Status-Verteilung."""
        status_counts = {"pending": 0, "in_progress": 0, "completed": 0, "failed": 0}
        for task in self.matrix["tasks"].values():
            status = task.get("status", "pending")
            if status in status_counts:
                status_counts[status] += 1
        return status_counts

    def _find_gaps(self) -> Dict[str, List[str]]:
        """Findet Luecken in der Traceability."""
        gaps = {
            "anforderungen_ohne_features": [],
            # AENDERUNG 07.02.2026: User Story Luecken erkennen
            "features_ohne_user_stories": [],
            "features_ohne_tasks": [],
            "tasks_ohne_dateien": [],
            "orphan_dateien": []
        }

        # Anforderungen ohne Features
        for req_id, req in self.matrix["anforderungen"].items():
            if not req.get("features"):
                gaps["anforderungen_ohne_features"].append(req_id)

        # Features ohne User Stories
        for feat_id, feat in self.matrix["features"].items():
            if not feat.get("user_stories"):
                gaps["features_ohne_user_stories"].append(feat_id)

        # Features ohne Tasks
        for feat_id, feat in self.matrix["features"].items():
            if not feat.get("tasks"):
                gaps["features_ohne_tasks"].append(feat_id)

        # Tasks ohne Dateien
        for task_id, task in self.matrix["tasks"].items():
            if not task.get("dateien"):
                gaps["tasks_ohne_dateien"].append(task_id)

        # Orphan Dateien (nicht mit Tasks verknuepft)
        for datei_pfad, datei in self.matrix["dateien"].items():
            if not datei.get("tasks"):
                gaps["orphan_dateien"].append(datei_pfad)

        return gaps

    def _get_statistics(self) -> Dict[str, Any]:
        """Berechnet Statistiken ueber die Matrix."""
        total_lines = sum(
            d.get("lines", 0)
            for d in self.matrix["dateien"].values()
        )

        return {
            "total_lines_of_code": total_lines,
            "avg_lines_per_file": total_lines / len(self.matrix["dateien"]) if self.matrix["dateien"] else 0,
            "files_per_task": len(self.matrix["dateien"]) / len(self.matrix["tasks"]) if self.matrix["tasks"] else 0,
            "tasks_per_feature": len(self.matrix["tasks"]) / len(self.matrix["features"]) if self.matrix["features"] else 0
        }

    def get_matrix(self) -> Dict[str, Any]:
        """Gibt die komplette Matrix zurueck."""
        return self.matrix

    def reset(self) -> None:
        """Setzt die Matrix zurueck."""
        self.matrix = {
            "version": "1.0",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "anforderungen": {},
            "features": {},
            # AENDERUNG 07.02.2026: User Stories in Reset
            "user_stories": {},
            "tasks": {},
            "dateien": {},
            "summary": {
                "total_anforderungen": 0,
                "total_features": 0,
                "total_user_stories": 0,
                "total_tasks": 0,
                "total_dateien": 0,
                "coverage": 0.0
            }
        }
        logger.info("Traceability-Matrix zurueckgesetzt")
