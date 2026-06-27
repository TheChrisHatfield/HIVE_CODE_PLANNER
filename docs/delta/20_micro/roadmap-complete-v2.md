# Feature Micro Brief: roadmap-complete-v2

**Hook:** `workflow.tools`, `workflow.blueprint_first`, `change.validation`

## Feature Name

Roadmap Complete v2 — validate Stage 7 artifacts and mark extended roadmap done.

## Scope

| In scope | Out of scope |
|----------|--------------|
| Extended `roadmap-status` | New compiler stages |
| `ci-check` roadmap step | Auto spec generation |
| `STAGE_ROADMAP.md` Stage 7 table | Cloud deployment |

## Acceptance Criteria

- [x] All 18 roadmap features have spec/micro/tasks
- [x] `roadmap-status` exits 0 when complete
- [x] `ci-check` roadmap-artifacts reflects extended list
- [x] Stage 7 documented in STAGE_ROADMAP

## Validation

```powershell
py -3.11 -m hive_planner roadmap-status
py -3.11 -m hive_planner ci-check
```
