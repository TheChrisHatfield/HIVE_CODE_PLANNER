# Impact packet — implementation-loop T028

**Date:** 2026-10-26  
**Hook:** `spec.flow`, `change.impact`, `change.validation`  
**Task:** Python checker infrastructure (`check` / Home Loop check)

## Primary

- `src/hive_planner/implementation_loop.py` — `coordinator_check`
- `src/hive_planner/cli.py` — `implementation-loop check`
- `src/hive_planner/launcher/service.py` / `app.py` — Home **Loop check**
- `docs/specs/implementation-loop/{spec,plan,tasks}.md`

## Tests

- `tests/test_implementation_loop_coordinator.py`
- `tests/test_implementation_loop.py`
- `tests/test_launcher.py`

## Secondary

- Reviewer and coder stay Cursor passes
- Bug hunt unchanged
- `wiring-audit check` runs only when that project enforces the audit

## Out of scope

- Python as coder or reviewer
- Merge/deploy
