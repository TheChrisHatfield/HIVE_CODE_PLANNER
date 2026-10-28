# Impact packet: quiet memory-check notice during bug hunts

**Date:** 2026-10-27  
**Hook:** `memory.agents_md`, `change.bugfix_mode`

## Change

The continual-learning stop hook skips the Hive Planner desktop notice when the chat transcript contains a bug-hunt request. The check stays due. Other chats still get the notice.

## Effects

- Primary: `src/hive_planner/vendor_templates/continual-learning/hooks/continual-learning-stop.py`
- Deployed copy: `.cursor/plugins/hive-continual-learning/hooks/continual-learning-stop.py`
- Tests: `tests/test_cursor_hooks_compat.py`

## Validation

`py -3.11 -m pytest tests/test_cursor_hooks_compat.py -q -k "notice or bug_hunt"`
