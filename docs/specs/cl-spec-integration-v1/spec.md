# Spec: cl-spec-integration-v1

**Hook:** `integration.cl_spec`, `spec.flow`, `memory.agents_md`  
**Status:** active  
**Delta:** [cl-spec-integration-v1.md](../../delta/20_micro/cl-spec-integration-v1.md)

## What

Continual Learning + Spec Kit integration: behavioral truth in specs, operational truth in `AGENTS.md`, drift checks in CI.

## Requirements

### R1 — Division of truth

Document and enforce behavioral vs operational memory layers (`docs/cl-spec-integration.md`).

### R2 — spec-drift-check CLI

`hive_planner spec-drift-check` classifies candidate/AGENTS bullets and flags behavioral drift not reflected in active spec.

### R3 — agents-propose rejection

Behavioral candidates (tags or heuristics) rejected before merge to `AGENTS.md`.

### R4 — ci-check integration

`ci-check` includes `spec-drift` step using handoff + drift report.

### R5 — spec creation gates

`hive_planner spec-create --feature <id>` refuses to accept a spec unless `spec.md` has a filled User Scenarios section, a filled Assumptions section, and a measurable Success Criteria section, and `tasks.md` contains the Integration wiring audit checklist. When those gates pass, the command sets `AGENTS.md` **Active feature** to that id. `spec-drift-check` and implementation-loop readiness fail while any gate is open.

## Out of scope

Auto-editing spec.md, cloud CL sync, non-markdown candidate formats.
