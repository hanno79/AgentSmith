# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 29.01.2026
Version: 1.1
Beschreibung: Memory Agent - Verwaltet Projekt- und Langzeiterinnerungen.
              Speichert Erkenntnisse aus Code-, Review- und Sandbox-Ergebnissen.
              ÄNDERUNG 29.01.2026: Async-Versionen (save_memory_async, update_memory_async)
              für non-blocking I/O und WebSocket-Stabilität.
"""

import os
import json
import re
import base64
import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional, TypedDict, Union

# Check if encryption is enabled
MEMORY_ENCRYPTION_ENABLED = os.getenv("MEMORY_ENCRYPTION_ENABLED", "false").lower() == "true"
MEMORY_ENCRYPTION_KEY = os.getenv("MEMORY_ENCRYPTION_KEY", None)


def _get_fernet() -> Optional['Fernet']:
    """Get Fernet instance if encryption is enabled and key is set."""
    if not MEMORY_ENCRYPTION_ENABLED or not MEMORY_ENCRYPTION_KEY:
        return None
    try:
        from cryptography.fernet import Fernet
        # Ensure key is properly formatted (base64 32-byte key)
        key = MEMORY_ENCRYPTION_KEY.encode() if isinstance(MEMORY_ENCRYPTION_KEY, str) else MEMORY_ENCRYPTION_KEY
        return Fernet(key)
    except Exception:
        return None


def _encrypt_data(data: str) -> str:
    """Encrypt data if encryption is enabled."""
    fernet = _get_fernet()
    if fernet:
        encrypted = fernet.encrypt(data.encode())
        return f"ENCRYPTED:{base64.b64encode(encrypted).decode()}"
    return data


def _decrypt_data(data: str) -> str:
    """Decrypt data if it's encrypted."""
    if data.startswith("ENCRYPTED:"):
        fernet = _get_fernet()
        if fernet:
            encrypted = base64.b64decode(data[10:])
            return fernet.decrypt(encrypted).decode()
    return data


class MemoryEntry(TypedDict):
    """Typdefinition für einen Memory-Eintrag."""
    timestamp: str
    coder_output_preview: str
    review_feedback: Optional[str]
    sandbox_feedback: Optional[str]


class Lesson(TypedDict, total=False):
    """Typdefinition für eine Lesson."""
    pattern: str
    category: str
    action: str
    tags: List[str]
    count: int
    first_seen: str
    last_seen: str


class MemoryData(TypedDict):
    """Typdefinition für Memory-Daten."""
    history: List[MemoryEntry]
    lessons: List[Lesson]


def load_memory(memory_path: str) -> MemoryData:
    """Lädt bestehendes Memory oder erstellt ein leeres. Supports encrypted files."""
    if os.path.exists(memory_path):
        with open(memory_path, "r", encoding="utf-8") as f:
            content = f.read()
        # Decrypt if encrypted, otherwise parse as-is (backwards compatible)
        decrypted_content = _decrypt_data(content)
        return json.loads(decrypted_content)
    return {"history": [], "lessons": []}


def save_memory(memory_path: str, memory_data: MemoryData) -> None:
    """Speichert das Memory dauerhaft als JSON. Encrypts if encryption is enabled."""
    dirpath = os.path.dirname(memory_path)
    if dirpath:
        os.makedirs(dirpath, exist_ok=True)
    json_content = json.dumps(memory_data, indent=2, ensure_ascii=False)
    # Encrypt if encryption is enabled
    encrypted_content = _encrypt_data(json_content)
    with open(memory_path, "w", encoding="utf-8") as f:
        f.write(encrypted_content)


# ÄNDERUNG 29.01.2026: Async-Version für non-blocking WebSocket-Stabilität
async def save_memory_async(memory_path: str, memory_data: MemoryData) -> None:
    """
    Async-Version von save_memory.
    Führt blockierende I/O und Encryption in separatem Thread aus,
    um den Event-Loop nicht zu blockieren.
    """
    def _blocking_save():
        dirpath = os.path.dirname(memory_path)
        if dirpath:
            os.makedirs(dirpath, exist_ok=True)
        json_content = json.dumps(memory_data, indent=2, ensure_ascii=False)
        encrypted_content = _encrypt_data(json_content)
        with open(memory_path, "w", encoding="utf-8") as f:
            f.write(encrypted_content)

    await asyncio.to_thread(_blocking_save)


def update_memory(
    memory_path: str,
    coder_output: str,
    review_output: Optional[str],
    sandbox_output: Optional[str] = None
) -> MemoryEntry:
    """
    Fügt neue Erkenntnisse ins Memory hinzu.
    """
    memory_data = load_memory(memory_path)

    entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "coder_output_preview": str(coder_output)[:500],
        "review_feedback": str(review_output)[:500] if review_output else None,
        "sandbox_feedback": str(sandbox_output)[:500] if sandbox_output else None
    }

    memory_data["history"].append(entry)
    save_memory(memory_path, memory_data)

    return entry


# ÄNDERUNG 29.01.2026: Async-Version für non-blocking WebSocket-Stabilität
async def update_memory_async(
    memory_path: str,
    coder_output: str,
    review_output: Optional[str],
    sandbox_output: Optional[str] = None
) -> MemoryEntry:
    """
    Async-Version von update_memory.
    Führt blockierende I/O in separatem Thread aus.
    """
    # load_memory ist schnell (read-only), bleibt synchron
    memory_data = load_memory(memory_path)

    entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "coder_output_preview": str(coder_output)[:500],
        "review_feedback": str(review_output)[:500] if review_output else None,
        "sandbox_feedback": str(sandbox_output)[:500] if sandbox_output else None
    }

    memory_data["history"].append(entry)
    await save_memory_async(memory_path, memory_data)

    return entry


def get_lessons_for_prompt(memory_path: str, tech_stack: str = None) -> str:
    """
    Lädt Lessons Learned aus dem Memory, gefiltert nach Tech-Stack.
    """
    if not os.path.exists(memory_path):
        return ""

    try:
        with open(memory_path, "r", encoding="utf-8") as f:
            content = f.read()
        # Decrypt if encrypted, otherwise parse as-is (backwards compatible)
        decrypted_content = _decrypt_data(content)
        data = json.loads(decrypted_content)
    except Exception:
        return ""

    lessons = data.get("lessons", [])
    relevant_lessons = []

    for lesson in lessons:
        # Simple keywords matching or global
        tags = lesson.get("tags", [])
        if "global" in tags:
            relevant_lessons.append(lesson["action"])
            continue
        
        # Check if tags match current tech stack (e.g. "flask" in "python/flask")
        if tech_stack:
            for tag in tags:
                if tag.lower() in tech_stack.lower():
                    relevant_lessons.append(lesson["action"])
                    break
    
    if not relevant_lessons:
        return ""

    return "\n".join([f"- [MEMORY]: {l}" for l in relevant_lessons])


def learn_from_error(memory_path: str, error_msg: str, tags: List[str]) -> str:
    """
    Fügt eine neue Lektion basierend auf einem Fehler hinzu.
    Nutzt verbesserte Duplikat-Erkennung und Action-Text-Generierung.
    """
    try:
        if not error_msg or not error_msg.strip():
            return "Kein Fehler zum Lernen angegeben."

        if os.path.exists(memory_path):
            with open(memory_path, "r", encoding="utf-8") as f:
                content = f.read()
            # Decrypt if encrypted, otherwise parse as-is (backwards compatible)
            decrypted_content = _decrypt_data(content)
            data = json.loads(decrypted_content)
        else:
            data = {"lessons": [], "history": []}

        # Extrahiere das Kernmuster
        error_pattern = extract_error_pattern(error_msg) if error_msg else ""
        if not error_pattern:
            error_pattern = error_msg[:100]

        # Check für exakte Duplikate (Pattern bereits bekannt)
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
            return match.group(1).strip()[:200]  # Limit auf 200 Zeichen

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


def is_duplicate_lesson(memory_path: str, error_pattern: Optional[Union[str, re.Pattern]], similarity_threshold: float = 0.6) -> bool:
    """
    Prüft ob eine ähnliche Lesson bereits existiert um Duplikate zu vermeiden.
    Verwendet einfaches Substring-Matching und Wort-Überlappung.
    """
    if not os.path.exists(memory_path):
        return False

    # Explizite Typ-Validierung: Prüfe auf None oder ungültige Typen
    if error_pattern is None:
        return False
    
    # Prüfe ob es ein String oder kompiliertes Regex-Pattern ist
    if not isinstance(error_pattern, (str, re.Pattern)):
        return False
    
    # Konvertiere kompiliertes Pattern zu String falls nötig
    if isinstance(error_pattern, re.Pattern):
        error_pattern = error_pattern.pattern
    
    # Prüfe auf leeren String nach Konvertierung
    if not error_pattern:
        return False

    try:
        with open(memory_path, "r", encoding="utf-8") as f:
            content = f.read()
        # Decrypt if encrypted, otherwise parse as-is (backwards compatible)
        decrypted_content = _decrypt_data(content)
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
    Kennt bekannte Muster mit spezifischen Ratschlägen.
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
