# Cursor handoff — Voice_Bot session 15c (2026-11-15)

Background: `cursor-handoff-2026-11-15-session15b.md`. Requirement: `spec.md` R37.

## Status

- **Live q8 autostart check: FAIL (G7 not closed).** Run with `moshi_call_gate` (handover), 3 session connects after the gate:
  - `GATE None` after 57.6 s, child running.
  - `ATTEMPT 0 OK` (handed-over socket).
  - `ATTEMPT 1` and `ATTEMPT 2` `moshi_unreachable` (`ConnectionClosedError`).
- **Root cause (server log `.hive/voice-bot/moshi-server.log`):** each websocket session builds its own speech-to-text LM copy on the GPU (`LocalSpeechToText` → `checkpoint_info.get_moshi` → `scripts/moshi_q8_server.py` `stream_load`). The second copy hits `torch.OutOfMemoryError` on a 16.00 GiB card (15.14 GiB already allocated). The earlier "per-connection OOM" guess is now confirmed.
- **Operator decision (chosen via AskQuestion, do not re-ask):** share one loaded STT LM across sessions in the q8 launcher. Recorded in R37 as "Not implemented yet." Rerun the check after the change.
- Host GPU is 16 GiB. The A3 proof was on a pod H100 NVL.

## Code state (uncommitted)

| File | Change |
|---|---|
| `src/hive_planner/voice_moshi.py` | One-slot hold (`_HELD`, `HOLD_MAX_AGE_S=30`), `moshi_call_gate` keeps the socket; `open_session` takes the held socket for the same URL. `moshi_listen_gate` still closes (typed/submit). |
| `src/hive_planner/launcher/voice_panel_controller.py` | Default `listen_gate` = `moshi_call_gate`. |
| `src/hive_planner/voice_moshi_server.py` | `MoshiServerProcess(log_path=...)`; child stdout/stderr append to `.hive/voice-bot/moshi-server.log`. |
| `tests/test_voice_moshi_server.py` | 6 new tests (handover, typed still closes, other URL not reused, hold consumed once, log receives output). |
| `tests/test_voice_bot_evidence_register.py` | Gate-id check counts only `G<n>` rows. Register data unchanged. |
| `docs/specs/Voice_Bot/spec.md` | R37: FAIL line, log excerpt, chosen fix. |
| `D:\DRIVE_DOWNLOADS\moshi-q8-spike\autostart_gate_check.py` (outside repo) | Imports `moshi_call_gate` as `moshi_listen_gate`. |

`.hive/voice-bot/config.json` was restored after the run. It has NO q8 keys. The temp backup was removed.

## Validation (session 15c)

| Check | Result |
|---|---|
| `pytest tests -k "voice or moshi or panel"` | 766 passed, 1 failed (register test; fixed afterward) |
| `pytest tests/test_voice_bot_evidence_register.py tests/test_voice_moshi.py tests/test_voice_moshi_server.py tests/test_voice_moshi_conversation.py` | 64 passed |
| Port 8998 LISTEN before run | none |
| Port 8009 (llm_stub, PID 64148) | listening |

## Wiring audit (session 15c)

- **Chain:** panel mic (`voice_panel_controller.py` ~L337) → `moshi_call_gate` → `_listen_gate` → `SERVER.ensure` (`voice_moshi_server.py`) → `scripts/moshi_q8_server.py` → `talk()` → `open_session`.
- **Gaps:**
  - A held socket that `talk()` never consumes is closed only after 30 s or on the next gate call. Not observed live.
  - `SERVER_LOG` uses the repo root from `__file__`, so portable builds write beside the install. Not handled.
  - Typed and submit paths (`voice_task.py` ~L1843, ~L1890) still use `moshi_listen_gate` (closes probe). Intended.
  - The Hive process does not set the q8 operator env. See the block below.

## Next step (in order)

1. Read R37 and this file. Spec before code.
2. Find the share point in `scripts/moshi_q8_server.py`: the `get_moshi` wrapper (~L98) and `stream_load` (~L59). Load one STT LM once and reuse it across websocket sessions. Keep the Mimi copy per session if it fits. Do not change moshi-rag upstream files.
3. Add a test that two sequential `open_session` connects both succeed (fixture or launcher unit test). Keep the live proof separate.
4. Rerun the live check with the q8 keys in a temp `config.json`, restored afterward.
5. Pass criteria: `GATE None`; 3 session connects OK with NO sleep between them; no `OutOfMemoryError` in `moshi-server.log`. If pass: update R37 "Autostart live" and the G7 row in `evidence-register.md`. If fail: record the excerpt in R37 and stop.
6. Wiring audit (`integration-wiring-audit.mdc`) before marking done.

## Operator env for the live check (Hive does not set these)

```powershell
$env:PYTHONPATH='D:\DRIVE_DOWNLOADS\HIVE_CODE_PLANNER\src;D:\DRIVE_DOWNLOADS\moshi-q8-spike\stubs;D:\DRIVE_DOWNLOADS\moshi-rag-src\moshi'
$env:NO_TORCH_COMPILE='1'; $env:NO_CUDA_GRAPH='1'; $env:HF_HUB_ENABLE_HF_TRANSFER='0'
$env:REFERENCE_ENCODER_URL='http://127.0.0.1:9'; $env:LLM_BASE_URL='http://127.0.0.1:8009/v1'
$env:LLM_API_KEY='unused-spike'; $env:LLM_MODEL_NAME='stub'
# stub on 8009: llm_stub.py must be running
```

Temp config keys used for the check (only for the run):
- `moshi_q8_weights`: `D:\DRIVE_DOWNLOADS\POD_BACKUPS\irfh4yaasw-q8\model.q8.safetensors`
- `moshi_mimi_weights`: `D:\DRIVE_DOWNLOADS\MOSHI_RAG_WEIGHTS\moshika-rag-pytorch-bf16\tokenizer-e351c8d8-checkpoint125.safetensors`
- `moshi_tokenizer`: `D:\DRIVE_DOWNLOADS\MOSHI_RAG_WEIGHTS\moshika-rag-pytorch-bf16\tokenizer_spm_32k_3.model`
- `moshi_model_config`: `D:\DRIVE_DOWNLOADS\moshi-q8-spike\config.local.json`

Scratch check: `py -3.11 D:\DRIVE_DOWNLOADS\moshi-q8-spike\autostart_gate_check.py` from the repo root (it reads `.hive/voice-bot/config.json`). Last output: `D:\DRIVE_DOWNLOADS\moshi-q8-spike\autostart_15c.log`.

## Do not redo

- A1/A2/A2b smoke. A3b recorded probe (done). Timeout change (15 s, done).
- The handover itself (done and tested). Do not revert to closing the probe for the call path.

## Caveats

- Evidence register G7 row still says `pass` from the 2026-11-15 local A3b run. Do not change it without a new passing live check. The live check only proves connects, not the fixed race.
- Keep `moshi_autostart` at its current value in `config.json` unless the live check passes.
