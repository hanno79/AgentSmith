# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 31.01.2026
Version: 1.5
Beschreibung: FastAPI Backend - REST API und WebSocket-Endpunkte für das Multi-Agent System.
              ÄNDERUNG 29.01.2026: API in Router-Module aufgeteilt.
              ÄNDERUNG 31.01.2026: Dependency-Check beim Server-Start.
"""
# ÄNDERUNG 29.01.2026: Router-Registrierung ausgelagert und File-Size reduziert
# ÄNDERUNG [31.01.2026]: Dependency-Check ohne Auto-Install in Produktion

import os
import logging

# Dependency-Check VOR allen anderen Imports (ausser logging)
# Auto-Install nur in DEV-Umgebungen aktivieren
def _is_dev_env() -> bool:
    env_value = (os.environ.get("ENV") or os.environ.get("NODE_ENV") or os.environ.get("APP_ENV") or "").lower()
    debug_value = os.environ.get("DEBUG", "").lower()
    return env_value in {"dev", "development", "local", "test"} or debug_value in {"1", "true", "yes"}

try:
    from .dependency_checker import check_and_install_dependencies
    _auto_install = _is_dev_env()
    _dep_result = check_and_install_dependencies(auto_install=_auto_install)
    if _dep_result["failed"]:
        logging.warning(f"Einige Dependencies konnten nicht installiert werden: {_dep_result['failed']}")
    if not _auto_install and _dep_result.get("missing"):
        logging.warning(f"Fehlende Dependencies (Auto-Install deaktiviert): {_dep_result['missing']}")
except Exception as e:
    logging.warning(f"Dependency-Check fehlgeschlagen: {e}")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler
from .middleware import SecurityHeadersMiddleware
from .app_state import limiter
from .routers import core, config, security, budget, library, external_bureau, dependencies, session, discovery

app = FastAPI(
    title="Agent Smith API",
    description="Backend API für das Multi-Agent System",
    version="1.0.0"
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(SecurityHeadersMiddleware)

app.include_router(core.router)
app.include_router(config.router)
app.include_router(security.router)
app.include_router(budget.router)
app.include_router(library.router)
app.include_router(external_bureau.router)
app.include_router(dependencies.router)
app.include_router(session.router)
app.include_router(discovery.router)
