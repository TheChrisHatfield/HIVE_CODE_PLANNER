# Feature Micro Brief: agnostic-loop

**Hook:** `workflow.tools`, `spec.flow`, `integration.wiring_audit`

<!-- ROSETTA-NAV -->

## Agent navigation (Rosetta Stone)

Load [`docs/planning-rosetta-stone.md`](../../planning-rosetta-stone.md) (`planning.rosetta`) before coding from this brief.

- **Spec Kit:** [`spec.md`](../../specs/agnostic-loop/spec.md)

## Feature Name

Agnostic loop — pause-cycle reward chooser; Hive Planner installs the portable hive-loop-kit with a generic catalog.

## Scope

| In scope | Out of scope |
|----------|--------------|
| Full kit install, generic replaceable catalog.json, Thompson + MCTS choose | SeamFlow / UV / train / reconstruction tables; Hive spec-gap catalog |
| CLI gates and opt-in install | Replacing bug hunt or implementation-loop |
| Home Enable + chat trigger | Python as coder/reviewer; merge/deploy |

**Files:** `src/hive_planner/agnostic_loop.py`, `src/hive_planner/cli.py`, `src/hive_planner/bootstrap.py`, `src/hive_planner/launcher/app.py`, `src/hive_planner/launcher/service.py`, `tests/test_agnostic_loop.py`

## Acceptance Criteria

- [x] Default rewards are generic work kinds; catalog.json is replaceable
- [x] `arm` / `begin` / `review` write `.hive/agnostic-loop/`
- [x] `choose --seed` is deterministic
- [x] Install is opt-in (not every `init`)

## Validation

```powershell
py -3.11 -m pytest tests/test_agnostic_loop.py -v
```
