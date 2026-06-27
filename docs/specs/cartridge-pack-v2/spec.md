# Spec: cartridge-pack-v2

**Hook:** `context.cartridge`, `cursor.rules`  
**Status:** active  
**Delta:** [cartridge-pack-v2.md](../../delta/20_micro/cartridge-pack-v2.md)

## What

Optional `--emit-rules-seeds` on cartridge `emit` to produce reviewable Cursor rule seeds under `cartridge/rules/`.

## Requirements

### R1 — Rule seed output

- When `--emit-rules-seeds` is set, write `cartridge/rules/<feature>.mdc.seed`.
- Body derived from Delta macro excerpt + micro brief (scope, acceptance, validation).
- Prefix with `<!-- DRAFT: rule seed ... -->` banner.

### R2 — No auto-compile to Cursor

- Never write or overwrite `.cursor/rules/*.mdc` during emit.
- Human copies reviewed seed → `.cursor/rules/` after editing.

### R3 — Regeneration policy

- Re-emit updates seeds that retain the draft banner.
- Skip seeds marked `<!-- MANUAL:` unless `--force-delta`.
- Skip seeds whose draft banner was removed (treated as reviewed).

### R4 — Manifest

- `targets.cursor_rules` is `"seed"` when flag set, `false` otherwise.
- `stats.pack_sync.rules_seed` reports written/updated/skipped/missing/disabled.

### R5 — Source map

- Include `cursor_rule_seed` mapping in `cartridge/mappings/source-map.json`.

## Out of scope

Auto-attaching rules in Cursor, LLM rule generation, overwriting live `.cursor/rules/`.
