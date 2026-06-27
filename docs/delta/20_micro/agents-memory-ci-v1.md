# Feature Micro Brief: agents-memory-ci-v1

**Hook:** `automation.ci_memory`, `memory.agents_md`, `workflow.git_handoff`

## Feature Name

AGENTS.md Memory CI v1 — local lint, dedupe, and proposal workflow for durable memory updates.

## Holistic Link

Prevents transient chat from polluting durable agent guidance while enabling governed promotion.

## Macro Link

Operationalizes [context-handoff-and-automation.md](../../context-handoff-and-automation.md) CI section without auto-writing to `main`.

## Scope

| In scope | Out of scope |
|----------|--------------|
| Local script/CLI: lint `AGENTS.md` structure | Nightly GitHub Actions (defer to v2) |
| Duplicate bullet detection | Transcript extraction |
| Max length / section checks | Direct merge to `main` |
| Proposal patch file output | Full Continual Learning plugin |

**Files:** `src/hive_planner/agents_memory.py`, `cli.py`, tests (future)

## Inputs / Outputs

- **In:** `AGENTS.md`, optional candidate bullets file
- **Out:** Validation report, proposed patch under `docs/proposals/agents-memory-*.md`

## Acceptance Criteria

- [x] Missing required sections → error with line hints
- [x] Duplicate bullets flagged
- [x] Bullets over max length flagged
- [x] Proposal file written; `AGENTS.md` unchanged unless `--apply` (default off)
- [x] `--apply` rejected in v1 (proposal-only)

## Validation

```powershell
py -3.11 -m hive_planner agents-lint
py -3.11 -m hive_planner agents-propose --candidates path/to/candidates.md
```
