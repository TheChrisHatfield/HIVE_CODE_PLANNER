# Spec: cartridge-pack-v1

**Hook:** `context.cartridge`, `context.cartridge_schema`  
**Status:** active  
**Delta:** [cartridge-pack-v1.md](../../delta/20_micro/cartridge-pack-v1.md)

## What

Extend `emit` to produce remaining cartridge schema files alongside delta sync and source-context.

## Requirements

### R1 — research-summary.md

Built from active feature micro brief + spec (problem, findings, constraints, risks, open questions).

### R2 — memory.md

Sync `## Durable Workspace Facts` from AGENTS.md with AUTO-SYNC banner; respect draft/manual skip rules.

### R3 — specseed

Copy `docs/specs/<feature>/spec.md` into `cartridge/specs/<feature>.specseed.md` with draft banner when missing/skippable.

### R4 — source-map.json

Map cartridge paths to Delta/spec/AGENTS/context-library sources.

### R5 — Manifest

Include `files` list and `stats.pack_sync`; write manifest after all outputs.

## Out of scope

LLM generation, auto-promotion to Delta, cursor rules emission.
