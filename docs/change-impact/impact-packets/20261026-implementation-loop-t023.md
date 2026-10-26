# Impact packet — Implementation loop T023

**Date:** 2026-10-26  
**Hook:** `change.impact`, `spec.flow`, `change.validation`  
**Change:** Coordinator recovery after fail, missing `gh`, and failed commit/slice gates.

## Primary

- `src/hive_planner/implementation_loop.py` — fail-retry handoff, `_gh` missing binary, commit restore, delayed task advance, loop branch
- `tests/test_implementation_loop_coordinator.py`
- `docs/specs/implementation-loop/spec.md` R10
- `docs/specs/implementation-loop/tasks.md` T023

## Secondary

- Installed coordinator/command text after reinstall (prompts only)
- Slice-end `test:full` no longer marks `complete` or appends retrospective on failure

## Tests

- `tests/test_implementation_loop_coordinator.py`
- `tests/test_implementation_loop.py` (installed text)

## Risks

- Existing in-progress loops with reviewer `fail` already in `result.md` can now hand off checker after a new coder result
