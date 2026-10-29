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

A library scheduler that smooths resize hitching. Each resize-related task is one schedulable unit. The unit gets a virtual deadline from how latency-sensitive it is. Each short time chunk, Thompson sampling chooses which not-yet-due units run, using the hitch cost observed after earlier chunks.

The four units are the resize jobs already present in the launcher. This feature does not edit those handlers. It schedules the four kinds so a later wiring change can call one planner instead of doing all four on every `<Configure>`.

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
| Macro | One pure scheduler module. The launcher, kernel, and Android are unchanged. |
| Micro | Queue, virtual deadline, chunk plan, Beta update from hitch cost. |

## Requirements

### R1 — One pending unit per kind

- The only kinds are `canvas_redraw`, `split_reposition`, `label_rewrap`, and `scrollbar_pack`.
- Enqueueing a kind that is already pending keeps the earlier deadline and replaces the payload.
- A kind that is not pending is stamped with `deadline_ms = now_ms + base_window_ms * (1 - sensitivity)`.
- `base_window_ms` defaults to 48. Sensitivity is the table above.

### R2 — Virtual deadline inside a chunk

- `plan_chunk(now_ms)` returns the units that run in this chunk, earliest deadline first among those that are due (`deadline_ms <= now_ms`).
- Due units run even when their cost exceeds the chunk budget. After a due unit overruns the budget, no optional unit runs in that chunk.
- Units that are not due fill whatever budget remains.

### R3 — Thompson sampling for optional units

- Each kind has a Beta posterior, prior Beta(1, 1), for the chance that running it stays under the hitch limit.
- Optional units are ordered by one draw from that kind's Beta, highest draw first. The draw uses an injectable random source so tests can fix the sequence.
- A unit runs only while `unit_cost_ms` still fits in the remaining budget. `unit_cost_ms` defaults to 4. The chunk budget defaults to 16.
- Kinds with no pending unit are not sampled.

### R4 — Hitch observation

- `observe(hitch_ms)` updates only the kinds returned by the last `plan_chunk`.
- A hitch at or below `hitch_limit_ms` (default 8) increments that kind's alpha by 1.
- A hitch above the limit increments beta by 1.
- `observe` before any plan, or after a plan that ran nothing, changes no posterior.
- A second `observe` without a new plan changes nothing.

## Overlap with another feature

Start and feature switch go through the implementation loop's file-overlap gate ([implementation-loop R11](../implementation-loop/spec.md)). The paths this feature declares are the File targets table in [plan.md](./plan.md): `src/hive_planner/lavd_resize.py` and `tests/test_lavd_resize.py`. A shared path with the feature already in the loop blocks start until **Allow overlap** is checked on the CodeSpec block. Force feature and Allow dirty start do not clear that block.

Those paths do not intersect controls-execute's launcher and chat-delivery paths. This gate would not have stopped a switch between these two features. A blocked loop and a dirty tree remain separate gates.

## Out of scope

Editing `src/hive_planner/launcher/app.py`. Installing a kernel scheduler. Android. Persisting posteriors across process restarts.

## Acceptance

- Given an empty queue, `plan_chunk` returns no units.
- Given all four kinds queued at the same time, the chunk runs `canvas_redraw` first because its deadline is immediate, and it does not run a not-due unit once the budget is spent.
- Given a fixed random sequence, two calls with the same posteriors and the same queue return the same optional order.
- Given a hitch above the limit after a plan, each kind that ran has beta increased by 1 and alpha unchanged. A hitch within the limit increases alpha instead.
