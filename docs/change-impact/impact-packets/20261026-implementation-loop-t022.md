# Impact packet — Implementation loop T022

**Date:** 2026-10-26  
**Hook:** `change.impact`, `spec.flow`, `change.validation`  
**Change:** Coordinator gap fixes from spec review.

## Primary

- `src/hive_planner/implementation_loop.py` — trunk refuse, current-task handoff, reviewer fail, needs-sign-off, Justfile/Taskfile, last_retrospective_n
- `tests/test_implementation_loop.py`, `tests/test_implementation_loop_coordinator.py`
- `docs/specs/implementation-loop/spec.md` R10 / state table

## Secondary

- Commit and push no longer possible on trunk after start
- Retrospective due uses last stub count, not `N % 5`

## Tests

- `tests/test_implementation_loop.py`
- `tests/test_implementation_loop_coordinator.py` (46 passed with install tests)

## Risks

- Existing `state.json` without `last_retrospective_n` loads as 0
