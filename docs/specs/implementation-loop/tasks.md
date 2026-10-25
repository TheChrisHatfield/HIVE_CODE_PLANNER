# Tasks: implementation-loop

<!-- ROSETTA-NAV -->

## Agent navigation (Rosetta Stone)

Load [`docs/planning-rosetta-stone.md`](../../planning-rosetta-stone.md) (`planning.rosetta`) before executing tasks.

- **Spec:** [`spec.md`](./spec.md)
- **Plan:** [`plan.md`](./plan.md)
- **Delta micro:** [`implementation-loop.md`](../../delta/20_micro/implementation-loop.md)

## Phase 1 — Spec records

- [x] T001 Write `docs/specs/implementation-loop/spec.md`, `plan.md`, `tasks.md`, and `docs/delta/20_micro/implementation-loop.md`

## Phase 2 — Readiness and install (US1)

- [x] T002 Add `src/hive_planner/implementation_loop.py` with pack render, MIT NOTICE text, `assess_implementation_readiness`, and command discovery
- [x] T003 Add CLI `implementation-loop install` (`--pack` required, `--print`, `--force-pack`) and `implementation-loop status --feature`
- [x] T004 Preserve `commands.json`, `state.json`, and `retrospective.log` on same-pack reinstall
- [x] T005 `tests/test_implementation_loop.py` for ready vs blocked fixtures, including missing `tasks.md`, empty commands, and trunk branch

## Phase 3 — Pass contract (US2)

- [x] T006 Render 4-pack command and role files: handoff, result file, coder then checker then reviewer, commit only by the coordinator
- [x] T007 Encode the 10-pass cap, `state.json` round-trip fields, slice pause, and no new tasks when the list is complete
- [x] T008 Assert installed text forbids merge, deploy, force-push, and coder commits

## Phase 4 — Solo pack (US3)

- [x] T009 Render 1-pack so the coordinator performs implement, check, and review, and the command does not delegate to coder, checker, or reviewer files

## Phase 5 — Learning (US4)

- [x] T010 Render `retrospective.md`: every five completed features, proposal file with `# operational` and `# behavioral`, apply path through `agents-propose` or `spec.md`
- [x] T011 Assert coding role text does not edit `AGENTS.md`

## Phase 6 — Entry points (US5)

- [x] T012 `is_implementation_loop_request` and always-on `.cursor/rules/implementation-loop.mdc` start phrases; questions and bug-hunt phrases do not match
- [x] T013 `init_project` installs only when `--implementation-loop-pack` is set
- [x] T014 Home **Enable implementation loop** asks for a pack and calls the install function

## Phase 7 — Maps and audit

- [x] T015 Add the module and test rows in `docs/change-impact/project-map.md` and `test-map.md` after the module exists
- [x] T016 Wiring audit: CLI, init flag, and Home all call install; status exit `2` on a blocked fixture; spec-drift-check for `implementation-loop`

## Active task

**None** — install, readiness, trigger, and Home enable are implemented.

## Validation log

```text
2026-10-25 — spec only
- docs/specs/implementation-loop/{spec,plan,tasks}.md
- docs/delta/20_micro/implementation-loop.md
- docs/delta/10_macro.md workflow step
- docs/change-impact/impact-packets/20261025-implementation-loop.md
- py -3.11 -m hive_planner spec-drift-check --feature implementation-loop: ok
- Runtime tests not run: no Python module yet

2026-10-25 — implementation complete
- src/hive_planner/implementation_loop.py: install, readiness, trigger, command discovery
- src/hive_planner/cli.py: implementation-loop install/status
- src/hive_planner/bootstrap.py: --implementation-loop-pack
- src/hive_planner/launcher/app.py + service.py: Home enable
- tests/test_implementation_loop.py: 14 passed
- py -3.11 -m hive_planner spec-drift-check --feature implementation-loop: ok
- py -3.11 -m hive_planner wiring-audit record --feature implementation-loop: recorded
- docs/change-impact/project-map.md + test-map.md: rows added
- Pre-existing failure: tests/test_launcher.py::test_run_unified_verify_on_bootstrapped_project (fails on main without this feature)
```
