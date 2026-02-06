# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 31.01.2026
Version: 1.0
Beschreibung: Coder-Funktionen für DevLoop.
              Extrahiert aus dev_loop_steps.py (Regel 1: Max 500 Zeilen)
              Enthält: Coder-Prompt Builder, Task-Ausführung, Output-Speicherung
              ÄNDERUNG 29.01.2026: Modellwechsel erst nach 2 gleichen Fehlern
              ÄNDERUNG 31.01.2026: Truncation-Detection und Unicode-Sanitization
"""

import os
import json
import time
import traceback
from typing import Dict, Any, Tuple, List

from crewai import Task

from agents.memory_agent import get_lessons_for_prompt
from agents.memory_core import get_constraints_for_prompt, save_environment_constraint
from budget_tracker import get_budget_tracker
from main import save_multi_file_output
from .agent_factory import init_agents
from .orchestration_helpers import (
    is_rate_limit_error,
    is_server_error,
    is_litellm_internal_error,
    is_openrouter_error  # ÄNDERUNG 02.02.2026: OpenRouter-Fehler für sofortigen Modellwechsel
)
from .heartbeat_utils import run_with_heartbeat
from .dev_loop_helpers import _sanitize_unicode, _check_for_truncation, get_python_dependency_versions
# AENDERUNG 06.02.2026: Import fuer PatchMode-Fix (vorher toter Code weil isinstance-Check immer False)
from .file_status_detector import get_file_status_summary_for_log

import re


# ÄNDERUNG 03.02.2026: Fix 8 - Think-Tag Filtering
# Entfernt Model-spezifische Tags (z.B. <think> von moonshotai/kimi-k2.5)

def _clean_model_output(raw_output: str) -> str:
    """
    Entfernt Model-spezifische Tags aus dem Output.

    ÄNDERUNG 03.02.2026: Fix 8 für moonshotai/kimi-k2.5 <think> Tags.
    Manche Modelle leaken ihren "Denkprozess" in den Code-Output.

    Args:
        raw_output: Roher Model-Output

    Returns:
        Bereinigter Output ohne Think-Tags
    """
    if not raw_output:
        return raw_output

    cleaned = raw_output

    # Entferne <think>...</think> Blöcke komplett
    cleaned = re.sub(r'<think>.*?</think>', '', cleaned, flags=re.DOTALL)

    # Entferne einzelne <think> oder </think> Tags
    cleaned = re.sub(r'</?think>', '', cleaned)

    # Entferne alles vor dem ersten "### FILENAME:" (häufiges Code-Format)
    if "### FILENAME:" in cleaned:
        idx = cleaned.find("### FILENAME:")
        # Nur kürzen wenn vor dem Marker unerwünschter Content ist
        prefix = cleaned[:idx].strip()
        if prefix and not prefix.startswith("```"):
            cleaned = cleaned[idx:]

    # Alternative: Entferne alles vor dem ersten Code-Block
    elif "```" in cleaned:
        idx = cleaned.find("```")
        prefix = cleaned[:idx].strip()
        # Nur kürzen wenn Prefix kurz und kein sinnvoller Text ist
        if prefix and len(prefix) < 50 and not any(
            kw in prefix.lower() for kw in ["hier", "here", "following", "code"]
        ):
            cleaned = cleaned[idx:]

    return cleaned.strip()


# ÄNDERUNG 03.02.2026: Patch-Modus Helper-Funktionen
# Verhindert dass Coder bei Fehlern kompletten Code überschreibt

def _is_targeted_fix_context(feedback: str) -> bool:
    """
    Prüft ob Feedback auf einen gezielten Fix oder additive Änderung hinweist.

    Args:
        feedback: Das Fehler-Feedback

    Returns:
        True wenn Patch-Modus sinnvoll, False sonst
    """
    if not feedback:
        return False

    # Spezifische Error-Indikatoren die auf gezielten Fix hinweisen
    # ÄNDERUNG 03.02.2026: Deutsche Fehlerbegriffe hinzugefügt für PatchMode-Aktivierung
    fix_indicators = [
        # Englische Error-Typen
        "TypeError:", "NameError:", "SyntaxError:", "ImportError:",
        "AttributeError:", "KeyError:", "ValueError:", "ModuleNotFoundError:",
        "expected", "got", "argument", "parameter", "takes",
        "missing", "undefined", "not defined", "cannot import",
        # Deutsche Fehlerbegriffe
        "Syntaxfehler", "Fehler:", "ungültig", "fehlgeschlagen",
        "nicht gefunden", "nicht definiert", "fehlerhaft", "Formatierung"
    ]

    # FIX 05.02.2026: Additive Änderungen (Tests, Docs, Features) sollten auch PatchMode nutzen
    additive_indicators = [
        "unit-test", "test", "tests/", "test_", "_test.",
        "erstelle test", "add test", "create test",
        "dokumentation", "documentation", "docstring",
        "hinzufügen", "ergänzen", "add", "create", "new file",
        "PFLICHT:", "REQUIRED:", "MUST:"
    ]

    feedback_lower = feedback.lower()
    return (any(ind.lower() in feedback_lower for ind in fix_indicators) or
            any(ind.lower() in feedback_lower for ind in additive_indicators))


def _get_affected_files_from_feedback(feedback: str) -> List[str]:
    """
    Extrahiert betroffene Dateinamen aus Feedback.

    Args:
        feedback: Das Fehler-Feedback

    Returns:
        Liste der betroffenen Dateinamen
    """
    if not feedback:
        return []

    # AENDERUNG 06.02.2026: Erweiterte Patterns fuer JavaScript/Next.js Fehler
    file_patterns = [
        r'File "([^"]+\.py)"',           # Python Traceback
        r'in ([a-zA-Z_][a-zA-Z0-9_]*\.py)',  # "in filename.py"
        r'([a-zA-Z_][a-zA-Z0-9_]*\.py):',    # "filename.py:"
        r'tests/([^/\s]+\.py)',           # Tests
        r'([a-zA-Z_][a-zA-Z0-9_]*\.(?:js|jsx|ts|tsx))[\s:]',  # JS/TS: filename.js:
        r'(?:in|from)\s+["\']([^"\']+\.(?:js|jsx|ts|tsx))["\']',  # import from 'file.js'
        r'Module not found.*?["\']([^"\']+)["\']',          # Module not found: 'xyz'
        r'Error:\s*([a-zA-Z0-9_/.\\-]+\.(?:js|jsx|ts|tsx))',  # Error: file.js
        r'([a-zA-Z0-9_/.-]+\.(?:js|jsx|ts|tsx))\s+(?:hat|has|contains)',  # datei.js hat Fehler
        r'(?:Datei|File|Syntax)\s+["\']?([a-zA-Z0-9_/.-]+\.(?:js|jsx|ts|tsx))',  # Datei "x.js"
    ]

    found_files = []
    for pattern in file_patterns:
        matches = re.findall(pattern, feedback)
        for match in matches:
            # Nur Dateinamen, nicht volle Pfade aus System-Bibliotheken
            if not any(skip in match.lower() for skip in ['site-packages', 'python3', '/usr/', 'venv/']):
                basename = os.path.basename(match)
                if basename not in found_files:
                    found_files.append(basename)

    return found_files[:5]  # Max 5 Dateien


# AENDERUNG 06.02.2026: ROOT-CAUSE-FIX PatchModeFallback
# Symptom: PatchModeFallback "Keine spezifischen Dateien gefunden" in jeder Iteration
# Ursache: manager.current_code ist immer ein String (LLM-Output), nie ein Dict
#          isinstance(manager.current_code, dict) war daher immer False
# Loesung: Projekt-Dateien von Festplatte lesen statt auf Dict-Format zu pruefen

def _get_current_code_dict(manager) -> Dict[str, str]:
    """
    Liest aktuelle Projekt-Dateien als Dict {filename: content}.

    Primaer von Festplatte (aktueller Stand inkl. UTDS-Aenderungen),
    Fallback auf Parsing des current_code Strings.
    """
    if isinstance(getattr(manager, 'current_code', None), dict):
        return manager.current_code

    code_dict = {}
    project_path = getattr(manager, 'project_path', None)
    if not project_path or not os.path.exists(str(project_path)):
        return code_dict

    skip_dirs = {
        '.git', 'node_modules', '__pycache__', '.next',
        'venv', '.venv', 'dist', 'build', '.cache'
    }
    code_extensions = {
        '.py', '.js', '.jsx', '.ts', '.tsx', '.html', '.css', '.json',
        '.cs', '.java', '.go', '.rs', '.php', '.rb', '.vue', '.svelte',
        '.bat', '.sh', '.yaml', '.yml', '.toml', '.cfg', '.ini',
        '.md', '.txt', '.sql'
    }

    project_path_str = str(project_path)
    for root, dirs, files in os.walk(project_path_str):
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        for filename in files:
            _, ext = os.path.splitext(filename)
            if ext.lower() in code_extensions:
                filepath = os.path.join(root, filename)
                rel_path = os.path.relpath(filepath, project_path_str).replace('\\', '/')
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        code_dict[rel_path] = f.read()
                except Exception:
                    pass

    return code_dict


def _build_patch_prompt(current_code, affected_files: List[str], feedback: str) -> str:
    """
    Baut einen Patch-fokussierten Prompt.

    Args:
        current_code: Dict mit aktuellem Code {filename: content} ODER String (Fallback)
        affected_files: Liste der betroffenen Dateien
        feedback: Das Fehler-Feedback

    Returns:
        Patch-Modus Prompt-String
    """
    prompt = "\n\n⚠️ PATCH-MODUS - NUR die folgenden Dateien anpassen:\n"
    prompt += "WICHTIG: Nur die betroffenen Zeilen ändern, Rest UNVERÄNDERT lassen!\n\n"

    # ÄNDERUNG 03.02.2026: Fix 8 - Typ-Check für current_code
    # current_code kann ein Dict ODER ein String sein (je nach Speicher-Format)
    if current_code is None:
        current_code = {}
    elif isinstance(current_code, str):
        # Fallback: Wenn current_code ein String ist, als Context anhängen
        prompt += f"--- AKTUELLER CODE (Vollständig) ---\n"
        prompt += f"```\n{current_code[:5000]}\n```\n\n"
        prompt += f"🔧 FEHLER ZU BEHEBEN:\n{feedback}\n\n"
        prompt += "📋 ANWEISUNGEN:\n"
        prompt += "1. Analysiere den Fehler genau\n"
        prompt += "2. Ändere NUR die betroffene(n) Zeile(n)\n"
        prompt += "3. Behalte alle anderen Funktionen/Klassen unverändert bei\n"
        prompt += "4. Gib die komplette korrigierte Datei aus\n"
        return prompt

    files_found = 0
    matched_paths = []
    for fname in affected_files:
        # Suche Datei im current_code (Fuzzy-Matching)
        # ROOT-CAUSE-FIX 06.02.2026 (v2): Mehrstufiges Matching
        # 1. Exakt -> 2. Endswith -> 3. Basename -> 4. Basename ohne Extension
        content = None
        matched_path = fname
        fname_normalized = fname.replace("\\", "/")
        fname_basename = os.path.basename(fname_normalized)

        # Stufe 1-3: Exakt, Endswith, Basename
        for code_file, code_content in current_code.items():
            code_normalized = code_file.replace("\\", "/")
            code_basename = os.path.basename(code_normalized)
            if (code_normalized == fname_normalized
                    or code_normalized.endswith(f"/{fname_normalized}")
                    or code_basename == fname_basename):
                content = code_content
                matched_path = code_file
                break

        # Stufe 4: Basename ohne Extension (fuer package.js -> package.json etc.)
        if not content and "." in fname_basename:
            fname_stem = fname_basename.rsplit(".", 1)[0]
            for code_file, code_content in current_code.items():
                code_basename = os.path.basename(code_file)
                code_stem = code_basename.rsplit(".", 1)[0] if "." in code_basename else code_basename
                if code_stem == fname_stem:
                    content = code_content
                    matched_path = code_file
                    logger.info(f"Fuzzy-Match: {fname} -> {code_file} (Basename-Stem)")
                    break

        if content:
            prompt += f"--- {matched_path} (AKTUELLER CODE) ---\n"
            prompt += f"```\n{content}\n```\n\n"
            files_found += 1
            matched_paths.append(matched_path)

    if files_found == 0 and len(affected_files) > 0:
        logger.warning(f"PatchMode: 0/{len(affected_files)} Dateien gematched! "
                      f"Gesucht: {affected_files[:3]}, Vorhanden: {list(current_code.keys())[:5]}")

    prompt += f"🔧 FEHLER ZU BEHEBEN:\n{feedback}\n\n"

    # AENDERUNG 06.02.2026: Explizite Multi-File-Anweisung
    # Symptom: LLM gibt nur 1 Datei aus obwohl 3 gefordert
    # Ursache: Anweisung "Gib die komplette korrigierte Datei aus" war Singular
    # Loesung: Explizite Liste der auszugebenden Dateien
    prompt += "📋 ANWEISUNGEN:\n"
    prompt += "1. Analysiere den Fehler genau\n"
    prompt += "2. Ändere NUR die betroffene(n) Zeile(n)\n"
    prompt += "3. Behalte alle anderen Funktionen/Klassen unverändert bei\n"
    if files_found > 1:
        file_list = ", ".join(matched_paths[:5])
        prompt += f"4. WICHTIG: Gib ALLE {files_found} korrigierten Dateien aus: {file_list}\n"
        prompt += "5. Nutze das Format: ### FILENAME: pfad/datei.ext fuer JEDE Datei\n"
    else:
        prompt += "4. Gib die komplette korrigierte Datei aus\n"

    return prompt


def build_coder_prompt(
    manager, 
    user_goal: str, 
    feedback: str, 
    iteration: int,
    utds_tasks: list = None,
    files_to_patch: list = None
) -> str:
    """
    Baut den Coder-Prompt basierend auf Kontext, Feedback, UTDS-Tasks und File-Status.
    
    AENDERUNG 05.02.2026: UTDS-Task-Erkennung und FileStatusDetector Integration.
    Wenn UTDS-Tasks vorhanden sind oder Dateien identifiziert wurden die gepatcht werden müssen,
    wird automatisch der Patch-Modus aktiviert.
    """
    c_prompt = f"Ziel: {user_goal}\nTech: {manager.tech_blueprint}\nDB: {manager.database_schema}\n"

    briefing_context = manager.get_briefing_context()
    if briefing_context:
        c_prompt += f"\n{briefing_context}\n"

    # AENDERUNG 05.02.2026: UTDS-Task-Erkennung für Patch-Modus
    use_patch_mode = False
    patch_mode_reason = ""
    
    # Patch-Modus Trigger: UTDS-Tasks vorhanden
    if utds_tasks and len(utds_tasks) > 0:
        use_patch_mode = True
        patch_mode_reason = "UTDS-Tasks erkannt"
        manager._ui_log("Coder", "UTDSMode", f"Patch-Modus: {patch_mode_reason} ({len(utds_tasks)} Tasks)")
    
    # Patch-Modus Trigger: Dateien zum Patches identifiziert
    elif files_to_patch and len(files_to_patch) > 0:
        use_patch_mode = True
        patch_mode_reason = "FileStatusDetector hat Dateien identifiziert"
        manager._ui_log("Coder", "FilePatchMode", f"Patch-Modus: {patch_mode_reason} ({len(files_to_patch)} Dateien)")
    
    # Patch-Modus Trigger: Feedback deutet auf gezielten Fix hin
    elif not manager.is_first_run and feedback and _is_targeted_fix_context(feedback):
        use_patch_mode = True
        patch_mode_reason = "Feedback deutet auf gezielten Fix hin"
    
    # AENDERUNG 06.02.2026: ROOT-CAUSE-FIX PatchModeFallback
    # Vorher: isinstance(manager.current_code, dict) war IMMER False weil current_code ein String ist
    # Jetzt: Projekt-Dateien von Festplatte lesen via _get_current_code_dict()
    if use_patch_mode:
        code_dict = _get_current_code_dict(manager)

        if utds_tasks or files_to_patch:
            # Patch-Modus mit expliziten Dateien (UTDS oder FileStatusDetector)
            affected_files = files_to_patch or _get_affected_files_from_feedback(feedback)

            if affected_files and code_dict:
                status_summary = get_file_status_summary_for_log(
                    str(manager.project_path),
                    code_dict,
                    affected_files
                )
                manager._ui_log("Coder", "PatchMode",
                    f"Patch-Dateien: {', '.join(affected_files[:5])}")
                manager._ui_log("Coder", "FileStatus", status_summary)

                c_prompt += _build_patch_prompt(code_dict, affected_files, feedback)
            else:
                # Fallback: Keine Dateien identifiziert oder Projekt leer
                manager._ui_log("Coder", "FullMode",
                    f"PatchMode-Fallback: {patch_mode_reason}")
                c_prompt += f"\nAlt-Code:\n{manager.current_code}\n"
                if feedback:
                    c_prompt += f"\nKorrektur: {feedback}\n"
        else:
            # Patch-Modus mit Feedback-Analyse (Dateinamen aus Fehlermeldungen extrahieren)
            affected_files = _get_affected_files_from_feedback(feedback)

            if affected_files and code_dict:
                manager._ui_log("Coder", "PatchMode",
                    f"Patch-Modus aktiv fuer: {', '.join(affected_files)}")
                c_prompt += _build_patch_prompt(code_dict, affected_files, feedback)
            else:
                # ROOT-CAUSE-FIX 06.02.2026 (v2): Fallback auf ALLE Dateien statt rohen String
                # Wenn code_dict vorhanden aber keine spezifischen Dateien identifiziert ->
                # Alle Dateien als Kontext geben (besser als unstrukturierter Code-String)
                if code_dict and feedback:
                    manager._ui_log("Coder", "PatchModeAllFiles",
                        f"Keine spezifischen Dateien erkannt - nutze alle {len(code_dict)} Dateien als Kontext")
                    c_prompt += _build_patch_prompt(code_dict, list(code_dict.keys()), feedback)
                else:
                    fallback_reason = "Kein code_dict" if not code_dict else "Keine Dateien im Feedback"
                    manager._ui_log("Coder", "PatchModeFallback", fallback_reason)
                    c_prompt += f"\nAlt-Code:\n{manager.current_code}\n"
                    if feedback:
                        c_prompt += f"\nKorrektur: {feedback}\n"
    elif not manager.is_first_run:
        # ROOT-CAUSE-FIX 06.02.2026 (v2):
        # Symptom: Iteration 1+ fiel immer auf FullMode zurueck (komplette Regenerierung)
        # Ursache: Kein UTDS/files_to_patch vorhanden -> Bedingungen 313-327 griffen nicht
        # Loesung: Wenn code_dict vorhanden, strukturierten Multi-File-Kontext nutzen statt rohen String
        code_dict = code_dict if 'code_dict' in dir() else _get_current_code_dict(manager)
        if code_dict and feedback:
            manager._ui_log("Coder", "StructuredPatchMode",
                f"Strukturierter Patch-Kontext ({len(code_dict)} Dateien) mit Feedback")
            c_prompt += _build_patch_prompt(code_dict, list(code_dict.keys()), feedback)
        else:
            manager._ui_log("Coder", "FullMode",
                f"Kein gezielter Fehler-Kontext erkannt - vollstaendige Regenerierung ({patch_mode_reason or 'Standard'})")
            c_prompt += f"\nAlt-Code:\n{manager.current_code}\n"
            if feedback:
                c_prompt += f"\nKorrektur: {feedback}\n"
    elif feedback:
        c_prompt += f"\nKorrektur: {feedback}\n"

    if iteration == 0 and not feedback:
        c_prompt += "\n\n🛡️ SECURITY BASICS (von Anfang an beachten!):\n"
        c_prompt += "- Kein innerHTML/document.write mit User-Input (XSS-Risiko)\n"
        c_prompt += "- Keine String-Konkatenation in SQL/DB-Queries (Injection-Risiko)\n"
        c_prompt += "- Keine hardcoded API-Keys, Passwörter oder Secrets im Code\n"
        c_prompt += "- Bei eval(): Nur mit Button-Input, NIEMALS mit User-Text-Input\n"
        c_prompt += "- Nutze textContent statt innerHTML wenn möglich\n\n"
        # AENDERUNG 06.02.2026: Test-Script-Pflicht in package.json
        tech_lang = manager.tech_blueprint.get("language", "") if manager.tech_blueprint else ""
        if tech_lang.lower() in ("javascript", "typescript"):
            c_prompt += "📦 PACKAGE.JSON PFLICHT:\n"
            c_prompt += "- package.json MUSS ein 'test' Script enthalten (z.B. 'jest' oder 'vitest run')\n"
            c_prompt += "- Beispiel: \"test\": \"jest --passWithNoTests\"\n\n"

    try:
        memory_path = os.path.join(manager.base_dir, "memory", "global_memory.json")
        tech_stack = manager.tech_blueprint.get("project_type", "") if manager.tech_blueprint else ""
        lessons = get_lessons_for_prompt(memory_path, tech_stack=tech_stack)
        if lessons and lessons.strip():
            c_prompt += f"\n\n📚 LESSONS LEARNED (aus früheren Projekten - UNBEDINGT BEACHTEN!):\n{lessons}\n"
            manager._ui_log("Memory", "LessonsApplied", f"Coder erhält {len(lessons.splitlines())} Lektionen")
    except Exception as les_err:
        manager._ui_log("Memory", "Warning", f"Lektionen konnten nicht geladen werden: {les_err}")

    # ÄNDERUNG 03.02.2026: Fix 7 - Environment Constraints laden
    # Verhindert wiederholte Fehler wie bleach-ImportError Oszillation
    try:
        memory_path = os.path.join(manager.base_dir, "memory", "global_memory.json")
        env_constraints = get_constraints_for_prompt(memory_path)
        if env_constraints and env_constraints.strip():
            c_prompt += f"\n\n⚠️ UMGEBUNGS-EINSCHRÄNKUNGEN (KRITISCH - NICHT IGNORIEREN!):\n"
            c_prompt += "Diese Module/Features sind in der Ausführungsumgebung NICHT verfügbar:\n"
            c_prompt += env_constraints + "\n"
            c_prompt += "\nWICHTIG: Verwende NUR die angegebenen Alternativen! Diese Einschränkungen sind PERMANENT!\n"
            manager._ui_log("Memory", "EnvConstraints", f"Coder erhält {len(env_constraints.splitlines())} Umgebungs-Constraints")
    except Exception as env_err:
        manager._ui_log("Memory", "Warning", f"Environment Constraints konnten nicht geladen werden: {env_err}")

    # AENDERUNG 01.02.2026: Dependency-Versionen aus Inventar laden
    # Verhindert dass LLM veraltete/falsche Versionen generiert (z.B. greenlet==2.0.7)
    try:
        dep_versions = get_python_dependency_versions()
        if dep_versions:
            c_prompt += f"\n\n📦 {dep_versions}\n"
            c_prompt += "WICHTIG: Für requirements.txt NUR diese Versionen verwenden! Keine eigenen Versionen erfinden!\n"
    except Exception as dep_err:
        manager._ui_log("Coder", "Warning", f"Dependency-Versionen konnten nicht geladen werden: {dep_err}")

    if hasattr(manager, 'security_vulnerabilities') and manager.security_vulnerabilities:
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        sorted_vulns = sorted(
            manager.security_vulnerabilities,
            key=lambda v: severity_order.get(v.get("severity", "medium"), 2)
        )

        coder_tasks = []
        task_prompt_lines = []

        for i, vuln in enumerate(sorted_vulns, 1):
            task_id = f"SEC-{i:03d}"
            severity = vuln.get("severity", "medium").upper()
            description = vuln.get("description", "Unbekannte Schwachstelle")
            fix = vuln.get("fix", "Bitte beheben")
            affected_file = vuln.get("affected_file", None)

            coder_tasks.append({
                "id": task_id,
                "type": "security",
                "severity": vuln.get("severity", "medium"),
                "description": description,
                "fix": fix,
                "affected_file": affected_file,
                "status": "pending"
            })

            file_hint = f"\n   -> DATEI: {affected_file}" if affected_file else ""
            task_prompt_lines.append(
                f"TASK {task_id} [{severity}]: {description}{file_hint}\n"
                f"   -> LÖSUNG: {fix}"
            )

        manager._ui_log("Coder", "CoderTasksOutput", json.dumps({
            "tasks": coder_tasks,
            "count": len(coder_tasks),
            "iteration": iteration + 1
        }, ensure_ascii=False))

        c_prompt += "\n\n⚠️ SECURITY TASKS (priorisiert nach Severity - CRITICAL zuerst):\n"
        c_prompt += "\n".join(task_prompt_lines)
        c_prompt += "\n\nWICHTIG: Bearbeite die Tasks in der angegebenen Reihenfolge! Implementiere die LÖSUNG für jeden Task!\n"

    c_prompt += "\n\n🧪 UNIT-TEST REQUIREMENT:\n"
    c_prompt += "- Erstelle IMMER Unit-Tests für alle neuen Funktionen/Klassen\n"
    c_prompt += "- Test-Dateien: tests/test_<modulname>.py oder tests/<modulname>.test.js\n"
    c_prompt += "- Mindestens 3 Test-Cases pro Funktion (normal, edge-case, error-case)\n"
    c_prompt += "- Format: ### FILENAME: tests/test_<modulname>.py\n"
    c_prompt += "- Tests müssen AUSFÜHRBAR sein (pytest bzw. npm test)\n"

    if manager.tech_blueprint and manager.tech_blueprint.get("requires_server"):
        c_prompt += "\n🔌 API-TESTS:\n"
        c_prompt += "- Teste JEDEN API-Endpoint mit mindestens 2 Test-Cases\n"
        c_prompt += "- Prüfe Erfolgs-Response UND Fehler-Response\n"
        c_prompt += "- Python: pytest + Flask test_client oder requests\n"
        c_prompt += "- JavaScript: jest + supertest\n"

    # AENDERUNG 06.02.2026: run.bat und Framework-Verzeichnisstruktur Regeln
    c_prompt += "\n\n📁 RUN.BAT PFLICHT-REGELN:\n"
    c_prompt += "- run.bat MUSS direkt per Doppelklick lauffaehig sein (KEINE Argumente erforderlich!)\n"
    c_prompt += "- MUSS mit '@echo off' beginnen\n"
    c_prompt += "- MUSS Dependencies installieren (npm install / pip install -r requirements.txt)\n"
    c_prompt += "- MUSS den Server in neuem Fenster starten: start \"\" cmd /c \"npm run dev\"\n"
    c_prompt += "- MUSS den Browser oeffnen: start \"\" http://localhost:PORT\n"
    c_prompt += "- MUSS am Ende 'pause > nul' haben\n"
    c_prompt += "- VERBOTEN: Argumente wie run.bat [dev|build|start]\n"

    # Framework-spezifische Verzeichnisstruktur
    framework = ""
    if manager.tech_blueprint:
        framework = manager.tech_blueprint.get("framework", "").lower()
        project_type = manager.tech_blueprint.get("project_type", "").lower()
        if "next" in framework or "next" in project_type:
            c_prompt += "\n📂 NEXT.JS VERZEICHNISSTRUKTUR (WICHTIG!):\n"
            c_prompt += "- Dateien in pages/, components/, lib/, styles/ (DIREKT im Root!)\n"
            c_prompt += "- NICHT unter src/pages/ oder src/components/ (Next.js ignoriert src/!)\n"
            c_prompt += "- API-Routen: pages/api/...\n"
            c_prompt += "- Erstelle jsconfig.json mit: { \"compilerOptions\": { \"baseUrl\": \".\" } }\n"

    c_prompt += "\nFormat: ### FILENAME: path/to/file.ext"
    return c_prompt


def run_coder_task(manager, project_rules: Dict[str, Any], c_prompt: str, agent_coder) -> Tuple[str, Any]:
    """
    Fuehrt den Coder-Task mit Retry-Logik und Heartbeat-Updates aus.
    ÄNDERUNG 29.01.2026: Modellwechsel erst nach 2 gleichen Fehlern mit demselben Modell.
    """
    task_coder = Task(description=c_prompt, expected_output="Code", agent=agent_coder)
    MAX_CODER_RETRIES = 6  # Erhöht: 2 Versuche pro Modell x 3 Modelle
    # ÄNDERUNG 30.01.2026: Timeout aus globaler Config
    CODER_TIMEOUT_SECONDS = manager.config.get("agent_timeout_seconds", 300)
    # ÄNDERUNG 29.01.2026: Modellwechsel erst nach X gleichen Fehlern
    ERRORS_BEFORE_MODEL_SWITCH = 2
    current_code = ""

    # Fehler-Tracker: (modell, fehlertyp) -> anzahl
    error_tracker = {}
    last_error_type = None

    for coder_attempt in range(MAX_CODER_RETRIES):
        current_model = manager.model_router.get_model("coder") if manager.model_router else "unknown"
        try:
            # ÄNDERUNG 29.01.2026: Heartbeat-Wrapper für stabile WebSocket-Verbindung
            raw_output = run_with_heartbeat(
                func=lambda: str(task_coder.execute_sync()).strip(),
                ui_log_callback=manager._ui_log,
                agent_name="Coder",
                task_description=f"Code-Generierung (Versuch {coder_attempt + 1}/{MAX_CODER_RETRIES})",
                heartbeat_interval=15,
                timeout_seconds=CODER_TIMEOUT_SECONDS
            )
            # ÄNDERUNG 03.02.2026: Fix 8 - Think-Tag Filtering
            # Entfernt <think> Tags und andere Model-spezifische Leaks
            current_code = _clean_model_output(raw_output)
            if current_code != raw_output:
                manager._ui_log("Coder", "ThinkTagFilter", "Model-Output bereinigt (Think-Tags entfernt)")
            break
        except TimeoutError as te:
            # ÄNDERUNG 02.02.2026: OpenRouter-Fehler = sofortiger Modellwechsel
            if is_openrouter_error(te):
                manager._ui_log("Coder", "OpenRouterError",
                                f"OpenRouter-Fehler erkannt bei {current_model} - sofortiger Modellwechsel")
                manager.model_router.mark_rate_limited_sync(current_model)
                # AENDERUNG 06.02.2026: tech_blueprint fuer Tech-Stack-Kontext
                agent_coder = init_agents(
                    manager.config,
                    project_rules,
                    router=manager.model_router,
                    include=["coder"],
                    tech_blueprint=getattr(manager, 'tech_blueprint', None)
                ).get("coder")
                task_coder = Task(description=c_prompt, expected_output="Code", agent=agent_coder)
                error_tracker = {}  # Tracker zurücksetzen nach Modellwechsel

                if coder_attempt == MAX_CODER_RETRIES - 1:
                    manager._ui_log("Coder", "Error", f"Alle {MAX_CODER_RETRIES} Versuche fehlgeschlagen (OpenRouter)")
                    raise te
                continue

            # Normaler Timeout (kein OpenRouter-spezifischer Fehler)
            error_type = "timeout"
            error_key = (current_model, error_type)

            # Bei neuem Fehlertyp: Tracker zurücksetzen
            if last_error_type and last_error_type != error_type:
                error_tracker = {}
            last_error_type = error_type

            error_tracker[error_key] = error_tracker.get(error_key, 0) + 1
            error_count = error_tracker[error_key]

            manager._ui_log("Coder", "Timeout",
                            f"Coder-Modell {current_model} timeout nach {CODER_TIMEOUT_SECONDS}s (Fehler {error_count}/{ERRORS_BEFORE_MODEL_SWITCH})")

            # Erst nach ERRORS_BEFORE_MODEL_SWITCH gleichen Fehlern Modell wechseln
            if error_count >= ERRORS_BEFORE_MODEL_SWITCH:
                manager._ui_log("Coder", "Status", f"🔄 Modellwechsel nach {error_count} Timeouts")
                manager.model_router.mark_rate_limited_sync(current_model)
                # AENDERUNG 06.02.2026: tech_blueprint fuer Tech-Stack-Kontext
                agent_coder = init_agents(
                    manager.config,
                    project_rules,
                    router=manager.model_router,
                    include=["coder"],
                    tech_blueprint=getattr(manager, 'tech_blueprint', None)
                ).get("coder")
                task_coder = Task(description=c_prompt, expected_output="Code", agent=agent_coder)
                error_tracker = {}  # Tracker zurücksetzen nach Modellwechsel

            if coder_attempt == MAX_CODER_RETRIES - 1:
                manager._ui_log("Coder", "Error", f"Alle {MAX_CODER_RETRIES} Versuche fehlgeschlagen (Timeout)")
                raise te
            continue

        except Exception as error:
            # ÄNDERUNG 29.01.2026: LiteLLM interne Bugs wie Rate-Limits behandeln
            if is_litellm_internal_error(error):
                error_type = "litellm_bug"
                error_key = (current_model, error_type)

                # Bei neuem Fehlertyp: Tracker zurücksetzen
                if last_error_type and last_error_type != error_type:
                    error_tracker = {}
                last_error_type = error_type

                error_tracker[error_key] = error_tracker.get(error_key, 0) + 1
                error_count = error_tracker[error_key]

                manager._ui_log("Coder", "Warning",
                                f"LiteLLM-Bug erkannt (Fehler {error_count}/{ERRORS_BEFORE_MODEL_SWITCH}): {str(error)[:100]}")

                # Erst nach ERRORS_BEFORE_MODEL_SWITCH gleichen Fehlern Modell wechseln
                if error_count >= ERRORS_BEFORE_MODEL_SWITCH:
                    manager._ui_log("Coder", "Status", f"🔄 Modellwechsel nach {error_count} LiteLLM-Bugs")
                    manager.model_router.mark_rate_limited_sync(current_model)
                    # AENDERUNG 06.02.2026: tech_blueprint fuer Tech-Stack-Kontext
                    agent_coder = init_agents(
                        manager.config,
                        project_rules,
                        router=manager.model_router,
                        include=["coder"],
                        tech_blueprint=getattr(manager, 'tech_blueprint', None)
                    ).get("coder")
                    task_coder = Task(description=c_prompt, expected_output="Code", agent=agent_coder)
                    error_tracker = {}  # Tracker zurücksetzen nach Modellwechsel

                if coder_attempt == MAX_CODER_RETRIES - 1:
                    manager._ui_log("Coder", "Error", f"Alle {MAX_CODER_RETRIES} Versuche fehlgeschlagen (LiteLLM-Bug): {str(error)[:200]}")
                    raise error
                continue

            if is_rate_limit_error(error):
                # Rate-Limit: Sofort wechseln (keine Wartezeit sinnvoll)
                manager.model_router.mark_rate_limited_sync(current_model)
                manager._ui_log(
                    "ModelRouter",
                    "RateLimit",
                    f"Modell {current_model} pausiert, wechsle zu Fallback..."
                )
                # AENDERUNG 06.02.2026: tech_blueprint fuer Tech-Stack-Kontext
                agent_coder = init_agents(
                    manager.config,
                    project_rules,
                    router=manager.model_router,
                    include=["coder"],
                    tech_blueprint=getattr(manager, 'tech_blueprint', None)
                ).get("coder")
                task_coder = Task(description=c_prompt, expected_output="Code", agent=agent_coder)
                error_tracker = {}  # Tracker zurücksetzen

                if coder_attempt == MAX_CODER_RETRIES - 1:
                    manager._ui_log("Coder", "Error", f"Alle {MAX_CODER_RETRIES} Versuche fehlgeschlagen: {str(error)[:200]}")
                    raise error
                continue

            # ÄNDERUNG 29.01.2026: Server-Fehler-Delay im Caller statt im Helper
            if is_server_error(error):
                manager._ui_log("Coder", "Warning", "Server-Fehler erkannt - kurze Pause von 5s")
                time.sleep(5)
            manager._ui_log("Coder", "Error", f"Unerwarteter Fehler: {str(error)[:200]}")
            raise error

    return current_code, agent_coder


def save_coder_output(manager, current_code: str, output_path: str, iteration: int, max_retries: int) -> tuple:
    """
    Speichert Coder-Output und sendet UI-Events.
    ÄNDERUNG 31.01.2026: Truncation-Detection für abgeschnittene LLM-Outputs.
    ÄNDERUNG 31.01.2026: Unicode-Sanitization vor Datei-Speicherung.
    ÄNDERUNG 31.01.2026: Gibt jetzt (created_files, truncated_files) zurück für Modellwechsel-Logik.
    """
    # ÄNDERUNG 31.01.2026: Unicode-Sanitization vor Datei-Speicherung
    # Entfernt unsichtbare Zeichen (U+FE0F etc.) die Python-Syntax brechen
    sanitized_code = _sanitize_unicode(current_code)

    def_file = os.path.basename(output_path)
    created_files = save_multi_file_output(manager.project_path, sanitized_code, def_file)
    manager._ui_log("Coder", "Files", f"Created: {', '.join(created_files)}")

    # ÄNDERUNG 31.01.2026: Truncation-Detection
    # Prüfe ob Python-Dateien vollständig sind (nicht abgeschnitten)
    # ÄNDERUNG 31.01.2026: truncated_files außerhalb try-Block für Rückgabe
    truncated_files = []
    try:
        files_to_check = {}
        for filename in created_files:
            if filename.endswith('.py'):
                filepath = os.path.join(manager.project_path, filename)
                if os.path.exists(filepath):
                    with open(filepath, 'r', encoding='utf-8') as f:
                        files_to_check[filename] = f.read()

        truncated_files = _check_for_truncation(files_to_check)
        if truncated_files:
            truncated_names = [f[0] for f in truncated_files]
            truncation_details = "; ".join([f"{f[0]}: {f[1]}" for f in truncated_files])
            manager._ui_log("Coder", "TruncationWarning", json.dumps({
                "truncated_files": truncated_names,
                "details": truncation_details,
                "iteration": iteration + 1,
                "action": "model_switch_recommended"
            }, ensure_ascii=False))
            manager._ui_log("Coder", "Warning",
                f"⚠️ Abgeschnittene Dateien erkannt: {', '.join(truncated_names)}")
    except Exception as trunc_err:
        manager._ui_log("Coder", "Warning", f"Truncation-Check fehlgeschlagen: {trunc_err}")

    current_model = manager.model_router.get_model("coder") if manager.model_router else "unknown"
    manager._ui_log("Coder", "CodeOutput", json.dumps({
        "code": current_code,
        "files": created_files,
        "iteration": iteration + 1,
        "max_iterations": max_retries,
        "model": current_model
    }, ensure_ascii=False))
    # ÄNDERUNG 03.02.2026: idle-Reset entfernt - wird jetzt zentral in dev_loop.py via try-finally gehandelt
    # Verhindert doppelten idle-Aufruf und garantiert idle auch bei Exceptions

    try:
        tracker = get_budget_tracker()
        today_totals = tracker.get_today_totals()
        manager._ui_log("Coder", "TokenMetrics", json.dumps({
            "total_tokens": today_totals.get("total_tokens", 0),
            "total_cost": today_totals.get("total_cost", 0.0)
        }, ensure_ascii=False))
    except Exception as budget_err:
        # ÄNDERUNG 29.01.2026: Budget-Tracker Fehler sichtbar loggen
        manager._ui_log(
            "Coder",
            "Warning",
            "Fehler bei get_budget_tracker/tracker.get_today_totals; Details siehe Stacktrace."
        )
        manager._ui_log("Coder", "Warning", traceback.format_exc())

    # ÄNDERUNG 31.01.2026: Gebe auch truncated_files zurück für Modellwechsel-Logik
    return created_files, truncated_files
