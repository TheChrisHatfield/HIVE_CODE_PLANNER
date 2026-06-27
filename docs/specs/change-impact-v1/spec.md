# Spec: change-impact-v1

**Hook:** `change.impact`, `next.files`  
**Delta:** [change-impact-v1.md](../../delta/20_micro/change-impact-v1.md)

## What

Generate structured impact packets before code edits, mapping primary/secondary/tertiary effects and required validations.

## Requirements

### R1 — Scaffold

- `docs/change-impact/policy.md`, `project-map.md`, `test-map.md`, `impact-packets/`
- `.cursor/rules/change-impact.mdc`

### R2 — Impact packet schema

JSON fields: `packet_id`, `feature`, `hook_ids`, `primary`, `secondary`, `tertiary`, `risk_score`, `validations`, `created_at`

### R3 — CLI

`hive_planner impact --feature NAME --files PATH [PATH...]`

### R4 — Test map integration

When primary target is under `src/`, include mapped tests from `test-map.md`.

### R5 — Delta doc detection

Files under `docs/delta/` in `--files` → tertiary doc impact entries.

### R6 — Non-blocking load

Optional packet load for warnings must not break ingest/emit.

### R7 — Rosetta integration

Packet includes relevant `hook_ids` from planning rosetta.

## Out of scope

Automated dependency graphs, CI memory promotion.
