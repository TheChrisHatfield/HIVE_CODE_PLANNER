<!-- AUTO-SYNC: from docs/delta/20_micro/shared-graph-memory-v1.md -->

# Research Summary

**Feature:** `shared-graph-memory-v1`

## Problem statement

Add a local shared-memory graph substrate: typed nodes and edges in staging and permanent JSONL stores, with CLI offload and rule-based promotion (no neural controller).

## Key findings

See Delta holistic context.

## Constraints

| In scope | Out of scope |
|----------|--------------|
| Typed node/edge schema (JSONL) | MLP-hybrid neural controller |
| `.hive/shared-memory/staging/` + `permanent/` | SurrealDB / Arango / cloud graph DB |
| `graph offload` / `promote` / `status` / `export` | Cross-machine multi-root sync |
| Rule-based promote (dedupe, endpoint check) | Vendor latent embeddings |

## Risks

- Draft cartridge files require human review before Delta promotion.

## Open questions

```powershell
py -3.11 -m pytest tests/test_graph_store.py -q
py -3.11 -m hive_planner graph status
```
