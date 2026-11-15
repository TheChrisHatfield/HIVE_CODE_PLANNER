# Cursor handoff — Voice_Bot session 15h (2026-11-15)

Background: operator paste at session start (15h); prior handoff `cursor-handoff-2026-11-15-session15e.md`. R37 q8 autostart **PASS (15e, commit `b707869`)**. This session: operator env confirmation (15g), wiring audit for Hive Voice bot + launcher UI (in progress, no code fixes yet).

## Status

- **R37 autostart:** still **PASS**. Do not rerun `autostart_gate_check.py` unless `scripts/moshi_q8_server.py` or `voice_moshi*` gate path changes.
- **15g confirmation (operator choice):** process-scoped env + q8 keys already in `.hive/voice-bot/config.json`. `autostart_gate_check.py` → `GATE None` after **58.1 s**; `ATTEMPT 0/1/2 OK`; exit 0. Log: `D:\DRIVE_DOWNLOADS\moshi-q8-spike\autostart_15g.log`. Config hash unchanged. **Not** a new G7 row (no transcript/spoken reply).
- **Stub LLM:** `D:\DRIVE_DOWNLOADS\moshi-q8-spike\llm_stub.py` already listening on **8009** (PID varied by session; answers `{"status":"ok"}`). Not restarted in 15h.
- **Wiring audit:** code trace + partial live context; **no product code changed** in 15h. Full `pytest -k "voice or acp"` was **not completed** (shell spawn aborted). Treat regression count as **last known good** from prior session (69+35 on moshi slices unless re-run).

## Config state (this host)

`.hive/voice-bot/config.json` (uncommitted vs last Voice_Bot commit if only this file changed):

- `voice_layer`: default **moshi** (field absent → default in loader)
- `stt_provider`: `faster-whisper` (typed / WAV mic path only)
- `moshi_autostart`: `true`
- Four q8 keys **pinned** → Hive picks `scripts/moshi_q8_server.py` via `q8_server_command` when autostart starts the child
- `input_device`: null unless operator set via Settings dropdown (T042c)

**Operator env:** Hive and the launcher **do not** set child env. Panel/CLI processes need (per run or user-level):

```powershell
$env:PYTHONPATH='D:\DRIVE_DOWNLOADS\HIVE_CODE_PLANNER\src;D:\DRIVE_DOWNLOADS\moshi-q8-spike\stubs;D:\DRIVE_DOWNLOADS\moshi-rag-src\moshi'
$env:NO_TORCH_COMPILE='1'; $env:NO_CUDA_GRAPH='1'; $env:HF_HUB_ENABLE_HF_TRANSFER='0'
$env:REFERENCE_ENCODER_URL='http://127.0.0.1:9'; $env:LLM_BASE_URL='http://127.0.0.1:8009/v1'
$env:LLM_API_KEY='unused-spike'; $env:LLM_MODEL_NAME='stub'
```

Without these, autostart from a Hive-started child tends to **`moshi_server_exited`**.

## Wiring audit (15h) — traced chains

| Layer | Chain | Verdict |
|---|---|---|
| **Config → q8 child** | `VoiceBotConfig` q8 keys → `voice_moshi._listen_gate` → `SERVER.ensure(..., launch=q8_server_command)` → `MoshiServerProcess` → `scripts/moshi_q8_server.py` | **Wired** (needs operator env on child) |
| **Settings UI** | `app.py` Voice Bot card → `set_input_device` → `save_voice_bot_config`; read-only status fields | **Wired** |
| **Panel shell** | `VoicePanel` callbacks → `VoicePanelController`; bridge menu start/stop; side → `submit_typed` → `POST /v1/submit`; end → interrupt + `POST /v1/call/end` | **Wired** |
| **Panel mic, Moshi** | `on_mic(True)` → `voice_layer == "moshi"` → `_start_moshi_call` → **`moshi_call_gate`** (worker thread) → `talk(url, SoundDeviceIO(input_device))` → duplex `MoshiConversation` | **Wired** (live q8 not re-proven duplex in 15h) |
| **Panel mic, typed** | `voice_layer != "moshi"` → requires `stt_provider` + `WavMicRecorder` → WAV → `POST /v1/submit/spoken` | **Wired** (not default layer) |
| **CLI `moshi-talk`** | loads config → `SoundDeviceIO(input_device)` → `talk()` → **`open_session` only** — **no** `moshi_call_gate`, **no** autostart | **Gap vs panel** — operator must have server up (or start child manually with env) |
| **CLI `moshi-probe`** | `open_session` + round trip; optional `--record` for G7 | **Wired** |
| **Bridge spoken** | `POST /v1/submit/spoken` → `submit_spoken` → **`moshi_listen_gate`** (probe + optional autostart) → faster-whisper → `submit` | **Wired** for typed path; **conflicts with live Moshi call** (see below) |

## Gaps found (prioritize)

1. **T056 / panel utterance vs q8 slot (high):** Live call holds **one** websocket (`moshi_call_gate` handover). `_on_moshi_utterance` still calls `_submit_recording` → bridge `submit_spoken`, which runs **`moshi_listen_gate`** and opens **another** connection (and may try autostart). On q8 slot limit 1 this yields **`moshi_unreachable`** / “No available slots” while the call is up. Unit tests mock HTTP only (`test_moshi_utterance_*`); they do not exercise the bridge gate. **Needs a spec-backed fix** (e.g. skip listen gate when the utterance originates from an active panel Moshi call, or use typed submit without a second Moshi probe). Relates **T056**, **R37**, **T053**.
2. **T056 live duplex (15f carry):** Three `moshi-talk` runs: audio out, **no text**, empty transcript. Check **`input_device`** and mic RMS; retry 30–45 s with speech. Do not record G7 without real transcript/reply.
3. **Operator env persistence:** Autostart works when env is set in the **same** shell as the gate check; launcher/panel child still inherits **only** what the parent process has. Optional future task: wire env into `MoshiServerProcess` spawn (spec first).
4. **Uncommitted:** `docs/specs/Voice_Bot/spec.md` ~line 277 (A3c “live-proven by 15e autostart PASS”) and `.hive/voice-bot/config.json` q8 keys — commit or revert **Voice_Bot only**; do not sweep Moshi_Tool_Lane, bug-hunt, cartridge churn.
5. **Stale:** `D:\DRIVE_DOWNLOADS\moshi-q8-spike\serve_q8_15f.pid` — harmless.

## Validation (15h)

| Check | Result |
|---|---|
| `autostart_gate_check.py` (15g, process env, config with q8 keys) | PASS (see above) |
| `pytest -k "voice or acp"` full suite | **Not run** (aborted) — re-run before claiming regression |
| Live panel duplex on q8 | **Not run** in 15h |
| Wiring audit code trace | Done (this doc) |

## Do not redo

- Share LM cache, streaming reset (15d); `no_wait_stt_shutdown` (15e); call-gate handover; 15 s connect timeout; A3b probe semantics.
- Another autostart gate rerun unless moshi gate/launcher code changes (15g was operator confirmation only).

## Open / suggested next (pick with operator)

1. **Fix gap #1:** design + minimal patch for utterance → task during live Moshi call (avoid second `moshi_listen_gate` on q8).
2. **T056 live:** mic device/levels, then `voice-bot moshi-talk` or launcher mic with env + bridge + stub 8009; speak during call; note transcript/text_frames.
3. **Complete audit:** `py -3.11 -m pytest tests -k "voice or acp" -q`; optionally launcher panel integration tests.
4. **Commit/revert:** uncommitted spec A3c line + config q8 keys (Voice_Bot scope only).
5. **Hive child env:** optional — pass PYTHONPATH/LLM_* into `MoshiServerProcess` spawn (spec + impact packet first).

## Wiring audit (closure template for next chat)

After any fix, report: chain traced, gap fixed or deferred, how validated (targeted test + live step if applicable).

---

## Paste into next chat

```
Voice_Bot session 15i. Read `docs/specs/Voice_Bot/cursor-handoff-2026-11-15-session15h.md` fully, then R37 in `docs/specs/Voice_Bot/spec.md`. R37 q8 autostart PASS (15e, `b707869`); 15g reran gate with process env only as confirmation — do not rerun `autostart_gate_check.py` unless moshi_q8_server.py or voice_moshi* gate code changes.

State: q8 keys committed in `.hive/voice-bot/config.json` (uncommitted vs other work — confirm git). Stub LLM on 8009; operator env NOT set by Hive. Wiring audit 15h found a high-priority gap: panel live Moshi call + `_on_moshi_utterance` → `/v1/submit/spoken` runs `moshi_listen_gate` and fights q8’s single slot. T056 live duplex still open (audio out, no text in 15f).

Ask me what to do next: (1) fix utterance/gate conflict, (2) T056 live mic + moshi-talk/panel, (3) pytest full voice suite + wiring audit close, (4) commit/revert spec+config, (5) child env wiring. Do not record G7 without real transcript/spoken reply. Do not sweep non–Voice_Bot files into a Voice_Bot commit.
```