@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
setlocal
echo ===================================================
echo   🤖 AGENT OFFICE MISSION CONTROL
echo ===================================================
echo.
echo [1/2] Starting Backend (FastAPI)...
start cmd /k ".\venv\Scripts\python.exe -m uvicorn backend.api:app --reload --port 8000"

echo [2/2] Starting Frontend (React)...
cd frontend
start "Frontend" cmd /k ""C:\Program Files\nodejs\npm.cmd" run dev"

echo.
echo ---------------------------------------------------
echo  Frontend: http://localhost:5173
echo  Backend:  http://localhost:8000/docs
echo ---------------------------------------------------
echo.
pause
