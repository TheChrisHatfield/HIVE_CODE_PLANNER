# Plan: lavd-resize-scheduler

**Hook:** `spec.flow`, `change.validation`, `integration.wiring_audit`  
**Spec:** [spec.md](./spec.md)  
**Status:** draft

<!-- ROSETTA-NAV -->

Load [`docs/planning-rosetta-stone.md`](../../planning-rosetta-stone.md) (`planning.rosetta`) before editing this plan.

## Layer mapping

| Layer | Mapping |
|-------|---------|
| Holistic | Defer resize work that has been hitching; run latency-critical work on its virtual deadline |
| Macro | New library module. Launcher handlers stay as they are |
| Micro | `lavd_resize.py` queue, deadlines, Thompson chunk plan, Beta update |

## Approach

Implement `ResizeScheduler` as a pure Python object. Callers enqueue one of the four unit kinds, ask for the next chunk, run those units themselves, then report the hitch in milliseconds. The scheduler does not import Tk and does not bind `<Configure>`.

Virtual deadline uses the sensitivity table in the spec. Optional units inside the leftover budget are ordered by one Beta draw per pending kind (Thompson sampling). Hitch above 8 ms is a miss (beta); otherwise a hit (alpha).

## File targets

| File | Change |
|------|--------|
| `src/hive_planner/lavd_resize.py` | Scheduler |
| `tests/test_lavd_resize.py` | Deadline order, budget, seeded Thompson order, hitch update |

## Validation

```powershell
py -3.11 -m pytest tests/test_lavd_resize.py -v
py -3.11 -m hive_planner spec-drift-check --feature lavd-resize-scheduler
```
