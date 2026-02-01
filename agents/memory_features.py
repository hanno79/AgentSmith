# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 01.02.2026
Version: 1.0
Beschreibung: Memory Agent Feature-Derivation und Session Recording.
              Extrahiert aus memory_agent.py (Regel 1: Max 500 Zeilen)

              Enthält:
              - record_feature_derivation
              - record_file_by_file_session
              - record_file_by_file_session_async
              - _create_traceability_sample
              - _learn_from_feature_patterns
              - _record_file_generation_failure
"""

import os
import asyncio
from datetime import datetime
from typing import Any, Dict, List

from agents.memory_core import load_memory, save_memory


def record_feature_derivation(
    memory_path: str,
    anforderungen: List[Dict[str, Any]],
    features: List[Dict[str, Any]],
    tasks: List[Dict[str, Any]],
    success: bool
) -> str:
    """
    Speichert eine Feature-Ableitungs-Session im Memory.
    """
    try:
        memory_data = load_memory(memory_path)

        # Erstelle Feature-Derivation Eintrag
        derivation_entry = {
            "type": "feature_derivation",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "success": success,
            "statistics": {
                "anforderungen_count": len(anforderungen),
                "features_count": len(features),
                "tasks_count": len(tasks),
                "avg_features_per_req": len(features) / len(anforderungen) if anforderungen else 0,
                "avg_tasks_per_feature": len(tasks) / len(features) if features else 0
            },
            "traceability_sample": _create_traceability_sample(anforderungen, features, tasks)
        }

        # Speichere in history
        memory_data["history"].append(derivation_entry)

        # Lerne aus erfolgreichen Mustern
        if success and features:
            _learn_from_feature_patterns(memory_data, features)

        save_memory(memory_path, memory_data)
        return f"Feature-Derivation gespeichert: {len(anforderungen)} REQs -> {len(features)} FEATs -> {len(tasks)} TASKs"

    except Exception as e:
        return f"Fehler beim Speichern der Feature-Derivation: {e}"


def _create_traceability_sample(
    anforderungen: List[Dict[str, Any]],
    features: List[Dict[str, Any]],
    tasks: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Erstellt eine Beispiel-Traceability fuer das Memory.
    """
    sample = {
        "req_to_feat": {},
        "feat_to_task": {}
    }

    # Mappe REQ -> FEAT (nur erste 5)
    for feat in features[:5]:
        for req_id in feat.get("anforderungen", []):
            if req_id not in sample["req_to_feat"]:
                sample["req_to_feat"][req_id] = []
            sample["req_to_feat"][req_id].append(feat.get("id", "FEAT-???"))

    # Mappe FEAT -> TASK (nur erste 5)
    for task in tasks[:5]:
        for feat_id in task.get("features", []):
            if feat_id not in sample["feat_to_task"]:
                sample["feat_to_task"][feat_id] = []
            sample["feat_to_task"][feat_id].append(task.get("id", "TASK-???"))

    return sample


def _learn_from_feature_patterns(
    memory_data: Dict[str, Any],
    features: List[Dict[str, Any]]
) -> None:
    """
    Lernt Muster aus erfolgreichen Feature-Definitionen.
    """
    # Analysiere Technologie-Verteilung
    tech_counts = {}
    for feat in features:
        tech = feat.get("technologie", "unknown")
        tech_counts[tech] = tech_counts.get(tech, 0) + 1

    # Finde dominante Technologie
    if tech_counts:
        dominant_tech = max(tech_counts, key=tech_counts.get)
        ratio = tech_counts[dominant_tech] / len(features)

        if ratio > 0.7:
            # Lerne: Dieses Projekt nutzt hauptsaechlich diese Technologie
            lesson = {
                "pattern": f"project_tech_{dominant_tech}",
                "category": "architecture",
                "action": f"Dieses Projekt verwendet hauptsaechlich {dominant_tech} ({ratio:.0%} der Features).",
                "tags": ["global", dominant_tech.lower()],
                "count": 1,
                "first_seen": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "last_seen": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }

            # Nur hinzufuegen wenn nicht bereits vorhanden
            existing_patterns = [l.get("pattern") for l in memory_data.get("lessons", [])]
            if lesson["pattern"] not in existing_patterns:
                if "lessons" not in memory_data:
                    memory_data["lessons"] = []
                memory_data["lessons"].append(lesson)


def record_file_by_file_session(
    memory_path: str,
    plan: Dict[str, Any],
    created_files: List[str],
    failed_files: List[str],
    success: bool
) -> str:
    """
    Speichert eine File-by-File Session im Memory.
    """
    try:
        memory_data = load_memory(memory_path)

        planned_files = plan.get("files", [])
        total_planned = len(planned_files)

        session_entry = {
            "type": "file_by_file_session",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "success": success,
            "statistics": {
                "planned_files": total_planned,
                "created_files": len(created_files),
                "failed_files": len(failed_files),
                "success_rate": len(created_files) / total_planned if total_planned > 0 else 0
            },
            "created": created_files[:10],  # Nur erste 10 speichern
            "failed": failed_files[:5] if failed_files else []
        }

        memory_data["history"].append(session_entry)

        # Lerne aus Fehlern
        if failed_files:
            for failed_file in failed_files[:3]:
                _record_file_generation_failure(memory_data, failed_file)

        save_memory(memory_path, memory_data)
        return f"File-by-File Session gespeichert: {len(created_files)}/{total_planned} erfolgreich"

    except Exception as e:
        return f"Fehler beim Speichern der File-by-File Session: {e}"


def _record_file_generation_failure(memory_data: Dict[str, Any], failed_file: str) -> None:
    """
    Lernt aus fehlgeschlagenen Datei-Generierungen.
    """
    # Extrahiere Datei-Typ
    raw_ext = os.path.splitext(failed_file)[1].lower()
    ext = raw_ext if raw_ext else ".noext"
    tag = ext.replace(".", "")
    pattern = f"file_generation_failed_{tag}"
    action_ext_label = "ohne Extension" if not raw_ext else ext

    # Suche existierende Lesson
    for lesson in memory_data.get("lessons", []):
        if lesson.get("pattern") == pattern:
            lesson["count"] = lesson.get("count", 0) + 1
            lesson["last_seen"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            return

    # Neue Lesson erstellen
    lesson = {
        "pattern": pattern,
        "category": "file_generation",
        "action": f"Dateien {action_ext_label} haben oefter Generierungsprobleme. Mehr Kontext bereitstellen.",
        "tags": ["global", "file_generation", tag],
        "count": 1,
        "first_seen": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "last_seen": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    if "lessons" not in memory_data:
        memory_data["lessons"] = []
    memory_data["lessons"].append(lesson)


async def record_file_by_file_session_async(
    memory_path: str,
    plan: Dict[str, Any],
    created_files: List[str],
    failed_files: List[str],
    success: bool
) -> str:
    """
    Async-Version von record_file_by_file_session.
    """
    def _blocking_record():
        return record_file_by_file_session(
            memory_path, plan, created_files, failed_files, success
        )

    return await asyncio.to_thread(_blocking_record)


# AENDERUNG 01.02.2026: UTDS Task-Derivation Recording
def record_task_derivation(
    memory_path: str,
    derivation_result: Dict[str, Any],
    success: bool = True
) -> str:
    """
    Speichert eine UTDS Task-Derivation Session im Memory.

    Args:
        memory_path: Pfad zur Memory-Datei
        derivation_result: TaskDerivationResult als Dict (via to_dict())
        success: Ob die Derivation erfolgreich war

    Returns:
        Status-Nachricht
    """
    try:
        memory_data = load_memory(memory_path)

        # Task-Derivation Eintrag erstellen
        entry = {
            "type": "task_derivation",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "source": derivation_result.get("source", "unknown"),
            "success": success,
            "statistics": {
                "total_tasks": derivation_result.get("total_tasks", 0),
                "tasks_by_category": derivation_result.get("tasks_by_category", {}),
                "tasks_by_priority": derivation_result.get("tasks_by_priority", {}),
                "tasks_by_agent": derivation_result.get("tasks_by_agent", {}),
                "derivation_time": derivation_result.get("derivation_time_seconds", 0)
            },
            "sample_tasks": []
        }

        # Sample Tasks speichern (max 3)
        tasks = derivation_result.get("tasks", [])
        for task in tasks[:3]:
            if isinstance(task, dict):
                entry["sample_tasks"].append({
                    "id": task.get("id", ""),
                    "title": task.get("title", "")[:50],
                    "category": task.get("category", ""),
                    "priority": task.get("priority", ""),
                    "target_agent": task.get("target_agent", "")
                })

        # In History speichern
        memory_data["history"].append(entry)

        # Lerne aus Task-Patterns
        if success and tasks:
            _learn_from_task_patterns(memory_data, tasks)

        save_memory(memory_path, memory_data)

        return f"Task-Derivation gespeichert: {entry['statistics']['total_tasks']} Tasks aus {entry['source']}"

    except Exception as e:
        return f"Fehler beim Speichern der Task-Derivation: {e}"


def _learn_from_task_patterns(memory_data: Dict[str, Any], tasks: List[Dict[str, Any]]) -> None:
    """
    Extrahiert Lern-Muster aus erfolgreichen Task-Ableitungen.

    Beispiel-Patterns:
    - "security_issues_need_review": Security-Tasks brauchen oft Review
    - "test_tasks_follow_code": Test-Tasks folgen Code-Aenderungen
    """
    if not tasks or len(tasks) < 2:
        return

    # Zaehle Kategorien
    category_counts = {}
    priority_counts = {}
    agent_counts = {}

    for task in tasks:
        if isinstance(task, dict):
            cat = task.get("category", "unknown")
            prio = task.get("priority", "unknown")
            agent = task.get("target_agent", "unknown")

            category_counts[cat] = category_counts.get(cat, 0) + 1
            priority_counts[prio] = priority_counts.get(prio, 0) + 1
            agent_counts[agent] = agent_counts.get(agent, 0) + 1

    total = len(tasks)

    # Lerne dominante Kategorie
    for cat, count in category_counts.items():
        ratio = count / total
        if ratio >= 0.7:  # 70%+ sind eine Kategorie
            pattern = f"task_derivation_dominant_{cat}"
            _add_or_update_lesson(
                memory_data,
                pattern=pattern,
                category="task_derivation",
                action=f"Die meisten Tasks ({ratio:.0%}) sind {cat}-Tasks. "
                       f"Fokus auf {cat}-Agenten legen.",
                tags=["global", "task_derivation", cat]
            )

    # Lerne wenn viele Critical-Tasks
    critical_count = priority_counts.get("critical", 0)
    if critical_count >= 2 or (total > 0 and critical_count / total >= 0.5):
        _add_or_update_lesson(
            memory_data,
            pattern="task_derivation_many_critical",
            category="task_derivation",
            action="Viele kritische Tasks erkannt. "
                   "Priorisierung und sequenzielle Verarbeitung empfohlen.",
            tags=["global", "task_derivation", "critical"]
        )


def _add_or_update_lesson(
    memory_data: Dict[str, Any],
    pattern: str,
    category: str,
    action: str,
    tags: List[str]
) -> None:
    """Fuegt eine Lesson hinzu oder aktualisiert sie."""
    if "lessons" not in memory_data:
        memory_data["lessons"] = []

    # Suche existierende Lesson
    for lesson in memory_data["lessons"]:
        if lesson.get("pattern") == pattern:
            lesson["count"] = lesson.get("count", 0) + 1
            lesson["last_seen"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            return

    # Neue Lesson erstellen
    memory_data["lessons"].append({
        "pattern": pattern,
        "category": category,
        "action": action,
        "tags": tags,
        "count": 1,
        "first_seen": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "last_seen": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
