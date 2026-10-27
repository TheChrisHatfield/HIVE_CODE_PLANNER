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

- `render_agent_prompt(iterations)` describes an autonomous loop: deep-dive, apply a fix, internal self-review, local commit, then the next iteration without waiting for the user.
- The agent must not stop after one bug to ask whether to continue. The only pause is that internal review.
- The default iteration count is 50.
- The loop repeats until that count of reviewed fixes, or until two consecutive search areas yield no real bug (satisfactory to stop — not invented work).
- The script forbids push and forbids filling the budget with invented bugs.

### R2 — Install

- `hive_planner bug-hunt` writes `.cursor/commands/bug-hunt.md`, `.cursor/rules/bug-hunt.mdc`, `.hive/bug-hunt/AGENT_PROMPT.md`, and `scripts/bug-hunt.md` under `--root`.
- The rule is `alwaysApply` and treats a chat request to perform a bug hunt as the start signal for the script.
- `--iterations` accepts 1 through 200.
- `--print` writes nothing and prints the script.

### R3 — Wiring

- The CLI command calls `install_bug_hunt`. A successful run leaves the command, the always-on rule, and the packet on disk. The command and packet contain the requested iteration count.
- `init_project` and `deploy_agent_handoff_scaffold` install the same artifacts so new and upgraded Hive projects can start hunts from chat.
- Home **Enable bug hunt** calls `run_project_bug_hunt_install` on the active linked project.

### R4 — Chat start signal

- `is_bug_hunt_request(text)` is true for explicit phrases and derivatives whose meaning is to run a hunt: "bug hunt", typos ("bug hun", "bung hunt"), hyphenation, `/bug-hunt`, "hunt for bugs", "start hunting bugs", "run a bug hunt", "run another loop to fix bugs", "loop to fix bugs".
- A question about the command itself (whether it works, where the file is, how to install it) is not a start signal.
- The always-on rule tells the agent to read `.cursor/commands/bug-hunt.md` (fallback `scripts/bug-hunt.md`) and start the loop in the same turn — not to explain how to invoke it.

## Out of scope

Running the hunt inside Hive planner, auto-commit of product code, and remote upload.
