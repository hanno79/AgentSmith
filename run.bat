@echo off
echo Starting Multi-Agent System (v3.1)...
.\venv\Scripts\python.exe main.py
if %errorlevel% neq 0 (
    echo.
    echo ---------------------------------------------------------------------
    echo ERROR: Application exited with code %errorlevel%.
    echo Please check the error message above.
    echo ---------------------------------------------------------------------
    pause
)
pause
