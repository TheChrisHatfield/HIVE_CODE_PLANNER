# Tasks: bug-hunt

<!-- ROSETTA-NAV -->

## Agent navigation (Rosetta Stone)

Load [`docs/planning-rosetta-stone.md`](../../planning-rosetta-stone.md) (`planning.rosetta`) before executing tasks.

- **Spec:** [`spec.md`](./spec.md)
- **Plan:** [`plan.md`](./plan.md)
- **Delta micro:** [`bug-hunt.md`](../../delta/20_micro/bug-hunt.md)

- [x] Spec and micro brief
- [x] `bug_hunt.py` script render and install
- [x] CLI `bug-hunt`
- [x] `tests/test_bug_hunt.py`
- [x] R4 chat-trigger matcher for derivative hunt phrases
- [x] R3 bootstrap + handoff deploy install
- [x] R3 Home **Loop controls** → Bug hunt Enable → `run_project_bug_hunt_install`

## Active task

**None** — validated.

## Validation log

```text
2026-10-20
- tests/test_bug_hunt.py + bootstrap init + launcher bug_hunt/agent templates: 34 passed
- hive_planner spec-drift-check --feature bug-hunt: ok
- Installed command, always-on rule, packet, and scripts/bug-hunt.md into this repo
```
