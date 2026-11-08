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
| Macro | Launcher handlers enqueue the four kinds. One pump runs `plan_chunk` at the next virtual deadline |
| Micro | `lavd_resize.py` queue, deadlines, one-unit budget, per-kind Beta update |

## Approach

Implement `ResizeScheduler` as a pure Python object. The launcher enqueues one of the four unit kinds, the pump asks for the next chunk at that chunk's virtual deadline, runs the returned payloads, then reports each kind's hitch in milliseconds. The scheduler does not import Tk.

The default chunk budget equals one unit (4 ms). The earliest due unit runs. Anything else waits until a later chunk has room or its own deadline is the earliest due unit. Virtual deadline uses the sensitivity table in the spec. Optional units inside the leftover budget are ordered by one Beta draw per pending kind (Thompson sampling). A hitch above 8 ms is a miss (beta) for that kind only; otherwise a hit (alpha).

## File targets

| File | Change |
|------|--------|
| `src/hive_planner/lavd_resize.py` | Scheduler |
| `src/hive_planner/launcher/app.py` | Enqueue the four resize jobs and run the chunk pump |
| `tests/test_lavd_resize.py` | Default budget holds the queue, seeded Thompson order, per-kind hitch |
| `tests/test_schedule_label_wrap.py` | Wrap and the other three handlers wait on virtual deadlines |
| `tests/test_launcher.py` | Canvas width applies on the scheduler tick; flush still applies immediately |

## Validation

```powershell
py -3.11 -m pytest tests/test_lavd_resize.py tests/test_schedule_label_wrap.py -q
py -3.11 -m pytest tests/test_launcher.py -q -k "scrollable_canvas or flush_scroll"
py -3.11 -m hive_planner spec-drift-check --feature lavd-resize-scheduler
```
