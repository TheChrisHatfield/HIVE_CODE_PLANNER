# Tasks: agents-memory-ci-v1

**Hook:** `spec.flow`

## Task 1 — Delta + spec ✅

- [x] Micro brief, spec, plan, tasks
- [x] Update loaders, `AGENTS.md` editable section

## Task 2 — Lint module ✅

- [x] Parse AGENTS.md sections
- [x] Duplicate and length checks
- [x] `agents-lint` CLI

## Task 3 — Proposal writer ✅

- [x] `docs/proposals/` scaffold
- [x] `agents-propose` CLI
- [x] Block `--apply` in v1

## Task 4 — Tests + bug gate ✅

- [x] `tests/test_agents_memory.py`
- [x] S4C-B1: duplicate detection
- [x] S4C-B2: AGENTS unchanged after propose
- [x] S4C-B3: full pytest regression

## Active task

**None** — Stage 4C complete. Next: `embedding-retrieval-v1` (Stage 4D).

## Bug gate (Stage 4C)

| Check | Test |
|-------|------|
| S4C-B1 duplicate detection | `test_lint_duplicate_bullets_warns` |
| S4C-B2 proposal only | `test_propose_writes_file_without_modifying_agents` |
| S4C-B3 regression | full pytest |

## Validation log

```text
2026-06-21 — Stage 4C bug gate
  py -3.11 -m pytest -v → 63 passed
  S4C-B1 duplicate detection → test_lint_duplicate_bullets_warns
  S4C-B2 proposal only → test_propose_writes_file_without_modifying_agents
  S4C-B3 regression → 63 passed
  agents-lint → ok
  agents-propose --candidates docs/proposals/example-candidates.md
2026-06-21 — post-v1.0.0 bug audit (Stage 4C)
- test_agents_memory.py: 7/7 PASS; S4C-B1..B3 verified
```
