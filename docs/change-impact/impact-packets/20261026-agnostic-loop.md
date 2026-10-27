# Impact packet — agnostic-loop

**Date:** 2026-10-26  
**Hook:** `workflow.tools`, `spec.flow`, `change.impact`  
**Task:** Install the full hive-loop-kit; generic replaceable catalog.json

## Primary

- `src/hive_planner/agnostic_loop.py`
- `src/hive_planner/cli.py`
- `src/hive_planner/bootstrap.py`
- `src/hive_planner/launcher/app.py` / `service.py` / `agent_prompt_templates.py` / `user_guide.py`
- `docs/specs/agnostic-loop/`
- `tests/test_agnostic_loop.py`

## Tests

- `tests/test_agnostic_loop.py`

## Secondary

- Bug hunt and implementation-loop unchanged
- `init` installs only with `--agnostic-loop`

## Out of scope

- SeamFlow catalog and source-kit reconstruction / train language
- Hive spec-gap baked catalog
- Merge/deploy
