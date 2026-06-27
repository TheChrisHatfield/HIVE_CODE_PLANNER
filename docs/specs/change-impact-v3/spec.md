# Spec: change-impact-v3

**Hook:** `change.impact`, `change.bugfix_mode`, `next.files`  
**Status:** active  
**Delta:** [change-impact-v3.md](../../delta/20_micro/change-impact-v3.md)

## What

Extend change-impact with bugfix mode and a limited Python call/import graph for richer secondary targets.

## Requirements

### R1 — Bugfix mode

- `impact --mode bugfix` sets base `risk_score` to `medium`.
- Adds `change.bugfix_mode` to packet `hook_ids`.
- Adds regression-oriented validations (symptom chain, anti-overfit, caller tests).

### R2 — Call graph module

- `call_graph.py` AST-scans `src/hive_planner/**/*.py`.
- Builds import reverse edges and same-package caller→callee edges.

### R3 — Deep / bugfix secondary targets

- `--mode bugfix` or `--deep` adds importer and call-site modules as secondary targets.
- Includes mapped regression tests for caller modules.

### R4 — Backward compatibility

- Default mode unchanged when neither `--mode bugfix` nor `--deep` is set.
- Existing packets without `mode` field load as `default`.

## Out of scope

External dependency graphs, non-Python languages, CI automation.
