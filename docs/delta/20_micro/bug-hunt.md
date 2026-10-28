# Feature Micro Brief: bug-hunt

**Hook:** `change.bugfix_mode`, `integration.wiring_audit`

<!-- ROSETTA-NAV -->

## Agent navigation (Rosetta Stone)

Load [`docs/planning-rosetta-stone.md`](../../planning-rosetta-stone.md) (`planning.rosetta`) before coding from this brief.

- **Hooks:** `change.bugfix_mode`, `integration.wiring_audit`, `spec.flow`
- **Spec Kit:** [`spec.md`](../../specs/bug-hunt/spec.md), [`plan.md`](../../specs/bug-hunt/plan.md), [`tasks.md`](../../specs/bug-hunt/tasks.md)

## Feature Name

Bug hunt — install the continuous find / fix / self-review / local-commit script.

## Scope

| In scope | Out of scope |
|----------|--------------|
| `hive_planner bug-hunt` | Executing the hunt inside the CLI |
| Cursor command, always-on chat rule, `.hive/bug-hunt/AGENT_PROMPT.md` | Push or pull-request automation |
| Chat start on "bug hunt" and derivative hunt phrases | Inventing bugs to fill the budget |
| Bootstrap + Home install into the active project | |
| Iteration count 1–200, default 50 | |
| Pause seconds: blank or omitted is 10, `0` skips the wait, any positive whole number is the wait | |
| Stop hook consumes `.hive/bug-hunt/continue.json`, waits, and starts the next pass | |

**Files:** `src/hive_planner/bug_hunt.py`, `src/hive_planner/cli.py`, `src/hive_planner/bootstrap.py`, `src/hive_planner/launcher/app.py`, `src/hive_planner/launcher/service.py`, `tests/test_bug_hunt.py`, `.cursor/rules/bug-hunt.mdc`

## Acceptance Criteria

- [x] Default script is a 50-iteration ceiling that ranks locations, then continues after internal review
- [x] Install writes the Cursor command and the packet
- [x] `--print` does not write files
- [x] Tests cover install, range, and CLI
- [x] Derivative chat phrases match; command-how questions do not
- [x] `init_project` / handoff deploy / Home Enable install the trigger

## Validation

```powershell
py -3.11 -m pytest tests/test_bug_hunt.py -v
py -3.11 -m hive_planner spec-drift-check --feature bug-hunt
```
