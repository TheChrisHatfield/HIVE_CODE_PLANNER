# Spec: Voice_Bot

**Hook:** `workflow.blueprint_first`, `voice.experience`, `integration.strategy`, `agent.handoff`, `agent.sessions`, `agent.events`, `agent.permissions`, `voice.interruption`, `voice.results`, `editor.context`, `cursor.native_chat`, `cursor.acp`, `security.boundaries`, `resource.constraints`, `research.capabilities`, `change.validation`  
**Status:** active (R33 latch enabled 2026-11-12; Acceptance 1–22 mapped in [acceptance-crosswalk.md](./acceptance-crosswalk.md); speech path remains `typed_instruction` until STT is pinned)  
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

## Feature scope and component relationship (2026-11-14)

- **Voice_Bot is the feature.** It is the whole voice-driven coding capability delivered inside HIVE Code Planner.
- **Moshi is a component of Voice_Bot.** It is the primary conversation layer (R36, R37): audio in, transcription, and speech out, with full-duplex listening and speaking. Moshi is not a separate feature and is not a replacement for Voice_Bot.
- **HIVE Code Planner is the host.** It owns the session, cartridge context, task routing, permissions, and evidence (R1, R4, R12). Moshi cannot execute tools or claim results on its own.
- **Other components** (Pipecat TTS for `speak()` per R32/OD-2, the faster-whisper fallback per T042, ACP coding transport) are also adapters inside Voice_Bot.
- **Reading rule:** when a requirement says "Voice_Bot," it covers Moshi and its adapters. When it says "Moshi," it refers only to the conversation component. Do not treat Moshi as a standalone product.

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

HIVE shall track voice-session start, active, interrupted, and ended states. Session state transitions (voice layer only; task states follow R20): `active` → `interrupted` when playback is stopped via `interrupt_playback` (R7). `interrupted` → `active` on the next `submit` or `queue_follow_up` in the same session. `interrupted` → `ended` on `end_call`. Playback interruption and call end are not task transitions (R20). Ending voice audio shall not silently cancel an unrelated coding task.

### R2 — Cartridge-aware context

Each delegated turn shall resolve context through the active HIVE cartridge and bind to a snapshot containing workspace, file, selection, document version, dirty state, diagnostics, and the user instruction. When a cartridge is active, the snapshot shall record cartridge id and source excerpt ids; when none is active, it records `cartridge_id: null`. The editor adapter records `selection` as `null` or `{text, start, end, truncated, bytes}` with 1-based line and column. HIVE `ContextSnapshot.selection_text` is `selection.text`, or empty when `selection` is `null`. T008 maps the editor object (including document version, dirty state, and diagnostics) into that snapshot on submit. Secrets shall be excluded before any provider call. Oversized content is truncated under R21 with an explicit `truncated` flag; it is never silently dropped. Secret detection uses a filename deny-list (`.env*`, `*.pem`, `*.key`, `id_rsa*`, `credentials*`) and a content check with provisional patterns (tested in T014): `sk-[A-Za-z0-9]{20,}`, `ghp_[A-Za-z0-9]{36}`, `AKIA[0-9A-Z]{16}`, `-----BEGIN [A-Z ]*PRIVATE KEY-----`, and `(?i)(api[_-]?key|token|secret|password)\s*[:=]\s*\S{16,}`. A match excludes the content and records `excluded: secret`. Binary and unsaved content record `excluded: binary` or `excluded: unsaved`.

### R3 — Provider adapters and narrow delegation

HIVE shall expose provider-neutral bounded operations for task submission, follow-up, status, diff, history, and cancellation. Cursor, ACP, Moshi, Pipecat, MCP, or other providers shall connect through adapters. The voice controller shall not receive unrestricted coding-agent shell access.

### R4 — HIVE session ownership

HIVE shall own the mapping between voice session, cartridge, context snapshot, coding task, and provider session. Native Agent integration is preferred only after supported submission and targeting are verified. Otherwise, HIVE shall use an explicitly owned persistent ACP session and identify it as separate.

### R5 — Asynchronous conversation

The voice session shall remain usable while a coding task runs. Initially, one coding turn per session shall be active; follow-ups shall queue until concurrent steering is verified. The queue is FIFO with a default depth of 5 (provisional). A follow-up beyond that depth is rejected with a spoken notice and creates no task. Queued items are held while a task is `awaiting_approval`. Queue entries are persisted in `.hive/voice-bot/state.json` as `{queue_id, session_id, text, state}`. `state` is one of `queued`, `held` (the active task is `awaiting_approval`), `dispatched`, or `discarded` (session ended before dispatch; see R26). A queue entry is not a task. The `task_id` field is absent until dispatch; after dispatch the same record includes `task_id`.

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

Before claiming native IDE handoff, HIVE shall record independent evidence for each question (`cursor.native_chat`): (1) supported submission of an external user turn, (2) supported targeting of the active conversation, (3) readable native progress/context, (4) replaceability of the native voice provider. Any unanswered question keeps the **labeled ACP fallback** as the coding session (`integration.strategy`). When G1a–G1d are recorded `fail` on a pinned version and G2 has run, G1 closes as `labeled_acp_fallback`; native handoff is not claimed. If ACP is also unavailable (for example, the `agent` binary is absent), no coding session exists: `submit_coding_task` returns `coding_unavailable`, and the voice layer says coding is unavailable. Nothing is labeled as a fallback that has not run.

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
- **Local-service authentication:** a connection to the local voice or Cursor bridge service must present a per-session token generated by HIVE at start and stored as `.hive/voice-bot/bridge-token`. The service is loopback HTTP only (`127.0.0.1`). A connection without a valid token is refused with HTTP 401, reaches no runner, and creates no session. Documented routes: `GET /v1/approval`, `POST /v1/reply`, `POST /v1/submit`, `GET /v1/submission`, `GET /v1/task`, `GET /v1/editor`, `POST /v1/editor`, `POST /v1/editor/show_diff` (queues the R18 `show_diff` editor action for a completed `task_id`; the extension opens it through `GET /v1/editor`; T043), `POST /v1/editor/navigate` (queues the R18 `navigate_to` editor action for a workspace-relative `file_path` bound to `context_snapshot_id`; R23 path check applies). A stale or mismatched `request_id` on reply is HTTP 409 and executes nothing. Endpoint discovery is `.hive/voice-bot/bridge.json` (`host`, `port`). Every documented route runs the declared R18 schema before dispatch (T017).
- **Tool-argument validation:** each R18 tool validates its arguments against a declared schema (types, lengths, enumerated values, required binding fields) before dispatch. A failed validation returns a structured error and creates no task.
- **Command separation:** conversational text and model output are never converted into executable commands. Execution requires an R6 approval bound to the exact action and arguments.

Limits (R21) apply to all of the above. Each boundary is tested on the integrated path, not only by helper or string checks (T017).

### R24 — Measured latency and resource budget (`resource.constraints`)

HIVE shall measure, not assume, the end-to-end latency from `transcript.final` to `task.started` acknowledgment, the time to first `spoken_update`, and the process resource use of the voice service and the coding adapter. Targets are read from the `voice_bot` config object (R21, T001a), not hard-coded in a handler. Until a baseline is measured on the pinned runtime, no numeric target is claimed; the first measurement is recorded in `docs/specs/Voice_Bot/evidence-register.md` with hardware, OS, and version. Hardware and model-size estimates are not promoted to fixed requirements (`resource.constraints`). Measurement is task T018.

### R25 — Call end during a pending approval

Ending the voice call does not cancel the task (R1). A pending approval stays visible in the editor, and its timeout still applies (R6). The outcome is recorded in the task's approval record (`approvals`, `approval`) only, not in `written_result`, because `written_result` holds the agent's own output text. No speech is produced after the call ends.

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

### R30 — Self-contained Voice_Bot deploy (Hive ships the voice stack)

A Voice_Bot deploy is self-contained: the operator does not hunt Moshi, Pipecat, or Cursor CLI as separate products. Hive core `dependencies` stay empty so non-voice installs stay small. The **`voice` extra** is the Voice_Bot pack: `moshi` and `pipecat-ai` are declared there. Install is:

```text
py -3.11 -m pip install -e ".[voice]"
py -3.11 -m hive_planner voice-bot ensure-runtime --install
```

`ensure-runtime` pip-installs any missing extra packages into that Python. Cursor `agent` is not a PyPI package; the same command reports the official installer (`irm 'https://cursor.com/install?win32=true' | iex` on Windows, `curl https://cursor.com/install -fsS | bash` elsewhere) and runs it only with `--install --install-agent`. `voice-bot status` reports each declared item as `installed` or not.

**Pack for other machines:** on a build host with network, run `py -3.11 -m hive_planner voice-bot pack --download-wheels`. That writes `.hive/voice-bot/deploy-pack/` (`manifest.json`, `requirements-voice.txt`, `INSTALL.md`, `hive-voice-bot-<version>.vsix`, `install-voice-bot.ps1`, optional `wheels/`). Copy the Hive repo and that folder to the target host; follow `INSTALL.md`: run `install-voice-bot.ps1` first (editor adapter), then pip online or offline `--find-links wheels`, then `ensure-runtime`.

Moshi is not treated as unsupported on Windows. The 2026-11-14 host check found `moshi` 0.2.13 importable with torch 2.5.0+cu124 and CUDA visible (R37 is the live gate, not this import). A failed pip install is recorded and the speech path stays `typed_instruction` until G3 evidence exists. Absence of `agent` after ensure-runtime still maps coding submit to `coding_unavailable` (R19). Presence of Moshi does not pin STT or close G3.

### R31 — Live G2 probe (operator login)

Fixture ACP turns never write G2 `pass`. `voice-bot live-prompt` is the only writer of a G2 live row. It runs one read-only `session/prompt` against the real `agent acp` child. Before that prompt it records `agent status` (or `CURSOR_API_KEY` present). If the CLI reports not logged in and no key is set, the command records G2 as `blocked` with that status text, creates no coding task, and must not claim pass. A logged-in prompt that returns a stopReason records G2 `pass` with CLI version, date, and stopReason in `evidence-register.md`. A logged-in prompt that errors records G2 `fail`. Tests without login assert `blocked` and that the evidence register is not flipped to pass.

### R32 — Spoken playback adapter (G3 hybrid)

`VoiceAdapter` shall expose `speak(text)` as well as `transcribe`. The typed adapter records `spoken_update` and performs no audio. When `pipecat` is importable, the Pipecat adapter must keep coding cancellation independent of playback interruption (R13 `cancel_on_interruption=False` or equivalent). `hybrid_speech_path()` stays `typed_instruction` until an STT provider is pinned in the evidence register (R10, T013). Installing Moshi or Pipecat does not close G3.

### R33 — G6 edits latch

`edits_enabled()` is true only when `docs/specs/Voice_Bot/evidence-register.md` records G6 as `pass` and `.hive/voice-bot/config.json` has `edits_enabled: true`. Either missing or false keeps production `agent` mode refused (R6, T015). Fixture permission tests do not write G6 `pass`. Live ACP permission evidence is recorded only by R34 before a human may set the config latch.

### R34 — Live G6 permission probe

Fixture ACP turns never write G6 `pass`. `voice-bot live-permission` is the only writer of a G6 live row. It runs one ACP session against the real `agent acp` child, prefers `agent` mode, and initializes with `clientCapabilities.fs` and `terminal` so the agent cannot self-write. Every `session/request_permission`, `cursor/create_plan`, `fs/write_text_file`, and `terminal/*` request is cancelled or errored so no file is written. After the first gated method is refused, HIVE sends `session/cancel` and stops the ACP child so a later self-write cannot create the probe file. Unknown server requests are JSON-RPC errors, not `result: null`. Before that session it records `agent status` (or `CURSOR_API_KEY` present). If the CLI reports not logged in and no key is set, the command records G6 as `blocked`, creates no coding task, and must not claim pass. A logged-in session that observes at least one of those gated methods and does not create the probe file records G6 `pass` with CLI version, date, and a summarized shape. A logged-in session that creates `.hive/voice-bot/g6-live-probe.tmp` without a gated method records G6 `fail` with `unguarded_write`. A logged-in session that observes a gated method and still creates that file records G6 `fail` with `unguarded_write`. A logged-in session that ends without a gated method and without that file records G6 `fail` with `no_permission_request`. Tests without login assert `blocked` and that the evidence register is not flipped to pass. Production `agent` mode stays refused until R33's config latch is also true. An empty `clientCapabilities` object is not used: that shape allowed a live self-write with no permission request.

### R35 — Live allowed-write probe (full `agent` mode)

R34 proves the gate refuses writes. R35 proves an allowed write reaches disk. `voice-bot live-write` is the only writer of an R35 live row. It runs one `agent`-mode task whose prompt explicitly instructs the agent to create `.hive/voice-bot/live-write-check.txt` containing a nonce generated by HIVE for that run. The prompt must name the file and the action; it must not describe the task as read-only. The command refuses to run unless `edits_enabled()` is true (R33). If it is false, the command records `blocked`, creates no coding task, and does not claim pass. It requires G6 `pass` in the evidence register first. Pass means the task completed, the file exists, and its content equals the nonce. Fail with `no_write` means the task completed and the file is missing or the nonce does not match. Fail with `agent_error` means the ACP session errored before completion. Each run records CLI version, date, task id, and the nonce hash, never the raw nonce. The probe does not change the G6 row, the R33 config, or any other gate. Tests use a fake ACP child and assert the `blocked` path without login and the `pass` and `no_write` paths with a fake agent. Edits remain on this host only after the operator sets the R33 latch. An R35 pass proves that an allowed write reaches disk on this host. It does not prove production permission safety: the production path is checked by the R22 `unguarded_write` gate, not by this probe.

### R36 — Moshi primary voice layer (direction 2026-11-14)

Moshi is the **primary communication tool** for Voice_Bot. It is the default speech adapter on every host where a Moshi server is running (Windows included; R37 defines the harness). Its reason for being primary is multi-duplex conversation: listening and speaking at the same time. Typed input is the fallback. Hive Code Planner is the add-on host. The coding, permission, and evidence rules (R2, R6, R18, R20, R22, R8, R14) still apply to every action Moshi triggers. Moshi supplies audio in, transcription, and speech out through the `VoiceAdapter` boundary (R11, R12).

- Moshi tool calls or intents are never executed directly. Each one must be mapped to an R18 tool call and pass R23 validation and R6 approval.
- Moshi narrates coding results only from `spoken_update` (R14). It does not narrate raw provider output.
- Moshi transcription is trusted only after a T013-style test (WER threshold and fixtures) is recorded in the evidence register. Until then the speech path on any host is `typed_instruction` or a labeled hybrid path (R10).
- Moshi's server takes audio in and returns audio plus text. It has no public text-injection input (checked in `moshi` 0.2.13 `server.py`). So HIVE's grounded `spoken_update` (R14) cannot be spoken verbatim through Moshi alone. Until a text-conditioned path is verified, `speak()` routes HIVE text to a separate TTS adapter (R32, Pipecat), and Moshi keeps the listen and converse role. **Decided (OD-2, T050, 2026-11-14):** `MoshiVoiceAdapter.speak()` delegates to the speech-out adapter (`speech_adapter` without Moshi: typed no-audio, or Pipecat when `audio_enabled` and importable). Moshi never speaks HIVE text. The Moshi text channel (`0x02`) is never used as evidence.
- Moshi's own replies are never evidence. Only HIVE `spoken_update` text (from R8 and R14 evidence) may describe task progress or results.
- **Spoken approval during a Moshi call (2026-11-14):** while one R6 request is pending, Moshi `0x02` text is an approval reply, not a new instruction. The launcher posts it to `POST /v1/reply` with the pending `request_id` and `task_id`. Matching uses the same exact-match rule as typed replies (R6). Unmatched text re-prompts and is not queued. Moshi text still cannot create a task and is not evidence. This path does not require `stt_provider`, a WAV, or a second Moshi handshake (the live call already holds the socket). The WER gate still blocks Moshi text as `submit_spoken` / `submit_coding_task`.
- **Decided (OD-1, revised 2026-11-14, operator choice "Hive owns the server"):** with `moshi_autostart` true (default) and a loopback `moshi_url`, the listen gate starts `python -m moshi.server --host H --port P` as a child process when no handshake answers, waits for the `0x00` handshake (`moshi_server_timeout` / `moshi_server_exited` on failure), and stops the child at interpreter exit (`hive_planner/voice_moshi_server.py`). Remote URLs are never started and report `moshi_unreachable`. The model still runs in the upstream server process, not in the HIVE process. HIVE never imports the model and never downloads weights; the upstream server fetches its own weights on first run. `moshi_autostart: false` restores operator-run behavior.
- Pipecat remains an optional playback adapter (R32). `cancel_on_interruption=False` still applies (R13).

### R37 — Moshi harness (live server, wire protocol)

The Moshi adapter talks to a Moshi server over websocket. It does not import the model into the HIVE process.

- **Endpoint:** `ws://<moshi_url host>:<port>/api/chat` (default `127.0.0.1:8998`, the `moshi.server` default). Config key `moshi_url` (string, default `ws://127.0.0.1:8998/api/chat`). Config key `voice_layer` (`moshi` or `typed`, default `moshi`).
- **Frames (binary):** first byte is the kind. Client sends `0x01` + Opus bytes (mic audio, streamed). Server sends `0x00` (handshake; the session is ready only after it arrives), `0x01` + Opus (model audio out), and `0x02` + UTF-8 text (model transcript). Any other kind is logged and ignored, never executed (R23 command separation).
- **Duplex:** mic frames keep flowing while output frames arrive. A dropped socket maps to the R20 provider-disconnect path, not to task cancel (R1, R7).
- **Gates:** `moshi_unreachable` if no handshake within a timeout; `moshi_unavailable` if the `moshi` package is not importable. Neither claims speech.
- **Handshake budget (2026-11-15, A3c):** `CONNECT_TIMEOUT_S` is 15 s for every Moshi connect (probe, listen gate, session). Reason: the local q8 server measured a 4.86 s handshake on 2026-11-15 (A3b), and the old 3 s budget refused a healthy server. A refused connection still fails immediately; the budget only bounds a hung one.
- **q8 autostart keys (2026-11-15, A3c, not yet live-proven):** `moshi_q8_weights`, `moshi_mimi_weights`, `moshi_tokenizer`, `moshi_model_config` must be set together or all null (`VoiceBotConfig` refuses a partial set). When set and `moshi_autostart` is true, Hive starts `scripts/moshi_q8_server.py` as the child instead of bare `python -m moshi.server`. The launcher carries the A3 spike fixes (streaming loader on device, Windows signal handler, eval/no-grad). The launcher still needs the operator env: `REFERENCE_ENCODER_URL`, `LLM_BASE_URL` (+ `LLM_API_KEY`, `LLM_MODEL_NAME`), and a `PYTHONPATH` with the moshi-rag source and xformers shim. Hive does not set those.
- **Back-to-back race (A3c, 2026-11-15):** on the q8 server a second handshake made right after the first connection closes fails with `moshi_unreachable` (measured: back-to-back fails; a 2 s pause works). Suspected per-connection Mimi deepcopy OOM, not proven.
- **Race decision (2026-11-15, operator choice: hand over):** the panel's call gate (`moshi_call_gate`) keeps the handshaken socket from its probe open in a one-slot holder. `open_session` hands that same socket to the next caller for the same URL, so a call uses one connection. A held socket older than 30 s is closed and re-probed. The typed or submit gate (`moshi_listen_gate`) still probes and closes. Launcher reuse of one Mimi copy is not done.
- **Child log (2026-11-15, operator choice: log file):** a Hive-started server appends stdout and stderr to `.hive/voice-bot/moshi-server.log` instead of DEVNULL, so server errors are visible from Hive.
- **Autostart live** only after `autostart_gate_check` passes with the handover (gate, then consecutive session connects with no sleep).
- **Autostart live, 2026-11-15 15c: FAIL (not closed).** Host GPU is 16 GiB (not the H100 of the A3 pod). Run: `autostart_gate_check.py` with `moshi_call_gate`, q8 keys set in a temp `config.json` (restored after), operator env, stub on 8009. Result: `GATE None` after 57.6 s, child running. `ATTEMPT 0 OK 0.0 s` (handed-over socket). `ATTEMPT 1 FAIL moshi_unreachable` (`ConnectionClosedError`, close code 1002 "reserved bits must be 0"). `ATTEMPT 2 FAIL moshi_unreachable` (`ConnectionClosedError`). Server log (`.hive/voice-bot/moshi-server.log`) excerpt: `Rejecting connection: No available slots`; `[Slot] acquired slot 0 (1/1)`; then `LocalSpeechToText` → `checkpoint_info.get_moshi` → `torch.OutOfMemoryError: CUDA out of memory ... GPU 0 has a total capacity of 16.00 GiB ... 15.14 GiB is allocated by PyTorch`. Finding: each websocket session builds its own speech-to-text LM copy on the GPU, so a second session on this card runs out of memory. The handover removes the probe-to-session double connect, but it does not remove the per-session LM load. Operator choice (2026-11-15, after FAIL): **share one loaded STT LM across sessions** in the q8 launcher (`scripts/moshi_q8_server.py`, the `get_moshi` wrapper), instead of one LM per websocket. Not implemented yet; R37 "Autostart live" stays open until a rerun of `autostart_gate_check.py` passes. Log: `moshi-q8-spike/autostart_15c.log`.
- **Share point (2026-11-15, session 15d, decided):** the q8 launcher `scripts/moshi_q8_server.py` loads each checkpoint once. A `get_moshi` cache, keyed by checkpoint weights, lora, device, dtype and call args, returns the same LM to every websocket session. This covers the speech-to-text LM that `LocalSpeechToText` builds per session. A cache hit also clears the shared LM's streaming state (`_stop_streaming`, a plain state reset). Without it the second session fails with `AssertionError: <module> is already streaming!` (first live rerun after the share: no OOM, but both later connects still failed). The Mimi copy stays per session (upstream `deepcopy`). The share is in the launcher only; moshi-rag upstream is not edited. Sessions still run one at a time (server slot limit 1), so the shared LM is never used by two streams at once. Proof: a unit test on the cache (one load for two calls) and a Hive test where two sequential `open_session` connects both succeed. Live proof is still the `autostart_gate_check.py` rerun.
- **Autostart live, 2026-11-15 15d rerun 2: FAIL (not closed, stop here).** With the share and the streaming reset: `GATE None` after 60.0 s, child running. No `OutOfMemoryError` and no `already streaming` in the new log lines. `ATTEMPT 0 OK 0.0 s`. `ATTEMPT 1` and `ATTEMPT 2` fail `moshi_unreachable` with close code 1002 "reserved bits must be 0". Server log excerpt (new lines only): `04:01:40.33 [Slot] acquired slot 0 (1/1)`; `04:01:40.37 new WebSocket client connected`; `04:01:40.70 WARNING Rejecting connection: No available slots`; `04:01:41.71 new WebSocket client connected`; `04:01:42.03 WARNING Rejecting connection: No available slots`; `04:01:42.34 [Slot] released slot 0`. Finding: the q8 server frees the slot about 2 s after the client closes the previous session. The gate check closes attempt 0 and connects again at once (no sleep). This is the close-then-connect race from the caveats, now proven. It fails the "NO sleep" criterion. Not fixed; the next fix needs an operator decision.
- **Slot race fix (2026-11-15, session 15e, operator choice: launcher fix):** the 2 s slot hold was upstream `LocalSpeechToText.shutdown`. It waits up to 2 s for a transcript iterator that the channel already cancelled on close, so nothing consumes its end marker. `scripts/moshi_q8_server.py` now installs `no_wait_stt_shutdown` (queues the marker, sets the completion event, no wait). Upstream moshi-rag is not edited. Unit test: `tests/test_moshi_q8_share.py::test_stt_shutdown_returns_at_once_without_a_consumer`. Known cosmetic upstream issue, not fixed: after each close `channel.run()` logs an `ExceptionGroup` traceback (its `except _ChannelClosed` misses the wrapped exception). The socket still closes cleanly.
- **Autostart live, 2026-11-15 15e: PASS.** `autostart_gate_check.py` with the q8 keys (temp config, restored after) and the handover: `GATE None` after 58.8 s, child running. `ATTEMPT 0 OK 0.0 s`, `ATTEMPT 1 OK 0.4 s`, `ATTEMPT 2 OK 0.3 s`, no sleep between connects. Server log: each close releases slot 0 at once, no `Rejecting connection`, no OOM, no already-streaming. Evidence: G7 row in `evidence-register.md`; logs in `moshi-q8-spike/autostart_15e*.log`. Caveat: the gate check proves connects and the slot release only, not a full audio round trip through the q8 server (the G7 probe row holds that).
- **Tools:** Moshi output is text and audio only. Any tool intent parsed from Moshi text maps to an R18 call that passes R23 validation and R6 approval. Moshi never runs a tool directly (R36).
- **Proof:** a live row in `evidence-register.md` (G7) with server version, model repo, host, and the handshake plus one audio round trip. Fixture tests use an in-process websocket stub; they never write G7 pass.
- **Decisions (2026-11-14):** OD-1 = Hive starts and stops a loopback server when `moshi_autostart` is true, otherwise operator-run (see R36). OD-2 = speech-out adapter, not Moshi (see R36).
- **Listen gate (T053):** when `voice_layer` is `moshi`, a spoken submit first runs a handshake probe. If Moshi is not importable it refuses with `moshi_unavailable`; if the handshake fails it refuses with `moshi_unreachable`. Both refuse with a spoken notice and create no task. Typed `submit` is not gated (R36 typed fallback). A live Moshi call's `0x02` approval replies do not run this gate: they reuse the open socket and `POST /v1/reply`.

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
| `resource.constraints` | Measured latency and resource use; Voice_Bot extra ships Moshi/Pipecat | R21, R24, R30, T018, T021 | `voice.moshi`, `voice.pipeline` |
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
| `src/hive_planner/voice_task.py` (T004–T011) | HIVE | Submit, queue, approval broker, spoken/written split |
| `src/hive_planner/voice_bridge.py` (T017) | HIVE | Loopback HTTP local-service (token, submit, approval, task) |
| `extensions/hive-voice-bot/` (T007) | Editor adapter | Context snapshots; approval UI still T008 |
| Voice / Pipecat service (external) | Voice adapter | Audio, STT, tool surface |
| `agent acp` | Cursor CLI | Coding execution transport |

## Decision gates (from cartridge / Rosetta)

| Gate | Required evidence | If not demonstrated |
|---|---|---|
| G0 — API availability | Pinned versions and reproducible checks | Do not implement from historical snippets alone |
| G1 — Native conversation | Supported submit/target into native Agent chat | Label limitation; use explicit ACP fallback |
| G2 — Coding transport | Read-only task, follow-up, updates, failure handling (evidenced by T004 output, not by T003 code alone) | Keep edits disabled. G2 is `pass` (live `session/prompt` 2026-11-10); AC 1–4 are covered in `acceptance-crosswalk.md`. Offline ACs (15–18) are also covered there. |
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
- Requiring the operator to install Moshi or Pipecat from outside the Hive `voice` extra (`resource.constraints`, R30).

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
- **SC-014:** The Hive `voice` extra declares Moshi and Pipecat; `voice-bot pack` can emit a deploy folder for other machines; `voice-bot ensure-runtime` can install them; `voice-bot status` reports each as installed or not; speech stays `typed_instruction` until G3 (R30).

## Deployment readiness

Verdict (2026-11-12, U3): **Read-only typed preview: READY. Full `agent` edit mode: NOT READY for production use.** The R22 `unguarded_write` check now runs on the production submit path (`voice_task.py` `_finish`), so the earlier blocker is closed. Two residual gaps were closed in code on 2026-11-12 (U6): (1) a write with no diff content now counts as a write event (`write_events`, one per tool call id) and fails the task without an approval; (2) each approved write permission covers one write, so two writes after one approval fail `unguarded_write`. A third closure (U10): an `execute` tool call whose shell command writes files (redirects, `tee`, `sed -i`, `mv`/`cp`/`rm`/`mkdir`, PowerShell write cmdlets; `voice_task.py` `WRITE_COMMAND_RE` and `_is_write_call`) counts as a write event. Writes with none of those forms, such as `python -c "open(...).write(...)"`, are not yet caught. Full-agent verdict stays NOT READY for production use until the operator reviews these closures and records the lane verdict. R35 proves an allowed write reaches disk on this host; it does not prove production permission safety. Speech I/O remains `typed_instruction` until STT is pinned (G3 hybrid path); native Composer handoff is not claimed (labeled ACP fallback).

Each host that enables `edits_enabled` must first sign the [operator production checklist](./operator-production-checklist.md); no fleet-wide READY is claimed.

Complete: T001–T040; live gates G2, G4, G5, G6 in `evidence-register.md`; T038 EDH→bridge→extension submit (16/16, 2026-11-12). Host submit forwards the T007 `editor_snapshot` (R2).

Residual operational notes (not deployment blockers):

| Note | Spec rows | Detail |
|---|---|---|
| R24 RSS budgets | R24, T018 | Latency enforced at runtime (T040); RSS ceilings enforced at runtime at task start (T044, `kind=rss`) and checked by `scripts/voice_r24_latency_probe.py` and config tests; 650 MB agent-children target is tight (one live outlier at 770 MB recorded). |
| G4 visible diff | R4, T014 | Live-tested in EDH 2026-11-12 (T043): `POST /v1/editor/show_diff` queues the action and the extension opens it as a diff editor (18/18). |
| STT / spoken mic | G3, R10 | `hybrid_speech_path()` is `typed_instruction`; Moshi STT unpinned. |

Exit criteria for deployment claims (met 2026-11-12):

1. Gates G1–G6 are `pass` in `evidence-register.md`, or the matching fallback is labeled and accepted (R4, R19).
2. T003–T020 and T029–T040 are complete with named integrated tests.
3. Acceptance 1–22 and SC-001–SC-014 mapped in `acceptance-crosswalk.md`.
4. `agent --version` pinned in evidence register (G2).
5. Integration wiring audit in `tasks.md` checked.
6. `spec-drift-check --feature Voice_Bot` passes after spec promotion (run after this status change).

To disable production `agent` mode on a host, set `edits_enabled` to false or remove the key (defaults false per `VoiceBotConfig`).

**Per-host latch rule (F1, 2026-11-12):** `edits_enabled` defaults absent/`false`. Only the operator sets it to `true`, and only on that host, after G6 pass and the F2 checklist. Bootstrap and pack scripts never set it. Full-agent verdict stays NOT READY for production use until the operator reviews.

### Speech I/O rollout (T041, decision 2026-11-12)

Scope: gap A in [deployment-gaps.md](./deployment-gaps.md). This section is the decision record. It adds no code. T042 implements it.

**Decision.** The accepted G3 end state today is `typed_instruction` on every OS. Spoken microphone input is not claimed. The rollout below is phased and each phase has pin criteria. Until a phase's criteria pass and an evidence-register row exists, `hybrid_speech_path()` stays `typed_instruction`.

| Phase | Host scope | Speech path | Claim allowed after pass |
|---|---|---|---|
| S0 (current) | Windows, Linux, macOS | `typed_instruction`, `STT_PROVIDER = None`, speak is no-audio (T034) | Typed control, labeled G3 hybrid |
| S1 (T042, revised 2026-11-14) | Windows first | Moshi primary conversation (R37) once the live harness passes; faster-whisper only as a WER-gated transcription fallback | Spoken input on the pinned Windows host, after R37 and the WER row |
| S2 (later) | Linux or macOS | Moshi primary, plus Pipecat playback where pinned | Per-host spoken claim |

**Moshi-first on Windows (R36, R37, 2026-11-14 direction).** Moshi is the primary conversation layer on Windows too, once the live harness (R37) passes. The faster-whisper STT pin (T042) is a fallback for transcription only, and it is used only if Moshi's own transcription fails the WER test (T013-style, recorded in the register). Whisper is not the Windows primary.

**STT pin criteria (S1).** All of these must hold before `STT_PROVIDER` moves off `None`:
1. Pinned package version and model id (with a content hash) recorded in `evidence-register.md` § T033.
2. Test method fixed before the run: a set of WAV fixtures with reference transcripts, and a stated word-error threshold.
3. CPU-only run on the reference Windows host, with the latency recorded against R24 `latency_target_ms`.
4. Replacing the T033 "documented unpinned" row with a dated pin row. Also update `tests/test_voice_bot_gates.py`, which asserts `STT_PROVIDER is None` today.

**TTS and speak pin criteria (S1 audio, R32).** `PipecatVoiceAdapter.speak` may produce audio only when all of these hold:
1. Pinned Pipecat version recorded in the register.
2. `audio_enabled` is true on the host (see config flags below).
3. A live row where `speech.spoken` carries `audio: true` and the payload records playback success.
4. R13 holds: `cancel_on_interruption=False` on long-running coding tools, with a test showing that speech interruption leaves the task `running` (acceptance 5).
Until then, speak stays the no-audio contract from T034.

**Config flags (proposed, no read site yet).**
- `audio_enabled` (bool, default false, absent means false). Gates whether the runtime calls `speak` with playback. T042 must add the read site.
- `stt_provider` (string or null, default null). Becomes the only source for `STT_PROVIDER`. It may be set only to a provider that has a pin row.
- Wiring rule: a flag that nothing reads is dead config. T042 must have a test that flips `hybrid_speech_path()` and the speak payload from the flag, not from a constant.

**R13 when audio is on.** Any long-running coding operation keeps `cancel_on_interruption=False`. Interruption stops playback only (R1, R32). It must not cancel the task.

**Evidence rows required before any G3 claim changes.**
- §T033 pin row (STT) with the phase, provider, version, test method, result, and date.
- §T034 live audio row (speak with `audio: true`), separate from the no-audio contract row.
- Live interruption row with audio on (G5 with audio), separate from the typed G5 row already recorded.
- Until all three exist, the G3 wording stays "labeled typed hybrid".

**Fleet install (T045, implemented 2026-11-12).** `voice-bot pack` builds the editor adapter as a VSIX from `extensions/hive-voice-bot/` (no npm; `test/` excluded) and writes `install-voice-bot.ps1`. The script installs the VSIX with `code --install-extension --force`, falling back to `cursor`. `INSTALL.md` lists that script as step 1, then the pip and offline steps. If the extension source is missing at build time, the pack still writes, reports `editor_vsix: null`, and `INSTALL.md` says there is no VSIX. `tests/test_voice_bot_self_contained.py` covers the layout.

## Assumptions

- The initial implementation runs locally in one workspace.
- Cursor ACP, extension APIs, Pipecat, and Moshi capabilities are version-dependent and require evidence.
- The voice service does not automatically gain access to the native IDE chat.
- One coding turn per owned session is serialized until concurrent steering is verified.
- Phase 1 uses typed instruction text. Spoken input and STT are validated in T013, so STT is not a Phase 1 dependency.

## Acceptance criteria

1. Read-only contextual question succeeds with the intended selection. Phase 1 (T004) proves this with an explicit file path and instruction text. T007 captures selection in the editor adapter. Selection-based acceptance on `voice-bot turn` closes when T008 maps that object into HIVE `selection_text`.
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
22. The Hive `voice` extra declares Moshi and Pipecat; `ensure-runtime` dry-run lists them; status reports installed vs missing; speech stays `typed_instruction` until G3 (R30, SC-014, `tests/test_voice_bot_self_contained.py`).

## Risks and open questions

- Native-chat submit/target/read/replace are recorded `fail` on pinned Cursor 2026.11.05 (G1 closed via labeled ACP; T012/T028). UI automation remains a non-goal.
- Cursor ACP live `session/prompt` is recorded (G2 pass 2026-11-10, CLI `2026.11.05-86047df`, `stopReason=end_turn`). T003–T004 fixture path remains.
- Moshi STT stays unpinned; G3 is closed via the labeled hybrid typed path (R10, T013, T024).
- Editor APIs may expose MCP/plugin registration without native-chat control—do not treat MCP enablement as coding-session attachment.
- Cartridge `translate` output is draft; promoting specseed without merge would overwrite curated requirements (use `--no-promote` + manual merge per R16).
- Whether an MCP “listening” tool blocks concurrent coding conversation is unresolved (`cursor.mcp`); validate before in-chat microphone loops. Owner: T016.
- Full-duplex Moshi audio does not imply reliable STT, tool calls, or external-result narration (`voice.moshi`).

## Validation

Start read-only. Record pinned versions and results in an evidence register. Validate native handoff, ACP transport, editor snapshots, permissions, interruption/cancellation, recovery, and spoken-result grounding before enabling edits. When mining tertiary sources, decompress `[HOOK:*]` blocks through the hook index above before adding acceptance text. Each acceptance criterion (15–21) and SC-011, SC-012, and SC-013 must have a named test in `tests/test_voice_bot*.py` that exercises the integrated path, not only a string or mock check.
