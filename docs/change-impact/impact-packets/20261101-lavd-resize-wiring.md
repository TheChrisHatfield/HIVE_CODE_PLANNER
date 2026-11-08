# Impact packet: LAVD resize scheduler wired into the launcher

**Date:** 2026-11-01
**Hook:** `change.impact`, `change.validation`, `spec.flow`
**Spec:** `docs/specs/lavd-resize-scheduler/spec.md` (R2, R4, Launcher)

## Change

The resize scheduler now runs from the Hive window. Canvas redraw, the Projects sash, label wrap, and scrollbar pack enqueue on `ResizeScheduler`. One timer wakes at the next virtual deadline. The default chunk budget is one unit, so the first chunk does not clear the queue. Each kind reports its own hitch.

## Effects

- Primary: `src/hive_planner/lavd_resize.py`, `src/hive_planner/launcher/app.py`
- Secondary: lavd spec, plan, tasks, and micro brief; controls-execute overlap note
- Tests: `tests/test_lavd_resize.py`, `tests/test_schedule_label_wrap.py`, `tests/test_launcher.py` (canvas tick and flush)

## Validation

```powershell
py -3.11 -m pytest tests/test_lavd_resize.py tests/test_schedule_label_wrap.py -q
py -3.11 -m pytest tests/test_launcher.py -q -k "scrollable_canvas or flush_scroll"
```
