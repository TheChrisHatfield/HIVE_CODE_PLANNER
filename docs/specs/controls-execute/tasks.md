# Tasks: controls-execute

<!-- ROSETTA-NAV -->

## Agent navigation (Rosetta Stone)

Load [`docs/planning-rosetta-stone.md`](../../planning-rosetta-stone.md) (`planning.rosetta`) before executing tasks.

- **Spec:** [`spec.md`](./spec.md)
- **Plan:** [`plan.md`](./plan.md)
- **Delta micro:** [`controls-execute.md`](../../delta/20_micro/controls-execute.md)

## Phase 1 — Adapter and delivery script (US1, US3)

- [x] T001 Add the chat-target adapter interface and outcome values in `src/hive_planner/launcher/chat_target.py`
- [x] T002 Add the Cursor delivery script and the in-workbench submitter. The script reads `composerHeaders` read-only for the active workspace id, matches the title, skips archived and subagent rows, and writes `request.json`. The submitter calls `submitChatMaybeAbortCurrent` and writes `result.json`. Do not open the desktop bridge and do not call that workbench function from Hive's process
- [x] T003 `tests/test_cursor_chat_delivery.py` for duplicate titles, another workspace ignored, unknown title, draft refused, loop not installed refused, already generating, and a failed script

## Phase 2 — Controls block (US1, US2)

- [ ] T004 Add the tab-name field and Execute button on each Controls block header. Folding keeps Loop, Command, the tab name, Run, and Execute visible
- [ ] T005 Map Bug hunt, CodeSpec, and Agnostic loop to `bug hunt`, `code spec`, and `agnostic loop`. Execute calls the delivery function with that phrase and the active repo. It does not call Run's install or gate functions
- [ ] T006 Show sent, not found, refused, already generating, and failed on the block. A skipped submit must not use the sent message
- [ ] T007 `tests/test_launcher.py` covers the phrase map, a fake adapter, and the failure messages, with 0 database reads and 0 submits in the button handler

## Phase 3 — Live checks

- [ ] T008 From the control-panel process, press Execute and confirm the named in-scope chat receives the phrase and one pass of that loop starts
- [ ] T009 Confirm already generating (composer status or the loop state file) and refused (draft or loop not installed) do not submit

## After each implementation task — Integration wiring audit (required)

- [x] Traced caller → handler → core (no layer break)
- [x] No false success when a sub-step failed or was skipped
- [x] Integration-level validation evidence attached
- [x] See `.cursor/rules/integration-wiring-audit.mdc`
