<!-- AUTO-SYNC: from docs/specs/Voice_Bot/spec.md -->

# Spec seed: Voice_Bot

# Spec: Voice_Bot

**Hook:** `workflow.blueprint_first`, `voice.experience`, `integration.strategy`, `agent.handoff`, `agent.sessions`, `agent.events`, `agent.permissions`, `voice.interruption`, `voice.results`, `editor.context`, `cursor.native_chat`, `cursor.acp`, `security.boundaries`, `resource.constraints`, `research.capabilities`, `change.validation`  
**Status:** draft (gap pass and fix pass applied 2026-11-09; 4-loop gap cascade and 9-second pause rule defined in [plan.md](./plan.md#gap-cascade-4-loops-9-second-pauses); provisional defaults marked)  
**Delta:** [Voice_Bot.md](../../delta/20_micro/Voice_Bot.md)  
**Rosetta:** [Planning Rosetta Stone](../../planning-rosetta-stone.md)

<!-- ROSETTA-NAV -->

## Agent navigation (Rosetta Stone)

Load [`docs/planning-rosetta-stone.md`](../../planning-rosetta-stone.md) (`planning.rosetta`) before implementation.

- **Delta micro:** [`Voice_Bot.md`](../../delta/20_micro/Voice_Bot.md)
- **Plan:** [`plan.md`](./plan.md)
- **Tasks:** [`tasks.md`](./tasks.md)
- **Primary hooks:** same canonical set as the header **Hook** line (mirrored in plan.md, tasks.md, and the delta micro brief)
- **Tertiary metatags:** `[HOOK:*]` blocks in `context-library/sources/imported/Mushi AI_Cursor a.md` (decompress via table below; do not treat PRIMARY FILES paths inside tertiary hooks as repo truth)

## Goal

Build Voice_Bot as a HIVE Code Planner feature. HIVE owns the voice-session state, cartridge-aware context, task routing, permissions, and evidence model; external voice and coding providers are adapters. The feature can discuss the code in view, delegate bounded coding work, and speak results grounded in actual agent evidence. **Dictation plus read-aloud alone does not satisfy the product goal** (`voice.experience`); continuous delegation with async coding and grounded progress is required.

## User Scenarios & Testing

### User Story 1 — Conversational inspection (Priority: P1)

As a developer, I can ask about the selected code and receive an answer grounded in the current workspace and selection.

**Independent Test:** Submit a read-only question against a selected function and verify the response contains the intended workspace and selection context without edits.

### User Story 2 — Delegated coding (Priority: P1)

As a developer, I can give a coding instruction without ending the voice session, while the coding agent works independently.

**Independent Test:** Start one coding task, ask a follow-up while it runs, and verify the task remains correlated to the same session.

### User Story 3 — Safe control (Priority: P1)

As a developer, I can approve, deny, interrupt, or explicitly cancel work with distinct outcomes.

**Independent Test:** Deny one permission, interrupt playback, and cancel one task; verify each produces a different recorded state.

### User Story 4 — Truthful results (Priority: P1)

As a developer, I hear progress and completion claims only when the bridge has corresponding evidence.

**Independent Test:** Complete a task with tests not run and verify the spoken result does not claim that tests passed.

### User Story 5 — HIVE-aware planning handoff (Priority: P2)

As a developer, I can speak about the active HIVE feature and have Voice_Bot load the correct cartridge, Rosetta hooks, spec, plan, and tasks before delegating work.

**Independent Test:** With `Voice_Bot` active, ask what the current acceptance criteria are; the answer cites the active spec without bypassing Spec Kit artifacts.

## Requirements

### R1 — HIVE-owned session lifecycle

HIVE shall track voice-session start, active, interrupted, and ended states. Ending voice audio shall not silently cancel an unrelated coding task.

### R2 — Cartridge-aware context

Each delegated turn shall resolve context through the active HIVE cartridge and bind to a snapshot containing workspace, file, selection, document version, dirty state, diagnostics, and the user instruction. When a cartridge is active, the snapshot shall record cartridge id and source excerpt ids; when none is active, it records `cartridge_id: null`. Secrets shall be excluded before any provider call. Oversized content is truncated under R21 with an explicit `truncated` flag; it is never silently dropped. Secret detection uses a filename deny-list (`.env*`, `*.pem`, `*.key`, `id_rsa*`, `credentials*`) and a content check with provisional patterns (tested in T014): `sk-[A-Za-z0-9]{20,}`, `ghp_[A-Za-z0-9]{36}`, `AKIA[0-9A-Z]{16}`, `-----BEGIN [A-Z ]*PRIVATE KEY-----`, and `(?i)(api[_-]?key|token|secret|password)\s*[:=]\s*\S{16,}`. A match excludes the content and records `excluded: secret`. Binary and unsaved content record `excluded: binary` or `excluded: unsaved`.

### R3 — Provider adapters and narrow delegation

HIVE shall expose provider-neutral bounded operations for task submission, follow-up, status, diff, history, and cancellation. Cursor, ACP, Moshi, Pipecat, MCP, or other providers shall connect through adapters. The voice controller shall not receive unrestricted coding-agent shell access.

### R4 — HIVE session ownership

HIVE shall own the mapping between voice session, cartridge, context snapshot, coding task, and provider session. Native Agent integration is preferred only after supported submission and targeting are verified. Otherwise, HIVE shall use an explicitly owned persistent ACP session and identify it as separate.

### R5 — Asynchronous conversation

The voice session shall remain usable while a coding task runs. Initially, one coding turn per session shall be active; follow-ups shall queue until concurrent steering is verified. The queue is FIFO with a default depth of 5 (provisional). A follow-up beyond that depth is rejected with a spoken notice and creates no task. Queued items are held while a task is `awaiting_approval`. Queue entries are persisted in `.hive/voice-bot/state.json` as `{queue_id, session_id, task_id, text, state}`. `state` is one of `queued`, `held` (the active task is `awaiting_approval`), `dispatched`, or `discarded` (session ended before dispatch; see R26). A queue entry is not a task and carries no `task_id` until it is dispatched.

### R6 — Permissions

Writes, commands, and other consequential actions shall require explicit approval bound to the request id, task, workspace, action, and arguments. Denial or timeout shall prevent execution. The approval timeout defaults to 120 seconds (provisional). A spoken approval is accepted only when it names the action of the pending request and matches its visible approval prompt; ambient or unrelated speech is ignored. Approval replies route to the pending request, never to the follow-up queue.

Approval requests have three kinds: `write_or_command`, `plan`, and `question`. All three use the R20 `awaiting_approval` transition and bind to one request id. A spoken answer to a `question` is an answer, not an approval; it is recorded as `answered` with its text and returns the task to `running`. A `question` reply is accepted when it is non-empty and arrives while that question's request id is the session's pending request; it does not need the `approve`/`deny` tokens. An empty or punctuation-only reply re-prompts and is not recorded as an answer. A `plan` approval is recorded as `approved` with the plan text as the bound action and returns the task to `running`. For all three kinds, a request not answered within the approval timeout is recorded as `timed_out`, nothing executes, and the task returns to `running`. Spoken matching is exact: the reply must contain the visible action label (case-insensitive) and an explicit yes or no (`approve`/`deny`). Ambiguous or partial matches re-prompt and never approve. Single-speaker use is assumed; the approval prompt is the authority, not the audio. `agent` mode is rejected with a spoken notice until G6 closes; `ask` and `plan` modes make no writes.

### R7 — Interruption and cancellation

Stopping playback shall not cancel coding. Coding cancellation shall be explicit, report requested and acknowledged states separately, and shall not claim rollback. Cancellation moves a task to `cancel_requested`, then to `cancelled` when acknowledged or `failed` (reason recorded) when the provider does not acknowledge (see R20).

### R8 — Grounded results

The bridge shall separate full written output from short spoken updates. A completed protocol turn shall not be treated as task success; test status shall come from actual test evidence. Test status has four states: `passed` (a recorded test command with exit code 0 in this task's evidence), `failed` (recorded non-zero exit), `not_run` (the task's evidence record is present and readable and contains no test command), and `unknown` (evidence record missing, unreadable, or unparsable). A missing record never maps to `not_run`. Spoken test claims map only from these states: `passed` may be said as passed; `not_run` must be said as "tests were not run"; `failed` and `unknown` must be said as stated.

### R9 — Recovery

The system shall correlate task, tool-call, protocol-request, session, and context identifiers. Retries, disconnects, timeouts, and shutdown shall not duplicate work or lose the last known outcome.

### R10 — Voice backend boundary

Speech transcription, tool selection, and external-result narration shall be validated independently. If Moshi cannot reliably perform a function, the implementation shall use an explicit adapter or hybrid speech path. Dedicated STT (R12) is an adapter slot; no STT provider is claimed until T013 records a verified provider in the evidence register.

### R11 — Model-agnostic HIVE orchestration

HIVE orchestration shall remain decoupled from any single voice or coding model. Replacing Moshi, Pipecat, Grok reference, or a Cursor transport shall not require rewriting session, task, permission, or evidence contracts.

### R12 — Component ownership

| Component | Owner | Responsibility |
|---|---|---|
| Dedicated STT | Voice adapter | Produce the verified user instruction |
| Voice conversation layer | Voice adapter (replaceable) | Audio session and conversational UX |
| HIVE Voice_Bot core | HIVE | Cartridge context, intent routing, task state, permissions, evidence |
| Editor integration | Extension adapter | Context snapshots, visible approvals, navigation |
| Coding execution | Coding adapter | Repository analysis, edits, commands, tests |
| Spoken output path | HIVE + voice adapter | Short, grounded summaries from recorded evidence |

The voice layer shall not claim completion unless HIVE has a matching successful outcome record.

### R13 — Asynchronous provider tools

Long-running coding operations shall use provider-neutral non-blocking semantics: user speech interruption must not implicitly cancel the coding task. Pipecat adapters realize this as `cancel_on_interruption=False`; other adapters must provide an equivalent. Results return when the provider finishes.

### R14 — Dual-channel results

HIVE shall persist `spoken_update` and `written_result` separately. `spoken_update` may be emitted only from normalized task evidence. Optimistic speech when work merely starts is forbidden. The only speech allowed at submission is an acknowledgment of acceptance ("task accepted, running"); it makes no claim about progress or outcome. Progress speech is limited to `task.awaiting_approval`, `task.completed`, `task.failed`, and at most one `task.progress` update per 30 seconds (provisional). A `spoken_update` is capped at 300 characters (provisional); longer evidence is shortened for speech, and the full text stays in `written_result`.

### R15 — Evidence register

Capability claims (native chat submission, ACP schemas, MCP directionality, Moshi grounding) shall be recorded in `docs/specs/Voice_Bot/evidence-register.md` with pinned versions, test method, pass/fail, and date before they appear in acceptance text.

### R16 — Cartridge-sourced planning loop

When tertiary research changes, HIVE shall refresh sourcing, re-emit the cartridge, classify sources without blind promotion, and merge distilled behavior into this spec before implementation claims advance. Tertiary excerpts (`cartridge/source-context.md`) shall inform adapters and build order but shall not override Delta, spec, plan, or tasks.

### R17 — Normalized event contract

HIVE shall map provider-specific messages to normalized events. Application event names (not provider literals) shall include: `transcript.final`, `context.snapshot`, `task.started`, `task.progress`, `task.awaiting_approval`, `task.completed`, `task.failed`, `speech.interrupted`. Raw provider payloads shall be retained on the task record for diagnosis. UI and spoken summaries shall consume normalized events, not raw streams.

### R18 — Bounded tool surface

The voice controller shall expose only narrow, validated tools. **Coding:** `submit_coding_task`, `task_status`, `task_diff`, `queue_follow_up`, `cancel_coding_task`. **Editor:** `get_context_snapshot`, `show_diff`, `navigate_to`. Each invocation shall bind `workspace` and `context_snapshot_id`; every call after submission also binds `task_id`. `submit_coding_task` is the only call that issues a `task_id`. It requires `mode` (`ask`, `plan`, or `agent`; `agent` is rejected under R6 until G6 closes) and a `client_request_id` generated by the voice adapter once per `transcript.final` event. A submit without `client_request_id` is rejected with `missing_client_request_id` and creates no task and no dedupe key. A retry with the same `(session_id, client_request_id)` returns the existing task and creates no second one. Unrestricted shell or filesystem tools shall not be exposed directly to the voice layer (`agent.handoff`, `security.boundaries`).

### R19 — Native chat investigation checklist (G1)

Before claiming native IDE handoff, HIVE shall record independent evidence for each question (`cursor.native_chat`): (1) supported submission of an external user turn, (2) supported targeting of the active conversation, (3) readable native progress/context, (4) replaceability of the native voice provider. Any unanswered question keeps the **labeled ACP fallback** as the coding session (`integration.strategy`). If ACP is also unavailable (for example, the `agent` binary is absent), no coding session exists: `submit_coding_task` returns `coding_unavailable`, and the voice layer says coding is unavailable. Nothing is labeled as a fallback that has not run.

### R20 — Task state machine

States: `submitted`, `running`, `awaiting_approval`, `cancel_requested`, `unknown`; terminal states: `completed`, `failed`, `cancelled`. `unknown` is non-terminal and is reachable only from provider disconnect or HIVE restart (R26).

- `submitted` → `running` when the provider session accepts the task; `submitted` → `failed` on submit error.
- `running` ⇄ `awaiting_approval` per approval request id.
- `awaiting_approval` → `running` on approval; on denial or timeout the action is recorded as `denied` or `timed_out`, nothing executes, and the task returns to `running`.
- `running` or `awaiting_approval` → `completed` or `failed` from provider evidence.
- `running` or `awaiting_approval` → `cancel_requested` → `cancelled` (acknowledged) or `failed` (not acknowledged; reason recorded).
- `submitted` → `cancel_requested` when cancel arrives before the provider accepts the task; then `cancelled` or `failed` as above.
- Provider disconnect from `submitted`, `running`, `awaiting_approval`, or `cancel_requested` → `unknown` (non-terminal; reason `provider_disconnected`). Reconnect with matching provider evidence returns the task to its prior state. No reconnect within 300 seconds (provisional) → `failed` with reason `provider_lost`. Nothing is re-submitted automatically.
- Playback interruption and call end are not transitions (R1, R7).

### R21 — Limits (provisional defaults; revise after G2 evidence)

- Instruction: 4,000 characters maximum. An over-limit instruction is rejected with a spoken notice; no task is created and nothing is silently truncated.
- Snapshot selection and file content: 64 KB maximum. Larger content is truncated with an explicit `truncated` flag, never silently.
- Approval timeout: 120 seconds.
- Follow-up queue depth: 5.
- `spoken_update`: 300 characters.
- Diff output (`task_diff`, `show_diff`): 256 KB maximum, with the same explicit `truncated` flag.
- Timeouts and limits above are read from one `voice_bot` config object (T001a; T001 did not create it). Each value must change observable behavior under test; none is hard-coded in a handler.

### R22 — Stale-context rule

Before any write, HIVE compares the snapshot's document version and dirty state with the live buffer. The check runs at submit and again at each write permission request, so a buffer that changes during an approval wait is caught at approval time. On mismatch the write is blocked, recorded as `stale`, and the user is told. HIVE does not reconcile automatically; the user may re-snapshot and resubmit. Provider-initiated writes are gated by the adapter: the provider session runs so that every write passes through `session/request_permission`, and the stale check runs at that request. A write without a matching permission request is a failed task with reason `unguarded_write`.

### R23 — Local security boundaries (`security.boundaries`)

HIVE shall enforce these boundaries for every voice, editor, and coding request:

- **Path validation:** every file path in a snapshot, tool argument, or diff request is normalized and must resolve inside the bound workspace root. A path that escapes the root (including via `..`, symlink, or absolute path) is rejected with reason `path_outside_workspace`; nothing is read or written.
- **Workspace restriction:** the voice controller and coding adapter operate only on the workspace bound to the session. Changing workspace requires a new session.
- **Local-service authentication:** a connection to the local voice or Cursor bridge service must present a per-session token generated by HIVE at start and stored under `.hive/voice-bot/`. A connection without a valid token is refused and creates no session.
- **Tool-argument validation:** each R18 tool validates its arguments against a declared schema (types, lengths, enumerated values, required binding fields) before dispatch. A failed validation returns a structured error and creates no task.
- **Command separation:** conversational text and model output are never converted into executable commands. Execution requires an R6 approval bound to the exact action and arguments.

Limits (R21) apply to all of the above. Each boundary is tested on the integrated path, not only by helper or string checks (T017).

### R24 — Measured latency and resource budget (`resource.constraints`)

HIVE shall measure, not assume, the end-to-end latency from `transcript.final` to `task.started` acknowledgment, the time to first `spoken_update`, and the process resource use of the voice service and the coding adapter. Targets are read from the `voice_bot` config object (R21), not hard-coded in a handler. Until T001a lands that object, tests use a test-owned placeholder budget that is not a product target. Until a baseline is measured on the pinned runtime, no numeric target is claimed; the first measurement is recorded in `docs/specs/Voice_Bot/evidence-register.md` with hardware, OS, and version. Hardware and model-size estimates are not promoted to fixed requirements (`resource.constraints`). Measurement is task T018.

### R25 — Call end during a pending approval

Ending the voice call does not cancel the task (R1). A pending approval stays visible in the editor, and its timeout still applies (R6). The outcome is recorded in `written_result` only. No speech is produced after the call ends.

### R26 — Restart and recovery

On HIVE restart, every task in `submitted`, `running`, `awaiting_approval`, or `cancel_requested` moves to `unknown` with reason `hive_restarted`, and any pending approval is recorded as `timed_out`. Queue entries in `dispatched` state are not re-sent. Entries in `queued` or `held` state become `discarded` unless their session resumes within the 300-second reconnect window (R20).

A restart-`unknown` task follows the R20 reconnect rule (provisional): matching provider evidence returns it to its last persisted non-`unknown` state, except that a pending approval stays `timed_out` and does not revive. No matching evidence within 300 seconds → `failed` with reason `provider_lost`. Nothing is re-submitted automatically.

Session end (provisional): when a voice session ends, its `queued` and `held` entries become `discarded` at once. The task itself continues (R1, R25), and no speech follows the call end. This is the session-end path that R5 `discarded` refers to.

### R27 — One pending approval per session

Because one coding turn is active per session (R5), a session has at most one pending approval. A second approval request while one is pending is refused by the broker with reason `approval_already_pending` and creates no action. A spoken approval reply that does not match exactly one pending request re-prompts (R6) and is never routed to the follow-up queue.

### R28 — Snapshot scope

Each session binds one workspace folder at start. In a multi-root workspace, that folder is chosen when the session starts; changing it requires a new session (R23). With no active editor, `get_context_snapshot` returns `file: null` with reason `no_active_file`, and a workspace-level instruction may still be submitted with `file: null`. Unsaved buffers are sent only as `excluded: unsaved`. Binary files are `excluded: binary`. Oversized files follow R2 truncation.

### R29 — Dedupe scope

The dedupe key `(session_id, client_request_id)` is scoped to one session. A retry after a HIVE restart (R26) with the same key returns the existing task in its recorded state, including `unknown`, and creates no task.

## Rosetta metatag decompression (tertiary → spec)

**Compression:** Upstream research stores concepts as `[HOOK:hook_id]` blocks (anchor summary + UNLOCKS). **Decompression:** Follow `planning.rosetta` → hook **UNLOCKS** → merge anchors into this spec and **tasks.md**; use `emit` retrieval when the full anchor is not in the active window. **Cartridge:** `source-context.md` is the compressed excerpt layer; this section is the decompressed index for Voice_Bot.

| HOOK_ID | Compressed anchor | Spec / task binding | Decompress (UNLOCKS) |
|---------|-------------------|---------------------|----------------------|
| `voice.experience` | Continuous voice; delegate without ending session; grounded progress | Goal, R5, R8, US1–US4 | `agent.handoff`, `voice.interruption`, `voice.results` |
| `integration.strategy` | Native-first probe; separate ACP fallback | R4, R19, non-goals | `cursor.native_chat`, `cursor.acp`, `cursor.mcp` |
| `cursor.native_chat` | Four separate native API questions | R19, G1, T012 | `research.capabilities`, `cursor.extension` |
| `cursor.mcp` | MCP tools ≠ push turn into chat; optional for Pipecat→ACP | R3, provider packaging, non-goals | `cursor.native_chat`, `voice.pipeline` |
| `cursor.acp` | Persistent JSON-RPC `agent acp`; bidirectional client | Runtime sequence, G2, T003–T004 | `agent.sessions`, `agent.events`, `agent.permissions` |
| `cursor.print_mode` | Smoke / constrained automation only | Optional dev check; not core architecture | `cursor.acp` |
| `cursor.extension` | Snapshots, approvals UI, voice lifecycle | R2, R6, T007 | `editor.context`, `agent.permissions` |
| `editor.context` | Versioned snapshot; stale detection; reconcile writes | R2, G4, acceptance #8 | `agent.handoff`, `change.validation` |
| `voice.pipeline` | Pipecat audio + tool dispatch; prove concurrency | R13, plan phase 4 | `voice.moshi`, `agent.handoff` |
| `voice.moshi` | Independent tests: STT, tools, result narration | R10, G3, T013 | `voice.results`, `research.capabilities` |
| `voice.grok_reference` | Behavioral reference only; not Cursor schema | Non-goals below | `voice.experience` |
| `agent.handoff` | Narrow coding + editor tools | R3, R18 | `agent.sessions`, `editor.context` |
| `agent.sessions` | Separate ids; queue; no “latest CLI = native chat” | R4, R5, R9 | `agent.events`, `cursor.acp` |
| `agent.events` | Normalized lifecycle events | R17, T005 | `voice.results`, `agent.permissions` |
| `agent.permissions` | Bound approvals; reader active; no ambient speech auth | R6, T008 | `cursor.extension`, `change.validation` |
| `voice.interruption` | Stop talk ≠ cancel task ≠ rollback | R7, T010, SC-003 | `agent.sessions` |
| `voice.results` | Milestone speech; no false test claims | R8, R14, G6 | `agent.events`, `voice.moshi` |
| `security.boundaries` | Path, workspace, local-service auth, tool-argument, and command separation | R18, R23, T017 | `agent.permissions`, `editor.context`, `resource.constraints` |
| `resource.constraints` | Measured latency and resource use; no unmeasured targets | R21, R24, T018 | `voice.moshi`, `voice.pipeline` |
| `research.capabilities` | Evidence register for consequential claims | R15, T002, G0–G6 | `cursor.native_chat`, `cursor.acp`, `voice.pipeline`, `voice.moshi` |

**Metatag mining procedure:** `ingest --embed` → `emit --feature Voice_Bot` → search tertiary for `## [HOOK:` → decompress row into spec → `spec-drift-check`. Use `translate --no-promote` for bulk classification only; hook blocks take precedence over un tagged prose.

## Cartridge ↔ sourcing feedback loop

**Rosetta hooks:** `planning.rosetta`, `compiler.pipeline`, `context.document_sourcing`, `research.capabilities`, `change.validation`

Primary truth stays Spec Kit (`spec.md`, `plan.md`, `tasks.md`, `evidence-register.md`). The cartridge is a compiled view; the context library is tertiary intake.

| Step | Command / artifact | Outcome |
|------|-------------------|---------|
| 1 — Ingest | `py -3.11 -m hive_planner ingest --embed` | Normalized chunks + embeddings in `context-library/` |
| 2 — Emit | `py -3.11 -m hive_planner emit --feature Voice_Bot --force-delta --emit-rules-seeds` | Refreshes `cartridge/source-context.md`, delta pack, `source-map.json` |
| 3 — Classify | `translate --input "<source.md>" --feature Voice_Bot --no-promote` | Draft holistic/macro/micro/memory/specseed only; writes `translator-status.json` |
| 4 — Merge | Human or agent review | Pull **build sequence**, ownership table, and hook anchors into this spec; update gates in `evidence-register.md` |
| 5 — Re-emit | `emit --feature Voice_Bot --force-delta` | Specseed mirrors curated spec; retrieval stays aligned |
| 6 — Drift | `spec-drift-check --feature Voice_Bot` | Blocks silent divergence from operational memory |

**Sourcing signals captured (2026-11-09 emit + translate):** hybrid retrieval surfaced `Mushi AI_Cursor a.md` (ACP bridge, Pipecat tools, extension limits) and HIVE transcript pages on **model-agnostic orchestration** (`session.transcript`). Translator pass: 29 holistic, 72 macro, 16 micro, 15 memory segments; 567 lines rejected as off-layer noise—use rejections as a guard against dumping research into requirements.

**Metatag pass (2026-11-09):** eighteen `[HOOK:*]` blocks in `Mushi AI_Cursor a.md` decompressed into R17–R19 and the hook index above; tertiary PRIMARY FILE paths inside those blocks are research placeholders only—not implementation targets unless copied here.

**Traceability:** `cartridge/mappings/source-map.json` links each cartridge file to Delta/spec layers. Delegated turns shall record cartridge id and source excerpt ids when present (see R2).

## Build order (evidence-gated)

Implementation follows **tasks.md** phases; each phase closes or records the matching decision gate before the next expands scope.

| Phase | Tasks | Gate focus | Build focus (from cartridge + sourcing) |
|-------|-------|------------|----------------------------------------|
| 1 | T001–T004, T001a | G0, G2 | HIVE contracts (`voice_bot.py`), evidence register, **ACP JSON-RPC client** (persistent `agent acp`, stdout pump, `session/update` routing), one **read-only** `session/prompt` in `ask` mode |
| 2 | T005–T007, T007a | G4 | Normalize session/task/event models in HIVE; **extension adapter** for `ContextSnapshot` (selection, version, dirty, diagnostics, size limits) |
| 3 | T008–T011 | G6, G3 | Permission broker (`session/request_permission`), queued follow-ups, interruption vs cancel, `spoken_update` / `written_result` from task evidence |
| 4 | T012–T020 (T016 G5; T017–T018 safety and latency; T020 edge rules) | G1, G3, G5, G6 (gates T015 edits) | Native-chat probe (T012) or labeled ACP fallback; Moshi/Pipecat grounding (T013); concurrency and disconnect tests (T014–T015) before writes |

**Provider packaging rule (sourced):** `vscode.cursor.mcp.registerServer()` and plugin-directory registration are valid for **shipping** Hive MCP and hooks; they are **not** a native Agent chat submit API. Coding transport for Voice_Bot is **ACP or verified native handoff**, not MCP alone (`evidence-register.md`).

## Runtime delegation sequence

Planning sequence from tertiary sources, reframed with **HIVE as the bridge** (the historical “bridge” layer is the HIVE Voice_Bot core plus adapters—not a separate ad hoc service):

```text
1. User speech → voice adapter (STT) → verified instruction text
2. HIVE resolves cartridge + Rosetta hooks → ContextSnapshot (+ optional feature Q&A from spec/plan/tasks)
3. Voice controller calls bounded submit_coding_task(instruction, snapshot, mode=ask|plan|agent)
4. HIVE returns task_id + running immediately (SC-007); voice session stays active (R5)
5. Coding adapter (ACP session/new + session/prompt) runs; stdout reader processes session/update
6. HIVE task log records chunks, tool events, permissions, stopReason — not spoken verbatim
7. On milestone evidence → short spoken_update; on completion → written_result + grounded summary
8. User may converse or queue follow-ups; one active coding turn until G5 proven
```

**ACP transport shape (documentation-level until G2 closes):** newline-delimited JSON-RPC on stdio to `agent acp`; initialize → authenticate → `session/new` with repo `cwd` → `session/prompt`; handle `session/request_permission`, `session/cancel`, and Cursor extension methods without blocking the reader. The ACP session id is **separate** from the IDE’s open Composer tab (R4, non-goals).

**Pipecat integration boundary (when voice adapter uses Pipecat):** long-running tools use `cancel_on_interruption=False` (R13); handler returns structured status to `result_callback`; voice model does not narrate Cursor output until HIVE normalizes task evidence (R10, `voice.results`).

**Repo layout target (HIVE-owned vs adapters):**

| Path (planned) | Owner | Role |
|----------------|-------|------|
| `src/hive_planner/voice_bot.py` | HIVE | Session, snapshot, task evidence, state persistence |
| `src/hive_planner/voice_acp.py` (T003) | HIVE | ACP subprocess, reader loop, disconnect detection |
| Voice / Pipecat service (external) | Voice adapter | Audio, STT, tool surface |
| Cursor extension (future) | Editor adapter | Snapshots, visible approvals |
| `agent acp` | Cursor CLI | Coding execution transport |

## Decision gates (from cartridge / Rosetta)

| Gate | Required evidence | If not demonstrated |
|---|---|---|
| G0 — API availability | Pinned versions and reproducible checks | Do not implement from historical snippets alone |
| G1 — Native conversation | Supported submit/target into native Agent chat | Label limitation; use explicit ACP fallback |
| G2 — Coding transport | Read-only task, follow-up, updates, failure handling (evidenced by T004 output, not by T003 code alone) | Keep edits disabled; AC 1–4 stay open; offline ACs (15–18) can still close |
| G3 — Voice grounding | Correct STT, tool choice, external-result narration | Hybrid speech path or block feature |
| G4 — Editor integrity | Unsaved context, stale detection, visible diffs | Block conflicting writes |
| G5 — Concurrent experience | Useful conversation during coding; correct interruption | Do not claim Grok-equivalent UX |
| G6 — Safe execution | Bound approvals, cancellation, dedupe, evidence-backed speech | Remain read-only |

## Non-goals

- Undocumented replacement of Cursor’s native voice provider.
- UI automation or simulated typing into the native Agent chat.
- Claiming that ACP automatically attaches to the open IDE chat.
- Enabling production edits before read-only transport, approval, and stale-buffer tests pass.
- Treating proposed Grok-style tool names or public Grok API behavior as recovered Cursor internal schemas (`voice.grok_reference`).
- Using CLI print/headless mode as a substitute for full ACP session, permission, and cancellation semantics (`cursor.print_mode`).
- Treating ambient or unrelated speech as permission approval (`agent.permissions`).
- Equating MCP tool registration with coding-session attachment or native chat submit (`cursor.mcp`).

## Success Criteria

- **SC-001:** A read-only contextual question returns the selected workspace context with no file changes.
- **SC-002:** A coding task remains correlated to one voice session and emits progress plus a final result.
- **SC-003:** Playback interruption does not change coding-task state.
- **SC-004:** Permission denial prevents the requested write or command.
- **SC-005:** Spoken claims match recorded task and test evidence.
- **SC-006:** Native handoff is reproduced on a pinned version or the separate ACP fallback is clearly identified.
- **SC-007:** A coding task returns `task_id` plus running status before work completes and conversation remains available.
- **SC-008:** `spoken_update` and `written_result` differ and both trace to the same task evidence record.
- **SC-009:** Active feature questions resolve through HIVE cartridge/spec context without inventing requirements.
- **SC-010:** Task lifecycle transitions emit the normalized events in R17; spoken updates cite `task.progress` or `task.completed` evidence, not raw provider tokens.

- **SC-011:** Each R20 transition is recorded, and `cancel_requested` and `cancelled` are separate records.
- **SC-012:** A retried submit with the same `client_request_id` returns the same `task_id` and creates no second task.
- **SC-013:** Spoken test claims match the R8 test-state mapping (`passed`, `failed`, `not_run`, `unknown`) for every completed task in the test run.

## Deployment readiness

Verdict (2026-11-09): **NOT READY**. The spec is `draft`. Acceptance criteria 1–21 are not all met; only T001, T001a, T002, and T019 are complete.

Verified 2026-11-09 (`pytest tests/test_voice_bot.py tests/test_voice_bot_config.py tests/test_voice_bot_evidence_register.py tests/test_spec_drift_specseed.py` → 24 passed; `agent --version` → `2026.11.05-86047df` on dev host). The passing tests cover contracts, config, and the evidence register only. The following are not implemented in `src/hive_planner/voice_bot.py`:

| Blocker | Spec rows | Task | Acceptance |
|---|---|---|---|
| ACP adapter + read-only prompt not implemented; G2 and G5 cannot be proven | R19, R24 | T003, T004 | 3, 4, 10 |
| No `submit_coding_task` / `client_request_id` dedupe | R18, R29, SC-012 | T006, T009 | 12 |
| No secret exclusion (`excluded: secret`) | R2 | T014 | 15 |
| No bounded tool registry or schema validation | R18, R23 | T006, T017 | 16, 19 |
| No path, workspace, or local-service token checks | R23 | T017 | 19 |
| No permission broker, approval kinds, or exact-match replies | R6, R27 | T008 | 7 |
| No FIFO follow-up queue or restart/call-end recovery | R5, R25, R26 | T009, T020 | 4, 21 |
| No stale-buffer check before writes | R22 | T007, T014 | 8 |
| No editor extension capture | R2, R28 | T007a, T007 | 1, 2 |
| Gates G1, G3, G5, G6 are not closed | R4, R10, R15 | T012, T013, T016 | 10, 11 |

Work is not started on T003 until G2 evidence exists (plan.md, tasks.md). The read-only mode in R6 and T015 stays in force.

Exit criteria for any deployment claim (all must hold):

1. Gates G1, G2, G3, G5, and G6 are `pass` in `evidence-register.md`, or the matching fallback is labeled and accepted (R4, R19). G4 closes after T007 and T014.
2. T003–T018 and T020 are complete, each with the named test file from `tasks.md` run through the integrated path (not string or mock checks).
3. Acceptance 1–21 and SC-001–SC-013 each cite a passing test or recorded evidence.
4. `agent --version` is recorded in `evidence-register.md` on the pinned runtime (G2).
5. The Integration wiring audit in `tasks.md` is checked, with the chain traced from voice event to written result.
6. `emit --feature Voice_Bot --force-delta` and `spec-drift-check --feature Voice_Bot` pass after any spec change.

Until these hold, the feature stays in read-only mode (R6, T015) and no spoken or written claim may describe it as deployed.

## Assumptions

- The initial implementation runs locally in one workspace.
- Cursor ACP, extension APIs, Pipecat, and Moshi capabilities are version-dependent and require evidence.
- The voice service does not automatically gain access to the native IDE chat.
- One coding turn per owned session is serialized until concurrent steering is verified.
- Phase 1 uses typed instruction text. Spoken input and STT are validated in T013, so STT is not a Phase 1 dependency.

## Acceptance criteria

1. Read-only contextual question succeeds with the intended selection. Phase 1 (T004) proves this with an explicit file path and instruction text; selection-based acceptance closes with T007 in Phase 2.
2. A second question retains the owned coding-session context.
3. A coding task emits observable progress and a final result.
4. Conversation continues while the task runs.
5. Speech interruption leaves coding state unchanged.
6. Explicit cancellation reports accurate cancellation semantics.
7. Permission denial prevents the requested action.
8. Stale editor context blocks conflicting writes (R22).
9. Spoken claims match recorded task and test evidence (SC-005).
10. Native handoff is verified or the ACP fallback is clearly labeled (SC-006).
11. Decision gates G0–G6 are recorded in the evidence register before the gate is claimed closed.
12. Submitting a coding task returns immediate `task_id` acceptance without ending the voice session.
13. Normalized events (R17) appear in task state for start, progress, approval wait, completion, and failure.
14. G1 checklist (R19) is recorded in the evidence register before native handoff is claimed.
15. Secret-bearing files or selections are excluded from the snapshot and marked `excluded: secret` (R2).
16. The voice controller tool registry exposes only the R18 tool names; a probe for any shell or filesystem tool fails (R18).
17. Replacing the voice adapter with a second stub adapter leaves session, task, permission, and evidence contracts unchanged (R11).
18. An over-limit instruction, snapshot, or diff is rejected or flagged `truncated`, and a test asserts the flag (R21).
19. Path escape, unauthenticated local-service connection, and invalid tool arguments are each refused with a recorded reason and create no task or write (R23, T017).
20. Measured latency and resource use are recorded in the evidence register on the pinned runtime, and the config object drives any target checked by a test (R24, T018).
21. Edge-case rules R25–R29 each have an integration test through the submit and approval paths (T020, `tests/test_voice_bot_edges.py`).

## Risks and open questions

- Supported native-chat turn submission and targeting are unresolved (G1 blocked; T012).
- Cursor ACP methods and schemas require validation against the installed `agent` binary (G2 blocked; CLI pinned `2026.11.05-86047df`; T003–T004 open as of 2026-11-09).
- Moshi’s structured tool calling and external-result grounding are unresolved (G3 blocked; T013).
- Editor APIs may expose MCP/plugin registration without native-chat control—do not treat MCP enablement as coding-session attachment.
- Cartridge `translate` output is draft; promoting specseed without merge would overwrite curated requirements (use `--no-promote` + manual merge per R16).
- Whether an MCP “listening” tool blocks concurrent coding conversation is unresolved (`cursor.mcp`); validate before in-chat microphone loops. Owner: T016.
- Full-duplex Moshi audio does not imply reliable STT, tool calls, or external-result narration (`voice.moshi`).

## Validation

Start read-only. Record pinned versions and results in an evidence register. Validate native handoff, ACP transport, editor snapshots, permissions, interruption/cancellation, recovery, and spoken-result grounding before enabling edits. When mining tertiary sources, decompress `[HOOK:*]` blocks through the hook index above before adding acceptance text. Each acceptance criterion (15–21) and SC-011, SC-012, and SC-013 must have a named test in `tests/test_voice_bot*.py` that exercises the integrated path, not only a string or mock check.
