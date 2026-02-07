# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 31.01.2026
Version: 1.0
Beschreibung: Gemeinsames ValidationResult-Dataclass fuer QualityGate und Dart-Validatoren.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List


@dataclass
class ValidationResult:
    """Ergebnis einer Qualitätsprüfung."""
    passed: bool
    issues: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    score: float = 1.0  # 0.0 bis 1.0
    details: Dict[str, Any] = field(default_factory=dict)
