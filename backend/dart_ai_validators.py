# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 31.01.2026
Version: 1.0
Beschreibung: Dart AI Feature-Ableitung Validatoren (aus quality_gate.py ausgelagert).
"""

from typing import Dict, Any, List

from backend.validation_result import ValidationResult


def validate_anforderungen(
    analyst_output: Dict[str, Any],
    briefing: Dict[str, Any]
) -> ValidationResult:
    """
    Validiert die Anforderungsanalyse des Analyst-Agenten.

    Args:
        analyst_output: Output des Analyst-Agenten
        briefing: Das Discovery-Briefing

    Returns:
        ValidationResult
    """
    issues = []
    warnings = []
    details = {"checked": []}

    anforderungen = analyst_output.get("anforderungen", [])

    details["checked"].append("minimum_requirements")
    if not anforderungen:
        issues.append("Keine Anforderungen extrahiert")
        return ValidationResult(passed=False, issues=issues, score=0.0)

    details["checked"].append("required_fields")
    required_fields = ["id", "titel", "beschreibung", "kategorie", "prioritaet"]
    for req in anforderungen:
        missing = [f for f in required_fields if not req.get(f)]
        if missing:
            warnings.append(
                f"Anforderung {req.get('id', '?')} fehlt: {', '.join(missing)}"
            )

    details["checked"].append("unique_ids")
    ids = [req.get("id") for req in anforderungen if req.get("id")]
    if len(ids) != len(set(ids)):
        issues.append("Doppelte Anforderungs-IDs gefunden")

    details["checked"].append("consistent_categories")
    kategorien = analyst_output.get("kategorien", [])
    for req in anforderungen:
        if req.get("kategorie") and req["kategorie"] not in kategorien:
            warnings.append(
                f"Anforderung {req.get('id', '?')} hat unbekannte Kategorie: {req['kategorie']}"
            )

    details["checked"].append("briefing_coverage")
    answers = briefing.get("answers", [])
    non_skipped = [a for a in answers if not a.get("skipped", False)]
    if non_skipped and len(anforderungen) < len(non_skipped) * 0.5:
        warnings.append(
            f"Nur {len(anforderungen)} Anforderungen fuer {len(non_skipped)} Discovery-Antworten"
        )

    score = 1.0 - (len(issues) * 0.3) - (len(warnings) * 0.1)
    score = max(0.0, min(1.0, score))

    details["total_anforderungen"] = len(anforderungen)
    details["kategorien"] = kategorien

    return ValidationResult(
        passed=len(issues) == 0,
        issues=issues,
        warnings=warnings,
        score=score,
        details=details
    )


def validate_features(
    konzepter_output: Dict[str, Any],
    anforderungen: List[Dict[str, Any]]
) -> ValidationResult:
    """
    Validiert die Feature-Extraktion des Konzepter-Agenten.

    Args:
        konzepter_output: Output des Konzepter-Agenten
        anforderungen: Die Anforderungen vom Analyst

    Returns:
        ValidationResult
    """
    issues = []
    warnings = []
    details = {"checked": []}

    features = konzepter_output.get("features", [])
    traceability = konzepter_output.get("traceability", {})

    details["checked"].append("minimum_features")
    if not features:
        issues.append("Keine Features extrahiert")
        return ValidationResult(passed=False, issues=issues, score=0.0)

    details["checked"].append("required_fields")
    required_fields = ["id", "titel", "anforderungen"]
    for feat in features:
        missing = [f for f in required_fields if not feat.get(f)]
        if missing:
            warnings.append(
                f"Feature {feat.get('id', '?')} fehlt: {', '.join(missing)}"
            )

    details["checked"].append("unique_ids")
    ids = [feat.get("id") for feat in features if feat.get("id")]
    if len(ids) != len(set(ids)):
        issues.append("Doppelte Feature-IDs gefunden")

    details["checked"].append("traceability_complete")
    req_ids = {req.get("id") for req in anforderungen if req.get("id")}
    covered_reqs = set(traceability.keys())
    uncovered = req_ids - covered_reqs
    if uncovered:
        warnings.append(
            f"{len(uncovered)} Anforderungen ohne Features: {', '.join(list(uncovered)[:3])}"
        )

    details["checked"].append("valid_references")
    for feat in features:
        for ref in feat.get("anforderungen", []):
            if ref not in req_ids:
                warnings.append(
                    f"Feature {feat.get('id', '?')} referenziert unbekannte Anforderung: {ref}"
                )

    details["checked"].append("file_estimates")
    for feat in features:
        est_files = feat.get("geschaetzte_dateien", 0)
        if est_files > 3:
            warnings.append(
                f"Feature {feat.get('id', '?')} hat {est_files} geschaetzte Dateien (max. 3 empfohlen)"
            )

    score = 1.0 - (len(issues) * 0.3) - (len(warnings) * 0.1)
    score = max(0.0, min(1.0, score))

    coverage = len(covered_reqs) / len(req_ids) if req_ids else 0.0
    details["total_features"] = len(features)
    details["traceability_coverage"] = coverage

    return ValidationResult(
        passed=len(issues) == 0,
        issues=issues,
        warnings=warnings,
        score=score,
        details=details
    )


def validate_file_by_file_plan(
    plan: Dict[str, Any],
    blueprint: Dict[str, Any]
) -> ValidationResult:
    """
    Validiert den File-by-File Generierungsplan.

    Args:
        plan: Der Plan vom Planner-Agenten
        blueprint: Das TechStack-Blueprint

    Returns:
        ValidationResult
    """
    issues = []
    warnings = []
    details = {"checked": []}

    files = plan.get("files", [])

    details["checked"].append("minimum_files")
    if not files:
        issues.append("Keine Dateien im Plan")
        return ValidationResult(passed=False, issues=issues, score=0.0)

    details["checked"].append("required_fields")
    for file_info in files:
        if not file_info.get("path"):
            issues.append("Datei ohne Pfad im Plan")
        if not file_info.get("description"):
            warnings.append(f"Datei {file_info.get('path', '?')} ohne Beschreibung")

    details["checked"].append("unique_paths")
    paths = [f.get("path") for f in files if f.get("path")]
    if len(paths) != len(set(paths)):
        issues.append("Doppelte Datei-Pfade im Plan")

    details["checked"].append("valid_dependencies")
    path_set = set(paths)
    for file_info in files:
        for dep in file_info.get("depends_on", []):
            if dep not in path_set:
                warnings.append(
                    f"Datei {file_info.get('path', '?')} hat unbekannte Abhaengigkeit: {dep}"
                )

    details["checked"].append("no_circular_deps")
    for file_info in files:
        path = file_info.get("path", "")
        if path in file_info.get("depends_on", []):
            issues.append(f"Datei {path} haengt von sich selbst ab")

    details["checked"].append("language_match")
    language = blueprint.get("language", "python").lower()
    expected_extensions = {
        "python": [".py"],
        "javascript": [".js", ".jsx", ".ts", ".tsx"],
        "java": [".java"],
        "go": [".go"]
    }

    if language in expected_extensions:
        exts = expected_extensions[language]
        code_files = [f for f in files if not f.get("path", "").endswith((".txt", ".md", ".json", ".bat", ".sh"))]
        for file_info in code_files:
            path = file_info.get("path", "")
            if not any(path.endswith(ext) for ext in exts):
                warnings.append(
                    f"Datei {path} hat unerwartete Endung fuer {language}"
                )

    score = 1.0 - (len(issues) * 0.3) - (len(warnings) * 0.1)
    score = max(0.0, min(1.0, score))

    details["total_files"] = len(files)

    return ValidationResult(
        passed=len(issues) == 0,
        issues=issues,
        warnings=warnings,
        score=score,
        details=details
    )


def validate_file_by_file_output(
    created_files: List[str],
    plan: Dict[str, Any],
    max_lines_per_file: int = 200
) -> ValidationResult:
    """
    Validiert den File-by-File Output gegen den Plan.

    Args:
        created_files: Liste der erfolgreich erstellten Dateien
        plan: Der urspruengliche Plan
        max_lines_per_file: Maximale erlaubte Zeilen pro Datei

    Returns:
        ValidationResult
    """
    issues = []
    warnings = []
    details = {"checked": []}

    planned_files = plan.get("files", [])
    planned_paths = {f.get("path") for f in planned_files if f.get("path")}

    details["checked"].append("completeness")
    created_set = set(created_files)
    missing = planned_paths - created_set
    if missing:
        if len(missing) > len(planned_paths) * 0.3:
            issues.append(f"{len(missing)} von {len(planned_paths)} Dateien fehlen")
        else:
            warnings.append(f"{len(missing)} Dateien nicht erstellt: {', '.join(list(missing)[:3])}")

    details["checked"].append("no_unexpected")
    unexpected = created_set - planned_paths
    if unexpected:
        warnings.append(f"{len(unexpected)} unerwartete Dateien erstellt")

    details["checked"].append("success_rate")
    if planned_paths:
        success_rate = len(created_set & planned_paths) / len(planned_paths)
        if success_rate < 0.7:
            issues.append(f"Erfolgsrate nur {success_rate:.0%}")
        elif success_rate < 0.9:
            warnings.append(f"Erfolgsrate {success_rate:.0%}")

    details["checked"].append("max_lines_per_file")
    for filepath in created_files:
        try:
            with open(filepath, encoding="utf-8", errors="ignore") as f:
                line_count = sum(1 for _ in f)
            if line_count > max_lines_per_file:
                warnings.append(
                    f"Datei {filepath} hat {line_count} Zeilen (max. {max_lines_per_file})"
                )
        except (OSError, IOError):
            warnings.append(f"Datei {filepath} konnte nicht geoeffnet werden (Zeilen-Check uebersprungen)")

    score = 1.0 - (len(issues) * 0.3) - (len(warnings) * 0.1)
    score = max(0.0, min(1.0, score))

    details["planned_count"] = len(planned_paths)
    details["created_count"] = len(created_files)
    details["missing_count"] = len(missing) if missing else 0

    return ValidationResult(
        passed=len(issues) == 0,
        issues=issues,
        warnings=warnings,
        score=score,
        details=details
    )
