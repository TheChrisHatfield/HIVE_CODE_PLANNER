# Impact packet — PP-T10e SC-PP6 judge

**Date:** 2026-11-23  
**Hook:** `change.impact`, `change.validation`  
**Spec:** `docs/specs/PersonaPlex_migrate` PP11.9 / G162 / PP-T10e

## Change

Text-token judge for the R49/R50 ladder: same prompt/WAV, bf16 offline vs q8 offline vs q8 live. Gap notes, moshika-rag weights, `moshi_rag_q8_local`, and cpu-offload cannot pass. Live WAV comparison is not executed (no q8 file); SC-PP6 stays fail-closed.

## Primary

- `scripts/personaplex_sc_pp6_judge.py`

## Secondary

- `tests/test_personaplex_pp_t10e.py`
- `docs/specs/PersonaPlex_migrate/pp-t10e-sc-pp6-record.md`

## Tests

- `tests/test_personaplex_pp_t10e.py`
