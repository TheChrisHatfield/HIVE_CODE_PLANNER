# Spec: implementation-loop

**Hook:** `spec.flow`, `workflow.tools`, `integration.cl_spec`, `integration.wiring_audit`  
**Status:** implemented  
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

The Python CLI installs the loop, reports whether a feature is ready, and enforces coordinator gates (`start`, `handoff`, `check`, `accept`, `commit`). It does not implement the feature and does not write reviewer judgments. `check` runs the checker infrastructure (R10).

## Layers

| Layer | This feature |
|-------|----------------|
| Holistic | Coding agents implement finished specs with less drift. Spec Kit stays the behavioral contract. |
| Macro | Agent loader gains an opt-in execution loop after Spec Kit. Unified handoff and bug hunt stay in place. |
| Micro | Install role prompts, a chat start rule, a readiness gate, and a retrospective that proposes memory updates. |

## User stories

### US1 — Install and readiness (P1)

A person enables the loop on a Hive project, picks a pack, and can see whether a named feature is ready to code.

**Independent test:** install into a temp project and run status. Ready means R1: project profile, spec, plan, tasks, micro brief, one open task, pack, non-trunk branch, and non-empty `build`, `test:quick`, and `test:full`. A feature missing `tasks.md` is blocked. All boxes checked with the other inputs present is `status: complete` and exit 0.

### US2 — One task, several passes (P1)

After the start phrase, the coordinator gives one open task to the coder, then the checker, then the reviewer. Each returns before the next starts. The coordinator commits only after the checker and the reviewer pass.

**Independent test:** installed 4-pack command and role files describe that order, the handoff file, the 10-pass cap, and commit ownership. `check` writes a checker `result.md` entry from `build` / `test:quick`. Status tracks round trips in `state.json`.

### US3 — Solo pack (P2)

A 1-pack uses one coordinator pass that designs nothing new, implements the task, runs the gates, and commits. Lane separation is waived only in that pack.

**Independent test:** a 1-pack install names only the coordinator as the executing role and still forbids merge and deploy.

### US4 — Learning between features (P2)

Every five completed features, the loop proposes durable lessons. The human approves them before they are written. Operational notes go through Continual Learning. Behavioral notes go to the spec.

**Independent test:** retrospective text states the count of five, the proposal file, and the ban on editing `AGENTS.md` inside a coding task.

### US5 — Start from chat or Home (P2)

Saying the start phrase in a project chat starts the loop in that turn. Home **Loop controls** opens the Controls tab. After install, Controls **Run** (Status / Start / Handoff / Check / Accept / Commit) calls the same Python coordinator gates as the CLI, so the user can click or type. Project init does not install it unless a pack is passed.

**Independent test:** trigger matcher, Home install call, Home gate wrappers call the same coordinator functions as the CLI, and init without a pack leaves the loop files absent.

### US6 — Python strict coordinator (P1)

The agent must not commit, increment round trips, or write the handoff by hand. Python owns those gates and the checker command (`check`). Cursor still implements and reviews.

**Independent test:** `start` blocks unrelated dirty paths; `handoff` stops at 10 round trips; `commit` refuses without checker and reviewer `pass` (4-pack: those passes must follow the last coder); a valid commit checks the task box and leaves `.hive/implementation-loop/` unstaged.

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

Trunk is `git symbolic-ref --short refs/remotes/origin/HEAD` when that ref exists. Strip a leading `origin/` so `origin/main` matches branch `main`. Otherwise trunk is `main` if that branch exists, else `master`.

Status exit code is `0` when ready **or** when the feature is `complete` (every box checked and the other R1 files exist). Exit `2` when blocked. The blocked message names each missing piece. The command does not create spec, plan, or tasks. Status JSON includes `round_trips`, `current_task`, `pack`, `pr_url`, and `state_status` from `state.json` when that file exists.

Install is allowed on trunk. Readiness still blocks until the current branch is not trunk.

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

Reinstall of the same pack refreshes prompts (including `retrospective.md` and role files), the command, and the rule. It keeps `state.json`, `retrospective.log`, and an existing handoff or result file. It fills only **empty** `commands.json` strings from discovery. It never clears a human-set command value.

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

The coordinator writes `.hive/implementation-loop/handoff.md` before each delegated pass. Fields: feature, task (id if present, else the checkbox line text plus its `##` heading), role, repo root, and the spec/plan/tasks paths.

`result.md` is a list of role outcomes for the **current** task. Each entry has `task`, `role`, `outcome`, `evidence`, and `question` when `outcome` is `fail`. A later pass **appends**. It does not overwrite. The coordinator replaces `result.md` when the next task's handoff is written, and when a new feature's first handoff is written. The coordinator accepts a pass only when an entry for that task and role exists with `pass`, `fail`, or `needs-sign-off`. A missing result is a failed pass.

Python `implementation-loop check` is the checker infrastructure: it runs `build` and `test:quick` from `commands.json`, then the wiring audit when that project enforces it, and **appends** a checker `result.md` entry. Cursor still implements and reviews. Bug hunt stays a separate loop. The 1-pack coordinator does not write `coder.md`, `checker.md`, or `reviewer.md`; it still calls `check` for the checker result and writes its own reviewer entry.

A role with a blocking question returns `fail` with `question` set. The coordinator asks the human, then re-hands the same role. That re-handoff counts as one round trip. The 10-pass cap is checked **before every** delegation, including a re-handoff. Checker or reviewer `fail` without `question` returns to the coder, then checker, then reviewer. `needs-sign-off` pauses for the human and does not start the coder.

Order for each open task in a 4-pack:

1. Coder implements and leaves the work uncommitted.
2. Checker runs via `implementation-loop check` (Home **Loop check**). On fail, the coder runs again. Repeat until the checker passes.
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

The coordinator commits on the current non-trunk branch after a task passes. The message is `implementation-loop <feature> <task-id-or-slug>`.

Commit the task's product files, `tasks.md`, and any approved `plan.md` edit. Leave `.hive/implementation-loop/` runtime files unstaged.

Unrelated dirty paths at loop **start** block until the human chooses. Paths under `.hive/implementation-loop/` and paths this task touched are expected dirt. The loop does not stash or discard unrelated changes.

When `origin` exists and `commands.json` has `"push": true` (the install default when `origin` exists), the coordinator pushes that branch. The first pushed task opens one pull request for the feature when `gh` can see a GitHub remote. Later task commits update that same pull request. The PR URL is stored in `state.json`.

When `origin` is missing, or `"push": false`, the coordinator commits locally and reports that no pull request was opened.

A push failure keeps the commit, sets `status` to `blocked`, and asks the human. It does not retry silently.

The loop does not merge, does not push to trunk, does not force-push, and does not deploy.

### R6 — Slice pause

Each `##` section that contains a checkbox is a slice. A heading with no checkboxes is not a slice. If no such heading exists, the whole file is one slice.

At the end of a slice run `test:full`. On failure, set `status` to `blocked`, keep the commits, add no repair task, and ask the human.

The coordinator continues to the next task when the reviewer passed and no assumption is unresolved. It pauses when the reviewer marked `needs-sign-off`, or when a task line still has `Assumption: unresolved`. Assumptions are marked `Assumption:` on the task line.

When no unchecked tasks remain, the coordinator sets `status` to `complete`, appends `YYYY-MM-DD | completed=N | feature-id` to `retrospective.log` (header comment does not count; only date lines count), and asks for pull-request approval only when `pr_url` is set. Otherwise it asks for local merge approval. It does not add new tasks.

### R7 — Learning

After a feature reaches `status: complete`, the coordinator counts completed features in `retrospective.log`. Lines use `YYYY-MM-DD | completed=N | summary`. The template line does not count.

When completed-feature count `N` is at least 5 more than `last_retrospective_n`, the next session runs `.hive/implementation-loop/retrospective.md` before starting another feature. It reviews task notes, results, and commits since the last log line. It keeps lessons that recur. It drops notes that apply to one task only.

Proposals are written to `docs/proposals/implementation-loop-candidates.md` with `# operational` and `# behavioral` sections. The human approves each item.

- Operational items are applied only through the existing `agents-propose` / `agents-apply` path.
- Behavioral items are applied by editing the owning `spec.md`. They are not written into `AGENTS.md`.
- Approved role notes are edited into `.hive/implementation-loop/roles/`.

The coding passes do not modify `AGENTS.md`. The retrospective does not run between tasks of an open feature.

### R8 — Chat start

`is_implementation_loop_request(text)` is true for a request to run this loop, including "implementation loop", "implement the spec", "run the implementation loop", "start the implementation loop", `/implementation-loop`, "code spec", "CodeSpec", and "code-spec".

A question about the loop (what it is, where it is installed, whether it is enabled) is not a start signal, including when that question is not at the start of the message. Bug-hunt phrases are not a start signal.

The always-on rule tells the agent to read `.cursor/commands/implementation-loop.md` and start in that turn. If several features have open tasks and the message names none, the agent asks which feature. If exactly one feature has open tasks, that feature is the target. If none are ready, the agent reports status and stops.

### R9 — Home

Home **Loop controls** opens the Controls tab. Controls **Implementation loop → Enable → Run** asks for `1-pack` or `4-pack` (pack field on the tab), then calls the same install function as the CLI on the active linked project. Same pack refreshes prompts. A different pack asks before `--force-pack`. Cancel leaves the project unchanged. Controls **Run** also runs coordinator gates (`status` / `start` / `handoff` / `check` / `accept` / `commit`) against the active repo.

Typing **code spec** (any case) in the Controls Loop box selects CodeSpec, swaps the command list, and shows the pack field. Controls **Install CodeSpec** finds the front-most Cursor window (or Cursor's most recent workspace), links that folder, selects CodeSpec, keeps the pack already on the block, folds settings (Compact does not write or start coding), then runs Enable. There is no Close button.

Feature id defaults from AGENTS.md Active feature when the field is left blank. Start uses Allow dirty start and Force feature on the tab. Handoff uses Continue after cap. The CodeSpec block does not ask for a role. It lists the pack's steps and marks the step that is running or stopped. Handoff and Accept take the role for that step. Chat remains valid: the Agent prompt template **Start the implementation loop** and the always-on phrase still start the loop without using Home.

### R10 — Python coordinator gates

Python enforces coordinator rules. It does not edit product code and does not write reviewer judgments. It **does** run the checker infrastructure (`implementation-loop check`): `build`, `test:quick`, and the wiring audit when enforced, then appends the checker `result.md` entry from those exits.

| Command | Does |
|---------|------|
| `implementation-loop start --feature <id>` | Readiness must be ready. Unrelated dirty paths block (`--allow-dirty` after the human chooses). Paths under `.hive/` are expected dirt. Sets `status` to `running`, `feature`, `branch`, and `current_task` to the first open checkbox. A different running feature blocks unless `--force-feature`. `status` `blocked` (push or slice `test:full` failure) blocks start unless `--force-feature` after the human agrees. When every box is already checked, sets `complete`, appends the retrospective line if missing, and does not start work. |
| `implementation-loop handoff --role <role>` | Writes `handoff.md` for the **current** task (not merely the first open checkbox). Replaces `result.md` on the first coder/coordinator handoff of a task. Increments `round_trips`. At 10, blocks unless `--continue-after-cap`. The role name is not rejected for belonging to the other pack (role names are case-insensitive). Checker requires last coder `pass`. Reviewer requires last checker `pass` **after** the last coder (a recode invalidates the previous checker). Checker or reviewer `fail` without `question` requires the next handoff to be `coder`; after that coder result, checker then reviewer are allowed again. A `fail` with `question` re-hands the same role. Checker or reviewer `needs-sign-off` forbids a coder handoff. Current branch must match `state.branch`. Detached `HEAD` is not a branch. Feature comes from `state.json`. Controls passes the role for the step on the CodeSpec block. |
| `implementation-loop check` | Runs the checker infrastructure for the current task. 4-pack: last coder outcome must be `pass`; checker or reviewer `fail` without `question` still returns to the coder first. 1-pack: loop must be running. Runs `build`, then `test:quick`, then `wiring-audit check` when that project enforces the audit. Appends a checker `result.md` entry (`pass` or `fail`) with command evidence. `ok` is false and the CLI exits 2 when the checker outcome is `fail` (the entry is still written). Does not increment `round_trips`, does not edit product code, and does not write a reviewer entry. Then `accept --role checker` as today. |
| `implementation-loop accept --role <role>` | Passes only when `result.md` has an entry for this task and role with `outcome` `pass`, `fail`, or `needs-sign-off`. Missing is a failed pass (exit 2). A role is not rejected for belonging to the other pack. `needs-sign-off` sets `slice_signoff`. Checker or reviewer `fail` without `question` sets `next_role` to `coder`. A `fail` with `question` sets `next_role` to the same role. Controls accepts the latest result for the current task. |
| `implementation-loop commit` | Refuses when the current branch is trunk or is not `state.branch`. Requires last checker and last reviewer `pass` for the current task. In 4-pack, that checker `pass` must be after the last coder, and that reviewer `pass` after the last checker. Blocks on `Assumption: unresolved`, `needs-sign-off`, or a dirty `AGENTS.md`. Checks off the **current** task, commits new product files plus `tasks.md` and changed `plan.md`, leaves `.hive/` unstaged, skips paths dirty at `start` and tool caches, resets `round_trips` to 0. If `git add` or `git commit` fails, restore the previous `tasks.md` checkbox and do not keep a partial checkoff. Message is `implementation-loop <feature> <task-id-or-slug>`. Does not merge, force-push, or push to trunk. When `push` is true and `origin` exists, pushes the current branch; on failure keeps the commit, sets `blocked`, does not advance `current_task`, and does not retry. After the first successful push, if `pr_url` is empty, run `gh pr create` when `gh` is available; store the URL in `state.json`. If `gh` is missing, leave `pr_url` empty and do not raise. Slice-end `test:full` failure (including a missing executable or a malformed command string) keeps the commit, sets `blocked`, and does not advance `current_task` or append a retrospective line. `handoff` and `accept` treat role names as case-insensitive. Advance to the next task (or `complete`) only after push and slice `test:full` succeed. When completed-feature count is at least 5 more than `last_retrospective_n`, write `docs/proposals/implementation-loop-candidates.md` if missing (`# operational` and `# behavioral`), set `last_retrospective_n`, and set `next_role` to `retrospective`. |

Exit `0` on success. Exit `2` on a gate block. JSON stdout includes `ok`, `action`, `feature`, `task`, `role`, `round_trips`, `blocked_reason`.

Installed coordinator and command text tell the agent to call these commands. The agent still runs coder and reviewer passes. Python runs the checker command gates and appends the checker `result.md` entry.

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
| `baseline_dirty` | Paths that were dirty at `start` (not under `.hive/`). `commit` does not stage these except `tasks.md` / `plan.md` |
| `last_retrospective_n` | Completed-feature count at the last retrospective stub |

`.hive/implementation-loop/commands.json`:

| Field | Meaning |
|-------|---------|
| `build` | Required command |
| `test:quick` | Required fast gate (tests). The wiring audit is a separate checker checklist, not this command |
| `test:full` | Required full gate, run at slice end |
| `push` | `true` or `false` |

## Out of scope

- Running **coder** or **reviewer** duties inside the Python process (implementing product code or judging the spec). Checker infrastructure in R10 (`check`) is in scope. Coordinator gates in R10 are in scope.
- Generating or replacing Spec Kit specification, plan, or tasks.
- Copilot paths, Copilot model pins, Jarvis or Friday personas, and the `bro` / `yagni` user skills.
- A 5-pack CI tracker, worktree-per-item workflow, and `vibe/` or `wi/` branch names.
- Merge to trunk, deploy, and app restart after commit.
- Installing the loop on every `init_project` without an explicit pack.
- Replacing bug hunt or unified agent handoff.

## Success criteria

- A project with a finished spec, plan, and task list can be installed and reported ready.
- A project missing any R1 input is reported blocked, with the missing input named.
- The installed 4-pack script gives each task a coder pass, a Python checker (`build` / `test:quick` / wiring audit), a reviewer pass, then one commit.
- The installed script forbids merge and deploy in every pack.
- Five completed features produce a proposal file the human must approve before memory or role files change.
- `tests/test_implementation_loop.py` covers install, readiness, the trigger phrase, pack handling, and the prohibitions in the installed text.
- Coordinator gate tests cover dirty-tree start, the 10-pass cap, refused commit, and a successful commit that checks the task box.

## Assumptions

- The target is a Hive project profile with Spec Kit layout.
- The human has finished specification before saying the start phrase.
- Cursor starts each role as its own agent pass. The handoff and result files are the contract between passes.
- "Checker passed" includes the integration wiring audit for that task.
- v1 targets Cursor. A Copilot renderer can be a later feature.

## Source adaptation

Role boundaries, one-task-at-a-time handoffs, the 10-pass cap, human merge and deploy, and the five-feature retrospective are adapted from agentic-loops. Hive replaces that repo's design session, `docs/features/` records, Copilot agent files, and direct guardrail edits with Spec Kit, `tasks.md`, Cursor role files, and Continual Learning.
