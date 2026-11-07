# Impact packet — Bug-hunt R11 recovery controller

**Date:** 2026-11-07  
**Hook:** `change.bugfix_mode`, `integration.wiring_audit`, `change.validation`

## Primary

- `src/hive_planner/bug_hunt.py` — confidence-weighted empty votes, recovery exclusions, lens metadata, and queue handoff
- `src/hive_planner/bug_hunt_continue.py` — validated atomic recovery state, threshold transition, reset/stop handling, and append-before-state-write ordering

## Secondary

- `tests/test_bug_hunt.py` — integrated stop-hook recovery path and confidence learning
- `.cursor/commands/bug-hunt.md`
- `scripts/bug-hunt.md`
- `.hive/bug-hunt/AGENT_PROMPT.md`
- `.cursor/hooks/bug_hunt_continue.py`

## Wiring

The stop hook consumes `continue.json`, appends the selected `rank-pass.json`
outcome through `bug_hunt.py`, persists `recovery.json`, then rebuilds the
queue. Recovery excludes the inspected location, prefers another qualifying
folder, rotates the six bounded lenses, and stops on the ceiling, exhaustion,
three recovery-empty passes, or state-write failure.

## Validation

- `py -3.11 -m pytest tests/test_bug_hunt.py -q` — 253 passed
- `py -3.11 -m hive_planner spec-drift-check --feature bug-hunt` — ok
- IDE lints — no errors
