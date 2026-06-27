<!--
meta:hook_id: repo.starter_files
meta:source: HIVE_PLANNING_DEV.md
meta:status: extracted
-->

# Agentic Coding Starter Kit

This starter kit packages the blueprint into actual repo-ready files for a spec-first workflow that uses Perplexity for research, GitHub Spec Kit for specification, and Cursor for implementation with rule-based execution and durable project memory. Spec Kit is documented as a toolkit for spec-driven development, and Cursor provides background agents plus a Continual Learning plugin that maintains durable workspace facts in `AGENTS.md`.[^3_1][^3_2][^3_3]

## Included files

- `AGENTS.md`
- `docs/delta/00_holistic.md`
- `docs/delta/10_macro.md`
- `docs/delta/20_micro/README.md`
- `docs/delta/20_micro/feature-template.md`
- `docs/specs/example-feature/spec.md`
- `docs/specs/example-feature/plan.md`
- `docs/specs/example-feature/tasks.md`
- `.cursor/rules/architecture.mdc`
- `.cursor/rules/task-execution.mdc`
- `.cursor/rules/validation.mdc`
- `spec-kit-agent-integration.md`


## How to use

1. Fill in `AGENTS.md` with durable project truth.
2. Define system mission and invariants in `00_holistic.md`.
3. Define architecture and interfaces in `10_macro.md`.
4. Create feature specs in `docs/specs/<feature>/` using the same pattern as the example feature.
5. Use Cursor to implement one task at a time while keeping rule files active.[^3_1][^3_4]

See [spec-kit-agent-integration.md](./spec-kit-agent-integration.md) for the Spec Kit workflow.

## Feature prompt template

```md
Holistic objective: <mission link>
Macro subsystem: <module or interface>
Micro scope: <files, functions, tests>
Constraints: <invariants>
Acceptance criteria: <testable outcomes>
Validation: <tests, checks, metrics>
Risks: <known uncertainties>
```

## Why this works

This approach reduces the need for the coding agent to infer system intent from long transcripts. It gives the agent a narrow execution frame while still preserving traceability to mission and architecture, which aligns with a context-focused and error-reducing implementation workflow.[cite:12][cite:17]

## Cursor connection points

Use Cursor for:

- Reading the current task and related spec.
- Applying rules from `.cursor/rules/`.
- Using `AGENTS.md` as durable repo memory.
- Running background agents for bounded implementation tasks where appropriate.[cite:13][cite:16][cite:17]
<span style="display:none">[^3_5]</span>

<div align="center">⁂</div>

[^3_1]: https://github.github.com/spec-kit/
[^3_2]: https://docs.cursor.com/en/background-agent
[^3_3]: https://cursor.com/marketplace/cursor/continual-learning
[^3_4]: https://www.youtube.com/watch?v=pPSIXbKswtQ
[^3_5]: 1000002304.jpg
