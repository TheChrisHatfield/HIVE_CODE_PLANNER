# Spec: git-handoff-ci-v1

**Hook:** `workflow.git_handoff`, `automation.ci_memory`  
**Status:** active  
**Delta:** [git-handoff-ci-v1.md](../../delta/20_micro/git-handoff-ci-v1.md)

## What

Add a unified CI/handoff check command and GitHub Actions workflow for pre-merge validation.

## Why

Stages 4C–5B added agents lint, map sync, and pytest separately. Handoff doc recommends a combined validation loop before merge.

## Requirements

### R1 — ci-check steps

1. `agents-lint` on repo `AGENTS.md` (errors fail)
2. Active feature from AGENTS.md has `docs/specs/<feature>/spec.md` and micro brief
3. Impact map drift check (dry-run sync) unless `--allow-map-drift`
4. Full pytest unless `--skip-pytest`

### R2 — Exit codes

- `0` when all steps pass
- `1` when any step fails

### R3 — GitHub Actions

- Workflow on push, PR, and manual dispatch
- Install `[dev]`, run `impact-sync-maps`, then `ci-check`

### R4 — Regression

- Existing CLI commands unchanged

## Out of scope

Proposal automation, transcript ingestion, required cloud remote.
