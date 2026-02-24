@echo off
REM ===================================================================
REM Author: rahn
REM Datum: 22.02.2026
REM Version: 2.0
REM Beschreibung: Startet AgentSmith via Docker Compose.
REM               AENDERUNG 22.02.2026: Fix 62 - Umstellung auf Docker Compose.
REM               Vorher: uvicorn direkt + npm run dev auf Windows-Host.
REM               Jetzt: docker compose up -d (Backend + Frontend im Container).
REM ===================================================================
chcp 65001 >nul

echo ===================================================
echo   AGENT OFFICE MISSION CONTROL (Docker)
echo ===================================================
echo.

REM crew_log.jsonl muss existieren fuer Volume-Mount in docker-compose.yml
if not exist crew_log.jsonl type nul > crew_log.jsonl

echo Starte AgentSmith via Docker Compose...
docker compose up -d
if %ERRORLEVEL% neq 0 (
    echo.
    echo FEHLER: docker compose up fehlgeschlagen!
    echo Pruefe ob Docker Desktop laeuft und docker-compose.yml vorhanden ist.
    exit /b 1
)

echo.
echo ---------------------------------------------------
echo   AgentSmith gestartet:
echo   Frontend: http://localhost:5173
echo   Backend:  http://localhost:8000/docs
echo ---------------------------------------------------
echo.
echo   Logs anzeigen:  docker compose logs -f backend
echo   Status:         docker compose ps
echo   Stoppen:        stop_office.bat
echo.
