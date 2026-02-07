# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 01.02.2026
Version: 1.4
Beschreibung: Quality Gate - Inhaltliche Qualitätskontrolle zwischen Agent-Steps.
              Prüft ob Agent-Outputs den Benutzer-Anforderungen entsprechen.

              AENDERUNG 01.02.2026 v1.4: validate_waisen() für Traceability-Check
              - Prüft ANF → FEAT → TASK → FILE Kette
              - Identifiziert Waisen-Elemente
              - Berechnet Coverage-Score

              AENDERUNG 01.02.2026 v1.3: Refaktoriert in Module (Regel 1: Max 500 Zeilen)
              - qg_constants.py: Keyword-Mappings, Severity-Konstanten
              - qg_requirements.py: Anforderungs-Extraktion
              - qg_techstack_validators.py: TechStack/Schema/Code/Design Validierung
              - qg_output_validators.py: Review/Security/Final/AgentMessage Validierung

              AENDERUNG 31.01.2026: Dart AI Feature-Ableitung Validierungen
              (validate_anforderungen, validate_features, validate_file_by_file_output).
              AENDERUNG 31.01.2026 v1.2: Fix UI-Typ Erkennung - "webapp" hat Prioritaet
              ueber generisches "gui" Keyword.
"""

from typing import Dict, Any, List, Optional

# Interne Module
from backend.validation_result import ValidationResult
from backend.qg_constants import (
    DB_KEYWORDS,
    LANG_KEYWORDS,
    FRAMEWORK_KEYWORDS,
    UI_TYPE_KEYWORDS,
)
from backend.qg_requirements import extract_requirements, get_requirements_summary
from backend.qg_techstack_validators import (
    validate_techstack as _validate_techstack,
    validate_schema as _validate_schema,
    validate_code as _validate_code,
    validate_design as _validate_design,
)
from backend.qg_output_validators import (
    validate_review as _validate_review,
    validate_security as _validate_security,
    validate_final as _validate_final,
    validate_agent_message as _validate_agent_message,
)
from backend.dart_ai_validators import (
    validate_anforderungen as _dart_validate_anforderungen,
    validate_features as _dart_validate_features,
    validate_file_by_file_plan as _dart_validate_file_by_file_plan,
    validate_file_by_file_output as _dart_validate_file_by_file_output,
)

# Re-Export fuer Aufrufer die "from backend.quality_gate import ValidationResult" nutzen
__all__ = ["QualityGate", "ValidationResult"]


class QualityGate:
    """
    Prüft Agent-Outputs auf inhaltliche Qualität und Anforderungs-Konformität.

    Diese Klasse validiert, dass die Ergebnisse der verschiedenen Agenten
    den ursprünglichen Benutzer-Anforderungen entsprechen.
    """

    # Keyword-Mappings als Klassen-Attribute für Rückwärtskompatibilität
    DB_KEYWORDS = DB_KEYWORDS
    LANG_KEYWORDS = LANG_KEYWORDS
    FRAMEWORK_KEYWORDS = FRAMEWORK_KEYWORDS
    UI_TYPE_KEYWORDS = UI_TYPE_KEYWORDS

    def __init__(self, user_goal: str, briefing: Optional[Dict[str, Any]] = None):
        """
        Initialisiert das Quality Gate.

        Args:
            user_goal: Das ursprüngliche Benutzer-Ziel (VERBINDLICH)
            briefing: Optional Discovery-Briefing mit zusätzlichen Details
        """
        self.user_goal = user_goal
        self.briefing = briefing or {}
        self.requirements = extract_requirements(user_goal)

    def _extract_requirements(self) -> Dict[str, Any]:
        """
        Extrahiert prüfbare Anforderungen aus user_goal.
        Delegiert an qg_requirements.extract_requirements().
        """
        return extract_requirements(self.user_goal)

    def validate_techstack(self, blueprint: Dict[str, Any]) -> ValidationResult:
        """
        Validiert TechStack-Blueprint gegen Benutzer-Anforderungen.
        """
        return _validate_techstack(self.requirements, blueprint)

    def validate_schema(self, schema: str, blueprint: Dict[str, Any]) -> ValidationResult:
        """
        Validiert DB-Schema gegen Blueprint und Anforderungen.
        """
        return _validate_schema(self.requirements, schema, blueprint)

    def validate_code(self, code: str, blueprint: Dict[str, Any]) -> ValidationResult:
        """
        Validiert generierten Code gegen Blueprint.
        """
        return _validate_code(self.requirements, code, blueprint)

    def validate_design(self, design_concept: str, blueprint: Dict[str, Any]) -> ValidationResult:
        """
        Validiert Design-Konzept gegen Blueprint und Anforderungen.
        """
        return _validate_design(design_concept, blueprint)

    def validate_review(
        self,
        review_output: str,
        code: str,
        blueprint: Dict[str, Any]
    ) -> ValidationResult:
        """
        Validiert Review-Output gegen Code und Blueprint.
        """
        return _validate_review(review_output, code, blueprint)

    def validate_security(
        self,
        vulnerabilities: List[Dict[str, Any]],
        severity_threshold: str = "high"
    ) -> ValidationResult:
        """
        Validiert Security-Findings gegen Schwellenwert.
        """
        return _validate_security(vulnerabilities, severity_threshold)

    def validate_final(
        self,
        code: str,
        tests_passed: bool,
        review_passed: bool,
        security_passed: bool,
        blueprint: Dict[str, Any]
    ) -> ValidationResult:
        """
        Finale Validierung des gesamten Projekts.
        """
        # Code-Validator-Funktion für finale Validierung
        def code_validator(c: str, bp: Dict[str, Any]) -> ValidationResult:
            return _validate_code(self.requirements, c, bp)

        return _validate_final(
            code, tests_passed, review_passed, security_passed,
            blueprint, code_validator
        )

    def validate_agent_message(
        self,
        message: Dict[str, Any],
        expected_type: str
    ) -> ValidationResult:
        """
        Validiert Agent-Nachrichten gemäß Kommunikationsprotokoll.
        """
        return _validate_agent_message(message, expected_type)

    def get_requirements_summary(self) -> str:
        """
        Gibt eine lesbare Zusammenfassung der erkannten Anforderungen zurück.
        """
        return get_requirements_summary(self.requirements)

    # =========================================================================
    # Dart AI Validierungen (delegiert an dart_ai_validators)
    # =========================================================================

    def validate_anforderungen(
        self,
        analyst_output: Dict[str, Any],
        briefing: Dict[str, Any]
    ) -> ValidationResult:
        """Delegiert an dart_ai_validators.validate_anforderungen."""
        return _dart_validate_anforderungen(analyst_output, briefing)

    def validate_features(
        self,
        konzepter_output: Dict[str, Any],
        anforderungen: List[Dict[str, Any]]
    ) -> ValidationResult:
        """Delegiert an dart_ai_validators.validate_features."""
        return _dart_validate_features(konzepter_output, anforderungen)

    def validate_file_by_file_plan(
        self,
        plan: Dict[str, Any],
        blueprint: Dict[str, Any]
    ) -> ValidationResult:
        """Delegiert an dart_ai_validators.validate_file_by_file_plan."""
        return _dart_validate_file_by_file_plan(plan, blueprint)

    def validate_file_by_file_output(
        self,
        created_files: List[str],
        plan: Dict[str, Any],
        max_lines_per_file: int = 200
    ) -> ValidationResult:
        """Delegiert an dart_ai_validators.validate_file_by_file_output."""
        return _dart_validate_file_by_file_output(created_files, plan, max_lines_per_file)

    # =========================================================================
    # Waisen-Check (NEU 01.02.2026)
    # =========================================================================

    def validate_waisen(
        self,
        anforderungen: List[Dict[str, Any]],
        features: List[Dict[str, Any]],
        tasks: List[Dict[str, Any]],
        file_generations: List[Dict[str, Any]]
    ) -> ValidationResult:
        """
        Prüft auf Waisen-Elemente in der Traceability-Kette.

        ANF → FEAT → TASK → FILE

        Identifiziert:
        - Anforderungen ohne zugehörige Features
        - Features ohne zugehörige Tasks
        - Tasks ohne generierte Dateien

        Args:
            anforderungen: Liste der Anforderungen (mit 'id')
            features: Liste der Features (mit 'id', 'anforderungen')
            tasks: Liste der Tasks (mit 'id', 'feature_id')
            file_generations: Liste der Dateien (mit 'task_id')

        Returns:
            ValidationResult mit Waisen-Details und Coverage-Score
        """
        issues = []
        warnings = []

        # 1. Anforderungen ohne Features
        anf_ids = {a.get("id") for a in anforderungen if a.get("id")}
        feat_ref_anf = set()
        for f in features:
            feat_ref_anf.update(f.get("anforderungen", []))

        waisen_anf = anf_ids - feat_ref_anf
        if waisen_anf:
            issues.append(f"Anforderungen ohne Features: {sorted(waisen_anf)}")

        # 2. Features ohne Tasks
        feat_ids = {f.get("id") for f in features if f.get("id")}
        task_ref_feat = {t.get("feature_id") for t in tasks if t.get("feature_id")}

        waisen_feat = feat_ids - task_ref_feat
        if waisen_feat:
            issues.append(f"Features ohne Tasks: {sorted(waisen_feat)}")

        # 3. Tasks ohne Dateien (nur Warnung, da nicht alle Tasks Dateien erzeugen)
        task_ids = {t.get("id") for t in tasks if t.get("id")}
        file_ref_task = {fg.get("task_id") for fg in file_generations if fg.get("task_id")}

        waisen_tasks = task_ids - file_ref_task
        if waisen_tasks:
            warnings.append(f"Tasks ohne Dateien: {sorted(waisen_tasks)}")

        # Coverage berechnen
        total = len(anf_ids) + len(feat_ids) + len(task_ids)
        waisen_count = len(waisen_anf) + len(waisen_feat) + len(waisen_tasks)
        coverage = 1.0 - (waisen_count / total) if total > 0 else 1.0

        return ValidationResult(
            passed=len(issues) == 0,
            issues=issues,
            warnings=warnings,
            score=coverage,
            details={
                "waisen": {
                    "anforderungen_ohne_features": list(waisen_anf),
                    "features_ohne_tasks": list(waisen_feat),
                    "tasks_ohne_dateien": list(waisen_tasks)
                },
                "counts": {
                    "anforderungen": len(anf_ids),
                    "features": len(feat_ids),
                    "tasks": len(task_ids),
                    "dateien": len(file_generations)
                },
                "coverage": coverage
            }
        )
