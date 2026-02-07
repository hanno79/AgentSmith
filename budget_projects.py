# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 01.02.2026
Version: 1.0
Beschreibung: Budget-Projekt-Management.
              Extrahiert aus budget_tracker.py (Regel 1: Max 500 Zeilen)
"""

import logging
from pathlib import Path
from typing import Dict, List, Any, Optional

from budget_config import ProjectBudget, UsageRecord
from budget_persistence import save_projects

logging.basicConfig(
    format="[%(asctime)s] [%(levelname)s] [%(funcName)s] - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def create_project(
    projects: Dict[str, ProjectBudget],
    projects_file: Path,
    project_id: str,
    name: str,
    budget: float
) -> ProjectBudget:
    """
    Erstellt ein neues Projekt mit eigenem Budget.

    Args:
        projects: Dictionary mit existierenden Projekten
        projects_file: Pfad zur Projects-Datei
        project_id: Eindeutige Projekt-ID
        name: Anzeigename
        budget: Budget in USD

    Returns:
        Das erstellte Projekt

    Raises:
        ValueError: Wenn Projekt mit dieser ID bereits existiert
        RuntimeError: Wenn Speichern fehlschlägt
    """
    if project_id in projects:
        logger.error("Projekt mit ID %s existiert bereits", project_id)
        raise ValueError("Projekt mit dieser ID existiert bereits")
    project = ProjectBudget(
        project_id=project_id,
        name=name,
        total_budget=budget
    )
    projects[project_id] = project
    try:
        save_projects(projects, projects_file)
    except Exception as e:
        logger.critical("Fehler beim Speichern der Projekte: %s", e)
        raise RuntimeError("Fehler beim Speichern der Projekte") from e
    return project


def get_project(projects: Dict[str, ProjectBudget], project_id: str) -> Optional[ProjectBudget]:
    """
    Gibt ein Projekt zurück.

    Args:
        projects: Dictionary mit Projekten
        project_id: Projekt-ID

    Returns:
        Projekt oder None
    """
    return projects.get(project_id)


def get_all_projects(
    projects: Dict[str, ProjectBudget],
    usage_history: List[UsageRecord]
) -> List[Dict[str, Any]]:
    """
    Gibt alle Projekte mit aktuellen Kosten zurück.

    Args:
        projects: Dictionary mit Projekten
        usage_history: Nutzungshistorie

    Returns:
        Liste mit Projekt-Details
    """
    result = []
    for project in projects.values():
        # Berechne aktuelle Kosten
        project_costs = sum(
            r.cost_usd for r in usage_history
            if r.project_id == project.project_id
        )

        result.append({
            "project_id": project.project_id,
            "name": project.name,
            "total_budget": project.total_budget,
            "spent": round(project_costs, 2),
            "remaining": round(project.total_budget - project_costs, 2),
            "percentage_used": round((project_costs / project.total_budget) * 100, 1) if project.total_budget > 0 else 0,
            "created_at": project.created_at
        })

    return result


def delete_project(
    projects: Dict[str, ProjectBudget],
    projects_file: Path,
    project_id: str
) -> bool:
    """
    Löscht ein Projekt.

    Args:
        projects: Dictionary mit Projekten
        projects_file: Pfad zur Projects-Datei
        project_id: Projekt-ID

    Returns:
        True wenn gelöscht, False wenn nicht gefunden
    """
    if project_id in projects:
        del projects[project_id]
        save_projects(projects, projects_file)
        return True
    return False


def update_project_costs(
    projects: Dict[str, ProjectBudget],
    projects_file: Path,
    project_id: str,
    cost: float
) -> None:
    """
    Aktualisiert die Kosten eines Projekts.

    Args:
        projects: Dictionary mit Projekten
        projects_file: Pfad zur Projects-Datei
        project_id: Projekt-ID
        cost: Kosten die addiert werden sollen
    """
    if project_id not in projects:
        logger.error("Projekt %s nicht gefunden – Kosten nicht aktualisiert", project_id)
        return
    projects[project_id].spent += cost
    save_projects(projects, projects_file)

