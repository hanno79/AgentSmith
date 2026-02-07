# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 01.02.2026
Version: 1.0
Beschreibung: Quality Gate Output-bezogene Validierungen.
              Extrahiert aus quality_gate.py (Regel 1: Max 500 Zeilen)

              Enthält:
              - validate_review
              - validate_security
              - validate_final
              - validate_agent_message
"""

from typing import Dict, Any, List

from backend.validation_result import ValidationResult
from backend.qg_constants import SEVERITY_ORDER, SEVERITY_WEIGHTS, VALID_AGENT_STATUSES


def validate_review(
    review_output: str,
    code: str,
    blueprint: Dict[str, Any]
) -> ValidationResult:
    """
    Validiert Review-Output gegen Code und Blueprint.

    Args:
        review_output: Das Review-Ergebnis des Reviewer-Agents
        code: Der zu reviewende Code
        blueprint: Das TechStack-Blueprint

    Returns:
        ValidationResult
    """
    issues = []
    warnings = []
    details = {"checked": []}

    if not review_output or len(review_output.strip()) < 20:
        issues.append("Review-Output ist leer oder zu kurz")
        return ValidationResult(passed=False, issues=issues, score=0.0, warnings=[])

    review_lower = review_output.lower()

    # Prüfung 1: Review sollte Stellung zum Code nehmen
    details["checked"].append("review_completeness")
    code_related_keywords = ["code", "implementierung", "funktion", "klasse", "methode", "variable"]
    if not any(kw in review_lower for kw in code_related_keywords):
        warnings.append("Review scheint keinen Bezug zum Code zu haben")

    # Prüfung 2: Review sollte ein Verdict enthalten
    details["checked"].append("verdict_present")
    verdict_keywords = ["approved", "rejected", "genehmigt", "abgelehnt", "ok", "nicht ok", "bestanden", "fehlgeschlagen"]
    if not any(kw in review_lower for kw in verdict_keywords):
        warnings.append("Review enthält kein eindeutiges Verdict (approved/rejected)")

    # Prüfung 3: Bei Ablehnung sollten Gründe genannt werden
    details["checked"].append("rejection_reasons")
    if any(kw in review_lower for kw in ["rejected", "abgelehnt", "nicht ok", "fehlgeschlagen"]):
        reason_keywords = ["weil", "grund", "problem", "fehler", "issue", "mangel"]
        if not any(kw in review_lower for kw in reason_keywords):
            warnings.append("Review lehnt ab, aber nennt keine konkreten Gründe")

    score = 1.0 - (len(issues) * 0.3) - (len(warnings) * 0.1)
    score = max(0.0, min(1.0, score))

    return ValidationResult(
        passed=len(issues) == 0,
        issues=issues,
        warnings=warnings,
        score=score,
        details=details
    )


def validate_security(
    vulnerabilities: List[Dict[str, Any]],
    severity_threshold: str = "high"
) -> ValidationResult:
    """
    Validiert Security-Findings gegen Schwellenwert.

    Args:
        vulnerabilities: Liste von Security-Findings mit severity
        severity_threshold: Minimal blockierende Severity ("critical", "high", "medium", "low")

    Returns:
        ValidationResult
    """
    issues = []
    warnings = []
    details = {"checked": [], "vulnerabilities_by_severity": {}}

    threshold_index = SEVERITY_ORDER.index(severity_threshold) if severity_threshold in SEVERITY_ORDER else 1

    # Gruppiere Vulnerabilities nach Severity
    by_severity = {"critical": [], "high": [], "medium": [], "low": [], "info": []}
    for vuln in vulnerabilities:
        sev = vuln.get("severity", "info").lower()
        if sev in by_severity:
            by_severity[sev].append(vuln)

    details["vulnerabilities_by_severity"] = {k: len(v) for k, v in by_severity.items()}
    details["checked"].append("severity_check")

    # Alle Severities berücksichtigen, nicht nur bis zum Threshold
    for sev in SEVERITY_ORDER:
        if by_severity[sev]:
            sev_index = SEVERITY_ORDER.index(sev)
            if sev_index < threshold_index:
                # Severity unter Threshold -> Issues (blockierend)
                if sev in ["critical", "high"]:
                    issues.append(
                        f"{len(by_severity[sev])} {sev.upper()}-Severity Vulnerabilities gefunden"
                    )
                else:
                    warnings.append(
                        f"{len(by_severity[sev])} {sev.upper()}-Severity Vulnerabilities gefunden"
                    )
            elif sev_index == threshold_index:
                # Severity gleich Threshold -> Issues für critical/high, Warnungen für medium/low
                if sev in ["critical", "high"]:
                    issues.append(
                        f"{len(by_severity[sev])} {sev.upper()}-Severity Vulnerabilities gefunden"
                    )
                else:
                    warnings.append(
                        f"{len(by_severity[sev])} {sev.upper()}-Severity Vulnerabilities gefunden"
                    )
            else:
                # Severity über Threshold -> Nur Warnungen (nicht blockierend)
                warnings.append(
                    f"{len(by_severity[sev])} {sev.upper()}-Severity Vulnerabilities gefunden"
                )

    # Score berechnen basierend auf Severity-Gewichtung
    penalty = sum(len(by_severity[sev]) * SEVERITY_WEIGHTS.get(sev, 0) for sev in by_severity)
    score = max(0.0, 1.0 - penalty)

    return ValidationResult(
        passed=len(issues) == 0,
        issues=issues,
        warnings=warnings,
        score=score,
        details=details
    )


def validate_final(
    code: str,
    tests_passed: bool,
    review_passed: bool,
    security_passed: bool,
    blueprint: Dict[str, Any],
    code_validator_func
) -> ValidationResult:
    """
    Finale Validierung des gesamten Projekts.

    Args:
        code: Der finale Code
        tests_passed: Ob alle Tests bestanden haben
        review_passed: Ob das Review bestanden hat
        security_passed: Ob der Security-Check bestanden hat
        blueprint: Das TechStack-Blueprint
        code_validator_func: Funktion zur Code-Validierung

    Returns:
        ValidationResult
    """
    issues = []
    warnings = []
    details = {"checked": [], "component_status": {}}

    # Prüfung 1: Code vorhanden
    details["checked"].append("code_exists")
    if not code or len(code.strip()) < 50:
        issues.append("Kein oder unvollständiger Code vorhanden")

    # Prüfung 2: Tests
    details["checked"].append("tests")
    details["component_status"]["tests"] = tests_passed
    if not tests_passed:
        issues.append("Tests sind fehlgeschlagen")

    # Prüfung 3: Review
    details["checked"].append("review")
    details["component_status"]["review"] = review_passed
    if not review_passed:
        warnings.append("Review wurde nicht bestanden (manuell prüfen)")

    # Prüfung 4: Security
    details["checked"].append("security")
    details["component_status"]["security"] = security_passed
    if not security_passed:
        issues.append("Security-Check nicht bestanden")

    # Prüfung 5: Blueprint-Konformität (nochmal prüfen)
    if code_validator_func:
        code_validation = code_validator_func(code, blueprint)
        details["code_validation_score"] = code_validation.score
        if not code_validation.passed:
            issues.extend(code_validation.issues)
        warnings.extend(code_validation.warnings)

    score = 1.0 - (len(issues) * 0.25) - (len(warnings) * 0.05)
    score = max(0.0, min(1.0, score))

    return ValidationResult(
        passed=len(issues) == 0,
        issues=issues,
        warnings=warnings,
        score=score,
        details=details
    )


def validate_agent_message(
    message: Dict[str, Any],
    expected_type: str
) -> ValidationResult:
    """
    Validiert Agent-Nachrichten gemäß Kommunikationsprotokoll.

    Erwartete Message-Typen: TASK, RESULT, QUESTION, STATUS, ERROR

    Args:
        message: Die Agent-Nachricht als Dictionary
        expected_type: Erwarteter Nachrichtentyp

    Returns:
        ValidationResult
    """
    issues = []
    warnings = []
    details = {"checked": [], "message_type": expected_type}

    # Basis-Struktur prüfen
    details["checked"].append("structure")
    required_fields = ["type", "agent", "timestamp"]
    for field in required_fields:
        if field not in message:
            issues.append(f"Pflichtfeld '{field}' fehlt in der Nachricht")

    # Typ-Validierung
    details["checked"].append("type_match")
    actual_type = message.get("type", "").upper()
    if actual_type != expected_type.upper():
        issues.append(f"Erwarteter Typ '{expected_type}', erhalten '{actual_type}'")

    # Typ-spezifische Validierung
    if expected_type.upper() == "TASK":
        details["checked"].append("task_content")
        if "content" not in message or not message.get("content"):
            issues.append("TASK-Nachricht muss 'content' enthalten")

    elif expected_type.upper() == "RESULT":
        details["checked"].append("result_content")
        if "result" not in message:
            issues.append("RESULT-Nachricht muss 'result' enthalten")
        if "status" not in message:
            warnings.append("RESULT-Nachricht sollte 'status' enthalten")

    elif expected_type.upper() == "QUESTION":
        details["checked"].append("question_content")
        if "question" not in message or not message.get("question"):
            issues.append("QUESTION-Nachricht muss 'question' enthalten")
        if "target" not in message:
            warnings.append("QUESTION-Nachricht sollte 'target' (Ziel-Agent) enthalten")

    elif expected_type.upper() == "STATUS":
        details["checked"].append("status_content")
        if "status" not in message:
            issues.append("STATUS-Nachricht muss 'status' enthalten")
        if message.get("status") not in VALID_AGENT_STATUSES:
            warnings.append(f"Unbekannter Status '{message.get('status')}'")

    elif expected_type.upper() == "ERROR":
        details["checked"].append("error_content")
        if "error" not in message or not message.get("error"):
            issues.append("ERROR-Nachricht muss 'error' enthalten")
        if "severity" not in message:
            warnings.append("ERROR-Nachricht sollte 'severity' enthalten")

    score = 1.0 - (len(issues) * 0.3) - (len(warnings) * 0.1)
    score = max(0.0, min(1.0, score))

    return ValidationResult(
        passed=len(issues) == 0,
        issues=issues,
        warnings=warnings,
        score=score,
        details=details
    )
