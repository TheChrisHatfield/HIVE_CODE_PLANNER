# Impact packet — implementation-loop Home help

**Date:** 2026-10-26  
**Hook:** `spec.flow`, `change.impact`, `change.validation`  
**Task:** Home **How to use** guide and Enable tooltip name Loop check

## Primary

- `scripts/README.md` — live Home user guide (loaded when the file exists)
- `src/hive_planner/launcher/user_guide.py` — append Implementation loop section if README is stale
- `src/hive_planner/launcher/app.py` — Enable implementation loop tooltip lists Loop buttons including check

## Tests

- `tests/test_launcher.py` — README documents the loop; stale README appends once; no duplicate section

## Secondary

- Fallback `_FALLBACK_GUIDE` already listed Loop check; unchanged besides existing daily-use line
- CLI argparse help for `implementation-loop check` unchanged

## Out of scope

- Coordinator gate behavior
- Merge/deploy
