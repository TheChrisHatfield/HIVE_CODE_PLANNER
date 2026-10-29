# Hive post-`/tasks` command supplement

Read **before** checking off tasks or starting `/implement` in a Hive unified project.

1. Run `py -3.11 -m hive_planner spec-create --feature <id>` before treating the spec as done. Exit 1 means the spec is not accepted: `spec.md` is missing User Scenarios, Assumptions, or measurable Success Criteria, or `tasks.md` has no Integration wiring audit checklist. Exit 0 sets `AGENTS.md` **Active feature** to that id.
2. Complete **Integration wiring audit** for each task — `.cursor/rules/integration-wiring-audit.mdc`.
3. Run headless gates before Continual Learning — `.hive/spec-kit/WORKFLOW.md`:
   - `py -3.11 -m hive_planner spec-drift-check`
   - `py -3.11 -m hive_planner agents-propose --dry-run`

Use Hive-patched templates from `.hive/spec-kit/templates/` (not upstream defaults).
