# Plan: embedding-retrieval-v1

**Hook:** `compiler.pipeline`  
**Spec:** [spec.md](./spec.md)

## Approach

Add `embeddings.py` with pluggable backend. v1 candidate: `sentence-transformers` with small model (`all-MiniLM-L6-v2`) behind optional extra. Keep vectors in JSON for local Git portability (acceptable for small corpora).

## Module map

```text
src/hive_planner/
  embeddings.py      # embed_text, load/save index, cosine_similarity
  indexer.py         # prune embedding index alongside chunk index
  emitter.py         # hybrid select_chunks
  pipeline.py        # --embed flag
  cli.py             # ingest --embed
tests/
  test_embeddings.py
```

## Risks

| Risk | Mitigation |
|------|------------|
| Large index files | Cap corpus size in v1; document limit |
| Slow first embed | Cache by content_hash; optional flag only |
| Model download in CI | Skip embedding tests when dep missing |
| Ranking regression | Default off; A/B test in tests with fixtures |

## Validation

- Keyword-only regression: all 36+ tests pass without `[embeddings]`
- With embeddings: rank relevant chunk higher for semantic query
- Prune removes orphan embedding rows
