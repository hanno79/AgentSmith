# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 31.01.2026
Version: 1.6
Beschreibung: FastAPI Backend - REST API und WebSocket-Endpunkte für das Multi-Agent System.
              ÄNDERUNG 29.01.2026: API in Router-Module aufgeteilt.
              ÄNDERUNG 31.01.2026: Dependency-Check beim Server-Start.
              ÄNDERUNG 31.01.2026: Automatischer Health-Check und periodischer Re-Check.
"""
# ÄNDERUNG 29.01.2026: Router-Registrierung ausgelagert und File-Size reduziert
# ÄNDERUNG [31.01.2026]: Dependency-Check ohne Auto-Install in Produktion

import os
import logging
import asyncio
from contextlib import asynccontextmanager

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

# AENDERUNG 31.01.2026: Import fuer Health-Check
from model_router import get_model_router
from .app_state import manager

# AENDERUNG 31.01.2026: Background-Task fuer periodischen Re-Check
_health_check_task = None


async def _periodic_health_recheck():
    """Periodischer Re-Check aller unavailable Modelle (alle 10 Minuten)."""
    while True:
        try:
            await asyncio.sleep(600)  # 10 Minuten warten
            router = get_model_router(manager.config)
            if router.permanently_unavailable:
                logging.info(f"Periodischer Re-Check: Pruefe {len(router.permanently_unavailable)} unavailable Modelle...")
                results = await router.recheck_unavailable_models()
                reactivated = [m for m, r in results.items() if r]
                if reactivated:
                    logging.info(f"Re-Check: {len(reactivated)} Modelle reaktiviert: {reactivated}")
        except asyncio.CancelledError:
            logging.info("Periodischer Health-Check Task beendet")
            break
        except Exception as e:
            logging.warning(f"Fehler beim periodischen Re-Check: {e}")


async def _initial_health_check():
    """Non-blocking initialer Health-Check im Hintergrund."""
    # AENDERUNG 02.02.2026: Kurze Verzoegerung damit Server zuerst startet
    await asyncio.sleep(2)
    try:
        logging.info("Background: Fuehre initialen Health-Check durch...")
        router = get_model_router(manager.config)
        results = await router.health_check_all_primary_models()
        unavailable = [r for r, info in results.items() if not info.get("available", True)]
        if unavailable:
            logging.warning(f"Health-Check: {len(unavailable)} Modelle nicht verfuegbar: {unavailable}")
        else:
            logging.info(f"Health-Check: Alle {len(results)} Primary-Modelle verfuegbar")
    except Exception as e:
        logging.warning(f"Initialer Health-Check fehlgeschlagen: {e}")


# Background-Task fuer initialen Health-Check
_initial_health_task = None


@asynccontextmanager
async def lifespan(app):
    """Lifespan Context Manager fuer Startup und Shutdown."""
    global _health_check_task, _initial_health_task
    # AENDERUNG 02.02.2026: Health-Check non-blocking im Hintergrund
    # Server startet sofort, Health-Check laeuft parallel
    logging.info("Startup: Server startet (Health-Check laeuft im Hintergrund)...")
    _initial_health_task = asyncio.create_task(_initial_health_check())

    # Starte periodischen Re-Check Task
    _health_check_task = asyncio.create_task(_periodic_health_recheck())
    logging.info("Periodischer Health-Check Task gestartet (alle 10 Minuten)")

    yield  # App laeuft

    # Shutdown: Tasks stoppen
    # AENDERUNG 02.02.2026: Auch initialen Health-Check Task stoppen
    for task in [_health_check_task, _initial_health_task]:
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
    logging.info("Shutdown: Health-Check Tasks gestoppt")


app = FastAPI(
    title="Agent Smith API",
    description="Backend API für das Multi-Agent System",
    version="1.0.0",
    lifespan=lifespan  # AENDERUNG 31.01.2026: Health-Check bei Startup/Shutdown
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
# AENDERUNG 06.02.2026: Health-Check Endpoints aus config.py ausgelagert (Regel 1)
from backend.routers import model_health
app.include_router(model_health.router)
app.include_router(security.router)
app.include_router(budget.router)
app.include_router(library.router)
app.include_router(external_bureau.router)
app.include_router(dependencies.router)
app.include_router(session.router)
app.include_router(discovery.router)
