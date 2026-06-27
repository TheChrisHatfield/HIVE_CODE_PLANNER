# Tasks: cartridge-compiler-v2

**Hook:** `spec.flow`

## Task 1 — Delta + spec ✅

- [x] Micro brief, spec, plan, tasks
- [x] Update `10_macro.md`, `20_micro/README.md`

## Task 2 — Normalizers + format registry ✅

- [x] `normalizers/text.py`, `pdf.py`, `docx.py`
- [x] Dispatch in `normalizer.py`
- [x] Optional deps in `pyproject.toml`

## Task 3 — Chunk metadata + emitter limits ✅

- [x] Nested heading paths, `page` field
- [x] Emitter max 3 docs / 8 excerpts

## Task 4 — Tests + bug gate ✅

- [x] `tests/test_formats.py` (S2-B1..S2-B5)
- [x] Regression B1–B8 (15 + 8 format tests = 23 passed)
- [x] Validation log below

## Active task

**None** — Stage 2 complete. Next: `change-impact-v1` (Stage 3).

## Validation log

```text
2026-06-21 — Stage 2 bug gate
  py -3.11 -m pytest -v → 23 passed
  B1–B8 regression via test_compiler.py
  S2-B1 empty PDF → test_empty_pdf_skipped
  S2-B2 corrupt PDF → test_corrupt_pdf_skipped
  S2-B3 DOCX no headings → test_docx_without_headings
  S2-B4 PDF re-ingest same doc_id → test_pdf_reingest_same_doc_id
  S2-B5 missing pymupdf → test_missing_pdf_dep_warning
  ingest: 1 doc, 3 chunks
  emit cartridge-compiler-v2: manifest + source-context
2026-06-21 — post-v1.0.0 bug audit (Stage 2)
- test_formats.py: 8/8 PASS; S2-B1..B5 verified
```
