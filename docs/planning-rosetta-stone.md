<!--
meta:title: Planning Rosetta Stone
meta:hook_id: planning.rosetta
meta:search: Planning Rosetta Stone
meta:purpose: Legend and navigation key for the full planning thread
meta:audience: Agentic coding agents, Cursor, human maintainers
meta:usage: Search for "Planning Rosetta Stone" or hook planning.rosetta before planning or coding
meta:format: semantic-markdown-with-hook-tags
meta:status: active
meta:scope: repo-wide
meta:priority: critical
meta:anchor_version: v1
-->
# Planning Rosetta Stone

This file is the legend and navigation key for the entire planning thread. It is designed so a coding agent can search for "Planning Rosetta Stone," find this document, and use the hooks, live links, and coverage map here to decompress the thread into the right conceptual layers instead of treating the thread as one flat block of text. Markdown headings and concise declarative structure are recommended for persistent AI memory and context files, while Cursor supports file-based context loading and outline-based reading strategies for long documents.[^16_1][^16_2][^16_3]

## Purpose

Use this file as the top-level legend for:

- what concepts exist in the thread,
- where those concepts live in the generated documents,
- how they relate to each other,
- and which hook to use when retrieving deep context for planning, coding, bug fixing, or change review.[^16_4][^16_5]


## How to use

1. Search for the concept or use the Hook Index below.
2. Open the linked document(s) in the same context window.
3. Follow the hook's "unlocks" guidance to load deeper context only when needed.
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
- [START_HERE.md](../START_HERE.md)
- [AGENTS.md](../AGENTS.md)

**UNLOCKS:**

- `context.delta`
- `workflow.tools`
- `context.cartridge`
- `change.impact`
- `context.document_sourcing`
- `memory.shared_graph`
- `representation.graph_native`

**THREAD COVERAGE:** Full-thread navigation and decompression layer.

***

## [HOOK:context.delta]

**HOOK_ID:** `context.delta`

**Meaning:** The three-level Delta model used to organize planning and coding context.

**PRIMARY FILES:**

- [thread-outline-with-metatags.md](./thread-outline-with-metatags.md)
- [agentic-coding-blueprint.md](./agentic-coding-blueprint.md)
- [START_HERE.md](../START_HERE.md)

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

- [AGENTS.md](../AGENTS.md)
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

- [START_HERE.md](../START_HERE.md)
- [AGENTS.md](../AGENTS.md)
- [starter-kit/README.md](../starter-kit/README.md)

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
- [starter-kit/spec-kit-agent-integration.md](../starter-kit/spec-kit-agent-integration.md)
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

- [START_HERE.md](../START_HERE.md)
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
- [AGENTS.md](../AGENTS.md)

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
- [starter-kit/.cursor/rules/validation.mdc](../starter-kit/.cursor/rules/validation.mdc)

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
- [AGENTS.md](../AGENTS.md)

**UNLOCKS:**

- proposal workflow
- dedupe policy
- review gates

**THREAD COVERAGE:** Automated memory promotion governance.

***

## [HOOK:integration.cl_spec]

**HOOK_ID:** `integration.cl_spec`

**Meaning:** Continual Learning and Spec Kit integration — behavioral truth in specs, operational truth in AGENTS.md.

**PRIMARY FILES:**

- [cl-spec-integration.md](./cl-spec-integration.md)
- [context-handoff-and-automation.md](./context-handoff-and-automation.md)
- [../starter-kit/spec-kit-agent-integration.md](../starter-kit/spec-kit-agent-integration.md)
- [../.cursor/rules/cl-spec-integration.mdc](../.cursor/rules/cl-spec-integration.mdc)

**UNLOCKS:**

- `spec.flow`
- `memory.agents_md`
- `automation.ci_memory`
- `change.validation`

**THREAD COVERAGE:** Memory/spec drift governance and CL candidate rejection policy.

***

## [HOOK:workflow.project_bootstrap]

**HOOK_ID:** `workflow.project_bootstrap`

**Meaning:** Bootstrap a new Hive agent profile directory from starter templates via `hive_planner init`.

**PRIMARY FILES:**

- [project-bootstrap-guide.md](./project-bootstrap-guide.md)
- [specs/project-bootstrap-v1/spec.md](./specs/project-bootstrap-v1/spec.md)
- [specs/starter-kit-v2/spec.md](./specs/starter-kit-v2/spec.md)
- [../src/hive_planner/bootstrap.py](../src/hive_planner/bootstrap.py)

**UNLOCKS:**

- one-folder-one-profile workflow
- starter-kit / bootstrap_templates copy
- detectable repo root via `is_repo_root()`
- `--profile full` starter-kit v2 (pyproject, CI stub, src/tests)
- optional `--git-init`

**THREAD COVERAGE:** New project scaffolding without mutating Hive source tree.

***

## [HOOK:repo.starter_files]

**HOOK_ID:** `repo.starter_files`

**Meaning:** Inventory of the generated repo artifacts from this thread.

**PRIMARY FILES:**

- [starter-kit/README.md](../starter-kit/README.md)
- [thread-outline-with-metatags.md](./thread-outline-with-metatags.md)

**UNLOCKS:**

- bootstrap checklist
- repo assembly
- required file verification

**THREAD COVERAGE:** Starter-kit generation and file coverage.

***

## [HOOK:memory.shared_graph]

**HOOK_ID:** `memory.shared_graph`

**Meaning:** Temporary and permanent shared knowledge stores for Hive — repos offload graph reflections; a promote gate curates into permanent memory.

**PRIMARY FILES:**

- [delta/20_micro/shared-graph-memory-v1.md](./delta/20_micro/shared-graph-memory-v1.md)
- [specs/shared-graph-memory-v1/spec.md](./specs/shared-graph-memory-v1/spec.md)
- [../src/hive_planner/graph_store.py](../src/hive_planner/graph_store.py)

**UNLOCKS:**

- `representation.graph_native`
- staging vs permanent tiers
- CLI `graph offload` / `graph promote`

**THREAD COVERAGE:** HIVE_CODE_DEV_1 shared-memory architecture (temp/permanent, hub curation).

***

## [HOOK:representation.graph_native]

**HOOK_ID:** `representation.graph_native`

**Meaning:** Knowledge as typed graph nodes and labeled edges (not flat documents); text is interchange, graph is the compute representation.

**PRIMARY FILES:**

- [specs/shared-graph-memory-v1/spec.md](./specs/shared-graph-memory-v1/spec.md)
- [delta/20_micro/shared-graph-memory-v1.md](./delta/20_micro/shared-graph-memory-v1.md)
- [delta/10_macro.md](./delta/10_macro.md)

**UNLOCKS:**

- node/edge schema
- relationship types (`supports`, `depends_on`, …)
- promote rules for dangling endpoints

**THREAD COVERAGE:** Graph-node design discussion from HIVE_CODE_DEV_1.

***

## [HOOK:meta.anchor_policy]

**HOOK_ID:** `meta.anchor_policy`

**Meaning:** Rules for adding and reusing hooks.

**PRIMARY FILES:**

- [thread-outline-with-metatags.md](./thread-outline-with-metatags.md)
- [planning-rosetta-stone-generation-template.md](./planning-rosetta-stone-generation-template.md)
- [planning-rosetta-stone.md](./planning-rosetta-stone.md)

**UNLOCKS:**

- new hook creation
- duplicate prevention
- anchor governance
- Rosetta generation for other agentic systems

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
- shared graph memory (staging/permanent)
- graph-native representation

This coverage is sufficient to recover the major concepts and their relationships without rereading the entire thread linearly.[^16_1][^16_4][^16_5]
