<!--
meta:hook_id: context.cartridge_schema
meta:source: HIVE_PLANNING_DEV.md (Schema v1 + Document Sourcing updates)
meta:status: extracted
-->

# Cartridge Schema v1 (Updated)

This document extends [cartridge-schema-v1.md](./cartridge-schema-v1.md) with generalized source-document settings from the [Document Sourcing Extension](./cartridge-document-sourcing-extension.md).

Read **cartridge-schema-v1.md** first for core folder structure, manifest fields, and classification rules.

## Updates: generalized source context

Replace PDF-specific settings with generalized source settings in `manifest.json`:

```json
{
  "schema_version": "cartridge.v1",
  "source_context": {
    "enabled": true,
    "library_root": "context-library/sources",
    "normalized_root": "context-library/normalized",
    "max_documents_per_query": 3,
    "max_chunks_per_query": 8,
    "mode": "supplemental",
    "allowed_formats": ["md", "txt", "pdf", "docx", "html", "csv", "json", "pptx"]
  }
}
```

## New optional cartridge file

```text
/cartridge/source-context.md
```

Replaces PDF-only `pdf-context.md` for format-agnostic tertiary context.

## `source-context.md` format

```md
# Source Context

## Active documents
- architecture/system-design.docx
- policy/security-guidelines.md
- research/domain-notes.pdf

## Retrieved excerpts
### Source: architecture/system-design.docx
- <short excerpt summary>

### Source: policy/security-guidelines.md
- <short excerpt summary>

## Why relevant
- Clarifies architecture assumptions for the active planning cycle.
- Adds validation constraints relevant to the current feature.
```

## Classification rules for sourced material

- Promote to **Holistic** if mission, success criteria, or stable constraints
- Promote to **Macro** if architecture, subsystems, interfaces, or workflows
- Promote to **Micro** if task scope, edge cases, or acceptance criteria
- Promote to **Memory** only if durable, reusable operational rule
- Otherwise keep as tertiary context in `source-context.md` only

## Related

- [cartridge-schema-v1.md](./cartridge-schema-v1.md)
- [cartridge-document-sourcing-extension.md](./cartridge-document-sourcing-extension.md)
- [context-library-structure-guide.md](./context-library-structure-guide.md)
- [document-context-metadata-standard.md](./document-context-metadata-standard.md)
