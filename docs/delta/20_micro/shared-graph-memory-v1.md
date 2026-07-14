# Feature Micro Brief: shared-graph-memory-v1

**Hook:** `memory.shared_graph`, `representation.graph_native`

<!-- ROSETTA-NAV -->

## Agent navigation (Rosetta Stone)

Load [`docs/planning-rosetta-stone.md`](../../planning-rosetta-stone.md) (`planning.rosetta`) before coding from this brief.

- **Hooks:** `memory.shared_graph`, `representation.graph_native`, `context.delta`
- **Spec Kit:** [`spec.md`](../../specs/shared-graph-memory-v1/spec.md), [`plan.md`](../../specs/shared-graph-memory-v1/plan.md), [`tasks.md`](../../specs/shared-graph-memory-v1/tasks.md)

## Feature Name

Shared Graph Memory v1 — staging + permanent JSONL graph stores with CLI offload/promote.

## Scope

| In scope | Out of scope |
|----------|--------------|
| Typed node/edge schema (JSONL) | MLP-hybrid neural controller |
| `.hive/shared-memory/staging/` + `permanent/` | SurrealDB / Arango / cloud graph DB |
| `graph offload` / `promote` / `status` / `export` | Cross-machine multi-root sync |
| Rule-based promote (dedupe, endpoint check) | Vendor latent embeddings |

## Acceptance Criteria

- [x] Nodes and edges validate against v1 schema before append
- [x] Offload appends to staging JSONL files
- [x] Promote copies valid new ids to permanent; skips duplicates; drops dangling edges with warnings
- [x] Manifest records counts and last promote
- [x] `pytest tests/test_graph_store.py` passes

## Validation

```powershell
py -3.11 -m pytest tests/test_graph_store.py -q
py -3.11 -m hive_planner graph status
```

## Source

Distilled from `HIVE_CODE_DEV_1` session transcript (`session.transcript`).
