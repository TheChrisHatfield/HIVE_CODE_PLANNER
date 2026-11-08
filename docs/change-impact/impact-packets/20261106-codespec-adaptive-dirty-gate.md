# Impact packet — CodeSpec adaptive dirty gate

**Date:** 2026-11-06  
**Hook:** `change.impact`, `spec.flow`, `change.validation`  
**Change:** Classify dirty paths by active-spec scope and deterministic confidence before CodeSpec start.

## Primary

- `src/hive_planner/implementation_loop.py`
- `src/hive_planner/launcher/app.py`
- `docs/specs/implementation-loop/spec.md`

## Secondary

- `tests/test_implementation_loop_coordinator.py`
- `tests/test_launcher.py`

## Behavior

- Feature-scoped paths always pass the scope gate.
- Documentation-only outside paths auto-start at medium confidence.
- Outside executable, test, configuration, hook, or package paths remain low confidence and require explicit approval.
- Baseline isolation continues to exclude pre-existing product files from the task commit.

## Validation

- Coordinator gate tests
- Controls summary test
- Implementation-loop spec drift
- Bug-hunt spec drift
- Linter and `git diff --check`
