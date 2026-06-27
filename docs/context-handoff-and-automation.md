<!--
meta:hook_id: workflow.git_handoff
meta:source: HIVE_PLANNING_DEV.md
meta:status: extracted
-->

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