# Feature Micro Brief: project-bootstrap-v1

**Hook:** `workflow.project_bootstrap`

## Feature Name

Project bootstrap — `hive_planner init` per-project Hive profile.

## Scope

| In scope | Out of scope |
|----------|--------------|
| `init --target` scaffold | Auto git init |
| START_HERE + Rosetta + AGENTS | Cloud hosting |
| Packaged bootstrap_templates fallback | Forking CL plugin |

**Files:** `src/hive_planner/bootstrap.py`, `cli.py`, `tests/test_bootstrap.py`, `docs/project-bootstrap-guide.md`

## Acceptance Criteria

- [x] init creates detectable Hive repo root
- [x] Non-empty target blocked without `--force`
- [x] Cursor rules + Spec Kit starter copied
- [x] Tests + guide documented

## Validation

```powershell
py -3.11 -m pytest tests/test_bootstrap.py -v
py -3.11 -m hive_planner init --target %TEMP%\hive-demo --name demo
```
