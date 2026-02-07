# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 07.02.2026
Version: 1.0
Beschreibung: Template-Loader - Laedt, matcht und merged Tech-Stack Templates.
              Kern-Modul fuer das Template-System: Templates sind vordefinierte,
              getestete Konfigurationen die als Basis fuer neue Projekte dienen.
"""

import os
import json
import shutil
import logging
import re
from typing import Dict, List, Optional, Tuple, Any

logger = logging.getLogger(__name__)

# Verzeichnisse relativ zum Modul
_MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
_STACKS_DIR = os.path.join(_MODULE_DIR, "stacks")
_FILE_TEMPLATES_DIR = os.path.join(_MODULE_DIR, "file_templates")

# Cache fuer geladene Templates (einmal laden, mehrfach nutzen)
_template_cache: Optional[Dict[str, dict]] = None


def load_all_templates() -> Dict[str, dict]:
    """
    Laedt alle Template-JSONs aus dem stacks/ Verzeichnis.
    Ergebnis wird gecacht fuer wiederholte Aufrufe.

    Returns:
        Dict mit template_id als Key und Template-Dict als Value
    """
    global _template_cache
    if _template_cache is not None:
        return _template_cache

    templates = {}
    if not os.path.isdir(_STACKS_DIR):
        logger.warning("Template-Verzeichnis nicht gefunden: %s", _STACKS_DIR)
        _template_cache = templates
        return templates

    for filename in os.listdir(_STACKS_DIR):
        if not filename.endswith(".json") or filename.startswith("_"):
            continue
        filepath = os.path.join(_STACKS_DIR, filename)
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                template = json.load(f)
            template_id = template.get("template_id")
            if not template_id:
                logger.warning("Template ohne template_id uebersprungen: %s", filename)
                continue
            # Pflichtfelder pruefen
            if "blueprint" not in template:
                logger.warning("Template ohne blueprint uebersprungen: %s", filename)
                continue
            templates[template_id] = template
        except (json.JSONDecodeError, IOError) as e:
            logger.error("Fehler beim Laden von Template %s: %s", filename, e)

    logger.info("Templates geladen: %d (%s)", len(templates), ", ".join(templates.keys()))
    _template_cache = templates
    return templates


def invalidate_cache():
    """Setzt den Template-Cache zurueck (z.B. nach Hinzufuegen eines gelernten Templates)."""
    global _template_cache
    _template_cache = None


def find_matching_templates(user_goal: str) -> List[Tuple[str, dict, float]]:
    """
    Keyword-Matching gegen den User-Goal-Text.

    Args:
        user_goal: Benutzeranforderung als Freitext

    Returns:
        Liste von (template_id, template, score) absteigend nach Score sortiert
    """
    templates = load_all_templates()
    if not templates:
        return []

    goal_lower = user_goal.lower()
    results = []

    for template_id, template in templates.items():
        keywords = template.get("match_keywords", [])
        priority = template.get("match_priority", 5)
        hits = sum(1 for kw in keywords if kw.lower() in goal_lower)
        if hits > 0:
            # Score: Anzahl Keyword-Treffer * Prioritaet
            score = hits * priority
            results.append((template_id, template, score))

    results.sort(key=lambda x: x[2], reverse=True)
    return results


def get_template_by_id(template_id: str) -> Optional[dict]:
    """
    Direkter Zugriff auf ein Template per ID.

    Args:
        template_id: Eindeutige Template-ID (z.B. "nextjs_tailwind")

    Returns:
        Template-Dict oder None
    """
    templates = load_all_templates()
    return templates.get(template_id)


def build_blueprint_from_template(template: dict, customizations: dict) -> dict:
    """
    Merged Template-Blueprint mit LLM-Customizations.

    Regeln:
    - Template-Dependencies sind die Minimum-Basis (NIE entfernbar)
    - LLM kann Dependencies HINZUFUEGEN (additional_dependencies)
    - LLM kann database, server_port etc. ueberschreiben
    - _source_template wird ins Blueprint geschrieben fuer spaetere Referenz

    Args:
        template: Das gewaehlte Template
        customizations: LLM-Output mit additional_dependencies und Ueberschreibungen

    Returns:
        Fertiger Blueprint (kompatibel mit bestehendem tech_blueprint Format)
    """
    import copy
    blueprint = copy.deepcopy(template.get("blueprint", {}))

    # Template-Metadaten anfuegen
    blueprint["_source_template"] = template.get("template_id")
    blueprint["_template_version"] = template.get("template_version", "1.0")

    # LLM-Customizations anwenden
    if not customizations:
        # Dependencies von Dict zu Liste konvertieren (Kompatibilitaet)
        blueprint["dependencies"] = _deps_dict_to_list(blueprint.get("dependencies", {}))
        return blueprint

    # Einfache Feld-Ueberschreibungen (database, server_port etc.)
    overridable_fields = {"database", "server_port", "reasoning"}
    for field in overridable_fields:
        if field in customizations and customizations[field]:
            blueprint[field] = customizations[field]

    # Additional Dependencies hinzufuegen (Template-Deps bleiben, neue kommen dazu)
    template_deps = blueprint.get("dependencies", {})
    additional = customizations.get("additional_dependencies", {})

    if isinstance(additional, dict):
        for pkg, version in additional.items():
            if pkg not in template_deps:
                template_deps[pkg] = version
    elif isinstance(additional, list):
        for pkg in additional:
            if pkg not in template_deps:
                template_deps[pkg] = "latest"

    # Dependencies von Dict zu Liste konvertieren (Kompatibilitaet mit bestehendem System)
    blueprint["dependencies"] = _deps_dict_to_list(template_deps)

    # Pinned-Versionen separat speichern fuer package.json-Generierung
    blueprint["_pinned_versions"] = template_deps

    return blueprint


def _deps_dict_to_list(deps: Any) -> list:
    """Konvertiert Dependencies-Dict zu Liste (Kompatibilitaet mit bestehendem System)."""
    if isinstance(deps, list):
        return deps
    if isinstance(deps, dict):
        return list(deps.keys())
    return []


def copy_file_templates(template: dict, project_path: str) -> List[str]:
    """
    Kopiert File-Templates ins Projektverzeichnis.
    Existierende Dateien werden NICHT ueberschrieben.

    Args:
        template: Das gewaehlte Template mit file_templates_dir Feld
        project_path: Ziel-Projektverzeichnis

    Returns:
        Liste der kopierten Dateipfade (relativ zum Projekt)
    """
    template_dir_name = template.get("file_templates_dir")
    if not template_dir_name:
        return []

    source_dir = os.path.join(_FILE_TEMPLATES_DIR, template_dir_name)
    if not os.path.isdir(source_dir):
        logger.warning("File-Template-Verzeichnis nicht gefunden: %s", source_dir)
        return []

    copied = []
    for root, _dirs, files in os.walk(source_dir):
        for filename in files:
            src_path = os.path.join(root, filename)
            # Relativer Pfad innerhalb des Template-Verzeichnisses
            rel_path = os.path.relpath(src_path, source_dir)
            dst_path = os.path.join(project_path, rel_path)

            # Zielverzeichnis erstellen
            os.makedirs(os.path.dirname(dst_path), exist_ok=True)

            # Nicht ueberschreiben — Coder hat Vorrang
            if not os.path.exists(dst_path):
                shutil.copy2(src_path, dst_path)
                copied.append(rel_path.replace("\\", "/"))
                logger.debug("File-Template kopiert: %s", rel_path)

    if copied:
        logger.info("File-Templates kopiert: %d Dateien (%s)", len(copied), ", ".join(copied[:5]))
    return copied


def get_coder_rules(template: dict) -> str:
    """
    Formatiert die Template-spezifischen Coder-Regeln als Prompt-String.

    Args:
        template: Template mit coder_rules Feld

    Returns:
        Formatierter String fuer den Coder-Prompt, oder leerer String
    """
    rules = template.get("coder_rules", [])
    if not rules:
        return ""

    display_name = template.get("display_name", template.get("template_id", ""))
    lines = [f"FRAMEWORK-REGELN (Template: {display_name}):"]
    for i, rule in enumerate(rules, 1):
        lines.append(f"  {i}. {rule}")
    return "\n".join(lines)


def get_template_summary_for_prompt() -> str:
    """
    Erzeugt eine kompakte Zusammenfassung aller verfuegbaren Templates
    fuer den TechStack-Agent Prompt.

    Returns:
        Formatierter String mit Template-Uebersicht
    """
    templates = load_all_templates()
    if not templates:
        return "Keine Templates verfuegbar."

    lines = ["VERFUEGBARE TEMPLATES (waehle das passende oder gib null zurueck):\n"]
    for tid, tmpl in sorted(templates.items(), key=lambda x: x[1].get("match_priority", 0), reverse=True):
        bp = tmpl.get("blueprint", {})
        deps = bp.get("dependencies", {})
        dep_names = list(deps.keys()) if isinstance(deps, dict) else deps
        dep_str = ", ".join(dep_names[:6])
        if len(dep_names) > 6:
            dep_str += f" (+{len(dep_names) - 6} weitere)"
        lines.append(
            f"- **{tid}**: {tmpl.get('display_name', tid)} "
            f"| Sprache: {bp.get('language', '?')} "
            f"| Typ: {bp.get('app_type', '?')} "
            f"| Dependencies: {dep_str}"
        )

    return "\n".join(lines)
