# Impact packet — PP-T10b personaplex_q8_local

**Date:** 2026-11-23  
**Hook:** `change.impact`, `change.validation`  
**Spec:** `docs/specs/PersonaPlex_migrate` PP11 / PP-T10b

## Change

CodeSpec closes the dedicated export script contracts: local `.safetensors` only, `copy_missing_weights=True` then `replace_linear_with_qlinear` **once** on `LMModel`, no Mimi/HF/`fuse_lora`, `quantize: true` in PersonaPlex JSON. Live one-pass write of `model.q8.safetensors` still needs a ≥48 GB GPU (this box: Tesla T10 ~17 GB; 16.7 GB bf16 file is present). Operator **go** for the A40 remains `docs/specs/PersonaPlex_migrate/runpod-q8-checklist.md`.

## Primary

- `scripts/personaplex_q8_local.py` (already scaffolded; contracts proven)

## Secondary

- `tests/test_personaplex_pp_t10b.py`

## Tests

- `tests/test_personaplex_pp_t10b.py`

## Spec

No new product behavior. PP-T10c–e still need the q8 file on GPU.
