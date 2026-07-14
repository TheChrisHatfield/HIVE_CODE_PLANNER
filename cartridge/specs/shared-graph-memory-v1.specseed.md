<!-- DRAFT: review before promoting -->

<!-- AUTO-SYNC: from docs/specs/shared-graph-memory-v1/spec.md -->

# Spec seed: shared-graph-memory-v1

# Spec: shared-graph-memory-v1

**Hook:** `memory.shared_graph`, `representation.graph_native`  
**Status:** active  
**Delta:** [shared-graph-memory-v1.md](../../delta/20_micro/shared-graph-memory-v1.md)

## What

Add a local shared-memory graph substrate: typed nodes and edges in staging and permanent JSONL stores, with CLI offload and rule-based promotion (no neural controller).

## Why

HIVE_CODE_DEV_1 defines repos as worker cells that offload reflections into a temporary store; Hive curates into permanent shared knowledge. V1 uses explicit graph records (text interchange → graph compute representation) so agents and tools reason over relationships instead of flat notes.

## Requirements

### R1 — Schema

- **Node:** `id`, `type` (`concept` | `spec` | `heuristic` | `repo` | `agent` | `paper` | `other`), `label`, `properties` (object), `provenance` (`source_repo`, `source_path`, `feature`, `created_at`), `status` (`staging` | `permanent`)
- **Edge:** `id`, `from`, `to`, `rel` (`supports` | `contradicts` | `depends_on` | `derived_from` | `related_to`), `confidence` (0–1), `provenance`, `status`

### R2 — Storage layout

- Staging: `.hive/shared-memory/staging/nodes.jsonl`, `edges.jsonl`
- Permanent: `.hive/shared-memory/permanent/nodes.jsonl`, `edges.jsonl`
- Manifest: `.hive/shared-memory/manifest.json` (`schema_version`, counts, `last_promote`)

### R3 — Offload

- `hive_planner graph offload --from <path>` appends validated records to staging.
- Input: JSON bundle `{ "nodes": [...], "edges": [...] }` or JSONL with `"kind": "node"|"edge"`.

### R4 — Promote

- `hive_planner graph promote [--dry-run]` moves staging → permanent under rules:
  - Valid schema only
  - Skip `id` already in permanent
  - Edges need both endpoints in permanent or same promote batch; otherwise drop with warning
  - Update manifest stats

### R5 — Status / export

- `graph status` reports counts per tier
- `graph export --tier staging|permanent [--pretty]` dumps nodes + edges as JSON

### R6 — Isolation

- Do not modify `memory_routing.py` or `call_graph.py`
- Module: `src/hive_planner/graph_store.py`

## Out of scope

MLP-hybrid controller, external graph databases, cross-machine sync, model latent access.
