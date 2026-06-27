# Tasks: cartridge-compiler-v3

**Hook:** `spec.flow`

## Task 1 — Delta + spec ✅

- [x] Micro brief, spec, plan, tasks
- [x] Update `20_micro/README.md`, `AGENTS.md`

## Task 2 — Normalizers + registry ✅

- [x] `normalizers/html.py`, `csv.py`, `pptx.py`
- [x] Dispatch in `normalizer.py`
- [x] Optional deps in `pyproject.toml`
- [x] `SUPPORTED_EXTENSIONS` in `config.py`

## Task 3 — Chunk metadata ✅

- [x] `Slide N` heading recognized in chunker (mirror Page N)

## Task 4 — Tests + bug gate ✅

- [x] `tests/test_formats_v3.py` (S4A-B1..S4A-B5)
- [x] Full pytest regression
- [x] Validation log below

## Active task

**None** — Stage 4A complete. Next: `cartridge-translator-v1` (Stage 4B).

## Bug gate (Stage 4A)

| Check | Test |
|-------|------|
| S4A-B1 empty HTML | `test_empty_html_skipped` |
| S4A-B2 corrupt / missing dep | `test_corrupt_html_skipped`, `test_missing_html_dep_warning` |
| S4A-B3 headerless CSV | `test_csv_without_headers` |
| S4A-B4 stable doc_id | `test_html_reingest_same_doc_id` |
| S4A-B5 full regression | all pytest |

## Validation log

```text
2026-06-21 — Stage 4A bug gate
  py -3.11 -m pytest -v → 36 passed (B1–B8 + S2 + S3 + S4A)
  S4A-B1 empty HTML → test_empty_html_skipped
  S4A-B2 corrupt/missing dep → test_corrupt_html_skipped, test_missing_html_dep_warning
  S4A-B3 headerless CSV → test_csv_without_headers
  S4A-B4 stable doc_id → test_html_reingest_same_doc_id
  S4A-B5 full regression → 36 passed
  emit cartridge-compiler-v3: manifest + source-context
2026-06-21 — post-v1.0.0 bug audit (Stage 4A)
- test_formats_v3.py: 10/10 PASS; S4A-B1..B5 verified
```
