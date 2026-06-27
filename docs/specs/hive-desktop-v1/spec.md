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

First-run wizard; then Home (ci-check, map sync), Projects (init + recent), Settings (paths, install).

### R4 — Windows launcher

`scripts/HivePlanner.bat` verifies Python, installs editable package if needed, starts native app.

### R5 — Stdlib only

tkinter + existing `hive_planner` APIs; no FastAPI, Electron, or Pyloid.
