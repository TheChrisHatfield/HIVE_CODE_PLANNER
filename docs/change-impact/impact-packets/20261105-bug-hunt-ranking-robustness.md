# Impact packet — Bug-hunt ranking robustness

**Date:** 2026-11-05
**Hook:** `change.impact`, `change.bugfix_mode`, `change.validation`
**Change:** Rank-row read/write hardening (NaN, digit strings, junk opened list, cache skip, Signals type, MemoryError, temp cleanup, findings/score persist). Sampled trust/place mix is unchanged.

## Primary
- `src/hive_planner/bug_hunt.py` — `_finding_count`, `load_rank_rows`, `_write_json`, `_load_opened`, `_append_rank_row`, `_candidate_files`, `_detector_ready`

## Secondary
- `tests/test_bug_hunt.py`
- `docs/specs/bug-hunt/tasks.md` — Ranking robustness task

## Tertiary
- Stop hook still copies `findings`/`score` from `rank-pass.json` via `_take_pass_file`

## Tests
- `tests/test_bug_hunt.py`
