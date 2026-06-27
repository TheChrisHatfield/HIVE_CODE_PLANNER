@echo off
REM Hive Planner native desktop app (tkinter — no browser)
echo ========================================
echo Hive Planner
echo ========================================
echo.

set SCRIPT_DIR=%~dp0
set HIVE_ROOT=%SCRIPT_DIR%..

cd /d "%HIVE_ROOT%"

py -3.11 --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python 3.11 not found. Install from https://python.org and retry.
    pause
    exit /b 1
)

py -3.11 -c "import hive_planner" >nul 2>&1
if errorlevel 1 (
    echo Installing hive-planner...
    py -3.11 -m pip install -e ".[dev]"
    if errorlevel 1 (
        echo ERROR: pip install failed.
        pause
        exit /b 1
    )
)

py -3.11 -m hive_planner.launcher
