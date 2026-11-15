# Voice_Bot — handoff after G7-q8 doc + re-prove pod (2026-11-14, session 7)

**Purpose:** Continue **G7-q8 live re-prove** on pod **`t13xqwp4ilb953`** (RUNNING, billable). G7-q8 **runbook** is in the repo; stack and q8 weights are **not** on the pod yet.

**Supersedes:** `docs/specs/Voice_Bot/cursor-handoff-2026-11-14-session6.md` for pod state and G7-q8 open item 1 (doc done).

**Repo:** `D:\DRIVE_DOWNLOADS\HIVE_CODE_PLANNER`  
**Python (this host):** `py -3.11`  
**Active feature:** Voice_Bot

## Verdict

| Lane | Verdict |
|------|---------|
| read-only typed preview | READY |
| full-agent production | NOT READY |
| **G7 Moshi harness (T055)** | **pass** — recorded 2026-11-14 (`moshi-probe --record`; do not redo unless user asks) |
| **G7-q8 q8 + quantize on server** | **partial** — tracked runbook `pod-artifacts/G7-q8-quantize-patch.md`; live proof **open** on new pod |
| **T056 Moshi wiring + duplex** | **done** |

## Active pod (billable)

| Field | Value |
|-------|-------|
| Pod id | **`t13xqwp4ilb953`** |
| Name | `g7-q8-reprove-voice-bot` |
| Status | **RUNNING** (read back via `get-pod` after create) |
| GPU | NVIDIA H100 NVL ×1, secure, **US-KS-2** |
| Catalog price | **$3.19/hr** (`list-gpu-types`; container **200 GB** disk bills separately) |
| Image | `runpod/pytorch:1.0.2-cu1281-torch280-ubuntu2404` |
| Host CUDA reported | 13.2 (`minCudaVersion` create was 12.8) |
| Ports | 8998, 8011, 8002 (http), 22 (tcp) |
| Proxy Moshi URL (pattern) | `wss://t13xqwp4ilb953-8998.proxy.runpod.net/api/chat` — verify after stack listens on 8998 |
| SSH proxy | `ssh t13xqwp4ilb953-64410a71@ssh.runpod.io` |

**Terminate or stop when user says billing should stop** — not automatic after tests.

**Old pod:** `yfhzy2r86j9akc` remains **gone** (404). Do not use its proxy URL.

## Session 7 completed

1. **G7-q8 doc:** `docs/specs/Voice_Bot/pod-artifacts/G7-q8-quantize-patch.md` — patch line, rationale, upstream caveat, idempotent `sed` apply (bash-tested on scratch file).
2. **User authorized** Runpod re-prove; **no pods** were running before create (`list-pods` empty).
3. **Created** pod `t13xqwp4ilb953`; **stopped before stack** — MCP cannot upload local files; q8 still on host disk only.

## Blocker (operator)

Upload q8 assets from **`D:\DRIVE_DOWNLOADS\POD_BACKUPS\irfh4yaasw-q8\`** to **`/workspace/q8/`** on the pod via **runpodctl** (or SSH + your transfer path). MCP `exec-pod` can verify SHA256 after upload; it cannot push the files.

| File (local) | Pod path | SHA256 (weights) |
|--------------|----------|-------------------|
| `model.q8.safetensors` | `/workspace/q8/model.q8.safetensors` | `0142f1c7df455c50e882cee8210ae3ccc28fecf1310762a6d7c3a693e89a0ddc` |
| `config.json` | `/workspace/q8/config.json` | (verify present) |

Optional: `llama-3.2-tokenizer/` under the same backup if encoder recipes need a local tokenizer path (see prior pod notes in `cursor-g7-runpod-handoff.md`).

## Fresh-pod warning

Unlike the terminated pod, **`t13xqwp4ilb953` is empty**: no `/tmp/vllm-venv`, `/tmp/vllm2`, `/workspace/moshi-rag-src/moshi`, warm HF cache, or `/workspace/q8`. Next chat must **bootstrap** (clone/install per `cursor-g7-runpod-handoff.md` launch recipes) **after** q8 upload, then:

1. Apply quantize patch from `G7-q8-quantize-patch.md` on pod `quantize.py` path.
2. Start encoder **:8011**, vLLM **:8002**, `moshi.server` **:8998** (`--host 0.0.0.0`, q8 paths).
3. Warm or tolerate ~65 s first handshake; probe timeout 3 s is too short for cold STT (`cursor-g7-runpod-handoff.md`).
4. **G7-q8 success criteria:** q8 loads with **documented patch only** (no ad-hoc mystery edits); optional `moshi-probe` **without** `--record`.
5. **T056 live utterances:** `py -3.11 -m hive_planner voice-bot moshi-talk --url wss://t13xqwp4ilb953-8998.proxy.runpod.net/api/chat --duration N` — expect **`utterances > 0`** when user speaks (session 6 CLI fix).

## Local artifacts

| Asset | Path |
|-------|------|
| q8 backup dir | `D:\DRIVE_DOWNLOADS\POD_BACKUPS\irfh4yaasw-q8\` |
| Quantize runbook | `docs/specs/Voice_Bot/pod-artifacts/G7-q8-quantize-patch.md` |
| Quantize snapshot | `docs/specs/Voice_Bot/pod-artifacts/quantize.py` |
| Stack recipes | `docs/specs/Voice_Bot/cursor-g7-runpod-handoff.md` |
| Tasks | `docs/specs/Voice_Bot/tasks.md` — T055/T056 done |

## Do not redo

- G7 `moshi-probe --record` (T055 pass unless user asks).
- T056 code audit unless new gap.
- Assume `yfhzy2r86j9akc` proxy URL.
- Wrong proxy host (**`60831`** suffix vs **`-8998`**).
- Recreate pod if `t13xqwp4ilb953` still RUNNING (use existing id unless user requests replace).

## Open micro-tasks (priority)

1. **G7-q8 live (this pod):** upload q8 → bootstrap stack → quantize patch from runbook → prove load + `moshi-talk` utterances (and optionally panel duplex).
2. **Evidence:** if G7-q8 passes, update `evidence-register.md` / `deployment-gaps.md` per spec (q8 partial → pass with criteria).
3. **T042 Speech S1** or **ML-T5** only if user pivots off pod work.

## Files touched session 7

- `docs/specs/Voice_Bot/pod-artifacts/G7-q8-quantize-patch.md` (new)
- `docs/specs/Voice_Bot/cursor-handoff-2026-11-14-session7.md` (this file)

## Paste into new chat

Copy as the **first user message** (adjust after upload/stack progress):

```
Voice_Bot next micro-task (session 7 handoff — G7-q8 live re-prove in progress)

Handoff: docs/specs/Voice_Bot/cursor-handoff-2026-11-14-session7.md
Repo: D:\DRIVE_DOWNLOADS\HIVE_CODE_PLANNER | Python: py -3.11

Verdict: read-only=READY full-agent=NOT READY | G7=pass | T055/T056=done | G7-q8=partial (runbook yes, live no)

Active pod: t13xqwp4ilb953 RUNNING ~$3.19/hr — billing ON until terminate/stop
Proxy (verify): wss://t13xqwp4ilb953-8998.proxy.runpod.net/api/chat

Done session 7:
- G7-q8-quantize-patch.md + sed apply tested
- Pod created; no stack, no q8 on pod yet

Do not redo: G7 --record; old pod yfhzy2r86j9akc; T056 unless new gap

Open next (one micro-task): <e.g. confirm q8 SHA on pod via exec-pod OR bootstrap venv/moshi-rag per cursor-g7-runpod-handoff OR start encoder/vllm/moshi after deps>

Blocked until: q8 upload to /workspace/q8/ via runpodctl (operator) — say "upload done" when ready

First action: get-pod t13xqwp4ilb953; if upload done, exec-pod ls -la /workspace/q8 && sha256sum model.q8.safetensors; else remind upload paths from handoff
```