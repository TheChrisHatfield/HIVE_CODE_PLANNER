# Impact packet — CodeSpec chat phrase and Install button

**Date:** 2026-10-28  
**Spec:** `docs/specs/implementation-loop/spec.md` R8–R9

## Change

Two extra starts for CodeSpec. Chat **code spec** (any case) is the same start as **implementation loop**. Controls **Install CodeSpec** finds the front-most Cursor window, links that folder, selects CodeSpec, keeps the pack, folds settings, then Enable. Compact still only hides settings.

## Primary

- `src/hive_planner/implementation_loop.py` — matcher and always-on rule phrases
- `src/hive_planner/launcher/service.py` — Cursor window title → workspace
- `src/hive_planner/launcher/app.py` — Loop alias, Install CodeSpec button

## Secondary

- `docs/specs/implementation-loop/{spec,plan,tasks}.md`
- `docs/delta/20_micro/implementation-loop.md`
- `START_HERE.md`, `AGENTS.md`, `scripts/README.md`
- `src/hive_planner/launcher/user_guide.py`, `agent_prompt_templates.py`
- `.cursor/rules/implementation-loop.mdc` (generated copy in this repo)

## Tests

- `tests/test_implementation_loop.py` — **code spec** trigger and rule text
- `tests/test_launcher.py` — Loop alias, window match, Install button present

## Tertiary

Compact does not write. No Close button. Product coding still needs the Cursor agent after Enable.
