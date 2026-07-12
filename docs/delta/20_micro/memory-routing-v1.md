# Feature Micro Brief: memory-routing-v1

**Hook:** `automation.ci_memory`, `integration.cl_spec`, `memory.agents_md`

## Feature Name

Memory routing v1 — autonomous split / route / Thompson for AGENTS.md promotion.

## Scope

| In scope | Out of scope |
|----------|--------------|
| Auto-split operational bullets >240 chars | Nightly schedule |
| Auto-route behavioral → `cl-candidates.md` | Auto-merge PRs to main |
| Thompson sampling for classifier-ambiguous | Full ML classifier |
| `.hive/memory-routing.json` arm stats | Launcher preview modal (removed for promote) |
| CL-7 subagent prefers `agents-propose --apply` | Changing the 240-char policy itself |

## Acceptance Criteria

- [x] Oversized operational candidates are split and applied without human preview
- [x] Behavioral candidates land in `docs/proposals/cl-candidates.md`
- [x] Explicit `# ambiguous` tags still hard-reject
- [x] Classifier-ambiguous uses Thompson arms
- [x] CL addon documents CL-7 autonomous CLI path

## Validation

```powershell
py -3.11 -m pytest tests/test_memory_routing.py tests/test_agents_memory.py -q
py -3.11 -m hive_planner agents-propose --candidates docs/proposals/candidates.md --apply
```
