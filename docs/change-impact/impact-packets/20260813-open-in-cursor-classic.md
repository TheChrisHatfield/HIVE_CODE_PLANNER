# Impact packet — Open in Cursor classic launch

**Date:** 2026-08-13  
**Hook:** `change.impact`  
**Change:** Cursor 3.x Open in Cursor opens editor workspace (`--classic` + CLI)

## Primary
- `src/hive_planner/launcher/service.py` — `open_in_cursor`, `resolve_cursor_cli_launch`
- `src/hive_planner/launcher/app.py` — `_on_open_cursor` / `_resolve_open_cursor_target`

## Secondary
- `tests/test_launcher.py` — launch argv and Open target resolution

## Tertiary
- Launcher Home/Projects “Open in Cursor” button

## Notes
- Linked `.code-workspace` paths open the workspace file itself with `--classic` (do not demote to primary folder).
- Projects tab Open prefers list selection; Home Open uses active project.

## Tests
- `tests/test_launcher.py` (`test_open_in_cursor_*`, `test_open_cursor_*`, `test_resolve_cursor_cli_launch_*`)
