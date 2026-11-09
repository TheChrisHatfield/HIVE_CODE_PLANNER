# Voice_Bot — Evidence Register

**Hook:** `research.capabilities`, `change.validation`  
**Spec:** [spec.md](./spec.md)

Record capability evidence before promoting claims into acceptance criteria. Each row needs pinned version, test method, result, and date.

**Legend:** `pass` = reproduced on this machine; `partial` = contract or docs only; `blocked` = prerequisite missing; `fail` = reproduced negative result.

| Claim ID | Component | Pinned version | Test | Result | Date | Notes |
|---|---|---|---|---|---|---|
| G0 | Hive planner CLI / Voice_Bot contracts | `hive-planner` **1.3.0**, Python **3.11.0**, cartridge `ctx-2026-11-09-Voice_Bot` | `py -3.11 -m pytest tests/test_voice_bot.py -q`; `py -3.11 -m hive_planner voice-bot status`; `py -3.11 -m hive_planner spec-drift-check --feature Voice_Bot`; `py -3.11 -m hive_planner roadmap-status` (22/22) | **pass** | 2026-11-09 | HIVE owns session state at `.hive/voice-bot/state.json`; no external voice stack required for G0. |
| G1 | Native Agent submit / target (open IDE chat) | Cursor desktop (Composer chat); no pinned public API | Spec + cartridge review; IDE extension MCP notes; **no** programmatic submit to active composer tab exercised | **blocked** | 2026-11-09 | Spec non-goals forbid UI automation. Plan: verify in T012 or label **ACP fallback** as separate session (G2). Do not claim native handoff until T012 `pass`. |
| G2 | Cursor ACP coding transport | Docs: [cursor.com/docs/cli/acp](https://cursor.com/docs/cli/acp) (fetched 2026-11-09); CLI binary `agent` **`2026.11.05-86047df`** at `%LOCALAPPDATA%\cursor-agent` | `Get-Command agent`; `agent --version`; `agent acp --help`; `py -3.11 -m hive_planner voice-bot status` → `cursor_agent_cli.available: true`; doc review: JSON-RPC stdio, `session/new`, `session/prompt`, `session/update`, `session/request_permission`, `session/cancel`, modes `ask`/`plan`/`agent` | **blocked** | 2026-11-09 | Binary installed and pinned on dev host; HIVE ACP adapter (**T003–T004**) and read-only `session/prompt` repro still open. Gate stays blocked until T004 records pass/fail. |
| G3 | Moshi STT / tool routing / grounded narration | None installed | Tertiary: `Mushi AI_Cursor a.md` (Pipecat + Moshi patterns) — no live Moshi/Pipecat run | **blocked** | 2026-11-09 | **T013** will pin Moshi/Pipecat versions and run STT + tool-choice checks. Until then: no spoken grounding claims in acceptance text. |
| G4 | Editor context snapshot integrity | HIVE `voice-bot.v1` (`ContextSnapshot` in `src/hive_planner/voice_bot.py`) | `pytest tests/test_voice_bot.py::test_validate_rejects_traversal`; `test_init_and_snapshot_round_trip` | **partial** | 2026-11-09 | Path traversal and snapshot persistence verified in HIVE layer only. Extension capture (selection, dirty, diagnostics) is **T007**; stale-buffer e2e is **T014**. |
| G5 | Async conversation during active coding | n/a until G2 live | Not exercised — requires concurrent voice loop + ACP `session/update` stream | **blocked** | 2026-11-09 | Do not claim Grok-equivalent UX (spec G5). Unblocks after T003–T004 read-only prompt + voice bridge wiring. |
| G6 | Permission + cancellation + evidence-backed speech | HIVE `TaskEvidence` + `grounded_spoken_update`; ACP docs (permission outcomes) | `pytest tests/test_voice_bot.py::test_grounded_spoken_update_blocks_false_test_claim` | **partial** | 2026-11-09 | Unit-level block on false “tests passed” when `tests_status=not_run`. ACP `session/request_permission` and `session/cancel` not integrated until T003/T008/T010. Production edits stay off (T015). |

## Gate closure status (spec §Decision gates)

| Gate | Closed? | Rationale |
|---|---|---|
| G0 | **Yes** | Reproducible CLI + contract tests on pinned Hive/Python versions. |
| G1 | No | Native chat targeting not demonstrated; explicit fallback path required. |
| G2 | No | CLI pinned (`2026.11.05-86047df`); ACP adapter and read-only prompt not implemented (T003–T004). |
| G3 | No | No voice provider pinned or tested. |
| G4 | No | HIVE snapshot only; editor/stale-buffer paths open. |
| G5 | No | No concurrent voice + coding session. |
| G6 | No | Speech grounding unit test only; permission/cancel integration open. |

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

Pin the reported `agent` version in this table and set G2 to `pass` or `fail` after T003 implements the adapter against that binary.

## Alternative transport (informational, not a closed gate)

| Surface | Pinned | Status | Notes |
|---|---|---|---|
| Cursor SDK (`cursor-sdk` / `@cursor/sdk`) | Public beta per Cursor SDK skill (2026) | **not evaluated** | External automation (`Agent.create` + `send`) is a separate path from IDE native chat; does not satisfy G1; may complement G2 for non-IDE hosts. |
| Hive MCP (`hive_planner mcp-serve`) | hive-planner 1.3.0 | **operational** | Planner/tools from agent context; not a substitute for ACP coding session (cartridge: MCP ≠ coding transport). |

## G1 sub-checklist (R19 / `cursor.native_chat`)

Each row is independent; G1 stays **blocked** until all are `pass` or explicitly waived with fallback labeled.

| # | Question | Test | Result | Date |
|---|----------|------|--------|------|
| G1a | External user turn submission into native Agent chat | T012 scripted probe on pinned Cursor | pending | 2026-11-09 |
| G1b | Target active native conversation | T012 | pending | 2026-11-09 |
| G1c | Read native progress / context | T012 | pending | 2026-11-09 |
| G1d | Native voice provider replaceability | research + pinned version | pending | 2026-11-09 |

## Sources mined (tertiary)

- `context-library/sources/imported/Mushi AI_Cursor a.md`
- `cartridge/source-context.md` (compiler retrieval)
- `cartridge/translator-status.json` (classification counts)
- `Mushi AI_Cursor a.md` — eighteen `[HOOK:*]` metatags decompressed into spec hook index (2026-11-09)
- [Cursor ACP docs](https://cursor.com/docs/cli/acp) (primary for G2 schema)

Tertiary sources do not override this spec.
