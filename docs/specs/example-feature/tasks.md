<!-- BOOTSTRAP: hive_planner init -->

# Tasks: example-feature

<!-- ROSETTA-NAV -->

## Agent navigation (Rosetta Stone)

Load [`docs/planning-rosetta-stone.md`](../../planning-rosetta-stone.md) (`planning.rosetta`) before executing tasks.

- **Spec:** [`spec.md`](./spec.md)
- **Plan:** [`plan.md`](./plan.md)
- **Delta micro:** [`example-feature.md`](../../delta/20_micro/example-feature.md)

## Task 1 — Replace scaffold

- [ ] Update holistic/macro docs
- [ ] Rename `example-feature` to your feature id
- [ ] Set active feature in `AGENTS.md`

## After each implementation task — Integration wiring audit (required)

- [ ] Traced caller → handler → core (no layer break)
- [ ] No false success when a sub-step failed or was skipped
- [ ] Integration-level validation evidence attached
- [ ] See `.cursor/rules/integration-wiring-audit.mdc`

## Active task

**Task 1**
