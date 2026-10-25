<!-- DRAFT: review before promoting -->

<!-- AUTO-SYNC: from AGENTS.md -->

# Memory (from AGENTS.md)

- Use Python 3.11 for local development (`py -3.11`).
- Stage 4C adds proposal-only AGENTS.md memory lint/propose; guarded `agents-apply` enabled in v2.
- Stage 5A syncs Delta holistic/macro/micro into cartridge on emit; skips draft/manual files unless `--force-delta`.
- Stage 5B adds `impact-sync-maps` to merge src/test discovery into change-impact maps without overwriting curated rows.
- Stage 5C adds `ci-check` for handoff validation (pytest, agents-lint, spec artifacts, map drift, spec-drift).
- Stage 6A adds full cartridge pack emit (research-summary, memory, specseed, source-map).
- v1.0.0 — Stages 1–6 compiler roadmap complete; use `roadmap-status` to verify.
- v1.1.0 — Stage 7 complete (CL/spec integration, memory v2, rule seeds, impact v3, project bootstrap); `roadmap-status` validates 18/18 features.
- v1.2.0 — Stage 8 complete (starter-kit v2 full profile, path/feature validation hardening); `roadmap-status` validates 20/20 features.
- v1.3.0 — Stage 9 complete (unified Spec Kit + CL vendored deploy); `roadmap-status` validates 22/22 features; use `unified-verify` on bootstrapped projects.
- `hive_planner init` must target a directory outside the Hive source tree (never a subdirectory of this repo). # operational
- Bootstrapped projects use plain `None` for active feature until the first real feature id is set.
- Starter-kit v2 (`--profile full`) adds pyproject, src/tests layout, `.gitignore`, and GitHub CI stub; `--git-init` is optional.
