# Plan: change-impact-v2

**Hook:** `change.impact`  
**Spec:** [spec.md](./spec.md)

## Approach

Add `map_sync.py` with discover + merge + render. Subcommand writes maps in place.

## Module map

```text
src/hive_planner/
  map_sync.py   # discover, merge, sync
  cli.py        # impact-sync-maps
tests/
  test_map_sync.py
```

## Validation

- Unit tests with temp repo fixtures
- Dry-run + write smoke on real repo
- Impact packet still resolves tests for edited src file
