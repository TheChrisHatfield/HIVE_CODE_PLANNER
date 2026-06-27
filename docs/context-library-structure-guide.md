<!--
meta:hook_id: context.library
meta:source: HIVE_PLANNING_DEV.md (Cartridge Document Sourcing Extension)
meta:status: extracted
-->

# Context Library Structure Guide

Centralized document library layout for tertiary context retrieval.

## Role

The context library supplies **tertiary context** during planning or prototyping. It must not replace Delta docs, active specs, tasks, or `AGENTS.md`.

## Directory layout

```text
/context-library/
  manifest.json
  /sources
    architecture/
    requirements/
    research/
    reference/
    policy/
    product/
  /normalized
    markdown/
    text/
    metadata/
  /indexes
    document-index.json
    chunk-index.json
```

## Design principles

- Separate **original sources** from **normalized outputs** and **indexes**.
- Organize sources by category (architecture, requirements, research, reference, policy, product).
- Normalize every format to markdown or text before indexing.
- Keep stable IDs and versioning for re-ingestion.

## Normalization outputs

For each source document:

- canonical markdown file
- raw extracted text if needed
- metadata record
- chunked excerpts for retrieval

Paths:

```text
context-library/normalized/markdown/<doc_id>.md
context-library/normalized/text/<doc_id>.txt
context-library/normalized/metadata/<doc_id>.json
```

## Retrieval policy

Query the library only when extra grounding is needed:

- architecture ambiguity
- regulated or policy-heavy work
- missing domain detail in the spec
- implementation uncertainty during prototyping
- need to validate against a source requirement

## Classification before promotion

When a source excerpt is retrieved:

- **Holistic** — mission, success criteria, stable constraints
- **Macro** — architecture, subsystems, interfaces, workflows
- **Micro** — task scope, edge cases, acceptance criteria
- **Memory** — durable, reusable operational rules
- **Otherwise** — keep as tertiary context in `source-context.md` only

## Related

- [cartridge-document-sourcing-extension.md](./cartridge-document-sourcing-extension.md)
- [document-context-metadata-standard.md](./document-context-metadata-standard.md)
- [cartridge-compiler-implementation.md](./cartridge-compiler-implementation.md)
