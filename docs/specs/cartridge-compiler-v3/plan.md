# Plan: cartridge-compiler-v3

**Hook:** `compiler.pipeline`  
**Spec:** [spec.md](./spec.md)

## Approach

Add `html.py`, `csv.py`, `pptx.py` under `normalizers/`. Extend `_dispatch_normalize()` in `normalizer.py`. CSV needs no optional extra; HTML and PPTX mirror v2 optional-dep pattern.

## Module changes

```text
src/hive_planner/
  normalizers/
    html.py      # beautifulsoup4
    csv.py       # stdlib csv
    pptx.py      # python-pptx
  normalizer.py  # dispatch html/htm/csv/pptx
  config.py      # SUPPORTED_EXTENSIONS
  chunker.py     # recognize Slide N in page metadata (optional)
  pyproject.toml # [html], [pptx] extras; extend [formats]
tests/
  test_formats_v3.py  # S4A-B1..S4A-B5
```

## Risks

| Risk | Mitigation |
|------|------------|
| HTML parsing variance | beautifulsoup4 + get_text; skip empty |
| Wide CSV rows | Cap displayed columns in normalized markdown; full text in raw |
| python-pptx not installed | Optional extra + per-file skip |
| Slide vs Page chunk metadata | Extend `_page_from_heading` to match `Slide N` |

## Validation

- `tests/test_formats_v3.py` for HTML/CSV/PPTX fixtures
- Existing `tests/test_compiler.py` + `tests/test_formats.py` for regression (B1–B8)
