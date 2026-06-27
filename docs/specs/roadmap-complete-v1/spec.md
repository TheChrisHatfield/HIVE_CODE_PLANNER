# Spec: roadmap-complete-v1

**Hook:** `workflow.tools`  
**Status:** active  
**Delta:** [roadmap-complete-v1.md](../../delta/20_micro/roadmap-complete-v1.md)

## What

Close the Stages 1–6 compiler roadmap with artifact validation and documentation.

## Requirements

### R1 — Roadmap feature list

Validate spec.md, micro brief, and tasks.md exist for all roadmap features.

### R2 — CLI

`hive_planner roadmap-status` reports complete/missing features.

### R3 — CI integration

`ci-check` includes roadmap-artifacts step (enabled by default).

### R4 — Documentation

`docs/delta/STAGE_ROADMAP.md` summarizes completed stages.

## Out of scope

Stage 7 planning, cloud platform, new format parsers.
