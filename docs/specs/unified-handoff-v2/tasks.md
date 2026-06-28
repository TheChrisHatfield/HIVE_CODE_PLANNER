# Tasks: unified-handoff-v2

**Spec:** [spec.md](./spec.md) · **Plan:** [plan.md](./plan.md)

## Task 1 — Stage 9 spec artifacts ✅

- [x] `docs/specs/unified-handoff-v2/spec.md`
- [x] `docs/specs/unified-handoff-v2/plan.md`
- [x] `docs/delta/20_micro/unified-handoff-v2.md`
- [x] `docs/unified-handoff-upstream-forks.md`
- [x] `docs/delta/STAGE_ROADMAP.md` Stage 9 section

## Task 2 — Vendor manifest skeleton

- [ ] Add `vendor/README.md` and `vendor/manifest.json` (template pins)
- [ ] Document submodule vs fork workflow in upstream forks guide
- [ ] CI: fail if manifest missing required keys

## Task 3 — Upstream vendor sync

- [ ] Script or submodule: pin `github/spec-kit` at stable ref
- [ ] Script or subtree: pin `cursor/plugins/continual-learning` at stable ref
- [ ] Record SHAs in `vendor/manifest.json` after first import

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

- [ ] `vendor_sync.py` — copy plugin + spec-kit overlay to target
- [ ] `init --agent-handoff unified` invokes vendor deploy
- [ ] `deploy_agent_handoff_scaffold` invokes vendor deploy
- [ ] Write `.hive/upstream-pins.json` on bootstrap

## Task 7 — CLI and optional extra

- [ ] `pyproject.toml` `[unified]` optional extra + package-data for vendor templates
- [ ] `hive_planner vendor-sync` / `unified-verify` commands
- [ ] Launcher help text for unified vendor path

## Task 8 — Tests and CI

- [ ] `tests/test_unified_handoff.py`
- [ ] Optional `ci-check` step `unified-vendor`
- [ ] Bootstrap tests assert vendor artifacts when unified

## Task 9 — Docs closure

- [ ] Update `docs/project-bootstrap-guide.md`
- [ ] Update `starter-kit/spec-kit-agent-integration.md`
- [ ] Cross-link `docs/cl-spec-integration.md` → upstream forks doc

## Task 10 — Stage 9 roadmap closure (roadmap-complete-v4)

- [ ] Add `roadmap-complete-v4` spec/micro/tasks
- [ ] Extend `ROADMAP_FEATURES` to include Stage 9 features
- [ ] Bump hive-planner version (v1.3.0 target)

## Active task

**Task 2** — Vendor manifest skeleton (next implementation slice).

## Validation log

```text
2026-06-26 — Stage 9 spec drafted (Task 1)
- unified-handoff-v2 spec/plan/tasks + upstream forks guide
- STAGE_ROADMAP Stage 9 planned (ROADMAP_FEATURES unchanged at 20/20)
```
