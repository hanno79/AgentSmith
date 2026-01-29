# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 29.01.2026
Version: 1.4
Beschreibung: FastAPI Backend - REST API und WebSocket-Endpunkte für das Multi-Agent System.
              ÄNDERUNG 29.01.2026: API in Router-Module aufgeteilt.
"""
# ÄNDERUNG 29.01.2026: Router-Registrierung ausgelagert und File-Size reduziert

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
