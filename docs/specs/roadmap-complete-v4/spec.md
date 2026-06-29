# Spec: roadmap-complete-v4

**Hook:** `workflow.tools`  
**Status:** active  
**Delta:** [roadmap-complete-v4.md](../../delta/20_micro/roadmap-complete-v4.md)

## What

Close Stage 9 by extending roadmap validation to unified-handoff-v2 and marking the extended roadmap complete at v1.3.0.

## Requirements

### R1 — Extended roadmap feature list

Validate spec/micro/tasks for all Stage 9 features plus prior roadmap features (22 total).

### R2 — CLI

`hive_planner roadmap-status` reports 22/22 when Stage 9 complete.

### R3 — CI integration

`ci-check` roadmap-artifacts step uses extended feature list; `unified-vendor` step validates vendored deploy.

### R4 — Documentation

`docs/delta/STAGE_ROADMAP.md` documents Stage 9 completion; README and ARCHITECTURE reflect v1.3.0.

## Out of scope

Stage 10 planning, PyPI packaging of Spec Kit wheel, cloud deploy.
