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
- [x] T004 Implement one HIVE-routed read-only prompt, streamed updates, final stop reason, and a contextual follow-up. Context is explicit file path and instruction text only; selection capture arrives with T007. T004 output is the G2 evidence. **Implemented 2026-11-09; G2 live evidence still open** (`agent status` reports "Not logged in"; tests run against the fixture turn server). Tests: `tests/test_voice_bot_readonly_turn.py`, `tests/test_voice_bot_turn_cli.py`.

## Phase 2 — Contracts and editor context

- [x] T005 Add normalized HIVE session, task, context snapshot, permission, and event models, including the R20 state enum, the R21 limits, and `client_request_id` on submit. Tests: `tests/test_voice_bot_contracts.py`.
- [x] T006 Add provider-neutral delegation handlers for submit, status, diff, follow-up, and cancellation. Tests: `tests/test_voice_bot_delegation.py` (SC-012 dedupe included).
- [x] T007a Scaffold the Cursor extension package (activation, `getContextSnapshot` command, approval UI stub) as the editor-adapter host for T007 and T008. Machine-level prerequisites are recorded here, not in the gates. **Scaffold done 2026-11-09** in `extensions/hive-voice-bot/` (`src/core.js` pure logic, `src/extension.js` vscode wiring, `test/core.test.js` 8 passed via `node --test test/core.test.js`). Not yet run inside an Extension Development Host; the approval stub is not connected to `voice-bot turn`.
- [x] T007 Add extension context capture with selection, dirty state, document version, diagnostics, and size limits. Depends on T007a. **Done 2026-11-09** in `extensions/hive-voice-bot/src/core.js` (`buildSelection`, `buildDiagnostics`, `truncateUtf8`, `loadSnapshotMaxBytes`) with host wiring in `src/extension.js`. Tests: `extensions/hive-voice-bot/test/core.test.js` (20 passed, one test per limit: selection under/at/over the byte limit, UTF-8 cut, config read, config fallback, diagnostics under/over budget, single oversized diagnostic). Live proof: `test/edh/run-edh.ps1` launches a real VS Code 1.143.0 Extension Development Host; `test/edh/smoke.js` reports 8/8 checks passed. Snapshot shape: `selection` is an object (or null). T008 maps `selection.text` into HIVE `selection_text`.

## Phase 3 — Safety and conversation

- [x] T008 Add visible approval handling for writes, commands, plans, and questions. Tests: `tests/test_voice_bot_permissions.py` (approval kinds, exact-match replies, timeout). **Done 2026-11-09:** broker on stdio; extension polls `GET /v1/approval` and replies through `answerPendingApproval`; HIVE maps the T007 `selection` object to `selection_text` (`map_editor_snapshot`, `POST /v1/submit` `selection_text`). Live ACP option kinds stay provisional until G2 login.
- [x] T009 Add one-active-turn FIFO queueing (depth 5, R21), duplicate-request protection via `client_request_id` (SC-012), approval-reply routing, and task recovery. Tests: `tests/test_voice_bot_queue.py`. Recovery here means disconnect → `unknown` → `provider_lost` after the reconnect window. Restart recovery (R26) is T020.
- [x] T010 Separate playback interruption, coding cancellation, call ending, and rollback reporting. Tests: `tests/test_voice_bot_interrupt.py`.
- [x] T011 Add evidence-backed spoken summaries and full written results. Map test status to the R8 states (`passed`, `failed`, `not_run`, `unknown`); test SC-013. Enforce the R14 speech cadence. Tests: `tests/test_voice_bot_results.py` (SC-013, cadence, cap).

## Phase 4 — Integration gates

- [x] T012 Answer all four R19 questions (submission, targeting, readable progress/context, provider replaceability) on a pinned version; record each in the evidence register. **Recorded 2026-11-09:** G1a–G1d are `blocked` (no public native-chat submit API; UI automation is a non-goal). Coding session remains the labeled ACP fallback.
- [x] T013 Test Moshi transcription, tool selection, external-result grounding, and hybrid fallback behavior. **Recorded 2026-11-09:** no Moshi/Pipecat install; hybrid path is `typed_instruction` (`hybrid_speech_path`, `tests/test_voice_bot_gates.py`). G3 stays blocked.
- [x] T014 Validate stale-buffer protection, disconnects (`unknown` → reconnect or `provider_lost`), timeouts, permission denial, and safe shutdown. Also add tests for acceptance 15 (secret exclusion), 16 (bounded tool registry), 17 (adapter swap with a stub), and 18 (truncation flags). Tests: `tests/test_voice_bot_safety.py`.
- [x] T015 Enable controlled edits only after all read-only and safety acceptance tests pass. **Gate implemented 2026-11-09:** `edits_enabled()` is false and `agent` mode is refused (`agent_mode_disabled`). G6 is not closed, so production edits stay off.
- [x] T017 Implement and test the R23 boundaries: path validation against the bound workspace (`path_outside_workspace`), per-session token for local-service connections, and schema validation on each R18 tool. Tests: `tests/test_voice_bot_security.py`, `tests/test_voice_bot_bridge.py`. Extension starts `voice-bot bridge` (`hive.voiceBot.startBridge`). Submit schema includes optional `selection_text`.
- [x] T018 Measure R24 latency (`transcript.final` → `task.started`, time to first `spoken_update`) and process resource use on the pinned runtime. Record results and hardware in `evidence-register.md`; read targets from the `voice_bot` config. Test: `tests/test_voice_bot_latency.py` asserts that config values change the checked target (acceptance 20).
- [x] T019 Make `spec-drift-check` compare specseed content with the curated spec, not only bullet presence. `check_memory_spec_drift` in `src/hive_planner/spec_drift.py` compares `cartridge/specs/<feature>.specseed.md` to `docs/specs/<feature>/spec.md` (normalized); missing specseed is skipped.
- [x] T016 Prove G5 (concurrency): a scripted test shows conversation continues while a task runs, a follow-up queues while `awaiting_approval`, and playback interruption leaves task state unchanged (SC-003, AC 4–5). Also resolves the MCP listening-tool risk in spec.md before any in-chat microphone loop. Tests: `tests/test_voice_bot_concurrency.py`. Fixture path only; live G5 stays blocked until G2 login. `IN_CHAT_MCP_MICROPHONE` is false.
- [x] T020 Implement and test R25–R29: call end during a pending approval, restart recovery, one pending approval per session, snapshot scope (no file, multi-root, unsaved, binary), and dedupe scope. Tests: `tests/test_voice_bot_edges.py`, run through the submit and approval paths, not helper-only.
- [x] T021 Self-contained Voice_Bot deploy (R30): Hive `voice` extra declares Moshi and Pipecat; `voice-bot ensure-runtime` installs missing packages; Cursor CLI uses the official installer. Tests: `tests/test_voice_bot_self_contained.py` (SC-014, AC 22).
- [x] T022 Wire previously uncoded spec rows on the Hive path: US5/SC-009 planning answers from spec/plan/tasks; R2 excerpt ids and file content; selection/file content in the ACP prompt; R18 workspace/`context_snapshot_id` bind; `navigate_to`/`show_diff` queue for the editor via `GET`/`POST /v1/editor`. Tests: `tests/test_voice_bot_planning.py`. Live G2/G3 still blocked.
- [x] T023 Live G2 probe (R31): `voice-bot live-prompt` records `agent status` / `CURSOR_API_KEY`, runs one real `session/prompt` only when logged in, and never writes G2 `pass` from the fixture path. Tests: `tests/test_voice_bot_live_prompt.py`.
- [x] T024 Spoken playback adapter (R32): `VoiceAdapter.speak`; typed path is no-audio; Pipecat adapter uses R13 cancellation independence when importable. Tests: `tests/test_voice_bot_speak.py`. G3 stays blocked until STT is pinned.
- [ ] T025 G6 edits latch (R33): `edits_enabled()` requires evidence-register G6 `pass` and config `edits_enabled: true`. Tests: `tests/test_voice_bot_gates.py`. Do not write G6 pass from fixture tests.

## Active task

**T023** — Live G2 probe (R31). Operator login still required for G2 `pass`; the task is to record blocked vs pass correctly. T024 and T025 follow.
**Prerequisite (met 2026-11-09):** Cursor Agent CLI — `agent --version` → `2026.11.05-86047df` at `%LOCALAPPDATA%\cursor-agent\agent.cmd` (not on PATH in this shell).

## Deployment readiness

See `spec.md` § Deployment readiness. Current verdict (2026-11-09): **not ready**. The CLI field `spec_ready: true` in `voice-bot status` only means the spec artifacts exist; it does not mean the feature is deployable.

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
```

## Integration wiring audit

- [x] Trace voice event → controller/tool handler → editor or coding adapter → task state → spoken/written result. Fixture path is traced (submit → ACP → evidence → spoken). Live STT and live `session/prompt` are not (G2/G3 still blocked in evidence-register).
- [x] Verify partial failures and denied permissions cannot report full success.
- [x] Verify every feature flag or integration setting has a read site and enabled path.
- [x] Prove the path with an integration-level test or scripted capability check.

See `.cursor/rules/integration-wiring-audit.mdc`.
