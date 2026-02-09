"""
Author: rahn
Datum: 02.02.2026
Version: 2.0
Beschreibung: Re-Export-Hub fuer DevLoop (backward compatibility).
              AENDERUNG 08.02.2026: Aufspaltung in dev_loop_core.py, dev_loop_augment.py,
              dev_loop_run_helpers.py (Regel 1: Max 500 Zeilen).
              Originale Logik verteilt auf:
              - dev_loop_core.py: DevLoop-Klasse mit run() Methode
              - dev_loop_augment.py: get_augment_context() Funktion
              - dev_loop_run_helpers.py: Helfer fuer run() (File-by-File, Truncation, UTDS, Success)
"""

# AENDERUNG 08.02.2026: Re-Export fuer bestehende Importeure
# orchestration_manager.py:80 → from .dev_loop import DevLoop
# tests/test_dev_loop.py → from backend.dev_loop import DevLoop
from .dev_loop_core import DevLoop

__all__ = ["DevLoop"]
