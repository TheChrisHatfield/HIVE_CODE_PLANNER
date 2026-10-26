# Impact packet — Implementation loop T020

**Date:** 2026-10-26  
**Hook:** `change.impact`, `spec.flow`, `change.validation`  
**Change:** Close deploy gaps: spec implemented, `gh pr create` + `pr_url`, five-feature proposal stub, `baseline_dirty` in the state table.

## Primary

- `src/hive_planner/implementation_loop.py`
- `tests/test_implementation_loop_coordinator.py`
- `docs/specs/implementation-loop/{spec,plan,tasks}.md`
- `docs/delta/20_micro/implementation-loop.md`
- `AGENTS.md` active feature (operational)

## Secondary

- Installed command/rule/coordinator after reinstall
- `docs/change-impact/test-map.md`

## Tertiary

- Cursor coder/checker/reviewer still agent passes
- Merge to `main` and remote push remain human steps

## Tests

- `tests/test_implementation_loop.py`
- `tests/test_implementation_loop_coordinator.py`
