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
              - dev_loop_validators.py: Sandbox+Tests, Review, Security-Rescan
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
# Re-exports aus dev_loop_coder.py
# =========================================================================
from .dev_loop_coder import (
    build_coder_prompt,
    run_coder_task,
    save_coder_output,
    rebuild_current_code_from_disk
)

# =========================================================================
# Re-exports aus dev_loop_validators.py
# =========================================================================
from .dev_loop_validators import (
    run_sandbox_and_tests,
    run_review,
    run_security_rescan
)

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
