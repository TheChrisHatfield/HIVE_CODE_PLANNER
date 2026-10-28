# Impact packet — Controls loop blocks

**Date:** 2026-10-27  
**Spec:** `docs/specs/hive-desktop-v1/spec.md` Controls

## Change

Controls can hold more than one loop block. **+** adds a block, **−** cannot remove the last one. Each block has its own loop, command, Run, and settings. The spec-task loop is labeled **CodeSpec**. Settings shown are the gates that loop already has: bug hunt fix ceiling; CodeSpec pack, feature, role, and start/handoff flags; agnostic reward, cycles, review, open counts, sims, horizon, seed, and arm-after-choose. Choose passes sims, horizon, and seed through the existing chooser. Defaults match the previous call (64, 4, no seed).

## Primary

- `src/hive_planner/launcher/app.py`
- `src/hive_planner/launcher/service.py` (`run_project_agnostic_loop_choose` optional sims/horizon/seed)

## Secondary

- `scripts/README.md`, `src/hive_planner/launcher/user_guide.py`
- `docs/specs/hive-desktop-v1/spec.md`, `docs/delta/20_micro/hive-desktop-v1.md`

## Tests

- `tests/test_launcher.py` — command pairing, per-loop settings, last-block guard
