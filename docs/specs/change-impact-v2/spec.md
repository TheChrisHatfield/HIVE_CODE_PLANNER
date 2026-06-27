# Spec: change-impact-v2

**Hook:** `change.impact`, `next.files`  
**Status:** active  
**Delta:** [change-impact-v2.md](../../delta/20_micro/change-impact-v2.md)

## What

Auto-sync `docs/change-impact/project-map.md` and `test-map.md` from repository structure and test imports.

## Why

v1 maps were manual; project-map notes auto-generation deferred. New modules (embeddings, delta_emit, map_sync) drifted from maps, weakening impact packets.

## Requirements

### R1 — Module discovery

- Scan `src/hive_planner/**/*.py` excluding `__init__.py`
- Add missing modules to project-map with docstring-derived role

### R2 — Test discovery

- Parse `tests/test_*.py` imports via AST
- Map `hive_planner.*` imports to `src/hive_planner/...py` paths
- Union with existing test-map rows

### R3 — Preserve manual curation

- Non-`src/` project-map rows unchanged
- Existing `src/` project-map rows not overwritten
- Existing test-map entries never removed

### R4 — CLI

`hive_planner impact-sync-maps [--dry-run]`

### R5 — Warnings

Report src modules with no mapped tests after sync.

## Out of scope

Call graphs, deleting stale rows, CI workflows.
