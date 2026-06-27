<!-- AUTO-SYNC: from docs/delta/20_micro/embedding-retrieval-v1.md -->

# Feature Micro Brief: embedding-retrieval-v1

**Hook:** `compiler.pipeline`, `context.library`, `context.metadata`

## Feature Name

Embedding Retrieval v1 — optional vector index alongside JSON chunk index for improved emit ranking.

## Holistic Link

Addresses holistic non-goal deferral: *JSON keyword index first* — adds optional semantic retrieval without replacing keyword fallback.

## Macro Link

Extends **Index builder** and **Cartridge emitter** per [cartridge-compiler-implementation.md](../../cartridge-compiler-implementation.md).

## Scope

| In scope | Out of scope |
|----------|--------------|
| Optional `[embeddings]` extra | Cloud vector DB |
| Local embedding index JSON/file | Re-embed on every ingest by default |
| Hybrid rank: embeddings + keyword regex | Full HNSW production index |
| Fallback to keyword-only when dep missing | Translator integration |

**Files:** `src/hive_planner/embeddings.py`, `emitter.py`, `pipeline.py`, `tests/test_embeddings.py`

## Inputs / Outputs

- **In:** Chunk index, optional `--embed` flag on ingest
- **Out:** `context-library/indexes/embedding-index.json`, improved `select_chunks` ranking

## Acceptance Criteria

- [x] Missing embedding dep → keyword-only emit unchanged
- [x] With `--embed`: embed command builds index for indexed chunks
- [x] Emit prefers hybrid score; still respects 3 doc / 8 excerpt limits
- [x] Embedding index pruned when chunks pruned
- [x] B1–B8 regression with embeddings disabled

## Validation

```powershell
py -3.11 -m pip install -e ".[dev,embeddings]"
py -3.11 -m hive_planner ingest --embed
py -3.11 -m hive_planner emit --feature embedding-retrieval-v1
py -3.11 -m pytest -v
```
