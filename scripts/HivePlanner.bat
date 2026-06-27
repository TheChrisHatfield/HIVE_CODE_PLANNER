@echo off
REM Launch Hive Planner with no console window (delegates to VBS + pythonw)
cd /d "%~dp0"
wscript //B "%~dp0HivePlanner.vbs"
