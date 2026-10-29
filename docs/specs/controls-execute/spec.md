# Feature Specification: Controls Execute

**Feature Branch**: `controls-execute`

**Created**: 2026-10-28

**Status**: Draft

**Input**: User description: "Controls Execute fires a script that sends a loop start phrase into the named chat."

**Hook:** `workflow.tools`, `spec.flow`  
**Delta:** [controls-execute.md](../../delta/20_micro/controls-execute.md)

<!-- ROSETTA-NAV -->

## Agent navigation (Rosetta Stone)

Before implementing, load the hook map — do not jump straight into requirements.

1. [`docs/planning-rosetta-stone.md`](../../planning-rosetta-stone.md) — hook `planning.rosetta`
2. Follow **UNLOCKS**: `context.delta` → [`00_holistic.md`](../../delta/00_holistic.md), [`10_macro.md`](../../delta/10_macro.md)
3. This feature — hook `spec.flow`:
   - **Feature id:** `controls-execute`
   - Delta micro: [`docs/delta/20_micro/controls-execute.md`](../../delta/20_micro/controls-execute.md)
   - Plan: [`plan.md`](./plan.md)
   - Tasks: [`tasks.md`](./tasks.md)
4. Host UI: [`docs/specs/hive-desktop-v1/spec.md`](../hive-desktop-v1/spec.md) Controls blocks. This spec adds Execute. It does not change what Run does.

## What

Each Controls block has a tab-name field and an Execute button beside Run. The button fires a Python delivery script. That script resolves the typed title to one chat in the active linked project and submits that loop's start phrase into that chat's context window. The installed loop then starts one pass. The user does not type the phrase.

Typing `bug hunt` in a chat only proves a chat and the loop scripts are connected. Execute does not copy that manual entry, the bug-hunt rule, or the stop hook.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Execute starts the loop in the named chat (Priority: P1)

The user types a chat title, chooses a loop, and presses Execute. The phrase is submitted in that chat, and the loop starts one pass there.

**Why this priority**: The button has to start the loop in the named chat. A phrase that never starts the loop is not success.

**Independent Test**: With Bug hunt installed on the active repo, type a known open chat title in that repo, press Execute, and confirm that chat shows `bug hunt` and one hunt pass begins.

**Acceptance Scenarios**:

1. **Given** a Controls block, the active repo, and a chat in that repo titled `Hive face benefits`, **When** the user enters that title, selects Bug hunt, and presses Execute, **Then** `bug hunt` is submitted in that chat and one bug-hunt pass starts.
2. **Given** the same block, **When** the user selects CodeSpec and presses Execute, **Then** the submitted phrase is `code spec` and one CodeSpec pass starts.
3. **Given** the same block, **When** the user selects Agnostic loop and presses Execute, **Then** the submitted phrase is `agnostic loop` and one agnostic pass starts.
4. **Given** a block whose Command is not the loop's start action, **When** the user presses Execute, **Then** the phrase is still the loop start phrase. Command does not change it.
5. **Given** a block, **When** the user presses Run, **Then** Run still executes the selected local gate on the active repo and does not submit a phrase into a chat.

---

### User Story 2 - A miss is visible (Priority: P2)

If the script cannot start the loop in the named chat, the block says why. It does not report sent.

**Why this priority**: A silent miss looks like the loop started.

**Independent Test**: Point Execute at a missing title, a draft, and a chat that is already generating. Each case shows its own result and does not start a new pass.

**Acceptance Scenarios**:

1. **Given** two in-scope chats with the same title, **When** Execute runs, **Then** the script uses the one with the later `lastUpdatedAt`.
2. **Given** no in-scope chat title matches after trim, **When** Execute runs, **Then** the block reports not found and nothing is submitted.
3. **Given** the winning chat is a draft, or the selected loop is not installed on the active repo, **When** Execute runs, **Then** the block reports refused and nothing is submitted.
4. **Given** the winning chat is already generating, or that loop already has a pass in progress on the active repo, **When** Execute runs, **Then** the block reports already generating and does not submit.
5. **Given** the script fails before a submit, **When** Execute runs, **Then** the block reports failed and does not claim the phrase was sent.

---

### User Story 3 - One adapter, Cursor first (Priority: P3)

The button calls one interface: resolve a display name inside the active repo, deliver a phrase into that context, return an outcome. The Cursor script is the first adapter. A later adapter can target another IDE without a second button.

**Why this priority**: The panel layout should survive a second IDE. That IDE is not built in this pass.

**Independent Test**: A test double receives the typed name, the active repo, and the loop phrase. The button handler does not read Cursor's database and does not submit a chat.

**Acceptance Scenarios**:

1. **Given** the Execute handler, **When** tests replace the adapter, **Then** the handler still passes the typed name, the active repo, and the loop phrase, and shows the adapter's outcome.
2. **Given** this pass, **When** Execute runs, **Then** only the Cursor adapter is installed. No Claude client is called.

---

### Edge Cases

- The typed name differs from a title only by surrounding spaces. Trim before compare. Compare without case sensitivity. Do not use a substring match.
- A blank tab name is not found. Do not submit.
- Two in-scope matches share `lastUpdatedAt`. Report the tie as failed. Do not pick one silently.
- Archived chats, subagent chats, and chats whose workspace is not the active linked project are not candidates. They do not win a title match.
- A matching title that exists only in another Cursor window's other project is not found.
- The phrase is the short start phrase only. Do not send the Command label or a loop script body.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Each Controls block MUST show a tab-name field on the same header as Loop and Command.
- **FR-002**: Each Controls block MUST show an Execute button on the header beside Run. Folding the block MUST leave Loop, Command, the tab-name field, Run, and Execute visible.
- **FR-003**: Execute MUST submit exactly one phrase for the selected loop: Bug hunt submits `bug hunt`, CodeSpec submits `code spec`, Agnostic loop submits `agnostic loop`.
- **FR-004**: The Execute button MUST call a Python delivery function. That is the same trigger shape Run uses: a Controls button calls Python. It is not the same destination. Run's functions install or query a loop on disk. Execute MUST NOT call those functions, including bug-hunt install. Execute's function MUST resolve a chat and submit the phrase there.
- **FR-005**: The title source MUST be Cursor's local composer headers in `%APPDATA%\Cursor\User\globalStorage\state.vscdb`, table `composerHeaders`, opened read-only (`mode=ro`). The display title is `value.name`. An empty name matches nothing. The chat id is `composerId`. Recency is `lastUpdatedAt`. A row is a draft when `value.isDraft` is true. Scope is the `workspaceId` column. Query that workspace id. Do not scan the whole `cursorDiskKV` table.
- **FR-006**: Scope MUST be the active linked project, the same folder Run uses (`linked_install_directory`). Find the `workspaceStorage/<id>/workspace.json` whose folder path resolves to that directory. Compare resolved paths, case-insensitive on Windows. Only headers with that `workspaceId` are candidates. Skip rows with column `isArchived` true and rows with column `isSubagent` true. Do not consider any other workspace, including another Cursor window on another project.
- **FR-007**: When more than one in-scope header shares the matched title, the script MUST choose the greatest `lastUpdatedAt`. Equal timestamps are `failed`. If that winner is a draft, the outcome is refused. Do not fall through to an older non-draft.
- **FR-008**: Hive's process MUST NOT call `submitChatMaybeAbortCurrent` itself. That function lives in the Cursor workbench. The delivery function writes `.hive/controls-execute/request.json` in the active repo with a new `nonce`, the `composerId`, and the `phrase`. The in-workbench submitter shipped with this feature reads that file and calls `submitChatMaybeAbortCurrent(composerId, phrase)` with force omitted. It writes `.hive/controls-execute/result.json` with the same `nonce` and `outcome` `sent` or `failed`. The delivery function waits up to 10 seconds for that nonce. No result is `failed`. The submitter MUST NOT open the desktop bridge socket, MUST NOT use the bridge bearer token, and MUST NOT call `composer.desktopBridge.sendMessage`. It MUST NOT paste or walk the accessibility tree.
- **FR-009**: `sent` is success only when the phrase is the user message in that chat and one pass starts. A pass has started when `composerData:<composerId>` in `cursorDiskKV` has `status` `generating` after the submit. The delivery function does not wait for the pass to finish. Bug hunt's pass is one read of `.cursor/commands/bug-hunt.md`. CodeSpec's pass is one read of `.cursor/commands/implementation-loop.md`. Agnostic loop's pass is one read of `.cursor/commands/agnostic-loop.md`. Phrase text with no generating status is `failed`, not `sent`.
- **FR-010**: Already generating MUST be reported, and nothing submitted, when either signal is true. First, `composerData:<composerId>` in `cursorDiskKV` has `status` `generating`. Else the selected loop's file on the active repo says a pass is in progress: Bug hunt `.hive/bug-hunt/continue.json` has `active` true, CodeSpec `.hive/implementation-loop/state.json` has `status` `running`, Agnostic loop `.hive/agnostic-loop/state.json` has `status` `running`.
- **FR-011**: Refused MUST be reported, and nothing submitted, when the winning header is a draft or the selected loop's command file is missing on the active repo. Bug hunt is installed when `.cursor/commands/bug-hunt.md` is a file. CodeSpec is installed when `.cursor/commands/implementation-loop.md` is a file. Agnostic loop is installed when `.cursor/commands/agnostic-loop.md` is a file.
- **FR-012**: The block MUST show sent, not found, refused, already generating, or failed. A failed or skipped submit MUST NOT read as sent.
- **FR-013**: Run MUST keep its current behavior: the selected command's local gate on the active linked repo.
- **FR-014**: Resolve and submit MUST go through one adapter interface. The Cursor script is the only adapter in this pass. A Claude adapter is out of scope and MUST NOT be implemented or called.
- **FR-015**: The name is the agent chat title from `value.name`. Execute MUST NOT target an editor file tab or the OS window title.

### Key Entities

- **Controls block**: One loop, one command, one tab name, Run, and Execute. The tab name is per block.
- **Composer header**: One row in `composerHeaders`. Title, composer id, workspace id, update time, archived, subagent, draft.
- **Chat-target adapter**: Given a display name, an active repo, and a phrase, returns one outcome.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In a test with two in-scope headers of the same title, Execute selects the later `lastUpdatedAt` 1 time out of 1 and submits that composer id with the loop phrase.
- **SC-002**: For each of the 3 loops, the submitted text equals that loop's start phrase, and that composer's status becomes `generating`. The Command label is not part of the text. The pass does not have to finish.
- **SC-003**: Each of the 4 non-sent outcomes (not found, refused, already generating, failed) appears as its own block message, and none of them is the sent message.
- **SC-004**: A Controls test can complete Execute with a fake adapter and 0 reads of `state.vscdb` and 0 composer submits inside the button handler.
- **SC-005**: A header whose workspace is not the active linked project is never the submit target, including when its title matches and its `lastUpdatedAt` is later.

## Assumptions

- The host window is the existing Hive Planner Controls tab on Windows.
- Title match is trim plus case-insensitive equality.
- Execute submits the phrase. It does not leave the text unsent, and it does not ask the user to press Enter in the IDE.
- The tab name lives on the block for as long as the other block fields do. This pass does not add a new settings file.
- `state.vscdb` is read to resolve headers. The write is the in-workbench submitter reacting to `request.json`. The Hive process does not call the workbench function itself.
- Claude and any non-Cursor IDE are out of scope for this pass. The adapter interface is the only preparation for them.

## Overlap with another feature

Start and feature switch go through the implementation loop's file-overlap gate ([implementation-loop R11](../implementation-loop/spec.md)). The paths this feature declares are the File targets table in [plan.md](./plan.md). A shared path with the feature already in the loop blocks start until Controls **Allow overlap** is checked. Force feature and Allow dirty start do not clear that block.

Those declared paths do not intersect lavd-resize-scheduler's paths (`src/hive_planner/lavd_resize.py`, `tests/test_lavd_resize.py`). This gate would not have stopped the switch off that blocked loop. The blocked status and the dirty tree remain separate gates.

## Decisions that close the earlier holes

- **Title source:** `composerHeaders` in Cursor's `state.vscdb`, as above. Not the desktop bridge thread list.
- **Write path:** `request.json` in the active repo, then the in-workbench submitter calls `submitChatMaybeAbortCurrent` for that composer id and writes `result.json`. Hive waits 10 seconds. The desktop bridge server, its token, paste, and the accessibility tree stay forbidden. Hive does not call the workbench function directly.
- **Scope:** Active linked project only. Archived and subagent rows are not candidates.
- **Already generating and refused:** Defined in FR-010 and FR-011. They are not names for the agent to invent.
- **Run's call shape:** Button calls Python. Execute does not call Run's install or gate functions.
