# Spec: cartridge-translator-v1

**Hook:** `context.cartridge`, `context.cartridge_schema`  
**Status:** active  
**Delta:** [cartridge-translator-v1.md](../../delta/20_micro/cartridge-translator-v1.md)

## What

Add a rule-based translator that classifies text segments into Holistic, Macro, Micro, Memory, or Reject and emits **draft** cartridge files under `cartridge/`.

## Why

Stage 4A completes format ingestion. The schema in [cartridge-schema-v1.md](../../cartridge-schema-v1.md) defines a translator pipeline that turns research into structured context — v1 uses deterministic rules, not an LLM.

## Requirements

### R1 — Segment input

- Accept file path (`--input`) or read from normalized markdown in context library.
- Split into segments by headings and blank-line paragraphs.

### R2 — Classification rules

- Keyword/rule maps per bucket from schema (mission → Holistic, subsystem → Macro, task/files → Micro, durable guidance → Memory).
- Default unmatched → Reject.
- Log classification counts in status JSON.

### R3 — Compress

- Trim segments to short bullet statements (max ~240 chars each).
- Deduplicate near-identical lines.

### R4 — Draft emit

- Write under `cartridge/` only:
  - `holistic.md`, `macro.md`, `micro/<feature>.md`, `memory.md`
  - optional `specs/<feature>.specseed.md`
- Prefix each file with draft banner: `<!-- DRAFT: review before promoting -->`

### R5 — Status contract

- Emit JSON matching suggested contract in cartridge schema (`status`, `files_written`, `promotions`, `rejections`).

### R6 — Governance

- Translator output is **secondary** — must not override active Delta/spec/tasks.
- No automatic writes to `AGENTS.md` or `.cursor/rules/`.

## Out of scope

LLM calls, auto-merge to Delta, CI automation, embedding-based classification.
