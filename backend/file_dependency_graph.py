# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 01.02.2026
Version: 1.0
Beschreibung: Dependency-Graph fuer parallele Datei-Generierung.
              Analysiert Abhaengigkeiten zwischen Dateien und gruppiert
              sie in parallele Batches.
"""

from typing import Dict, List, Set, Tuple
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)


@dataclass
class FileDependency:
    """
    Repraesentiert eine Datei mit ihren Abhaengigkeiten.

    Attributes:
        filename: Name der Datei (z.B. "src/app.py")
        depends_on: Liste von Dateien die vorher existieren muessen
        priority: Niedrigere Werte = frueher generieren
    """
    filename: str
    depends_on: List[str] = field(default_factory=list)
    priority: int = 0


# Prioritaets-Mappings fuer verschiedene Tech-Stacks
PRIORITY_RULES = {
    # Python/Flask Projekte
    "python": {
        "config": 0,        # requirements.txt, .env, config.py
        "models": 1,        # models.py, schema.py
        "database": 2,      # database.py, db.py
        "core": 3,          # app.py, main.py
        "routes": 4,        # routes/, blueprints/
        "templates": 5,     # templates/, static/
        "tests": 6,         # tests/, test_*.py
        "scripts": 7,       # run.bat, start.sh
    },
    # JavaScript/Node.js Projekte
    "javascript": {
        "config": 0,        # package.json, .env
        "types": 1,         # types/, interfaces/
        "models": 2,        # models/, schemas/
        "database": 3,      # db/, database/
        "core": 4,          # app.js, index.js, server.js
        "routes": 5,        # routes/, api/
        "components": 6,    # components/, views/
        "tests": 7,         # tests/, __tests__/
    }
}


def _get_file_category(filename: str) -> str:
    """
    Bestimmt die Kategorie einer Datei basierend auf Namen und Pfad.

    Args:
        filename: Dateiname mit optionalem Pfad

    Returns:
        Kategorie-String (z.B. "config", "models", "tests")
    """
    filename_lower = filename.lower()

    # Config-Dateien
    if any(x in filename_lower for x in [
        "requirements.txt", "package.json", ".env", "config.py",
        "config.js", "config.yaml", "config.json", ".gitignore"
    ]):
        return "config"

    # Test-Dateien
    if any(x in filename_lower for x in ["test_", "_test.", "tests/", "__tests__", ".test.", "spec."]):
        return "tests"

    # Scripts
    if any(x in filename_lower for x in [".bat", ".sh", "run.", "start.", "dockerfile"]):
        return "scripts"

    # Models/Schema
    if any(x in filename_lower for x in ["models", "schema", "entities"]):
        return "models"

    # Database
    if any(x in filename_lower for x in ["database", "db.", "/db/", "migration"]):
        return "database"

    # Templates/Static (Frontend Assets)
    if any(x in filename_lower for x in ["templates/", "static/", "public/", "assets/", ".html", ".css"]):
        return "templates"

    # Routes/API
    if any(x in filename_lower for x in ["routes", "api/", "endpoints", "blueprint"]):
        return "routes"

    # Components (React/Vue)
    if any(x in filename_lower for x in ["components/", "views/", ".jsx", ".vue", ".tsx"]):
        return "components"

    # Types/Interfaces
    if any(x in filename_lower for x in ["types/", "interfaces/", ".d.ts"]):
        return "types"

    # Core application files
    if any(x in filename_lower for x in ["app.py", "main.py", "app.js", "index.js", "server.js"]):
        return "core"

    # Default: treat as core
    return "core"


def _get_dependencies_for_category(
    category: str,
    file_list: List[str],
    tech_stack: str
) -> List[str]:
    """
    Bestimmt die Abhaengigkeiten fuer eine Kategorie.

    Args:
        category: Kategorie der Datei
        file_list: Liste aller Dateien im Projekt
        tech_stack: Tech-Stack (python, javascript, etc.)

    Returns:
        Liste von Dateinamen von denen diese Kategorie abhaengt
    """
    deps = []

    # Dependency-Regeln pro Kategorie
    if category == "database":
        # Database haengt von Models ab
        deps = [f for f in file_list if _get_file_category(f) == "models"]

    elif category == "core":
        # Core haengt von Models und Database ab
        deps = [f for f in file_list if _get_file_category(f) in ("models", "database")]

    elif category == "routes":
        # Routes haengen von Core ab
        deps = [f for f in file_list if _get_file_category(f) in ("models", "database", "core")]

    elif category == "templates":
        # Templates haengen von Core und Routes ab
        deps = [f for f in file_list if _get_file_category(f) == "core"]

    elif category == "components":
        # Components haengen von Types und Models ab
        deps = [f for f in file_list if _get_file_category(f) in ("types", "models")]

    elif category == "tests":
        # Tests haengen von allem ab (ausser anderen Tests und Scripts)
        deps = [f for f in file_list if _get_file_category(f) not in ("tests", "scripts")]

    elif category == "scripts":
        # Scripts haengen von allem ab (werden zuletzt generiert)
        deps = [f for f in file_list if _get_file_category(f) != "scripts"]

    return deps


def build_dependency_graph(
    file_list: List[str],
    tech_stack: str = "python"
) -> Dict[str, FileDependency]:
    """
    Erstellt einen Dependency-Graph fuer die gegebenen Dateien.

    Args:
        file_list: Liste der zu generierenden Dateien
        tech_stack: Tech-Stack (python, javascript, etc.)

    Returns:
        Dict mit Dateiname -> FileDependency Mapping
    """
    # Normalisiere Tech-Stack
    tech_stack = tech_stack.lower()
    if "python" in tech_stack or "flask" in tech_stack or "django" in tech_stack:
        tech_stack = "python"
    elif "javascript" in tech_stack or "node" in tech_stack or "react" in tech_stack:
        tech_stack = "javascript"

    priority_map = PRIORITY_RULES.get(tech_stack, PRIORITY_RULES["python"])

    graph = {}

    for filename in file_list:
        category = _get_file_category(filename)
        priority = priority_map.get(category, 5)  # Default priority 5
        deps = _get_dependencies_for_category(category, file_list, tech_stack)

        # Entferne self-references
        deps = [d for d in deps if d != filename]

        graph[filename] = FileDependency(
            filename=filename,
            depends_on=deps,
            priority=priority
        )

        logger.debug(f"Datei {filename}: Kategorie={category}, Prioritaet={priority}, Deps={len(deps)}")

    return graph


def get_parallel_batches(
    graph: Dict[str, FileDependency]
) -> List[List[str]]:
    """
    Gruppiert Dateien in parallele Batches.

    Dateien im selben Batch koennen parallel generiert werden.
    Batches werden sequenziell abgearbeitet (Batch 1 vor Batch 2).

    Args:
        graph: Dependency-Graph von build_dependency_graph()

    Returns:
        Liste von Batches, wobei jeder Batch eine Liste von Dateinamen ist
    """
    batches = []
    completed: Set[str] = set()
    remaining = set(graph.keys())

    iteration = 0
    max_iterations = len(graph) + 1  # Schutz gegen Endlosschleife

    while remaining and iteration < max_iterations:
        iteration += 1

        # Finde alle Dateien deren Dependencies erfuellt sind
        ready = []
        for filename in remaining:
            dep = graph[filename]
            # Alle Dependencies muessen completed sein
            if all(d in completed for d in dep.depends_on):
                ready.append((dep.priority, filename))

        if not ready:
            # Zyklische Abhaengigkeit erkannt - nimm alle verbleibenden
            logger.warning(f"Zyklische Abhaengigkeit erkannt bei: {remaining}")
            ready = [(0, f) for f in remaining]

        # Sortiere nach Prioritaet
        ready.sort()

        # Gruppiere alle mit gleicher (niedrigster) Prioritaet
        min_priority = ready[0][0]
        batch = [f for p, f in ready if p == min_priority]

        batches.append(batch)
        completed.update(batch)
        remaining -= set(batch)

        logger.debug(f"Batch {len(batches)}: {len(batch)} Dateien mit Prioritaet {min_priority}")

    return batches


def analyze_parallelization_potential(
    file_list: List[str],
    tech_stack: str = "python"
) -> Dict:
    """
    Analysiert das Parallelisierungs-Potenzial fuer eine Dateiliste.

    Args:
        file_list: Liste der zu generierenden Dateien
        tech_stack: Tech-Stack

    Returns:
        Dict mit Analyse-Ergebnissen
    """
    graph = build_dependency_graph(file_list, tech_stack)
    batches = get_parallel_batches(graph)

    total_files = len(file_list)
    total_batches = len(batches)
    max_parallel = max(len(b) for b in batches) if batches else 0

    # Berechne theoretische Zeitersparnis
    # Annahme: Jede Datei braucht gleich lang
    sequential_time = total_files  # Relative Einheit
    parallel_time = total_batches  # Mit voller Parallelisierung pro Batch
    speedup = sequential_time / parallel_time if parallel_time > 0 else 1

    return {
        "total_files": total_files,
        "total_batches": total_batches,
        "max_parallel_per_batch": max_parallel,
        "theoretical_speedup": round(speedup, 2),
        "batches": [
            {"batch_number": i + 1, "files": b, "count": len(b)}
            for i, b in enumerate(batches)
        ],
        "categories": {
            category: [f for f in file_list if _get_file_category(f) == category]
            for category in set(_get_file_category(f) for f in file_list)
        }
    }


# Exportiere Hauptfunktionen
__all__ = [
    "FileDependency",
    "build_dependency_graph",
    "get_parallel_batches",
    "analyze_parallelization_potential"
]
