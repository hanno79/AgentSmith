# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 08.02.2026
Version: 1.0
Beschreibung: Prompt-Builder-Funktionen fuer den DevLoop Coder.
              Extrahiert aus dev_loop_coder.py (Regel 1: Max 500 Zeilen).
              Enthaelt: _build_patch_prompt, build_coder_prompt,
              Security-Fix-Templates, Framework-spezifische Prompt-Regeln.
"""

import os
import json
import logging
from typing import Dict, Any, List

from agents.memory_agent import get_lessons_for_prompt
from agents.memory_core import get_constraints_for_prompt
from .dev_loop_helpers import get_python_dependency_versions
from .file_status_detector import get_file_status_summary_for_log
from .dev_loop_coder_utils import (
    _is_targeted_fix_context,
    _get_affected_files_from_feedback,
    _get_current_code_dict,
)

logger = logging.getLogger(__name__)


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

    # AENDERUNG 03.02.2026: Fix 8 - Typ-Check fuer current_code
    # current_code kann ein Dict ODER ein String sein (je nach Speicher-Format)
    if current_code is None:
        current_code = {}
    elif isinstance(current_code, str):
        # Fallback: Wenn current_code ein String ist, als Context anhaengen
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


# AENDERUNG 07.02.2026: Security Fix-Templates mit konkreten Code-Beispielen (Fix 20)
# ROOT-CAUSE-FIX:
# Symptom: SQL Injection wird erkannt aber Coder schreibt selben unsicheren Code
# Ursache: Coder bekommt nur "Verwende parametrisierte Queries" ohne konkretes Beispiel
# Loesung: Template mit FALSCH/RICHTIG Vergleich fuer bekannte Vulnerability-Typen
_SECURITY_FIX_TEMPLATES = {
    "sql_injection": {
        "keywords": ["sql injection", "sql-injection", "string-konkatenation in sql",
                     "string concatenation", "template literal", "sql query"],
        "fix_example": (
            "FALSCH: db.prepare(`SELECT * FROM t WHERE id = ${id}`)\n"
            "FALSCH: db.prepare(`UPDATE task SET ${updates.join(', ')} WHERE id = ?`)\n"
            "RICHTIG: Feste Feld-Liste mit individuellen Parametern:\n"
            "  const stmt = db.prepare('UPDATE task SET title = ?, description = ?, status = ? WHERE id = ?');\n"
            "  stmt.run(title, description, status, id);\n"
            "REGEL: KEINE Template-Literals oder String-Konkatenation in SQL! "
            "Jeder Wert als separater ? Parameter."
        )
    },
    "xss": {
        "keywords": ["xss", "innerhtml", "document.write", "dangerouslysetinnerhtml"],
        "fix_example": (
            "FALSCH: element.innerHTML = userInput\n"
            "RICHTIG: element.textContent = userInput\n"
            "Oder: DOMPurify.sanitize(userInput) wenn HTML noetig"
        )
    },
}


def build_coder_prompt(
    manager,
    user_goal: str,
    feedback: str,
    iteration: int,
    utds_tasks: list = None,
    files_to_patch: list = None,
    utds_protected_files: list = None,
    iteration_history: list = None
) -> str:
    """
    Baut den Coder-Prompt basierend auf Kontext, Feedback, UTDS-Tasks und File-Status.

    AENDERUNG 05.02.2026: UTDS-Task-Erkennung und FileStatusDetector Integration.
    Wenn UTDS-Tasks vorhanden sind oder Dateien identifiziert wurden die gepatcht werden muessen,
    wird automatisch der Patch-Modus aktiviert.
    """
    c_prompt = f"Ziel: {user_goal}\nTech: {manager.tech_blueprint}\nDB: {manager.database_schema}\n"

    briefing_context = manager.get_briefing_context()
    if briefing_context:
        c_prompt += f"\n{briefing_context}\n"

    # AENDERUNG 08.02.2026: Designer-Output als Pflicht-Input fuer Coder (Fix 22.6)
    if hasattr(manager, 'design_concept') and manager.design_concept and "Kein Design" not in manager.design_concept:
        design_brief = manager.design_concept[:500]
        c_prompt += (
            f"\n### DESIGN-VORGABEN (PFLICHT — vom Designer-Agenten):\n"
            f"{design_brief}\n"
            f"Verwende diese Farben und das beschriebene Design-Konzept!\n"
        )

    # AENDERUNG 09.02.2026: Fix 35 — Iteration-Memory fuer Coder-Kontext
    if iteration_history and len(iteration_history) > 0:
        c_prompt += "\n### ITERATIONS-HISTORIE (vorherige Fixes - BEACHTEN!):\n"
        for entry in iteration_history[-5:]:  # Letzte 5 Iterationen
            it_nr = entry["iteration"]
            fb_files = ", ".join(entry.get("feedback_files", [])[:5])
            utds_files = ", ".join(entry.get("utds_fixed", [])[:5])
            c_prompt += f"- Iteration {it_nr}: Reviewer bemangelte [{fb_files}]"
            if utds_files:
                c_prompt += f" -> UTDS hat gefixt: [{utds_files}]"
            c_prompt += "\n"
        # Ping-Pong-Warnung fuer Dateien die mehrfach bemangelt wurden
        repeated = {}
        for entry in iteration_history:
            for f in entry.get("feedback_files", []):
                repeated[f] = repeated.get(f, 0) + 1
        pp_files = [f for f, c in repeated.items() if c >= 2]
        if pp_files:
            max_count = max(repeated[f] for f in pp_files)
            c_prompt += f"ACHTUNG: {', '.join(pp_files)} wurde(n) bereits {max_count}x bemangelt!\n"
            c_prompt += "Diese Dateien NICHT mit falschen Patterns regenerieren!\n"

    # AENDERUNG 09.02.2026: Fix 35 — Geschuetzte Dateien als Warnung im Prompt
    if utds_protected_files and len(utds_protected_files) > 0:
        c_prompt += "\n### GESCHUETZTE DATEIEN (gerade durch UTDS gefixt - NICHT veraendern!):\n"
        for pf in utds_protected_files:
            c_prompt += f"- {pf} (UTDS-Fix aktiv, NICHT regenerieren)\n"
        c_prompt += "Generiere diese Dateien NICHT neu. Sie wurden gerade automatisch repariert.\n"

    # AENDERUNG 05.02.2026: UTDS-Task-Erkennung fuer Patch-Modus
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
    if use_patch_mode:
        code_dict = _get_current_code_dict(manager)

        if utds_tasks or files_to_patch:
            affected_files = files_to_patch or _get_affected_files_from_feedback(feedback)

            # AENDERUNG 09.02.2026: Fix 35 — UTDS-geschuetzte Dateien aus Patch-Liste entfernen
            if utds_protected_files and affected_files:
                pre_count = len(affected_files)
                affected_files = [f for f in affected_files
                                  if not any(p in f or f in p for p in utds_protected_files)]
                removed = pre_count - len(affected_files)
                if removed > 0:
                    manager._ui_log("Coder", "FileProtection",
                        f"{removed} UTDS-geschuetzte Datei(en) aus Patch-Liste entfernt")

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
                manager._ui_log("Coder", "FullMode",
                    f"PatchMode-Fallback: {patch_mode_reason}")
                c_prompt += f"\nAlt-Code:\n{manager.current_code}\n"
                if feedback:
                    c_prompt += f"\nKorrektur: {feedback}\n"
        else:
            affected_files = _get_affected_files_from_feedback(feedback)

            # AENDERUNG 09.02.2026: Fix 35 — UTDS-geschuetzte Dateien auch hier filtern
            if utds_protected_files and affected_files:
                affected_files = [f for f in affected_files
                                  if not any(p in f or f in p for p in utds_protected_files)]

            if affected_files and code_dict:
                manager._ui_log("Coder", "PatchMode",
                    f"Patch-Modus aktiv fuer: {', '.join(affected_files)}")
                c_prompt += _build_patch_prompt(code_dict, affected_files, feedback)
            else:
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
        # ROOT-CAUSE-FIX 06.02.2026 (v2): Strukturierter Multi-File-Kontext statt roher String
        code_dict = _get_current_code_dict(manager)
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

    # AENDERUNG 03.02.2026: Fix 7 - Environment Constraints laden
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
    try:
        dep_versions = get_python_dependency_versions()
        if dep_versions:
            c_prompt += f"\n\n📦 {dep_versions}\n"
            c_prompt += "WICHTIG: Für requirements.txt NUR diese Versionen verwenden! Keine eigenen Versionen erfinden!\n"
    except Exception as dep_err:
        manager._ui_log("Coder", "Warning", f"Dependency-Versionen konnten nicht geladen werden: {dep_err}")

    # AENDERUNG 07.02.2026: Security Fix-Templates
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
            # AENDERUNG 07.02.2026: Template-Fix anhaengen wenn bekannter Vulnerability-Typ
            template_hint = ""
            desc_lower = description.lower()
            for tmpl_key, tmpl_data in _SECURITY_FIX_TEMPLATES.items():
                if any(kw in desc_lower for kw in tmpl_data["keywords"]):
                    template_hint = f"\n   -> KONKRETES BEISPIEL:\n   {tmpl_data['fix_example']}"
                    break

            task_prompt_lines.append(
                f"TASK {task_id} [{severity}]: {description}{file_hint}\n"
                f"   -> LÖSUNG: {fix}{template_hint}"
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

    # AENDERUNG 07.02.2026: Dynamische Template-Regeln statt hartcodierte Framework-Regeln
    _source_template = None
    if manager.tech_blueprint:
        _source_template = manager.tech_blueprint.get("_source_template")

    if _source_template:
        # Template-basierte Regeln — dynamisch aus Template laden
        try:
            from techstack_templates.template_loader import get_template_by_id, get_coder_rules
            template = get_template_by_id(_source_template)
            if template:
                coder_rules = get_coder_rules(template)
                if coder_rules:
                    c_prompt += f"\n\n{coder_rules}\n"
                # Pinned-Versionen aus Template als Referenz
                pinned = manager.tech_blueprint.get("_pinned_versions", {})
                if pinned:
                    c_prompt += "\nGEPINNTE VERSIONEN (verwende EXAKT diese):\n"
                    for pkg, ver in pinned.items():
                        c_prompt += f"  {pkg}: {ver}\n"
                # AENDERUNG 07.02.2026: SVG Data-URL Verbot auch bei Template-Projekten (Fix 20)
                c_prompt += "\nKEINE INLINE SVG DATA-URLs:\n"
                c_prompt += "- NIEMALS url(\"data:image/svg+xml,...\") in CSS oder JSX verwenden!\n"
                c_prompt += "- Stattdessen: CSS-Gradienten, separate .svg in public/, Unicode-Zeichen\n"
        except ImportError:
            pass
    else:
        # Fallback: Hartcodierte Regeln fuer Projekte ohne Template
        language = ""
        if manager.tech_blueprint:
            language = manager.tech_blueprint.get("language", "").lower()
        if language in ("javascript", "typescript"):
            c_prompt += "\n\nDEPENDENCY-VOLLSTAENDIGKEIT (KRITISCH!):\n"
            c_prompt += "- JEDE importierte Bibliothek MUSS in package.json 'dependencies' stehen!\n"
            c_prompt += "- Verwende EXAKTE Versionen (KEIN ^ oder ~ Prefix)!\n"
            c_prompt += "- Node.js built-ins (fs, path, crypto) NICHT in package.json.\n"
        framework = ""
        if manager.tech_blueprint:
            framework = manager.tech_blueprint.get("framework", "").lower()
            project_type = manager.tech_blueprint.get("project_type", "").lower()
            if "next" in framework or "next" in project_type:
                # AENDERUNG 08.02.2026: App Router statt Pages Router (Fix 22.4C)
                c_prompt += "\nNEXT.JS REGELN (App Router):\n"
                c_prompt += "- ES6 import/export (KEIN require/module.exports)\n"
                c_prompt += "- Dateien in app/, components/, lib/ DIREKT im Root (NICHT src/)\n"
                c_prompt += "- app/layout.js + app/globals.css MUESSEN existieren\n"
                c_prompt += "- API-Routen als Route Handlers: export async function GET/POST(request) in app/api/*/route.js\n"
                c_prompt += "- Client-Components mit 'use client' Direktive am Dateianfang\n"
                c_prompt += "- Verwende next/jest, NICHT @next/jest\n"
                # AENDERUNG 07.02.2026: SVG Data-URL Verbot (Fix 20)
                c_prompt += "- KEINE inline SVG Data-URLs in CSS oder JSX! "
                c_prompt += "Verwende stattdessen: CSS-Gradienten (radial-gradient, linear-gradient), "
                c_prompt += "separate .svg Dateien in public/, oder Unicode-Zeichen.\n"

    # AENDERUNG 08.02.2026: Router-Konsistenz bei Next.js erzwingen (Fix 23A)
    if manager.tech_blueprint:
        _pt = manager.tech_blueprint.get("project_type", "").lower()
        if "next" in _pt:
            c_prompt += "\nROUTER-KONSISTENZ (KRITISCH):\n"
            c_prompt += "- VERBOTEN: Erstelle KEINE Dateien unter pages/ (Pages Router ist VERALTET)\n"
            c_prompt += "- Verwende AUSSCHLIESSLICH App Router: app/layout.js, app/page.js, app/api/*/route.js\n"
            c_prompt += "- Wenn pages/ Dateien existieren: IGNORIERE sie, erstelle KEINE neuen\n"

    # AENDERUNG 07.02.2026: Datei-Blacklist (gilt fuer ALLE Frameworks)
    c_prompt += "\nDIESE DATEIEN NIEMALS GENERIEREN:\n"
    c_prompt += "- package-lock.json (wird automatisch durch npm install erstellt)\n"
    c_prompt += "- node_modules/ (wird automatisch durch npm install erstellt)\n"
    c_prompt += "- .next/ (wird automatisch durch next build erstellt)\n"

    # AENDERUNG 09.02.2026: Purple-Verbot (CLAUDE.md Regel 19, Dreifach-Schutz)
    c_prompt += "\nDESIGN-REGELN (Regel 19 - VERBINDLICH):\n"
    c_prompt += "- KEINE purple, violet oder indigo Farben verwenden!\n"
    c_prompt += "- KEINE blue-purple Gradients!\n"
    c_prompt += "- Verwende moderne, saubere Farben die zum Thema passen.\n"

    c_prompt += "\nFormat: ### FILENAME: path/to/file.ext"
    return c_prompt
