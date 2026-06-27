# Tasks: change-impact-v3

## Task 1 — Delta + spec ✅

## Task 2 — call_graph.py ✅

## Task 3 — impact mode + CLI ✅

## Task 4 — Tests ✅

## Active task

**None** — Phase 4 pending validation log.

## Validation log

```text
2026-06-26 — Phase 4 gate
- call_graph.py AST import/call edges
- impact --mode bugfix --deep wired through CLI
- test_impact.py: 19/19 PASS
- Full pytest: 136/136 PASS
- ci-check: 5/5 PASS
- impact-sync-maps: call_graph.py added to project-map
- Bug hunt: import symbol paths, call-site reason priority, skip graph for non-src targets
- Full pytest post-hunt: 138/138 PASS
```
