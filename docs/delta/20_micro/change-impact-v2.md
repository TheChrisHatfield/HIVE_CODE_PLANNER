# Feature Micro Brief: change-impact-v2

**Hook:** `change.impact`, `next.files`, `change.validation`

## Feature Name

Change Impact v2 — auto-merge src module and test import discovery into change-impact maps.

## Holistic Link

Reduces map drift that causes impact packets to miss tests or modules after new stages land.

## Macro Link

Extends **change-impact** subsystem per [change-impact-lift.md](../../change-impact-lift.md).

## Scope

| In scope | Out of scope |
|----------|--------------|
| AST import scan of `tests/test_*.py` | Full call-graph analysis |
| Add missing `src/hive_planner/**/*.py` rows | Delete manual doc rows |
| Merge discovered tests with existing test-map | CI auto-merge to AGENTS.md |
| `impact-sync-maps [--dry-run]` CLI | Overwrite curated project-map roles |

**Files:** `src/hive_planner/map_sync.py`, `cli.py`, `tests/test_map_sync.py`

## Acceptance Criteria

- [x] `impact-sync-maps` adds missing src modules to project-map
- [x] Test imports merged into test-map without dropping manual entries
- [x] Manual doc rows in project-map preserved
- [x] `--dry-run` reports changes without writing
- [x] Full pytest regression

## Validation

```powershell
py -3.11 -m hive_planner impact-sync-maps --dry-run
py -3.11 -m hive_planner impact-sync-maps
py -3.11 -m pytest -v
```
