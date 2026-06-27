# Tasks: cartridge-compiler-v1

**Hook:** `spec.flow` | Execute **one task at a time**

## Task 1 — Repo scaffold ✅

- [x] Delta docs (`00_holistic`, `10_macro`, `20_micro/cartridge-compiler-v1`)
- [x] Spec / plan / tasks
- [x] Cursor rules (architecture, task-execution, validation)
- [x] `context-library/` directory skeleton

## Task 2 — Core package + discovery/normalize ✅

- [x] `pyproject.toml` + `src/hive_planner/` package
- [x] `discovery.py` — scan MD/TXT
- [x] `normalizer.py` — write normalized markdown + metadata
- [x] Tests for discovery

## Task 3 — Chunker + indexer ✅

- [x] `chunker.py` — heading-aware chunks
- [x] `indexer.py` — document-index + chunk-index JSON
- [x] `cli ingest` command
- [x] Tests for chunker and ingest integration

## Task 4 — Emitter + status CLI ✅

- [x] `emitter.py` — manifest + source-context
- [x] `cli emit` and `cli status`
- [x] End-to-end validation per micro brief

## Active task

**None** — v1 complete. Next: PDF/DOCX normalization or Delta auto-seeding (v2).

## Validation log

```text
2026-06-21 — py -3.11 -m pytest: 4 passed
2026-06-21 — ingest: 1 doc, 3 chunks
2026-06-21 — emit cartridge-compiler-v1: manifest + source-context written
2026-06-21 — post-v1.0.0 bug audit (Stage 1)
- test_compiler.py: 17/17 PASS (+2 text normalizer tests for normalizers/text.py)
- Smoke: ingest + emit cartridge-compiler-v1 + status OK
```
