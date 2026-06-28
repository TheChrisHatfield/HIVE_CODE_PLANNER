# Spec: unified-handoff-v2

**Hook:** `integration.unified_handoff`, `integration.cl_spec`, `workflow.project_bootstrap`, `spec.flow`  
**Status:** planned  
**Delta:** [unified-handoff-v2.md](../../delta/20_micro/unified-handoff-v2.md)

## What

Ship Hive Code Planner as a **unified deploy package**: vendored, pinned forks of **GitHub Spec Kit** and **Cursor Continual Learning** (from `cursor/plugins`), plus bootstrap wiring so new projects get symbiotic Spec Kit + CL + Hive CLI gates without manual marketplace installs.

Stage 7 (`cl-spec-integration-v1`) defined the **contract** (behavioral vs operational, wiring audit, `spec-drift-check`). Stage 9 **implements upstream coupling** via controlled forks, not marketplace assumptions.

## Background

| Upstream | Source | Delivery today | Hive gap |
|----------|--------|----------------|----------|
| Spec Kit | [github/spec-kit](https://github.com/github/spec-kit) | External CLI (`/specify`, `/plan`, `/tasks`) | No Hive templates (Rosetta nav, wiring audit in tasks) |
| Continual Learning | [cursor/plugins/continual-learning](https://github.com/cursor/plugins/tree/main/continual-learning) | Cursor marketplace plugin | Section mismatch; no spec-drift / wiring-audit gate in plugin |

Hive already implements a **portable CLI mirror** (`agents_memory.py`, `spec_drift.py`). v2 aligns the **IDE plugin path** with that mirror via shared contract and fork patches.

## Requirements

### R1 — Vendor layout and pin manifest

Add `vendor/` (or git submodules) with pin manifest `vendor/manifest.json`:

```json
{
  "spec_kit": {
    "upstream": "https://github.com/github/spec-kit",
    "path": "vendor/spec-kit",
    "ref": "<pinned-tag-or-sha>"
  },
  "continual_learning": {
    "upstream": "https://github.com/cursor/plugins",
    "path": "vendor/cursor-plugins/continual-learning",
    "ref": "<pinned-tag-or-sha>",
    "subtree": "continual-learning"
  }
}
```

Document update policy: bump pins only with changelog entry and regression tests.

### R2 — Hive Spec Kit fork patches

Minimum patches on vendored Spec Kit (templates / commands / docs):

1. **Task template** — include Integration wiring audit checklist (`.cursor/rules/integration-wiring-audit.mdc`).
2. **Spec template** — optional Rosetta navigation block placeholder compatible with `hive_planner.rosetta_nav`.
3. **Feature id** — document alignment with `.hive/project.json` active feature and `docs/delta/20_micro/<feature>.md`.
4. **Post-`/tasks` hook doc** — run wiring audit before marking tasks complete; reference `spec-drift-check` before CL promotion.

Do not rewrite Spec Kit core logic in Python; patch templates and Hive-specific command wrappers only.

### R3 — Hive Continual Learning fork patches

Minimum patches on vendored `continual-learning/` plugin:

1. **Section alignment** — write operational bullets to `## Durable Workspace Facts` (Hive standard) or map upstream `## Learned Workspace Facts` → Hive section in subagent prompt.
2. **Behavioral routing** — subagent rejects or tags behavioral bullets; direct user to `docs/specs/<feature>/spec.md` (mirror `agents-propose` heuristics).
3. **Pre-promote gate** — skill/subagent requires Integration wiring audit pass before editing `AGENTS.md`.
4. **CLI bridge** — optional export to `docs/proposals/candidates-template.md` format for `hive_planner agents-propose` (CI parity).
5. **Env vars** — document `CONTINUAL_LEARNING_*` plus Hive overrides (`HIVE_SPEC_DRIFT_CHECK=1`, `HIVE_WIRING_AUDIT=1`).

Preserve MIT license and upstream attribution in `vendor/README.md`.

### R4 — Unified optional dependency

`pyproject.toml`:

```toml
[project.optional-dependencies]
unified = []  # meta extra; documents vendor install path
```

Add `hive_planner vendor-sync` (or `unified-install`) CLI:

- Verify `vendor/manifest.json` pins
- Copy Hive-patched plugin into target `.cursor/` (or documented plugin install path)
- Emit Spec Kit config pointer for bootstrapped projects

### R5 — Bootstrap and deploy integration

Extend `init --agent-handoff unified` and `deploy_agent_handoff_scaffold`:

1. Copy vendored CL plugin tree into target (e.g. `.cursor/plugins/hive-continual-learning/` or merge hooks per Cursor plugin spec).
2. Copy Hive Spec Kit template overlay into target (e.g. `.hive/spec-kit/` or `docs/specs/_templates/`).
3. Write `vendor/manifest.json` snapshot into target `.hive/upstream-pins.json`.
4. Warn when marketplace CL is also installed — prefer vendored fork for Hive projects.

Existing rules (`integration-wiring-audit.mdc`, `cl-spec-integration.mdc`) remain; v2 does not remove Stage 7 artifacts.

### R6 — Single symbiotic contract

One document remains authoritative: `docs/cl-spec-integration.md`. Fork patches must not contradict:

| Layer | Owner |
|-------|-------|
| Behavioral | Spec Kit `spec.md` |
| Operational | `AGENTS.md` `## Durable Workspace Facts` |
| IDE memory loop | Hive-patched CL plugin |
| CI / headless | `agents-propose`, `spec-drift-check`, `ci-check` |

Add `docs/unified-handoff-upstream-forks.md` as operator guide (pins, patch list, sync workflow).

### R7 — Validation and CI

- New tests: `tests/test_unified_handoff.py` — vendor manifest present, bootstrap copies plugin overlay, pin snapshot written.
- `ci-check` optional step `unified-vendor` when `.hive/upstream-pins.json` exists (warn if pins drift from Hive source manifest).
- `roadmap-complete-v4` (future) closes Stage 9 artifact count.

### R8 — Documentation

Update:

- `docs/project-bootstrap-guide.md` — unified install path
- `starter-kit/spec-kit-agent-integration.md` — vendored Spec Kit, not marketplace-only
- `docs/cl-spec-integration.md` — link to upstream forks doc
- `docs/delta/STAGE_ROADMAP.md` — Stage 9 tracking

## Out of scope

- Forking entire `cursor/plugins` monorepo (only `continual-learning` subtree)
- PyPI packaging of Spec Kit as `hive-spec-kit` wheel (future optional)
- Auto-editing `spec.md` from transcript mining
- Non-Cursor agent runtimes (Copilot, Claude Code) in v2
- Cloud sync of CL state

## Success metrics

- New user runs one command chain and gets Spec Kit templates + CL plugin + Hive gates without manual `/add-plugin`
- Behavioral bullet attempted in IDE is rejected or routed to spec (same outcome as `agents-propose`)
- `ci-check` and IDE path share one candidate format

## Related

- [unified-handoff-upstream-forks.md](../../unified-handoff-upstream-forks.md)
- [cl-spec-integration-v1](../cl-spec-integration-v1/spec.md)
- [project-bootstrap-v1](../project-bootstrap-v1/spec.md)
