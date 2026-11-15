# Voice_Bot — handoff after slice 5e docs, Moshi-RAG q8 confirm, local load spike (2026-11-15, session 12)

**Purpose:** Continue **Voice_Bot** with **T042 slice 5e closed in `tasks.md`**, confirmed **Moshi-RAG q8** identity, and a **local dual-GPU load spike** (no repo Moshi refactor, no inference yet).

**Supersedes:** `docs/specs/Voice_Bot/cursor-handoff-2026-11-14-session11.md` for **`tasks.md` slice 5e status, local q8 feasibility, and operator intent (Moshi-primary on this host)** only. Session 11 STT clips, pod terminate, and 5e code remain authoritative where not updated here.

**Repo:** `D:\DRIVE_DOWNLOADS\HIVE_CODE_PLANNER`  
**Python (this host):** `py -3.11`  
**Active feature:** Voice_Bot

## Verdict

| Lane | Verdict |
|------|---------|
| read-only typed preview | READY |
| full-agent production | NOT READY |
| **G7 Moshi harness (T055)** | **pass** (recorded; old pod URL) |
| **G7-q8** | **pass (caveated)** — q8 file **confirmed Moshi-RAG** on this host (header + config; SHA256 unchanged) |
| **Local q8 LM load (this PC)** | **partial** — build + weights on **2× T10 16 GB** with spike workarounds; **no forward pass, no server, no audio** |
| **T056 live Moshi talk** | **open** (no account pods; local server not wired) |
| **T056 STT clips (pinned Whisper)** | **partial** — rows through **-4**; no WER |
| **T042 slice 5e** | **docs closed** in `tasks.md`; code unchanged from session 11 |
| **Moshi replaces Whisper (refactor)** | **blocked** — needs **spec/Delta** first (R36/R10/R37); **no VoiceBot code changed** this session |

## Operator direction (carry forward)

Quantize was for **running Moshi-RAG on this local Windows host**, not only RunPod. User asked to **refactor VoiceBot around Moshi (q8) instead of Whisper** once local path works. **Spec today:** Moshi is primary **conversation** layer; **faster-whisper** is the pinned **STT fallback** until G3/WER; R37 = **websocket to `moshi.server`**, not in-process model. Any Moshi-as-STT or in-process load change is a **behavioral spec task** before `src/` edits.

## Done session 12 (this chat)

1. **`tasks.md`:** added **T042 slice 5e** status bullet (wiring, 15-pass test note, env skip on Tk line 232, spoken-path gap). Parent **T042** still open.
2. **q8 identity:** `POD_BACKUPS\irfh4yaasw-q8\` — `model.q8.safetensors` **12,237,164,792 B**, SHA256 **`0142f1c7…a0ddc`**; `config.json` has **`multi_arc_encoder`**, **`rag_token_id`**, **`quantize": true`**; source repo **`kyutai/moshika-rag-pytorch-bf16`** (bf16 sibling **`D:\DRIVE_DOWNLOADS\MOSHI_RAG_WEIGHTS\moshika-rag-pytorch-bf16\`** ~15.4 GB).
3. **Local spike (outside repo):** `D:\DRIVE_DOWNLOADS\moshi-q8-spike\load_q8.py` — streaming safetensors read (avoids mmap crash / paging 1455); **`bitsandbytes` 0.50.2** installed on host Python; clone **`D:\DRIVE_DOWNLOADS\moshi-rag-src`** (upstream `kyutai-labs/moshi-rag`) with pod/repo **`quantize.py`** + session 9 **`arc_encoder.py`**; stub **`xformers`** (no Windows wheel); ARC tokenizer path in **`config.local.json`** → `MOSHI_RAG_HF\llama-3.2-tokenizer`; ARC encoder weights cached under **`MOSHI_RAG_WEIGHTS\hf_home`**. **Success:** LM built on CPU, placed **LM blocks → cuda:0 (~8.0 GB)**, **`condition_provider` → cuda:1 (~12.1 GB)**; **~4 min** load; **exit 0**. **Not run:** forward step, `moshi.server`, Mimi, RAG encode (stub blocks `memory_efficient_attention`).

## RunPod (re-read every chat)

| Field | Value |
|-------|-------|
| Account pods | **none** (unchanged from session 11; re-verify with `list-pods`) |
| Former pod | **`t13xqwp4ilb953`** — **TERMINATED** |
| New live Moshi | **new pod** per `cursor-g7-runpod-handoff.md` **or** pursue **local server** path below |

## Local assets (this host)

| Asset | Path |
|-------|------|
| q8 weights + config | `D:\DRIVE_DOWNLOADS\POD_BACKUPS\irfh4yaasw-q8\` |
| bf16 Moshi-RAG checkpoint | `D:\DRIVE_DOWNLOADS\MOSHI_RAG_WEIGHTS\moshika-rag-pytorch-bf16\` |
| ARC / HF cache | `D:\DRIVE_DOWNLOADS\MOSHI_RAG_WEIGHTS\hf_home\` |
| Llama tokenizer (ARC) | `D:\DRIVE_DOWNLOADS\MOSHI_RAG_HF\llama-3.2-tokenizer\` |
| Moshi-RAG source (clone) | `D:\DRIVE_DOWNLOADS\moshi-rag-src\` |
| Load spike script | `D:\DRIVE_DOWNLOADS\moshi-q8-spike\` (`load_q8.py`, `config.local.json`, `stubs\xformers\`) |
| GPUs | **2× NVIDIA Tesla T10**, **16 GB** each |
| Installed PyPI (host, not repo) | **`bitsandbytes` 0.50.2**; `moshi` 0.2.12 pip package **lacks RAG** — use **moshi-rag-src** on `PYTHONPATH` |

## Local q8 spike — known blockers

| Blocker | Notes |
|---------|--------|
| **VRAM split** | q8 LM + ARC **do not fit one 16 GB card**; spike uses **cuda:0 + cuda:1**. |
| **xformers** | **No Windows build** tried; spike uses **stub** → RAG reference encode **will fail** until real xformers or alternate attention path. |
| **Full duplex stack** | Pod recipe still needs **encoder :8011**, **vLLM :8002**, **Moshi :8998**, **quantize patch** — not replicated locally yet. |
| **Paging / mmap** | Default `safetensors.load_file` → **1455** or **access violation** on 12 GB file; spike **streaming loader** required. |

## Do not redo

- **`tasks.md` slice 5e bullet** unless facts change.
- **q8 SHA256 verify** unless file replaced.
- **Re-clone moshi-rag-src** if `D:\DRIVE_DOWNLOADS\moshi-rag-src` intact.
- **Re-download ARC encoder** if `hf_home` cache already has `kyutai/ARC4_Encoder_Llama`.
- Session 11 items: STT clips **-4**, dead pod URLs, 5e core code.

## Open micro-tasks (priority — pick one per chat)

### A. Local inference spike (no repo)

1. One **forward / generate** step on loaded q8 LM (**cuda:0**) after load script — confirm no OOM on 8 GB headroom.
2. **Real xformers on Windows** (WSL2/CUDA build, or documented fallback) → smoke **ARC encode** on **cuda:1**.
3. Minimal **`moshi.server`** on loopback with q8 paths + **`G7-q8-quantize-patch.md`** + dual-GPU launch notes; then `voice-bot moshi-probe` **without** `--record` first.

### B. Spec before Moshi-primary STT refactor

1. Delta + **`spec.md`**: Moshi as **primary STT** vs R36/R10 (WER gate, evidence rows).
2. Plan: **R37 in-process vs local server**; whether Hive **`moshi_autostart`** loads q8 from config paths on Windows.

### C. VoiceBot product (after A or B)

1. Spoken-path **slice 5e** watcher (`/v1/submit/spoken`, Moshi utterance).
2. **Live Moshi talk** on RunPod **or** local server once probe passes.
3. Optional: Windows combined pytest **loopback_echo** crash bisect.

### D. Live Moshi on RunPod (billing)

New pod + stack from backups (parallel track if local stalls on xformers).

## Validation (session 12)

| Check | Result |
|-------|--------|
| `py -3.11 -m pytest tests/test_voice_panel_task_watch.py -q` | **15 passed** (also **14+1 skip** env-dependent) |
| `py -3.11 -m hive_planner spec-drift-check --feature Voice_Bot` | **ok** (after `tasks.md` edit) |
| Local spike `load_q8.py cuda:0` | **exit 0**; VRAM **cuda:0 ~8.02 GB**, **cuda:1 ~12.13 GB** (spike logs `run6.log` under `moshi-q8-spike`) |

## Wiring audit (session 12)

- **Repo:** documentation-only change (`tasks.md` slice 5e); no `src/` behavior change.
- **Spike:** load chain traced: streaming `load_file` → `CheckpointInfo.from_hf_repo` (local q8 + bf16 mimi/tokenizer paths) → `get_moshi` on CPU → per-child `.to(cuda:0|cuda:1)`. Not integrated with Hive `voice_panel`, bridge, or `moshi_autostart`.

## Files touched session 12 (repo)

- `docs/specs/Voice_Bot/tasks.md` (slice **5e** status bullet)
- `docs/specs/Voice_Bot/cursor-handoff-2026-11-15-session12.md` (this file)

## Files touched session 12 (outside repo)

- Host pip: **`bitsandbytes`**
- `D:\DRIVE_DOWNLOADS\moshi-rag-src\` (clone + patched `quantize.py`, `arc_encoder.py`)
- `D:\DRIVE_DOWNLOADS\moshi-q8-spike\` (loader, config, stubs, logs)

## Paste into new chat

```
Voice_Bot next micro-task (session 12 handoff — local q8 forward or spec)

Handoff: docs/specs/Voice_Bot/cursor-handoff-2026-11-15-session12.md
Repo: D:\DRIVE_DOWNLOADS\HIVE_CODE_PLANNER | Python: py -3.11

Verdict: read-only=READY full-agent=NOT READY | G7 T055=pass | G7-q8=pass+q8 confirmed Moshi-RAG | T056 live=open | T042 slice 5e=docs done | local q8 load=partial (no infer) | Moshi-as-STT refactor=spec-blocked

Pod: none (re-verify list-pods)
Local: 2× T10 16GB | q8 POD_BACKUPS\irfh4yaasw-q8 | spike D:\DRIVE_DOWNLOADS\moshi-q8-spike | moshi-rag-src D:\DRIVE_DOWNLOADS\moshi-rag-src

Done session 12: tasks.md 5e bullet; q8=RAG proof; dual-GPU load spike exit 0 (~8GB+~12GB VRAM); bitsandbytes on host

Do not redo: 5e tasks bullet; q8 SHA; STT clips 1–4; dead pod

Open next (one): A) forward pass + xformers/server local, B) spec Moshi-primary STT, C) 5e spoken path / live talk after probe, D) new RunPod pod

First action: read handoff § Open micro-tasks; for A run load_q8.py then one LM forward on cuda:0
```