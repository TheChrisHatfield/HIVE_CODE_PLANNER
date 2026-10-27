# START_HERE

Loader entrypoint for coding agents in this repository. Load these files into the **normal context window** (via `@` references or rules)—not as copy-paste blocks.

## First retrieval step

When planning or coding, search for **Planning Rosetta Stone** or hook `planning.rosetta`:

1. [`docs/planning-rosetta-stone.md`](docs/planning-rosetta-stone.md) — top-level legend and hook index
2. [`docs/thread-outline-with-metatags.md`](docs/thread-outline-with-metatags.md) — meta-tag anchor map
3. [`AGENTS.md`](AGENTS.md) — durable repo operating guidance

Raw planning source archive: [`docs/HIVE_PLANNING_DEV.md`](docs/HIVE_PLANNING_DEV.md)

## Read order

Before implementation decisions:

1. `docs/planning-rosetta-stone.md` (hook `planning.rosetta`)
2. `docs/thread-outline-with-metatags.md`
3. `AGENTS.md`
4. `docs/delta/00_holistic.md` (when present)
5. `docs/delta/10_macro.md` (when present)
6. active `docs/delta/20_micro/<feature>.md` (when present)
7. active `docs/specs/<feature>/spec.md`, `plan.md`, `tasks.md` (when present)
8. **secondary long docs** per hook — see `.cursor/rules/deep-context-secondary.mdc` (deep detail after hooks)
9. active change-impact packet in `docs/change-impact/impact-packets/` (when present)
10. `source-context.md` only if tertiary reference is needed

## Secondary deep context

After hooks, load long-form docs for synthesis detail: `.cursor/rules/deep-context-secondary.mdc`

Trigger: **deep context**, **secondary lookup**, **long docs after hooks**

## Context priority

- **Primary:** Delta docs + active spec/plan/tasks + active micro brief
- **Secondary:** `AGENTS.md` + `.cursor/rules/` + long docs per hook (after Rosetta lookup)
- **Tertiary:** `source-context.md` or other document-sourced excerpts

Tertiary context must not override primary task truth.

## Rosetta stone role

`docs/planning-rosetta-stone.md` is the searchable legend. Use its `HOOK_ID` values to map questions, tasks, and changes to the right concept instead of inferring structure from raw chat or the full planning archive.

To **author or extend** a Rosetta Stone (any agentic system), follow [`docs/planning-rosetta-stone-generation-template.md`](docs/planning-rosetta-stone-generation-template.md).

To **upload to Perplexity / Gemini / ChatGPT** at the start of a planning session, upload [`docs/ROSETTA-PLANNING-SESSION-CONTRACT.md`](docs/ROSETTA-PLANNING-SESSION-CONTRACT.md) (standalone — inline markers + Rosetta output rules).

## Agnostic loop

Opt-in pause-cycle chooser: `py -3.11 -m hive_planner agnostic-loop install` copies the hive-loop-kit, or Home **Enable agnostic loop**. Then `arm` / `begin` / `review` / `choose` (CLI or `scripts/agnostic_loop.py`). Replace `.hive/agnostic-loop/catalog.json` for another tool. Not bug hunt and not the implementation loop. Spec: [`docs/specs/agnostic-loop/spec.md`](docs/specs/agnostic-loop/spec.md).

## Implementation loop

After `spec.md`, `plan.md`, and `tasks.md` exist, install the opt-in coding loop with `py -3.11 -m hive_planner implementation-loop install --pack 4-pack` (or `1-pack`), or Home **Enable implementation loop**. Run gates from chat (**implementation loop**) or Home **Loop status / start / handoff / check / accept / commit**. Spec: [`docs/specs/implementation-loop/spec.md`](docs/specs/implementation-loop/spec.md).

## Execution rule

Before editing code:

- identify the active feature and task
- map it to one or more `HOOK_ID` values from the Rosetta Stone
- identify primary, secondary, and tertiary change implications
- confirm which files define execution truth for the current task

## Fallback behavior

If a concept is unclear:

1. check `docs/planning-rosetta-stone.md`
2. check `docs/thread-outline-with-metatags.md`
3. check Delta docs (when present)
4. check current spec and plan (when present)
5. only then consult `docs/HIVE_PLANNING_DEV.md` or tertiary source context

## Memory rule

Only promote durable repeated truths into `AGENTS.md`. Do not treat session-local discussion as durable memory unless distilled into repo files.
