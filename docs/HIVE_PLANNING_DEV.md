<img src="https://r2cdn.perplexity.ai/pplx-full-logo-primary-dark%402x.png" style="height:64px;margin-right:32px"/>

# develope and research strategy and taco c using this as base. using continual learning addon for cursor and spec kit git hub usage.

** Plan in separate AI system. Perplexity etc ( perplexity is good for readers and planning, due to it RAG usage )

1) GIVES a blue print and fine details worked out conceptually for Agentic coding agent or IDE.
2) Helps with context focus, allows the Agentic coding agent to focus on building and working connections between macro and micro details. As it has a solid blue print to fill in the gaps. ( Helps focus it on narrow concept development less errors) Context focus and alignment.

** Agent coding agent feed -- Use mechanism to fee the structure context as ground thruth for better understanding when coding. Holistic, Macro, and Micro. Levels. Allos.llm to see the complexity.rrlarions through that delta.

** CORE Concpets in three ( Delta) Holistic, Macro, and Micro.

1) This allows structure to concept in uniform way to establish consistent connection of data and duatium points, for better understanding during coding.
2) Goal procude enough information the Coding Agentic to understand for better rapid prottyping

Yes — the right strategy is to treat **Perplexity/spec planning** as the upstream “thinking system” and Cursor as the downstream “building system,” with a shared contract that keeps holistic, macro, and micro context aligned during coding. Cursor’s Continual Learning plugin is designed to incrementally learn durable preferences and workspace facts into `AGENTS.md`, while GitHub Spec Kit centers development around a spec-first flow of Spec → Plan → Tasks → Implement, which fits your blueprint-first idea very well. [^1_1][^1_2]

## Core strategy

Your base idea is solid: use one AI environment for conceptual architecture and planning, then feed a distilled structure into the coding agent so it can execute with less drift and fewer local mistakes. Spec Kit explicitly aims to refine what to build before implementation, and Cursor’s rules and agent memory patterns support reusable guidance during execution. [^1_2][^1_3][^1_4]

The best framing is a three-layer “Delta” context model:

- Holistic = mission, product theory, constraints, system intent.
- Macro = architecture, subsystems, interfaces, workflows, data contracts.
- Micro = tasks, files, functions, tests, edge cases.
This matches your goal of giving the coding agent a uniform structure that preserves relationships across levels rather than dumping raw notes into context. [^1_2]


## Recommended stack

Use Perplexity as the **research and blueprint** layer because your stated goal is stronger conceptual grounding and retrieval-supported planning before coding. Then use Spec Kit as the formalization layer that converts the blueprint into executable artifacts, and Cursor as the implementation layer with rules, background agents, and continual memory updates. [^1_2][^1_5][^1_1]

A practical division of labor:


| Layer | Primary tool | Job |
| :-- | :-- | :-- |
| Research | Perplexity | Explore architecture options, tradeoffs, failure modes, and produce the first blueprint. [^1_2] |
| Specification | GitHub Spec Kit | Convert blueprint into structured spec, plan, tasks, and implementation workflow. [^1_2][^1_6] |
| Execution | Cursor | Build tasks iteratively using rules, agents, and project memory. [^1_5][^1_3][^1_4] |
| Memory | Cursor Continual Learning + `AGENTS.md` | Preserve stable repo facts, preferences, and coding conventions over time. [^1_7][^1_1] |

## Delta framework

Build your system around a canonical context pack that every agent consumes in reduced form. Your own prior work already points toward shared latent or shared structured memory, fidelity tiers, and stage contracts, so the Delta model should become the human-readable control plane for that deeper architecture.

Use these three artifacts:

1. `00_holistic.md`
Contains vision, problem framing, success criteria, non-goals, constraints, glossary, and system invariants.
2. `10_macro.md`
Contains modules, data flows, agent roles, interfaces, lifecycle stages, memory design, and dependency graph.
3. `20_micro/`
Contains feature specs, task briefs, acceptance criteria, test plans, file-level notes, and implementation checklists.

The key rule is that each lower level must trace upward:

- Every micro task links to a macro component.
- Every macro component links to a holistic objective.
- Every code change should be explainable as “delta from blueprint,” not a fresh local guess.
That structure supports your aim of helping the coding agent understand complexity and relationships through aligned levels of abstraction. [^1_2]


## Cursor integration

Cursor rules should carry stable behavioral constraints, while `AGENTS.md` should hold cross-tool operational truth that can be updated by continual learning. Public guidance around Cursor in 2026 distinguishes project rules in `.cursor/rules/`, legacy `.cursorrules`, and cross-tool `agents.md` usage, which is useful for separating permanent repo policy from evolving working memory. [^1_3][^1_4][^1_8]

Recommended split:

- `AGENTS.md`
    - Repo mission.
    - Delta model definitions.
    - Architectural invariants.
    - Shared terminology.
    - Stable engineering preferences.
    - “How to think in this repo.”
- `.cursor/rules/architecture.mdc`
    - Enforce traceability: every implementation must cite the related spec/task/module.
    - Ban unscoped edits.
    - Require validation and impact notes.
- `.cursor/rules/task-execution.mdc`
    - Work only from one active micro task at a time.
    - Summarize assumptions before modifying files.
    - Check local interfaces before coding.
- Continual Learning plugin
    - Allow it to append only high-signal bullets to `AGENTS.md`.
    - Restrict updates to durable facts, not transient conversations.
The official Cursor plugin listing describes the continual-learning plugin as updating `AGENTS.md` from transcript changes with high-signal bullet points, which is exactly the behavior you want if curated carefully. [^1_7][^1_1]


## Spec Kit workflow

Spec Kit’s default flow is already close to your ideal operating model: create the spec, derive the technical plan, break it into tasks, then implement. Community examples and docs also show related commands for clarification and analysis, which are useful for checking consistency before coding begins. [^1_2][^1_6][^1_9]

A good operating sequence is:

1. Research in Perplexity.
2. Draft `00_holistic.md`, `10_macro.md`, and initial feature intent.
3. Run Spec Kit specification for the feature.
4. Run plan generation with your architectural preferences.
5. Run tasks generation to create narrow executable units.
6. In Cursor, implement one micro task at a time with rules attached.
7. Use continual learning only after successful validated changes to capture durable lessons. [^1_2][^1_1][^1_9]

For each feature, feed Spec Kit a prompt shaped like:

- Holistic objective.
- Macro subsystem affected.
- Micro task scope.
- Constraints and invariants.
- Acceptance tests.
- Known interfaces.

That gives the coding agent narrower, more grounded context and reduces the chance of broad, misaligned edits. [^1_2][^1_6]

## Governance model

To keep the system from drifting, define a context governance policy. Cursor guidance emphasizes keeping rules short, specific, and checkable, and using background agents with clear security boundaries and approval expectations. [^1_3][^1_5]

Use these policies:

- Blueprint truth lives in versioned markdown, not chat history.
- Spec truth lives in Spec Kit artifacts.
- Execution truth lives in tasks and code.
- Learned truth lives in curated `AGENTS.md` bullets.
- Any new durable pattern must be promoted from micro → macro → holistic only after validation.

This creates a clean promotion path:

- Observation.
- Repeated success.
- Durable rule.
- Architectural principle.
That fits your broader goal of continual learning inside a narrow coding domain without allowing noisy local behavior to overwrite core system intent. [^1_1]

A concise repo layout could be:

```text
/docs
  /delta
    00_holistic.md
    10_macro.md
    20_micro/
  /specs
    feature-x/
      spec.md
      plan.md
      tasks.md
AGENTS.md
.cursor/
  /rules
    architecture.mdc
    task-execution.mdc
    validation.mdc
```

The strategic point is simple: Perplexity produces the blueprint, Spec Kit turns it into machine-actionable structure, and Cursor executes against that structure with continual memory constrained to durable repo truth. [^1_2][^1_1][^1_4]

Would you like me to turn this into a concrete v1 repo blueprint with file templates for `AGENTS.md`, Delta docs, and Cursor rule files?
<span style="display:none">[^1_10][^1_11][^1_12][^1_13][^1_14][^1_15]</span>

<div align="center">⁂</div>

[^1_1]: https://cursor.com/marketplace/cursor/continual-learning

[^1_2]: https://github.github.com/spec-kit/

[^1_3]: https://www.youtube.com/watch?v=pPSIXbKswtQ

[^1_4]: https://github.com/EveryInc/compound-engineering-plugin/blob/main/docs/specs/cursor.md

[^1_5]: https://docs.cursor.com/en/background-agent

[^1_6]: https://github.com/dav1dc-github/spec-kit-demo

[^1_7]: https://github.com/cursor/plugins

[^1_8]: https://www.mdfile.exchange/compare/agents-md-vs-cursor-rules

[^1_9]: https://www.youtube.com/watch?v=61K-2VRaC6s

[^1_10]: https://note.com/nsp_inc_robots/n/n270f3fff76ea

[^1_11]: https://www.youtube.com/watch?v=LA_HqmiGvsE

[^1_12]: https://www.reddit.com/r/cursor/comments/1tlgjwq/should_i_git_ignore_continual_learning_plugin/

[^1_13]: https://github.com/cursor/plugins/actions

[^1_14]: https://www.reddit.com/r/GithubCopilot/comments/1qr1s8o/i_forked_githubs_spec_kit_to_make_specdriven/

[^1_15]: https://github.com/girijashankarj/cursor-handbook/blob/main/docs/components/agents.md


---

# Agentic Coding Repo Blueprint

This blueprint defines a practical repo structure for a spec-first, context-aligned agentic coding workflow that uses Perplexity for research and planning, GitHub Spec Kit for formal specification, and Cursor for implementation with project memory. Spec Kit is documented as a toolkit for spec-driven development that places specifications at the center of AI-assisted software development, while Cursor provides background agents and a Continual Learning plugin that updates `AGENTS.md` with durable workspace facts and preferences.[^2_1][^2_2][^2_3]

## System Intent

The operating model separates planning from execution so the coding agent receives a distilled blueprint instead of raw, drifting chat context. This matches the goal of using an upstream reasoning system to produce a conceptual architecture and a downstream coding system to implement against that structure with better focus and fewer alignment errors.[^2_1]

The core organizing model is **Delta**:

- **Holistic**: mission, product theory, invariants, constraints, success criteria.
- **Macro**: architecture, subsystems, data contracts, agent roles, interfaces, workflows.
- **Micro**: tasks, files, functions, tests, edge cases, change scopes.

This layered model supports durable traceability from strategy to architecture to code, and it is especially compatible with narrow-domain continual learning where stable structure matters more than broad improvisation.[^2_3]

## Recommended Repo Layout

```text
/docs
  /delta
    00_holistic.md
    10_macro.md
    /20_micro
      README.md
      feature-template.md
  /specs
    /feature-name
      spec.md
      plan.md
      tasks.md
AGENTS.md
.cursor/
  /rules
    architecture.mdc
    task-execution.mdc
    validation.mdc
README.md
```

The split above keeps persistent repo truth in versioned documents, implementation policy in Cursor rules, and executable planning in Spec Kit artifacts. Guidance around Cursor in 2026 distinguishes reusable project rules from cross-tool agent guidance, which makes this separation useful for keeping stable rules apart from evolving learned context.[^2_4][^2_5][^2_6]

## Operating Workflow

1. Research the feature, subsystem, or product direction in Perplexity and produce the first blueprint draft.[^2_1]
2. Update `00_holistic.md` and `10_macro.md` so the intent and architecture are explicit before implementation begins.
3. Create or refresh a feature spec in `/docs/specs/<feature>/spec.md` using Spec Kit’s spec-first workflow.[^2_1][^2_7]
4. Derive `plan.md` from the spec, including constraints, interfaces, risks, and validation strategy.[^2_1]
5. Break the plan into narrow executable work units in `tasks.md`, each tied to one macro component and one acceptance target.[^2_1][^2_8]
6. In Cursor, execute one micro task at a time using rules that require scope control, traceability, and validation.[^2_2][^2_4]
7. After validated completion, allow continual learning to promote only durable facts or preferences into `AGENTS.md`.[^2_3]

## Document Templates

### `AGENTS.md`

```md
# AGENTS.md

## Repo Purpose
- One paragraph describing the product, system, or platform.

## Delta Model
- Holistic = mission, constraints, invariants, success criteria.
- Macro = modules, interfaces, workflows, data contracts.
- Micro = tasks, file scope, tests, edge cases.

## Non-Negotiable Invariants
- Do not implement without a linked spec and task.
- Do not make broad multi-module edits without explicit scope.
- Preserve naming consistency with Delta docs.
- Favor narrow validated changes over speculative rewrites.

## Coding Preferences
- Prefer explicit contracts over implicit behavior.
- Add tests for behavior changes.
- Explain interface impacts before modifying shared modules.

## Durable Workspace Facts
- Append only stable facts proven across multiple tasks.
- Do not store transient chat observations here.

## Task Execution Pattern
- Read linked spec.
- Read linked task.
- Identify affected files.
- State assumptions.
- Implement minimal valid change.
- Validate.
- Update docs if architecture changed.
```

`AGENTS.md` works well as the durable cross-tool control file because Cursor’s Continual Learning plugin explicitly updates that file with durable user preferences and workspace facts derived from transcript changes.[^2_3]

### `docs/delta/00_holistic.md`

```md
# Holistic Context

## Mission
- What the system is fundamentally trying to achieve.

## Problem
- What failure, inefficiency, or unmet need this system addresses.

## Success Criteria
- Concrete indicators the system is working.

## Non-Goals
- What the system is intentionally not trying to do.

## Invariants
- Architectural truths that should rarely change.

## Constraints
- Runtime, tooling, performance, budget, security, compliance, or UX constraints.

## Core Terms
- Definitions for repo-specific vocabulary.
```


### `docs/delta/10_macro.md`

```md
# Macro Architecture

## System Overview
- One-paragraph architectural summary.

## Subsystems
- Name
- Purpose
- Inputs
- Outputs
- Dependencies
- Failure modes

## Data Contracts
- Shared types, schemas, message formats, interface rules.

## Agent Roles
- Planning agent
- Coding agent
- Validation agent
- Memory / learning agent

## Workflow Graph
- Describe major stage transitions.

## Risks
- Main alignment, complexity, and coupling risks.
```


### `docs/delta/20_micro/feature-template.md`

```md
# Feature Micro Brief

## Feature Name
- Name of the feature.

## Holistic Link
- Which mission or success criterion this supports.

## Macro Link
- Which subsystem or interface this changes.

## Scope
- Exact files, modules, and boundaries.

## Inputs / Outputs
- Data entering and leaving the feature.

## Acceptance Criteria
- Concrete testable outcomes.

## Edge Cases
- Known corner cases and failure modes.

## Validation
- Tests, manual checks, metrics, or logs to inspect.
```


## Cursor Rules

### `.cursor/rules/architecture.mdc`

```md
---
description: Enforce traceability from code changes to blueprint and spec
alwaysApply: true
---

- Every implementation change must reference one relevant spec or micro task.
- Before editing, summarize how the task maps to Holistic, Macro, and Micro layers.
- Do not introduce new architectural patterns unless the Delta docs are updated first.
- If a task conflicts with existing architecture, stop and propose a Delta doc revision.
```


### `.cursor/rules/task-execution.mdc`

```md
---
description: Keep execution narrow and deterministic
alwaysApply: true
---

- Work on one micro task at a time.
- Identify exact target files before editing.
- Avoid opportunistic refactors unless they are required for the task.
- State assumptions when interfaces are ambiguous.
- Prefer minimal complete changes over broad cleanup.
```


### `.cursor/rules/validation.mdc`

```md
---
description: Require validation before completion
alwaysApply: true
---

- Every completed task must include validation evidence.
- For behavior changes, add or update tests.
- For interface changes, explain downstream impact.
- For architecture changes, update Delta docs and linked specs.
- Do not mark complete if validation is missing.
```

Public Cursor guidance highlights rules, background agents, and structured project memory as key control mechanisms, so these rule files should remain short, checkable, and tied to execution behavior rather than broad prose.[^2_2][^2_4]

## Spec Kit Usage Pattern

Use Spec Kit as the structured bridge between conceptual planning and implementation. Its documentation describes a spec-driven workflow centered on formal specifications, and community tutorials commonly frame the working sequence as specification, planning, and task breakdown before implementation.[^2_1][^2_9][^2_8]

Suggested feature loop:

```text
/specify  -> produce or refine spec.md
/plan     -> derive technical plan.md
/tasks    -> generate executable tasks.md
```

Each feature prompt should include:

- Holistic objective.
- Macro subsystem touched.
- Micro scope and target files.
- Constraints and invariants.
- Acceptance criteria.
- Validation requirements.
- Known risks or open questions.

This keeps the coding system grounded in an explicit chain from intent to architecture to task, rather than relying on the agent to reconstruct context from long transcripts.[^2_1][^2_7]

## Continual Learning Policy

The Continual Learning plugin should be treated as a selective memory promoter, not an unrestricted note collector. The plugin is described as incrementally learning durable user preferences and workspace facts from transcript changes and keeping `AGENTS.md` up to date, which means governance is essential so the file stays high-signal.[^2_3]

Recommended promotion rules:

- Promote only repeated, validated, durable patterns.
- Promote naming conventions, stable architecture preferences, and recurring workflow rules.
- Do not promote one-off experiments, temporary bugs, or uncertain hypotheses.
- Review `AGENTS.md` changes periodically to remove drift.
- Treat `AGENTS.md` as operational truth, not brainstorming storage.

A useful promotion ladder is:

1. Observation in task execution.
2. Repetition across successful tasks.
3. Promotion into `AGENTS.md` as durable guidance.
4. Promotion into Delta docs if it changes architecture or system theory.

## Example Task Mapping

| Layer | Example entry |
| :-- | :-- |
| Holistic | “Reduce coding drift and improve agent alignment during rapid prototyping.” |
| Macro | “Introduce a blueprint ingestion pipeline that exposes mission, architecture, and task contracts to the coding agent.” |
| Micro | “Add `loadBlueprintContext()` and validate context packet assembly for one feature flow.” |

This mapping gives the coding agent a narrow local job while preserving the reason that job exists inside the larger system design.[^2_1][^2_3]

## Governance Rules

Use these repo-level policies:

- Blueprint truth lives in Delta docs.
- Feature truth lives in Spec Kit artifacts.
- Execution truth lives in tasks, code, and tests.
- Learned truth lives in curated `AGENTS.md` entries.
- No durable change should bypass traceability.

That governance model aligns well with Cursor’s rule-based project control and with your broader goal of building a continually improving coding system inside a narrow domain without losing structural coherence.[^2_2][^2_4][^2_3]

## Implementation Notes

This blueprint is strongest when each feature branch contains a small, explicit context packet derived from Holistic, Macro, and Micro documents rather than requiring the coding agent to reload the full repository worldview every time. That approach keeps the context focused while preserving the relationships between broad intent and local code changes.[^2_1]

For your architecture direction, this also matches your stated emphasis on a structured, uniform representation that improves understanding during coding and helps rapid prototyping by making the system’s complexity visible at multiple levels.

<div align="center">⁂</div>

[^2_1]: https://github.github.com/spec-kit/

[^2_2]: https://docs.cursor.com/en/background-agent

[^2_3]: https://cursor.com/marketplace/cursor/continual-learning

[^2_4]: https://www.youtube.com/watch?v=pPSIXbKswtQ

[^2_5]: https://github.com/EveryInc/compound-engineering-plugin/blob/main/docs/specs/cursor.md

[^2_6]: https://www.mdfile.exchange/compare/agents-md-vs-cursor-rules

[^2_7]: https://github.com/dav1dc-github/spec-kit-demo

[^2_8]: https://www.youtube.com/watch?v=61K-2VRaC6s

[^2_9]: https://www.youtube.com/watch?v=LA_HqmiGvsE


---

# Agentic Coding Starter Kit

This starter kit packages the blueprint into actual repo-ready files for a spec-first workflow that uses Perplexity for research, GitHub Spec Kit for specification, and Cursor for implementation with rule-based execution and durable project memory. Spec Kit is documented as a toolkit for spec-driven development, and Cursor provides background agents plus a Continual Learning plugin that maintains durable workspace facts in `AGENTS.md`.[^3_1][^3_2][^3_3]

## Included files

- `AGENTS.md`
- `docs/delta/00_holistic.md`
- `docs/delta/10_macro.md`
- `docs/delta/20_micro/README.md`
- `docs/delta/20_micro/feature-template.md`
- `docs/specs/example-feature/spec.md`
- `docs/specs/example-feature/plan.md`
- `docs/specs/example-feature/tasks.md`
- `.cursor/rules/architecture.mdc`
- `.cursor/rules/task-execution.mdc`
- `.cursor/rules/validation.mdc`
- `spec-kit-agent-integration.md`


## How to use

1. Fill in `AGENTS.md` with durable project truth.
2. Define system mission and invariants in `00_holistic.md`.
3. Define architecture and interfaces in `10_macro.md`.
4. Create feature specs in `docs/specs/<feature>/` using the same pattern as the example feature.
5. Use Cursor to implement one task at a time while keeping rule files active.[^3_1][^3_4] policy>
Acceptance criteria: <testable outcomes>
Validation: <tests, checks, metrics>
Risks: <known uncertainties>
```

## Why this works

This approach reduces the need for the coding agent to infer system intent from long transcripts. It gives the agent a narrow execution frame while still preserving traceability to mission and architecture, which aligns with a context-focused and error-reducing implementation workflow.[cite:12][cite:17]

## Cursor connection points

Use Cursor for:

- Reading the current task and related spec.
- Applying rules from `.cursor/rules/`.
- Using `AGENTS.md` as durable repo memory.
- Running background agents for bounded implementation tasks where appropriate.[cite:13][cite:16][cite:17]
<span style="display:none">[^3_5]</span>

<div align="center">⁂</div>

[^3_1]: https://github.github.com/spec-kit/
[^3_2]: https://docs.cursor.com/en/background-agent
[^3_3]: https://cursor.com/marketplace/cursor/continual-learning
[^3_4]: https://www.youtube.com/watch?v=pPSIXbKswtQ
[^3_5]: 1000002304.jpg

---

# Context Handoff, Iterative Spec Updates, and AGENTS Automation

This document extends the starter kit with three operational topics: maintaining context between Perplexity and Cursor via Git, best practices for iterative Spec Kit updates during development, and safe automation patterns for `AGENTS.md` updates in CI/CD. Spec Kit is positioned as a spec-driven workflow centered on specifications, while Cursor provides background agents and a Continual Learning plugin that updates `AGENTS.md` using durable, high-signal transcript-derived facts.[^4_1][^4_2][^4_3][^4_4]

## Maintaining Context via Git

The cleanest way to maintain context between Perplexity and Cursor is to treat Git as the transport layer for durable context, not just for code. The branch should carry the current Delta docs, the active Spec Kit artifacts, and curated `AGENTS.md` guidance so Cursor can read repo state directly instead of depending on chat continuity.[^4_1][^4_3][^4_5]

### What should move through Git

Commit these context artifacts with the feature branch:

- `docs/delta/00_holistic.md`
- `docs/delta/10_macro.md`
- `docs/delta/20_micro/<feature>.md`
- `docs/specs/<feature>/spec.md`
- `docs/specs/<feature>/plan.md`
- `docs/specs/<feature>/tasks.md`
- `AGENTS.md`
- `.cursor/rules/*.mdc`

This keeps planning context versioned, reviewable, and available to Cursor in the same repository state as the code changes.[^4_1][^4_2]

### Recommended branch pattern

Use one branch per feature or per architecture change. Keep the branch narrative in this order:

1. Commit spec and Delta changes first.
2. Commit implementation changes second.
3. Commit validation and any durable memory promotion third.

Community guidance around Spec Kit stresses that the specification should remain the primary reference point and that regular commits make rollback easier when implementation drifts from intent.[^4_6][^4_5]

### Suggested commit structure

```text
feat(spec): add blueprint context loader spec and plan
feat(code): implement bounded context packet assembly
test(validation): add packet generation tests
chore(memory): promote durable repo guidance to AGENTS.md
```

This pattern makes Git history act like a context timeline: intent first, execution second, memory promotion last.

### Perplexity to Git handoff

A practical handoff loop is:

1. Research or plan in Perplexity.
2. Convert the output into markdown artifacts inside the repo.
3. Commit those artifacts before coding begins.
4. Open the branch in Cursor.
5. Ask Cursor to work only from the committed docs and the active task.

The value here is that the context becomes inspectable repo state rather than a transient prompt.[^4_1][^4_2]

### Minimal handoff packet

For each active feature, include a short `handoff.md` or feature micro brief with:

- Goal.
- Why it matters.
- Architecture touched.
- Allowed file scope.
- Acceptance criteria.
- Known risks.
- Links to spec, plan, and tasks.

That keeps Cursor focused without reloading the entire project worldview each time.

## Iterative Spec Kit Updates

The best practice is to treat specs as living but stable reference documents. Public discussion around Spec Kit highlights the need for safe workflows when projects evolve, especially to avoid overwriting project-specific state while keeping specs aligned with the codebase.[^4_7][^4_6][^4_5]

### Update policy

Use this hierarchy:

- `spec.md` = product and behavior truth.
- `plan.md` = implementation strategy truth.
- `tasks.md` = current execution breakdown.

If code changes behavior, update the spec. If only the implementation path changes, update the plan. If only execution sequencing changes, update tasks without rewriting the whole spec.[^4_8][^4_5]

### When to update

Update Spec Kit artifacts when:

- Acceptance criteria change.
- Scope expands or contracts.
- Architecture assumptions change.
- Implementation reveals a better approach that affects behavior or interfaces.
- Validation exposes drift between delivered behavior and intended behavior.[^4_7][^4_8]


### Iterative loop

A safe iterative pattern is:

1. Clarify ambiguous requirements before planning.
2. Generate initial `spec.md`.
3. Generate `plan.md`.
4. Generate `tasks.md`.
5. Implement a small slice.
6. Compare code and behavior to the spec.
7. If drift appears, revise the spec first, then regenerate plan/tasks as needed.

Spec Kit guidance emphasizes clarification before planning, and community guidance recommends updating the spec and discarding off-track changes when implementation goes off the rails.[^4_9][^4_6]

### Drift control rules

- Never let code become the only source of truth.
- Do not silently patch around spec conflicts.
- If implementation teaches something durable, promote it back into the spec or Delta docs.
- Recreate `tasks.md` freely when needed, but protect `spec.md` as the behavioral contract.[^4_5]


### Good iterative hygiene

- Keep feature specs small and focused.
- Define non-goals explicitly.
- Use measurable acceptance criteria.
- Cross-link related specs and architecture docs.
- Archive completed or superseded specs so active work stays clean.[^4_8]


## Automating `AGENTS.md` in CI/CD

Automation is useful, but `AGENTS.md` should be treated as curated operational memory rather than a raw append-only log. Cursor’s Continual Learning plugin is described as using transcript deltas, high-signal bullet extraction, deduplication, and incremental indexing to keep `AGENTS.md` current, which is a good model for CI/CD automation as well.[^4_10][^4_3][^4_11][^4_12]

### What to automate

Good automation targets:

- Linting `AGENTS.md` structure.
- Checking duplicate bullets.
- Rejecting overly long or low-signal entries.
- Verifying required sections exist.
- Comparing `AGENTS.md` changes against allowed scopes.
- Opening a PR with proposed memory updates instead of pushing directly.


### What not to automate blindly

Avoid fully automatic direct writes to `main` based on unreviewed chat or build output. `AGENTS.md` should not absorb transient incidents, one-off debugging notes, or speculative assumptions.[^4_3][^4_11]

### Best CI/CD model

Use a proposal workflow instead of direct mutation:

1. Nightly or on-demand job gathers candidate updates.
2. Script deduplicates and validates bullets.
3. Job opens a PR named like `chore/agents-memory-refresh`.
4. Human or designated reviewer approves the changes.
5. Merge updates `AGENTS.md`.

This matches the plugin’s incremental, high-signal model while preserving governance.[^4_10][^4_11]

### Example pipeline stages

```text
extract -> filter -> dedupe -> validate -> propose PR -> review -> merge
```


### Validation rules for automated updates

Require that every proposed bullet is:

- Durable across multiple sessions or tasks.
- Useful across future work.
- Expressed as one plain-language bullet.
- Non-redundant with existing guidance.
- Not tied to a temporary bug or branch-specific state.[^4_3][^4_11]


### Example GitHub Actions strategy

A lightweight implementation can:

- Run on schedule or manual dispatch.
- Read candidate memory notes from a generated artifact or transcript export.
- Compare against current `AGENTS.md`.
- Produce a patch file or PR.

Cursor’s Background Agents API is also positioned for programmatic creation and management of coding agents that can update docs and respond to feedback, so teams that want deeper automation could combine CI with bounded background-agent tasks for doc-refresh workflows.[^4_4]

### Guardrails

- Never let automation overwrite the entire file.
- Preserve manually written sections.
- Restrict automation to an editable subsection such as `## Durable Workspace Facts`.
- Keep an audit trail in Git history.
- Roll back memory changes like any other code change.


## Recommended combined workflow

For a mature setup, use this sequence:

1. Perplexity produces blueprint or research output.
2. Repo docs are updated and committed.
3. Spec Kit artifacts are generated or revised.
4. Cursor implements tasks from the committed branch state.
5. Validation confirms behavior.
6. Continual learning proposes durable `AGENTS.md` updates.
7. CI validates and opens a reviewable PR for memory promotion.

This creates a closed loop where context is transported by Git, shaped by specs, executed by the coding agent, and promoted into durable operational memory only after review.[^4_1][^4_3][^4_4][^4_5]
<span style="display:none">[^4_13][^4_14][^4_15][^4_16][^4_17][^4_18]</span>

<div align="center">⁂</div>

[^4_1]: https://github.github.com/spec-kit/

[^4_2]: https://docs.cursor.com/en/background-agent

[^4_3]: https://cursor.com/marketplace/cursor/continual-learning

[^4_4]: https://docs.cursor.com/en/background-agent/api/overview

[^4_5]: https://www.reddit.com/r/speckit/comments/1o0p4va/localden_answering_your_github_spec_kit_questions/

[^4_6]: https://www.youtube.com/watch?v=OFow2aTnqB8

[^4_7]: https://github.com/github/spec-kit/issues/916

[^4_8]: https://lillytechsystems.com/ai-school/spec-kit/best-practices.html

[^4_9]: https://github.com/github/spec-kit

[^4_10]: https://github.com/cursor/plugins

[^4_11]: https://skills-rank.com/skill/cursor/plugins/continual-learning

[^4_12]: https://www.linkedin.com/posts/dmitrii-khizbullin_i-highly-recommend-the-continual-learning-activity-7431795903281135617-FR1D

[^4_13]: 1000002306.jpg

[^4_14]: https://docs.cursor.com/ja/background-agent

[^4_15]: https://note.com/nsp_inc_robots/n/n270f3fff76ea

[^4_16]: https://cursor.com/changelog/0-50

[^4_17]: https://b.hatena.ne.jp/entry/s/docs.cursor.com/background-agent

[^4_18]: https://linear.app/changelog/2025-08-21-cursor-agent


---

# so can it be designed to read text from perplexity research to translate into something the Agentic Agentic and use for Spec kit and continual learning addon. think we be creating a Nintendo cartridge. for a system that can read the cartridge

Yes — that is a very good design, and your “Nintendo cartridge” metaphor is strong. You can design a **portable context cartridge**: Perplexity research goes in, a translator normalizes it, and the output becomes a repo-readable package that Cursor, Spec Kit, and the continual-learning flow can all consume consistently. [^5_1][^5_2][^5_3]

In that model, the cartridge is not raw chat text. It is a structured markdown or JSON-backed bundle that stores intent, constraints, architecture, and reusable lessons in a form that AI coding agents can reload from Git at any time. Cursor rules are persistent prompt-level context, `AGENTS.md` is a simple repo-level instruction file, and Spec Kit works best when specifications define the “what” before implementation begins. [^5_2][^5_1][^5_4]

## Cartridge model

Think of the cartridge as a **standardized context pack** that your system can insert into any coding session. The reader is the agentic IDE stack: Cursor reads rules and `AGENTS.md`, Spec Kit reads spec artifacts, and the continual-learning addon updates durable repo guidance from transcript deltas instead of rescanning everything. [^5_2][^5_3][^5_5]

A good cartridge contains:

- Holistic context: mission, goals, constraints, non-goals.
- Macro context: architecture, modules, interfaces, workflows.
- Micro context: tasks, file scope, tests, acceptance criteria.
- Memory context: durable preferences and repo truths suitable for `AGENTS.md`.
- Spec context: normalized feature definition ready for `spec.md`, `plan.md`, and `tasks.md`. [^5_1][^5_6]


## Translation pipeline

The key is to add a **translator** between Perplexity output and the repo. Perplexity research is often rich but too narrative, while Spec Kit and Cursor need compressed, structured, reusable context. Spec Kit explicitly emphasizes structured refinement and clarification before implementation, which fits a translator stage very well. [^5_4][^5_1]

The pipeline can be:

1. Perplexity research output.
2. Cartridge translator extracts durable signals.
3. Cartridge writer emits repo files.
4. Spec Kit uses cartridge data to generate or update `spec.md`, `plan.md`, `tasks.md`.
5. Cursor reads `AGENTS.md` and `.cursor/rules`.
6. Continual learning updates only the durable-memory section after validated work. [^5_1][^5_2][^5_3]

So yes: the system can absolutely “read the cartridge,” as long as you define the cartridge format tightly enough.

## Best format

The safest first version is markdown-first, not latent-first. Cursor documentation states that `AGENTS.md` is a plain markdown file for agent instructions, and rules are reusable scoped instructions included at the start of model context, so markdown is the most compatible base layer. [^5_2][^5_7]

Use a hybrid cartridge:

- Human-readable `.md` files for agent loading and Git review.
- Optional `.json` manifest for machine parsing and automation.
- Stable folder layout so every tool knows where to look. [^5_2][^5_1]

Example layout:

```text
/cartridge
  manifest.json
  holistic.md
  macro.md
  micro.md
  memory.md
  feature-spec.md
```

Then compile it into:

- `docs/delta/...`
- `docs/specs/<feature>/...`
- `AGENTS.md`
- `.cursor/rules/...`


## What gets promoted

Not every Perplexity sentence should enter the cartridge. The continual-learning plugin’s public behavior is to extract only high-signal reusable information, merge with existing bullets, and deduplicate similar content, which is exactly the filter you want in your translator too. [^5_3]

Promotion rules should be:

- Research insight becomes cartridge content if it affects architecture, constraints, or execution.
- Repeated successful behavior becomes `AGENTS.md`.
- Feature definition becomes Spec Kit input.
- One-off commentary stays out. [^5_1][^5_3]

A simple mapping table:


| Source | Destination |
| :-- | :-- |
| Product goals, constraints | `holistic.md` |
| Architecture reasoning | `macro.md` |
| Feature steps, acceptance criteria | `feature-spec.md` |
| Narrow coding scope | `micro.md` |
| Repeated durable guidance | `AGENTS.md` |
| Behavioral implementation contract | `spec.md`, `plan.md`, `tasks.md` |

## Practical design

The best v1 is a **Cartridge Compiler** script or agent that takes Perplexity text and outputs normalized repo artifacts. That fits your broader goal of turning broad planning into a structured substrate the coding agent can actually use for rapid prototyping and alignment.

Core modules:

- Parser: splits raw research into claims, requirements, constraints, risks.
- Normalizer: maps claims into Holistic/Macro/Micro/Memory buckets.
- Deduper: removes overlap and compresses wording.
- Spec emitter: writes Spec Kit-ready spec/plan/task seeds.
- Memory emitter: updates only approved `AGENTS.md` sections.
- Git packager: commits the cartridge as the handoff boundary. [^5_1][^5_3][^5_2]


## Design rule

The cartridge should be treated like a **game cartridge, not RAM**. It should hold stable, replayable, loadable state, not live conversational noise. Spec Kit works best when specifications are the central artifact, and Cursor’s memory model works best when it captures durable workspace facts rather than raw transcript history. [^5_4][^5_1][^5_5]

So the short answer is: yes, and the right way is to build a **Perplexity-to-Cartridge translator** that converts research text into a standardized repo context pack which your agentic IDE can load into Spec Kit, Cursor rules, and continual learning safely. [^5_1][^5_2][^5_3]

Would you like me to generate a concrete **Cartridge Schema v1** next, with fields, folder structure, and translator rules?
<span style="display:none">[^5_10][^5_11][^5_12][^5_13][^5_14][^5_15][^5_8][^5_9]</span>

<div align="center">⁂</div>

[^5_1]: https://github.github.com/spec-kit/

[^5_2]: https://docs.cursor.com/en/context/rules

[^5_3]: https://skills-rank.com/ko/skill/cursor/plugins/continual-learning

[^5_4]: https://github.com/github/spec-kit

[^5_5]: https://note.com/nsp_inc_robots/n/n270f3fff76ea

[^5_6]: https://github.com/dav1dc-github/spec-kit-demo

[^5_7]: https://docs.cursor.com/ko/context/rules

[^5_8]: https://speckit.md/introduction.md

[^5_9]: https://docs.cursor.com/zh/context/rules

[^5_10]: https://www.youtube.com/watch?v=pP_dSNz_EdQ\&vl=ja

[^5_11]: https://docs.cursor.com/ja/context/rules

[^5_12]: https://forum.cursor.com/t/why-the-push-for-agentic-when-models-can-barely-follow-a-single-simple-instruction/137154

[^5_13]: https://blog.scottlogic.com/2025/11/26/putting-spec-kit-through-its-paces-radical-idea-or-reinvented-waterfall.html

[^5_14]: https://www.reddit.com/r/cursor/comments/1nqwz02/switching_to_agentsmd/

[^5_15]: https://docs.cursor.com/zh-Hant/context/rules


---

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

# Cartridge PDF Extension

This extension adds centralized PDF sourcing to the cartridge system so planning agents can pull supporting context from a shared document directory and coding agents can reference relevant excerpts during prototyping when extra context is helpful. Cursor rules provide persistent scoped context, while Spec Kit distinguishes between feature specs and broader codebase context or memory-bank style documents, which makes a centralized PDF layer a good optional support system rather than the primary source of execution truth.[^7_1][^7_2][^7_3]

## Intent

The PDF layer should support planning and occasional in-task reference, but it should not replace the Delta docs, specs, tasks, or `AGENTS.md`. The role of the PDF directory is to provide **tertiary context**: not required for every task, but useful for grounding design choices, surfacing overlooked constraints, and offering extra insight while coding.[^7_2][^7_4]

## Central directory design

Use a dedicated repo-adjacent or repo-internal directory such as:

```text
/context-library/pdfs/
```

Recommended structure:

```text
/context-library/
  manifest.json
  /pdfs
    architecture/
    domain/
    requirements/
    research/
    reference/
  /extracted
    raw-text/
    markdown/
    metadata/
  /indexes
    chunk-index.json
    document-index.json
```

This layout separates source PDFs from extracted text and retrieval metadata, which matches common PDF/RAG ingestion guidance that emphasizes text extraction, segmentation, and metadata handling before retrieval.[^7_5][^7_6][^7_7]

## Role in the stack

Use the PDF library in three ways:

- **Planning time**: enrich specs, plans, and architecture decisions.
- **Prototype time**: allow the coding agent to retrieve only relevant excerpts when needed.
- **Review time**: verify whether an implementation still aligns with source documentation.

The PDF directory should remain subordinate to the main planning artifacts. Specs and tasks still define what to build, while PDF excerpts provide supplemental grounding.[^7_3][^7_2]

## Processing pipeline

A practical pipeline is:

1. Ingest PDF files from the centralized directory.
2. Extract text, tables, and metadata.
3. Convert pages or sections into markdown or chunked text.
4. Tag each chunk with source document, page, section, and topic metadata.
5. Build a lightweight retrieval index.
6. Expose top relevant chunks to the planning or coding agent only when requested.

Document-ingestion guidance for PDF-based retrieval commonly recommends extraction, page or section segmentation, metadata capture, and chunk-level indexing so later queries can recover context with source traceability.[^7_5][^7_6][^7_7]

## Cartridge changes

Add an optional PDF reference section to `manifest.json`:

```json
{
  "schema_version": "cartridge.v1",
  "pdf_context": {
    "enabled": true,
    "library_root": "context-library/pdfs",
    "max_documents_per_query": 3,
    "max_chunks_per_query": 8,
    "mode": "supplemental"
  }
}
```

Add a new optional file:

```text
/cartridge/pdf-context.md
```

This file stores the PDF-derived notes that were actually selected for the current feature or planning cycle.

## New file format

### `pdf-context.md`

```md
# PDF Context

## Active documents
- architecture/system-design.pdf
- domain/compliance-notes.pdf

## Retrieved excerpts
### Source: architecture/system-design.pdf p.12
- <short excerpt summary>

### Source: domain/compliance-notes.pdf p.4
- <short excerpt summary>

## Why relevant
- Explains interface assumptions for the planning stage.
- Provides constraint details relevant to validation.
```

This keeps PDF usage explicit and reviewable rather than silently mixing external document content into task execution.

## Retrieval policy

The agent should not load the whole PDF library into context. It should query the index only when:

- planning hits an ambiguity,
- a feature touches regulated or domain-heavy logic,
- architecture details are not fully captured in Delta docs,
- a coding task would benefit from deeper grounding.

This helps keep the active context tight while still allowing insight recovery when needed. Cursor rules are prompt-level context, so feeding only relevant excerpts preserves focus better than adding full documents indiscriminately.[^7_1]

## Triage context model

Your phrasing of **triacrat context** fits well as a three-tier relevance system:

- **Primary context**: Delta docs, active spec, active plan, active task.
- **Secondary context**: `AGENTS.md`, Cursor rules, durable repo conventions.
- **Tertiary context**: retrieved PDF excerpts from the centralized library.

The PDF layer belongs in tertiary context because it is helpful but not normally required for every coding step.[^7_2][^7_8]

## Classification rules for PDF material

When PDF content is retrieved, classify it before use:

- If it defines mission, invariants, or core constraints, promote distilled form into Holistic.
- If it defines subsystem behavior or interfaces, promote distilled form into Macro.
- If it defines exact feature scope or acceptance rules, promote distilled form into Micro or Spec Kit artifacts.
- If it is broadly reusable guidance, consider promotion into `AGENTS.md` after review.
- Otherwise, keep it in `pdf-context.md` only for the active cycle.

This prevents document retrieval from becoming another uncontrolled prompt dump.

## Indexing recommendations

For a v1 implementation, capture at least:

- document path
- title
- page number
- section heading if detectable
- text chunk
- keywords
- last updated date
- trust level or document class

PDF retrieval guidance commonly emphasizes metadata capture and chunk-level segmentation because these improve searchability and traceability during later use.[^7_5][^7_6]

## Example planning flow with PDFs

```text
Perplexity research
  -> translator builds cartridge
  -> planning agent checks for ambiguity
  -> PDF retriever searches centralized directory
  -> top excerpts written to pdf-context.md
  -> spec/plan updated with distilled facts
  -> coding agent reads only distilled outputs plus optional excerpts
```

This lets the system use PDFs as a just-in-time augmentation layer without making the coding loop bloated or unfocused.

## Example repo policy

Add this guidance to `AGENTS.md` or a Cursor rule:

```md
- Use centralized PDF context only as tertiary support.
- Never replace active specs or tasks with raw PDF excerpts.
- Distill PDF findings into Delta docs or spec artifacts before relying on them repeatedly.
- Keep retrieved PDF snippets short and source-labeled.
```


## Recommended v1 constraints

- Maximum 3 documents per retrieval.
- Maximum 8 chunks inserted into working context.
- Maximum 1 short excerpt per chunk.
- Always preserve source path and page.
- Summarize first, quote sparingly.

Those limits help preserve task focus while still giving the coding agent access to extra grounding and potential new insights during prototyping.[^7_7][^7_9]

## Outcome

With this extension, the cartridge system becomes a four-part context stack:

1. Research translation from Perplexity.
2. Structured cartridge files.
3. Spec and repo memory compilation.
4. Optional centralized PDF retrieval for tertiary context.

That gives you exactly what you described: PDF material is not mandatory, but it can help the agent stay on task, recover missing details, and discover useful implementation insights during planning and prototyping.[^7_2][^7_7][^7_1]
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

That path keeps the first version simple, reviewable, and compatible with Spec Kit and Cursor’s current context mechanisms.[cite:12][cite:47][cite:46]

## PDF extension

A centralized PDF directory can be added as an optional tertiary-context source for planning and selective prototyping support. The detailed design is provided in the companion document `cartridge-pdf-extension.md`, which describes a shared `/context-library/pdfs/` layout, extraction and indexing flow, `pdf-context.md` as an optional cartridge file, and rules for using retrieved excerpts only as supplemental context rather than replacing active specs or tasks.[cite:47][cite:58][cite:60][cite:65]
<span style="display:none">[^7_10][^7_11][^7_12][^7_13][^7_14][^7_15]</span>

<div align="center">⁂</div>

[^7_1]: https://docs.cursor.com/en/context/rules

[^7_2]: https://martinfowler.com/articles/exploring-gen-ai/sdd-3-tools.html

[^7_3]: https://github.com/github/spec-kit

[^7_4]: https://developer.microsoft.com/blog/spec-driven-development-spec-kit

[^7_5]: https://mallahyari.github.io/rag-ebook/03_prepare_data.html

[^7_6]: https://arxiv.org/pdf/2410.15944.pdf

[^7_7]: https://medium.com/@harshguptalnm/building-a-scalable-rag-system-for-pdf-data-retrieval-9ad505948e63

[^7_8]: https://www.cursorforpms.com/fundamentals/project-rules

[^7_9]: https://www.youtube.com/watch?v=QTq9GWkTJ4A

[^7_10]: https://medium.com/@iamarunbrahma/building-a-production-grade-rag-document-ingestion-pipeline-with-llamaindex-and-qdrant-08f4ea1c03c1

[^7_11]: https://docs.cursor.com/ko/context/rules

[^7_12]: https://docs.cursor.com/ja/context/rules

[^7_13]: https://docs.cursor.com/en/context/@-symbols/@-cursor-rules

[^7_14]: https://den.dev/blog/github-spec-kit/

[^7_15]: https://github.com/github/spec-kit/discussions/1251


---

# Cartridge Document Sourcing Extension

This extension replaces the PDF-specific context layer with a generalized document-sourcing layer for the same tertiary reference role. The design fits Cursor’s scoped context model, where rules can be always included, auto-attached, or agent-requested, and it also fits the broader spec-driven idea that high-level context documents and memory-bank files support execution without replacing the active spec and task artifacts.[^8_1][^8_2][^8_3]

## Intent

The goal is to support a centralized document library that can supply **same-level tertiary context** during planning or prototyping, regardless of whether the source is PDF, Markdown, DOCX, TXT, HTML, CSV, or another supported document format. This context is optional and reference-oriented: it should help the agent stay grounded, recover missing detail, or surface useful insights without becoming the primary execution source.[^8_4][^8_5][^8_6]

## Tertiary context role

Use a three-tier context model:

- **Primary context**: Delta docs, active `spec.md`, `plan.md`, `tasks.md`, and feature micro briefs.
- **Secondary context**: `AGENTS.md`, Cursor rules, constitution or memory-bank documents.
- **Tertiary context**: source-derived excerpts from the centralized document library.

This follows the distinction between active task specifications and broader memory-bank or constitution files that support work across sessions.[^8_2][^8_3][^8_7]

## Supported source types

The document layer should be format-agnostic. Public document-ingestion systems commonly support heterogeneous inputs such as PDF, DOCX, TXT, Markdown, HTML, CSV, and related formats, which makes a unified source-library design practical.[^8_4][^8_6][^8_8][^8_9]

Recommended first-wave source types:

- Markdown (`.md`)
- Plain text (`.txt`)
- PDF (`.pdf`)
- Word (`.docx`)
- HTML (`.html`, `.htm`)
- CSV (`.csv`)
- PowerPoint (`.pptx`) if used as requirements or planning material
- JSON (`.json`) if it contains structured policy or configuration context


## Centralized directory

Use a neutral directory such as:

```text
/context-library/sources/
```

Recommended structure:

```text
/context-library/
  manifest.json
  /sources
    architecture/
    requirements/
    research/
    reference/
    policy/
    product/
  /normalized
    markdown/
    text/
    metadata/
  /indexes
    document-index.json
    chunk-index.json
```

This structure separates original documents from normalized outputs and indexing metadata, which is consistent with common ingestion workflows that first parse documents, then normalize them into text or markdown before retrieval.[^8_5][^8_9]

## Normalization model

Every source document should be converted into a common normalized representation so the rest of the cartridge system does not care about the original format. A practical standard is markdown plus metadata because markdown is readable by humans, Git-friendly, and easy for agents to consume.[^8_5][^8_7]

Normalization outputs:

- canonical markdown file
- raw extracted text if needed
- metadata record
- chunked excerpts for retrieval

Example metadata:

```json
{
  "source_path": "context-library/sources/architecture/system-design.docx",
  "normalized_path": "context-library/normalized/markdown/system-design.md",
  "document_type": "architecture",
  "format": "docx",
  "title": "System Design",
  "last_updated": "2026-06-21",
  "trust_level": "high"
}
```


## Cartridge changes

Replace the PDF-specific settings with generalized source settings in `manifest.json`:

```json
{
  "schema_version": "cartridge.v1",
  "source_context": {
    "enabled": true,
    "library_root": "context-library/sources",
    "normalized_root": "context-library/normalized",
    "max_documents_per_query": 3,
    "max_chunks_per_query": 8,
    "mode": "supplemental",
    "allowed_formats": ["md", "txt", "pdf", "docx", "html", "csv", "json", "pptx"]
  }
}
```

Add a generalized optional cartridge file:

```text
/cartridge/source-context.md
```


## `source-context.md` format

```md
# Source Context

## Active documents
- architecture/system-design.docx
- policy/security-guidelines.md
- research/domain-notes.pdf

## Retrieved excerpts
### Source: architecture/system-design.docx
- <short excerpt summary>

### Source: policy/security-guidelines.md
- <short excerpt summary>

### Source: research/domain-notes.pdf
- <short excerpt summary>

## Why relevant
- Clarifies architecture assumptions for the active planning cycle.
- Adds validation constraints relevant to the current feature.
- Supplies background detail useful during prototyping.
```


## Retrieval policy

The agent should query the source library only when extra grounding is needed. Cursor rules support agent-requested and auto-attached context patterns, which means this document layer is best used as selective retrieval rather than unconditional prompt stuffing.[^8_1][^8_10][^8_11]

Good triggers:

- architecture ambiguity
- regulated or policy-heavy work
- missing domain detail in the spec
- implementation uncertainty during prototyping
- need to validate against a source requirement


## Classification rules for sourced material

When a source excerpt is retrieved, classify it before promotion:

- Promote to Holistic if it defines mission, success criteria, or stable constraints.
- Promote to Macro if it defines architecture, subsystems, interfaces, or workflows.
- Promote to Micro if it defines exact task scope, edge cases, or acceptance criteria.
- Promote to Memory only if it is a durable, reusable operational rule.
- Otherwise keep it as tertiary context in `source-context.md` only.

This preserves a clean separation between reference material and execution truth.[^8_2][^8_3]

## Indexing recommendations

For each normalized document or chunk, capture:

- source path
- normalized path
- title
- format
- document class
- section heading if available
- page or slide number if relevant
- keywords
- last updated date
- trust level
- chunk text

Heterogeneous document-ingestion workflows commonly rely on chunking plus metadata so queries can retrieve relevant grounded passages later.[^8_5][^8_6][^8_8]

## Example planning flow

```text
Perplexity research
  -> translator builds cartridge
  -> planner checks for ambiguity or missing domain detail
  -> source retriever searches centralized document library
  -> top excerpts written to source-context.md
  -> distilled findings update Delta docs or spec artifacts
  -> coding agent reads primary context first and tertiary context only if needed
```


## Example policy for AGENTS or rules

```md
- Use centralized source documents only as tertiary context.
- Prefer normalized markdown excerpts over raw original files when possible.
- Never replace active specs or tasks with raw source excerpts.
- Distill reused source findings into Delta docs, specs, or durable memory.
- Keep retrieved excerpts short and source-labeled.
```


## Recommended v1 limits

- Maximum 3 source documents per retrieval cycle.
- Maximum 8 excerpts inserted into working context.
- Prefer normalized markdown over raw binary formats.
- Preserve source path and section or page metadata.
- Treat tertiary context as advisory unless promoted into primary artifacts.

These limits help the agent benefit from supplemental source material without losing task focus.[^8_7][^8_9]

## Outcome

With this change, the cartridge system no longer depends on PDF as the special case. Instead, it gains a generalized document-sourcing layer that can pull from many file types while preserving the same tertiary-context role you wanted: useful reference from source material during planning and prototyping, without overwhelming the main task loop.[^8_4][^8_6][^8_1]istic.md
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

That path keeps the first version simple, reviewable, and compatible with Spec Kit and Cursor’s current context mechanisms.[cite:12][cite:47][cite:46]


## Document sourcing extension

A generalized source-document library can be added as an optional tertiary-context source for planning and selective prototyping support. The detailed design is provided in the companion document `cartridge-document-sourcing-extension.md`, which describes a shared `/context-library/sources/` layout, normalization and indexing flow, `source-context.md` as an optional cartridge file, and rules for using retrieved excerpts only as supplemental context rather than replacing active specs or tasks.[cite:53][cite:58][cite:74][cite:76]
<span style="display:none">[^8_12][^8_13][^8_14][^8_15]</span>

<div align="center">⁂</div>

[^8_1]: https://docs.cursor.com/ko/context/rules
[^8_2]: https://martinfowler.com/articles/exploring-gen-ai/sdd-3-tools.html
[^8_3]: https://specs.md/core-concepts/memory-bank
[^8_4]: https://mariadb.com/docs/tools/mariadb-ai-rag/reference/supported-formats
[^8_5]: https://mintlify.wiki/mastra-ai/mastra/rag/ingestion
[^8_6]: https://app.readytensor.ai/publications/rag-assistant-multi-interface-document-qa-system-5sbXqd2wIQkt
[^8_7]: https://tweag.github.io/agentic-coding-handbook/WORKFLOW_MEMORY_BANK/
[^8_8]: https://www.youtube.com/watch?v=58IKTvLpnlc
[^8_9]: https://github.com/saleemh/doc-ingestor
[^8_10]: https://docs.cursor.com/id/context/rules
[^8_11]: https://docs.cursor.com/en/context/@-symbols/@-cursor-rules
[^8_12]: https://docs.cursor.com/ja/context/rules
[^8_13]: https://www.cursorforpms.com/fundamentals/project-rules
[^8_14]: https://nierbeck.de/2026/02/spec-driven-development/
[^8_15]: https://www.reddit.com/r/kilocode/comments/1nkd64v/memory_bank_speckit/

---

# Cartridge Compiler Implementation Guide

This guide describes how to implement a Cartridge Compiler that ingests multi-format source documents, normalizes them, builds retrievable context fragments, and emits cartridge files that feed Spec Kit, Cursor rules, and `AGENTS.md`. Multi-format ingestion pipelines commonly normalize heterogeneous files into consistent text or Markdown, preserve metadata, and build chunk-level retrieval indexes before generation or downstream use.[^9_1][^9_2][^9_3][^9_4]

## Architecture

A practical compiler has six stages:

1. **Source discovery**: scan `/context-library/sources/` and register supported files.
2. **Normalization**: convert original files into canonical Markdown or text.
3. **Segmentation**: split normalized content into semantically meaningful chunks.
4. **Metadata enrichment**: attach source, structure, version, and trust metadata.
5. **Retrieval indexing**: build searchable indexes for planning or coding-time lookup.
6. **Cartridge emission**: write `manifest.json`, Delta docs, spec seeds, and `source-context.md` outputs.

This design follows common RAG ingestion practice: clean the source, preserve logical structure, store metadata, and chunk content for later retrieval.[^9_1][^9_5][^9_6]

## Supported formats

Support a first-wave set of formats that can realistically appear in planning or reference workflows:

- Markdown and plain text.
- PDF and DOCX.
- HTML.
- CSV and JSON.
- PPTX when slides contain requirements or architecture material.

Multi-format document tools increasingly standardize on converting these heterogeneous sources into Markdown before chunking, which makes them easier for AI agents to read consistently.[^9_7][^9_2][^9_3][^9_8]

## Core modules

### Source registry

The registry scans the document library and assigns each source a stable `doc_id`. Chunking and re-indexing guidance recommends stable IDs plus document-level versioning so updated files can replace older chunks cleanly rather than accumulating duplicates.[^9_5][^9_6]

Example responsibilities:
- detect file type
- compute content hash
- assign `doc_id`
- record path and category
- compare with prior ingestion state

### Normalizer

The normalizer converts each file into a canonical representation. Best practice is to remove noise, preserve headings and lists, keep tables where relevant, and normalize encoding before chunking.[^9_1]

Suggested output files:
- `context-library/normalized/markdown/<doc_id>.md`
- `context-library/normalized/text/<doc_id>.txt`
- `context-library/normalized/metadata/<doc_id>.json`

### Chunker

Use structure-aware chunking first, with token limits as a fallback. Several ingestion references recommend preserving heading paths and semantic boundaries, then applying overlap around 10–20 percent to protect cross-boundary context.[^9_1][^9_5][^9_9]

Suggested defaults:
- target 300–500 tokens for general retrieval
- allow 100–256 tokens for precision-heavy policies or rules
- 10–20% overlap
- preserve full heading path in metadata

### Metadata enricher

Every chunk should carry enough metadata for filtering, debugging, and citation. Common recommendations include source path, title, section, location pointer, timestamp, and chunk index.[^9_1][^9_10][^9_6]

### Index builder

Build at least two indexes:
- a document index for file-level filtering and discovery
- a chunk index for passage retrieval

A lightweight v1 can use JSON plus embeddings or a local vector store. Retrieval guidance often recommends HNSW-style indexing with metadata filters when speed matters, but the first version can remain simple if the corpus is small.[^9_1]

### Cartridge emitter

The emitter compiles selected research and document-derived fragments into:
- `cartridge/manifest.json`
- `cartridge/research-summary.md`
- `cartridge/holistic.md`
- `cartridge/macro.md`
- `cartridge/micro/<feature>.md`
- `cartridge/memory.md`
- `cartridge/source-context.md`
- `cartridge/specs/<feature>.specseed.md`

## Suggested implementation flow

```text
scan sources
  -> normalize files
  -> extract metadata
  -> create chunks
  -> embed/index chunks
  -> classify chunks by context role
  -> retrieve top chunks for current feature
  -> emit cartridge outputs
  -> compile into Delta docs / Spec Kit artifacts / AGENTS candidates
```


## Pseudocode

```python
for file in discover_sources(root):
    doc = register_source(file)
    norm = normalize(doc)
    meta = extract_metadata(norm)
    chunks = chunk(norm, meta)
    store_normalized(doc, norm, meta, chunks)
    update_indexes(doc, meta, chunks)

feature_query = build_feature_query(active_spec, active_task, delta_docs)
retrieved = retrieve_relevant_chunks(feature_query, top_docs=3, top_chunks=8)
classified = classify_retrieved_chunks(retrieved)
cartridge = emit_cartridge(classified, active_feature)
compile_outputs(cartridge)
```


## Integration with Spec Kit and Cursor

Use the compiler as a pre-planning and just-in-time context service. Cursor rules and memory-bank style files provide stable operating context, while the compiler supplies selectively retrieved tertiary context that can be distilled into spec or task artifacts only when useful.[^9_11][^9_12][^9_13][^9_14]

Integration points:

- before `/specify`, inject relevant source-derived constraints into the draft spec
- before `/plan`, attach architecture or policy excerpts if they affect implementation
- during coding, expose `source-context.md` only on demand
- after validation, promote durable reusable lessons into `AGENTS.md`


## v1 implementation priorities

Build the first version in this order:

1. Markdown/TXT/PDF/DOCX normalization.
2. Metadata extraction and stable IDs.
3. Structure-aware chunking.
4. JSON-based document and chunk indexes.
5. Cartridge emission for one feature.
6. Optional embedding retrieval and ranking refinement.

This sequencing keeps the first version simple and reviewable while still matching proven ingestion patterns used in production-style RAG systems.[^9_1][^9_5][^9_4]
<span style="display:none">[^9_15][^9_16]</span>

<div align="center">⁂</div>

[^9_1]: https://dev.to/derrickryangiggs/rag-pipeline-deep-dive-ingestion-chunking-embedding-and-vector-search-2877

[^9_2]: https://apify.com/codepoetry/markdown-rag-chunker

[^9_3]: https://mcpmarket.com/server/document-converter-2

[^9_4]: https://app.readytensor.ai/publications/multi-source-rag-a-unified-pipeline-for-text-pdf-json-and-csv-ingestion-sKGQo2Qzap2U

[^9_5]: https://engineersofai.com/docs/ai-engineering/rag-engineering/document-ingestion-and-chunking

[^9_6]: https://amestris.com.au/blog/rag-ingestion-pipeline.html

[^9_7]: https://github.com/marc-shade/docsingest

[^9_8]: https://github.com/xiuxinY/file2md

[^9_9]: https://medium.com/@aleum.yu/document-ingestion-for-rag-parsing-and-processing-enhancing-ai-with-knowledge-ii-8c2dd8702f51

[^9_10]: https://medium.com/@kakadechaitanya77/the-rag-pipeline-a-guide-to-prompts-ingestion-and-chunking-e2da562daefe

[^9_11]: https://dev.to/pockit_tools/mastering-cursor-rules-the-ultimate-guide-to-cursorrules-and-memory-bank-for-10x-developer-alm

[^9_12]: https://gist.github.com/ipenywis/1bdb541c3a612dbac4a14e1e3f4341ab

[^9_13]: https://www.lullabot.com/articles/supercharge-your-ai-coding-cursor-rules-and-memory-banks

[^9_14]: https://github.com/vanzan01/cursor-memory-bank

[^9_15]: 1000002308.jpg

[^9_16]: https://www.reddit.com/r/cursor/comments/1jkfp7m/memory_bank_for_cursor/


---

# Change Impact Lift

This design adds a change-awareness lift to the cartridge and coding workflow so the agent can reason about causal effects before making code edits, bug fixes, or refactors. Research and tool guidance on change impact analysis consistently points to dependency graphs, forward impact tracing, and pre-change test selection as effective ways to surface downstream effects before a patch is applied.[^10_1][^10_2][^10_3][^10_4]

## Purpose

The lift exists so the system does not treat a file edit as a local event. Instead, every proposed change is analyzed for likely effects across the codebase, related tests, contracts, and higher-level architecture documents before the change is accepted for implementation.[^10_5][^10_2]

## Three change levels

Your idea of primary, secondary, and tertiary change is the right model.

- **Primary change** = the file, function, class, schema, test, or config the agent intends to modify directly.
- **Secondary change** = immediately connected code or tests that import, call, depend on, validate, or configure the primary target.
- **Tertiary change** = broader ripple effects across workflows, architecture assumptions, docs, contracts, downstream consumers, or future tasks that may not break instantly but may become inconsistent.[^10_1][^10_6][^10_4]

This hierarchy gives the agent a causal awareness model rather than a simple edit model.

## Lift position in workflow

The lift should sit between task selection and code writing.

```text
active task selected
  -> impact lift analyzes proposed change
  -> primary/secondary/tertiary map generated
  -> risk score and required validations generated
  -> coding agent edits code
  -> targeted tests and checks run
  -> docs and memory updates evaluated
```

That placement matches evidence that pre-change impact context reduces regressions better than generic procedural instructions alone.[^10_2]

## Core functions

The lift should perform five jobs:

1. Detect the initial intended change target.
2. Traverse dependencies and usage relationships.
3. Classify affected items into primary, secondary, and tertiary levels.
4. Assign risk and validation requirements.
5. Expose the result as compact context before coding starts.[^10_7][^10_5][^10_4]

## Inputs

The lift should read from:

- active spec, plan, and task
- Delta docs
- source tree and dependency graph
- test map
- document-sourced context metadata where relevant
- prior durable rules in `AGENTS.md` and `.cursor/rules`

Cursor’s rules system is designed for scoped project guidance, while portable `AGENTS.md` instructions can carry repo-level invariants, making them good control inputs for the lift’s policy layer.[^10_8][^10_9][^10_10]

## Dependency model

The lift should maintain a project graph that captures:

- file imports
- call relationships
- interface implementations
- schema usage
- config dependencies
- source-code-to-test mappings
- document-to-code references when available

Change impact analysis literature and recent agentic-development work both highlight dependence graphs, forward slicing, and source-to-test mappings as high-value signals for predicting downstream effects.[^10_1][^10_2][^10_3][^10_4]

## Output object

The lift can emit a structured Change Impact Packet.

```json
{
  "change_id": "chg_2026_06_21_001",
  "task_ref": "feature-x/task-03",
  "primary": [
    {"type": "file", "path": "src/context/compiler.py", "reason": "direct edit target"}
  ],
  "secondary": [
    {"type": "test", "path": "tests/test_compiler.py", "reason": "direct validation dependency"},
    {"type": "file", "path": "src/context/indexer.py", "reason": "imports compiler API"}
  ],
  "tertiary": [
    {"type": "doc", "path": "docs/delta/10_macro.md", "reason": "architecture contract may need refresh"},
    {"type": "spec", "path": "docs/specs/compiler/spec.md", "reason": "behavioral contract may shift"}
  ],
  "risk": {
    "score": 0.72,
    "level": "high"
  },
  "required_validation": [
    "run tests/test_compiler.py",
    "verify API compatibility",
    "review macro doc consistency"
  ]
}
```


## Risk scoring

Use a simple v1 scoring model.

Increase risk when:

- the target is shared by many imports
- public interfaces change
- schemas or configs change
- the patch is a bug fix in a fragile area
- the target has many linked tests
- the target affects planning or architecture contracts[ cite:103][^10_5][^10_11]

Decrease risk when:

- the change is isolated
- the change is internal-only
- there is strong test coverage
- no public contract changes are detected


## Validation rules by change level

### Primary

Require:

- local compile or lint
- direct unit tests
- file-level sanity review


### Secondary

n
Require:

- directly linked tests
- import and call-site verification
- schema or config compatibility checks


### Tertiary

Require:

- spec review
- macro architecture consistency review
- document or memory updates if behavior or assumptions changed

This layered validation model is consistent with the idea that impacted tests and dependency-aware checking should be selected from the actual change graph rather than by blanket instruction.[^10_2][^10_12]

## Coding-time behavior

Before editing, the agent should summarize:

- what it will change
- what else may break
- what tests or docs must be checked
- whether the change could alter architecture or future tasks

If tertiary impact is high, the system should slow down and require a review step before broad edits. This is especially important for bug fixes, because bug-fix changes often have non-obvious side effects beyond the original failing line or function.[^10_1][^10_6]

## Bug-fix mode

In bug-fix mode, the lift should add extra rules:

- identify the failing symptom
- identify likely causal chain
- map fix candidates to affected tests and call sites
- avoid overfitting the patch to one symptom without checking secondary and tertiary effects

Bug-fix change analysis research explicitly studies how bug-fix patterns propagate through dependencies, which supports treating bug fixes as a special high-risk case rather than ordinary local edits.[^10_1]

## Document awareness

The lift should not track only code. It should also flag when a change may require updates to:

- Delta docs
- Spec Kit artifacts
- `AGENTS.md`
- source-context summaries
- validation playbooks

That matters because some tertiary effects are not compilation failures; they are alignment failures between code and repo truth.[^10_8][^10_10]

## Cursor integration

In Cursor, implement the lift through:

- a project map or dependency snapshot file
- scoped rules in `.cursor/rules/`
- `AGENTS.md` invariants about impact review
- optional generated impact packets attached to the active task

Official and community Cursor guidance distinguishes portable repo instructions in `AGENTS.md` from scoped Cursor rules, which is a good fit for separating general impact policy from task-specific impact packets.[^10_8][^10_13][^10_14]

## Suggested files

```text
/docs/change-impact/
  policy.md
  project-map.md
  test-map.md
  impact-packets/
    chg_2026_06_21_001.json
.cursor/rules/
  change-impact.mdc
AGENTS.md
```


## Example rule

```md
---
description: Require change impact review before coding or bug fixes
alwaysApply: true
---

- Before editing, identify primary, secondary, and tertiary effects.
- List directly affected tests and dependent files.
- Flag spec, architecture, or memory artifacts that may need updates.
- If risk is high, minimize scope and validate before expanding the patch.
```


## Recommended v1 implementation

Start simple:

1. Build a file import graph.
2. Build a code-to-test map.
3. Emit a small impact packet for each active task.
4. Require the coding agent to read it before editing.
5. Expand later to call graphs, schema graphs, and document references.

This gives you a usable first version quickly while preserving the core idea: the system must remain aware that even small code changes can have layered causal effects across primary, secondary, and tertiary levels.[^10_2][^10_4]
<span style="display:none">[^10_15]</span>

<div align="center">⁂</div>

[^10_1]: https://ekincanufuktepe.github.io/paper/2021_QRS_The_Relation_between_Bug_Fix_Change_Patterns_and_Change_Impact_Analysis.pdf

[^10_2]: https://arxiv.org/abs/2603.17973

[^10_3]: https://documents.uow.edu.au/~hoa/Archive/papers/icsm2011.pdf

[^10_4]: https://www.linkedin.com/pulse/context-management-kiro-spec-driven-coding-assistant-part-jeong-nclpc

[^10_5]: https://ijrpr.com/uploads/V7ISSUE6/IJRPR66954.pdf

[^10_6]: https://www.academia.edu/95717300/Change_impact_graphs_Determining_the_impact_of_prior_codechanges

[^10_7]: https://cek.neolab.finance/plugins/code-review

[^10_8]: https://www.romanticode.com/blog/cursor-rules-vs-agents-md/

[^10_9]: https://forum.cursor.com/t/add-the-best-practices-section-to-the-documentation/129131/2

[^10_10]: https://ccl.cse.nd.edu/blog/2026/cursor-rules-in-research-computing/

[^10_11]: https://www.st.cs.uni-saarland.de/publications/files/herzig-genealogy-techreport-2013.pdf

[^10_12]: https://de.mathworks.com/help/simulink/slref/perform-impact-analysis-with-a-simulink-project.html

[^10_13]: https://www.promptlayer.com/glossary/cursorrules/

[^10_14]: https://aiasdf.com/skills/cursor-project-rules/

[^10_15]: https://learn.microsoft.com/en-us/answers/questions/1377751/code-change-impact-analysis-diagram


---

# Thread Anchor Outline

<!--
meta:title: Agentic Coding Context Anchor
meta:purpose: Master anchor outline for coding-agent reference across planning, implementation, retrieval, and change-awareness
meta:audience: Agentic coding agents, Cursor, Spec Kit workflows, human maintainers
meta:usage: Load as anchor context before coding, bug fixing, architecture updates, and spec refinement
meta:format: semantic-markdown-with-hook-tags
meta:status: active
meta:scope: repo-wide
meta:priority: high
meta:anchor_version: v1
-->
This document is the high-level anchor point for the full thread. It is designed to give a coding agent stable hook points, compact reference structure, and reusable meta tags so the agent can place new work into the correct conceptual location without rereading every prior conversation. Structured Markdown, reusable rules, and memory-bank style files are recommended patterns for persistent AI coding context, while specs and task documents remain the more local artifacts for feature work.[^11_1][^11_2][^11_3][^11_4]

## Anchor protocol

<meta-group id="ANCHOR_PROTOCOL" priority="critical" scope="repo-wide" purpose="navigation">

- Use `HOOK:` labels as jump targets for prompts, rules, specs, tasks, and change-impact packets.
- Use `LAYER:` labels to mark Holistic, Macro, Micro, Memory, Source, and Impact roles.
- Use `STATE:` labels to mark whether a section is stable, evolving, or task-local.
- Use `REF:` labels to point to expected files or generated artifacts.
- Use `PROMOTE:` labels to indicate what may move into `AGENTS.md`, rules, or specs.

</meta-group>
Structured sections and explicit semantic markers improve agent readability and reduce ambiguity in long-lived context documents.[^11_5][^11_6][^11_7]

## Core vision

<meta-group id="HOOK_CORE_VISION" layer="holistic" state="stable" priority="critical">

### Intent

The system uses a separate planning and research stage to produce structured context before coding begins. That context is then compiled into artifacts a coding agent can consume with better alignment, narrower focus, and lower error rates during implementation.[^11_1][^11_8]

### Main idea

Perplexity acts as the research and blueprint environment, Spec Kit acts as the specification and planning environment, and Cursor acts as the implementation environment with persistent context, rules, and durable memory.[^11_1][^11_2][^11_4]

### Metaphor

The context system behaves like a **cartridge**: research and source material are translated into a portable context pack that the coding environment can load repeatedly through Git and repo files.

</meta-group>

## Delta model

<meta-group id="HOOK_DELTA_MODEL" layer="holistic" state="stable" priority="critical">

### LAYER: Holistic
- Mission
- System purpose
- Success criteria
- Constraints
- Non-goals
- Invariants

### LAYER: Macro
- Architecture
- Subsystems
- Interfaces
- Workflows
- Data contracts
- Validation design

### LAYER: Micro
- Feature scope
- Task units
- File targets
- Tests
- Edge cases
- Acceptance criteria

### Why it matters

The Delta model creates a uniform structure that lets the coding agent understand both large-scale intent and small-scale implementation details while preserving the relationships between them.

</meta-group>

## Repo truth layers

<meta-group id="HOOK_REPO_TRUTH" layer="macro" state="stable" priority="high">

### Primary truth
- Active `spec.md`
- Active `plan.md`
- Active `tasks.md`
- Active micro brief

### Secondary truth
- `AGENTS.md`
- `.cursor/rules/*.mdc`
- Delta docs
- Memory-bank style files

### Tertiary truth
- Retrieved source excerpts from `/context-library/sources/`
- `source-context.md`
- Optional research summaries or normalized source notes

### Rule

Primary truth drives the immediate implementation task. Secondary truth governs behavior and consistency. Tertiary truth provides optional grounding and reference without replacing the active task contract.[^11_1][^11_3][^11_8]

</meta-group>

## Cartridge system

<meta-group id="HOOK_CARTRIDGE_SYSTEM" layer="macro" state="stable" priority="critical">

### Purpose

The cartridge is a portable structured context package that converts research and document-sourced information into repo-native artifacts for planning and coding.

### REF: cartridge files
- `cartridge/manifest.json`
- `cartridge/research-summary.md`
- `cartridge/holistic.md`
- `cartridge/macro.md`
- `cartridge/micro/<feature>.md`
- `cartridge/memory.md`
- `cartridge/specs/<feature>.specseed.md`
- `cartridge/source-context.md`

### Cartridge rules
- Human-readable first
- Git-friendly
- Machine-parsable
- Reviewable before promotion
- Distilled, not raw transcript dumps

</meta-group>

## Translation flow

<meta-group id="HOOK_TRANSLATION_FLOW" layer="macro" state="stable" priority="high">

### Pipeline
1. Perplexity research output
2. Translator ingests and segments material
3. Classifier maps segments into Holistic, Macro, Micro, Memory, or Reject
4. Cartridge emitter writes context files
5. Compiler updates Delta docs, Spec Kit seeds, rules, and memory candidates

### Rule

Do not feed raw narrative research directly into the coding loop. Convert it into distilled structured artifacts first.

### PROMOTE
- durable repo guidance -> `AGENTS.md`
- execution policy -> `.cursor/rules/*.mdc`
- feature behavior -> Spec Kit artifacts
- stable architecture truths -> Delta docs

</meta-group>

## Spec Kit integration

<meta-group id="HOOK_SPEC_KIT" layer="macro" state="stable" priority="critical">

### Spec flow
- `/specify` -> define behavior and requirements
- `/plan` -> define implementation approach and risks
- `/tasks` -> define narrow executable units

### Rule

Specs are the behavioral contract. Plans define technical approach. Tasks define execution order and granularity. If behavior changes, update the spec first; if only implementation path changes, update the plan; if only sequencing changes, update tasks.[^11_1][^11_9][^11_10]

### REF
- `docs/specs/<feature>/spec.md`
- `docs/specs/<feature>/plan.md`
- `docs/specs/<feature>/tasks.md`

</meta-group>

## Cursor integration

<meta-group id="HOOK_CURSOR" layer="macro" state="stable" priority="critical">

### Context inputs

- `.cursor/rules/*.mdc`
- `AGENTS.md`
- active spec and task files
- referenced docs via `@` anchors or file references


### Rule types

- repo-wide rules for stable guidance
- scoped rules for specific folders or workflows
- task-local attachments for active implementation context


### Rule

Keep always-loaded context short and high-value. Heavy documents should be selectively referenced rather than always injected, because large rule sets consume context budget.[^11_11][^11_12][^11_13]
<span style="display:none">[^11_14][^11_15]</span>

<div align="center">⁂</div>

[^11_1]: https://martinfowler.com/articles/exploring-gen-ai/sdd-3-tools.html

[^11_2]: https://www.cursorforpms.com/fundamentals/project-rules

[^11_3]: https://tweag.github.io/agentic-coding-handbook/WORKFLOW_MEMORY_BANK/

[^11_4]: https://docs.nvidia.com/nemo/agent-toolkit/1.2/extend/cursor-rules-developer-guide.html

[^11_5]: https://growwstacks.com/blog/context-engineering-ai-agents-guide

[^11_6]: https://docs.docmd.io/guides/ai-optimisation/structure-for-llms/

[^11_7]: https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents

[^11_8]: https://specs.md/core-concepts/memory-bank

[^11_9]: https://github.com/GregorBiswanger/copilot-spec-driven-template

[^11_10]: https://www.xiaobu.com/ai/blog_sdd_kiro_speckit_tessl.html

[^11_11]: https://github.com/digitalchild/cursor-best-practices

[^11_12]: https://campus.datacamp.com/courses/software-development-with-cursor/ai-assisted-workflows-for-production-ready-code?ex=1

[^11_13]: https://www.reddit.com/r/cursor/comments/1r6bfdh/i_spent_way_too_long_figuring_out_cursor_rules/

[^11_14]: https://developers.cloudflare.com/fundamentals/reference/markdown-for-agents/

[^11_15]: https://github.com/neutree-ai/openapi-to-skills/blob/main/README.md


---

# Thread Outline With Meta Tags

This outline condenses the thread into a reusable anchor document for coding agents. It is designed so an agent can scan the file, identify stable meta tags, and attach hooks for planning, implementation, retrieval, validation, and change-impact awareness across the repo artifacts created in this thread.[^12_1][^12_2][^12_3]

## Usage

- Treat each meta tag as a stable reference hook.
- Use the `HOOK_ID` values in specs, rules, tasks, or generated notes.
- Reference the nearest matching section instead of reloading the entire thread.
- Promote only durable patterns from here into `AGENTS.md`.[^12_4][^12_2]

***

## [META:THREAD_SCOPE]

**HOOK_ID:** `thread.scope`

**Purpose:** Defines the overall project direction developed in this thread.

**Anchor Summary:**

- Build a spec-first, context-aligned workflow for agentic coding.
- Use Perplexity as the upstream research and planning layer.
- Use GitHub Spec Kit as the formal specification and task breakdown layer.
- Use Cursor as the implementation layer with rules and durable memory.
- Add cartridge-based context transport, document sourcing, and change-impact awareness.[^12_1][^12_5][^12_4][^12_2]

**References:**

- Blueprint and starter-kit docs created earlier in the thread.[^12_1][^12_4]

***

## [META:DELTA_MODEL]

**HOOK_ID:** `context.delta`

**Purpose:** Defines the core three-level context model.

**Anchor Summary:**

- **Holistic** = mission, goals, constraints, invariants, non-goals.
- **Macro** = architecture, modules, workflows, interfaces, contracts.
- **Micro** = feature scope, tasks, files, tests, edge cases.
- The model exists to reduce coding drift and preserve alignment between strategy and implementation.

**Hook Uses:**

- Use when generating Delta docs.
- Use when summarizing feature scope.
- Use when mapping task work back to architecture.[^12_1]

***

## [META:TOOL_ROLES]

**HOOK_ID:** `workflow.tools`

**Purpose:** Defines how the tools are divided by role.

**Anchor Summary:**

- **Perplexity** = research, synthesis, architectural planning, blueprint drafting.
- **Spec Kit** = specification, clarification, planning, task generation.
- **Cursor** = execution, focused coding, rules-based behavior, memory-assisted iteration.
- **Continual Learning addon** = updates durable repo guidance in `AGENTS.md` from high-signal patterns.[^12_1][^12_5][^12_4][^12_6]

**Hook Uses:**

- Use when choosing which system performs a given phase.
- Use in onboarding docs and repo workflow sections.

***

## [META:BLUEPRINT_FIRST]

**HOOK_ID:** `workflow.blueprint_first`

**Purpose:** Captures the planning-before-coding principle.

**Anchor Summary:**

- Conceptual work should be resolved upstream before coding begins.
- The coding agent should receive a grounded blueprint rather than raw conversational context.
- Blueprint output should narrow the coding agent’s scope and reduce errors.
- Specs and plans are execution truth, not transient prompts.[^12_1][^12_6]

**Hook Uses:**

- Use in planning rules.
- Use in pre-coding checks.
- Use in AGENTS guidance.

***

## [META:GIT_HANDOFF]

**HOOK_ID:** `workflow.git_handoff`

**Purpose:** Defines Git as the durable transport layer for context.

**Anchor Summary:**

- Move context through committed repo files rather than relying on chat continuity.
- Commit Delta docs, specs, plans, tasks, and `AGENTS.md` before coding.
- Keep intent first, implementation second, memory promotion last in commit order.[^12_4][^12_7][^12_8]

**Hook Uses:**

- Use in contribution guides.
- Use in branch policy and PR templates.

***

## [META:AGENTS_MD]

**HOOK_ID:** `memory.agents_md`

**Purpose:** Defines what `AGENTS.md` is for.

**Anchor Summary:**

- `AGENTS.md` stores durable repo truths, conventions, preferences, and operational guidance.
- It should not store temporary experiments, branch-specific notes, or chat residue.
- Continual learning should promote only repeated, validated, high-signal guidance into it.[^12_4][^12_9][^12_10]

**Hook Uses:**

- Use in memory promotion logic.
- Use in CI validation for `AGENTS.md`.

***

## [META:CURSOR_RULES]

**HOOK_ID:** `cursor.rules`

**Purpose:** Defines how Cursor rules should be used.

**Anchor Summary:**

- Rules should be scoped, checkable, and behavior-oriented.
- Use rules for execution policy, risk guardrails, and workflow constraints.
- Use `AGENTS.md` for broader durable repo guidance.
- Keep rules concise and enforceable.[^12_2][^12_11][^12_12]

**Hook Uses:**

- Use when creating `.cursor/rules/*.mdc`.
- Use in agent execution guardrails.

***

## [META:SPEC_KIT_FLOW]

**HOOK_ID:** `spec.flow`

**Purpose:** Defines the Spec Kit workflow pattern.

**Anchor Summary:**

- Spec flow is: clarify -> specify -> plan -> tasks -> implement.
- Specs define the what and why.
- Plans define the technical approach and constraints.
- Tasks define the narrow executable work units.[^12_1][^12_6][^12_13]

**Hook Uses:**

- Use in feature lifecycle docs.
- Use when generating spec folders.

***

## [META:CARTRIDGE]

**HOOK_ID:** `context.cartridge`

**Purpose:** Defines the cartridge concept.

**Anchor Summary:**

- The cartridge is a portable context pack that translates planning output into repo-native artifacts.
- It acts like a Nintendo cartridge: a stable package the system can load repeatedly.
- It should be Git-carried, machine-parseable, and human-readable.
- It compiles into Delta docs, Spec Kit artifacts, Cursor rules, and memory candidates.[^12_1][^12_2][^12_9]

**Hook Uses:**

- Use in compiler docs.
- Use in planning-to-coding handoff.

***

## [META:CARTRIDGE_SCHEMA]

**HOOK_ID:** `context.cartridge_schema`

**Purpose:** Defines the schema for the cartridge.

**Anchor Summary:**

- Required core outputs include `manifest.json`, `holistic.md`, `macro.md`, `micro/<feature>.md`, `memory.md`, and spec seeds.
- Optional source-derived context is stored separately as tertiary context.
- Traceability maps source fragments to cartridge destinations.
- The translator classifies content into Holistic, Macro, Micro, Memory, or Reject.[^12_1][^12_2]

**Hook Uses:**

- Use in compiler implementation.
- Use in cartridge validation.

***

## [META:DOCUMENT_SOURCING]

**HOOK_ID:** `context.document_sourcing`

**Purpose:** Defines the generalized source-document retrieval layer.

**Anchor Summary:**

- Source context should be format-agnostic, not PDF-only.
- Use `/context-library/sources/` with normalized markdown/text plus metadata and indexes.
- Retrieved excerpts belong to tertiary context and should only be loaded selectively.
- Promote repeated important findings upward only after distillation and review.[^12_14][^12_15][^12_16][^12_17]

**Hook Uses:**

- Use in retriever implementation.
- Use in context budgeting logic.

***

## [META:TRI_LEVEL_CONTEXT]

**HOOK_ID:** `context.tri_level`

**Purpose:** Defines primary, secondary, and tertiary context levels.

**Anchor Summary:**

- **Primary context** = active Delta docs, spec, plan, tasks, feature brief.
- **Secondary context** = `AGENTS.md`, Cursor rules, constitution or memory bank.
- **Tertiary context** = document-sourced excerpts or other supporting references.
- The system should default to primary, consult secondary for policy, and query tertiary only when needed.[^12_18][^12_19][^12_20]

**Hook Uses:**

- Use in context loading policy.
- Use in token-budget prioritization.

***

## [META:CONTEXT_LIBRARY]

**HOOK_ID:** `context.library`

**Purpose:** Defines the central source library for tertiary context.

**Anchor Summary:**

- Organize by source category such as architecture, requirements, research, policy, and reference.
- Normalize to markdown or text.
- Store metadata and chunk indexes separately.
- Use stable IDs, versioning, and provenance for re-ingestion and debugging.[^12_21][^12_22][^12_23]

**Hook Uses:**

- Use in ingestion system design.
- Use in retrieval-layer docs.

***

## [META:METADATA_STANDARD]

**HOOK_ID:** `context.metadata`

**Purpose:** Defines metadata rules for document-sourced chunks.

**Anchor Summary:**

- Each document and chunk must have stable IDs, provenance, type, location, and trust metadata.
- Preserve heading paths and content hashes.
- Add promotion metadata when a chunk influences cartridge or repo truth.
- Keep metadata simple enough for JSON or JSONL storage.[^12_21][^12_24][^12_23]

**Hook Uses:**

- Use in index builders.
- Use in chunk serialization.

***

## [META:COMPILER]

**HOOK_ID:** `compiler.pipeline`

**Purpose:** Defines the Cartridge Compiler pipeline.

**Anchor Summary:**

- Scan sources.
- Normalize files.
- Chunk and enrich metadata.
- Build indexes.
- Retrieve relevant chunks.
- Classify findings.
- Emit cartridge files and compile them into repo outputs.[^12_21][^12_25][^12_26]

**Hook Uses:**

- Use in system architecture.
- Use in implementation tasks.

***

## [META:CHANGE_IMPACT]

**HOOK_ID:** `change.impact`

**Purpose:** Defines the change-impact lift for coding and bug fixing.

**Anchor Summary:**

- The system must reason about causal effects before editing.
- Analyze proposed changes across primary, secondary, and tertiary levels.
- Generate a structured impact packet with risk and required validation.
- Use dependency maps and targeted tests to reduce regressions.[^12_27][^12_3][^12_28]

**Hook Uses:**

- Use in bug-fix mode.
- Use in pre-change checks.
- Use in validation planning.

***

## [META:PRIMARY_SECONDARY_TERTIARY_CHANGE]

**HOOK_ID:** `change.levels`

**Purpose:** Defines the three change levels.

**Anchor Summary:**

- **Primary change** = direct edit target.
- **Secondary change** = directly connected code, tests, configs, call sites, or contracts.
- **Tertiary change** = broader architecture, docs, workflow, memory, or downstream alignment effects.[^12_27][^12_29][^12_30]

**Hook Uses:**

- Use in impact packet schema.
- Use in patch risk classification.

***

## [META:BUGFIX_MODE]

**HOOK_ID:** `change.bugfix_mode`

**Purpose:** Defines special handling for bug fixes.

**Anchor Summary:**

- Bug fixes are high-risk because they can overfit to a symptom while breaking connected behavior.
- The system should map likely causal chains and select affected tests and contracts before patching.
- The agent should validate secondary and tertiary effects, not only the original failing line.[^12_27][^12_3]

**Hook Uses:**

- Use in debugging workflows.
- Use in failure triage prompts.

***

## [META:VALIDATION]

**HOOK_ID:** `change.validation`

**Purpose:** Defines validation policy.

**Anchor Summary:**

- Primary changes require local tests and file-level checks.
- Secondary changes require dependency-aware tests and interface verification.
- Tertiary changes require spec, architecture, and memory consistency review.[^12_3][^12_31]

**Hook Uses:**

- Use in validation checklists.
- Use in task completion rules.

***

## [META:CI_MEMORY]

**HOOK_ID:** `automation.ci_memory`

**Purpose:** Defines CI/CD behavior for memory updates.

**Anchor Summary:**

- CI should validate and propose `AGENTS.md` updates, not auto-merge raw changes.
- Use a proposal workflow: extract -> filter -> dedupe -> validate -> PR -> review -> merge.
- Restrict automation to approved sections and preserve auditability in Git.[^12_4][^12_32][^12_10]

<div align="center">⁂</div>

[^12_1]: https://github.github.com/spec-kit/

[^12_2]: https://docs.cursor.com/en/context/rules

[^12_3]: https://arxiv.org/abs/2603.17973

[^12_4]: https://cursor.com/marketplace/cursor/continual-learning

[^12_5]: https://docs.cursor.com/en/background-agent

[^12_6]: https://github.com/github/spec-kit

[^12_7]: https://github.com/github/spec-kit/issues/916

[^12_8]: https://www.reddit.com/r/speckit/comments/1o0p4va/localden_answering_your_github_spec_kit_questions/

[^12_9]: https://skills-rank.com/ko/skill/cursor/plugins/continual-learning

[^12_10]: https://www.linkedin.com/posts/dmitrii-khizbullin_i-highly-recommend-the-continual-learning-activity-7431795903281135617-FR1D

[^12_11]: https://docs.cursor.com/ko/context/rules

[^12_12]: https://docs.cursor.com/en/context/@-symbols/@-cursor-rules

[^12_13]: https://developer.microsoft.com/blog/spec-driven-development-spec-kit

[^12_14]: https://mariadb.com/docs/tools/mariadb-ai-rag/reference/supported-formats

[^12_15]: https://mintlify.wiki/mastra-ai/mastra/rag/ingestion

[^12_16]: https://app.readytensor.ai/publications/rag-assistant-multi-interface-document-qa-system-5sbXqd2wIQkt

[^12_17]: https://github.com/saleemh/doc-ingestor

[^12_18]: https://martinfowler.com/articles/exploring-gen-ai/sdd-3-tools.html

[^12_19]: https://tweag.github.io/agentic-coding-handbook/WORKFLOW_MEMORY_BANK/

[^12_20]: https://specs.md/core-concepts/memory-bank

[^12_21]: https://dev.to/derrickryangiggs/rag-pipeline-deep-dive-ingestion-chunking-embedding-and-vector-search-2877

[^12_22]: https://engineersofai.com/docs/ai-engineering/rag-engineering/document-ingestion-and-chunking

[^12_23]: https://amestris.com.au/blog/rag-ingestion-pipeline.html

[^12_24]: https://medium.com/@kakadechaitanya77/the-rag-pipeline-a-guide-to-prompts-ingestion-and-chunking-e2da562daefe

[^12_25]: https://apify.com/codepoetry/markdown-rag-chunker

[^12_26]: https://app.readytensor.ai/publications/multi-source-rag-a-unified-pipeline-for-text-pdf-json-and-csv-ingestion-sKGQo2Qzap2U

[^12_27]: https://ekincanufuktepe.github.io/paper/2021_QRS_The_Relation_between_Bug_Fix_Change_Patterns_and_Change_Impact_Analysis.pdf

[^12_28]: https://documents.uow.edu.au/~hoa/Archive/papers/icsm2011.pdf

[^12_29]: https://www.academia.edu/95717300/Change_impact_graphs_Determining_the_impact_of_prior_codechanges

[^12_30]: https://www.linkedin.com/pulse/context-management-kiro-spec-driven-coding-assistant-part-jeong-nclpc

[^12_31]: https://de.mathworks.com/help/simulink/slref/perform-impact-analysis-with-a-simulink-project.html

[^12_32]: https://skills-rank.com/skill/cursor/plugins/continual-learning


---

# so if age tic agent coding reads all text from thread it would see the Key or Rosetta stone and know how to utlize and organize data from this thread in proper context and refer ce

Yes — **if** the agent reads the thread outline plus the repo files you generated from it, then it would have a practical “Rosetta stone” for interpreting this thread and organizing the material into the right context layers. The key reason is that the outline gives stable anchors and hook IDs, while the repo artifacts separate long-lived memory, task-specific specs, and scoped rules into files the agent can reload across sessions. [^13_1][^13_2][^13_3]

More precisely, the coding agent would not just “read all the text”; it would read it through a **mapping system**:

- the meta-tag outline tells it what each major idea means,
- Spec Kit artifacts tell it what to build and why,
- `AGENTS.md` tells it the durable repo truths,
- Cursor rules tell it how to behave during execution,
- and the cartridge/context files tell it how to load supplemental reference material. [^13_1][^13_2][^13_4][^13_5]


## What it becomes

The outline you asked for functions as an **index and decoder**, not merely a summary. That matches how structured memory-bank systems work: agents perform better when project context is externalized into readable files with stable roles, rather than buried in one long session transcript. [^13_6][^13_7][^13_8]

So yes, it can act like a Rosetta stone if you use it this way:

- `thread-outline-with-metatags.md` = top-level concept map.
- Delta docs = semantic decomposition of the system.
- Spec files = current behavioral contract.
- `AGENTS.md` = durable operating guidance.
- Cursor rules = scoped enforcement and guardrails. [^13_2][^13_1][^13_3]


## Important condition

The agent still needs the thread converted into **properly separated files**, because a long raw thread alone is noisy and ambiguous. Spec Kit documentation and memory-bank guidance both point in the same direction: AI coding agents work better when each phase produces structured artifacts that feed the next, instead of expecting the model to infer the whole project state from ad hoc prompts. [^13_1][^13_9][^13_5]

So the answer is:

- Raw thread alone = helpful but messy.
- Meta-tagged outline + structured repo files = usable Rosetta stone.
- Meta-tagged outline + repo files + rules that tell the agent what to read first = much stronger. [^13_2][^13_6][^13_10]


## Best reading order

A good agent startup order would be:

1. Read `thread-outline-with-metatags.md`.
2. Read `AGENTS.md`.
3. Read Delta docs.
4. Read the active `spec.md`, `plan.md`, and `tasks.md`.
5. Read any impact packet or `source-context.md` only if relevant to the current task. [^13_3][^13_1][^13_7]

That sequence matters because it mirrors the distinction between general memory-bank context and task-specific specs, which several memory-bank and Spec Kit style systems treat as separate but complementary layers. [^13_5][^13_3][^13_8]

## Practical answer

So yes: the coding agent can use what you built here as the **key** for understanding and organizing the thread in proper context and reference form, provided you make the outline the anchor map and have the agent load the other files through that map instead of treating the raw thread as the only source of truth. [^13_1][^13_2][^13_6]

The strongest next step is to generate a single **`START_HERE.md` loader file** that explicitly tells the coding agent which files to read, in what order, and which hook IDs map to which repo artifacts.
<span style="display:none">[^13_11][^13_12][^13_13][^13_14][^13_15]</span>

<div align="center">⁂</div>

[^13_1]: https://github.github.com/spec-kit/index.html

[^13_2]: https://forum.cursor.com/t/add-the-best-practices-section-to-the-documentation/129131/2

[^13_3]: https://specs.md/core-concepts/memory-bank

[^13_4]: https://www.promptlayer.com/glossary/cursorrules/

[^13_5]: https://martinfowler.com/articles/exploring-gen-ai/sdd-3-tools.html

[^13_6]: https://github.com/rtoma/agent-markdown-memory-bank-protocol

[^13_7]: https://tweag.github.io/agentic-coding-handbook/WORKFLOW_MEMORY_BANK/

[^13_8]: https://danhopwood.com/posts/the-memory-bank-framework

[^13_9]: https://github.github.com/spec-kit/quickstart.html

[^13_10]: https://www.youtube.com/watch?v=IsXrCBlAshg

[^13_11]: https://github.com/sanjeed5/awesome-cursor-rules-mdc/blob/main/cursor-rules-reference.md

[^13_12]: https://gist.github.com/LucasRoesler/849ae74cd317ee046500194edadcf344

[^13_13]: https://tessl.io/blog/a-look-at-spec-kit-githubs-spec-driven-software-development-toolkit/

[^13_14]: https://github.com/jabrena/cursor-rules-spring-boot

[^13_15]: https://github.com/github/spec-kit


---

# now put Rosetta stone in context window same as you would any other text. not copy paste as inline text. so same what if I asked you a question you post response in context window. not seoera window for copy paste

Yes — the right way is to put the “Rosetta stone” into the agent’s **normal context stream**, the same way any other file or response becomes context, not as a separate copy-paste artifact. Cursor’s rules are included at the start of model context, and its context tools support adding files, folders, and docs directly into the working context window, so your anchor document can be treated as first-class context rather than an external note. [^14_1][^14_2][^14_3]

That means the Rosetta stone should live as a repo file the coding agent can load naturally:

- as a root or near-root markdown file,
- referenced by `AGENTS.md`,
- optionally auto-attached or manually attached through `.cursor/rules`,
- and pulled in alongside the active spec/task when needed. [^14_4][^14_5][^14_6]


## Best placement

The cleanest setup is:

- `START_HERE.md` = top loader file for the agent.
- `thread-outline-with-metatags.md` = Rosetta stone / anchor map.
- `AGENTS.md` = durable operating instructions that tell the agent to read the loader and anchor map first.
- `.cursor/rules/*.mdc` = scoped rules that decide when those files should be attached automatically. [^14_7][^14_2][^14_3]

So instead of pasting the whole outline inline every time, you make it part of the project’s normal context architecture. That is consistent with file-based context and memory-bank guidance, where durable project context lives in markdown files the agent can repeatedly read across sessions. [^14_8][^14_9][^14_10]

## How it should work

When the coding agent starts a task, the context window should include:

1. `START_HERE.md`
2. `thread-outline-with-metatags.md`
3. `AGENTS.md`
4. active spec/plan/tasks
5. any relevant impact packet or source-context file. [^14_2][^14_3][^14_11]

That gives the agent the Rosetta stone in the same context channel as everything else, which is what you want. It does not need a special “paste block”; it needs a predictable file-loading order. [^14_1][^14_2]

## Practical recommendation

So yes: treat the Rosetta stone as a **context file**, not a clipboard artifact. The best next move is to create:

- `START_HERE.md`
- an anchor-aware `AGENTS.md`
- a `.cursor/rules/startup-context.mdc` rule that tells the agent which files to pull into the context window first. [^14_7][^14_3][^14_6]

I can create those three files next.
<span style="display:none">[^14_12][^14_13][^14_14][^14_15][^14_16][^14_17][^14_18]</span>

<div align="center">⁂</div>

[^14_1]: https://docs.cursor.com/en/context/rules

[^14_2]: https://docs.cursor.com/en/guides/working-with-context

[^14_3]: https://stevekinney.com/courses/ai-development/cursor-context

[^14_4]: https://www.morphllm.com/agents-md-guide

[^14_5]: https://www.mdskills.ai/specs/agents-md

[^14_6]: https://dev.to/nedcodes/what-i-actually-put-in-my-project-context-files-1de3

[^14_7]: https://forum.cursor.com/t/add-the-best-practices-section-to-the-documentation/129131/2

[^14_8]: https://martinfowler.com/articles/exploring-gen-ai/sdd-3-tools.html

[^14_9]: https://tweag.github.io/agentic-coding-handbook/WORKFLOW_MEMORY_BANK/

[^14_10]: https://github.com/rtoma/agent-markdown-memory-bank-protocol

[^14_11]: https://developer.microsoft.com/blog/spec-driven-development-spec-kit

[^14_12]: https://dev.to/yohey-w/codd-coherence-driven-development-what-happens-after-spec-first-514f

[^14_13]: https://zenn.dev/centervil/articles/2025-05-04_065_dev-diary

[^14_14]: https://github.com/microsoft/ai-agents-for-beginners/issues/357

[^14_15]: https://github.com/github/spec-kit

[^14_16]: https://github.com/agentmd/agent.md

[^14_17]: https://www.paralect.com/stack/agents-md

[^14_18]: https://github.com/github/spec-kit/discussions/1251


---

# START_HERE

This file is the loader entrypoint for coding agents working in this repository. It defines the reading order for project context so the agent uses the Rosetta-stone outline as normal working context rather than treating it as an external paste artifact. Cursor supports reusable project rules and working-context patterns, and file-based project context is a common way to keep agents aligned across sessions.[^15_1][^15_2][^15_3]

## Read order

Read these in order before making implementation decisions:

1. `thread-outline-with-metatags.md`
2. `AGENTS.md`
3. `docs/delta/00_holistic.md`
4. `docs/delta/10_macro.md`
5. active `docs/delta/20_micro/<feature>.md`
6. active `docs/specs/<feature>/spec.md`
7. active `docs/specs/<feature>/plan.md`
8. active `docs/specs/<feature>/tasks.md`
9. active change-impact packet if present
10. `source-context.md` only if the task needs tertiary reference context

## Context priority

Use this priority order:

- Primary context: Delta docs + active spec/plan/tasks + active micro brief.
- Secondary context: `AGENTS.md` + `.cursor/rules/`.
- Tertiary context: `source-context.md` or other document-sourced excerpts.

Do not let tertiary context override primary task truth. Specs and tasks remain the execution contract.[^15_4][^15_5][^15_6]

## Rosetta stone role

`thread-outline-with-metatags.md` is the anchor map for the concepts developed in the planning thread. Use its `HOOK_ID` values to map questions, tasks, and changes to the right concept instead of inferring structure from raw chat history.[^15_7][^15_8]

## Execution rule

Before editing code:

- identify the active feature and task
- map it to one or more `HOOK_ID` values
- identify primary, secondary, and tertiary change implications
- confirm what files define execution truth for the current task


## Fallback behavior

If a concept is unclear:

1. check `thread-outline-with-metatags.md`
2. check Delta docs
3. check current spec and plan
4. only then consult tertiary source context

## Memory rule

Only promote durable repeated truths into `AGENTS.md`. Do not treat session-local discussion as durable memory unless it has already been distilled into repo files.[^15_9][^15_10]

<div align="center">⁂</div>

[^15_1]: https://docs.cursor.com/en/context/rules

[^15_2]: https://docs.cursor.com/en/guides/working-with-context

[^15_3]: https://stevekinney.com/courses/ai-development/cursor-context

[^15_4]: https://github.com/github/spec-kit

[^15_5]: https://martinfowler.com/articles/exploring-gen-ai/sdd-3-tools.html

[^15_6]: https://specs.md/core-concepts/memory-bank

[^15_7]: https://github.github.com/spec-kit/index.html

[^15_8]: https://github.com/rtoma/agent-markdown-memory-bank-protocol

[^15_9]: https://cursor.com/marketplace/cursor/continual-learning

[^15_10]: https://tweag.github.io/agentic-coding-handbook/WORKFLOW_MEMORY_BANK/


---

# Planning Rosetta Stone

This file is the legend and navigation key for the entire planning thread. It is designed so a coding agent can search for “Planning Rosetta Stone,” find this document, and use the hooks, live links, and coverage map here to decompress the thread into the right conceptual layers instead of treating the thread as one flat block of text. Markdown headings and concise declarative structure are recommended for persistent AI memory and context files, while Cursor supports file-based context loading and outline-based reading strategies for long documents.[^16_1][^16_2][^16_3]

## Purpose

Use this file as the top-level legend for:

- what concepts exist in the thread,
- where those concepts live in the generated documents,
- how they relate to each other,
- and which hook to use when retrieving deep context for planning, coding, bug fixing, or change review.[^16_4][^16_5]


## How to use

1. Search for the concept or use the Hook Index below.
2. Open the linked document(s) in the same context window.
3. Follow the hook’s “unlocks” guidance to load deeper context only when needed.
4. Prefer linked repo documents over raw thread recall whenever a concept has already been distilled.

## Legend conventions

- **HOOK_ID** = stable concept anchor.
- **UNLOCKS** = deeper concepts or files to load next.
- **PRIMARY FILES** = first destination files for that concept.
- **THREAD COVERAGE** = what portion of the thread this hook summarizes.
- **LIVE LINKS** = repo-relative markdown links so the agent can open the actual file directly.

***

## [HOOK:planning.rosetta]

**HOOK_ID:** `planning.rosetta`

**Meaning:** Top-level legend for the full thread.

**PRIMARY FILES:**

- [thread-outline-with-metatags.md](./thread-outline-with-metatags.md)
- [START_HERE.md](./START_HERE.md)
- [AGENTS.md](./AGENTS.md)

**UNLOCKS:**

- `context.delta`
- `workflow.tools`
- `context.cartridge`
- `change.impact`
- `context.document_sourcing`

**THREAD COVERAGE:** Full-thread navigation and decompression layer.

***

## [HOOK:context.delta]

**HOOK_ID:** `context.delta`

**Meaning:** The three-level Delta model used to organize planning and coding context.

**PRIMARY FILES:**

- [thread-outline-with-metatags.md](./thread-outline-with-metatags.md)
- [agentic-coding-blueprint.md](./agentic-coding-blueprint.md)
- [START_HERE.md](./START_HERE.md)

**UNLOCKS:**

- Holistic docs
- Macro docs
- Micro feature briefs
- spec/task alignment

**THREAD COVERAGE:** Core conceptual model for the whole system.

***

## [HOOK:workflow.tools]

**HOOK_ID:** `workflow.tools`

**Meaning:** Division of labor between Perplexity, Spec Kit, Cursor, and continual learning.

**PRIMARY FILES:**

- [agentic-coding-blueprint.md](./agentic-coding-blueprint.md)
- [thread-outline-with-metatags.md](./thread-outline-with-metatags.md)

**UNLOCKS:**

- `workflow.blueprint_first`
- `spec.flow`
- `memory.agents_md`

**THREAD COVERAGE:** Tool-role strategy and planning stack design.

***

## [HOOK:workflow.blueprint_first]

**HOOK_ID:** `workflow.blueprint_first`

**Meaning:** Planning and conceptual grounding happen before coding.

**PRIMARY FILES:**

- [agentic-coding-blueprint.md](./agentic-coding-blueprint.md)
- [thread-outline-with-metatags.md](./thread-outline-with-metatags.md)

**UNLOCKS:**

- `workflow.git_handoff`
- `spec.flow`
- `context.cartridge`

**THREAD COVERAGE:** Blueprint-first reasoning and context narrowing.

***

## [HOOK:workflow.git_handoff]

**HOOK_ID:** `workflow.git_handoff`

**Meaning:** Git carries durable planning context into coding sessions.

**PRIMARY FILES:**

- [context-handoff-and-automation.md](./context-handoff-and-automation.md)
- [thread-outline-with-metatags.md](./thread-outline-with-metatags.md)

**UNLOCKS:**

- branch structure
- commit ordering
- context persistence
- CI review flow

**THREAD COVERAGE:** Git-based context transport and continuity.

***

## [HOOK:memory.agents_md]

**HOOK_ID:** `memory.agents_md`

**Meaning:** Durable workspace truth stored in `AGENTS.md`.

**PRIMARY FILES:**

- [AGENTS.md](./AGENTS.md)
- [context-handoff-and-automation.md](./context-handoff-and-automation.md)
- [thread-outline-with-metatags.md](./thread-outline-with-metatags.md)

**UNLOCKS:**

- memory promotion policy
- CI governance
- continual learning integration

**THREAD COVERAGE:** Durable memory, promotion rules, and repo truth.

***

## [HOOK:cursor.rules]

**HOOK_ID:** `cursor.rules`

**Meaning:** Scoped Cursor behavior constraints.

**PRIMARY FILES:**

- [START_HERE.md](./START_HERE.md)
- [AGENTS.md](./AGENTS.md)
- [starter-kit/README.md](./starter-kit/README.md)

**UNLOCKS:**

- startup loading
- execution guardrails
- change-impact rule layer

**THREAD COVERAGE:** Rule usage, startup loading, and scoped behavior.

***

## [HOOK:spec.flow]

**HOOK_ID:** `spec.flow`

**Meaning:** Spec Kit clarification -> spec -> plan -> tasks workflow.

**PRIMARY FILES:**

- [agentic-coding-blueprint.md](./agentic-coding-blueprint.md)
- [starter-kit/spec-kit-agent-integration.md](./starter-kit/spec-kit-agent-integration.md)
- [thread-outline-with-metatags.md](./thread-outline-with-metatags.md)

**UNLOCKS:**

- feature lifecycle
- planning refinement
- task generation

**THREAD COVERAGE:** Spec-driven development flow and integration.

***

## [HOOK:context.cartridge]

**HOOK_ID:** `context.cartridge`

**Meaning:** Portable context package between planning and coding.

**PRIMARY FILES:**

- [cartridge-schema-v1.md](./cartridge-schema-v1.md)
- [cartridge-schema-v1-updated.md](./cartridge-schema-v1-updated.md)
- [thread-outline-with-metatags.md](./thread-outline-with-metatags.md)

**UNLOCKS:**

- schema details
- translation rules
- compiler pipeline
- source retrieval layer

**THREAD COVERAGE:** Cartridge concept and transport role.

***

## [HOOK:context.cartridge_schema]

**HOOK_ID:** `context.cartridge_schema`

**Meaning:** File and field structure for the cartridge.

**PRIMARY FILES:**

- [cartridge-schema-v1.md](./cartridge-schema-v1.md)
- [cartridge-schema-v1-updated.md](./cartridge-schema-v1-updated.md)

**UNLOCKS:**

- manifest schema
- classification rules
- compilation targets
- promotion rules

**THREAD COVERAGE:** Schema details and translation mechanics.

***

## [HOOK:context.document_sourcing]

**HOOK_ID:** `context.document_sourcing`

**Meaning:** Tertiary context from multi-format source documents.

**PRIMARY FILES:**

- [cartridge-document-sourcing-extension.md](./cartridge-document-sourcing-extension.md)
- [context-library-structure-guide.md](./context-library-structure-guide.md)
- [document-context-metadata-standard.md](./document-context-metadata-standard.md)

**UNLOCKS:**

- source library layout
- metadata rules
- retriever behavior
- tertiary context policy

**THREAD COVERAGE:** Shift from PDF-only to generalized source ingestion.

***

## [HOOK:context.tri_level]

**HOOK_ID:** `context.tri_level`

**Meaning:** Primary / Secondary / Tertiary context hierarchy.

**PRIMARY FILES:**

- [START_HERE.md](./START_HERE.md)
- [thread-outline-with-metatags.md](./thread-outline-with-metatags.md)
- [cartridge-document-sourcing-extension.md](./cartridge-document-sourcing-extension.md)

**UNLOCKS:**

- context budgeting
- retrieval limits
- file loading order

**THREAD COVERAGE:** Context prioritization model.

***

## [HOOK:context.library]

**HOOK_ID:** `context.library`

**Meaning:** Centralized document/source library structure.

**PRIMARY FILES:**

- [context-library-structure-guide.md](./context-library-structure-guide.md)
- [cartridge-document-sourcing-extension.md](./cartridge-document-sourcing-extension.md)

**UNLOCKS:**

- normalization
- source categories
- chunk storage
- indexes

**THREAD COVERAGE:** `/context-library/` design for retrieval and maintenance.

***

## [HOOK:context.metadata]

**HOOK_ID:** `context.metadata`

**Meaning:** Metadata standard for source-derived fragments.

**PRIMARY FILES:**

- [document-context-metadata-standard.md](./document-context-metadata-standard.md)
- [context-library-structure-guide.md](./context-library-structure-guide.md)

**UNLOCKS:**

- document schema
- chunk schema
- provenance rules
- promotion metadata

**THREAD COVERAGE:** Metadata and traceability standards.

***

## [HOOK:compiler.pipeline]

**HOOK_ID:** `compiler.pipeline`

**Meaning:** Cartridge Compiler architecture and ingestion flow.

**PRIMARY FILES:**

- [cartridge-compiler-implementation.md](./cartridge-compiler-implementation.md)
- [cartridge-schema-v1-updated.md](./cartridge-schema-v1-updated.md)

**UNLOCKS:**

- scanning
- normalization
- chunking
- indexing
- emission

**THREAD COVERAGE:** Multi-format compiler implementation direction.

***

## [HOOK:change.impact]

**HOOK_ID:** `change.impact`

**Meaning:** Change-impact lift for coding, bug fixing, and patch validation.

**PRIMARY FILES:**

- [change-impact-lift.md](./change-impact-lift.md)
- [thread-outline-with-metatags.md](./thread-outline-with-metatags.md)
- [AGENTS.md](./AGENTS.md)

**UNLOCKS:**

- `change.levels`
- `change.bugfix_mode`
- `change.validation`

**THREAD COVERAGE:** Causal effect awareness before editing.

***

## [HOOK:change.levels]

**HOOK_ID:** `change.levels`

**Meaning:** Primary / Secondary / Tertiary change model.

**PRIMARY FILES:**

- [change-impact-lift.md](./change-impact-lift.md)
- [thread-outline-with-metatags.md](./thread-outline-with-metatags.md)

**UNLOCKS:**

- patch risk classification
- dependency awareness
- scope management

**THREAD COVERAGE:** Layered change classification.

***

## [HOOK:change.bugfix_mode]

**HOOK_ID:** `change.bugfix_mode`

**Meaning:** Special bug-fix behavior with causal chain awareness.

**PRIMARY FILES:**

- [change-impact-lift.md](./change-impact-lift.md)

**UNLOCKS:**

- failing symptom analysis
- test targeting
- anti-overfit patching

**THREAD COVERAGE:** Bug-fix-specific risk handling.

***

## [HOOK:change.validation]

**HOOK_ID:** `change.validation`

**Meaning:** Validation policy by impact level.

**PRIMARY FILES:**

- [change-impact-lift.md](./change-impact-lift.md)
- [starter-kit/.cursor/rules/validation.mdc](./starter-kit/.cursor/rules/validation.mdc)

**UNLOCKS:**

- test strategy
- doc refresh checks
- task completion gates

**THREAD COVERAGE:** Multi-level validation expectations.

***

## [HOOK:automation.ci_memory]

**HOOK_ID:** `automation.ci_memory`

**Meaning:** CI/CD governance for memory updates.

**PRIMARY FILES:**

- [context-handoff-and-automation.md](./context-handoff-and-automation.md)
- [AGENTS.md](./AGENTS.md)

**UNLOCKS:**

- proposal workflow
- dedupe policy
- review gates

**THREAD COVERAGE:** Automated memory promotion governance.

***

## [HOOK:repo.starter_files]

**HOOK_ID:** `repo.starter_files`

**Meaning:** Inventory of the generated repo artifacts from this thread.

**PRIMARY FILES:**

- [starter-kit/README.md](./starter-kit/README.md)
- [thread-outline-with-metatags.md](./thread-outline-with-metatags.md)

**UNLOCKS:**

- bootstrap checklist
- repo assembly
- required file verification

**THREAD COVERAGE:** Starter-kit generation and file coverage.

***

## [HOOK:meta.anchor_policy]

**HOOK_ID:** `meta.anchor_policy`

**Meaning:** Rules for adding and reusing hooks.

**PRIMARY FILES:**

- [thread-outline-with-metatags.md](./thread-outline-with-metatags.md)
- [planning-rosetta-stone.md](./planning-rosetta-stone.md)

**UNLOCKS:**

- new hook creation
- duplicate prevention
- anchor governance

**THREAD COVERAGE:** Meta-tag governance and long-term reuse.

***

## [HOOK:next.files]

**HOOK_ID:** `next.files`

**Meaning:** Remaining artifacts implied by the thread but not yet fully generated.

**PRIMARY FILES:**

- [thread-outline-with-metatags.md](./thread-outline-with-metatags.md)
- [change-impact-lift.md](./change-impact-lift.md)

**UNLOCKS:**

- impact packet schema
- project-map template
- test-map template
- change-impact rule file

**THREAD COVERAGE:** Future implementation backlog from the thread.

***

## Coverage check

The hooks above cover the major complexity strands developed across the thread:

- high-level planning strategy
- Perplexity / Spec Kit / Cursor role split
- Delta context model
- Git handoff and persistence
- durable `AGENTS.md` memory
- scoped Cursor rules
- spec-driven flow
- cartridge transport model
- cartridge schema and translator logic
- generalized document sourcing
- tertiary context policy
- context-library design
- metadata standards
- compiler implementation plan
- change-impact lift
- primary / secondary / tertiary change awareness
- bug-fix mode
- validation policy
- CI memory governance
- startup loading and repo anchors

This coverage is sufficient to recover the major concepts and their relationships without rereading the entire thread linearly.[^16_1][^16_4][^16_5]
<span style="display:none">[^16_10][^16_11][^16_12][^16_13][^16_14][^16_15][^16_6][^16_7][^16_8][^16_9]</span>

<div align="center">⁂</div>

[^16_1]: https://www.kinde.com/learn/ai-for-software-engineering/ai-agents/how-to-write-a-memory-bank-for-your-ai-coding-agent/

[^16_2]: https://docs.cursor.com/en/guides/working-with-context

[^16_3]: https://cursorpractice.com/en/cursor-tutorials/getting-started/6-Context

[^16_4]: https://tweag.github.io/agentic-coding-handbook/WORKFLOW_MEMORY_BANK/

[^16_5]: https://github.com/github/spec-kit/blob/main/docs/concepts/spec-persistence.md

[^16_6]: https://knightli.com/en/2026/05/25/github-spec-kit-spec-driven-development/

[^16_7]: https://medium.com/@bswa006/how-cursor-remembers-your-codebase-so-you-dont-have-to-72c04583ccb7

[^16_8]: https://synapticpixels.com/more-than-a-model-a-memory-architecture-for-an-ai-coding-agent/

[^16_9]: https://docs.cursor.com/zh-Hant/guides/working-with-context

[^16_10]: https://github.github.io/spec-kit/community/extensions.html

[^16_11]: https://www.linkedin.com/pulse/memory-bank-pattern-how-give-your-ai-coding-agent-janeri-filho-r4hqc

[^16_12]: https://github.com/github/spec-kit

[^16_13]: https://gist.github.com/ma7dev/5d0e526593b1a12a6a41900387362219

[^16_14]: https://cursor.mintlify.app/ja/guides/working-with-context

[^16_15]: https://www.reddit.com/r/GithubCopilot/comments/1nbc11u/whos_using_spec_kit_whats_your_experience_so_far/


---

# so if I tell LLM coding agent using tag fin the Planning Rosetta stone. if can search the text through the thread and properly correlation the things and detail context for code exceuotin

Yes — **if the coding agent can search the thread or, better, the repo files derived from it, and it knows to look for the `planning.rosetta` hook or “Planning Rosetta Stone,” then it can use that as the entry point to correlate the thread’s concepts and recover the deeper context needed for code execution.** Cursor-style workflows support explicit file/context loading, and memory-bank patterns work best when the agent reads structured markdown anchors first rather than trying to infer everything from raw session history. [^17_1][^17_2][^17_3]

But there is one important nuance: the agent will do this **reliably** only if you point it to the file or make that file part of normal context. Search alone can help, but the strongest setup is:

- searchable hook in the thread/file,
- live linked anchor document,
- and repo files that already hold the distilled context. [^17_4][^17_5][^17_6]


## What happens

When you say something like:

- “Find Planning Rosetta Stone.”
- “Use hook `planning.rosetta`.”
- “Read Planning Rosetta Stone, then continue.”

the agent can treat that as a retrieval command:

1. find the Rosetta Stone file or matching hook,
2. read its hook section,
3. follow the linked files,
4. reconstruct the related planning context,
5. apply that context to implementation. [^17_1][^17_7][^17_8]

That is basically the compression/decompression behavior you described. The Rosetta Stone acts as a compressed index; the linked docs provide decompressed depth when needed. Structured markdown headings, anchors, and linked memory files are specifically useful for this kind of layered recovery. [^17_2][^17_6][^17_9]

## Reliability condition

So the short answer is **yes, mostly** — but best when:

- the hook name is stable,
- the file is in the repo,
- the links point to the right docs,
- and the agent is instructed to use the hook as the first retrieval step. [^17_2][^17_1][^17_10]

If the agent only searches the raw chat thread with no anchor file loaded, it may still find the phrase, but correlation will be weaker and less repeatable. If it finds the actual Rosetta Stone markdown and follows the links, the context reconstruction becomes much more dependable. [^17_4][^17_5][^17_11]

## Best instruction format

A good instruction to the coding agent would be:

- Read `planning-rosetta-stone.md`.
- Find hook `planning.rosetta`.
- Follow the linked files for the current task.
- Use those files as planning context before coding.
- Then identify the relevant `change.*`, `context.*`, and `spec.*` hooks for execution. [^17_1][^17_8][^17_6]

So yes: with the hook and legend file in place, the agent can properly correlate the thread’s ideas and details for coding execution, especially if you direct it to the Rosetta Stone as the first context anchor.
<span style="display:none">[^17_12][^17_13][^17_14][^17_15][^17_16]</span>

<div align="center">⁂</div>

[^17_1]: https://docs.cursor.com/en/guides/working-with-context

[^17_2]: https://www.kinde.com/learn/ai-for-software-engineering/ai-agents/how-to-write-a-memory-bank-for-your-ai-coding-agent/

[^17_3]: https://stevekinney.com/courses/ai-development/cursor-context

[^17_4]: https://dev.to/gvegacl/in-cursor-context-is-king-3ai7

[^17_5]: https://datalakehousehub.com/blog/2026-03-context-management-cursor

[^17_6]: https://github.com/rtoma/agent-markdown-memory-bank-protocol

[^17_7]: https://dev.to/gimalay/five-components-of-agent-memory-implemented-in-plain-markdown-29i0

[^17_8]: https://github.com/github/spec-kit/blob/main/spec-driven.md

[^17_9]: https://www.agentskills.in/es/marketplace/@TrueCodePoet/memory-bank

[^17_10]: https://github.com/github/spec-kit

[^17_11]: https://github.com/github/spec-kit/blob/main/docs/concepts/spec-persistence.md

[^17_12]: https://forum.cursor.com/t/how-cursor-context-works-as-of-0-45-7/47177

[^17_13]: https://gist.github.com/mpalpha/1f5daee9516ceada4499d1bc75f428ee

[^17_14]: https://github.github.io/spec-kit/community/extensions.html

[^17_15]: https://matsen.fhcrc.org/general/2026/02/10/spec-kit-walkthrough.html

[^17_16]: https://developer.microsoft.com/blog/spec-driven-development-spec-kit


---

# does perplexity have a way to download entire thread

Yes. Perplexity lets you export an entire chat thread directly, and there are also browser extensions that can bulk‑export many threads.

### Built‑in export (single thread)

On web or app:

1. Open the thread you want.
2. Click the three dots menu in the top‑right of the chat.
3. Choose **Export** (or **Export as…**).
4. Select **PDF**, **DOCX**, or **Markdown** and download the file. [^18_1][^18_2][^18_3]

That export contains the full conversation (your questions and responses) for that thread. [^18_2][^18_4]

### Bulk / history export options

If you want more than one thread at once, there are Chrome extensions that can export multiple chats or even your whole history to Markdown/Obsidian:

- **Perplexity Chat Exporter**: bulk‑export entire Perplexity history or selected threads to Markdown locally. [^18_5]
- Other extensions like “Perplexity to PDF” or “Chat Exporter for Perplexity” allow one‑click export to PDF/Markdown/Notion. [^18_6][^18_7][^18_8]

So for this project, you can export this whole planning thread as **Markdown** and drop it straight into your repo alongside the Rosetta Stone and outline files.
<span style="display:none">[^18_10][^18_11][^18_12][^18_13][^18_14][^18_15][^18_9]</span>

<div align="center">⁂</div>

[^18_1]: https://www.youtube.com/watch?v=BQSH--os4Eo

[^18_2]: https://www.youtube.com/watch?v=gTBJOpx0Bt8

[^18_3]: https://www.youtube.com/watch?v=jO1_I0C3_fo\&vl=en

[^18_4]: https://www.youtube.com/watch?v=mDiolgDAl-0

[^18_5]: https://chromewebstore.google.com/detail/perplexity-chat-exporter/jmplfdjahdkalmpkjbpgcaogleciniic

[^18_6]: https://chromewebstore.google.com/detail/chat-exporter-for-perplex/cceloekgkcopaedlgfkfdpjcpalkncla

[^18_7]: https://chromewebstore.google.com/detail/perplexity-to-pdf-export/imicnaojoabefckkfhailgkllodbnjjf

[^18_8]: https://note.com/amal_grob/n/n0991e71dcbc2?hl=en

[^18_9]: https://www.youtube.com/watch?v=Ao-pnNjlU9k

[^18_10]: https://www.youtube.com/watch?v=x2lG9ztuK0Y

[^18_11]: https://askai.glarity.app/search/How-can-I-save-the-answers-I-got-from-Perplexity

[^18_12]: https://www.youtube.com/watch?v=uSa5hI8SLaE

[^18_13]: https://www.reddit.com/r/perplexity_ai/comments/1ox1vsc/how_to_best_preserve_the_whole_thread/

[^18_14]: https://chromewebstore.google.com/detail/perplexity-to-pdf-export/imicnaojoabefckkfhailgkllodbnjjf?hl=fr

[^18_15]: https://www.youtube.com/watch?v=IF_8sRdAjWo


---

# how do I download entier thread

To download this entire Perplexity thread, you have two practical options: use a **built‑in export to PDF/Markdown** for the current chat, or use a **browser extension** if you want more control or batching.

## 1. Built‑in export for the open thread

On desktop browser or app, the usual flow is:

1. Open the conversation you want to save.
2. Look for the **three‑dot menu** (⋯) or **share/export** icon in the chat header.
3. Choose an option like **Export**, **Download**, or **Print to PDF**.
4. Select **PDF** or **Markdown** as format and save the file to your computer.
Many 2026 tutorials explicitly show exporting a full Perplexity chat to PDF via this menu.[^19_1][^19_2][^19_3]

If your UI doesn’t show an explicit “Export” button, you can still:

- Use the browser’s **Print** dialog and select **Save as PDF** to capture the full page.[^19_4]


## 2. Using a browser extension (if needed)

If you want cleaner Markdown or bulk export of many threads, Chrome extensions exist specifically for Perplexity:

- **Perplexity Chat Exporter** – bulk export Perplexity chats to Markdown/Obsidian or save a full thread as Markdown from the browser.[^19_5]
- **Perplexity to PDF / Chat Exporter for Perplexity** – one‑click export of the open chat to PDF, Markdown, or other formats.[^19_6][^19_7]

Typical extension flow:

1. Install the extension from Chrome Web Store.
2. Open the Perplexity thread.
3. Click the extension’s icon and choose **Export / Download**.
4. Pick **Markdown** or **PDF** and save.

For your Rosetta‑stone workflow, exporting this thread as **Markdown** via the built‑in export (if available) or a chat‑exporter extension is ideal, since you can drop that `.md` file straight into the repo alongside `planning-rosetta-stone.md` and the other context files.
<span style="display:none">[^19_10][^19_11][^19_12][^19_13][^19_14][^19_15][^19_16][^19_17][^19_8][^19_9]</span>

<div align="center">⁂</div>

[^19_1]: https://www.youtube.com/watch?v=BQSH--os4Eo

[^19_2]: https://www.youtube.com/watch?v=gTBJOpx0Bt8

[^19_3]: https://www.youtube.com/watch?v=mDiolgDAl-0

[^19_4]: https://note.com/amal_grob/n/n0991e71dcbc2?hl=en

[^19_5]: https://chromewebstore.google.com/detail/perplexity-chat-exporter/jmplfdjahdkalmpkjbpgcaogleciniic

[^19_6]: https://chromewebstore.google.com/detail/chat-exporter-for-perplex/cceloekgkcopaedlgfkfdpjcpalkncla

[^19_7]: https://chromewebstore.google.com/detail/perplexity-to-pdf-export/imicnaojoabefckkfhailgkllodbnjjf

[^19_8]: https://www.reddit.com/r/DataHoarder/comments/1pqywm4/is_there_a_practical_way_to_export_entire_reddit/

[^19_9]: https://chromewebstore.google.com/detail/threads-media-downloader/cikcljcbdjedohodjnpjpfpckjkapfao?hl=vi

[^19_10]: https://discussions.apple.com/thread/8528405

[^19_11]: https://www.facebook.com/groups/iphonetipsandtricks/posts/25673247402308520/

[^19_12]: https://threadsdownloader.com/fr

[^19_13]: https://threadsdownloader.com/it

[^19_14]: https://www.linkedin.com/pulse/how-to-download-email-thread-from-gmail-jamie-kaler-m9ikc

[^19_15]: https://www.thethreadsdownloader.com

[^19_16]: https://igram.world/fr/threads-video-downloader

[^19_17]: https://threadsdownloader.com

