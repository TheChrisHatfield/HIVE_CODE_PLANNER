# Plan: cartridge-compiler-v1

**Hook:** `compiler.pipeline`  
**Spec:** [spec.md](./spec.md)

## Approach

Python package `hive_planner` with small single-purpose modules. No external deps for v1 core (stdlib only). Optional `pytest` for dev.

## Module layout

```text
src/hive_planner/
  config.py      # paths relative to repo root
  models.py      # dataclasses: SourceDoc, Chunk, indexes
  discovery.py   # scan sources/
  normalizer.py  # read md/txt, write normalized + metadata
  chunker.py     # heading-aware + overlap chunking
  indexer.py     # read/write JSON indexes
  emitter.py     # cartridge manifest + source-context
  cli.py         # argparse entry
  __main__.py
```

## Risks

| Risk | Mitigation |
|------|------------|
| Windows path handling | Use `pathlib` throughout; root from cwd or `--root` |
| Large files | Stream read; cap chunk count per doc with warning |
| Keyword retrieval too naive | Document as v1 limitation; embeddings in v2 |

## Validation strategy

- Unit tests: discovery filters, chunker heading paths, indexer merge
- Integration: ingest sample source → assert indexes populated
- Manual: emit cartridge-compiler-v1 → inspect manifest + source-context

## Dependencies

- Python 3.10+
- pytest (dev only)
