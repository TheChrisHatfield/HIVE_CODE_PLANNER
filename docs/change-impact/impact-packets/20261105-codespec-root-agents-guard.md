# Impact packet — CodeSpec root AGENTS.md commit guard

**Date:** 2026-11-05
**Hook:** `change.impact`, `spec.flow`, `change.validation`
**Change:** `coordinator_commit` blocks only a dirty repo-root `AGENTS.md`, not nested copies.

## Primary
- `src/hive_planner/implementation_loop.py` — `_is_repo_root_agents_md`, `coordinator_commit`
- `docs/specs/implementation-loop/spec.md` — R10 commit row

## Secondary
- `tests/test_implementation_loop_coordinator.py`

## Tertiary
- Untracked plugin `AGENTS.md` no longer blocks a product commit

## Tests
- `tests/test_implementation_loop_coordinator.py`
