"""
Author: rahn
Datum: 08.02.2026
Version: 1.0
Beschreibung: Augment-Kontext-Integration fuer DevLoop.
              Extrahiert aus dev_loop.py (Regel 1: Max 500 Zeilen).
              AENDERUNG 01.02.2026: Augment Context Integration bei wiederholten Fehlern.
              AENDERUNG 02.02.2026: shutil.which() fuer vollstaendigen npx-Pfad.
              AENDERUNG 06.02.2026: ROOT-CAUSE-FIX Windows-Pfad-Bug (shlex.split auf Pfade mit Leerzeichen).
"""

import logging
import shutil

logger = logging.getLogger(__name__)


def get_augment_context(
    manager,
    sandbox_result: str,
    review_output: str,
    iteration: int
) -> str:
    """
    Holt Augment-Kontext bei wiederholten Fehlern (Iteration 3+).

    Args:
        manager: OrchestrationManager-Instanz
        sandbox_result: Sandbox/Test-Output mit Fehlern
        review_output: Reviewer-Feedback
        iteration: Aktuelle Iteration (0-basiert)

    Returns:
        Augment-Kontext-String oder leerer String wenn nicht verfuegbar
    """
    # Pruefe ob External Bureau verfuegbar
    if not hasattr(manager, 'external_bureau') or not manager.external_bureau:
        return ""

    # Nur bei Iteration 3+ (nach 2 fehlgeschlagenen Versuchen)
    if iteration < 2:
        return ""

    # Pruefe ob use_for_context aktiviert ist
    augment_cfg = manager.config.get("external_specialists", {}).get("augment_context", {})
    if not augment_cfg.get("use_for_context", False):
        return ""

    try:
        augment = manager.external_bureau.get_specialist("augment")
        if not augment:
            return ""

        # Pruefe CLI-Verfuegbarkeit
        if not augment.check_available():
            manager._ui_log("Augment", "NotAvailable",
                           "Auggie CLI nicht verfuegbar - ueberspringe Kontext-Analyse")
            return ""

        # Aktiviere wenn noetig
        from external_specialists.base_specialist import SpecialistStatus
        if augment.status != SpecialistStatus.READY:
            manager.external_bureau.activate_specialist("augment")

        manager._ui_log("Augment", "ContextAnalysis",
                       f"Hole Architektur-Kontext fuer Iteration {iteration + 1}...")

        # Query mit Fehler-Kontext
        query = f"""Analysiere diese Fehler und gib Kontext zur Architektur:

SANDBOX-FEHLER (gekuerzt):
{sandbox_result[:800] if sandbox_result else 'Keine'}

REVIEW-FEEDBACK (gekuerzt):
{review_output[:500] if review_output else 'Keines'}

Was koennte strukturell falsch sein? Gib konkrete Hinweise."""

        import subprocess
        import time as _time

        # AENDERUNG 01.02.2026: Synchroner Subprocess statt asyncio (Timeout-Fix)
        # Problem: asyncio.wait_for() konnte den Subprocess in Thread nicht abbrechen
        # Loesung: Direkter subprocess.run() mit eingebautem Timeout
        timeout = augment_cfg.get("timeout_seconds", 300)  # Default: 5 Minuten
        cli_command = augment_cfg.get("cli_command", "npx @augmentcode/auggie")

        # AENDERUNG 02.02.2026: shutil.which() fuer vollstaendigen npx-Pfad
        # Problem: subprocess.run() mit shell=False findet npx nicht im PATH
        # Loesung: Vollstaendigen Pfad zu npx ermitteln
        if cli_command.startswith("npx"):
            npx_path = shutil.which("npx")
            if not npx_path:
                manager._ui_log("Augment", "NotFound",
                               "npx nicht im PATH gefunden - npm install -g @augmentcode/auggie")
                return ""
        else:
            npx_path = None

        # AENDERUNG 06.02.2026: ROOT-CAUSE-FIX Windows-Pfad-Bug
        # Symptom: Augment CLI "NotFound" auf Windows (shlex zerlegt Pfad mit Leerzeichen)
        # Ursache: shlex.split() splittet "C:\Program Files\nodejs\npx.CMD" am Leerzeichen
        # Loesung: Array direkt bauen statt shlex.split() auf modifizierten String
        short_query = "Gib eine kurze Uebersicht der Projekt-Architektur."
        parts = cli_command.split()  # ["npx", "@augmentcode/auggie"]
        if npx_path:
            cmd_argv = [npx_path] + parts[1:] + [short_query, "--print"]
        else:
            cmd_argv = parts + [short_query, "--print"]

        project_path = str(manager.project_path) if hasattr(manager, 'project_path') else None
        manager._ui_log("Augment", "Debug",
                       f"Starte: {' '.join(cmd_argv)[:80]}... | cwd={project_path} | timeout={timeout}s")
        start_time = _time.time()

        try:
            result = subprocess.run(
                cmd_argv,
                capture_output=True,
                timeout=timeout,
                text=True,
                encoding='utf-8',
                errors='replace',
                cwd=project_path,
                shell=False
            )

            elapsed = _time.time() - start_time
            manager._ui_log("Augment", "Debug",
                           f"Subprocess fertig nach {elapsed:.1f}s | returncode={result.returncode}")

            if result.returncode == 0 and result.stdout.strip():
                context_output = result.stdout[:2000]
                manager._ui_log("Augment", "ContextResult",
                               f"Kontext erhalten: {len(context_output)} Zeichen in {elapsed:.1f}s")
                return context_output
            else:
                # DIAGNOSE: Detaillierte Fehlerinfo
                stdout_info = result.stdout[:300] if result.stdout else "(leer)"
                stderr_info = result.stderr[:300] if result.stderr else "(leer)"
                manager._ui_log("Augment", "NoOutput",
                               f"returncode={result.returncode} | stdout={stdout_info} | stderr={stderr_info}")
                return ""

        except subprocess.TimeoutExpired:
            elapsed = _time.time() - start_time
            manager._ui_log("Augment", "Timeout",
                           f"Timeout nach {elapsed:.1f}s (limit={timeout}s)")
            return ""
        except FileNotFoundError:
            manager._ui_log("Augment", "NotFound",
                           f"Augment CLI nicht gefunden: {cli_command}")
            return ""
        except OSError as ose:
            manager._ui_log("Augment", "OSError",
                           f"Betriebssystemfehler: {str(ose)[:200]}")
            return ""

    except Exception as e:
        manager._ui_log("Augment", "ContextError", f"Fehler: {str(e)[:200]}")
        return ""
