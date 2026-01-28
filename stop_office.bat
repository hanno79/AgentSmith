@echo off
REM ===================================================================
REM Author: rahn
REM Datum: 25.01.2026
REM Version: 1.0
REM Beschreibung: Stoppt Backend und Frontend Services sauber.
REM ===================================================================
chcp 65001 >nul
echo ===================================================
echo   AGENT OFFICE - SHUTDOWN
echo ===================================================
echo.

echo [1/2] Stopping Backend (Port 8000)...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8000 ^| findstr LISTENING') do (
    echo      Stopping process %%a
    taskkill /PID %%a /F >nul 2>&1
)

echo [2/2] Stopping Frontend (Port 5173)...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :5173 ^| findstr LISTENING') do (
    echo      Stopping process %%a
    taskkill /PID %%a /F >nul 2>&1
)

echo.
echo ---------------------------------------------------
echo  All services stopped.
echo ---------------------------------------------------
