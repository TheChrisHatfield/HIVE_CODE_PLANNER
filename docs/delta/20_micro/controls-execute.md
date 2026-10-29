# Micro: controls-execute

**Hook:** `workflow.tools`, `spec.flow`  
**Status:** draft  
**Spec:** [controls-execute](../../specs/controls-execute/spec.md)

<!-- ROSETTA-NAV -->

## Agent navigation (Rosetta Stone)

Load [`docs/planning-rosetta-stone.md`](../../planning-rosetta-stone.md) (`planning.rosetta`) before coding from this brief.

- **Hooks:** `context.delta`, `spec.flow`
- **Spec Kit:** [`spec.md`](../../specs/controls-execute/spec.md), [`plan.md`](../../specs/controls-execute/plan.md), [`tasks.md`](../../specs/controls-execute/tasks.md)

## What

Execute on a Controls block fires a Python delivery function. It submits that loop's start phrase into one chat of the active linked project, and the loop starts one pass.

A typed `bug hunt` in chat only proves the chat and the loop scripts are connected. Execute does not copy that manual entry, and it does not call Run's install functions.

## UI

- Each block header gains a tab-name field and an Execute button beside Run
- Folding still leaves Loop, Command, the tab name, Run, and Execute visible
- Run is unchanged

## Resolve and submit

Read `composerHeaders` in Cursor's `state.vscdb`. Title is `value.name`. Id is `composerId`. Recency is `lastUpdatedAt`. Only the active project's `workspaceId`. Skip archived and subagent rows. Latest title match wins.

Hive writes `.hive/controls-execute/request.json`. The in-workbench submitter calls `submitChatMaybeAbortCurrent` and writes `result.json`. Hive waits 10 seconds. Not the desktop bridge server, not paste, not the accessibility tree. Hive does not call the workbench function itself.

Phrases: Bug hunt `bug hunt`, CodeSpec `code spec`, Agnostic loop `agnostic loop`.

Already generating: composer `status` is `generating`, or the loop's state file on the active repo is running (`continue.json` active, or CodeSpec/agnostic `state.json` status `running`). Refused: the winner is a draft, or the loop is not installed.

## Adapter

One interface. Cursor is the only adapter in this pass. A Claude adapter is later work.
