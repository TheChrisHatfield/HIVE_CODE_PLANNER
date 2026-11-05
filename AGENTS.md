# AGENTS.md — Hive Code Planner

Durable operating guidance for agentic coding in this repo.

## Repository root

`<path to your HIVE_CODE_PLANNER checkout>`

## Planning Rosetta Stone (required anchor)

Before planning or coding, load the Rosetta Stone into normal context:

- **Search phrase:** `Planning Rosetta Stone`
- **Hook ID:** `planning.rosetta`
- **File:** `docs/planning-rosetta-stone.md`

Follow linked hooks and `PRIMARY FILES` from that document. Do not treat the raw Perplexity export as the only source of truth.

To generate or extend a Rosetta Stone from another agentic system, use [`docs/planning-rosetta-stone-generation-template.md`](docs/planning-rosetta-stone-generation-template.md).

## Startup read order

See [`START_HERE.md`](START_HERE.md).

1. `docs/planning-rosetta-stone.md`
2. `docs/thread-outline-with-metatags.md`
3. This file
4. Active Delta / spec / task artifacts (when present)
5. **Secondary long docs** (after hooks): `.cursor/rules/deep-context-secondary.mdc` — outline-first read by `HOOK_ID`

## Delta model

Three-level context structure:

- **Holistic** — mission, goals, constraints, invariants, non-goals
- **Macro** — architecture, modules, workflows, interfaces, contracts
- **Micro** — feature scope, tasks, files, tests, edge cases

## Tool roles

- **Perplexity** — upstream research and blueprint planning
- **Spec Kit** — specification, clarification, plan, tasks
- **Cursor** — implementation with rules and memory
- **Continual Learning** — promote only high-signal durable facts into this file

## Context truth layers

- **Primary:** active Delta docs, spec, plan, tasks, micro brief
- **Secondary:** `AGENTS.md`, `.cursor/rules/`, long docs per hook (see `deep-context-secondary.mdc`)
- **Tertiary:** document-sourced excerpts (`source-context.md`, context library)

Primary truth drives the immediate task. Secondary governs behavior. Tertiary is optional grounding only.

## Execution guardrails

- Work from one active micro task when possible
- Map work to `HOOK_ID` values before editing
- Update spec before behavior changes; update plan for approach changes; update tasks for sequencing only
- Do not promote transient chat into durable memory without distillation and review

## Active feature

Two lanes may be active at once. Each lane names one feature. A feature that is not listed is not active.

- **bug-hunt** — sampled detector trust and place attention (R9). Open tasks R5/R6 and R9.
- **controls-execute** — Controls Execute button. Open tasks T004–T009.
- **implementation-loop** — file-overlap gate. Open task T030.

A lane is ready when its feature is listed here and its own spec, plan, and tasks exist. Listing a lane does not start it. Two lanes that declare the same plan file still need `--allow-overlap` to start. Force feature does not grant that.
## Planning source archive

Full thread export (reference only): `docs/HIVE_PLANNING_DEV.md`

## Durable Workspace Facts

- Use Python 3.11 for local development (`py -3.11`).
- Stage 4C adds proposal-only AGENTS.md memory lint/propose; guarded `agents-apply` enabled in v2.
- Stage 5A syncs Delta holistic/macro/micro into cartridge on emit; skips draft/manual files unless `--force-delta`.
- Stage 5B adds `impact-sync-maps` to merge src/test discovery into change-impact maps without overwriting curated rows.
- Stage 5C adds `ci-check` for handoff validation (pytest, agents-lint, spec artifacts, map drift, spec-drift).
- Stage 6A adds full cartridge pack emit (research-summary, memory, specseed, source-map).
- v1.0.0 — Stages 1–6 compiler roadmap complete; use `roadmap-status` to verify.
- v1.1.0 — Stage 7 complete (CL/spec integration, memory v2, rule seeds, impact v3, project bootstrap); `roadmap-status` validates 18/18 features.
- v1.2.0 — Stage 8 complete (starter-kit v2 full profile, path/feature validation hardening); `roadmap-status` validates 20/20 features.
- v1.3.0 — Stage 9 complete (unified Spec Kit + CL vendored deploy); `roadmap-status` validates 22/22 features; use `unified-verify` on bootstrapped projects.
- `hive_planner init` must target a directory outside the Hive source tree (never a subdirectory of this repo). # operational
- Bootstrapped projects use plain `None` for active feature until the first real feature id is set.
- Starter-kit v2 (`--profile full`) adds pyproject, src/tests layout, `.gitignore`, and GitHub CI stub; `--git-init` is optional.
- Cursor 3.x project/plugin hooks must emit JSON on stdout (`additional_context` / `followup_message` / `{}`); plain text causes parse errors. # operational
- Hive Continual Learning stop hook runs via `py -3.11` (not Bun); `afterFileEdit` matchers use tool types (`Write|TabWrite`), not file paths. # operational
- Cursor 3.x loads project plugins via `workspaceOpen` `pluginPaths` (see `.cursor/hooks/hive_workspace_open.py`); `.cursor/plugins/` alone is not auto-discovered. # operational
- Bug hunts: `py -3.11 -m hive_planner bug-hunt` writes the command, rule, packet, and stop hook. The hook waits that run's pause and starts the next pass. # operational
- Implementation loop: `py -3.11 -m hive_planner implementation-loop install --pack {1-pack|4-pack}` then status, start, handoff, check, accept, and commit. Chat `code spec` starts it. # operational
- Agnostic loop: `py -3.11 -m hive_planner agnostic-loop install`, then rewards, arm, begin, review, observe, choose, and status. `init` adds it only with `--agnostic-loop`. # operational
- Hive Planner MCP: `py -3.11 -m hive_planner mcp-serve`. Settings → Agent MCP → Enable writes `hive-planner` into the project's `.cursor/mcp.json`. # operational
