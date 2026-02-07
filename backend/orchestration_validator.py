# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 01.02.2026
Version: 1.0
Beschreibung: OrchestratorValidator - Zentrale Prüfinstanz gemäß Dart AI Kommunikationsprotokoll.

              Verantwortlichkeiten:
              1. Agent-Outputs prüfen bevor sie weitergeleitet werden
              2. Root Cause Analyse bei Fehlern durchführen
              3. Entscheidung: Weiter / Fix / Modellwechsel
              4. Einheitlicher Modellwechsel für alle Agenten

              ÄNDERUNG 01.02.2026: Neu erstellt gemäß Dart AI Protokoll (Hierarchical Process).
"""

import re
import hashlib
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Set
from enum import Enum

from .dev_loop_helpers import hash_error, _is_python_file_complete, _check_for_truncation


class ValidatorAction(Enum):
    """Mögliche Aktionen nach Validierung."""
    PROCEED = "proceed"          # Output OK, weiter zum nächsten Agent
    FIX = "fix"                  # Fehler gefunden, zurück zur Korrektur
    MODEL_SWITCH = "model_switch"  # Modellwechsel empfohlen
    ESCALATE = "escalate"        # Eskalation an Meta-Orchestrator/Mensch


@dataclass
class ValidationDecision:
    """Entscheidung des Orchestrators nach Output-Prüfung."""
    action: ValidatorAction
    target_agent: str                           # Nächster Agent oder "coder" bei Fix
    feedback: str = ""                          # Strukturiertes Feedback für nächsten Agent
    root_cause: Optional[str] = None            # Erkannte Ursache (wenn Fehler)
    affected_files: List[str] = field(default_factory=list)
    model_switch_recommended: bool = False
    error_hash: Optional[str] = None            # Für Modellwechsel-Tracking
    issues: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class OrchestratorValidator:
    """
    Prüft Agent-Outputs gemäß Dart AI Kommunikationsprotokoll.

    Im Hierarchical Process ist der Orchestrator der Manager, der JEDEN Output
    prüft bevor er an den nächsten Agent weitergeleitet wird.

    Workflow:
    1. Agent liefert RESULT an Orchestrator
    2. Orchestrator validiert (diese Klasse)
    3. Orchestrator entscheidet: PROCEED / FIX / MODEL_SWITCH / ESCALATE
    4. Orchestrator sendet strukturierten TASK an nächsten Agent
    """

    # Bekannte Fehler-Patterns für Root Cause Erkennung
    ERROR_PATTERNS = {
        "circular_import": [
            r"ImportError.*circular",
            r"cannot import name.*from partially initialized module",
            r"most likely due to a circular import",
        ],
        "module_not_found": [
            r"ModuleNotFoundError: No module named",
            r"ImportError: No module named",
        ],
        "syntax_error": [
            r"SyntaxError:",
            r"IndentationError:",
            r"TabError:",
        ],
        "name_error": [
            r"NameError: name '(\w+)' is not defined",
        ],
        "type_error": [
            r"TypeError:",
        ],
        "attribute_error": [
            r"AttributeError: '(\w+)' object has no attribute '(\w+)'",
        ],
        "file_not_found": [
            r"FileNotFoundError:",
            r"No such file or directory",
        ],
        "key_error": [
            r"KeyError:",
        ],
        "value_error": [
            r"ValueError:",
        ],
    }

    # Root Cause Templates
    ROOT_CAUSE_TEMPLATES = {
        "circular_import": """
SYMPTOM: {symptom}

URSACHE: Zirkulärer Import zwischen Modulen.
Module importieren sich gegenseitig, was zu einem Import-Deadlock führt.

BETROFFENE DATEIEN: {files}

LÖSUNG:
1. Identifiziere die zirkuläre Abhängigkeit (A importiert B, B importiert A)
2. Extrahiere gemeinsame Abhängigkeiten in ein separates Modul
3. Oder: Verwende Lazy Imports (Import innerhalb der Funktion)
4. Prüfe ob alle Imports wirklich benötigt werden
""",
        "module_not_found": """
SYMPTOM: {symptom}

URSACHE: Ein importiertes Modul existiert nicht oder ist nicht installiert.

BETROFFENE DATEIEN: {files}

LÖSUNG:
1. Prüfe ob das Modul korrekt geschrieben ist (Tippfehler?)
2. Prüfe ob die Datei existiert und am richtigen Ort liegt
3. Bei externen Modulen: In requirements.txt aufnehmen
4. Bei eigenen Modulen: Relativen Import verwenden (from . import)
""",
        "syntax_error": """
SYMPTOM: {symptom}

URSACHE: Der Code enthält ungültige Python-Syntax.

BETROFFENE DATEIEN: {files}

LÖSUNG:
1. Prüfe die angegebene Zeile und die Zeilen davor
2. Häufige Ursachen: Fehlende Klammern, Doppelpunkte, Einrückung
3. Strings müssen korrekt geschlossen sein
4. Prüfe auf versteckte Unicode-Zeichen
""",
        "name_error": """
SYMPTOM: {symptom}

URSACHE: Eine Variable oder Funktion wird verwendet, bevor sie definiert wurde.

BETROFFENE DATEIEN: {files}

LÖSUNG:
1. Prüfe ob der Name korrekt geschrieben ist (Groß-/Kleinschreibung)
2. Prüfe ob die Definition VOR der Verwendung steht
3. Prüfe ob der Import korrekt ist
4. Bei Klassenmethoden: 'self.' nicht vergessen
""",
        "generic": """
SYMPTOM: {symptom}

URSACHE: Ein Laufzeitfehler ist aufgetreten.

BETROFFENE DATEIEN: {files}

LÖSUNG:
1. Analysiere die Fehlermeldung und den Traceback
2. Prüfe die betroffene Codezeile
3. Validiere die Eingabedaten und Variablentypen
4. Füge bei Bedarf Error-Handling hinzu
""",
    }

    def __init__(self, manager, model_router, config: Dict[str, Any]):
        """
        Initialisiert den OrchestratorValidator.

        Args:
            manager: OrchestrationManager für Logging und State
            model_router: ModelRouter für Modellwechsel-Entscheidungen
            config: Konfiguration mit models, etc.
        """
        self.manager = manager
        self.model_router = model_router
        self.config = config

        # Tracking für wiederholte Fehler pro Agent
        self._error_counts: Dict[str, Dict[str, int]] = {}  # agent → {error_hash → count}
        self._max_same_error = 3  # Nach 3x gleichem Fehler: Modellwechsel

    def validate_coder_output(
        self,
        code_output: str,
        created_files: Dict[str, str],
        expected_files: Optional[List[str]] = None
    ) -> ValidationDecision:
        """
        Prüft Coder-Output bevor er an Reviewer geht.

        Prüfungen:
        - Code vorhanden und nicht leer
        - Keine offensichtlichen Truncations
        - Alle erwarteten Dateien enthalten

        Args:
            code_output: Der komplette Coder-Output
            created_files: Dict mit Dateiname → Inhalt
            expected_files: Optional Liste erwarteter Dateien

        Returns:
            ValidationDecision mit Aktion und Details
        """
        # ÄNDERUNG 01.02.2026: "Analysis" Event triggert Glow-Effekt in UI
        self.manager._ui_log(
            "Orchestrator", "Analysis",
            f"Prüfe Coder-Output ({len(created_files) if created_files else 0} Dateien)..."
        )

        issues = []
        warnings = []

        try:
            # Prüfung 1: Code vorhanden?
            if not code_output or len(code_output.strip()) < 50:
                issues.append("Coder hat keinen oder zu wenig Code geliefert")
                self.manager._ui_log(
                    "Orchestrator", "Status",
                    "Coder-Output unvollständig - zurück zur Korrektur"
                )
                return ValidationDecision(
                    action=ValidatorAction.FIX,
                    target_agent="coder",
                    feedback="Der generierte Code ist leer oder unvollständig. Bitte generiere den kompletten Code.",
                    issues=issues
                )

            # Prüfung 2: Dateien vorhanden?
            if not created_files:
                issues.append("Keine Dateien im Output erkannt")
                self.manager._ui_log(
                    "Orchestrator", "Status",
                    "Keine Dateien im Output erkannt - zurück zur Korrektur"
                )
                return ValidationDecision(
                    action=ValidatorAction.FIX,
                    target_agent="coder",
                    feedback="Es wurden keine Dateien erkannt. Verwende das Format: ### FILENAME: dateiname.py",
                    issues=issues
                )

            # Prüfung 3: Truncation Detection
            truncated = _check_for_truncation(created_files)
            if truncated:
                truncated_names = [t[0] for t in truncated]
                issues.append(f"Truncation erkannt in: {', '.join(truncated_names)}")
                self.manager._ui_log(
                    "Orchestrator", "Working",
                    f"Truncation erkannt - Modellwechsel empfohlen"
                )
                return ValidationDecision(
                    action=ValidatorAction.MODEL_SWITCH,
                    target_agent="coder",
                    feedback=f"Die folgenden Dateien wurden abgeschnitten: {', '.join(truncated_names)}. Bitte vollständig generieren.",
                    model_switch_recommended=True,
                    affected_files=truncated_names,
                    issues=issues
                )

            # Prüfung 4: Erwartete Dateien vorhanden?
            if expected_files:
                missing = [f for f in expected_files if f not in created_files]
                if missing:
                    warnings.append(f"Fehlende Dateien: {', '.join(missing)}")

            # Prüfung 5: Mindestanzahl Dateien
            if len(created_files) < 3:
                warnings.append(f"Nur {len(created_files)} Dateien erstellt (Minimum: 3)")

            # Alles OK - weiter zum Reviewer
            self.manager._ui_log(
                "Orchestrator", "Status",
                f"Coder-Output OK ({len(created_files)} Dateien) - weiter zum Reviewer"
            )
            return ValidationDecision(
                action=ValidatorAction.PROCEED,
                target_agent="reviewer",
                warnings=warnings
            )
        except Exception as e:
            issues.append(f"Validierungsfehler: {str(e)}")
            self.manager._ui_log("Orchestrator", "Error", f"Coder-Output-Validierung fehlgeschlagen: {e}")
            return ValidationDecision(
                action=ValidatorAction.FIX,
                target_agent="coder",
                feedback=f"Ein unerwarteter Validierungsfehler ist aufgetreten: {str(e)}. Bitte erneut versuchen.",
                issues=issues
            )

    def validate_review_output(
        self,
        review_output: str,
        review_verdict: str,
        sandbox_result: str,
        sandbox_failed: bool,
        current_code: str,
        current_files: Dict[str, str],
        current_model: str
    ) -> ValidationDecision:
        """
        Prüft Review-Output bevor er an Coder zurückgeht.

        Prüfungen:
        - Verdict vorhanden (OK/FEEDBACK)
        - Bei FEEDBACK: Root Cause Analyse vorhanden?
        - Wenn Root Cause fehlt: Orchestrator analysiert selbst

        Args:
            review_output: Reviewer-Feedback
            review_verdict: "OK" oder "FEEDBACK"
            sandbox_result: Sandbox/Test-Ausgabe
            sandbox_failed: Ob Sandbox fehlgeschlagen ist
            current_code: Aktueller Code
            current_files: Aktuelle Dateien
            current_model: Aktuelles Coder-Modell

        Returns:
            ValidationDecision mit Root Cause und Modellwechsel-Empfehlung
        """
        # ÄNDERUNG 01.02.2026: "Analysis" Event triggert Glow-Effekt in UI
        self.manager._ui_log(
            "Orchestrator", "Analysis",
            "Prüfe Review-Output und Sandbox-Ergebnis..."
        )

        # Wenn Review OK und Sandbox OK → PROCEED
        if review_verdict == "OK" and not sandbox_failed:
            self.manager._ui_log(
                "Orchestrator", "Status",
                "Review und Sandbox OK - weiter zum Tester"
            )
            return ValidationDecision(
                action=ValidatorAction.PROCEED,
                target_agent="tester"
            )

        # Fehler vorhanden - Root Cause Analyse nötig
        error_content = sandbox_result if sandbox_failed else review_output
        error_hash = hash_error(error_content)

        # Prüfe ob Root Cause bereits im Review enthalten ist
        has_root_cause = self._check_root_cause_in_review(review_output)

        if has_root_cause:
            # Reviewer hat gute Analyse geliefert
            root_cause = review_output
            self.manager._ui_log(
                "Orchestrator", "Status",
                "Reviewer hat Root Cause Analyse geliefert"
            )
        else:
            # Orchestrator muss selbst analysieren
            self.manager._ui_log(
                "Orchestrator", "Working",
                "Reviewer lieferte keine Ursachenanalyse - führe eigene Analyse durch..."
            )
            root_cause = self.analyze_root_cause(
                error_output=error_content,
                code_files=current_files
            )
            self.manager._ui_log(
                "Orchestrator", "Analysis",
                f"Root Cause Analyse abgeschlossen"
            )

        # Prüfe ob Modellwechsel nötig (3x gleicher Fehler)
        self._record_error_attempt("coder", error_hash, current_model)
        model_switch = self._should_switch_model("coder", error_hash, current_model)

        feedback = self._build_structured_feedback(
            root_cause=root_cause,
            sandbox_result=sandbox_result,
            review_output=review_output,
            sandbox_failed=sandbox_failed
        )

        return ValidationDecision(
            action=ValidatorAction.MODEL_SWITCH if model_switch else ValidatorAction.FIX,
            target_agent="coder",
            feedback=feedback,
            root_cause=root_cause,
            error_hash=error_hash,
            model_switch_recommended=model_switch
        )

    def validate_security_output(
        self,
        vulnerabilities: List[Dict[str, Any]],
        current_model: str
    ) -> ValidationDecision:
        """
        Prüft Security-Output.

        Args:
            vulnerabilities: Liste der gefundenen Vulnerabilities
            current_model: Aktuelles Security-Modell

        Returns:
            ValidationDecision
        """
        # ÄNDERUNG 01.02.2026: "Analysis" Event triggert Glow-Effekt in UI
        self.manager._ui_log(
            "Orchestrator", "Analysis",
            f"Prüfe Security-Scan ({len(vulnerabilities)} Findings)..."
        )

        # Kritische Vulnerabilities?
        critical = [v for v in vulnerabilities if v.get("severity", "").lower() in ("critical", "high")]

        if not critical:
            self.manager._ui_log(
                "Orchestrator", "Status",
                "Security-Scan OK - keine kritischen Issues"
            )
            return ValidationDecision(
                action=ValidatorAction.PROCEED,
                target_agent="final"
            )

        # Fehler-Hash für Modellwechsel
        vuln_summary = " ".join([v.get("description", "") for v in critical[:3]])
        error_hash = hash_error(f"security:{vuln_summary}")

        self._record_error_attempt("security", error_hash, current_model)
        model_switch = self._should_switch_model("security", error_hash, current_model)

        feedback = self._build_security_feedback(critical)

        self.manager._ui_log(
            "Orchestrator", "Working",
            f"{len(critical)} kritische Security-Issues - zurück zur Korrektur"
        )

        return ValidationDecision(
            action=ValidatorAction.MODEL_SWITCH if model_switch else ValidatorAction.FIX,
            target_agent="coder",
            feedback=feedback,
            error_hash=error_hash,
            model_switch_recommended=model_switch,
            issues=[f"{len(critical)} kritische Security-Issues"]
        )

    def analyze_root_cause(
        self,
        error_output: str,
        code_files: Dict[str, str]
    ) -> str:
        """
        Führt Ursachenanalyse durch wenn Reviewer nur Symptome liefert.

        Args:
            error_output: Fehlermeldung/Sandbox-Output
            code_files: Aktuelle Codedateien

        Returns:
            Strukturierte Root Cause Analyse
        """
        if not error_output:
            return ""

        # Erkenne Fehlertyp anhand Patterns
        error_type = "generic"
        symptom = error_output[:500]

        for err_type, patterns in self.ERROR_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, error_output, re.IGNORECASE):
                    error_type = err_type
                    # Extrahiere relevanten Teil als Symptom
                    match = re.search(pattern, error_output)
                    if match:
                        symptom = match.group(0)
                    break
            if error_type != "generic":
                break

        # Finde betroffene Dateien
        affected_files = self._find_affected_files(error_output, code_files)

        # Generiere Root Cause Analyse aus Template
        template = self.ROOT_CAUSE_TEMPLATES.get(error_type, self.ROOT_CAUSE_TEMPLATES["generic"])
        root_cause = template.format(
            symptom=symptom,
            files=", ".join(affected_files) if affected_files else "Nicht identifiziert"
        )

        return root_cause

    def _check_root_cause_in_review(self, review_output: str) -> bool:
        """Prüft ob Review bereits eine Root Cause Analyse enthält."""
        if not review_output:
            return False

        # Suche nach typischen Root Cause Indikatoren
        indicators = [
            "ursache:",
            "root cause:",
            "grund:",
            "das problem ist",
            "das liegt daran",
            "weil",
            "verursacht durch",
            "betroffene dateien",
            "lösung:",
        ]

        review_lower = review_output.lower()
        matches = sum(1 for ind in indicators if ind in review_lower)

        # Mindestens 2 Indikatoren für gute Analyse
        return matches >= 2

    def _record_error_attempt(self, agent_role: str, error_hash: str, current_model: str) -> None:
        """Zählt Fehlerversuch und loggt bei Erreichen des Schwellwerts."""
        if not error_hash:
            return
        if agent_role not in self._error_counts:
            self._error_counts[agent_role] = {}
        key = f"{current_model}:{error_hash}"
        self._error_counts[agent_role][key] = self._error_counts[agent_role].get(key, 0) + 1
        count = self._error_counts[agent_role][key]
        if count >= self._max_same_error:
            self.manager._ui_log(
                "Orchestrator", "ModelSwitchDecision",
                f"Modell {current_model} hat Fehler {error_hash[:8]} {count}x versucht - Wechsel empfohlen"
            )

    def _should_switch_model(self, agent_role: str, error_hash: str, current_model: str) -> bool:
        """
        Entscheidet ob Modellwechsel nötig ist (nur lesend, keine Seiteneffekte).

        Kriterium: Gleiches Modell hat diesen Fehler bereits _max_same_error mal versucht.
        """
        if not error_hash:
            return False
        agent_errors = self._error_counts.get(agent_role, {})
        key = f"{current_model}:{error_hash}"
        return agent_errors.get(key, 0) >= self._max_same_error

    def _find_affected_files(self, error_output: str, code_files: Dict[str, str]) -> List[str]:
        """Findet betroffene Dateien aus der Fehlermeldung."""
        affected = []

        for filename in code_files.keys():
            # Prüfe ob Dateiname in Fehlermeldung vorkommt
            if filename in error_output:
                affected.append(filename)
            # Prüfe auch ohne Extension
            name_without_ext = filename.rsplit(".", 1)[0]
            if name_without_ext in error_output:
                if filename not in affected:
                    affected.append(filename)

        return affected

    def _build_structured_feedback(
        self,
        root_cause: str,
        sandbox_result: str,
        review_output: str,
        sandbox_failed: bool
    ) -> str:
        """Erstellt strukturiertes Feedback für den Coder."""
        feedback_parts = []

        # Header
        if sandbox_failed:
            feedback_parts.append("⚠️ FEHLER ERKANNT - KORREKTUR ERFORDERLICH\n")
        else:
            feedback_parts.append("📝 REVIEW-FEEDBACK\n")

        # Root Cause (wichtigster Teil)
        if root_cause:
            feedback_parts.append(root_cause)

        # Sandbox-Details (gekürzt)
        if sandbox_failed and sandbox_result:
            feedback_parts.append("\n--- SANDBOX-OUTPUT (Details) ---")
            feedback_parts.append(sandbox_result[:1000])

        # Review-Details (gekürzt, wenn root_cause den Review-Text noch nicht enthält)
        if review_output and root_cause not in review_output:
            feedback_parts.append("\n--- REVIEWER-KOMMENTAR ---")
            feedback_parts.append(review_output[:500])

        return "\n".join(feedback_parts)

    def _build_security_feedback(self, critical_vulns: List[Dict[str, Any]]) -> str:
        """Erstellt Feedback für Security-Issues."""
        lines = ["⚠️ KRITISCHE SECURITY-VULNERABILITIES GEFUNDEN\n"]

        for i, vuln in enumerate(critical_vulns[:5], 1):
            lines.append(f"{i}. [{vuln.get('severity', 'HIGH').upper()}] {vuln.get('description', 'Unbekannt')}")
            if vuln.get("fix"):
                lines.append(f"   → LÖSUNG: {vuln.get('fix')}")
            lines.append("")

        lines.append("WICHTIG: Alle Security-Issues müssen behoben werden bevor das Projekt akzeptiert wird.")

        return "\n".join(lines)

    def mark_error_resolved(self, agent_role: str, error_hash: str):
        """Markiert einen Fehler als gelöst (Reset des Counters)."""
        if agent_role in self._error_counts:
            keys_to_remove = [k for k in self._error_counts[agent_role] if error_hash in k]
            for key in keys_to_remove:
                del self._error_counts[agent_role][key]

    def get_status(self) -> Dict[str, Any]:
        """Gibt den aktuellen Status des Validators zurück."""
        return {
            "error_tracking": {
                agent: {k: v for k, v in errors.items()}
                for agent, errors in self._error_counts.items()
            },
            "max_same_error": self._max_same_error
        }
