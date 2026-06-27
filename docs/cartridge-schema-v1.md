<!--
meta:hook_id: context.cartridge_schema
meta:source: HIVE_PLANNING_DEV.md
meta:status: extracted
-->

# Cartridge Schema v1

This schema defines a portable context cartridge that translates Perplexity research into repo-native artifacts for Cursor, Spec Kit, and durable agent memory. The design fits Spec Kit’s spec-driven workflow and Cursor’s context model built around reusable rules plus `AGENTS.md`-style durable guidance.[^6_1][^6_2][^6_3]

## Purpose

The cartridge is a standardized context package that can be committed to Git and loaded by an agentic coding environment. It is meant to preserve stable intent, architecture, scope, and durable lessons in a form that can be translated into Delta docs, Spec Kit artifacts, Cursor rules, and `AGENTS.md` updates.[^6_1][^6_2]

## Design principles

- Human-readable first.
- Git-friendly and reviewable.
- Machine-parsable for automation.
- Layered by Holistic, Macro, Micro, and Memory.
- Stable enough to be reused across sessions.
- Narrow enough to reduce context drift.

Cursor rules are designed as reusable scoped instructions, while the continual-learning plugin is described as maintaining durable workspace facts using transcript deltas and high-signal bullet updates to `AGENTS.md`, so a cartridge should preserve only durable and structured information.[^6_2][^6_3]

## Folder structure

```text
/cartridge
  manifest.json
  research-summary.md
  holistic.md
  macro.md
  micro/
    feature-name.md
  memory.md
  specs/
    feature-name.specseed.md
  mappings/
    source-map.json
```


## Required files

### `manifest.json`

Machine-readable index for the cartridge.

```json
{
  "schema_version": "cartridge.v1",
  "cartridge_id": "ctx-2026-06-21-feature-x",
  "title": "Blueprint Context for Feature X",
  "created_at": "2026-06-21T02:56:00-04:00",
  "source": {
    "type": "perplexity-research",
    "session_ref": "optional-human-reference"
  },
  "targets": {
    "delta_docs": true,
    "spec_kit": true,
    "cursor_rules": true,
    "agents_md": true
  },
  "features": ["feature-x"],
  "status": "draft"
}
```


### `research-summary.md`

Compressed human summary of the imported Perplexity material.

Required sections:

- Problem statement
- Key findings
- Constraints
- Risks
- Open questions


### `holistic.md`

Mission-level truth.

Required fields:

- Mission
- Problem
- Success criteria
- Non-goals
- Invariants
- Constraints
- Terms


### `macro.md`

Architecture-level truth.

Required fields:

- System overview
- Subsystems
- Interfaces
- Data contracts
- Workflow stages
- Risks


### `micro/<feature>.md`

Task-facing feature context.

Required fields:

- Feature name
- Holistic link
- Macro link
- Scope
- Inputs and outputs
- Acceptance criteria
- Edge cases
- Validation


### `memory.md`

Candidate durable guidance for `AGENTS.md` promotion.

Required sections:

- Stable conventions
- Repeated preferences
- Architecture heuristics
- Promotion candidates
- Rejected non-durable observations


### `specs/<feature>.specseed.md`

Seed artifact for Spec Kit conversion.

Required sections:

- Feature
- Goal
- User value
- Constraints
- Acceptance criteria
- Risks
- Validation


### `mappings/source-map.json`

Traceability map from imported research fragments to cartridge fields.

```json
{
  "items": [
    {
      "source_fragment_id": "r1",
      "source_type": "perplexity",
      "destination": "holistic.mission",
      "confidence": 0.94,
      "notes": "Mission statement distilled from research summary"
    }
  ]
}
```


## Translator pipeline

The translator converts freeform research into cartridge files in five stages.

### 1. Ingest

Input types:

- pasted Perplexity text
- markdown research notes
- saved planning transcripts

Output:

- normalized raw document


### 2. Segment

Break text into units such as:

- goals
- constraints
- architecture ideas
- implementation guidance
- durable preferences
- speculative commentary


### 3. Classify

Map each segment into one of these buckets:

- Holistic
- Macro
- Micro
- Memory
- Reject


### 4. Compress

Rewrite accepted segments into short, durable, low-ambiguity statements. Spec Kit works best from clear specifications and taskable requirements rather than narrative discussion, so the translator should favor compact and testable language.[^6_1][^6_4]

### 5. Emit

Write the cartridge files and optionally compile them into repo destinations:

- `docs/delta/...`
- `docs/specs/<feature>/...`
- `AGENTS.md`
- `.cursor/rules/...`


## Classification rules

Use these rules during translation.

### Holistic

Put a statement in Holistic if it defines:

- mission
- system purpose
- success criteria
- non-goals
- governing constraints
- long-lived invariants

Example:

- “The system should help coding agents stay aligned by feeding them structured multi-level context.”


### Macro

Put a statement in Macro if it defines:

- subsystems
- interfaces
- workflow stages
- major responsibilities
- memory architecture
- validation architecture

Example:

- “The planning system should hand off bounded task packets to the coding environment.”


### Micro

Put a statement in Micro if it defines:

- exact feature scope
- target modules or files
- acceptance criteria
- edge cases
- tests
- local implementation boundaries

Example:

- “Create a context packet builder that reads one feature brief and returns Holistic, Macro, and Micro summaries.”


### Memory

Put a statement in Memory if it is:

- reusable across future tasks
- expressed as durable operational guidance
- likely to improve future agent behavior
- not tied to one temporary branch state

Example:

- “Prefer explicit task scope before editing shared modules.”


### Reject

Reject a statement if it is:

- speculative but unvalidated
- conversational filler
- duplicate narrative
- overly branch-specific
- not useful beyond the current exchange


## Promotion rules

Only a subset of cartridge content should be promoted into `AGENTS.md`. Cursor’s continual-learning pattern emphasizes durable high-signal facts rather than raw transcript memory, so promotion should be conservative.[^6_3][^6_5]

Promote only if the statement is:

- durable
- reusable
- short
- non-redundant
- operationally useful

Do not promote:

- temporary experiments
- one-off failures
- ambiguous preferences
- feature-specific acceptance criteria


## Compilation targets

### Delta docs

Map cartridge files to:

- `holistic.md` -> `docs/delta/00_holistic.md`
- `macro.md` -> `docs/delta/10_macro.md`
- `micro/<feature>.md` -> `docs/delta/20_micro/<feature>.md`


### Spec Kit

Map spec seed to:

- `specs/<feature>.specseed.md` -> `docs/specs/<feature>/spec.md`
- derive `plan.md`
- derive `tasks.md`

Spec Kit is explicitly built around a spec-first flow where the specification becomes the anchor artifact for AI-assisted development.[^6_1][^6_4]

### Cursor

Map durable instructions to:

- `AGENTS.md`
- `.cursor/rules/*.mdc`

Cursor documents rules as reusable scoped instructions, which makes them appropriate for small policy statements compiled from cartridge outputs.[^6_2]

## Suggested translator output contract

A translator can return this JSON object after processing:

```json
{
  "status": "ok",
  "cartridge_id": "ctx-2026-06-21-feature-x",
  "files_written": [
    "cartridge/manifest.json",
    "cartridge/holistic.md",
    "cartridge/macro.md",
    "cartridge/micro/feature-x.md",
    "cartridge/memory.md",
    "cartridge/specs/feature-x.specseed.md"
  ],
  "promotions": {
    "agents_md_candidates": 4,
    "cursor_rule_candidates": 2,
    "spec_seed_created": true
  },
  "rejections": 7
}
```


## Example feature cartridge

```text
/cartridge
  manifest.json
  research-summary.md
  holistic.md
  macro.md
  micro/
    blueprint-loader.md
  memory.md
  specs/
    blueprint-loader.specseed.md
  mappings/
    source-map.json
```

This cartridge could then compile into:

```text
/docs/delta/00_holistic.md
/docs/delta/10_macro.md
/docs/delta/20_micro/blueprint-loader.md
/docs/specs/blueprint-loader/spec.md
/docs/specs/blueprint-loader/plan.md
/docs/specs/blueprint-loader/tasks.md
AGENTS.md
.cursor/rules/architecture.mdc
```


## Governance model

Treat the cartridge as a reviewed transport object, not a hidden prompt cache. Git should carry the cartridge so the same structured context can be loaded by humans, agents, CI workflows, and future sessions. This aligns with your “Nintendo cartridge” analogy: the repo is the console, and the cartridge is the portable structured knowledge pack the system knows how to read.

## Recommended v1 implementation path

1. Start with markdown cartridge files and one `manifest.json`.
2. Build a simple translator that classifies text into Holistic, Macro, Micro, Memory, or Reject.
3. Emit spec seeds for one feature at a time.
4. Promote only reviewed memory candidates into `AGENTS.md`.
5. Add automation later for compilation and CI checks.

That path keeps the first version simple, reviewable, and compatible with Spec Kit and Cursor’s current context mechanisms.[^6_1][^6_2][^6_3]

<div align="center">⁂</div>

[^6_1]: https://github.github.com/spec-kit/

[^6_2]: https://docs.cursor.com/en/context/rules

[^6_3]: https://skills-rank.com/ko/skill/cursor/plugins/continual-learning

[^6_4]: https://github.com/github/spec-kit

[^6_5]: https://note.com/nsp_inc_robots/n/n270f3fff76ea


---