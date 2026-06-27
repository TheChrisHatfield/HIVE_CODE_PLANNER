# Feature Micro Brief: cl-spec-integration-v1

**Hook:** `integration.cl_spec`, `spec.flow`, `memory.agents_md`, `automation.ci_memory`

## Feature Name

Continual Learning + Spec Kit integration — keep behavioral truth in specs.

## Scope

| In scope | Out of scope |
|----------|--------------|
| `spec-drift-check` CLI | Auto spec edits |
| CI spec-drift step | External CL APIs |
| Behavioral candidate rejection | New bullet formats |

## Acceptance Criteria

- [x] `spec-drift-check` reports operational vs behavioral bullets
- [x] Behavioral bullets not in spec flagged as drift
- [x] `agents-propose` rejects behavioral candidates
- [x] `ci-check` includes spec-drift step

## Validation

```powershell
py -3.11 -m hive_planner spec-drift-check
py -3.11 -m hive_planner ci-check --skip-pytest
```
