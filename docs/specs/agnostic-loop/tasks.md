# Tasks: agnostic-loop

<!-- ROSETTA-NAV -->

Load [`docs/planning-rosetta-stone.md`](../../planning-rosetta-stone.md) (`planning.rosetta`) before executing tasks.

- **Spec:** [`spec.md`](./spec.md)
- **Plan:** [`plan.md`](./plan.md)
- **Delta micro:** [`agnostic-loop.md`](../../delta/20_micro/agnostic-loop.md)

## Phase 1 — Spec records

- [x] T001 Write spec, plan, tasks, and Delta micro

## Phase 2 — Engine and CLI

- [x] T002 Port chooser + arm/begin/review/observe/choose with `--root` state
- [x] T003 CLI `agnostic-loop` subcommands; install writes the kit
- [x] T004 Tests: cycle, choose seed, kit catalog, trigger, install

## Phase 3 — Entry

- [x] T005 Home Enable, prompt template, START_HERE / user guide pointers
- [x] T006 Optional `init --agnostic-loop`; maps and impact packet
- [x] T007 Install full kit (scripts, remap, skill, catalog.json); catalog.json is replaceable
- [x] T008 Strip source-repo catalog names and tick rules; default rewards are generic

## Active task

**None** — T008 checked.

## Validation log

```text
2026-10-26 — port hive-loop-kit into Hive Planner
- src/hive_planner/agnostic_loop.py
- CLI + Home Enable
- tests/test_agnostic_loop.py
2026-10-26 — T007 full kit install + replaceable catalog.json
- py -3.11 -m pytest tests/test_agnostic_loop.py
2026-10-26 — T008 generic catalog (no source-repo tick rules)
- py -3.11 -m pytest tests/test_agnostic_loop.py
```
