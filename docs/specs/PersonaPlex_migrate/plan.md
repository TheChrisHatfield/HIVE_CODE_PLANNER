# Plan: PersonaPlex_migrate

**Spec:** [spec.md](./spec.md)  
**Tasks:** [tasks.md](./tasks.md)  
**Delta:** [PersonaPlex_migrate.md](../../delta/20_micro/PersonaPlex_migrate.md)

<!-- ROSETTA-NAV -->

## Agent navigation (Rosetta Stone)

Load [`docs/planning-rosetta-stone.md`](../../planning-rosetta-stone.md) (`planning.rosetta`) before executing this plan.

## Approach

Same **diligence as Kyutai Moshi → Moshi-RAG**. `moshi-rag-src` is read-only ground truth. Port **conditioners, fuser, streaming_sum, encoder, RAGManager** — do not close on forced text tokens.

1. Diff PersonaPlex `lm.py` / `loaders.py` vs Moshi-RAG (PP0). Record missing `condition_provider`, fuser methods, `update_streaming_sum_tensors`.
2. Copy NVIDIA tree → `code-improvements/personaplex-migrate` (PP1).
3. Port `conditioners/` + encoder HTTP into the **encoder child**. Grow 7B `LMGen` **pending + consume + embedding add** only (PP19). Do **not** load `ConditionProvider` / construct a second `ConditionFuser` on GPU 0.
4. Prove one tensor path (SC-PP2) on **bf16 or q8** — `update_*` **and** `apply_pending` on ≥2 steps.
5. **Proper q8 (PP11):** port `QLinear`; **`personaplex_q8_local.py`** (local path, LM-only, copy_missing on bf16 then off on q8); loader dtype skip; `personaplex_server.py` stream_load; prove step, graphs on/off, bf16 vs q8. Conditioner/ARC separate. Not `moshi_rag_q8_local.py`.
6. Hive **PP-T8 smoke** (discriminator, query, launcher wraps) may land here or in parallel after T4 classes exist. **SC-PP7** Hive talk is **after SC-PP2 and SC-PP6**.
7. Live Hive turn (**PP-T9**, SC-PP11). Cutover default (PP13) after SC-PP2/3/6/7/11 **and PP-T9**.

```text
PP-T1/T0 inventory -> PP-T2 copy -> PP-T12 architecture port
                                 -> PP-T3..T7 RAG + streaming_sum proof
                                 -> PP-T10 proper q8 (export, load, graphs, bf16 compare)
                                 -> PP-T8 Hive + encoder
                                 -> PP-T9 live
                                 -> PP-T11 cutover
```

Forced-text inject is debug-only (PP12).

**Hive-only innovations (not a Kyutai or NVIDIA drop-in):** PP15 pin identity + streaming_sum knowledge; PP16 local `.pt` voice embeddings; PP17 prefill abort on hold drop. These are in-scope product, not close-out substitutes for SC-PP2/SC-PP6.

**Kyutai diligence (PP19):** ARC + fuser live in the **encoder** child; 7B **adds** one `[B,1,4096]` frame **after `embed_codes`, before `transformer`** (I4; NVIDIA `forward_embeddings` is transformer-only). No `first_speaker` LUT. No `condition_provider` tensors in the 7B load. Hive frombuffer encoder reader. No streaming_sum during pin.

**Voice_Bot delay/garble (PP21):** Moshi-RAG live lag was STT + step < recv; live garble was server pipeline (R50 offline q8 clean). PersonaPlex `opus_loop` has no STT; skip `other_mimi` codec in the live loop; prove 12.5 Hz after `0x00` and R49/R50 on this server. Not assumed fixed.

**Injection sites (PP22):** I1 `/embed` → I2 pending (squeeze/dtype) → I3 apply in `step` → I4 graph-arg add. Pin/query/q8/opus/LLM wraps are the other inject/refuse points. Kyutai `batch_runner` is not ported.

## File targets (working copy unless noted)

| Task | Files |
|---|---|
| Copy | `code-improvements/personaplex-migrate/` |
| Ground truth (read) | `moshi-rag-src/moshi/moshi/{conditioners,models/lm.py,server_conditioner.py,inference_utils,reference,llm}` |
| Port | working copy `conditioners/`, `models/lm.py`, `models/loaders.py`, encoder entry |
| QLinear | working copy `utils/quantize.py`; Hive `scripts/personaplex_q8_local.py`; loader dtype skip; `personaplex_server.py` stream_load |
| Hive | Step into existing: `voice_bot.py` `VoiceBotConfig`; `voice_moshi.py` `_listen_gate` / `_q8_preflight` / `_connect_handshake` / `_probe_*`; `voice_moshi_server.py` `moshi_child_env` / `q8_server_command` (mirror `personaplex_server_command` + `personaplex_launcher_path`) / `encoder_server_command` / `ensure_loopback_encoder`. New files: `scripts/personaplex_server.py`, `scripts/personaplex_q8_local.py`. PP20 wrap table. |
| Query/seed | working copy `server.py` (PP-T13); no idle-timeout patch |
| Not edited | `moshi-rag-src`, NVIDIA snapshot, `scripts/moshi_q8_server.py`, `scripts/moshi_rag_q8_local.py` |

## Validation

`py -3.11 -m pytest tests/test_personaplex_migrate.py -q` must assert retrieve + encoder tensor + `update_streaming_sum_tensors` **and** `apply_pending` on ≥2 steps (SC-PP2). Text-only or update-without-consume fails.

After spec edits: `py -3.11 -m hive_planner emit --feature PersonaPlex_migrate --force-delta` then `spec-drift-check --feature PersonaPlex_migrate` (loop 10).

Open after cascade (still block CodeSpec): **G6** pin+sum unproven until PP-T12/T5 (**PP13 gate**), **G10** dual-Mimi VRAM, **G2/PP14** VAD, **G46** 7B handshake time. Keep NVIDIA **context 2048**. G17/G27/G57 tasked. Spec-only 2026-11-21 third cascade closed wording G201+. Re-run emit + spec-drift on that cascade loop 10.
