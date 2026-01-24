# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 24.01.2026
Version: 1.0
Beschreibung: Pytest Fixtures - Gemeinsame Test-Konfiguration und Fixtures für AgentSmith Tests.
"""

import os
import sys
import json
import pytest
import tempfile
import shutil

# Füge Projekt-Root zum Python-Path hinzu
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def temp_dir():
    """Erstellt ein temporäres Verzeichnis für Tests."""
    dir_path = tempfile.mkdtemp()
    yield dir_path
    shutil.rmtree(dir_path, ignore_errors=True)


@pytest.fixture
def temp_memory_file(temp_dir):
    """Erstellt eine temporäre Memory-Datei."""
    memory_path = os.path.join(temp_dir, "memory", "test_memory.json")
    # Erstelle Verzeichnis falls nicht vorhanden
    memory_dir = os.path.dirname(memory_path)
    if memory_dir:
        os.makedirs(memory_dir, exist_ok=True)
    yield memory_path


@pytest.fixture
def sample_memory_data():
    """Beispiel-Memory-Daten für Tests."""
    return {
        "history": [
            {
                "timestamp": "2026-01-23 10:00:00",
                "coder_output_preview": "def hello(): print('Hello')",
                "review_feedback": "Code looks good",
                "sandbox_feedback": "Python-Syntax OK"
            }
        ],
        "lessons": [
            {
                "pattern": "ModuleNotFoundError",
                "category": "error",
                "action": "VERMEIDE FEHLER: Modul nicht gefunden",
                "tags": ["global", "python"],
                "count": 2,
                "first_seen": "2026-01-22 09:00:00",
                "last_seen": "2026-01-23 10:00:00"
            },
            {
                "pattern": "Flask app context",
                "category": "error",
                "action": "VERMEIDE FEHLER: Verwende app.app_context()",
                "tags": ["flask", "webapp"],
                "count": 1,
                "first_seen": "2026-01-23 11:00:00",
                "last_seen": "2026-01-23 11:00:00"
            }
        ]
    }


@pytest.fixture
def populated_memory_file(temp_dir, sample_memory_data):
    """Erstellt eine Memory-Datei mit Beispieldaten."""
    memory_dir = os.path.join(temp_dir, "memory")
    os.makedirs(memory_dir, exist_ok=True)
    memory_path = os.path.join(memory_dir, "test_memory.json")

    with open(memory_path, "w", encoding="utf-8") as f:
        json.dump(sample_memory_data, f, indent=2, ensure_ascii=False)

    yield memory_path


@pytest.fixture
def sample_config():
    """Beispiel-Konfiguration für Tests."""
    return {
        "mode": "test",
        "project_type": "webapp",
        "include_designer": True,
        "max_retries": 3,
        "models": {
            "test": {
                "meta_orchestrator": "test-model",
                "coder": "test-model",
                "reviewer": "test-model",
                "designer": "test-model",
                "researcher": "test-model",
                "database_designer": "test-model",
                "techstack_architect": "test-model",
                "security": "test-model"
            }
        },
        "templates": {
            "webapp": {
                "global": ["PEP8 einhalten"],
                "coder": ["Erstelle requirements.txt"],
                "reviewer": ["Prüfe Imports"]
            }
        }
    }


@pytest.fixture
def valid_python_code():
    """Gültiger Python-Code für Sandbox-Tests."""
    return '''
def hello_world():
    """Simple hello world function."""
    print("Hello, World!")

if __name__ == "__main__":
    hello_world()
'''


@pytest.fixture
def invalid_python_code():
    """Ungültiger Python-Code für Sandbox-Tests."""
    return '''
def broken_function(
    print("Missing closing parenthesis"
'''


@pytest.fixture
def valid_html_code():
    """Gültiger HTML-Code für Sandbox-Tests."""
    return '''<!DOCTYPE html>
<html>
<head>
    <title>Test Page</title>
</head>
<body>
    <h1>Hello World</h1>
</body>
</html>'''


@pytest.fixture
def invalid_html_code():
    """Unvollständiger HTML-Code für Sandbox-Tests."""
    return '''<!DOCTYPE html>
<html>
<head>
    <title>Test Page</title>
</head>
<body>
    <h1>Missing closing tags'''
