# Impact packet — Bug hunt as a core Hive feature

**Date:** 2026-10-20  
**Hook:** `change.impact`, `change.bugfix_mode`, `integration.wiring_audit`  
**Change:** Install chat-triggered bug hunt on bootstrap / Home; match derivative hunt phrases

## Primary
- `src/hive_planner/bug_hunt.py` — `is_bug_hunt_request`, broader always-on rule, `force` on install
- `src/hive_planner/bootstrap.py` — `_install_bug_hunt_artifacts` from `init_project` and handoff deploy
- `src/hive_planner/launcher/service.py` — `run_project_bug_hunt_install`
- `src/hive_planner/launcher/app.py` — Home **Enable bug hunt**

## Secondary
- `tests/test_bug_hunt.py`, `tests/test_bootstrap.py`, `tests/test_launcher.py`
- `src/hive_planner/launcher/agent_prompt_templates.py`, `user_guide.py`

## Tertiary
- Cursor chats in any Hive project: saying bug hunt / hunt for bugs starts the loop

## Tests
- `tests/test_bug_hunt.py`
- `tests/test_bootstrap.py::test_init_creates_detectable_repo_root`
- `tests/test_launcher.py` (`-k "bug_hunt"`)
