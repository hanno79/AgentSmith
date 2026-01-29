@echo off
REM ===================================================================
REM Author: rahn
REM Datum: 25.01.2026
REM Version: 1.1
REM Beschreibung: Startet Backend und Frontend Services.
REM               AENDERUNG 25.01.2026: Auto-Stop vor Neustart.
REM ===================================================================
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
setlocal
echo ===================================================
echo   AGENT OFFICE MISSION CONTROL
echo ===================================================
echo.

REM Zuerst bestehende Prozesse stoppen (falls vorhanden)
echo [0/2] Cleaning up existing processes...
if exist "stop_office.bat" (
    call stop_office.bat >nul 2>&1
)
timeout /t 2 /nobreak >nul

echo [1/2] Starting Backend (FastAPI)...
REM ÄNDERUNG 29.01.2026: --reload entfernt um Worktree-Pfad-Probleme zu vermeiden
start cmd /k ".\venv\Scripts\python.exe -m uvicorn backend.api:app --host 0.0.0.0 --port 8000"

echo [2/2] Starting Frontend (React)...
cd frontend
start "Frontend" cmd /k ""C:\Program Files\nodejs\npm.cmd" run dev"

echo.
echo ---------------------------------------------------
echo  Frontend: http://localhost:5173
echo  Backend:  http://localhost:8000/docs
echo ---------------------------------------------------
echo.
echo  To stop all services, run: stop_office.bat
echo.
pause
