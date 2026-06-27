<!--
meta:hook_id: change.impact
meta:source: HIVE_PLANNING_DEV.md
meta:status: extracted
-->

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