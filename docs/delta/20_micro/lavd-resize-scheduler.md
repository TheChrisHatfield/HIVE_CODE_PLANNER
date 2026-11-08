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
| Four unit kinds with fixed latency sensitivity | Linux sched_ext / `scx_lavd` |
| Virtual deadline from sensitivity | Android |
| One-unit default chunk budget so deadlines hold not-due work | Persisting posteriors |
| Per-kind hitch update | |
| Launcher enqueue and one deadline pump | |

**Files:** `src/hive_planner/lavd_resize.py`, `src/hive_planner/launcher/app.py`, `tests/test_lavd_resize.py`, `tests/test_schedule_label_wrap.py`

## Acceptance Criteria

- [x] One pending unit per kind; a repeat enqueue keeps the earlier deadline
- [x] Default budget runs the earliest due unit and leaves the others queued
- [x] Optional units follow a seeded Thompson draw and stop when the budget is spent
- [x] Each kind that ran updates from its own hitch; a kind that did not run stays put
- [x] Launcher canvas, sash, wrap, and scrollbar jobs enqueue through the scheduler

## Validation

```powershell
py -3.11 -m pytest tests/test_lavd_resize.py tests/test_schedule_label_wrap.py -q
py -3.11 -m pytest tests/test_launcher.py -q -k "scrollable_canvas or flush_scroll"
py -3.11 -m hive_planner spec-drift-check --feature lavd-resize-scheduler
```
