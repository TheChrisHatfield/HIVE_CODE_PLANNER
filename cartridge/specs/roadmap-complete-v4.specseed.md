<!-- DRAFT: review before promoting -->

<!-- AUTO-SYNC: from docs/specs/roadmap-complete-v4/spec.md -->

# Spec seed: roadmap-complete-v4

# Spec: roadmap-complete-v4

**Hook:** `workflow.tools`  
**Status:** active  
**Delta:** [roadmap-complete-v4.md](../../delta/20_micro/roadmap-complete-v4.md)

<!-- ROSETTA-NAV -->

## Agent navigation (Rosetta Stone)

Before implementing, load the hook map — do not jump straight into requirements.

1. [`docs/planning-rosetta-stone.md`](../../planning-rosetta-stone.md) — hook `planning.rosetta`
2. Follow **UNLOCKS**: `context.delta` → [`00_holistic.md`](../../delta/00_holistic.md), [`10_macro.md`](../../delta/10_macro.md)
3. This feature — hook `spec.flow`:
   - Delta micro: [`roadmap-complete-v4.md`](../../delta/20_micro/roadmap-complete-v4.md)
   - Plan: [`plan.md`](./plan.md)
   - Tasks: [`tasks.md`](./tasks.md)

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
