<!--
meta:hook_id: integration.unified_handoff
meta:purpose: Vendor pins and Hive patch list for Spec Kit + Continual Learning
meta:status: active
-->

# Unified Handoff — Upstream Forks

**Hook:** `integration.unified_handoff`, `integration.cl_spec`  
**Spec:** [specs/unified-handoff-v2/spec.md](./specs/unified-handoff-v2/spec.md)

Operator guide for vendoring, pinning, and patching Spec Kit and Continual Learning for Hive unified deploy.

## Why fork instead of marketplace-only

Stage 7 built Hive-side gates (`agents-propose`, `spec-drift-check`, wiring audit rules) **around** external tools. For multi-user deploy, users should not manually install:

- GitHub Spec Kit CLI separately
- Cursor marketplace `/add-plugin continual-learning` separately

Both upstreams have **open GitHub source**. Hive ships **pinned forks** with symbiotic patches and bootstrap install.

## Upstream sources

| Component | Upstream repo | Hive vendor path | License |
|-----------|---------------|------------------|---------|
| Spec Kit | [github/spec-kit](https://github.com/github/spec-kit) | `vendor/spec-kit/` | Check upstream |
| Continual Learning | [cursor/plugins → continual-learning](https://github.com/cursor/plugins/tree/main/continual-learning) | `vendor/cursor-plugins/continual-learning/` | MIT |

**Recommended:** maintain org forks (e.g. `hive-code-planner/spec-kit`, `hive-code-planner/continual-learning`) and submodule/subtree into this repo. Track pins in `vendor/manifest.json`.

## Pin manifest (template)

Create `vendor/manifest.json` when Task 2 lands:

```json
{
  "schema": "hive-upstream-pins/v1",
  "updated": "2026-06-26",
  "spec_kit": {
    "upstream": "https://github.com/github/spec-kit",
    "fork": "https://github.com/<org>/spec-kit",
    "path": "vendor/spec-kit",
    "ref": "TBD",
    "hive_patch_rev": "1"
  },
  "continual_learning": {
    "upstream": "https://github.com/cursor/plugins",
    "fork": "https://github.com/<org>/continual-learning",
    "path": "vendor/cursor-plugins/continual-learning",
    "subtree": "continual-learning",
    "ref": "TBD",
    "hive_patch_rev": "1"
  }
}
```

Bootstrapped projects receive a snapshot at `.hive/upstream-pins.json`.

## Sync workflow

```powershell
py -3.11 -m hive_planner vendor-sync --check
py -3.11 -m hive_planner vendor-sync --apply
py -3.11 -m hive_planner unified-verify
```

### Submodule vs fork (recommended)

| Approach | When to use | Notes |
|----------|-------------|-------|
| **Org fork + submodule** | Production Hive deploy | Pin `ref` in `vendor/manifest.json`; CI `unified-vendor` validates schema |
| **Git subtree** | Single-repo consumers | Import `continual-learning/` subtree only |
| **Package template only** | Bootstrapped app projects | Bootstrap copies `.hive/upstream-pins.json`; no `vendor/` in target |

Hive source CI runs `unified-vendor` when `vendor/manifest.json` exists (`TBD` refs warn until Task 3 import).

Manual interim workflow:

```powershell
git submodule add -b main https://github.com/<org>/spec-kit vendor/spec-kit
# continual-learning: subtree or submodule of fork containing only plugin dir
```

## Hive patch list — Spec Kit

Apply on top of pinned upstream ref. Bump `hive_patch_rev` when patches change.

| ID | File / area | Patch |
|----|-------------|-------|
| SK-1 | Task generation template | Append per-task **Integration wiring audit** checklist referencing `.cursor/rules/integration-wiring-audit.mdc` |
| SK-2 | Spec template | Optional `## Agent navigation (Rosetta Stone)` placeholder compatible with `hive_planner.rosetta_nav` |
| SK-3 | Feature docs | Document active feature id ↔ `docs/delta/20_micro/<feature>.md` ↔ `.hive/project.json` |
| SK-4 | Workflow doc | After `/tasks`, require wiring audit before checkoff; before CL, run `spec-drift-check` |
| SK-5 | Templates dir | Ship overlay at `.hive/spec-kit/templates/` copied by bootstrap |

## Hive patch list — Continual Learning

Upstream plugin structure:

```text
continual-learning/
├── .cursor-plugin/
├── hooks/              # stop cadence (JS)
├── skills/continual-learning/
└── agents/             # agents-memory-updater
```

| ID | File / area | Patch |
|----|-------------|-------|
| CL-1 | `agents/` subagent prompt | Write operational bullets to `## Durable Workspace Facts` (Hive section name) |
| CL-2 | Subagent guardrails | Reject or route behavioral bullets to `docs/specs/<feature>/spec.md` (same heuristics as `spec_drift.classify_bullet`) |
| CL-3 | Skill workflow | Block AGENTS.md edit until Integration wiring audit passes |
| CL-4 | Hook or skill | Optional export: write candidate file under `docs/proposals/` for `agents-propose` CI parity |
| CL-5 | README | Document Hive env vars: `HIVE_WIRING_AUDIT`, `HIVE_SPEC_DRIFT_CHECK`, link to `docs/cl-spec-integration.md` |
| CL-6 | Section mapping | If keeping upstream headings for compatibility, map `Learned Workspace Facts` → merge target `Durable Workspace Facts` |

## Single contract (IDE + CI)

Both fork paths must honor [cl-spec-integration.md](./cl-spec-integration.md):

1. Behavioral → Spec Kit `spec.md`
2. Operational → `AGENTS.md` `## Durable Workspace Facts`
3. Wiring audit before memory promotion
4. `spec-drift-check` before merge / session end

Hive CLI (`agents_memory.py`, `spec_drift.py`) remains the **CI and headless** enforcement layer. The forked CL plugin is the **IDE** enforcement layer. Same rules, two runtimes.

## Bootstrap deploy targets

When `agent_handoff=unified`, bootstrap copies:

| Artifact | Target (planned) |
|----------|------------------|
| Hive-patched CL plugin | `.cursor/plugins/hive-continual-learning/` or project plugin path per Cursor spec |
| Spec Kit template overlay | `.hive/spec-kit/` |
| Pin snapshot | `.hive/upstream-pins.json` |
| Existing Stage 7 rules | `.cursor/rules/integration-wiring-audit.mdc`, `cl-spec-integration.mdc` |

Warn when marketplace CL plugin is also enabled; recommend vendored fork for Hive projects.

## Install for end users (target)

```powershell
pip install "hive-planner[unified]"
py -3.11 -m hive_planner init --target ./my-app --profile full --agent-handoff unified --git-init
```

User gets: Delta scaffold, Spec Kit templates, vendored CL plugin, Hive CLI gates, pin snapshot — one flow.

## Out of scope (v2)

- Publishing separate PyPI packages for forks
- Running Spec Kit inside `hive_planner` Python process
- Replacing Cursor hook runtime with pure Python

## Related

- [cl-spec-integration.md](./cl-spec-integration.md)
- [project-bootstrap-guide.md](./project-bootstrap-guide.md)
- [specs/unified-handoff-v2/spec.md](./specs/unified-handoff-v2/spec.md)
