@echo off
REM Launch Hive Planner with no console window (delegates to VBS + pythonw)
REM For a custom icon, use HivePlanner.lnk or run CreateHivePlannerShortcut.ps1
cd /d "%~dp0"
wscript //B "%~dp0HivePlanner.vbs"
