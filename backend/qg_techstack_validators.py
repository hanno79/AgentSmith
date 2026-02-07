# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 01.02.2026
Version: 1.0
Beschreibung: Quality Gate TechStack-bezogene Validierungen.
              Extrahiert aus quality_gate.py (Regel 1: Max 500 Zeilen)

              Enthält:
              - validate_techstack
              - validate_schema
              - validate_code
              - validate_design
"""

from typing import Dict, Any

from backend.validation_result import ValidationResult
from backend.qg_constants import DB_INDICATORS, FRAMEWORK_INDICATORS


def validate_techstack(
    requirements: Dict[str, Any],
    blueprint: Dict[str, Any]
) -> ValidationResult:
    """
    Validiert TechStack-Blueprint gegen Benutzer-Anforderungen.

    Args:
        requirements: Extrahierte Anforderungen
        blueprint: Das TechStack-Blueprint Dictionary

    Returns:
        ValidationResult mit passed/failed Status und Details
    """
    issues = []
    warnings = []
    details = {"checked": [], "blueprint": blueprint}

    # Prüfung 1: Datenbank-Vorgabe respektiert?
    if requirements.get("database"):
        details["checked"].append("database")
        required_db = requirements["database"]
        blueprint_db = blueprint.get("database")

        if required_db != "generic_db":  # generic_db = irgendeine DB, nicht spezifisch
            if not blueprint_db:
                issues.append(
                    f"Benutzer forderte Datenbank '{required_db}', "
                    f"aber Blueprint enthält keine Datenbank-Angabe"
                )
            elif blueprint_db != required_db:
                issues.append(
                    f"Benutzer forderte '{required_db}', "
                    f"aber Blueprint hat '{blueprint_db}'"
                )

    # Prüfung 2: Sprach-Vorgabe respektiert?
    if requirements.get("language"):
        details["checked"].append("language")
        required_lang = requirements["language"]
        blueprint_lang = blueprint.get("language")

        if blueprint_lang and blueprint_lang != required_lang:
            issues.append(
                f"Benutzer forderte Sprache '{required_lang}', "
                f"aber Blueprint hat '{blueprint_lang}'"
            )

    # Prüfung 3: Framework-Vorgabe respektiert?
    if requirements.get("framework"):
        details["checked"].append("framework")
        required_fw = requirements["framework"]
        blueprint_type = blueprint.get("project_type", "")

        # Prüfe ob Framework im project_type enthalten ist
        if required_fw.lower() not in blueprint_type.lower():
            warnings.append(
                f"Benutzer erwähnte Framework '{required_fw}', "
                f"aber project_type ist '{blueprint_type}'"
            )

    # Prüfung 4: UI-Typ passend?
    if requirements.get("ui_type"):
        details["checked"].append("ui_type")
        required_ui = requirements["ui_type"]
        blueprint_app_type = blueprint.get("app_type")

        if required_ui == "desktop" and blueprint_app_type != "desktop":
            issues.append(
                f"Benutzer forderte Desktop-App, "
                f"aber Blueprint hat app_type '{blueprint_app_type}'"
            )
        elif required_ui == "api" and blueprint_app_type not in ["api", "webapp"]:
            warnings.append(
                f"Benutzer forderte API, "
                f"aber Blueprint hat app_type '{blueprint_app_type}'"
            )

    # Prüfung 5: Konsistenz-Check
    if blueprint.get("requires_server") and not blueprint.get("server_port"):
        warnings.append("requires_server=true aber kein server_port definiert")

    # Score berechnen
    score = 1.0 - (len(issues) * 0.3) - (len(warnings) * 0.1)
    score = max(0.0, min(1.0, score))

    passed = len(issues) == 0
    details["requirements"] = requirements

    return ValidationResult(
        passed=passed,
        issues=issues,
        warnings=warnings,
        score=score,
        details=details
    )


def validate_schema(
    requirements: Dict[str, Any],
    schema: str,
    blueprint: Dict[str, Any]
) -> ValidationResult:
    """
    Validiert DB-Schema gegen Blueprint und Anforderungen.

    Args:
        requirements: Extrahierte Anforderungen
        schema: Das generierte Datenbank-Schema (SQL oder andere)
        blueprint: Das TechStack-Blueprint

    Returns:
        ValidationResult
    """
    issues = []
    warnings = []
    details = {"checked": []}

    # Prüfung 1: Schema sollte existieren wenn Datenbank gefordert
    if requirements.get("database") and not schema:
        issues.append("Datenbank wurde gefordert, aber kein Schema generiert")

    # Prüfung 2: Schema-Typ passt zu Blueprint
    if schema and blueprint.get("database"):
        db_type = blueprint["database"]
        details["checked"].append("schema_type")

        # Einfache Heuristik für Schema-Typ-Erkennung
        schema_lower = schema.lower()
        if db_type == "sqlite" and "sqlite" not in schema_lower:
            if "create table" not in schema_lower:
                warnings.append("Schema enthält keine SQL CREATE TABLE Statements")
        elif db_type == "mongodb":
            if "collection" not in schema_lower and "schema" not in schema_lower:
                warnings.append("MongoDB-Schema sollte Collections definieren")

    # Prüfung 3: Schema nicht leer
    if schema and len(schema.strip()) < 50:
        warnings.append("Schema erscheint sehr kurz/unvollständig")

    score = 1.0 - (len(issues) * 0.3) - (len(warnings) * 0.1)
    score = max(0.0, min(1.0, score))

    return ValidationResult(
        passed=len(issues) == 0,
        issues=issues,
        warnings=warnings,
        score=score,
        details=details
    )


def validate_code(
    requirements: Dict[str, Any],
    code: str,
    blueprint: Dict[str, Any]
) -> ValidationResult:
    """
    Validiert generierten Code gegen Blueprint.

    Args:
        requirements: Extrahierte Anforderungen
        code: Der generierte Code
        blueprint: Das TechStack-Blueprint

    Returns:
        ValidationResult
    """
    issues = []
    warnings = []
    details = {"checked": []}

    if not code or len(code.strip()) < 10:
        issues.append("Kein oder leerer Code generiert")
        return ValidationResult(passed=False, issues=issues, score=0.0, details={"checked": []})

    code_lower = code.lower()
    language = blueprint.get("language", "")

    # Prüfung 1: Sprache passt
    details["checked"].append("language_indicators")
    if language == "python":
        if "def " not in code and "class " not in code and "import " not in code:
            warnings.append("Python-Code enthält keine typischen Python-Keywords")
    elif language == "javascript":
        if "function " not in code and "const " not in code and "let " not in code:
            warnings.append("JavaScript-Code enthält keine typischen JS-Keywords")

    # Prüfung 2: Datenbank-Integration wenn gefordert
    if requirements.get("database"):
        details["checked"].append("database_usage")
        db = requirements["database"]

        if db in DB_INDICATORS:
            if not any(ind in code_lower for ind in DB_INDICATORS[db]):
                warnings.append(
                    f"Datenbank '{db}' wurde gefordert, "
                    f"aber keine entsprechenden Imports/Verwendung im Code gefunden"
                )

    # Prüfung 3: Framework-Verwendung wenn im Blueprint
    project_type = blueprint.get("project_type", "")
    details["checked"].append("framework_usage")

    for fw, indicators in FRAMEWORK_INDICATORS.items():
        if fw in project_type.lower():
            if not any(ind in code for ind in indicators):
                warnings.append(
                    f"project_type enthält '{fw}', "
                    f"aber keine entsprechenden Imports im Code"
                )
            break

    score = 1.0 - (len(issues) * 0.3) - (len(warnings) * 0.1)
    score = max(0.0, min(1.0, score))

    return ValidationResult(
        passed=len(issues) == 0,
        issues=issues,
        warnings=warnings,
        score=score,
        details=details
    )


def validate_design(
    design_concept: str,
    blueprint: Dict[str, Any]
) -> ValidationResult:
    """
    Validiert Design-Konzept gegen Blueprint und Anforderungen.

    Args:
        design_concept: Das generierte Design-Konzept
        blueprint: Das TechStack-Blueprint

    Returns:
        ValidationResult
    """
    issues = []
    warnings = []

    if not design_concept or len(design_concept.strip()) < 50:
        warnings.append("Design-Konzept erscheint sehr kurz")

    # Design sollte zum app_type passen
    app_type = blueprint.get("app_type", "")
    design_lower = design_concept.lower() if design_concept else ""

    if app_type == "desktop":
        if "fenster" not in design_lower and "window" not in design_lower and "gui" not in design_lower:
            warnings.append("Desktop-App Design sollte Fenster/GUI-Elemente beschreiben")
    elif app_type == "webapp":
        if "seite" not in design_lower and "page" not in design_lower and "layout" not in design_lower:
            warnings.append("Webapp Design sollte Seiten/Layout beschreiben")

    score = 1.0 - (len(issues) * 0.3) - (len(warnings) * 0.1)
    score = max(0.0, min(1.0, score))

    return ValidationResult(
        passed=len(issues) == 0,
        issues=issues,
        warnings=warnings,
        score=score
    )
