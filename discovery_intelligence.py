# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 01.02.2026
Version: 1.0
Beschreibung: Memory-basierter Option Generator fuer Discovery Session.
              Extrahiert aus discovery_session.py (Regel 1: Max 500 Zeilen)
"""

from typing import Dict, List

from discovery_models import AnswerOption

# Memory-Agent Integration
try:
    from agents.memory_agent import load_memory, get_lessons_for_prompt
    MEMORY_AVAILABLE = True
except ImportError:
    MEMORY_AVAILABLE = False


class OptionGenerator:
    """Generiert intelligente Optionen aus Memory, Researcher und Standards."""

    def __init__(self, memory_path: str = None):
        self.memory_path = memory_path
        self._memory_cache = None

    def _load_memory(self) -> Dict:
        """Laedt Memory-Daten mit Caching."""
        if self._memory_cache is not None:
            return self._memory_cache

        if not MEMORY_AVAILABLE or not self.memory_path:
            return {"history": [], "lessons": []}

        try:
            self._memory_cache = load_memory(self.memory_path)
            return self._memory_cache
        except Exception:
            return {"history": [], "lessons": []}

    def enhance_options_from_memory(
        self,
        base_options: List[AnswerOption],
        context: Dict,
        category: str
    ) -> List[AnswerOption]:
        """
        Erweitert Basis-Optionen mit Vorschlaegen aus dem Memory.

        Prioritaet:
        1. Memory-Agent (hoechste) - "In deinem letzten Projekt..."
        2. Researcher - Best Practices aus Web
        3. Vordefinierte Standards (Fallback)
        """
        memory = self._load_memory()
        enhanced = list(base_options)

        # Suche relevante Lessons im Memory
        lessons = memory.get("lessons", [])
        history = memory.get("history", [])

        for lesson in lessons:
            tags = lesson.get("tags", [])

            # Pruefe ob Lesson zum Kontext passt
            if category in tags or any(t in str(context).lower() for t in tags):
                # Erstelle Option aus Lesson
                action = lesson.get("action", "")
                if action and len(action) > 10:
                    # Pruefe ob aehnliche Option bereits existiert
                    exists = any(action.lower() in opt.text.lower() for opt in enhanced)
                    if not exists:
                        enhanced.insert(0, AnswerOption(
                            text=f"[Memory] {action[:80]}...",
                            value=f"memory_{lesson.get('pattern', 'unknown')[:30]}",
                            is_recommended=True,
                            reason=f"Basierend auf {lesson.get('count', 1)} frueheren Erfahrungen",
                            source="memory"
                        ))
                        break  # Nur eine Memory-Option pro Frage

        # Analysiere History fuer haeufige Patterns
        if history and len(history) >= 3:
            # Extrahiere Tech-Stack aus letzten Projekten
            recent_tech = self._extract_recent_tech(history[-5:])
            if recent_tech and category == "technical":
                for tech in recent_tech[:2]:
                    exists = any(tech.lower() in opt.text.lower() for opt in enhanced)
                    if not exists:
                        enhanced.insert(1, AnswerOption(
                            text=f"[Zuletzt verwendet] {tech}",
                            value=f"recent_{tech.lower()}",
                            is_recommended=False,
                            reason="In frueheren Projekten verwendet",
                            source="memory"
                        ))

        return enhanced[:7]  # Max 7 Optionen

    def _extract_recent_tech(self, history: List[Dict]) -> List[str]:
        """Extrahiert Tech-Stack aus History."""
        tech_keywords = ["python", "javascript", "react", "flask", "fastapi",
                        "django", "node", "typescript", "vue", "angular"]
        found = []

        for entry in history:
            code = entry.get("coder_output_preview", "").lower()
            for tech in tech_keywords:
                if tech in code and tech not in found:
                    found.append(tech.capitalize())

        return found

    def get_context_recommendations(self, vision: str) -> Dict[str, str]:
        """Analysiert Vision und gibt kontextbasierte Empfehlungen."""
        recommendations = {}
        vision_lower = vision.lower()

        # Sprach-Empfehlungen
        if any(w in vision_lower for w in ["data", "daten", "analyse", "ml", "ki"]):
            recommendations["language"] = "python"
            recommendations["language_reason"] = "Beste Wahl fuer Datenanalyse und ML"
        elif any(w in vision_lower for w in ["web", "frontend", "ui", "react"]):
            recommendations["language"] = "javascript"
            recommendations["language_reason"] = "Standard fuer Web-Frontends"
        elif any(w in vision_lower for w in ["api", "backend", "server"]):
            recommendations["language"] = "python"
            recommendations["language_reason"] = "FastAPI/Flask ideal fuer APIs"

        # Datenbank-Empfehlungen
        if any(w in vision_lower for w in ["user", "nutzer", "login", "auth"]):
            recommendations["database"] = "postgresql"
            recommendations["database_reason"] = "Robust fuer Benutzerdaten"
        elif any(w in vision_lower for w in ["dokument", "json", "flexibel"]):
            recommendations["database"] = "mongodb"
            recommendations["database_reason"] = "Flexibles Schema"

        return recommendations
