# Spec: agents-memory-ci-v1

**Hook:** `automation.ci_memory`, `memory.agents_md`  
**Status:** active  
**Delta:** [agents-memory-ci-v1.md](../../delta/20_micro/agents-memory-ci-v1.md)

## What

Provide local tooling to lint, dedupe, and propose updates to `AGENTS.md` following the proposal workflow in [context-handoff-and-automation.md](../../context-handoff-and-automation.md).

## Why

Stage 3 change-impact flags doc edits; this stage adds governed memory promotion without blind automation.

## Requirements

### R1 — Structure lint

- Required sections: Repository root, Planning Rosetta Stone, Startup read order, Delta model, Active feature.
- Report missing or empty sections.

### R2 — Content lint

- Flag duplicate bullets (normalized whitespace, case-insensitive).
- Flag bullets exceeding 240 characters.
- Flag low-signal patterns (e.g. "TODO", branch names, session ids).

### R3 — Proposal workflow

- `agents-propose` merges validated candidate bullets into a proposal markdown file.
- Never modify `AGENTS.md` by default.
- Explicit `--apply` flag exists but returns error in v1 with message to use manual review.

### R4 — Output

- Write proposals to `docs/proposals/agents-memory-<timestamp>.md`.
- Include diff-style before/after for proposed section additions.

### R5 — CLI

- `hive_planner agents-lint [--path AGENTS.md]`
- `hive_planner agents-propose --candidates FILE`

## Out of scope

GitHub Actions, transcript parsing, auto-merge, overwriting entire AGENTS.md.
