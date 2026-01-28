# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 28.01.2026
Version: 1.0
Beschreibung: Abstrakte Basisklasse fuer externe Specialists im External Bureau.
              Ermoeglicht einfache Erweiterung durch neue externe Dienste.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class SpecialistStatus(Enum):
    """Status-Zustaende eines Specialists."""
    DORMANT = "DORMANT"           # Nicht aktiv, aber verfuegbar
    READY = "READY"               # Aktiv und bereit
    COMPILING = "COMPILING"       # Wird gerade ausgefuehrt
    ERROR = "ERROR"               # Fehler aufgetreten
    RATE_LIMITED = "RATE_LIMITED" # Rate-Limit erreicht


class SpecialistCategory(Enum):
    """Kategorien fuer Filter im UI."""
    COMBAT = "combat"             # Code-Review Tools (CodeRabbit, Semgrep)
    INTELLIGENCE = "intelligence" # Recherche (EXA, Web Search)
    CREATIVE = "creative"         # Generative Tools (Future)


@dataclass
class SpecialistFinding:
    """Einzelnes Finding eines Specialists."""
    severity: str                 # CRITICAL, HIGH, MEDIUM, LOW, INFO
    description: str
    file: str = ""
    line: int = 0
    fix: str = ""
    category: str = ""


@dataclass
class SpecialistResult:
    """Ergebnis einer Specialist-Ausfuehrung."""
    success: bool
    findings: List[SpecialistFinding] = field(default_factory=list)
    summary: str = ""
    raw_output: str = ""
    duration_ms: int = 0
    error: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class BaseSpecialist(ABC):
    """
    Abstrakte Basisklasse fuer alle externen Specialists.

    Um einen neuen Specialist hinzuzufuegen:
    1. Neue Klasse von BaseSpecialist erben
    2. name, category, stats Properties implementieren
    3. check_available() und execute() implementieren
    4. In external_bureau_manager.py registrieren
    5. In config.yaml Eintrag hinzufuegen
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialisiert den Specialist.

        Args:
            config: Konfiguration aus config.yaml (specialist-spezifischer Abschnitt)
        """
        self.config = config
        self.status = SpecialistStatus.DORMANT
        self.last_run: Optional[datetime] = None
        self.last_result: Optional[SpecialistResult] = None
        self.cooldown_until: Optional[datetime] = None
        self.run_count = 0
        self.error_count = 0

    @property
    @abstractmethod
    def name(self) -> str:
        """Eindeutiger Anzeigename des Specialists."""
        pass

    @property
    @abstractmethod
    def category(self) -> SpecialistCategory:
        """Kategorie fuer Filter (Combat/Intelligence/Creative)."""
        pass

    @property
    @abstractmethod
    def stats(self) -> Dict[str, int]:
        """
        Statistiken fuer UI-Anzeige (STR, INT, AGI - jeweils 0-100).

        STR = Staerke der Analyse
        INT = Intelligenz/Tiefe der Insights
        AGI = Geschwindigkeit/Reaktionsfaehigkeit
        """
        pass

    @property
    def description(self) -> str:
        """Optionale Beschreibung fuer Tooltip im UI."""
        return ""

    @property
    def icon(self) -> str:
        """Optionales Icon (Material Icons Name oder Emoji)."""
        return "extension"

    @abstractmethod
    def check_available(self) -> bool:
        """
        Prueft ob der Specialist verfuegbar ist.

        Returns:
            True wenn CLI installiert / API erreichbar / Credentials vorhanden
        """
        pass

    @abstractmethod
    async def execute(self, context: Dict[str, Any]) -> SpecialistResult:
        """
        Fuehrt den Specialist aus.

        Args:
            context: Kontext mit:
                - code: Der zu analysierende Code
                - project_path: Pfad zum Projektverzeichnis
                - tech_blueprint: Tech-Stack Information
                - query: Suchanfrage (fuer Intelligence-Specialists)

        Returns:
            SpecialistResult mit Findings und Summary
        """
        pass

    def activate(self) -> bool:
        """
        Aktiviert den Specialist.

        Returns:
            True wenn erfolgreich aktiviert
        """
        if self.is_in_cooldown():
            logger.warning(f"{self.name}: Noch im Cooldown bis {self.cooldown_until}")
            return False

        if self.check_available():
            self.status = SpecialistStatus.READY
            logger.info(f"{self.name}: Aktiviert")
            return True
        else:
            self.status = SpecialistStatus.ERROR
            logger.warning(f"{self.name}: Nicht verfuegbar")
            return False

    def deactivate(self):
        """Deaktiviert den Specialist."""
        self.status = SpecialistStatus.DORMANT
        logger.info(f"{self.name}: Deaktiviert")

    def is_in_cooldown(self) -> bool:
        """Prueft ob der Specialist im Cooldown ist."""
        if self.cooldown_until is None:
            return False
        return datetime.now() < self.cooldown_until

    def set_cooldown(self, seconds: int):
        """Setzt Cooldown nach Rate-Limit."""
        from datetime import timedelta
        self.cooldown_until = datetime.now() + timedelta(seconds=seconds)
        self.status = SpecialistStatus.RATE_LIMITED
        logger.info(f"{self.name}: Cooldown fuer {seconds}s gesetzt")

    def get_cooldown_remaining(self) -> int:
        """Gibt verbleibende Cooldown-Sekunden zurueck."""
        if self.cooldown_until is None:
            return 0
        remaining = (self.cooldown_until - datetime.now()).total_seconds()
        return max(0, int(remaining))

    def to_dict(self) -> Dict[str, Any]:
        """Serialisiert den Specialist fuer API/UI."""
        return {
            "id": self.__class__.__name__.lower().replace("specialist", ""),
            "name": self.name,
            "status": self.status.value,
            "category": self.category.value,
            "stats": self.stats,
            "available": self.check_available(),
            "description": self.description,
            "icon": self.icon,
            "run_count": self.run_count,
            "error_count": self.error_count,
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "cooldown_remaining": self.get_cooldown_remaining(),
            "last_result_summary": self.last_result.summary if self.last_result else None
        }
