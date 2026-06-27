# Architecture

System design for Hive Code Planner.

## Planning context

Agent navigation starts at the **Planning Rosetta Stone**:

- File: [`planning-rosetta-stone.md`](./planning-rosetta-stone.md)
- Hook: `planning.rosetta`
- Loader: [`../START_HERE.md`](../START_HERE.md)

Full planning archive: [`HIVE_PLANNING_DEV.md`](./HIVE_PLANNING_DEV.md)

## Status

v1.1.0 — Stage 7 complete (18/18 roadmap artifacts). Stages 1–6 shipped at v1.0.0. Stage 7 adds CL/Spec Kit integration, memory v2 (`agents-apply` / `agents-ingest`), cartridge rule seeds (`--emit-rules-seeds`), change impact v3 (`--mode bugfix`, call graph), and project bootstrap (`hive_planner init`).

Validate with:

```powershell
py -3.11 -m hive_planner roadmap-status
py -3.11 -m hive_planner ci-check
py -3.11 -m hive_planner spec-drift-check
```
