# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 29.01.2026
Version: 1.0
Beschreibung: Security-Endpoints für Deploy Patches und Status.
"""
# ÄNDERUNG 29.01.2026: Security-Endpunkte in eigenes Router-Modul verschoben

from fastapi import APIRouter, HTTPException, Request
from ..app_state import manager, limiter

router = APIRouter()


@router.post("/security-feedback")
@limiter.limit("60/minute")
def trigger_security_fix(request: Request):
    """
    Markiert Security-Issues als 'must fix' für die nächste Coder-Iteration.
    Wird vom 'Deploy Patches' Button im Frontend aufgerufen.
    """
    try:
        manager.force_security_fix = True
        vulnerabilities_count = len(manager.security_vulnerabilities) if hasattr(manager, 'security_vulnerabilities') else 0
        return {
            "status": "ok",
            "message": f"Security-Fix aktiviert für {vulnerabilities_count} Vulnerabilities",
            "vulnerabilities_count": vulnerabilities_count
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/security-status")
def get_security_status():
    """Gibt den aktuellen Security-Status zurück."""
    try:
        return {
            "vulnerabilities": manager.security_vulnerabilities if hasattr(manager, 'security_vulnerabilities') else [],
            "force_security_fix": manager.force_security_fix if hasattr(manager, 'force_security_fix') else False,
            "count": len(manager.security_vulnerabilities) if hasattr(manager, 'security_vulnerabilities') else 0
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
