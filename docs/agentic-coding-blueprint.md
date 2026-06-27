<!--
meta:hook_id: workflow.tools
meta:source: HIVE_PLANNING_DEV.md
meta:status: extracted
-->

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