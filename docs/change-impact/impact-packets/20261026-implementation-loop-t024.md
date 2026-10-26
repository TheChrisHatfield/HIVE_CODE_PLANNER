# Impact packet — Implementation loop T024

**Date:** 2026-10-26  
**Hook:** `change.impact`, `spec.flow`, `change.validation`  
**Change:** Leftover coordinator gates after T023.

## Primary

- `src/hive_planner/implementation_loop.py` — checker-after-coder, accept next_role, test:full FileNotFoundError, blocked start, detached HEAD, posix shlex
- `src/hive_planner/cli.py` — `--force-feature` help
- `tests/test_implementation_loop_coordinator.py`
- `docs/specs/implementation-loop/spec.md` R10

## Secondary

- Re-start after slice `test:full` failure now requires `--force-feature`

## Tests

- `tests/test_implementation_loop_coordinator.py`

## Risks

- In-progress loops that skipped checker after recode will now block reviewer until a new checker pass
