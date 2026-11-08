# Impact packet — Bug-hunt ranker gaps

**Date:** 2026-11-05
**Hook:** `change.impact`, `change.validation`
**Change:** A blank continue file does not claim the queue head. A stop with no outcome appends one `stopped` row. Voted rows that omit `findings` move trust, and rows that omit both `findings` and `score` move surprise.

## Primary
- `src/hive_planner/bug_hunt.py` — `_take_pass_file`, `_append_unlabeled_stop`, `save_stopped_outcome`, `_trust_votes`, `surprise_scale`

## Secondary
- `tests/test_bug_hunt.py`
- `docs/specs/bug-hunt/spec.md` — R9 trust and surprise sentences for omitted keys

## Tertiary
- Stop hook still calls `save_stopped_outcome`. `stopped` casts no six-weight, trust, or place vote.

## Tests
- `tests/test_bug_hunt.py`
