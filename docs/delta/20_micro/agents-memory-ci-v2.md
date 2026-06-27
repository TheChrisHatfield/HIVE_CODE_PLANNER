# Feature Micro Brief: agents-memory-ci-v2

**Hook:** `automation.ci_memory`, `integration.cl_spec`

## Feature Name

AGENTS.md Memory CI v2 — guarded apply, candidate ingest, GHA proposal workflow.

## Scope

| In scope | Out of scope |
|----------|--------------|
| `agents-apply`, `--apply` | Auto-merge PR bot |
| `agents-ingest` | Transcript plugin |
| GHA proposal artifact | Nightly schedule |

## Acceptance Criteria

- [x] Operational apply merges into Durable Workspace Facts only
- [x] Behavioral candidates rejected on apply
- [x] Rollback on lint failure
- [x] `agents-ingest` normalizes exports
- [x] GHA workflow_dispatch proposal job

## Validation

```powershell
py -3.11 -m pytest tests/test_agents_memory.py -v
py -3.11 -m hive_planner agents-apply --candidates docs/proposals/example-candidates.md
```
