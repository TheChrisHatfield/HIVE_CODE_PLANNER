# Voice_Bot — handoff after q8 upload to G7-q8 pod (2026-11-14, session 8)

**Purpose:** Continue **G7-q8 live re-prove** on pod **`t13xqwp4ilb953`** (RUNNING, billable). **q8 weights and config are on the pod and SHA-verified.** Stack bootstrap, quantize patch apply, and live `moshi-talk` proof remain **open**.

**Supersedes:** `docs/specs/Voice_Bot/cursor-handoff-2026-11-14-session7.md` for pod asset state and upload blocker (cleared).

**Repo:** `D:\DRIVE_DOWNLOADS\HIVE_CODE_PLANNER`  
**Python (this host):** `py -3.11`  
**Active feature:** Voice_Bot

## Verdict

| Lane | Verdict |
|------|---------|
| read-only typed preview | READY |
| full-agent production | NOT READY |
| **G7 Moshi harness (T055)** | **pass** — recorded 2026-11-14 (`moshi-probe --record`; do not redo unless user asks) |
| **G7-q8 q8 + quantize on server** | **partial** — runbook in repo; **q8 on pod verified**; **live load + utterances not done** |
| **T056 Moshi wiring + duplex** | **done** |

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
| Proxy Moshi URL (pattern) | `wss://t13xqwp4ilb953-8998.proxy.runpod.net/api/chat` — only after stack listens on 8998 |
| SSH direct | `ssh root@216.81.245.29 -p 38211` — **refused from operator host in session 8**; use **`exec-pod`** or SSH proxy `ssh t13xqwp4ilb953-64410a71@ssh.runpod.io` |
| Pod `runpodctl` | `/usr/bin/runpodctl` **1.14.15** (works for `receive` on pod) |

**Terminate or stop when user says billing should stop** — not automatic after tests.

**Old pod:** `yfhzy2r86j9akc` remains **gone** (404).

## On-pod assets (session 8 verified)

| Path | Size / note |
|------|-------------|
| `/workspace/q8/model.q8.safetensors` | 12,237,164,792 bytes |
| `/workspace/q8/config.json` | 2,069 bytes |
| `/workspace/q8/sha.txt` | SHA256 **match** (see below) |

**Expected weights SHA256:** `0142f1c7df455c50e882cee8210ae3ccc28fecf1310762a6d7c3a693e89a0ddc`

**Re-verify (read-only):**

```text
exec-pod: ls -l /workspace/q8/ && cat /workspace/q8/sha.txt
```

**Not on pod yet:** `/tmp/vllm-venv`, `/tmp/vllm2`, `/workspace/moshi-rag-src/moshi`, warm HF cache, running encoder/vLLM/moshi, quantize patch on installed `quantize.py`. Optional **`llama-3.2-tokenizer/`** still only on host (`POD_BACKUPS\irfh4yaasw-q8\`).

## Session 8 completed

1. **q8 upload** — local `runpodctl send` + pod `runpodctl receive` via **`exec-pod`** (operator SSH direct was refused; relay works).
2. **SHA256** on pod matches handoff; `config.json` present.
3. Transfer logs on pod: `/workspace/q8/recv_weights.log`, `/workspace/q8/recv_cfg.log` (safe to ignore after success).

## Transfer recipe (repeat if pod recreated)

| Step | Where |
|------|--------|
| `runpodctl send <local-path>` | Operator host — capture first stdout line (one-time code) |
| `mkdir -p /workspace/q8 && nohup runpodctl receive <code> > /workspace/q8/recv.log 2>&1 &` | Pod via `exec-pod` |
| Large file ~3 min @ ~60 MB/s for 12 GB | Poll `tail` on recv log; then `sha256sum` in background if hash exceeds exec timeout |

Local backup: `D:\DRIVE_DOWNLOADS\POD_BACKUPS\irfh4yaasw-q8\`

## Fresh-pod stack (next chat)

Follow **`docs/specs/Voice_Bot/cursor-g7-runpod-handoff.md`** launch recipes on **`t13xqwp4ilb953`** (do not recreate pod if still RUNNING):

1. Bootstrap venv, moshi-rag clone/install, vLLM env as in handoff.
2. Apply quantize patch from **`docs/specs/Voice_Bot/pod-artifacts/G7-q8-quantize-patch.md`** on pod `quantize.py` (documented patch only).
3. Start encoder **:8011**, vLLM **:8002**, `moshi.server` **:8998** (`--host 0.0.0.0`, q8 paths under `/workspace/q8/`).
4. Warm or tolerate ~65 s first handshake; cold STT needs >3 s probe timeout (`cursor-g7-runpod-handoff.md`).
5. **G7-q8 success:** q8 loads with patch only; optional `moshi-probe` **without** `--record`.
6. **T056 live:** `py -3.11 -m hive_planner voice-bot moshi-talk --url wss://t13xqwp4ilb953-8998.proxy.runpod.net/api/chat --duration N` — **`utterances > 0`** when user speaks.

## Do not redo

- G7 `moshi-probe --record` (T055 pass unless user asks).
- T056 code audit unless new gap.
- Re-upload q8 if `/workspace/q8/sha.txt` still matches (unless pod wiped).
- Assume `yfhzy2r86j9akc` proxy URL.
- Wrong proxy host pattern (use **`-8998`** suffix form above).
- Recreate pod if `t13xqwp4ilb953` still RUNNING (unless user requests replace).

## Open micro-tasks (priority)

1. **G7-q8 live (this pod):** bootstrap stack → quantize patch → prove q8 load → `moshi-talk` utterances (optional panel duplex).
2. **Evidence:** on pass, update `evidence-register.md` / `deployment-gaps.md` (q8 partial → pass with criteria).
3. **Tokenizer on pod** only if bootstrap recipes fail without local tokenizer path.
4. **T042 Speech S1** or **ML-T5** only if user pivots off pod work.

## Local artifacts

| Asset | Path |
|-------|------|
| q8 backup dir | `D:\DRIVE_DOWNLOADS\POD_BACKUPS\irfh4yaasw-q8\` |
| Quantize runbook | `docs/specs/Voice_Bot/pod-artifacts/G7-q8-quantize-patch.md` |
| Stack recipes | `docs/specs/Voice_Bot/cursor-g7-runpod-handoff.md` |
| Prior handoff | `docs/specs/Voice_Bot/cursor-handoff-2026-11-14-session7.md` |

## Files touched session 8

- `docs/specs/Voice_Bot/cursor-handoff-2026-11-14-session8.md` (this file)

## Paste into new chat

```
Voice_Bot next micro-task (session 8 handoff — G7-q8 stack bootstrap)

Handoff: docs/specs/Voice_Bot/cursor-handoff-2026-11-14-session8.md
Repo: D:\DRIVE_DOWNLOADS\HIVE_CODE_PLANNER | Python: py -3.11

Verdict: read-only=READY full-agent=NOT READY | G7=pass | T055/T056=done | G7-q8=partial (q8 on pod yes, stack/live no)

Active pod: t13xqwp4ilb953 RUNNING ~$3.19/hr — billing ON until terminate/stop
Proxy (when up): wss://t13xqwp4ilb953-8998.proxy.runpod.net/api/chat

Done session 8:
- q8 + config on /workspace/q8/; SHA256 verified (0142f1c7…a0ddc)
- Upload via runpodctl send/receive + exec-pod (not operator SSH)

Do not redo: G7 --record; re-upload q8 if sha still valid; old pod yfhzy2r86j9akc; T056 unless new gap

Open next (one micro-task): bootstrap venv/moshi-rag per cursor-g7-runpod-handoff → apply G7-q8-quantize-patch → start :8011/:8002/:8998 → moshi-talk utterances

Blocked: none (q8 upload cleared)

First action: get-pod t13xqwp4ilb953; exec-pod ls -l /workspace/q8 && cat sha.txt; load cursor-g7-runpod-handoff and begin bootstrap on pod
```