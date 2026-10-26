# Feature Micro Brief: implementation-loop

**Hook:** `spec.flow`, `workflow.tools`, `integration.cl_spec`  
**Status:** implemented

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
| Readiness command that blocks when the spec stack or commands are missing | Running coder or reviewer inside Python |
| Python coordinator gates: start, handoff, check, accept, commit | Agent-owned git commit or hand-edited round trips |
| Retrospective every five completed features, human-approved | Editing `AGENTS.md` during a coding task |
| Chat start phrase, Home enable, and Home coordinator buttons | Install on every `init` without a pack |

**Files:** `src/hive_planner/implementation_loop.py`, `src/hive_planner/cli.py`, `src/hive_planner/bootstrap.py`, `src/hive_planner/launcher/app.py`, `src/hive_planner/launcher/service.py`, `src/hive_planner/launcher/agent_prompt_templates.py`, `src/hive_planner/launcher/user_guide.py`, `tests/test_implementation_loop.py`, `tests/test_implementation_loop_coordinator.py`, `tests/test_launcher.py`

## Acceptance Criteria

- [x] Install requires an explicit pack and writes the command, rule, roles, and NOTICE
- [x] Status is ready only when spec, plan, tasks, micro brief, commands, pack, and a non-trunk branch are present
- [x] 4-pack commits only after checker and reviewer result files pass
- [x] 1-pack keeps a single coordinator and still forbids merge and deploy
- [x] Retrospective proposals split operational and behavioral, and coding passes leave `AGENTS.md` alone
- [x] Chat phrase and Home install use the same installer; plain init does not
- [x] Home Loop status/start/handoff/check/accept/commit call the same Python gates as the CLI; chat remains valid
- [x] Python `check` runs build / test:quick / wiring audit and appends the checker result; bug hunt stays separate

## Validation

```powershell
py -3.11 -m pytest tests/test_implementation_loop.py tests/test_implementation_loop_coordinator.py tests/test_launcher.py -k "implementation_loop" -v
py -3.11 -m hive_planner spec-drift-check --feature implementation-loop
```

T018: status JSON includes `round_trips` from `state.json`. Installed coordinator text covers dirty tree, commit slug, slice `test:full`, and five-feature retrospective. Always-on rule picks or asks for the feature.

T023: reviewer/checker fail returns to coder then checker; missing `gh` leaves `pr_url` empty; push and slice `test:full` failures do not advance `current_task`.

T024: reviewer requires a checker pass after the last coder; `start` stays blocked unless `--force-feature`.

T025: thirty-cycle gap loop — commit order, trigger questions, discovery, feature id, 1-pack commit.

T026: role names case-insensitive; malformed `test:full` does not crash after commit.
