# Sample reference: Planning Rosetta Stone usage

This file lives in the context library as a **tertiary source** example.

When you run `python -m hive_planner ingest`, the compiler should:

1. Discover this file under `context-library/sources/`
2. Normalize it to `context-library/normalized/markdown/<doc_id>.md`
3. Chunk by `#` headings
4. Include excerpts in `cartridge/source-context.md` when relevant to a feature query

## Keywords for retrieval testing

cartridge compiler ingest normalize chunk index manifest rosetta stone planning

## Related hooks

- `planning.rosetta`
- `compiler.pipeline`
- `context.library`
