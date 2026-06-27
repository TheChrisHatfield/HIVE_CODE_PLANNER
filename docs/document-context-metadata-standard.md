<!--
meta:hook_id: context.metadata
meta:source: HIVE_PLANNING_DEV.md (Cartridge Document Sourcing Extension)
meta:status: extracted
-->

# Document Context Metadata Standard

Metadata rules for source-derived documents and chunks in the context library.

## Document metadata (example)

```json
{
  "source_path": "context-library/sources/architecture/system-design.docx",
  "normalized_path": "context-library/normalized/markdown/system-design.md",
  "document_type": "architecture",
  "format": "docx",
  "title": "System Design",
  "last_updated": "2026-06-21",
  "trust_level": "high"
}
```

## Required fields

| Field | Purpose |
|-------|---------|
| `source_path` | Original file location |
| `normalized_path` | Canonical normalized output |
| `document_type` | Category (architecture, requirements, research, etc.) |
| `format` | Original format (md, pdf, docx, etc.) |
| `title` | Human-readable title |
| `last_updated` | Version / freshness |
| `trust_level` | high / medium / low |

## Chunk metadata

For each normalized document chunk, capture:

- source path
- normalized path
- title
- format
- document class
- section heading (if available)
- page or slide number (if relevant)
- keywords
- last updated date
- trust level
- chunk text

## Promotion metadata

When a chunk influences cartridge or repo truth, record:

- promotion target (holistic / macro / micro / memory)
- promotion date
- reviewing agent or human
- linked hook IDs

## Storage

- Document records: `context-library/normalized/metadata/<doc_id>.json`
- Chunk indexes: `context-library/indexes/chunk-index.json`
- Document index: `context-library/indexes/document-index.json`

Prefer JSON or JSONL — keep schemas simple enough for automation.

## Related

- [context-library-structure-guide.md](./context-library-structure-guide.md)
- [cartridge-document-sourcing-extension.md](./cartridge-document-sourcing-extension.md)
