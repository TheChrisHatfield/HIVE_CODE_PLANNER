# Spec: cartridge-compiler-v2

**Hook:** `context.document_sourcing`, `compiler.pipeline`  
**Status:** active  
**Delta:** [cartridge-compiler-v2.md](../../delta/20_micro/cartridge-compiler-v2.md)

## What

Extend the cartridge compiler to ingest PDF and DOCX sources, enrich chunk metadata, and enforce tertiary retrieval limits on emit.

## Why

Rosetta hook `context.document_sourcing` requires format-agnostic tertiary context. v1 proved MD/TXT pipeline; v2 adds the next formats from [cartridge-document-sourcing-extension.md](../../cartridge-document-sourcing-extension.md).

## Requirements

### R1 — Format support

- Discover `.pdf` and `.docx` alongside `.md` and `.txt`.
- Route to format-specific normalizers via registry in `normalizer.py`.

### R2 — Optional dependencies

- `[pdf]` extra → `pymupdf`
- `[docx]` extra → `python-docx`
- Missing dep for a format → skip file with warning; do not abort ingest.

### R3 — PDF normalization

- Extract text per page; build markdown with `# Page N` sections.
- Metadata includes `format: pdf`, page count when available.
- Image-only / empty PDF → warning, skip (S2-B1).

### R4 — DOCX normalization

- Extract paragraphs and heading styles; preserve as markdown headings.
- No headings → chunk body text under document title (S2-B3).

### R5 — Chunk metadata

- `heading_path` uses ` > ` for nested headings.
- `page` field on chunks from PDF pages (optional int, default null/omitted).

### R6 — Emitter limits

- Max 3 source documents in `source-context.md`.
- Max 8 excerpt chunks total.

### R7 — Regression

- All v1 behavior and shared bug gate B1–B8 unchanged.

## Out of scope

HTML, CSV, PPTX, embeddings, cartridge holistic/macro auto-emission.
