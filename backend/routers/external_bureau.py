# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 29.01.2026
Version: 1.0
Beschreibung: External Bureau Endpunkte für Specialists und Reviews.
"""
# ÄNDERUNG 29.01.2026: External-Bureau-Endpunkte in eigenes Router-Modul verschoben

from typing import Optional, Any
import os
import dataclasses
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from ..api_logging import log_event
from ..app_state import manager

router = APIRouter()

_external_bureau_manager = None


def _safe_serialize(obj: Any):
    """
    ÄNDERUNG 29.01.2026: Sichere Serialisierung für Findings.
    """
    try:
        if dataclasses.is_dataclass(obj):
            return dataclasses.asdict(obj)
        if hasattr(obj, "dict") and callable(obj.dict):
            return obj.dict()
        if hasattr(obj, "__dict__"):
            return vars(obj)
        if isinstance(obj, dict):
            return {k: _safe_serialize(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [_safe_serialize(v) for v in obj]
        if isinstance(obj, (str, int, float, bool)) or obj is None:
            return obj
    except Exception:
        return {"_unserializable": True, "repr": repr(obj)}
    return {"_unserializable": True, "repr": repr(obj)}


def get_external_bureau_manager():
    """Lazy-load des External Bureau Managers."""
    global _external_bureau_manager
    if _external_bureau_manager is None:
        try:
            from agents.external_bureau_manager import ExternalBureauManager
            _external_bureau_manager = ExternalBureauManager(manager.config)
        except Exception as e:
            log_event("API", "Error", f"External Bureau Manager konnte nicht geladen werden: {e}")
            return None
    return _external_bureau_manager


@router.get("/external-bureau/status")
def get_external_bureau_status():
    """Gibt den Status des External Bureau zurueck."""
    bureau = get_external_bureau_manager()
    if not bureau:
        return {
            "enabled": False,
            "error": "External Bureau Manager nicht verfuegbar",
            "specialists": []
        }
    return bureau.get_status()


@router.get("/external-bureau/specialists")
def get_all_specialists(category: Optional[str] = None):
    """
    Listet alle externen Specialists auf.

    Args:
        category: Optional - "all", "combat", "intelligence", "creative"
    """
    bureau = get_external_bureau_manager()
    if not bureau:
        return {"specialists": [], "error": "External Bureau nicht verfuegbar"}

    if category:
        specialists = bureau.get_specialists_by_category(category)
    else:
        specialists = bureau.get_all_specialists()

    return {"specialists": specialists, "count": len(specialists)}


@router.post("/external-bureau/specialists/{specialist_id}/activate")
def activate_specialist(specialist_id: str):
    """Aktiviert einen Specialist."""
    bureau = get_external_bureau_manager()
    if not bureau:
        raise HTTPException(status_code=503, detail="External Bureau nicht verfuegbar")

    result = bureau.activate_specialist(specialist_id)
    if result["success"]:
        return result
    raise HTTPException(status_code=400, detail=result["message"])


@router.post("/external-bureau/specialists/{specialist_id}/deactivate")
def deactivate_specialist(specialist_id: str):
    """Deaktiviert einen Specialist."""
    bureau = get_external_bureau_manager()
    if not bureau:
        raise HTTPException(status_code=503, detail="External Bureau nicht verfuegbar")

    result = bureau.deactivate_specialist(specialist_id)
    if result["success"]:
        return result
    raise HTTPException(status_code=400, detail=result["message"])


@router.get("/external-bureau/findings")
def get_external_findings():
    """Gibt alle gesammelten Findings aller Specialists zurueck."""
    bureau = get_external_bureau_manager()
    if not bureau:
        return {"findings": [], "error": "External Bureau nicht verfuegbar"}

    findings = bureau.get_combined_findings()
    return {"findings": findings, "count": len(findings)}


class SearchRequest(BaseModel):
    query: str
    num_results: int = 10


@router.post("/external-bureau/search")
async def run_external_search(request: SearchRequest):
    """Fuehrt eine EXA Search durch."""
    bureau = get_external_bureau_manager()
    if not bureau:
        raise HTTPException(status_code=503, detail="External Bureau nicht verfuegbar")

    result = await bureau.run_search(request.query)
    if not result:
        raise HTTPException(status_code=400, detail="EXA Search nicht verfuegbar oder nicht aktiviert")

    return {
        "success": result.success,
        "findings": [_safe_serialize(f) for f in result.findings],
        "summary": result.summary,
        "duration_ms": result.duration_ms,
        "error": result.error
    }


class ReviewRequest(BaseModel):
    project_path: Optional[str] = None
    files: Optional[list] = None


@router.post("/external-bureau/review")
async def run_external_review(request: ReviewRequest):
    """Fuehrt ein Review mit allen aktiven COMBAT-Specialists durch."""
    bureau = get_external_bureau_manager()
    if not bureau:
        raise HTTPException(status_code=503, detail="External Bureau nicht verfuegbar")

    # ÄNDERUNG 29.01.2026: project_path validieren, kein Default "."
    project_path = request.project_path or manager.project_path
    if not project_path or not str(project_path).strip() or str(project_path).strip() in [".", "./"]:
        raise HTTPException(status_code=400, detail="project_path ist erforderlich und darf nicht '.' sein")
    if not os.path.isdir(project_path):
        raise HTTPException(status_code=400, detail=f"project_path existiert nicht: {project_path}")

    context = {
        "project_path": project_path,
        "files": request.files or []
    }

    results = await bureau.run_review_specialists(context)

    return {
        "results": [
            {
                "success": r.success,
                "findings_count": len(r.findings),
                "summary": r.summary,
                "duration_ms": r.duration_ms,
                "error": r.error
            }
            for r in results
        ],
        "total_findings": sum(len(r.findings) for r in results)
    }
