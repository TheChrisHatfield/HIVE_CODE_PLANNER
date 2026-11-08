# Impact packet — Bug-hunt findings-present bonus

**Date:** 2026-11-04
**Hook:** `change.impact`, `change.bugfix_mode`, `change.validation`
**Change:** Rank files with detector findings above zero-finding files without changing six-weight learning

## Primary
- `src/hive_planner/bug_hunt.py` — `FINDINGS_PRESENT_BONUS`, `rank_queue_score`, `score_unopened` sort
- `docs/specs/bug-hunt/spec.md` — R5 findings-present bonus

## Secondary
- `tests/test_bug_hunt.py` — ordering tests and prompt phrase
- `render_agent_prompt` text in `bug_hunt.py`

## Tertiary
- Installed hunt scripts on next `bug-hunt` install (generated from `render_agent_prompt`)

## Tests
- `tests/test_bug_hunt.py`
- full pytest suite
