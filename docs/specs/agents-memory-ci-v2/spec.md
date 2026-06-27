# Spec: agents-memory-ci-v2

**Hook:** `automation.ci_memory`, `integration.cl_spec`  
**Status:** active  
**Delta:** [agents-memory-ci-v2.md](../../delta/20_micro/agents-memory-ci-v2.md)

## What

Extend memory CI with guarded `--apply`, candidate ingest, and optional GitHub Actions proposal workflow.

## Requirements

### R1 — Guarded apply

- `agents-propose --apply` and `agents-apply` merge operational candidates into `## Durable Workspace Facts` only.
- Behavioral candidates rejected (Phase 1 spec-drift integration).
- Roll back file if post-apply lint fails.

### R2 — Candidate ingest

- `agents-ingest --from FILE` normalizes transcript/CL exports to tagged candidates markdown.

### R3 — Proposal audit trail

- Apply still writes `docs/proposals/agents-memory-<timestamp>.md` with `Applied: true`.

### R4 — GitHub Actions

- Manual-dispatch workflow runs lint, spec-drift-check, agents-propose, uploads proposal artifact.

## Out of scope

Auto-merge to main, transcript extraction plugin, nightly schedule (defer v2.1).
