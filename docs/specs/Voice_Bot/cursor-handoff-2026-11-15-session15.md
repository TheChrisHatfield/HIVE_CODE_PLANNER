# Voice_Bot — handoff after local loopback moshi.server (2026-11-15, session 15)

**Purpose:** Continue **Voice_Bot** with **A3 partly closed**: q8 `moshi.server` runs on loopback; G7 probe passes only with spike launcher, extended connect timeout, and stub LLM. Hive autostart and recorded G7 evidence remain open.

**Supersedes:** `docs/specs/Voice_Bot/cursor-handoff-2026-11-15-session14.md` for **A2b ARC real weights** and **A3 moshi.server** status. Session 14 shim facts and session 13 q8 forward still hold.

**Repo:** `D:\DRIVE_DOWNLOADS\HIVE_CODE_PLANNER`
**Python (this host):** `py -3.11`
**Active feature:** Voice_Bot

## Verdict

| Lane | Verdict |
|------|---------|
| read-only typed preview | READY |
| full-agent production | NOT READY |
| G7 Moshi harness (T055) | pass (recorded; old pod URL) |
| G7-q8 | pass (caveated) |
| Local q8 LM forward (A1) | pass (session 13) |
| ARC shim + random-weight encode (A2) | pass (session 14) |
| **ARC real weights (A2b)** | **pass (session 15, prior in-chat)** — bf16 load, one `forward_embedder`, finite; production `load_weights()` VRAM not measured |
| **Loopback moshi.server + probe (A3)** | **partial pass (session 15)** — spike `serve_q8.py`; probe `g7: pass` without `--record`; not Hive autostart |
| T056 live Moshi talk | open — local server spike-only; 6× frame latency; RAG/ARC stubbed |
| T056 STT clips (pinned Whisper) | partial — rows through -4; no WER |
| T042 slice 5e | docs closed in `tasks.md` |
| Moshi replaces Whisper (refactor) | blocked — needs spec/Delta first (R36/R10/R37); no VoiceBot code changed |

## Done session 15 (this chat)

### A2b (carried from prior turn in same session 15 thread; not repeated here)

- `kyutai/ARC4_Encoder_Llama` on cuda:1 bf16; script `D:\DRIVE_DOWNLOADS\moshi-q8-spike\arc_real_weights.py`, log `arc_real_weights.log`.
- Checkpoint all F32; per-tensor bf16 on CPU before load; peak cuda:1 ~11.25 GiB; forward (1, 12, 4096) finite.
- Unexpected keys `embedder.cont_tok.0.weight`, `rec_tok.0.weight` (same as production `strict=False`).

### A3 (loopback server + probe)

1. **`serve_q8.py`** — spike launcher calling upstream `moshi.server.main()` with q8 paths from `config.local.json`.
2. **`llm_stub.py`** — port 8009 OpenAI-compat stub for upstream `LLMReferenceGenerator` warmup (`LLM_BASE_URL` required).
3. **`probe_a3_wrapper.py`** — raises `CONNECT_TIMEOUT_S` to 15 s for probe only (handshake ~4.7 s; repo default 3.0 s).
4. **`A3_moshi_server_result.md`** in spike folder — launch recipe and open issues.
5. **Deps installed** on host: `msgpack`, `gradium` (upstream server imports).
6. **Probe (no `--record`):** `g7: pass`, handshake 4765 ms, `audio_frames: 1`, log `moshi_probe_a3.log`.

### Spike fixes in `serve_q8.py` (not in Hive repo)

| Fix | Why |
|-----|-----|
| `stream_load(..., device)` places tensors on target device | Else all 780 LM params stay CPU → warmup `scatter_with_mask_` device error |
| `AbstractEventLoop.add_signal_handler` no-op | Windows `NotImplementedError` in upstream `_serve()` |
| Patch `CheckpointInfo.get_mimi/get_moshi` → `eval()` + `requires_grad_(False)` | Else `pcm.numpy()` fails in `_output_loop` |

`moshi-rag-src` `quantize.py` already has `.float()` on `weight_scb` (G7-q8 patch applied locally).

## Gotchas (session 15)

- Upstream **`get_reference_encoder_url()`** must be set or server exits; with it set, **`reference_with_time` is skipped** locally (ARC not in server process).
- Upstream **`LLM_BASE_URL`** must be set; warmup hits a real HTTP POST (use `llm_stub.py` or a real vLLM).
- **`CONNECT_TIMEOUT_S = 3.0`** in `voice_moshi.py` → default probe `moshi_unreachable` even when server is healthy.
- **Per-connection `deepcopy(mimi_copy)`** on cuda:0; LM ~12.9 GiB on 16 GiB T10 → OOM after failed probes; **restart server** between probe attempts.
- Hive **`voice_moshi_server.server_command`** = bare `python -m moshi.server` only — **cannot** start q8 stack without new config wiring.

## RunPod (re-read every chat)

| Field | Value |
|-------|-------|
| Account pods | not re-verified this chat (re-verify with `list-pods`) |
| Former pod | `t13xqwp4ilb953` — TERMINATED |

## Local assets (this host)

| Asset | Path |
|-------|------|
| 2× Tesla T10 16 GB | cuda:0 (server LM+Mimi); cuda:1 free while ARC skipped in server |
| q8 weights | `D:\DRIVE_DOWNLOADS\POD_BACKUPS\irfh4yaasw-q8` |
| bf16 mimi/tokenizer | `D:\DRIVE_DOWNLOADS\MOSHI_RAG_WEIGHTS\moshika-rag-pytorch-bf16` |
| q8 spike | `D:\DRIVE_DOWNLOADS\moshi-q8-spike` (`serve_q8.py`, `llm_stub.py`, `probe_a3_wrapper.py`, `A3_moshi_server_result.md`, prior A1/A2 scripts) |
| moshi-rag source | `D:\DRIVE_DOWNLOADS\moshi-rag-src` |
| xformers shim | `D:\DRIVE_DOWNLOADS\moshi-q8-spike\stubs\xformers` |
| **Required env (spike server)** | `NO_TORCH_COMPILE=1`, `NO_CUDA_GRAPH=1`, `PYTHONPATH=D:\DRIVE_DOWNLOADS\moshi-q8-spike\stubs;D:\DRIVE_DOWNLOADS\moshi-rag-src\moshi`, `REFERENCE_ENCODER_URL` (any URL if skipping local ARC), `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL_NAME` |

### Quick relaunch (A3)

```powershell
# From spike folder; start stub first if not running
py -3.11 D:\DRIVE_DOWNLOADS\moshi-q8-spike\llm_stub.py
# Server (see A3_moshi_server_result.md for full env)
py -3.11 D:\DRIVE_DOWNLOADS\moshi-q8-spike\serve_q8.py 8998
# Probe without --record (15 s connect budget)
py -3.11 D:\DRIVE_DOWNLOADS\moshi-q8-spike\probe_a3_wrapper.py 15 voice-bot moshi-probe --url ws://127.0.0.1:8998/api/chat --timeout 90
```

## Do not redo

- A1 forward smoke (`forward_run2.log`).
- A2 shim / random-weight ARC smoke unless shim files change.
- A2b real-weight ARC forward unless checkpoint or loader changes.
- Full A3 bring-up from scratch unless `serve_q8.py` or weights change — reuse `A3_moshi_server_result.md`.

## Open micro-tasks (pick one per chat)

### A. Local inference spike (no repo)

1. ~~A1 q8 forward~~ **done (session 13).**
2. ~~A2 ARC shim~~ **done (session 14).**
2b. ~~A2b ARC real weights (spike script)~~ **done (session 15).** Optional: **A2c** production `ArcEncoderConditioner.load_weights()` VRAM; paraphrase similarity on ARC output.
3. ~~A3 server + unrecorded probe~~ **partial (session 15).** **Next:** `moshi-probe --record` after clean server restart; spec/Delta for `CONNECT_TIMEOUT_S` vs local handshake; wire Hive `moshi_autostart` + q8 paths; real LLM + reference encoder URL (or local ARC path without skip).

### B. Spec before Moshi-primary STT refactor

Unchanged — Delta + `spec.md` for R36/R10/R37; `moshi_autostart` q8 on Windows.

### C. VoiceBot product

5e spoken path; live talk after probe + autostart; optional Windows loopback_echo pytest bisect.

### D. RunPod (billing)

Only with user go-ahead.

## Validation (session 15)

| Check | Result |
|-------|--------|
| `GET http://127.0.0.1:8998/api/health` | 200 |
| `moshi_probe_a3.log` (wrapper 15 s connect, no `--record`) | `g7: pass`, handshake 4765 ms, audio_frames 1 |
| Repo pytest | not run (spike-only; no `src/` change) |

## Wiring audit (session 15)

- **Repo:** `docs/specs/Voice_Bot/cursor-handoff-2026-11-15-session15.md` only.
- **Chain traced (probe):** CLI `moshi-probe` → `moshi_live_probe` → `open_session` → WS `0x00` handshake → silence Opus frames → recv audio/text.
- **Chain traced (server):** `serve_q8.py` → `moshi.server.main` → `load_models` → q8 `CheckpointInfo.from_hf_repo` → warmup → aiohttp WS `/api/chat`.
- **Gaps:** Hive `MoshiServerProcess.server_command` does not pass q8 args or env; `CONNECT_TIMEOUT_S` too low for measured handshake; G7 evidence not written; RAG/ARC/real LLM not in loop.

## Files touched session 15

- Repo: `docs/specs/Voice_Bot/cursor-handoff-2026-11-15-session15.md` (this file).
- Outside repo: `moshi-q8-spike/serve_q8.py`, `llm_stub.py`, `probe_a3_wrapper.py`, `diag_lm_device.py`, `A3_moshi_server_result.md`, logs `serve_q8_8998.*`, `moshi_probe_a3.log`; host pip `msgpack`, `gradium`.

## Paste into new chat

```
Voice_Bot next micro-task (session 15 handoff — recorded probe or Hive autostart)

Handoff: docs/specs/Voice_Bot/cursor-handoff-2026-11-15-session15.md
Repo: D:\DRIVE_DOWNLOADS\HIVE_CODE_PLANNER | Python: py -3.11

Verdict: read-only=READY full-agent=NOT READY | G7 T055=pass | G7-q8=pass | local q8 forward=pass (A1) | ARC shim=pass (A2) | ARC real weights=pass (A2b) | A3 loopback server+probe=PARTIAL (g7 pass unrecorded) | T056 live=open | T042 5e=docs done | Moshi-as-STT refactor=spec-blocked

Done session 15: serve_q8.py + llm_stub + probe wrapper; health 200; moshi-probe g7=pass (4765 ms handshake, 1 audio frame) WITHOUT --record. Spike fixes: stream_load device, Windows signal handler, eval/no-grad. Installed msgpack+gradium.

Open A3 gaps: CONNECT_TIMEOUT_S 3s < ~4.7s handshake; Hive autostart has no q8 paths; Mimi deepcopy OOM if server not restarted; RAG/ARC/LLM stubbed; batched step ~500ms/frame.

Pod: none (re-verify list-pods)
Local: 2× T10 16GB | q8 POD_BACKUPS\irfh4yaasw-q8 | spike D:\DRIVE_DOWNLOADS\moshi-q8-spike (read A3_moshi_server_result.md) | moshi-rag-src D:\DRIVE_DOWNLOADS\moshi-rag-src
Spike env: NO_TORCH_COMPILE=1 NO_CUDA_GRAPH=1 PYTHONPATH=D:\DRIVE_DOWNLOADS\moshi-q8-spike\stubs;D:\DRIVE_DOWNLOADS\moshi-rag-src\moshi

Do not redo: A1/A2/A2b smoke; full A3 bring-up unless serve_q8.py changes

Open next (one): A3b) moshi-probe --record after clean server restart, A3c) spec+wire Hive moshi_autostart for q8, A2c) production ARC load_weights VRAM, B) Moshi-primary STT spec, C) 5e spoken, D) RunPod pod

First action: read handoff § Quick relaunch and A3_moshi_server_result.md; confirm server/stub PIDs or relaunch; run probe with --record OR draft spec delta for CONNECT_TIMEOUT_S + autostart args
```