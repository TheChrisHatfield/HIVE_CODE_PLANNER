# Impact packet — PP-T10a QLinear port

**Date:** 2026-11-23  
**Hook:** `change.impact`, `change.validation`  
**Spec:** `docs/specs/PersonaPlex_migrate` PP11 / PP-T10a

## Change

Working-copy QLinear matches moshi-rag plus G7 `weight_scb.float()`. `LMModel(quantize=)` and `StreamingTransformer` layer-by-layer replace run in `__init__` before `LMGen` CUDA graphs. Diff recorded in `docs/specs/PersonaPlex_migrate/q8-quantize-diff-pp-t10a.md`. Export GPU path is still PP-T10b.

## Primary

- `code-improvements/personaplex-migrate/moshi/moshi/utils/quantize.py`
- `code-improvements/personaplex-migrate/moshi/moshi/models/lm.py`
- `code-improvements/personaplex-migrate/moshi/moshi/modules/transformer.py`

## Secondary

- `tests/test_personaplex_q8_forward.py`
- `docs/specs/PersonaPlex_migrate/q8-quantize-diff-pp-t10a.md`

## Tests

- `tests/test_personaplex_q8_forward.py::test_pp_t10a_qlinear_g7_and_replace_twice`

## Spec

No new product behavior. PP-T10b–e remain open.
