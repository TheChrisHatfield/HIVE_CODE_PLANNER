# Impact packet — Implementation loop spec

**Date:** 2026-10-25  
**Hook:** `change.impact`, `spec.flow`, `integration.cl_spec`  
**Change:** Specify the post-spec coding loop. Docs only; no `src/` behavior yet.

## Primary

- `docs/specs/implementation-loop/spec.md` — execution stage after Spec Kit
- `docs/specs/implementation-loop/plan.md` — install and readiness approach
- `docs/specs/implementation-loop/tasks.md` — implementation sequence
- `docs/delta/20_micro/implementation-loop.md` — micro brief

## Secondary

- `docs/delta/10_macro.md` — workflow step after tasks exist
- Future `src/hive_planner/implementation_loop.py` and `tests/test_implementation_loop.py`
- Future CLI, optional bootstrap flag, and Home enable

## Tertiary

- Bootstrapped projects gain the loop only when a pack is chosen
- `AGENTS.md` stays the operational memory file; this spec does not add bullets
- Bug hunt and unified handoff stay installed as they are

## Tests

- None for this docs change
- Planned: `tests/test_implementation_loop.py` when T002 starts

## Risks

- Active feature in `AGENTS.md` remains `roadmap-complete-v4`. This spec is draft until implementation tasks begin.
- Macro workflow text now names a loop the CLI does not install yet.
