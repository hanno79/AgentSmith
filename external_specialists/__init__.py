# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 28.01.2026
Version: 1.0
Beschreibung: External Specialists Package - Externe Fachkraefte fuer das External Bureau.
"""

from .base_specialist import (
    BaseSpecialist,
    SpecialistStatus,
    SpecialistCategory,
    SpecialistResult,
    SpecialistFinding
)
from .coderabbit_specialist import CodeRabbitSpecialist
from .exa_specialist import EXASpecialist

__all__ = [
    # Base Classes
    "BaseSpecialist",
    "SpecialistStatus",
    "SpecialistCategory",
    "SpecialistResult",
    "SpecialistFinding",
    # Specialists
    "CodeRabbitSpecialist",
    "EXASpecialist",
]
