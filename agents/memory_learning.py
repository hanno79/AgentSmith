# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 01.02.2026
Version: 1.0
Beschreibung: Memory Agent Lern-Funktionen.
              Extrahiert aus memory_agent.py (Regel 1: Max 500 Zeilen)

              Enthält:
              - learn_from_error
              - extract_error_pattern
              - generate_tags_from_context
              - is_duplicate_lesson
              - _generate_action_text
"""

import os
import re
import json
from datetime import datetime
from typing import Dict, List, Optional, Union

from agents.memory_encryption import decrypt_data
from agents.memory_core import load_memory, save_memory


def extract_error_pattern(error_text: str) -> str:
    """
    Extrahiert ein aussagekräftiges Fehlermuster aus Raw-Error-Output.
    Fokussiert auf die Kernfehlermeldung, nicht den vollen Traceback.
    """
    if not error_text:
        return ""

    # Bekannte Fehlermuster zum Extrahieren
    patterns = [
        # Python Errors
        r'((?:TypeError|ValueError|NameError|SyntaxError|ImportError|ModuleNotFoundError|AttributeError|KeyError|IndexError|RuntimeError|FileNotFoundError):\s*[^\n]+)',
        # Sandbox Marker
        r'❌\s*([^\n]+)',
        # JavaScript Errors
        r'(SyntaxError:\s*[^\n]+)',
        r'(ReferenceError:\s*[^\n]+)',
        # Generische Error-Zeilen
        r'(Error:\s*[^\n]+)',
        r'(Fehler:\s*[^\n]+)',  # Deutsche Fehlerpräfixe
    ]

    for pattern in patterns:
        match = re.search(pattern, error_text, re.IGNORECASE)
        if match:
            return match.group(1).strip()[:200]

    # Fallback: Erste Zeile nach ❌ oder "error"
    lines = error_text.split('\n')
    for line in lines:
        if '❌' in line or 'error' in line.lower():
            return line.strip()[:200]

    # Ultimativer Fallback
    return error_text.strip()[:200]


def generate_tags_from_context(tech_blueprint: dict, error_text: str) -> List[str]:
    """
    Generiert passende Tags basierend auf Tech-Stack und Fehlerkontext.
    """
    tags = ["global"]  # Immer global für projektübergreifende Sichtbarkeit

    if not tech_blueprint:
        tech_blueprint = {}

    # Sprach-Tag hinzufügen
    language = tech_blueprint.get("language", "").lower()
    if language:
        tags.append(language)

    # Projekt-Typ hinzufügen
    project_type = tech_blueprint.get("project_type", "").lower()
    if project_type:
        tags.append(project_type)

    # Framework-Tags aus tech_blueprint
    frameworks = tech_blueprint.get("framework", "")
    if isinstance(frameworks, str):
        frameworks = [frameworks] if frameworks else []
    for fw in frameworks:
        if fw:
            tags.append(fw.lower())

    # Frameworks aus Fehlertext erkennen
    error_lower = (error_text or "").lower()
    framework_keywords = {
        "flask": ["flask", "werkzeug", "jinja2"],
        "fastapi": ["fastapi", "starlette", "uvicorn"],
        "django": ["django"],
        "react": ["react", "jsx"],
        "node": ["node", "npm", "express"],
        "vue": ["vue"],
        "angular": ["angular"],
    }

    for fw, keywords in framework_keywords.items():
        if any(kw in error_lower for kw in keywords):
            if fw not in tags:
                tags.append(fw)

    # Kategorie basierend auf Fehlertyp
    if "syntax" in error_lower:
        tags.append("syntax")
    if "import" in error_lower or "module" in error_lower:
        tags.append("import")
    if "security" in error_lower or "csrf" in error_lower or "xss" in error_lower:
        tags.append("security")

    return list(set(tags))  # Duplikate entfernen


def is_duplicate_lesson(
    memory_path: str,
    error_pattern: Optional[Union[str, re.Pattern]],
    similarity_threshold: float = 0.6
) -> bool:
    """
    Prüft ob eine ähnliche Lesson bereits existiert um Duplikate zu vermeiden.
    """
    if not os.path.exists(memory_path):
        return False

    # Explizite Typ-Validierung
    if error_pattern is None:
        return False

    if not isinstance(error_pattern, (str, re.Pattern)):
        return False

    # Konvertiere kompiliertes Pattern zu String falls nötig
    if isinstance(error_pattern, re.Pattern):
        error_pattern = error_pattern.pattern

    if not error_pattern:
        return False

    try:
        with open(memory_path, "r", encoding="utf-8") as f:
            content = f.read()
        decrypted_content = decrypt_data(content)
        data = json.loads(decrypted_content)
    except Exception:
        return False

    error_lower = error_pattern.lower()
    error_words = set(error_lower.split())

    for lesson in data.get("lessons", []):
        existing_pattern = lesson.get("pattern", "").lower()

        # Exakte Match-Prüfung
        if existing_pattern in error_lower or error_lower in existing_pattern:
            return True

        # Wort-Überlappungs-Prüfung
        existing_words = set(existing_pattern.split())
        if len(error_words) > 0 and len(existing_words) > 0:
            overlap = len(error_words & existing_words) / max(len(error_words), len(existing_words))
            if overlap >= similarity_threshold:
                return True

    return False


def _generate_action_text(error_msg: str) -> str:
    """
    Generiert einen hilfreichen Aktionstext aus einer Fehlermeldung.
    """
    if not error_msg:
        return "VERMEIDE: Unbekannter Fehler aufgetreten."

    # Bekannte Fehlermuster mit spezifischen Ratschlägen
    known_patterns = {
        "before_first_request": "VERMEIDE 'before_first_request' (Flask Deprecated). Nutze stattdessen 'with app.app_context()' für Initialisierungen.",
        "cannot import name 'markup' from 'flask'": "IMPORTIERE Markup von 'markupsafe' (from markupsafe import Markup), NICHT von flask.",
        "enumerate' is undefined": "Stelle sicher, dass 'enumerate' in Jinja2 verfügbar ist: app.jinja_env.globals.update(enumerate=enumerate)",
        "modulenotfounderror": "Prüfe ob das Modul in requirements.txt/package.json enthalten ist und installiert wurde.",
        "syntaxerror": "Prüfe Klammern, Einrückungen und Anführungszeichen im Code.",
        "importerror": "Prüfe den Import-Pfad und ob das Modul installiert ist.",
        "typeerror": "Prüfe die Datentypen der übergebenen Argumente.",
        "nameerror": "Prüfe ob die Variable/Funktion definiert ist bevor sie verwendet wird.",
        "keyerror": "Prüfe ob der Schlüssel im Dictionary existiert (nutze .get() mit Default).",
        "attributeerror": "Prüfe ob das Objekt das angeforderte Attribut/Methode besitzt.",
    }

    error_lower = (error_msg or "").lower()
    for pattern, advice in known_patterns.items():
        if pattern in error_lower:
            return advice

    # Generischer Aktionstext
    return f"VERMEIDE: {error_msg[:180]}..."


def learn_from_error(memory_path: str, error_msg: str, tags: List[str]) -> str:
    """
    Fügt eine neue Lektion basierend auf einem Fehler hinzu.
    """
    try:
        if not error_msg or not error_msg.strip():
            return "Kein Fehler zum Lernen angegeben."

        if os.path.exists(memory_path):
            with open(memory_path, "r", encoding="utf-8") as f:
                content = f.read()
            decrypted_content = decrypt_data(content)
            data = json.loads(decrypted_content)
        else:
            data = {"lessons": [], "history": []}

        # Extrahiere das Kernmuster
        error_pattern = extract_error_pattern(error_msg) if error_msg else ""
        if not error_pattern:
            error_pattern = error_msg[:100]

        # Check für exakte Duplikate
        for l in data.get("lessons", []):
            existing_pattern = l.get("pattern", "").lower()
            if existing_pattern in error_pattern.lower() or error_pattern.lower()[:50] in existing_pattern:
                l["count"] = l.get("count", 0) + 1
                l["last_seen"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                save_memory(memory_path, data)
                return f"Bekannter Fehler aktualisiert: {l['pattern'][:50]}..."

        # Check für ähnliche Patterns (Fuzzy-Match)
        if is_duplicate_lesson(memory_path, error_pattern):
            return "Ähnlicher Fehler bereits bekannt - übersprungen."

        # Neue Lesson mit verbessertem Action-Text
        action_text = _generate_action_text(error_pattern)

        new_lesson = {
            "pattern": error_pattern[:100],
            "category": "error",
            "action": action_text,
            "tags": tags if tags else ["global"],
            "count": 1,
            "first_seen": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "last_seen": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        if "lessons" not in data:
            data["lessons"] = []

        data["lessons"].append(new_lesson)
        save_memory(memory_path, data)
        return f"Neue Lektion gelernt: {error_pattern[:50]}..."

    except Exception as e:
        return f"Fehler beim Lernen: {e}"
