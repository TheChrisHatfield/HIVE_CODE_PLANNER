# Plan: roadmap-complete-v4

**Spec:** [spec.md](./spec.md)

<!-- ROSETTA-NAV -->

## Agent navigation (Rosetta Stone)

Load [`docs/planning-rosetta-stone.md`](../../planning-rosetta-stone.md) (`planning.rosetta`) before editing this plan.

- **Spec:** [`spec.md`](./spec.md)
- **Delta micro:** [`roadmap-complete-v4.md`](../../delta/20_micro/roadmap-complete-v4.md)
- **Hooks:** `spec.flow`, `context.delta`

## Approach

1. Extend `ROADMAP_FEATURES` with `unified-handoff-v2` and `roadmap-complete-v4`.
2. Bump `pyproject.toml` version to v1.3.0.
3. Sync README, ARCHITECTURE, AGENTS, and STAGE_ROADMAP for Stage 9 closure.
4. Mark unified-handoff-v2 tasks complete; validation gate via `roadmap-status` + `ci-check`.

## Module map

| Module | Change |
|--------|--------|
| `roadmap_status.py` | Add Stage 9 feature ids |
| `docs/delta/STAGE_ROADMAP.md` | Stage 9 complete |
| `docs/specs/unified-handoff-v2/tasks.md` | All tasks ✅ |

## Validation

```powershell
py -3.11 -m hive_planner roadmap-status
py -3.11 -m hive_planner ci-check --skip-pytest
py -3.11 -m pytest -q
```
