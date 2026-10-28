# Impact packet — Controls loop collapse

**Date:** 2026-10-27  
**Spec:** `docs/specs/hive-desktop-v1/spec.md` Controls

## Change

Each Controls loop block can hide its settings. **+** adds a collapsed block. ▾/▸ toggles fields; Loop, Command, and Run stay. Home **CodeSpec** expands the CodeSpec block when it scrolls into view.

## Primary

- `src/hive_planner/launcher/app.py`

## Secondary

- `docs/specs/hive-desktop-v1/spec.md`, `docs/delta/20_micro/hive-desktop-v1.md`
- `scripts/README.md`

## Tests

- `tests/test_controls_collapse.py`
