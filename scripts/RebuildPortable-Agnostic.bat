@echo off
REM ============================================================================
REM Hive Planner - agnostic one-click portable build (Windows)
REM
REM Works from any folder and any PC. It does not assume a drive letter,
REM a specific Python install, or Cursor. Steps:
REM   1. Find Python 3.10+ (py launcher first, then python on PATH).
REM   2. Create a private venv at build\portable-venv (gitignored).
REM   3. Hand off to scripts\build_portable.ps1 with that venv's python.
REM   4. Output: dist\HivePlannerPortable\HivePlanner.exe
REM ============================================================================
setlocal EnableExtensions
cd /d "%~dp0.."
set "REPO=%CD%"
set "VENV=%REPO%\build\portable-venv"
set "VPY=%VENV%\Scripts\python.exe"

if not exist "%REPO%\pyproject.toml" goto :notrepo
if not exist "%REPO%\scripts\build_portable.ps1" goto :notrepo

echo Hive Planner portable build
echo Repo: %REPO%
echo.

REM --- 1. Find a usable Python (3.10+) -------------------------------------
set "PY_CMD="
where py >nul 2>&1
if not errorlevel 1 (
    py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
    if not errorlevel 1 set "PY_CMD=py -3"
)
if not defined PY_CMD (
    where python >nul 2>&1
    if not errorlevel 1 (
        python -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
        if not errorlevel 1 set "PY_CMD=python"
    )
)
if not defined PY_CMD goto :nopython
echo Using Python: %PY_CMD%

REM --- 2. Private build venv (reused on later runs) ------------------------
if not exist "%VPY%" (
    echo Creating build venv at %VENV% ...
    %PY_CMD% -m venv "%VENV%"
    if errorlevel 1 goto :fail
)

echo Installing build dependencies (first run takes a few minutes)...
"%VPY%" -m pip install --quiet --upgrade pip
if errorlevel 1 goto :fail
"%VPY%" -m pip install --quiet -e "%REPO%[portable,pdf]"
if errorlevel 1 goto :fail

REM --- 3. Build with the venv python --------------------------------------
echo.
echo Running PyInstaller. This usually takes several minutes.
powershell -NoProfile -ExecutionPolicy Bypass -File "%REPO%\scripts\build_portable.ps1" -PythonExe "%VPY%"
if errorlevel 1 goto :fail

echo.
echo Build finished.
echo Output: %REPO%\dist\HivePlannerPortable\HivePlanner.exe
echo Zip the HivePlannerPortable folder to share it.
pause
exit /b 0

:notrepo
echo Could not find pyproject.toml and scripts\build_portable.ps1 next to this file.
echo Keep this file in the scripts folder of the Hive Planner repo.
pause
exit /b 1

:nopython
echo Python 3.10 or newer was not found.
echo Install it from https://www.python.org/downloads/ and tick "Add python.exe to PATH".
pause
exit /b 1

:fail
echo.
echo Portable build FAILED (exit code %ERRORLEVEL%). Scroll up for the first error.
pause
exit /b 1
