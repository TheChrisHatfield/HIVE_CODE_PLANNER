# Voice_Bot — Evidence Register

**Hook:** `research.capabilities`, `change.validation`  
**Spec:** [spec.md](./spec.md)

Record capability evidence before promoting claims into acceptance criteria. Each row needs pinned version, test method, result, and date.

**Legend:** `pass` = reproduced on this machine; `partial` = contract or docs only; `blocked` = prerequisite missing; `fail` = reproduced negative result.

| Claim ID | Component | Pinned version | Test | Result | Date | Notes |
|---|---|---|---|---|---|---|
| G0 | Hive planner CLI / Voice_Bot contracts | `hive-planner` **1.3.0**, Python **3.11.0**, cartridge `ctx-2026-11-09-Voice_Bot` | `py -3.11 -m pytest tests/test_voice_bot.py -q`; `py -3.11 -m hive_planner voice-bot status`; `py -3.11 -m hive_planner spec-drift-check --feature Voice_Bot`; `py -3.11 -m hive_planner roadmap-status` (22/22) | **pass** | 2026-11-09 | HIVE owns session state at `.hive/voice-bot/state.json`; no external voice stack required for G0. |
| G1 | Native Agent submit / target (open IDE chat) | Cursor desktop (Composer chat); CLI `2026.11.05-86047df`; no public native submit API | T012/T028: G1a–G1d `fail`; `native_chat_path()` → `labeled_acp_fallback`; G2 live ACP has run | **pass** | 2026-11-10 | G1 closed via the labeled ACP fallback (R19). Native handoff is not claimed. UI automation remains a non-goal. |
| G2 | Cursor ACP coding transport | Docs: [cursor.com/docs/cli/acp](https://cursor.com/docs/cli/acp) (fetched 2026-11-09); CLI binary `agent` **`2026.11.05-86047df`** at `%LOCALAPPDATA%\cursor-agent` | T023 `voice-bot live-prompt --record` (R31); logged-in CLI; `stopReason=end_turn` | **pass** | 2026-11-10 | live session/prompt stopReason=end_turn |
| G3 | Moshi STT / tool routing / grounded narration | Hive extra `voice` + T024 `VoiceAdapter.speak`; STT unpinned | T013/T024: `hybrid_speech_path()` → `typed_instruction`; `TypedInstructionAdapter.speak` is no-audio; `tests/test_voice_bot_speak.py` | **pass** | 2026-11-10 | G3 closed via the labeled hybrid fallback (R10, R32). Moshi STT is not pinned. Installing Moshi later does not by itself reopen this row. |
| G4 | Editor context snapshot integrity | HIVE `voice-bot.v1`; extension `extensions/hive-voice-bot/` | `map_editor_snapshot`; `tests/test_voice_bot_safety.py` (secret, truncation, stale); EDH smoke 8/8 | **partial** | 2026-11-09 | T007 capture and T008 mapping exist. Stale check uses an injected live buffer, not a live Extension Host write. |
| G5 | Async conversation during active coding | fixture ACP turn server | `tests/test_voice_bot_concurrency.py` | **partial** | 2026-11-09 | Fixture: follow-up while running, held while `awaiting_approval`, interrupt leaves state. Live concurrent voice loop not recorded. No in-chat MCP microphone (`IN_CHAT_MCP_MICROPHONE` is false). |
| G6 | Permission + cancellation + evidence-backed speech | HIVE `VoiceTaskRunner` broker + R8 mapping; live ACP `agent` **`2026.11.05-86047df`** | T026 `voice-bot live-permission --record`; fixture `tests/test_voice_bot_permissions.py` / interrupt / results; T025 latch | **pass** | 2026-11-10 | live gate session/request_permission n=1 stopReason=cancelled |

## Gate closure status (spec §Decision gates)

| Gate | Closed? | Rationale |
|---|---|---|
| G0 | **Yes** | Reproducible CLI + contract tests on pinned Hive/Python versions. |
| G1 | **Yes** | G1a–G1d `fail` on pinned Cursor; coding session is labeled ACP (G2 pass). Native handoff is not claimed. |
| G2 | **Yes** | Live `session/prompt` recorded 2026-11-10 (`stopReason=end_turn`) on CLI `2026.11.05-86047df`. |
| G3 | **Yes** | Hybrid typed path accepted (R10). STT remains unpinned. |
| G4 | No | Mapping and fixture stale check exist; live editor write path not closed. |
| G5 | No | Fixture concurrency proven; live concurrent voice loop not recorded. |
| G6 | **Yes** | live gate session/request_permission n=1 stopReason=cancelled |

## Repro — G0 (copy/paste)

```powershell
cd D:\DRIVE_DOWNLOADS\HIVE_CODE_PLANNER
py -3.11 -m pytest tests/test_voice_bot.py -q
py -3.11 -m hive_planner voice-bot status
py -3.11 -m hive_planner spec-drift-check --feature Voice_Bot
py -3.11 -m hive_planner roadmap-status
```

## Repro — G2 (when Cursor CLI available)

```powershell
where agent
agent --version
agent acp
# JSON-RPC: initialize → authenticate → session/new → session/prompt (ask mode)
```

Pin the reported `agent` version in this table and set G2 to `pass` or `fail` after a logged-in live `session/prompt` on that binary. The fixture path does not close G2.

## Repro — G6

```powershell
py -3.11 -m pytest tests/test_voice_bot_live_permission.py tests/test_voice_bot_permissions.py tests/test_voice_bot_gates.py -q
py -3.11 -m hive_planner voice-bot live-permission --feature Voice_Bot --record --timeout 180
```

G6 `pass` requires a live gated method and no probe file at `.hive/voice-bot/g6-live-probe.tmp`. Fixture tests never write G6 pass. Production `agent` mode stays off until R33 `edits_enabled: true` as well.

## Alternative transport (informational, not a closed gate)

| Surface | Pinned | Status | Notes |
|---|---|---|---|
| Cursor SDK (`cursor-sdk` / `@cursor/sdk`) | Public beta per Cursor SDK skill (2026) | **not evaluated** | External automation (`Agent.create` + `send`) is a separate path from IDE native chat; does not satisfy G1; may complement G2 for non-IDE hosts. |
| Hive MCP (`hive_planner mcp-serve`) | hive-planner 1.3.0 | **operational** | Planner/tools from agent context; not a substitute for ACP coding session (cartridge: MCP ≠ coding transport). |

## G1 sub-checklist (R19 / `cursor.native_chat`)

Each row is independent. G1a–G1d are `fail` (answered: not supported). G1 the gate is `pass` because the ACP fallback has run (G2) and is labeled (`native_chat_path()` = `labeled_acp_fallback`). Native handoff is not claimed.

| # | Question | Test | Result | Date |
|---|----------|------|--------|------|
| G1a | External user turn submission into native Agent chat | T012/T028: no public submit API; UI automation is a non-goal | fail | 2026-11-10 |
| G1b | Target active native conversation | T012/T028: no targeting API for the open Composer tab | fail | 2026-11-10 |
| G1c | Read native progress / context | T012/T028: not readable from this process as native chat | fail | 2026-11-10 |
| G1d | Native voice provider replaceability | T012/T028: no documented replace API | fail | 2026-11-10 |

## Sources mined (tertiary)

- `context-library/sources/imported/Mushi AI_Cursor a.md`
- `cartridge/source-context.md` (compiler retrieval)
- `cartridge/translator-status.json` (classification counts)
- `Mushi AI_Cursor a.md` — eighteen `[HOOK:*]` metatags decompressed into spec hook index (2026-11-09)
- [Cursor ACP docs](https://cursor.com/docs/cli/acp) (primary for G2 schema)

Tertiary sources do not override this spec.

## T018 latency (R24)

Measured on the fixture ACP path (not a product target). Config `latency_target_ms` / `first_spoken_update_target_ms` stay unset until a live baseline. Test: `tests/test_voice_bot_latency.py` (a 1 ms target fails a 10 ms sample; a 60 s target passes). Hardware: Windows 10, Python 3.11, Cursor Agent CLI `2026.11.05-86047df` (not logged in).
