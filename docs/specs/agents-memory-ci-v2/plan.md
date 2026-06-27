# Plan: agents-memory-ci-v2

**Hook:** `automation.ci_memory`  
**Spec:** [spec.md](./spec.md)

## Approach

Extend `agents_memory.py` with `run_agents_memory`, `ingest_agents_candidates`, guarded apply with lint rollback. Add CLI aliases and GHA workflow (proposal-only).

## Validation

```powershell
py -3.11 -m pytest tests/test_agents_memory.py -v
py -3.11 -m hive_planner agents-ingest --from docs/proposals/candidates-template.md
py -3.11 -m hive_planner agents-apply --candidates docs/proposals/example-candidates.md
```
