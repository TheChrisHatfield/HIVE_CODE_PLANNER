---
name: agents-memory-updater
description: Mine high-signal transcript deltas, update `AGENTS.md` (Hive unified handoff), and keep the incremental transcript index in sync.
model: inherit
---

# AGENTS.md memory updater (Hive)

Own the full memory update flow for continual learning in **Hive unified handoff** projects.

**Contract:** [docs/cl-spec-integration.md](../../../docs/cl-spec-integration.md)

## Trigger

Use from `continual-learning` when transcript deltas may produce durable memory updates.

## Pre-flight (required)

Before editing `AGENTS.md`:

1. Complete the **Integration wiring audit** on validated changes (`.cursor/rules/integration-wiring-audit.mdc`).
2. Run `py -3.11 -m hive_planner spec-drift-check` when promoting behavioral or cross-layer facts.
3. Read `.cursor/plugins/hive-continual-learning/WORKFLOW.md` for full gates.

If wiring audit is not complete, respond exactly: `Blocked: complete Integration wiring audit before AGENTS.md edit.`

## Workflow

1. Read existing `AGENTS.md` first. If it does not exist, create it with only:
   - `## Learned User Preferences` (optional; user-specific tone/preferences)
   - `## Durable Workspace Facts` (Hive operational memory — **not** `## Learned Workspace Facts`)
2. Load the incremental index if present.
3. Inspect only transcript files under `~/.cursor/projects/<workspace-slug>/agent-transcripts/` that are new or have newer mtimes than the index.
4. Classify each candidate bullet (mirror `hive_planner spec_drift.classify_bullet` heuristics):
   - **Operational** → may go to `## Durable Workspace Facts` (commands, paths, repo conventions, tooling)
   - **Behavioral** → **do not** write to `AGENTS.md`; route to `docs/specs/<active-feature>/spec.md`
5. For operational bullets only, update `AGENTS.md`:
   - merge into `## Durable Workspace Facts` (map legacy `## Learned Workspace Facts` → this section if present)
   - update matching bullets in place
   - add only net-new bullets
   - deduplicate semantically similar bullets
   - keep the section to at most 12 bullets
6. For behavioral bullets, append to `docs/proposals/cl-candidates.md` using the template format (see CL-4 export below).
7. Refresh the incremental index for processed transcripts and remove entries for files that no longer exist.
8. If the merge produces no `AGENTS.md` changes, leave `AGENTS.md` unchanged but still refresh the index.
9. If no meaningful updates exist, respond exactly: `No high-signal memory updates.`

## Behavioral routing (CL-2)

Reject or route bullets that match behavioral heuristics:

- Tags: `# behavioral`
- Keywords: must, shall, requirement, acceptance, API behavior, validates, returns, when … then, non-negotiable

Tell the user to update `docs/specs/<feature>/spec.md` instead. Use active feature from `AGENTS.md` **Active feature** or `.hive/project.json`.

## Section mapping (CL-6)

| Upstream section | Hive target |
|------------------|-------------|
| `## Learned Workspace Facts` | `## Durable Workspace Facts` |
| Legacy bullets under Learned Workspace Facts | Merge into Durable Workspace Facts, then remove empty Learned section |

Operational workspace facts **never** use `## Learned Workspace Facts` in Hive projects.

## Candidate export (CL-4)

When behavioral bullets are found, append to `docs/proposals/cl-candidates.md`:

```markdown
# behavioral
- <bullet text>

# operational
- <any operational candidates held for agents-propose review>
```

Run `py -3.11 -m hive_planner agents-propose --dry-run` for CI parity before merge.

## Guardrails

- Use plain bullet points only under allowed sections.
- Allowed AGENTS.md sections for memory writes:
  - `## Learned User Preferences` (optional)
  - `## Durable Workspace Facts` (operational only)
- Do not write evidence/confidence tags.
- Do not write process instructions, rationale, or metadata blocks into AGENTS.md.
- Exclude secrets, private data, one-off instructions, and transient details.

## Output

- Updated `AGENTS.md` and `.cursor/hooks/state/continual-learning-index.json` when needed
- Optional `docs/proposals/cl-candidates.md` when behavioral bullets routed
- Otherwise exactly `No high-signal memory updates.`
