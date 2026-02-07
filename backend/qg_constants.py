# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 01.02.2026
Version: 1.1
Beschreibung: Quality Gate Konstanten und Keyword-Mappings.
              Extrahiert aus quality_gate.py (Regel 1: Max 500 Zeilen)
              ÄNDERUNG 02.02.2026: Quality-Gate-Konstanten aus quality_gate.py ausgelagert
              ÄNDERUNG 03.02.2026: LANGUAGE_TEST_CONFIG für dynamische Test-Erkennung
"""

from typing import Dict, List


# Keyword-Mappings für Anforderungs-Extraktion
DB_KEYWORDS: Dict[str, str] = {
    "sqlite": "sqlite", "postgres": "postgres", "postgresql": "postgres",
    "mysql": "mysql", "mariadb": "mysql", "mongodb": "mongodb", "mongo": "mongodb",
    "redis": "redis", "elasticsearch": "elasticsearch", "neo4j": "neo4j",
    "datenbank": "generic_db", "database": "generic_db"
}

LANG_KEYWORDS: Dict[str, str] = {
    "python": "python", "javascript": "javascript", "typescript": "javascript",
    "node": "javascript", "java": "java", "kotlin": "kotlin",
    "go": "go", "golang": "go", "rust": "rust", "c++": "cpp", "c#": "csharp"
}

FRAMEWORK_KEYWORDS: Dict[str, str] = {
    "flask": "flask", "fastapi": "fastapi", "django": "django",
    "express": "express", "react": "react", "vue": "vue", "angular": "angular",
    "tkinter": "tkinter", "pyqt": "pyqt", "electron": "electron",
    "streamlit": "streamlit", "gradio": "gradio"
}

UI_TYPE_KEYWORDS: Dict[str, List[str]] = {
    "desktop": ["desktop", "fenster", "gui", "window"],
    "webapp": ["webapp", "website", "webseite", "browser", "web app"],
    "api": ["api", "rest", "endpoint", "backend", "service"],
    "cli": ["cli", "kommandozeile", "terminal", "console", "command line"]
}

# Severity-Order für Security-Validierung
SEVERITY_ORDER = ["critical", "high", "medium", "low", "info"]

# Severity-Gewichtung für Score-Berechnung
SEVERITY_WEIGHTS = {
    "critical": 0.4,
    "high": 0.25,
    "medium": 0.1,
    "low": 0.05,
    "info": 0.01
}

# Framework-Indikatoren für Code-Validierung
FRAMEWORK_INDICATORS = {
    "flask": ["from flask", "import flask", "Flask("],
    "fastapi": ["from fastapi", "import fastapi", "FastAPI("],
    "tkinter": ["import tkinter", "from tkinter", "Tk("],
    "pyqt": ["PyQt", "from PyQt", "QApplication"]
}

# Datenbank-Indikatoren für Code-Validierung
DB_INDICATORS = {
    "sqlite": ["sqlite", "sqlite3", "database", ".db"],
    "postgres": ["postgres", "psycopg", "asyncpg", "pg_"],
    "mysql": ["mysql", "pymysql", "mariadb"],
    "mongodb": ["mongo", "pymongo", "collection"]
}

# Gültige Agent-Statuses
VALID_AGENT_STATUSES = ["working", "waiting", "completed", "failed", "blocked"]


# =========================================================================
# ÄNDERUNG 03.02.2026: Test-Konfiguration pro Sprache/Framework
# Ermöglicht dynamische Test-Erkennung für alle unterstützten Techstacks
# =========================================================================

LANGUAGE_TEST_CONFIG: Dict[str, Dict] = {
    "python": {
        "test_patterns": ["test_*.py", "*_test.py"],
        "code_extensions": [".py"],
        "test_command": "pytest",
        "skip_patterns": ["test_", "_test.py", "conftest.py"],
    },
    "javascript": {
        "test_patterns": ["*.test.js", "*.spec.js", "*.test.ts", "*.spec.ts",
                         "*.test.jsx", "*.spec.jsx", "*.test.tsx", "*.spec.tsx"],
        "code_extensions": [".js", ".ts", ".jsx", ".tsx"],
        "test_command": "npm test",
        "skip_patterns": [".test.", ".spec."],
    },
    "csharp": {  # .NET / C# / Excel-Addins / VSTO
        "test_patterns": ["*Tests.cs", "*Test.cs", "*.Tests.dll"],
        "code_extensions": [".cs", ".vb"],
        "test_command": "dotnet test",
        "skip_patterns": ["Tests.cs", "Test.cs"],
    },
    "php": {
        "test_patterns": ["*Test.php", "test_*.php"],
        "code_extensions": [".php"],
        "test_command": "phpunit",
        "skip_patterns": ["Test.php", "test_"],
    },
    "cpp": {  # C/C++
        "test_patterns": ["*_test.cpp", "test_*.cpp", "*_test.c", "test_*.c"],
        "code_extensions": [".cpp", ".c", ".h", ".hpp", ".cc", ".cxx"],
        "test_command": "ctest",
        "skip_patterns": ["_test.", "test_"],
    },
    "go": {
        "test_patterns": ["*_test.go"],
        "code_extensions": [".go"],
        "test_command": "go test ./...",
        "skip_patterns": ["_test.go"],
    },
    "rust": {
        "test_patterns": ["*_test.rs"],
        "code_extensions": [".rs"],
        "test_command": "cargo test",
        "skip_patterns": ["_test.rs"],
    },
    "java": {
        "test_patterns": ["*Test.java", "*Tests.java", "*IT.java"],
        "code_extensions": [".java"],
        "test_command": "mvn test",
        "skip_patterns": ["Test.java", "Tests.java", "IT.java"],
    },
    "kotlin": {
        "test_patterns": ["*Test.kt", "*Tests.kt"],
        "code_extensions": [".kt", ".kts"],
        "test_command": "gradle test",
        "skip_patterns": ["Test.kt", "Tests.kt"],
    },
    "ruby": {
        "test_patterns": ["*_test.rb", "test_*.rb", "*_spec.rb"],
        "code_extensions": [".rb"],
        "test_command": "rake test",
        "skip_patterns": ["_test.rb", "test_", "_spec.rb"],
    },
    "swift": {
        "test_patterns": ["*Tests.swift", "*Test.swift"],
        "code_extensions": [".swift"],
        "test_command": "swift test",
        "skip_patterns": ["Tests.swift", "Test.swift"],
    },
    "static": {  # HTML/CSS only - keine Unit-Tests
        "test_patterns": [],
        "code_extensions": [".html", ".css", ".htm"],
        "test_command": None,  # Nur UI-Tests via Playwright
        "skip_patterns": [],
    },
}

# Mapping von project_type/language/framework → Config-Key
LANGUAGE_MAPPING: Dict[str, str] = {
    # Python
    "python": "python", "python_script": "python", "python_cli": "python",
    "flask": "python", "flask_app": "python", "fastapi": "python",
    "fastapi_app": "python", "django": "python", "django_app": "python",
    "tkinter": "python", "tkinter_desktop": "python",
    "pyqt": "python", "pyqt_desktop": "python", "pyside": "python",
    "streamlit": "python", "gradio": "python",
    # JavaScript/TypeScript
    "javascript": "javascript", "typescript": "javascript",
    "nodejs": "javascript", "nodejs_app": "javascript", "node": "javascript",
    "nodejs_express": "javascript", "express": "javascript",
    "react": "javascript", "react_app": "javascript",
    "vue": "javascript", "vue_app": "javascript",
    "angular": "javascript", "angular_app": "javascript",
    "electron": "javascript", "electron_app": "javascript",
    "nextjs": "javascript", "nuxt": "javascript",
    # .NET / C#
    "csharp": "csharp", "c#": "csharp", "dotnet": "csharp", ".net": "csharp",
    "aspnet": "csharp", "asp.net": "csharp", "blazor": "csharp",
    "excel_addin": "csharp", "vsto": "csharp", "office_addin": "csharp",
    "wpf": "csharp", "winforms": "csharp", "maui": "csharp",
    # PHP
    "php": "php", "php_app": "php",
    "laravel": "php", "symfony": "php", "wordpress": "php",
    # C/C++
    "cpp": "cpp", "c++": "cpp", "c": "cpp",
    "qt": "cpp", "qt_app": "cpp",
    # Go
    "go": "go", "golang": "go", "go_app": "go",
    # Rust
    "rust": "rust", "rust_app": "rust",
    # Java
    "java": "java", "java_app": "java",
    "spring": "java", "springboot": "java", "spring_boot": "java",
    # Kotlin
    "kotlin": "kotlin", "kotlin_app": "kotlin",
    # Ruby
    "ruby": "ruby", "ruby_app": "ruby",
    "rails": "ruby", "ruby_on_rails": "ruby",
    # Swift
    "swift": "swift", "swift_app": "swift",
    "ios": "swift", "macos_app": "swift",
    # Static
    "static_html": "static", "html": "static", "css": "static",
    "static": "static", "landing_page": "static",
}


def get_test_config_for_project(tech_blueprint: Dict) -> Dict:
    """
    Ermittelt die Test-Konfiguration basierend auf tech_blueprint.

    Priorität: language > framework > project_type > Fallback (Python)

    Args:
        tech_blueprint: Blueprint mit project_type, language, framework

    Returns:
        Test-Config dict mit test_patterns, code_extensions, test_command, skip_patterns
    """
    if not tech_blueprint:
        return LANGUAGE_TEST_CONFIG["python"]

    # Extrahiere relevante Felder (lowercase für Matching)
    language = str(tech_blueprint.get("language", "")).lower().strip()
    framework = str(tech_blueprint.get("framework", "")).lower().strip()
    project_type = str(tech_blueprint.get("project_type", "")).lower().strip()

    # Suche in Prioritäts-Reihenfolge
    for key in [language, framework, project_type]:
        if key and key in LANGUAGE_MAPPING:
            config_key = LANGUAGE_MAPPING[key]
            if config_key in LANGUAGE_TEST_CONFIG:
                return LANGUAGE_TEST_CONFIG[config_key]

    # Fallback: Python (häufigstes Szenario)
    return LANGUAGE_TEST_CONFIG["python"]
