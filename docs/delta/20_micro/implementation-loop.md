# Feature Micro Brief: implementation-loop

**Hook:** `spec.flow`, `workflow.tools`, `integration.cl_spec`  
**Status:** draft

<!-- ROSETTA-NAV -->

## Agent navigation (Rosetta Stone)

Load [`docs/planning-rosetta-stone.md`](../../planning-rosetta-stone.md) (`planning.rosetta`) before coding from this brief.

- **Hooks:** `spec.flow`, `workflow.tools`, `integration.cl_spec`, `integration.wiring_audit`
- **Spec Kit:** [`spec.md`](../../specs/implementation-loop/spec.md), [`plan.md`](../../specs/implementation-loop/plan.md), [`tasks.md`](../../specs/implementation-loop/tasks.md)

## Feature Name

Implementation loop — code a finished Hive spec in separate passes.

## Scope

| In scope | Out of scope |
|----------|--------------|
| Install a Cursor loop that reads `docs/specs/<feature>/{spec,plan,tasks}.md` | Writing or regenerating the spec, plan, or tasks |
| 1-pack and 4-pack | 5-pack tracker, personas, Copilot install |
| One task per cycle: implement, check, review, then coordinator commit | Merge, deploy, force-push |
| Readiness command that blocks when the spec stack or commands are missing | Running the coding loop inside Python |
| Retrospective every five completed features, human-approved | Editing `AGENTS.md` during a coding task |
| Chat start phrase and Home enable | Install on every `init` without a pack |

**Files:** `src/hive_planner/implementation_loop.py`, `src/hive_planner/cli.py`, `src/hive_planner/bootstrap.py`, `src/hive_planner/launcher/app.py`, `src/hive_planner/launcher/service.py`, `tests/test_implementation_loop.py`

## Acceptance Criteria

- [x] Install requires an explicit pack and writes the command, rule, roles, and NOTICE
- [x] Status is ready only when spec, plan, tasks, micro brief, commands, pack, and a non-trunk branch are present
- [x] 4-pack commits only after checker and reviewer result files pass
- [x] 1-pack keeps a single coordinator and still forbids merge and deploy
- [x] Retrospective proposals split operational and behavioral, and coding passes leave `AGENTS.md` alone
- [x] Chat phrase and Home install use the same installer; plain init does not

## Validation

```powershell
py -3.11 -m pytest tests/test_implementation_loop.py -v
py -3.11 -m hive_planner spec-drift-check --feature implementation-loop
```
