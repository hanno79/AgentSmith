# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 06.02.2026
Version: 1.0
Beschreibung: Tests fuer backend.file_dependency_graph.
              Umfassende Tests fuer Dependency-Graph Algorithmen:
              FileDependency Dataclass, Kategorie-Erkennung,
              Abhaengigkeitsregeln, Batch-Bildung und Parallelisierungs-Analyse.
"""

import pytest

from backend.file_dependency_graph import (
    FileDependency,
    _get_file_category,
    _get_dependencies_for_category,
    build_dependency_graph,
    get_parallel_batches,
    analyze_parallelization_potential,
)


# =========================================================================
# FileDependency Dataclass
# =========================================================================


class TestFileDependency:
    """Tests fuer die FileDependency Dataclass."""

    def test_dataclass_defaults(self):
        """Standardwerte: depends_on=[], priority=0."""
        dep = FileDependency(filename="app.py")
        assert dep.filename == "app.py"
        assert dep.depends_on == []
        assert dep.priority == 0

    def test_dataclass_mit_werten(self):
        """Explizite Werte werden korrekt gesetzt."""
        dep = FileDependency(
            filename="routes.py",
            depends_on=["app.py", "models.py"],
            priority=4
        )
        assert dep.filename == "routes.py"
        assert dep.depends_on == ["app.py", "models.py"]
        assert dep.priority == 4


# =========================================================================
# _get_file_category
# =========================================================================


class TestGetFileCategory:
    """Tests fuer die Kategorie-Erkennung von Dateinamen."""

    def test_config_dateien(self):
        """Config-Dateien: requirements.txt, package.json, .env."""
        assert _get_file_category("requirements.txt") == "config"
        assert _get_file_category("package.json") == "config"
        assert _get_file_category(".env") == "config"
        assert _get_file_category("config.yaml") == "config"
        assert _get_file_category("config.py") == "config"
        assert _get_file_category(".gitignore") == "config"

    def test_test_dateien(self):
        """Test-Dateien: test_app.py, app.test.js, tests/."""
        assert _get_file_category("test_app.py") == "tests"
        assert _get_file_category("app.test.js") == "tests"
        assert _get_file_category("tests/test_login.py") == "tests"
        assert _get_file_category("__tests__/App.test.jsx") == "tests"
        assert _get_file_category("login.spec.js") == "tests"

    def test_model_dateien(self):
        """Model-Dateien: models.py, schema.py, entities.py."""
        assert _get_file_category("models.py") == "models"
        assert _get_file_category("schema.py") == "models"
        assert _get_file_category("src/entities.py") == "models"

    def test_script_dateien(self):
        """Script-Dateien: run.bat, start.sh, Dockerfile."""
        assert _get_file_category("run.bat") == "scripts"
        assert _get_file_category("start.sh") == "scripts"
        assert _get_file_category("Dockerfile") == "scripts"

    def test_core_dateien(self):
        """Core-Dateien: app.py, main.py, index.js, server.js."""
        assert _get_file_category("app.py") == "core"
        assert _get_file_category("main.py") == "core"
        assert _get_file_category("index.js") == "core"
        assert _get_file_category("server.js") == "core"

    def test_template_dateien(self):
        """Template-Dateien: templates/, static/, .html, .css."""
        assert _get_file_category("templates/index.html") == "templates"
        assert _get_file_category("static/style.css") == "templates"
        assert _get_file_category("public/favicon.ico") == "templates"
        assert _get_file_category("page.html") == "templates"

    def test_component_dateien(self):
        """Component-Dateien: components/App.jsx, .vue, .tsx."""
        assert _get_file_category("components/App.jsx") == "components"
        assert _get_file_category("views/Home.vue") == "components"
        assert _get_file_category("Button.tsx") == "components"

    def test_route_dateien(self):
        """Route-Dateien: routes/, api/, endpoints, blueprint."""
        assert _get_file_category("routes/auth.py") == "routes"
        assert _get_file_category("api/users.js") == "routes"
        assert _get_file_category("endpoints.py") == "routes"

    def test_database_dateien(self):
        """Database-Dateien: database.py, db.py, migration."""
        assert _get_file_category("database.py") == "database"
        assert _get_file_category("db.py") == "database"
        assert _get_file_category("migration_001.py") == "database"

    def test_types_dateien(self):
        """Types-Dateien: types/, interfaces/, .d.ts."""
        assert _get_file_category("types/user.ts") == "types"
        assert _get_file_category("interfaces/IUser.ts") == "types"
        assert _get_file_category("global.d.ts") == "types"

    def test_unbekannt_ist_core(self):
        """Unbekannte Dateiarten werden als 'core' eingestuft."""
        assert _get_file_category("unknown.xyz") == "core"
        assert _get_file_category("helper.py") == "core"
        assert _get_file_category("utils.js") == "core"


# =========================================================================
# _get_dependencies_for_category
# =========================================================================


class TestGetDependenciesForCategory:
    """Tests fuer die Abhaengigkeitsregeln pro Kategorie."""

    def setup_method(self):
        """Gemeinsame Dateiliste fuer alle Tests."""
        self.file_list = [
            "requirements.txt",  # config
            "models.py",         # models
            "database.py",       # database
            "app.py",            # core
            "routes/auth.py",    # routes
            "test_app.py",       # tests
            "run.bat",           # scripts
        ]

    def test_database_haengt_von_models_ab(self):
        """Database-Kategorie haengt nur von Models ab."""
        deps = _get_dependencies_for_category("database", self.file_list, "python")
        assert "models.py" in deps
        assert "app.py" not in deps
        assert "requirements.txt" not in deps

    def test_routes_haengt_von_core_ab(self):
        """Routes haengen von Models, Database und Core ab."""
        deps = _get_dependencies_for_category("routes", self.file_list, "python")
        assert "models.py" in deps
        assert "database.py" in deps
        assert "app.py" in deps
        assert "requirements.txt" not in deps

    def test_tests_haengen_von_allem_ab(self):
        """Tests haengen von allem ausser Tests und Scripts ab."""
        deps = _get_dependencies_for_category("tests", self.file_list, "python")
        assert "requirements.txt" in deps
        assert "models.py" in deps
        assert "database.py" in deps
        assert "app.py" in deps
        assert "routes/auth.py" in deps
        # Tests und Scripts sind NICHT in den Dependencies
        assert "test_app.py" not in deps
        assert "run.bat" not in deps

    def test_config_hat_keine_deps(self):
        """Config-Kategorie hat keine Abhaengigkeiten."""
        deps = _get_dependencies_for_category("config", self.file_list, "python")
        assert deps == []

    def test_core_haengt_von_models_und_database_ab(self):
        """Core haengt von Models und Database ab."""
        deps = _get_dependencies_for_category("core", self.file_list, "python")
        assert "models.py" in deps
        assert "database.py" in deps
        assert "requirements.txt" not in deps

    def test_scripts_haengen_von_allem_ab(self):
        """Scripts haengen von allem ausser anderen Scripts ab."""
        deps = _get_dependencies_for_category("scripts", self.file_list, "python")
        assert "models.py" in deps
        assert "app.py" in deps
        assert "test_app.py" in deps
        assert "run.bat" not in deps

    def test_components_haengen_von_types_und_models_ab(self):
        """Components haengen von Types und Models ab."""
        js_files = ["types/user.ts", "models.py", "components/App.jsx", "app.js"]
        deps = _get_dependencies_for_category("components", js_files, "javascript")
        assert "types/user.ts" in deps
        assert "models.py" in deps
        assert "components/App.jsx" not in deps


# =========================================================================
# build_dependency_graph
# =========================================================================


class TestBuildDependencyGraph:
    """Tests fuer den Aufbau des Dependency-Graphen."""

    def test_python_projekt(self):
        """Typisches Python-Projekt erzeugt korrekten Graphen."""
        files = ["requirements.txt", "models.py", "app.py", "test_app.py"]
        graph = build_dependency_graph(files, "python")

        assert len(graph) == 4
        assert "requirements.txt" in graph
        assert "models.py" in graph
        assert "app.py" in graph
        assert "test_app.py" in graph

        # Config hat keine Dependencies
        assert graph["requirements.txt"].depends_on == []

        # Models hat keine Dependencies (nur config waere moeglich, aber Regel sagt nein)
        assert graph["models.py"].depends_on == []

        # Core haengt von Models ab
        assert "models.py" in graph["app.py"].depends_on

        # Tests haengen von allem (ausser Tests/Scripts) ab
        assert "requirements.txt" in graph["test_app.py"].depends_on
        assert "models.py" in graph["test_app.py"].depends_on
        assert "app.py" in graph["test_app.py"].depends_on

    def test_tech_stack_normalisierung(self):
        """Tech-Stack wird korrekt normalisiert: flask -> python, react -> javascript."""
        files = ["requirements.txt", "app.py"]

        # Flask -> Python
        graph_flask = build_dependency_graph(files, "flask")
        assert graph_flask["requirements.txt"].priority == 0  # Python config priority

        # Django -> Python
        graph_django = build_dependency_graph(files, "Django")
        assert graph_django["requirements.txt"].priority == 0

        # React -> JavaScript
        js_files = ["package.json", "index.js"]
        graph_react = build_dependency_graph(js_files, "react")
        assert graph_react["package.json"].priority == 0  # JS config priority

        # Node -> JavaScript
        graph_node = build_dependency_graph(js_files, "node")
        assert graph_node["package.json"].priority == 0

    def test_keine_self_references(self):
        """Dateien referenzieren sich nicht selbst als Abhaengigkeit."""
        files = ["models.py", "database.py"]
        graph = build_dependency_graph(files, "python")
        # database haengt von models ab, aber nicht von sich selbst
        assert "database.py" not in graph["database.py"].depends_on

    def test_prioritaeten_korrekt(self):
        """Prioritaeten entsprechen den PRIORITY_RULES."""
        files = ["requirements.txt", "models.py", "database.py", "app.py", "test_app.py"]
        graph = build_dependency_graph(files, "python")

        assert graph["requirements.txt"].priority == 0  # config
        assert graph["models.py"].priority == 1          # models
        assert graph["database.py"].priority == 2        # database
        assert graph["app.py"].priority == 3             # core
        assert graph["test_app.py"].priority == 6        # tests


# =========================================================================
# get_parallel_batches
# =========================================================================


class TestGetParallelBatches:
    """Tests fuer die Batch-Gruppierung."""

    def test_unabhaengige_dateien(self):
        """Unabhaengige Dateien (gleiche Prioritaet) landen in einem Batch."""
        # Mehrere Config-Dateien haben keine Abhaengigkeiten und gleiche Prioritaet
        files = ["requirements.txt", "package.json", ".env"]
        graph = build_dependency_graph(files, "python")
        batches = get_parallel_batches(graph)

        # Alle Config-Dateien sollten im selben Batch sein
        assert len(batches) == 1
        assert set(batches[0]) == {"requirements.txt", "package.json", ".env"}

    def test_abhaengigkeitskette(self):
        """Abhaengigkeitskette erzeugt mehrere sequenzielle Batches."""
        files = ["requirements.txt", "models.py", "app.py", "test_app.py"]
        graph = build_dependency_graph(files, "python")
        batches = get_parallel_batches(graph)

        # Es muessen mehrere Batches sein (config -> models -> core -> tests)
        assert len(batches) > 1

        # Alle Dateien muessen in irgendeinem Batch enthalten sein
        alle_dateien = set()
        for batch in batches:
            alle_dateien.update(batch)
        assert alle_dateien == set(files)

        # Abhaengigkeiten muessen in frueheren Batches liegen
        batch_index = {}
        for i, batch in enumerate(batches):
            for f in batch:
                batch_index[f] = i

        for filename, dep in graph.items():
            for abhaengigkeit in dep.depends_on:
                assert batch_index[abhaengigkeit] < batch_index[filename], (
                    f"Erwartet: {abhaengigkeit} (Batch {batch_index[abhaengigkeit]}) "
                    f"vor {filename} (Batch {batch_index[filename]})"
                )

    def test_zyklen_werden_behandelt(self):
        """Zyklische Abhaengigkeiten fuehren nicht zu Endlosschleifen."""
        # Manuell einen Graphen mit Zyklus erstellen
        graph = {
            "a.py": FileDependency(filename="a.py", depends_on=["b.py"], priority=0),
            "b.py": FileDependency(filename="b.py", depends_on=["a.py"], priority=0),
        }
        batches = get_parallel_batches(graph)

        # Funktion darf nicht haengen bleiben
        assert len(batches) >= 1

        # Alle Dateien muessen verarbeitet worden sein
        alle_dateien = set()
        for batch in batches:
            alle_dateien.update(batch)
        assert alle_dateien == {"a.py", "b.py"}

    def test_leerer_graph(self):
        """Leerer Graph ergibt keine Batches."""
        batches = get_parallel_batches({})
        assert batches == []


# =========================================================================
# analyze_parallelization_potential
# =========================================================================


class TestAnalyzeParallelizationPotential:
    """Tests fuer die Parallelisierungs-Analyse."""

    def test_metriken(self):
        """Analyse liefert alle erwarteten Metriken."""
        files = [
            "requirements.txt",
            "models.py",
            "database.py",
            "app.py",
            "routes/auth.py",
            "test_app.py",
        ]
        result = analyze_parallelization_potential(files, "python")

        # Pflichtfelder pruefen
        assert result["total_files"] == 6
        assert result["total_batches"] >= 1
        assert result["max_parallel_per_batch"] >= 1
        assert result["theoretical_speedup"] >= 1.0

        # Speedup muss korrekt berechnet sein: total_files / total_batches
        expected_speedup = round(6 / result["total_batches"], 2)
        assert result["theoretical_speedup"] == expected_speedup

        # Batches-Details muessen vorhanden sein
        assert "batches" in result
        assert len(result["batches"]) == result["total_batches"]
        for batch_info in result["batches"]:
            assert "batch_number" in batch_info
            assert "files" in batch_info
            assert "count" in batch_info
            assert batch_info["count"] == len(batch_info["files"])

        # Kategorien muessen vorhanden sein
        assert "categories" in result
        assert "config" in result["categories"]
        assert "requirements.txt" in result["categories"]["config"]
        assert "models" in result["categories"]
        assert "models.py" in result["categories"]["models"]

    def test_einzelne_datei(self):
        """Analyse mit einer einzelnen Datei funktioniert."""
        result = analyze_parallelization_potential(["app.py"], "python")
        assert result["total_files"] == 1
        assert result["total_batches"] == 1
        assert result["theoretical_speedup"] == 1.0
        assert result["max_parallel_per_batch"] == 1

    def test_javascript_projekt(self):
        """Analyse mit JavaScript Tech-Stack funktioniert."""
        files = ["package.json", "types/user.ts", "components/App.jsx", "app.test.js"]
        result = analyze_parallelization_potential(files, "javascript")

        assert result["total_files"] == 4
        assert result["total_batches"] >= 1
        assert "categories" in result
        assert "config" in result["categories"]
        assert "package.json" in result["categories"]["config"]
