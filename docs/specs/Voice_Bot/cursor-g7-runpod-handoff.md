# Voice_Bot — G7 Runpod live stack handoff (2026-11-14, session 4 end)

> **Pod closed (session 5):** use **`cursor-handoff-2026-11-14-session5.md`** for the next chat paste block and T056 follow-ups. Keep this file for **stack launch recipes** and G7 history.

**Purpose:** Continue **Voice_Bot live Moshi** on Runpod after **G7 pass (T055 done)**. Next focus: **T056** live `moshi-talk` / wiring audit; pod **kept RUNNING** for that work unless the user terminates.

**Repo:** `D:\DRIVE_DOWNLOADS\HIVE_CODE_PLANNER`  
**Python (this host):** `py -3.11`  
**Active feature:** Voice_Bot — `evidence-register.md` (G7 **pass**, G7-q8 partial), **T056** open.

## Verdict

| Lane | Verdict |
|------|---------|
| read-only typed preview | READY |
| full-agent production | NOT READY (unchanged) |
| **G7 Moshi harness (T055)** | **pass** — `moshi-probe --record` 2026-11-14 |
| **G7-q8 on live server** | **partial** — q8 loads on pod with quantize patch only |
| **T056 live conversation** | **open** — code + tests on host; live duplex not recorded |

## G7 evidence (do not re-record unless reproving)

| Field | Value |
|-------|-------|
| Pod | `yfhzy2r86j9akc` (`g7-moshi-single-h100`) |
| Probe URL | `wss://yfhzy2r86j9akc-8998.proxy.runpod.net/api/chat` |
| Model label | `kyutai/moshika-rag-pytorch-bf16` |
| Result | `g7 pass`, handshake ~1562 ms, `audio_frames 1`, reason `handshake_and_round_trip` |
| Register | `docs/specs/Voice_Bot/evidence-register.md` G7 row **pass** |

**Proxy trap:** use hostname suffix **`-8998`**, not public port **60831** (Cloudflare **404** on wrong host).

## Live pod (billing — user chose KEEP after G7)

| Field | Value |
|-------|-------|
| Pod id | `yfhzy2r86j9akc` |
| Status | **RUNNING** (verify with `get-pod` each session) |
| GPU | **NVIDIA H100 NVL**, ~94 GB VRAM |
| Cost | **$3.19/hr** |
| Moshi proxy | `wss://yfhzy2r86j9akc-8998.proxy.runpod.net/api/chat` |
| Exec | Runpod MCP **`exec-pod`** |

**Terminate when user says stop:** `pod-action` terminate on `yfhzy2r86j9akc` (destroys pod disk including q8 + pod-only patches).

## On-pod state (session 4 end — stack was UP)

Re-verify after idle/reboot; processes may have died.

| Item | Status (last known) |
|------|---------------------|
| Encoder **:8011** | Up — `ref_encoder_8011.log`, ~24 GB VRAM |
| vLLM **:8002** | Up — `/tmp/vllm2`, Qwen2.5-3B-Instruct, log `vllm_8002.log` |
| `moshi.server` **:8998** | Up — `0.0.0.0`, q8 weights, log `moshi_8998.log`, ~76 GB total GPU with stack |
| `/workspace/q8/` | q8 safetensors + config on pod disk |
| `/tmp/vllm-venv` | moshi 0.2.13 + **msgpack**, **gradium** (added session 4) |
| `/tmp/vllm2` | vLLM 0.33.0 — **only** for `vllm serve` |
| HF cache | Warm under `/workspace/.cache/huggingface` (STT, encoder, Qwen, artifacts) |

**Local q8 SHA256:** `0142f1c7df455c50e882cee8210ae3ccc28fecf1310762a6d7c3a693e89a0ddc`

## Pod-only fixes (not in repo)

1. `arc_encoder.py`: `unsloth/Llama-3.2-3B-Instruct`; **`use_fast=True`** (line 413).
2. Encoder **`--port 8011`** (nginx on **8001**).
3. **`HF_HUB_ENABLE_HF_TRANSFER=0`** for encoder and Moshi (image enables hf_transfer without package).
4. **`PYTHONPATH=/tmp/enc-libs:/workspace/moshi-rag-src/moshi`** for Moshi (stock site-packages lacks `multi_arc_encoder`).
5. **`quantize.py`**: `state.SCB = self.weight_scb.float()` — required for q8 load; backup `quantize.py.orig`.
6. Moshi **`--host 0.0.0.0`** so Runpod proxy reaches the server (not `127.0.0.1` only).
7. **Never `pkill -f 'python3 -m moshi.server'`** — pattern can kill **`server_conditioner`**; use `pkill -f 'moshi.server --host'` or pid-specific kill.

## Cold vs warm websocket

- **First client** after Moshi start: ~**65 s** until `0x00` handshake (per-connection STT build in RAG `Channel`).
- **Warm:** ~**1.1–1.6 s** handshake (`/workspace/hs_timing.log` on pod).
- Hive probe **`CONNECT_TIMEOUT_S = 3.0`**: warm stack only; pre-warm with one connection or pod-side curl/ws before `moshi-probe`.

## Launch recipes (session 4 — use when stack down)

**Encoder** (restart ~1–2 min with cache):

```bash
cd /workspace
HF_HUB_ENABLE_HF_TRANSFER=0 \
PYTHONPATH=/tmp/enc-libs:/workspace/moshi-rag-src/moshi \
nohup /tmp/vllm-venv/bin/python3 -m moshi.server_conditioner \
  --config hf://kyutai/moshika-rag-pytorch-bf16/config.json \
  --moshi-weight hf://kyutai/moshika-rag-pytorch-bf16/model.safetensors \
  --cuda-device 0 \
  --conditioner reference_with_time \
  --port 8011 \
  > /workspace/ref_encoder_8011.log 2>&1 &
```

**vLLM :8002**:

```bash
export PATH=/tmp/vllm2/bin:$PATH
cd /workspace
nohup vllm serve Qwen/Qwen2.5-3B-Instruct \
  --host 0.0.0.0 --port 8002 --api-key dummy \
  --gpu-memory-utilization 0.2 --max-model-len 4096 \
  > /workspace/vllm_8002.log 2>&1 &
```

**Moshi server** (q8, proxy-reachable):

```bash
cd /workspace
export HF_HUB_ENABLE_HF_TRANSFER=0
export PYTHONPATH=/tmp/enc-libs:/workspace/moshi-rag-src/moshi
export REFERENCE_ENCODER_URL=http://localhost:8011
export LLM_BASE_URL=http://localhost:8002/v1
export LLM_API_KEY=dummy
export LLM_MODEL_NAME=Qwen/Qwen2.5-3B-Instruct

nohup /tmp/vllm-venv/bin/python3 -m moshi.server \
  --host 0.0.0.0 --port 8998 --device cuda \
  --moshi-weight /workspace/q8/model.q8.safetensors \
  --config /workspace/q8/config.json \
  > /workspace/moshi_8998.log 2>&1 &
```

**Re-probe G7** (only if re-validating; register already pass):

```powershell
py -3.11 -m hive_planner voice-bot moshi-probe --feature Voice_Bot `
  --url wss://yfhzy2r86j9akc-8998.proxy.runpod.net/api/chat `
  --timeout 60 --model-repo kyutai/moshika-rag-pytorch-bf16
```

Add `--record` only if intentionally overwriting the G7 row.

## Next chat — ordered micro-tasks

1. `get-pod` — confirm RUNNING; `ss -ltnp` for 8011, 8002, 8998; restart stack from recipes if needed.
2. Optional warm-up: pod-side websocket or one failed probe with **long** timeout before real work.
3. **T056 live:** `py -3.11 -m hive_planner voice-bot moshi-talk --url wss://yfhzy2r86j9akc-8998.proxy.runpod.net/api/chat --duration N` (mic/speaker on Windows host; latency over proxy).
4. Complete **T056 wiring audit** in `tasks.md` with live notes (single-connection lock: no concurrent probe during talk).
5. Optional repo follow-ups: port quantize float cast into tracked script/docs; prove q8 without pod patch (G7-q8).
6. **Terminate pod** when user says billing should stop (not automatic after G7).

## Do not redo

- T055 `--record` (G7 already pass unless user asks to reprove).
- q8 transfer; encoder cold HF downloads; vllm2 build from `/tmp/vllm-venv` vLLM.
- Wrong proxy URL (`60831` host).
- `use_fast=False` tokenizer; encoder on **8001**.
- Broad `pkill` on `moshi.server` / `python3 -m moshi`.

## Wiring audit

- **Chain (validated session 4):** encoder (:8011) → vLLM (:8002) → moshi.server (:8998) → `moshi-probe --record` → evidence G7 **pass**.
- **Gap (T056):** live `moshi-talk` and panel duplex path against proxy URL; concurrent probe + talk (server lock).
- **G7-q8 gap:** q8 proven on server only with pod `quantize.py` patch.

## Paste into new chat

Copy as the **first user message** (or: *continue Voice_Bot Runpod using `docs/specs/Voice_Bot/cursor-g7-runpod-handoff.md`*):

```
CONTINUE Voice_Bot (Runpod — T056 live after G7 pass)

Last chat: 2026-11-14 session 4 (G7 pass recorded; pod kept for T056)
Budget: pod yfhzy2r86j9akc still billing $3.19/hr H100 NVL — user chose KEEP
Verdict: read-only=READY full-agent=NOT READY
G7: pass — moshi-probe --record via wss://yfhzy2r86j9akc-8998.proxy.runpod.net/api/chat (handshake ~1562 ms, audio 1)
G7-q8: partial — q8 loads on pod only with quantize.py float cast (not in repo)
T055: done | T056: open (live moshi-talk + wiring audit)

Done session 4:
- vLLM 0.33.0 :8002; moshi.server :8998 (0.0.0.0, q8); encoder :8011
- Pod deps msgpack/gradium; HF_HUB_ENABLE_HF_TRANSFER=0; PYTHONPATH moshi-rag-src; quantize SCB float cast
- G7 evidence + tasks.md T055; proxy URL uses -8998 not 60831
- Cold STT ~65s first ws; warm handshake ~1.1s (CONNECT_TIMEOUT_S=3 on host)

Open next:
- get-pod + verify stack → warm ws if needed
- Live moshi-talk against proxy URL; T056 wiring notes (no probe during active call — server lock)
- Optional: repo quantize/q8 doc; terminate pod when user stops billing

Do not redo: G7 --record; q8 transfer; vllm2 rebuild; wrong proxy host; broad pkill killing encoder

Files changed (session 4): docs/specs/Voice_Bot/evidence-register.md, tasks.md, cursor-g7-runpod-handoff.md

Blocked / watch: single Moshi connection lock; first handshake timeout if stack cold

First action: get-pod yfhzy2r86j9akc; exec-pod ss -ltnp + tail logs; if down, restart per handoff launch recipes; then moshi-talk with --url wss://yfhzy2r86j9akc-8998.proxy.runpod.net/api/chat
```