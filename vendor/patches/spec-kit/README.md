# Spec Kit Hive patches (optional override)

Packaged overlay ships in `src/hive_planner/vendor_templates/spec-kit/` and deploys to `.hive/spec-kit/` on unified bootstrap.

To override pins locally for hive source development, add files here (same layout as the packaged overlay). Bump `hive_patch_rev` in `vendor/manifest.json` when patches change.

See [docs/unified-handoff-upstream-forks.md](../../docs/unified-handoff-upstream-forks.md).
