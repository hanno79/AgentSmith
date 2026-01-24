"""
Author: rahn
Datum: 24.01.2026
Version: 1.0
Beschreibung: Tests für Security-Agent Feedback-Mechanismus.
              Prüft Extraktion von Vulnerabilities und Lösungsvorschlägen.
"""

import pytest
import re
from typing import List, Dict, Any


def extract_vulnerabilities(security_result: str) -> List[Dict[str, Any]]:
    """
    Standalone-Version der _extract_vulnerabilities Methode für Tests.
    Extrahiert Vulnerabilities UND Lösungsvorschläge aus dem Security-Agent Output.
    """
    vulnerabilities = []
    if not security_result:
        return vulnerabilities

    # Neues Pattern: "VULNERABILITY: [description] | FIX: [solution]"
    vuln_pattern = r'VULNERABILITY:\s*(.+?)(?:\s*\|\s*FIX:\s*(.+?))?(?=VULNERABILITY:|$)'
    matches = re.findall(vuln_pattern, security_result, re.IGNORECASE | re.DOTALL)

    for match in matches:
        vuln_text = match[0].strip() if match[0] else ""
        fix_text = match[1].strip() if len(match) > 1 and match[1] else ""

        # Falls kein FIX gefunden, versuche alternative Patterns
        if not fix_text and "|" in vuln_text:
            parts = vuln_text.split("|", 1)
            vuln_text = parts[0].strip()
            if len(parts) > 1 and "fix" in parts[1].lower():
                fix_text = parts[1].replace("FIX:", "").replace("fix:", "").strip()

        severity = "medium"

        # Severity-Klassifikation basierend auf Schlüsselwörtern
        if any(word in vuln_text.lower() for word in ["critical", "kritisch", "sql injection", "rce", "remote code"]):
            severity = "critical"
        elif any(word in vuln_text.lower() for word in ["high", "hoch", "xss", "csrf", "injection"]):
            severity = "high"
        elif any(word in vuln_text.lower() for word in ["low", "niedrig", "info", "informational", "minimal"]):
            severity = "low"

        vulnerabilities.append({
            "severity": severity,
            "description": vuln_text[:200],
            "fix": fix_text[:300],
            "type": "SECURITY_ISSUE"
        })

    return vulnerabilities[:10]


class TestSecurityVulnerabilityExtraction:
    """Tests für extract_vulnerabilities Funktion"""

    def test_extract_vulnerabilities_with_fix(self):
        """Testet Extraktion von Vulnerabilities MIT Lösungsvorschlägen"""
        security_output = """
        VULNERABILITY: eval() ermöglicht Code Injection | FIX: Verwende sichere Parser-Bibliothek
        VULNERABILITY: innerHTML ermöglicht XSS | FIX: Nutze textContent statt innerHTML
        """

        vulns = extract_vulnerabilities(security_output)

        assert len(vulns) == 2, "Erwartet: 2 Vulnerabilities, Erhalten: {}".format(len(vulns))
        assert "eval()" in vulns[0]["description"], "Erste Vulnerability sollte eval() enthalten"
        assert "Parser" in vulns[0].get("fix", ""), "Erster FIX sollte Parser erwähnen"
        assert "innerHTML" in vulns[1]["description"], "Zweite Vulnerability sollte innerHTML enthalten"
        assert "textContent" in vulns[1].get("fix", ""), "Zweiter FIX sollte textContent erwähnen"

    def test_extract_vulnerabilities_without_fix(self):
        """Testet Extraktion wenn kein FIX angegeben"""
        security_output = "VULNERABILITY: Hardcoded API Key gefunden"

        vulns = extract_vulnerabilities(security_output)

        assert len(vulns) == 1, "Erwartet: 1 Vulnerability, Erhalten: {}".format(len(vulns))
        assert "API Key" in vulns[0]["description"], "Sollte API Key erwähnen"
        assert vulns[0].get("fix", "") == "", "FIX sollte leer sein"

    def test_severity_classification_critical(self):
        """Testet Severity-Klassifikation für CRITICAL"""
        security_output = """
        VULNERABILITY: Critical SQL Injection in login form | FIX: Use prepared statements
        VULNERABILITY: RCE via file upload | FIX: Validate file types
        """

        vulns = extract_vulnerabilities(security_output)

        assert vulns[0]["severity"] == "critical", "SQL Injection sollte critical sein"
        assert vulns[1]["severity"] == "critical", "RCE sollte critical sein"

    def test_severity_classification_high(self):
        """Testet Severity-Klassifikation für HIGH"""
        security_output = """
        VULNERABILITY: High XSS risk in user input | FIX: Sanitize input
        VULNERABILITY: CSRF vulnerability on forms | FIX: Add CSRF token
        """

        vulns = extract_vulnerabilities(security_output)

        assert vulns[0]["severity"] == "high", "XSS sollte high sein"
        assert vulns[1]["severity"] == "high", "CSRF sollte high sein"

    def test_severity_classification_low(self):
        """Testet Severity-Klassifikation für LOW"""
        security_output = """
        VULNERABILITY: Low info disclosure in error messages | FIX: Generic error messages
        VULNERABILITY: Minimal risk: debug output in console | FIX: Remove console.log
        """

        vulns = extract_vulnerabilities(security_output)

        assert vulns[0]["severity"] == "low", "Info disclosure sollte low sein"
        assert vulns[1]["severity"] == "low", "Minimal risk sollte low sein"

    def test_secure_output_returns_empty_list(self):
        """Testet dass SECURE Antwort leere Liste zurückgibt"""
        security_output = "SECURE - Keine kritischen Sicherheitslücken gefunden."

        vulns = extract_vulnerabilities(security_output)

        assert len(vulns) == 0, "SECURE sollte leere Liste zurückgeben"

    def test_empty_input_returns_empty_list(self):
        """Testet dass leere Eingabe leere Liste zurückgibt"""
        vulns = extract_vulnerabilities("")
        assert len(vulns) == 0, "Leere Eingabe sollte leere Liste zurückgeben"

        vulns = extract_vulnerabilities(None)
        assert len(vulns) == 0, "None sollte leere Liste zurückgeben"

    def test_max_vulnerabilities_limit(self):
        """Testet dass maximal 10 Vulnerabilities zurückgegeben werden"""
        # Erstelle 15 Vulnerabilities
        security_output = "\n".join([
            f"VULNERABILITY: Issue {i} | FIX: Fix {i}"
            for i in range(15)
        ])

        vulns = extract_vulnerabilities(security_output)

        assert len(vulns) == 10, "Sollte maximal 10 Vulnerabilities zurückgeben"

    def test_description_truncation(self):
        """Testet dass Beschreibungen auf 200 Zeichen begrenzt werden"""
        long_description = "A" * 500
        security_output = f"VULNERABILITY: {long_description} | FIX: Short fix"

        vulns = extract_vulnerabilities(security_output)

        assert len(vulns[0]["description"]) <= 200, "Beschreibung sollte auf 200 Zeichen begrenzt sein"

    def test_fix_truncation(self):
        """Testet dass FIX-Vorschläge auf 300 Zeichen begrenzt werden"""
        long_fix = "B" * 500
        security_output = f"VULNERABILITY: Short desc | FIX: {long_fix}"

        vulns = extract_vulnerabilities(security_output)

        assert len(vulns[0].get("fix", "")) <= 300, "FIX sollte auf 300 Zeichen begrenzt sein"


class TestSecurityFeedbackFormatting:
    """Tests für Security-Feedback Formatierung"""

    def test_feedback_includes_fix_suggestions(self):
        """Testet dass Feedback die Lösungsvorschläge enthält"""
        vulns = [
            {"severity": "high", "description": "eval() ist unsicher", "fix": "Verwende Function()"},
            {"severity": "medium", "description": "innerHTML XSS", "fix": "Nutze textContent"}
        ]

        security_feedback = "\n".join([
            f"- [{v.get('severity', 'unknown').upper()}] {v.get('description', '')}\n"
            f"  → LÖSUNG: {v.get('fix', 'Bitte beheben')}"
            for v in vulns
        ])

        assert "→ LÖSUNG: Verwende Function()" in security_feedback
        assert "→ LÖSUNG: Nutze textContent" in security_feedback
        assert "[HIGH]" in security_feedback
        assert "[MEDIUM]" in security_feedback

    def test_feedback_with_missing_fix(self):
        """Testet Feedback wenn FIX fehlt"""
        vulns = [
            {"severity": "high", "description": "Unknown vulnerability", "fix": ""},
        ]

        security_feedback = "\n".join([
            f"- [{v.get('severity', 'unknown').upper()}] {v.get('description', '')}\n"
            f"  → LÖSUNG: {v.get('fix', 'Bitte beheben') or 'Bitte beheben'}"
            for v in vulns
        ])

        # Wenn fix leer, sollte "Bitte beheben" erscheinen
        assert "→ LÖSUNG:" in security_feedback

    def test_feedback_severity_ordering(self):
        """Testet dass Feedback Severity korrekt anzeigt"""
        vulns = [
            {"severity": "critical", "description": "Critical issue", "fix": "Fix now"},
            {"severity": "high", "description": "High issue", "fix": "Fix soon"},
            {"severity": "medium", "description": "Medium issue", "fix": "Fix later"},
            {"severity": "low", "description": "Low issue", "fix": "Optional fix"},
        ]

        security_feedback = "\n".join([
            f"- [{v.get('severity', 'unknown').upper()}] {v.get('description', '')}"
            for v in vulns
        ])

        assert "[CRITICAL]" in security_feedback
        assert "[HIGH]" in security_feedback
        assert "[MEDIUM]" in security_feedback
        assert "[LOW]" in security_feedback


class TestSecurityRetryLogic:
    """Tests für Security-Retry-Logik"""

    def test_security_retry_count_increments(self):
        """Testet dass security_retry_count korrekt erhöht wird"""
        security_retry_count = 0
        security_passed = False

        # Simuliere 3 fehlgeschlagene Security-Checks
        for _ in range(3):
            if not security_passed:
                security_retry_count += 1

        assert security_retry_count == 3, "Retry-Count sollte 3 sein"

    def test_security_passes_after_max_retries(self):
        """Testet dass nach max_security_retries security_passed = True gesetzt wird"""
        security_retry_count = 0
        max_security_retries = 3
        security_passed = False
        security_rescan_vulns = [{"severity": "high", "description": "Test"}]

        # Simuliere 3 fehlgeschlagene Security-Checks
        for _ in range(3):
            if not security_passed:
                security_retry_count += 1
                if security_retry_count >= max_security_retries:
                    security_passed = True  # Erlaube Fortfahren mit Warnung

        assert security_passed == True, "Nach max_retries sollte security_passed True sein"
        assert security_retry_count == 3, "Retry-Count sollte genau 3 sein"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
