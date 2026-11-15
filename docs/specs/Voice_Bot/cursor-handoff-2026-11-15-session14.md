# Voice_Bot — handoff after ARC xformers SDPA shim (2026-11-15, session 14)

**Purpose:** Continue **Voice_Bot** with **A2 partly closed**: the ARC reference-encoder path now runs on Windows through a spike-only SDPA shim, using random weights. Real ARC weights and the moshi.server path are still open.

**Supersedes:** `docs/specs/Voice_Bot/cursor-handoff-2026-11-15-session13.md` for the **A2 / xformers** status only. Session 13 facts for local q8 forward, Windows compile env, and verdict table still hold.

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
| **ARC encode shape / mask path (A2, random weights)** | **pass (session 14)** — SDPA shim, full-size `forward_embedder` on cuda:1 |
| **ARC encode with real weights** | **open** — `load_weights()` not run locally |
| T056 live Moshi talk | open (no account pods; local server not wired) |
| T056 STT clips (pinned Whisper) | partial — rows through -4; no WER |
| T042 slice 5e | docs closed in `tasks.md` |
| Moshi replaces Whisper (refactor) | blocked — needs spec/Delta first (R36/R10/R37); no VoiceBot code changed |

## Done session 14 (this chat)

1. **Read the ARC call sites** in `D:\DRIVE_DOWNLOADS\moshi-rag-src\moshi\moshi\conditioners\arc_encoder.py`:
   - `memory_efficient_attention` at line 153 (`Attention.forward`).
   - `BlockDiagonalMask.from_seqlens` / `BlockDiagonalCausalMask.from_seqlens` at lines 320–360 (`ArcEncoderTransformer.forward_embedder`).
   - The old spike stub set `memory_efficient_attention = None` and had no `from_seqlens`, so the path failed with `AttributeError` before its own ImportError guard.
2. **Replaced the stub with an SDPA shim (spike only, outside repo):**
   - `D:\DRIVE_DOWNLOADS\moshi-q8-spike\stubs\xformers\ops\fmha\attn_bias.py` — dense bool block-diagonal masks; causal variant uses top-left alignment.
   - `D:\DRIVE_DOWNLOADS\moshi-q8-spike\stubs\xformers\ops\fmha\__init__.py` — `memory_efficient_attention` on `[B, L, H, D]` via `F.scaled_dot_product_attention`; returns `.contiguous()` because ARC calls `.view()` on the output.
3. **Smoke test:** `D:\DRIVE_DOWNLOADS\moshi-q8-spike\arc_sdpa_smoke.py`, log `arc_sdpa_smoke.log`.
   - Shim vs naive per-block reference, non-causal and causal: max abs err 3.6e-7.
   - `ArcEncoderTransformer(compression_rate=-4)` bf16 on cuda:1, random weights, 40 input tokens → `(10, 3072)`, finite, peak 5.73 GiB, 0.50 s.

## Gotchas found this session

- **PYTHONPATH must be absolute.** A relative `moshi-rag-src\moshi` resolved inside the spike folder and gave `No module named moshi.conditioners.arc_encoder`. Use:
  `D:\DRIVE_DOWNLOADS\moshi-q8-spike\stubs;D:\DRIVE_DOWNLOADS\moshi-rag-src\moshi`
- **Shim output must be contiguous** (see step 2) or ARC `.view()` raises a RuntimeError.

## RunPod (re-read every chat)

| Field | Value |
|-------|-------|
| Account pods | none seen this session (re-verify with `list-pods`) |
| Former pod | `t13xqwp4ilb953` — TERMINATED |

## Local assets (this host)

| Asset | Path |
|-------|------|
| 2× Tesla T10 16 GB | cuda:0 (LM), cuda:1 (condition provider / ARC) |
| q8 weights | `POD_BACKUPS\irfh4yaasw-q8` |
| q8 spike | `D:\DRIVE_DOWNLOADS\moshi-q8-spike` (`load_q8.py`, `forward_q8.py`, `diag_q8.py`, `arc_sdpa_smoke.py`) |
| moshi-rag source | `D:\DRIVE_DOWNLOADS\moshi-rag-src` |
| xformers shim | `D:\DRIVE_DOWNLOADS\moshi-q8-spike\stubs\xformers` |
| **Required env (spike)** | `NO_TORCH_COMPILE=1`, `NO_CUDA_GRAPH=1`, `PYTHONPATH=D:\DRIVE_DOWNLOADS\moshi-q8-spike\stubs;D:\DRIVE_DOWNLOADS\moshi-rag-src\moshi` |

## Do not redo

- Session 13 A1 forward smoke (`forward_run2.log` is the reference).
- Session 14 shim unit check and random-weight ARC smoke, unless `attn_bias.py` or `fmha/__init__.py` change.
- Re-clone `moshi-rag-src` only if the folder is missing or corrupt.

## Open micro-tasks (pick one per chat)

### A. Local inference spike (no repo)

1. ~~One forward on cuda:0~~ **done (session 13).**
2. ~~ARC encode shape / mask path with shim~~ **done (session 14, random weights).**
2b. **ARC with real weights:** check the ARC checkpoint is in the HF cache (`ArcEncoderConditioner.hf_repo` → `model.safetensors`), run `load_weights()` on cuda:1 in bf16, then one `forward_embedder` on a real reference text. Check output is finite and the value range is plausible. Log to `arc_real_weights.log`.
3. Minimal **`moshi.server`** on loopback with q8 paths + `G7-q8-quantize-patch.md` + dual-GPU + `NO_TORCH_COMPILE` launch notes; then `voice-bot moshi-probe` without `--record` first.

### B. Spec before Moshi-primary STT refactor

1. Delta + `spec.md`: Moshi as primary STT vs R36/R10 (WER gate, evidence rows).
2. Plan: R37 in-process vs local server; whether Hive `moshi_autostart` loads q8 from config paths on Windows.

### C. VoiceBot product (after A or B)

1. Spoken-path slice 5e watcher (`/v1/submit/spoken`, Moshi utterance).
2. Live Moshi talk on RunPod or local server once probe passes.
3. Optional: Windows combined pytest loopback_echo crash bisect.

### D. Live Moshi on RunPod (billing)

New pod + stack from backups (parallel if local stalls).

## Validation (session 14)

| Check | Result |
|-------|--------|
| `arc_sdpa_smoke.py` shim check | exit 0, max abs err 3.6e-7 (both masks) |
| `arc_sdpa_smoke.py` ARC forward, random weights, cuda:1 | exit 0, `(10, 3072)`, finite |
| Repo pytest | not run (spike-only; no `src/` change) |

## Wiring audit (session 14)

- **Repo:** documentation only (this file). No `src/` behavior change.
- **Chain traced:** `ArcEncoderConditioner._get_condition` → `ArcEncoderTransformer.forward_embedder` → `TransformerBlock` → `Attention.forward` → `memory_efficient_attention` (shim) → SDPA. Mask chain: `BlockDiagonalMask.from_seqlens` → `materialize`.
- **Not traced:** `ArcEncoderConditioner.load_weights` with real weights; `loaders.get_moshi_lm`; Hive `voice_panel`, bridge, `moshi_autostart`, `voice-bot moshi-probe`.
- **Gap:** the smoke test uses random weights, so it shows shape and finiteness only, not embedding quality.

## Files touched session 14

- Repo: `docs/specs/Voice_Bot/cursor-handoff-2026-11-15-session14.md` (this file).
- Outside repo: `stubs\xformers\ops\fmha\attn_bias.py`, `stubs\xformers\ops\fmha\__init__.py`, `arc_sdpa_smoke.py`, `arc_sdpa_smoke.log`.

## Paste into new chat

```
Voice_Bot next micro-task (session 14 handoff — ARC real weights or moshi.server)

Handoff: docs/specs/Voice_Bot/cursor-handoff-2026-11-15-session14.md
Repo: D:\DRIVE_DOWNLOADS\HIVE_CODE_PLANNER | Python: py -3.11

Verdict: read-only=READY full-agent=NOT READY | G7 T055=pass | G7-q8=pass | local q8 forward=pass (A1) | ARC shim + random-weight encode=pass (A2) | ARC real weights=open | T056 live=open | T042 5e=docs done | Moshi-as-STT refactor=spec-blocked

Pod: none (re-verify list-pods)
Local: 2× T10 16GB | q8 POD_BACKUPS\irfh4yaasw-q8 | spike D:\DRIVE_DOWNLOADS\moshi-q8-spike | moshi-rag-src D:\DRIVE_DOWNLOADS\moshi-rag-src
Spike env: NO_TORCH_COMPILE=1 NO_CUDA_GRAPH=1 PYTHONPATH=D:\DRIVE_DOWNLOADS\moshi-q8-spike\stubs;D:\DRIVE_DOWNLOADS\moshi-rag-src\moshi (absolute paths)

Done session 14: xformers SDPA shim in stubs; arc_sdpa_smoke.py exit 0 (shim err 3.6e-7; ARC forward (10,3072) finite on cuda:1, random weights)

Do not redo: A1 forward smoke; A2 shim/random-weight smoke (unless shim files change)

Open next (one): A2b) ARC load_weights real checkpoint + one forward, A3) loopback moshi.server + probe, B) Moshi-primary STT spec, C) 5e spoken path, D) RunPod pod

First action: read handoff § A2b; confirm ARC checkpoint in HF cache; run load_weights on cuda:1 with arc_sdpa_smoke-style script
```
