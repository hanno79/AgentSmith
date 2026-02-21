# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 08.02.2026
Version: 1.0
Beschreibung: Planner Default-Plan Logik - Template-basierte und generische Fallback-Plaene.
              Extrahiert aus planner_agent.py fuer Regel 1 Konformitaet (<500 Zeilen).
              # AENDERUNG 08.02.2026: Neues Modul (Fix 27 Regel-1 Refactoring)
"""

import os
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# AENDERUNG 10.02.2026: Fix 49 — Auf Modul-Ebene fuer Import aus anderen Modulen
# Template-Config-Dateien die bereits vom Template kopiert wurden und NICHT regeneriert werden sollen
# AENDERUNG 13.02.2026: Fix 52 — .mjs/.ts Varianten hinzugefuegt
# ROOT-CAUSE-FIX: Coder generiert next.config.mjs obwohl Template next.config.js hat
# → Beide Config-Dateien existieren → Next.js kann nicht starten
# Ursache: PROTECTED_CONFIGS hatte nur .js Varianten, nicht .mjs/.ts
# AENDERUNG 20.02.2026: Fix 57d — globals.css hinzugefuegt
# ROOT-CAUSE-FIX: Coder ueberschreibt globals.css mit nur 3 Zeilen (Tailwind Directives)
# obwohl Template 62 Zeilen mit Shadcn CSS-Custom-Properties hat → Next.js rendert nicht
PROTECTED_CONFIGS = {
    "tailwind.config.js", "tailwind.config.ts",
    "postcss.config.js", "postcss.config.mjs", "postcss.config.ts",
    "next.config.js", "next.config.mjs", "next.config.ts",
    "jsconfig.json", "tsconfig.json",
    "vite.config.js", "vite.config.mjs", "vite.config.ts",
    "globals.css",  # Fix 57d: Shadcn CSS-Variablen schuetzen
}
# Stem-Varianten: next.config → [next.config.js, next.config.mjs, next.config.ts]
# Werden in dev_loop_run_helpers.py fuer Stem-Match genutzt
PROTECTED_CONFIG_STEMS = {os.path.splitext(c)[0] for c in PROTECTED_CONFIGS
                          if c.endswith(('.js', '.mjs', '.ts'))}


def _extract_api_resources(database_schema: str, blueprint: Dict[str, Any]) -> list:
    """
    AENDERUNG 20.02.2026: Fix 58b+58f — ALLE API-Ressourcen aus DB-Schema.
    ROOT-CAUSE-FIX 58b: Hardcoded "todos" fuehrte zu Tabellen-Mismatch.
    ROOT-CAUSE-FIX 58f: Nur erste Tabelle extrahiert → fehlende Routes fuer
    weitere Tabellen (z.B. /api/ideas 404 bei bugs+ideas Schema).
    Jetzt werden ALLE Tabellennamen als Liste zurueckgegeben.

    Args:
        database_schema: SQL-Schema vom DBDesigner
        blueprint: TechStack-Blueprint

    Returns:
        Liste aller API-Ressourcen-Namen (z.B. ["bugs", "ideas"] oder ["data"] als Fallback)
    """
    if not database_schema or "Kein Datenbank" in database_schema:
        return ["data"]

    try:
        from backend.orchestration_helpers import extract_tables_from_schema
        tables = extract_tables_from_schema(database_schema)
        if tables:
            resources = [t.get("name", "data") for t in tables if t.get("name")]
            if resources:
                logger.info(f"[PlannerDefaults] API-Ressourcen aus Schema: {resources} "
                           f"({len(resources)} Tabellen)")
                return resources
    except ImportError:
        logger.warning("[PlannerDefaults] extract_tables_from_schema nicht verfuegbar")

    return ["data"]


def _create_template_based_plan(blueprint: Dict[str, Any],
                                database_schema: str = "") -> Optional[List[Dict[str, Any]]]:
    """
    AENDERUNG 08.02.2026: Template-basierter Default-Plan (Fix 27).
    Erstellt einen Default-Plan basierend auf dem Template des Blueprints.
    Nutzt required_files + directory_structure aus dem Template.

    ROOT-CAUSE-FIX:
    Symptom: Default-Plan generiert src/index.js (Express) fuer Next.js Projekte
    Ursache: create_default_plan() kennt nur python/javascript, nicht Frameworks
    Loesung: Template-Wissen nutzen (required_files aus stacks/*.json)

    Returns:
        Liste von File-Dicts oder None wenn kein Template verfuegbar
    """
    source_template = blueprint.get("_source_template")
    if not source_template:
        return None

    try:
        from techstack_templates.template_loader import load_all_templates
        templates = load_all_templates()
        template = templates.get(source_template)
        if not template:
            return None
    except Exception:
        return None

    project_type = blueprint.get("project_type", "")
    db_type = blueprint.get("database", "none")

    files = []

    # 1. package.json / requirements.txt (immer Priority 1)
    pkg_file = blueprint.get("package_file", "package.json")
    files.append({
        "path": pkg_file,
        "description": "Dependencies",
        "depends_on": [],
        "estimated_lines": 25,
        "priority": 1
    })

    # 2. DB-Datei wenn noetig (Priority 1)
    if db_type and db_type != "none":
        if "next" in project_type:
            db_path = "lib/db.js"
        elif "flask" in project_type or "fastapi" in project_type:
            db_path = "src/database.py"
        else:
            db_path = "src/database.js"
        files.append({
            "path": db_path,
            "description": f"Datenbank-Initialisierung ({db_type})",
            "depends_on": [],
            "estimated_lines": 60,
            "priority": 1
        })

    # 3. CSS/Styles (Priority 1)
    # AENDERUNG 20.02.2026: Fix 57d — Basename-Match fuer PROTECTED_CONFIGS
    # ROOT-CAUSE-FIX: rf="app/globals.css" matched nicht gegen "globals.css" im Set
    required = template.get("required_files", [])
    for rf in required:
        if rf.endswith(".css") and os.path.basename(rf) not in PROTECTED_CONFIGS:
            files.append({
                "path": rf,
                "description": "Stylesheet / CSS-Importe",
                "depends_on": [],
                "estimated_lines": 20,
                "priority": 1
            })

    # 4. Layout/Wrapper-Dateien (Priority 2)
    for rf in required:
        if "layout" in rf or "_app" in rf or "base.html" in rf:
            css_deps = [f["path"] for f in files if f["path"].endswith(".css")]
            files.append({
                "path": rf,
                "description": "Layout/Wrapper",
                "depends_on": css_deps,
                "estimated_lines": 40,
                "priority": 2
            })

    # 5. API-Routen wenn DB vorhanden (Priority 3)
    # AENDERUNG 20.02.2026: Fix 58b+58f — Eine Route PRO Tabelle aus Schema
    # ROOT-CAUSE-FIX 58b: Hardcoded "todos" → Tabellen-Mismatch
    # ROOT-CAUSE-FIX 58f: Nur eine Route → fehlende Routes bei Multi-Tabellen-Schema
    if db_type and db_type != "none":
        if "next" in project_type:
            db_dep = "lib/db.js"
            api_resources = _extract_api_resources(database_schema, blueprint)
            for resource in api_resources:
                files.append({
                    "path": f"app/api/{resource}/route.js",
                    "description": f"API Route Handler (CRUD) fuer {resource}",
                    "depends_on": [db_dep],
                    "estimated_lines": 100,
                    "priority": 3
                })
        elif "flask" in project_type:
            files.append({
                "path": "src/routes.py",
                "description": "Flask Routes",
                "depends_on": ["src/database.py"],
                "estimated_lines": 100,
                "priority": 3
            })

    # 6. Hauptseite/App (Priority 4) - verbleibende required_files
    # AENDERUNG 20.02.2026: Fix 57d — Basename-Match fuer PROTECTED_CONFIGS
    for rf in required:
        if os.path.basename(rf) in PROTECTED_CONFIGS:
            continue
        if rf.endswith(".css") or "layout" in rf or "_app" in rf or "base.html" in rf:
            continue
        if rf in ("package.json", "requirements.txt", "run.bat"):
            continue
        existing = {f["path"] for f in files}
        if rf in existing:
            continue
        files.append({
            "path": rf,
            "description": "Anwendungsdatei",
            "depends_on": [],
            "estimated_lines": 80,
            "priority": 4
        })

    # 7. run.bat (letzte Priority)
    if not any(f["path"] == "run.bat" for f in files):
        files.append({
            "path": "run.bat",
            "description": "Windows-Startskript",
            "depends_on": [pkg_file],
            "estimated_lines": 15,
            "priority": 5
        })

    return files if len(files) >= 3 else None


def create_default_plan(blueprint: Dict[str, Any], user_prompt: str,
                        database_schema: str = "") -> Dict[str, Any]:
    """
    Erstellt einen Standard-Plan wenn der Planner-Agent fehlschlaegt.

    Args:
        blueprint: TechStack-Blueprint
        user_prompt: Benutzer-Anforderung
        database_schema: SQL-Schema vom DBDesigner (fuer dynamische API-Pfade)

    Returns:
        Standard-Plan basierend auf Projekt-Typ
    """
    # AENDERUNG 08.02.2026: Template-basierter Default-Plan (Fix 27)
    # AENDERUNG 20.02.2026: Fix 58b — database_schema durchreichen
    template_files = _create_template_based_plan(blueprint, database_schema)
    if template_files:
        return {
            "project_name": "project",
            "total_files": len(template_files),
            "estimated_lines": sum(f["estimated_lines"] for f in template_files),
            "files": template_files,
            "source": "template_fallback"
        }

    # Generischer Fallback wenn kein Template verfuegbar
    project_type = blueprint.get("project_type", "python_script")
    language = blueprint.get("language", "python")

    # Standard-Dateien je nach Projekt-Typ
    if language == "python":
        files = [
            {
                "path": "src/config.py",
                "description": "Konfiguration und Konstanten",
                "depends_on": [],
                "estimated_lines": 30,
                "priority": 1
            },
            {
                "path": "src/database.py",
                "description": "Datenbanklogik und Modelle",
                "depends_on": ["src/config.py"],
                "estimated_lines": 100,
                "priority": 2
            },
            {
                "path": "src/main.py",
                "description": "Hauptanwendung und UI",
                "depends_on": ["src/config.py", "src/database.py"],
                "estimated_lines": 150,
                "priority": 3
            },
            {
                "path": "requirements.txt",
                "description": "Python-Dependencies",
                "depends_on": [],
                "estimated_lines": 10,
                "priority": 1
            },
            {
                "path": "run.bat",
                "description": "Windows-Startskript",
                "depends_on": ["requirements.txt"],
                "estimated_lines": 10,
                "priority": 4
            },
            {
                "path": "tests/test_database.py",
                "description": "Unit-Tests fuer Datenbanklogik",
                "depends_on": ["src/database.py"],
                "estimated_lines": 80,
                "priority": 5
            }
        ]
    elif language == "javascript":
        files = [
            {
                "path": "src/config.js",
                "description": "Konfiguration und Konstanten",
                "depends_on": [],
                "estimated_lines": 30,
                "priority": 1
            },
            {
                "path": "src/index.js",
                "description": "Hauptanwendung",
                "depends_on": ["src/config.js"],
                "estimated_lines": 150,
                "priority": 2
            },
            {
                "path": "package.json",
                "description": "NPM-Dependencies",
                "depends_on": [],
                "estimated_lines": 20,
                "priority": 1
            },
            {
                "path": "run.bat",
                "description": "Windows-Startskript",
                "depends_on": ["package.json"],
                "estimated_lines": 10,
                "priority": 3
            }
        ]
        # AENDERUNG 08.02.2026: DB-Dateien fuer JS Default-Plan (Fix 22.5)
        db_type = blueprint.get("database", "none")
        if db_type and db_type != "none":
            if "next" in project_type:
                files.insert(1, {
                    "path": "lib/db.js",
                    "description": f"Datenbank-Initialisierung ({db_type})",
                    "depends_on": [],
                    "estimated_lines": 60,
                    "priority": 1
                })
            else:
                files.insert(1, {
                    "path": "src/database.js",
                    "description": f"Datenbank-Initialisierung ({db_type})",
                    "depends_on": ["src/config.js"],
                    "estimated_lines": 80,
                    "priority": 2
                })
    else:
        # Generischer Fallback
        files = [
            {
                "path": "src/main.py",
                "description": "Hauptanwendung",
                "depends_on": [],
                "estimated_lines": 200,
                "priority": 1
            },
            {
                "path": "requirements.txt",
                "description": "Dependencies",
                "depends_on": [],
                "estimated_lines": 10,
                "priority": 1
            },
            {
                "path": "run.bat",
                "description": "Startskript",
                "depends_on": [],
                "estimated_lines": 10,
                "priority": 2
            }
        ]

    return {
        "project_name": "project",
        "total_files": len(files),
        "estimated_lines": sum(f["estimated_lines"] for f in files),
        "files": files,
        "source": "default_fallback"
    }


def sort_files_by_priority(plan: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Sortiert die Dateien nach Prioritaet und Abhaengigkeiten.

    Args:
        plan: Planner-Output mit files-Liste

    Returns:
        Sortierte Liste der Dateien
    """
    files = plan.get("files", [])

    # Sortiere primaer nach priority, sekundaer nach Anzahl der Abhaengigkeiten
    def sort_key(f):
        return (
            f.get("priority", 999),
            len(f.get("depends_on", []))
        )

    return sorted(files, key=sort_key)


def get_ready_files(plan: Dict[str, Any], completed_files: List[str]) -> List[Dict[str, Any]]:
    """
    Gibt alle Dateien zurueck, deren Abhaengigkeiten erfuellt sind.

    Args:
        plan: Planner-Output mit files-Liste
        completed_files: Liste der bereits erstellten Dateipfade

    Returns:
        Liste der jetzt erstellbaren Dateien
    """
    files = plan.get("files", [])
    completed_set = set(completed_files)
    ready = []

    for f in files:
        if f["path"] in completed_set:
            continue  # Bereits erstellt

        depends = f.get("depends_on", [])
        if all(dep in completed_set for dep in depends):
            ready.append(f)

    return ready
