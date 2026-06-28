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

## Task 4 — Hive Spec Kit patches

- [ ] Task template: wiring audit checklist per task
- [ ] Spec template: Rosetta nav placeholder block
- [ ] Document feature-id ↔ `.hive/project.json` in Spec Kit README overlay
- [ ] Post-`/tasks` validation doc → `spec-drift-check`

## Task 5 — Hive Continual Learning patches

- [ ] Map `Learned Workspace Facts` → `Durable Workspace Facts`
- [ ] Subagent: reject/route behavioral bullets (mirror `classify_bullet`)
- [ ] Skill: require wiring audit before AGENTS.md edit
- [ ] Optional: export candidates markdown for `agents-propose`

## Task 6 — Bootstrap deploy wiring

- [x] `vendor_sync.py` — manifest load, verify, project pins snapshot
- [x] `init --agent-handoff unified` writes `.hive/upstream-pins.json`
- [x] `deploy_agent_handoff_scaffold` writes `.hive/upstream-pins.json`
- [ ] Copy vendored plugin + spec-kit overlay to target (Task 3+)

## Task 7 — CLI and optional extra

- [x] `pyproject.toml` `[unified]` optional extra + `vendor_templates` package-data
- [x] `hive_planner vendor-sync` / `unified-verify` commands
- [ ] Launcher help text for unified vendor path

## Task 8 — Tests and CI

- [x] `tests/test_unified_handoff.py`
- [x] Optional `ci-check` step `unified-vendor`
- [x] Bootstrap tests assert upstream pins when unified (see test_unified_handoff)

## Task 9 — Docs closure

- [ ] Update `docs/project-bootstrap-guide.md`
- [ ] Update `starter-kit/spec-kit-agent-integration.md`
- [ ] Cross-link `docs/cl-spec-integration.md` → upstream forks doc

## Task 10 — Stage 9 roadmap closure (roadmap-complete-v4)

- [ ] Add `roadmap-complete-v4` spec/micro/tasks
- [ ] Extend `ROADMAP_FEATURES` to include Stage 9 features
- [ ] Bump hive-planner version (v1.3.0 target)

## Active task

**Task 4** — Hive Spec Kit patches (wiring audit template, Rosetta nav, feature-id docs).

## Validation log

```text
2026-06-26 — Stage 9 spec drafted (Task 1)
- unified-handoff-v2 spec/plan/tasks + upstream forks guide
- STAGE_ROADMAP Stage 9 planned (ROADMAP_FEATURES unchanged at 20/20)

2026-06-26 — Stage 9 Task 3 upstream import
- vendor-sync --apply imports spec-kit + continual-learning at pinned SHAs
- vendor/spec-kit @ b7e67f55, vendor/cursor-plugins/continual-learning @ 0452e08
```
