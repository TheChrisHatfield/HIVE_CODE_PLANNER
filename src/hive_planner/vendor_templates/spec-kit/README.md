# Hive Spec Kit overlay (unified handoff)

Hive-patched Spec Kit templates for symbiotic deploy with Hive Planner, Continual Learning, and CI gates.

**Upstream:** vendored `github/spec-kit` (see `.hive/upstream-pins.json`)  
**Overlay path:** `.hive/spec-kit/templates/`  
**Contract:** [docs/cl-spec-integration.md](../../docs/cl-spec-integration.md)

## Feature id alignment (SK-3)

Keep these three identifiers in sync:

| Source | Field / path | Example |
|--------|----------------|---------|
| `.hive/project.json` | `active_feature` (when set) | `my-feature` |
| Delta micro brief | `docs/delta/20_micro/<feature-id>.md` | `docs/delta/20_micro/my-feature.md` |
| Spec Kit bundle | `docs/specs/<feature-id>/` | `docs/specs/my-feature/spec.md` |

**Rules:**

1. Use kebab-case feature ids (same validation as `hive_planner` cartridge promote).
2. After `/specify`, confirm the spec folder name matches the Delta micro brief filename (without `.md`).
3. Set `AGENTS.md` **Active feature** to the same id before implementation.
4. Run `py -3.11 -m hive_planner spec-drift-check` before Continual Learning promotion.

## Template overrides

| File | Hive patch |
|------|------------|
| `templates/spec-template.md` | Rosetta navigation placeholder (`hive_planner.rosetta_nav`) |
| `templates/tasks-template.md` | Integration wiring audit checklist per task |
| `WORKFLOW.md` | Post-`/tasks` gates (wiring audit, `spec-drift-check`) |

Point Spec Kit or your agent workflow at `.hive/spec-kit/templates/` instead of upstream defaults when working in a Hive unified project.

## Related

- [WORKFLOW.md](./WORKFLOW.md) — post-`/tasks` validation sequence
- [docs/unified-handoff-upstream-forks.md](../../docs/unified-handoff-upstream-forks.md) — pin and patch policy
- `.cursor/rules/integration-wiring-audit.mdc` — wiring audit rule
