# Spec: implementation-loop

**Hook:** `spec.flow`, `workflow.tools`, `integration.cl_spec`, `integration.wiring_audit`  
**Status:** draft  
**Created:** 2026-10-25  
**Delta:** [implementation-loop.md](../../delta/20_micro/implementation-loop.md)

<!-- ROSETTA-NAV -->

## Agent navigation (Rosetta Stone)

Before implementing, load the hook map — do not jump straight into requirements.

1. [`docs/planning-rosetta-stone.md`](../../planning-rosetta-stone.md) — hook `planning.rosetta`
2. Follow **UNLOCKS**: `spec.flow`, `workflow.tools`, `integration.cl_spec`, `change.validation`
3. This feature — hook `spec.flow`:
   - **Feature id:** `implementation-loop`
   - Delta micro: [`implementation-loop.md`](../../delta/20_micro/implementation-loop.md)
   - Plan: [`plan.md`](./plan.md)
   - Tasks: [`tasks.md`](./tasks.md)

## What

Hive Planner already produces the specification: `spec.md`, `plan.md`, and `tasks.md`. This feature installs a Cursor coding loop that starts only after those files exist and implements that task list one task at a time.

The loop is adapted from [microsoft/agentic-loops](https://github.com/microsoft/agentic-loops) (MIT, copyright Mr. Das, 2026). Hive keeps Spec Kit as the specification stage. The loop is the execution stage. Each role is a separate agent pass. Git state, the task file, and a handoff file carry the work between passes.

The Python CLI installs the loop and reports whether a feature is ready. It does not implement the feature.

## Layers

| Layer | This feature |
|-------|----------------|
| Holistic | Coding agents implement finished specs with less drift. Spec Kit stays the behavioral contract. |
| Macro | Agent loader gains an opt-in execution loop after Spec Kit. Unified handoff and bug hunt stay in place. |
| Micro | Install role prompts, a chat start rule, a readiness gate, and a retrospective that proposes memory updates. |

## User stories

### US1 — Install and readiness (P1)

A person enables the loop on a Hive project, picks a pack, and can see whether a named feature is ready to code.

**Independent test:** install into a temp project and run status. A feature with spec, plan, tasks, commands, and a non-trunk branch is ready. A feature missing `tasks.md` is blocked.

### US2 — One task, several passes (P1)

After the start phrase, the coordinator gives one open task to the coder, then the checker, then the reviewer. Each returns before the next starts. The coordinator commits only after the checker and the reviewer pass.

**Independent test:** installed 4-pack command and role files describe that order, the handoff file, the 10-pass cap, and commit ownership. Status tracks round trips in `state.json`.

### US3 — Solo pack (P2)

A 1-pack uses one coordinator pass that designs nothing new, implements the task, runs the gates, and commits. Lane separation is waived only in that pack.

**Independent test:** a 1-pack install names only the coordinator as the executing role and still forbids merge and deploy.

### US4 — Learning between features (P2)

Every five completed features, the loop proposes durable lessons. The human approves them before they are written. Operational notes go through Continual Learning. Behavioral notes go to the spec.

**Independent test:** retrospective text states the count of five, the proposal file, and the ban on editing `AGENTS.md` inside a coding task.

### US5 — Start from chat or Home (P2)

Saying the start phrase in a project chat starts the loop in that turn. Home can install it after the pack is chosen. Project init does not install it unless a pack is passed.

**Independent test:** trigger matcher, Home install call, and init without a pack leaves the loop files absent.

## Requirements

### R1 — Ready to code

`assess_implementation_readiness(root, feature)` blocks when any of these is missing or false:

- `.hive/project.json` exists (Hive project profile).
- `docs/specs/<feature>/spec.md`, `plan.md`, and `tasks.md` exist.
- `docs/delta/20_micro/<feature>.md` exists.
- `tasks.md` contains at least one unchecked task (`- [ ]`).
- `.hive/implementation-loop/commands.json` has non-empty `build`, `test:quick`, and `test:full`.
- The current Git branch is not trunk.
- Pack is `1-pack` or `4-pack`.

Trunk is `git symbolic-ref --short refs/remotes/origin/HEAD` when that ref exists. Otherwise trunk is `main` if that branch exists, else `master`.

Status exit code is `0` when ready and `2` when blocked. The blocked message names each missing piece. The command does not create spec, plan, or tasks.

A Hive project whose `pyproject` or `ci-check` entry point is present may record `py -3.11 -m pytest` as `test:quick` and `py -3.11 -m hive_planner ci-check` as `test:full` during install. Any required command that cannot be read from CI, `pyproject`, Make, Task, or package scripts stays empty. Empty required commands block readiness. The installer does not invent a command.

### R2 — Install

`hive_planner implementation-loop install --pack {1-pack|4-pack}` writes, under `--root`:

| Path | Role |
|------|------|
| `.cursor/commands/implementation-loop.md` | Loop script the chat runs |
| `.cursor/rules/implementation-loop.mdc` | Always-on start rule |
| `.hive/implementation-loop/roles/coordinator.md` | Coordinator pass |
| `.hive/implementation-loop/roles/coder.md` | Coder pass (4-pack) |
| `.hive/implementation-loop/roles/checker.md` | Checker pass (4-pack) |
| `.hive/implementation-loop/roles/reviewer.md` | Reviewer pass (4-pack) |
| `.hive/implementation-loop/retrospective.md` | Learning pass |
| `.hive/implementation-loop/NOTICE` | MIT notice for the adapted source |
| `.hive/implementation-loop/commands.json` | Gate commands, created only if absent |
| `.hive/implementation-loop/state.json` | Loop state, created only if absent |
| `.hive/implementation-loop/retrospective.log` | Learning log, created only if absent |

`--print` prints the coordinator script and writes nothing.

`--pack` is required. There is no default pack.

Install does not edit `AGENTS.md`, `docs/specs/`, Delta docs, or `.github/copilot-instructions.md`.

Reinstall of the same pack refreshes prompts, the command, and the rule. It keeps `commands.json` values, `state.json`, `retrospective.log`, and an existing handoff or result file.

Reinstall with a different pack exits with an error unless `--force-pack` is set.

`init_project` installs these files only when `--implementation-loop-pack` is `1-pack` or `4-pack`. Omitted means the loop is not installed.

The NOTICE names the MIT license, copyright Mr. Das 2026, and `https://github.com/microsoft/agentic-loops`.

### R3 — Roles and passes

A 4-pack has four passes. A 1-pack has one pass, the coordinator, which also implements, checks, and reviews.

| Pass | May edit product code | May commit | Must do |
|------|----------------------|------------|---------|
| Coordinator | Only in 1-pack | Yes, after gates pass | Own `tasks.md` checkoff, `state.json`, handoff, and git |
| Coder | Yes | No | Implement the single task named in the handoff |
| Checker | No | No | Run `test:quick` and the wiring audit. On failure, report it |
| Reviewer | No | No | Compare the diff to `spec.md` and `plan.md` |

Delegated passes return to the coordinator. They do not start other passes.

The coordinator writes `.hive/implementation-loop/handoff.md` before each delegated pass. The pass writes `.hive/implementation-loop/result.md` before returning. The coordinator accepts a pass only when `result.md` names that task and a `pass` or `fail` outcome. A missing result is a failed pass.

Order for each open task in a 4-pack:

1. Coder implements and leaves the work uncommitted.
2. Checker runs. On fail, the coder runs again. Repeat until the checker passes.
3. Reviewer runs.
4. Coordinator updates the task, resets the round-trip count, commits, and pushes only as R5 allows.

One round trip is one delegation plus its return, including a clarification handoff. `state.json` field `round_trips` increments on each one. At 10, the coordinator stops and asks the human before another pass. A new chat reads `state.json` and continues the count. The count resets to `0` only when the task is committed and the next task begins.

The coder records assumptions on that task in `tasks.md`. The coordinator is the only pass that checks the task box, and only after the checker and reviewer results are `pass`.

### R4 — What may change during a task

| Kind of change | Where it goes |
|----------------|---------------|
| What the product must do | Stop. The human updates `spec.md` before coding continues. |
| Build approach only | `plan.md`, in the reviewer or coordinator pass, after the reviewer names the change. |
| Task order only | `tasks.md` |
| How to run or check the project | Retrospective candidates, not during the task |
| Lesson for one role | That role file, only after retrospective approval |

The loop does not run Spec Kit `/specify`, `/plan`, or `/tasks`. If those files are missing, status blocks and the script tells the human to finish specification first.

### R5 — Git

The coordinator commits on the current non-trunk branch after a task passes. The message includes the feature id and the task id.

When `origin` exists and `commands.json` has `"push": true` (the install default when `origin` exists), the coordinator pushes that branch. The first pushed task opens one pull request for the feature when `gh` can see a GitHub remote. Later task commits update that same pull request. The PR URL is stored in `state.json`.

When `origin` is missing, or `"push": false`, the coordinator commits locally and reports that no pull request was opened.

The loop does not merge, does not push to trunk, does not force-push, and does not deploy.

An unrelated dirty tree at start blocks the loop until the human chooses how to handle it. The loop does not stash or discard those changes.

### R6 — Slice pause

A slice is one `##` section in `tasks.md` that contains task checkboxes. When the section has no such heading, the whole file is one slice.

At the end of a slice the coordinator continues to the next task when the reviewer passed and no assumption needs a decision. It pauses for the human when the reviewer marked the slice `needs-sign-off`, or when an assumption is unresolved. A blocking disagreement is asked immediately, in the pass where it appears.

When no unchecked tasks remain, the coordinator sets state `status` to `complete`, asks the human to approve the pull request, and does not add new tasks.

### R7 — Learning

After a feature reaches `status: complete`, the coordinator counts completed features in `retrospective.log`. Lines use `YYYY-MM-DD | completed=N | summary`. The template line does not count.

When `N` has grown by 5 or more since the last log line, the next session runs `.hive/implementation-loop/retrospective.md` before starting another feature. It reviews task notes, results, and commits since the last log line. It keeps lessons that recur. It drops notes that apply to one task only.

Proposals are written to `docs/proposals/implementation-loop-candidates.md` with `# operational` and `# behavioral` sections. The human approves each item.

- Operational items are applied only through the existing `agents-propose` / `agents-apply` path.
- Behavioral items are applied by editing the owning `spec.md`. They are not written into `AGENTS.md`.
- Approved role notes are edited into `.hive/implementation-loop/roles/`.

The coding passes do not modify `AGENTS.md`. The retrospective does not run between tasks of an open feature.

### R8 — Chat start

`is_implementation_loop_request(text)` is true for a request to run this loop, including "implementation loop", "implement the spec", "run the implementation loop", "start the implementation loop", and `/implementation-loop`.

A question about the loop (what it is, where it is installed, whether it is enabled) is not a start signal. Bug-hunt phrases are not a start signal.

The always-on rule tells the agent to read `.cursor/commands/implementation-loop.md` and start in that turn. If several features have open tasks and the message names none, the agent asks which feature. If exactly one feature has open tasks, that feature is the target. If none are ready, the agent reports status and stops.

### R9 — Home

Home **Enable implementation loop** asks for `1-pack` or `4-pack`, then calls the same install function as the CLI on the active linked project. Cancel leaves the project unchanged.

## State

`.hive/implementation-loop/state.json`:

| Field | Meaning |
|-------|---------|
| `feature` | Active feature id, or empty when idle |
| `pack` | `1-pack` or `4-pack` |
| `branch` | Branch the loop is committing to |
| `current_task` | Task id from `tasks.md`, or empty |
| `round_trips` | Delegations on the current task |
| `status` | `idle`, `running`, `blocked`, or `complete` |
| `pr_url` | Open pull request, or empty |
| `slice_signoff` | `continue` or `needs-sign-off` |

`.hive/implementation-loop/commands.json`:

| Field | Meaning |
|-------|---------|
| `build` | Required command |
| `test:quick` | Required fast gate. Includes the wiring audit |
| `test:full` | Required full gate, run at slice end |
| `push` | `true` or `false` |

## Out of scope

- Running the coding loop inside the Python process.
- Generating or replacing Spec Kit specification, plan, or tasks.
- Copilot paths, Copilot model pins, Jarvis or Friday personas, and the `bro` / `yagni` user skills.
- A 5-pack CI tracker, worktree-per-item workflow, and `vibe/` or `wi/` branch names.
- Merge to trunk, deploy, and app restart after commit.
- Installing the loop on every `init_project` without an explicit pack.
- Replacing bug hunt or unified agent handoff.

## Success criteria

- A project with a finished spec, plan, and task list can be installed and reported ready.
- A project missing any R1 input is reported blocked, with the missing input named.
- The installed 4-pack script gives each task its own coder, checker, and reviewer passes, then one commit.
- The installed script forbids merge and deploy in every pack.
- Five completed features produce a proposal file the human must approve before memory or role files change.
- `tests/test_implementation_loop.py` covers install, readiness, the trigger phrase, pack handling, and the prohibitions in the installed text.

## Assumptions

- The target is a Hive project profile with Spec Kit layout.
- The human has finished specification before saying the start phrase.
- Cursor starts each role as its own agent pass. The handoff and result files are the contract between passes.
- "Checker passed" includes the integration wiring audit for that task.
- v1 targets Cursor. A Copilot renderer can be a later feature.

## Source adaptation

Role boundaries, one-task-at-a-time handoffs, the 10-pass cap, human merge and deploy, and the five-feature retrospective are adapted from agentic-loops. Hive replaces that repo's design session, `docs/features/` records, Copilot agent files, and direct guardrail edits with Spec Kit, `tasks.md`, Cursor role files, and Continual Learning.
