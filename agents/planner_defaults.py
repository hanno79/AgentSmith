# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 08.02.2026
Version: 1.0
Beschreibung: Planner Default-Plan Logik - Template-basierte und generische Fallback-Plaene.
              Extrahiert aus planner_agent.py fuer Regel 1 Konformitaet (<500 Zeilen).
              # AENDERUNG 08.02.2026: Neues Modul (Fix 27 Regel-1 Refactoring)
"""

from typing import Any, Dict, List, Optional


def _create_template_based_plan(blueprint: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
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

    # Template-Config-Dateien die bereits vom Template kopiert wurden
    PROTECTED_CONFIGS = {
        "tailwind.config.js", "postcss.config.js", "next.config.js",
        "jsconfig.json", "tsconfig.json", "vite.config.js"
    }

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
    required = template.get("required_files", [])
    for rf in required:
        if rf.endswith(".css") and rf not in PROTECTED_CONFIGS:
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
    if db_type and db_type != "none":
        if "next" in project_type:
            db_dep = "lib/db.js"
            files.append({
                "path": "app/api/todos/route.js",
                "description": "API Route Handler (CRUD)",
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
    for rf in required:
        if rf in PROTECTED_CONFIGS:
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


def create_default_plan(blueprint: Dict[str, Any], user_prompt: str) -> Dict[str, Any]:
    """
    Erstellt einen Standard-Plan wenn der Planner-Agent fehlschlaegt.

    Args:
        blueprint: TechStack-Blueprint
        user_prompt: Benutzer-Anforderung

    Returns:
        Standard-Plan basierend auf Projekt-Typ
    """
    # AENDERUNG 08.02.2026: Template-basierter Default-Plan (Fix 27)
    template_files = _create_template_based_plan(blueprint)
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
