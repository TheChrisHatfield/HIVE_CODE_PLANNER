# Spec: embedding-retrieval-v1

**Hook:** `compiler.pipeline`, `context.library`  
**Status:** active  
**Delta:** [embedding-retrieval-v1.md](../../delta/20_micro/embedding-retrieval-v1.md)

## What

Add optional embedding-based chunk ranking for cartridge emit while preserving keyword retrieval as fallback.

## Why

Keyword regex in [`emitter.py`](../../../src/hive_planner/emitter.py) works for small corpora but misses semantic matches. Holistic doc deferred full vector retrieval; this stage adds it as an optional layer.

## Requirements

### R1 — Optional dependency

- `[embeddings]` extra → lightweight local model or `sentence-transformers` (TBD in plan review).
- Missing dep → ingest/emit behave as v3.

### R2 — Embedding index

- Store per-chunk vectors in `context-library/indexes/embedding-index.json` (or companion file if size warrants).
- Fields: `chunk_id`, `model_id`, `vector` (list of floats).

### R3 — Ingest hook

- `hive_planner ingest --embed` builds/updates embedding index for current chunks.
- Skip re-embed when content_hash unchanged.

### R4 — Hybrid ranking

- `select_chunks`: combine keyword score (existing) + cosine similarity to feature query embedding.
- Weights configurable constants in `emitter.py` (e.g. 0.4 keyword + 0.6 semantic).

### R5 — Prune sync

- When `prune_index` removes chunks, remove matching embedding entries.

### R6 — Regression

- Default path (no `--embed`, no dep) identical to cartridge-compiler-v3.

## Out of scope

External vector DB, GPU requirement, automatic holistic/macro emission, online model API calls.
