# Impact packet: bug-hunt pause between inference passes

**Date:** 2026-10-27
**Feature:** bug-hunt
**Hook:** `change.bugfix_mode`, `change.impact`

## Change

Each bug-hunt iteration is one inference pass. Enable writes the pause into the script.

- Blank or omitted pause: 10 seconds, not skippable.
- `0`: no wait between passes.
- Any positive whole number: that many seconds, not skippable.

Stop conditions stay: committed-fix ceiling, two consecutive empty searches, no qualifying location.

## Files

- `src/hive_planner/bug_hunt.py` — `parse_pause_seconds`, prompt, install
- `src/hive_planner/cli.py` — `--pause-seconds`
- `src/hive_planner/launcher/app.py` — Bug hunt **Pause seconds**
- `src/hive_planner/launcher/service.py` — `run_project_bug_hunt_install(..., pause_seconds=)`
- `docs/specs/bug-hunt/spec.md`, `docs/delta/20_micro/bug-hunt.md`

## Tests

`tests/test_bug_hunt.py`, `tests/test_launcher.py` (controls settings, pause field, install text).

## Wiring

Controls Pause seconds → `_controls_bug_hunt_pause` → `run_project_bug_hunt_install` → `install_bug_hunt` → command, rule, packet, `scripts/bug-hunt.md`.
