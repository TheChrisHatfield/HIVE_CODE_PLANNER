# Impact packet: popup window position

**Date:** 2026-10-27  
**Hook:** `change.impact`, `workflow.tools`  
**Spec:** `docs/specs/hive-desktop-v1/spec.md` (R7)

## Change

Hive Planner dialogs reopen at the last screen position for that dialog title, including a position on another monitor. Add workspace link and every other `_dialog` window share this path. `simpledialog` prompts get it from the same class binding. Hover tooltips are skipped.

## Effects

- Primary: `src/hive_planner/launcher/popup_placement.py`, `src/hive_planner/launcher/app.py` (`_dialog`, app init)
- Secondary: hive-desktop spec and micro delta
- Persistence: `%APPDATA%\HivePlanner\popup-placements.json` (separate from `config.json`)
- Tests: `tests/test_popup_placement.py`

## Validation

`py -3.11 -m pytest tests/test_popup_placement.py -q`
