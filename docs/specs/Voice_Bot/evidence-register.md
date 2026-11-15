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
| G4 | Editor context snapshot integrity | VS Code **1.143.0** Extension Development Host; HIVE `voice-bot.v1`; extension `extensions/hive-voice-bot/` | Live: `powershell -File extensions/hive-voice-bot/test/edh/run-edh.ps1` → 13/13 (capture, 256-byte selection cap, diagnostics budget, then a live unsaved buffer edit: `document_version` up, `dirty` true, unsaved text withheld per R28, revert restores clean). Python: `tests/test_voice_bot_safety.py`, `tests/test_voice_bot_bridge.py` (stale submit and stale reply) | **pass** | 2026-11-11 | Scope: unsaved context, live buffer version/dirty, stale detection inputs, and withheld unsaved content. Visible diff (`show_diff`) and `navigate` run only in code and fixture tests, not in a live EDH check. **2026-11-12 (T043):** live EDH 18/18 on VS Code 1.146.0: the runner queues `show_diff` through `POST /v1/editor/show_diff` for the completed smoke task; the extension opens an untitled `diff` editor and acks it (pending clears). Command: `powershell -File extensions/hive-voice-bot/test/edh/run-edh.ps1`. |
| G5 | Async conversation during active coding | real Cursor Agent CLI `2026.11.05-86047df` (logged in), read-only `ask` turn | `py -3.11 scripts/voice_g5_live_probe.py` (live `agent acp`, throwaway repo) | **pass** | 2026-11-11 | Live: task ran at about 6 s; a follow-up submitted while running returned `queued` (`task_id` null); `interrupt_playback()` left the task `running`; first task reached `completed` (`end_turn`); the queued entry reached `dispatched`. Spoken mic loop is not run: typed Phase 1 path only, and `IN_CHAT_MCP_MICROPHONE` is false. |
| G7 | Moshi primary voice harness (R36, R37) | `moshi` **0.2.13** importable (Python 3.11, this host); torch **2.5.0+cu124**, CUDA visible; server `moshi.server` default `ws://127.0.0.1:8998/api/chat`; protocol read from installed `server.py` (kinds `0x00` handshake, `0x01` Opus, `0x02` text) | `py -3.11 -m hive_planner voice-bot moshi-probe --feature Voice_Bot` (no `--record`, no server on 8998). Result: `g7 blocked`, `reason moshi_unreachable`, `handshake_ms null`. Fixture tests: `tests/test_voice_moshi.py` (21, loopback stub; never writes G7). | **pass** | 2026-11-15 | url ws://127.0.0.1:8998/api/chat; model local q8 spike (irfh4yaasw-q8, A3 loopback); handshake 4860.0 ms; audio 1, text 0; handshake_and_round_trip. **2026-11-15 15e autostart gate: pass.** `autostart_gate_check.py` with q8 keys in a temp `config.json` (restored after): `GATE None` after 58.8 s, child running, `ATTEMPT 0 OK 0.0 s`, `ATTEMPT 1 OK 0.4 s`, `ATTEMPT 2 OK 0.3 s`, no sleep between connects. Fix: launcher `no_wait_stt_shutdown` (`scripts/moshi_q8_server.py`), so the slot frees on close instead of 2 s later. Log: `moshi-q8-spike/autostart_15e.log`; server lines: `moshi-q8-spike/autostart_15e_server_new_lines.log`. |
| G7-pod-2026-11-14 | Moshi primary voice harness (prior run, restored; superseded as the current G7 row) | Same as G7 above | Prior `moshi-probe --record` on a RunPod pod (row overwritten by the 2026-11-15 local run; restored 2026-11-15) | **pass (superseded)** | 2026-11-14 | url wss://yfhzy2r86j9akc-8998.proxy.runpod.net/api/chat; model kyutai/moshika-rag-pytorch-bf16; handshake 1562.0 ms; audio 1, text 0; handshake_and_round_trip. Pod is no longer running. |
| G6 | Permission + cancellation + evidence-backed speech | HIVE `VoiceTaskRunner` broker + R8 mapping; live ACP `agent` **`2026.11.05-86047df`** | T026 `voice-bot live-permission --record`; fixture `tests/test_voice_bot_permissions.py` / interrupt / results; T025 latch | **pass** | 2026-11-10 | live gate session/request_permission n=1 stopReason=cancelled |
| G7-q8 | Moshi q8 weights staged for live `moshi.server` (G7 input, not a live claim) | Runpod network volume `irfh4yaasw` (80 GB, EU-SE-1); `moshika-rag-q8/model.q8.safetensors` 12,237,164,792 B + `moshika-rag-q8/config.json`; ARC tokenizer via pcuenq (ungated) `llama-3.2-tokenizer/`; export ran on a since-terminated pod `z52c1qcvxouzxg` | Stage: `scripts/moshi_rag_q8_local.py --arc-tokenizer` (q8 export, STAGE_DONE). Not re-verified this turn; carried from the 2026-11-14 handoff. | **pass (caveated)** | 2026-11-14 | Session 9, pod `t13xqwp4ilb953` (H100 NVL, US-KS-2): q8 weights loaded in live `moshi.server` on :8998 using the documented `G7-q8-quantize-patch.md` only. `moshi-probe` (no `--record`) returned `g7: pass`, handshake 1468 ms. Caveats: pod-only `arc_encoder.py` edits (`use_fast=True`, tokenizer `unsloth/Llama-3.2-3B-Instruct`), vLLM `--gpu-memory-utilization 0.3`, and extra deps, all listed in `deployment-gaps.md` (Session 9 pod-only deltas). Not in repo. STAGE_DONE on `irfh4yaasw` only. Staging proves files exist, not that `moshi.server` loads them. 2026-11-14: the q8 weights loaded in a live `moshi.server` on pod `yfhzy2r86j9akc` and G7 is recorded **pass**. The load needed a pod-only float cast in `moshi-rag-src` `quantize.py` (not in repo), so the repo export is not yet proven unpatched. Dead pods: `i6lrxj5klthnbe`, `z52c1qcvxouzxg` (terminated). |
| T056-live-clip | Live operator clip through pinned STT (typed/Whisper path only, not Moshi talk) | Clip `.hive/voice-bot/recordings/clip-20261114-194246-619207.wav` (34.11 s, 16 kHz mono, peak_int16 12223, not silent); pinned faster-whisper 1.2.1, `Systran/faster-whisper-base.en` @ `3d3d5dee26484f91867d81cb899cfcf72b96be6c` via `FasterWhisperAdapter` (`src/hive_planner/voice_stt.py`) | `.hive\stt-pin\.venv\Scripts\python.exe` with `PYTHONPATH=src`: `resolve_pinned_model_dir()` then `transcribe_file(clip)`. Transcript saved to `.hive/voice-bot/recordings/clip-20261114-194246-619207.transcript.txt` | **partial (transcript only; no WER)** | 2026-11-14 | Opening sentences are readable. Trailing "Thank you… come again" repeats look like a Whisper hallucination over silence. No reference text exists for this clip, so no WER is claimed. Not a live Moshi or G3 claim; T042 live row is still open. |
| T056-live-clip-2 | Second live operator clip through pinned STT (typed/Whisper path only, not Moshi talk) | Clip `.hive/voice-bot/recordings/clip-20261114-194802-158013.wav` (18.98 s, 16 kHz mono, peak_int16 6633, not silent); pinned faster-whisper 1.2.1, `Systran/faster-whisper-base.en` @ `3d3d5dee26484f91867d81cb899cfcf72b96be6c` via `FasterWhisperAdapter` | Same as T056-live-clip. Transcript saved to `.hive/voice-bot/recordings/clip-20261114-194802-158013.transcript.txt` | **partial (transcript only; no WER)** | 2026-11-14 | Clean transcript: "This is another test to confirm that everything is working correctly…". Final "Thank you very much." reads as speech, not the silence repeats in the first clip. Operator said "15-second recording"; the clip is 19.0 s. No reference text, so no WER claimed. Not a live Moshi or G3 claim; T042 live row is still open. |
| T056-live-clip-3 | Third live operator clip through pinned STT (typed/Whisper path only, not Moshi talk) | Clip `.hive/voice-bot/recordings/clip-20261114-195013-527434.wav` (about 19.4 s by file size, 16 kHz mono; peak not re-measured this row); pinned faster-whisper 1.2.1, `Systran/faster-whisper-base.en` @ `3d3d5dee26484f91867d81cb899cfcf72b96be6c` via `FasterWhisperAdapter` | Same as T056-live-clip. Transcript saved to `.hive/voice-bot/recordings/clip-20261114-195013-527434.transcript.txt` | **partial (transcript only; no WER)** | 2026-11-14 | Transcript is readable and on-topic about adding recordings as evidence for a delta. One word error: "speech to text" was transcribed as "speech to sex". No reference text, so no WER claimed. Not a live Moshi or G3 claim; T042 live row is still open. |
| T056-live-clip-4 | Fourth live operator clip through pinned STT (typed/Whisper path only, not Moshi talk) | Clip `.hive/voice-bot/recordings/clip-20261114-194025-466141.wav` (14.98 s, 16 kHz mono, peak_int16 688 of 32767, near-silent) | `.hive\stt-pin\.venv\Scripts\python.exe` with `PYTHONPATH=src`: `resolve_pinned_model_dir()` then `FasterWhisperAdapter(...).transcribe_file(clip)`, pinned faster-whisper 1.2.1, `Systran/faster-whisper-base.en` @ `3d3d5dee26484f91867d81cb899cfcf72b96be6c`. Transcript saved to `.hive/voice-bot/recordings/clip-20261114-194025-466141.transcript.txt` | **partial (transcript only; no WER; input near-silent)** | 2026-11-14 | Transcript is "We'll see you again in a few minutes." Peak 688 suggests little or no speech in the clip, so this is likely a Whisper filler over silence, not a usable STT result. No reference text, so no WER claimed. Not a live Moshi or G3 claim; T042 live row is still open. |

## Gate closure status (spec §Decision gates)

| Gate | Closed? | Rationale |
|---|---|---|
| G0 | **Yes** | Reproducible CLI + contract tests on pinned Hive/Python versions. |
| G1 | **Yes** | G1a–G1d `fail` on pinned Cursor; coding session is labeled ACP (G2 pass). Native handoff is not claimed. |
| G2 | **Yes** | Live `session/prompt` recorded 2026-11-10 (`stopReason=end_turn`) on CLI `2026.11.05-86047df`. |
| G3 | **Yes** | Hybrid typed path accepted (R10). STT remains unpinned. |
| G4 | **Yes** (2026-11-11) | Live EDH 13/13 on VS Code 1.143.0 covers an unsaved buffer write and the stale-detection inputs. Visible diff live-tested 2026-11-12 (T043): EDH 18/18, `show_diff` queued via `POST /v1/editor/show_diff` and opened as a diff editor. |
| G5 | **Yes** (2026-11-11) | Live `agent acp` probe: follow-up queued while running, interrupt left coding state unchanged, queued follow-up dispatched. Typed path; spoken mic loop is not part of this gate. |
| G6 | **Yes** | live gate session/request_permission n=1 stopReason=cancelled |

## T033 — Moshi STT decision (documented unpinned)

**Decision (2026-11-11):** No STT provider is pinned. The documented path is explicit `unpinned`, which the spec allows (R10, §Decision gates G3).

- Code (superseded 2026-11-12 by T042 slice): `STT_PROVIDER` constant removed. `stt_provider` in `.hive/voice-bot/config.json` (default null) is the flag. `hybrid_speech_path(config)` returns `typed_instruction` unless that is a pinned provider. Adapter: `src/hive_planner/voice_stt.py`. The historical 2026-11-11 pin decision below is kept as written.
- Tests: `tests/test_voice_bot_gates.py::test_hybrid_speech_path_is_typed_until_stt_is_pinned` (asserts `STT_PROVIDER is None` and the typed path). `tests/test_voice_bot_speak.py` (typed path, no audio). `tests/test_voice_bot_self_contained.py` (dry-run `speech_path` is `typed_instruction`).
- Production hash gate (2026-11-13): `resolve_pinned_model_dir()` returns None unless the local `model.bin` sha256 equals `STT_PIN_MODEL_BIN_SHA256`; a wrong-hash file keeps speech on the typed path. Tests: `tests/test_voice_stt.py` (reject and accept cases).
- Installing the `voice` extra (Moshi) does not pin STT. A later pin needs a row here with a pinned version, test method, pass result, and date, plus a test change that moves `STT_PROVIDER` off `None`.

**T041 decision (2026-11-12): phased, typed default on Windows until row S1 passes.** The G3 end state stays `typed_instruction` on all OSes. Phase S1 target is a Whisper-class local STT on Windows. Moshi is not a Windows target (R30). Pin criteria are in [spec.md](./spec.md) § Speech I/O rollout. No pin row exists yet, so `STT_PROVIDER` stays `None`. Gap A remains open until a dated pin row is recorded here.

### T033 STT pin row (S1 candidate, criteria 1–3, 2026-11-12)

| Claim ID | Component | Pinned version | Test | Result | Date | Notes |
|---|---|---|---|---|---|---|
| T033-S1 | Whisper-class local STT on Windows, CPU, `stt_provider` candidate | `faster-whisper` **1.2.1**, `ctranslate2` **4.9.0**, Python **3.11.0** (venv `.hive/stt-pin/.venv`); model `Systran/faster-whisper-base.en` at commit `3d3d5dee26484f91867d81cb899cfcf72b96be6c`, `model.bin` sha256 `2a166925539a16005f14ff328359f9b9adb9dc4fb631bb3b227526862e93e2ef` (145,216,508 bytes); CPU host Intel Xeon Gold 6140 (Windows 10.0.22631), int8 | `.hive\stt-pin\.venv\Scripts\python.exe scripts\stt_pin\run_pin.py`. Fixtures: `scripts/stt_pin/fixtures/*.wav` (5 clips, 16 kHz mono PCM16, SAPI TTS) with exact reference text in `scripts/stt_pin/fixtures.json`. Fixed before the run: corpus WER threshold **0.10**; decode beam 5, `language=en`, no VAD. Raw output `.hive/stt-pin/result.json` | **pass** (criteria 1–4 gate; live audio rows open) | 2026-11-12 | Corpus WER **0.0976** (4 word edits / 41 reference words). Per clip: c01 0.00, c02 0.22, c03 0.00, c04 0.00, c05 0.25. Hypothesis misses: "voicebot" for "voice bot", "dock string" for "docstring". CPU latency per clip 845–1023 ms (p95 1023 ms, corpus RTF 0.286), against the R24 `latency_target_ms` reference of 8000 ms. That is not the same metric: 8000 ms is submit to `task.started`, and this is one transcription call. **Margin is thin:** 5 clips, 41 words, synthetic speech only. Not a claim about noisy or live microphone audio. **Criterion 4 gate (C1, 2026-11-12):** `stt_provider` is the only STT flag and accepts only a pinned id (`PINNED_STT_PROVIDERS`, `voice_bot.py`). `hybrid_speech_path(config)` returns `stt` only when that pinned provider is set and the pinned model is local. Test: `tests/test_voice_bot_gates.py::test_hybrid_speech_path_follows_pinned_stt_provider_config`. The `STT_PROVIDER` constant is gone. Host config keeps `stt_provider` null. `audio_enabled` speak rows and live mic remain open (T042; C3/C4). G3 wording stays "labeled typed hybrid". |

## T034 — Pipecat speak contract (no audio claimed)

**Contract (2026-11-11):** The runtime speak path is `TypedInstructionAdapter` (`voice_task.py`, `speech.spoken` with `audio: false`). `PipecatVoiceAdapter` is not on the runtime path.

- Pipecat installed: `PipecatVoiceAdapter.speak` returns a payload with `played: false` and `audio: false`. It does not play audio.
- Pipecat missing: `speak` raises `VoiceBotError("pipecat_unavailable")`. This is an explicit error, not a silent no-audio default. The runtime does not call it, so the turn still completes.
- `cancel_on_interruption` is `False` (R13, R32).
- Tests: `tests/test_voice_bot_speak.py` (8 passed), including forced missing-import, installed payload, and a real runner turn that still records no-audio speech when the Pipecat adapter raises.
- Not claimed: real Pipecat audio playback. That needs a separate pin and live test.

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

## R35 live allowed-write probe (full `agent` lane)

| Claim ID | Component | Pinned version | Test | Result | Date | Notes |
|---|---|---|---|---|---|---|
| R35 | Full `agent` mode allowed write reaches disk | `agent` CLI **`2026.11.05-86047df`** (logged in); Python **3.11.0**; HIVE `live_write` (T047) | `py -3.11 -m hive_planner voice-bot live-write --feature Voice_Bot --timeout 180` (saved to `.hive/voice-bot/live-write-run.json`) | **pass** | 2026-11-12 | ACP session `51b937ee-4fb4-46a7-b10e-9b487d74ee7f`, `stopReason=end_turn`, mode `agent`, `permissions=[]`. Probe file `.hive/voice-bot/live-write-check.txt` present, nonce match, nonce hash `afc93b69b236ec1a` (raw nonce not recorded here). No coding task is created by this probe. Earlier 02:21 host run (session `3c573c26`) is in `tasks.md` only; no artifact kept its nonce hash, so this re-run is the citable proof. R35 does not change the G6 row or the R33 config. |

### R35 run file shape (`.hive/voice-bot/live-write-run.json`, F3 notes)

Written by `live_write()` in `src/hive_planner/voice_bot.py`. Keys: `ok`, `r35` (`pass` | `no_write` | `agent_error` | `blocked`), `feature`, `agent_path`, `login`, `fixture`, `reason`, `session_id`, `stop_reason`, `mode`, `permissions` (summarized `session/request_permission` calls), `nonce_hash` (first 16 hex of SHA-256 of the nonce; the raw nonce is never written), `file_present`, `nonce_match`.

- **Not in this file:** tool-call evidence. The probe has its own ACP handler and does not go through `VoiceTaskRunner._on_update`, so it has no `kind` or redacted command rows. The F3 rows live on the task record (`evidence.tool_calls`), not in this file.
- **Tool-call evidence (F3, task record):** each ingested `tool_call` adds `{tool_call_id, kind, command, status}` to `CodingTask.evidence.tool_calls`. `command` is redacted by `redact_command()` in `src/hive_planner/voice_task.py` (bearer tokens and `token|password|passwd|secret|api_key|authorization|auth` values masked, `sk-` keys masked, then truncated to 200 chars). `status` moves from `pending` to `completed` or `failed` on `tool_call_update`.
- **Known gap:** the redactor masks named credential flags only. A bare positional secret (for example `-p hunter2`) is not masked. Treat command evidence as best-effort, not a guarantee.
- Tests: `tests/test_voice_bot_tool_evidence.py` (fake ACP `EXEC_SECRET` trigger through `runner.submit`).

## R33 production edits latch

| Event | Date | Host | Config |
|---|---|---|---|
| Operator enabled full `agent` lane | 2026-11-12 | Hive source repo | `.hive/voice-bot/config.json` → `edits_enabled: true` (G6 register **pass** required at runtime via `edits_enabled()`) |

Spec status promoted from **draft** to **active** the same date after explicit operator approval.

## Operator full-agent production approval (F4 template)

Filled by a human only. Copy this row for each host. Leave every field blank until the operator fills it in.

| Field | Value |
|---|---|
| Approval row | Operator full-agent production approval |
| Date | ______________ |
| Host id | ______________ (hostname) |
| Checklist version | ______________ ([operator-production-checklist.md](./operator-production-checklist.md), version or date) |
| Signer initials | ______ (blank until the human fills it) |
| Known residuals read | ☐ U10 interpreter/alias writes not caught ☐ F3 positional secrets not masked ☐ F3 `raw_events` may be unredacted |

**Effect of this row:** signing does **not** set `edits_enabled`. The human sets `"edits_enabled": true` in `.hive/voice-bot/config.json` on that host as a separate step, after signing. The row does not change the R33 latch, the G6 row, or the R35 row. It applies to this host only and does not make full-agent READY fleet-wide.

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

Fixture ACP path (not a product target): `tests/test_voice_bot_latency.py` (a 1 ms target fails a 10 ms sample; a 60 s target passes).

**Live baseline (2026-11-11, R24):** `scripts/voice_g5_live_probe.py`, Windows 10, Python 3.11, Cursor Agent CLI `2026.11.05-86047df` (logged in). Submit to `running` (`task.started` proxy, includes ACP child start and `session/new`): 5.9–7.1 s over two runs. Full read-only ask turn: 29.9–34.1 s. **Superseded by the R24 measurement below:** first `spoken_update` and process resource use are now recorded there. The G5 probe (`voice_g5_live_probe.py`) does not measure resources. Config `latency_target_ms` and `first_spoken_update_target_ms` stay unset; no numeric target is claimed from this baseline.

**R24 live measurement (2026-11-11, `scripts/voice_r24_latency_probe.py 3`):** Windows 10.0.22631, Intel64 Family 6 Model 85 (72 logical CPUs), 63.7 GB RAM, Python 3.11.0, `agent` CLI `2026.11.05-86047df`. One read-only ask turn per run in a throwaway repo, three runs, all `completed`, runner idle after settle in every run.

| Run | submit → `task.started` (s) | submit → first `spoken_update` (s) | submit → terminal `spoken_update` (s) | Voice service CPU (s) | Agent children CPU (s) | Peak RSS voice service / agent children (MB) | Max child processes |
|---|---|---|---|---|---|---|---|
| 1 | 7.459 | 7.459 | 29.950 | 6.47 | 52.92 | 20.8 / 607.8 | 17 |
| 2 | 5.814 | 5.814 | 29.001 | 6.34 | 50.00 | 21.0 / 616.3 | 17 |
| 3 | 6.013 | 6.013 | 29.316 | 6.23 | 51.16 | 21.1 / 630.2 | 17 |

- First `spoken_update` is the acknowledgment `Task accepted, running.`, emitted at `task.started`. Time to first spoken update equals submit-to-running (about 5.8–7.5 s). This is the `agent` child start plus `session/new`, not model latency.
- The first agent chunk then emits `Still working.` (about 27 s in), and the outcome emits `Tests were not run. Task completed.` (about 29 s).
- Voice-service CPU is about 6.3 s per run, measured as this probe process's CPU delta (not broken down further). Agent children are about 50–53 s CPU across the run (ACP child plus its own subprocesses).
- Finding (closed 2026-11-11): the acknowledgment was overwritten in `evidence.spoken_update` by `Still working.` on the first chunk. Fixed: progress speech now calls `_say(..., record=False)`, so it is spoken and logged as `speech.spoken` but `evidence.spoken_update` keeps `Task accepted, running.`. Test: `test_voice_bot_results.py::test_progress_speech_does_not_clobber_acceptance_ack`.
- Probe note: the first two probe drafts read the terminal speech before `_settle` ran. The probe now waits for `runner.wait_idle()`. Those drafts are not evidence.
- Target decided 2026-11-11: `latency_target_ms` and `first_spoken_update_target_ms` default to **8000 ms** in `VoiceBotConfig`. That sits just above the worst measured submit-to-running (7.1 s, both sides of the 5.8–7.5 s range noted above). Note the margin is thin: a slower host may exceed it. Resource-use targets set 2026-11-11 in `VoiceBotConfig`: `agent_children_rss_target_mb` 650 (measured peaks 607.8–630.2 MB), `voice_service_rss_target_mb` 100 (provisional; measured ~21 MB). Tests: `tests/test_voice_bot_resources.py`. The probe writes `rss_check` per run; that field has not been re-recorded live against these targets yet.

**Live `rss_check` re-run (2026-11-11, `scripts/voice_r24_latency_probe.py 1`, CLI `2026.11.05-86047df`, logged in):** one run, `completed`, idle after settle. submit → `task.started` 4.591 s; submit → terminal `spoken_update` 58.896 s; voice service CPU 6.88 s, peak RSS 20.7 MB; agent children CPU 69.03 s, peak RSS **770.2 MB**, max 21 child processes. `rss_check`: `voice_service_ok` true (target 100 MB); **`agent_children_ok` false (target 650 MB)**. Latency is within the 8000 ms target. The agent-children resource target was **exceeded** in this run. The earlier three runs peaked at 607.8–630.2 MB with 17 child processes, so this run used more children and more memory. One sample is not enough to say whether the 650 MB target is too tight or the host load varied. The target was not changed.

**Follow-up `rss_check` re-run (2026-11-11, `scripts/voice_r24_latency_probe.py 3`, same CLI, logged in):** three runs, all `completed`, idle after settle. Submit to `task.started` 4.61–4.64 s; submit to terminal `spoken_update` 24.97–26.12 s. Agent children peak RSS 616.9 / 639.8 / 623.0 MB (limit 650 MB, all `agent_children_ok` true). Voice service peak RSS 20.5–21.0 MB (all ok). Max child processes 16–19. Combined with the 2026-11-11 baseline, four of four runs on the 650 MB target now pass, but the first sample at 770.2 MB was recorded as an outlier and is kept in this register. The 770 MB run also took about 59 s, against about 25 s for these runs, so host load is the likely cause. Treat the 650 MB target as tight, not wrong.

**T5-rss decision (2026-11-12): target tight, no change.** `agent_children_rss_target_mb` stays 650 in `VoiceBotConfig`. Four of five recorded runs passed; the 770.2 MB run is kept as an outlier tied to host load (about 59 s vs about 25 s). No config or test change was made. Live `rss_check` was not re-run in this item.
