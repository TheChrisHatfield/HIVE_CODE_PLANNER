# Impact packet — PP-T10c q8 loader

**Date:** 2026-11-23  
**Hook:** `change.impact`, `change.validation`  
**Spec:** `docs/specs/PersonaPlex_migrate` PP11 / PP-T10c

## Change

`get_moshi_lm` auto-sets `quantize=True` and `copy_missing_weights=False` for q8 files, inits QLinear on the real device (not meta), coerces remaining floats to **fp16**, and `_cast_loaded_tensor` skips int8/uint8/`weight_scb`. Same cast on the offload helper; q8+`cpu_offload` still raises. Fat/Patch 1 expand still refuses non-float. One CUDA `QLinear` matmul proves no G7 SCB crash; a full 7B `LMGen.step` still needs `model.q8.safetensors` (PP-T10d).

## Primary

- `code-improvements/personaplex-migrate/moshi/moshi/models/loaders.py`

## Secondary

- `tests/test_personaplex_pp_t10c.py`

## Tests

- `tests/test_personaplex_pp_t10c.py`
