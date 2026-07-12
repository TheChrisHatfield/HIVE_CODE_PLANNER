# Hive Continual Learning (unified handoff)

Hive-patched fork of [cursor/plugins/continual-learning](https://github.com/cursor/plugins/tree/main/continual-learning) for symbiotic deploy with Hive Planner and Spec Kit.

**Deploy path:** `.cursor/plugins/hive-continual-learning/`  
**Contract:** [docs/cl-spec-integration.md](../../../../docs/cl-spec-integration.md)

## Hive patches (CL-1–CL-6)

| ID | Change |
|----|--------|
| CL-1 | Write operational bullets to `## Durable Workspace Facts` |
| CL-2 | Route behavioral bullets to `docs/specs/<feature>/spec.md` |
| CL-3 | Skill requires wiring audit before AGENTS.md edit |
| CL-4 | Export candidates to `docs/proposals/cl-candidates.md` |
| CL-5 | Hive env vars documented below |
| CL-6 | Map `## Learned Workspace Facts` → `## Durable Workspace Facts` |
| CL-7 | Prefer autonomous `agents-propose --apply` (auto-split / route / Thompson) over hand-editing AGENTS.md |

## Installation (Hive bootstrap)

Unified bootstrap copies this plugin to `.cursor/plugins/hive-continual-learning/`. Prefer the vendored fork over marketplace `/add-plugin continual-learning` for Hive projects.

## How it works

Same upstream architecture: `stop` hook → `continual-learning` skill → `agents-memory-updater` subagent.

Hive additions: wiring audit gate, behavioral routing, autonomous memory routing via Hive CLI, spec-drift parity with CLI.

## Trigger cadence

See upstream defaults in hook config. Optional env overrides:

- `CONTINUAL_LEARNING_MIN_TURNS` / `CONTINUAL_LEARNING_MIN_MINUTES`
- `CONTINUAL_LEARNING_TRIAL_MODE` and trial variants

### Hive overrides (CL-5)

- `HIVE_WIRING_AUDIT=1` — enforce wiring audit gate before memory promotion (default on for unified handoff)
- `hive_planner wiring-audit record --evidence "<command>"` — record attestation after audit
- `hive_planner wiring-audit check` — verify attestation matches active feature and tasks checklist
- `HIVE_SPEC_DRIFT_CHECK=1` — remind to run `spec-drift-check` before AGENTS.md merge

## Output format in AGENTS.md (Hive)

- `## Learned User Preferences` — optional user tone/preferences
- `## Durable Workspace Facts` — **operational only** (Hive standard)

Do not use `## Learned Workspace Facts` in new writes; merge legacy content into Durable Workspace Facts.

## License

MIT (upstream). See LICENSE.
