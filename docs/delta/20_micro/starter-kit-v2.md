# Feature Micro Brief: starter-kit-v2

**Hook:** `workflow.project_bootstrap`, `repo.starter_files`

## Feature Name

Starter-kit v2 — full bootstrap profile with pyproject, CI stub, and optional git init.

## Scope

| In scope | Out of scope |
|----------|--------------|
| `--profile full` scaffold | Cloud hosting |
| `--git-init` optional | Auto Hive pip install in target |
| CI workflow stub | Multiple custom profiles |

**Files:** `src/hive_planner/bootstrap.py`, `cli.py`, `tests/test_bootstrap.py`, `docs/project-bootstrap-guide.md`

## Acceptance Criteria

- [x] `minimal` profile unchanged from v1
- [x] `full` profile writes pyproject, src/tests, CI, gitignore
- [x] `--git-init` initializes repo or warns on skip
- [x] Tests cover full profile and git init paths

## Validation

```powershell
py -3.11 -m pytest tests/test_bootstrap.py -v
py -3.11 -m hive_planner init --target %TEMP%\hive-full --profile full --git-init --name "Demo"
```
