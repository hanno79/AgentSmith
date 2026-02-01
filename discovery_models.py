# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 01.02.2026
Version: 1.0
Beschreibung: Datenmodelle fuer Discovery Session.
              Extrahiert aus discovery_session.py (Regel 1: Max 500 Zeilen)
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from enum import Enum


# ============================================================================
# ENUMS
# ============================================================================

class AnswerMode(Enum):
    """Modi fuer Antwortoptionen."""
    SINGLE = "single"           # Eine Option waehlen
    MULTIPLE = "multiple"       # Mehrere Optionen kombinieren
    CUSTOM = "custom"           # Freitext
    COMBINATION = "combination" # Option + eigene Ergaenzung
    SKIP = "skip"              # Wird als offener Punkt notiert


class SessionPhase(Enum):
    """Phasen der Discovery Session."""
    VISION = "vision"           # Phase 1: Freie Eingabe
    TEAM_SETUP = "team_setup"   # Phase 2: Agenten-Auswahl
    GUIDED_QA = "guided_qa"     # Phase 3: Geführte Fragen
    SUMMARY = "summary"         # Zusammenfassung
    BRIEFING = "briefing"       # Output generieren


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class AnswerOption:
    """Eine Antwortoption mit Empfehlung."""
    text: str
    value: Any
    is_recommended: bool = False
    reason: Optional[str] = None
    source: Optional[str] = None  # "memory", "researcher", "standard"


@dataclass
class GuidedQuestion:
    """Eine gefuehrte Frage mit Optionen."""
    agent: str
    question: str
    options: List[AnswerOption]
    mode: AnswerMode = AnswerMode.SINGLE
    required: bool = True
    category: str = "general"
    help_text: Optional[str] = None


@dataclass
class Answer:
    """Eine Antwort auf eine GuidedQuestion."""
    question_id: str
    agent: str
    selected_options: List[Any]
    custom_text: Optional[str] = None
    skipped: bool = False
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class ProjectBriefing:
    """Das generierte Projektbriefing."""
    project_name: str
    auftraggeber: str
    datum: str
    teilnehmende_agenten: List[str]
    projektziel: str
    scope_enthalten: List[str]
    scope_ausgeschlossen: List[str]
    datengrundlage: List[str]
    technische_anforderungen: Dict[str, Any]
    erfolgskriterien: List[str]
    timeline: Dict[str, str]
    offene_punkte: List[str]
