"""
Author: rahn
Datum: 29.01.2026
Version: 1.0
Beschreibung: Hilfsfunktionen fuer OrchestrationManager (Parsing/Formatting/Checks).
"""

import logging
import re
from typing import Dict, Any, List

from logger_utils import log_event

# ÄNDERUNG 29.01.2026: Helper aus OrchestrationManager ausgelagert

logger = logging.getLogger(__name__)


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
    try:
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
    except Exception as parse_err:
        # ÄNDERUNG 29.01.2026: Regex/Parsing-Fehler sichtbar machen
        logger.exception(
            "Fehler beim Parsen des Schemas mit Pattern %s: %s",
            table_pattern,
            parse_err
        )
        return tables[:10]

    return tables[:10]


def is_server_error(error: Exception) -> bool:
    """
    Prüft, ob eine Exception ein Server-Fehler ist (500/502/503/504).
    ÄNDERUNG 02.02.2026: Sichere Attribut-Zugriffe mit try-except (Bug-Fix)
    """
    # ÄNDERUNG 02.02.2026: Sichere Attribut-Zugriffe statt hasattr()
    # hasattr() kann bei manchen Exception-Objekten fehlschlagen
    status_code = None
    try:
        status_code = error.response.status_code
    except (AttributeError, TypeError):
        try:
            status_code = error.status_code
        except (AttributeError, TypeError):
            pass

    if status_code in [500, 502, 503, 504]:
        return True

    error_str = str(error).lower()
    server_error_patterns = [
        'internal server error',
        'service unavailable',
        'bad gateway',
        'gateway timeout',
        '500',
        '502',
        '503',
        '504',
        # AENDERUNG 13.02.2026: Fix 54 — Connection-Errors sind auch Server-Fehler
        # OpenRouter bricht manchmal HTTP-Verbindungen ab nach langer Laufzeit
        # Diese werden von litellm als APIError geworfen, haben aber keinen Status-Code
        'peer closed connection',
        'incomplete chunked read',
        'connection reset',
        'connection aborted',
        'remoteprotocolerror',
    ]
    return any(pattern in error_str for pattern in server_error_patterns)


# ÄNDERUNG 29.01.2026: LiteLLM interne Fehler erkennen
def is_litellm_internal_error(error: Exception) -> bool:
    """
    Prüft ob ein Fehler ein bekannter LiteLLM/CrewAI interner Bug ist.
    Diese Fehler treten auf wenn LiteLLM versucht auf Attribute zuzugreifen
    die bei generischen Exceptions nicht existieren.

    Args:
        error: Die aufgetretene Exception

    Returns:
        True wenn es ein bekannter LiteLLM-Bug ist
    """
    error_str = str(error)
    bug_patterns = [
        "has no attribute 'request'",
        "has no attribute 'status_code'",
        "Exception-Mapping",
        "convert_to_model_response_object",
        "exception_mapping_utils"
    ]
    return any(pattern in error_str for pattern in bug_patterns)


# ÄNDERUNG 29.01.2026: Modell-Nicht-Verfügbar Fehler erkennen (404)
# ÄNDERUNG 02.02.2026: Sichere Attribut-Zugriffe mit try-except (Bug-Fix)
def is_model_unavailable_error(error: Exception) -> bool:
    """
    Prüft ob ein Fehler bedeutet, dass das Modell nicht verfügbar ist.
    Dies tritt auf bei 404 Fehlern von OpenRouter wenn ein Provider offline ist.

    Args:
        error: Die aufgetretene Exception

    Returns:
        True wenn das Modell nicht verfügbar ist (404, NotFound)
    """
    # ÄNDERUNG 02.02.2026: Sichere Attribut-Zugriffe statt hasattr()
    status_code = None
    try:
        status_code = error.response.status_code
    except (AttributeError, TypeError):
        try:
            status_code = error.status_code
        except (AttributeError, TypeError):
            pass

    if status_code == 404:
        return True

    # Prüfe Fehler-String
    error_str = str(error).lower()
    unavailable_patterns = [
        'notfounderror',
        '404',
        'not found',
        'model not available',
        'provider returned error',
        'page not found'
    ]
    return any(pattern in error_str for pattern in unavailable_patterns)


# AENDERUNG 31.01.2026: Pruefe ob Fehler permanent ist (z.B. "free period ended")
def is_permanently_unavailable_error(error: Exception) -> bool:
    """
    Prueft ob ein Fehler bedeutet, dass das Modell PERMANENT nicht verfuegbar ist.
    Z.B. wenn ein Free-Tier abgelaufen ist.

    Args:
        error: Die aufgetretene Exception

    Returns:
        True wenn das Modell dauerhaft nicht verfuegbar ist
    """
    error_str = str(error).lower()
    permanent_patterns = [
        'free period ended',
        'free tier ended',
        'subscription required',
        'model has been deprecated',
        'model is no longer available',
        'model discontinued',
        'please migrate to',
        'model removed'
    ]
    # AENDERUNG 26.02.2026: Root-Cause-Fix — OpenRouter "no endpoints found"
    # Diese Fehler sind fuer den laufenden Run i.d.R. dauerhaft und sollten
    # nicht nur als temporaeres Rate-Limit behandelt werden.
    endpoint_patterns = [
        'no endpoints found for',
        'no endpoint found for',
        'no providers available for',
    ]
    if any(pattern in error_str for pattern in endpoint_patterns):
        return True
    return any(pattern in error_str for pattern in permanent_patterns)


# AENDERUNG 31.01.2026: Zentrale Fehlerbehandlung fuer Modell-Fehler
def handle_model_error(model_router, model: str, error: Exception) -> str:
    """
    Behandelt einen Modell-Fehler und markiert das Modell entsprechend.

    - Bei permanenten Fehlern (z.B. "free period ended"): mark_permanently_unavailable
    - Bei temporaeren Fehlern (Rate-Limit, 404 temporaer): mark_rate_limited_sync

    Args:
        model_router: Der ModelRouter
        model: Die Modell-ID
        error: Der aufgetretene Fehler

    Returns:
        Fehlertyp-String: "permanent", "rate_limit", "unavailable" oder "unknown".
        "unknown" wird zurueckgegeben, wenn der Fehler keinem der bekannten Muster
        (permanent, Rate-Limit, 404/unavailable) zugeordnet werden kann; Aufrufer
        sollten dies als generischen Fehlerpfad behandeln (z.B. Logging und Retry).
    """
    if is_permanently_unavailable_error(error):
        # Permanenter Fehler - Modell fuer diesen Run deaktivieren
        reason = str(error)[:200]
        model_router.mark_permanently_unavailable(model, reason)
        return "permanent"
    elif is_rate_limit_error(error):
        # Temporaerer Rate-Limit
        model_router.mark_rate_limited_sync(model)
        return "rate_limit"
    elif is_model_unavailable_error(error):
        # 404 aber nicht permanent erkannt - als temporaer behandeln
        model_router.mark_rate_limited_sync(model)
        return "unavailable"
    else:
        return "unknown"


# ÄNDERUNG 30.01.2026: Leere LLM-Antworten erkennen für Retry-Logik
def is_empty_response_error(error: Exception) -> bool:
    """
    Prüft ob ein Fehler auf eine leere LLM-Antwort hinweist.
    Diese Fehler sollten zu einem Retry mit Fallback-Modell führen.

    Args:
        error: Die aufgetretene Exception

    Returns:
        True wenn die Antwort leer/None war
    """
    error_str = str(error).lower()
    empty_patterns = [
        'none or empty',
        'empty response',
        'invalid response from llm',
        'no response',
        'null response',
        'response is none',
        'empty content'
    ]
    return any(pattern in error_str for pattern in empty_patterns)


def extract_vulnerabilities(security_result: str,
                            existing_files: List[str] = None) -> List[Dict[str, Any]]:
    """
    Extrahiert Vulnerabilities UND Lösungsvorschläge aus dem Security-Agent Output.

    AENDERUNG 10.02.2026: Fix 44 — existing_files fuer Dateinamen-Validierung.

    Args:
        security_result: Rohtext-Ergebnis der Sicherheitsanalyse
        existing_files: Liste echte Projekt-Dateien fuer Validierung (optional)

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

        # AENDERUNG 07.02.2026: Erweiterte Datei-Extraktion fuer Security-Findings (Fix 20)
        # ROOT-CAUSE-FIX:
        # Symptom: affected_file=None bei 90% der Security-Findings
        # Ursache: Nur ein Regex-Pattern, erkennt nicht [DATEI:filename] Format
        # Loesung: 4 Patterns in Prioritaetsreihenfolge, nehme ersten Treffer
        # AENDERUNG 10.02.2026: Fix 41b - Dynamic Routes sicher ([id], [slug])
        file_patterns = [
            r'\[DATEI:(.+?\.[a-z]{1,4})\]',                                  # [DATEI:app/api/todos/[id]/route.js]
            r'(?:in|file|datei)\s+["\']?([a-zA-Z0-9_./\\-]+\.[a-z]{2,4})["\']?',  # in filename.js
            r'([a-zA-Z0-9_./\\-]+\.[jt]sx?)\s+(?:Zeile|line|L)\s+\d+',       # file.js Zeile 42
            r'(?:Zeile|line|L)\s+\d+\s+(?:in|von)\s+([a-zA-Z0-9_./\\-]+\.[jt]sx?)',  # Zeile 42 in file.js
        ]
        affected_file = None
        for fp in file_patterns:
            file_match = re.search(fp, vuln_text, re.IGNORECASE)
            if file_match:
                affected_file = file_match.group(1).strip()
                break

        # AENDERUNG 10.02.2026: Fix 44 — Validiere affected_file gegen echte Dateien
        # ROOT-CAUSE-FIX: LLM halluziniert Dateinamen (tasks statt todos)
        # → Downstream-PatchMode erstellt Phantom-Dateien
        if affected_file and existing_files:
            if affected_file not in existing_files:
                af_base = os.path.basename(affected_file)
                for ef in existing_files:
                    if os.path.basename(ef) == af_base:
                        logger.info(f"Security affected_file korrigiert: {affected_file} → {ef}")
                        affected_file = ef
                        break

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

            # AENDERUNG 07.02.2026: Gleiche erweiterte Datei-Extraktion wie oben (Fix 20)
            affected_file = None
            # AENDERUNG 10.02.2026: Fix 41b - Dynamic Routes sicher
            for fp in [
                r'\[DATEI:(.+?\.[a-z]{1,4})\]',
                r'(?:in|file|datei)\s+["\']?([a-zA-Z0-9_./\\-]+\.[a-z]{2,4})["\']?',
                r'([a-zA-Z0-9_./\\-]+\.[jt]sx?)\s+(?:Zeile|line|L)\s+\d+',
                r'(?:Zeile|line|L)\s+\d+\s+(?:in|von)\s+([a-zA-Z0-9_./\\-]+\.[jt]sx?)',
            ]:
                file_match = re.search(fp, vuln_text, re.IGNORECASE)
                if file_match:
                    affected_file = file_match.group(1).strip()
                    break

            # AENDERUNG 10.02.2026: Fix 44 — Validiere affected_file (s.o.)
            if affected_file and existing_files:
                if affected_file not in existing_files:
                    af_base = os.path.basename(affected_file)
                    for ef in existing_files:
                        if os.path.basename(ef) == af_base:
                            logger.info(f"Security affected_file korrigiert: {affected_file} → {ef}")
                            affected_file = ef
                            break

            vulnerabilities.append({
                "severity": severity,
                "description": vuln_text[:2000],
                "fix": fix_text[:5000],
                "affected_file": affected_file,
                "type": "SECURITY_ISSUE"
            })

    # AENDERUNG 08.02.2026: Halluzinierte CVEs filtern (Fix 32)
    # ROOT-CAUSE-FIX:
    # Symptom: Gemini 2.5 Flash erfindet CVE-Nummern (z.B. CVE-2025-66478)
    # Ursache: LLM halluziniert plausibel klingende CVE-IDs
    # Loesung: CVE-basierte Findings auf LOW downgraden (nicht blockierend)
    cve_pattern = re.compile(r'CVE-\d{4}-\d{4,7}')
    for vuln in vulnerabilities:
        desc = vuln.get('description', '')
        cves_found = cve_pattern.findall(desc)
        if cves_found and vuln.get('severity') in ('critical', 'high'):
            vuln['severity'] = 'low'
            vuln['description'] = desc + ' [CVE nicht verifiziert - Severity auf LOW gesetzt]'

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
    ÄNDERUNG 02.02.2026: Sichere Attribut-Zugriffe mit try-except (Bug-Fix)

    Args:
        error: Die Exception, die geprüft werden soll

    Returns:
        True NUR wenn Status-Code 429/402 oder explizites Rate-Limit erkannt wird
    """
    # ÄNDERUNG 02.02.2026: Sichere Attribut-Zugriffe statt hasattr()
    status_code = None
    try:
        status_code = error.response.status_code
    except (AttributeError, TypeError):
        try:
            status_code = error.status_code
        except (AttributeError, TypeError):
            pass

    error_str = str(error).lower()
    rate_limit_pattern = r'\brate[_\s-]?limit\b'

    if is_server_error(error):
        log_event("System", "Warning",
                  "Server-Fehler erkannt (kein Rate-Limit)")
        return False

    # AENDERUNG 20.02.2026: Fix 58e — "out of credits" als Rate-Limit erkennen
    # ROOT-CAUSE-FIX: Augment "You have run out of credits" wurde nicht als Rate-Limit
    # erkannt → Reviewer iterierte endlos ohne Modellwechsel
    credit_exhaustion = any(p in error_str for p in [
        'out of credits', 'credits exhausted', 'insufficient credits',
        'no credits', 'credit limit'
    ])
    is_rate_limit = (status_code in [429, 402]) or bool(re.search(rate_limit_pattern, error_str)) or credit_exhaustion

    # AENDERUNG 09.02.2026: Fix 36c — Rate-Limit vs. Upstream-Error unterscheiden
    # ROOT-CAUSE-FIX:
    # Symptom: Bezahlte Modelle werden faelschlich als "rate-limited" erkannt
    # Ursache: "upstream error" ist zu generisch — matcht auch 500/502 Server-Fehler
    # Loesung: Upstream-Errors nur als Rate-Limit wenn sie explizit 429/rate-limit enthalten
    upstream_rate_limit_patterns = [
        'upstream error: 429',
        'upstream error: rate limit',
        'upstream error: too many requests',
        'upstream error: quota exceeded',
        'upstream error: insufficient_quota',
    ]
    is_upstream_rate_limit = any(pattern in error_str for pattern in upstream_rate_limit_patterns)

    # OpenRouterException separat — kann Rate-Limit ODER Server-Error sein
    is_openrouter_generic = 'openrouterexception' in error_str and not is_rate_limit
    if is_openrouter_generic:
        openrouter_rate_indicators = ['429', 'rate', 'quota', 'limit', 'too many']
        is_openrouter_rate = any(ind in error_str for ind in openrouter_rate_indicators)
        if not is_openrouter_rate:
            log_event("System", "Warning",
                      f"OpenRouter-Fehler erkannt aber KEIN Rate-Limit: {error_str[:200]}")
        else:
            is_upstream_rate_limit = True

    if is_upstream_rate_limit and not is_rate_limit:
        log_event("System", "Warning",
                  "Upstream-Rate-Limit erkannt fuer Fallback")

    return is_rate_limit or is_upstream_rate_limit


# ÄNDERUNG 02.02.2026: OpenRouter-Fehler Erkennung für sofortigen Modellwechsel
def is_openrouter_error(error: Exception) -> bool:
    """
    Prueft ob ein Timeout ein OpenRouter-spezifischer Fehler ist.
    Diese sollten sofort einen Modellwechsel ausloesen (wie Rate-Limits).

    OpenRouter meldet Provider-Fehler als litellm.Timeout mit speziellem Text:
    'litellm.Timeout: OpenrouterException - Provider returned error'

    Args:
        error: Die aufgetretene Exception

    Returns:
        True wenn es ein OpenRouter-spezifischer Fehler ist
    """
    error_str = str(error).lower()
    # AENDERUNG 09.02.2026: Fix 36c — "upstream error" nicht mehr pauschal als OpenRouter-Error
    openrouter_patterns = [
        'openrouterexception',
        'provider returned error',
    ]
    # "upstream error" nur wenn es kein generischer Server-Error ist (500/502/503)
    if 'upstream error' in error_str:
        server_error_indicators = ['500', '502', '503', 'internal server error', 'bad gateway']
        if not any(ind in error_str for ind in server_error_indicators):
            return True
    return any(pattern in error_str for pattern in openrouter_patterns)


# AENDERUNG 21.02.2026: Claude SDK Error-Erkennung fuer Provider-Fallback
def is_claude_sdk_error(error: Exception) -> bool:
    """
    Prueft ob ein Fehler vom Claude SDK Provider stammt.
    Wird verwendet um gezielt auf OpenRouter zu fallen.

    Args:
        error: Die aufgetretene Exception

    Returns:
        True wenn es ein Claude SDK-spezifischer Fehler ist
    """
    error_str = str(error).lower()
    claude_sdk_patterns = [
        'claude sdk',
        'claude-agent-sdk',
        'claude_agent_sdk',
        'claudeagentoptions',
        'anyio',  # Async-Runtime des SDK
    ]
    # Typ-Check: ImportError vom SDK
    if isinstance(error, ImportError) and 'claude' in error_str:
        return True
    return any(pattern in error_str for pattern in claude_sdk_patterns)


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
        "unable to process",
        # AENDERUNG 20.02.2026: Fix 58e — Credit-Exhaustion als ungueltige Antwort
        "out of credits",
        "run out of credits",
        "insufficient credits",
    ]
    response_lower = response.lower()
    return any(pattern in response_lower for pattern in invalid_patterns)


# ÄNDERUNG 31.01.2026: Unicode-Sanitizing für Code-Output
def sanitize_unicode_hyphens(code: str) -> str:
    """
    Ersetzt Unicode-Hyphens durch ASCII-Hyphens.

    Einige LLM-Modelle (z.B. mimo-v2-flash) verwenden Unicode-Hyphens
    (U+2011 Non-Breaking Hyphen) statt ASCII-Hyphens (U+002D).
    Python akzeptiert diese nicht in Kommentaren/Code.

    Args:
        code: Der zu bereinigende Code-String

    Returns:
        Code mit ersetzten Unicode-Hyphens
    """
    if not code:
        return code

    problematic_chars = {
        '\u2011': '-',  # Non-Breaking Hyphen
        '\u2010': '-',  # Hyphen
        '\u2012': '-',  # Figure Dash
        '\u2013': '-',  # En Dash
        '\u2014': '-',  # Em Dash
        '\u2212': '-',  # Minus Sign
    }
    for char, replacement in problematic_chars.items():
        code = code.replace(char, replacement)
    return code


# ÄNDERUNG 31.01.2026: Review-Output Truncation gegen Wiederholungen
def truncate_review_output(review_output: str, max_length: int = 3000) -> str:
    """
    Kuerzt Review-Output und entfernt Wiederholungen.

    Einige LLM-Modelle (z.B. llama-3.3-70b-instruct) geraten bei
    langen Outputs in Wiederholungsschleifen. Diese Funktion
    dedupliziert Zeilen und kuerzt auf max_length.

    Args:
        review_output: Der Review-Text
        max_length: Maximale Laenge des Outputs

    Returns:
        Gekuerzter und deduplizierter Review-Text
    """
    if not review_output or len(review_output) <= max_length:
        return review_output

    # Finde Wiederholungen (einfache Heuristik)
    lines = review_output.split('\n')
    seen = set()
    unique_lines = []
    for line in lines:
        line_key = line.strip()[:100]  # Erste 100 Zeichen als Key
        if line_key and line_key not in seen:
            seen.add(line_key)
            unique_lines.append(line)

    result = '\n'.join(unique_lines)
    if len(result) > max_length:
        return result[:max_length] + "\n[... gekuerzt]"
    return result
