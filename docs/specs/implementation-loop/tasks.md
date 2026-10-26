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
- [x] T017 Status reports `complete` (exit 0) when every task is checked and the other R1 files exist, even if `state.json` is not already `complete`. Do not treat "no open task" as blocked in that case. Trunk still blocks starting work, not this complete report.
- [x] T018 Close remaining R1/R5/R6/R7/R8 prompt and status gaps: status JSON reports `round_trips` from `state.json`; coordinator text covers dirty tree, commit slug, slice `test:full`, and five-feature retrospective; always-on rule picks or asks for the feature; spec R1 documents `origin/` trunk strip

## Phase 8 — Python coordinator gates (US6)

- [x] T019 Python `start` / `handoff` / `accept` / `commit` gates: dirty-tree block, 10-pass cap, refuse commit without checker and reviewer `pass`, check off the task, leave `.hive/` unstaged; installed coordinator text calls these commands; tests in `tests/test_implementation_loop_coordinator.py`
- [x] T020 Close deploy gaps: spec status implemented; `baseline_dirty` in state table; first successful push opens `gh pr create` and stores `pr_url`; every five completed features writes the proposal stub; commit leftover spec/docs
- [x] T021 Live 4-pack proof: add an Implementation loop pointer to `START_HERE.md`
- [x] T022 Fix coordinator gaps: refuse commit on trunk; handoff uses current task; reviewer fail returns to coder; `needs-sign-off` is a real accept/commit outcome; Justfile/Taskfile discovery; retrospective due every +5 completed
- [x] T023 Fix coordinator recovery: reviewer/checker fail then coder then checker; missing `gh` does not raise; push/`test:full` failure does not advance the next task; restore `tasks.md` if git commit fails; handoff/commit stay on `state.branch`
- [x] T024 Fix leftover gates: reviewer requires checker after last coder; accept `next_role` after fail/question; missing `test:full` binary does not crash; `start` stays blocked unless `--force-feature`
- [x] T025 Thirty-cycle spec/code gap loop: commit after recode, result case, questions, discovery, blocked start, feature id, 1-pack commit, atomic state write
- [x] T026 Follow-up gap loop: case-insensitive roles, `result.md`/`test:full` OSError and bad quotes, `state.json` write errors

## Active task

**None** — T026 follow-up gap loop checked.

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

2026-10-25 — gap-cascade close-out
- spec.md R1–R9 patched with cascade rules (result list, complete status, reinstall fill, clarification, push failure)
- reinstall refreshes retrospective.md and fills empty command strings
- tests T008/T011/T013: 19 passed
- Home asks before force-pack
- 4-pack installed into this repo

2026-10-25 — T017 complete-status gate
- assess_implementation_readiness: all boxes checked + commands/pack => complete (exit 0) without state.status already complete
- tests/test_implementation_loop.py: 21 passed

2026-10-26 — T018 remaining spec/code gaps
- ReadinessReport.to_dict includes round_trips, current_task, pack, pr_url, state_status
- coordinator.md: dirty tree, commit slug, slice ## + test:full, five-feature retrospective
- always-on rule: several features / exactly one / none ready
- spec R1: strip origin/ from trunk; status JSON fields
- tests/test_implementation_loop.py: 25 passed
- spec-drift-check --feature implementation-loop: ok

2026-10-26 — T019 Python coordinator gates
- CLI start / handoff / accept / commit
- tests/test_implementation_loop.py + tests/test_implementation_loop_coordinator.py: 31 passed
- spec-drift-check --feature implementation-loop: ok

2026-10-26 — T020 deploy-gap close-out
- spec/plan/micro Status: implemented
- gh pr create stores pr_url; five completes write proposal stub
- tests: 40 passed

2026-10-26 — T022 coordinator gap fixes
- commit refuses trunk; handoff uses current_task; reviewer fail -> coder; needs-sign-off accept/commit
- Justfile/Taskfile discovery; last_retrospective_n
- tests: 46 passed

2026-10-26 — T023 coordinator recovery
- reviewer/checker fail then coder then checker; missing gh; delayed task advance; restore checkoff
- tests: 52 passed (test_implementation_loop.py + test_implementation_loop_coordinator.py)
- spec-drift-check --feature implementation-loop: ok

2026-10-26 — T024 leftover gates
- reviewer requires checker after last coder; accept next_role; missing test:full binary; start blocked unless --force-feature
- tests: 55 passed
- spec-drift-check --feature implementation-loop: ok

2026-10-26 — T025 thirty-cycle gap loop
- commit order after recode; result case; trigger questions; Taskfile/yaml; feature id; 1-pack commit; atomic JSON
- tests: 63 passed
- spec-drift-check --feature implementation-loop: ok

2026-10-26 — T026 follow-up gap loop
- role case; result/test:full OSError and bad quotes; state.json write
- tests: 65 passed
```


