# Hive post-`/tasks` command supplement

Read **before** checking off tasks or starting `/implement` in a Hive unified project.

1. Confirm feature id alignment — see `.hive/spec-kit/README.md` (SK-3).
2. Complete **Integration wiring audit** for each task — `.cursor/rules/integration-wiring-audit.mdc`.
3. Run headless gates before Continual Learning — `.hive/spec-kit/WORKFLOW.md`:
   - `py -3.11 -m hive_planner spec-drift-check`
   - `py -3.11 -m hive_planner agents-propose --dry-run`

Use Hive-patched templates from `.hive/spec-kit/templates/` (not upstream defaults).
