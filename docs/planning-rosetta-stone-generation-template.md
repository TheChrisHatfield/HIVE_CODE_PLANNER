<!--
meta:title: Planning Rosetta Stone Generation Template
meta:hook_id: meta.anchor_policy
meta:search: generate Planning Rosetta Stone template agentic systems
meta:purpose: Unified template and procedure for any agentic system to author a repo hook map
meta:audience: Perplexity, Spec Kit, Cursor, Claude, GPT, Hive bootstrap agents, human maintainers
meta:usage: Follow this file when creating or extending docs/planning-rosetta-stone.md in any Hive-aligned repo
meta:format: semantic-markdown-with-hook-tags
meta:status: active
meta:scope: repo-wide
meta:priority: critical
meta:anchor_version: v1
-->
# Planning Rosetta Stone — Generation Template

**Hook:** `meta.anchor_policy` · **Search:** `generate Planning Rosetta Stone`

> **Upload to external AIs (Perplexity, Gemini, ChatGPT):** use the standalone
> [`ROSETTA-PLANNING-SESSION-CONTRACT.md`](./ROSETTA-PLANNING-SESSION-CONTRACT.md) —
> self-contained instructions + inline marker rules. No repo context required.

Use this document when **authoring or extending** a repo’s Planning Rosetta Stone inside a Hive checkout.

**Canonical output file:** `docs/planning-rosetta-stone.md`  
**Reference instance (full thread):** [`planning-rosetta-stone.md`](./planning-rosetta-stone.md)  
**Secondary meta map:** [`thread-outline-with-metatags.md`](./thread-outline-with-metatags.md)

---

## What you are generating

A **Planning Rosetta Stone** is a searchable legend that maps stable concept hooks (`HOOK_ID`) to repo files. Coding agents load it first so they decompress planning context by hook instead of re-reading raw chat or a monolithic archive.

| Field | Role |
|-------|------|
| **Search phrase** | Human/agent retrieval anchor — always include `Planning Rosetta Stone` |
| **Hook ID** | Stable machine anchor — dot notation, lowercase (`planning.rosetta`) |
| **PRIMARY FILES** | First files to open for that concept |
| **UNLOCKS** | Related hooks to load next (lazy depth) |
| **THREAD COVERAGE** | What part of the planning thread this hook summarizes |

---

## When to generate

Generate or refresh a Rosetta Stone when:

1. **Bootstrapping a new project** — slim hook map for Delta, rules, change-impact, optional Spec Kit / CL.
2. **Distilling a long planning thread** — full hook index covering every major concept strand.
3. **Adding a new cross-cutting concern** — new hook + PRIMARY FILES + UNLOCKS; never bury concepts only in chat.
4. **Promoting durable patterns** — after validation, mirror critical hooks in `AGENTS.md` and `.cursor/rules/`.

Do **not** replace Delta specs, plans, or tasks with the Rosetta Stone. It is navigation metadata, not execution truth.

---

## Agent workflow (all systems)

Follow this order when generating from a planning thread or blueprint:

1. **Inventory concepts** — list mission, tools, context layers, workflows, validation, and integration points.
2. **Assign HOOK_ID values** — one stable ID per concept; prefer existing IDs from the catalog below.
3. **Map PRIMARY FILES** — repo-relative markdown links only; every link must resolve or be marked `(planned)`.
4. **Wire UNLOCKS** — declare depth order; avoid circular unlock chains.
5. **Write the root hook** — `planning.rosetta` must unlock the top-level concept set.
6. **Add companion anchors** — patch `AGENTS.md` and `START_HERE.md` (templates below).
7. **Optional secondary layer** — for thread distillation, also produce or update `docs/thread-outline-with-metatags.md`.
8. **Validate** — run the checklist at the end of this file.

**Tool roles (typical division):**

| System | Rosetta phase |
|--------|----------------|
| **Perplexity / research agent** | Draft full hook index from thread; propose HOOK_ID + coverage |
| **Spec Kit** | Reference hooks in spec/plan/tasks; use navigation blocks |
| **Cursor / coding agent** | Load Rosetta first; follow PRIMARY FILES; patch missing nav |
| **Hive `init` / bootstrap** | Emit slim project Rosetta from this template |
| **Continual Learning** | Promote durable hook policy into `AGENTS.md`; do not duplicate full index |

---

## File placement and discovery

| File | Required | Purpose |
|------|----------|---------|
| `docs/planning-rosetta-stone.md` | **Yes** | Hook legend (this template’s output) |
| `START_HERE.md` | **Yes** | Loader entry; links Rosetta + read order |
| `AGENTS.md` | **Yes** | Durable ops; includes Rosetta anchor section |
| `docs/thread-outline-with-metatags.md` | Thread distillation only | Secondary meta-tag map |
| `docs/delta/00_holistic.md` | Recommended | Holistic layer |
| `docs/delta/10_macro.md` | Recommended | Macro layer |
| `docs/delta/20_micro/<feature>.md` | Per feature | Micro briefs |

**Discovery contract (must appear in output):**

- Search phrase: `Planning Rosetta Stone`
- Root hook: `planning.rosetta`
- Path: `docs/planning-rosetta-stone.md`

---

## Document skeleton (copy and fill)

Replace `{PROJECT_NAME}`, `{VERSION}`, and hook blocks. Keep the HTML comment metadata block at the top.

```markdown
<!--
meta:title: Planning Rosetta Stone
meta:hook_id: planning.rosetta
meta:search: Planning Rosetta Stone
meta:purpose: Legend and navigation key for the planning thread
meta:audience: Agentic coding agents, human maintainers
meta:usage: Search for "Planning Rosetta Stone" or hook planning.rosetta before planning or coding
meta:format: semantic-markdown-with-hook-tags
meta:status: active
meta:scope: repo-wide
meta:priority: critical
meta:anchor_version: v1
-->
# Planning Rosetta Stone — {PROJECT_NAME}

This file is the legend and navigation key for the project’s planning context. Search for **Planning Rosetta Stone** or hook `planning.rosetta` before planning or coding.

## Purpose

Use this file to find:

- what concepts exist,
- where they live in the repo,
- how they relate,
- which hook to load for planning, coding, bug fixing, or change review.

## How to use

1. Search for the concept or use the Hook Index below.
2. Open PRIMARY FILES in the same context window.
3. Follow UNLOCKS only when deeper detail is needed.
4. Prefer linked repo documents over raw thread recall.

## Legend conventions

- **HOOK_ID** — stable concept anchor (`domain.name`).
- **UNLOCKS** — deeper hooks or files to load next.
- **PRIMARY FILES** — first destination files for that concept.
- **THREAD COVERAGE** — portion of planning material summarized by this hook.
- **LIVE LINKS** — repo-relative markdown links.

***

## [HOOK:planning.rosetta]

**HOOK_ID:** `planning.rosetta`

**Meaning:** Top-level legend for the project.

**PRIMARY FILES:**

- [START_HERE.md](../START_HERE.md)
- [AGENTS.md](../AGENTS.md)
- [delta/00_holistic.md](delta/00_holistic.md)

**UNLOCKS:**

- `context.delta`
- `cursor.rules`
- `change.impact`

**THREAD COVERAGE:** Full-project navigation layer.

***

<!-- Repeat one [HOOK:...] block per concept (see Hook entry template below) -->

## Coverage check

List the major strands this Rosetta covers and confirm each has a HOOK_ID entry.
```

---

## Hook entry template (repeat per concept)

```markdown
## [HOOK:{namespace}.{name}]

**HOOK_ID:** `{namespace}.{name}`

**Meaning:** {One sentence — what this concept is.}

**PRIMARY FILES:**

- [{relative-path}]({relative-path})
- [{relative-path}]({relative-path})

**UNLOCKS:**

- `{related.hook}`
- `{related.hook}`

**THREAD COVERAGE:** {What planning material this hook summarizes.}
```

**Naming rules:**

- Use lowercase dot notation: `context.delta`, `workflow.tools`, `change.bugfix_mode`.
- Never reuse a HOOK_ID for a different meaning.
- Prefer extending an existing hook’s PRIMARY FILES over inventing near-duplicate IDs.
- Root hook is always `planning.rosetta`.

---

## Minimum hook catalog (new projects)

Every bootstrapped Hive-aligned repo should include at least:

| HOOK_ID | Meaning | Typical PRIMARY FILES |
|---------|---------|------------------------|
| `planning.rosetta` | This legend | `START_HERE.md`, `AGENTS.md` |
| `context.delta` | Holistic / macro / micro model | `docs/delta/00_holistic.md`, `docs/delta/10_macro.md`, `docs/delta/20_micro/` |
| `cursor.rules` | Scoped agent behavior | `.cursor/rules/*.mdc` |
| `change.impact` | Pre-edit impact awareness | `docs/change-impact/policy.md` |
| `change.bugfix_mode` | Bug-fix causal chain mode | `docs/change-impact/policy.md` |

**Add when integrated:**

| HOOK_ID | When |
|---------|------|
| `spec.flow` | Spec Kit enabled |
| `integration.cl_spec` | Spec Kit + Continual Learning unified handoff |
| `workflow.project_bootstrap` | Hive `init` / scaffold docs |
| `memory.agents_md` | CL promotes into `AGENTS.md` |
| `compiler.pipeline` | Hive cartridge compiler wired |
| `context.document_sourcing` | Context library / tertiary sources |

**Full thread distillation** — add hooks from the [reference Rosetta Stone](./planning-rosetta-stone.md) as concepts appear (cartridge, metadata, CI memory, validation, etc.).

---

## Slim vs full Rosetta

| Tier | When | Shape |
|------|------|--------|
| **Slim** | `hive_planner init`, small projects | Title + core hook table + PRIMARY FILES list |
| **Full** | Hive source repo, long planning threads | Every hook as `[HOOK:...]` block with UNLOCKS + THREAD COVERAGE + coverage check |

Slim example (table form is acceptable for v1 projects):

```markdown
# Planning Rosetta Stone — My App

Search phrase: **Planning Rosetta Stone** · Hook: `planning.rosetta`

## Core hooks

| HOOK_ID | Meaning |
|---------|---------|
| `planning.rosetta` | This legend |
| `context.delta` | Holistic / macro / micro docs |
| `cursor.rules` | `.cursor/rules/*.mdc` |
| `change.impact` | Impact packets before edits |

## Primary files

- [`START_HERE.md`](../START_HERE.md)
- [`AGENTS.md`](../AGENTS.md)
- [`delta/00_holistic.md`](delta/00_holistic.md)
- [`change-impact/policy.md`](change-impact/policy.md)
```

Full form is required when the project has more than ~8 concepts or multiple tool integrations.

---

## Companion: AGENTS.md section

Insert after `## Repository root` (or after title if no root section):

```markdown
## Planning Rosetta Stone (required anchor)

Before planning or coding, load the hook map into normal context:

- **Search phrase:** `Planning Rosetta Stone`
- **Hook ID:** `planning.rosetta`
- **File:** `docs/planning-rosetta-stone.md`

Follow linked hooks (`context.delta`, `spec.flow`, `change.impact`, etc.) before diving into spec or Delta files.
```

---

## Companion: START_HERE.md pointers

```markdown
When planning or coding, search for **Planning Rosetta Stone** or hook `planning.rosetta`:

1. [`docs/planning-rosetta-stone.md`](docs/planning-rosetta-stone.md) — top-level legend and hook index
2. [`AGENTS.md`](AGENTS.md) — durable repo operating guidance
```

---

## Companion: handoff file navigation blocks

When Spec Kit or Delta handoff files exist, prepend an **Agent navigation (Rosetta Stone)** block so implementers load hooks before requirements.

**Spec (`docs/specs/<feature>/spec.md`):**

```markdown
<!-- ROSETTA-NAV -->

## Agent navigation (Rosetta Stone)

Before implementing, load the hook map — do not jump straight into requirements.

1. [`docs/planning-rosetta-stone.md`](../../planning-rosetta-stone.md) — hook `planning.rosetta`
2. Follow **UNLOCKS**: `context.delta` → [`00_holistic.md`](../../delta/00_holistic.md), [`10_macro.md`](../../delta/10_macro.md)
3. This feature — hook `spec.flow`:
   - Delta micro: [`<feature>.md`](../../delta/20_micro/<feature>.md)
   - Plan: [`plan.md`](./plan.md)
   - Tasks: [`tasks.md`](./tasks.md)
```

**Plan / tasks / micro brief** — same pattern; point back to `planning.rosetta` and list sibling handoff paths. Hive tooling can auto-patch missing blocks via `repair_handoff_rosetta_navigation`.

---

## Validation checklist

Before marking generation complete:

- [ ] Output path is `docs/planning-rosetta-stone.md`
- [ ] HTML metadata block includes `meta:hook_id: planning.rosetta` and `meta:search: Planning Rosetta Stone`
- [ ] Root hook `planning.rosetta` exists with PRIMARY FILES and UNLOCKS
- [ ] Every PRIMARY FILE link is repo-relative and resolvable (or tagged planned)
- [ ] No duplicate HOOK_ID definitions
- [ ] `START_HERE.md` links to the Rosetta Stone
- [ ] `AGENTS.md` contains the required anchor section with `planning.rosetta`
- [ ] Active spec/plan/tasks/micro files include Agent navigation blocks (when Spec Kit is used)
- [ ] Coverage check section lists all major concept strands
- [ ] Repo root detectable: `START_HERE.md` + `docs/planning-rosetta-stone.md` both present

**Hive CLI validation (when wired):**

```powershell
py -3.11 -m hive_planner ci-check
```

Handoff drift checks include missing Rosetta navigation on active feature artifacts.

---

## Anti-patterns

| Do not | Do instead |
|--------|------------|
| Paste the entire planning thread into the Rosetta | One hook per concept; link to distilled docs |
| Invent hooks without PRIMARY FILES | Every hook points at least one file |
| Use absolute machine paths in links | Repo-relative markdown only |
| Replace spec/plan/tasks with hooks | Hooks navigate; specs remain execution truth |
| Duplicate full Rosetta into `AGENTS.md` | Anchor section + link to full legend |
| Change HOOK_ID meaning in place | Add a new hook; deprecate old ID in coverage check |
| Skip `planning.rosetta` root hook | Always present; always searchable |

---

## Related hooks

| HOOK_ID | Document |
|---------|----------|
| `planning.rosetta` | [`planning-rosetta-stone.md`](./planning-rosetta-stone.md) — live reference instance |
| `meta.anchor_policy` | This file + [`thread-outline-with-metatags.md`](./thread-outline-with-metatags.md) |
| `workflow.project_bootstrap` | [`project-bootstrap-guide.md`](./project-bootstrap-guide.md) |
| `spec.flow` | [`../starter-kit/spec-kit-agent-integration.md`](../starter-kit/spec-kit-agent-integration.md) |

---

## Machine-readable summary

For agents that prefer a compact generation contract:

```yaml
output_file: docs/planning-rosetta-stone.md
search_phrase: Planning Rosetta Stone
root_hook: planning.rosetta
required_companions:
  - START_HERE.md
  - AGENTS.md
hook_block_fields:
  - HOOK_ID
  - Meaning
  - PRIMARY FILES
  - UNLOCKS
  - THREAD COVERAGE
minimum_hooks:
  - planning.rosetta
  - context.delta
  - cursor.rules
  - change.impact
  - change.bugfix_mode
navigation_marker: "<!-- ROSETTA-NAV -->"
navigation_heading: "## Agent navigation (Rosetta Stone)"
```
