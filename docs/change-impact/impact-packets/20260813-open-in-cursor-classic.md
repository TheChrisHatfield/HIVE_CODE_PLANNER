# Impact packet — Open in Cursor classic launch

**Date:** 2026-08-13  
**Hook:** `change.impact`  
**Change:** Cursor 3.x Open in Cursor opens editor workspace (`--classic` + CLI) + wiring fixes

## Primary
- `src/hive_planner/launcher/service.py` — `open_in_cursor`, `resolve_cursor_cli_launch`, `_cursor_launch_prefix_error`
- `src/hive_planner/launcher/app.py` — `_on_open_cursor`, `_resolve_open_cursor_target`, `_show_workspace_picker(open_after_link=)`

## Secondary
- `tests/test_launcher.py` — launch argv, Open target resolution, false-success guards

## Tertiary
- Launcher Home/Projects “Open in Cursor” button

## Fix ledger
1. Launch via cli.js + `--classic` (Cursor 3.x Agents/Glass bypass)
2. Projects list selection honored on Open
3. Home Open uses active (not Projects highlight)
4. Linked `.code-workspace` opens as workspace file (not demoted folder)
5. Open-after-link when prompted to add a workspace
6. `cursor.cmd` fallback via `cmd.exe /c`
7. Activate-on-Open does not `load_config()` (preserves unsaved Settings)
8. Reject missing launch exe/cli.js before reporting success

## Tests
- `tests/test_launcher.py` (`-k "open_in_cursor or open_cursor or resolve_cursor_cli"`) — 14+ related passed
