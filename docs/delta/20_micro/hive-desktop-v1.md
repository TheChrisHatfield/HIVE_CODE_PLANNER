# Micro: hive-desktop-v1

**Hook:** `workflow.tools`, `workflow.project_bootstrap`  
**Status:** active (Stage 9A)

## What

Native desktop app for Hive Planner (tkinter) — cream/emerald palette borrowed from KOKORO VoiceFlow / `tts_overlay_unified.py`. No browser, no HTTP server.

## Commands

```powershell
scripts\HivePlanner.bat
py -3.11 -m hive_planner.launcher
```

Config: `%APPDATA%\HivePlanner\config.json`

## UI

- First-run onboarding wizard (4 steps)
- Tabbed dashboard: Home, Projects, Settings
- Native folder picker (`Browse…`)
- Background threads for install / ci-check (UI stays responsive)

## Out of scope (v1)

PyInstaller EXE, Pyloid/React shell, system tray.
