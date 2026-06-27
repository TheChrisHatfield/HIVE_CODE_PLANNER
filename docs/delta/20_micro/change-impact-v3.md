# Feature Micro Brief: change-impact-v3

**Hook:** `change.impact`, `change.bugfix_mode`, `next.files`

## Feature Name

Change Impact v3 — bugfix mode and Python call graph.

## Scope

| In scope | Out of scope |
|----------|--------------|
| `--mode bugfix`, `--deep` | External package graphs |
| `call_graph.py` AST edges | Deleting stale map rows |
| Caller/importer secondary targets | CI workflow automation |

**Files:** `src/hive_planner/call_graph.py`, `impact.py`, `cli.py`, `tests/test_impact.py`

## Acceptance Criteria

- [x] Bugfix mode sets medium risk and bugfix validations
- [x] Deep/bugfix adds call-graph secondary targets
- [x] Default mode unchanged without flags
- [x] Tests cover graph expansion and mode errors

## Validation

```powershell
py -3.11 -m pytest tests/test_impact.py -v
py -3.11 -m hive_planner impact --feature change-impact-v3 --mode bugfix --files src/hive_planner/call_graph.py
```
