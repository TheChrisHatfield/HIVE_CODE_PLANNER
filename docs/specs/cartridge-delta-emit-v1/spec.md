# Spec: cartridge-delta-emit-v1

**Hook:** `context.cartridge`, `context.delta`, `compiler.pipeline`  
**Status:** active  
**Delta:** [cartridge-delta-emit-v1.md](../../delta/20_micro/cartridge-delta-emit-v1.md)

## What

Extend cartridge `emit` to copy primary Delta layers into `cartridge/` alongside manifest and source-context.

## Why

Compiler v1 deferred holistic/macro auto-emission. Schema maps cartridge holistic/macro to Delta; this closes the loop for agent loading without manual copy.

## Requirements

### R1 — Delta sources

- Holistic: `docs/delta/00_holistic.md`
- Macro: `docs/delta/10_macro.md`
- Micro: `docs/delta/20_micro/<feature>.md` when present

### R2 — Cartridge targets

- `cartridge/holistic.md`
- `cartridge/macro.md`
- `cartridge/micro/<feature>.md`

### R3 — AUTO-SYNC contract

- Prefix: `<!-- AUTO-SYNC: from docs/delta/... -->`
- Re-emit updates files that retain AUTO-SYNC banner
- Skip files with `<!-- DRAFT:` or `<!-- MANUAL:` banners (translator/manual edits)

### R4 — Force flag

- `emit --force-delta` overwrites skipped draft/manual targets

### R5 — Manifest stats

- `stats.delta_sync`: `{ holistic, macro, micro }` → `written | updated | skipped (...) | missing`

### R6 — Regression

- Source-context emission, hybrid retrieval, and ingest unchanged

## Out of scope

Reverse promotion to Delta, AGENTS.md writes, translator changes, CI automation.
