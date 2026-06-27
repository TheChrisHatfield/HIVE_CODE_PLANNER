<!--
meta:title: Thread Outline With Meta Tags
meta:hook_id: meta.anchor_policy
meta:purpose: Condensed anchor document with stable meta tags and HOOK_ID values
meta:usage: Secondary map after Planning Rosetta Stone; use HOOK_ID in specs, rules, and tasks
meta:status: active
meta:scope: repo-wide
meta:priority: high
-->
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
- Blueprint output should narrow the coding agentâ€™s scope and reduce errors.
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

