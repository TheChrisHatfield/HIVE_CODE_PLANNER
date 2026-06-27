# Tasks: change-impact-v2

**Hook:** `spec.flow`

## Task 1 — Delta + spec ✅

- [x] Micro brief, spec, plan, tasks
- [x] Update loaders

## Task 2 — map_sync module ✅

- [x] src module discovery
- [x] AST test import discovery
- [x] Merge/render project-map and test-map

## Task 3 — CLI ✅

- [x] `impact-sync-maps [--dry-run]`

## Task 4 — Tests + bug gate ✅

- [x] `tests/test_map_sync.py`
- [x] delta_emit skip fix (draft after blank line)
- [x] S5B-B1 dry-run no write
- [x] S5B-B2 preserve manual rows
- [x] S5B-B3 full pytest regression

## Active task

**None** — Stage 5B complete. Next: `git-handoff-ci-v1` (Stage 5C).

## Bug gate (Stage 5B)

| Check | Test |
|-------|------|
| S5B-B1 dry-run | `test_sync_dry_run_does_not_write` |
| S5B-B2 manual preserve | `test_sync_preserves_manual_project_rows` |
| S5B-B3 import merge | `test_sync_merges_test_imports` |
| S5B-B4 regression | full pytest |

## Validation log

```text
2026-06-21 — Stage 5B bug gate
- S5B-B1: test_sync_dry_run_does_not_write PASS
- S5B-B2: test_sync_preserves_manual_project_rows PASS
- S5B-B3: test_sync_merges_test_imports PASS
- S5B-B4: 87/87 pytest PASS
- Smoke: impact-sync-maps added 9 project rows, merged test imports
2026-06-21 — post-v1.0.0 bug audit (Stage 5B)
- test_map_sync.py: 7/7 PASS; S5B-B1..B4 verified
- Smoke: impact-sync-maps --dry-run OK
```
