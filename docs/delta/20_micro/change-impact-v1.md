# Feature Micro Brief: change-impact-v1

**Hook:** `change.impact`, `next.files`, `change.validation`

## Feature Name

Change Impact Lift v1 — pre-edit impact packets for primary/secondary/tertiary change awareness.

## Holistic Link

Reduces coding drift and regressions by forcing causal effect review before patches.

## Macro Link

Adds **change-impact** subsystem alongside compiler per [change-impact-lift.md](../../change-impact-lift.md).

## Scope

| In scope | Out of scope |
|----------|--------------|
| `docs/change-impact/` scaffold | Full call-graph analysis |
| Impact packet JSON schema | CI auto-merge to AGENTS.md |
| `hive_planner impact` CLI | Schema/code graph automation |
| `.cursor/rules/change-impact.mdc` | |

## Acceptance Criteria

- [x] `impact --feature X --files path` writes packet JSON
- [x] Unknown feature → error, no empty packet
- [x] Primary `src/` target lists tests from test-map
- [x] `docs/delta/*` edits flagged as tertiary doc impact
- [x] Invalid packet JSON on load → warning only (does not block ingest/emit)
- [x] Shared bug gate B1–B8 still pass

## Validation

```powershell
py -3.11 -m hive_planner impact --feature cartridge-compiler-v2 --files src/hive_planner/emitter.py
py -3.11 -m pytest -v
```
