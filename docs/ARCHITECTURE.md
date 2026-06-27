# Architecture

System design for Hive Code Planner.

## Planning context

Agent navigation starts at the **Planning Rosetta Stone**:

- File: [`planning-rosetta-stone.md`](./planning-rosetta-stone.md)
- Hook: `planning.rosetta`
- Loader: [`../START_HERE.md`](../START_HERE.md)

Full planning archive: [`HIVE_PLANNING_DEV.md`](./HIVE_PLANNING_DEV.md)

## Status

v1.2.0 — Stage 8 complete (20/20 roadmap artifacts). v1.1.0 shipped Stage 7 (CL/spec integration, memory v2, rule seeds, impact v3, project bootstrap). v1.0.0 shipped Stages 1–6. Stage 8 adds starter-kit v2 (`--profile full`, `--git-init`) and path/feature validation hardening.

Validate with:

```powershell
py -3.11 -m hive_planner roadmap-status
py -3.11 -m hive_planner ci-check
py -3.11 -m hive_planner spec-drift-check
```
