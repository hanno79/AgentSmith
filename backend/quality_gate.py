# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 30.01.2026
Version: 1.0
Beschreibung: Quality Gate - Inhaltliche Qualitätskontrolle zwischen Agent-Steps.
              Prüft ob Agent-Outputs den Benutzer-Anforderungen entsprechen.
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
import re


@dataclass
class ValidationResult:
    """Ergebnis einer Qualitätsprüfung."""
    passed: bool
    issues: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    score: float = 1.0  # 0.0 bis 1.0
    details: Dict[str, Any] = field(default_factory=dict)


class QualityGate:
    """
    Prüft Agent-Outputs auf inhaltliche Qualität und Anforderungs-Konformität.

    Diese Klasse validiert, dass die Ergebnisse der verschiedenen Agenten
    den ursprünglichen Benutzer-Anforderungen entsprechen.
    """

    # Keyword-Mappings für Anforderungs-Extraktion
    DB_KEYWORDS = {
        "sqlite": "sqlite", "postgres": "postgres", "postgresql": "postgres",
        "mysql": "mysql", "mariadb": "mysql", "mongodb": "mongodb", "mongo": "mongodb",
        "redis": "redis", "elasticsearch": "elasticsearch", "neo4j": "neo4j",
        "datenbank": "generic_db", "database": "generic_db"
    }

    LANG_KEYWORDS = {
        "python": "python", "javascript": "javascript", "typescript": "javascript",
        "node": "javascript", "java": "java", "kotlin": "kotlin",
        "go": "go", "golang": "go", "rust": "rust", "c++": "cpp", "c#": "csharp"
    }

    FRAMEWORK_KEYWORDS = {
        "flask": "flask", "fastapi": "fastapi", "django": "django",
        "express": "express", "react": "react", "vue": "vue", "angular": "angular",
        "tkinter": "tkinter", "pyqt": "pyqt", "electron": "electron",
        "streamlit": "streamlit", "gradio": "gradio"
    }

    UI_TYPE_KEYWORDS = {
        "desktop": ["desktop", "fenster", "gui", "window"],
        "webapp": ["webapp", "website", "webseite", "browser", "web app"],
        "api": ["api", "rest", "endpoint", "backend", "service"],
        "cli": ["cli", "kommandozeile", "terminal", "console", "command line"]
    }

    def __init__(self, user_goal: str, briefing: Optional[Dict[str, Any]] = None):
        """
        Initialisiert das Quality Gate.

        Args:
            user_goal: Das ursprüngliche Benutzer-Ziel (VERBINDLICH)
            briefing: Optional Discovery-Briefing mit zusätzlichen Details
        """
        self.user_goal = user_goal
        self.briefing = briefing or {}
        self.requirements = self._extract_requirements()

    def _extract_requirements(self) -> Dict[str, Any]:
        """
        Extrahiert prüfbare Anforderungen aus user_goal.

        NUR Benutzer-Vorgaben zählen als verbindlich!
        Researcher-Vorschläge werden hier NICHT berücksichtigt.

        Returns:
            Dictionary mit erkannten Anforderungen
        """
        goal_lower = self.user_goal.lower()
        requirements = {}

        # Datenbank-Vorgaben
        for keyword, db_type in self.DB_KEYWORDS.items():
            if keyword in goal_lower:
                requirements["database"] = db_type
                break

        # Sprach-Vorgaben
        for keyword, lang in self.LANG_KEYWORDS.items():
            if keyword in goal_lower:
                requirements["language"] = lang
                break

        # Framework-Vorgaben
        for keyword, fw in self.FRAMEWORK_KEYWORDS.items():
            if keyword in goal_lower:
                requirements["framework"] = fw
                break

        # UI-Typ
        for ui_type, keywords in self.UI_TYPE_KEYWORDS.items():
            if any(kw in goal_lower for kw in keywords):
                requirements["ui_type"] = ui_type
                break

        return requirements

    def validate_techstack(self, blueprint: Dict[str, Any]) -> ValidationResult:
        """
        Validiert TechStack-Blueprint gegen Benutzer-Anforderungen.

        Args:
            blueprint: Das TechStack-Blueprint Dictionary

        Returns:
            ValidationResult mit passed/failed Status und Details
        """
        issues = []
        warnings = []
        details = {"checked": [], "blueprint": blueprint}

        # Prüfung 1: Datenbank-Vorgabe respektiert?
        if self.requirements.get("database"):
            details["checked"].append("database")
            required_db = self.requirements["database"]
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
        if self.requirements.get("language"):
            details["checked"].append("language")
            required_lang = self.requirements["language"]
            blueprint_lang = blueprint.get("language")

            if blueprint_lang and blueprint_lang != required_lang:
                issues.append(
                    f"Benutzer forderte Sprache '{required_lang}', "
                    f"aber Blueprint hat '{blueprint_lang}'"
                )

        # Prüfung 3: Framework-Vorgabe respektiert?
        if self.requirements.get("framework"):
            details["checked"].append("framework")
            required_fw = self.requirements["framework"]
            blueprint_type = blueprint.get("project_type", "")

            # Prüfe ob Framework im project_type enthalten ist
            if required_fw.lower() not in blueprint_type.lower():
                warnings.append(
                    f"Benutzer erwähnte Framework '{required_fw}', "
                    f"aber project_type ist '{blueprint_type}'"
                )

        # Prüfung 4: UI-Typ passend?
        if self.requirements.get("ui_type"):
            details["checked"].append("ui_type")
            required_ui = self.requirements["ui_type"]
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
        # Jeder Issue reduziert Score um 0.3, jede Warning um 0.1
        score = 1.0 - (len(issues) * 0.3) - (len(warnings) * 0.1)
        score = max(0.0, min(1.0, score))  # Clamp zwischen 0 und 1

        passed = len(issues) == 0
        details["requirements"] = self.requirements

        return ValidationResult(
            passed=passed,
            issues=issues,
            warnings=warnings,
            score=score,
            details=details
        )

    def validate_schema(self, schema: str, blueprint: Dict[str, Any]) -> ValidationResult:
        """
        Validiert DB-Schema gegen Blueprint und Anforderungen.

        Args:
            schema: Das generierte Datenbank-Schema (SQL oder andere)
            blueprint: Das TechStack-Blueprint

        Returns:
            ValidationResult
        """
        issues = []
        warnings = []
        details = {"checked": []}

        # Prüfung 1: Schema sollte existieren wenn Datenbank gefordert
        if self.requirements.get("database") and not schema:
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

    def validate_code(self, code: str, blueprint: Dict[str, Any]) -> ValidationResult:
        """
        Validiert generierten Code gegen Blueprint.

        Args:
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
            return ValidationResult(passed=False, issues=issues, score=0.0)

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
        if self.requirements.get("database"):
            details["checked"].append("database_usage")
            db = self.requirements["database"]

            db_indicators = {
                "sqlite": ["sqlite", "sqlite3", "database", ".db"],
                "postgres": ["postgres", "psycopg", "asyncpg", "pg_"],
                "mysql": ["mysql", "pymysql", "mariadb"],
                "mongodb": ["mongo", "pymongo", "collection"]
            }

            if db in db_indicators:
                if not any(ind in code_lower for ind in db_indicators[db]):
                    warnings.append(
                        f"Datenbank '{db}' wurde gefordert, "
                        f"aber keine entsprechenden Imports/Verwendung im Code gefunden"
                    )

        # Prüfung 3: Framework-Verwendung wenn im Blueprint
        project_type = blueprint.get("project_type", "")
        details["checked"].append("framework_usage")

        framework_indicators = {
            "flask": ["from flask", "import flask", "Flask("],
            "fastapi": ["from fastapi", "import fastapi", "FastAPI("],
            "tkinter": ["import tkinter", "from tkinter", "Tk("],
            "pyqt": ["PyQt", "from PyQt", "QApplication"]
        }

        for fw, indicators in framework_indicators.items():
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

    def validate_design(self, design_concept: str, blueprint: Dict[str, Any]) -> ValidationResult:
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

    def validate_review(
        self,
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
            return ValidationResult(passed=False, issues=issues, score=0.0)

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
        self,
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

        severity_order = ["critical", "high", "medium", "low", "info"]
        threshold_index = severity_order.index(severity_threshold) if severity_threshold in severity_order else 1

        # Gruppiere Vulnerabilities nach Severity
        by_severity = {"critical": [], "high": [], "medium": [], "low": [], "info": []}
        for vuln in vulnerabilities:
            sev = vuln.get("severity", "info").lower()
            if sev in by_severity:
                by_severity[sev].append(vuln)

        details["vulnerabilities_by_severity"] = {k: len(v) for k, v in by_severity.items()}
        details["checked"].append("severity_check")

        # Prüfe ob blockierende Severities vorhanden
        for i, sev in enumerate(severity_order[:threshold_index + 1]):
            if by_severity[sev]:
                if sev in ["critical", "high"]:
                    issues.append(
                        f"{len(by_severity[sev])} {sev.upper()}-Severity Vulnerabilities gefunden"
                    )
                else:
                    warnings.append(
                        f"{len(by_severity[sev])} {sev.upper()}-Severity Vulnerabilities gefunden"
                    )

        # Score berechnen basierend auf Severity-Gewichtung
        severity_weights = {"critical": 0.4, "high": 0.25, "medium": 0.1, "low": 0.05, "info": 0.01}
        penalty = sum(len(by_severity[sev]) * severity_weights.get(sev, 0) for sev in by_severity)
        score = max(0.0, 1.0 - penalty)

        return ValidationResult(
            passed=len(issues) == 0,
            issues=issues,
            warnings=warnings,
            score=score,
            details=details
        )

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

        Args:
            code: Der finale Code
            tests_passed: Ob alle Tests bestanden haben
            review_passed: Ob das Review bestanden hat
            security_passed: Ob der Security-Check bestanden hat
            blueprint: Das TechStack-Blueprint

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
        code_validation = self.validate_code(code, blueprint)
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
        self,
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
            valid_statuses = ["working", "waiting", "completed", "failed", "blocked"]
            if message.get("status") not in valid_statuses:
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

    def get_requirements_summary(self) -> str:
        """
        Gibt eine lesbare Zusammenfassung der erkannten Anforderungen zurück.

        Returns:
            Formatierter String mit Anforderungen
        """
        if not self.requirements:
            return "Keine spezifischen Anforderungen erkannt."

        parts = []
        if self.requirements.get("database"):
            parts.append(f"Datenbank: {self.requirements['database']}")
        if self.requirements.get("language"):
            parts.append(f"Sprache: {self.requirements['language']}")
        if self.requirements.get("framework"):
            parts.append(f"Framework: {self.requirements['framework']}")
        if self.requirements.get("ui_type"):
            parts.append(f"UI-Typ: {self.requirements['ui_type']}")

        return ", ".join(parts) if parts else "Keine spezifischen Anforderungen erkannt."
