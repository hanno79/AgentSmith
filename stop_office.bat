@echo off
REM ===================================================================
REM Author: rahn
REM Datum: 22.02.2026
REM Version: 2.0
REM Beschreibung: Stoppt AgentSmith Docker Container sauber.
REM               AENDERUNG 22.02.2026: Fix 62 - Umstellung auf Docker Compose.
REM               Vorher: taskkill auf Ports 8000 + 5173.
REM               Jetzt: docker compose down (alle Container gestoppt).
REM ===================================================================
chcp 65001 >nul

echo ===================================================
echo   AGENT OFFICE - SHUTDOWN (Docker)
echo ===================================================
echo.

echo Stoppe AgentSmith Docker Container...
docker compose down

echo.
echo ---------------------------------------------------
echo   AgentSmith gestoppt.
echo ---------------------------------------------------
echo.
