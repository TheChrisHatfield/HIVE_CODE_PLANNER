# Spec: cartridge-compiler-v3

**Hook:** `context.document_sourcing`, `compiler.pipeline`  
**Status:** active  
**Delta:** [cartridge-compiler-v3.md](../../delta/20_micro/cartridge-compiler-v3.md)

## What

Extend the cartridge compiler to ingest HTML, CSV, and PPTX sources using the same discover → normalize → chunk → index → emit pipeline as v2.

## Why

v2 added PDF/DOCX. Rosetta hook `context.document_sourcing` and [cartridge-compiler-implementation.md](../../cartridge-compiler-implementation.md) list HTML, CSV, and PPTX as first-wave formats.

## Requirements

### R1 — Format support

- Discover `.html`, `.htm`, `.csv`, `.pptx` alongside existing formats.
- Route to format-specific normalizers via registry in `normalizer.py`.

### R2 — Optional dependencies

- `[html]` extra → `beautifulsoup4`
- `[pptx]` extra → `python-pptx`
- CSV uses stdlib only.
- Missing dep for a format → skip file with warning; do not abort ingest.

### R3 — HTML normalization

- Parse HTML; extract `<title>` or first `<h1>` for title.
- Convert headings and body text to markdown.
- Script/style stripped; empty body → warning, skip (S4A-B1).

### R4 — CSV normalization

- Read rows with stdlib `csv`.
- First row as headers when multiple columns; render as markdown table.
- Single-column or headerless files → body paragraphs under document title (S4A-B3).

### R5 — PPTX normalization

- Extract slide titles and text shapes per slide.
- Markdown structure: `# Title`, `## Slide N`, slide body.
- Empty deck → warning, skip.

### R6 — Chunk metadata

- Nested `heading_path` unchanged from v2.
- PPTX `## Slide N` sections chunk like PDF `## Page N`.

### R7 — Emitter limits

- Max 3 source documents in `source-context.md`.
- Max 8 excerpt chunks total.

### R8 — Regression

- All v1/v2 behavior and shared bug gate B1–B8 unchanged.

## Out of scope

Embeddings, cartridge translator, CI AGENTS.md automation, JSON normalizer.
