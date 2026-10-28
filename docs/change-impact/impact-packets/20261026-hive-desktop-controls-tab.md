# Impact packet — Hive desktop Controls tab

**Date:** 2026-10-26  
**Spec:** `docs/specs/hive-desktop-v1/spec.md` R3; also bug-hunt / implementation-loop / agnostic-loop Home duality

## Change

Home shows one **Loop controls** button (opens Controls). Controls is one loop picker, one command picker, and one **Run** that calls the same launcher service functions as the CLI on the active linked repo.

## Primary

- `src/hive_planner/launcher/app.py` — Home **Loop controls**; Controls `_on_controls_run`
- `src/hive_planner/launcher/service.py` — peek + agnostic gate wrappers

## Secondary

- `src/hive_planner/launcher/user_guide.py`, `scripts/README.md`, `START_HERE.md`
- `docs/specs/hive-desktop-v1/spec.md`, `docs/delta/20_micro/hive-desktop-v1.md`
- `docs/specs/bug-hunt/spec.md`, `docs/specs/implementation-loop/spec.md`, `docs/specs/agnostic-loop/spec.md`
- `tests/test_launcher.py`

## Tests

- `tests/test_launcher.py` — peek/install/gates against a temp repo; Controls tab + Loop controls + `_on_controls_run` registered in app source
