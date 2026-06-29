# Hive Continual Learning workflow gates

**Hook:** `integration.cl_spec`, `integration.wiring_audit`  
**Plugin path:** `.cursor/plugins/hive-continual-learning/`

## Before AGENTS.md promotion

1. **Integration wiring audit** — complete `.cursor/rules/integration-wiring-audit.mdc` on validated changes.
2. **Classify bullets** — operational → `## Durable Workspace Facts`; behavioral → `docs/specs/<feature>/spec.md`.
3. **Spec drift** — run `py -3.11 -m hive_planner spec-drift-check` before session end or merge.

## Headless CI parity

```powershell
py -3.11 -m hive_planner spec-drift-check
py -3.11 -m hive_planner agents-propose --dry-run
py -3.11 -m hive_planner ci-check
```

## Candidate export

Behavioral bullets routed by the subagent go to `docs/proposals/cl-candidates.md` for review and `agents-propose`.

## Environment overrides

| Variable | Purpose |
|----------|---------|
| `CONTINUAL_LEARNING_*` | Upstream cadence (see README) |
| `HIVE_WIRING_AUDIT=1` | Require wiring audit acknowledgment before CL runs |
| `HIVE_SPEC_DRIFT_CHECK=1` | Remind to run spec-drift-check before promotion |

## Related

- [docs/cl-spec-integration.md](../../docs/cl-spec-integration.md)
- [.hive/spec-kit/WORKFLOW.md](../../.hive/spec-kit/WORKFLOW.md)
