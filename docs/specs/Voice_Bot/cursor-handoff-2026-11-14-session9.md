# Voice_Bot — handoff after G7-q8 stack live on pod (2026-11-14, session 9)

**Purpose:** Continue **T056 live `moshi-talk`** and optional **G7-q8 evidence** on pod **`t13xqwp4ilb953`** (RUNNING, billable). **Full stack is up; q8 loads with quantize patch; host `moshi-probe` passed without `--record`.** Utterances and register updates remain **open**.

**Supersedes:** `docs/specs/Voice_Bot/cursor-handoff-2026-11-14-session8.md` for bootstrap, stack, and probe state.

**Repo:** `D:\DRIVE_DOWNLOADS\HIVE_CODE_PLANNER`  
**Python (this host):** `py -3.11`  
**Active feature:** Voice_Bot

## Verdict

| Lane | Verdict |
|------|---------|
| read-only typed preview | READY |
| full-agent production | NOT READY |
| **G7 Moshi harness (T055)** | **pass** — recorded 2026-11-14 (`moshi-probe --record` on old pod; do not redo unless user asks) |
| **G7-q8 q8 + quantize on server** | **partial → live-proven (unrecorded)** — stack on `t13xqwp4ilb953`; probe **pass** without `--record`; `evidence-register.md` still **partial** until user authorizes record or manual row update |
| **T056 Moshi wiring + duplex** | **code done** — **live `moshi-talk` / utterances > 0 not done** |

## Active pod (billable)

| Field | Value |
|-------|-------|
| Pod id | **`t13xqwp4ilb953`** |
| Name | `g7-q8-reprove-voice-bot` |
| Status | **RUNNING** — re-read with `get-pod` |
| GPU | NVIDIA H100 NVL ×1, secure, **US-KS-2** |
| Catalog price | **$3.19/hr** (container **200 GB** disk bills separately) |
| Image | `runpod/pytorch:1.0.2-cu1281-torch280-ubuntu2404` |
| Host CUDA | 13.2 |
| Ports | 8998, 8011, 8002 (http), 22 (tcp) |
| **Proxy Moshi URL** | `wss://t13xqwp4ilb953-8998.proxy.runpod.net/api/chat` |
| Exec | Runpod MCP **`exec-pod`** (preferred over operator SSH direct) |
| SSH proxy | `ssh t13xqwp4ilb953-64410a71@ssh.runpod.io` |

**Terminate or stop when user says billing should stop** — not automatic after tests.

**Old pod:** `yfhzy2r86j9akc` remains **gone** (404).

## Stack state (session 9 — verify each chat)

Re-read with `exec-pod`: `ss -ltnp` for **8011, 8002, 8998**; tail `ref_encoder_8011.log`, `vllm_8002.log`, `moshi_8998.log`.

| Service | Port | Log | Last known |
|---------|------|-----|------------|
| `moshi.server_conditioner` (encoder) | **8011** | `/workspace/ref_encoder_8011.log` | Listening; Uvicorn on `0.0.0.0:8011` |
| `vllm serve` Qwen2.5-3B-Instruct | **8002** | `/workspace/vllm_8002.log` | Listening; **`--gpu-memory-utilization 0.3`** (0.2 failed KV cache next to encoder) |
| `moshi.server` (q8 weights) | **8998** | `/workspace/moshi_8998.log` | Listening; weights `/workspace/q8/` |

**GPU VRAM (session 9):** ~88 GB used with stack up (little headroom).

**HF cache:** ~32 GB warm under `/workspace/.cache/huggingface` after first boot.

## q8 on pod

| Path | Note |
|------|------|
| `/workspace/q8/model.q8.safetensors` | 12,237,164,792 bytes |
| `/workspace/q8/config.json` | present |
| SHA256 | `0142f1c7df455c50e882cee8210ae3ccc28fecf1310762a6d7c3a693e89a0ddc` |

## Session 9 completed

1. **Bootstrap** on fresh pod disk: clone `kyutai-labs/moshi-rag` → `/workspace/moshi-rag-src`; `/tmp/vllm-venv` (moshi 0.2.13 + RAG runtime deps); `/tmp/vllm2` (vLLM 0.33.0).
2. **Quantize patch** applied per `docs/specs/Voice_Bot/pod-artifacts/G7-q8-quantize-patch.md` (`quantize.py.orig` on pod).
3. **Pod-only source edits** (not in repo): `arc_encoder.py` — `use_fast=True`; tokenizer default **`unsloth/Llama-3.2-3B-Instruct`** (gated `meta-llama/...` fails); `xformers==0.0.33.post2` with `uv pip install --no-deps` (0.0.36 breaks torch 2.9.1).
4. **Extra deps** in `/tmp/vllm-venv` beyond handoff list: `openai`, `transformers==4.55.3`, `websockets`, `sphn`, `httpx`, `fastapi`, `uvicorn`, `scipy`, `accelerate`, and others scanned from RAG imports.
5. **Stack started** — all three ports listening.
6. **Cold-handshake trap:** first host `moshi-probe` → `moshi_unreachable` (STT cold build; host `CONNECT_TIMEOUT_S=3`). Pod warm script `/workspace/warm_ws.py` → handshake byte `0x00` in ~1.1 s.
7. **Probe (no record):** `py -3.11 -m hive_planner voice-bot moshi-probe --feature Voice_Bot --url wss://t13xqwp4ilb953-8998.proxy.runpod.net/api/chat --timeout 60 --model-repo kyutai/moshika-rag-pytorch-bf16` → **`g7: pass`**, `handshake_ms 1468.0`, `audio_frames 1`, `reason handshake_and_round_trip`.

## Launch recipes (restart if stack down)

From `docs/specs/Voice_Bot/cursor-g7-runpod-handoff.md`, with these **session 9 deltas**:

- vLLM: add **`--gpu-memory-utilization 0.3`**.
- Ensure `/tmp/vllm-venv` has RAG deps and `xformers==0.0.33.post2` before encoder start.
- Apply quantize sed + `arc_encoder` fixes if pod disk wiped.

**Encoder :8011**

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

**vLLM :8002**

```bash
export PATH=/tmp/vllm2/bin:$PATH
cd /workspace
nohup vllm serve Qwen/Qwen2.5-3B-Instruct \
  --host 0.0.0.0 --port 8002 --api-key dummy \
  --gpu-memory-utilization 0.3 --max-model-len 4096 \
  > /workspace/vllm_8002.log 2>&1 &
```

**Moshi :8998 (q8)**

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

**Warm before host probe (if stack was cold-restarted)**

```bash
nohup /tmp/vllm-venv/bin/python3 /workspace/warm_ws.py > /workspace/warm_ws.log 2>&1 &
# expect: HANDSHAKE_BYTES 1 first_byte 00 ... ~1–65 s first time
```

## Do not redo

- G7 T055 `moshi-probe --record` on old pod URL unless user asks.
- Re-upload q8 if `/workspace/q8/sha.txt` still matches (unless pod wiped).
- Full bootstrap from scratch if `/tmp/vllm-venv`, moshi-rag clone, and HF cache still present.
- Recreate pod while `t13xqwp4ilb953` RUNNING unless user requests replace.
- Wrong proxy host (use **`-8998`** suffix, not raw public port in hostname).
- Broad `pkill` on `vllm serve` / `moshi.server_conditioner` via `exec-pod` (pattern can kill the wrapper shell).

## Open micro-tasks (priority)

1. **T056 live:** `py -3.11 -m hive_planner voice-bot moshi-talk --url wss://t13xqwp4ilb953-8998.proxy.runpod.net/api/chat --duration N` — operator mic; **`utterances > 0`** when user speaks. No concurrent `moshi-probe` during active call (server lock).
2. **G7-q8 evidence (optional):** User decision on `--record` vs manual `evidence-register.md` / `deployment-gaps.md` update for `t13xqwp4ilb953` + q8 patch criteria.
3. **Repo follow-up (optional):** Document session 9 pod-only deps, vLLM 0.3 util, arc_encoder/unsloth defaults, warm-up script in handoff or deployment-gaps.
4. **Billing:** `pod-action` stop/terminate when user says stop.

## Local artifacts

| Asset | Path |
|-------|------|
| q8 backup | `D:\DRIVE_DOWNLOADS\POD_BACKUPS\irfh4yaasw-q8\` |
| Quantize runbook | `docs/specs/Voice_Bot/pod-artifacts/G7-q8-quantize-patch.md` |
| Stack recipes | `docs/specs/Voice_Bot/cursor-g7-runpod-handoff.md` |
| Prior handoff | `docs/specs/Voice_Bot/cursor-handoff-2026-11-14-session8.md` |

## Files touched session 9

- `docs/specs/Voice_Bot/cursor-handoff-2026-11-14-session9.md` (this file)

## Paste into new chat

```
Voice_Bot next micro-task (session 9 handoff — T056 live moshi-talk)

Handoff: docs/specs/Voice_Bot/cursor-handoff-2026-11-14-session9.md
Repo: D:\DRIVE_DOWNLOADS\HIVE_CODE_PLANNER | Python: py -3.11

Verdict: read-only=READY full-agent=NOT READY | T055 G7=pass (recorded) | G7-q8=live pass unrecorded | T056 live=open

Active pod: t13xqwp4ilb953 RUNNING ~$3.19/hr — billing ON until terminate/stop
Proxy (live): wss://t13xqwp4ilb953-8998.proxy.runpod.net/api/chat
Stack: :8011/:8002/:8998 up; q8 + quantize patch; ~88 GB VRAM

Done session 9:
- Bootstrap venv/moshi-rag; quantize patch; pod-only arc_encoder + xformers + extra deps
- vLLM gpu-memory-utilization 0.3; warm_ws then moshi-probe pass (1468 ms, audio 1) without --record

Do not redo: G7 --record on old pod; re-bootstrap if stack still up; re-upload q8 if sha valid

Open next (one micro-task): get-pod + ss logs → warm if cold → moshi-talk utterances; optional evidence-register G7-q8 update

Blocked: none

First action: get-pod t13xqwp4ilb953; exec-pod ss -ltnp + tail moshi_8998.log; moshi-talk --url wss://t13xqwp4ilb953-8998.proxy.runpod.net/api/chat
```