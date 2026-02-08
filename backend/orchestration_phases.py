# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 31.01.2026
Version: 1.0
Beschreibung: Agent-Phasen-Modul für Orchestration Manager.
              Extrahiert aus orchestration_manager.py (Regel 1: Max 500 Zeilen)
              Enthält: TechStack, DB-Designer, Designer Phase
"""

import os
import json
import re
import logging
from datetime import datetime
from typing import Callable, Dict, Any

from crewai import Task

from .agent_factory import init_agents
from .orchestration_helpers import (
    extract_tables_from_schema, extract_design_data,
    is_model_unavailable_error, is_rate_limit_error, is_empty_response_error
)
from .heartbeat_utils import run_with_heartbeat
from .orchestration_utils import _repair_json, _extract_json_from_text, _infer_blueprint_from_requirements
from .orchestration_budget import set_current_agent
from .quality_gate import QualityGate

logger = logging.getLogger(__name__)

# AENDERUNG 07.02.2026: Dependency-Helpers extrahiert nach orchestration_deps.py (Regel 1)
from .orchestration_deps import (
    ensure_required_dependencies as _ensure_required_dependencies,
    sanitize_python_dependencies as _sanitize_python_dependencies,
    apply_template_if_selected as _apply_template_if_selected,
)


def run_techstack_phase(
    user_goal: str,
    base_project_rules: dict,
    project_id: str,
    agent_timeout: int,
    config: dict,
    model_router,
    project_path: str,
    discovery_briefing: Dict[str, Any],
    ui_log_callback: Callable,
    update_worker_status_callback: Callable
) -> tuple:
    """
    TechStack-Analyse Phase.

    Args:
        user_goal: Benutzerziel
        base_project_rules: Basis-Projekt-Regeln
        project_id: Projekt-ID
        agent_timeout: Timeout für Agenten
        config: Konfiguration
        model_router: Model Router Instanz
        project_path: Projekt-Pfad
        discovery_briefing: Discovery Briefing
        ui_log_callback: UI-Log Callback
        update_worker_status_callback: Worker-Status Callback

    Returns:
        Tuple (tech_blueprint, quality_gate)
    """
    ui_log_callback("TechArchitect", "Status", "Analysiere TechStack...")
    set_current_agent("TechStack-Architect", project_id)
    update_worker_status_callback("techstack_architect", "working", "Analysiere TechStack...",
                                   model_router.get_model("techstack_architect"))

    # AENDERUNG 08.02.2026: Template-Score als Empfehlung an TechArchitect (Fix 22.1)
    # ROOT-CAUSE-FIX: TechArchitect-LLM ignoriert Template-Ranking weil es nur als Auflistung kommt
    # Symptom: nextjs_tailwind gewaehlt statt nextjs_sqlite trotz Score 50 vs 72
    # Loesung: Expliziten Score-Vergleich als "STARKE EMPFEHLUNG" in Task-Description
    template_hint = ""
    try:
        from techstack_templates.template_loader import find_matching_templates
        template_matches = find_matching_templates(user_goal)
        if template_matches:
            top_id, _top_tmpl, top_score = template_matches[0]
            second_score = template_matches[1][2] if len(template_matches) > 1 else 0
            if top_score > second_score * 1.3:
                template_hint = (
                    f"\n\nSTARKE EMPFEHLUNG: Verwende Template '{top_id}' "
                    f"(Score {top_score} vs naechstbestes {second_score}). "
                    f"Dieses Template passt am besten zu den Anforderungen."
                )
                ui_log_callback("TechArchitect", "Info",
                    f"Template-Matching: '{top_id}' empfohlen (Score {top_score} vs {second_score})")
            elif template_matches:
                top3 = [f"'{tid}' (Score {s})" for tid, _, s in template_matches[:3]]
                template_hint = f"\n\nTemplate-Ranking: {', '.join(top3)}"
    except Exception as tmpl_err:
        logger.warning("Template-Matching fehlgeschlagen: %s", tmpl_err)

    # ÄNDERUNG 02.02.2026: MAX_TECHSTACK_RETRIES erhöht von 3 auf 7 (Bug #3 Fix)
    # Grund: primary + 4 fallbacks + extended_fallbacks + dynamischer Fallback brauchen mehr Versuche
    MAX_TECHSTACK_RETRIES = 7
    techstack_result = None
    for techstack_attempt in range(MAX_TECHSTACK_RETRIES):
        current_techstack_model = model_router.get_model("techstack_architect")
        try:
            agent_techstack = init_agents(config, base_project_rules, router=model_router,
                                          include=["techstack_architect"]).get("techstack_architect")
            techstack_task = Task(description=f"Entscheide TechStack für: {user_goal}{template_hint}",
                                  expected_output="JSON-Blueprint.", agent=agent_techstack)
            techstack_result = run_with_heartbeat(
                func=lambda: str(techstack_task.execute_sync()), ui_log_callback=ui_log_callback,
                agent_name="TechStack", task_description="Tech-Stack Analyse",
                heartbeat_interval=15, timeout_seconds=agent_timeout
            )
            break
        except Exception as ts_error:
            if is_model_unavailable_error(ts_error) or is_rate_limit_error(ts_error) or is_empty_response_error(ts_error):
                ui_log_callback("TechStack", "Warning", f"Modell {current_techstack_model} nicht verfügbar/leer (Versuch {techstack_attempt + 1}/{MAX_TECHSTACK_RETRIES}), wechsle zu Fallback...")
                model_router.mark_rate_limited_sync(current_techstack_model)
                if techstack_attempt == MAX_TECHSTACK_RETRIES - 1:
                    # ÄNDERUNG 02.02.2026: Erst requirement-basierten Fallback wenn alle Modelle erschöpft
                    fallback_blueprint = _infer_blueprint_from_requirements(user_goal)
                    ui_log_callback("TechStack", "Error", f"Alle TechStack-Modelle erschöpft nach {MAX_TECHSTACK_RETRIES} Versuchen, verwende requirement-basierten Fallback: {fallback_blueprint['project_type']}")
                    techstack_result = json.dumps(fallback_blueprint)
                continue
            else:
                # ÄNDERUNG 03.02.2026: ROOT-CAUSE-FIX - idle vor raise
                # Problem: raise ohne idle ließ TechArchitect auf "working" stecken
                update_worker_status_callback("techstack_architect", "idle")
                raise ts_error

    # JSON-Parsing
    tech_blueprint = {}
    if not techstack_result:
        tech_blueprint = _infer_blueprint_from_requirements(user_goal)
        ui_log_callback("TechStack", "Warning", "Kein TechStack-Ergebnis, verwende requirement-basierten Fallback")
    else:
        try:
            json_text = None
            code_block_match = re.search(r'```(?:json)?\s*(\{[\s\S]*?\})\s*```', techstack_result)
            if code_block_match:
                json_text = code_block_match.group(1)
            if not json_text:
                json_text = _extract_json_from_text(techstack_result)
                if json_text and "'" in json_text and '"' not in json_text:
                    json_text = _repair_json(json_text)
                    ui_log_callback("TechArchitect", "Info", "JSON mit single quotes erkannt, repariere...")
            if json_text:
                try:
                    tech_blueprint = json.loads(json_text)
                except json.JSONDecodeError:
                    repaired = _repair_json(json_text)
                    tech_blueprint = json.loads(repaired)
                    ui_log_callback("TechArchitect", "Info", "JSON erfolgreich repariert")
            else:
                raise ValueError("Kein JSON gefunden in TechStack-Antwort")
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            tech_blueprint = _infer_blueprint_from_requirements(user_goal)
            ui_log_callback("TechArchitect", "Warning", f"Blueprint-Parsing fehlgeschlagen ({e}), verwende requirement-basierten Fallback: {tech_blueprint['project_type']}")

    # AENDERUNG 07.02.2026: Template-basierte Blueprint-Erstellung
    # Wenn Agent ein Template gewaehlt hat, Blueprint aus Template bauen
    tech_blueprint = _apply_template_if_selected(tech_blueprint, project_path, ui_log_callback)

    # AENDERUNG 02.02.2026: Ungueltige Python-Pakete entfernen (Bug #2 Fix)
    # Safety Net: Laeuft IMMER, auch bei Template-basierten Blueprints
    if "dependencies" in tech_blueprint:
        tech_blueprint["dependencies"] = _sanitize_python_dependencies(
            tech_blueprint["dependencies"],
            tech_blueprint.get("language", ""),
            ui_log_callback
        )
        # AENDERUNG 07.02.2026: Pflicht-Dependencies ergaenzen (react-dom, postcss etc.)
        # AENDERUNG 08.02.2026: database-Parameter durchreichen fuer DB-Dependency Safety Net (Fix 22.2)
        tech_blueprint["dependencies"] = _ensure_required_dependencies(
            tech_blueprint["dependencies"],
            tech_blueprint.get("language", ""),
            tech_blueprint.get("project_type", ""),
            ui_log_callback,
            database=tech_blueprint.get("database", "none")
        )

    ui_log_callback("TechArchitect", "Blueprint", json.dumps(tech_blueprint, ensure_ascii=False))
    update_worker_status_callback("techstack_architect", "idle")
    ui_log_callback("TechArchitect", "TechStackOutput", json.dumps({
        "blueprint": tech_blueprint, "model": model_router.get_model("techstack_architect"),
        "decisions": [
            {"type": "Sprache", "value": tech_blueprint.get("language", "unknown")},
            {"type": "Framework", "value": tech_blueprint.get("project_type", "unknown")},
            {"type": "Datenbank", "value": tech_blueprint.get("database", "keine")},
            {"type": "Server", "value": f"Port {tech_blueprint.get('server_port', '-')}" if tech_blueprint.get("requires_server") else "Nicht benötigt"}
        ],
        "dependencies": tech_blueprint.get("dependencies", []),
        "reasoning": tech_blueprint.get("reasoning", "")
    }, ensure_ascii=False))

    with open(os.path.join(project_path, "tech_blueprint.json"), "w", encoding="utf-8") as f:
        json.dump(tech_blueprint, f, indent=2, ensure_ascii=False)

    quality_gate = QualityGate(user_goal, discovery_briefing)
    ts_validation = quality_gate.validate_techstack(tech_blueprint)
    ui_log_callback("QualityGate", "TechStackValidation", json.dumps({
        "step": "TechStack", "passed": ts_validation.passed, "score": ts_validation.score,
        "issues": ts_validation.issues, "warnings": ts_validation.warnings,
        "requirements": quality_gate.get_requirements_summary()
    }, ensure_ascii=False))
    if not ts_validation.passed:
        ui_log_callback("QualityGate", "Warning", f"TechStack-Blueprint verletzt Benutzer-Anforderungen: {', '.join(ts_validation.issues)}")

    return tech_blueprint, quality_gate


def run_db_designer_phase(
    user_goal: str,
    project_rules: dict,
    project_id: str,
    agent_timeout: int,
    config: dict,
    model_router,
    tech_blueprint: dict,
    quality_gate,
    doc_service,
    ui_log_callback: Callable,
    update_worker_status_callback: Callable
) -> str:
    """
    DB-Designer Phase.

    Returns:
        database_schema als String
    """
    ui_log_callback("DBDesigner", "Status", "Erstelle Schema...")
    set_current_agent("Database-Designer", project_id)
    dbdesigner_model = model_router.get_model("database_designer") if model_router else "unknown"
    update_worker_status_callback("db_designer", "working", "Erstelle Schema...", dbdesigner_model)

    database_schema = ""
    MAX_DB_RETRIES = 3
    for db_attempt in range(MAX_DB_RETRIES):
        current_db_model = model_router.get_model("database_designer")
        try:
            agent_db = init_agents(config, project_rules, router=model_router, include=["db_designer"]).get("db_designer")
            if agent_db:
                task_db = Task(description=f"Schema für {user_goal}", expected_output="Schema", agent=agent_db)
                database_schema = run_with_heartbeat(
                    func=lambda: str(task_db.execute_sync()), ui_log_callback=ui_log_callback,
                    agent_name="DB-Designer", task_description="Datenbank-Schema Erstellung",
                    heartbeat_interval=15, timeout_seconds=agent_timeout
                )
                break
        except Exception as db_error:
            if is_model_unavailable_error(db_error) or is_rate_limit_error(db_error) or is_empty_response_error(db_error):
                ui_log_callback("DBDesigner", "Warning", f"Modell {current_db_model} nicht verfügbar/leer (Versuch {db_attempt + 1}/{MAX_DB_RETRIES}), wechsle...")
                model_router.mark_rate_limited_sync(current_db_model)
                if db_attempt == MAX_DB_RETRIES - 1:
                    ui_log_callback("DBDesigner", "Error", "Alle DB-Modelle nicht verfügbar, überspringe Schema")
                    database_schema = ""
            else:
                ui_log_callback("DBDesigner", "Error", f"Schema-Fehler: {str(db_error)[:200]}")
                database_schema = ""
                break

    update_worker_status_callback("db_designer", "idle")
    ui_log_callback("DBDesigner", "DBDesignerOutput", json.dumps({
        "schema": database_schema[:2000] if database_schema else "",
        "model": dbdesigner_model, "status": "completed" if database_schema else "error",
        "tables": extract_tables_from_schema(database_schema) if database_schema else [],
        "timestamp": datetime.now().isoformat()
    }, ensure_ascii=False))

    if database_schema and quality_gate:
        schema_validation = quality_gate.validate_schema(database_schema, tech_blueprint)
        ui_log_callback("QualityGate", "SchemaValidation", json.dumps({
            "step": "DBSchema", "passed": schema_validation.passed, "score": schema_validation.score,
            "issues": schema_validation.issues, "warnings": schema_validation.warnings
        }, ensure_ascii=False))
        if doc_service:
            doc_service.collect_schema(database_schema)
            doc_service.collect_quality_validation("DBSchema", {
                "passed": schema_validation.passed, "score": schema_validation.score,
                "issues": schema_validation.issues, "warnings": schema_validation.warnings
            })

    return database_schema


def run_designer_phase(
    user_goal: str,
    project_rules: dict,
    project_id: str,
    project_path: str,
    agent_timeout: int,
    config: dict,
    model_router,
    tech_blueprint: dict,
    quality_gate,
    doc_service,
    ui_log_callback: Callable,
    update_worker_status_callback: Callable
) -> str:
    """
    Designer Phase.

    Returns:
        design_concept als String
    """
    ui_log_callback("Designer", "Status", "Erstelle Design-Konzept...")
    set_current_agent("Designer", project_id)
    designer_model = model_router.get_model("designer") if model_router else "unknown"
    update_worker_status_callback("designer", "working", "Erstelle Design-Konzept...", designer_model)

    design_concept = ""
    MAX_DESIGN_RETRIES = 3
    for design_attempt in range(MAX_DESIGN_RETRIES):
        current_design_model = model_router.get_model("designer")
        try:
            agent_des = init_agents(config, project_rules, router=model_router, include=["designer"]).get("designer")
            if agent_des:
                tech_info = f"Tech-Stack: {tech_blueprint.get('project_type', 'webapp')}"
                if tech_blueprint.get('dependencies'):
                    tech_info += f", Frameworks: {', '.join(tech_blueprint.get('dependencies', []))}"
                task_des = Task(description=f"Design für: {user_goal}\n{tech_info}", expected_output="Konzept", agent=agent_des)
                design_concept = run_with_heartbeat(
                    func=lambda: str(task_des.execute_sync()), ui_log_callback=ui_log_callback,
                    agent_name="Designer", task_description="UI/UX Design",
                    heartbeat_interval=15, timeout_seconds=agent_timeout
                )
                break
        except Exception as des_error:
            if is_model_unavailable_error(des_error) or is_rate_limit_error(des_error) or is_empty_response_error(des_error):
                ui_log_callback("Designer", "Warning", f"Modell {current_design_model} nicht verfügbar/leer (Versuch {design_attempt + 1}/{MAX_DESIGN_RETRIES}), wechsle...")
                model_router.mark_rate_limited_sync(current_design_model)
                if design_attempt == MAX_DESIGN_RETRIES - 1:
                    ui_log_callback("Designer", "Error", "Alle Design-Modelle nicht verfügbar, überspringe Design")
                    design_concept = ""
            else:
                ui_log_callback("Designer", "Error", f"Design-Fehler: {str(des_error)[:200]}")
                design_concept = ""
                break

    update_worker_status_callback("designer", "idle")
    if design_concept:
        design_data = extract_design_data(design_concept)
        ui_log_callback("Designer", "DesignerOutput", json.dumps({
            "colorPalette": design_data["colorPalette"], "typography": design_data["typography"],
            "atomicAssets": design_data["atomicAssets"], "qualityScore": design_data["qualityScore"],
            "iterationInfo": {"current": 1, "progress": 100}, "viewport": {"width": 1440, "height": 900},
            "previewUrl": f"file://{project_path}/index.html" if project_path else "",
            "concept": design_concept[:2000] if design_concept else "",
            "model": designer_model, "timestamp": datetime.now().isoformat()
        }, ensure_ascii=False))

        if quality_gate:
            design_validation = quality_gate.validate_design(design_concept, tech_blueprint)
            ui_log_callback("QualityGate", "DesignValidation", json.dumps({
                "step": "Design", "passed": design_validation.passed, "score": design_validation.score,
                "issues": design_validation.issues, "warnings": design_validation.warnings
            }, ensure_ascii=False))
            if doc_service:
                doc_service.collect_design(design_concept)
                doc_service.collect_quality_validation("Design", {
                    "passed": design_validation.passed, "score": design_validation.score,
                    "issues": design_validation.issues, "warnings": design_validation.warnings
                })

    return design_concept


# AENDERUNG 08.02.2026: Fix 24 - Waisen-Check Phase
def run_waisen_check_phase(
    anforderungen: list,
    features: list,
    tasks: list,
    file_generations: list,
    quality_gate: QualityGate,
    ui_log_callback: Callable
):
    """
    Waisen-Check: Prueft Traceability-Kette ANF → FEAT → TASK → FILE.
    Aufgerufen nach Feature-Ableitung und Planner-Phase.

    ROOT-CAUSE-FIX 08.02.2026:
    Symptom: QualityGate.validate_waisen() existiert, wird aber nirgends aufgerufen
    Ursache: Fehlende Integration in Orchestration-Flow
    Loesung: Dedizierte Phase nach Feature-Ableitung
    """
    try:
        result = quality_gate.validate_waisen(
            anforderungen, features, tasks, file_generations
        )

        ui_log_callback("Validator", "WaisenCheck", json.dumps({
            "step": "WaisenCheck",
            "passed": result.passed,
            "score": result.score,
            "waisen": result.details.get("waisen", {}),
            "counts": result.details.get("counts", {})
        }, ensure_ascii=False))

        if not result.passed:
            for issue in result.issues:
                ui_log_callback("Validator", "WaisenWarning", issue)

        if result.warnings:
            for warning in result.warnings:
                ui_log_callback("Validator", "WaisenInfo", warning)

        logger.info(f"Waisen-Check: passed={result.passed}, score={result.score:.2f}")
        return result

    except Exception as e:
        logger.warning(f"Waisen-Check Fehler: {e}")
        ui_log_callback("Validator", "WaisenError", f"Waisen-Check fehlgeschlagen: {e}")
        return None
