<!--
meta:hook_id: compiler.pipeline
meta:source: HIVE_PLANNING_DEV.md
meta:status: extracted
-->

# Cartridge Compiler Implementation Guide

This guide describes how to implement a Cartridge Compiler that ingests multi-format source documents, normalizes them, builds retrievable context fragments, and emits cartridge files that feed Spec Kit, Cursor rules, and `AGENTS.md`. Multi-format ingestion pipelines commonly normalize heterogeneous files into consistent text or Markdown, preserve metadata, and build chunk-level retrieval indexes before generation or downstream use.[^9_1][^9_2][^9_3][^9_4]

## Architecture

A practical compiler has six stages:

1. **Source discovery**: scan `/context-library/sources/` and register supported files.
2. **Normalization**: convert original files into canonical Markdown or text.
3. **Segmentation**: split normalized content into semantically meaningful chunks.
4. **Metadata enrichment**: attach source, structure, version, and trust metadata.
5. **Retrieval indexing**: build searchable indexes for planning or coding-time lookup.
6. **Cartridge emission**: write `manifest.json`, Delta docs, spec seeds, and `source-context.md` outputs.

This design follows common RAG ingestion practice: clean the source, preserve logical structure, store metadata, and chunk content for later retrieval.[^9_1][^9_5][^9_6]

## Supported formats

Support a first-wave set of formats that can realistically appear in planning or reference workflows:

- Markdown and plain text.
- PDF and DOCX.
- HTML.
- CSV and JSON.
- PPTX when slides contain requirements or architecture material.

Multi-format document tools increasingly standardize on converting these heterogeneous sources into Markdown before chunking, which makes them easier for AI agents to read consistently.[^9_7][^9_2][^9_3][^9_8]

## Core modules

### Source registry

The registry scans the document library and assigns each source a stable `doc_id`. Chunking and re-indexing guidance recommends stable IDs plus document-level versioning so updated files can replace older chunks cleanly rather than accumulating duplicates.[^9_5][^9_6]

Example responsibilities:
- detect file type
- compute content hash
- assign `doc_id`
- record path and category
- compare with prior ingestion state

### Normalizer

The normalizer converts each file into a canonical representation. Best practice is to remove noise, preserve headings and lists, keep tables where relevant, and normalize encoding before chunking.[^9_1]

Suggested output files:
- `context-library/normalized/markdown/<doc_id>.md`
- `context-library/normalized/text/<doc_id>.txt`
- `context-library/normalized/metadata/<doc_id>.json`

### Chunker

Use structure-aware chunking first, with token limits as a fallback. Several ingestion references recommend preserving heading paths and semantic boundaries, then applying overlap around 10–20 percent to protect cross-boundary context.[^9_1][^9_5][^9_9]

Suggested defaults:
- target 300–500 tokens for general retrieval
- allow 100–256 tokens for precision-heavy policies or rules
- 10–20% overlap
- preserve full heading path in metadata

### Metadata enricher

Every chunk should carry enough metadata for filtering, debugging, and citation. Common recommendations include source path, title, section, location pointer, timestamp, and chunk index.[^9_1][^9_10][^9_6]

### Index builder

Build at least two indexes:
- a document index for file-level filtering and discovery
- a chunk index for passage retrieval

A lightweight v1 can use JSON plus embeddings or a local vector store. Retrieval guidance often recommends HNSW-style indexing with metadata filters when speed matters, but the first version can remain simple if the corpus is small.[^9_1]

### Cartridge emitter

The emitter compiles selected research and document-derived fragments into:
- `cartridge/manifest.json`
- `cartridge/research-summary.md`
- `cartridge/holistic.md`
- `cartridge/macro.md`
- `cartridge/micro/<feature>.md`
- `cartridge/memory.md`
- `cartridge/source-context.md`
- `cartridge/specs/<feature>.specseed.md`

## Suggested implementation flow

```text
scan sources
  -> normalize files
  -> extract metadata
  -> create chunks
  -> embed/index chunks
  -> classify chunks by context role
  -> retrieve top chunks for current feature
  -> emit cartridge outputs
  -> compile into Delta docs / Spec Kit artifacts / AGENTS candidates
```


## Pseudocode

```python
for file in discover_sources(root):
    doc = register_source(file)
    norm = normalize(doc)
    meta = extract_metadata(norm)
    chunks = chunk(norm, meta)
    store_normalized(doc, norm, meta, chunks)
    update_indexes(doc, meta, chunks)

feature_query = build_feature_query(active_spec, active_task, delta_docs)
retrieved = retrieve_relevant_chunks(feature_query, top_docs=3, top_chunks=8)
classified = classify_retrieved_chunks(retrieved)
cartridge = emit_cartridge(classified, active_feature)
compile_outputs(cartridge)
```


## Integration with Spec Kit and Cursor

Use the compiler as a pre-planning and just-in-time context service. Cursor rules and memory-bank style files provide stable operating context, while the compiler supplies selectively retrieved tertiary context that can be distilled into spec or task artifacts only when useful.[^9_11][^9_12][^9_13][^9_14]

Integration points:

- before `/specify`, inject relevant source-derived constraints into the draft spec
- before `/plan`, attach architecture or policy excerpts if they affect implementation
- during coding, expose `source-context.md` only on demand
- after validation, promote durable reusable lessons into `AGENTS.md`


## v1 implementation priorities

Build the first version in this order:

1. Markdown/TXT/PDF/DOCX normalization.
2. Metadata extraction and stable IDs.
3. Structure-aware chunking.
4. JSON-based document and chunk indexes.
5. Cartridge emission for one feature.
6. Optional embedding retrieval and ranking refinement.

This sequencing keeps the first version simple and reviewable while still matching proven ingestion patterns used in production-style RAG systems.[^9_1][^9_5][^9_4]
<span style="display:none">[^9_15][^9_16]</span>

<div align="center">⁂</div>

[^9_1]: https://dev.to/derrickryangiggs/rag-pipeline-deep-dive-ingestion-chunking-embedding-and-vector-search-2877

[^9_2]: https://apify.com/codepoetry/markdown-rag-chunker

[^9_3]: https://mcpmarket.com/server/document-converter-2

[^9_4]: https://app.readytensor.ai/publications/multi-source-rag-a-unified-pipeline-for-text-pdf-json-and-csv-ingestion-sKGQo2Qzap2U

[^9_5]: https://engineersofai.com/docs/ai-engineering/rag-engineering/document-ingestion-and-chunking

[^9_6]: https://amestris.com.au/blog/rag-ingestion-pipeline.html

[^9_7]: https://github.com/marc-shade/docsingest

[^9_8]: https://github.com/xiuxinY/file2md

[^9_9]: https://medium.com/@aleum.yu/document-ingestion-for-rag-parsing-and-processing-enhancing-ai-with-knowledge-ii-8c2dd8702f51

[^9_10]: https://medium.com/@kakadechaitanya77/the-rag-pipeline-a-guide-to-prompts-ingestion-and-chunking-e2da562daefe

[^9_11]: https://dev.to/pockit_tools/mastering-cursor-rules-the-ultimate-guide-to-cursorrules-and-memory-bank-for-10x-developer-alm

[^9_12]: https://gist.github.com/ipenywis/1bdb541c3a612dbac4a14e1e3f4341ab

[^9_13]: https://www.lullabot.com/articles/supercharge-your-ai-coding-cursor-rules-and-memory-banks

[^9_14]: https://github.com/vanzan01/cursor-memory-bank

[^9_15]: 1000002308.jpg

[^9_16]: https://www.reddit.com/r/cursor/comments/1jkfp7m/memory_bank_for_cursor/


---