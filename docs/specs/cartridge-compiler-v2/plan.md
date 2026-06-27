# Plan: cartridge-compiler-v2

**Hook:** `compiler.pipeline`  
**Spec:** [spec.md](./spec.md)

## Approach

Add `src/hive_planner/normalizers/` package with `pdf.py`, `docx.py`, `text.py`. Keep v1 MD/TXT logic in `text.py`. Central `normalize_document()` dispatches by extension.

## Module changes

```text
src/hive_planner/
  normalizers/
    __init__.py
    text.py      # md, txt (extracted from normalizer.py)
    pdf.py       # pymupdf
    docx.py      # python-docx
  normalizer.py  # dispatch + write artifacts
  chunker.py     # nested headings, page-aware sections
  emitter.py     # doc/chunk limits
  models.py      # ChunkRecord.page optional
```

## Risks

| Risk | Mitigation |
|------|------------|
| pymupdf not installed on all machines | Optional extra + per-file skip |
| PDF text extraction quality | Normalize to markdown; warn on empty |
| ChunkRecord schema change breaks index load | Default `page=None`; tolerant parse |

## Validation

- `tests/test_formats.py` for PDF/DOCX fixtures (generated in tests)
- Existing `tests/test_compiler.py` for regression (B1–B8)
