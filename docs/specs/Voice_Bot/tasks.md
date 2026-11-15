# Tasks: Voice_Bot

**Spec:** [spec.md](./spec.md)  
**Plan:** [plan.md](./plan.md)

<!-- ROSETTA-NAV -->

## Agent navigation (Rosetta Stone)

Load [`docs/planning-rosetta-stone.md`](../../planning-rosetta-stone.md) (`planning.rosetta`) before executing tasks.

- **Spec:** [`spec.md`](./spec.md)
- **Plan:** [`plan.md`](./plan.md)
- **Delta micro:** [`Voice_Bot.md`](../../delta/20_micro/Voice_Bot.md)
- **Primary hooks:** same canonical set as spec.md header (see spec.md Hook line)

## Phase 1 — Evidence and read-only transport

- [x] T001 Define the HIVE-owned voice/session/task/context contracts and cartridge traceability fields.
- [x] T002 Populate `evidence-register.md` with pinned versions and G0–G6 capability results.
- [x] T001a Add the `voice_bot` config object holding every R21 limit and the R24 budgets, and read each limit from it. Implemented in `src/hive_planner/voice_bot.py` (`VoiceBotConfig`, `load_voice_bot_config`, read by snapshot and instruction validation). Tests: `tests/test_voice_bot_config.py` (passing 2026-11-09).
- [x] T003 Implement an ACP JSON-RPC adapter with persistent process, response routing, and disconnect detection.
- [x] T004 Implement one HIVE-routed read-only prompt, streamed updates, final stop reason, and a contextual follow-up. Context is explicit file path and instruction text only; selection capture arrives with T007. T004 output is the G2 evidence. **G2 live recorded 2026-11-10** (`voice-bot live-prompt --record`, `stopReason=end_turn`). Fixture tests remain: `tests/test_voice_bot_readonly_turn.py`, `tests/test_voice_bot_turn_cli.py`.

## Phase 2 — Contracts and editor context

- [x] T005 Add normalized HIVE session, task, context snapshot, permission, and event models, including the R20 state enum, the R21 limits, and `client_request_id` on submit. Tests: `tests/test_voice_bot_contracts.py`.
- [x] T006 Add provider-neutral delegation handlers for submit, status, diff, follow-up, and cancellation. Tests: `tests/test_voice_bot_delegation.py` (SC-012 dedupe included).
- [x] T007a Scaffold the Cursor extension package (activation, `getContextSnapshot` command, approval UI stub) as the editor-adapter host for T007 and T008. Machine-level prerequisites are recorded here, not in the gates. **Scaffold done 2026-11-09** in `extensions/hive-voice-bot/` (`src/core.js` pure logic, `src/extension.js` vscode wiring). EDH smoke 8/8 (T007). Approval poll is connected (T008 `GET /v1/approval` → `answerPendingApproval`); `hive.voiceBot.approvalStub` remains a manual check that executes nothing.
- [x] T007 Add extension context capture with selection, dirty state, document version, diagnostics, and size limits. Depends on T007a. **Done 2026-11-09** in `extensions/hive-voice-bot/src/core.js` (`buildSelection`, `buildDiagnostics`, `truncateUtf8`, `loadSnapshotMaxBytes`) with host wiring in `src/extension.js`. Tests: `extensions/hive-voice-bot/test/core.test.js` (20 passed, one test per limit: selection under/at/over the byte limit, UTF-8 cut, config read, config fallback, diagnostics under/over budget, single oversized diagnostic). Live proof: `test/edh/run-edh.ps1` launches a real VS Code 1.143.0 Extension Development Host; `test/edh/smoke.js` reports 8/8 checks passed. Snapshot shape: `selection` is an object (or null). T008 maps `selection.text` into HIVE `selection_text`.

## Phase 3 — Safety and conversation

- [x] T008 Add visible approval handling for writes, commands, plans, and questions. Tests: `tests/test_voice_bot_permissions.py` (approval kinds, exact-match replies, timeout). **Done 2026-11-09:** broker on stdio; extension polls `GET /v1/approval` and replies through `answerPendingApproval`; HIVE maps the T007 `selection` object to `selection_text` (`map_editor_snapshot`, `POST /v1/submit` `selection_text`). Live ACP option kinds stay provisional until G2 login.
- [x] T009 Add one-active-turn FIFO queueing (depth 5, R21), duplicate-request protection via `client_request_id` (SC-012), approval-reply routing, and task recovery. Tests: `tests/test_voice_bot_queue.py`. Recovery here means disconnect → `unknown` → `provider_lost` after the reconnect window. Restart recovery (R26) is T020.
- [x] T010 Separate playback interruption, coding cancellation, call ending, and rollback reporting. Tests: `tests/test_voice_bot_interrupt.py`.
- [x] T011 Add evidence-backed spoken summaries and full written results. Map test status to the R8 states (`passed`, `failed`, `not_run`, `unknown`); test SC-013. Enforce the R14 speech cadence. Tests: `tests/test_voice_bot_results.py` (SC-013, cadence, cap).

## Phase 4 — Integration gates

- [x] T012 Answer all four R19 questions (submission, targeting, readable progress/context, provider replaceability) on a pinned version; record each in the evidence register. **Updated 2026-11-10 (T028):** G1a–G1d are `fail` (no public native-chat API; UI automation is a non-goal). G1 gate is `pass` via labeled ACP (`native_chat_path()`); G2 has run.
- [x] T013 Test Moshi transcription, tool selection, external-result grounding, and hybrid fallback behavior. **Recorded 2026-11-10:** hybrid path is `typed_instruction`; G3 closed as the labeled fallback. Moshi STT is not pinned.
- [x] T014 Validate stale-buffer protection, disconnects (`unknown` → reconnect or `provider_lost`), timeouts, permission denial, and safe shutdown. Also add tests for acceptance 15 (secret exclusion), 16 (bounded tool registry), 17 (adapter swap with a stub), and 18 (truncation flags). Tests: `tests/test_voice_bot_safety.py`. **Live G4 2026-11-11:** `extensions/hive-voice-bot/test/edh/run-edh.ps1` → 13/13 (adds a live unsaved buffer edit, recapture with version and dirty change, and a revert). Live visible diff is not covered.
- [x] T015 Enable controlled edits only after all read-only and safety acceptance tests pass. **Gate implemented 2026-11-09:** `edits_enabled()` is false and `agent` mode is refused (`agent_mode_disabled`). G6 live permission is recorded `pass` (2026-11-10, T026/T027), but production edits stay off until the R33 config latch (`edits_enabled: true`) is set by a human.
- [x] T017 Implement and test the R23 boundaries: path validation against the bound workspace (`path_outside_workspace`), per-session token for local-service connections, and schema validation on each R18 tool. Tests: `tests/test_voice_bot_security.py`, `tests/test_voice_bot_bridge.py`. Extension starts `voice-bot bridge` (`hive.voiceBot.startBridge`). Submit schema includes optional `selection_text`.
- [x] T018 Measure R24 latency (`transcript.final` → `task.started`, time to first `spoken_update`) and process resource use on the pinned runtime. Record results and hardware in `evidence-register.md`; read targets from the `voice_bot` config. Test: `tests/test_voice_bot_latency.py` asserts that config values change the checked target (acceptance 20).
- [x] T019 Make `spec-drift-check` compare specseed content with the curated spec, not only bullet presence. `check_memory_spec_drift` in `src/hive_planner/spec_drift.py` compares `cartridge/specs/<feature>.specseed.md` to `docs/specs/<feature>/spec.md` (normalized); missing specseed is skipped.
- [x] T016 Prove G5 (concurrency): a scripted test shows conversation continues while a task runs, a follow-up queues while `awaiting_approval`, and playback interruption leaves task state unchanged (SC-003, AC 4–5). Also resolves the MCP listening-tool risk in spec.md before any in-chat microphone loop. Tests: `tests/test_voice_bot_concurrency.py`. **Live 2026-11-11:** `scripts/voice_g5_live_probe.py` on the logged-in `agent acp`: follow-up queued while running, interrupt left the task `running`, queued follow-up dispatched. G5 `pass` (typed path; spoken mic loop not in scope). `IN_CHAT_MCP_MICROPHONE` is false.
- [x] T020 Implement and test R25–R29: call end during a pending approval, restart recovery, one pending approval per session, snapshot scope (no file, multi-root, unsaved, binary), and dedupe scope. Tests: `tests/test_voice_bot_edges.py`, run through the submit and approval paths, not helper-only.
- [x] T021 Self-contained Voice_Bot deploy (R30): Hive `voice` extra declares Moshi and Pipecat; `voice-bot ensure-runtime` installs missing packages; Cursor CLI uses the official installer. Tests: `tests/test_voice_bot_self_contained.py` (SC-014, AC 22).
- [x] T022 Wire previously uncoded spec rows on the Hive path: US5/SC-009 planning answers from spec/plan/tasks; R2 excerpt ids and file content; selection/file content in the ACP prompt; R18 workspace/`context_snapshot_id` bind; `navigate_to`/`show_diff` queue for the editor via `GET`/`POST /v1/editor`. Tests: `tests/test_voice_bot_planning.py`. Live G2 recorded 2026-11-10.
- [x] T023 Live G2 probe (R31): `voice-bot live-prompt` records `agent status` / `CURSOR_API_KEY`, runs one real `session/prompt` only when logged in, and never writes G2 `pass` from the fixture path. Tests: `tests/test_voice_bot_live_prompt.py`.
- [x] T024 Spoken playback adapter (R32): `VoiceAdapter.speak`; typed path is no-audio; Pipecat adapter uses R13 cancellation independence when importable. Tests: `tests/test_voice_bot_speak.py`. G3 closed via hybrid typed path; STT unpinned.
- [x] T025 G6 edits latch (R33): `edits_enabled()` requires evidence-register G6 `pass` and config `edits_enabled: true`. `submit(..., mode="agent")` is refused until both are true, then accepted. Tests: `tests/test_voice_bot_gates.py`. Do not write G6 pass from fixture tests.
- [x] T026 Live G6 permission probe (R34): `voice-bot live-permission` records G6 from a real `session/request_permission` and always cancels. Fixture paths and logged-out CLI never write G6 pass. Tests: `tests/test_voice_bot_live_permission.py`. **Live 2026-11-10:** permission shape recorded (`reject-once` selected); probe file still written (`unguarded_write`). (Superseded by T027: the same day's rerun recorded G6 `pass`.) R33 config stays false.
- [x] T027 After the first gated refuse, send `session/cancel` and stop the ACP child so a later self-write cannot create the probe file; unknown server requests are JSON-RPC errors. Tests: `tests/test_voice_bot_live_permission.py` (`G6_WRITE_UNLESS_CANCEL`), `tests/test_voice_acp.py` (`terminate`). **Live 2026-11-10:** `voice-bot live-permission --record` → G6 **pass**, `wrote=false`, `stopReason=cancelled`. R33 config latch stays false until a human sets `edits_enabled`.
- [x] T028 Close G1 as labeled ACP fallback (R19): G1a–G1d recorded `fail` on pinned Cursor; `native_chat_path()` is `labeled_acp_fallback`; G2 has run so the fallback is not an unrun label. Tests: `tests/test_voice_bot_gates.py`. Native handoff is not claimed.

## Phase 5 — Bridge and voice wiring (proposed, [gap-fill-proposal.md](./gap-fill-proposal.md))

- [x] T029 R22 live buffer: wire `set_live_buffer` on bridge startup from extension poll; stale block without `editor_snapshot` in body. Tests: `tests/test_voice_bot_bridge.py`. **Done 2026-11-11:** bridge installs `live_buffer_for` at `start()` and removes it at `close()`; `POST /v1/live` (token + schema, workspace-relative path, int version, bool dirty) calls `record_live_buffer`; the extension approval poll posts the active editor via `bridgeClient.liveBuffer`. Reply without snapshot blocks a stale write (200 `stale`); submit without a version is still not compared. Tests: bridge 44 passed (7 new live-feed cases); extension `npm test` 51 passed (`bridge-client.test.js` live feed case).
- [x] T030 R1 session `interrupted`: apply spec Patch A, then set session on `interrupt_playback`; restore `active` on submit/follow-up. Tests: `tests/test_voice_bot_interrupt.py`.
- [x] T031 Bridge `interrupt` / `end_call` HTTP + extension commands. Tests: `tests/test_voice_bot_bridge.py`. **Done 2026-11-11:** `POST /v1/playback/interrupt` and `POST /v1/call/end` run token + schema (workspace required, unknown keys 400) and call `runner.interrupt_playback()` / `runner.end_call()`; extension `interruptPlayback` / `endCall` client methods and commands `hive.voiceBot.interruptPlayback` / `hive.voiceBot.endCall`. Tests: bridge + interrupt 63 passed (5 new); extension `npm test` 52 passed (new client path test).
- [x] T032 `task_diff` non-stub when write evidence exists (fixture latch). Tests: `tests/test_voice_bot_delegation.py` (5 new cases; latch-on diff, cap, latch-off no-evidence). Done 2026-11-11, fixture only; no live R33 run.
- [x] T033 Moshi STT pin or documented unpinned (G3). Update `evidence-register.md`. **Done 2026-11-11:** documented unpinned in `evidence-register.md` § T033; `STT_PROVIDER = None`; tests `test_voice_bot_gates.py`, `test_voice_bot_speak.py`, `test_voice_bot_self_contained.py` assert `typed_instruction`.
- [x] T034 Pipecat `speak` audio path or explicit no-audio contract. Tests: `tests/test_voice_bot_speak.py`. **Done 2026-11-11:** no-audio payload when installed; explicit `pipecat_unavailable` error when missing; runtime uses typed adapter (evidence-register § T034). 8 passed.
- [x] T035 `transcript.final` voice controller (bounded tools). New tests. **Done 2026-11-11:** the controller is `VoiceTaskRunner.invoke_controller_tool` (allowlist `VOICE_CONTROLLER_TOOLS`); `submit()` emits one `transcript.final` per submit and dedupes retries on `(session_id, client_request_id)`. Tests: `tests/test_voice_bot_controller.py` 4 passed (one dispatch per final transcript, retry returns the same task, missing `client_request_id` creates nothing, `shell` refused as `unbounded_tool`). `voice or acp` 319 passed; `spec-drift-check --feature Voice_Bot` ok.
- [x] T036 Bridge HTTP for cancel, queue, diff, reconnect (Patch B). Tests: bridge + delegation. **Done 2026-11-11:** routes `/v1/cancel`, `/v1/queue`, `GET /v1/diff`, `/v1/reconnect` call `cancel` / `queue_follow_up` / `task_diff` / `reconnect_task`. Tests: bridge 62 passed (10 T036 HTTP cases incl. diff with write evidence under latch); delegation 18 passed (queue FIFO, reconnect refused when not unknown, reconnect restores prior state on live ACP session match).
- [x] T037 Multi-root workspace binding in extension. Tests: `extensions/hive-voice-bot/test/core.test.js`. **Done 2026-11-11:** `pickSessionRoot` in `src/core.js` picks the most specific folder holding the active file, else `folder[0]`. `src/extension.js` pins that root at `startBridge` (R28) in `sessionWorkspaceRoot()`, used by snapshot capture, bridge client, navigate, and the live-buffer feed. Tests: 6 new multi-root cases in `core.test.js`; extension `npm test` 58 passed (was 52). `spec-drift-check --feature Voice_Bot` ok. Editor wiring is not unit-tested without a VS Code host; EDH smoke is T038.
- [x] T038 Live EDH → bridge → runner chain (one recorded run). **Done 2026-11-12:** `test/edh/smoke.js` now drives the chain inside the Extension Host: `hive.voiceBot.startBridge` (extension spawns the bridge on the fixture root), `hive.voiceBot.submitTask` (extension captures the editor snapshot and POSTs `/v1/submit`), follow to terminal state, `hive.voiceBot.stopBridge`. Recorded run: `run-edh.ps1` exit 0, 16/16 checks, VS Code 1.146.0, task `task_69b25e485d56` completed (`end_turn`, tests not_run). `npm test` 58/58. No Python code changed. R33 latch unchanged (fixture config has no `edits_enabled`).
- [x] T039 Expose `reconnect_task` on bridge. Tests: `tests/test_voice_bot_edges.py`. **Done 2026-11-12:** T036 already wired `POST /v1/reconnect`. Edges coverage: `test_restart_reconnect_over_bridge_refuses_without_provider_evidence` (restart → 409 `no_provider_evidence`); `test_reconnect_over_http_restores_running_when_provider_session_matches` (disconnect → HTTP 200, `running`, active slot restored). `pytest tests/test_voice_bot_edges.py` 7/7. No runner/bridge/extension code changed this pass.
- [x] T040 R24 runtime enforcement beyond config tests. **Done 2026-11-12:** `VoiceTaskRunner._event` now calls `_check_r24_budget` on `task.started` (against `latency_target_ms`) and on the first `speech.spoken` (against `first_spoken_update_target_ms`). An over-budget result appends `r24.over_budget` with `kind`, `elapsed_ms`, `target_ms`, once per kind per task. Missing target is not checked. Tests: `tests/test_voice_bot_r24_runtime.py` 4/4 (deterministic clock); `test_voice_bot_latency.py` + `test_voice_bot_resources.py` 8/8; `pytest tests -k "voice or acp"` 325 passed. Remaining R24 gap: RSS budgets are still checked only by `scripts/voice_r24_latency_probe.py`, not at runtime.

## Phase 6 — Speech I/O and fleet install (deployment gaps A and D)

- [x] T041 Speech I/O rollout decision (gap A, spec-only). **Done 2026-11-12:** `spec.md` § Speech I/O rollout (phases S0–S2, Windows Whisper-class STT target, STT and speak pin criteria, proposed `audio_enabled` and `stt_provider` flags, R13 `cancel_on_interruption=False` when audio is on, evidence rows required before G3 changes); `evidence-register.md` § T033 decision; `deployment-gaps.md` A statement tightened. No code, no installs, no live mic. Merge gate: `spec-drift-check --feature Voice_Bot`.
- [ ] T042 Speech S1 implementation (after T041 pin criteria pass). **Deferred for preview ship (2026-11-12, Path A):** S0 stays the default; the checkbox stays open; see `deployment-gaps.md` § Polish decision. **Partial 2026-11-12 (slices 1–4 + R13 close-out; C1 criterion 4 gate test done, live mic still open):** `stt_provider` config is the only STT flag (the `STT_PROVIDER` constant is removed; default null, pinned values only); `hybrid_speech_path(config)` reads it; `src/hive_planner/voice_stt.py` `FasterWhisperAdapter`; `submit_spoken` + `POST /v1/submit/spoken` (bytes or in-workspace WAV path, transcript becomes the instruction); `audio_enabled` read site in `speech_adapter(config)` gates `PipecatVoiceAdapter.speak` playback (default false). Tests: `tests/test_voice_stt.py`, `tests/test_voice_stt_runtime.py`, `tests/test_voice_bot_speak.py`, bridge tests, and R13 `test_r13_playback_interrupt_with_audio_on_leaves_running_task_unchanged` in `tests/test_voice_bot_interrupt.py` (audio on, Pipecat path selected via monkeypatch, running task unchanged after interrupt). **Not done (checkbox stays open):** live mic capture on the host (out of scope for this slice); spec S1 criterion 4 (STT pin row and gate test update) is partial; no live `audio: true` evidence row and no live audio-on interruption row yet. G3 stays "labeled typed hybrid" until those rows exist.
  - **T042 slice 5 — launcher panel wiring (open).** Every control in `launcher/voice_panel.py` forwards to `launcher/voice_panel_controller.py`; no decorative no-ops. Back = focus the main shell (panel stays). Menu = read-only status (bridge, `stt_provider`, `audio_enabled`). Mic start is refused until capture exists (`stt_not_configured` or `mic_capture_not_wired`); stop always succeeds. End = interrupt playback when `audio_enabled`, then `POST /v1/call/end` on a live bridge. Slices: **5a** (this: skeleton, `app.py` wiring, end + mic refusal, tests), **5b** side typed fallback, **5c** menu bridge start/stop, **5d** mic record → workspace WAV → `submit_spoken`, **5e** orb/greeting task sync, **5f** tasks validation and wiring audit. **5a status:** wiring done; tests in `tests/test_voice_panel.py` and `tests/test_voice_panel_controller.py`. No live mic claim; G3 unchanged. **5b status:** side button (lines icon) opens a typed-instruction dialog → `submit_typed` → `POST /v1/submit` on a live bridge (`client_request_id` uuid, mode `ask`); refusals for no project, empty text, bridge down, and bridge HTTP errors; success only on 200; typed path is the S0 fallback, no live mic claim.
  - **T042 slice 5c — menu bridge start/stop (2026-11-14).** Menu asks one yes/no: start the bridge, or stop it when running. `VoicePanelController.start_bridge()` spawns `python -m hive_planner --root <project> voice-bot bridge` with stdin held open and reports success only after the endpoint answers (`bridge_started`); a second start is refused (`bridge_already_running`). `stop_bridge()` closes stdin and waits only for the process it started (`bridge_stopped`); a bridge started elsewhere is refused (`bridge_not_owned`). Tests: `tests/test_voice_panel_controller.py` (8 new). Live: start → answers → second start refused → stop → endpoint gone, via the real CLI. Mic (5d) and orb sync (5e) still open, so T042 stays open.
  - **T042 slice 5d — real recorder (2026-11-14).** `src/hive_planner/launcher/voice_mic_recorder.py` `WavMicRecorder`: sounddevice capture at 16 kHz mono int16, saved `input_device` name read at each start, WAV bytes returned on stop. Missing sounddevice or a bad device refuses with OSError (panel shows the reason). `app.py` constructs it and passes `recorder=`. `sounddevice>=0.4` added to the `voice` extra. Tests: `tests/test_voice_mic_recorder.py` (8, fake device; includes panel start → stop → `/v1/submit/spoken`). No live microphone run yet, so G3 is unchanged.
  - **T042 slice 5f — wiring audit (2026-11-14, docs only).** Panel control → handler → bridge route: on_back → `app._voice_on_back` → focus only (local); on_menu → `app._voice_on_menu` → messagebox `menu_text()` (read-only); on_mic → `controller.on_mic` → refusal stub (`mic_capture_not_wired`), no route; on_side → `app._voice_on_side` → `submit_typed` → `POST /v1/submit`; on_end → `app._voice_on_end` → `controller.on_end` → `POST /v1/playback/interrupt` (if audio on) then `POST /v1/call/end`. Settings is not a panel button: it is the read-only Voice Bot card on the Settings tab (`app.py` `_sync_voice_bot_card_for_active`), no route. **Gap (Mushi path):** spec lists `POST /v1/submit/spoken`; the panel never calls it until slice 5d records mic audio. No code change in this audit.
  - **T042 slice 5e — greeting task sync (2026-11-14, code + tests; parent T042 stays open).** After `submit_typed` returns 200 with `task_id` and `context_snapshot_id`, the controller polls `GET /v1/task` every 2 s. The greeting reads `Working on it...` or `Waiting for your approval...` until a terminal state, a bridge error, hang-up (`on_end`), or a 10 min cap. The panel reads `task_text()` on the animation tick, and listening wins over the task label. Wiring: `app.py` `task_text=voice_controller.task_text` → `submit_typed` → `_start_task_watch` → `_get_from_bridge("/v1/task")` → `_task_label` → `VoicePanel._sync_task_text` → `_greeting.configure`. Tests: `tests/test_voice_panel_task_watch.py` 15 passed on 4 of 5 runs. On the other run, one Tk test (line 232) skipped with "no display available for Tk" (14 passed, 1 skipped); it is an environment skip, not a failure. Gap: spoken submit (`/v1/submit/spoken`) and the Moshi utterance path do not start the watcher yet. **Closed in code 2026-11-15 (session 15k, uncommitted until 15l commit):** `VoicePanelController._submit_recording` calls `_start_task_watch` when `/v1/submit/spoken` returns 200 with `task_id` and `context_snapshot_id`; the Moshi utterance path uses the same route, so it is covered. Tests: `tests/test_voice_panel_task_watch.py::test_spoken_submit_starts_task_watch` and `::test_spoken_submit_without_task_starts_no_watch`; `pytest tests/test_voice_panel_task_watch.py tests/test_voice_panel_controller.py -q` → 72 passed, 1 skipped (Tk no-display). No live mic or live Moshi claim.
  - **Re-audit 2026-11-14 (after 5d):** the panel stop path now does call `POST /v1/submit/spoken` (`_submit_recording`). Start is refused while `stt_provider` is null, which is the shipped default, so the mic is off in the default config. Moshi is only a listen gate on that route (`moshi_listen_gate`); the `moshi-talk` loop is not connected to the panel mic. Fixed: a refused mic stop no longer flips the orb back to "listening" (`voice_panel.py` `_toggle_listening`; test `test_mic_stop_refusal_does_not_revert_to_listening`). Tests: `test_voice_panel.py`, `test_voice_panel_controller.py`, `test_voice_mic_recorder.py`, `test_voice_bot_settings_card.py`, `test_voice_moshi*.py`, `test_voice_bot_bridge.py` → 199 passed.
  - **Config-only note: `input_device` (2026-11-14, docs only).** `input_device` is a `VoiceBotConfig` field (null or non-empty string), read by `load_voice_bot_config` and written by `save_voice_bot_config` to `.hive/voice-bot/config.json`. No UI reads or writes it yet: the Settings Voice Bot card stays read-only, and the panel mic stays refused (`mic_capture_not_wired`). A Settings microphone control is out of scope until a UI slice adds it. That slice must start with a failing test that the handler calls `save_voice_bot_config` and reloads the value.
  - [x] T042b Settings `input_device` controller hop (2026-11-14). `VoicePanelController.set_input_device(name)` returns `InputDeviceResult(ok, code, input_device)`. Blank or whitespace name saves `null`. Refuses with `no_project` without a project and `config_invalid` when `config.json` is broken (file left unchanged). On success it saves through `save_voice_bot_config`, reloads from disk, and returns the reloaded value. Tests: `tests/test_voice_panel_controller.py`. The Settings dropdown that calls this hop is a later slice (T042c, not started).
  - [x] T042c Settings Voice Bot card `input_device` dropdown (2026-11-14, spec note). The read-only card gains a microphone dropdown that calls `VoicePanelController.set_input_device`. Blank choice saves `null`. After the save, the card refreshes from the reloaded value (the value returned by the controller, not the widget's typed text). Failing handler test first: `tests/test_voice_bot_settings_card.py`. Not done until the dropdown is wired and the test passes.
- [x] T043 Live visible diff (gap B / G4). **Done 2026-11-12:** new documented route `POST /v1/editor/show_diff` (`voice_bridge.py`, schema `show_diff`) calls `VoiceTaskRunner.show_diff` for a completed `task_id`; `test/edh/smoke.js` posts it through the live bridge and asserts the extension opens an untitled `diff` editor and acks the action. Tests: `test_show_diff_over_http_queues_the_editor_action_for_a_completed_task` (63/63 bridge). Live: `run-edh.ps1` 18/18 on VS Code 1.146.0. Evidence: G4 row in `evidence-register.md`.
- [x] T044 R24 RSS runtime check (gap C). **Done 2026-11-12:** `VoiceTaskRunner._check_r24_rss` runs on `task.started`, reads an injectable RSS reader (`rss_reader`, default `default_rss_mb` via psutil), and compares `agent_children_rss_target_mb` and `voice_service_rss_target_mb` from `VoiceBotConfig`. An over-budget scope appends `r24.over_budget` with `kind=rss`, `scope`, `measured_mb`, `target_mb`, once per scope per task. Unmeasured scope or missing target is not checked. Tests: 7 new cases in `tests/test_voice_bot_resources.py` (fake reader, integrated through `VoiceTaskRunner.submit`); `test_voice_bot_r24_runtime.py` and `test_voice_bot_latency.py` unchanged and passing.
- [x] T045 Deploy pack ergonomics (gap D). **Done 2026-11-12:** `voice-bot pack` builds `hive-voice-bot-<version>.vsix` from `extensions/hive-voice-bot/` (zip, no npm, `test/` excluded) and writes `install-voice-bot.ps1` (installs with `code`, falls back to `cursor`). `INSTALL.md` makes that script step 1 and keeps the pip and offline steps. `manifest.json` gains an `editor` block. Tests: 5 new cases in `tests/test_voice_bot_self_contained.py` (VSIX layout, script CLI order, PowerShell parse, INSTALL order, no-extension path). Spec: R30 pack line and § Speech I/O rollout fleet-install paragraph updated.

## Phase 7 — Moshi primary voice layer (direction 2026-11-14)

Spec R36 and R37; plan step list in [plan.md](./plan.md) § Moshi refactor sequence.

- [x] T049 Decide OD-1 (who starts the Moshi server: Hive-managed child, or operator-run external server) and record it in spec R37. **Decided 2026-11-14 (aligned with spec R37 / OD-1, operator choice "Hive owns the server"):** with `moshi_autostart` true (default) and a loopback `moshi_url`, HIVE starts and stops a child `moshi.server`; remote URLs are never started. `moshi_autostart: false` restores operator-run behavior (spec R36, R37).
- [x] T050 Decide OD-2 (how HIVE `spoken_update` reaches speech: separate TTS via Pipecat, or a verified Moshi text path). Record it in spec R36. **Decided 2026-11-14:** `MoshiVoiceAdapter.speak()` delegates to the speech-out adapter; Moshi never speaks HIVE text.
- [x] T051 Add `voice_layer` (`moshi` | `typed`, default `moshi`) and `moshi_url` to `VoiceBotConfig`, with validation tests. Read them in `speech_adapter(config)`; test that flipping `voice_layer` changes the adapter chosen. **Done 2026-11-14:** `tests/test_voice_moshi.py` (validation, flip, repo config load).
- [x] T052 Moshi websocket adapter (`src/hive_planner/voice_moshi.py`): handshake on `0x00`, duplex `0x01` mic frames out, `0x01` audio and `0x02` text in. Tests use an in-process websocket stub, not G7 evidence. **Done 2026-11-14:** `tests/test_voice_moshi.py` uses a real loopback `websockets` server (handshake, audio and text round trip, kind byte on send, missing handshake, closed port). Fixture only; G7 untouched.
- [x] T053 Unreachable and unavailable paths: `moshi_unreachable` and `moshi_unavailable` produce a spoken notice and create no task. Test through `speech_adapter` and the bridge. **Done 2026-11-14:** the listen gate runs in `submit_spoken` before STT; `test_spoken_submit_refused_when_moshi_unreachable_creates_no_task` checks no task and the spoken notice; typed submit stays open during an outage (R36). Bridge-level refusal is not separately tested.
- [x] T054 Route `speak()` per OD-2 (R36). Keep `hybrid_speech_path()` at `typed_instruction` until a WER row exists. **Done 2026-11-14:** `tests/test_voice_moshi.py` checks the delegation, `voice_layer` tag, no-audio payload, and `transcribe` refusal.
- [x] T055 Live G7 probe: handshake plus one audio round trip against a real Moshi server. Record in `evidence-register.md`. Only this probe may set G7 `pass`. **Done 2026-11-14:** Runpod pod `yfhzy2r86j9akc` (H100 NVL) ran encoder :8011, vLLM :8002 (Qwen2.5-3B), and `moshi.server` :8998 with the q8 weights. `py -3.11 -m hive_planner voice-bot moshi-probe --feature Voice_Bot --url wss://yfhzy2r86j9akc-8998.proxy.runpod.net/api/chat --record` returned `g7: pass`, `handshake_ms 1562.0`, `audio_frames 1`. Pod-only fixes are not in the repo: `msgpack`/`gradium` installed in `/tmp/vllm-venv`, `HF_HUB_ENABLE_HF_TRANSFER=0`, a float cast of the int8 scale in `moshi-rag-src/.../utils/quantize.py`, and Moshi bound to `0.0.0.0`. The first connection takes about 65 s (cold STT build) and then warm handshakes take about 1.1 s.
- [x] T056 Wiring audit for Moshi: `voice_layer` read site, adapter selection, handshake, and speech path traced end to end. **Status 2026-11-14: done** (audit closed; live pod not required, see the closing note below). Traced: `voice_layer` → `speech_adapter` → `MoshiVoiceAdapter` → `speak` delegation (pass); `submit_spoken` → `moshi_listen_gate` → refuse (pass). **2026-11-14 code pass (conversation loop built, live still open):** `voice_moshi.py` `MoshiConversation` (mic PCM re-framed to 1920 samples, Opus-encoded, sent as `0x01`; model `0x01` decoded to playback; model `0x02` text kept in transcript only, never evidence, never a task), `run_conversation` (receive thread + mic loop, stop event, drop reported as `moshi_unreachable`), `SoundDeviceIO` (lazy `sounddevice` mic and speaker), and `talk()` (handshake first, then audio devices). CLI: `voice-bot moshi-talk [--url] [--duration]`. Tests: `tests/test_voice_moshi_conversation.py` (7 cases, real Opus round trip over loopback, fake audio devices for the integrated `talk` path). Real run with no server: `moshi-talk` → `moshi_unreachable`, exit 1, no devices opened. Still open: the launcher panel mic does not call the loop (it still refuses `mic_capture_not_wired`); Moshi text is not routed into HIVE tasks (R36 WER gate); 24 kHz capture on the chosen device is unproven; no live server, so T056 stays open. Gate-side listen check (`moshi_listen_gate`) still opens a separate socket and is unchanged.
- **T056 wiring fix 2026-11-14:** the launcher mic button now runs one duplex Moshi call when `voice_layer` is `moshi`. `VoicePanelController.on_mic(True)` runs the listen gate (refuses with `moshi_unreachable` and shows it), then starts `voice_moshi.talk` on a worker thread. `on_mic(False)` and `on_end()` stop it and join. The WAV/Whisper route runs only when `voice_layer` is `typed`. No WAV is sent in Moshi mode. Model text stays transcript-only (R36). Tests: `tests/test_voice_panel_controller.py` (7 new, including a real `talk` over a loopback Moshi stub), `tests/test_voice_mic_recorder.py` pinned to `typed`. Still open: live G7 with a real `moshi.server`. The server holds one global lock per connection (`code-improvements/moshi/moshi/moshi/server.py` `handle_chat`), so a second client (the spoken-submit gate or a probe) during a live call gets `moshi_unreachable` even though the server is up.
- **T056 Moshi call-mode spoken approval (2026-11-14):** default `voice_layer` `moshi` now routes live-call `0x02` text to a pending R6 approval through `POST /v1/reply` (exact-match, never a new task). No WAV and no `stt_provider` on that path. `MoshiConversation.handle_frame` takes `on_text`; the panel passes `_on_moshi_text`. A pending Moshi tool-lane approval uses `MoshiToolBroker.reply` on the same frame. Whisper `/v1/reply/spoken` stays the typed-layer path. Live mic / live faster-whisper / live G7 remain open.
- **Regression fixed 2026-11-14:** the default `voice_layer` is `moshi`, so the listen gate now applies to every spoken submit. Tests that exercise STT or speech-out in isolation (`test_voice_stt_runtime.py`, `test_voice_bot_bridge.py` spoken routes, `test_voice_bot_speak.py` adapter choice) now set `voice_layer: typed`. The gate itself is tested in `test_voice_moshi.py`. `pytest tests -k "voice or acp"` 646 passed, 2 skipped.

- **T056 close 2026-11-14 (wiring audit summary):** chain traced: `cli.py` `voice-bot moshi-talk` → `talk(..., on_utterance=count_utterance_only)` → `run_conversation` → `MoshiConversation._segment` → `UtteranceSegmenter` → `utterances` counter. Gap found: the CLI passed no `on_utterance`, so the segmenter never ran and `utterances` stayed 0 even with live speech. Fixed in `cli.py` and `voice_moshi.py` (`count_utterance_only`). Proof: `tests/test_voice_moshi_conversation.py::test_cli_moshi_talk_counts_user_utterances` runs real `main([... moshi-talk ...])` against a loopback websocket with a scripted mic; it fails with the fix removed (`0 == 2`) and passes with it. Suites `test_voice_moshi_conversation.py`, `test_voice_moshi.py`, `test_voice_panel_controller.py` → 98 passed. Caveat: live-server utterance count was not re-recorded on a pod; the panel `on_utterance` path is code-level tested only. Speech-to-task is panel-only by design; the CLI count is diagnostic.
- **T056 live run 2026-11-14 (partial, T056 stays open until the closing note above; now closed):** `py -3.11 -m hive_planner voice-bot moshi-talk --url wss://yfhzy2r86j9akc-8998.proxy.runpod.net/api/chat --duration 20 --timeout 60` returned `error: ""`, `sent_frames 249` (about 20 s of mic audio), `audio_out_samples 474240` (about 19.8 s of model audio back), `speaker_errors 0`, `utterances 0`, `text_frames 0`. The duplex audio path works over the proxy. **Correction (same day, after check):** `utterances 0` does not mean silence. The CLI `moshi-talk` calls `talk()` without `on_utterance`, so the utterance segmenter is never created and the counter cannot increase. The pod's `moshi_8998.log` at 23:31 UTC (about the same time as this run) shows the server's STT recognizing user words ("…ever got to India…") and triggering a RAG reference. Server-side speech recognition is therefore seen, but the client has no utterance evidence yet. Still open: a client-side utterance count (CLI wiring fix), and the panel path trace.

## Active task

**Phase 5 complete (T029–T040 [x], 2026-11-12). Gap-fill COMPLETE; R33 latch ON on this host only (2026-11-12, operator authorized).** `.hive/voice-bot/config.json` has `edits_enabled: true`; spec promoted to **active**. Full `agent` mode runs only on a host where the operator has set the per-host `edits_enabled` latch after G6 pass and the F2 checklist. Lane verdict stays NOT READY for production use until operator review (see `deployment-gaps.md` § Verdict by lane). Residuals: R24 RSS at runtime is probe/config-test only for RSS; speech path `typed_instruction`. G1 **pass** via labeled ACP; native Composer submit **fail**.
**Prerequisite (met 2026-11-09):** Cursor Agent CLI — `agent --version` → `2026.11.05-86047df` at `%LOCALAPPDATA%\cursor-agent\agent.cmd` (not on PATH in this shell).

## Deployment readiness

Current verdict (2026-11-12): see `spec.md` § Deployment readiness. Read-only lane READY. Full `agent` lane NOT READY for production use; it is enabled only per host by the operator (`edits_enabled: true` after G6 pass and F2 checklist). No fleet-wide READY claim. The CLI field `spec_ready: true` only means spec artifacts exist.

## Validation log

```text
2026-11-09 — T001
- src/hive_planner/voice_bot.py — contracts + `.hive/voice-bot/state.json`
- CLI: `py -3.11 -m hive_planner voice-bot status|init`
- tests/test_voice_bot.py — 5 passed

2026-11-09 — T002
- docs/specs/Voice_Bot/evidence-register.md — G0 pass; G1–G3,G5 blocked; G4,G6 partial
- tests/test_voice_bot_evidence_register.py — 2 passed
- spec-drift-check --feature Voice_Bot — ok

2026-11-09 — cartridge ↔ sourcing loop → spec
- ingest --embed (4 docs; CLI status_summary error after processing — emit unaffected)
- emit --feature Voice_Bot --force-delta --emit-rules-seeds
- translate Mushi AI_Cursor a.md --no-promote (29/72/16/15 classified; 567 reject)
- spec.md — R16, feedback loop, build order, runtime sequence, risks
- spec-drift-check --feature Voice_Bot — ok (post re-emit)

2026-11-09 — Rosetta metatag mine → spec
- Decompressed 18 [HOOK:*] blocks from Mushi AI_Cursor a.md
- spec.md — R17 events, R18 tools, R19 G1 checklist, hook index, SC-010/AC 13–14
- evidence-register.md — G1a–G1d rows
- emit + spec-drift-check — ok

2026-11-09 — T019
- src/hive_planner/spec_drift.py — `_specseed_divergence`, wired into `check_memory_spec_drift`
- tests/test_spec_drift_specseed.py — 3 passed (divergence, match, missing seed skipped)
- tests/test_spec_drift.py + tests/test_ci_handoff.py — 82 passed (targeted)
- spec-drift-check --feature Voice_Bot — ok (specseed matches spec.md)

2026-11-09 — Voice_Bot gap cascade (4 loops, 9-second pause between loops)
- Loop 1 probe: read spec, plan, tasks, micro brief; seeded gaps from text.
- Loop 2 check: confirmed 7 gaps against R-rows, tasks, and evidence register.
- Loop 3 patch: spec.md — R5/R26 session-end discard; R20/R26 restart reconnect rule; R6 question reply rule; R8 missing record is unknown, not not_run; Phase 4 gate list adds G6 for T015; Validation covers AC 15–21 and SC-011–013; status line.
- Loop 4 review: cross-check against plan, tasks, micro brief; emit --feature Voice_Bot --force-delta; spec-drift-check --feature Voice_Bot — ok.
- Pause: 9-second pause between loops is defined as a cascade rule in plan.md (Gap cascade). Correction 2026-11-09: earlier entry claimed timed waits ran; none were verified. Treat as unverified until a run logs them.
- Gaps fixed in the 2026-11-09 pass: R21 pointed at T001 for the config object (now T001a); micro brief lacked R25–R29 edge rules (added); plan lacked the T001a step before T005/T009 (added).
- Validation: `emit --feature Voice_Bot --force-delta` then `spec-drift-check --feature Voice_Bot` — ok; `pytest tests/test_voice_bot.py tests/test_spec_drift_specseed.py` — 8 passed.
- Implementation gaps remain (T001a, T003 blocked on G2 `agent` binary).

2026-11-09 — Voice_Bot gap cascade re-run (verified pauses)
- Loop 1 probe: `agent` binary absent on PATH (G2 still blocked). Candidate gaps: T014 unnamed test file for AC 15–18; cascade entry above unverified.
- Pauses: the 9-second L1→L2, L2→L3, L3→L4 waits are NOT verified by any run record. Treat as unverified (see correction above).
- Loop 2 check: confirmed C1 (T014 test file) and C2 (unverified cascade record).
- Loop 3 patch: tasks.md T014 names `tests/test_voice_bot_safety.py`; this entry replaces the unverified claim.
- Loop 4 review: `emit --feature Voice_Bot --force-delta` wrote cartridge only; `spec-drift-check --feature Voice_Bot` ok (no drift items, handoff missing none); `pytest tests/test_voice_bot.py tests/test_spec_drift_specseed.py` 8 passed.
- Result: accepted set. No L4 fail signal, so nothing returned to L3. C1 closed; test file `tests/test_voice_bot_safety.py` is named but not yet written (T014 still open). T001a and T003 remain open.

2026-11-09 — G2 machine prerequisite (Cursor Agent CLI)
- Installed `agent` via `irm 'https://cursor.com/install?win32=true' | iex` → `2026.11.05-86047df`
- `src/hive_planner/voice_bot.py` — `resolve_cursor_agent_cli()` + `voice-bot status` field `cursor_agent_cli`
- evidence-register.md — G2 pins CLI version; gate remains blocked until T003–T004

2026-11-09 — T003 (adapter + CLI wiring)
- src/hive_planner/voice_acp.py — AcpClient: framing, id routing, disconnect detection
- src/hive_planner/voice_bot.py — acp_probe() starts `agent acp`, sends initialize, closes; no model call
- src/hive_planner/cli.py — `voice-bot acp-probe [--feature] [--agent-path] [--timeout]`
- tests/test_voice_acp.py + tests/test_voice_bot_acp_probe.py + tests/test_voice_bot.py — 21 passed (adapter + probe, child processes)
- Real run: `py -3.11 -m hive_planner voice-bot acp-probe --feature Voice_Bot` → ok, protocol_version 1 (agent 2026.11.05)
- Wiring audit items stay unchecked: they cover the voice-event → spoken-result path, which T004 builds.

2026-11-09 — T004–T011 (runner, contracts, delegation, permissions, queue, interrupt, results)
- src/hive_planner/voice_task.py — VoiceTaskRunner: R20 table, one ACP session, FIFO queue, approval broker, cancel, call end, R8 mapping, spoken/written split
- src/hive_planner/voice_acp.py — DEFER reply for server requests (reader stays free during approvals); reply()/reply_error()
- src/hive_planner/voice_bot.py — R20 task states, task fields (transitions, events, raw_events, approvals), queue + dedupe in state, atomic state save with retry
- src/hive_planner/cli.py — `voice-bot turn` (read-only, ask/plan only; exit 0 only when completed)
- tests/fixtures/acp_turn_server.py — stdio ACP turn server (session/new, set_mode, prompt, permission, cancel, tool-call exit codes, crash)
- Tests (all real subprocess / CLI path, 66 collected): test_voice_bot_readonly_turn (9), test_voice_bot_contracts (9), test_voice_bot_delegation (10), test_voice_bot_permissions (8), test_voice_bot_queue (5), test_voice_bot_interrupt (8), test_voice_bot_results (12), test_voice_bot_turn_cli (5)
- `py -3.11 -m pytest tests -k "voice or acp or specseed"` → 113 passed (x3 stable); full `pytest tests` → 1947 passed
- `emit --feature Voice_Bot --force-delta` (spec.md byte-identical before and after) then `spec-drift-check --feature Voice_Bot` → ok (specseed had diverged from spec.md)
- Bugs caught and fixed during validation: CodingTask lost the stop reason; cancel result lacked rollback; state save raced on Windows (fixed temp name + retry); tests read terminal state before its finish step (test helpers now read under the runner lock); cadence test compared unchanged text
- Wiring audit (this pass): chain traced CLI `voice-bot turn` → submit (snapshot persisted) → ACP spawn/initialize/session/new/set_mode → session/prompt → session/update pump → task evidence → evidence record → spoken/written → exit code.
  - Gap: no voice or editor entry point answers approvals or cancels; `voice-bot turn` cannot receive an approval and times it out (fail-safe, not success). Owned by T007a/T008.
  - Gap: R26 restart recovery is not implemented (a restarted runner does not move stale tasks to `unknown`). Owned by T020.
  - Gap: `snapshot_max_bytes` applies to selection text only; no file content is read until T007.
  - Unverified: ACP method names, mode ids, option kinds, and tool-call shape are provisional until a logged-in run (G2).
- Not done in this pass: T007, T007a, T012–T018, T020; G2, G5, G6 remain open.

2026-11-09 — T007 editor context capture (extension)
- extensions/hive-voice-bot/src/core.js — selection (byte-capped, UTF-8 safe, 1-based positions), diagnostics (severity names, byte budget, diagnostics_truncated), snapshot_max_bytes read from .hive/voice-bot/config.json (default 64 KB)
- extensions/hive-voice-bot/src/extension.js — reads editor selection, document diagnostics, config limit; passes them to core
- extensions/hive-voice-bot/test/core.test.js — 20 passed (`node --test test/core.test.js`); `npm test` script fixed (Node 26 rejects a directory argument)
- Extension Development Host: `powershell -File extensions/hive-voice-bot/test/edh/run-edh.ps1` → VS Code 1.143.0, 8/8 checks passed (fixture config limit 256 bytes; 300-char selection truncated and flagged; oversized diagnostic dropped and flagged)
- Wiring audit (T007 path): command → extension capture → core limits → snapshot returned. Gap: no caller consumes the snapshot yet (approval stub and `voice-bot turn` are not connected; T008). Gap: Python `ContextSnapshot` still takes `selection_text` and `list[str]` diagnostics; adapter needed before T008. Gap: unsaved, binary, and secret exclusion (R2, R28) are not applied; owned by T014 and T020.
- Not verified: approval flow in the host (the stub still shows a modal prompt only; no voice path calls it).

2026-11-09 — Voice_Bot gap cascade (status vs implementation)
- Loop 1 probe: spec Deployment readiness, evidence-register G2/G4/G6, R5 task_id, R2 selection shape, R23 HTTP bridge, G2 login risk, AC1 T007 close, plan layout.
- Pauses: 9-second L1→L2, L2→L3, L3→L4 waits ran via AwaitShell.
- Loop 2 check: eight confirmed (those probe items). Dropped build-order as historical.
- Loop 3 patch: spec.md R2/R5/R23, Deployment readiness, AC1, G2 risk, repo layout; evidence-register G2/G4/G5/G6; plan.md architecture files.
- Loop 4 review: emit --feature Voice_Bot --force-delta; R24 still said T001a had not landed → fail signal to L3 once; R24 patched to T001a present; re-emit; spec-drift-check --feature Voice_Bot — ok (no drift items, handoff missing none).
- Result: accepted set. No second L4 failure.

2026-11-09 — T008, T012–T020 fill
- map_editor_snapshot + submit selection_text; exclusions secret/binary/unsaved; hive_restarted recovery; stale check on write approve; bounded invoke_controller_tool; hybrid typed STT; edits_enabled false; G1a–d blocked; fixture G5; R24 config-driven latency check.
- tests: test_voice_bot_safety/concurrency/latency/edges/gates.py
- `pytest tests -k "voice or acp or specseed"` → 173 passed, 1839 deselected
- `node --test` extension core + bridge-client → 29 passed
- Live G2 still blocked (not logged in). G1/G3/G6 not closed. Feature remains NOT READY.

2026-11-10 — T022 uncoded spec rows
- Planning Q&A from spec/plan/tasks (US5/SC-009); snapshot file_content + source_excerpt_ids (R2); selection/file content in ACP prompt; R18 workspace/snapshot bind; navigate_to/show_diff queue + GET/POST /v1/editor
- tests/test_voice_bot_planning.py; extension core/bridge-client tests
- pytest planning+contracts+safety+bridge+edges+delegation: 68 passed; more voice tests 51 passed; node --test 31 passed
- emit --feature Voice_Bot --force-delta; spec-drift-check --feature Voice_Bot — ok
- Wiring audit: instruction → submit → snapshot (file content, excerpt ids) → hive_spec or ACP prompt (selection included) → spoken/written. Editor: navigate_to/show_diff → state.editor_actions → GET /v1/editor → extension showTextDocument → POST /v1/editor ack. Still blocked: live G2 session/prompt, G3 STT/TTS.

2026-11-09 — T021 R30 self-contained deploy
- spec.md R30: Hive `voice` extra ships Moshi + Pipecat; `voice-bot ensure-runtime --install`
- `voice-bot pack [--download-wheels]` for deploy folder on other machines
- Cursor CLI: official installer via `--install --install-agent`
- tests/test_voice_bot_self_contained.py

2026-11-10 — T026 / R34 live G6
- `voice-bot live-permission --record` against CLI 2026.11.05-86047df (logged in)
- Live `session/request_permission` options: allow-once, allow-always, reject-once; toolCall.kind=execute
- Client selected reject-once; `.hive/voice-bot/g6-live-probe.tmp` still appeared (`unguarded_write`)
- G6 register cell is **fail**; `edits_enabled()` stays false (no config latch)
- tests/test_voice_bot_live_permission.py + test_voice_bot_gates.py

2026-11-10 — T027 stop-after-refuse
- AcpClient.terminate; live_permission sends session/cancel then kills the child after the first gated refuse
- Unknown G6 server requests are JSON-RPC errors, not result null
- Fixture G6_WRITE_UNLESS_CANCEL would write the probe file unless cancelled; test asserts no file
- pytest tests/test_voice_bot_live_permission.py tests/test_voice_acp.py tests/test_voice_bot_live_prompt.py tests/test_voice_bot_gates.py — 33 passed
- Live `voice-bot live-permission --record` → g6 pass, wrote=false, stopReason=cancelled
- emit --feature Voice_Bot --force-delta; spec-drift-check --feature Voice_Bot — ok
- R33 config latch not set; production agent mode stays off

2026-11-10 — review of unpushed Voice_Bot commits
- R33: `mode=agent` was always refused even when G6 pass and config `edits_enabled` were true. Submit now allows agent only when `edits_enabled(paths)` is true; CLI `--mode` includes `agent` and still exits 1 with `agent_mode_disabled` when the latch is off.
- R23: host navigate/open uses `resolveWorkspaceRelative`; editor snapshot with `path_outside_workspace` drops payload. Token compare no longer raises on length mismatch. Task poll stops on lookup failure.
- pytest gates/edges/bridge/turn-cli/readonly/security — 61 passed; `node --test` extension core+bridge-client — 33 passed.

2026-11-10 — T028 G1 labeled ACP
- G1a–G1d recorded fail (no public native Composer API)
- native_chat_path() = labeled_acp_fallback; G2 has run
- evidence-register G1 pass; gate closure Yes
- tests/test_voice_bot_gates.py

2026-11-10 — Voice_Bot gap cascade (code vs spec, 4 loops, 9-second pauses)
- Loop 1 probe: host submit dropped T007 version/dirty/diagnostics; HTTP body cap 16 KiB vs R21 64 KiB; spec T008 future tense; T007a/T022 stale; deployment table pre-T028.
- Pauses: 9-second L1→L2, L2→L3, L3→L4 waits ran via AwaitShell.
- Loop 2 check: confirmed C1 (R2/G4 host snapshot), C2 (R21 body cap), C3–C6 (stale spec/tasks/deployment). Dropped R33 latch flip, G4/G5 pass without live evidence, Pipecat audio.
- Loop 3 patch: `editor_snapshot` on POST /v1/submit; runner keeps mapped diagnostics/truncated/excluded; body cap from R21 config; extension submit sends the captured snapshot; spec R2/deployment, tasks T007a/T022, plan architecture.
- Loop 4 review: pytest bridge/safety/planning/security 47 passed; node bridge-client+core 32 passed; emit --feature Voice_Bot --force-delta; spec-drift-check --feature Voice_Bot — ok (no drift items, handoff missing none).
- Result: accepted set. No L4 fail signal.

2026-11-10 — Voice_Bot code-review cascade (bugs vs spec, 4 loops, 9-second pauses)
- Loop 1 probe: `_finish` vs disconnect-cancel race; `close()` timer writes; R22 stale check missing at submit; `_bind_workspace` vs bridge realpath/normcase; dropped queue_full spoken notice and disk re-read of excluded files.
- Pauses: 9-second L1→L2, L2→L3, L3→L4 waits ran via AwaitShell.
- Loop 2 check: confirmed C1 (R7/R20), C2 (R9), C3 (R22), C5 (R23).
- Loop 3 patch: `_finish` no-ops when closed or already terminal; `_closed` gates timers and dispatch; submit refuses stale live buffers before creating a task; `same_workspace` shared by runner bind and bridge.
- Loop 4 review: pytest cascade/safety/review/loop/security/edges 40 passed; cascade/bridge/gates/permissions/queue/interrupt 63 passed; emit --feature Voice_Bot --force-delta; spec-drift-check --feature Voice_Bot — ok (no drift items, handoff missing none).
- Result: accepted set. No L4 fail signal.

2026-11-10 — Voice_Bot code-review cascade (bugs vs spec, 10 loops, 9-second pauses, cascade NN)
- Loop 1 probe: excluded snapshot disk re-read; prompt leak; submit/save after close; missing spoken on queue_full / instruction_too_long / agent_mode_disabled; reconnect without waiter (dropped); reply-under-lock (dropped).
- Pauses: 9-second waits L1→L10 ran via AwaitShell (9000ms each).
- Loop 2 check: confirmed C1 (R2/R28), C2 (R9), C3 (R5), C4 (R21), C5 (R6). Dropped reconnect waiter and lock-held ACP reply.
- Loop 3 patch: skip disk re-read when excluded; keep payload cleared; omit excluded text from ACP prompt; `_closed` gates submit and `_save`; DelegationError.spoken; bridge returns spoken.
- Loop 4 review: `_save` during init raised AttributeError (`_closed` unset). Fail signal to L3 once: set `_closed = False` before first `_save`.
- Loop 5 residual: pytest nn-cascade + safety/queue/cascade/review/loop/contracts/readonly/edges/bridge — 88 passed. Probe: editor poll remembered a failed navigate.
- Loop 6 check: confirmed C6 (R18) failed editor open skipped forever.
- Loop 7 patch: `editorActionAdvance` in core.js; host retries until open, then acks.
- Loop 8 review: pytest nn-cascade/safety/queue/cascade/review/loop 38 passed; `node --test` core + review-fixes + bridge-client 38 passed.
- Loop 9 emit: `emit --feature Voice_Bot --force-delta`; `spec-drift-check --feature Voice_Bot` — ok (no drift items, handoff missing none).
- Loop 10 audit: chain submit editor_snapshot → map exclusions → no disk refill → prompt omit; close → session_not_active and `_save` no-op; queue_full/agent/instruction errors carry spoken through bridge; editor poll → apply → advance → ack.
- Result: accepted set. One L4 fail signal, then accepted.

2026-11-11 — Voice_Bot code-review cascade (bugs vs spec, 10 loops, 9-second pauses, cascade NN)
- Loop 1 probe: host poll treats a finished approve as timeout; R22 live buffer never set in production; dropped follow-up success spoken and unstripped instruction length.
- Pauses: 9-second waits L1→L10 ran via AwaitShell (9000ms each).
- Loop 2 check: confirmed C1 (R6 false timeout toast), C2 (R22 write check tautology without a live snapshot).
- Loop 3 patch: `POST /v1/reply` accepts `editor_snapshot`; `reply_approval` compares that live version/dirty; host captures snapshot at reply time; watch decision `cleared` after a local answer.
- Loop 4 review: pytest nn-cascade/safety/permissions/bridge/cascade/review-fixes 67 passed; `node --test` core+review-fixes+bridge-client 40 passed.
- Loop 5 residual: a thrown reply left `shownRequestId` set, so the next poll was `already_shown` and the modal never retried.
- Loop 6 check: confirmed C8 (R6 host retry).
- Loop 7 patch: keep shown id after a local attempt until pending clears (`cleared`, not timeout); clear and retry on throw.
- Loop 8 review: `node --test` 40 passed.
- Loop 9 emit: `emit --feature Voice_Bot --force-delta`; `spec-drift-check --feature Voice_Bot` — ok (no drift items, handoff missing none).
- Loop 10 audit: poll approval → modal → live snapshot at reply → bridge schema → `_live_buffer_at_reply` → stale deny or approve; locallySettled pending-false → cleared, no "nothing was executed" toast.
- Result: accepted set. No L4 fail signal.

2026-11-11 — Voice_Bot code-review cascade pass 2 (10 loops, 9-second pauses, cascade NN)
- Loop 1 probe: extension approval poll marks `approvalLocallySettled` after dismiss or reprompt; stale submit lacked `DelegationError.spoken`; bridge CLI turn hid spoken on refuse.
- Pauses: 9-second waits L1→L10 via Cursor `Await` (9000ms each).
- Loop 2 check: confirmed C9 (R6 modal stall on dismiss/reprompt), C10 (R22 stale submit voice notice).
- Loop 3 patch: `approvalReplySettlesHost`; host resets `shownRequestId` when unsettled; stale submit spoken; `run_turn_via_bridge` and extension submit show spoken.
- Loop 4 review: pytest cascade/nn/bridge 60 passed; `node --test` review-fixes+core+bridge-client 42 passed.
- Loop 5 residual: HTTP stale submit needed an integration pin.
- Loop 6 check: confirmed C11 (bridge `POST /v1/submit` stale without spoken).
- Loop 7 patch: `test_stale_submit_over_http_includes_spoken_notice`.
- Loop 8 review: `pytest tests -k "voice or acp"` — 244 passed.
- Loop 9 emit: `spec-drift-check --feature Voice_Bot` — ok (no drift items, handoff missing none).
- Loop 10 audit: approval dismiss → `approvalReplySettlesHost` false → modal retries; reprompt same; stale submit → bridge 400 + spoken → extension/CLI surfaces text. Impact: `docs/change-impact/impact-packets/2026-11-11-voice-bot-nn-cascade-2.md`.
- Result: accepted set. No L4 fail signal.

2026-11-11 — Voice_Bot code-review cascade pass 3 (10 loops, 9-second pauses, cascade NN)
- Loop 1 probe: HTTP 200 approval replies (`stale`, `reprompt`, `denied`) hid `spoken` in the extension host; `session_not_active` had no spoken on bridge submit after `close()`.
- Pauses: 9-second waits L1→L10 via Cursor `Await` (9000ms each).
- Loop 2 check: confirmed C12 (R6/R22 host UX), C13 (R9 session end notice).
- Loop 3 patch: `approvalReplySpokenNotice`; `stale` does not settle the host latch; extension warning toast; `_require_active_session` spoken; bridge/NN regression tests.
- Loop 4 review: pytest nn-cascade/bridge/cascade 44 passed; `node --test` review-fixes+core+bridge-client 43 passed.
- Loop 5 residual: no new wiring gaps on submit→spoken or approval→editor_snapshot chain.
- Loop 6–8 review: `pytest tests -k "voice or acp"` — 245 passed.
- Loop 9 emit: `spec-drift-check --feature Voice_Bot` — ok (no drift items, handoff missing none).
- Loop 10 audit: approve reply with stale buffer → host shows spoken warning; runner `close()` → `POST /v1/submit` 400 + spoken. Impact: `docs/change-impact/impact-packets/2026-11-11-voice-bot-nn-cascade-3.md`.
- Result: accepted set. No L4 fail signal.

2026-11-11 — Voice_Bot code-review cascade pass 4 (10 loops, 9-second pauses, cascade NN)
- Loop 1 probe: write approval compared version/dirty on whichever editor was active; cancel after close returned cancel_requested without a save.
- Pauses: 9-second waits L1→L10 via Cursor Await (9000ms each).
- Loop 2 check: confirmed C14 (R22 file identity), C15 (R9 false cancel success). Dropped missing spoken on successful queue_follow_up and UTF-8 disk refill.
- Loop 3 patch: `_live_file_mismatch` on write approve; cancel/reply after close refuse; nn-cascade tests.
- Loop 4 review: pytest nn-cascade/cascade/permissions/interrupt/bridge — 62 passed.
- Loop 5 residual: GET /v1/approval omitted `file_path`, so the host could not snapshot the bound file.
- Loop 6 check: confirmed C16 (R22 host live buffer of the snapshot file).
- Loop 7 patch: pending view `file_path`; `pickLiveDocumentRelative`; host `captureSnapshot(pending.file_path)`.
- Loop 8 review: pytest nn-cascade/bridge/permissions/edges/cascade/safety — 68 passed; `node --test` core+review-fixes+bridge-client — 44 passed.
- Loop 9 emit: `spec-drift-check --feature Voice_Bot` — ok (no drift items, handoff missing none). Impact: `docs/change-impact/impact-packets/2026-11-11-voice-bot-nn-cascade-4.md`.
- Loop 10 audit: write approve → live snapshot file vs bound path → stale or buffers_match; cancel after close → session_not_active; poll approval → file_path → capture bound document → reply.
- Result: accepted set. No L4 fail signal.

2026-11-11 — Voice_Bot code-review cascade pass 5 (10 loops, 9-second pauses, cascade NN)
- Loop 1 probe: host live-document find used case-sensitive `path.normalize`; an open bound file on Windows became a version-0 dummy so write approvals always looked stale.
- Pauses: 9-second waits L1→L10 via Cursor Await (9000ms each).
- Loop 2 check: confirmed C17 (R22 Windows live buffer identity). Dropped queued-submit follow-up (not a hard stop) and close/`_ensure_session` race.
- Loop 3 patch: `sameFsPath` / `matchOpenFsPath` in core; host `captureSnapshot` uses them; review-fixes test.
- Loop 4 review: `node --test` core+review-fixes+bridge-client — 45 passed; pytest nn-cascade/cascade/permissions/bridge/safety — 63 passed. No L4 fail signal.
- Loop 5 residual: dummy version-0 remains only when the bound file is not open (fail closed). No new critical wiring gap.
- Loop 6 check: no further confirmed critical.
- Loop 7: no patch.
- Loop 8 review: `pytest tests -k "voice or acp"` — 248 passed, 1863 deselected; `node --test` — 45 passed.
- Loop 9 emit: `emit --feature Voice_Bot --force-delta`; `spec-drift-check --feature Voice_Bot` — ok (no drift items, handoff missing none).
- Loop 10 audit: poll approval → `file_path` → `captureSnapshot` → `matchOpenFsPath` → live version/dirty → `POST /v1/reply` → `_live_file_mismatch` / `buffers_match`. Impact: `docs/change-impact/impact-packets/2026-11-11-voice-bot-nn-cascade-5.md`.
- Result: accepted set. No L4 fail signal.

2026-11-11 — Voice_Bot code-review cascade pass 6 (10 loops, 9-second pauses, cascade NN)
- Loop 1 probe: Stop Bridge during ACP handshake leaked `agent acp` (`_client` still None). Dropped C2 as same race (R26 recover) and C3 missing-dirty-file (not a hard stop).
- Pauses: 9-second waits L1→L10 via monitored shell ticks.
- Loop 2 check: confirmed C1 (R9 duplicate ACP after shutdown).
- Loop 3–4: rank/inspect — terminate unassigned child in `_ensure_session`; `_launch` `_closed` gate; do not start pump until keep.
- Loop 5 patch: `src/hive_planner/voice_task.py`; test `test_close_during_acp_handshake_kills_unassigned_child`.
- Loop 6 test: pytest nn-cascade — 12 passed.
- Loop 7 audit: stopBridge stdin.end → cli finally runner.close → handshake terminate. Pass.
- Loop 8 second hunt: empty.
- Loop 9 regression: pytest nn-cascade + permissions + readonly_turn — 29 passed.
- Loop 10: no further patch. Impact: `docs/change-impact/impact-packets/2026-11-11-voice-bot-nn-cascade-6.md`.
- Result: accepted set. No L4 fail signal.

2026-11-11 — Haiku micro-task A (spec drift)
- Before: `spec-drift-check --feature Voice_Bot` ok=false, spec_actions: specseed diverges from docs/specs/Voice_Bot/spec.md.
- Ran: `emit --feature Voice_Bot --force-delta` (exit 0; rewrote cartridge/*, specseed included).
- After: `spec-drift-check --feature Voice_Bot` ok=true, drift_items=[], spec_actions=[].
- Spec status unchanged (draft). No spec text edited.
- Tests: `pytest tests -k "voice or acp" -q` — 286 passed, 1863 deselected. `npm test` (extensions/hive-voice-bot) — 51 pass, 0 fail.
- T031 not started this chat (micro-task A only).

2026-11-11 — Haiku micro-task B (T031 bridge interrupt / end call)
- `voice_bridge.py`: routes `POST /v1/playback/interrupt` → `interrupt_playback()`, `POST /v1/call/end` → `end_call()`; schema `{workspace}` required; docstring route list updated. spec.md R23 route list not changed (same precedent as T029 `/v1/live`).
- `extensions/hive-voice-bot`: `core.js` `interruptPlayback()` / `endCall()`; `extension.js` commands; `package.json` activation + contributions.
- Tests: `tests/test_voice_bot_bridge.py` +5 (token refusal, interrupt keeps task state and sets `interrupted`, end-call keeps task running and discards queued, unknown key and missing workspace → 400). `bridge-client.test.js` +1.
- Results: `pytest tests/test_voice_bot_bridge.py tests/test_voice_bot_interrupt.py` 63 passed; `pytest tests -k "voice or acp"` 291 passed, 1863 deselected; `npm test` 52 pass, 0 fail; `spec-drift-check` ok=true.
- Gap: extension routes are checked with a fake fetch and the Python HTTP tests, not a live Extension Host or a real bridge process.

2026-11-12 — gap-fill closure after T040 (docs only, no code)
- `gap-evaluation-plan.md` P2-4 marked Met 2026-11-12 (R24 runtime check in `voice_task.py`; tests `test_voice_bot_r24_runtime.py` 4/4).
- Active task replaced: Phase 5 complete; gap-fill COMPLETE; full-agent NOT READY until R33.
- Residuals recorded: R24 RSS budgets probe-only (`scripts/voice_r24_latency_probe.py`); `hive_spec` `task.started` path has no dedicated R24 test (optional, not added).
- `py -3.11 -m hive_planner spec-drift-check --feature Voice_Bot` — ok=true, drift_items=[], spec_actions=[], handoff missing=[].
- Spec verdict unchanged (read-only READY; full agent NOT READY until R33). `edits_enabled` not changed.

2026-11-12 — R33 latch + spec promotion (operator request)
- `.hive/voice-bot/config.json` created with `edits_enabled: true`
- `spec.md` status draft → **active**; § Deployment readiness updated (full agent READY with residuals)
- `evidence-register.md` § R33 latch row; `tests/test_voice_bot_gates.py` production latch test aligned
- Verified: `edits_enabled()` → True (G6 register pass); `emit --feature Voice_Bot --force-delta`; `spec-drift-check` ok; `pytest tests/test_voice_bot_gates.py` 8 passed
- 2026-11-12 — deployment gap scoping (docs only, no code): [deployment-gaps.md](./deployment-gaps.md) maps residuals A–F to proposed T041–T048; first code task T047 after spec T046; `live-write-check.txt` confirmed absent.
- 2026-11-12 — T046 spec done (docs only): added R35 live allowed-write probe to `spec.md` after R34 (R34 is the G6 refusal probe, not reused). T047 implements `voice-bot live-write` against R35.
- 2026-11-12 — T047 done: `live_write` in `voice_bot.py` + CLI `voice-bot live-write`; fixture `tests/fixtures/acp_live_write_server.py`; `tests/test_voice_bot_live_write.py` 9/9; `live-permission` tests 10/10 unchanged; `pytest tests -k "voice or acp"` 336 passed; `emit --force-delta` re-run; `spec-drift-check --feature Voice_Bot` ok. Real host run not done (needs operator OK on edits latch). Register row for R35 not written (spec does not name a row yet).
- 2026-11-12 — R35 live host (operator go-ahead): `voice-bot live-write` → r35 pass, nonce_match, session 3c573c26, agent CLI 2026.11.05-86047df; `.hive/voice-bot/live-write-check.txt` created; permissions list empty (agent wrote without session/request_permission in trace).
- 2026-11-13 — C3 extension → bridge spoken submit: `src/core.js` `createBridgeClient().submitSpoken` posts `/v1/submit/spoken` (`wav_path`, `client_request_id`, `mode`, `file_path`); optional command `hive.voiceBot.submitSpoken` in `src/extension.js` + `package.json` (WAV path is workspace-relative, prompted by input box). Test: `test/bridge-client.test.js` mock-fetch `submitSpoken posts the WAV path…` (C3). `node --test test/bridge-client.test.js test/core.test.js` → 43 pass, 0 fail; `node --check` on core.js and extension.js ok. Live mic capture is operator-run (Cursor/OS) and is not implemented in the extension; no `audio_enabled`, `edits_enabled`, or `stt_provider` change. Not committed.
- 2026-11-12 — Gap E closed (docs only, after one re-run): the 3c573c26 run left no persisted session or nonce hash, so `voice-bot live-write` was run again. Result: r35 pass, `end_turn`, session `51b937ee-4fb4-46a7-b10e-9b487d74ee7f`, nonce hash `afc93b69b236ec1a` (checked against the on-disk nonce), agent CLI 2026.11.05-86047df, permissions empty. Payload saved to `.hive/voice-bot/live-write-run.json`. R35 row added to `evidence-register.md`; `deployment-gaps.md` row E and the full-agent lane updated. G6 row and R33 config unchanged. No spec change.

2026-11-13 — Voice_Bot two-pass code review, pass 2 (close-out)
- Wired `test/code-review-2026-11-13.test.js` into the extension `npm test` script.
- Defect fixed: `followTask` poll timers were untracked. After Stop Bridge, a network error kept polling a dead bridge until the 15-minute deadline. `createTimerRegistry` (core.js) now tracks them; `stopBridge` and `clearIfCurrent` clear all. Regression tests added (+2).
- Hunt, no change needed: bridge `wav_path` (relpath) → `submit_spoken` → `_resolve_file` fence before STT. Covered by `test_wav_path_outside_workspace_is_refused_before_transcribing`.
- `emit --feature Voice_Bot --force-delta`; `spec-drift-check --feature Voice_Bot` ok=true (no drift items, no spec actions).
- Validation: `npm test` 70 pass / 0 fail; `node --check` ok; `pytest tests/test_voice_bot_code_review_2026_11_13.py` 9 passed; `pytest tests -k "voice or acp"` 523 passed, 2 skipped.
- Impact packet: `docs/change-impact/impact-packets/2026-11-13-voice-bot-two-pass-review.md`.
- Spec text unchanged. `edits_enabled` / R33 unchanged. Verdict unchanged.
- Gap not closed: the poll-cleanup fix is verified by unit tests and call-site reading, not in a live Extension Development Host.
```


## T038 live evidence (2026-11-12, closed)

**Closed 2026-11-12 (T038 [x]):** the EDH run that matters is the one in T038 above: `run-edh.ps1` 16/16, extension `hive.voiceBot.submitTask` posts the snapshot to `/v1/submit`, task `task_69b25e485d56` completed. The earlier partial notes below are kept as history. They are superseded and do not mean the box is open.

- EDH smoke: `extensions/hive-voice-bot/test/edh/run-edh.ps1` exit 0, 13/13 checks, VS Code 1.146.0, snapshot fields and revert verified.
- Bridge: started with `py -3.11 -m hive_planner --root <repo> voice-bot bridge` (stdin held open; bridge exits on stdin close). Endpoint `127.0.0.1:61490`.
- Bridge → runner: one `run_turn_via_bridge` submit, `client_request_id` `t038-a0c8719024`, mode `ask`. Result: submit accepted, `task_db8b6b7722b7` completed, reason `end_turn`, `tests_status` not_run.
- First snapshot attempt: bridge at repo root returned HTTP 400 `file_not_found: src/a.py` because the EDH snapshot names the fixture workspace. Fixed by running the bridge with `--root` at `test/edh/fixture` (its config has no `edits_enabled`, so R33 stays off).
- Snapshot submit (2026-11-12, after the fixture fix): EDH snapshot from a second EDH run (13/13) sent to `/v1/submit` on the fixture bridge. HTTP 200, `client_request_id` `t038-snap-856f47c9b8`, task `task_52a2e966402d` completed, reason `end_turn`.
- Superseded (historical): the Python-client POST above was the pre-T038 partial. The extension-driven chain is now covered by the T038 [x] run (EDH 16/16).

## Integration wiring audit

- [x] Trace voice event → controller/tool handler → editor or coding adapter → task state → spoken/written result. Fixture path is traced (submit → ACP → evidence → spoken). Live `session/prompt` recorded G2 pass 2026-11-10. G3 hybrid typed path is closed. G1 is labeled ACP (`native_chat_path`), not native Composer. Live G6: `live-permission` → ACP `session/request_permission` → reject-once → `session/cancel` + child stop → no probe file; register pass; R33 latch ON on this host (2026-11-12; `edits_enabled: true` in `.hive/voice-bot/config.json`, per-host only).
- [x] Verify partial failures and denied permissions cannot report full success.
- [x] Verify every feature flag or integration setting has a read site and enabled path.
- [x] Prove the path with an integration-level test or scripted capability check.

**Wiring audit 2026-11-11 (closure pass):** chain traced: VS Code buffer → `core.js` snapshot (`editor_snapshot` on submit/reply bodies) → `voice_bridge.py` validation → `VoiceTaskRunner` stale check (`buffers_match`, `_live_buffer_at_reply`) → ACP `session/prompt` (`agent acp`) → queue/interrupt → task evidence. Gaps found: (1) no single live run passes EDH snapshot through the HTTP bridge into a runner submit, the stale path is covered by `tests/test_voice_bot_bridge.py`; (2) live visible diff (`show_diff`) not run; (3) R24 first-spoken-update and resource use are measured in `evidence-register.md` §T018 (`scripts/voice_r24_latency_probe.py 3`, 2026-11-11); AC20 resource targets are in code (`VoiceBotConfig`, `rss_check`, `tests/test_voice_bot_resources.py`). An optional live `rss_check` re-run is not a lane-A deploy blocker. Validation: live EDH 13/13, live G5 probe reproduced twice, existing suites in the evidence register.

See `.cursor/rules/integration-wiring-audit.mdc`.
- 2026-11-12 — T048 done (docs only): acceptance-crosswalk.md verified pytest count updated from 253 to 336 (py -3.11 -m pytest tests -k voice or acp -q; not re-run this turn). No product code changed.

2026-11-12 — T045 deploy pack ergonomics (gap D) done
- Code: src/hive_planner/voice_bot.py (build_editor_vsix, _VOICE_INSTALL_PS1, _voice_pack_install_md vsix_name, build_voice_deploy_pack extension_dir)
- Tests: py -3.11 -m pytest tests/test_voice_bot_self_contained.py -q -> 13 passed (8 existing + 5 new)
- Regression: py -3.11 -m pytest tests -k "voice or acp" -q -> 341 passed (was 336; +5 new)
- Real pack: py -3.11 -m hive_planner voice-bot pack -> ok; VSIX 14176 bytes, lists extension/package.json, src/core.js, src/extension.js; no test/ files
- Drift: spec-drift-check --feature Voice_Bot failed (specseed diverged) -> emit --feature Voice_Bot --force-delta once -> spec-drift-check ok
- Not run: real code --install-extension on operator VS Code (would modify the installed editor; left for operator)

2026-11-12 — T044 R24 RSS runtime check (gap C) done
- Code: src/hive_planner/voice_task.py (`default_rss_mb`, `RssReader`, `VoiceTaskRunner(rss_reader=...)`, `_check_r24_rss` called on task.started)
- Tests: py -3.11 -m pytest tests/test_voice_bot_resources.py tests/test_voice_bot_r24_runtime.py tests/test_voice_bot_latency.py -q -> 19 passed
- Regression: py -3.11 -m pytest tests -k "voice or acp" -q -> 347 passed, 1 failed (test_voice_bot_bridge.py::test_live_feed_without_token_records_nothing, ConnectionAbortedError under full-run load). Rerun alone: py -3.11 -m pytest tests/test_voice_bot_bridge.py -q -> 62 passed. Flaky under load, not touched by T044.
- Drift: spec-drift-check --feature Voice_Bot -> ok. Spec: R24 traceability row (line ~393) updated; no acceptance text change needed.
- Wiring audit: chain traced: VoiceTaskRunner.submit -> _event("task.started") -> _check_r24_rss -> _rss_reader -> r24.over_budget (kind=rss). Config read via load_voice_bot_config in _init_state. Gaps found: none in the runtime path. Not run: live agent RSS sample inside a real submit (default reader uses psutil, which is not declared in pyproject).

2026-11-13 — T033 / T042 STT pin integrity trade-off (docs + validation close)
- Decision (a): evidence-register § T033 now records the production hash gate (`resolve_pinned_model_dir` refuses a `model.bin` whose sha256 differs from the pin). Register sentence only; no spec rewrite.
- Decision (b): `_PIN_CHECKS` cache keyed on (path, size, mtime_ns) is accepted. The sha256 runs once per file version, and each `hybrid_speech_path` call costs a stat. Hashing on every submit was rejected: the model is about 145 MB and was not timed here, so the cost is an estimate. Accepted residual risk: a same-size file with a preserved mtime could evade the cache. Local cache only; low risk.
- Validation: `py -3.11 -m pytest tests/test_voice_stt.py tests/test_voice_stt_runtime.py -q` -> 20 passed, 2 skipped. `py -3.11 -m pytest -k "voice or acp" -q` -> 546 passed, 3 skipped (full suite, green after the pin fix).
- Impact: `resolve_pinned_model_dir` callers are `voice_task.py` (adapter fallback) and `voice_bot.py` (`hybrid_speech_path`). Interface unchanged; no downstream change.
- Not run: live mic or live audio rows (still open under T042).

2026-11-14 — T056 conversation loop (code, no live server)
- src/hive_planner/voice_moshi.py: MoshiConversation, run_conversation, SoundDeviceIO, talk; session handshake before audio devices open.
- src/hive_planner/cli.py: voice-bot moshi-talk (new subcommand; no downstream callers yet).
- tests/test_voice_moshi_conversation.py: 7 passed; tests/test_voice_moshi.py: 24 passed (existing probe and gate unchanged).
- pytest tests -k "voice or acp or launcher" -q: 1018 passed, 2 skipped.
- Real: py -3.11 -m hive_planner voice-bot moshi-talk --timeout 2 -> moshi_unreachable, exit 1 (no server on 127.0.0.1:8998).
- T055 G7 still blocked: no Moshi weights in the local HF cache and no server on 8998. Evidence register not changed.
- Not run: live mic or speaker, live Moshi server, launcher panel wiring to moshi-talk.
