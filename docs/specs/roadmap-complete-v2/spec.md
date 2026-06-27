# Spec: roadmap-complete-v2

**Hook:** `workflow.tools`  
**Status:** active  
**Delta:** [roadmap-complete-v2.md](../../delta/20_micro/roadmap-complete-v2.md)

## What

Close the Stage 7 roadmap by extending artifact validation to CL/spec integration, memory v2, cartridge rule seeds, change impact v3, and project bootstrap.

## Requirements

### R1 — Extended roadmap feature list

Validate spec/micro/tasks for all Stage 7 features plus prior v1 roadmap features.

### R2 — CLI

`hive_planner roadmap-status` reports 18/18 when Stage 7 complete.

### R3 — CI integration

`ci-check` roadmap-artifacts step uses extended feature list.

### R4 — Documentation

`docs/delta/STAGE_ROADMAP.md` documents Stage 7 completion.

## Out of scope

Stage 8 planning, cloud platform, new format parsers.
