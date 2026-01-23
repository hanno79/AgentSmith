# -*- coding: utf-8 -*-
"""
Memory-Agent: verwaltet Projekt- und Langzeiterinnerungen.
Speichert Erkenntnisse aus Code-, Review- und Sandbox-Ergebnissen.
"""

import os
import json
from datetime import datetime


def load_memory(memory_path: str):
    """Lädt bestehendes Memory oder erstellt ein leeres."""
    if os.path.exists(memory_path):
        with open(memory_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"history": [], "lessons": []}


def save_memory(memory_path: str, memory_data: dict):
    """Speichert das Memory dauerhaft als JSON."""
    os.makedirs(os.path.dirname(memory_path), exist_ok=True)
    with open(memory_path, "w", encoding="utf-8") as f:
        json.dump(memory_data, f, indent=2, ensure_ascii=False)


def update_memory(memory_path: str, coder_output: str, review_output: str, sandbox_output: str = None):
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


def get_lessons_for_prompt(memory_path: str, tech_stack: str = None) -> str:
    """
    Lädt Lessons Learned aus dem Memory, gefiltert nach Tech-Stack.
    """
    if not os.path.exists(memory_path):
        return ""

    try:
        with open(memory_path, "r", encoding="utf-8") as f:
            data = json.load(f)
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


def learn_from_error(memory_path: str, error_msg: str, tags: list):
    """
    Fügt eine neue Lektion basierend auf einem Fehler hinzu.
    """
    try:
        if os.path.exists(memory_path):
            with open(memory_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = {"lessons": []}
        
        # Check duplicates
        for l in data.get("lessons", []):
            if l["pattern"] in error_msg:
                l["count"] = l.get("count", 0) + 1
                l["last_seen"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                save_memory(memory_path, data)
                return f"Bekannter Fehler aktualisiert: {l['pattern']}"

        # New Lesson
        new_lesson = {
            "pattern": error_msg[:100], 
            "category": "error",
            "action": f"VERMEIDE FEHLER: {error_msg[:200]}...",
            "tags": tags,
            "count": 1,
            "first_seen": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "last_seen": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        if "lessons" not in data:
            data["lessons"] = []
            
        data["lessons"].append(new_lesson)
        save_memory(memory_path, data)
        return "Neue Lektion gelernt und gespeichert."

    except Exception as e:
        return f"Fehler beim Lernen: {e}"
