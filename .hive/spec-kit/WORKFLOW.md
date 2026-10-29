# Hive Spec Kit workflow gates (post-`/tasks`)

**Hook:** `spec.flow`, `integration.wiring_audit`, `integration.cl_spec`  
**Applies to:** unified handoff projects (`agent_handoff_mode: unified`)

## After `/tasks` — before checking off work

1. **Accept the spec** — `py -3.11 -m hive_planner spec-create --feature <id>` exits 1 until `spec.md` has User Scenarios, Assumptions, and measurable Success Criteria, and `tasks.md` includes the Integration wiring audit checklist. Exit 0 sets `AGENTS.md` **Active feature**. Do not treat the spec as done on a non-zero exit.
2. **Integration wiring audit (each task)** — before marking any task complete:
   - [ ] Traced caller → handler → core (no layer break)
   - [ ] No false success when a sub-step failed or was skipped
   - [ ] Integration-level validation evidence attached
   - [ ] See `.cursor/rules/integration-wiring-audit.mdc`
3. **Implement one task at a time** — attach validation evidence in the task list or PR notes.

## Before Continual Learning / `AGENTS.md` promotion

Run Hive headless gates (CI parity):

```powershell
py -3.11 -m hive_planner spec-drift-check
py -3.11 -m hive_planner agents-propose --dry-run
py -3.11 -m hive_planner ci-check
```

**Contract:**

| Layer | Owner |
|-------|-------|
| Behavioral facts | Spec Kit `spec.md` |
| Operational facts | `AGENTS.md` `## Durable Workspace Facts` |
| Wiring audit | Required before memory promotion |
| Drift | `spec-drift-check` must pass before CL checkoff |

## Spec Kit command handoff

After `/tasks` completes, read this file before `/implement` or manual task checkoff. Do not promote Continual Learning candidates until wiring audit and spec-drift gates pass.

See [docs/cl-spec-integration.md](../../docs/cl-spec-integration.md).
