# Impact packet: scrollbar sync failure is a posterior miss

**Date:** 2026-11-01
**Hook:** `change.validation`, `spec.flow`
**Spec:** `docs/specs/lavd-resize-scheduler/spec.md` (R4)

## Change

A failed Projects or recent-list scrollbar sync records the Tcl error and reports a hitch above the limit. The scrollbar posterior takes a miss instead of a clean success.

## Effects

- Primary: `src/hive_planner/launcher/app.py` (`_run_resize_chunk`, `_apply_projects_top_scroll`, `_sync_recent_scrollbar`)
- Tests: `tests/test_schedule_label_wrap.py`

## Validation

`py -3.11 -m pytest tests/test_schedule_label_wrap.py tests/test_lavd_resize.py -q`
