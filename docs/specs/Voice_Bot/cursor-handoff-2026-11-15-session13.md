# Voice_Bot — handoff after local q8 forward pass (2026-11-15, session 13)

**Purpose:** Continue **Voice_Bot** with **A1 closed**: one **training-style forward** on the locally loaded **Moshi-RAG q8** LM on **cuda:0** (no repo Moshi refactor, no `moshi.server`, no ARC encode).

**Supersedes:** `docs/specs/Voice_Bot/cursor-handoff-2026-11-15-session12.md` for **local q8 inference feasibility (forward), Windows torch.compile/Triton workaround, and spike script inventory** only. Session 12 load spike, q8 identity, `tasks.md` slice 5e, and operator intent remain authoritative where not updated here.

**Repo:** `D:\DRIVE_DOWNLOADS\HIVE_CODE_PLANNER`  
**Python (this host):** `py -3.11`  
**Active feature:** Voice_Bot

## Verdict

| Lane | Verdict |
|------|---------|
| read-only typed preview | READY |
| full-agent production | NOT READY |
| **G7 Moshi harness (T055)** | **pass** (recorded; old pod URL) |
| **G7-q8** | **pass (caveated)** — q8 file **confirmed Moshi-RAG** (unchanged from session 12) |
| **Local q8 LM load + forward (this PC)** | **partial** — dual-GPU load **+ one `forward(codes)` on cuda:0**; **no OOM** on ~8 GB headroom; **no server, no audio, no ARC encode** |
| **T056 live Moshi talk** | **open** (no account pods; local server not wired) |
| **T056 STT clips (pinned Whisper)** | **partial** — rows through **-4**; no WER |
| **T042 slice 5e** | **docs closed** in `tasks.md` (unchanged) |
| **Moshi replaces Whisper (refactor)** | **blocked** — needs **spec/Delta** first (R36/R10/R37); **no VoiceBot code changed** this session |

## Operator direction (carry forward)

Unchanged from session 12: quantize targets **local Windows** Moshi-RAG; long-term **Moshi-primary** intent; **spec today** = Moshi **conversation** via **R37 websocket** to `moshi.server`; **faster-whisper** STT fallback until G3/WER. Spike work stays **outside repo** until spec allows in-process or server wiring.

## Done session 13 (this chat)

1. **Micro-task A1 — one forward on cuda:0:** `D:\DRIVE_DOWNLOADS\moshi-q8-spike\forward_q8.py` imports `load_q8` (module-level load), runs `model(codes)` with shape `[1, 17, 4]` (text stream + 16 audio codebooks), `torch.no_grad()`.
2. **Windows compile fix (required for forward):** without env vars, Moshi `torch.compile` → **Inductor/Triton missing** on Windows (`BackendCompilerFailed`). **Fix:** `NO_TORCH_COMPILE=1` and `NO_CUDA_GRAPH=1` (supported in `moshi-rag-src/.../utils/compile.py` via `NO_TORCH_COMPILE`).
3. **Forward evidence (`forward_run2.log`):** load ~187 s CPU build; VRAM **cuda:0 8.02 GB** (peak 8.02), **cuda:1 12.13 GB** (peak 12.17); **`forward(codes) ok in 1.52 s`**; logits `(1, 8, 4, 2048)` **float16**; **exit 0**.
4. **NaN logits — not a numerical fault:** `diag_q8.py` + hooks: **no non-finite activations** in hooked modules; **14 336 NaNs** = **7 × 2048** invalid positions after `_undelay_sequence` padding for **delay-1** audio codebooks (`lm.py` train forward fills invalid slots with NaN by design). Finite slice min/max ≈ **-3.74 / 9.43**.
5. **Failed first attempt retained:** `forward_run.log` (no `NO_TORCH_COMPILE`) documents Triton failure for future operators.

## RunPod (re-read every chat)

| Field | Value |
|-------|-------|
| Account pods | **none** (re-verify with `list-pods`) |
| Former pod | **`t13xqwp4ilb953`** — **TERMINATED** |
| New live Moshi | **new pod** per `cursor-g7-runpod-handoff.md` **or** local server after A3 |

## Local assets (this host)

Unchanged from session 12, plus spike additions:

| Asset | Path |
|-------|------|
| q8 load spike | `D:\DRIVE_DOWNLOADS\moshi-q8-spike\load_q8.py`, `config.local.json`, `stubs\xformers\` |
| Forward / diag | `forward_q8.py`, `diag_q8.py` |
| Logs | `forward_run2.log` (pass), `forward_run.log` (compile fail), `diag_run.log` |
| **Required env (forward/server spike)** | `NO_TORCH_COMPILE=1`, `NO_CUDA_GRAPH=1`; `PYTHONPATH` = `stubs;moshi-rag-src\moshi` |

## Local q8 spike — known blockers

| Blocker | Notes |
|---------|--------|
| **torch.compile / Triton** | Default forward **fails on Windows**; set **`NO_TORCH_COMPILE=1`** (and **`NO_CUDA_GRAPH=1`**) for eager path. |
| **xformers** | **Stub only** → RAG **`multi_arc_encoder`** / `memory_efficient_attention` **still blocked** for A2. |
| **VRAM split** | Still **cuda:0 LM + cuda:1 condition_provider**; forward did not increase cuda:0 peak beyond load. |
| **Full duplex stack** | `moshi.server`, Mimi, encoder/vLLM ports — **not local** (A3). |

## Do not redo

- **Session 12:** q8 SHA, 5e `tasks.md` bullet, load-only `load_q8.py` smoke unless weights/paths change.
- **Session 13:** full **A1 forward smoke** unless regressing load/compile env; re-use **`forward_run2.log`** facts.
- Re-clone **moshi-rag-src** if intact; re-download **ARC** if `hf_home` cache present.

## Open micro-tasks (priority — pick one per chat)

### A. Local inference spike (no repo)

1. ~~One forward / generate on cuda:0~~ **done (session 13).**
2. **Real xformers on Windows** (WSL2/CUDA build, SDPA fallback in ARC, or documented shim) → smoke **ARC encode** on **cuda:1**.
3. Minimal **`moshi.server`** on loopback with q8 paths + **`G7-q8-quantize-patch.md`** + dual-GPU + **`NO_TORCH_COMPILE`** launch notes; then `voice-bot moshi-probe` **without** `--record` first.

### B. Spec before Moshi-primary STT refactor

1. Delta + **`spec.md`**: Moshi as **primary STT** vs R36/R10 (WER gate, evidence rows).
2. Plan: **R37 in-process vs local server**; whether Hive **`moshi_autostart`** loads q8 from config paths on Windows.

### C. VoiceBot product (after A or B)

1. Spoken-path **slice 5e** watcher (`/v1/submit/spoken`, Moshi utterance).
2. **Live Moshi talk** on RunPod **or** local server once probe passes.
3. Optional: Windows combined pytest **loopback_echo** crash bisect.

### D. Live Moshi on RunPod (billing)

New pod + stack from backups (parallel if local stalls on xformers).

## Validation (session 13)

| Check | Result |
|-------|--------|
| Spike `forward_q8.py` with `NO_TORCH_COMPILE=1` | **exit 0**; forward **1.52 s**; VRAM cuda:0 **8.02 GB** peak |
| Spike `diag_q8.py` | **exit 0**; NaNs explained by delay-mask padding, hooked modules **all finite** |
| Repo pytest | **not run** (spike-only session; no `src/` change) |

## Wiring audit (session 13)

- **Repo:** documentation only (`cursor-handoff-2026-11-15-session13.md`); no `src/` behavior change.
- **Spike chain:** `stream_load` → `CheckpointInfo` → `get_moshi` → per-child `.to(cuda:0|1)` → `LMModel.forward(codes)` with compile disabled. Not integrated with Hive `voice_panel`, bridge, `moshi_autostart`, or `voice-bot moshi-probe`.

## Files touched session 13 (repo)

- `docs/specs/Voice_Bot/cursor-handoff-2026-11-15-session13.md` (this file)

## Files touched session 13 (outside repo)

- `D:\DRIVE_DOWNLOADS\moshi-q8-spike\forward_q8.py`
- `D:\DRIVE_DOWNLOADS\moshi-q8-spike\diag_q8.py`
- `D:\DRIVE_DOWNLOADS\moshi-q8-spike\forward_run.log`, `forward_run2.log`, `diag_run.log`

## Paste into new chat

```
Voice_Bot next micro-task (session 13 handoff — ARC/xformers or moshi.server)

Handoff: docs/specs/Voice_Bot/cursor-handoff-2026-11-15-session13.md
Repo: D:\DRIVE_DOWNLOADS\HIVE_CODE_PLANNER | Python: py -3.11

Verdict: read-only=READY full-agent=NOT READY | G7 T055=pass | G7-q8=pass | T056 live=open | T042 5e=docs done | local q8 forward=pass (A1) | ARC encode=blocked (xformers stub) | Moshi-as-STT refactor=spec-blocked

Pod: none (re-verify list-pods)
Local: 2× T10 16GB | q8 POD_BACKUPS\irfh4yaasw-q8 | spike D:\DRIVE_DOWNLOADS\moshi-q8-spike | moshi-rag-src D:\DRIVE_DOWNLOADS\moshi-rag-src
Spike env: NO_TORCH_COMPILE=1 NO_CUDA_GRAPH=1 PYTHONPATH=stubs;moshi-rag-src\moshi

Done session 13: one forward(codes) cuda:0 ~1.5s no OOM; NaNs=expected delay padding; forward_q8.py + diag_q8.py

Do not redo: A1 forward smoke; session 12 q8 SHA/5e bullet; STT clips 1–4

Open next (one): A2) ARC encode / xformers Windows, A3) loopback moshi.server + probe, B) Moshi-primary STT spec, C) 5e spoken path, D) RunPod pod

First action: read handoff § A2; grep ARC memory_efficient_attention call sites and try SDPA or WSL xformers path
```