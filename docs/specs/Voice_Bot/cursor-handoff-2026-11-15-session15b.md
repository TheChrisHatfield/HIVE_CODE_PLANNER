# Voice_Bot — handoff after A3c (2026-11-15, session 15b)

**Supersedes:** `cursor-handoff-2026-11-15-session15.md` for A3b and A3c status. Session 15 facts (spike, A1/A2/A2b) still hold.

**Repo:** `D:\DRIVE_DOWNLOADS\HIVE_CODE_PLANNER` | **Python:** `py -3.11` | **Feature:** Voice_Bot

## Verdict

| Lane | Verdict |
|------|---------|
| G7 (T055) | pass, current row is local q8 (2026-11-15, recorded); prior pod pass restored as `G7-pod-2026-11-14` |
| Default probe, no wrapper | pass (handshake 4859 ms, 1 audio frame), `CONNECT_TIMEOUT_S` now 15 s |
| Hive autostart of q8 | **open**: gate starts launcher and handshake works, but the session connect fails (race below) |
| Full-agent production | NOT READY (unchanged) |

## Done this session (15b)

1. **A3b:** restarted spike server (clean GPU), `moshi-probe --record` passed, row written to `evidence-register.md`.
2. **Evidence restored:** `G7-pod-2026-11-14` row added (pass, superseded), the pod row the recorded run overwrote.
3. **A3c, timeout:** `CONNECT_TIMEOUT_S` 3.0 -> 15.0 in `src/hive_planner/voice_moshi.py`; R37 spec line added. Default probe passes without the wrapper.
4. **A3c, launcher:** new `scripts/moshi_q8_server.py` (spike fixes: streaming loader on device, Windows signal handler no-op, eval/no-grad). Child process only; HIVE never imports the model.
5. **A3c, config keys:** `moshi_q8_weights`, `moshi_mimi_weights`, `moshi_tokenizer`, `moshi_model_config` in `VoiceBotConfig` (`src/hive_planner/voice_bot.py`), all-or-none validation. `q8_server_command()` in `voice_moshi_server.py`; `ensure(url, is_ready, launch)` takes an optional per-start command; the listen gate passes it only when the q8 keys are set.
6. **Tests:** `tests/test_voice_moshi.py` + `tests/test_voice_moshi_server.py` = 36 passed. New tests: q8 all-or-none, argv carries four paths, gate starts the launcher (not bare), launcher refuses missing files.
7. **Local config:** `.hive/voice-bot/config.json` has `moshi_autostart: true`, q8 keys removed (reverted, so Hive is not half-working). `edits_enabled` latch untouched.

## Open issue: back-to-back connection race (blocks live autostart)

- Measured on a fresh launcher (`scripts/moshi_q8_server.py`): connect 0 OK 4.6 s; connect 1 immediately after close FAILS `moshi_unreachable`; the same two connects with a 2 s pause both OK.
- Listen gate does probe-then-close (`_probe_code`), then the session connects right away. So the gate passes and the session fails.
- Server log shows `torch.OutOfMemoryError` on GPU 0 in one run (15.14 GiB allocated). Per-connection Mimi `deepcopy` is the suspected cause; not proven.
- Hive child stdout/stderr go to DEVNULL (`voice_moshi_server.py`), so server errors are invisible from Hive.

## Decision still needed (do not pick silently)

1. **Hand over** the gate's open session to the caller (one connection only). Recommended.
2. **Launcher reuses one Mimi copy** instead of per-connection deepcopy (touches upstream internals; riskier).
3. **Settle delay** after gate probe closes (quick, fragile).

Also consider: send child output to a log file under `.hive/voice-bot/` (small behavior change; spec line first).

## Quick relaunch (manual, for probes)

```powershell
# env (spike)
$env:PYTHONPATH='D:\DRIVE_DOWNLOADS\HIVE_CODE_PLANNER\src;D:\DRIVE_DOWNLOADS\moshi-q8-spike\stubs;D:\DRIVE_DOWNLOADS\moshi-rag-src\moshi'
$env:NO_TORCH_COMPILE='1'; $env:NO_CUDA_GRAPH='1'; $env:HF_HUB_ENABLE_HF_TRANSFER='0'
$env:REFERENCE_ENCODER_URL='http://127.0.0.1:9'; $env:LLM_BASE_URL='http://127.0.0.1:8009/v1'
$env:LLM_API_KEY='unused-spike'; $env:LLM_MODEL_NAME='stub'
# stub on 8009 (llm_stub.py) must be running; then the launcher:
py -3.11 scripts\moshi_q8_server.py --port 8998 --q8 D:\DRIVE_DOWNLOADS\POD_BACKUPS\irfh4yaasw-q8\model.q8.safetensors --mimi D:\DRIVE_DOWNLOADS\MOSHI_RAG_WEIGHTS\moshika-rag-pytorch-bf16\tokenizer-e351c8d8-checkpoint125.safetensors --tokenizer D:\DRIVE_DOWNLOADS\MOSHI_RAG_WEIGHTS\moshika-rag-pytorch-bf16\tokenizer_spm_32k_3.model --config D:\DRIVE_DOWNLOADS\moshi-q8-spike\config.local.json
```

Health 200 takes about 35 s. Do not run two connections back to back on one server; wait about 2 s between connects.

## Scratch scripts (outside repo, spike only)

- `D:\DRIVE_DOWNLOADS\moshi-q8-spike\autostart_gate_check.py`: runs the listen gate then three timed connects.
- `D:\DRIVE_DOWNLOADS\moshi-q8-spike\two_connection_check.py` (2 s gap, OK) and `two_connection_nosleep.py` (no gap, FAIL).

## Do not redo

- A1/A2/A2b smoke. A3b recorded probe (done; do not re-record without a reason).
- Timeout change (done, tested).

## Validation (session 15b)

| Check | Result |
|-------|--------|
| `pytest tests/test_voice_moshi.py tests/test_voice_moshi_server.py` | 36 passed |
| ReadLints on edited Python | no errors |
| Default `moshi-probe`, no wrapper, no `--record` | g7 pass, handshake 4859 ms |
| Listen-gate autostart (q8 keys) | gate None after 55-59 s, child running (launcher, not bare) |
| Session connect after autostart | FAIL (race above); not closed |

## Wiring audit (session 15b)

- **Chain traced:** config keys -> `VoiceBotConfig` -> `moshi_listen_gate` -> `SERVER.ensure(launch=q8_server_command)` -> `scripts/moshi_q8_server.py` -> upstream `moshi.server.main()` -> WS `/api/chat` -> handshake OK.
- **Gap:** after the gate, the session connect is refused by the server (back-to-back race). Integration is not complete.
- **Gap:** child output is DEVNULL; failures are only visible by manual launcher run.
- **Spec:** R37 lines added for timeout, q8 keys, and the race.
