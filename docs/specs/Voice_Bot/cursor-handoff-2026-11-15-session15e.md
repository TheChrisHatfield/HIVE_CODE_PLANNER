# Cursor handoff — Voice_Bot session 15e (2026-11-15)

Background: `cursor-handoff-2026-11-15-session15d.md`. Requirement: `spec.md` R37 (slot race decision and autostart closure).

## Status

- **R37 q8 autostart: PASS (closed).** Live `autostart_gate_check.py` with handover and temp q8 keys: `GATE None` after 58.8 s, child running; `ATTEMPT 0 OK 0.0 s`, `ATTEMPT 1 OK 0.4 s`, `ATTEMPT 2 OK 0.3 s`, no sleep between connects.
- **G7 register:** Notes cell appended with 15e autostart pass (columns unchanged; probe row still cites A3b handshake/round-trip). Do not rewrite the probe test column without a new recorded probe.
- **Fixed in 15e (operator choice: launcher fix, option 2 from 15d):** upstream `LocalSpeechToText.shutdown()` held the batch slot ~2 s after each client close because it waited for a transcript iterator the channel had already cancelled. Launcher now installs `no_wait_stt_shutdown` via `apply_fast_stt_shutdown`. Slot acquire/release is immediate in the live log.
- **Carried from 15d (do not redo or revert):** shared STT LM (`share_loaded_models` + `_stop_streaming` on cache hit); fixes OOM and "already streaming" on 16 GiB GPU.
- **Carried from 15c (do not redo or revert):** `moshi_call_gate` handover, `moshi-server.log`, 15 s connect budget.

## Live run (15e)

Gate stdout (`moshi-q8-spike/autostart_15e.log`):

```
GATE None after 58.8 s child_running True
ATTEMPT 0 OK 0.0 s
ATTEMPT 1 OK 0.4 s
ATTEMPT 2 OK 0.3 s
```

Server log excerpt (new lines only; `autostart_15e_server_new_lines.log`):

```
04:09:43.63 [Slot] acquired slot 0 (1/1)
04:09:43.66 [Slot] released slot 0
04:09:44.00 [Slot] acquired slot 0 (1/1)
04:09:44.03 [Slot] released slot 0
04:09:44.32 [Slot] acquired slot 0 (1/1)
04:09:44.37 [Slot] released slot 0
```

No `Rejecting connection: No available slots`, no `OutOfMemoryError`, no `already streaming`.

## Code state (likely uncommitted: 15c + 15d + 15e)

| File | Role |
|---|---|
| `src/hive_planner/voice_moshi.py` | Handover (`moshi_call_gate`, `open_session` reuse) |
| `src/hive_planner/launcher/voice_panel_controller.py` | Default listen gate = `moshi_call_gate` |
| `src/hive_planner/voice_moshi_server.py` | Child log to `.hive/voice-bot/moshi-server.log` |
| `scripts/moshi_q8_server.py` | `stream_load`, `share_loaded_models`, `no_wait_stt_shutdown`, `apply_fast_stt_shutdown` |
| `tests/test_moshi_q8_share.py` | Share cache, streaming reset, fast shutdown (4 tests) |
| `tests/test_voice_moshi_server.py` | Handover + two sequential `open_session` on stub |
| `tests/test_voice_bot_evidence_register.py` | Gate-id row filter fix |
| `docs/specs/Voice_Bot/spec.md` | R37 through 15e (FAIL history, share, slot fix, **Autostart live PASS**) |
| `docs/specs/Voice_Bot/evidence-register.md` | G7 Notes: 15e autostart pass |

Outside repo: `D:\DRIVE_DOWNLOADS\moshi-q8-spike\autostart_gate_check.py` still uses `moshi_call_gate`.

## Validation (15e)

| Check | Result |
|---|---|
| `py -3.11 -m pytest tests/test_voice_moshi.py tests/test_voice_moshi_server.py tests/test_voice_moshi_conversation.py tests/test_voice_bot_evidence_register.py tests/test_moshi_q8_share.py -q` | 69 passed |
| Live `autostart_gate_check.py` | PASS (see above) |
| `.hive/voice-bot/config.json` after run | Restored; no q8 keys; `moshi_autostart` true |

## Wiring audit (15e)

- **Chain traced:** panel mic → `moshi_call_gate` → `SERVER.ensure` → `moshi_q8_server.py` (`get_moshi` cache + fast STT shutdown) → `open_session` / gate check connects.
- **Live-proven (15e):** child start; handover attempt 0; back-to-back attempt 1/2 without sleep; slot release on close.
- **Gaps (unchanged):**
  1. Hive does not set operator env (`PYTHONPATH`, `REFERENCE_ENCODER_URL`, `LLM_*`); autostart only works when the operator (or future Hive wiring) provides them. `.hive/voice-bot/config.json` still has no persistent q8 paths unless the operator adds them or a separate task wires paths from config.
  2. `test_two_sequential_open_sessions_both_connect` uses `moshi_stub_server.py` (no slot limit); live gate is the proof for the race.
  3. Held socket 30 s caveat; `SERVER_LOG` portable path caveat (from 15d).
  4. **Cosmetic upstream:** after each close, `channel.run()` logs `ExceptionGroup` with `_ChannelClosed` inside; not fixed (would need moshi-rag or a launcher monkeypatch on `Channel.run`). Sockets still close cleanly.
  5. **Scope:** autostart gate proves connects and slot release, not duplex audio through the panel on live q8 (`voice-bot moshi-talk` / launcher mic with real server still operator-driven).

## Open / suggested next (pick with operator)

1. **Git:** commit the 15c–15e stack if the operator wants it saved (no commit was made in session 15e).
2. **Doc debt:** R37 bullet still says q8 autostart keys are "not yet live-proven" (A3c line); reconcile with 15e PASS if editing spec for clarity only.
3. **T056 live on this host:** with q8 keys in config (or temp) + operator env + stub LLM on 8009, run launcher mic or `voice-bot moshi-talk` against loopback q8; record utterances/audio if desired (separate from autostart gate).
4. **T042 slice 5d** (mic record → WAV → spoken submit) remains open for typed path; Moshi mic path is wired but live duplex on q8 is not re-recorded in 15e.
5. **Optional:** suppress or patch upstream `ExceptionGroup` noise in launcher (low priority).

## Do not redo

- Share LM cache and streaming reset (15d).
- Slot-race fix (`no_wait_stt_shutdown`) unless a regression appears.
- A1/A2/A2b, A3b probe, 15 s timeout, call-gate handover.
- Another autostart gate rerun unless code changes under `moshi_q8_server.py` or `voice_moshi*` gate path.

## Operator env for live q8 (Hive does not set these)

```powershell
$env:PYTHONPATH='D:\DRIVE_DOWNLOADS\HIVE_CODE_PLANNER\src;D:\DRIVE_DOWNLOADS\moshi-q8-spike\stubs;D:\DRIVE_DOWNLOADS\moshi-rag-src\moshi'
$env:NO_TORCH_COMPILE='1'; $env:NO_CUDA_GRAPH='1'; $env:HF_HUB_ENABLE_HF_TRANSFER='0'
$env:REFERENCE_ENCODER_URL='http://127.0.0.1:9'; $env:LLM_BASE_URL='http://127.0.0.1:8009/v1'
$env:LLM_API_KEY='unused-spike'; $env:LLM_MODEL_NAME='stub'
# llm_stub on 8009 must be running
```

Temp q8 keys (only for runs; restore config without keys afterward unless operator pins them):

- `moshi_q8_weights`: `D:\DRIVE_DOWNLOADS\POD_BACKUPS\irfh4yaasw-q8\model.q8.safetensors`
- `moshi_mimi_weights`: `D:\DRIVE_DOWNLOADS\MOSHI_RAG_WEIGHTS\moshika-rag-pytorch-bf16\tokenizer-e351c8d8-checkpoint125.safetensors`
- `moshi_tokenizer`: `D:\DRIVE_DOWNLOADS\MOSHI_RAG_WEIGHTS\moshika-rag-pytorch-bf16\tokenizer_spm_32k_3.model`
- `moshi_model_config`: `D:\DRIVE_DOWNLOADS\moshi-q8-spike\config.local.json`

Autostart proof command: `py -3.11 D:\DRIVE_DOWNLOADS\moshi-q8-spike\autostart_gate_check.py` from repo root (record log offset before run).

## Caveats

- `moshi_autostart` stays `true` in `config.json`.
- 16 GiB host GPU; batch-size 1 on launcher args.
- moshi-rag upstream not edited; all fixes in `scripts/moshi_q8_server.py`.

---

## Paste into next chat

```
Voice_Bot session 15f. Read `docs/specs/Voice_Bot/cursor-handoff-2026-11-15-session15e.md` fully, then R37 in `docs/specs/Voice_Bot/spec.md`. R37 q8 autostart is PASS (15e): do not rerun `autostart_gate_check.py` unless moshi gate/launcher code changes. Uncommitted stack: 15c handover + server log, 15d share LM, 15e `no_wait_stt_shutdown`. Ask me what to do next: commit, live panel/`moshi-talk` on loopback q8, doc reconciliation (A3c “live-proven” line), or T042/T056 slice. Operator must set PYTHONPATH + REFERENCE_ENCODER_URL + LLM stub env; q8 keys are not in config by default.
```