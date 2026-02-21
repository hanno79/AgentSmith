# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 24.01.2026
Version: 1.1
Beschreibung: Pytest Fixtures - Gemeinsame Test-Konfiguration und Fixtures fuer AgentSmith Tests.

              AENDERUNG 05.02.2026 v1.1: sample_memory_data erweitert
              - domain_vocabulary und known_data_sources hinzugefuegt
"""

import os
import sys
import json
import pytest
import tempfile
import shutil

# Fuege Projekt-Root zum Python-Path hinzu
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def temp_dir():
    """Erstellt ein temporaeres Verzeichnis fuer Tests."""
    dir_path = tempfile.mkdtemp()
    yield dir_path
    shutil.rmtree(dir_path, ignore_errors=True)


@pytest.fixture
def temp_memory_file(temp_dir):
    """Erstellt eine temporaere Memory-Datei."""
    memory_path = os.path.join(temp_dir, "memory", "test_memory.json")
    # Erstelle Verzeichnis falls nicht vorhanden
    memory_dir = os.path.dirname(memory_path)
    if memory_dir:
        os.makedirs(memory_dir, exist_ok=True)
    yield memory_path


@pytest.fixture
def sample_memory_data():
    """Beispiel-Memory-Daten fuer Tests."""
    # AENDERUNG 05.02.2026: Struktur wurde am 01.02.2026 erweitert
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
        ],
        # AENDERUNG 05.02.2026: Neue Felder hinzugefuegt
        "domain_vocabulary": [],
        "known_data_sources": []
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
    """Beispiel-Konfiguration fuer Tests."""
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
                "reviewer": ["Pruefe Imports"]
            }
        }
    }


@pytest.fixture
def valid_python_code():
    """Gueltiger Python-Code fuer Sandbox-Tests."""
    return '''
def hello_world():
    """Simple hello world function."""
    print("Hello, World!")

if __name__ == "__main__":
    hello_world()
'''


@pytest.fixture
def invalid_python_code():
    """Ungueltiger Python-Code fuer Sandbox-Tests."""
    return '''
def broken_function(
    print("Missing closing parenthesis"
'''


@pytest.fixture
def valid_html_code():
    """Gueltiger HTML-Code fuer Sandbox-Tests."""
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
    """Unvollstaendiger HTML-Code fuer Sandbox-Tests."""
    return '''<!DOCTYPE html>
<html>
<head>
    <title>Test Page</title>
</head>
<body>
    <h1>Missing closing tags
</body>
</html>'''  # NOTE: h1 tag is not closed - but this is still accepted by simple validator


# NOTE: The HTML validator in sandbox_runner.py only checks for <html> and </html> presence,
# not proper tag nesting. For truly invalid HTML, we need to remove </html>:


# =========================================================================
# AENDERUNG 14.02.2026: Phase 0 Test-Coverage-Plan — Neue Fixtures
# =========================================================================

@pytest.fixture
def sample_tech_blueprint():
    """Beispiel Next.js Tech-Blueprint fuer DevLoop-Tests."""
    return {
        "project_type": "webapp",
        "framework": "Next.js",
        "language": "javascript",
        "styling": "tailwindcss",
        "database": "sqlite",
        "container_id": "#__next"
    }


@pytest.fixture
def sample_code_dict():
    """Beispiel code_dict mit typischen Next.js Projekt-Dateien."""
    return {
        "app/page.js": """'use client'
import { useState, useEffect } from 'react'

export default function Home() {
  const [items, setItems] = useState([])
  return <div><h1>Meine App</h1></div>
}
""",
        "app/layout.js": """export default function RootLayout({ children }) {
  return (
    <html lang="de" suppressHydrationWarning>
      <body suppressHydrationWarning>{children}</body>
    </html>
  )
}
""",
        "lib/db.js": """import Database from 'better-sqlite3'
const db = new Database('data/app.db')
export function getItems() { return db.prepare('SELECT * FROM items').all() }
export function addItem(name) { return db.prepare('INSERT INTO items (name) VALUES (?)').run(name) }
""",
        "app/api/items/route.js": """import { getItems, addItem } from '../../../lib/db'
import { NextResponse } from 'next/server'

export async function GET() {
  const items = getItems()
  return NextResponse.json(items)
}

export async function POST(request) {
  const { name } = await request.json()
  addItem(name)
  return NextResponse.json({ success: true })
}
""",
        "package.json": '{"name": "test-app", "dependencies": {"next": "14.2.0", "react": "18.2.0"}}',
    }


@pytest.fixture
def sample_feedback():
    """Beispiel Reviewer-Feedback mit [DATEI:xxx] Markern."""
    return """REVIEW-ERGEBNIS: NICHT BESTANDEN

BETROFFENE DATEIEN:
- [DATEI:app/page.js] — fehlende Error-Boundary
- [DATEI:lib/db.js] — SQL-Injection Risiko bei addItem()
- `app/api/items/route.js` — fehlende Input-Validierung

DETAILS:
1. app/page.js: Die useState-Initialisierung braucht Error-Handling
2. lib/db.js hat SQL-Injection via string concatenation
"""


@pytest.fixture
def sample_coder_output():
    """Beispiel Multi-File Coder-Output mit ### FILENAME: Markern."""
    return """### FILENAME: app/page.js
'use client'
import { useState, useEffect } from 'react'

export default function Home() {
  const [items, setItems] = useState([])
  useEffect(() => {
    fetch('/api/items').then(r => r.json()).then(setItems)
  }, [])
  return <div><h1>Items</h1></div>
}

### FILENAME: lib/db.js
import Database from 'better-sqlite3'
const db = new Database('data/app.db')
export function getItems() { return db.prepare('SELECT * FROM items').all() }
"""


@pytest.fixture
def mock_manager(temp_dir):
    """Mock-Manager mit allen DevLoop-relevanten Attributen."""
    from unittest.mock import MagicMock
    manager = MagicMock()
    manager.project_path = temp_dir
    manager.current_code = ""
    manager.iteration = 0
    manager.max_iterations = 50
    manager.tech_blueprint = {
        "project_type": "webapp",
        "framework": "Next.js",
        "language": "javascript",
    }
    manager.config = {"mode": "test"}
    manager._file_feedback_counter = {}
    manager._iteration_history = []
    manager._utds_protected_files = set()
    manager._fbf_created_files = []
    return manager
