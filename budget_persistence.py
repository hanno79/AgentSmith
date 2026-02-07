# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 01.02.2026
Version: 1.0
Beschreibung: Budget-Persistenz - Laden und Speichern von Budget-Daten.
              Extrahiert aus budget_tracker.py (Regel 1: Max 500 Zeilen)
"""

import json
import logging
from pathlib import Path
from typing import Dict, List
from dataclasses import asdict

from budget_config import UsageRecord, BudgetConfig, ProjectBudget

logger = logging.getLogger(__name__)


def load_usage_history(usage_file: Path) -> List[UsageRecord]:
    """
    Lädt Nutzungshistorie aus Datei.

    Args:
        usage_file: Pfad zur Usage-Datei

    Returns:
        Liste von UsageRecords
    """
    if usage_file.exists():
        try:
            with open(usage_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return [UsageRecord(**record) for record in data]
        except Exception as e:
            logger.warning(f"Fehler beim Laden der Usage History: {e}")
    return []


def save_usage_history(usage_history: List[UsageRecord], usage_file: Path) -> bool:
    """
    Speichert Nutzungshistorie in Datei.

    Args:
        usage_history: Liste der UsageRecords
        usage_file: Pfad zur Usage-Datei

    Returns:
        True bei Erfolg, False bei Fehler
    """
    try:
        with open(usage_file, "w", encoding="utf-8") as f:
            json.dump([asdict(r) for r in usage_history], f, indent=2)
        return True
    except (OSError, IOError, TypeError, ValueError) as e:
        logger.error(f"Fehler beim Speichern der Usage History: {e}. Datei: {usage_file}")
        return False


def load_config(config_file: Path) -> BudgetConfig:
    """
    Lädt Budget-Konfiguration aus Datei.

    Args:
        config_file: Pfad zur Config-Datei

    Returns:
        BudgetConfig Objekt
    """
    if config_file.exists():
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return BudgetConfig(**data)
        except Exception as e:
            logger.warning(f"Fehler beim Laden der Config: {e}")
    return BudgetConfig()


def save_config(config: BudgetConfig, config_file: Path) -> bool:
    """
    Speichert Budget-Konfiguration in Datei.

    Args:
        config: BudgetConfig Objekt
        config_file: Pfad zur Config-Datei

    Returns:
        True bei Erfolg, False bei Fehler
    """
    try:
        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(asdict(config), f, indent=2)
        return True
    except (OSError, IOError) as e:
        logger.error(f"Fehler beim Speichern der Config: {e}")
        return False


def load_projects(projects_file: Path) -> Dict[str, ProjectBudget]:
    """
    Lädt Projekte aus Datei.

    Args:
        projects_file: Pfad zur Projects-Datei

    Returns:
        Dictionary mit Projekten
    """
    if projects_file.exists():
        try:
            with open(projects_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return {k: ProjectBudget(**v) for k, v in data.items()}
        except Exception as e:
            logger.warning(f"Fehler beim Laden der Projekte: {e}")
    return {}


def save_projects(projects: Dict[str, ProjectBudget], projects_file: Path) -> bool:
    """
    Speichert Projekte in Datei.

    Args:
        projects: Dictionary mit Projekten
        projects_file: Pfad zur Projects-Datei

    Returns:
        True bei Erfolg, False bei Fehler
    """
    try:
        with open(projects_file, "w", encoding="utf-8") as f:
            json.dump({k: asdict(v) for k, v in projects.items()}, f, indent=2)
        return True
    except (OSError, IOError) as e:
        logger.error(f"Fehler beim Speichern der Projekte: {e}")
        return False
