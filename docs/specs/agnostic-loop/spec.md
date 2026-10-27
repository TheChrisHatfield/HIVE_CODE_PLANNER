# Spec: agnostic-loop

**Hook:** `workflow.tools`, `spec.flow`, `integration.wiring_audit`  
**Status:** implemented  
**Created:** 2026-10-26  
**Delta:** [agnostic-loop.md](../../delta/20_micro/agnostic-loop.md)

<!-- ROSETTA-NAV -->

## Agent navigation (Rosetta Stone)

1. [`docs/planning-rosetta-stone.md`](../../planning-rosetta-stone.md) — hook `planning.rosetta`
2. Follow **UNLOCKS**: `workflow.tools`, `spec.flow`, `change.validation`
3. This feature — hook `workflow.tools`:
   - **Feature id:** `agnostic-loop`
   - Delta micro: [`agnostic-loop.md`](../../delta/20_micro/agnostic-loop.md)
   - Plan: [`plan.md`](./plan.md)
   - Tasks: [`tasks.md`](./tasks.md)

## What

Hive Planner **installs the portable hive-loop-kit** into a project: scripts, trajectory contract, lay-footnote skill, and a replaceable catalog. Python arms one **reward** (kind of work), opens one **hook** (work item), pauses, and records a review. A Thompson / Monte Carlo tree-search chooser picks the next reward from open counts and hit/miss observations.

This is not the implementation loop and not bug hunt. Those remain separate. Source-repo tables (SeamFlow / UV / training / paper reconstruction) are not shipped. Default rewards are generic pause-cycle work kinds for any Hive-bootstrapped project. Another tool replaces `.hive/agnostic-loop/catalog.json`.

## Layers

| Layer | This feature |
|-------|----------------|
| Holistic | Agents pick the next kind of work with a recorded cycle, not a silent endless chat. |
| Macro | Opt-in kit beside bug hunt and implementation-loop; compiler and cartridge stay unchanged. |
| Micro | Kit files, replaceable catalog, `.hive/agnostic-loop/` state and policy, CLI gates, chat install, Home enable. |

## Requirements

### R1 — Catalog

Default rewards (generic work kinds): `inspect`, `fill`, `extend`, `method`, `infer`, `script`, `goal-infer`, `goal-extend`.

Each reward has a hook list and a one-tick rule stored in `.hive/agnostic-loop/catalog.json`. Tick rules describe one slice of work. They must not mention mining papers, reconstruction, training launches, UV, or a host product. A landed tick may refill other rewards (`refill`). Rollouts prefer `chain` but every reward stays legal at the root. Replacing `catalog.json` is how another tool changes names and hooks.

The catalog must not name SeamFlow, UV seam, training launches, source-kit ids (`boundary`, `fill-unknown`, `train-script`, …), or Hive spec-gap / implement / wiring work ids. Default hook ids are generic (`inspect.00` … `fill.00` …).

### R2 — Gates

Under `--root`, state is `.hive/agnostic-loop/state.json`, reviews `.hive/agnostic-loop/reviews/`, policy `.hive/agnostic-loop/policy.json`.

| Command | Does |
|---------|------|
| `rewards` | List catalog ids |
| `status` | State plus policy means |
| `arm --reward --cycles` | Point a paused sequence at a reward. Cap = completed + cycles. Refuses if status is `running` |
| `begin` | Open one hook. Exit 2 at cap. Refuses a second running cycle |
| `review --note` | Write a review file, advance hook, pause. Exit 2 when the cap is reached |
| `observe --reward --hit\|--miss` | Update the Beta posterior |
| `choose [--open] [--arm]` | MCTS-UCT + Thompson rollouts; optional arm of the first planned reward |

Exit `0` success, `2` cycle cap, `3` refuse. JSON stdout includes `ok` and `action`. Default pause hint is 10 seconds. Default arm cycles is 30.

`arm` / `begin` / `review` do not edit product code, do not commit, and do not run implementation-loop or bug-hunt Python gates.

### R3 — Install

`hive_planner agnostic-loop install` writes the kit:

| Path | Role |
|------|------|
| `scripts/agnostic_loop.py` | Portable engine (same gates as the Hive CLI) |
| `scripts/trajectory_remap.py` | Alias that starts `agnostic_loop.py` |
| `scripts/trajectory-loop.md` | One-tick contract |
| `skills/lay-footnote/SKILL.md` | End-of-reply lay footnote |
| `.hive/agnostic-loop/README.md` | Kit readme |
| `.hive/agnostic-loop/catalog.json` | Reward tables (created only if absent) |
| `.hive/agnostic-loop/loop.md` | Same contract as `trajectory-loop.md` |
| `.cursor/commands/agnostic-loop.md` | Chat script |
| `.cursor/rules/agnostic-loop.mdc` | Always-on start rule |
| `scripts/agnostic-loop.md` | Fallback copy of the command |

`--print` prints the command and writes nothing. Install does not edit `AGENTS.md` or specs. `init_project` does not install this loop unless `--agnostic-loop` is set. Projects may run `py -3.11 scripts/agnostic_loop.py` without importing Hive Planner.

### R4 — Chat and Home

`is_agnostic_loop_request(text)` is true for “agnostic loop”, “hive loop kit”, “run the agnostic loop”, “start the agnostic loop”, `/agnostic-loop`. Questions about the loop are not a start signal. Implementation-loop and bug-hunt phrases are not a start signal.

Home **Enable agnostic loop** calls the same install as the CLI on the linked project. Chat remains valid.

## Out of scope

- SeamFlow / UV / training tables and launching training
- Replacing bug hunt or implementation-loop
- Merge, deploy, force-push
- Python implementing product code or writing reviewer judgments
- Storing lay footnotes in `AGENTS.md`

## Success criteria

- A temp project can install the kit and run `arm` / `begin` / `review` with default generic rewards.
- Replacing `catalog.json` changes reward ids used by `arm`.
- `choose --seed` is deterministic for the same open counts.
- Catalog tests reject SeamFlow ids, source-kit reconstruction language, and Hive spec-gap ids.
- Bug hunt and implementation-loop stay unwired to this module.
