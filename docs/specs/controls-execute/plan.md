# Plan: controls-execute

**Hook:** `workflow.tools`, `spec.flow`, `change.validation`, `integration.wiring_audit`  
**Spec:** [spec.md](./spec.md)  
**Status:** draft

<!-- ROSETTA-NAV -->

## Agent navigation (Rosetta Stone)

Load [`docs/planning-rosetta-stone.md`](../../planning-rosetta-stone.md) (`planning.rosetta`) before editing this plan.

- **Spec:** [`spec.md`](./spec.md)
- **Delta micro:** [`controls-execute.md`](../../delta/20_micro/controls-execute.md)
- **Hooks:** `workflow.tools`, `spec.flow`, `change.validation`

## Layer mapping

| Layer | Mapping |
|-------|---------|
| Holistic | The control panel starts a loop in a named chat of the active project. The user does not retype the phrase. |
| Macro | Run stays a local gate. Execute is a button that calls a different Python function: resolve a header, submit into that chat. |
| Micro | Tab name and Execute sit on each Controls block. One adapter hides the Cursor read and submit. |

## Approach

Add the field and button in `_mount_controls_instance` on the block header, next to Run. Folding still hides settings only.

The button handler maps the loop to the start phrase and calls the chat-target adapter with the typed name, the active repo, and the phrase. It does not read `state.vscdb` and it does not call bug-hunt install or any other Run gate.

The Cursor adapter reads `composerHeaders` read-only for the active project's workspace id and applies the match and scope rules. It writes `.hive/controls-execute/request.json`. Install copies `cursor_submitter` into the active project and loads it with the workspace-open `pluginPaths` mechanism (`hive_workspace_open.py`). That submitter calls `submitChatMaybeAbortCurrent` and writes `result.json`. The adapter waits up to 10 seconds. If that plugin host cannot call the workbench function, stop. Do not switch to the desktop bridge, paste, or the accessibility tree. The adapter does not call the workbench function itself.

A later IDE adapter implements the same resolve-and-deliver operations. This pass does not add that adapter.

## File targets

| File | Change |
|------|--------|
| `src/hive_planner/launcher/chat_target.py` | Adapter interface plus outcome values |
| `src/hive_planner/launcher/cursor_chat_delivery.py` | Header read, workspace scope, request file, wait for result |
| `src/hive_planner/launcher/cursor_submitter/` | In-workbench half: read request, submit by composer id, write result |
| `src/hive_planner/launcher/app.py` | Tab-name field, Execute button, phrase map, outcome text |
| `tests/test_launcher.py` | Block widgets, phrase map, fake adapter, handler does not install a loop |
| `tests/test_cursor_chat_delivery.py` | Title match, other workspace ignored, draft refused, generating skipped |
| `docs/delta/20_micro/controls-execute.md` | This feature's micro note |

## Phrase map

| Loop | Text Execute submits |
|------|----------------------|
| Bug hunt | `bug hunt` |
| CodeSpec | `code spec` |
| Agnostic loop | `agnostic loop` |

## Open checks during build

- From the control-panel process, the named in-scope chat receives the phrase and one pass of that loop starts.
- A generating composer, or a loop state file already running, is reported already generating.
- A draft winner, or a loop that is not installed, is reported refused.

## Out of scope

Claude adapter. Desktop bridge server and its token. Keystroke paste. Accessibility-tree targeting. Copying the bug-hunt manual trigger. Changing Run.
