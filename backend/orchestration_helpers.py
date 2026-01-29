"""
Author: rahn
Datum: 29.01.2026
Version: 1.0
Beschreibung: Hilfsfunktionen fuer OrchestrationManager (Parsing/Formatting/Checks).
"""

import re
import time
from typing import Dict, Any, List

from logger_utils import log_event

# ÄNDERUNG 29.01.2026: Helper aus OrchestrationManager ausgelagert


def create_human_readable_verdict(verdict: str, sandbox_failed: bool, review_output: str) -> str:
    """
    Erstellt menschenlesbare Zusammenfassung des Reviews.

    Args:
        verdict: "OK" oder "FEEDBACK"
        sandbox_failed: True wenn Sandbox/Test Fehler hatte
        review_output: Vollständiger Review-Text

    Returns:
        Menschenlesbare Zusammenfassung mit Emoji
    """
    if verdict == "OK" and not sandbox_failed:
        return "✅ REVIEW BESTANDEN: Code erfüllt alle Anforderungen."
    if sandbox_failed:
        return "❌ REVIEW FEHLGESCHLAGEN: Sandbox/Test hat Fehler gemeldet."
    if review_output:
        first_sentence = review_output.split('.')[0][:100]
        return f"⚠️ ÄNDERUNGEN NÖTIG: {first_sentence}"
    return "⚠️ ÄNDERUNGEN NÖTIG: Bitte Feedback beachten."


def extract_tables_from_schema(schema: str) -> List[Dict[str, Any]]:
    """
    Extrahiert Tabellen-Informationen aus einem SQL-Schema-String.

    Args:
        schema: SQL-Schema als String

    Returns:
        Liste von Tabellen-Dictionaries mit name, columns, type
    """
    tables = []
    if not schema:
        return tables

    table_pattern = r'CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[\"\`]?(\w+)[\"\`]?\s*\((.*?)\);'
    matches = re.findall(table_pattern, schema, re.IGNORECASE | re.DOTALL)

    for match in matches:
        table_name = match[0]
        columns_str = match[1]
        columns = []
        for line in columns_str.split(','):
            line = line.strip()
            if line and not line.upper().startswith(('PRIMARY', 'FOREIGN', 'UNIQUE', 'CHECK', 'INDEX', 'CONSTRAINT')):
                col_match = re.match(r'[\"\`]?(\w+)[\"\`]?\s+(\w+)', line)
                if col_match:
                    col_name = col_match.group(1)
                    col_type = col_match.group(2)
                    is_primary = 'PRIMARY KEY' in line.upper()
                    is_foreign = 'REFERENCES' in line.upper() or 'FOREIGN' in line.upper()
                    columns.append({
                        "name": col_name,
                        "type": col_type,
                        "isPrimary": is_primary,
                        "isForeign": is_foreign
                    })

        tables.append({
            "name": table_name,
            "columns": columns,
            "type": "table"
        })

    return tables[:10]


def extract_vulnerabilities(security_result: str) -> List[Dict[str, Any]]:
    """
    Extrahiert Vulnerabilities UND Lösungsvorschläge aus dem Security-Agent Output.

    Args:
        security_result: Rohtext-Ergebnis der Sicherheitsanalyse

    Returns:
        Liste von Vulnerability-Dictionaries mit severity, description, fix, type
    """
    vulnerabilities = []
    if not security_result:
        return vulnerabilities

    full_pattern = r'VULNERABILITY:\s*(.+?)\s*\|\s*FIX:\s*(.+?)\s*\|\s*SEVERITY:\s*(\w+)'
    full_matches = re.findall(full_pattern, security_result, re.IGNORECASE | re.DOTALL)

    for match in full_matches:
        vuln_text = match[0].strip()
        fix_text = match[1].strip()
        severity_text = match[2].strip().lower()

        severity = severity_text if severity_text in ["critical", "high", "medium", "low"] else "medium"

        file_match = re.search(
            r'(?:in|file|datei|zeile\s+\d+\s+in)\s+["\']?([a-zA-Z0-9_./\\-]+\.[a-z]{2,4})["\']?',
            vuln_text,
            re.IGNORECASE
        )
        affected_file = file_match.group(1) if file_match else None

        vulnerabilities.append({
            "severity": severity,
            "description": vuln_text[:2000],
            "fix": fix_text[:5000],
            "affected_file": affected_file,
            "type": "SECURITY_ISSUE"
        })

    if not vulnerabilities:
        old_pattern = r'VULNERABILITY:\s*(.+?)(?:\s*\|\s*FIX:\s*(.+?))?(?=VULNERABILITY:|$)'
        old_matches = re.findall(old_pattern, security_result, re.IGNORECASE | re.DOTALL)

        for match in old_matches:
            vuln_text = match[0].strip() if match[0] else ""
            fix_text = match[1].strip() if len(match) > 1 and match[1] else ""

            if not fix_text and "|" in vuln_text:
                parts = vuln_text.split("|", 1)
                vuln_text = parts[0].strip()
                if len(parts) > 1 and "fix" in parts[1].lower():
                    fix_text = parts[1].replace("FIX:", "").replace("fix:", "").strip()

            severity = "medium"
            if any(word in vuln_text.lower() for word in ["critical", "kritisch", "sql injection", "rce", "remote code"]):
                severity = "critical"
            elif any(word in vuln_text.lower() for word in ["high", "hoch", "xss", "csrf", "injection"]):
                severity = "high"
            elif any(word in vuln_text.lower() for word in ["low", "niedrig", "info", "informational", "minimal"]):
                severity = "low"

            file_match = re.search(
                r'(?:in|file|datei)\s+["\']?([a-zA-Z0-9_./\\-]+\.[a-z]{2,4})["\']?',
                vuln_text,
                re.IGNORECASE
            )
            affected_file = file_match.group(1) if file_match else None

            vulnerabilities.append({
                "severity": severity,
                "description": vuln_text[:2000],
                "fix": fix_text[:5000],
                "affected_file": affected_file,
                "type": "SECURITY_ISSUE"
            })

    return vulnerabilities[:10]


def extract_design_data(design_concept: str) -> Dict[str, Any]:
    """
    Extrahiert strukturierte Design-Daten aus Designer Agent Output.

    Args:
        design_concept: Rohtext-Design-Konzept vom Designer Agent

    Returns:
        Dictionary mit colorPalette, typography, atomicAssets, qualityScore
    """
    result = {
        "colorPalette": [],
        "typography": [],
        "atomicAssets": [],
        "qualityScore": {"overall": 0, "contrast": 0, "hierarchy": 0, "consistency": 0}
    }
    if not design_concept:
        return result

    hex_pattern = r'#([0-9A-Fa-f]{6})\b'
    hex_matches = re.findall(hex_pattern, design_concept)
    color_names = ["Primary", "Secondary", "Accent", "Neutral", "Background"]
    for i, hex_val in enumerate(hex_matches[:5]):
        result["colorPalette"].append({
            "name": color_names[i] if i < len(color_names) else f"Color{i+1}",
            "hex": f"#{hex_val.upper()}"
        })

    font_pattern = r'\b(Inter|Roboto|Open Sans|Lato|Montserrat|Poppins|Raleway|Nunito|Source Sans|Fira Sans)\b'
    font_matches = list(set(re.findall(font_pattern, design_concept, re.IGNORECASE)))
    primary_font = font_matches[0] if font_matches else "Inter"
    for config in [("Display", "700", "48px"), ("Heading", "600", "24px"), ("Body", "400", "16px")]:
        result["typography"].append({
            "name": config[0],
            "font": primary_font,
            "weight": config[1],
            "size": config[2]
        })

    component_pattern = r'\b(Button|Card|Input|Modal|Form|Header|Footer|Navbar|Sidebar|Table|List)\b'
    component_matches = list(set(re.findall(component_pattern, design_concept, re.IGNORECASE)))
    for comp in component_matches[:4]:
        result["atomicAssets"].append({
            "name": f"{comp.title()} Component",
            "status": "pending"
        })

    score = min(
        100,
        len(result["colorPalette"]) * 20
        + len(result["typography"]) * 15
        + len(result["atomicAssets"]) * 10
        + 25
    )
    result["qualityScore"] = {
        "overall": score,
        "contrast": min(100, 70 + len(result["colorPalette"]) * 5),
        "hierarchy": min(100, 65 + len(result["typography"]) * 10),
        "consistency": min(100, 75 + len(result["atomicAssets"]) * 5)
    }

    return result


def format_test_feedback(test_result: Dict[str, Any]) -> str:
    """
    Formatiert Test-Ergebnisse als strukturiertes Feedback für den Coder.

    Args:
        test_result: Dictionary mit unit_tests und ui_tests Ergebnissen

    Returns:
        Formatierter Feedback-Text
    """
    lines = []

    ut = test_result.get("unit_tests", {})
    if ut.get("status") == "FAIL":
        lines.append("🧪 UNIT-TEST FEHLER:")
        failed_count = ut.get("failed_count", 0)
        if failed_count:
            lines.append(f"   {failed_count} Test(s) fehlgeschlagen")
        summary = ut.get("summary", "")
        if summary:
            lines.append(f"   Zusammenfassung: {summary}")
        details = ut.get("details", "")
        if details:
            lines.append(f"   Details:\n{details[:1500]}")
        lines.append("")

    ui = test_result.get("ui_tests", {})
    if ui.get("status") in ["FAIL", "ERROR"]:
        lines.append("🖥️ UI-TEST FEHLER:")
        issues = ui.get("issues", [])
        for issue in issues[:5]:
            lines.append(f"   - {issue}")
        if not ui.get("has_visible_content", True):
            lines.append("   ⚠️ LEERE SEITE ERKANNT - kein sichtbarer Inhalt!")
        if len(issues) > 5:
            lines.append(f"   ... und {len(issues) - 5} weitere Probleme")
        lines.append("")

    if lines:
        lines.append("🔄 RE-TEST ERFORDERLICH:")
        lines.append("Nach deinen Fixes werden die Tests AUTOMATISCH erneut ausgeführt.")
        lines.append("Der Loop läuft bis alle Tests grün sind oder max_iterations erreicht.\n")

    return "\n".join(lines) if lines else "✅ Alle Tests bestanden"


def is_rate_limit_error(error: Exception) -> bool:
    """
    Prüft, ob eine Exception ein Rate-Limit-Fehler ist.
    Server-Fehler (500, 503) sind keine Rate-Limits.

    Args:
        error: Die Exception, die geprüft werden soll

    Returns:
        True NUR wenn Status-Code 429/402 oder explizites Rate-Limit erkannt wird
    """
    status_code = None
    if hasattr(error, 'response') and hasattr(error.response, 'status_code'):
        status_code = error.response.status_code
    elif hasattr(error, 'status_code'):
        status_code = error.status_code

    error_str = str(error).lower()
    rate_limit_pattern = r'\brate[_\s-]?limit\b'

    server_error_patterns = [
        'internal server error',
        'service unavailable',
        'bad gateway',
        'gateway timeout',
        '500',
        '502',
        '503',
        '504'
    ]
    is_server_error = any(pattern in error_str for pattern in server_error_patterns)

    if is_server_error:
        log_event("System", "Warning",
                  "Server-Fehler erkannt (kein Rate-Limit) - kurze Pause von 5s")
        time.sleep(5)
        return False

    is_rate_limit = (status_code in [429, 402]) or bool(re.search(rate_limit_pattern, error_str))

    upstream_patterns = [
        'upstream error',
        'openrouterexception'
    ]
    is_upstream = any(pattern in error_str for pattern in upstream_patterns)

    if is_upstream and not is_rate_limit:
        log_event("System", "Warning",
                  "Upstream-Fehler erkannt - wird als Rate-Limit behandelt für Fallback")

    return is_rate_limit or is_upstream


def is_empty_or_invalid_response(response: str) -> bool:
    """
    Erkennt leere oder ungültige Antworten von LLM-Modellen.

    Args:
        response: Die Antwort des Modells

    Returns:
        True wenn die Antwort leer, ungültig oder ein bekanntes Fehlermuster ist
    """
    if not response or not response.strip():
        return True

    invalid_patterns = [
        "(no response",
        "no response -",
        "indicating failure",
        "malfunctioning",
        "[empty]",
        "[no output]",
        "failed to generate",
        "unable to process"
    ]
    response_lower = response.lower()
    return any(pattern in response_lower for pattern in invalid_patterns)
