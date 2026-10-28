# Spec: bug-hunt

**Hook:** `change.bugfix_mode`, `integration.wiring_audit`  
**Status:** active  
**Delta:** [bug-hunt.md](../../delta/20_micro/bug-hunt.md)

<!-- ROSETTA-NAV -->

## Agent navigation (Rosetta Stone)

Before implementing, load the hook map — do not jump straight into requirements.

1. [`docs/planning-rosetta-stone.md`](../../planning-rosetta-stone.md) — hook `planning.rosetta`
2. Follow **UNLOCKS**: `change.bugfix_mode`, `integration.wiring_audit`
3. This feature — hook `spec.flow`:
   - Delta micro: [`bug-hunt.md`](../../delta/20_micro/bug-hunt.md)
   - Plan: [`plan.md`](./plan.md)
   - Tasks: [`tasks.md`](./tasks.md)

## What

A core Hive Planner feature that installs the continuous bug-hunt agent script into a project and starts that loop from any Cursor chat when the user asks to hunt bugs.

## Requirements

### R1 — Script text

- `render_agent_prompt(iterations, pause_seconds=None)` describes one inference pass per iteration: rank a location, deep-dive, apply a fix, internal self-review, local commit, write the outcome row, write `.hive/bug-hunt/continue.json`, then end that turn.
- A blank pause is 10 seconds. The stop hook waits that many seconds, and the wait is not skippable. `0` makes the hook start the next pass without waiting. Any positive whole number is the wait in seconds, including a value written as `10.0` or `0.0`. The hook's time limit is raised when that wait is longer than a day, so the wait is not cut off. The hook consumes `continue.json` after the wait and submits the next inference pass, so ending the turn does not stop the hunt. Active false at the start of a pass means that token was used, not that the hunt is over. The agent must not ask whether to continue. When a stop condition is met, the continue file is written with active false and the hook does not start another pass. A committed, skipped, or review-failed outcome resets the empty-search count.
- The default iteration count is 50. That count is a ceiling on committed fixes, not a quota. Controls Fix ceiling starts at 50, and Enable writes that field into the script.
- Before editing, the script ranks locations with a weighted sum (fix-commit churn × 3, a failing or thin test counted once × 5, unwired hop × 5, unread flag × 4, reverted commit × 4, two stores for one fact × 4). Line churn is a tie-break. The sum is not compared to 0.35, and there is no floor until a model exists. A logistic regression on the shared row, fit as committed versus every other outcome, may replace those weights only after 30 completed rows that include both a committed outcome and another outcome. If that fit cannot be made, the weighted sum stays and any signal still qualifies. Its probability picks the next file when the fit exists. The floor is 0.35 and applies only to that probability. Unopened locations are not empty searches.
- Before the edit, the script classifies the named scenario as fix, record-and-skip, or empty. A confirmed bug stays fix, including when the harness is missing. A potential bug that needs a product decision, touches a secret, or has no harness is record-and-skip before any edit. A classifier may use 0.65 and 0.35 on P(real bug) only after 30 rows in `.hive/bug-hunt/rank-rows.jsonl`, and must not override those two rules. Only fix proceeds to the edit. Self-review runs only when a patch exists. A failed review is not an empty search. It is `skipped` only when the outcome order already chose `skipped` (record-and-skip, product decision, or secret). Every other failed review restores that iteration's uncommitted edits and is `review-failed`.
- Each opened location appends one row (file, signals, scenario, outcome) to `.hive/bug-hunt/rank-rows.jsonl` once, after the outcome is known. Outcome is `committed`, `skipped`, `empty`, or `review-failed`. A failed review is `skipped` only when the outcome order already chose `skipped`. Every other failed review is `review-failed`. The location model treats only `committed` as positive. The classifier treats `committed` and `review-failed` as a real bug. The next hunt reads that file and may append a new row for a location this run already recorded. The queue opens the highest qualifying score only.
- After the patch, the script ranks tests from past diffs on the same files and runs the top of that list. The ranker orders the harness. The self-review gate still decides the commit.
- The loop stops at the ceiling, after two consecutive empty searches, or when no unopened location still qualifies. An empty search is an opened location classified empty, or an opened location with neither a confirmed bug nor a potential bug. Record-and-skip and `review-failed` are not empty searches. An empty outcome restores that iteration's uncommitted edits and does not commit.
- A product decision or a secret is recorded as `skipped` and is not committed, including when the review fails or the patch cannot be covered. An uncoverable or failed patch that is not a secret or a product decision is `review-failed` and is not committed. A passing review commits only when none of those exceptions apply. If that local commit fails, the outcome is `review-failed` and that iteration's uncommitted edits are restored.
- The script forbids push and forbids filling the budget with invented bugs.

### R2 — Install

- `hive_planner bug-hunt` writes `.cursor/commands/bug-hunt.md`, `.cursor/rules/bug-hunt.mdc`, `.hive/bug-hunt/AGENT_PROMPT.md`, `scripts/bug-hunt.md`, and `.cursor/hooks/bug_hunt_continue.py` under `--root`. It adds that hook to `.cursor/hooks.json` on `stop` without removing other hook events.
- The rule is `alwaysApply` and treats a chat request to perform a bug hunt as the start signal for the script.
- `--iterations` accepts 1 through 200.
- `--pause-seconds` accepts 0 or any positive whole number the stop hook can wait (not larger than the platform sleep limit). The default is 10. `0` skips the wait.
- `--print` writes nothing and prints the script.

### R3 — Wiring

- The CLI command calls `install_bug_hunt`. A successful run leaves the command, the always-on rule, the packet, and the stop hook on disk. The command and packet contain the requested iteration count and the pause seconds for that run. The hook reads `.hive/bug-hunt/continue.json` from the working directory or a parent directory, waits `pause_seconds` when that file is active (`true`, `1`, or the word true; `0` does not wait; a missing pause is taken from the installed script before the 10-second default), clears active after the wait, and returns `followup_message` so the next turn is the next iteration. Each pass writes `ceiling`, `committed`, and `consecutive_empty` beside `active` and `pause_seconds`. The hook honors those counters even when `active` was left true by a crash: at the ceiling or at two consecutive empty outcomes it clears the token and does not start another pass. A broken `.cursor/hooks.json` fails a direct install before the script files are replaced. Init and handoff deploy replace that broken file when force is set, then install the stop hook onto the replacement.
- `init_project` and `deploy_agent_handoff_scaffold` install the same artifacts so new and upgraded Hive projects can start hunts from chat. Those installs use the default pause of 10 seconds.
- Home **Loop controls** opens the Controls tab. Controls **Bug hunt → Enable → Run** calls `run_project_bug_hunt_install` on the active linked project. Fix ceiling and Pause seconds are fields on that block. A blank Pause seconds field installs 10. `0` installs a script that does not wait. `hive_bug_hunt_enable` accepts `pause_seconds`. When that argument is omitted, the enable keeps the pause already written in the installed script, and uses 10 only when no script pause is found.

### R4 — Chat start signal

- `is_bug_hunt_request(text)` is true for explicit phrases and derivatives whose meaning is to run a hunt: "bug hunt", typos ("bug hun", "bung hunt"), hyphenation, `/bug-hunt`, "hunt for bugs", "start hunting bugs", "run a bug hunt", "run another loop to fix bugs", "loop to fix bugs".
- A question about the command itself (whether it works, where the file is, how to install it) is not a start signal. A review, summary, audit, or explanation request for the script is not a start signal unless that same message then starts a hunt ("read the bug hunt command and start a bug hunt"). A negation or stop request ("do not run the bug hunt", "stop the bug hunt", "skip the bug hunt", "never bug hunt", "do not loop to fix bugs") is not a start signal and must not restart the loop. "end to end bug hunt" and a start after another clause ("stop explaining and run a bug hunt") are start signals.
- The always-on rule tells the agent to read `.cursor/commands/bug-hunt.md` (fallback `scripts/bug-hunt.md`) and start the loop in the same turn — not to explain how to invoke it.

## Out of scope

Running the hunt inside Hive planner, auto-commit of product code, and remote upload.
