# Tasks: embedding-retrieval-v1

**Hook:** `spec.flow`

## Task 1 — Delta + spec ✅

- [x] Micro brief, spec, plan, tasks
- [x] Update loaders

## Task 2 — embeddings.py + index ✅

- [x] Builtin TF-IDF embedder + optional sentence-transformers
- [x] `embedding-index.json` load/save/prune
- [x] content_hash skip on re-embed

## Task 3 — Hybrid emit + ingest ✅

- [x] `select_chunks` hybrid scoring
- [x] `ingest --embed` CLI flag
- [x] Prune embedding rows on ingest

## Task 4 — Tests + bug gate ✅

- [x] `tests/test_embeddings.py`
- [x] S4D-B1: missing embed index → keyword-only unchanged
- [x] S4D-B2: prune sync
- [x] S4D-B3: full pytest regression

## Active task

**None** — Stage 4 complete (Stages 1–4D). Next: `cartridge-delta-emit-v1` (Stage 5A).

## Bug gate (Stage 4D)

| Check | Test |
|-------|------|
| S4D-B1 keyword-only default | `test_ingest_without_embed_leaves_embedding_empty` |
| S4D-B2 prune sync | `test_ingest_prune_removes_stale_embeddings`, `test_prune_embedding_index_removes_orphans` |
| S4D-B3 hybrid rank | `test_hybrid_select_prefers_semantic_match` |
| S4D-B4 regression | full pytest |

## Validation log

```text
2026-06-21 — Stage 4D bug gate
- S4D-B1: test_ingest_without_embed_leaves_embedding_empty PASS
- S4D-B2: test_ingest_prune_removes_stale_embeddings, test_prune_embedding_index_removes_orphans PASS
- S4D-B3: test_hybrid_select_prefers_semantic_match PASS
- S4D-B4: 70/70 pytest PASS
- Smoke: ingest --embed + emit --feature embedding-retrieval-v1 OK
2026-06-21 — post-v1.0.0 bug audit (Stage 4D)
- test_embeddings.py: 7/7 PASS; model_id + hybrid scoring verified
- Smoke: ingest --embed + emit embedding-retrieval-v1 OK
```
