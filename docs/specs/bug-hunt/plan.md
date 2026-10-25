# Plan: bug-hunt

**Hook:** `change.bugfix_mode`, `integration.wiring_audit`  
**Spec:** [spec.md](./spec.md)

<!-- ROSETTA-NAV -->

## Agent navigation (Rosetta Stone)

Load [`docs/planning-rosetta-stone.md`](../../planning-rosetta-stone.md) (`planning.rosetta`) before editing this plan.

- **Spec:** [`spec.md`](./spec.md)
- **Delta micro:** [`bug-hunt.md`](../../delta/20_micro/bug-hunt.md)
- **Hooks:** `change.bugfix_mode`, `integration.wiring_audit`, `spec.flow`

## Approach

Keep the script text and chat-trigger matcher in `bug_hunt.py`. The CLI, project bootstrap, handoff deploy, and Home **Enable bug hunt** all call `install_bug_hunt` so the Cursor command + always-on rule land in the project. The rule matches derivative "perform a bug hunt" phrasing; `is_bug_hunt_request` is the testable contract.

## Validation

```powershell
py -3.11 -m pytest tests/test_bug_hunt.py -v
py -3.11 -m hive_planner spec-drift-check --feature bug-hunt
```
