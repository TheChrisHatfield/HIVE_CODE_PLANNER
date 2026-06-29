# Tasks: unified-handoff-v2

**Spec:** [spec.md](./spec.md) · **Plan:** [plan.md](./plan.md)

## Task 1 — Stage 9 spec artifacts ✅

- [x] `docs/specs/unified-handoff-v2/spec.md`
- [x] `docs/specs/unified-handoff-v2/plan.md`
- [x] `docs/delta/20_micro/unified-handoff-v2.md`
- [x] `docs/unified-handoff-upstream-forks.md`
- [x] `docs/delta/STAGE_ROADMAP.md` Stage 9 section

## Task 2 — Vendor manifest skeleton ✅

- [x] Add `vendor/README.md` and `vendor/manifest.json` (template pins)
- [x] Document submodule vs fork workflow in upstream forks guide
- [x] CI: `unified-vendor` step validates manifest schema (hive source)

## Task 3 — Upstream vendor sync ✅

- [x] Script or submodule: pin `github/spec-kit` at stable ref (`b7e67f55`)
- [x] Script or subtree: pin `cursor/plugins/continual-learning` at stable ref (`0452e08`)
- [x] Record SHAs in `vendor/manifest.json` after first import
- [x] `vendor-sync --apply` imports via git sparse checkout

## Task 4 — Hive Spec Kit patches ✅

- [x] Task template: wiring audit checklist per task
- [x] Spec template: Rosetta nav placeholder block
- [x] Document feature-id ↔ `.hive/project.json` in Spec Kit README overlay
- [x] Post-`/tasks` validation doc → `spec-drift-check` (`WORKFLOW.md`)
- [x] Packaged overlay at `vendor_templates/spec-kit/` → `.hive/spec-kit/` on bootstrap

## Task 5 — Hive Continual Learning patches ✅

- [x] Map `Learned Workspace Facts` → `Durable Workspace Facts`
- [x] Subagent: reject/route behavioral bullets (mirror `classify_bullet`)
- [x] Skill: require wiring audit before AGENTS.md edit
- [x] Optional: export candidates markdown for `agents-propose`
- [x] Packaged overlay at `vendor_templates/continual-learning/` → `.cursor/plugins/hive-continual-learning/` on bootstrap

## Task 6 — Bootstrap deploy wiring ✅

- [x] `vendor_sync.py` — manifest load, verify, project pins snapshot
- [x] `init --agent-handoff unified` writes `.hive/upstream-pins.json`
- [x] `deploy_agent_handoff_scaffold` writes `.hive/upstream-pins.json`
- [x] Copy Spec Kit overlay to `.hive/spec-kit/` (Task 4)
- [x] Copy vendored CL plugin to `.cursor/plugins/hive-continual-learning/` (Task 5)

## Task 7 — CLI and optional extra

- [x] `pyproject.toml` `[unified]` optional extra + `vendor_templates` package-data
- [x] `hive_planner vendor-sync` / `unified-verify` commands
- [x] Launcher help text for unified vendor path

## Task 8 — Tests and CI

- [x] `tests/test_unified_handoff.py`
- [x] Optional `ci-check` step `unified-vendor`
- [x] Bootstrap tests assert upstream pins when unified (see test_unified_handoff)

## Task 9 — Docs closure ✅

- [x] Update `docs/project-bootstrap-guide.md`
- [x] Update `starter-kit/spec-kit-agent-integration.md`
- [x] Cross-link `docs/cl-spec-integration.md` → upstream forks doc

## Task 10 — Stage 9 roadmap closure (roadmap-complete-v4) ✅

- [x] Add `roadmap-complete-v4` spec/micro/tasks
- [x] Extend `ROADMAP_FEATURES` to include Stage 9 features
- [x] Bump hive-planner version (v1.3.0 target)

## Active task

**None** — Stage 9 (`unified-handoff-v2`) complete.

## Validation log

```text
2026-06-26 — Stage 9 spec drafted (Task 1)
- unified-handoff-v2 spec/plan/tasks + upstream forks guide
- STAGE_ROADMAP Stage 9 planned (ROADMAP_FEATURES unchanged at 20/20)

2026-06-26 — Stage 9 Task 4 Spec Kit patches
- vendor_templates/spec-kit overlay (SK-1–SK-5); deploy to .hive/spec-kit on unified bootstrap
- spec_kit hive_patch_rev bumped to 2

2026-06-26 — Stage 9 closure (Tasks 5–10)
- CL overlay deploy; launcher vendor help; docs closure; roadmap-complete-v4; v1.3.0
```
