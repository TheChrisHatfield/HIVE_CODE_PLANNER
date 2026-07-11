<!--
meta:title: Rosetta Stone Planning Session Contract
meta:hook_id: meta.anchor_policy
meta:search: Planning Rosetta Stone upload contract inline markers
meta:purpose: Standalone upload file — instruct any AI how to structure planning output with Rosetta hooks and inline markers
meta:audience: Perplexity, Google Gemini, ChatGPT, Claude, NotebookLM, any planning-session AI
meta:usage: Upload this file at the start of a planning session; follow all output rules in every document you produce
meta:format: semantic-markdown-with-hook-tags
meta:status: active
meta:scope: portable — no repo required
meta:priority: critical
meta:anchor_version: v1
-->

# Rosetta Stone Planning Session Contract

**Upload this file to your planning session.** Any AI that reads this document must follow these rules for **every planning artifact** it produces — blueprints, architecture notes, specs, feature briefs, thread summaries, and the Rosetta Stone itself.

---

## Instructions to the reading AI

You are in a **planning session**. Your job is not only to think and write prose — you must **tag every document** with stable hooks and inline markers so downstream coding agents (Cursor, Hive, Spec Kit) can navigate context without re-reading the full chat.

**Always do these three things:**

1. **Embed inline markers** in every planning document you write (see §2).
2. **Produce a Planning Rosetta Stone** as a separate document (see §3).
3. **Cross-link hooks** — every major section references a `HOOK_ID`; the Rosetta Stone lists all hooks and where they live.

**Search phrase (include in every Rosetta Stone):** `Planning Rosetta Stone`  
**Root hook (always present):** `planning.rosetta`

---

## 1. Marker system overview

Four marker layers work together. Use all of them in full planning threads; use layers 1–3 minimum for small projects.

| Layer | Syntax | Where | Purpose |
|-------|--------|-------|---------|
| **File header** | HTML comment `meta:*` tags | Top of every file | Machine-readable file identity |
| **Section hook** | `## [HOOK:domain.name]` | Major sections | Stable concept anchor |
| **Inline hook ref** | `` `hook_id` `` or `(hook: domain.name)` | Body text, bullets | Point to concept without duplicating |
| **Nav block** | `<!-- ROSETTA-NAV -->` + heading | Spec / plan / tasks / feature briefs | Tell coders what to load first |

**Separator between hook blocks:** use `***` on its own line.

---

## 2. Inline markers — use in EVERY planning document

### 2a. File header block (required on every file you create)

Paste this block as the **first lines** of every markdown file. Fill in values.

```markdown
<!--
meta:title: {Document Title}
meta:hook_id: {primary.hook_for_this_file}
meta:search: {human search phrase}
meta:purpose: {one line}
meta:audience: {who reads this}
meta:usage: {when to load this file}
meta:format: semantic-markdown-with-hook-tags
meta:status: draft | active | extracted
meta:scope: {feature name | repo-wide}
meta:priority: critical | high | normal
meta:anchor_version: v1
-->
```

**Example — feature spec header:**

```markdown
<!--
meta:title: User Auth Feature Spec
meta:hook_id: spec.flow
meta:search: user auth specification
meta:purpose: Behavioral requirements for authentication
meta:audience: Coding agents, reviewers
meta:usage: Load after planning.rosetta and context.delta before implementation
meta:format: semantic-markdown-with-hook-tags
meta:status: draft
meta:scope: user-auth-v1
meta:priority: high
meta:anchor_version: v1
-->
```

### 2b. Section hook headings (required on major sections)

Every major concept section must use this heading form:

```markdown
## [HOOK:domain.name]

**HOOK_ID:** `domain.name`

**Meaning:** {one sentence}

**Anchor summary:**
- {bullet}
- {bullet}

**Inline refs:** unlocks `other.hook`, relates to `another.hook`
```

**Example — inside an architecture blueprint:**

```markdown
## [HOOK:context.delta]

**HOOK_ID:** `context.delta`

**Meaning:** Three-level context model for this project.

**Anchor summary:**
- **Holistic** — mission, constraints, non-goals
- **Macro** — modules, interfaces, workflows
- **Micro** — feature scope, files, tests

**Inline refs:** unlocks `spec.flow`, `change.impact`
```

### 2c. Inline references within body text

When mentioning a concept mid-paragraph, tag it inline so agents can jump to the Rosetta entry:

```markdown
Follow `workflow.blueprint_first` before coding. Map each feature to `context.delta` layers.
This change requires `change.impact` review (see hook `change.bugfix_mode` for defects).
```

Preferred forms (pick one per doc, stay consistent):

- Backticks: `` `planning.rosetta` ``
- Parenthetical: `(hook: spec.flow)`
- Bold label: **Hook:** `context.tri_level`

### 2d. Navigation block (required on spec, plan, tasks, feature briefs)

Any document that a **coding agent will execute from** must start with this block immediately after the title / header metadata:

```markdown
<!-- ROSETTA-NAV -->

## Agent navigation (Rosetta Stone)

Before implementing, load the hook map — do not jump straight into requirements.

1. **Planning Rosetta Stone** — hook `planning.rosetta`
2. **Unlocks:** `context.delta` → holistic + macro + this feature's micro brief
3. **This artifact** — hook `{this_file_hook}`:
   - Related spec / plan / tasks / delta paths (list intended file names)
```

Replace `{this_file_hook}` with e.g. `spec.flow`, `context.delta`, `change.impact`.

### 2e. Context-member tags inside long sections

For long planning sections (thread exports, meeting notes, research dumps), mark each logical **context member** with a lightweight inline anchor:

```markdown
### [CTX:authentication.requirements]

**HOOK_ID:** `spec.flow`  
**Member type:** requirement  
**Promote to:** `docs/specs/user-auth/spec.md`

- Users must sign in with email and password
- Session timeout: 24 hours
```

```markdown
### [CTX:architecture.api_boundary]

**HOOK_ID:** `context.delta`  
**Member type:** macro  
**Promote to:** `docs/delta/10_macro.md`

- Public REST API behind `/api/v1`
- Internal service calls over gRPC
```

**Context member rules:**

| Field | Required | Values |
|-------|----------|--------|
| `[CTX:...]` label | Yes | `topic.subtopic` slug |
| `HOOK_ID` | Yes | Existing or new hook |
| `Member type` | Yes | `holistic`, `macro`, `micro`, `requirement`, `constraint`, `workflow`, `integration`, `validation` |
| `Promote to` | Yes | Target repo path (or `(new file)` if not yet created) |

---

## 3. Planning Rosetta Stone — required session output

At the end of (or during) the planning session, produce a document titled **Planning Rosetta Stone**. This is the master index.

### 3a. Rosetta Stone file header

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
```

### 3b. Rosetta Stone body template

```markdown
# Planning Rosetta Stone — {PROJECT_NAME}

Search phrase: **Planning Rosetta Stone** · Root hook: `planning.rosetta`

## Purpose

Legend mapping concepts → files. Coding agents load this first.

## How to use

1. Find the concept or hook below.
2. Open PRIMARY FILES.
3. Follow UNLOCKS only when deeper detail is needed.

## Legend conventions

- **HOOK_ID** — stable anchor (`domain.name`)
- **PRIMARY FILES** — first files to open
- **UNLOCKS** — related hooks next
- **THREAD COVERAGE** — what this hook summarizes

***

## [HOOK:planning.rosetta]

**HOOK_ID:** `planning.rosetta`

**Meaning:** Top-level legend for this project.

**PRIMARY FILES:**
- START_HERE.md (planned)
- AGENTS.md (planned)
- {list other anchors}

**UNLOCKS:**
- `context.delta`
- {other top-level hooks}

**THREAD COVERAGE:** Full planning thread navigation.

***

## [HOOK:{next.hook}]

**HOOK_ID:** `{next.hook}`

**Meaning:** {one sentence}

**PRIMARY FILES:**
- {path or planned path}

**UNLOCKS:**
- `{related.hook}`

**THREAD COVERAGE:** {coverage note}

***

## Coverage check

- [ ] {concept strand 1} → `{hook.id}`
- [ ] {concept strand 2} → `{hook.id}`
```

Repeat the `[HOOK:...]` block for **every concept** introduced in the session.

---

## 4. Minimum hook catalog

Assign hooks from this catalog before inventing new IDs:

| HOOK_ID | Use when discussing… |
|---------|----------------------|
| `planning.rosetta` | The legend itself / navigation |
| `context.delta` | Holistic / macro / micro layers |
| `context.tri_level` | Primary / secondary / tertiary context |
| `workflow.tools` | Tool roles (research vs spec vs code) |
| `workflow.blueprint_first` | Plan before code |
| `workflow.git_handoff` | Git as context transport |
| `spec.flow` | Spec → plan → tasks workflow |
| `cursor.rules` | Agent behavior rules |
| `memory.agents_md` | Durable AGENTS.md memory |
| `change.impact` | Pre-edit impact analysis |
| `change.bugfix_mode` | Bug-fix causal chains |
| `change.validation` | Test / validation gates |
| `integration.cl_spec` | Spec Kit + continual learning split |
| `meta.anchor_policy` | How hooks and markers are defined |

**New hooks:** use `domain.name` lowercase dots. Never reuse an ID for a different meaning.

---

## 5. Document types — what markers each needs

| Document type | Header meta | ROSETTA-NAV | Section hooks | CTX members |
|---------------|-------------|-------------|---------------|-------------|
| Rosetta Stone | Required | No | Every entry | No |
| Blueprint / thread outline | Required | Recommended | Every major section | Yes for long threads |
| Holistic delta | Required | Recommended | Yes | Optional |
| Macro delta | Required | Recommended | Yes | Optional |
| Micro / feature brief | Required | **Required** | Yes | Optional |
| Spec | Required | **Required** | Yes | Per requirement |
| Plan | Required | **Required** | Yes | Optional |
| Tasks | Required | **Required** | Yes | Optional |
| Research notes | Required | No | Yes | **Required** |

---

## 6. Session workflow for the reading AI

When the user uploads this contract and starts planning:

1. **Acknowledge** — confirm you will tag all output with hooks and inline markers.
2. **During planning** — every artifact uses §2 markers; tag concepts inline as they appear.
3. **Track hooks** — maintain a running list of `HOOK_ID` values assigned.
4. **Deliver Rosetta Stone** — produce §3 document listing every hook + PRIMARY FILES + UNLOCKS.
5. **Deliver coverage check** — confirm every major thread topic maps to a hook.
6. **List promote targets** — for each `[CTX:...]` member, show which repo file it should land in.

---

## 7. Complete mini-example (copy pattern)

Below is one full small planning output showing all marker layers:

```markdown
<!--
meta:title: Holistic — TaskApp
meta:hook_id: context.delta
meta:search: TaskApp mission goals
meta:purpose: Holistic layer for TaskApp
meta:audience: Coding agents
meta:usage: Load after planning.rosetta
meta:format: semantic-markdown-with-hook-tags
meta:status: draft
meta:scope: repo-wide
meta:priority: high
meta:anchor_version: v1
-->
# Holistic — TaskApp

<!-- ROSETTA-NAV -->

## Agent navigation (Rosetta Stone)

Load hook `planning.rosetta` first. This file is holistic layer (`context.delta`).

## [HOOK:context.delta]

**HOOK_ID:** `context.delta`

**Meaning:** Top-level mission and constraints for TaskApp.

**Anchor summary:**
- Mission: simple team task tracking
- Non-goal: enterprise SSO in v1

### [CTX:holistic.mission]

**HOOK_ID:** `context.delta`  
**Member type:** holistic  
**Promote to:** `docs/delta/00_holistic.md`

- Help small teams track tasks without configuration overhead

### [CTX:holistic.constraints]

**HOOK_ID:** `context.delta`  
**Member type:** constraint  
**Promote to:** `docs/delta/00_holistic.md`

- Must work offline-first on mobile
- Follow `change.validation` for all user-data edits
```

---

## 8. Rules — do not break these

| Rule | Detail |
|------|--------|
| Always produce a Rosetta Stone | Even short sessions get a slim hook table |
| Always include `Planning Rosetta Stone` search phrase | In the Rosetta document |
| Always include root hook `planning.rosetta` | With PRIMARY FILES and UNLOCKS |
| Tag before prose drifts | Hooks first, then expand |
| One HOOK_ID = one meaning | Never recycle IDs |
| Mark promote targets | Every `[CTX:...]` says where it lands in repo |
| Spec/plan/tasks get ROSETTA-NAV | Non-negotiable for coding handoff |
| Prefer catalog hooks (§4) | Before inventing new IDs |

---

## 9. Slim Rosetta (short sessions)

For sessions under ~30 minutes, a table Rosetta is acceptable:

```markdown
# Planning Rosetta Stone — {PROJECT}

Search: **Planning Rosetta Stone** · Hook: `planning.rosetta`

| HOOK_ID | Meaning | Primary file (planned) |
|---------|---------|------------------------|
| `planning.rosetta` | This legend | docs/planning-rosetta-stone.md |
| `context.delta` | Holistic/macro/micro | docs/delta/ |
| `spec.flow` | Spec/plan/tasks | docs/specs/{feature}/ |
| `change.impact` | Impact before edits | docs/change-impact/ |
```

Still use file headers and inline `` `hook` `` refs in all other documents.

---

## 10. User prompt snippet (paste with this upload)

```text
I've uploaded the Rosetta Stone Planning Session Contract.

Follow it for ALL documents you produce in this session:
- HTML meta header on every file
- [HOOK:...] section headings on major concepts
- Inline `hook_id` references in body text
- [CTX:...] context members in long sections with Promote to paths
- <!-- ROSETTA-NAV --> on spec/plan/tasks/feature briefs
- Deliver a Planning Rosetta Stone index at the end

Project name: {YOUR PROJECT}
```

Replace `{YOUR PROJECT}` before sending.

---

**End of contract.** Upload this file unchanged to Perplexity, Gemini, ChatGPT, Claude, or any planning AI.
