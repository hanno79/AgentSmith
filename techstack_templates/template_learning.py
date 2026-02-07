# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 07.02.2026
Version: 1.0
Beschreibung: Template-Lernschleife - Extrahiert bewaehrte Konfigurationen aus
              erfolgreichen Projekten und schlaegt neue Templates vor.
              Nutzt bestehende library/archive/ Infrastruktur.
"""

import os
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any

from techstack_templates.template_loader import (
    load_all_templates,
    get_template_by_id,
    invalidate_cache,
)

logger = logging.getLogger(__name__)

_MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
_STACKS_DIR = os.path.join(_MODULE_DIR, "stacks")
_USAGE_STATS_FILE = os.path.join(_STACKS_DIR, "_usage_stats.json")


def extract_proven_recipe(project_archive: dict) -> Optional[dict]:
    """
    Extrahiert die finale Dependency-Kombination aus einem erfolgreichen Projekt.

    Args:
        project_archive: Archiviertes Projekt (aus library/archive/*.json)

    Returns:
        Recipe-Dict oder None bei Fehler
    """
    if not project_archive or project_archive.get("status") != "success":
        return None

    # Tech-Blueprint aus Projekt-Eintraegen extrahieren
    tech_blueprint = _extract_blueprint_from_archive(project_archive)
    if not tech_blueprint:
        return None

    base_template = tech_blueprint.get("_source_template")
    project_type = tech_blueprint.get("project_type", "")
    language = tech_blueprint.get("language", "")

    # Dependencies sammeln (aus Blueprint + tatsaechlich installierte)
    all_deps = set()
    blueprint_deps = tech_blueprint.get("dependencies", [])
    if isinstance(blueprint_deps, list):
        all_deps.update(blueprint_deps)
    elif isinstance(blueprint_deps, dict):
        all_deps.update(blueprint_deps.keys())

    # Template-Basis-Dependencies ermitteln (um additional zu berechnen)
    template_deps = set()
    if base_template:
        tmpl = get_template_by_id(base_template)
        if tmpl:
            bp_deps = tmpl.get("blueprint", {}).get("dependencies", {})
            if isinstance(bp_deps, dict):
                template_deps = set(bp_deps.keys())
            elif isinstance(bp_deps, list):
                template_deps = set(bp_deps)

    additional_deps = all_deps - template_deps

    return {
        "project_id": project_archive.get("project_id", ""),
        "project_goal": project_archive.get("goal", ""),
        "base_template": base_template,
        "project_type": project_type,
        "language": language,
        "all_dependencies": sorted(all_deps),
        "additional_dependencies": sorted(additional_deps),
        "timestamp": project_archive.get("completed_at", ""),
    }


def find_similar_recipes(
    recipe: dict,
    archive_dir: str,
    min_similarity: float = 0.7
) -> List[dict]:
    """
    Sucht in library/archive/ nach Projekten mit aehnlicher Dependency-Kombination.

    Args:
        recipe: Referenz-Recipe (von extract_proven_recipe)
        archive_dir: Pfad zum Archiv-Verzeichnis
        min_similarity: Minimale Aehnlichkeit (0.0-1.0)

    Returns:
        Liste aehnlicher Recipes
    """
    if not os.path.isdir(archive_dir):
        return []

    similar = []
    ref_additional = set(recipe.get("additional_dependencies", []))
    ref_base = recipe.get("base_template", "")

    if not ref_additional:
        return []

    for filename in os.listdir(archive_dir):
        if not filename.endswith(".json"):
            continue
        filepath = os.path.join(archive_dir, filename)
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                archive = json.load(f)
            # Nur erfolgreiche Projekte
            if archive.get("status") != "success":
                continue
            # Eigenes Projekt ueberspringen
            if archive.get("project_id") == recipe.get("project_id"):
                continue

            other_recipe = extract_proven_recipe(archive)
            if not other_recipe:
                continue
            # Gleiche Basis?
            if other_recipe.get("base_template") != ref_base:
                continue

            other_additional = set(other_recipe.get("additional_dependencies", []))
            if not other_additional:
                continue

            # Jaccard-Aehnlichkeit
            intersection = ref_additional & other_additional
            union = ref_additional | other_additional
            similarity = len(intersection) / len(union) if union else 0.0

            if similarity >= min_similarity:
                other_recipe["similarity"] = round(similarity, 2)
                similar.append(other_recipe)
        except (json.JSONDecodeError, IOError):
            continue

    similar.sort(key=lambda x: x.get("similarity", 0), reverse=True)
    return similar


def propose_new_template(recipes: List[dict]) -> Optional[dict]:
    """
    Generiert Template-Vorschlag aus aehnlichen erfolgreichen Recipes.
    Benoetigt >= 2 Recipes mit gleicher Basis.

    Args:
        recipes: Liste aehnlicher Recipes (inkl. dem Referenz-Recipe)

    Returns:
        Template-JSON Dict oder None
    """
    if len(recipes) < 2:
        return None

    # Gemeinsame Basis
    base_template_id = recipes[0].get("base_template")
    if not base_template_id:
        return None

    base_template = get_template_by_id(base_template_id)
    if not base_template:
        return None

    # Gemeinsame additional Dependencies (in ALLEN Recipes vorhanden)
    all_additional_sets = [set(r.get("additional_dependencies", [])) for r in recipes]
    common_additional = all_additional_sets[0]
    for dep_set in all_additional_sets[1:]:
        common_additional = common_additional & dep_set

    if not common_additional:
        return None

    # Template-ID generieren
    sorted_deps = sorted(common_additional)
    feature_tag = sorted_deps[0].replace("-", "_").replace("@", "").replace("/", "_")
    new_template_id = f"{base_template_id}_{feature_tag}"

    # Blueprint erweitern
    import copy
    new_blueprint = copy.deepcopy(base_template.get("blueprint", {}))
    base_deps = new_blueprint.get("dependencies", {})

    # Additional Dependencies hinzufuegen
    if isinstance(base_deps, dict):
        for dep in common_additional:
            if dep not in base_deps:
                base_deps[dep] = "latest"
    elif isinstance(base_deps, list):
        for dep in common_additional:
            if dep not in base_deps:
                base_deps.append(dep)
    new_blueprint["dependencies"] = base_deps

    # Keywords erweitern
    base_keywords = list(base_template.get("match_keywords", []))
    for dep in common_additional:
        keyword = dep.replace("-", " ").replace("_", " ").lower()
        base_keywords.append(keyword)
        base_keywords.append(dep.lower())

    # Projekt-IDs der Quellen
    source_projects = [r.get("project_id", "") for r in recipes]

    return {
        "template_id": new_template_id,
        "template_version": "1.0",
        "display_name": f"{base_template.get('display_name', '')} + {', '.join(sorted_deps[:3])}",
        "source": "learned",
        "learned_from": source_projects,
        "learned_at": datetime.now().isoformat(),
        "match_keywords": base_keywords,
        "match_priority": base_template.get("match_priority", 5) + 1,
        "blueprint": new_blueprint,
        "required_files": base_template.get("required_files", []),
        "directory_structure": base_template.get("directory_structure", {}),
        "coder_rules": base_template.get("coder_rules", []),
        "file_templates_dir": base_template.get("file_templates_dir", ""),
        "container_ids": base_template.get("container_ids", []),
    }


def save_learned_template(template: dict) -> str:
    """
    Speichert ein gelerntes Template in stacks/.

    Args:
        template: Template-Dict (von propose_new_template)

    Returns:
        template_id des gespeicherten Templates
    """
    template_id = template.get("template_id", "learned_unknown")
    filepath = os.path.join(_STACKS_DIR, f"{template_id}.json")

    os.makedirs(_STACKS_DIR, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(template, f, indent=2, ensure_ascii=False)

    # Cache invalidieren damit neues Template sofort verfuegbar ist
    invalidate_cache()
    logger.info("Gelerntes Template gespeichert: %s", template_id)
    return template_id


def record_template_usage(template_id: str, project_id: str, success: bool):
    """
    Trackt welches Template wie oft erfolgreich/fehlgeschlagen ist.

    Args:
        template_id: ID des verwendeten Templates
        project_id: Projekt-ID
        success: Ob das Projekt erfolgreich war
    """
    stats = _load_usage_stats()

    if template_id not in stats:
        stats[template_id] = {
            "total_uses": 0, "successes": 0, "failures": 0,
            "success_rate": 0.0, "last_used": "", "projects": []
        }

    entry = stats[template_id]
    entry["total_uses"] += 1
    if success:
        entry["successes"] += 1
    else:
        entry["failures"] += 1
    entry["success_rate"] = round(entry["successes"] / entry["total_uses"], 2)
    entry["last_used"] = datetime.now().isoformat()
    entry["projects"].append({
        "project_id": project_id,
        "success": success,
        "timestamp": datetime.now().isoformat()
    })
    # Maximal 50 Projekte pro Template speichern
    entry["projects"] = entry["projects"][-50:]

    _save_usage_stats(stats)


def try_learn_from_project(project_archive: dict, archive_dir: str) -> Optional[str]:
    """
    Haupteinstiegspunkt: Versucht aus einem erfolgreichen Projekt zu lernen.
    Wird von library_manager.complete_project() aufgerufen.

    Args:
        project_archive: Das gerade abgeschlossene Projekt
        archive_dir: Pfad zum Archiv-Verzeichnis

    Returns:
        template_id des neuen Templates oder None
    """
    recipe = extract_proven_recipe(project_archive)
    if not recipe:
        return None

    # Template-Nutzung tracken
    base_template = recipe.get("base_template")
    if base_template:
        record_template_usage(
            base_template,
            recipe.get("project_id", ""),
            True
        )

    # Nur lernen wenn es additional Dependencies gibt
    if not recipe.get("additional_dependencies"):
        return None

    similar = find_similar_recipes(recipe, archive_dir)
    if not similar:
        return None

    # Referenz-Recipe + aehnliche zusammen
    all_recipes = [recipe] + similar
    proposed = propose_new_template(all_recipes)
    if not proposed:
        return None

    # Pruefen ob ein Template mit gleicher ID bereits existiert
    existing = get_template_by_id(proposed["template_id"])
    if existing:
        logger.info("Template '%s' existiert bereits, ueberspringe", proposed["template_id"])
        return None

    template_id = save_learned_template(proposed)
    logger.info(
        "Neues Template gelernt: %s (aus %d aehnlichen Projekten)",
        template_id, len(all_recipes)
    )
    return template_id


def _extract_blueprint_from_archive(project_archive: dict) -> Optional[dict]:
    """Extrahiert tech_blueprint aus Projekt-Archiv-Eintraegen."""
    for entry in project_archive.get("entries", []):
        content = entry.get("content", "")
        if entry.get("type") == "TechStackOutput":
            try:
                data = json.loads(content) if isinstance(content, str) else content
                return data.get("blueprint", {})
            except (json.JSONDecodeError, TypeError):
                continue
        if entry.get("type") == "Blueprint":
            try:
                return json.loads(content) if isinstance(content, str) else content
            except (json.JSONDecodeError, TypeError):
                continue
    return None


def _load_usage_stats() -> dict:
    """Laedt Template-Nutzungsstatistiken."""
    if os.path.exists(_USAGE_STATS_FILE):
        try:
            with open(_USAGE_STATS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {}


def _save_usage_stats(stats: dict):
    """Speichert Template-Nutzungsstatistiken."""
    os.makedirs(os.path.dirname(_USAGE_STATS_FILE), exist_ok=True)
    with open(_USAGE_STATS_FILE, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)
