<!--
meta:hook_id: spec.flow
meta:source: HIVE_PLANNING_DEV.md (Blueprint + Starter Kit)
meta:status: extracted
-->

# Spec Kit Agent Integration

How Spec Kit connects Perplexity planning output to Cursor implementation.

## Hive unified deploy (Stage 9)

For Hive projects, prefer the **vendored Spec Kit overlay** deployed at `.hive/spec-kit/` — not a separate marketplace or global Spec Kit install.

| Artifact | Path |
|----------|------|
| Spec + task templates | `.hive/spec-kit/templates/` |
| Post-`/tasks` workflow gates | `.hive/spec-kit/WORKFLOW.md` |
| Feature id alignment | `.hive/spec-kit/README.md` |
| Pin snapshot | `.hive/upstream-pins.json` |

Bootstrap or refresh:

```powershell
py -3.11 -m hive_planner init --target <path> --agent-handoff unified
# or desktop app: Home → Deploy agent handoff
```

Use templates from `.hive/spec-kit/templates/` when drafting `docs/specs/<feature>/`. Run `spec-drift-check` and complete the wiring audit before Continual Learning promotion. Operator guide: [../docs/unified-handoff-upstream-forks.md](../docs/unified-handoff-upstream-forks.md).

## Division of labor

| Phase | Tool | Output |
|-------|------|--------|
| Research | Perplexity | Blueprint draft, tradeoffs, architecture options |
| Specification | Spec Kit | `spec.md`, `plan.md`, `tasks.md` |
| Execution | Cursor | Code, tests, narrow task completion |
| Memory | Continual Learning | Durable updates to `AGENTS.md` |

## Spec Kit workflow

```text
/specify  -> produce or refine spec.md
/plan     -> derive technical plan.md
/tasks    -> generate executable tasks.md
```

Operational sequence:

1. Research in Perplexity.
2. Draft `00_holistic.md`, `10_macro.md`, and initial feature intent.
3. Run Spec Kit specification for the feature.
4. Run plan generation with architectural preferences.
5. Run tasks generation to create narrow executable units.
6. In Cursor, implement one micro task at a time with rules attached.
6b. **Integration wiring audit** (required before checking off each task) — see `.cursor/rules/integration-wiring-audit.mdc`.
7. Use continual learning only after validated changes and the wiring audit passes.

## Continual Learning candidate format

Export or write candidate bullets to a markdown file for `agents-propose`:

```markdown
# operational
- Prefer `py -3.11 -m hive_planner ci-check` before handoff.

# behavioral
- Endpoint must validate cartridge manifest schema version.
```

- Tag lines with `# operational` or `# behavioral`, or rely on `spec-drift-check` heuristics.
- Behavioral candidates are rejected by `agents-propose`; update `spec.md` first.
- See [../docs/cl-spec-integration.md](../docs/cl-spec-integration.md) (hook `integration.cl_spec`).

## Feature prompt shape

Each feature prompt should include:

- Holistic objective
- Macro subsystem affected
- Micro task scope
- Constraints and invariants
- Acceptance criteria
- Validation requirements (include integration wiring audit per `.cursor/rules/integration-wiring-audit.mdc`)
- Known risks or open questions

## Spec flow rules

- **Specs** define the what and why (behavioral contract).
- **Plans** define technical approach and constraints.
- **Tasks** define narrow executable work units.

If behavior changes → update spec first.  
If only implementation path changes → update plan.  
If only sequencing changes → update tasks.

## Feature artifact paths

```text
docs/specs/<feature>/spec.md
docs/specs/<feature>/plan.md
docs/specs/<feature>/tasks.md
```

## Clarification before planning

Run clarification when requirements are ambiguous **before** plan and task generation. Update spec and discard off-track changes when implementation goes off the rails.

## Related

- [../docs/agentic-coding-blueprint.md](../docs/agentic-coding-blueprint.md)
- [README.md](./README.md)
- [../START_HERE.md](../START_HERE.md)
