# Tasks: git-handoff-ci-v1

**Hook:** `spec.flow`

## Task 1 — Delta + spec ✅

- [x] Micro brief, spec, plan, tasks
- [x] Update loaders

## Task 2 — ci_handoff module ✅

- [x] `run_ci_check` orchestration
- [x] Active feature parser from AGENTS.md

## Task 3 — CLI + workflow ✅

- [x] `ci-check` subcommand
- [x] `.github/workflows/ci.yml`

## Task 4 — Tests + bug gate ✅

- [x] `tests/test_ci_handoff.py`
- [x] map_sync table header parse fix
- [x] S5C-B1 handoff artifacts
- [x] S5C-B2 map drift detection
- [x] S5C-B3 full pytest regression

## Active task

**None** — Stage 5C complete. Next: `cartridge-pack-v1` (Stage 6A), then `roadmap-complete-v1` (Stage 6B).

## Bug gate (Stage 5C)

| Check | Test |
|-------|------|
| S5C-B1 handoff artifacts | `test_ci_check_validates_handoff_artifacts` |
| S5C-B2 map drift | `test_ci_check_detects_map_drift` |
| S5C-B3 map header parse | `test_render_does_not_duplicate_table_header` |
| S5C-B4 regression | full pytest |

## Validation log

```text
2026-06-21 — Stage 5C bug gate
- S5C-B1: test_ci_check_validates_handoff_artifacts PASS
- S5C-B2: test_ci_check_detects_map_drift PASS
- S5C-B3: test_render_does_not_duplicate_table_header PASS
- S5C-B4: 92/92 pytest PASS
- Smoke: impact-sync-maps + ci-check OK
2026-06-21 — post-v1.0.0 bug audit (Stage 5C)
- test_ci_handoff.py: 4/4 PASS; S5C-B1..B4 verified
- Smoke: ci-check --skip-pytest OK
```
