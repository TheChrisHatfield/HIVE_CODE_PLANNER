# Impact packet — PP-T10d CUDA graphs + streaming_sum

**Date:** 2026-11-23  
**Hook:** `change.impact`, `change.validation`  
**Spec:** `docs/specs/PersonaPlex_migrate` PP11.8 / G17 / PP-T10d

## Change

`LMGen` disables CUDA graphs when `NO_CUDA_GRAPH` is set. `cuda_graphs_enabled` / `step_meets_12_5_hz` live in working-copy `compile.py`. Record: graphs **with** a live sum argument **pass** on Tesla T10; 7B 12.5 Hz not measured. Default stays graphs on.

## Primary

- `code-improvements/personaplex-migrate/moshi/moshi/utils/compile.py`
- `code-improvements/personaplex-migrate/moshi/moshi/models/lm.py`

## Secondary

- `tests/test_personaplex_pp_t10d.py`
- `docs/specs/PersonaPlex_migrate/pp-t10d-graphs-record.md`

## Tests

- `tests/test_personaplex_pp_t10d.py`
