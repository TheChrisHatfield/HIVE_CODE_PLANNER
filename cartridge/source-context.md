# Source Context

**Feature:** `cartridge-pack-v1`
**Generated:** 2026-06-27T03:31:59.281186+00:00
**Limits:** max 3 documents, max 8 excerpts

## Active documents
- context-library/sources/reference/rosetta-usage-sample.md — Sample reference: Planning Rosetta Stone usage

## Retrieved excerpts

### Source: context-library/sources/reference/rosetta-usage-sample.md (Sample reference: Planning Rosetta Stone usage > Keywords for retrieval testing)
- ## Keywords for retrieval testing  cartridge compiler ingest normalize chunk index manifest rosetta stone planning

### Source: context-library/sources/reference/rosetta-usage-sample.md (Sample reference: Planning Rosetta Stone usage)
- # Sample reference: Planning Rosetta Stone usage  This file lives in the context library as a **tertiary source** example.  When you run `python -m hive_planner ingest`, the compiler should:  1. Discover this file under `context-library/sources/` 2. Normalize it to `context-library/normalized/markdown/<doc_id>.md` 3. Chunk by `#` headings 4. Include excerpts in `cartridge/source-context.md` whe...

### Source: context-library/sources/reference/rosetta-usage-sample.md (Sample reference: Planning Rosetta Stone usage > Related hooks)
- ## Related hooks  - `planning.rosetta` - `compiler.pipeline` - `context.library`

## Why relevant
- Tertiary context retrieved by hybrid keyword/embedding match for the active feature.
- Does not override Delta docs, spec, plan, or tasks.

## Hooks
- `planning.rosetta`
- `compiler.pipeline`
- `context.document_sourcing`
