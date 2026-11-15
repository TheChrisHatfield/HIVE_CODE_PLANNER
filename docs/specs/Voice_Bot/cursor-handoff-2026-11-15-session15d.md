# Cursor handoff — Voice_Bot session 15d (2026-11-15)

Background: `cursor-handoff-2026-11-15-session15c.md`. Requirement: `spec.md` R37 (share point and rerun 2 lines).

## Status

- **Live q8 autostart check: still FAIL (G7 not closed).** The G7 row in `evidence-register.md` is unchanged (still the 2026-11-15 A3b pass). Do not change it without a new passing live check.
- **Fixed in 15d:** the OOM. One shared speech-to-text LM is now reused across websocket sessions (launcher `get_moshi` cache). The live rerun shows no `OutOfMemoryError`.
- **Fixed in 15d:** the second session hit `AssertionError: lm is already streaming!`. A cache hit now clears the shared LM's leftover streaming state (`_stop_streaming`).
- **Open (new root cause, proven in the live log):** the q8 server frees its single slot about 2 s after the client closes. The gate check closes attempt 0 and connects attempt 1 at once. The server rejects it (`No available slots`), which surfaces as close code 1002 "reserved bits must be 0" and `moshi_unreachable`.

## Live rerun 2 (log excerpt, new lines only)

```
04:01:40.33 [Slot] acquired slot 0 (1/1)
04:01:40.37 new WebSocket client connected
04:01:40.70 WARNING Rejecting connection: No available slots
04:01:41.71 new WebSocket client connected
04:01:42.03 WARNING Rejecting connection: No available slots
04:01:42.34 [Slot] released slot 0
```

Gate check output: `GATE None` after 60.0 s (child running). `ATTEMPT 0 OK 0.0 s`. `ATTEMPT 1` and `ATTEMPT 2` `moshi_unreachable`.

## Code state (uncommitted, on top of 15c)

| File | Change in 15d |
|---|---|
| `scripts/moshi_q8_server.py` | New `share_loaded_models(get_moshi)`: cache keyed by weights, lora, args. A cache hit calls `_stop_streaming()`. `main()` routes `CheckpointInfo.get_moshi` through it. |
| `tests/test_moshi_q8_share.py` | NEW. 3 tests: one load for two calls; second session can start streaming (regression for "already streaming"); different checkpoint/device/args not shared. |
| `tests/test_voice_moshi_server.py` | New `test_two_sequential_open_sessions_both_connect` (stub server, two `open_session` connects with no sleep). |
| `docs/specs/Voice_Bot/spec.md` | R37: "Share point (15d)" bullet and "Autostart live, 15d rerun 2: FAIL" bullet. |

## Validation (15d)

| Check | Result |
|---|---|
| `py -3.11 -m pytest tests/test_voice_moshi.py tests/test_voice_moshi_server.py tests/test_voice_moshi_conversation.py tests/test_voice_bot_evidence_register.py tests/test_moshi_q8_share.py -q` | 68 passed (64 from 15c + 1 two-connect test + 3 share tests) |
| Live `autostart_gate_check.py`, run 1 (before streaming reset) | GATE None; attempt 1/2 `moshi_unreachable`; `torch.OutOfMemoryError` gone; new `already streaming` AssertionError |
| Live `autostart_gate_check.py`, run 2 (after streaming reset) | GATE None; attempt 1/2 `moshi_unreachable` (slot race, see above); no OOM; no already-streaming |

## Wiring audit (15d)

- **Chain traced:** panel mic (`voice_panel_controller.py`) → `moshi_call_gate` → `_listen_gate` → `SERVER.ensure` (child started, log file) → `q8_server_command` → `scripts/moshi_q8_server.py` → `get_moshi` cache (`share_loaded_models`) → `talk()` → `open_session`.
- **Live-proven links:** gate starts child; child loads model; handover gives attempt 0 a socket; share removes the second load (no OOM).
- **Gaps found:**
  1. Slot release after client close (new, open, see decision below).
  2. The two-connect Hive test (`test_two_sequential_open_sessions_both_connect`) runs against `moshi_stub_server.py`, which has no slot limit. It proves the Hive side only and would not catch the slot race. The live rerun is the real proof.
  3. A held socket that `talk()` never consumes is still closed only after 30 s or on the next gate call (unchanged caveat).
  4. `SERVER_LOG` still uses the repo root from `__file__` (portable builds not handled).

## Open decision (ask the operator, do not pick silently)

The operator was asked (AskQuestion) and answered "create handoff prompt for next chat". So no fix was applied. The three options that were offered, with trade-offs:

1. **Wait:** Hive waits about 2.5 s after a close before the next connect. Cheap; matches the 2 s pause measured in A3c. It relaxes the R37 "NO sleep" criterion for the gate check. Real use is not hurt: a new call is seconds after the last one.
2. **Launcher fix:** patch `scripts/moshi_q8_server.py` so the slot frees on client close (no moshi-rag edit). This is the proper fix, but it needs a look at upstream teardown first (`moshi-rag-src/moshi/moshi/server.py` `handle_chat`, `Channel` teardown, `[Slot] released`). Larger change.
3. **Stop:** keep the share fix and tests, leave G7 open, and do nothing more on the race.

Next chat should ask the operator which of the three to apply, then continue. Do not re-open the share decision.

## Restore and state

- `.hive/voice-bot/config.json` was restored after both runs. It has NO q8 keys. Verified.
- Port 8998: no LISTEN after the run (child stopped). Port 8009 (llm_stub, PID 64148) listening.
- Share is in the launcher only. moshi-rag upstream is not edited.

## Do not redo

- A1/A2/A2b smoke, A3b record probe, 15 s timeout, the handover (done and tested; do not revert).
- The share decision (launcher cache, one shared LM across sessions). Done and tested.

## Operator env for the live check (Hive does not set these)

```powershell
$env:PYTHONPATH='D:\DRIVE_DOWNLOADS\HIVE_CODE_PLANNER\src;D:\DRIVE_DOWNLOADS\moshi-q8-spike\stubs;D:\DRIVE_DOWNLOADS\moshi-rag-src\moshi'
$env:NO_TORCH_COMPILE='1'; $env:NO_CUDA_GRAPH='1'; $env:HF_HUB_ENABLE_HF_TRANSFER='0'
$env:REFERENCE_ENCODER_URL='http://127.0.0.1:9'; $env:LLM_BASE_URL='http://127.0.0.1:8009/v1'
$env:LLM_API_KEY='unused-spike'; $env:LLM_MODEL_NAME='stub'
# stub on 8009: llm_stub.py must be running (currently PID 64148)
```

Temp config keys (write to `.hive/voice-bot/config.json` only for the run, then restore the original, which has no q8 keys):
- `moshi_q8_weights`: `D:\DRIVE_DOWNLOADS\POD_BACKUPS\irfh4yaasw-q8\model.q8.safetensors`
- `moshi_mimi_weights`: `D:\DRIVE_DOWNLOADS\MOSHI_RAG_WEIGHTS\moshika-rag-pytorch-bf16\tokenizer-e351c8d8-checkpoint125.safetensors`
- `moshi_tokenizer`: `D:\DRIVE_DOWNLOADS\MOSHI_RAG_WEIGHTS\moshika-rag-pytorch-bf16\tokenizer_spm_32k_3.model`
- `moshi_model_config`: `D:\DRIVE_DOWNLOADS\moshi-q8-spike\config.local.json`

Live check: `py -3.11 D:\DRIVE_DOWNLOADS\moshi-q8-spike\autostart_gate_check.py` from the repo root. Record the log offset before the run and scan only new lines.

## Caveats

- `moshi_autostart` stays `true` in `config.json`. Keep it unchanged.
- The live check proves connects only; it does not prove the slot-race fix until the rerun passes.
