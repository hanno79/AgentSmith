# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 31.01.2026
Version: 1.4
Beschreibung: DevLoop-Orchestrator - Re-exportiert alle Schritt-Funktionen.
              REFAKTORIERT: Aus 1482 Zeilen → 6 Module + Orchestrator
              Enthält keine eigene Logik mehr, nur Re-exports für Rückwärtskompatibilität.

              Module:
              - dev_loop_helpers.py: Error-Hashing, Truncation-Detection, Sandbox-Checks
              - dev_loop_test_utils.py: Test-Generierung
              - dev_loop_coder.py: Coder-Prompt, Task-Ausführung, Output-Speicherung
              - dev_loop_sandbox.py: Sandbox+Tests (_is_harmless_warning_only, run_sandbox_and_tests)
              - dev_loop_review.py: Review (run_review)
              - dev_loop_security.py: Security-Rescan (run_security_rescan)
              - dev_loop_feedback.py: Feedback-Builder, Modellwechsel-Logik

              ÄNDERUNG 30.01.2026: HELP_NEEDED Events bei kritischen Security-Issues und fehlenden Tests.
              ÄNDERUNG 30.01.2026: Fix - Unit-Test HELP_NEEDED wird IMMER geprüft (auch bei Security-Issues).
              AENDERUNG 31.01.2026: hash_error() fuer Fehler-Modell-Historie.
              AENDERUNG 31.01.2026: Aufsplitten in 6 Module (Regel 1: Max 500 Zeilen).
"""

# =========================================================================
# Re-exports aus dev_loop_helpers.py
# =========================================================================
from .dev_loop_helpers import (
    hash_error,
    run_sandbox_for_project,
    TruncationError,
    _is_python_file_complete,
    _check_for_truncation,
    _sanitize_unicode
)

# =========================================================================
# Re-exports aus dev_loop_test_utils.py
# =========================================================================
from .dev_loop_test_utils import (
    run_test_generator,
    ensure_tests_exist
)

# =========================================================================
# Re-exports aus dev_loop_coder.py, dev_loop_coder_prompt.py, dev_loop_coder_utils.py
# AENDERUNG 08.02.2026: Refactoring — Coder in 3 Module aufgeteilt (Regel 1)
# =========================================================================
from .dev_loop_coder import (
    run_coder_task,
    save_coder_output,
)
from .dev_loop_coder_prompt import build_coder_prompt
from .dev_loop_coder_utils import rebuild_current_code_from_disk

# =========================================================================
# AENDERUNG 08.02.2026: Re-exports aus aufgeteilten Validator-Modulen (Regel 1)
# =========================================================================
from .dev_loop_sandbox import run_sandbox_and_tests
from .dev_loop_review import run_review
from .dev_loop_security import run_security_rescan

# =========================================================================
# Re-exports aus dev_loop_feedback.py
# =========================================================================
from .dev_loop_feedback import (
    build_feedback,
    handle_model_switch
)

# =========================================================================
# Expliziter __all__ Export für IDE-Unterstützung und Dokumentation
# =========================================================================
__all__ = [
    # Helpers
    'hash_error',
    'run_sandbox_for_project',
    'TruncationError',
    '_is_python_file_complete',
    '_check_for_truncation',
    '_sanitize_unicode',
    # Test Utils
    'run_test_generator',
    'ensure_tests_exist',
    # Coder
    'build_coder_prompt',
    'run_coder_task',
    'save_coder_output',
    'rebuild_current_code_from_disk',
    # Validators
    'run_sandbox_and_tests',
    'run_review',
    'run_security_rescan',
    # Feedback
    'build_feedback',
    'handle_model_switch'
]
