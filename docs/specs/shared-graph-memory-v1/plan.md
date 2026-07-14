# Plan: shared-graph-memory-v1

**Hook:** `memory.shared_graph`  
**Spec:** [spec.md](./spec.md)

## Approach

Implement JSONL append stores under `.hive/shared-memory/` with a small validation + promote module. Rule-based promote acts as the v1 stand-in for the future MLP controller gate.

## Module map

```text
src/hive_planner/
  graph_store.py     # schema, load/append, promote, status, export
  config.py          # RepoPaths shared-memory helpers
  cli.py             # nested: graph offload|promote|status|export
tests/
  test_graph_store.py
  fixtures/shared-graph/sample-bundle.json
docs/delta/20_micro/shared-graph-memory-v1.md
docs/specs/shared-graph-memory-v1/
```

## Risks

| Risk | Mitigation |
|------|------------|
| Dangling edges after partial promote | Drop with warning; never hard-fail entire batch |
| ID collisions across repos | Require opaque string ids; skip duplicates on promote |
| Confuse with AGENTS.md routing | Separate module + paths under shared-memory/ |

## Validation

- Unit tests for schema reject, offload append, promote dedupe, dangling edge drop
- CLI `graph status` after fixture offload + promote
