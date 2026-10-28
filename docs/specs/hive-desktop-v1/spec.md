# Spec: hive-desktop-v1

**Hook:** `workflow.tools`, `workflow.project_bootstrap`  
**Delta:** [hive-desktop-v1.md](../../delta/20_micro/hive-desktop-v1.md)

## What

Self-contained native desktop window for Hive Planner workflows.

## Requirements

### R1 — Native GUI (no browser)

`hive_planner.launcher` opens a tkinter window. Must not require or open a web browser.

### R2 — VoiceFlow-inspired styling

Reuse KOKORO cream/emerald palette (`#faf8f5`, `#10b981`) and card layout patterns from `tts_overlay_unified.py`.

### R3 — Onboarding + dashboard

First-run wizard; then Home (ci-check, map sync, **Loop controls**, and a **CodeSpec** button, grouped under editable headings; **Arrange groups** moves groups and buttons), Controls (one or more loop blocks, each with its own Run, against the active repo; the spec-task loop is labeled CodeSpec; **+** adds a collapsed block; **Install CodeSpec** targets the Cursor window in front then Enable; typing **code spec** in Loop selects CodeSpec; ▾/▸ hides fields while Loop, Command, and Run stay), Projects (init + recent; the Linked workspaces list sits in a draggable split so it can be resized, with Add link… and Set as active staying on that pane), Settings (paths, install, Agent MCP enable, Arrange Home groups). Under the Controls heading, one plain-language line names each loop: Bug hunt finds and fixes bugs, CodeSpec codes a finished spec, and Agnostic loop picks the next small job. Hover text on Controls says what each button, command, and setting does in one plain sentence. The Command tip follows the command that is selected. Home **CodeSpec** opens Controls on a CodeSpec block. **Loop controls** still opens that same tab. The CodeSpec block has no role picker. A step list on that block shows the pack's order and marks each step waiting, now, done, or stopped. One-pack order is coordinator implements, check runs tests, review, commit. Four-pack order is coder, check, reviewer, coordinator commits. Handoff and Accept use the step the list is on. Pack is still chosen on Enable.

### R4 — Windows launcher

`scripts/HivePlanner.bat` verifies Python, installs editable package if needed, starts native app.

### R5 — Stdlib only

tkinter + existing `hive_planner` APIs; no FastAPI, Electron, or Pyloid.

### R6 — Agent MCP (control Hive Planner)

Hive Planner is a stdio MCP server (`mcp-serve`, Content-Length JSON-RPC, stdlib only — no `mcp` package). Tools wrap existing Hive APIs (health check, map sync, bug hunt, implementation loop, agnostic loop). No merge, deploy, or push tools.

Settings **Agent MCP → Enable** writes a `hive-planner` entry into the **active project's** `.cursor/mcp.json` (other servers kept). Disable marks that entry disabled. Cursor must reload MCP after Enable.

### R7 — Popup position

Every Hive Planner dialog window reopens where that dialog was last moved, including a position on another monitor. The spot is stored per dialog title in `%APPDATA%\HivePlanner\popup-placements.json`. A dialog with no usable saved position opens centered on the main window. A saved position that no longer sits on a connected monitor is skipped until the dialog is moved again. Hover tooltips stay beside the pointer. Windows message boxes and file pickers stay with the system placement.
