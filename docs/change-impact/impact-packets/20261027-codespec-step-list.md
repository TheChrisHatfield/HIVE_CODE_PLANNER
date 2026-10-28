# Impact packet — CodeSpec step list

**Date:** 2026-10-27  
**Spec:** `docs/specs/hive-desktop-v1/spec.md` R3, `docs/specs/implementation-loop/spec.md` R9–R10

## Change

The CodeSpec block no longer has a role picker. Handoff and Accept take the role for the current step. The block lists the pack order and marks waiting, now, done, or stopped. Pack at Enable is unchanged. Bug hunt and Agnostic loop settings are unchanged.

## Primary

- `src/hive_planner/launcher/app.py` — CodeSpec step list; Handoff/Accept call `codespec_role_for`
- `src/hive_planner/implementation_loop.py` — step list, inferred role; pack allowlist on handoff/accept removed

## Secondary

- `docs/specs/hive-desktop-v1/spec.md`, `docs/specs/implementation-loop/spec.md`
- `docs/delta/20_micro/hive-desktop-v1.md`, `docs/delta/20_micro/implementation-loop.md`
- `scripts/README.md`, `src/hive_planner/launcher/user_guide.py`

## Tests

- `tests/test_implementation_loop_coordinator.py` — step marks and role inference
- `tests/test_launcher.py` — CodeSpec settings omit `role`
