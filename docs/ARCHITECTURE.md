# Architecture

System design for Hive Code Planner.

## Planning context

Agent navigation starts at the **Planning Rosetta Stone**:

- File: [`planning-rosetta-stone.md`](./planning-rosetta-stone.md)
- Hook: `planning.rosetta`
- Loader: [`../START_HERE.md`](../START_HERE.md)

Full planning archive: [`HIVE_PLANNING_DEV.md`](./HIVE_PLANNING_DEV.md)

## Status

v1.0.0 — Stages 1–6 compiler roadmap complete. Stage 7 Phase 1 adds Continual Learning + Spec Kit integration (`integration.cl_spec`, `spec-drift-check`, `agents-propose` behavioral rejection).

Validate with:

```powershell
py -3.11 -m hive_planner roadmap-status
py -3.11 -m hive_planner ci-check
py -3.11 -m hive_planner spec-drift-check
```
