# Plan: change-impact-v3

**Hook:** `change.impact`, `change.bugfix_mode`  
**Spec:** [spec.md](./spec.md)

## Approach

Add `call_graph.py`; extend `build_impact_packet()` with `mode` and `deep` parameters; wire CLI flags.

## Validation

```powershell
py -3.11 -m pytest tests/test_impact.py -v
py -3.11 -m hive_planner impact --feature change-impact-v3 --mode bugfix --files src/hive_planner/impact.py
```
