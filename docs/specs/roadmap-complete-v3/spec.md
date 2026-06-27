# Spec: roadmap-complete-v3

**Hook:** `workflow.tools`  
**Status:** active  
**Delta:** [roadmap-complete-v3.md](../../delta/20_micro/roadmap-complete-v3.md)

## What

Close the Stage 8 roadmap by extending artifact validation to starter-kit v2 and security hardening.

## Requirements

### R1 — Extended roadmap feature list

Validate spec/micro/tasks for all Stage 8 features plus prior roadmap features (20 total).

### R2 — CLI

`hive_planner roadmap-status` reports 20/20 when Stage 8 complete.

### R3 — CI integration

`ci-check` roadmap-artifacts step uses extended feature list.

### R4 — Documentation

`docs/delta/STAGE_ROADMAP.md` documents Stage 8 completion; README and ARCHITECTURE reflect v1.2.0.

## Out of scope

Stage 9 planning, cloud platform, new format parsers.
