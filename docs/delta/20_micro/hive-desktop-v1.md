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
- Tabbed dashboard: Home, Controls, Projects, Settings
- Home **Loop controls** opens the Controls tab (no separate Enable/Loop status rows on Home)
- Home **CodeSpec** opens that same tab and ensures a CodeSpec block is present
- Home command buttons sit in titled groups (Project, Loops, Sources, Memory, Setup). **Arrange groups** (Home or Settings) lets the user rename headings and move groups or buttons; the layout is stored in `config.json`
- Controls tab: one or more loop blocks (＋ adds, − removes, the last block stays). Each block has its own loop, command, Run, and settings. **＋** adds a collapsed block; **Install CodeSpec** targets the Cursor window in front then Enable; typing **code spec** in Loop selects CodeSpec; ▾/▸ hides fields while Loop, Command, and Run stay. The heading lists a one-line summary of each loop: Bug hunt, CodeSpec, and Agnostic loop. Hover text on each button, command, and setting says what it does in one plain sentence, and the Command tip follows the selected command. A CodeSpec block lists that pack's steps and marks the one that is running or stopped. It does not ask for a role. All blocks run on the active linked repo
- Projects: a drag sash resizes the Linked workspaces list. Add link… and Set as active stay on that pane
- Native folder picker (`Browse…`)
- Dialog windows reopen at the last position for that dialog title, including another monitor (`popup-placements.json`). With no usable saved position they open centered on the main window. A position on a disconnected monitor is skipped. Hover tooltips stay beside the pointer
- Background threads for install / ci-check (UI stays responsive)
- Settings **Agent MCP**: Enable/Disable writes `hive-planner` into the active project's `.cursor/mcp.json` so a Cursor agent can call this Hive Planner (`mcp-serve` stdio JSON-RPC)

## Out of scope (v1)

PyInstaller EXE, Pyloid/React shell, system tray.
