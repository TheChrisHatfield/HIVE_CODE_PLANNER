@echo off
REM One-click portable rebuild: PyInstaller onedir -> dist\HivePlannerPortable
setlocal
cd /d "%~dp0.."
if not exist "scripts\build_portable.ps1" (
    echo Could not find scripts\build_portable.ps1
    echo Run this file from the Hive Planner repo.
    pause
    exit /b 1
)
echo Rebuilding Hive Planner portable...
echo Repo: %CD%
echo This usually takes several minutes.
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0build_portable.ps1"
set "ERR=%ERRORLEVEL%"
echo.
if not "%ERR%"=="0" (
    echo Rebuild failed. Exit code %ERR%.
    pause
    exit /b %ERR%
)
echo Rebuild finished.
echo Output: %CD%\dist\HivePlannerPortable\HivePlanner.exe
pause
exit /b 0
