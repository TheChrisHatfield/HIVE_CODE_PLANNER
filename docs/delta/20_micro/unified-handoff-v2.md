# Feature Micro Brief: unified-handoff-v2

**Hook:** `integration.cl_spec`, `integration.unified_handoff`, `workflow.project_bootstrap`, `spec.flow`

## Feature Name

Unified agent handoff v2 — vendored Spec Kit + Continual Learning forks with Hive symbiosis.

## Scope

| In scope | Out of scope |
|----------|--------------|
| Fork pins + vendor layout for Spec Kit and CL plugin | Cloud deploy / SaaS packaging |
| Bootstrap/deploy installs Hive-patched upstreams | Auto-editing `spec.md` from transcripts |
| Single contract: IDE CL plugin ↔ Hive CLI gates | Non-Cursor IDEs (v2) |
| `hive-planner[unified]` optional extra | Rewriting Spec Kit core in Python |

## Problem

Stage 7 integrated Spec Kit and Continual Learning **around** external tools (docs, rules, `agents-propose`, `spec-drift-check`). Multi-user deploy still assumes users install marketplace Spec Kit and CL separately. Section names and gates diverge (upstream CL uses `## Learned Workspace Facts`; Hive uses `## Durable Workspace Facts`).

## Acceptance Criteria

- [x] `vendor/` layout documented with pinned upstream SHAs
- [x] Hive fork patch list applied to Spec Kit templates + CL subagent/skill
- [x] `init --agent-handoff unified` and `deploy-agent-handoff` copy vendored plugin + spec-kit config
- [x] CL plugin pre-promote calls wiring audit + `spec-drift-check` / `agents-propose` contract
- [x] `pyproject.toml` exposes `[unified]` optional extra with install docs
- [x] `docs/unified-handoff-upstream-forks.md` is the operator guide
- [x] Tests cover vendor copy + version pin manifest

## Validation

```powershell
py -3.11 -m hive_planner init --target ./tmp-unified --agent-handoff unified --force
# expect vendor manifest + .cursor plugin + spec-kit hive templates
py -3.11 -m hive_planner ci-check --skip-pytest
py -3.11 -m pytest tests/test_unified_handoff.py -q
```

## Related

- [unified-handoff-v2 spec](../../specs/unified-handoff-v2/spec.md)
- [unified-handoff-upstream-forks.md](../../unified-handoff-upstream-forks.md)
- [cl-spec-integration-v1.md](./cl-spec-integration-v1.md) (Stage 7 contract — superseded at runtime by v2 forks)
