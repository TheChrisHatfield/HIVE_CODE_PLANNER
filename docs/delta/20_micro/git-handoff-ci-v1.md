# Feature Micro Brief: git-handoff-ci-v1

**Hook:** `workflow.git_handoff`, `automation.ci_memory`, `change.validation`

## Feature Name

Git Handoff CI v1 — local and GitHub Actions validation suite for branch handoff readiness.

## Holistic Link

Closes the Perplexity → Git → Cursor loop from [context-handoff-and-automation.md](../../context-handoff-and-automation.md) with executable gates.

## Macro Link

Combines **agents-memory-ci**, **change-impact**, and pytest into one handoff check.

## Scope

| In scope | Out of scope |
|----------|--------------|
| `ci-check` CLI (pytest + agents-lint + handoff artifacts) | Auto-merge AGENTS.md |
| Map drift detection via dry-run sync | Transcript parsing |
| `.github/workflows/ci.yml` template | Required GitHub remote |
| `--skip-pytest`, `--allow-map-drift` flags | Nightly propose jobs |

**Files:** `src/hive_planner/ci_handoff.py`, `.github/workflows/ci.yml`, `tests/test_ci_handoff.py`

## Acceptance Criteria

- [x] `ci-check` fails on agents-lint errors
- [x] Validates active feature spec + micro brief exist
- [x] Detects impact-map drift unless `--allow-map-drift`
- [x] GitHub workflow runs sync + ci-check
- [x] Full pytest regression

## Validation

```powershell
py -3.11 -m hive_planner impact-sync-maps
py -3.11 -m hive_planner ci-check
py -3.11 -m pytest -v
```
