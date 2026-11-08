# Tasks: lavd-resize-scheduler

<!-- ROSETTA-NAV -->

Load [`docs/planning-rosetta-stone.md`](../../planning-rosetta-stone.md) (`planning.rosetta`) before executing tasks.

- **Spec:** [`spec.md`](./spec.md)
- **Plan:** [`plan.md`](./plan.md)
- **Delta micro:** [`lavd-resize-scheduler.md`](../../delta/20_micro/lavd-resize-scheduler.md)

## Phase 1 — Spec records

- [x] T001 Write spec, plan, tasks, and Delta micro for the four resize units

## Phase 2 — Scheduler

- [x] T002 Implement `ResizeScheduler` in `src/hive_planner/lavd_resize.py` and `tests/test_lavd_resize.py` per spec R1–R4

## Phase 3 — Launcher

- [x] T003 Route canvas, sash, wrap, and scrollbar work through `ResizeScheduler`. Default budget is one unit. `observe` takes one hitch per kind.

## Active task

**T003** — launcher pump and per-kind hitch attribution.

## After each implementation task — Integration wiring audit

- [x] Traced Configure handler → `_resize_put` → `plan_chunk` → payload → `observe`
- [x] A chunk that runs one kind does not report success for the kinds still queued
- [x] Integration-level validation: scheduler tests plus launcher canvas tick and wrap harness
- [x] See `.cursor/rules/integration-wiring-audit.mdc`

## Validation log

```text
2026-10-28 — spec written
- docs/specs/lavd-resize-scheduler/
- docs/delta/20_micro/lavd-resize-scheduler.md

2026-11-01 — T003 wired the scheduler into the launcher
- default budget 4 ms holds not-due kinds
- observe updates each ran kind from its own hitch
- canvas, sash, wrap, and scrollbar enqueue through one deadline pump
```
