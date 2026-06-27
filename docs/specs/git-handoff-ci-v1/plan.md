# Plan: git-handoff-ci-v1

**Hook:** `workflow.git_handoff`  
**Spec:** [spec.md](./spec.md)

## Approach

New `ci_handoff.py` orchestrates existing modules. Workflow file is optional for local-only repos but ready when remote is added.

## Module map

```text
src/hive_planner/
  ci_handoff.py       # run_ci_check, parse_active_feature
  cli.py              # ci-check subcommand
.github/workflows/
  ci.yml
tests/
  test_ci_handoff.py
```

## Validation

- Unit tests with temp AGENTS.md fixtures
- Smoke `ci-check --skip-pytest` on repo after map sync
