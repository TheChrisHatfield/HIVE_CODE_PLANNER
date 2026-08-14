# Impact packet — Open in Cursor classic launch

**Date:** 2026-08-13  
**Hook:** `change.impact`  
**Change:** Cursor 3.x Open in Cursor opens editor workspace (`--classic` + CLI)

## Primary
- `src/hive_planner/launcher/service.py` — `open_in_cursor`, `resolve_cursor_cli_launch`

## Secondary
- `tests/test_launcher.py` — launch argv expectations

## Tertiary
- Launcher Home/Projects “Open in Cursor” button (no UI text change)

## Tests
- `tests/test_launcher.py` (`test_open_in_cursor_*`, `test_resolve_cursor_cli_launch_*`)
