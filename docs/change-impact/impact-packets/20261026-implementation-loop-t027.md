# Impact packet — implementation-loop T027

**Date:** 2026-10-26  
**Hook:** `spec.flow`, `change.impact`, `change.validation`  
**Task:** Home chat/GUI duality for coordinator gates

## Primary

- `src/hive_planner/launcher/service.py` — status/start/handoff/accept/commit wrappers
- `src/hive_planner/launcher/app.py` — Loop status/start/handoff/accept/commit
- `src/hive_planner/launcher/agent_prompt_templates.py` — Start the implementation loop
- `src/hive_planner/launcher/user_guide.py` — Home button list
- `docs/specs/implementation-loop/{spec,plan,tasks}.md`
- `docs/delta/20_micro/implementation-loop.md`

## Tests

- `tests/test_launcher.py` — Home wrappers and prompt template
- Existing coordinator tests unchanged (Python gates stay in `implementation_loop.py`)

## Secondary

- CLI remains the same functions; Home does not reimplement gates
- Chat phrase and Agent prompt template stay valid

## Out of scope

- Merge/deploy
- Python as coder/checker/reviewer
