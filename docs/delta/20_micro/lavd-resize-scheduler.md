# Feature Micro Brief: lavd-resize-scheduler

**Hook:** `spec.flow`, `change.validation`, `integration.wiring_audit`  
**Status:** draft

<!-- ROSETTA-NAV -->

## Agent navigation (Rosetta Stone)

Load [`docs/planning-rosetta-stone.md`](../../planning-rosetta-stone.md) (`planning.rosetta`) before coding from this brief.

- **Hooks:** `spec.flow`, `change.validation`, `integration.wiring_audit`
- **Spec Kit:** [`spec.md`](../../specs/lavd-resize-scheduler/spec.md), [`plan.md`](../../specs/lavd-resize-scheduler/plan.md), [`tasks.md`](../../specs/lavd-resize-scheduler/tasks.md)

## Feature Name

LAVD resize scheduler — virtual deadlines plus Thompson sampling for resize units.

## Scope

| In scope | Out of scope |
|----------|--------------|
| Four unit kinds with fixed latency sensitivity | Editing launcher `<Configure>` handlers |
| Virtual deadline from sensitivity | Linux sched_ext / `scx_lavd` |
| Chunk plan and Thompson order for optional units | Android |
| Beta update from observed hitch cost | Persisting posteriors |

**Files:** `src/hive_planner/lavd_resize.py`, `tests/test_lavd_resize.py`

## Acceptance Criteria

- [ ] One pending unit per kind; a repeat enqueue keeps the earlier deadline
- [ ] Due units run first, even when they exceed the chunk budget
- [ ] Optional units follow a seeded Thompson draw and stop when the budget is spent
- [ ] Hitch above the limit increments beta for the kinds that ran; a clean chunk increments alpha

## Validation

```powershell
py -3.11 -m pytest tests/test_lavd_resize.py -v
py -3.11 -m hive_planner spec-drift-check --feature lavd-resize-scheduler
```
