<!-- AUTO-SYNC: from docs/specs/cartridge-compiler-v1/spec.md -->

# Spec seed: cartridge-compiler-v1

# Spec: cartridge-compiler-v1

**Hook:** `spec.flow`, `compiler.pipeline`  
**Status:** active  
**Delta:** [cartridge-compiler-v1.md](../../delta/20_micro/cartridge-compiler-v1.md)

## What

Build a local Python CLI that ingests markdown and plain-text files from `context-library/sources/`, normalizes them, chunks them with structure-aware splitting, writes JSON indexes, and emits a v1 cartridge skeleton under `cartridge/`.

## Why

The Planning Rosetta Stone and blueprint define a cartridge pipeline; v1 makes the first stage executable so agents can load `source-context.md` and indexes instead of re-parsing raw sources.

## Requirements

### R1 — Source discovery

- Scan `context-library/sources/` recursively.
- Accept `.md` and `.txt` in v1.
- Assign stable `doc_id` from SHA256 of repo-relative path.
- Record format, title (from first `# heading` or filename), content hash.

### R2 — Normalization

- Write canonical markdown to `context-library/normalized/markdown/<doc_id>.md`.
- Write metadata JSON to `context-library/normalized/metadata/<doc_id>.json`.
- Metadata follows [document-context-metadata-standard.md](../../document-context-metadata-standard.md).

### R3 — Chunking

- Split markdown on `#` headings; preserve heading path in chunk metadata.
- Target ~400 tokens (~1600 chars) with ~15% overlap for plain text fallback.
- Write chunks to chunk index (not separate files in v1).

### R4 — Indexing

- Update `context-library/indexes/document-index.json`.
- Update `context-library/indexes/chunk-index.json`.
- Idempotent re-ingest replaces prior entries for same `doc_id`.

### R5 — Cartridge emission

- `emit --feature <name>` writes:
  - `cartridge/manifest.json` (schema v1)
  - `cartridge/source-context.md` (top keyword-matched chunks for feature name)
- Does not overwrite `cartridge/holistic.md` if manually edited (skip if exists).

### R6 — CLI

```text
python -m hive_planner ingest [--root PATH]
python -m hive_planner emit --feature NAME [--root PATH]
python -m hive_planner status [--root PATH]
```

## Out of scope (v1)

- PDF, DOCX, HTML parsers
- Embedding retrieval
- Automatic Delta/spec generation from chunks

## Acceptance

All checkboxes in micro brief pass; pytest green.
