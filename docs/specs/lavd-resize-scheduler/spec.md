# Spec: lavd-resize-scheduler

**Hook:** `spec.flow`, `change.validation`, `integration.wiring_audit`  
**Status:** draft  
**Created:** 2026-10-28  
**Delta:** [lavd-resize-scheduler.md](../../delta/20_micro/lavd-resize-scheduler.md)

<!-- ROSETTA-NAV -->

## Agent navigation (Rosetta Stone)

1. [`docs/planning-rosetta-stone.md`](../../planning-rosetta-stone.md) — hook `planning.rosetta`
2. Follow **UNLOCKS**: `spec.flow`, `change.validation`
3. This feature — hook `spec.flow`:
   - **Feature id:** `lavd-resize-scheduler`
   - Delta micro: [`lavd-resize-scheduler.md`](../../delta/20_micro/lavd-resize-scheduler.md)
   - Plan: [`plan.md`](./plan.md)
   - Tasks: [`tasks.md`](./tasks.md)

## What

A library scheduler that smooths resize hitching, called by the launcher. Each resize-related task is one schedulable unit. The unit gets a virtual deadline from how latency-sensitive it is. Each short time chunk runs the earliest due unit, then fills any leftover budget with not-yet-due units chosen by Thompson sampling. The hitch cost of each kind is observed on its own.

The four units are the resize jobs in the launcher. Configure handlers enqueue a kind. They do not start their own `after` debounce. The scheduler's pump runs the chunk.

| Unit | Launcher job it stands for | Latency sensitivity |
|------|----------------------------|---------------------|
| `canvas_redraw` | Canvas width sync and scroll-region measure in `_scrollable_tab` | 1.00 |
| `split_reposition` | Projects sash place | 0.55 |
| `label_rewrap` | Hub and form `wraplength` updates | 0.35 |
| `scrollbar_pack` | Show or hide a scrollbar with `pack` / `pack_forget` | 0.15 |

Higher sensitivity means a tighter virtual deadline. `canvas_redraw` is due as soon as it is queued. `scrollbar_pack` can wait, because packing a scrollbar mid-drag is what retriggers layout.

## Layers

| Layer | This feature |
|-------|----------------|
| Holistic | A resize drag stays responsive by deferring work that has been hitching. |
| Macro | One scheduler module. The launcher enqueues the four resize jobs and runs each chunk from one deadline timer. |
| Micro | Queue, virtual deadline, one-unit default budget, per-kind hitch update. |

## Requirements

### R1 — One pending unit per kind

- The only kinds are `canvas_redraw`, `split_reposition`, `label_rewrap`, and `scrollbar_pack`.
- Enqueueing a kind that is already pending keeps the earlier deadline and replaces the payload.
- A kind that is not pending is stamped with `deadline_ms = now_ms + base_window_ms * (1 - sensitivity)`.
- `base_window_ms` defaults to 48. Sensitivity is the table above.
- `cancel` drops that kind. The launcher uses it when a wrap is too narrow to apply.

### R2 — Virtual deadline inside a chunk

- `plan_chunk(now_ms)` returns the units that run in this chunk.
- The earliest due unit (`deadline_ms <= now_ms`) runs even when its cost exceeds the chunk budget.
- Further due units run only while `unit_cost_ms` still fits. A late tick must not empty a queue of due units in one chunk.
- Units that are not due fill whatever budget remains, earliest Thompson draw first. With the default budget they do not fit after the one due unit, so the deadline holds them.

### R3 — Thompson sampling for optional units

- Each kind has a Beta posterior, prior Beta(1, 1), for the chance that running it stays under the hitch limit.
- Optional units are ordered by one draw from that kind's Beta, highest draw first. The draw uses an injectable random source so tests can fix the sequence.
- A unit runs only while `unit_cost_ms` still fits in the remaining budget. `unit_cost_ms` defaults to 4. The chunk budget defaults to 4, the same as one unit, so the first chunk of a full queue runs the one due unit and leaves the rest pending.
- Kinds with no pending unit are not sampled.

### R4 — Hitch observation

- `observe(hitches)` takes one measurement per kind. It updates only kinds returned by the last `plan_chunk` that are present in that mapping.
- Each kind is compared to `hitch_limit_ms` (default 8) on its own. A hitch at or below the limit increments that kind's alpha by 1. A hitch above the limit increments that kind's beta by 1.
- A kind that ran but is omitted from the mapping is left unchanged. A kind that did not run is ignored, even if the mapping names it.
- `observe` before any plan, or after a plan that ran nothing, changes no posterior.
- A second `observe` without a new plan changes nothing.

## Launcher

The four resize jobs enqueue through `ResizeScheduler` instead of their own `<Configure>` timers. One pump on the Hive window wakes at the next virtual deadline, runs that chunk, and records each kind's own duration as its hitch. Canvas scroll-restore still flushes immediately so a saved scroll position is not left waiting on the deadline.

| Unit | Launcher entry |
|------|----------------|
| `canvas_redraw` | `_bind_scrolling_canvas` |
| `split_reposition` | `_place_projects_split_once` |
| `label_rewrap` | `_schedule_label_wrap` |
| `scrollbar_pack` | `_sync_projects_top_scroll` and `_schedule_recent_scrollbar` |

## Overlap with another feature

Start and feature switch go through the implementation loop's file-overlap gate ([implementation-loop R11](../implementation-loop/spec.md)). The paths this feature declares are the File targets table in [plan.md](./plan.md). A shared path with the feature already in the loop blocks start until **Allow overlap** is checked on the CodeSpec block. Force feature and Allow dirty start do not clear that block.

`src/hive_planner/launcher/app.py` is also a controls-execute path. A switch between these two features stops on that file until overlap is allowed.

## Out of scope

Installing a kernel scheduler. Android. Persisting posteriors across process restarts.

## Acceptance

- Given an empty queue, `plan_chunk` returns no units.
- Given all four kinds queued at the same time and the default budget, the chunk runs `canvas_redraw` only. The other three keep their deadlines.
- Given a fixed random sequence, two calls with the same posteriors and the same queue return the same optional order, and the default budget does not return every queued kind.
- Given two kinds that ran in one chunk and two different hitch measurements, each posterior moves on its own measurement. A hitch named for a kind that did not run does not move that posterior.

## User Scenarios & Testing

### User Story 1 - A resize drag stays responsive (Priority: P1)

The window is dragged. Canvas redraw can run on the next scheduler tick. The sash, label wrap, and scrollbar wait for their virtual deadlines instead of all running in that same tick.

**Acceptance Scenarios**:

1. **Given** all four resize kinds queued at the same time, **When** the default chunk is planned, **Then** only `canvas_redraw` runs and the other three stay queued.
2. **Given** a chunk that ran two kinds, **When** each kind reports its own hitch, **Then** each posterior moves from its own measurement.

## Success Criteria

- **SC-001**: With the default budget, the first chunk of a full queue returns one kind.
- **SC-002**: `observe` never applies one hitch number to every kind that ran.
- **SC-003**: Canvas, sash, wrap, and scrollbar Configure paths enqueue on `ResizeScheduler`.

## Assumptions

- The feature id matches the spec folder name.
- Callers share one monotonic clock with `enqueue` and `plan_chunk`.
- A kind's hitch is the time its own payload took, in milliseconds.
