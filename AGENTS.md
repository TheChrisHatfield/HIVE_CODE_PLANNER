# AGENTS.md — Hive Code Planner

Durable operating guidance for agentic coding in this repo.

## Repository root

`d:\DRIVE_DOWNLOADS\HIVE_CODE_PLANNER`

## Planning Rosetta Stone (required anchor)

Before planning or coding, load the Rosetta Stone into normal context:

- **Search phrase:** `Planning Rosetta Stone`
- **Hook ID:** `planning.rosetta`
- **File:** `docs/planning-rosetta-stone.md`

Follow linked hooks and `PRIMARY FILES` from that document. Do not treat the raw Perplexity export as the only source of truth.

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

**roadmap-complete-v1** — Stages 1–6 roadmap complete (v1.0.0).

Roadmap validation (Stage 6B):

```powershell
py -3.11 -m hive_planner roadmap-status
py -3.11 -m hive_planner ci-check
```

Cartridge pack emit (Stage 6A):

```powershell
py -3.11 -m hive_planner emit --feature cartridge-pack-v1 --force-delta
```

Handoff CI (Stage 5C):

```powershell
py -3.11 -m hive_planner impact-sync-maps
py -3.11 -m hive_planner ci-check
py -3.11 -m hive_planner ci-check --allow-map-drift
```

Impact map sync (Stage 5B):

```powershell
py -3.11 -m hive_planner impact-sync-maps --dry-run
py -3.11 -m hive_planner impact-sync-maps
```

Delta cartridge sync (Stage 5A):

```powershell
py -3.11 -m hive_planner emit --feature cartridge-delta-emit-v1
py -3.11 -m hive_planner emit --feature cartridge-delta-emit-v1 --force-delta
```

Hybrid retrieval (Stage 4D):

```powershell
py -3.11 -m hive_planner ingest --embed
py -3.11 -m hive_planner emit --feature embedding-retrieval-v1
```

Memory CI (Stage 4C):

```powershell
py -3.11 -m hive_planner agents-lint
py -3.11 -m hive_planner agents-propose --candidates docs/proposals/example-candidates.md
py -3.11 -m hive_planner agents-apply --candidates docs/proposals/example-candidates.md
py -3.11 -m hive_planner agents-ingest --from path/to/export.txt
py -3.11 -m hive_planner spec-drift-check
py -3.11 -m hive_planner spec-drift-check --candidates docs/proposals/candidates-template.md
```

Translator (Stage 4B):

```powershell
py -3.11 -m hive_planner translate --input docs/delta/20_micro/cartridge-compiler-v3.md --feature cartridge-translator-v1
```

Compiler (Stage 4A):

```powershell
py -3.11 -m pip install -e ".[dev,pdf,docx,html,pptx]"
py -3.11 -m hive_planner ingest
py -3.11 -m hive_planner emit --feature cartridge-compiler-v3
```

Change impact (Stage 3):

```powershell
py -3.11 -m hive_planner impact --feature change-impact-v1 --files src/hive_planner/impact.py
```

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
