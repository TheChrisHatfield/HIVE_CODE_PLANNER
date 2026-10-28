# Impact packet: Projects linked-workspace split

**Date:** 2026-10-27  
**Hook:** `change.impact`, `workflow.tools`  
**Spec:** `docs/specs/hive-desktop-v1/spec.md` (R3)

## Change

Projects tab uses a vertical `PanedWindow`. Dragging the sash resizes the Linked workspaces list. Add link… and Set as active stay on the lower pane. The list still scrolls when there are more rows than the pane shows.

## Effects

- Primary: `src/hive_planner/launcher/app.py` (`_build_projects_tab`, scrollbar sync)
- Secondary: hive-desktop spec and micro delta
- Tests: `tests/test_launcher.py` sash math and source wiring

## Validation

`py -3.11 -m pytest tests/test_launcher.py -q -k "recent_scrollbar or projects_split"`
