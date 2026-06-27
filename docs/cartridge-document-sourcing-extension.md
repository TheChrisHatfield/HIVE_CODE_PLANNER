<!--
meta:hook_id: context.document_sourcing
meta:source: HIVE_PLANNING_DEV.md
meta:status: extracted
-->

# Cartridge Document Sourcing Extension

This extension replaces the PDF-specific context layer with a generalized document-sourcing layer for the same tertiary reference role. The design fits Cursor’s scoped context model, where rules can be always included, auto-attached, or agent-requested, and it also fits the broader spec-driven idea that high-level context documents and memory-bank files support execution without replacing the active spec and task artifacts.[^8_1][^8_2][^8_3]

## Intent

The goal is to support a centralized document library that can supply **same-level tertiary context** during planning or prototyping, regardless of whether the source is PDF, Markdown, DOCX, TXT, HTML, CSV, or another supported document format. This context is optional and reference-oriented: it should help the agent stay grounded, recover missing detail, or surface useful insights without becoming the primary execution source.[^8_4][^8_5][^8_6]

## Tertiary context role

Use a three-tier context model:

- **Primary context**: Delta docs, active `spec.md`, `plan.md`, `tasks.md`, and feature micro briefs.
- **Secondary context**: `AGENTS.md`, Cursor rules, constitution or memory-bank documents.
- **Tertiary context**: source-derived excerpts from the centralized document library.

This follows the distinction between active task specifications and broader memory-bank or constitution files that support work across sessions.[^8_2][^8_3][^8_7]

## Supported source types

The document layer should be format-agnostic. Public document-ingestion systems commonly support heterogeneous inputs such as PDF, DOCX, TXT, Markdown, HTML, CSV, and related formats, which makes a unified source-library design practical.[^8_4][^8_6][^8_8][^8_9]

Recommended first-wave source types:

- Markdown (`.md`)
- Plain text (`.txt`)
- PDF (`.pdf`)
- Word (`.docx`)
- HTML (`.html`, `.htm`)
- CSV (`.csv`)
- PowerPoint (`.pptx`) if used as requirements or planning material
- JSON (`.json`) if it contains structured policy or configuration context


## Centralized directory

Use a neutral directory such as:

```text
/context-library/sources/
```

Recommended structure:

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

This structure separates original documents from normalized outputs and indexing metadata, which is consistent with common ingestion workflows that first parse documents, then normalize them into text or markdown before retrieval.[^8_5][^8_9]

## Normalization model

Every source document should be converted into a common normalized representation so the rest of the cartridge system does not care about the original format. A practical standard is markdown plus metadata because markdown is readable by humans, Git-friendly, and easy for agents to consume.[^8_5][^8_7]

Normalization outputs:

- canonical markdown file
- raw extracted text if needed
- metadata record
- chunked excerpts for retrieval

Example metadata:

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


## Cartridge changes

Replace the PDF-specific settings with generalized source settings in `manifest.json`:

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

Add a generalized optional cartridge file:

```text
/cartridge/source-context.md
```


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

### Source: research/domain-notes.pdf
- <short excerpt summary>

## Why relevant
- Clarifies architecture assumptions for the active planning cycle.
- Adds validation constraints relevant to the current feature.
- Supplies background detail useful during prototyping.
```


## Retrieval policy

The agent should query the source library only when extra grounding is needed. Cursor rules support agent-requested and auto-attached context patterns, which means this document layer is best used as selective retrieval rather than unconditional prompt stuffing.[^8_1][^8_10][^8_11]

Good triggers:

- architecture ambiguity
- regulated or policy-heavy work
- missing domain detail in the spec
- implementation uncertainty during prototyping
- need to validate against a source requirement


## Classification rules for sourced material

When a source excerpt is retrieved, classify it before promotion:

- Promote to Holistic if it defines mission, success criteria, or stable constraints.
- Promote to Macro if it defines architecture, subsystems, interfaces, or workflows.
- Promote to Micro if it defines exact task scope, edge cases, or acceptance criteria.
- Promote to Memory only if it is a durable, reusable operational rule.
- Otherwise keep it as tertiary context in `source-context.md` only.

This preserves a clean separation between reference material and execution truth.[^8_2][^8_3]

## Indexing recommendations

For each normalized document or chunk, capture:

- source path
- normalized path
- title
- format
- document class
- section heading if available
- page or slide number if relevant
- keywords
- last updated date
- trust level
- chunk text

Heterogeneous document-ingestion workflows commonly rely on chunking plus metadata so queries can retrieve relevant grounded passages later.[^8_5][^8_6][^8_8]

## Example planning flow

```text
Perplexity research
  -> translator builds cartridge
  -> planner checks for ambiguity or missing domain detail
  -> source retriever searches centralized document library
  -> top excerpts written to source-context.md
  -> distilled findings update Delta docs or spec artifacts
  -> coding agent reads primary context first and tertiary context only if needed
```


## Example policy for AGENTS or rules

```md
- Use centralized source documents only as tertiary context.
- Prefer normalized markdown excerpts over raw original files when possible.
- Never replace active specs or tasks with raw source excerpts.
- Distill reused source findings into Delta docs, specs, or durable memory.
- Keep retrieved excerpts short and source-labeled.
```


## Recommended v1 limits

- Maximum 3 source documents per retrieval cycle.
- Maximum 8 excerpts inserted into working context.
- Prefer normalized markdown over raw binary formats.
- Preserve source path and section or page metadata.
- Treat tertiary context as advisory unless promoted into primary artifacts.

These limits help the agent benefit from supplemental source material without losing task focus.[^8_7][^8_9]

## Outcome

With this change, the cartridge system no longer depends on PDF as the special case. Instead, it gains a generalized document-sourcing layer that can pull from many file types while preserving the same tertiary-context role you wanted: useful reference from source material during planning and prototyping, without overwhelming the main task loop.[^8_4][^8_6][^8_1]istic.md
/docs/delta/10_macro.md
/docs/delta/20_micro/blueprint-loader.md
/docs/specs/blueprint-loader/spec.md
/docs/specs/blueprint-loader/plan.md
/docs/specs/blueprint-loader/tasks.md
AGENTS.md
.cursor/rules/architecture.mdc

```

## Governance model

Treat the cartridge as a reviewed transport object, not a hidden prompt cache. Git should carry the cartridge so the same structured context can be loaded by humans, agents, CI workflows, and future sessions. This aligns with your “Nintendo cartridge” analogy: the repo is the console, and the cartridge is the portable structured knowledge pack the system knows how to read.

## Recommended v1 implementation path

1. Start with markdown cartridge files and one `manifest.json`.
2. Build a simple translator that classifies text into Holistic, Macro, Micro, Memory, or Reject.
3. Emit spec seeds for one feature at a time.
4. Promote only reviewed memory candidates into `AGENTS.md`.
5. Add automation later for compilation and CI checks.

That path keeps the first version simple, reviewable, and compatible with Spec Kit and Cursor’s current context mechanisms.[cite:12][cite:47][cite:46]


## Document sourcing extension

A generalized source-document library can be added as an optional tertiary-context source for planning and selective prototyping support. The detailed design is provided in the companion document `cartridge-document-sourcing-extension.md`, which describes a shared `/context-library/sources/` layout, normalization and indexing flow, `source-context.md` as an optional cartridge file, and rules for using retrieved excerpts only as supplemental context rather than replacing active specs or tasks.[cite:53][cite:58][cite:74][cite:76]
<span style="display:none">[^8_12][^8_13][^8_14][^8_15]</span>

<div align="center">⁂</div>

[^8_1]: https://docs.cursor.com/ko/context/rules
[^8_2]: https://martinfowler.com/articles/exploring-gen-ai/sdd-3-tools.html
[^8_3]: https://specs.md/core-concepts/memory-bank
[^8_4]: https://mariadb.com/docs/tools/mariadb-ai-rag/reference/supported-formats
[^8_5]: https://mintlify.wiki/mastra-ai/mastra/rag/ingestion
[^8_6]: https://app.readytensor.ai/publications/rag-assistant-multi-interface-document-qa-system-5sbXqd2wIQkt
[^8_7]: https://tweag.github.io/agentic-coding-handbook/WORKFLOW_MEMORY_BANK/
[^8_8]: https://www.youtube.com/watch?v=58IKTvLpnlc
[^8_9]: https://github.com/saleemh/doc-ingestor
[^8_10]: https://docs.cursor.com/id/context/rules
[^8_11]: https://docs.cursor.com/en/context/@-symbols/@-cursor-rules
[^8_12]: https://docs.cursor.com/ja/context/rules
[^8_13]: https://www.cursorforpms.com/fundamentals/project-rules
[^8_14]: https://nierbeck.de/2026/02/spec-driven-development/
[^8_15]: https://www.reddit.com/r/kilocode/comments/1nkd64v/memory_bank_speckit/

---