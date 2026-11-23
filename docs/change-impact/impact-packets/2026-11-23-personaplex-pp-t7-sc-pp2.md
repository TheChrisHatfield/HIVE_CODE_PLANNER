# Impact packet — PersonaPlex PP-T7 SC-PP2 fixture tests

**Date:** 2026-11-23  
**Hook:** `change.impact`, `change.validation`  
**Spec:** `docs/specs/PersonaPlex_migrate/spec.md` SC-PP2 / PP-T7

## Change

`tests/test_personaplex_migrate.py` now fails SC-PP2 when only text inject ran, and when `update_streaming_sum_tensors` ran without `apply_pending` on ≥2 steps. bf16 dummy fixture; no live mic.

## Primary

- `tests/test_personaplex_migrate.py`

## Tests

- `py -3.11 -m pytest tests/test_personaplex_migrate.py -q`
